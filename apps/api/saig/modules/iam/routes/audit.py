from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.iam.repository import IamRepository
from saig.modules.iam.schemas import AuditLogOut
from saig.shared.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogOut])
async def list_audit_logs(
    params: PageParams = Depends(page_params),
    action: str | None = Query(None, max_length=120),
    actor_id: str | None = Query(None, alias="actorId"),
    entity_table: str | None = Query(None, alias="entityTable", max_length=80),
    current: CurrentUser = Depends(require_permission("audit:read")),
    session: AsyncSession = Depends(get_db),
) -> Page[AuditLogOut]:
    logs, total = await IamRepository(session).list_audit_logs(
        current.organization_id, params, action, actor_id, entity_table
    )
    return Page.build([AuditLogOut.model_validate(item) for item in logs], total, params)
