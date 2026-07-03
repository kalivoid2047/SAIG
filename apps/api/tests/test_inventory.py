from tests.conftest import TestContext
from tests.helpers import make_lot, make_variety, make_warehouse

MOVEMENTS = "/api/v1/stock/movements"
TRANSFERS = "/api/v1/stock/transfers"


async def test_receipt_and_balance(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    wh = await make_warehouse(ctx, token)
    lot = await make_lot(ctx, token, variety)

    res = await ctx.client.post(
        MOVEMENTS, headers=ctx.auth(token),
        json={"warehouseId": wh, "lotId": lot, "movementType": "receipt", "quantityKg": 1000},
    )
    assert res.status_code == 201, res.text

    balances = (await ctx.client.get("/api/v1/stock/balances", headers=ctx.auth(token))).json()
    assert len(balances) == 1
    assert balances[0]["balanceKg"] == 1000


async def test_write_off_cannot_go_negative(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    wh = await make_warehouse(ctx, token)
    lot = await make_lot(ctx, token, variety)

    await ctx.client.post(
        MOVEMENTS, headers=ctx.auth(token),
        json={"warehouseId": wh, "lotId": lot, "movementType": "receipt", "quantityKg": 100},
    )
    # Writing off more than available is rejected atomically (BR-2)
    res = await ctx.client.post(
        MOVEMENTS, headers=ctx.auth(token),
        json={"warehouseId": wh, "lotId": lot, "movementType": "write_off", "quantityKg": 250},
    )
    assert res.status_code == 422
    assert res.json()["availableKg"] == 100

    # Balance is unchanged
    balances = (await ctx.client.get("/api/v1/stock/balances", headers=ctx.auth(token))).json()
    assert balances[0]["balanceKg"] == 100


async def test_duplicate_warehouse_and_lot_codes(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    await make_warehouse(ctx, token, "WH-DUP")
    res = await ctx.client.post(
        "/api/v1/warehouses", headers=ctx.auth(token),
        json={"name": "Dup", "code": "wh-dup", "latitude": 0, "longitude": 35},
    )
    assert res.status_code == 409

    await make_lot(ctx, token, variety, "L-DUP")
    res = await ctx.client.post(
        "/api/v1/stock/lots", headers=ctx.auth(token),
        json={"varietyId": variety, "lotNumber": "L-DUP",
              "producedAt": "2026-01-01", "expiresAt": "2027-01-01"},
    )
    assert res.status_code == 409


async def test_lot_expiry_must_be_after_production(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    res = await ctx.client.post(
        "/api/v1/stock/lots", headers=ctx.auth(token),
        json={"varietyId": variety, "lotNumber": "L-BAD",
              "producedAt": "2027-01-01", "expiresAt": "2026-01-01"},
    )
    assert res.status_code == 422


async def test_transfer_full_lifecycle(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    src = await make_warehouse(ctx, token, "WH-SRC")
    dst = await make_warehouse(ctx, token, "WH-DST")
    lot = await make_lot(ctx, token, variety)

    await ctx.client.post(
        MOVEMENTS, headers=ctx.auth(token),
        json={"warehouseId": src, "lotId": lot, "movementType": "receipt", "quantityKg": 500},
    )

    transfer = (await ctx.client.post(
        TRANSFERS, headers=ctx.auth(token),
        json={"fromWarehouseId": src, "toWarehouseId": dst, "lotId": lot, "quantityKg": 200},
    )).json()
    assert transfer["status"] == "pending"

    res = await ctx.client.post(
        f"{TRANSFERS}/{transfer['id']}/dispatch", headers=ctx.auth(token)
    )
    assert res.status_code == 200
    assert res.json()["status"] == "dispatched"

    # Source debited immediately
    balances = {
        b["warehouseId"]: b["balanceKg"]
        for b in (await ctx.client.get("/api/v1/stock/balances", headers=ctx.auth(token))).json()
    }
    assert balances[src] == 300

    # Receive with a short delivery → variance flagged, destination credited actual
    res = await ctx.client.post(
        f"{TRANSFERS}/{transfer['id']}/receive", headers=ctx.auth(token),
        json={"receivedKg": 190},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "received"
    assert body["varianceNote"] is not None

    balances = {
        b["warehouseId"]: b["balanceKg"]
        for b in (await ctx.client.get("/api/v1/stock/balances", headers=ctx.auth(token))).json()
    }
    assert balances[dst] == 190


async def test_transfer_insufficient_stock_rejected(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    src = await make_warehouse(ctx, token, "WH-A")
    dst = await make_warehouse(ctx, token, "WH-B")
    lot = await make_lot(ctx, token, variety)
    res = await ctx.client.post(
        TRANSFERS, headers=ctx.auth(token),
        json={"fromWarehouseId": src, "toWarehouseId": dst, "lotId": lot, "quantityKg": 50},
    )
    assert res.status_code == 422


async def test_inventory_permission_boundary(ctx: TestContext):
    # Viewer can read but not move stock
    viewer = await ctx.login("viewer@example.com")
    res = await ctx.client.get("/api/v1/warehouses", headers=ctx.auth(viewer))
    assert res.status_code == 200
    res = await ctx.client.post(
        "/api/v1/warehouses", headers=ctx.auth(viewer),
        json={"name": "X", "code": "X1", "latitude": 0, "longitude": 35},
    )
    assert res.status_code == 403
