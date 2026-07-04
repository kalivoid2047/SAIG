from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.supplychain.models import (
    Delivery,
    DeliveryEvent,
    Order,
    RoutePlan,
    Vehicle,
)
from saig.shared.pagination import PageParams


class SupplyChainRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- vehicles ------------------------------------------------------------

    async def list_vehicles(self, organization_id: str) -> list[Vehicle]:
        stmt = (
            select(Vehicle)
            .where(Vehicle.organization_id == organization_id, Vehicle.deleted_at.is_(None))
            .order_by(Vehicle.registration)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_vehicle(self, vehicle_id: str, organization_id: str) -> Vehicle | None:
        stmt = select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.organization_id == organization_id,
            Vehicle.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_vehicle_by_reg(self, registration: str, organization_id: str) -> Vehicle | None:
        stmt = select(Vehicle).where(
            Vehicle.organization_id == organization_id,
            func.lower(Vehicle.registration) == registration.lower(),
            Vehicle.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- orders --------------------------------------------------------------

    async def get_order(self, order_id: str, organization_id: str) -> Order | None:
        stmt = select(Order).where(
            Order.id == order_id,
            Order.organization_id == organization_id,
            Order.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_orders_by_ids(self, order_ids: list[str], organization_id: str) -> list[Order]:
        if not order_ids:
            return []
        stmt = select(Order).where(
            Order.id.in_(order_ids),
            Order.organization_id == organization_id,
            Order.deleted_at.is_(None),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_orders(
        self, organization_id: str, params: PageParams, status: str | None = None
    ) -> tuple[list[Order], int]:
        conditions = [Order.organization_id == organization_id, Order.deleted_at.is_(None)]
        if status:
            conditions.append(Order.status == status)
        total = (
            await self.session.execute(select(func.count(Order.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            select(Order)
            .where(*conditions)
            .order_by(Order.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def order_ids_already_routed(
        self, organization_id: str, order_ids: list[str]
    ) -> set[str]:
        """Orders attached to a non-cancelled route already."""
        from saig.modules.supplychain.models import RouteStop

        stmt = (
            select(RouteStop.order_id)
            .join(RoutePlan, RoutePlan.id == RouteStop.route_plan_id)
            .where(
                RoutePlan.organization_id == organization_id,
                RoutePlan.status != "cancelled",
                RouteStop.order_id.in_(order_ids),
            )
        )
        return set((await self.session.execute(stmt)).scalars().all())

    # --- route plans ---------------------------------------------------------

    async def get_route(self, route_id: str, organization_id: str) -> RoutePlan | None:
        stmt = select(RoutePlan).where(
            RoutePlan.id == route_id, RoutePlan.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_routes(self, organization_id: str) -> list[RoutePlan]:
        stmt = (
            select(RoutePlan)
            .where(RoutePlan.organization_id == organization_id)
            .order_by(RoutePlan.created_at.desc())
            .limit(200)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def active_routes(self, organization_id: str) -> list[RoutePlan]:
        stmt = select(RoutePlan).where(
            RoutePlan.organization_id == organization_id,
            RoutePlan.status == "dispatched",
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # --- deliveries ----------------------------------------------------------

    async def get_delivery(self, delivery_id: str, organization_id: str) -> Delivery | None:
        stmt = (
            select(Delivery)
            .join(Order, Order.id == Delivery.order_id)
            .where(Delivery.id == delivery_id, Order.organization_id == organization_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_deliveries(
        self, organization_id: str, status: str | None = None, route_id: str | None = None
    ) -> list[Delivery]:
        conditions = [Order.organization_id == organization_id]
        if status:
            conditions.append(Delivery.status == status)
        if route_id:
            conditions.append(Delivery.route_plan_id == route_id)
        stmt = (
            select(Delivery)
            .join(Order, Order.id == Delivery.order_id)
            .where(*conditions)
            .order_by(Delivery.created_at.desc())
            .limit(500)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def deliveries_for_route(self, route_id: str) -> list[Delivery]:
        stmt = select(Delivery).where(Delivery.route_plan_id == route_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_delivery_events(self, delivery_id: str) -> list[DeliveryEvent]:
        stmt = (
            select(DeliveryEvent)
            .where(DeliveryEvent.delivery_id == delivery_id)
            .order_by(DeliveryEvent.occurred_at.desc(), DeliveryEvent.id.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_active_routes(self, organization_id: str) -> int:
        stmt = select(func.count(RoutePlan.id)).where(
            RoutePlan.organization_id == organization_id,
            RoutePlan.status == "dispatched",
        )
        return int((await self.session.execute(stmt)).scalar_one())
