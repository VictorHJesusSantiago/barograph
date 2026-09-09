"""Tests for the geospatial module (interpolation, masking, projection)."""

from __future__ import annotations

import numpy as np
import pytest

from barograph.core.models import GriddedField, ModelSource, Variable
from barograph.geospatial import (
    IDWInterpolator,
    SimpleKriging,
    bounding_box,
    haversine_distance,
    interpolate_station_field,
    mask_outside_polygon,
    mask_radius,
    point_in_polygon,
)
from barograph.raster.layer import CRS, RasterLayer


def test_haversine_baseline():
    # ~111km per degree of latitude
    d = haversine_distance(0.0, 0.0, 0.0, 1.0)
    assert 110.0 < d < 112.0


def test_distance_symmetric():
    d1 = haversine_distance(10.0, 20.0, 12.0, 22.0)
    d2 = haversine_distance(12.0, 22.0, 10.0, 20.0)
    assert d1 == pytest.approx(d2)


def test_honolulu_baseline():
    # Approximate great-circle distance Honolulu->Tokyo ~6160 km
    d = haversine_distance(-157.86, 21.31, 139.69, 35.68)
    assert 6000 < d < 6300


def test_point_in_polygon():
    poly = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert point_in_polygon(5.0, 5.0, poly)
    assert not point_in_polygon(50.0, 5.0, poly)


def test_bounding_box():
    lons = np.array([-50.0, -45.0])
    lats = np.array([-25.0, -20.0])
    lon_min, lon_max, lat_min, lat_max = bounding_box(lons, lats, margin_deg=1.0)
    assert lon_min == -51.0
    assert lat_max == -19.0


def test_idw_reproduces_station_values():
    interp = IDWInterpolator(max_points=1)
    grid = interp.fit_predict(
        np.array([0.0]), np.array([0.0]), np.array([42.0]),
        np.array([0.0]), np.array([0.0]),
    )
    assert grid[0, 0] == pytest.approx(42.0)


def test_interpolate_station_field_creates_grid():
    field = interpolate_station_field(
        obs_lons=np.array([-50.0, -49.0]),
        obs_lats=np.array([-25.0, -24.0]),
        obs_values=np.array([10.0, 20.0]),
        grid_lons=np.linspace(-50.0, -49.0, 3),
        grid_lats=np.linspace(-25.0, -24.0, 3),
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        valid_time="2026-01-01T00:00:00",
        init_time="2026-01-01T00:00:00",
        method="nearest",
    )
    assert isinstance(field, GriddedField)
    assert field.data.shape == (3, 3)
    assert field.meta["interpolation"] == "nearest"


def test_interpolate_station_field_unknown_method():
    with pytest.raises(ValueError):
        interpolate_station_field(
            obs_lons=np.array([0.0]), obs_lats=np.array([0.0]),
            obs_values=np.array([1.0]),
            grid_lons=np.array([0.0]), grid_lats=np.array([0.0]),
            variable=Variable.TEMPERATURE, source=ModelSource.GFS,
            valid_time="2026-01-01", init_time="2026-01-01",
            method="bogus",
        )


def test_mask_outside_polygon():
    layer = make_layer(np.full((5, 6), 1.0))
    # strictly larger than the layer domain -> all cells inside
    square = [(-49.0, -27.0), (-43.0, -27.0), (-43.0, -19.0), (-49.0, -19.0)]
    masked = mask_outside_polygon(layer, square)
    valid = masked.band(0)
    assert np.all(np.isfinite(valid))  # whole layer inside polygon


def test_mask_outside_polygon_partial():
    layer = make_layer(np.full((5, 6), 1.0))
    # sub-region rectangle -> outer cells become NaN
    square = [(-47.0, -25.0), (-45.0, -25.0), (-45.0, -21.0), (-47.0, -21.0)]
    masked = mask_outside_polygon(layer, square)
    valid = masked.band(0)
    assert np.any(np.isnan(valid))
    assert np.any(np.isfinite(valid))


def test_mask_radius():
    layer = make_layer(np.full((5, 6), 1.0))
    masked = mask_radius(layer, -46.0, -23.0, radius_km=50.0)
    valid = masked.band(0)
    assert np.any(np.isnan(valid))


def test_simple_kriging_sane_output():
    interp = SimpleKriging(range_km=200.0)
    out = interp.fit_predict(
        np.array([0.0, 1.0, 2.0]), np.array([0.0, 0.0, 0.0]),
        np.array([10.0, 12.0, 14.0]),
        grid_lons=np.array([1.0]), grid_lats=np.array([0.0]),
    )
    assert np.isfinite(out[0, 0])
    assert 9.0 < out[0, 0] < 15.0


def make_layer(data):
    lats = np.linspace(-26.0, -20.0, data.shape[0])
    lons = np.linspace(-48.0, -44.0, data.shape[1])
    return RasterLayer(data=data, lats=lats, lons=lons, name="t",
                       crs=CRS(epsg=4326))
