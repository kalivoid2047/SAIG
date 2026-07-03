from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow

# Crop cycle lifecycle (domain-model.md: monotonic transitions).
CROP_STATUSES = ("planned", "planted", "growing", "harvested", "failed")
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"planted", "failed"},
    "planted": {"growing", "failed"},
    "growing": {"harvested", "failed"},
    "harvested": set(),
    "failed": set(),
}

SOIL_TEXTURES = ("sand", "loamy_sand", "sandy_loam", "loam", "silt_loam", "clay_loam", "clay")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_regions_org_code"),)


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    region_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("regions.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200))
    national_id: Mapped[str | None] = mapped_column(String(40), nullable=True)  # PII
    phone: Mapped[str | None] = mapped_column(String(25), nullable=True)  # PII
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # PII
    gender: Mapped[str | None] = mapped_column(String(15), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cooperative: Mapped[str | None] = mapped_column(String(200), nullable=True)
    consent_given_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    registered_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    farms: Mapped[list["Farm"]] = relationship(back_populates="farmer", lazy="selectin")

    __table_args__ = (
        Index(
            "ux_farmers_org_national_id",
            "organization_id",
            "national_id",
            unique=True,
            postgresql_where=Column("national_id").isnot(None) & Column("deleted_at").is_(None),
            sqlite_where=Column("national_id").isnot(None) & Column("deleted_at").is_(None),
        ),
        Index(
            "ux_farmers_org_phone",
            "organization_id",
            "phone",
            unique=True,
            postgresql_where=Column("phone").isnot(None) & Column("deleted_at").is_(None),
            sqlite_where=Column("phone").isnot(None) & Column("deleted_at").is_(None),
        ),
    )


class ProductionRecord(Base):
    __tablename__ = "production_records"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    farmer_id: Mapped[str] = mapped_column(GUID, ForeignKey("farmers.id"), index=True)
    season: Mapped[str] = mapped_column(String(40))
    variety_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("seed_varieties.id"), nullable=True
    )
    area_ha: Mapped[float] = mapped_column(Numeric(10, 4))
    yield_kg: Mapped[float] = mapped_column(Numeric(12, 3))
    source: Mapped[str] = mapped_column(String(20), default="declared")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("farmer_id", "season", "variety_id", name="uq_production_farmer_season"),
    )


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    farmer_id: Mapped[str] = mapped_column(GUID, ForeignKey("farmers.id"), index=True)
    region_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("regions.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    # Portable geo per ADR-0002; PostGIS geometry arrives via additive migration.
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    total_area_ha: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    # joined: many-to-one, always needed with the farm (map popups, lists);
    # avoids async lazy-load faults (MissingGreenlet) outside a greenlet context
    farmer: Mapped[Farmer] = relationship(back_populates="farms", lazy="joined")
    fields: Mapped[list["FieldPlot"]] = relationship(back_populates="farm", lazy="selectin")

    __table_args__ = (Index("ix_farms_lat_lng", "latitude", "longitude"),)


class FieldPlot(Base):
    """A cultivated field. Named FieldPlot to avoid clashing with pydantic.Field."""

    __tablename__ = "fields"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    farm_id: Mapped[str] = mapped_column(GUID, ForeignKey("farms.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    boundary: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # GeoJSON Polygon
    area_ha: Mapped[float] = mapped_column(Numeric(10, 4))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="fields")


class SoilSample(Base):
    __tablename__ = "soil_samples"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    field_id: Mapped[str] = mapped_column(GUID, ForeignKey("fields.id"), index=True)
    sampled_at: Mapped[date] = mapped_column(Date)
    ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    nitrogen_ppm: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    phosphorus_ppm: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    potassium_ppm: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    organic_matter_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    texture: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="lab")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class CropCycle(Base):
    __tablename__ = "crop_cycles"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    field_id: Mapped[str] = mapped_column(GUID, ForeignKey("fields.id"), index=True)
    variety_id: Mapped[str] = mapped_column(GUID, ForeignKey("seed_varieties.id"))
    season: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(15), default="planned", index=True)
    planted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_harvest_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_harvest_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_yield_kg: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    practices: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
