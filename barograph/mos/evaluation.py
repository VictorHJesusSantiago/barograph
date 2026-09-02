"""MOS evaluation metrics and cross-validation helpers."""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import KFold

from barograph.mos.regressor import MOSRegressor


def cross_validate_mos(
    X: np.ndarray,
    y: np.ndarray,
    algorithm: str = "gradient_boosting",
    n_folds: int = 5,
    hyperparameters: dict | None = None,
    random_state: int = 42,
) -> dict[str, float]:
    """K-fold cross-validation and aggregate skill scores.

    Returns MAE, RMSE, BIAS, and Pearson correlation of out-of-fold predictions.
    """
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    preds = np.empty_like(y, dtype=np.float64)
    preds[:] = np.nan

    for train_idx, test_idx in kf.split(X):
        reg = MOSRegressor(algorithm=algorithm, hyperparameters=hyperparameters)
        reg.fit(X[train_idx], y[train_idx])
        preds[test_idx] = reg.predict(X[test_idx])

    valid = ~np.isnan(preds)
    preds = preds[valid]
    y_valid = y[valid]

    mae = float(np.mean(np.abs(preds - y_valid)))
    rmse = float(np.sqrt(np.mean((preds - y_valid) ** 2)))
    bias = float(np.mean(preds - y_valid))
    corr = float(np.corrcoef(preds, y_valid)[0, 1])

    return {
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "correlation": corr,
        "n_samples": int(len(y_valid)),
    }


def skill_vs_reference(
    preds: np.ndarray,
    reference: np.ndarray,
    obs: np.ndarray,
) -> dict[str, float]:
    """Skill scores relative to a reference forecast (e.g. climatology).

    Returns skill of MSE and MAE relative to the reference.
    """
    model_mse = np.mean((preds - obs) ** 2)
    ref_mse = np.mean((reference - obs) ** 2)
    model_mae = np.mean(np.abs(preds - obs))
    ref_mae = np.mean(np.abs(reference - obs))

    skill_mse = 1.0 - model_mse / ref_mse if ref_mse > 0 else np.nan
    skill_mae = 1.0 - model_mae / ref_mae if ref_mae > 0 else np.nan

    return {"skill_mse": float(skill_mse), "skill_mae": float(skill_mae)}


def mse_reduction(
    preds: np.ndarray,
    reference: np.ndarray,
    obs: np.ndarray,
) -> float:
    """MSE reduction of `preds` relative to `reference`, in percent."""
    model_mse = np.mean((preds - obs) ** 2)
    ref_mse = np.mean((reference - obs) ** 2)
    if ref_mse <= 0:
        return 0.0
    return float(100.0 * (1.0 - model_mse / ref_mse))
