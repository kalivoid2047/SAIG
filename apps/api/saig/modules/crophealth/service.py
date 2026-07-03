from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.crophealth.models import (
    DISEASE_TRANSITIONS,
    Disease,
    DiseaseReport,
)
from saig.modules.crophealth.repository import CropHealthRepository
from saig.modules.crophealth.schemas import (
    DiseaseCreate,
    DiseaseReportCreate,
)
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.database import utcnow
from saig.shared.errors import DomainError, NotFoundError
from saig.shared.geo import haversine_km

# FR-CROP-3 defaults (configurable later per organization).
OUTBREAK_RADIUS_KM = 10.0
OUTBREAK_WINDOW_DAYS = 7
OUTBREAK_MIN_REPORTS = 3


class CropHealthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CropHealthRepository(session)
        self.audit = AuditService(session)

    # --- disease catalog -----------------------------------------------------

    async def list_diseases(self, organization_id: str) -> list[Disease]:
        return await self.repo.list_diseases(organization_id)

    async def create_disease(
        self, data: DiseaseCreate, organization_id: str, actor_id: str
    ) -> Disease:
        disease = Disease(
            organization_id=organization_id,
            name=data.name,
            crop=data.crop,
            pathogen_type=data.pathogen_type,
            description=data.description,
            treatment_guide=data.treatment_guide,
        )
        self.session.add(disease)
        await self.session.flush()
        self.audit.record("diseases.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="diseases", entity_id=disease.id,
                          after={"name": disease.name, "crop": disease.crop})
        await self.session.commit()
        return disease

    # --- reports -------------------------------------------------------------

    async def create_report(
        self, data: DiseaseReportCreate, organization_id: str, actor_id: str
    ) -> tuple[DiseaseReport, bool]:
        """Creates a report, geotagged from its farm, then runs outbreak
        detection. Returns (report, outbreak_triggered).

        Outbreak scan runs synchronously here; when the PG-backed job runner
        lands (ADR-0001) this moves to a DiseaseReportCreated event handler.
        """
        resolved = await self.repo.resolve_cycle_location(data.crop_cycle_id, organization_id)
        if resolved is None:
            raise NotFoundError("Crop cycle not found.")
        _cycle, lat, lng = resolved

        if data.disease_id is not None:
            if await self.repo.get_disease(data.disease_id, organization_id) is None:
                raise NotFoundError("Disease not found.")

        report = DiseaseReport(
            organization_id=organization_id,
            crop_cycle_id=data.crop_cycle_id,
            disease_id=data.disease_id,
            reported_by=actor_id,
            severity=data.severity,
            affected_pct=data.affected_pct,
            latitude=lat,
            longitude=lng,
            notes=data.notes,
        )
        self.session.add(report)
        await self.session.flush()

        outbreak = await self._scan_outbreak(report, organization_id)

        self.audit.record(
            "disease_reports.create",
            actor_id=actor_id,
            organization_id=organization_id,
            entity_table="disease_reports",
            entity_id=report.id,
            after={"severity": report.severity, "outbreak": outbreak},
        )
        if outbreak:
            self.audit.record(
                "disease_reports.outbreak_detected",
                actor_id=actor_id,
                organization_id=organization_id,
                entity_table="disease_reports",
                entity_id=report.id,
            )
        await self.session.commit()
        return report, outbreak

    async def _scan_outbreak(self, new_report: DiseaseReport, organization_id: str) -> bool:
        since = utcnow() - timedelta(days=OUTBREAK_WINDOW_DAYS)
        pool = await self.repo.recent_reports_for_disease(
            organization_id, new_report.disease_id, since
        )
        cluster = [
            r
            for r in pool
            if haversine_km(
                float(new_report.latitude), float(new_report.longitude),
                float(r.latitude), float(r.longitude),
            )
            <= OUTBREAK_RADIUS_KM
        ]
        if len(cluster) >= OUTBREAK_MIN_REPORTS:
            for r in cluster:
                r.is_outbreak = True
            return True
        return False

    async def transition_report(
        self, report_id: str, to: str, organization_id: str, actor_id: str
    ) -> DiseaseReport:
        report = await self.repo.get_report(report_id, organization_id)
        if report is None:
            raise NotFoundError("Disease report not found.")
        allowed = DISEASE_TRANSITIONS[report.status]
        if to not in allowed:
            raise DomainError(
                f"Cannot move report from '{report.status}' to '{to}'. "
                f"Allowed: {sorted(allowed) or 'none (terminal)'}."
            )
        before = report.status
        report.status = to
        self.audit.record("disease_reports.transition", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="disease_reports", entity_id=report.id,
                          before={"status": before}, after={"status": to})
        await self.session.commit()
        return report

    async def confirm_disease(
        self, report_id: str, disease_id: str, organization_id: str, actor_id: str
    ) -> DiseaseReport:
        report = await self.repo.get_report(report_id, organization_id)
        if report is None:
            raise NotFoundError("Disease report not found.")
        if await self.repo.get_disease(disease_id, organization_id) is None:
            raise NotFoundError("Disease not found.")
        report.disease_id = disease_id
        await self.session.commit()
        return report
