from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow

DISEASE_REPORT_STATUSES = ("reported", "confirmed", "treated", "resolved", "dismissed")
# Monotonic-ish workflow (FR-CROP-2); any active state can be dismissed.
DISEASE_TRANSITIONS: dict[str, set[str]] = {
    "reported": {"confirmed", "dismissed"},
    "confirmed": {"treated", "dismissed"},
    "treated": {"resolved", "dismissed"},
    "resolved": set(),
    "dismissed": set(),
}


class Disease(Base):
    __tablename__ = "diseases"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    crop: Mapped[str] = mapped_column(String(60))
    pathogen_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_guide: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class DiseaseReport(Base):
    __tablename__ = "disease_reports"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    crop_cycle_id: Mapped[str] = mapped_column(GUID, ForeignKey("crop_cycles.id"), index=True)
    disease_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("diseases.id"), nullable=True
    )
    reported_by: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"))
    severity: Mapped[int] = mapped_column(SmallInteger)  # 1..5
    affected_pct: Mapped[float] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(15), default="reported", index=True)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_outbreak: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
