"""Portable geospatial helpers (ADR-0002): GeoJSON validation + spherical area."""

import math
from typing import Any

from pydantic import BaseModel, field_validator

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG)


class GeoJSONPolygon(BaseModel):
    """A validated GeoJSON Polygon (WGS84, [lng, lat] positions)."""

    type: str
    coordinates: list[list[list[float]]]

    @field_validator("type")
    @classmethod
    def _must_be_polygon(cls, v: str) -> str:
        if v != "Polygon":
            raise ValueError("boundary must be a GeoJSON Polygon")
        return v

    @field_validator("coordinates")
    @classmethod
    def _validate_rings(cls, rings: list[list[list[float]]]) -> list[list[list[float]]]:
        if not rings:
            raise ValueError("polygon must have at least an exterior ring")
        for ring in rings:
            if len(ring) < 4:
                raise ValueError("each ring needs at least 4 positions (closed)")
            if ring[0] != ring[-1]:
                raise ValueError("rings must be closed (first position == last)")
            for pos in ring:
                if len(pos) < 2:
                    raise ValueError("positions must be [lng, lat]")
                lng, lat = pos[0], pos[1]
                if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
                    raise ValueError(f"position out of range: [{lng}, {lat}]")
        return rings

    def model_dump_geojson(self) -> dict[str, Any]:
        return {"type": "Polygon", "coordinates": self.coordinates}


def _ring_area_m2(ring: list[list[float]]) -> float:
    """Spherical excess area of one ring (Chamberlain & Duquette 2007)."""
    if len(ring) < 4:
        return 0.0
    total = 0.0
    n = len(ring) - 1  # last == first
    for i in range(n):
        lng1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lng2, lat2 = math.radians(ring[(i + 1) % n][0]), math.radians(ring[(i + 1) % n][1])
        total += (lng2 - lng1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(total) * EARTH_RADIUS_M**2 / 2


def polygon_area_hectares(polygon: GeoJSONPolygon) -> float:
    """Exterior ring minus holes, in hectares."""
    rings = polygon.coordinates
    area = _ring_area_m2(rings[0])
    for hole in rings[1:]:
        area -= _ring_area_m2(hole)
    return round(max(area, 0.0) / 10_000, 4)


def validate_lat_lng(latitude: float, longitude: float) -> None:
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise ValueError("coordinates out of WGS84 range")


# ~0.05° ≈ 5.5 km at the equator — the weather ingestion grid resolution.
WEATHER_CELL_SIZE_DEG = 0.05


def weather_cell(latitude: float, longitude: float) -> tuple[str, float, float]:
    """Snap a coordinate to its grid cell. Returns (key, cell_lat, cell_lng).

    Farms in the same cell share one weather series, bounding external API
    cost by geography rather than farm count (schema.sql: intel.weather_cells).
    """
    cell_lat = round(round(latitude / WEATHER_CELL_SIZE_DEG) * WEATHER_CELL_SIZE_DEG, 3)
    cell_lng = round(round(longitude / WEATHER_CELL_SIZE_DEG) * WEATHER_CELL_SIZE_DEG, 3)
    return f"{cell_lat:.3f},{cell_lng:.3f}", cell_lat, cell_lng


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km — used for disease-outbreak clustering."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))
