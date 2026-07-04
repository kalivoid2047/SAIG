from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Vehicles ----------------------------------------------------------------

class VehicleCreate(BaseModel):
    registration: str = Field(min_length=1, max_length=30)
    capacity_kg: float = Field(gt=0, alias="capacityKg")
    driver_id: str | None = Field(default=None, alias="driverId")


class VehicleUpdate(BaseModel):
    status: Literal["available", "on_route", "maintenance", "retired"] | None = None
    capacity_kg: float | None = Field(default=None, gt=0, alias="capacityKg")
    driver_id: str | None = Field(default=None, alias="driverId")


class VehicleOut(ORMModel):
    id: str
    registration: str
    capacity_kg: float = Field(serialization_alias="capacityKg")
    status: str
    driver_id: str | None = Field(default=None, serialization_alias="driverId")


# --- Orders ------------------------------------------------------------------

class OrderItemIn(BaseModel):
    variety_id: str = Field(alias="varietyId")
    quantity_kg: float = Field(gt=0, alias="quantityKg")
    unit_price: float | None = Field(default=None, ge=0, alias="unitPrice")


class OrderItemOut(ORMModel):
    id: str
    variety_id: str = Field(serialization_alias="varietyId")
    quantity_kg: float = Field(serialization_alias="quantityKg")
    unit_price: float | None = Field(default=None, serialization_alias="unitPrice")


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200, alias="customerName")
    destination_lat: float = Field(ge=-90, le=90, alias="destinationLat")
    destination_lng: float = Field(ge=-180, le=180, alias="destinationLng")
    region_id: str | None = Field(default=None, alias="regionId")
    requested_date: date | None = Field(default=None, alias="requestedDate")
    items: list[OrderItemIn] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    status: Literal["confirmed", "cancelled"]


class OrderOut(ORMModel):
    id: str
    customer_name: str = Field(serialization_alias="customerName")
    region_id: str | None = Field(default=None, serialization_alias="regionId")
    destination_lat: float = Field(serialization_alias="destinationLat")
    destination_lng: float = Field(serialization_alias="destinationLng")
    status: str
    requested_date: date | None = Field(default=None, serialization_alias="requestedDate")
    created_at: datetime = Field(serialization_alias="createdAt")
    items: list[OrderItemOut] = []


# --- Route plans -------------------------------------------------------------

class RoutePlanCreate(BaseModel):
    origin_warehouse_id: str = Field(alias="originWarehouseId")
    planned_date: date = Field(alias="plannedDate")
    vehicle_id: str | None = Field(default=None, alias="vehicleId")
    order_ids: list[str] = Field(min_length=1, alias="orderIds")


class RouteStopOut(ORMModel):
    id: str
    order_id: str = Field(serialization_alias="orderId")
    stop_sequence: int = Field(serialization_alias="stopSequence")
    eta: datetime | None = None


class RoutePlanOut(ORMModel):
    id: str
    origin_warehouse_id: str = Field(serialization_alias="originWarehouseId")
    vehicle_id: str | None = Field(default=None, serialization_alias="vehicleId")
    driver_id: str | None = Field(default=None, serialization_alias="driverId")
    status: str
    planned_date: date = Field(serialization_alias="plannedDate")
    total_distance_km: float | None = Field(default=None, serialization_alias="totalDistanceKm")
    optimizer_meta: dict | None = Field(default=None, serialization_alias="optimizerMeta")
    stops: list[RouteStopOut] = []


# --- Deliveries --------------------------------------------------------------

class DeliveryEventIn(BaseModel):
    event_type: Literal["status_change", "location_ping", "note"] = Field(alias="eventType")
    status: Literal["in_transit", "delivered", "failed"] | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    note: str | None = Field(default=None, max_length=1000)


class DeliveryEventOut(ORMModel):
    id: int
    event_type: str = Field(serialization_alias="eventType")
    status: str | None
    latitude: float | None
    longitude: float | None
    note: str | None
    occurred_at: datetime = Field(serialization_alias="occurredAt")


class DeliveryOut(ORMModel):
    id: str
    order_id: str = Field(serialization_alias="orderId")
    route_plan_id: str | None = Field(default=None, serialization_alias="routePlanId")
    status: str
    delivered_at: datetime | None = Field(default=None, serialization_alias="deliveredAt")
    created_at: datetime = Field(serialization_alias="createdAt")
