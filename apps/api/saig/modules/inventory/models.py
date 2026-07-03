from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow

MOVEMENT_TYPES = (
    "receipt",
    "dispatch",
    "transfer_out",
    "transfer_in",
    "adjustment",
    "write_off",
)
TRANSFER_STATUSES = ("pending", "dispatched", "received", "cancelled")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    region_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("regions.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(30))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    capacity_kg: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_warehouses_org_code"),)


class StockLot(Base):
    __tablename__ = "stock_lots"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    variety_id: Mapped[str] = mapped_column(GUID, ForeignKey("seed_varieties.id"))
    lot_number: Mapped[str] = mapped_column(String(60))
    produced_at: Mapped[date] = mapped_column(Date)
    expires_at: Mapped[date] = mapped_column(Date)
    germination_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "lot_number", name="uq_lots_org_number"),
        CheckConstraint("expires_at > produced_at", name="lot_expiry_after_production"),
    )


class StockMovement(Base):
    """Append-only ledger. Balance is derived (v_stock_balances in schema.sql);
    negative balances are prevented in the service under a row lock, never by
    mutating a stored quantity (BR-2)."""

    __tablename__ = "stock_movements"

    # BigInteger on PostgreSQL; SQLite needs plain INTEGER for autoincrement.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    warehouse_id: Mapped[str] = mapped_column(GUID, ForeignKey("warehouses.id"))
    lot_id: Mapped[str] = mapped_column(GUID, ForeignKey("stock_lots.id"))
    movement_type: Mapped[str] = mapped_column(String(20))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 3))  # signed: + in, - out
    transfer_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("stock_transfers.id"), nullable=True
    )
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    performed_by: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    __table_args__ = (Index("ix_stock_movements_balance", "warehouse_id", "lot_id"),)


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    from_warehouse_id: Mapped[str] = mapped_column(GUID, ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[str] = mapped_column(GUID, ForeignKey("warehouses.id"))
    lot_id: Mapped[str] = mapped_column(GUID, ForeignKey("stock_lots.id"))
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 3))
    received_kg: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="pending")
    requested_by: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"))
    variance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint(
            "from_warehouse_id <> to_warehouse_id", name="transfer_distinct_warehouses"
        ),
    )
