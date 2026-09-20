"""Integration tests for end-to-end workflows."""

from datetime import datetime

import numpy as np
import pytest

from barograph.alerts import AlertEngine
from barograph.alerts.rules import AlertRule, Operator, Severity
from barograph.core.coordinates import (
    clip_to_bbox,
    create_grid,
    extract_point_series,
    find_nearest_grid_point,
    reproject_field,
)
from barograph.core.models import (
    Coordinate,
    EnsembleForecast,
    GriddedField,
    ModelSource,
    Variable,
)
from barograph.core.temporal import resample_temporal
from barograph.ensemble.pooling import EnsemblePooler
from barograph.ensemble.statistics import EnsembleStatistics
from barograph.postprocessing.quantile_mapping import QuantileMapper
from barograph.verification.metrics import VerificationMetrics


@pytest.fixture
def sample_field():
    lats = np.linspace(-25.0, -20.0, 20)
    lons = np.linspace(-50.0, -45.0, 20)
    data = np.random.default_rng(42).normal(25.0, 5.0, (20, 20))
    return GriddedField(
        data=data.astype(np.float32),
        lats=lats,
        lons=lons,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, 12),
        init_time=datetime(2026, 1, 1, 0),
    )


@pytest.fixture
def sample_ensemble():
    lats = np.linspace(-25.0, -20.0, 10)
    lons = np.linspace(-50.0, -45.0, 10)
    t = datetime(2026, 1, 1, 12)
    rng = np.random.default_rng(42)

    fields = []
    for m in range(5):
        data = rng.normal(25.0 + m * 0.5, 2.0, (10, 10)).astype(np.float32)
        fields.append(
            GriddedField(
                data=data,
                lats=lats,
                lons=lons,
                variable=Variable.TEMPERATURE,
                source=ModelSource.GFS,
                valid_time=t,
                init_time=t,
            )
        )

    return EnsembleForecast(
        members=fields,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        init_time=t,
        valid_time=t,
    )


def test_full_ingest_to_alert_workflow(sample_field):
    field = sample_field

    target = Coordinate(latitude=-22.5, longitude=-47.5)
    i, j = find_nearest_grid_point(target, field.lats, field.lons)
    point_data = extract_point_series(field.data, field.lats, field.lons, target)
    assert point_data.ndim == 0

    assert 0 <= i < field.shape[0]
    assert 0 <= j < field.shape[1]

    engine = AlertEngine(notification_channels=[])
    engine.add_rule(
        AlertRule(
            variable=Variable.TEMPERATURE,
            threshold=30.0,
            operator=Operator.GREATER_OR_EQUAL,
            severity=Severity.WARNING,
        )
    )
    alerts = engine.evaluate_field(field)
    assert isinstance(alerts, list)


def test_ensemble_statistics_pipeline(sample_ensemble):
    stats = EnsembleStatistics()

    mean = stats.ensemble_mean(sample_ensemble)
    assert mean.data.shape == (10, 10)

    spread = stats.ensemble_spread(sample_ensemble)
    assert spread.data.shape == (10, 10)
    assert np.all(spread.data >= 0)

    iqr = stats.interquartile_range(sample_ensemble)
    assert iqr.data.shape == (10, 10)

    prob = stats.probability_above(sample_ensemble, 25.0)
    assert prob.data.shape == (10, 10)
    assert np.all(prob.data >= 0) and np.all(prob.data <= 1)

    obs = np.full((10, 10), 25.0)
    rank = stats.member_rank(sample_ensemble, obs)
    assert rank.shape == (10, 10)


def test_quantile_mapping_correction():
    rng = np.random.default_rng(42)
    forecast = rng.normal(20.0, 3.0, 100).astype(np.float64)
    observation = rng.normal(18.0, 2.5, 100).astype(np.float64)

    qm = QuantileMapper()
    qm.fit(forecast, observation)
    corrected = qm.transform_data(forecast)

    assert corrected.shape == forecast.shape
    bias_before = np.mean(forecast) - np.mean(observation)
    bias_after = np.mean(corrected) - np.mean(observation)
    assert abs(bias_after) <= abs(bias_before) + 0.5


def test_verification_metrics_pipeline():
    rng = np.random.default_rng(42)
    obs = rng.normal(25.0, 2.0, 50)
    pred = obs + rng.normal(0, 1.0, 50)

    metrics = VerificationMetrics()
    mae = metrics.mae(obs, pred)
    rmse = metrics.rmse(obs, pred)
    corr = metrics.correlation(obs, pred)

    assert mae >= 0
    assert rmse >= 0
    assert -1 <= corr <= 1

    all_metrics = metrics.compute_all(obs, pred)
    assert "mae" in all_metrics
    assert "rmse" in all_metrics


def test_reproject_2d():
    lats = np.linspace(-25.0, -20.0, 10)
    lons = np.linspace(-50.0, -45.0, 10)
    data = np.random.default_rng(42).normal(20.0, 2.0, (10, 10))

    dst_lats = np.linspace(-24.0, -21.0, 5)
    dst_lons = np.linspace(-49.0, -46.0, 5)

    result = reproject_field(data, lats, lons, dst_lats, dst_lons)
    assert result.shape == (5, 5)
    assert not np.all(np.isnan(result))


def test_reproject_3d():
    lats = np.linspace(-25.0, -20.0, 10)
    lons = np.linspace(-50.0, -45.0, 10)
    data = np.random.default_rng(42).normal(20.0, 2.0, (3, 10, 10))

    dst_lats = np.linspace(-24.0, -21.0, 5)
    dst_lons = np.linspace(-49.0, -46.0, 5)

    result = reproject_field(data, lats, lons, dst_lats, dst_lons)
    assert result.shape == (3, 5, 5)
    assert not np.all(np.isnan(result))


def test_reproject_4d():
    lats = np.linspace(-25.0, -20.0, 8)
    lons = np.linspace(-50.0, -45.0, 8)
    data = np.random.default_rng(42).normal(20.0, 2.0, (2, 3, 8, 8))

    dst_lats = np.linspace(-24.0, -21.0, 4)
    dst_lons = np.linspace(-49.0, -46.0, 4)

    result = reproject_field(data, lats, lons, dst_lats, dst_lons)
    assert result.shape == (2, 3, 4, 4)


def test_resample_temporal_1d():
    times = [datetime(2026, 1, 1, i) for i in range(12)]
    data = np.arange(12, dtype=np.float64)

    result, new_times = resample_temporal(data, times, target_step_hours=3.0, method="mean")
    assert result.ndim == 1
    assert len(result) > 0
    assert len(result) == len(new_times)
    assert np.all(np.isfinite(result))


def test_resample_temporal_2d():
    times = [datetime(2026, 1, 1, i) for i in range(12)]
    data = np.random.default_rng(42).normal(0, 1, (12, 5, 5))

    result, new_times = resample_temporal(data, times, target_step_hours=3.0, method="mean")
    assert result.ndim == 3
    assert result.shape[0] == len(new_times)
    assert result.shape[1:] == (5, 5)


def test_resample_temporal_3d():
    times = [datetime(2026, 1, 1, i) for i in range(12)]
    data = np.random.default_rng(42).normal(0, 1, (12, 3, 5, 5))

    result, new_times = resample_temporal(data, times, target_step_hours=3.0, method="sum")
    assert result.ndim == 4
    assert result.shape[0] == len(new_times)
    assert result.shape[1:] == (3, 5, 5)


def test_clip_to_bbox():
    lats = np.linspace(-25.0, -20.0, 20)
    lons = np.linspace(-50.0, -45.0, 20)
    data = np.random.default_rng(42).normal(0, 1, (20, 20))

    clipped_lats, clipped_lons, clipped_data = clip_to_bbox(
        lats,
        lons,
        data,
        (-23.0, -21.0, -48.0, -46.0),
    )
    assert len(clipped_lats) < 20
    assert len(clipped_lons) < 20
    assert clipped_data.shape == (len(clipped_lats), len(clipped_lons))


def test_grid_creation():
    lats, lons = create_grid(-25.0, -20.0, -50.0, -45.0, resolution_km=25.0)
    assert len(lats) > 0
    assert len(lons) > 0
    assert lats[0] >= -25.0
    assert lats[-1] <= -20.0 + 1.0


def test_alert_cooldown():
    engine = AlertEngine(cooldown_minutes=60, notification_channels=[])
    engine.add_rule(
        AlertRule(
            variable=Variable.TEMPERATURE,
            threshold=20.0,
            operator=Operator.GREATER_OR_EQUAL,
            severity=Severity.WARNING,
        )
    )

    lats = np.linspace(-25.0, -20.0, 5)
    lons = np.linspace(-50.0, -45.0, 5)
    data = np.full((5, 5), 25.0)
    field = GriddedField(
        data=data,
        lats=lats,
        lons=lons,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, 12),
        init_time=datetime(2026, 1, 1, 0),
    )

    alerts1 = engine.evaluate_field(field)
    assert len(alerts1) > 0

    alerts2 = engine.evaluate_field(field)
    assert len(alerts2) == 0


def test_ensemble_pooler_pipeline():
    rng = np.random.default_rng(42)
    members = rng.normal(25.0, 2.0, (20, 10, 10))

    pooler = EnsemblePooler()
    params = pooler.fit_members(members)

    assert "mean" in params
    assert "std" in params

    quantiles = pooler.quantile_function(params, np.array([0.1, 0.5, 0.9]))
    assert quantiles.shape == (3, 10, 10)

    prob = pooler.probability_exceed(params, 27.0)
    assert prob.shape == (10, 10)
    assert np.all(prob >= 0) and np.all(prob <= 1)
