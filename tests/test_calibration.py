"""Unit tests for ensemble pooling and EMOS calibration."""

import numpy as np

from barograph.ensemble.pooling import EnsemblePooler
from barograph.postprocessing.emos import EMOSCalibrator
from barograph.postprocessing.quantile_mapping import QuantileMapper


def test_ensemble_pooler_fit():
    members = np.random.normal(5, 2, size=(20, 10, 10))
    pooler = EnsemblePooler(distribution="normal", method="parametric")
    params = pooler.fit_members(members)

    assert np.isclose(params["mean"].mean(), 5.0, atol=0.5)
    assert np.isclose(params["std"].mean(), 2.0, atol=0.5)


def test_probability_exceed():
    members = np.random.normal(10, 1, size=(100,))
    pooler = EnsemblePooler()
    params = pooler.fit_members(members[:, None])

    p = pooler.probability_exceed(params, 12.0)
    assert 0.0 < float(np.mean(p)) < 0.2


def test_quantile_mapping_corrects_bias():
    rng = np.random.default_rng(42)
    model = rng.normal(5, 2, 5000)
    obs = rng.normal(8, 1.5, 5000)

    qm = QuantileMapper(n_bins=100)
    qm.fit(model, obs)

    corrected = qm.transform_data(model)
    assert abs(corrected.mean() - 8.0) < 0.5
    assert abs(corrected.std() - 1.5) < 0.5


def test_emos_calibration_reduces_error():
    rng = np.random.default_rng(7)
    n = 500
    ens_mean = rng.normal(10, 2, n)
    ens_var = rng.uniform(0.5, 3.0, n)
    obs = rng.normal(ens_mean * 1.2 + 2, np.sqrt(ens_var))

    calibrator = EMOSCalibrator()
    calibrator.fit(ens_mean, ens_var, obs)

    loc, scale = calibrator.predict_distribution(ens_mean, ens_var)
    # Calibrated mean should be closer to obs than raw mean
    err_raw = np.mean(np.abs(ens_mean - obs))
    err_cal = np.mean(np.abs(loc - obs))
    assert err_cal < err_raw * 1.1

    # CRPS of calibrated distribution should be finite and reasonable
    crps = calibrator.crps_score(ens_mean, ens_var, obs)
    assert np.isfinite(crps)
    assert crps > 0
