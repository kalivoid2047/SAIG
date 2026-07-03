from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.crophealth.models import Disease, DiseaseReport
from saig.modules.fieldops.models import CropCycle, Farm, FieldPlot
from saig.shared.pagination import PageParams


class CropHealthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_diseases(self, organization_id: str) -> list[Disease]:
        stmt = (
            select(Disease)
            .where(Disease.organization_id == organization_id)
            .order_by(Disease.crop, Disease.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_disease(self, disease_id: str, organization_id: str) -> Disease | None:
        stmt = select(Disease).where(
            Disease.id == disease_id, Disease.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_report(self, report_id: str, organization_id: str) -> DiseaseReport | None:
        stmt = select(DiseaseReport).where(
            DiseaseReport.id == report_id,
            DiseaseReport.organization_id == organization_id,
            DiseaseReport.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def resolve_cycle_location(
        self, crop_cycle_id: str, organization_id: str
    ) -> tuple[CropCycle, float, float] | None:
        """Cycle + its farm's coordinates (geotag source, UC-03)."""
        stmt = (
            select(CropCycle, Farm.latitude, Farm.longitude)
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(
                CropCycle.id == crop_cycle_id,
                Farm.organization_id == organization_id,
                CropCycle.deleted_at.is_(None),
            )
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        cycle, lat, lng = row
        return cycle, float(lat), float(lng)

    async def list_reports(
        self,
        organization_id: str,
        params: PageParams,
        status: str | None = None,
        disease_id: str | None = None,
    ) -> tuple[list[DiseaseReport], int]:
        conditions = [
            DiseaseReport.organization_id == organization_id,
            DiseaseReport.deleted_at.is_(None),
        ]
        if status:
            conditions.append(DiseaseReport.status == status)
        if disease_id:
            conditions.append(DiseaseReport.disease_id == disease_id)
        total = (
            await self.session.execute(
                select(func.count(DiseaseReport.id)).where(*conditions)
            )
        ).scalar_one()
        stmt = (
            select(DiseaseReport)
            .where(*conditions)
            .order_by(DiseaseReport.reported_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def recent_reports_for_disease(
        self, organization_id: str, disease_id: str | None, since: datetime
    ) -> list[DiseaseReport]:
        """Active reports of the same disease since a cutoff — the outbreak
        candidate pool (FR-CROP-3)."""
        conditions = [
            DiseaseReport.organization_id == organization_id,
            DiseaseReport.deleted_at.is_(None),
            DiseaseReport.reported_at >= since,
            DiseaseReport.status.in_(("reported", "confirmed", "treated")),
        ]
        conditions.append(
            DiseaseReport.disease_id == disease_id
            if disease_id is not None
            else DiseaseReport.disease_id.is_(None)
        )
        stmt = select(DiseaseReport).where(*conditions)
        return list((await self.session.execute(stmt)).scalars().all())

    async def heatmap_points(
        self, organization_id: str
    ) -> list[DiseaseReport]:
        stmt = select(DiseaseReport).where(
            DiseaseReport.organization_id == organization_id,
            DiseaseReport.deleted_at.is_(None),
            DiseaseReport.status.in_(("reported", "confirmed", "treated")),
        )
        return list((await self.session.execute(stmt)).scalars().all())
