from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.catalog.models import SeedVariety, VarietySuitability
from saig.modules.catalog.schemas import SuitabilityEntry, VarietyCreate, VarietyUpdate
from saig.modules.fieldops.models import Region
from saig.modules.iam.services.audit_service import AuditService
from saig.shared.database import utcnow
from saig.shared.errors import ConflictError, DomainError, NotFoundError


class CatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def list_varieties(
        self, organization_id: str, crop: str | None = None, include_inactive: bool = False
    ) -> list[SeedVariety]:
        conditions = [
            SeedVariety.organization_id == organization_id,
            SeedVariety.deleted_at.is_(None),
        ]
        if crop:
            conditions.append(func.lower(SeedVariety.crop) == crop.lower())
        if not include_inactive:
            conditions.append(SeedVariety.is_active.is_(True))
        stmt = select(SeedVariety).where(*conditions).order_by(SeedVariety.crop, SeedVariety.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_variety(self, variety_id: str, organization_id: str) -> SeedVariety:
        stmt = select(SeedVariety).where(
            SeedVariety.id == variety_id,
            SeedVariety.organization_id == organization_id,
            SeedVariety.deleted_at.is_(None),
        )
        variety = (await self.session.execute(stmt)).scalar_one_or_none()
        if variety is None:
            raise NotFoundError("Seed variety not found.")
        return variety

    async def create_variety(
        self, data: VarietyCreate, organization_id: str, actor_id: str
    ) -> SeedVariety:
        stmt = select(SeedVariety).where(
            SeedVariety.organization_id == organization_id,
            func.lower(SeedVariety.code) == data.code.lower(),
            SeedVariety.deleted_at.is_(None),
        )
        if (await self.session.execute(stmt)).scalar_one_or_none() is not None:
            raise ConflictError("A variety with this code already exists.")
        variety = SeedVariety(
            organization_id=organization_id,
            crop=data.crop,
            name=data.name,
            code=data.code.upper(),
            maturity_days=data.maturity_days,
            yield_potential_kg_ha=data.yield_potential_kg_ha,
            drought_tolerance=data.drought_tolerance,
            disease_tolerance=data.disease_tolerance,
            characteristics=data.characteristics,
            notes=data.notes,
            suitability=[],  # mark collection loaded (async: no lazy IO on serialization)
        )
        self.session.add(variety)
        await self.session.flush()
        self.audit.record("varieties.create", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="seed_varieties", entity_id=variety.id,
                          after={"code": variety.code, "name": variety.name})
        await self.session.commit()
        return variety

    async def update_variety(
        self, variety_id: str, data: VarietyUpdate, organization_id: str, actor_id: str
    ) -> SeedVariety:
        variety = await self.get_variety(variety_id, organization_id)
        for field_name in (
            "crop", "name", "maturity_days", "yield_potential_kg_ha",
            "drought_tolerance", "disease_tolerance", "characteristics", "notes", "is_active",
        ):
            value = getattr(data, field_name)
            if value is not None:
                setattr(variety, field_name, value)
        self.audit.record("varieties.update", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="seed_varieties", entity_id=variety.id)
        await self.session.commit()
        return variety

    async def delete_variety(
        self, variety_id: str, organization_id: str, actor_id: str
    ) -> None:
        variety = await self.get_variety(variety_id, organization_id)
        variety.deleted_at = utcnow()
        variety.is_active = False
        self.audit.record("varieties.delete", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="seed_varieties", entity_id=variety.id,
                          before={"code": variety.code, "name": variety.name})
        await self.session.commit()

    async def set_suitability(
        self,
        variety_id: str,
        entries: list[SuitabilityEntry],
        organization_id: str,
        actor_id: str,
    ) -> SeedVariety:
        """Replace the region-suitability matrix row for one variety."""
        variety = await self.get_variety(variety_id, organization_id)

        region_ids = [e.region_id for e in entries]
        if len(region_ids) != len(set(region_ids)):
            raise DomainError("Duplicate region in suitability entries.")
        if region_ids:
            stmt = select(func.count(Region.id)).where(
                Region.id.in_(region_ids),
                Region.organization_id == organization_id,
                Region.deleted_at.is_(None),
            )
            if (await self.session.execute(stmt)).scalar_one() != len(region_ids):
                raise NotFoundError("One or more regions not found.")

        variety.suitability = [
            VarietySuitability(region_id=e.region_id, score=e.score, rationale=e.rationale)
            for e in entries
        ]
        self.audit.record("varieties.suitability", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="seed_varieties", entity_id=variety.id,
                          after={"regions": len(entries)})
        await self.session.commit()
        return variety
