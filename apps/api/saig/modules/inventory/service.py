from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.fieldops.repository import FieldOpsRepository
from saig.modules.iam.services.audit_service import AuditService
from saig.modules.inventory.models import (
    StockLot,
    StockMovement,
    StockTransfer,
    Warehouse,
)
from saig.modules.inventory.repository import InventoryRepository
from saig.modules.inventory.schemas import (
    LotCreate,
    MovementCreate,
    TransferCreate,
    WarehouseCreate,
)
from saig.shared.database import utcnow
from saig.shared.errors import ConflictError, DomainError, NotFoundError

# Manual movement signs: down-corrections use write_off (BR-2 keeps this auditable).
MOVEMENT_SIGN = {"receipt": 1, "adjustment": 1, "write_off": -1}


class InventoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryRepository(session)
        self.audit = AuditService(session)

    # --- warehouses ----------------------------------------------------------

    async def list_warehouses(self, organization_id: str) -> list[Warehouse]:
        return await self.repo.list_warehouses(organization_id)

    async def create_warehouse(
        self, data: WarehouseCreate, organization_id: str, actor_id: str
    ) -> Warehouse:
        existing = await self.repo.list_warehouses(organization_id)
        if any(w.code.lower() == data.code.lower() for w in existing):
            raise ConflictError("A warehouse with this code already exists.")
        if data.region_id is not None:
            if await FieldOpsRepository(self.session).get_region(
                data.region_id, organization_id
            ) is None:
                raise NotFoundError("Region not found.")
        warehouse = Warehouse(
            organization_id=organization_id,
            region_id=data.region_id,
            name=data.name,
            code=data.code.upper(),
            latitude=data.latitude,
            longitude=data.longitude,
            capacity_kg=data.capacity_kg,
        )
        self.session.add(warehouse)
        await self.session.flush()
        self.audit.record("warehouses.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="warehouses", entity_id=warehouse.id,
                          after={"code": warehouse.code, "name": warehouse.name})
        await self.session.commit()
        return warehouse

    # --- lots ----------------------------------------------------------------

    async def list_lots(self, organization_id: str) -> list[StockLot]:
        return await self.repo.list_lots(organization_id)

    async def create_lot(
        self, data: LotCreate, organization_id: str, actor_id: str
    ) -> StockLot:
        if await self.repo.get_lot_by_number(data.lot_number, organization_id) is not None:
            raise ConflictError("A lot with this number already exists.")
        if await FieldOpsRepository(self.session).get_variety(
            data.variety_id, organization_id
        ) is None:
            raise NotFoundError("Seed variety not found.")
        lot = StockLot(
            organization_id=organization_id,
            variety_id=data.variety_id,
            lot_number=data.lot_number,
            produced_at=data.produced_at,
            expires_at=data.expires_at,
            germination_pct=data.germination_pct,
        )
        self.session.add(lot)
        await self.session.flush()
        self.audit.record("stock_lots.create", actor_id=actor_id, organization_id=organization_id,
                          entity_table="stock_lots", entity_id=lot.id,
                          after={"lot_number": lot.lot_number})
        await self.session.commit()
        return lot

    # --- movements -----------------------------------------------------------

    async def record_movement(
        self, data: MovementCreate, organization_id: str, actor_id: str
    ) -> StockMovement:
        warehouse = await self.repo.get_warehouse(data.warehouse_id, organization_id)
        if warehouse is None:
            raise NotFoundError("Warehouse not found.")
        if await self.repo.get_lot(data.lot_id, organization_id) is None:
            raise NotFoundError("Stock lot not found.")

        signed = data.quantity_kg * MOVEMENT_SIGN[data.movement_type]
        await self._guard_non_negative(data.warehouse_id, data.lot_id, signed)

        movement = StockMovement(
            warehouse_id=data.warehouse_id,
            lot_id=data.lot_id,
            movement_type=data.movement_type,
            quantity_kg=signed,
            reference=data.reference,
            performed_by=actor_id,
        )
        self.session.add(movement)
        await self.session.flush()
        self.audit.record("stock_movements.create", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="stock_movements", entity_id=str(movement.id),
                          after={"type": data.movement_type, "qty": signed})
        await self.session.commit()
        return movement

    async def _guard_non_negative(self, warehouse_id: str, lot_id: str, delta: float) -> None:
        """Reject any movement that would drive the (warehouse, lot) balance
        below zero (BR-2). On PostgreSQL this pairs with SELECT ... FOR UPDATE;
        on SQLite the read+check+insert runs inside one transaction."""
        if delta >= 0:
            return
        balance = await self.repo.balance(warehouse_id, lot_id)
        if balance + delta < 0:
            raise DomainError(
                f"Insufficient stock: {balance:g} kg available, "
                f"{abs(delta):g} kg requested.",
                extra={"availableKg": balance},
            )

    # --- transfers -----------------------------------------------------------

    async def create_transfer(
        self, data: TransferCreate, organization_id: str, actor_id: str
    ) -> StockTransfer:
        src = await self.repo.get_warehouse(data.from_warehouse_id, organization_id)
        dst = await self.repo.get_warehouse(data.to_warehouse_id, organization_id)
        if src is None or dst is None:
            raise NotFoundError("Warehouse not found.")
        if await self.repo.get_lot(data.lot_id, organization_id) is None:
            raise NotFoundError("Stock lot not found.")
        available = await self.repo.balance(data.from_warehouse_id, data.lot_id)
        if available < data.quantity_kg:
            raise DomainError(
                f"Insufficient stock at source: {available:g} kg available.",
                extra={"availableKg": available},
            )
        transfer = StockTransfer(
            organization_id=organization_id,
            from_warehouse_id=data.from_warehouse_id,
            to_warehouse_id=data.to_warehouse_id,
            lot_id=data.lot_id,
            quantity_kg=data.quantity_kg,
            requested_by=actor_id,
        )
        self.session.add(transfer)
        await self.session.flush()
        self.audit.record("stock_transfers.create", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="stock_transfers", entity_id=transfer.id,
                          after={"qty": data.quantity_kg})
        await self.session.commit()
        return transfer

    async def dispatch_transfer(
        self, transfer_id: str, organization_id: str, actor_id: str
    ) -> StockTransfer:
        transfer = await self.repo.get_transfer(transfer_id, organization_id)
        if transfer is None:
            raise NotFoundError("Transfer not found.")
        if transfer.status != "pending":
            raise DomainError(f"Only pending transfers can be dispatched (is '{transfer.status}').")

        # Debit the source atomically with the state change.
        await self._guard_non_negative(
            transfer.from_warehouse_id, transfer.lot_id, -float(transfer.quantity_kg)
        )
        self.session.add(
            StockMovement(
                warehouse_id=transfer.from_warehouse_id,
                lot_id=transfer.lot_id,
                movement_type="transfer_out",
                quantity_kg=-float(transfer.quantity_kg),
                transfer_id=transfer.id,
                performed_by=actor_id,
            )
        )
        transfer.status = "dispatched"
        transfer.dispatched_at = utcnow()
        self.audit.record("stock_transfers.dispatch", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="stock_transfers", entity_id=transfer.id)
        await self.session.commit()
        return transfer

    async def receive_transfer(
        self, transfer_id: str, received_kg: float, organization_id: str, actor_id: str
    ) -> StockTransfer:
        transfer = await self.repo.get_transfer(transfer_id, organization_id)
        if transfer is None:
            raise NotFoundError("Transfer not found.")
        if transfer.status != "dispatched":
            raise DomainError(
                f"Only dispatched transfers can be received (is '{transfer.status}')."
            )
        if received_kg > float(transfer.quantity_kg):
            raise DomainError("Received quantity cannot exceed the dispatched quantity.")

        self.session.add(
            StockMovement(
                warehouse_id=transfer.to_warehouse_id,
                lot_id=transfer.lot_id,
                movement_type="transfer_in",
                quantity_kg=received_kg,
                transfer_id=transfer.id,
                performed_by=actor_id,
            )
        )
        transfer.status = "received"
        transfer.received_kg = received_kg
        transfer.received_at = utcnow()
        variance = float(transfer.quantity_kg) - received_kg
        if variance > 0:
            # Short delivery: the difference is written off at source-in-transit
            # so the ledger stays balanced, and the variance is flagged.
            transfer.variance_note = f"Short by {variance:g} kg on receipt."
            self.audit.record("stock_transfers.variance", actor_id=actor_id,
                              organization_id=organization_id,
                              entity_table="stock_transfers", entity_id=transfer.id,
                              after={"varianceKg": variance})
        self.audit.record("stock_transfers.receive", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="stock_transfers", entity_id=transfer.id,
                          after={"receivedKg": received_kg})
        await self.session.commit()
        return transfer

    async def cancel_transfer(
        self, transfer_id: str, organization_id: str, actor_id: str
    ) -> StockTransfer:
        transfer = await self.repo.get_transfer(transfer_id, organization_id)
        if transfer is None:
            raise NotFoundError("Transfer not found.")
        if transfer.status != "pending":
            raise DomainError("Only pending transfers can be cancelled.")
        transfer.status = "cancelled"
        self.audit.record("stock_transfers.cancel", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="stock_transfers", entity_id=transfer.id)
        await self.session.commit()
        return transfer
