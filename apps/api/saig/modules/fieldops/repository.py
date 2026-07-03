from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.catalog.models import SeedVariety
from saig.modules.fieldops.models import (
    CropCycle,
    Farm,
    Farmer,
    FieldPlot,
    ProductionRecord,
    Region,
    SoilSample,
)
from saig.shared.pagination import PageParams


class FieldOpsRepository:
    """Org-scoped persistence for the Field Operations bounded context."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- regions -----------------------------------------------------------

    async def list_regions(self, organization_id: str) -> list[Region]:
        stmt = (
            select(Region)
            .where(Region.organization_id == organization_id, Region.deleted_at.is_(None))
            .order_by(Region.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_region(self, region_id: str, organization_id: str) -> Region | None:
        stmt = select(Region).where(
            Region.id == region_id,
            Region.organization_id == organization_id,
            Region.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_region_by_code(self, code: str, organization_id: str) -> Region | None:
        stmt = select(Region).where(
            Region.organization_id == organization_id,
            func.lower(Region.code) == code.lower(),
            Region.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- farmers ------------------------------------------------------------

    async def get_farmer(self, farmer_id: str, organization_id: str) -> Farmer | None:
        stmt = select(Farmer).where(
            Farmer.id == farmer_id,
            Farmer.organization_id == organization_id,
            Farmer.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_farmer_duplicate(
        self,
        organization_id: str,
        national_id: str | None,
        phone: str | None,
        exclude_id: str | None = None,
    ) -> Farmer | None:
        conditions = []
        if national_id:
            conditions.append(Farmer.national_id == national_id)
        if phone:
            conditions.append(Farmer.phone == phone)
        if not conditions:
            return None
        stmt = select(Farmer).where(
            Farmer.organization_id == organization_id,
            Farmer.deleted_at.is_(None),
            or_(*conditions),
        )
        if exclude_id:
            stmt = stmt.where(Farmer.id != exclude_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def list_farmers(
        self,
        organization_id: str,
        params: PageParams,
        search: str | None = None,
        region_id: str | None = None,
    ) -> tuple[list[Farmer], int]:
        conditions = [
            Farmer.organization_id == organization_id,
            Farmer.deleted_at.is_(None),
        ]
        if search:
            like = f"%{search.lower()}%"
            conditions.append(func.lower(Farmer.full_name).like(like))
        if region_id:
            conditions.append(Farmer.region_id == region_id)
        total = (
            await self.session.execute(select(func.count(Farmer.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            select(Farmer)
            .where(*conditions)
            .order_by(Farmer.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        farmers = list((await self.session.execute(stmt)).scalars().all())
        return farmers, total

    async def list_production_records(self, farmer_id: str) -> list[ProductionRecord]:
        stmt = (
            select(ProductionRecord)
            .where(ProductionRecord.farmer_id == farmer_id)
            .order_by(ProductionRecord.season.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # --- farms / fields --------------------------------------------------------

    async def get_farm(self, farm_id: str, organization_id: str) -> Farm | None:
        stmt = select(Farm).where(
            Farm.id == farm_id,
            Farm.organization_id == organization_id,
            Farm.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_farms(
        self,
        organization_id: str,
        farmer_id: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[Farm]:
        conditions = [Farm.organization_id == organization_id, Farm.deleted_at.is_(None)]
        if farmer_id:
            conditions.append(Farm.farmer_id == farmer_id)
        if bbox:
            min_lat, min_lng, max_lat, max_lng = bbox
            conditions += [
                Farm.latitude >= min_lat,
                Farm.latitude <= max_lat,
                Farm.longitude >= min_lng,
                Farm.longitude <= max_lng,
            ]
        stmt = select(Farm).where(*conditions).order_by(Farm.created_at.desc()).limit(2000)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_field(self, field_id: str, organization_id: str) -> FieldPlot | None:
        stmt = (
            select(FieldPlot)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(
                FieldPlot.id == field_id,
                Farm.organization_id == organization_id,
                FieldPlot.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_soil_samples(self, field_id: str) -> list[SoilSample]:
        stmt = (
            select(SoilSample)
            .where(SoilSample.field_id == field_id)
            .order_by(SoilSample.sampled_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # --- crop cycles -------------------------------------------------------------

    async def get_crop_cycle(self, cycle_id: str, organization_id: str) -> CropCycle | None:
        stmt = (
            select(CropCycle)
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(
                CropCycle.id == cycle_id,
                Farm.organization_id == organization_id,
                CropCycle.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_active_cycle(self, field_id: str, season: str) -> CropCycle | None:
        stmt = select(CropCycle).where(
            CropCycle.field_id == field_id,
            CropCycle.season == season,
            CropCycle.status.in_(("planned", "planted", "growing")),
            CropCycle.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_crop_cycles(
        self,
        organization_id: str,
        params: PageParams,
        status: str | None = None,
        season: str | None = None,
        field_id: str | None = None,
    ) -> tuple[list[CropCycle], int]:
        conditions = [Farm.organization_id == organization_id, CropCycle.deleted_at.is_(None)]
        if status:
            conditions.append(CropCycle.status == status)
        if season:
            conditions.append(CropCycle.season == season)
        if field_id:
            conditions.append(CropCycle.field_id == field_id)
        base = (
            select(CropCycle)
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(*conditions)
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        stmt = (
            base.order_by(CropCycle.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        cycles = list((await self.session.execute(stmt)).scalars().all())
        return cycles, total

    # --- catalog lookups (cross-context read, by id only) ---------------------------

    async def get_variety(self, variety_id: str, organization_id: str) -> SeedVariety | None:
        stmt = select(SeedVariety).where(
            SeedVariety.id == variety_id,
            SeedVariety.organization_id == organization_id,
            SeedVariety.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
