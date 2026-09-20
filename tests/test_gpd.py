import numpy as np
import pytest

from barograph.extreme.gpd import (
    GPDDistribution,
    excess_rate,
    fit_gpd,
    return_level,
)


def _sample_exponential(scale, n, seed):
    rng = np.random.default_rng(seed)
    return scale * rng.exponential(size=n)


def test_excess_rate():
    values = np.array([1.0, 8.0, 2.0, 10.0, 3.0])
    assert excess_rate(values, 5.0) == pytest.approx(0.4)


def test_fit_gpd_exponential_shape_near_zero():
    # An exponential distribution has GPD shape xi = 0.
    excess = _sample_exponential(2.0, 4000, seed=1)
    dist = fit_gpd(excess, threshold=0.0)
    assert dist.shape == pytest.approx(0.0, abs=0.1)
    # the GPD scale equals the exponential scale parameter
    assert dist.scale == pytest.approx(2.0, rel=0.15)


def test_fit_gpd_requires_positive_excesses():
    with pytest.raises(ValueError):
        fit_gpd(np.array([0.0, 0.0, 0.0]), threshold=0.0)


def test_excess_quantile_near_probability_one_is_large():
    dist = GPDDistribution(scale=1.0, shape=0.0, threshold=0.0)
    # exponential tail quantile grows without bound near p=1
    q = dist.excess_quantile(np.array([1.0 - 1e-6]))[0]
    assert q > 10.0


def test_return_level_exponential_match():
    # For an exponential tail, the return level x_T with exceedance rate
    # n_year per block is threshold + scale*ln(n_year*T).
    dist = GPDDistribution(scale=2.0, shape=0.0, threshold=10.0, n_year=5.0)
    rl = return_level(dist, np.array([20.0]))
    expected = 10.0 + 2.0 * np.log(5.0 * 20.0)
    assert rl[0] == pytest.approx(expected, rel=1e-6)


def test_return_level_increases_with_period():
    dist = GPDDistribution(scale=1.5, shape=0.2, threshold=5.0, n_year=4.0)
    rl_10 = return_level(dist, np.array([10.0]))
    rl_100 = return_level(dist, np.array([100.0]))
    assert rl_100[0] > rl_10[0]


def test_return_level_rejects_period_below_one():
    dist = GPDDistribution(scale=1.0, shape=0.0, threshold=0.0)
    with pytest.raises(ValueError):
        return_level(dist, np.array([0.5]))


def test_exponential_level_recovered_from_fit():
    # Fit a GPD to a large exponential sample and compare the POT return level
    # to the theoretical exponential level (tolerance absorbs L-moment noise).
    excess = _sample_exponential(3.0, 20000, seed=4)
    dist = fit_gpd(excess, threshold=0.0)
    rl = return_level(
        GPDDistribution(scale=dist.scale, shape=dist.shape, threshold=10.0, n_year=10.0),
        np.array([50.0]),
    )
    theoretical = 10.0 + 3.0 * np.log(500.0)
    assert rl[0] == pytest.approx(theoretical, rel=0.1)


def test_return_level_units_are_threshold_plus_excess():
    dist = GPDDistribution(scale=2.0, shape=0.0, threshold=0.0, n_year=1.0)
    rl = return_level(dist, np.array([2.0]))
    # with n_year=1 the 2-block level is threshold + scale*ln(2)
    assert rl[0] == pytest.approx(2.0 * np.log(2.0), rel=1e-6)
