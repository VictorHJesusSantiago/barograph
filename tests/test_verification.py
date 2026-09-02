"""Unit tests for verification metrics."""

import numpy as np

from barograph.verification.brier import (
    brier_decomposition,
    brier_score,
    brier_skill_score,
)
from barograph.verification.crps import crps_ensemble, crps_normal, crps_score
from barograph.verification.reliability import reliability_diagram


def test_brier_score_perfect():
    prob = np.array([0.0, 1.0, 1.0, 0.0])
    obs = np.array([0.0, 1.0, 1.0, 0.0])
    scores = brier_score(prob, obs)
    assert np.allclose(scores, 0.0)


def test_brier_score_imperfect():
    prob = np.array([0.5, 0.5])
    obs = np.array([0.0, 1.0])
    scores = brier_score(prob, obs)
    assert np.allclose(scores, 0.25)


def test_brier_decomp():
    rng = np.random.default_rng(3)
    prob = rng.uniform(0, 1, 1000)
    obs = (rng.uniform(0, 1, 1000) < prob).astype(float)

    decomp = brier_decomposition(prob, obs, n_bins=10)
    assert decomp["brier"] > 0
    assert abs(decomp["reliability"] + decomp["resolution"] - decomp["uncertainty"])
    assert decomp["uncertainty"] > 0


def test_crps_ensemble():
    members = np.array([
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [1.0, 2.0, 3.0, 4.0, 5.0],
    ])
    obs = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
    score = crps_ensemble(members, obs)
    assert np.all(np.isfinite(score))


def test_crps_normal():
    loc = np.array([0.0, 1.0, 2.0])
    scale = np.array([1.0, 1.0, 1.0])
    obs = np.array([0.0, 1.0, 2.0])
    crps_vals = crps_normal(loc, scale, obs)
    # CRPS at the distribution mean with unit std is 2*phi(0) - 1/sqrt(pi)
    expected = 2 / np.sqrt(2 * np.pi) - 1 / np.sqrt(np.pi)
    assert np.allclose(crps_vals, expected, atol=1e-4)


def test_crps_score_ensemble_wrapper():
    members = np.random.randn(20, 100)
    obs = np.random.randn(100)
    val = crps_score(members, obs, method="ensemble")
    assert np.isfinite(val)
    assert val > 0


def test_reliability_diagram():
    rng = np.random.default_rng(5)
    prob = rng.uniform(0, 1, 1000)
    obs = (rng.uniform(0, 1, 1000) < prob).astype(float)

    result = reliability_diagram(prob, obs, n_bins=10)
    assert len(result["forecast_prob"]) == 10
    assert len(result["observed_freq"]) == 10
    assert np.all(result["observed_freq"][~np.isnan(result["observed_freq"])] >= 0)


def test_brier_skill():
    rng = np.random.default_rng(1)
    prob = rng.uniform(0, 1, 500)
    obs = (rng.uniform(0, 1, 500) < 0.3).astype(float)
    skill = brier_skill_score(prob, obs)
    assert np.isfinite(skill)
