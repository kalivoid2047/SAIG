from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.inventory.repository import InventoryRepository
from saig.modules.supplychain.repository import SupplyChainRepository
from saig.modules.supplychain.schemas import (
    DeliveryEventIn,
    DeliveryEventOut,
    DeliveryOut,
    OrderCreate,
    OrderOut,
    OrderStatusUpdate,
    RoutePlanCreate,
    RoutePlanOut,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
)
from saig.modules.supplychain.service import SupplyChainService
from saig.shared.pagination import Page, PageParams, page_params

vehicles_router = APIRouter(prefix="/vehicles", tags=["supply-chain"])
orders_router = APIRouter(prefix="/orders", tags=["supply-chain"])
routes_router = APIRouter(prefix="/routes", tags=["supply-chain"])
deliveries_router = APIRouter(prefix="/deliveries", tags=["supply-chain"])
gis_router = APIRouter(prefix="/gis", tags=["supply-chain"])


# --- Vehicles ----------------------------------------------------------------

@vehicles_router.get("", response_model=list[VehicleOut])
async def list_vehicles(
    current: CurrentUser = Depends(require_permission("logistics:read")),
    session: AsyncSession = Depends(get_db),
) -> list[VehicleOut]:
    vehicles = await SupplyChainRepository(session).list_vehicles(current.organization_id)
    return [VehicleOut.model_validate(v) for v in vehicles]


@vehicles_router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    body: VehicleCreate,
    current: CurrentUser = Depends(require_permission("logistics:manage")),
    session: AsyncSession = Depends(get_db),
) -> VehicleOut:
    vehicle = await SupplyChainService(session).create_vehicle(
        body, current.organization_id, current.id
    )
    return VehicleOut.model_validate(vehicle)


@vehicles_router.patch("/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: str,
    body: VehicleUpdate,
    current: CurrentUser = Depends(require_permission("logistics:manage")),
    session: AsyncSession = Depends(get_db),
) -> VehicleOut:
    vehicle = await SupplyChainService(session).update_vehicle(
        vehicle_id, body, current.organization_id, current.id
    )
    return VehicleOut.model_validate(vehicle)


# --- Orders ------------------------------------------------------------------

@orders_router.get("", response_model=Page[OrderOut])
async def list_orders(
    params: PageParams = Depends(page_params),
    order_status: str | None = Query(None, alias="status"),
    current: CurrentUser = Depends(require_permission("logistics:read")),
    session: AsyncSession = Depends(get_db),
) -> Page[OrderOut]:
    orders, total = await SupplyChainRepository(session).list_orders(
        current.organization_id, params, order_status
    )
    return Page.build([OrderOut.model_validate(o) for o in orders], total, params)


@orders_router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    current: CurrentUser = Depends(require_permission("logistics:manage")),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await SupplyChainService(session).create_order(
        body, current.organization_id, current.id
    )
    return OrderOut.model_validate(order)


@orders_router.post("/{order_id}/status", response_model=OrderOut)
async def set_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    current: CurrentUser = Depends(require_permission("logistics:manage")),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await SupplyChainService(session).set_order_status(
        order_id, body.status, current.organization_id, current.id
    )
    return OrderOut.model_validate(order)


# --- Route plans -------------------------------------------------------------

@routes_router.get("", response_model=list[RoutePlanOut])
async def list_routes(
    current: CurrentUser = Depends(require_permission("logistics:read")),
    session: AsyncSession = Depends(get_db),
) -> list[RoutePlanOut]:
    routes = await SupplyChainRepository(session).list_routes(current.organization_id)
    return [RoutePlanOut.model_validate(r) for r in routes]


@routes_router.post("", response_model=RoutePlanOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RoutePlanCreate,
    current: CurrentUser = Depends(require_permission("logistics:plan")),
    session: AsyncSession = Depends(get_db),
) -> RoutePlanOut:
    route = await SupplyChainService(session).create_route(
        body, current.organization_id, current.id
    )
    return RoutePlanOut.model_validate(route)


@routes_router.post("/{route_id}/dispatch", response_model=RoutePlanOut)
async def dispatch_route(
    route_id: str,
    current: CurrentUser = Depends(require_permission("logistics:plan")),
    session: AsyncSession = Depends(get_db),
) -> RoutePlanOut:
    route = await SupplyChainService(session).dispatch_route(
        route_id, current.organization_id, current.id
    )
    return RoutePlanOut.model_validate(route)


# --- Deliveries --------------------------------------------------------------

@deliveries_router.get("", response_model=list[DeliveryOut])
async def list_deliveries(
    delivery_status: str | None = Query(None, alias="status"),
    route_id: str | None = Query(None, alias="routeId"),
    current: CurrentUser = Depends(require_permission("logistics:read")),
    session: AsyncSession = Depends(get_db),
) -> list[DeliveryOut]:
    deliveries = await SupplyChainRepository(session).list_deliveries(
        current.organization_id, delivery_status, route_id
    )
    return [DeliveryOut.model_validate(d) for d in deliveries]


@deliveries_router.get("/{delivery_id}/events", response_model=list[DeliveryEventOut])
async def list_delivery_events(
    delivery_id: str,
    current: CurrentUser = Depends(require_permission("logistics:read")),
    session: AsyncSession = Depends(get_db),
) -> list[DeliveryEventOut]:
    repo = SupplyChainRepository(session)
    if await repo.get_delivery(delivery_id, current.organization_id) is None:
        return []
    events = await repo.list_delivery_events(delivery_id)
    return [DeliveryEventOut.model_validate(e) for e in events]


@deliveries_router.post("/{delivery_id}/events", response_model=DeliveryOut)
async def record_delivery_event(
    delivery_id: str,
    body: DeliveryEventIn,
    current: CurrentUser = Depends(require_permission("logistics:track")),
    session: AsyncSession = Depends(get_db),
) -> DeliveryOut:
    delivery = await SupplyChainService(session).record_delivery_event(
        delivery_id, body, current.organization_id, current.id
    )
    return DeliveryOut.model_validate(delivery)


# --- GIS: active routes ------------------------------------------------------

@gis_router.get("/routes/active")
async def active_routes(
    current: CurrentUser = Depends(require_permission("logistics:read")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Dispatched routes as GeoJSON LineStrings: warehouse origin → ordered stops."""
    sc = SupplyChainRepository(session)
    inv = InventoryRepository(session)
    routes = await sc.active_routes(current.organization_id)
    features = []
    for route in routes:
        warehouse = await inv.get_warehouse(route.origin_warehouse_id, current.organization_id)
        if warehouse is None:
            continue
        coords = [[float(warehouse.longitude), float(warehouse.latitude)]]
        for stop in route.stops:
            order = await sc.get_order(stop.order_id, current.organization_id)
            if order is not None:
                coords.append([float(order.destination_lng), float(order.destination_lat)])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "id": route.id,
                    "status": route.status,
                    "stops": len(route.stops),
                    "distanceKm": float(route.total_distance_km or 0),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
