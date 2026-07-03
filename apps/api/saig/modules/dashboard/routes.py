from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.dashboard.schemas import DashboardKpis
from saig.modules.dashboard.service import DashboardService
from saig.modules.iam.deps import CurrentUser, get_current_user, get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpis)
async def dashboard_kpis(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardKpis:
    # Any authenticated user sees KPIs scoped to their organization; the
    # figures are aggregate and contain no PII.
    return await DashboardService(session).kpis(current.organization_id)
