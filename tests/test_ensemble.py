"""Unit tests for ensemble statistics and pooling."""

from datetime import datetime

import numpy as np

from barograph.core.models import EnsembleForecast, GriddedField, ModelSource, Variable
from barograph.ensemble import EnsemblePooler, EnsembleStatistics


def make_ensemble(n_members=20, ny=8, nx=10, mean=100, std=10, seed=0):
    rng = np.random.default_rng(seed)
    lats = np.linspace(-25, -20, ny)
    lons = np.linspace(-50, -45, nx)
    t = datetime(2026, 1, 1, 12)
    members = []
    for _ in range(n_members):
        data = mean + std * rng.standard_normal((ny, nx))
        members.append(GriddedField(
            data=data, lats=lats, lons=lons,
            variable=Variable.PRECIPITATION, source=ModelSource.GFS,
            valid_time=t, init_time=t,
        ))
    return EnsembleForecast(
        members=members, variable=Variable.PRECIPITATION, source=ModelSource.GFS,
        init_time=t, valid_time=t,
    )


def test_ensemble_mean_spread():
    ens = make_ensemble()
    mean = ens.ensemble_mean
    spread = ens.ensemble_spread
    assert np.isclose(mean.data.mean(), 100, atol=2)
    assert np.isclose(spread.data.mean(), 10, atol=1)


def test_ensemble_quantiles():
    ens = make_ensemble()
    p90 = EnsembleStatistics.ensemble_percentile(ens, 90)
    p10 = EnsembleStatistics.ensemble_percentile(ens, 10)
    assert np.all(p90.data > p10.data)


def test_probability_above():
    ens = make_ensemble(mean=5, std=1)
    p = EnsembleStatistics.probability_above(ens, 6.5)
    assert 0.0 < p.data.mean() < 1.0


def test_exceedance_fraction():
    ens = make_ensemble(mean=5, std=1)
    frac = EnsembleStatistics.exceedance_fraction(ens, 5)
    assert 0 <= frac <= 1


def test_member_rank():
    ens = make_ensemble(n_members=50)
    ens_stats = EnsembleStatistics()
    rank = ens_stats.member_rank(ens, np.full((8, 10), 100.0))
    assert 0 <= rank.max() <= 50


def test_ensemble_pooler_quantiles():
    members = np.random.default_rng(3).normal(10, 2, (30, 50))
    pooler = EnsemblePooler(distribution="normal", method="parametric")
    params = pooler.fit_members(members)

    q = pooler.quantile_function(params, np.array([0.5]))
    # Median ~ 10
    assert np.isclose(q[0].mean(), 10, atol=0.5)


def test_ensemble_pooler_cdf():
    members = np.random.default_rng(4).normal(10, 2, (30, 500))
    pooler = EnsemblePooler(distribution="normal")
    params = pooler.fit_members(members)
    cdf_at_10 = pooler.cdf(params, np.array(10.0))
    assert 0.45 < cdf_at_10.mean() < 0.55


def test_probability_between():
    members = np.random.default_rng(5).normal(10, 2, (50, 100))
    pooler = EnsemblePooler()
    params = pooler.fit_members(members)
    p = pooler.probability_between(params, 8, 12)
    assert 0.6 < p.mean() < 0.8
