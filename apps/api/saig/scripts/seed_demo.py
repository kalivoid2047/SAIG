"""Demo dataset for local development: regions, varieties, farmers, farms,
fields, crop cycles, plus Phase 2 diseases, disease reports (with an
outbreak cluster), warehouses, lots and stock — around the Kenyan Rift Valley.

Usage:
    python -m saig.scripts.seed_demo

Skips itself entirely if any region already exists (won't pollute real data).
Requires the base seed (org + roles) to have run first.
"""

import asyncio
import math
import random
import sys
from datetime import date

from sqlalchemy import select

from saig.modules.catalog.models import SeedVariety, VarietySuitability
from saig.modules.crophealth.models import Disease, DiseaseReport
from saig.modules.fieldops.models import (
    CropCycle,
    Farm,
    Farmer,
    FieldPlot,
    ProductionRecord,
    Region,
)
from saig.modules.iam.models import Organization, User
from saig.modules.inventory.models import StockLot, StockMovement, Warehouse
from saig.modules.predictions.models import SalesHistory
from saig.modules.risk.service import RiskService
from saig.modules.supplychain.models import (
    Delivery,
    Order,
    OrderItem,
    RoutePlan,
    RouteStop,
    Vehicle,
)
from saig.modules.weather.provider import OpenMeteoProvider
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


def _add_months_seed(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


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

        admin = (
            await session.execute(
                select(User).where(User.organization_id == org.id, User.deleted_at.is_(None))
            )
        ).scalars().first()

        season = "2026-long-rains"
        farmer_count = 0
        cycles: list[tuple[CropCycle, float, float]] = []
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
                    cycle = CropCycle(
                        field_id=field.id,
                        variety_id=rng.choice(varieties).id,
                        season=season,
                        status=rng.choice(["planted", "growing"]),
                    )
                    session.add(cycle)
                    await session.flush()
                    cycles.append((cycle, round(lat, 6), round(lng, 6)))

                # Historical production records (yield-model training data):
                # realised yield ≈ variety potential x a noisy achievement ratio.
                for past in ("2024-long-rains", "2025-long-rains"):
                    v = rng.choice(varieties)
                    area = round(rng.uniform(0.5, 4.0), 2)
                    ratio = rng.uniform(0.55, 0.85) + 0.02 * (v.drought_tolerance or 3)
                    yield_kg_ha = float(v.yield_potential_kg_ha or 5000) * min(ratio, 0.95)
                    session.add(ProductionRecord(
                        farmer_id=farmer.id, season=past, variety_id=v.id,
                        area_ha=area, yield_kg=round(yield_kg_ha * area, 1),
                        source="migrated",
                    ))

        # --- Phase 2: crop health -------------------------------------------
        blight = Disease(organization_id=org.id, name="Maize Leaf Blight",
                         crop="maize", pathogen_type="fungal",
                         treatment_guide="Apply fungicide; remove infected residue.")
        rust = Disease(organization_id=org.id, name="Wheat Stem Rust",
                       crop="wheat", pathogen_type="fungal")
        session.add_all([blight, rust])
        await session.flush()

        report_count = 0
        if admin is not None and cycles:
            # Scattered individual reports
            for cycle, lat, lng in rng.sample(cycles, min(5, len(cycles))):
                session.add(DiseaseReport(
                    organization_id=org.id, crop_cycle_id=cycle.id, disease_id=blight.id,
                    reported_by=admin.id, severity=rng.randint(2, 3),
                    affected_pct=rng.uniform(5, 25), latitude=lat, longitude=lng,
                ))
                report_count += 1
            # A tight cluster (>=3 within 10km) flagged as an outbreak
            east_lat, east_lng = CENTROIDS["EAST"]
            for i in range(3):
                cycle = cycles[i % len(cycles)][0]
                session.add(DiseaseReport(
                    organization_id=org.id, crop_cycle_id=cycle.id, disease_id=blight.id,
                    reported_by=admin.id, severity=4, affected_pct=35,
                    latitude=round(east_lat + i * 0.01, 6),
                    longitude=round(east_lng + i * 0.01, 6),
                    is_outbreak=True,
                ))
                report_count += 1

        # --- Phase 2: inventory ---------------------------------------------
        warehouses = []
        for name, code, rcode in [("Nakuru Central", "WH-NAK", "RIFT"),
                                  ("Machakos Depot", "WH-MAC", "EAST")]:
            region = next(r for r in regions if r.code == rcode)
            wlat, wlng = CENTROIDS[rcode]
            wh = Warehouse(organization_id=org.id, region_id=region.id, name=name,
                           code=code, latitude=wlat, longitude=wlng,
                           capacity_kg=600_000, manager_id=admin.id if admin else None)
            session.add(wh)
            warehouses.append(wh)
        await session.flush()

        lots = []
        for i, variety in enumerate(varieties):
            lot = StockLot(
                organization_id=org.id, variety_id=variety.id,
                lot_number=f"L-2026-{i + 1:03d}",
                produced_at=date(2026, 1, 15), expires_at=date(2027, 6, 30),
                germination_pct=round(rng.uniform(88, 96), 1),
            )
            session.add(lot)
            lots.append(lot)
        await session.flush()

        if admin is not None:
            for wh in warehouses:
                for lot in lots:
                    session.add(StockMovement(
                        warehouse_id=wh.id, lot_id=lot.id, movement_type="receipt",
                        quantity_kg=round(rng.uniform(20_000, 120_000), 1),
                        performed_by=admin.id, reference="opening balance",
                    ))

        # --- Phase 3: sales history (demand-model training data) ------------
        # 24 months per regionxvariety with a seasonal shape + gentle trend.
        base_month = date(2024, 7, 1)
        sales_rows = 0
        for region in regions:
            for variety in varieties:
                base = rng.uniform(800, 2500)
                trend = rng.uniform(-5, 25)
                for m in range(24):
                    month = _add_months_seed(base_month, m)
                    seasonal = 1.0 + 0.35 * math.sin((month.month / 12) * 2 * math.pi)
                    qty = max(base * seasonal + trend * m + rng.uniform(-120, 120), 0.0)
                    session.add(SalesHistory(
                        organization_id=org.id, region_id=region.id, variety_id=variety.id,
                        period_month=month, quantity_kg=round(qty, 1),
                        revenue=round(qty * rng.uniform(2.5, 4.0), 2),
                    ))
                    sales_rows += 1

        # --- Phase 2: supply chain ------------------------------------------
        vehicles = [
            Vehicle(organization_id=org.id, registration=reg, capacity_kg=cap,
                    driver_id=admin.id if admin else None)
            for reg, cap in [("KAA-101A", 10_000), ("KBB-202B", 15_000)]
        ]
        session.add_all(vehicles)
        await session.flush()

        origin = warehouses[0]
        order_count = 0
        route = None
        if admin is not None:
            orders = []
            east_lat, east_lng = CENTROIDS["EAST"]
            for i in range(3):
                dealer = rng.choice(["Umoja", "Green Valley", "Rift"])
                order = Order(
                    organization_id=org.id,
                    customer_name=f"{dealer} Agrodealer {i + 1}",
                    destination_lat=round(east_lat + rng.uniform(-0.3, 0.3), 6),
                    destination_lng=round(east_lng + rng.uniform(-0.3, 0.3), 6),
                    status="confirmed",
                    created_by=admin.id,
                    items=[OrderItem(variety_id=rng.choice(varieties).id,
                                     quantity_kg=round(rng.uniform(200, 1500), 1))],
                )
                session.add(order)
                orders.append(order)
                order_count += 1
            await session.flush()

            # One dispatched route with sequenced stops (nearest-neighbour + deliveries)
            route = RoutePlan(
                organization_id=org.id, origin_warehouse_id=origin.id,
                vehicle_id=vehicles[0].id, driver_id=admin.id, status="dispatched",
                planned_date=date(2026, 8, 1), total_distance_km=142.5,
                optimizer_meta={"method": "nearest_neighbour", "stops": len(orders)},
            )
            for seq, order in enumerate(orders, start=1):
                route.stops.append(RouteStop(order_id=order.id, stop_sequence=seq))
            session.add(route)
            await session.flush()
            vehicles[0].status = "on_route"
            for order in orders:
                session.add(Delivery(order_id=order.id, route_plan_id=route.id,
                                     status="in_transit"))

        await session.commit()

        # --- Phase 3: initial risk board ------------------------------------
        # Climate uses the weather provider (degrades gracefully if offline).
        risk_written = await RiskService(session, OpenMeteoProvider()).recompute(org.id, None)

        print(f"Demo data: {len(regions)} regions, {len(varieties)} varieties, "
              f"{farmer_count} farmers, {len(cycles)} crop cycles, "
              f"{report_count} disease reports, {len(warehouses)} warehouses, "
              f"{len(lots)} lots with stock, {len(vehicles)} vehicles, "
              f"{order_count} orders, 1 dispatched route, "
              f"{sales_rows} sales-history rows, {risk_written} risk assessments "
              f"(train with train_models).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
