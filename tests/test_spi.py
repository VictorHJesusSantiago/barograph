import numpy as np
import pytest

from barograph.indices.spi import (
    classify_drought,
    compute_spi,
    compute_spi_series,
)


def test_spi_near_normal_for_constant_series():
    # A perfectly constant series has no deviation from the climatology.
    result = compute_spi(np.full(60, 50.0))
    assert np.all(np.abs(result) < 1e-12)


def test_spi_wet_samples_positive():
    # Samples far above the bulk of the distribution get a positive index.
    rng = np.random.default_rng(1)
    base = rng.uniform(0.1, 0.9, 80)
    mixed = np.concatenate([base, [30.0, 40.0, 60.0]])
    spi = compute_spi(mixed)
    # the last three large spikes index as wet (positive)
    assert np.all(spi[-3:] > 0.0)


def test_spi_dry_samples_negative():
    # Samples far below the bulk of the distribution get a negative index.
    rng = np.random.default_rng(2)
    low = rng.uniform(0.0, 0.5, 20)
    wet = rng.uniform(4.0, 8.0, 80)
    spi = compute_spi(np.concatenate([low, wet]))
    # the twenty dry samples index as negative (a dry spell)
    assert np.all(spi[:20] < 0.0)


def test_spi_ordering_preserved():
    rng = np.random.default_rng(3)
    base = rng.uniform(1.0, 2.0, 50)
    spi = compute_spi(np.concatenate([base, [10.0], [0.5]]))
    # 10.0 is well above the median -> positive; 0.5 well below -> negative
    assert spi[-2] > 1.0
    assert spi[-1] < -1.0


def test_spi_too_few_samples():
    with pytest.raises(ValueError):
        compute_spi(np.array([1.0, 2.0]))


def test_classify_drought_categories():
    assert classify_drought(2.5) == "extremely wet"
    assert classify_drought(1.7) == "severely wet"
    assert classify_drought(1.2) == "moderately wet"
    assert classify_drought(0.3) == "near normal"
    assert classify_drought(-0.5) == "near normal"
    assert classify_drought(-1.2) == "moderately dry"
    assert classify_drought(-1.8) == "severely dry"
    assert classify_drought(-2.3) == "extremely dry"


def test_compute_spi_series_rolling():
    # Uniform precipitation over a rolling window stays near normal.
    rng = np.random.default_rng(4)
    precip = rng.uniform(1.0, 2.0, 120)
    series = compute_spi_series(precip, 4)
    assert series.shape == (120,)
    # the first window-1 entries are NaN (incomplete window)
    assert np.all(np.isnan(series[:3]))
    # every complete window value is finite
    assert np.all(np.isfinite(series[3:]))


def test_compute_spi_series_short():
    assert np.all(np.isnan(compute_spi_series(np.array([1.0, 2.0]), 10)))


def test_compute_spi_series_constant_returns_zeros():
    precip = np.full(50, 3.0)
    series = compute_spi_series(precip, 4)
    assert np.all(series[3:] == pytest.approx(0.0, abs=1e-9))
