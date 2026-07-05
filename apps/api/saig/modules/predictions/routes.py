from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.predictions.repository import PredictionsRepository
from saig.modules.predictions.schemas import (
    DemandForecastOut,
    DemandSeriesOut,
    JobResult,
    ModelVersionOut,
    YieldPredictionOut,
    YieldRescoreRequest,
)
from saig.modules.predictions.service import PredictionService

forecasts_router = APIRouter(prefix="/forecasts", tags=["predictions"])
predictions_router = APIRouter(prefix="/predictions", tags=["predictions"])
models_router = APIRouter(prefix="/models", tags=["predictions"])


# --- Yield -------------------------------------------------------------------

@predictions_router.get("/yield", response_model=list[YieldPredictionOut])
async def list_yield_predictions(
    crop_cycle_id: str | None = Query(None, alias="cropCycleId"),
    current: CurrentUser = Depends(require_permission("forecasts:read")),
    session: AsyncSession = Depends(get_db),
) -> list[YieldPredictionOut]:
    repo = PredictionsRepository(session)
    if crop_cycle_id:
        row = await repo.latest_yield_for_cycle(crop_cycle_id)
        return [YieldPredictionOut.model_validate(row)] if row else []
    rows = await repo.latest_yield_predictions(current.organization_id)
    return [YieldPredictionOut.model_validate(r) for r in rows]


@predictions_router.post(
    "/yield/rescore", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED
)
async def rescore_yield(
    body: YieldRescoreRequest,
    current: CurrentUser = Depends(require_permission("forecasts:trigger")),
    session: AsyncSession = Depends(get_db),
) -> JobResult:
    count = await PredictionService(session).score_yield(
        current.organization_id, current.id, body.crop_cycle_ids, run_type="manual"
    )
    return JobResult(status="completed", detail=f"Scored {count} crop cycle(s).", count=count)


# --- Demand ------------------------------------------------------------------

@forecasts_router.get("/demand", response_model=DemandSeriesOut)
async def demand_series(
    region_id: str = Query(alias="regionId"),
    variety_id: str = Query(alias="varietyId"),
    current: CurrentUser = Depends(require_permission("forecasts:read")),
    session: AsyncSession = Depends(get_db),
) -> DemandSeriesOut:
    rows = await PredictionService(session).demand_series(
        current.organization_id, region_id, variety_id
    )
    return DemandSeriesOut(
        regionId=region_id,
        varietyId=variety_id,
        modelVersion="promoted",
        points=[DemandForecastOut.model_validate(r) for r in rows],
    )


@forecasts_router.post(
    "/demand/run", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED
)
async def run_demand(
    current: CurrentUser = Depends(require_permission("forecasts:trigger")),
    session: AsyncSession = Depends(get_db),
) -> JobResult:
    count = await PredictionService(session).run_demand_forecast(
        current.organization_id, current.id
    )
    return JobResult(status="completed", detail=f"Generated {count} forecast points.", count=count)


# --- Model registry ----------------------------------------------------------

@models_router.get("", response_model=list[ModelVersionOut])
async def list_models(
    model_name: str | None = Query(None, alias="name"),
    current: CurrentUser = Depends(require_permission("models:read")),
    session: AsyncSession = Depends(get_db),
) -> list[ModelVersionOut]:
    models = await PredictionsRepository(session).list_models(
        current.organization_id, model_name
    )
    return [ModelVersionOut.model_validate(m) for m in models]
