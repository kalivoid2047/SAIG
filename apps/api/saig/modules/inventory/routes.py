from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.inventory.repository import InventoryRepository
from saig.modules.inventory.schemas import (
    LotCreate,
    LotOut,
    MovementCreate,
    MovementOut,
    StockBalanceOut,
    TransferCreate,
    TransferOut,
    TransferReceive,
    WarehouseCreate,
    WarehouseOut,
)
from saig.modules.inventory.service import InventoryService

router = APIRouter(tags=["inventory"])

NEAR_EXPIRY_DAYS = 90


@router.get("/warehouses", response_model=list[WarehouseOut])
async def list_warehouses(
    current: CurrentUser = Depends(require_permission("inventory:read")),
    session: AsyncSession = Depends(get_db),
) -> list[WarehouseOut]:
    warehouses = await InventoryService(session).list_warehouses(current.organization_id)
    return [WarehouseOut.model_validate(w) for w in warehouses]


@router.post("/warehouses", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate,
    current: CurrentUser = Depends(require_permission("inventory:manage")),
    session: AsyncSession = Depends(get_db),
) -> WarehouseOut:
    warehouse = await InventoryService(session).create_warehouse(
        body, current.organization_id, current.id
    )
    return WarehouseOut.model_validate(warehouse)


@router.get("/stock/lots", response_model=list[LotOut])
async def list_lots(
    current: CurrentUser = Depends(require_permission("inventory:read")),
    session: AsyncSession = Depends(get_db),
) -> list[LotOut]:
    lots = await InventoryService(session).list_lots(current.organization_id)
    return [LotOut.model_validate(lot) for lot in lots]


@router.post("/stock/lots", response_model=LotOut, status_code=status.HTTP_201_CREATED)
async def create_lot(
    body: LotCreate,
    current: CurrentUser = Depends(require_permission("inventory:manage")),
    session: AsyncSession = Depends(get_db),
) -> LotOut:
    lot = await InventoryService(session).create_lot(body, current.organization_id, current.id)
    return LotOut.model_validate(lot)


@router.get("/stock/balances", response_model=list[StockBalanceOut])
async def stock_balances(
    expiring_within_days: int | None = Query(None, alias="expiringWithinDays", ge=1, le=3650),
    current: CurrentUser = Depends(require_permission("inventory:read")),
    session: AsyncSession = Depends(get_db),
) -> list[StockBalanceOut]:
    rows = await InventoryRepository(session).balances_for_org(current.organization_id)
    soon_cutoff = date.today() + timedelta(days=NEAR_EXPIRY_DAYS)
    out: list[StockBalanceOut] = []
    for r in rows:
        if expiring_within_days is not None:
            if r.expires_at > date.today() + timedelta(days=expiring_within_days):
                continue
        out.append(
            StockBalanceOut(
                warehouseId=r.warehouse_id,
                lotId=r.lot_id,
                varietyId=r.variety_id,
                lotNumber=r.lot_number,
                expiresAt=r.expires_at,
                balanceKg=float(r.balance_kg),
                expiringSoon=r.expires_at <= soon_cutoff,
            )
        )
    # FEFO ordering: soonest expiry first (FR-INV-3)
    out.sort(key=lambda b: b.expiresAt)
    return out


@router.post("/stock/movements", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def record_movement(
    body: MovementCreate,
    current: CurrentUser = Depends(require_permission("inventory:move")),
    session: AsyncSession = Depends(get_db),
) -> MovementOut:
    movement = await InventoryService(session).record_movement(
        body, current.organization_id, current.id
    )
    return MovementOut.model_validate(movement)


@router.get("/stock/movements", response_model=list[MovementOut])
async def list_movements(
    warehouse_id: str = Query(alias="warehouseId"),
    lot_id: str | None = Query(None, alias="lotId"),
    current: CurrentUser = Depends(require_permission("inventory:read")),
    session: AsyncSession = Depends(get_db),
) -> list[MovementOut]:
    # warehouse ownership check keeps movements org-scoped
    if await InventoryRepository(session).get_warehouse(
        warehouse_id, current.organization_id
    ) is None:
        return []
    movements = await InventoryRepository(session).list_movements(warehouse_id, lot_id)
    return [MovementOut.model_validate(m) for m in movements]


@router.get("/stock/expiring", response_model=list[StockBalanceOut])
async def expiring_stock(
    within_days: int = Query(90, alias="withinDays", ge=1, le=3650),
    current: CurrentUser = Depends(require_permission("inventory:read")),
    session: AsyncSession = Depends(get_db),
) -> list[StockBalanceOut]:
    rows = await InventoryRepository(session).expiring_lots(current.organization_id, within_days)
    return [
        StockBalanceOut(
            warehouseId=r.warehouse_id,
            lotId=r.lot_id,
            varietyId=r.variety_id,
            lotNumber=r.lot_number,
            expiresAt=r.expires_at,
            balanceKg=float(r.balance_kg),
            expiringSoon=True,
        )
        for r in sorted(rows, key=lambda x: x.expires_at)
    ]


@router.get("/stock/transfers", response_model=list[TransferOut])
async def list_transfers(
    current: CurrentUser = Depends(require_permission("inventory:read")),
    session: AsyncSession = Depends(get_db),
) -> list[TransferOut]:
    transfers = await InventoryRepository(session).list_transfers(current.organization_id)
    return [TransferOut.model_validate(t) for t in transfers]


@router.post("/stock/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    body: TransferCreate,
    current: CurrentUser = Depends(require_permission("inventory:transfer")),
    session: AsyncSession = Depends(get_db),
) -> TransferOut:
    transfer = await InventoryService(session).create_transfer(
        body, current.organization_id, current.id
    )
    return TransferOut.model_validate(transfer)


@router.post("/stock/transfers/{transfer_id}/dispatch", response_model=TransferOut)
async def dispatch_transfer(
    transfer_id: str,
    current: CurrentUser = Depends(require_permission("inventory:transfer")),
    session: AsyncSession = Depends(get_db),
) -> TransferOut:
    transfer = await InventoryService(session).dispatch_transfer(
        transfer_id, current.organization_id, current.id
    )
    return TransferOut.model_validate(transfer)


@router.post("/stock/transfers/{transfer_id}/receive", response_model=TransferOut)
async def receive_transfer(
    transfer_id: str,
    body: TransferReceive,
    current: CurrentUser = Depends(require_permission("inventory:transfer")),
    session: AsyncSession = Depends(get_db),
) -> TransferOut:
    transfer = await InventoryService(session).receive_transfer(
        transfer_id, body.received_kg, current.organization_id, current.id
    )
    return TransferOut.model_validate(transfer)


@router.post("/stock/transfers/{transfer_id}/cancel", response_model=TransferOut)
async def cancel_transfer(
    transfer_id: str,
    current: CurrentUser = Depends(require_permission("inventory:transfer")),
    session: AsyncSession = Depends(get_db),
) -> TransferOut:
    transfer = await InventoryService(session).cancel_transfer(
        transfer_id, current.organization_id, current.id
    )
    return TransferOut.model_validate(transfer)
