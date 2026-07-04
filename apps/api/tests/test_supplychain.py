from tests.conftest import TestContext
from tests.helpers import (
    make_order,
    make_variety,
    make_vehicle,
    make_warehouse,
)

VEHICLES = "/api/v1/vehicles"
ORDERS = "/api/v1/orders"
ROUTES = "/api/v1/routes"
DELIVERIES = "/api/v1/deliveries"


async def test_vehicle_crud_and_duplicate(ctx: TestContext):
    token = await ctx.login()
    await make_vehicle(ctx, token, "KAA-001A")
    res = await ctx.client.post(
        VEHICLES, headers=ctx.auth(token),
        json={"registration": "kaa-001a", "capacityKg": 5000},
    )
    assert res.status_code == 409  # case-insensitive uniqueness

    vehicles = (await ctx.client.get(VEHICLES, headers=ctx.auth(token))).json()
    assert len(vehicles) == 1
    assert vehicles[0]["status"] == "available"


async def test_order_lifecycle_and_variety_validation(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)

    # unknown variety rejected
    res = await ctx.client.post(
        ORDERS, headers=ctx.auth(token),
        json={"customerName": "X", "destinationLat": 0, "destinationLng": 35,
              "items": [{"varietyId": "00000000-0000-0000-0000-000000000000", "quantityKg": 10}]},
    )
    assert res.status_code == 404

    order_id = await make_order(ctx, token, variety, confirm=False)
    listing = (await ctx.client.get(ORDERS, headers=ctx.auth(token),
                                    params={"status": "pending"})).json()
    assert listing["meta"]["totalItems"] == 1

    res = await ctx.client.post(
        f"{ORDERS}/{order_id}/status", headers=ctx.auth(token), json={"status": "confirmed"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"


async def test_route_planning_sequences_and_measures(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    # three orders at increasing distance from the warehouse (-0.3, 35.9)
    o1 = await make_order(ctx, token, variety, lat=-0.31, lng=35.92)
    o2 = await make_order(ctx, token, variety, lat=-0.50, lng=36.10)
    o3 = await make_order(ctx, token, variety, lat=-0.35, lng=35.95)

    res = await ctx.client.post(
        ROUTES, headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01",
              "orderIds": [o2, o1, o3]},
    )
    assert res.status_code == 201, res.text
    route = res.json()
    assert route["status"] == "planned"
    assert route["totalDistanceKm"] > 0
    assert len(route["stops"]) == 3
    # nearest-neighbour: the closest order (o1) is visited first, farthest (o2) last
    seq = {s["orderId"]: s["stopSequence"] for s in route["stops"]}
    assert seq[o1] == 1
    assert seq[o2] == 3
    # stops carry increasing ETAs
    etas = [s["eta"] for s in sorted(route["stops"], key=lambda s: s["stopSequence"])]
    assert etas[0] < etas[1] < etas[2]


async def test_route_requires_confirmed_orders(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    pending = await make_order(ctx, token, variety, confirm=False)
    res = await ctx.client.post(
        ROUTES, headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01",
              "orderIds": [pending]},
    )
    assert res.status_code == 422


async def test_order_cannot_be_double_routed(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    order = await make_order(ctx, token, variety)
    payload = {"originWarehouseId": warehouse, "plannedDate": "2026-08-01", "orderIds": [order]}
    assert (await ctx.client.post(ROUTES, headers=ctx.auth(token), json=payload)).status_code == 201
    res = await ctx.client.post(ROUTES, headers=ctx.auth(token), json=payload)
    assert res.status_code == 409


async def test_vehicle_capacity_enforced(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    vehicle = await make_vehicle(ctx, token, "KAB-002B", capacity_kg=300)
    order = await make_order(ctx, token, variety, quantity_kg=500)  # exceeds capacity
    res = await ctx.client.post(
        ROUTES, headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01",
              "vehicleId": vehicle, "orderIds": [order]},
    )
    assert res.status_code == 422


async def test_full_dispatch_and_delivery_flow(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    vehicle = await make_vehicle(ctx, token, capacity_kg=10000)
    order = await make_order(ctx, token, variety, quantity_kg=800)

    route = (await ctx.client.post(
        ROUTES, headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01",
              "vehicleId": vehicle, "orderIds": [order]},
    )).json()

    # dispatch → vehicle on_route, delivery created in_transit
    res = await ctx.client.post(f"{ROUTES}/{route['id']}/dispatch", headers=ctx.auth(token))
    assert res.status_code == 200
    assert res.json()["status"] == "dispatched"

    veh = (await ctx.client.get(VEHICLES, headers=ctx.auth(token))).json()[0]
    assert veh["status"] == "on_route"

    deliveries = (await ctx.client.get(DELIVERIES, headers=ctx.auth(token))).json()
    assert len(deliveries) == 1
    delivery_id = deliveries[0]["id"]
    assert deliveries[0]["status"] == "in_transit"

    # a location ping (tracking) does not change status
    res = await ctx.client.post(
        f"{DELIVERIES}/{delivery_id}/events", headers=ctx.auth(token),
        json={"eventType": "location_ping", "latitude": -0.32, "longitude": 35.93},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_transit"

    # mark delivered → order fulfilled, route completed, vehicle freed
    res = await ctx.client.post(
        f"{DELIVERIES}/{delivery_id}/events", headers=ctx.auth(token),
        json={"eventType": "status_change", "status": "delivered"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "delivered"

    order_row = (await ctx.client.get(ORDERS, headers=ctx.auth(token))).json()["data"][0]
    assert order_row["status"] == "fulfilled"
    veh = (await ctx.client.get(VEHICLES, headers=ctx.auth(token))).json()[0]
    assert veh["status"] == "available"

    events = (await ctx.client.get(
        f"{DELIVERIES}/{delivery_id}/events", headers=ctx.auth(token)
    )).json()
    assert len(events) >= 3  # in_transit, ping, delivered


async def test_active_routes_geojson(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    vehicle = await make_vehicle(ctx, token)
    order = await make_order(ctx, token, variety)
    route = (await ctx.client.post(
        ROUTES, headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01",
              "vehicleId": vehicle, "orderIds": [order]},
    )).json()
    await ctx.client.post(f"{ROUTES}/{route['id']}/dispatch", headers=ctx.auth(token))

    res = await ctx.client.get("/api/v1/gis/routes/active", headers=ctx.auth(token))
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    line = body["features"][0]
    assert line["geometry"]["type"] == "LineString"
    assert len(line["geometry"]["coordinates"]) == 2  # warehouse + one stop


async def test_logistics_permission_boundary(ctx: TestContext):
    viewer = await ctx.login("viewer@example.com")
    res = await ctx.client.get(VEHICLES, headers=ctx.auth(viewer))
    assert res.status_code == 403  # Viewer has no logistics:read


async def test_supplychain_org_isolation(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    order = await make_order(ctx, token, variety, confirm=False)
    other = await ctx.login("admin2@example.com")
    res = await ctx.client.post(
        f"{ORDERS}/{order}/status", headers=ctx.auth(other), json={"status": "confirmed"}
    )
    assert res.status_code == 404
