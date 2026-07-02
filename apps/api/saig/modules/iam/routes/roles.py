from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.iam.schemas import PermissionOut, RoleCreate, RoleOut, RoleUpdate
from saig.modules.iam.services.role_service import RoleService

router = APIRouter(tags=["roles"])


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    current: CurrentUser = Depends(require_permission("roles:manage")),
    session: AsyncSession = Depends(get_db),
) -> list[PermissionOut]:
    permissions = await RoleService(session).list_permissions()
    return [PermissionOut.model_validate(p) for p in permissions]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    current: CurrentUser = Depends(require_permission("users:read")),
    session: AsyncSession = Depends(get_db),
) -> list[RoleOut]:
    roles = await RoleService(session).list_roles(current.organization_id)
    return [RoleOut.model_validate(r) for r in roles]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    current: CurrentUser = Depends(require_permission("roles:manage")),
    session: AsyncSession = Depends(get_db),
) -> RoleOut:
    role = await RoleService(session).create_role(body, current.organization_id, current.id)
    return RoleOut.model_validate(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: str,
    body: RoleUpdate,
    current: CurrentUser = Depends(require_permission("roles:manage")),
    session: AsyncSession = Depends(get_db),
) -> RoleOut:
    role = await RoleService(session).update_role(
        role_id, body, current.organization_id, current.id
    )
    return RoleOut.model_validate(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    current: CurrentUser = Depends(require_permission("roles:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await RoleService(session).delete_role(role_id, current.organization_id, current.id)
