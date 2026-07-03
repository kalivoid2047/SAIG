from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.catalog.models import SeedVariety
from saig.modules.crophealth.models import DiseaseReport
from saig.modules.dashboard.schemas import DashboardKpis
from saig.modules.fieldops.models import CropCycle, Farm, Farmer, FieldPlot
from saig.modules.inventory.models import StockTransfer, Warehouse
from saig.modules.inventory.repository import InventoryRepository

EXPIRY_SOON_DAYS = 90


class DashboardService:
    """Read-only cross-context aggregation for the executive dashboard.

    Reads other contexts' tables directly for KPIs only; all writes stay
    within their owning modules (dashboard is a pure read model — the
    materialized-view approach in schema.sql is the scale-up path).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _count(self, stmt) -> int:
        return int((await self.session.execute(stmt)).scalar_one())

    async def kpis(self, organization_id: str) -> DashboardKpis:
        active_farmers = await self._count(
            select(func.count(Farmer.id)).where(
                Farmer.organization_id == organization_id, Farmer.deleted_at.is_(None)
            )
        )
        active_cycles = await self._count(
            select(func.count(CropCycle.id))
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(
                Farm.organization_id == organization_id,
                CropCycle.deleted_at.is_(None),
                CropCycle.status.in_(("planned", "planted", "growing")),
            )
        )
        harvested = await self._count(
            select(func.count(CropCycle.id))
            .join(FieldPlot, FieldPlot.id == CropCycle.field_id)
            .join(Farm, Farm.id == FieldPlot.farm_id)
            .where(
                Farm.organization_id == organization_id,
                CropCycle.status == "harvested",
            )
        )
        varieties = await self._count(
            select(func.count(SeedVariety.id)).where(
                SeedVariety.organization_id == organization_id,
                SeedVariety.deleted_at.is_(None),
                SeedVariety.is_active.is_(True),
            )
        )
        warehouses = await self._count(
            select(func.count(Warehouse.id)).where(
                Warehouse.organization_id == organization_id, Warehouse.deleted_at.is_(None)
            )
        )
        pending_transfers = await self._count(
            select(func.count(StockTransfer.id)).where(
                StockTransfer.organization_id == organization_id,
                StockTransfer.status == "pending",
            )
        )
        open_reports = await self._count(
            select(func.count(DiseaseReport.id)).where(
                DiseaseReport.organization_id == organization_id,
                DiseaseReport.deleted_at.is_(None),
                DiseaseReport.status.in_(("reported", "confirmed", "treated")),
            )
        )
        active_outbreaks = await self._count(
            select(func.count(DiseaseReport.id)).where(
                DiseaseReport.organization_id == organization_id,
                DiseaseReport.deleted_at.is_(None),
                DiseaseReport.is_outbreak.is_(True),
                DiseaseReport.status.in_(("reported", "confirmed", "treated")),
            )
        )

        inv = InventoryRepository(self.session)
        total_stock = await inv.total_stock_kg(organization_id)
        expiring = await inv.expiring_lots(organization_id, EXPIRY_SOON_DAYS)

        return DashboardKpis(
            activeFarmers=active_farmers,
            activeCropCycles=active_cycles,
            harvestedCycles=harvested,
            seedVarieties=varieties,
            warehouses=warehouses,
            totalStockKg=round(total_stock, 2),
            lotsExpiringSoon=len(expiring),
            openDiseaseReports=open_reports,
            activeOutbreaks=active_outbreaks,
            pendingTransfers=pending_transfers,
        )
