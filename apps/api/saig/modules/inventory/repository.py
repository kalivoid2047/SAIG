from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.inventory.models import (
    StockLot,
    StockMovement,
    StockTransfer,
    Warehouse,
)


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- warehouses ----------------------------------------------------------

    async def list_warehouses(self, organization_id: str) -> list[Warehouse]:
        stmt = (
            select(Warehouse)
            .where(Warehouse.organization_id == organization_id, Warehouse.deleted_at.is_(None))
            .order_by(Warehouse.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_warehouse(self, warehouse_id: str, organization_id: str) -> Warehouse | None:
        stmt = select(Warehouse).where(
            Warehouse.id == warehouse_id,
            Warehouse.organization_id == organization_id,
            Warehouse.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- lots ----------------------------------------------------------------

    async def list_lots(self, organization_id: str) -> list[StockLot]:
        stmt = (
            select(StockLot)
            .where(StockLot.organization_id == organization_id)
            .order_by(StockLot.expires_at)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_lot(self, lot_id: str, organization_id: str) -> StockLot | None:
        stmt = select(StockLot).where(
            StockLot.id == lot_id, StockLot.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_lot_by_number(self, lot_number: str, organization_id: str) -> StockLot | None:
        stmt = select(StockLot).where(
            StockLot.organization_id == organization_id, StockLot.lot_number == lot_number
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- balances (derived from the ledger) ----------------------------------

    async def balance(self, warehouse_id: str, lot_id: str) -> float:
        stmt = select(func.coalesce(func.sum(StockMovement.quantity_kg), 0)).where(
            StockMovement.warehouse_id == warehouse_id,
            StockMovement.lot_id == lot_id,
        )
        return float((await self.session.execute(stmt)).scalar_one())

    async def balances_for_org(self, organization_id: str) -> list[tuple]:
        """Returns rows of (warehouse_id, lot_id, variety_id, lot_number,
        expires_at, balance_kg) for non-zero balances."""
        stmt = (
            select(
                StockMovement.warehouse_id,
                StockMovement.lot_id,
                StockLot.variety_id,
                StockLot.lot_number,
                StockLot.expires_at,
                func.sum(StockMovement.quantity_kg).label("balance_kg"),
            )
            .join(StockLot, StockLot.id == StockMovement.lot_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(Warehouse.organization_id == organization_id)
            .group_by(
                StockMovement.warehouse_id,
                StockMovement.lot_id,
                StockLot.variety_id,
                StockLot.lot_number,
                StockLot.expires_at,
            )
            .having(func.sum(StockMovement.quantity_kg) != 0)
        )
        return list((await self.session.execute(stmt)).all())

    async def total_stock_kg(self, organization_id: str) -> float:
        stmt = (
            select(func.coalesce(func.sum(StockMovement.quantity_kg), 0))
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(Warehouse.organization_id == organization_id)
        )
        return float((await self.session.execute(stmt)).scalar_one())

    async def list_movements(
        self, warehouse_id: str, lot_id: str | None = None
    ) -> list[StockMovement]:
        conditions = [StockMovement.warehouse_id == warehouse_id]
        if lot_id:
            conditions.append(StockMovement.lot_id == lot_id)
        stmt = (
            select(StockMovement)
            .where(*conditions)
            .order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
            .limit(500)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def expiring_lots(self, organization_id: str, within_days: int) -> list[tuple]:
        cutoff = date.today() + timedelta(days=within_days)
        rows = await self.balances_for_org(organization_id)
        return [r for r in rows if r.expires_at <= cutoff and r.balance_kg > 0]

    # --- transfers -----------------------------------------------------------

    async def get_transfer(self, transfer_id: str, organization_id: str) -> StockTransfer | None:
        stmt = select(StockTransfer).where(
            StockTransfer.id == transfer_id,
            StockTransfer.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_transfers(self, organization_id: str) -> list[StockTransfer]:
        stmt = (
            select(StockTransfer)
            .where(StockTransfer.organization_id == organization_id)
            .order_by(StockTransfer.created_at.desc())
            .limit(200)
        )
        return list((await self.session.execute(stmt)).scalars().all())
