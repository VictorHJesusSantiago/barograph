"""Unit tests for downscaling methods."""

from datetime import datetime

import numpy as np

from barograph.core.coordinates import find_nearest_grid_point, haversine_distance
from barograph.core.models import Coordinate, GriddedField, ModelSource, Variable
from barograph.downscaling.bias_correction import BiasCorrectionDownscaler
from barograph.downscaling.quantile_delta_transform import QDTDownscaler


def make_field(data: np.ndarray, var: Variable = Variable.TEMPERATURE) -> GriddedField:
    lats = np.linspace(-25, -20, data.shape[0])
    lons = np.linspace(-50, -45, data.shape[1])
    t = datetime(2026, 1, 1, 12)
    return GriddedField(
        data=data,
        lats=lats,
        lons=lons,
        variable=var,
        source=ModelSource.GFS,
        valid_time=t,
        init_time=t,
    )


def test_haversine_distance():
    coord1 = Coordinate(0.0, 0.0)
    coord2 = Coordinate(0.0, 1.0)
    dist = haversine_distance(coord1, coord2)
    assert 100.0 < dist < 112.0


def test_find_nearest_grid_point():
    lats = np.linspace(-25, -20, 50)
    lons = np.linspace(-50, -45, 60)
    target = Coordinate(latitude=-22.5, longitude=-47.0)
    i, j = find_nearest_grid_point(target, lats, lons)
    assert 0 <= i < 50
    assert 0 <= j < 60
    assert abs(lats[i] - target.latitude) < 0.5
    assert abs(lons[j] - target.longitude) < 0.5


def test_bias_correction_additive():
    rng = np.random.default_rng(1)
    n = 200
    coarse = [make_field(rng.normal(5, 1, (10, 10))) for _ in range(n)]
    fine = [make_field(rng.normal(8, 1, (10, 10))) for _ in range(n)]

    ds = BiasCorrectionDownscaler(mode="additive").fit(coarse, fine)
    # New forecast sampled from coarse distribution
    new_field = make_field(np.full((10, 10), 5.0))
    corrected = ds.transform(new_field)
    # Corrected center should be near fine mean (8)
    assert abs(corrected.data[5, 5] - 8.0) < 0.3


def test_qdt_downscaling():
    rng = np.random.default_rng(2)
    n = 300
    coarse = [make_field(rng.normal(5, 1, (6, 6))) for _ in range(n)]
    fine = [make_field(rng.normal(8, 2, (6, 6))) for _ in range(n)]

    ds = QDTDownscaler().fit(coarse, fine)

    new_field = make_field(np.full((6, 6), 6.0))
    corrected = ds.transform(new_field)
    # Should be pulled toward the fine distribution (~8)
    assert 6.0 < corrected.data[3, 3] < 10.0


def test_bias_correction_mismatched_counts():
    coarse = [make_field(np.zeros((4, 4))) for _ in range(10)]
    fine = [make_field(np.zeros((4, 4))) for _ in range(20)]

    ds = BiasCorrectionDownscaler()
    try:
        ds.fit(coarse, fine)
        assert False, "Should have raised"
    except ValueError:
        pass
