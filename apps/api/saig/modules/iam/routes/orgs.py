from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_current_user, get_db, require_permission
from saig.modules.iam.schemas import (
    DepartmentCreate,
    DepartmentOut,
    OrganizationOut,
    OrganizationUpdate,
)
from saig.modules.iam.services.org_service import OrgService

router = APIRouter(tags=["organization"])


@router.get("/organization", response_model=OrganizationOut)
async def get_organization(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrganizationOut:
    org = await OrgService(session).get_organization(current.organization_id)
    return OrganizationOut.model_validate(org)


@router.patch("/organization", response_model=OrganizationOut)
async def update_organization(
    body: OrganizationUpdate,
    current: CurrentUser = Depends(require_permission("org:manage")),
    session: AsyncSession = Depends(get_db),
) -> OrganizationOut:
    org = await OrgService(session).update_organization(
        current.organization_id, body, current.id
    )
    return OrganizationOut.model_validate(org)


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[DepartmentOut]:
    departments = await OrgService(session).list_departments(current.organization_id)
    return [DepartmentOut.model_validate(d) for d in departments]


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    current: CurrentUser = Depends(require_permission("org:manage")),
    session: AsyncSession = Depends(get_db),
) -> DepartmentOut:
    dept = await OrgService(session).create_department(body, current.organization_id, current.id)
    return DepartmentOut.model_validate(dept)


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: str,
    current: CurrentUser = Depends(require_permission("org:manage")),
    session: AsyncSession = Depends(get_db),
) -> None:
    await OrgService(session).delete_department(
        department_id, current.organization_id, current.id
    )
