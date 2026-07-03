import pytest

from saig.shared.geo import GeoJSONPolygon, polygon_area_hectares


def square(lng0: float, lat0: float, size_deg: float) -> GeoJSONPolygon:
    return GeoJSONPolygon(
        type="Polygon",
        coordinates=[[
            [lng0, lat0],
            [lng0 + size_deg, lat0],
            [lng0 + size_deg, lat0 + size_deg],
            [lng0, lat0 + size_deg],
            [lng0, lat0],
        ]],
    )


def test_equatorial_square_area_close_to_expected():
    # 0.001° ≈ 111.32 m at the equator → ~1.239 ha square
    area = polygon_area_hectares(square(37.0, 0.0, 0.001))
    assert 1.20 <= area <= 1.28


def test_hole_subtracts_area():
    outer = square(37.0, 0.0, 0.002)
    inner = square(37.0005, 0.0005, 0.001)
    polygon = GeoJSONPolygon(
        type="Polygon",
        coordinates=[outer.coordinates[0], inner.coordinates[0]],
    )
    full = polygon_area_hectares(outer)
    holed = polygon_area_hectares(polygon)
    assert holed < full
    assert abs(holed - (full - polygon_area_hectares(inner))) < 0.01


def test_invalid_polygons_rejected():
    with pytest.raises(ValueError, match="Polygon"):
        GeoJSONPolygon(type="Point", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]])
    with pytest.raises(ValueError, match="closed"):
        GeoJSONPolygon(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1]]])
    with pytest.raises(ValueError, match="out of range"):
        GeoJSONPolygon(
            type="Polygon",
            coordinates=[[[200, 0], [201, 0], [201, 1], [200, 0]]],
        )
