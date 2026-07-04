from datetime import datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.fieldops.repository import FieldOpsRepository
from saig.modules.iam.services.audit_service import AuditService
from saig.modules.inventory.repository import InventoryRepository
from saig.modules.supplychain.models import (
    Delivery,
    DeliveryEvent,
    Order,
    OrderItem,
    RoutePlan,
    RouteStop,
    Vehicle,
)
from saig.modules.supplychain.repository import SupplyChainRepository
from saig.modules.supplychain.schemas import (
    DeliveryEventIn,
    OrderCreate,
    RoutePlanCreate,
    VehicleCreate,
    VehicleUpdate,
)
from saig.shared.database import UTC, utcnow
from saig.shared.errors import ConflictError, DomainError, NotFoundError
from saig.shared.geo import haversine_km

AVG_SPEED_KMH = 40.0  # naive ETA model; VRP + real routing arrive with the ML service (FR-SC-4)
SERVICE_MINUTES_PER_STOP = 15
DEPART_HOUR = 8


class SupplyChainService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SupplyChainRepository(session)
        self.field_repo = FieldOpsRepository(session)
        self.inv_repo = InventoryRepository(session)
        self.audit = AuditService(session)

    # --- vehicles ------------------------------------------------------------

    async def create_vehicle(
        self, data: VehicleCreate, organization_id: str, actor_id: str
    ) -> Vehicle:
        if await self.repo.get_vehicle_by_reg(data.registration, organization_id) is not None:
            raise ConflictError("A vehicle with this registration already exists.")
        vehicle = Vehicle(
            organization_id=organization_id,
            registration=data.registration,
            capacity_kg=data.capacity_kg,
            driver_id=data.driver_id,
        )
        self.session.add(vehicle)
        await self.session.flush()
        self.audit.record("vehicles.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="vehicles", entity_id=vehicle.id,
                          after={"registration": vehicle.registration})
        await self.session.commit()
        return vehicle

    async def update_vehicle(
        self, vehicle_id: str, data: VehicleUpdate, organization_id: str, actor_id: str
    ) -> Vehicle:
        vehicle = await self.repo.get_vehicle(vehicle_id, organization_id)
        if vehicle is None:
            raise NotFoundError("Vehicle not found.")
        if data.status is not None:
            vehicle.status = data.status
        if data.capacity_kg is not None:
            vehicle.capacity_kg = data.capacity_kg
        if data.driver_id is not None:
            vehicle.driver_id = data.driver_id
        self.audit.record("vehicles.update", actor_id=actor_id, organization_id=organization_id,
                          entity_table="vehicles", entity_id=vehicle.id)
        await self.session.commit()
        return vehicle

    # --- orders --------------------------------------------------------------

    async def create_order(
        self, data: OrderCreate, organization_id: str, actor_id: str
    ) -> Order:
        if data.region_id is not None:
            if await self.field_repo.get_region(data.region_id, organization_id) is None:
                raise NotFoundError("Region not found.")
        for item in data.items:
            if await self.field_repo.get_variety(item.variety_id, organization_id) is None:
                raise NotFoundError(f"Seed variety {item.variety_id} not found.")
        order = Order(
            organization_id=organization_id,
            customer_name=data.customer_name,
            region_id=data.region_id,
            destination_lat=data.destination_lat,
            destination_lng=data.destination_lng,
            requested_date=data.requested_date,
            created_by=actor_id,
            items=[
                OrderItem(
                    variety_id=i.variety_id, quantity_kg=i.quantity_kg, unit_price=i.unit_price
                )
                for i in data.items
            ],
        )
        self.session.add(order)
        await self.session.flush()
        self.audit.record("orders.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="orders", entity_id=order.id,
                          after={"customer": order.customer_name})
        await self.session.commit()
        return order

    async def set_order_status(
        self, order_id: str, status: str, organization_id: str, actor_id: str
    ) -> Order:
        order = await self.repo.get_order(order_id, organization_id)
        if order is None:
            raise NotFoundError("Order not found.")
        if order.status in ("fulfilled", "cancelled"):
            raise DomainError(f"Order is already {order.status}.")
        order.status = status
        self.audit.record("orders.status", actor_id=actor_id, organization_id=organization_id,
                          entity_table="orders", entity_id=order.id, after={"status": status})
        await self.session.commit()
        return order

    # --- route planning ------------------------------------------------------

    async def create_route(
        self, data: RoutePlanCreate, organization_id: str, actor_id: str
    ) -> RoutePlan:
        warehouse = await self.inv_repo.get_warehouse(data.origin_warehouse_id, organization_id)
        if warehouse is None:
            raise NotFoundError("Origin warehouse not found.")

        orders = await self.repo.get_orders_by_ids(data.order_ids, organization_id)
        if len(orders) != len(set(data.order_ids)):
            raise NotFoundError("One or more orders not found.")
        not_confirmed = [o.id for o in orders if o.status != "confirmed"]
        if not_confirmed:
            raise DomainError("All orders must be confirmed before routing.")
        already = await self.repo.order_ids_already_routed(organization_id, data.order_ids)
        if already:
            raise ConflictError("One or more orders are already on an active route.")

        vehicle = None
        if data.vehicle_id is not None:
            vehicle = await self.repo.get_vehicle(data.vehicle_id, organization_id)
            if vehicle is None:
                raise NotFoundError("Vehicle not found.")
            if vehicle.status != "available":
                raise DomainError(f"Vehicle is {vehicle.status}, not available.")
            total_load = await self._route_load(orders)
            if total_load > float(vehicle.capacity_kg):
                raise DomainError(
                    f"Load {total_load:g} kg exceeds vehicle capacity "
                    f"{float(vehicle.capacity_kg):g} kg."
                )

        sequenced, total_km = self._sequence_nearest_neighbour(
            float(warehouse.latitude), float(warehouse.longitude), orders
        )

        route = RoutePlan(
            organization_id=organization_id,
            origin_warehouse_id=warehouse.id,
            vehicle_id=vehicle.id if vehicle else None,
            driver_id=vehicle.driver_id if vehicle else None,
            status="planned",
            planned_date=data.planned_date,
            total_distance_km=round(total_km, 2),
            optimizer_meta={"method": "nearest_neighbour", "stops": len(orders)},
        )
        depart = datetime.combine(data.planned_date, time(DEPART_HOUR, 0), tzinfo=UTC)
        cumulative_km = 0.0
        for seq, (order, leg_km) in enumerate(sequenced, start=1):
            cumulative_km += leg_km
            travel_min = (cumulative_km / AVG_SPEED_KMH) * 60 + SERVICE_MINUTES_PER_STOP * (seq - 1)
            route.stops.append(
                RouteStop(
                    order_id=order.id,
                    stop_sequence=seq,
                    eta=depart + timedelta(minutes=travel_min),
                )
            )
        self.session.add(route)
        await self.session.flush()
        self.audit.record("routes.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="route_plans", entity_id=route.id,
                          after={"stops": len(orders), "distanceKm": route.total_distance_km})
        await self.session.commit()
        return route

    async def _route_load(self, orders: list[Order]) -> float:
        total = 0.0
        for order in orders:
            total += sum(float(i.quantity_kg) for i in order.items)
        return total

    @staticmethod
    def _sequence_nearest_neighbour(
        origin_lat: float, origin_lng: float, orders: list[Order]
    ) -> tuple[list[tuple[Order, float]], float]:
        """Greedy nearest-neighbour ordering from the warehouse. A heuristic
        placeholder; the OR-Tools VRP solver lands in the ML service (FR-SC-4)."""
        remaining = list(orders)
        cur_lat, cur_lng = origin_lat, origin_lng
        sequence: list[tuple[Order, float]] = []
        total = 0.0
        while remaining:
            nearest = min(
                remaining,
                key=lambda o: haversine_km(
                    cur_lat, cur_lng, float(o.destination_lat), float(o.destination_lng)
                ),
            )
            leg = haversine_km(
                cur_lat, cur_lng,
                float(nearest.destination_lat), float(nearest.destination_lng),
            )
            sequence.append((nearest, leg))
            total += leg
            cur_lat, cur_lng = float(nearest.destination_lat), float(nearest.destination_lng)
            remaining.remove(nearest)
        return sequence, total

    async def dispatch_route(
        self, route_id: str, organization_id: str, actor_id: str
    ) -> RoutePlan:
        route = await self.repo.get_route(route_id, organization_id)
        if route is None:
            raise NotFoundError("Route not found.")
        if route.status != "planned":
            raise DomainError(f"Only planned routes can be dispatched (is '{route.status}').")
        if route.vehicle_id is None:
            raise DomainError("Assign a vehicle before dispatching.")
        vehicle = await self.repo.get_vehicle(route.vehicle_id, organization_id)
        if vehicle is None or vehicle.status != "available":
            raise DomainError("Assigned vehicle is no longer available.")

        for stop in route.stops:
            delivery = Delivery(
                order_id=stop.order_id, route_plan_id=route.id, status="in_transit"
            )
            self.session.add(delivery)
            await self.session.flush()
            self.session.add(
                DeliveryEvent(
                    delivery_id=delivery.id, event_type="status_change",
                    status="in_transit", recorded_by=actor_id,
                )
            )
        vehicle.status = "on_route"
        route.status = "dispatched"
        self.audit.record("routes.dispatch", actor_id=actor_id, organization_id=organization_id,
                          entity_table="route_plans", entity_id=route.id)
        await self.session.commit()
        return route

    # --- delivery tracking ---------------------------------------------------

    async def record_delivery_event(
        self, delivery_id: str, data: DeliveryEventIn, organization_id: str, actor_id: str
    ) -> Delivery:
        delivery = await self.repo.get_delivery(delivery_id, organization_id)
        if delivery is None:
            raise NotFoundError("Delivery not found.")
        if delivery.status in ("delivered", "failed"):
            raise DomainError(f"Delivery is already {delivery.status}.")

        self.session.add(
            DeliveryEvent(
                delivery_id=delivery.id,
                event_type=data.event_type,
                status=data.status,
                latitude=data.latitude,
                longitude=data.longitude,
                note=data.note,
                recorded_by=actor_id,
            )
        )
        if data.event_type == "status_change" and data.status in ("delivered", "failed"):
            delivery.status = data.status
            if data.status == "delivered":
                delivery.delivered_at = utcnow()
                await self._maybe_fulfil_order(delivery.order_id)
            await self._maybe_complete_route(delivery.route_plan_id, organization_id)

        self.audit.record("deliveries.event", actor_id=actor_id, organization_id=organization_id,
                          entity_table="deliveries", entity_id=delivery.id,
                          after={"type": data.event_type, "status": data.status})
        await self.session.commit()
        return delivery

    async def _maybe_fulfil_order(self, order_id: str) -> None:
        order = await self.session.get(Order, order_id)
        if order is not None and order.status == "confirmed":
            order.status = "fulfilled"

    async def _maybe_complete_route(self, route_id: str | None, organization_id: str) -> None:
        if route_id is None:
            return
        deliveries = await self.repo.deliveries_for_route(route_id)
        if deliveries and all(d.status in ("delivered", "failed") for d in deliveries):
            route = await self.repo.get_route(route_id, organization_id)
            if route is not None:
                route.status = "completed"
                if route.vehicle_id:
                    vehicle = await self.session.get(Vehicle, route.vehicle_id)
                    if vehicle is not None:
                        vehicle.status = "available"
