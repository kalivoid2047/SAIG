"""Shared factory helpers for Phase 2 tests (build via the public API so
org-scoping and validation are exercised end-to-end)."""

from tests.conftest import TestContext


async def make_region(ctx: TestContext, token: str, code: str = "EAST") -> str:
    res = await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token),
        json={"name": f"Region {code}", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_variety(ctx: TestContext, token: str, code: str = "MZ-401") -> str:
    res = await ctx.client.post(
        "/api/v1/varieties", headers=ctx.auth(token),
        json={"crop": "maize", "name": f"Variety {code}", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_farmer(ctx: TestContext, token: str, phone: str = "+254712345678") -> str:
    res = await ctx.client.post(
        "/api/v1/farmers", headers=ctx.auth(token),
        json={"fullName": "Test Farmer", "phone": phone, "consentGiven": True},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_farm(
    ctx: TestContext, token: str, farmer_id: str, lat: float = -0.30, lng: float = 35.95,
    region_id: str | None = None,
) -> str:
    body = {"farmerId": farmer_id, "name": "Test Farm", "latitude": lat, "longitude": lng}
    if region_id is not None:
        body["regionId"] = region_id
    res = await ctx.client.post("/api/v1/farms", headers=ctx.auth(token), json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_field(ctx: TestContext, token: str, farm_id: str) -> str:
    res = await ctx.client.post(
        f"/api/v1/farms/{farm_id}/fields", headers=ctx.auth(token),
        json={"name": "Plot", "areaHa": 2.0},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_crop_cycle(
    ctx: TestContext, token: str, field_id: str, variety_id: str, season: str = "2026-long-rains"
) -> str:
    res = await ctx.client.post(
        f"/api/v1/fields/{field_id}/crop-cycles", headers=ctx.auth(token),
        json={"varietyId": variety_id, "season": season},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_warehouse(ctx: TestContext, token: str, code: str = "WH-01") -> str:
    res = await ctx.client.post(
        "/api/v1/warehouses", headers=ctx.auth(token),
        json={"name": f"Warehouse {code}", "code": code, "latitude": -0.3, "longitude": 35.9},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_lot(
    ctx: TestContext, token: str, variety_id: str, lot_number: str = "L-001"
) -> str:
    res = await ctx.client.post(
        "/api/v1/stock/lots", headers=ctx.auth(token),
        json={"varietyId": variety_id, "lotNumber": lot_number,
              "producedAt": "2026-01-01", "expiresAt": "2027-01-01", "germinationPct": 92},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_vehicle(
    ctx: TestContext, token: str, registration: str = "KAA-001A", capacity_kg: float = 10000
) -> str:
    res = await ctx.client.post(
        "/api/v1/vehicles", headers=ctx.auth(token),
        json={"registration": registration, "capacityKg": capacity_kg},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_order(
    ctx: TestContext,
    token: str,
    variety_id: str,
    lat: float = -0.30,
    lng: float = 35.95,
    quantity_kg: float = 500,
    confirm: bool = True,
) -> str:
    res = await ctx.client.post(
        "/api/v1/orders", headers=ctx.auth(token),
        json={
            "customerName": "Test Customer",
            "destinationLat": lat,
            "destinationLng": lng,
            "items": [{"varietyId": variety_id, "quantityKg": quantity_kg}],
        },
    )
    assert res.status_code == 201, res.text
    order_id = res.json()["id"]
    if confirm:
        r = await ctx.client.post(
            f"/api/v1/orders/{order_id}/status", headers=ctx.auth(token),
            json={"status": "confirmed"},
        )
        assert r.status_code == 200, r.text
    return order_id
