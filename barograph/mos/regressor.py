"""Model Output Statistics (MOS) regressor."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

from barograph.core.models import PointForecast


class MOSRegressor:
    """MOS regressor wrapping either a linear model or gradient boosting.

    Maps raw NWP predictands (and derived predictors) to calibrated
    point forecasts (temperature, wind, etc.) using historical paired
    model-observation training data.
    """

    def __init__(
        self,
        algorithm: str = "gradient_boosting",
        hyperparameters: dict | None = None,
    ):
        self.algorithm = algorithm
        self.hyperparameters = hyperparameters or {}
        self._model: Any | None = None
        self._feature_names: list[str] | None = None
        self._fitted = False

    def _build_model(self):
        if self.algorithm == "linear":
            from sklearn.linear_model import Ridge

            return Ridge(alpha=self.hyperparameters.get("alpha", 1.0))
        elif self.algorithm == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingRegressor

            return GradientBoostingRegressor(
                n_estimators=self.hyperparameters.get("n_estimators", 200),
                learning_rate=self.hyperparameters.get("learning_rate", 0.05),
                max_depth=self.hyperparameters.get("max_depth", 3),
                random_state=42,
            )
        elif self.algorithm == "random_forest":
            from sklearn.ensemble import RandomForestRegressor

            return RandomForestRegressor(
                n_estimators=self.hyperparameters.get("n_estimators", 300),
                random_state=42,
            )
        else:
            raise ValueError(f"Unknown MOS algorithm: {self.algorithm}")

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> MOSRegressor:
        """Fit the regressor.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Target observations.
            feature_names: Optional labels for each feature.
        """
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)

        if X.ndim != 2:
            raise ValueError(f"X must be 2D, got {X.ndim}D")

        if len(X) != len(y):
            raise ValueError("X and y must have the same number of rows")

        if np.isnan(y).any():
            raise ValueError("Target y contains NaN values")

        self._model = self._build_model()
        if self._model is None:
            raise RuntimeError("Could not build model")
        self._model.fit(X, y)
        self._feature_names = feature_names
        self._fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict calibrated values."""
        if not self._fitted or self._model is None:
            raise RuntimeError("MOSRegressor must be fit before predict.")
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return self._model.predict(X)

    def predict_point_forecast(
        self,
        X: np.ndarray,
        times: list,
        station_id: str | None = None,
    ) -> PointForecast:
        """Predict and wrap results in a PointForecast."""
        preds = self.predict(X)
        return PointForecast(
            coord=None,
            variable=None,
            values=[float(p) for p in preds],
            times=times,
            source=None,
            init_time=times[0] if times else None,
            member_id=None,
            meta={"station_id": station_id, "algorithm": self.algorithm},
        )

    def feature_importance(self) -> np.ndarray | Any | None:
        """Return feature importances if the model supports them."""
        if not self._fitted or self._model is None:
            return None
        if hasattr(self._model, "feature_importances_"):
            return self._model.feature_importances_
        if hasattr(self._model, "coef_"):
            return np.abs(self._model.coef_)
        return None

    def save(self, path: str | Path) -> Path:
        """Save the trained model."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "model": self._model,
                    "feat_names": self._feature_names,
                    "algorithm": self.algorithm,
                },
                f,
            )
        return path

    @classmethod
    def load(cls, path: str | Path) -> MOSRegressor:
        """Load a trained model."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj = cls(algorithm=data["algorithm"])
        obj._model = data["model"]
        obj._feature_names = data["feat_names"]
        obj._fitted = True
        return obj
