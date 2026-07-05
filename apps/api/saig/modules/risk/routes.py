from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.risk.schemas import JobResult, RiskBoardOut, RiskHistoryPoint
from saig.modules.risk.scoring import RISK_DOMAINS
from saig.modules.risk.service import RiskService
from saig.modules.weather.deps import get_weather_provider
from saig.modules.weather.provider import WeatherProvider

router = APIRouter(prefix="/risks", tags=["risk"])


@router.get("/board", response_model=RiskBoardOut)
async def risk_board(
    region_id: str | None = Query(None, alias="regionId"),
    current: CurrentUser = Depends(require_permission("risks:read")),
    session: AsyncSession = Depends(get_db),
) -> RiskBoardOut:
    board = await RiskService(session).board(current.organization_id, region_id)
    return RiskBoardOut(**board)


@router.get("/history", response_model=list[RiskHistoryPoint])
async def risk_history(
    domain: str = Query(...),
    region_id: str | None = Query(None, alias="regionId"),
    days: int = Query(90, ge=7, le=365),
    current: CurrentUser = Depends(require_permission("risks:read")),
    session: AsyncSession = Depends(get_db),
) -> list[RiskHistoryPoint]:
    if domain not in RISK_DOMAINS:
        return []
    points = await RiskService(session).history(
        current.organization_id, region_id, domain, days
    )
    return [RiskHistoryPoint(**p) for p in points]


@router.post("/recompute", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
async def recompute(
    current: CurrentUser = Depends(require_permission("risks:compute")),
    session: AsyncSession = Depends(get_db),
    provider: WeatherProvider = Depends(get_weather_provider),
) -> JobResult:
    count = await RiskService(session, provider).recompute(current.organization_id, current.id)
    return JobResult(status="completed", detail=f"Wrote {count} risk assessments.", count=count)
