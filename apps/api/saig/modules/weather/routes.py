from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.fieldops.repository import FieldOpsRepository
from saig.modules.iam.deps import CurrentUser, get_db, require_permission
from saig.modules.weather.deps import get_weather_provider
from saig.modules.weather.provider import WeatherProvider
from saig.modules.weather.schemas import AgroIndicators, ForecastResponse, HistoryResponse
from saig.modules.weather.service import WeatherService
from saig.shared.errors import AppError, NotFoundError

router = APIRouter(prefix="/weather", tags=["weather"])


class WeatherUnavailableError(AppError):
    status_code = 503
    error_type = "weather_unavailable"
    title = "Weather provider unavailable"


async def _resolve_location(
    session: AsyncSession,
    organization_id: str,
    farm_id: str | None,
    lat: float | None,
    lng: float | None,
) -> tuple[float, float]:
    if farm_id:
        farm = await FieldOpsRepository(session).get_farm(farm_id, organization_id)
        if farm is None:
            raise NotFoundError("Farm not found.")
        return float(farm.latitude), float(farm.longitude)
    if lat is not None and lng is not None:
        return lat, lng
    raise NotFoundError("Provide farmId or lat/lng.")


@router.get("/forecast", response_model=ForecastResponse)
async def forecast(
    farm_id: str | None = Query(None, alias="farmId"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    days: int = Query(14, ge=1, le=16),
    refresh: bool = Query(False),
    current: CurrentUser = Depends(require_permission("weather:read")),
    session: AsyncSession = Depends(get_db),
    provider: WeatherProvider = Depends(get_weather_provider),
) -> ForecastResponse:
    latitude, longitude = await _resolve_location(
        session, current.organization_id, farm_id, lat, lng
    )
    try:
        return await WeatherService(session, provider).get_forecast(
            latitude, longitude, days, refresh
        )
    except httpx.HTTPError as exc:
        raise WeatherUnavailableError("Could not reach the weather provider.") from exc


@router.get("/history", response_model=HistoryResponse)
async def history(
    farm_id: str | None = Query(None, alias="farmId"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    days: int = Query(30, ge=1, le=365),
    current: CurrentUser = Depends(require_permission("weather:read")),
    session: AsyncSession = Depends(get_db),
    provider: WeatherProvider = Depends(get_weather_provider),
) -> HistoryResponse:
    latitude, longitude = await _resolve_location(
        session, current.organization_id, farm_id, lat, lng
    )
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    try:
        return await WeatherService(session, provider).get_history(
            latitude, longitude, start, end
        )
    except httpx.HTTPError as exc:
        raise WeatherUnavailableError("Could not reach the weather provider.") from exc


@router.get("/aggregates", response_model=AgroIndicators)
async def aggregates(
    farm_id: str | None = Query(None, alias="farmId"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    window: int = Query(90, ge=7, le=365),
    current: CurrentUser = Depends(require_permission("weather:read")),
    session: AsyncSession = Depends(get_db),
    provider: WeatherProvider = Depends(get_weather_provider),
) -> AgroIndicators:
    latitude, longitude = await _resolve_location(
        session, current.organization_id, farm_id, lat, lng
    )
    try:
        return await WeatherService(session, provider).get_agro_indicators(
            latitude, longitude, window
        )
    except httpx.HTTPError as exc:
        raise WeatherUnavailableError("Could not reach the weather provider.") from exc
