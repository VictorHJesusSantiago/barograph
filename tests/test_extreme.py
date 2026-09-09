from datetime import datetime

import numpy as np
import pytest

from barograph.extreme.gev import (
    GEVDistribution,
    fit_gev,
    gevcdf,
    return_level,
    return_period,
)
from barograph.extreme.peak import (
    annual_maxima,
    block_maxima,
    peak_over_threshold,
)


def test_block_maxima():
    values = np.array([1.0, 9.0, 2.0, 8.0, 3.0, 7.0, 4.0, 0.0])
    maxima = block_maxima(values, 2)
    assert maxima.tolist() == [9.0, 8.0, 7.0, 4.0]


def test_block_maxima_partial_block_dropped():
    values = np.arange(5, dtype=float)
    maxima = block_maxima(values, 2)
    assert maxima.tolist() == [1.0, 3.0]


def test_annual_maxima():
    times = [
        datetime(2020, 1, 1),
        datetime(2020, 6, 1),
        datetime(2021, 3, 1),
        datetime(2021, 9, 1),
    ]
    values = np.array([5.0, 9.0, 2.0, 7.0])
    assert sorted(annual_maxima(values, times).tolist()) == [7.0, 9.0]


def test_peak_over_threshold():
    values = np.array([1.0, 6.0, 3.0, 9.0, 2.0])
    excess = peak_over_threshold(values, 5.0)
    assert sorted(excess.tolist()) == [1.0, 4.0]


def test_gevcdf_gumbel_known_values():
    # GEV with shape 0 is the Gumbel CDF exp(-exp(-z))
    cdf = gevcdf(np.array([0.0]), 0.0, 1.0, 0.0)
    assert cdf[0] == pytest.approx(np.exp(-1.0), rel=1e-9)


def test_gev_cdf_at_loc_is_euler():
    cdf = gevcdf(np.array([10.0]), 10.0, 2.0, 0.3)
    # CDF at the location is exp(-1) regardless of shape/scale
    assert cdf[0] == pytest.approx(np.exp(-1.0), rel=1e-6)


def test_return_level_known_distribution():
    # For a Gumbel distribution loc=0, scale=1, the 2-block return level solves
    # exp(-exp(-z)) = 0.5 -> z = -ln(ln(2))
    dist = GEVDistribution(loc=0.0, scale=1.0, shape=0.0)
    rl = return_level(dist, np.array([2.0]))
    assert rl[0] == pytest.approx(-np.log(np.log(2.0)), rel=1e-6)


def test_return_level_inverse_of_return_period():
    dist = GEVDistribution(loc=5.0, scale=2.0, shape=0.1)
    rl = return_level(dist, np.array([50.0]))
    rp = return_period(dist, rl)
    assert rp[0] == pytest.approx(50.0, rel=1e-3)


def test_fit_gev_reasonable_parameters():
    rng = np.random.default_rng(42)
    # Draw from a known Gumbel loc=10 scale=3 via inverse transform
    u = rng.random(5000)
    samples = 10.0 - 3.0 * np.log(-np.log(u))
    fit = fit_gev(samples)
    # L-moment fit should approximate the generating parameters
    assert fit.distribution.loc == pytest.approx(10.0, abs=0.5)
    assert fit.distribution.scale == pytest.approx(3.0, abs=0.4)
    assert fit.distribution.shape == pytest.approx(0.0, abs=0.15)
    assert fit.n_blocks == 5000


def test_fit_gev_returns_level_monotonic():
    rng = np.random.default_rng(7)
    u = rng.random(4000)
    samples = 10.0 - 2.0 * np.log(-np.log(u))
    fit = fit_gev(samples)
    rl_10 = fit.return_level(np.array([10.0]))
    rl_100 = fit.return_level(np.array([100.0]))
    assert rl_100[0] > rl_10[0]


def test_fit_gev_requires_minimum_samples():
    with pytest.raises(ValueError):
        fit_gev(np.array([1.0, 2.0]))


def test_annual_maxima_feeds_gev():
    times = []
    values = []
    rng = np.random.default_rng(3)
    for year in range(2010, 2022):
        u = rng.random(10)
        extreme = 20.0 - 4.0 * np.log(-np.log(u)).max()
        times.append(datetime(year, 7, 1))
        values.append(extreme)
    mx = annual_maxima(np.array(values), times)
    fit = fit_gev(mx)
    assert fit.n_blocks == 12
    rl = fit.return_level(np.array([10.0]))
    assert np.isfinite(rl[0])
