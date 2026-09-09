"""Tests for the model (ML pipeline) module."""

from __future__ import annotations

import numpy as np

from barograph.model import FeatureSelector, RegressionPipeline


def make_data(n=200):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(n, 4))
    y = 3.0 * X[:, 0] - 2.0 * X[:, 1] + rng.normal(scale=0.1, size=n)
    names = ["a", "b", "c", "d"]
    return X, y, names


def test_linear_pipeline_fits():
    X, y, names = make_data()
    pipe = RegressionPipeline(kind="linear")
    model = pipe.fit(X, y, names)
    preds = model.predict(X)
    assert preds.shape == y.shape
    assert np.corrcoef(preds, y)[0, 1] > 0.99


def test_ridge_evaluate():
    X, y, names = make_data()
    pipe = RegressionPipeline(kind="ridge", alpha=1.0)
    metrics = pipe.fit_predict_evaluate(X, y, X, y, names)
    assert metrics["rmse"] < 1.0


def test_feature_selection_keeps_top():
    X, y, names = make_data()
    sel = FeatureSelector(keep=2).fit(X, y, names)
    assert len(sel.selected_features) == 2
    assert "a" in sel.selected_features  # highest |corr|
    Xs = sel.transform(X, names)
    assert Xs.shape[1] == 2


def test_feature_selection_all():
    X, y, names = make_data()
    sel = FeatureSelector(keep=4).fit(X, y, names)
    assert set(sel.selected_features) == set(names)


def test_unknown_kind_raises():
    X, y, names = make_data()
    with np.testing.assert_raises(ValueError):
        RegressionPipeline(kind="bogus").fit(X, y, names)


def test_pipeline_mismatch_raises():
    X, y, names = make_data(n=200)
    with np.testing.assert_raises(ValueError):
        RegressionPipeline(kind="linear").fit(X, y[:10], names)


def test_save_load_roundtrip(tmp_path):
    X, y, names = make_data()
    model = RegressionPipeline(kind="ridge").fit(X, y, names)
    path = tmp_path / "model.pkl"
    RegressionPipeline.save(model, path)
    loaded = RegressionPipeline.load(path)
    assert loaded.kind == "ridge"
    np.testing.assert_allclose(loaded.predict(X[:5]), model.predict(X[:5]))


def test_forest_pipeline():
    X, y, names = make_data()
    pipe = RegressionPipeline(kind="forest", n_estimators=20)
    model = pipe.fit(X, y, names)
    preds = model.predict(X)
    assert preds.shape == y.shape
