"""Demo dataset for local development: regions, varieties, farmers, farms,
fields and crop cycles around the Kenyan Rift Valley.

Usage:
    python -m saig.scripts.seed_demo

Skips itself entirely if any region already exists (won't pollute real data).
Requires the base seed (org + roles) to have run first.
"""

import asyncio
import random
import sys

from sqlalchemy import select

from saig.modules.catalog.models import SeedVariety, VarietySuitability
from saig.modules.fieldops.models import CropCycle, Farm, Farmer, FieldPlot, Region
from saig.modules.iam.models import Organization
from saig.shared.config import get_settings
from saig.shared.database import create_engine_and_sessionmaker, utcnow

REGIONS = [("Eastern", "EAST"), ("Rift Valley", "RIFT"), ("Western", "WEST")]

VARIETIES = [
    dict(crop="maize", name="Pioneer 401", code="MZ-401", maturity_days=120,
         yield_potential_kg_ha=6500, drought_tolerance=2, disease_tolerance=4),
    dict(crop="maize", name="DroughtGuard 514", code="MZ-514", maturity_days=105,
         yield_potential_kg_ha=5200, drought_tolerance=5, disease_tolerance=3),
    dict(crop="wheat", name="Highland 201", code="WH-201", maturity_days=140,
         yield_potential_kg_ha=4200, drought_tolerance=3, disease_tolerance=3),
]

FIRST = ["Amina", "David", "Esther", "John", "Grace", "Peter", "Ruth", "Samuel",
         "Mary", "Daniel", "Faith", "Joseph"]
LAST = ["Mwangi", "Ochieng", "Kamau", "Wanjiku", "Otieno", "Njoroge", "Chebet", "Kiprop"]

# Rough centroids per region code (lat, lng)
CENTROIDS = {"EAST": (-1.45, 37.95), "RIFT": (-0.30, 35.95), "WEST": (0.30, 34.60)}


async def main() -> None:
    rng = random.Random(42)  # noqa: S311 - deterministic demo data, not crypto
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    async with session_factory() as session:
        org = (
            await session.execute(
                select(Organization).where(Organization.deleted_at.is_(None))
            )
        ).scalars().first()
        if org is None:
            print("Run `python -m saig.scripts.seed` first.", file=sys.stderr)
            raise SystemExit(1)

        existing = (await session.execute(select(Region))).scalars().first()
        if existing is not None:
            print("Regions already exist — demo seed skipped.")
            return

        regions = [
            Region(organization_id=org.id, name=name, code=code) for name, code in REGIONS
        ]
        session.add_all(regions)
        await session.flush()

        varieties = [
            SeedVariety(
                organization_id=org.id,
                suitability=[
                    VarietySuitability(region_id=r.id, score=rng.randint(2, 5))
                    for r in regions
                ],
                **v,
            )
            for v in VARIETIES
        ]
        session.add_all(varieties)
        await session.flush()

        season = "2026-long-rains"
        farmer_count = 0
        for region in regions:
            base_lat, base_lng = CENTROIDS[region.code]
            for _ in range(6):
                farmer_count += 1
                farmer = Farmer(
                    organization_id=org.id,
                    region_id=region.id,
                    full_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                    phone=f"+2547{rng.randint(10000000, 99999999)}",
                    gender=rng.choice(["male", "female"]),
                    birth_year=rng.randint(1960, 2000),
                    cooperative=rng.choice(["Umoja Co-op", "Harvest SACCO", None]),
                    consent_given_at=utcnow(),
                )
                session.add(farmer)
                await session.flush()

                lat = base_lat + rng.uniform(-0.4, 0.4)
                lng = base_lng + rng.uniform(-0.4, 0.4)
                farm = Farm(
                    organization_id=org.id,
                    farmer_id=farmer.id,
                    region_id=region.id,
                    name=f"{farmer.full_name.split()[1]} Farm",
                    latitude=round(lat, 6),
                    longitude=round(lng, 6),
                    total_area_ha=round(rng.uniform(0.5, 12.0), 2),
                )
                session.add(farm)
                await session.flush()

                field = FieldPlot(
                    farm_id=farm.id,
                    name="Main plot",
                    area_ha=round(rng.uniform(0.3, 4.0), 2),
                )
                session.add(field)
                await session.flush()

                if rng.random() < 0.8:
                    session.add(
                        CropCycle(
                            field_id=field.id,
                            variety_id=rng.choice(varieties).id,
                            season=season,
                            status=rng.choice(["planted", "growing"]),
                        )
                    )

        await session.commit()
        print(f"Demo data: {len(regions)} regions, {len(varieties)} varieties, "
              f"{farmer_count} farmers with farms/fields/cycles.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
