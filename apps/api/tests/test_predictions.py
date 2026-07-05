from datetime import date

from sqlalchemy import select

from saig.modules.fieldops.models import ProductionRecord
from saig.modules.predictions.models import SalesHistory
from saig.modules.predictions.service import TrainingService
from tests.conftest import TestContext
from tests.helpers import (
    make_crop_cycle,
    make_farm,
    make_farmer,
    make_field,
    make_variety,
)


async def _seed_training_data(ctx: TestContext, token: str) -> tuple[str, str, str]:
    """Creates a farmer/farm/field + variety, plus historical production and
    sales rows, then returns (region_id, variety_id, crop_cycle_id)."""
    region = (await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token), json={"name": "Rift", "code": "RIFT"}
    )).json()["id"]
    variety = await make_variety(ctx, token)
    farmer = await make_farmer(ctx, token)
    farm = await make_farm(ctx, token, farmer)
    field = await make_field(ctx, token, farm)
    cycle = await make_crop_cycle(ctx, token, field, variety)

    # Historical production + sales inserted directly (bulk fixtures).
    async with ctx.session_factory() as session:
        for i in range(12):
            session.add(ProductionRecord(
                farmer_id=farmer, season=f"S{i}", variety_id=variety,
                area_ha=2.0, yield_kg=2.0 * (5000 + i * 50), source="migrated",
            ))
        for m in range(24):
            month = date(2024 + m // 12, m % 12 + 1, 1)
            session.add(SalesHistory(
                organization_id=ctx.org_id, region_id=region, variety_id=variety,
                period_month=month, quantity_kg=1000 + 30 * m, channel="direct",
            ))
        await session.commit()
    return region, variety, cycle


async def _train(ctx: TestContext) -> None:
    async with ctx.session_factory() as session:
        training = TrainingService(session)
        await training.train_yield(ctx.org_id, None)
        await training.train_demand(ctx.org_id, None)


async def test_yield_training_scoring_and_lineage(ctx: TestContext):
    token = await ctx.login()
    _region, _variety, cycle = await _seed_training_data(ctx, token)
    await _train(ctx)

    # rescore active cycles
    res = await ctx.client.post(
        "/api/v1/predictions/yield/rescore", headers=ctx.auth(token), json={}
    )
    assert res.status_code == 202, res.text
    assert res.json()["count"] >= 1

    # read the prediction for the cycle
    res = await ctx.client.get(
        "/api/v1/predictions/yield", headers=ctx.auth(token),
        params={"cropCycleId": cycle},
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    pred = rows[0]
    assert pred["predictedYieldKgHa"] > 0
    assert pred["piLowKgHa"] <= pred["predictedYieldKgHa"] <= pred["piHighKgHa"]
    assert 0 <= pred["confidence"] <= 1


async def test_demand_forecast_horizon_and_intervals(ctx: TestContext):
    token = await ctx.login()
    region, variety, _cycle = await _seed_training_data(ctx, token)
    await _train(ctx)

    res = await ctx.client.post("/api/v1/forecasts/demand/run", headers=ctx.auth(token))
    assert res.status_code == 202
    assert res.json()["count"] == 12  # one regionxvariety x 12 months

    res = await ctx.client.get(
        "/api/v1/forecasts/demand", headers=ctx.auth(token),
        params={"regionId": region, "varietyId": variety},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["points"]) == 12
    for p in body["points"]:
        assert p["piLowKg"] <= p["forecastQtyKg"] <= p["piHighKg"]


async def test_models_registry_lists_promoted(ctx: TestContext):
    token = await ctx.login()
    await _seed_training_data(ctx, token)
    await _train(ctx)

    res = await ctx.client.get("/api/v1/models", headers=ctx.auth(token))
    assert res.status_code == 200
    models = res.json()
    names = {m["modelName"]: m for m in models}
    assert "yield" in names and "demand" in names
    assert names["yield"]["status"] == "promoted"
    assert "mae" in names["yield"]["metrics"]


async def test_serving_without_model_is_domain_error(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.post(
        "/api/v1/predictions/yield/rescore", headers=ctx.auth(token), json={}
    )
    assert res.status_code == 422
    assert "promoted" in res.json()["detail"]


async def test_retraining_retires_previous_version(ctx: TestContext):
    token = await ctx.login()
    await _seed_training_data(ctx, token)
    await _train(ctx)
    await _train(ctx)  # train again

    async with ctx.session_factory() as session:
        rows = (
            await session.execute(
                select(SalesHistory)  # touch to keep session; then query models
            )
        )
        assert rows is not None
    res = await ctx.client.get(
        "/api/v1/models", headers=ctx.auth(token), params={"name": "yield"}
    )
    versions = res.json()
    promoted = [m for m in versions if m["status"] == "promoted"]
    retired = [m for m in versions if m["status"] == "retired"]
    assert len(promoted) == 1  # only one promoted at a time
    assert len(retired) >= 1


async def test_demand_accuracy_backtest(ctx: TestContext):
    token = await ctx.login()
    _region, _variety, _cycle = await _seed_training_data(ctx, token)
    # 24 months of clean seasonal-ish data → backtest should evaluate the segment
    res = await ctx.client.get("/api/v1/forecasts/demand/accuracy", headers=ctx.auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body["segmentsEvaluated"] == 1
    assert body["pointsEvaluated"] > 0
    assert body["mape"] is not None and body["mape"] >= 0


async def test_yield_accuracy_empty_without_harvest(ctx: TestContext):
    token = await ctx.login()
    await _seed_training_data(ctx, token)
    res = await ctx.client.get("/api/v1/predictions/yield/accuracy", headers=ctx.auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body["cyclesEvaluated"] == 0
    assert body["mape"] is None


async def test_forecasts_permission_and_isolation(ctx: TestContext):
    # A viewer can read forecasts but not trigger runs
    viewer = await ctx.login("viewer@example.com")
    res = await ctx.client.post(
        "/api/v1/forecasts/demand/run", headers=ctx.auth(viewer)
    )
    assert res.status_code == 403

    # Cross-org read yields no data (org-scoped registry → domain error on run)
    other = await ctx.login("admin2@example.com")
    res = await ctx.client.post(
        "/api/v1/predictions/yield/rescore", headers=ctx.auth(other), json={}
    )
    assert res.status_code == 422  # other org has no promoted model
