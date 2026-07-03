from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.fieldops.models import (
    ALLOWED_TRANSITIONS,
    CropCycle,
    Farm,
    Farmer,
    FieldPlot,
    ProductionRecord,
    Region,
    SoilSample,
)
from saig.modules.fieldops.repository import FieldOpsRepository
from saig.modules.fieldops.schemas import (
    CropCycleCreate,
    CropCycleTransition,
    FarmCreate,
    FarmerCreate,
    FarmerUpdate,
    FarmUpdate,
    FieldCreate,
    ProductionRecordCreate,
    RegionCreate,
    RegionUpdate,
    SoilSampleCreate,
)
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.database import utcnow
from saig.shared.errors import ConflictError, DomainError, NotFoundError
from saig.shared.geo import polygon_area_hectares
from saig.shared.pagination import PageParams


def mask_pii(farmer: Farmer) -> Farmer:
    """Redact PII in place on a detached copy of values (NFR-SEC5).

    Last characters are kept so officers can confirm identity verbally
    without full disclosure.
    """
    if farmer.national_id:
        farmer.national_id = "•••" + farmer.national_id[-2:]
    if farmer.phone:
        farmer.phone = "•••" + farmer.phone[-3:]
    if farmer.email:
        name, _, domain = farmer.email.partition("@")
        farmer.email = (name[:1] + "•••@" + domain) if domain else "•••"
    return farmer


class RegionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FieldOpsRepository(session)
        self.audit = AuditService(session)

    async def list_regions(self, organization_id: str) -> list[Region]:
        return await self.repo.list_regions(organization_id)

    async def create_region(
        self, data: RegionCreate, organization_id: str, actor_id: str
    ) -> Region:
        if await self.repo.get_region_by_code(data.code, organization_id) is not None:
            raise ConflictError("A region with this code already exists.")
        region = Region(organization_id=organization_id, name=data.name, code=data.code.upper())
        self.session.add(region)
        await self.session.flush()
        self.audit.record("regions.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="regions", entity_id=region.id,
                          after={"name": region.name, "code": region.code})
        await self.session.commit()
        return region

    async def update_region(
        self, region_id: str, data: RegionUpdate, organization_id: str, actor_id: str
    ) -> Region:
        region = await self.repo.get_region(region_id, organization_id)
        if region is None:
            raise NotFoundError("Region not found.")
        if data.name is not None:
            region.name = data.name
        self.audit.record("regions.update", actor_id=actor_id, organization_id=organization_id,
                          entity_table="regions", entity_id=region.id)
        await self.session.commit()
        return region

    async def delete_region(self, region_id: str, organization_id: str, actor_id: str) -> None:
        region = await self.repo.get_region(region_id, organization_id)
        if region is None:
            raise NotFoundError("Region not found.")
        region.deleted_at = utcnow()
        self.audit.record("regions.delete", actor_id=actor_id, organization_id=organization_id,
                          entity_table="regions", entity_id=region.id,
                          before={"name": region.name, "code": region.code})
        await self.session.commit()


class FarmerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FieldOpsRepository(session)
        self.audit = AuditService(session)

    async def list_farmers(
        self,
        organization_id: str,
        params: PageParams,
        search: str | None,
        region_id: str | None,
        include_pii: bool,
    ) -> tuple[list[Farmer], int]:
        farmers, total = await self.repo.list_farmers(organization_id, params, search, region_id)
        if not include_pii:
            farmers = [mask_pii(f) for f in farmers]
            # masked values must never be flushed back
            for f in farmers:
                self.session.expunge(f)
        return farmers, total

    async def get_farmer(
        self, farmer_id: str, organization_id: str, include_pii: bool, actor_id: str
    ) -> Farmer:
        farmer = await self.repo.get_farmer(farmer_id, organization_id)
        if farmer is None:
            raise NotFoundError("Farmer not found.")
        if include_pii:
            # FR-FRM-5: every unmasked PII read is audit-logged.
            self.audit.record("farmers.read_pii", actor_id=actor_id,
                              organization_id=organization_id,
                              entity_table="farmers", entity_id=farmer.id)
            await self.session.commit()
        else:
            self.session.expunge(farmer)
            mask_pii(farmer)
        return farmer

    async def create_farmer(
        self, data: FarmerCreate, organization_id: str, actor_id: str
    ) -> Farmer:
        duplicate = await self.repo.find_farmer_duplicate(
            organization_id, data.national_id, data.phone
        )
        if duplicate is not None:
            raise ConflictError(
                "A farmer with this national ID or phone already exists.",
                extra={"existingFarmerId": duplicate.id},
            )
        if data.region_id is not None:
            if await self.repo.get_region(data.region_id, organization_id) is None:
                raise NotFoundError("Region not found.")
        farmer = Farmer(
            organization_id=organization_id,
            region_id=data.region_id,
            full_name=data.full_name,
            national_id=data.national_id,
            phone=data.phone,
            email=str(data.email) if data.email else None,
            gender=data.gender,
            birth_year=data.birth_year,
            cooperative=data.cooperative,
            consent_given_at=utcnow(),  # schema enforces consent_given=True
            registered_by=actor_id,
            farms=[],  # mark collection loaded: serializers read it post-commit (async: no lazy IO)
        )
        self.session.add(farmer)
        await self.session.flush()
        self.audit.record("farmers.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="farmers", entity_id=farmer.id,
                          after={"full_name": farmer.full_name, "region_id": farmer.region_id})
        await self.session.commit()
        return farmer

    async def update_farmer(
        self, farmer_id: str, data: FarmerUpdate, organization_id: str, actor_id: str
    ) -> Farmer:
        farmer = await self.repo.get_farmer(farmer_id, organization_id)
        if farmer is None:
            raise NotFoundError("Farmer not found.")
        if data.phone is not None:
            dup = await self.repo.find_farmer_duplicate(
                organization_id, None, data.phone, exclude_id=farmer.id
            )
            if dup is not None:
                raise ConflictError("Another farmer already uses this phone number.")
            farmer.phone = data.phone
        if data.full_name is not None:
            farmer.full_name = data.full_name
        if data.email is not None:
            farmer.email = str(data.email)
        if data.cooperative is not None:
            farmer.cooperative = data.cooperative
        if data.region_id is not None:
            if await self.repo.get_region(data.region_id, organization_id) is None:
                raise NotFoundError("Region not found.")
            farmer.region_id = data.region_id
        self.audit.record("farmers.update", actor_id=actor_id, organization_id=organization_id,
                          entity_table="farmers", entity_id=farmer.id)
        await self.session.commit()
        return farmer

    async def delete_farmer(self, farmer_id: str, organization_id: str, actor_id: str) -> None:
        farmer = await self.repo.get_farmer(farmer_id, organization_id)
        if farmer is None:
            raise NotFoundError("Farmer not found.")
        farmer.deleted_at = utcnow()
        self.audit.record("farmers.delete", actor_id=actor_id, organization_id=organization_id,
                          entity_table="farmers", entity_id=farmer.id,
                          before={"full_name": farmer.full_name})
        await self.session.commit()

    async def add_production_record(
        self, farmer_id: str, data: ProductionRecordCreate, organization_id: str, actor_id: str
    ) -> ProductionRecord:
        farmer = await self.repo.get_farmer(farmer_id, organization_id)
        if farmer is None:
            raise NotFoundError("Farmer not found.")
        if data.variety_id is not None:
            if await self.repo.get_variety(data.variety_id, organization_id) is None:
                raise NotFoundError("Seed variety not found.")
        existing = await self.repo.list_production_records(farmer_id)
        if any(r.season == data.season and r.variety_id == data.variety_id for r in existing):
            raise ConflictError("A record for this season and variety already exists.")
        record = ProductionRecord(
            farmer_id=farmer_id,
            season=data.season,
            variety_id=data.variety_id,
            area_ha=data.area_ha,
            yield_kg=data.yield_kg,
            source=data.source,
        )
        self.session.add(record)
        await self.session.flush()
        self.audit.record("farmers.production_record", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="production_records", entity_id=record.id)
        await self.session.commit()
        return record

    async def list_production_records(
        self, farmer_id: str, organization_id: str
    ) -> list[ProductionRecord]:
        if await self.repo.get_farmer(farmer_id, organization_id) is None:
            raise NotFoundError("Farmer not found.")
        return await self.repo.list_production_records(farmer_id)


class FarmService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FieldOpsRepository(session)
        self.audit = AuditService(session)

    async def list_farms(self, organization_id: str, farmer_id: str | None) -> list[Farm]:
        return await self.repo.list_farms(organization_id, farmer_id)

    async def get_farm(self, farm_id: str, organization_id: str) -> Farm:
        farm = await self.repo.get_farm(farm_id, organization_id)
        if farm is None:
            raise NotFoundError("Farm not found.")
        return farm

    async def create_farm(self, data: FarmCreate, organization_id: str, actor_id: str) -> Farm:
        if await self.repo.get_farmer(data.farmer_id, organization_id) is None:
            raise NotFoundError("Farmer not found.")
        if data.region_id is not None:
            if await self.repo.get_region(data.region_id, organization_id) is None:
                raise NotFoundError("Region not found.")
        farm = Farm(
            organization_id=organization_id,
            farmer_id=data.farmer_id,
            region_id=data.region_id,
            name=data.name,
            latitude=data.latitude,
            longitude=data.longitude,
            total_area_ha=data.total_area_ha,
            fields=[],  # mark collection loaded (async: no lazy IO on serialization)
        )
        self.session.add(farm)
        await self.session.flush()
        self.audit.record("farms.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="farms", entity_id=farm.id,
                          after={"name": farm.name, "farmer_id": farm.farmer_id})
        await self.session.commit()
        return farm

    async def update_farm(
        self, farm_id: str, data: FarmUpdate, organization_id: str, actor_id: str
    ) -> Farm:
        farm = await self.get_farm(farm_id, organization_id)
        if data.name is not None:
            farm.name = data.name
        if data.latitude is not None:
            farm.latitude = data.latitude
        if data.longitude is not None:
            farm.longitude = data.longitude
        if data.total_area_ha is not None:
            farm.total_area_ha = data.total_area_ha
        if data.region_id is not None:
            if await self.repo.get_region(data.region_id, organization_id) is None:
                raise NotFoundError("Region not found.")
            farm.region_id = data.region_id
        self.audit.record("farms.update", actor_id=actor_id, organization_id=organization_id,
                          entity_table="farms", entity_id=farm.id)
        await self.session.commit()
        return farm

    async def delete_farm(self, farm_id: str, organization_id: str, actor_id: str) -> None:
        farm = await self.get_farm(farm_id, organization_id)
        farm.deleted_at = utcnow()
        self.audit.record("farms.delete", actor_id=actor_id, organization_id=organization_id,
                          entity_table="farms", entity_id=farm.id, before={"name": farm.name})
        await self.session.commit()

    async def add_field(
        self, farm_id: str, data: FieldCreate, organization_id: str, actor_id: str
    ) -> FieldPlot:
        farm = await self.get_farm(farm_id, organization_id)
        if data.boundary is not None:
            area_ha = polygon_area_hectares(data.boundary)
            if area_ha <= 0:
                raise DomainError("Field boundary encloses no area.")
            boundary = data.boundary.model_dump_geojson()
        else:
            if data.area_ha is None:
                raise DomainError("Provide either a boundary polygon or an explicit area.")
            area_ha = data.area_ha
            boundary = None
        field = FieldPlot(farm_id=farm.id, name=data.name, boundary=boundary, area_ha=area_ha)
        self.session.add(field)
        await self.session.flush()
        self.audit.record("fields.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="fields", entity_id=field.id,
                          after={"name": field.name, "area_ha": float(area_ha)})
        await self.session.commit()
        return field

    async def delete_field(self, field_id: str, organization_id: str, actor_id: str) -> None:
        field = await self.repo.get_field(field_id, organization_id)
        if field is None:
            raise NotFoundError("Field not found.")
        field.deleted_at = utcnow()
        self.audit.record("fields.delete", actor_id=actor_id, organization_id=organization_id,
                          entity_table="fields", entity_id=field.id)
        await self.session.commit()

    async def add_soil_sample(
        self, field_id: str, data: SoilSampleCreate, organization_id: str, actor_id: str
    ) -> SoilSample:
        field = await self.repo.get_field(field_id, organization_id)
        if field is None:
            raise NotFoundError("Field not found.")
        sample = SoilSample(
            field_id=field.id,
            sampled_at=data.sampled_at,
            ph=data.ph,
            nitrogen_ppm=data.nitrogen_ppm,
            phosphorus_ppm=data.phosphorus_ppm,
            potassium_ppm=data.potassium_ppm,
            organic_matter_pct=data.organic_matter_pct,
            texture=data.texture,
            source=data.source,
        )
        self.session.add(sample)
        await self.session.flush()
        self.audit.record("soil_samples.create", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="soil_samples", entity_id=sample.id)
        await self.session.commit()
        return sample

    async def list_soil_samples(
        self, field_id: str, organization_id: str
    ) -> list[SoilSample]:
        if await self.repo.get_field(field_id, organization_id) is None:
            raise NotFoundError("Field not found.")
        return await self.repo.list_soil_samples(field_id)


class CropService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FieldOpsRepository(session)
        self.audit = AuditService(session)

    async def list_cycles(
        self,
        organization_id: str,
        params: PageParams,
        status: str | None,
        season: str | None,
        field_id: str | None,
    ) -> tuple[list[CropCycle], int]:
        return await self.repo.list_crop_cycles(organization_id, params, status, season, field_id)

    async def get_cycle(self, cycle_id: str, organization_id: str) -> CropCycle:
        cycle = await self.repo.get_crop_cycle(cycle_id, organization_id)
        if cycle is None:
            raise NotFoundError("Crop cycle not found.")
        return cycle

    async def create_cycle(
        self, field_id: str, data: CropCycleCreate, organization_id: str, actor_id: str
    ) -> CropCycle:
        field = await self.repo.get_field(field_id, organization_id)
        if field is None:
            raise NotFoundError("Field not found.")
        if await self.repo.get_variety(data.variety_id, organization_id) is None:
            raise NotFoundError("Seed variety not found.")
        if await self.repo.find_active_cycle(field_id, data.season) is not None:
            raise ConflictError("This field already has an active cycle for the season.")
        cycle = CropCycle(
            field_id=field_id,
            variety_id=data.variety_id,
            season=data.season,
            expected_harvest_at=data.expected_harvest_at,
            practices=data.practices,
        )
        self.session.add(cycle)
        await self.session.flush()
        self.audit.record("crop_cycles.create", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="crop_cycles", entity_id=cycle.id,
                          after={"season": cycle.season, "variety_id": cycle.variety_id})
        await self.session.commit()
        return cycle

    async def transition(
        self,
        cycle_id: str,
        data: CropCycleTransition,
        organization_id: str,
        actor_id: str,
    ) -> CropCycle:
        cycle = await self.get_cycle(cycle_id, organization_id)
        allowed = ALLOWED_TRANSITIONS[cycle.status]
        if data.to not in allowed:
            raise DomainError(
                f"Cannot transition from '{cycle.status}' to '{data.to}'. "
                f"Allowed: {sorted(allowed) or 'none (terminal state)'}."
            )
        if data.to == "harvested" and data.actual_yield_kg is None:
            raise DomainError("Recording the harvest requires actualYieldKg.")
        if data.to != "harvested" and data.actual_yield_kg is not None:
            raise DomainError("actualYieldKg is only valid when transitioning to harvested.")

        occurred = data.occurred_on or date.today()
        before_status = cycle.status
        cycle.status = data.to
        if data.to == "planted":
            cycle.planted_at = occurred
        elif data.to == "harvested":
            cycle.actual_harvest_at = occurred
            cycle.actual_yield_kg = data.actual_yield_kg

        self.audit.record("crop_cycles.transition", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="crop_cycles", entity_id=cycle.id,
                          before={"status": before_status}, after={"status": cycle.status})
        await self.session.commit()
        return cycle
