from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow

MODEL_STATUSES = ("trained", "evaluated", "promoted", "retired")


class ModelVersion(Base):
    """Registry row. Exactly one 'promoted' version per model serves (BR-3)."""

    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(60))  # yield | demand
    version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(15), default="trained")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_key: Mapped[str] = mapped_column(String(200))
    training_rows: Mapped[int | None] = mapped_column(Numeric(10, 0), nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    promoted_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "model_name", "version", name="uq_model_version"),
        # one promoted version per (org, model) — enforced in service + partial index
        Index(
            "ux_model_promoted",
            "organization_id",
            "model_name",
            unique=True,
            postgresql_where=text("status = 'promoted'"),
            sqlite_where=text("status = 'promoted'"),
        ),
    )


class FeatureSnapshot(Base):
    """Immutable snapshot of the exact inputs used for a prediction (BR-3)."""

    __tablename__ = "feature_snapshots"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    entity_type: Mapped[str] = mapped_column(String(40))  # crop_cycle | region_variety
    entity_id: Mapped[str] = mapped_column(String(80))
    features: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    model_version_id: Mapped[str] = mapped_column(GUID, ForeignKey("model_versions.id"))
    run_type: Mapped[str] = mapped_column(String(15))  # scheduled | manual | scenario
    triggered_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


class YieldPredictionRow(Base):
    __tablename__ = "yield_predictions"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    prediction_run_id: Mapped[str] = mapped_column(GUID, ForeignKey("prediction_runs.id"))
    crop_cycle_id: Mapped[str] = mapped_column(GUID, ForeignKey("crop_cycles.id"), index=True)
    feature_snapshot_id: Mapped[str] = mapped_column(GUID, ForeignKey("feature_snapshots.id"))
    predicted_yield_kg_ha: Mapped[float] = mapped_column(Numeric(10, 2))
    pi_low_kg_ha: Mapped[float] = mapped_column(Numeric(10, 2))
    pi_high_kg_ha: Mapped[float] = mapped_column(Numeric(10, 2))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    low_confidence: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)


class DemandForecastRow(Base):
    __tablename__ = "demand_forecasts"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    prediction_run_id: Mapped[str] = mapped_column(GUID, ForeignKey("prediction_runs.id"))
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    region_id: Mapped[str] = mapped_column(GUID, ForeignKey("regions.id"))
    variety_id: Mapped[str] = mapped_column(GUID, ForeignKey("seed_varieties.id"))
    period_month: Mapped[date] = mapped_column(Date)
    forecast_qty_kg: Mapped[float] = mapped_column(Numeric(14, 3))
    pi_low_kg: Mapped[float] = mapped_column(Numeric(14, 3))
    pi_high_kg: Mapped[float] = mapped_column(Numeric(14, 3))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    seasonal_component: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)

    __table_args__ = (
        Index("ix_demand_fc_lookup", "region_id", "variety_id", "period_month", "created_at"),
    )


class SalesHistory(Base):
    """Historical + ongoing sales — training data for the demand model."""

    __tablename__ = "sales_history"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    region_id: Mapped[str] = mapped_column(GUID, ForeignKey("regions.id"))
    variety_id: Mapped[str] = mapped_column(GUID, ForeignKey("seed_varieties.id"))
    period_month: Mapped[date] = mapped_column(Date)
    quantity_kg: Mapped[float] = mapped_column(Numeric(14, 3))
    revenue: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), default="direct")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "region_id", "variety_id", "period_month", "channel",
            name="uq_sales_history_segment",
        ),
    )
