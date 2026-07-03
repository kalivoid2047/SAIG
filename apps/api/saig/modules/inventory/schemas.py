from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Warehouses --------------------------------------------------------------

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    region_id: str | None = Field(default=None, alias="regionId")
    capacity_kg: float | None = Field(default=None, gt=0, alias="capacityKg")


class WarehouseOut(ORMModel):
    id: str
    name: str
    code: str
    latitude: float
    longitude: float
    region_id: str | None = Field(default=None, serialization_alias="regionId")
    capacity_kg: float | None = Field(default=None, serialization_alias="capacityKg")


# --- Lots --------------------------------------------------------------------

class LotCreate(BaseModel):
    variety_id: str = Field(alias="varietyId")
    lot_number: str = Field(min_length=1, max_length=60, alias="lotNumber")
    produced_at: date = Field(alias="producedAt")
    expires_at: date = Field(alias="expiresAt")
    germination_pct: float | None = Field(default=None, ge=0, le=100, alias="germinationPct")

    @model_validator(mode="after")
    def _expiry_after_production(self) -> "LotCreate":
        if self.expires_at <= self.produced_at:
            raise ValueError("expiresAt must be after producedAt")
        return self


class LotOut(ORMModel):
    id: str
    variety_id: str = Field(serialization_alias="varietyId")
    lot_number: str = Field(serialization_alias="lotNumber")
    produced_at: date = Field(serialization_alias="producedAt")
    expires_at: date = Field(serialization_alias="expiresAt")
    germination_pct: float | None = Field(default=None, serialization_alias="germinationPct")


# --- Movements ---------------------------------------------------------------

class MovementCreate(BaseModel):
    warehouse_id: str = Field(alias="warehouseId")
    lot_id: str = Field(alias="lotId")
    movement_type: Literal["receipt", "adjustment", "write_off"] = Field(alias="movementType")
    quantity_kg: float = Field(gt=0, alias="quantityKg")
    reference: str | None = Field(default=None, max_length=120)


class MovementOut(ORMModel):
    id: int
    warehouse_id: str = Field(serialization_alias="warehouseId")
    lot_id: str = Field(serialization_alias="lotId")
    movement_type: str = Field(serialization_alias="movementType")
    quantity_kg: float = Field(serialization_alias="quantityKg")
    reference: str | None
    occurred_at: datetime = Field(serialization_alias="occurredAt")


class StockBalanceOut(BaseModel):
    warehouseId: str
    lotId: str
    varietyId: str
    lotNumber: str
    expiresAt: date
    balanceKg: float
    expiringSoon: bool


# --- Transfers ---------------------------------------------------------------

class TransferCreate(BaseModel):
    from_warehouse_id: str = Field(alias="fromWarehouseId")
    to_warehouse_id: str = Field(alias="toWarehouseId")
    lot_id: str = Field(alias="lotId")
    quantity_kg: float = Field(gt=0, alias="quantityKg")

    @model_validator(mode="after")
    def _distinct(self) -> "TransferCreate":
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("source and destination warehouses must differ")
        return self


class TransferReceive(BaseModel):
    received_kg: float = Field(ge=0, alias="receivedKg")


class TransferOut(ORMModel):
    id: str
    from_warehouse_id: str = Field(serialization_alias="fromWarehouseId")
    to_warehouse_id: str = Field(serialization_alias="toWarehouseId")
    lot_id: str = Field(serialization_alias="lotId")
    quantity_kg: float = Field(serialization_alias="quantityKg")
    received_kg: float | None = Field(default=None, serialization_alias="receivedKg")
    status: str
    variance_note: str | None = Field(default=None, serialization_alias="varianceNote")
    created_at: datetime = Field(serialization_alias="createdAt")
