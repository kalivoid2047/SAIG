from datetime import date, timedelta

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.crophealth.models import DiseaseReport
from saig.modules.fieldops.models import CropCycle, Farm, FieldPlot
from saig.modules.inventory.models import StockLot, StockMovement, Warehouse
from saig.modules.predictions.models import DemandForecastRow, YieldPredictionRow
from saig.modules.risk.models import RiskAssessment
from saig.modules.supplychain.models import Delivery, Order, Vehicle

ACTIVE_DISEASE = ("reported", "confirmed", "treated")
ACTIVE_CYCLE = ("planned", "planted", "growing")


class RiskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- disease signals -----------------------------------------------------

    async def disease_signals(
        self, organization_id: str, region_id: str | None = None
    ) -> tuple[int, int, float]:
        conditions = [
            DiseaseReport.organization_id == organization_id,
            DiseaseReport.deleted_at.is_(None),
            DiseaseReport.status.in_(ACTIVE_DISEASE),
        ]
        stmt = select(
            func.count(DiseaseReport.id),
            func.coalesce(func.sum(cast(DiseaseReport.is_outbreak, Integer)), 0),
            func.coalesce(func.avg(DiseaseReport.severity), 0),
        )
        if region_id is not None:
            stmt = (
                stmt.select_from(DiseaseReport)
                .join(CropCycle, CropCycle.id == DiseaseReport.crop_cycle_id)
                .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
                .join(Farm, Farm.id == FieldPlot.farm_id)
            )
            conditions.append(Farm.region_id == region_id)
        stmt = stmt.where(*conditions)
        count, outbreaks, avg_sev = (await self.session.execute(stmt)).one()
        return int(count), int(outbreaks), float(avg_sev)

    # --- supply-chain signals ------------------------------------------------

    async def supply_signals(self, organization_id: str) -> tuple[int, int, int, int]:
        failed = await self._count(
            select(func.count(Delivery.id))
            .join(Order, Order.id == Delivery.order_id)
            .where(Order.organization_id == organization_id, Delivery.status == "failed")
        )
        in_transit = await self._count(
            select(func.count(Delivery.id))
            .join(Order, Order.id == Delivery.order_id)
            .where(Order.organization_id == organization_id, Delivery.status == "in_transit")
        )
        available = await self._count(
            select(func.count(Vehicle.id)).where(
                Vehicle.organization_id == organization_id,
                Vehicle.deleted_at.is_(None),
                Vehicle.status == "available",
            )
        )
        total = await self._count(
            select(func.count(Vehicle.id)).where(
                Vehicle.organization_id == organization_id,
                Vehicle.deleted_at.is_(None),
                Vehicle.status != "retired",
            )
        )
        return failed, in_transit, available, total

    # --- inventory signals ---------------------------------------------------

    async def inventory_signals(self, organization_id: str) -> tuple[float | None, int, int]:
        # Stock on hand per variety.
        stock_stmt = (
            select(StockLot.variety_id, func.sum(StockMovement.quantity_kg))
            .join(StockLot, StockLot.id == StockMovement.lot_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(Warehouse.organization_id == organization_id)
            .group_by(StockLot.variety_id)
        )
        stock = {v: float(q or 0) for v, q in (await self.session.execute(stock_stmt)).all()}

        # Latest demand forecast total (next 3 months) per variety.
        horizon_end = date.today().replace(day=1) + timedelta(days=93)
        latest = (
            select(
                DemandForecastRow.variety_id,
                func.max(DemandForecastRow.created_at).label("latest"),
            )
            .where(DemandForecastRow.organization_id == organization_id)
            .group_by(DemandForecastRow.variety_id)
            .subquery()
        )
        demand_stmt = (
            select(DemandForecastRow.variety_id, func.sum(DemandForecastRow.forecast_qty_kg))
            .join(
                latest,
                (latest.c.variety_id == DemandForecastRow.variety_id)
                & (latest.c.latest == DemandForecastRow.created_at),
            )
            .where(DemandForecastRow.period_month <= horizon_end)
            .group_by(DemandForecastRow.variety_id)
        )
        demand = {v: float(q or 0) for v, q in (await self.session.execute(demand_stmt)).all()}

        ratios = [
            stock.get(v, 0.0) / d
            for v, d in demand.items()
            if d > 0
        ]
        min_coverage = min(ratios) if ratios else None

        # Near-expiry lots with positive balance.
        cutoff = date.today() + timedelta(days=90)
        near = await self._count(
            select(func.count(func.distinct(StockLot.id)))
            .join(StockMovement, StockMovement.lot_id == StockLot.id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(Warehouse.organization_id == organization_id, StockLot.expires_at <= cutoff)
        )
        return min_coverage, near, len(ratios)

    # --- production signals ---------------------------------------------------

    async def production_signals(
        self, organization_id: str, region_id: str | None = None
    ) -> tuple[float, int, int]:
        cycle_conditions = [Farm.organization_id == organization_id, CropCycle.deleted_at.is_(None)]
        if region_id is not None:
            cycle_conditions.append(Farm.region_id == region_id)

        total = await self._count(
            select(func.count(CropCycle.id))
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(*cycle_conditions, CropCycle.status.in_((*ACTIVE_CYCLE, "harvested")))
        )
        failed = await self._count(
            select(func.count(CropCycle.id))
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(*cycle_conditions, CropCycle.status == "failed")
        )

        # Low-confidence ratio over latest yield predictions in scope.
        pred_stmt = (
            select(YieldPredictionRow.low_confidence)
            .join(CropCycle, CropCycle.id == YieldPredictionRow.crop_cycle_id)
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(Farm.organization_id == organization_id)
        )
        if region_id is not None:
            pred_stmt = pred_stmt.where(Farm.region_id == region_id)
        flags = [bool(x) for (x,) in (await self.session.execute(pred_stmt)).all()]
        low_ratio = (sum(flags) / len(flags)) if flags else 0.0
        return low_ratio, failed, total + failed

    async def demand_confidence(self, organization_id: str) -> float:
        stmt = select(func.avg(DemandForecastRow.confidence)).where(
            DemandForecastRow.organization_id == organization_id
        )
        val = (await self.session.execute(stmt)).scalar_one_or_none()
        return float(val) if val is not None else 0.5

    async def region_centroids(self, organization_id: str) -> list[tuple[str, float, float]]:
        stmt = (
            select(
                Farm.region_id,
                func.avg(Farm.latitude),
                func.avg(Farm.longitude),
            )
            .where(
                Farm.organization_id == organization_id,
                Farm.deleted_at.is_(None),
                Farm.region_id.isnot(None),
            )
            .group_by(Farm.region_id)
        )
        return [
            (r, float(lat), float(lng))
            for r, lat, lng in (await self.session.execute(stmt)).all()
        ]

    # --- assessment persistence ----------------------------------------------

    async def upsert_assessment(
        self, organization_id: str, region_id: str | None, domain: str,
        score: int, factors: list[dict], assessed_date: date,
    ) -> None:
        stmt = select(RiskAssessment).where(
            RiskAssessment.organization_id == organization_id,
            RiskAssessment.region_id.is_(None) if region_id is None
            else RiskAssessment.region_id == region_id,
            RiskAssessment.domain == domain,
            RiskAssessment.assessed_date == assessed_date,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.score = score
            existing.factors = factors
        else:
            self.session.add(
                RiskAssessment(
                    organization_id=organization_id, region_id=region_id, domain=domain,
                    score=score, factors=factors, assessed_date=assessed_date,
                )
            )

    async def board(
        self, organization_id: str, region_id: str | None
    ) -> list[RiskAssessment]:
        """Latest assessment per domain for the given scope."""
        latest_date = await self._latest_date(organization_id, region_id)
        if latest_date is None:
            return []
        stmt = self._scope_filter(
            select(RiskAssessment), organization_id, region_id
        ).where(RiskAssessment.assessed_date == latest_date)
        return list((await self.session.execute(stmt)).scalars().all())

    async def previous_scores(
        self, organization_id: str, region_id: str | None, before: date
    ) -> dict[str, int]:
        stmt = self._scope_filter(
            select(RiskAssessment), organization_id, region_id
        ).where(RiskAssessment.assessed_date < before).order_by(
            RiskAssessment.assessed_date.desc()
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        out: dict[str, int] = {}
        for r in rows:
            out.setdefault(r.domain, r.score)
        return out

    async def history(
        self, organization_id: str, region_id: str | None, domain: str,
        since: date,
    ) -> list[RiskAssessment]:
        stmt = (
            self._scope_filter(select(RiskAssessment), organization_id, region_id)
            .where(RiskAssessment.domain == domain, RiskAssessment.assessed_date >= since)
            .order_by(RiskAssessment.assessed_date)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def high_risk_count(self, organization_id: str) -> int:
        latest_date = await self._latest_date(organization_id, None)
        if latest_date is None:
            return 0
        return await self._count(
            self._scope_filter(select(func.count(RiskAssessment.id)), organization_id, None)
            .where(RiskAssessment.assessed_date == latest_date, RiskAssessment.score >= 70)
        )

    # --- helpers -------------------------------------------------------------

    @staticmethod
    def _scope_filter(stmt, organization_id: str, region_id: str | None):
        stmt = stmt.where(RiskAssessment.organization_id == organization_id)
        if region_id is None:
            return stmt.where(RiskAssessment.region_id.is_(None))
        return stmt.where(RiskAssessment.region_id == region_id)

    async def _latest_date(self, organization_id: str, region_id: str | None) -> date | None:
        stmt = self._scope_filter(
            select(func.max(RiskAssessment.assessed_date)), organization_id, region_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _count(self, stmt) -> int:
        return int((await self.session.execute(stmt)).scalar_one())
