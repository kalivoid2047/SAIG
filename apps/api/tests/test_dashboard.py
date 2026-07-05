from tests.conftest import TestContext
from tests.helpers import (
    make_farm,
    make_farmer,
    make_field,
    make_lot,
    make_variety,
    make_warehouse,
)


async def test_dashboard_kpis_reflect_state(ctx: TestContext):
    token = await ctx.login()

    # Empty org
    kpis = (await ctx.client.get("/api/v1/dashboard/kpis", headers=ctx.auth(token))).json()
    assert kpis["activeFarmers"] == 0
    assert kpis["totalStockKg"] == 0

    variety = await make_variety(ctx, token)
    farmer = await make_farmer(ctx, token)
    farm = await make_farm(ctx, token, farmer)
    field = await make_field(ctx, token, farm)
    await ctx.client.post(
        f"/api/v1/fields/{field}/crop-cycles", headers=ctx.auth(token),
        json={"varietyId": variety, "season": "2026-long-rains"},
    )
    wh = await make_warehouse(ctx, token)
    lot = await make_lot(ctx, token, variety)
    await ctx.client.post(
        "/api/v1/stock/movements", headers=ctx.auth(token),
        json={"warehouseId": wh, "lotId": lot, "movementType": "receipt", "quantityKg": 750},
    )

    kpis = (await ctx.client.get("/api/v1/dashboard/kpis", headers=ctx.auth(token))).json()
    assert kpis["activeFarmers"] == 1
    assert kpis["activeCropCycles"] == 1
    assert kpis["seedVarieties"] == 1
    assert kpis["warehouses"] == 1
    assert kpis["totalStockKg"] == 750
    assert kpis["openDiseaseReports"] == 0
    assert kpis["openOrders"] == 0
    assert kpis["activeRoutes"] == 0
    assert kpis["projectedProductionKg"] == 0
    assert kpis["yieldPredictionCount"] == 0
    assert kpis["highRiskCount"] == 0


async def test_dashboard_is_org_scoped(ctx: TestContext):
    token = await ctx.login()
    await make_farmer(ctx, token)

    other = await ctx.login("admin2@example.com")
    kpis = (await ctx.client.get("/api/v1/dashboard/kpis", headers=ctx.auth(other))).json()
    assert kpis["activeFarmers"] == 0
