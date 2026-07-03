from tests.conftest import TestContext
from tests.helpers import (
    make_crop_cycle,
    make_farm,
    make_farmer,
    make_field,
    make_variety,
)

REPORTS = "/api/v1/disease-reports"


async def _cycle_at(ctx: TestContext, token: str, variety: str, lat: float, lng: float) -> str:
    farmer = await make_farmer(ctx, token, phone=f"+2547{int((lat + 90) * 1e5) % 100000000:08d}")
    farm = await make_farm(ctx, token, farmer, lat=lat, lng=lng)
    field = await make_field(ctx, token, farm)
    return await make_crop_cycle(ctx, token, field, variety)


async def test_disease_catalog_and_report_geotag(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    disease = (await ctx.client.post(
        "/api/v1/diseases", headers=ctx.auth(token),
        json={"name": "Maize Leaf Blight", "crop": "maize", "pathogenType": "fungal"},
    )).json()
    cycle = await _cycle_at(ctx, token, variety, -0.30, 35.95)

    res = await ctx.client.post(
        REPORTS, headers=ctx.auth(token),
        json={"cropCycleId": cycle, "diseaseId": disease["id"], "severity": 3, "affectedPct": 20},
    )
    assert res.status_code == 201, res.text
    report = res.json()
    # geotagged from the farm location
    assert abs(report["latitude"] - -0.30) < 1e-6
    assert abs(report["longitude"] - 35.95) < 1e-6
    assert report["isOutbreak"] is False


async def test_outbreak_detection_clusters_nearby_reports(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    disease = (await ctx.client.post(
        "/api/v1/diseases", headers=ctx.auth(token),
        json={"name": "Blight", "crop": "maize"},
    )).json()

    # Three reports within ~2km → outbreak (>= 3 within 10km / 7 days)
    coords = [(-0.300, 35.950), (-0.305, 35.952), (-0.302, 35.955)]
    last = None
    for lat, lng in coords:
        cycle = await _cycle_at(ctx, token, variety, lat, lng)
        last = await ctx.client.post(
            REPORTS, headers=ctx.auth(token),
            json={"cropCycleId": cycle, "diseaseId": disease["id"],
                  "severity": 4, "affectedPct": 30},
        )
        assert last.status_code == 201
    assert last.json()["isOutbreak"] is True

    # All three are now flagged
    listing = await ctx.client.get(
        REPORTS, headers=ctx.auth(token), params={"diseaseId": disease["id"]}
    )
    assert sum(1 for r in listing.json()["data"] if r["isOutbreak"]) == 3


async def test_far_reports_do_not_cluster(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    disease = (await ctx.client.post(
        "/api/v1/diseases", headers=ctx.auth(token), json={"name": "Rust", "crop": "wheat"},
    )).json()
    # Three reports > 100 km apart
    for lat, lng in [(-0.30, 35.95), (-1.30, 36.95), (0.70, 34.60)]:
        cycle = await _cycle_at(ctx, token, variety, lat, lng)
        res = await ctx.client.post(
            REPORTS, headers=ctx.auth(token),
            json={"cropCycleId": cycle, "diseaseId": disease["id"],
                  "severity": 2, "affectedPct": 10},
        )
        assert res.json()["isOutbreak"] is False


async def test_report_status_workflow(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    cycle = await _cycle_at(ctx, token, variety, -0.30, 35.95)
    report = (await ctx.client.post(
        REPORTS, headers=ctx.auth(token),
        json={"cropCycleId": cycle, "severity": 3, "affectedPct": 15},
    )).json()

    transition = lambda to: ctx.client.post(  # noqa: E731
        f"{REPORTS}/{report['id']}/transitions", headers=ctx.auth(token), json={"to": to}
    )
    # invalid jump reported → resolved
    assert (await transition("resolved")).status_code == 422
    assert (await transition("confirmed")).status_code == 200
    assert (await transition("treated")).status_code == 200
    assert (await transition("resolved")).status_code == 200
    # terminal
    assert (await transition("dismissed")).status_code == 422


async def test_heatmap_geojson(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    cycle = await _cycle_at(ctx, token, variety, -0.30, 35.95)
    await ctx.client.post(
        REPORTS, headers=ctx.auth(token),
        json={"cropCycleId": cycle, "severity": 5, "affectedPct": 50},
    )
    res = await ctx.client.get("/api/v1/gis/disease-heatmap", headers=ctx.auth(token))
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    assert body["features"][0]["properties"]["severity"] == 5
