from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow


class SeedVariety(Base):
    __tablename__ = "seed_varieties"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    crop: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(30))
    maturity_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    yield_potential_kg_ha: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    drought_tolerance: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # 1..5
    disease_tolerance: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # 1..5
    characteristics: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    suitability: Mapped[list["VarietySuitability"]] = relationship(
        back_populates="variety", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ux_varieties_org_code",
            "organization_id",
            "code",
            unique=True,
            postgresql_where=Column("deleted_at").is_(None),
            sqlite_where=Column("deleted_at").is_(None),
        ),
    )


class VarietySuitability(Base):
    __tablename__ = "variety_region_suitability"

    variety_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("seed_varieties.id", ondelete="CASCADE"), primary_key=True
    )
    region_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int] = mapped_column(SmallInteger)  # 1..5
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    variety: Mapped[SeedVariety] = relationship(back_populates="suitability")
