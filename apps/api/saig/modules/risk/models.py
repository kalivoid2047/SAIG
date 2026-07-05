from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow


class RiskAssessment(Base):
    """A daily 0-100 risk score per domain per scope (org-wide when region is
    null), with its factor decomposition. Recompute upserts by natural key."""

    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(GUID, ForeignKey("organizations.id"), index=True)
    region_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("regions.id"), nullable=True)
    domain: Mapped[str] = mapped_column(String(20))
    score: Mapped[int] = mapped_column(SmallInteger)
    factors: Mapped[list] = mapped_column(JSON, default=list)
    assessed_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "region_id", "domain", "assessed_date",
            name="uq_risk_scope_domain_date",
        ),
        Index("ix_risk_trend", "organization_id", "domain", "assessed_date"),
    )
