from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.weather.models import WeatherCell, WeatherForecast, WeatherObservation
from saig.modules.weather.provider import DailyWeather, WeatherProvider
from saig.modules.weather.schemas import (
    AgroIndicators,
    DailyWeatherOut,
    ForecastResponse,
    HistoryResponse,
)
from saig.shared.database import utcnow
from saig.shared.geo import weather_cell

GDD_BASE_C = 10.0  # maize base temperature
HEAT_STRESS_C = 35.0
FORECAST_TTL_HOURS = 6  # FR-WX-1: refresh at least every 6h


class WeatherService:
    def __init__(self, session: AsyncSession, provider: WeatherProvider):
        self.session = session
        self.provider = provider

    async def _get_or_create_cell(self, latitude: float, longitude: float) -> WeatherCell:
        key, cell_lat, cell_lng = weather_cell(latitude, longitude)
        cell = (
            await self.session.execute(
                select(WeatherCell).where(WeatherCell.cell_key == key)
            )
        ).scalar_one_or_none()
        if cell is None:
            cell = WeatherCell(cell_key=key, latitude=cell_lat, longitude=cell_lng)
            self.session.add(cell)
            await self.session.flush()
        return cell

    async def get_forecast(
        self, latitude: float, longitude: float, days: int = 14, refresh: bool = False
    ) -> ForecastResponse:
        cell = await self._get_or_create_cell(latitude, longitude)

        existing = list(
            (
                await self.session.execute(
                    select(WeatherForecast)
                    .where(WeatherForecast.cell_id == cell.id)
                    .where(WeatherForecast.forecast_date >= date.today())
                    .order_by(WeatherForecast.forecast_date)
                )
            )
            .scalars()
            .all()
        )
        issued = max((f.issued_at for f in existing), default=None)
        stale = issued is None or (utcnow() - issued) > timedelta(hours=FORECAST_TTL_HOURS)

        if refresh or stale:
            fetched = await self.provider.fetch_forecast(
                float(cell.latitude), float(cell.longitude), days
            )
            await self._upsert_forecast(cell, fetched)
            await self.session.commit()
            existing = list(
                (
                    await self.session.execute(
                        select(WeatherForecast)
                        .where(WeatherForecast.cell_id == cell.id)
                        .where(WeatherForecast.forecast_date >= date.today())
                        .order_by(WeatherForecast.forecast_date)
                    )
                )
                .scalars()
                .all()
            )
            issued = max((f.issued_at for f in existing), default=None)
            stale = False

        return ForecastResponse(
            cellKey=cell.cell_key,
            latitude=float(cell.latitude),
            longitude=float(cell.longitude),
            source=self.provider.source_name,
            issuedAt=issued,
            stale=stale,
            days=[
                DailyWeatherOut(
                    day=f.forecast_date,
                    rainfallMm=_f(f.rainfall_mm),
                    tempMinC=_f(f.temp_min_c),
                    tempMaxC=_f(f.temp_max_c),
                    humidityPct=_f(f.humidity_pct),
                    windKmh=_f(f.wind_kmh),
                )
                for f in existing[:days]
            ],
        )

    async def get_history(
        self, latitude: float, longitude: float, start: date, end: date
    ) -> HistoryResponse:
        cell = await self._get_or_create_cell(latitude, longitude)
        rows = list(
            (
                await self.session.execute(
                    select(WeatherObservation)
                    .where(WeatherObservation.cell_id == cell.id)
                    .where(WeatherObservation.observed_date.between(start, end))
                    .order_by(WeatherObservation.observed_date)
                )
            )
            .scalars()
            .all()
        )
        have = {r.observed_date for r in rows}
        wanted = {start + timedelta(days=i) for i in range((end - start).days + 1)}
        if wanted - have:
            fetched = await self.provider.fetch_history(
                float(cell.latitude), float(cell.longitude), start, end
            )
            await self._upsert_observations(cell, fetched)
            await self.session.commit()
            rows = list(
                (
                    await self.session.execute(
                        select(WeatherObservation)
                        .where(WeatherObservation.cell_id == cell.id)
                        .where(WeatherObservation.observed_date.between(start, end))
                        .order_by(WeatherObservation.observed_date)
                    )
                )
                .scalars()
                .all()
            )

        return HistoryResponse(
            cellKey=cell.cell_key,
            latitude=float(cell.latitude),
            longitude=float(cell.longitude),
            days=[
                DailyWeatherOut(
                    day=r.observed_date,
                    rainfallMm=_f(r.rainfall_mm),
                    tempMinC=_f(r.temp_min_c),
                    tempMaxC=_f(r.temp_max_c),
                    humidityPct=_f(r.humidity_pct),
                    windKmh=_f(r.wind_kmh),
                )
                for r in rows
            ],
        )

    async def get_agro_indicators(
        self, latitude: float, longitude: float, window_days: int = 90
    ) -> AgroIndicators:
        end = date.today() - timedelta(days=1)  # yesterday is the last settled day
        start = end - timedelta(days=window_days - 1)
        history = await self.get_history(latitude, longitude, start, end)
        cell_key, *_ = weather_cell(latitude, longitude)

        def rainfall_since(days: int) -> float | None:
            cutoff = end - timedelta(days=days - 1)
            vals = [
                d.rainfallMm
                for d in history.days
                if d.day >= cutoff and d.rainfallMm is not None
            ]
            return round(sum(vals), 1) if vals else None

        gdd = 0.0
        gdd_points = 0
        heat_days = 0
        for d in history.days:
            if d.tempMinC is not None and d.tempMaxC is not None:
                mean = (d.tempMinC + d.tempMaxC) / 2
                gdd += max(0.0, mean - GDD_BASE_C)
                gdd_points += 1
            if d.tempMaxC is not None and d.tempMaxC > HEAT_STRESS_C:
                heat_days += 1

        return AgroIndicators(
            cellKey=cell_key,
            windowDays=window_days,
            rainfall7dMm=rainfall_since(7),
            rainfall30dMm=rainfall_since(30),
            rainfall90dMm=rainfall_since(90),
            growingDegreeDays=round(gdd, 1) if gdd_points else None,
            heatStressDays=heat_days,
            dataPoints=len(history.days),
            asOf=history.days[-1].day if history.days else None,
        )

    # --- persistence helpers -------------------------------------------------

    async def _upsert_forecast(self, cell: WeatherCell, days: list[DailyWeather]) -> None:
        existing = {
            f.forecast_date: f
            for f in (
                await self.session.execute(
                    select(WeatherForecast).where(WeatherForecast.cell_id == cell.id)
                )
            )
            .scalars()
            .all()
        }
        now = utcnow()
        for d in days:
            row = existing.get(d.day)
            if row is None:
                row = WeatherForecast(cell_id=cell.id, forecast_date=d.day)
                self.session.add(row)
            row.rainfall_mm = d.rainfall_mm
            row.temp_min_c = d.temp_min_c
            row.temp_max_c = d.temp_max_c
            row.humidity_pct = d.humidity_pct
            row.wind_kmh = d.wind_kmh
            row.source = self.provider.source_name
            row.issued_at = now

    async def _upsert_observations(self, cell: WeatherCell, days: list[DailyWeather]) -> None:
        existing = {
            o.observed_date
            for o in (
                await self.session.execute(
                    select(WeatherObservation).where(WeatherObservation.cell_id == cell.id)
                )
            )
            .scalars()
            .all()
        }
        for d in days:
            if d.day in existing:
                continue
            self.session.add(
                WeatherObservation(
                    cell_id=cell.id,
                    observed_date=d.day,
                    rainfall_mm=d.rainfall_mm,
                    temp_min_c=d.temp_min_c,
                    temp_max_c=d.temp_max_c,
                    humidity_pct=d.humidity_pct,
                    wind_kmh=d.wind_kmh,
                    source=self.provider.source_name,
                )
            )


def _f(value) -> float | None:
    return None if value is None else float(value)
