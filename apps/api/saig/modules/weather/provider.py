"""Weather provider abstraction.

The provider is a port (Protocol); the API/service depend on the interface,
not on Open-Meteo. Tests inject a deterministic fake — no real HTTP in the
suite (testing-strategy.md). Open-Meteo is keyless, which keeps local dev
Docker-free and credential-free (ADR-0001 spirit).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

import httpx

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


@dataclass(frozen=True)
class DailyWeather:
    day: date
    rainfall_mm: float | None
    temp_min_c: float | None
    temp_max_c: float | None
    humidity_pct: float | None
    wind_kmh: float | None


class WeatherProvider(Protocol):
    source_name: str

    async def fetch_forecast(
        self, latitude: float, longitude: float, days: int = 14
    ) -> list[DailyWeather]: ...

    async def fetch_history(
        self, latitude: float, longitude: float, start: date, end: date
    ) -> list[DailyWeather]: ...


def _zip_daily(daily: dict) -> list[DailyWeather]:
    times = daily.get("time", [])
    rain = daily.get("precipitation_sum", [])
    tmin = daily.get("temperature_2m_min", [])
    tmax = daily.get("temperature_2m_max", [])
    humidity = daily.get("relative_humidity_2m_mean", [])
    wind = daily.get("wind_speed_10m_max", [])

    def at(seq: list, i: int):
        return seq[i] if i < len(seq) else None

    out: list[DailyWeather] = []
    for i, t in enumerate(times):
        out.append(
            DailyWeather(
                day=date.fromisoformat(t),
                rainfall_mm=at(rain, i),
                temp_min_c=at(tmin, i),
                temp_max_c=at(tmax, i),
                humidity_pct=at(humidity, i),
                wind_kmh=at(wind, i),
            )
        )
    return out


class OpenMeteoProvider:
    """Keyless Open-Meteo integration (forecast + historical archive)."""

    source_name = "open-meteo"

    _DAILY_VARS = (
        "precipitation_sum,temperature_2m_min,temperature_2m_max,"
        "relative_humidity_2m_mean,wind_speed_10m_max"
    )

    def __init__(self, timeout_seconds: float = 10.0):
        self._timeout = timeout_seconds

    async def fetch_forecast(
        self, latitude: float, longitude: float, days: int = 14
    ) -> list[DailyWeather]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": self._DAILY_VARS,
            "forecast_days": min(max(days, 1), 16),
            "timezone": "UTC",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            res = await client.get(OPEN_METEO_FORECAST_URL, params=params)
            res.raise_for_status()
            return _zip_daily(res.json().get("daily", {}))

    async def fetch_history(
        self, latitude: float, longitude: float, start: date, end: date
    ) -> list[DailyWeather]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": self._DAILY_VARS,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timezone": "UTC",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            res = await client.get(OPEN_METEO_ARCHIVE_URL, params=params)
            res.raise_for_status()
            return _zip_daily(res.json().get("daily", {}))


class FakeWeatherProvider:
    """Deterministic provider for tests and offline dev.

    Generates smooth pseudo-weather from the date + location so results are
    stable and assertions are possible without network access.
    """

    source_name = "fake"

    async def fetch_forecast(
        self, latitude: float, longitude: float, days: int = 14
    ) -> list[DailyWeather]:
        today = date.today()
        return [self._day(latitude, today + timedelta(days=i)) for i in range(days)]

    async def fetch_history(
        self, latitude: float, longitude: float, start: date, end: date
    ) -> list[DailyWeather]:
        out: list[DailyWeather] = []
        cursor = start
        while cursor <= end:
            out.append(self._day(latitude, cursor))
            cursor += timedelta(days=1)
        return out

    @staticmethod
    def _day(latitude: float, day: date) -> DailyWeather:
        seasonal = (day.timetuple().tm_yday % 60) / 60  # 0..1 sawtooth
        return DailyWeather(
            day=day,
            rainfall_mm=round(2 + 8 * seasonal, 1),
            temp_min_c=round(14 + 4 * seasonal, 1),
            temp_max_c=round(26 + 8 * seasonal, 1),
            humidity_pct=round(55 + 20 * seasonal, 1),
            wind_kmh=round(8 + 6 * seasonal, 1),
        )
