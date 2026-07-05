from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.catalog.models import SeedVariety
from saig.modules.fieldops.models import CropCycle, Farm, FieldPlot, ProductionRecord
from saig.modules.predictions.models import (
    DemandForecastRow,
    ModelVersion,
    SalesHistory,
    YieldPredictionRow,
)


class PredictionsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- model registry ------------------------------------------------------

    async def get_promoted(self, organization_id: str, model_name: str) -> ModelVersion | None:
        stmt = select(ModelVersion).where(
            ModelVersion.organization_id == organization_id,
            ModelVersion.model_name == model_name,
            ModelVersion.status == "promoted",
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_models(
        self, organization_id: str, model_name: str | None = None
    ) -> list[ModelVersion]:
        conditions = [ModelVersion.organization_id == organization_id]
        if model_name:
            conditions.append(ModelVersion.model_name == model_name)
        stmt = select(ModelVersion).where(*conditions).order_by(ModelVersion.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def demote_promoted(self, organization_id: str, model_name: str) -> None:
        current = await self.get_promoted(organization_id, model_name)
        if current is not None:
            current.status = "retired"

    # --- training data -------------------------------------------------------

    async def yield_training_rows(self, organization_id: str) -> list[dict]:
        """Historical yields joined to variety traits → training features."""
        stmt = (
            select(
                ProductionRecord.area_ha,
                ProductionRecord.yield_kg,
                SeedVariety.yield_potential_kg_ha,
                SeedVariety.maturity_days,
                SeedVariety.drought_tolerance,
                SeedVariety.disease_tolerance,
            )
            .join(SeedVariety, SeedVariety.id == ProductionRecord.variety_id)
            .join(Farm, Farm.farmer_id == ProductionRecord.farmer_id)
            .where(Farm.organization_id == organization_id)
            .where(ProductionRecord.variety_id.isnot(None))
            .where(ProductionRecord.area_ha > 0)
        )
        rows = []
        for r in (await self.session.execute(stmt)).all():
            area = float(r.area_ha)
            rows.append(
                {
                    "yield_potential_kg_ha": float(r.yield_potential_kg_ha or 0),
                    "maturity_days": float(r.maturity_days or 0),
                    "drought_tolerance": float(r.drought_tolerance or 3),
                    "disease_tolerance": float(r.disease_tolerance or 3),
                    "area_ha": area,
                    "yield_kg_ha": float(r.yield_kg) / area if area else 0.0,
                }
            )
        return rows

    async def active_cycle_features(
        self, organization_id: str, crop_cycle_ids: list[str] | None = None
    ) -> list[dict]:
        """Feature rows for scoring active crop cycles (aligned with training)."""
        conditions = [
            Farm.organization_id == organization_id,
            CropCycle.deleted_at.is_(None),
            CropCycle.status.in_(("planned", "planted", "growing")),
        ]
        if crop_cycle_ids:
            conditions.append(CropCycle.id.in_(crop_cycle_ids))
        stmt = (
            select(
                CropCycle.id.label("crop_cycle_id"),
                FieldPlot.area_ha,
                SeedVariety.yield_potential_kg_ha,
                SeedVariety.maturity_days,
                SeedVariety.drought_tolerance,
                SeedVariety.disease_tolerance,
            )
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .join(SeedVariety, SeedVariety.id == CropCycle.variety_id)
            .where(*conditions)
        )
        rows = []
        for r in (await self.session.execute(stmt)).all():
            rows.append(
                {
                    "crop_cycle_id": r.crop_cycle_id,
                    "yield_potential_kg_ha": float(r.yield_potential_kg_ha or 0),
                    "maturity_days": float(r.maturity_days or 0),
                    "drought_tolerance": float(r.drought_tolerance or 3),
                    "disease_tolerance": float(r.disease_tolerance or 3),
                    "area_ha": float(r.area_ha or 0),
                }
            )
        return rows

    async def harvested_vs_predicted(self, organization_id: str) -> list[tuple[float, float]]:
        """(predicted_kg_ha, actual_kg_ha) for harvested cycles that carry a
        yield prediction — the ground truth for yield-model accuracy."""
        stmt = (
            select(
                YieldPredictionRow.predicted_yield_kg_ha,
                CropCycle.actual_yield_kg,
                FieldPlot.area_ha,
            )
            .join(CropCycle, CropCycle.id == YieldPredictionRow.crop_cycle_id)
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(
                Farm.organization_id == organization_id,
                CropCycle.status == "harvested",
                CropCycle.actual_yield_kg.isnot(None),
                FieldPlot.area_ha > 0,
            )
        )
        out = []
        for predicted, actual_kg, area in (await self.session.execute(stmt)).all():
            out.append((float(predicted), float(actual_kg) / float(area)))
        return out

    async def sales_history_rows(self, organization_id: str) -> list[dict]:
        stmt = select(
            SalesHistory.region_id,
            SalesHistory.variety_id,
            SalesHistory.period_month,
            SalesHistory.quantity_kg,
        ).where(SalesHistory.organization_id == organization_id)
        return [
            {
                "region_id": r.region_id,
                "variety_id": r.variety_id,
                "period_month": r.period_month,
                "quantity_kg": float(r.quantity_kg),
            }
            for r in (await self.session.execute(stmt)).all()
        ]

    async def sales_segments(self, organization_id: str) -> list[tuple[str, str]]:
        stmt = (
            select(SalesHistory.region_id, SalesHistory.variety_id)
            .where(SalesHistory.organization_id == organization_id)
            .distinct()
        )
        return [(r.region_id, r.variety_id) for r in (await self.session.execute(stmt)).all()]

    # --- prediction reads ----------------------------------------------------

    async def latest_yield_for_cycle(self, crop_cycle_id: str) -> YieldPredictionRow | None:
        stmt = (
            select(YieldPredictionRow)
            .where(YieldPredictionRow.crop_cycle_id == crop_cycle_id)
            .order_by(YieldPredictionRow.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_yield_predictions(self, organization_id: str) -> list[YieldPredictionRow]:
        """Latest prediction per active crop cycle (org-scoped via join)."""
        stmt = (
            select(YieldPredictionRow)
            .join(CropCycle, CropCycle.id == YieldPredictionRow.crop_cycle_id)
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(Farm.organization_id == organization_id)
            .order_by(YieldPredictionRow.crop_cycle_id, YieldPredictionRow.created_at.desc())
        )
        seen: set[str] = set()
        latest: list[YieldPredictionRow] = []
        for row in (await self.session.execute(stmt)).scalars():
            if row.crop_cycle_id not in seen:
                seen.add(row.crop_cycle_id)
                latest.append(row)
        return latest

    async def latest_demand_series(
        self, organization_id: str, region_id: str, variety_id: str
    ) -> list[DemandForecastRow]:
        latest_run = (
            await self.session.execute(
                select(func.max(DemandForecastRow.created_at)).where(
                    DemandForecastRow.organization_id == organization_id,
                    DemandForecastRow.region_id == region_id,
                    DemandForecastRow.variety_id == variety_id,
                )
            )
        ).scalar_one_or_none()
        if latest_run is None:
            return []
        stmt = (
            select(DemandForecastRow)
            .where(
                DemandForecastRow.organization_id == organization_id,
                DemandForecastRow.region_id == region_id,
                DemandForecastRow.variety_id == variety_id,
                DemandForecastRow.created_at == latest_run,
            )
            .order_by(DemandForecastRow.period_month)
        )
        return list((await self.session.execute(stmt)).scalars().all())
