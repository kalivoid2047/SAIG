import pytest

from saig.ml.routing import InfeasibleRouteError, Stop, optimize
from tests.conftest import TestContext
from tests.helpers import make_order, make_variety, make_vehicle, make_warehouse

ROUTES = "/api/v1/routes"


# --- pure optimizer ----------------------------------------------------------

def _stops() -> list[Stop]:
    return [
        Stop("o1", -0.31, 35.92, 300),
        Stop("o2", -0.50, 36.10, 400),
        Stop("o3", -0.35, 35.95, 250),
        Stop("o4", -0.28, 36.05, 350),
        Stop("o5", -0.45, 35.88, 200),
        Stop("o6", -0.33, 36.12, 500),
    ]


def test_optimizer_assigns_within_capacity():
    origin = (-0.30, 35.95)
    result = optimize(origin, _stops(), capacities=[1200, 1200])
    # every order is served exactly once
    served = [oid for r in result.routes for oid in r.order_ids]
    assert sorted(served) == ["o1", "o2", "o3", "o4", "o5", "o6"]
    # no route exceeds capacity
    demand = {s.order_id: s.demand_kg for s in _stops()}
    for r in result.routes:
        assert sum(demand[o] for o in r.order_ids) <= 1200
    assert result.total_distance_km > 0
    assert result.savings_pct >= 0  # never worse than the naive baseline


def test_optimizer_infeasible_when_over_capacity():
    with pytest.raises(InfeasibleRouteError):
        optimize((-0.30, 35.95), _stops(), capacities=[100])


def test_optimizer_empty_inputs():
    assert optimize((-0.3, 35.9), [], [1000]).routes == []
    assert optimize((-0.3, 35.9), _stops(), []).routes == []


# --- endpoint ----------------------------------------------------------------

async def test_optimize_endpoint_creates_routes(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    await make_vehicle(ctx, token, "KAA-1", capacity_kg=1500)
    await make_vehicle(ctx, token, "KBB-2", capacity_kg=1500)

    order_ids = []
    coords = [(-0.31, 35.92), (-0.50, 36.10), (-0.35, 35.95), (-0.28, 36.05)]
    for i, (lat, lng) in enumerate(coords):
        order_ids.append(
            await make_order(ctx, token, variety, lat=lat, lng=lng, quantity_kg=400 + i * 100)
        )

    res = await ctx.client.post(
        f"{ROUTES}/optimize", headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01", "orderIds": order_ids},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["routesCreated"] >= 1
    assert body["totalDistanceKm"] > 0
    assert body["savingsPct"] >= 0
    # all orders distributed across the created routes, each stop sequenced
    served = [s["orderId"] for r in body["routes"] for s in r["stops"]]
    assert sorted(served) == sorted(order_ids)
    for r in body["routes"]:
        assert r["status"] == "planned"
        assert [s["stopSequence"] for s in r["stops"]] == list(range(1, len(r["stops"]) + 1))
        assert r["optimizerMeta"]["method"] in ("or-tools", "greedy_2opt")


async def test_optimize_rejects_unconfirmed_orders(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    await make_vehicle(ctx, token)
    pending = await make_order(ctx, token, variety, confirm=False)
    res = await ctx.client.post(
        f"{ROUTES}/optimize", headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01", "orderIds": [pending]},
    )
    assert res.status_code == 422


async def test_optimize_infeasible_capacity_returns_422(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    await make_vehicle(ctx, token, "SMALL", capacity_kg=100)
    big = await make_order(ctx, token, variety, quantity_kg=5000)
    res = await ctx.client.post(
        f"{ROUTES}/optimize", headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01", "orderIds": [big]},
    )
    assert res.status_code == 422
    assert "capacity" in res.json()["detail"].lower()


async def test_optimize_requires_available_vehicle(ctx: TestContext):
    token = await ctx.login()
    variety = await make_variety(ctx, token)
    warehouse = await make_warehouse(ctx, token)
    order = await make_order(ctx, token, variety)
    res = await ctx.client.post(
        f"{ROUTES}/optimize", headers=ctx.auth(token),
        json={"originWarehouseId": warehouse, "plannedDate": "2026-08-01", "orderIds": [order]},
    )
    assert res.status_code == 422  # no vehicles at all
