from tests.conftest import TestContext
from tests.helpers import make_farm, make_farmer


async def test_forecast_by_latlng(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.get(
        "/api/v1/weather/forecast", headers=ctx.auth(token),
        params={"lat": -0.3, "lng": 35.95, "days": 7},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "fake"
    assert len(body["days"]) == 7
    assert body["stale"] is False
    assert all("tempMaxC" in d for d in body["days"])


async def test_forecast_by_farm_and_cell_sharing(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)
    farm = await make_farm(ctx, token, farmer, lat=-0.30, lng=35.95)

    res = await ctx.client.get(
        "/api/v1/weather/forecast", headers=ctx.auth(token), params={"farmId": farm}
    )
    assert res.status_code == 200
    key1 = res.json()["cellKey"]

    # A nearby point (<5km) resolves to the same weather cell (cost dedup)
    res2 = await ctx.client.get(
        "/api/v1/weather/forecast", headers=ctx.auth(token),
        params={"lat": -0.301, "lng": 35.951},
    )
    assert res2.json()["cellKey"] == key1


async def test_agro_indicators(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.get(
        "/api/v1/weather/aggregates", headers=ctx.auth(token),
        params={"lat": -0.3, "lng": 35.95, "window": 90},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dataPoints"] > 0
    assert body["rainfall7dMm"] is not None
    assert body["growingDegreeDays"] is not None
    assert body["heatStressDays"] >= 0


async def test_weather_requires_permission(ctx: TestContext):
    # Warehouse Manager role lacks weather:read
    admin = await ctx.login()
    res = await ctx.client.post(
        "/api/v1/users", headers=ctx.auth(admin),
        json={"email": "wh@example.com", "password": "ValidPass123!", "fullName": "WH",
              "roleIds": [await _role_id(ctx, admin, "Warehouse Manager")]},
    )
    assert res.status_code == 201
    wh_token = await ctx.login("wh@example.com", "ValidPass123!")
    res = await ctx.client.get(
        "/api/v1/weather/forecast", headers=ctx.auth(wh_token),
        params={"lat": 0, "lng": 35},
    )
    assert res.status_code == 403


async def _role_id(ctx: TestContext, token: str, name: str) -> str:
    roles = (await ctx.client.get("/api/v1/roles", headers=ctx.auth(token))).json()
    return next(r["id"] for r in roles if r["name"] == name)
