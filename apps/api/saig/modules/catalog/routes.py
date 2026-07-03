from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.catalog.schemas import (
    SuitabilityEntry,
    VarietyCreate,
    VarietyOut,
    VarietyUpdate,
)
from saig.modules.catalog.service import CatalogService
from saig.modules.iam.deps import CurrentUser, get_db, require_permission

router = APIRouter(prefix="/varieties", tags=["varieties"])


@router.get("", response_model=list[VarietyOut])
async def list_varieties(
    crop: str | None = Query(None, max_length=60),
    include_inactive: bool = Query(False, alias="includeInactive"),
    current: CurrentUser = Depends(require_permission("varieties:read")),
    session: AsyncSession = Depends(get_db),
) -> list[VarietyOut]:
    varieties = await CatalogService(session).list_varieties(
        current.organization_id, crop, include_inactive
    )
    return [VarietyOut.model_validate(v) for v in varieties]


@router.post("", response_model=VarietyOut, status_code=status.HTTP_201_CREATED)
async def create_variety(
    body: VarietyCreate,
    current: CurrentUser = Depends(require_permission("varieties:manage")),
    session: AsyncSession = Depends(get_db),
) -> VarietyOut:
    variety = await CatalogService(session).create_variety(
        body, current.organization_id, current.id
    )
    return VarietyOut.model_validate(variety)


@router.get("/{variety_id}", response_model=VarietyOut)
async def get_variety(
    variety_id: str,
    current: CurrentUser = Depends(require_permission("varieties:read")),
    session: AsyncSession = Depends(get_db),
) -> VarietyOut:
    variety = await CatalogService(session).get_variety(variety_id, current.organization_id)
    return VarietyOut.model_validate(variety)


@router.patch("/{variety_id}", response_model=VarietyOut)
async def update_variety(
    variety_id: str,
    body: VarietyUpdate,
    current: CurrentUser = Depends(require_permission("varieties:manage")),
    session: AsyncSession = Depends(get_db),
) -> VarietyOut:
    variety = await CatalogService(session).update_variety(
        variety_id, body, current.organization_id, current.id
    )
    return VarietyOut.model_validate(variety)


@router.delete("/{variety_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variety(
    variety_id: str,
    current: CurrentUser = Depends(require_permission("varieties:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await CatalogService(session).delete_variety(variety_id, current.organization_id, current.id)


@router.put("/{variety_id}/suitability", response_model=VarietyOut)
async def set_suitability(
    variety_id: str,
    body: list[SuitabilityEntry],
    current: CurrentUser = Depends(require_permission("varieties:manage")),
    session: AsyncSession = Depends(get_db),
) -> VarietyOut:
    variety = await CatalogService(session).set_suitability(
        variety_id, body, current.organization_id, current.id
    )
    return VarietyOut.model_validate(variety)
