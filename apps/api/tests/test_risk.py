from saig.modules.risk import scoring
from tests.conftest import TestContext
from tests.helpers import (
    make_crop_cycle,
    make_farm,
    make_farmer,
    make_field,
    make_variety,
)

# --- pure scoring ------------------------------------------------------------

def test_climate_scoring_bands():
    calm = scoring.score_climate(0, 80.0, data_available=True)
    assert calm.score < 40
    severe = scoring.score_climate(10, 0.0, data_available=True)
    assert severe.score >= 70
    unknown = scoring.score_climate(0, None, data_available=False)
    assert unknown.score == 40
    # factor contributions sum to the score
    assert round(sum(f["contribution"] for f in severe.factors)) == severe.score


def test_disease_outbreak_dominates():
    quiet = scoring.score_disease(0, 0, 0.0)
    assert quiet.score == 0
    outbreak = scoring.score_disease(5, 2, 4.0)
    assert outbreak.score >= 70


def test_inventory_low_coverage_is_high_risk():
    stocked = scoring.score_inventory(1.5, 0, covered_segments=3)
    assert stocked.score < 20
    short = scoring.score_inventory(0.2, 4, covered_segments=3)
    assert short.score >= 60


def test_band_thresholds():
    assert scoring.band(10) == "low"
    assert scoring.band(50) == "medium"
    assert scoring.band(85) == "high"


def test_financial_composite_reflects_inputs():
    low = scoring.score_financial(10, 10, demand_confidence=0.9)
    high = scoring.score_financial(90, 80, demand_confidence=0.2)
    assert high.score > low.score


# --- endpoints ---------------------------------------------------------------

async def test_recompute_and_board(ctx: TestContext):
    token = await ctx.login()
    # Minimal signals: a region with a farm/field/cycle and an outbreak report.
    region = (await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token), json={"name": "Rift", "code": "RIFT"}
    )).json()["id"]
    variety = await make_variety(ctx, token)
    farmer = await make_farmer(ctx, token)
    # attach farmer to the region so region centroid + regional risk populate
    farm = await make_farm(ctx, token, farmer, region_id=region)
    field = await make_field(ctx, token, farm)
    cycle = await make_crop_cycle(ctx, token, field, variety)
    disease = (await ctx.client.post(
        "/api/v1/diseases", headers=ctx.auth(token), json={"name": "Blight", "crop": "maize"}
    )).json()
    await ctx.client.post(
        "/api/v1/disease-reports", headers=ctx.auth(token),
        json={"cropCycleId": cycle, "diseaseId": disease["id"], "severity": 4, "affectedPct": 30},
    )

    res = await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(token))
    assert res.status_code == 202, res.text
    assert res.json()["count"] >= 6  # six org-scope domains

    board = (await ctx.client.get("/api/v1/risks/board", headers=ctx.auth(token))).json()
    domains = {d["domain"]: d for d in board["domains"]}
    assert set(domains) == {
        "climate", "disease", "supply_chain", "inventory", "production", "financial",
    }
    for d in board["domains"]:
        assert 0 <= d["score"] <= 100
        assert d["band"] in ("low", "medium", "high")
        assert round(sum(f["contribution"] for f in d["factors"])) == d["score"]
    assert board["assessedDate"] is not None


async def test_regional_board(ctx: TestContext):
    token = await ctx.login()
    region = (await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token), json={"name": "East", "code": "EAST"}
    )).json()["id"]
    variety = await make_variety(ctx, token)
    farmer = await make_farmer(ctx, token)
    farm = await make_farm(ctx, token, farmer, region_id=region)
    field = await make_field(ctx, token, farm)
    await make_crop_cycle(ctx, token, field, variety)

    await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(token))
    board = (await ctx.client.get(
        "/api/v1/risks/board", headers=ctx.auth(token), params={"regionId": region}
    )).json()
    domains = {d["domain"] for d in board["domains"]}
    assert domains == {"climate", "disease", "production"}


async def test_recompute_is_idempotent_per_day(ctx: TestContext):
    token = await ctx.login()
    first = (await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(token))).json()
    second = (await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(token))).json()
    # Re-running the same day upserts, not appends: board still has 6 org domains.
    assert first["count"] == second["count"]
    board = (await ctx.client.get("/api/v1/risks/board", headers=ctx.auth(token))).json()
    assert len(board["domains"]) == 6


async def test_history_endpoint(ctx: TestContext):
    token = await ctx.login()
    await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(token))
    res = await ctx.client.get(
        "/api/v1/risks/history", headers=ctx.auth(token), params={"domain": "disease"}
    )
    assert res.status_code == 200
    points = res.json()
    assert len(points) >= 1
    assert all(0 <= p["score"] <= 100 for p in points)


async def test_risk_permission_boundary(ctx: TestContext):
    # Viewer can read the board but not trigger recompute.
    viewer = await ctx.login("viewer@example.com")
    board = await ctx.client.get("/api/v1/risks/board", headers=ctx.auth(viewer))
    assert board.status_code == 200
    res = await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(viewer))
    assert res.status_code == 403


async def test_risk_org_isolation(ctx: TestContext):
    token = await ctx.login()
    await ctx.client.post("/api/v1/risks/recompute", headers=ctx.auth(token))
    other = await ctx.login("admin2@example.com")
    board = (await ctx.client.get("/api/v1/risks/board", headers=ctx.auth(other))).json()
    assert board["domains"] == []
