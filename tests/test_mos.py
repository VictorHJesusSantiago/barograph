"""Unit tests for MOS regressor and trainer."""

import numpy as np
import pytest
from sklearn.datasets import make_regression

from barograph.mos.regressor import MOSRegressor


def test_mos_regressor_fit_predict():
    X, y = make_regression(n_samples=300, n_features=5, noise=0.1, random_state=42)
    reg = MOSRegressor(algorithm="gradient_boosting")
    reg.fit(X, y)
    preds = reg.predict(X)
    assert np.all(np.isfinite(preds))
    assert abs(np.mean(preds) - np.mean(y)) < 5.0


def test_mos_linear():
    X, y = make_regression(n_samples=200, n_features=3, random_state=1)
    reg = MOSRegressor(algorithm="linear")
    reg.fit(X, y)
    preds = reg.predict(X)
    assert np.all(np.isfinite(preds))


def test_mos_requires_fit():
    reg = MOSRegressor()
    with pytest.raises(RuntimeError):
        reg.predict(np.zeros((3, 3)))


def test_mos_feature_importance():
    X, y = make_regression(n_samples=100, n_features=4, random_state=5)
    reg = MOSRegressor(algorithm="linear")
    reg.fit(X, y)
    importance = reg.feature_importance()
    assert importance is not None
    assert importance.shape == (4,)


def test_mos_save_load(tmp_path):
    X, y = make_regression(n_samples=100, n_features=4, random_state=9)
    reg = MOSRegressor(algorithm="linear")
    reg.fit(X, y)
    path = reg.save(tmp_path / "model.pkl")
    loaded = MOSRegressor.load(path)
    preds = loaded.predict(X[:5])
    assert np.all(np.isfinite(preds))
