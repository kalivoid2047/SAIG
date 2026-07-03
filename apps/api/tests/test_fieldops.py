from tests.conftest import VIEWER_EMAIL, TestContext

FARMERS = "/api/v1/farmers"
FARMS = "/api/v1/farms"


async def make_region(ctx: TestContext, token: str, code: str = "EAST") -> str:
    res = await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token), json={"name": f"Region {code}", "code": code}
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def make_farmer(ctx: TestContext, token: str, **overrides) -> dict:
    payload = {
        "fullName": "Amina Mwangi",
        "phone": "+254712345678",
        "nationalId": "ID-1001",
        "consentGiven": True,
        **overrides,
    }
    res = await ctx.client.post(FARMERS, headers=ctx.auth(token), json=payload)
    assert res.status_code == 201, res.text
    return res.json()


async def make_variety(ctx: TestContext, token: str, code: str = "MZ-401") -> str:
    res = await ctx.client.post(
        "/api/v1/varieties",
        headers=ctx.auth(token),
        json={"crop": "maize", "name": f"Variety {code}", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --- Regions -----------------------------------------------------------------

async def test_region_create_and_duplicate(ctx: TestContext):
    token = await ctx.login()
    await make_region(ctx, token, "RIFT")
    res = await ctx.client.post(
        "/api/v1/regions", headers=ctx.auth(token), json={"name": "Dup", "code": "rift"}
    )
    assert res.status_code == 409  # code uniqueness is case-insensitive


# --- Farmers ------------------------------------------------------------------

async def test_farmer_requires_consent(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.post(
        FARMERS, headers=ctx.auth(token),
        json={"fullName": "No Consent", "consentGiven": False},
    )
    assert res.status_code == 422


async def test_farmer_duplicate_returns_existing_id(ctx: TestContext):
    token = await ctx.login()
    created = await make_farmer(ctx, token)
    res = await ctx.client.post(
        FARMERS, headers=ctx.auth(token),
        json={"fullName": "Other Name", "phone": "+254712345678", "consentGiven": True},
    )
    assert res.status_code == 409
    assert res.json()["existingFarmerId"] == created["id"]


async def test_pii_masked_for_viewer_full_for_admin(ctx: TestContext):
    admin_token = await ctx.login()
    farmer = await make_farmer(ctx, admin_token)
    viewer_token = await ctx.login(VIEWER_EMAIL)

    # Viewer (no farmers:read_pii): masked
    res = await ctx.client.get(f"{FARMERS}/{farmer['id']}", headers=ctx.auth(viewer_token))
    assert res.status_code == 200
    body = res.json()
    assert body["piiMasked"] is True
    assert body["phone"].startswith("•••")
    assert body["nationalId"].startswith("•••")

    # Admin: full PII, and the read is audit-logged
    res = await ctx.client.get(f"{FARMERS}/{farmer['id']}", headers=ctx.auth(admin_token))
    body = res.json()
    assert body["piiMasked"] is False
    assert body["phone"] == "+254712345678"

    audit = await ctx.client.get(
        "/api/v1/audit-logs", headers=ctx.auth(admin_token),
        params={"action": "farmers.read_pii"},
    )
    assert audit.json()["meta"]["totalItems"] >= 1


async def test_masked_values_never_persisted(ctx: TestContext):
    admin_token = await ctx.login()
    farmer = await make_farmer(ctx, admin_token)
    viewer_token = await ctx.login(VIEWER_EMAIL)
    # Viewer read (masks in memory) …
    await ctx.client.get(f"{FARMERS}/{farmer['id']}", headers=ctx.auth(viewer_token))
    # … must not corrupt stored PII
    res = await ctx.client.get(f"{FARMERS}/{farmer['id']}", headers=ctx.auth(admin_token))
    assert res.json()["phone"] == "+254712345678"


async def test_production_record_lifecycle(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)
    payload = {"season": "2025-long-rains", "areaHa": 2.5, "yieldKg": 5400}
    res = await ctx.client.post(
        f"{FARMERS}/{farmer['id']}/production-records", headers=ctx.auth(token), json=payload
    )
    assert res.status_code == 201
    res = await ctx.client.post(
        f"{FARMERS}/{farmer['id']}/production-records", headers=ctx.auth(token), json=payload
    )
    assert res.status_code == 409  # same season+variety

    res = await ctx.client.get(f"{FARMERS}/{farmer['id']}", headers=ctx.auth(token))
    assert len(res.json()["productionRecords"]) == 1


# --- Farms & fields ------------------------------------------------------------

async def test_farm_and_field_with_boundary_area(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)

    res = await ctx.client.post(
        FARMS, headers=ctx.auth(token),
        json={"farmerId": farmer["id"], "name": "Mwangi Farm",
              "latitude": -0.30, "longitude": 35.95, "totalAreaHa": 5.0},
    )
    assert res.status_code == 201, res.text
    farm_id = res.json()["id"]

    # boundary → server-computed area (≈1.24 ha square, near the equator)
    boundary = {
        "type": "Polygon",
        "coordinates": [[
            [35.95, -0.30], [35.951, -0.30], [35.951, -0.299],
            [35.95, -0.299], [35.95, -0.30],
        ]],
    }
    res = await ctx.client.post(
        f"{FARMS}/{farm_id}/fields", headers=ctx.auth(token),
        json={"name": "North plot", "boundary": boundary},
    )
    assert res.status_code == 201, res.text
    field = res.json()
    assert 1.1 <= field["areaHa"] <= 1.4
    assert field["boundary"]["type"] == "Polygon"

    # neither boundary nor area → domain error
    res = await ctx.client.post(
        f"{FARMS}/{farm_id}/fields", headers=ctx.auth(token), json={"name": "Bad plot"}
    )
    assert res.status_code == 422


async def test_farm_requires_existing_farmer(ctx: TestContext):
    token = await ctx.login()
    res = await ctx.client.post(
        FARMS, headers=ctx.auth(token),
        json={"farmerId": "00000000-0000-0000-0000-000000000000", "name": "Ghost Farm",
              "latitude": 0, "longitude": 35},
    )
    assert res.status_code == 404


async def test_soil_samples(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)
    farm = (await ctx.client.post(
        FARMS, headers=ctx.auth(token),
        json={"farmerId": farmer["id"], "name": "F", "latitude": 0, "longitude": 35},
    )).json()
    field = (await ctx.client.post(
        f"{FARMS}/{farm['id']}/fields", headers=ctx.auth(token),
        json={"name": "Plot", "areaHa": 1.5},
    )).json()

    res = await ctx.client.post(
        f"/api/v1/fields/{field['id']}/soil-samples", headers=ctx.auth(token),
        json={"sampledAt": "2026-06-01", "ph": 6.4, "texture": "loam",
              "organicMatterPct": 3.1},
    )
    assert res.status_code == 201
    res = await ctx.client.get(
        f"/api/v1/fields/{field['id']}/soil-samples", headers=ctx.auth(token)
    )
    assert len(res.json()) == 1
    assert res.json()[0]["ph"] == 6.4


# --- Crop cycles ------------------------------------------------------------------

async def test_crop_cycle_lifecycle_and_rules(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)
    variety_id = await make_variety(ctx, token)
    farm = (await ctx.client.post(
        FARMS, headers=ctx.auth(token),
        json={"farmerId": farmer["id"], "name": "F", "latitude": 0, "longitude": 35},
    )).json()
    field = (await ctx.client.post(
        f"{FARMS}/{farm['id']}/fields", headers=ctx.auth(token),
        json={"name": "Plot", "areaHa": 2.0},
    )).json()

    create = lambda: ctx.client.post(  # noqa: E731
        f"/api/v1/fields/{field['id']}/crop-cycles", headers=ctx.auth(token),
        json={"varietyId": variety_id, "season": "2026-long-rains"},
    )
    res = await create()
    assert res.status_code == 201, res.text
    cycle_id = res.json()["id"]
    assert res.json()["status"] == "planned"

    # one active cycle per field+season
    assert (await create()).status_code == 409

    transition = lambda body: ctx.client.post(  # noqa: E731
        f"/api/v1/crop-cycles/{cycle_id}/transitions", headers=ctx.auth(token), json=body
    )

    # invalid jump planned → harvested
    res = await transition({"to": "harvested", "actualYieldKg": 100})
    assert res.status_code == 422

    assert (await transition({"to": "planted", "occurredOn": "2026-03-15"})).status_code == 200
    assert (await transition({"to": "growing"})).status_code == 200

    # harvest requires yield
    assert (await transition({"to": "harvested"})).status_code == 422
    res = await transition({"to": "harvested", "actualYieldKg": 5400,
                            "occurredOn": "2026-08-01"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "harvested"
    assert body["actualYieldKg"] == 5400
    assert body["plantedAt"] == "2026-03-15"

    # terminal state
    assert (await transition({"to": "failed"})).status_code == 422

    # a new cycle can now start for the same field+season (previous is closed)
    assert (await create()).status_code == 201


# --- GIS -----------------------------------------------------------------------------

async def test_gis_farms_geojson_and_bbox(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)
    await ctx.client.post(
        FARMS, headers=ctx.auth(token),
        json={"farmerId": farmer["id"], "name": "Rift Farm",
              "latitude": -0.30, "longitude": 35.95},
    )

    res = await ctx.client.get("/api/v1/gis/farms", headers=ctx.auth(token))
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    feature = body["features"][0]
    assert feature["geometry"]["coordinates"] == [35.95, -0.30]
    assert feature["properties"]["farmerName"] == "Amina Mwangi"

    # bbox excluding the farm
    res = await ctx.client.get(
        "/api/v1/gis/farms", headers=ctx.auth(token),
        params={"minLat": 5, "minLng": 0, "maxLat": 10, "maxLng": 10},
    )
    assert res.json()["features"] == []


async def test_fieldops_org_isolation(ctx: TestContext):
    token = await ctx.login()
    farmer = await make_farmer(ctx, token)
    other_token = await ctx.login("admin2@example.com")
    res = await ctx.client.get(f"{FARMERS}/{farmer['id']}", headers=ctx.auth(other_token))
    assert res.status_code == 404
