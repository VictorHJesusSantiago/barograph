"""Unit tests for coordinate and temporal utilities."""

from datetime import datetime, timedelta

import numpy as np

from barograph.core.coordinates import (
    clip_to_bbox,
    create_grid,
    extract_point_series,
    find_nearest_grid_point,
    haversine_distance,
)
from barograph.core.models import Coordinate
from barograph.core.temporal import (
    resample_temporal,
    temporal_interpolate,
    time_weights,
    utcnow,
)


def test_haversine_distance_same_point():
    coord = Coordinate(0.0, 0.0)
    assert haversine_distance(coord, coord) < 1e-6


def test_haversine_distance_pole_to_pole():
    c1 = Coordinate(0.0, 0.0)
    c2 = Coordinate(90.0, 0.0)
    assert 10000.0 < haversine_distance(c1, c2) < 10011.0


def test_find_nearest_grid_point():
    lats = np.linspace(-25, -20, 50)
    lons = np.linspace(-50, -45, 60)
    target = Coordinate(latitude=-22.5, longitude=-47.0)
    i, j = find_nearest_grid_point(target, lats, lons)
    assert 0 <= i < 50 and 0 <= j < 60
    assert abs(lats[i] - -22.5) < 0.5
    assert abs(lons[j] - -47.0) < 0.5


def test_extract_point_series_2d():
    data = np.arange(20).reshape(4, 5)
    lats = np.linspace(0, 3, 4)
    lons = np.linspace(0, 4, 5)
    target = Coordinate(1.3, 2.7)
    val = extract_point_series(data, lats, lons, target)
    assert np.isfinite(val)


def test_create_grid():
    lats, lons = create_grid(-25, -20, -50, -45, resolution_km=100)
    assert lats[0] <= -25 and lats[-1] >= -20
    assert lons[0] <= -50 and lons[-1] >= -45
    assert len(lats) > 1 and len(lons) > 1


def test_clip_to_bbox():
    lats = np.linspace(-25, -20, 50)
    lons = np.linspace(-50, -45, 60)
    data = np.random.rand(50, 60)
    clats, clons, cdata = clip_to_bbox(lats, lons, data, (-23, -21, -48, -46))
    assert clats.shape[0] == cdata.shape[0]
    assert clons.shape[0] == cdata.shape[1]
    assert len(clats) < 50 and len(clons) < 60


def test_utcnow_is_naive():
    now = utcnow()
    assert now.tzinfo is None


def test_temporal_interpolate():
    times = [datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 2)]
    values = [0.0, 10.0]
    targets = [datetime(2026, 1, 1, 1)]
    result = temporal_interpolate(values, times, targets)
    assert np.allclose(result, [5.0])


def test_resample_temporal():
    times = [datetime(2026, 1, 1, 0) + timedelta(hours=h) for h in range(6)]
    data = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    result, out_times = resample_temporal(data, times, target_step_hours=3, method="mean")
    assert len(result) == len(out_times)


def test_time_weights():
    times = [datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 1), datetime(2026, 1, 1, 3)]
    w = time_weights(times)
    assert len(w) == 3
    assert w[0] == 0.5
    assert w[2] == 1.0
