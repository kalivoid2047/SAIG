from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow

VEHICLE_STATUSES = ("available", "on_route", "maintenance", "retired")
ORDER_STATUSES = ("pending", "confirmed", "fulfilled", "cancelled")
ROUTE_STATUSES = ("draft", "planned", "dispatched", "completed", "cancelled")
DELIVERY_STATUSES = ("pending", "assigned", "in_transit", "delivered", "failed")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    registration: Mapped[str] = mapped_column(String(30))
    capacity_kg: Mapped[float] = mapped_column(Numeric(12, 3))
    status: Mapped[str] = mapped_column(String(15), default="available")
    driver_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "registration", name="uq_vehicles_org_reg"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(200))
    region_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("regions.id"), nullable=True)
    destination_lat: Mapped[float] = mapped_column(Numeric(9, 6))
    destination_lng: Mapped[float] = mapped_column(Numeric(9, 6))
    status: Mapped[str] = mapped_column(String(15), default="pending", index=True)
    requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    order_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    variety_id: Mapped[str] = mapped_column(GUID, ForeignKey("seed_varieties.id"))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    order: Mapped[Order] = relationship(back_populates="items")


class RoutePlan(Base):
    __tablename__ = "route_plans"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    origin_warehouse_id: Mapped[str] = mapped_column(GUID, ForeignKey("warehouses.id"))
    vehicle_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="draft", index=True)
    planned_date: Mapped[date] = mapped_column(Date)
    total_distance_km: Mapped[float | None] = mapped_column(Numeric(9, 2), nullable=True)
    optimizer_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route_plan", lazy="selectin", cascade="all, delete-orphan",
        order_by="RouteStop.stop_sequence",
    )


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    route_plan_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("route_plans.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[str] = mapped_column(GUID, ForeignKey("orders.id"))
    stop_sequence: Mapped[int] = mapped_column(SmallInteger)
    eta: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    route_plan: Mapped[RoutePlan] = relationship(back_populates="stops")

    __table_args__ = (
        UniqueConstraint("route_plan_id", "stop_sequence", name="uq_route_stop_seq"),
        UniqueConstraint("route_plan_id", "order_id", name="uq_route_stop_order"),
    )


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    order_id: Mapped[str] = mapped_column(GUID, ForeignKey("orders.id"), index=True)
    route_plan_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("route_plans.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(15), default="pending", index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)


class DeliveryEvent(Base):
    """Timestamped delivery status/location trail (driver check-ins, FR-SC-5)."""

    __tablename__ = "delivery_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    delivery_id: Mapped[str] = mapped_column(GUID, ForeignKey("deliveries.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))  # status_change | location_ping | note
    status: Mapped[str | None] = mapped_column(String(15), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
