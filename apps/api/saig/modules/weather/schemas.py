from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DailyWeatherOut(BaseModel):
    day: date
    rainfallMm: float | None = None
    tempMinC: float | None = None
    tempMaxC: float | None = None
    humidityPct: float | None = None
    windKmh: float | None = None


class ForecastResponse(BaseModel):
    cellKey: str
    latitude: float
    longitude: float
    source: str
    issuedAt: datetime | None = None
    stale: bool
    days: list[DailyWeatherOut]


class HistoryResponse(BaseModel):
    cellKey: str
    latitude: float
    longitude: float
    days: list[DailyWeatherOut]


class AgroIndicators(BaseModel):
    """Agronomic aggregates over recent observed weather (FR-WX-2)."""

    cellKey: str
    windowDays: int
    rainfall7dMm: float | None = None
    rainfall30dMm: float | None = None
    rainfall90dMm: float | None = None
    growingDegreeDays: float | None = Field(default=None, description="base 10°C")
    heatStressDays: int = 0
    dataPoints: int
    asOf: date | None = None
