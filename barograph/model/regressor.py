"""Estimator-based regression pipelines with feature selection.

These utilities build on :mod:`scikit-learn` to provide a small, reusable
pipeline for training, evaluating, and persisting forecast models (e.g. MOS
station models) without tying callers to a particular estimator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

try:  # scikit-learn is an optional heavy dependency
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression, Ridge

    _HAVE_SKLEARN = True
except Exception:  # pragma: no cover - reduced environment
    _HAVE_SKLEARN = False

    class LinearRegression:  # type: ignore[no-redef]
        pass

    class Ridge:  # type: ignore[no-redef]
        pass

    class RandomForestRegressor:  # type: ignore[no-redef]
        pass


def _make_estimator(kind: str, **kwargs: Any) -> Any:
    """Instantiate a supported estimator, raising on unknown kinds."""
    if not _HAVE_SKLEARN:
        raise RuntimeError("scikit-learn is required for model pipelines")
    if kind == "linear":
        return LinearRegression()
    if kind == "ridge":
        return Ridge(alpha=kwargs.get("alpha", 1.0))
    if kind == "forest":
        return RandomForestRegressor(
            n_estimators=kwargs.get("n_estimators", 100),
            random_state=kwargs.get("random_state", 0),
            max_depth=kwargs.get("max_depth"),
        )
    raise ValueError(f"Unsupported estimator kind: {kind!r}")


@dataclass
class FeatureSelector:
    """Select top-*k* features by absolute correlation with the target.

    Args:
        keep: Number of features to retain.
    """

    keep: int = 8
    _selected: list[str] = field(default_factory=list, repr=False)

    def fit(
        self, X: np.ndarray, y: np.ndarray, feature_names: list[str]
    ) -> FeatureSelector:
        """Rank features by absolute correlation and store the top *keep*."""
        n = max(self.keep, 1)
        if X.shape[1] == 0:
            self._selected = feature_names[:n]
            return self
        scores = np.abs(np.corrcoef(X, y, rowvar=False)[:-1, -1])
        scores = np.nan_to_num(scores, nan=0.0)
        idx = np.argsort(-scores)[: min(n, X.shape[1])]
        self._selected = [feature_names[i] for i in idx]
        return self

    def transform(self, X: np.ndarray, feature_names: list[str]) -> np.ndarray:
        """Return only the columns named in ``_selected``."""
        if not self._selected:
            return X
        lookup = {name: i for i, name in enumerate(feature_names)}
        cols = [lookup[name] for name in self._selected if name in lookup]
        return X[:, cols] if cols else X

    @property
    def selected_features(self) -> list[str]:
        return list(self._selected)


@dataclass
class RegressionModel:
    """A fitted regression model with its metadata."""

    estimator: Any
    kind: str
    feature_names: list[str]
    selector: FeatureSelector | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict on raw feature matrix *X* (selector applied internally)."""
        if self.selector is not None:
            X = self.selector.transform(X, self.feature_names)
        return np.asarray(self.estimator.predict(X)).ravel()


class RegressionPipeline:
    """Train, evaluate and persist a regression model.

    Args:
        kind: One of ``"linear"``, ``"ridge"``, ``"forest"``.
        feature_selection: Retain this many top features (0 to disable).
        kwargs: Estimator parameters passed through (e.g. ``alpha``, ``n_estimators``).

    """

    def __init__(
        self,
        kind: str = "ridge",
        feature_selection: int = 0,
        **kwargs: Any,
    ) -> None:
        self.kind = kind
        self.kwargs = kwargs
        self.feature_selection = feature_selection
        self.selector = (
            FeatureSelector(keep=feature_selection) if feature_selection else None
        )
        self.model: RegressionModel | None = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
    ) -> RegressionModel:
        """Fit the pipeline and return a fitted :class:`RegressionModel`."""
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of rows")
        if self.selector is not None:
            self.selector.fit(X, y, feature_names)
            Xs = self.selector.transform(X, feature_names)
        else:
            Xs = X
        estimator = _make_estimator(self.kind, **self.kwargs)
        estimator.fit(Xs, y)
        self.model = RegressionModel(
            estimator=estimator,
            kind=self.kind,
            feature_names=list(feature_names),
            selector=self.selector,
            params={"kind": self.kind, **self.kwargs},
        )
        return self.model

    def fit_predict_evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: list[str],
    ) -> dict[str, float]:
        """Fit then score on a held-out test set.

        Returns:
            A dict with ``mae`` and ``rmse``.
        """
        self.fit(X, y, feature_names)
        preds = self.model.predict(X_test) if self.model else np.array([])
        yt = np.asarray(y_test, dtype=np.float64)
        mae = float(np.mean(np.abs(preds - yt)))
        rmse = float(np.sqrt(np.mean((preds - yt) ** 2)))
        return {"mae": mae, "rmse": rmse}

    @staticmethod
    def save(model: RegressionModel, path: str | Path) -> None:
        """Persist a fitted model to disk (joblib-style pickle)."""
        import pickle

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": model}, f)

    @staticmethod
    def load(path: str | Path) -> RegressionModel:
        """Load a model saved by :meth:`save`."""
        import pickle

        with open(path, "rb") as f:
            payload = pickle.load(f)
        return payload["model"]
