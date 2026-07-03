from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from saig.shared.database import GUID, Base, TZDateTime, new_uuid, utcnow


class WeatherCell(Base):
    """A ~5 km grid cell. Farms resolve to a shared cell so ingestion cost is
    bounded by geography, not by farm count (schema.sql: intel.weather_cells)."""

    __tablename__ = "weather_cells"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    cell_key: Mapped[str] = mapped_column(String(40), unique=True)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    cell_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("weather_cells.id"), primary_key=True
    )
    observed_date: Mapped[date] = mapped_column(Date, primary_key=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    temp_min_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    temp_max_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    wind_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    cell_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("weather_cells.id"), primary_key=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, primary_key=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    temp_min_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    temp_max_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    wind_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    issued_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("cell_id", "forecast_date", name="uq_forecast_cell_date"),
    )
