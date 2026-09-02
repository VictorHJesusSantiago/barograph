"""Aggregate verification metrics module."""

from __future__ import annotations

import numpy as np

from barograph.verification.brier import brier_score
from barograph.verification.crps import crps_ensemble


class VerificationMetrics:
    """Compute and aggregate standard verification metrics."""

    def __init__(self):
        pass

    @staticmethod
    def mae(obs: np.ndarray, fcst: np.ndarray) -> float:
        return float(np.mean(np.abs(np.asarray(fcst) - np.asarray(obs))))

    @staticmethod
    def rmse(obs: np.ndarray, fcst: np.ndarray) -> float:
        return float(np.sqrt(np.mean((np.asarray(fcst) - np.asarray(obs)) ** 2)))

    @staticmethod
    def bias(obs: np.ndarray, fcst: np.ndarray) -> float:
        return float(np.mean(np.asarray(fcst) - np.asarray(obs)))

    @staticmethod
    def mean_absolute_percentage_error(obs: np.ndarray, fcst: np.ndarray) -> float:
        obs = np.asarray(obs)
        fcst = np.asarray(fcst)
        mask = obs != 0
        if np.sum(mask) == 0:
            return np.nan
        return float(np.mean(np.abs((fcst[mask] - obs[mask]) / obs[mask])))

    @staticmethod
    def correlation(obs: np.ndarray, fcst: np.ndarray) -> float:
        obs = np.asarray(obs)
        fcst = np.asarray(fcst)
        valid = ~(np.isnan(obs) | np.isnan(fcst))
        if valid.sum() < 2:
            return np.nan
        return float(np.corrcoef(obs[valid], fcst[valid])[0, 1])

    @staticmethod
    def heidke_skill_score(
        hits: int, false_alarms: int, misses: int, correct_negatives: int
    ) -> float:
        """Heidke Skill Score."""
        total = hits + false_alarms + misses + correct_negatives
        if total == 0:
            return np.nan

        expected_correct = (
            (hits + misses) * (hits + false_alarms)
            + (correct_negatives + false_alarms) * (correct_negatives + misses)
        ) / total

        observed_correct = hits + correct_negatives
        if total - expected_correct == 0:
            return np.nan
        return (observed_correct - expected_correct) / (total - expected_correct)

    @staticmethod
    def reliability(prob: np.ndarray, obs: np.ndarray, n_bins: int = 10) -> float:
        from barograph.verification.brier import brier_decomposition
        return brier_decomposition(prob, obs, n_bins)["reliability"]

    def compute_all(
        self,
        obs: np.ndarray,
        fcst: np.ndarray,
        prob: np.ndarray | None = None,
        ensemble: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Compute a comprehensive set of metrics."""
        results = {}
        results["mae"] = self.mae(obs, fcst)
        results["rmse"] = self.rmse(obs, fcst)
        results["bias"] = self.bias(obs, fcst)
        results["correlation"] = self.correlation(obs, fcst)

        if prob is not None and len(prob) == len(obs) and np.all((obs == 0) | (obs == 1)):
            results["brier"] = float(np.mean(brier_score(prob, obs)))
            from barograph.verification.brier import brier_decomposition
            results.update(brier_decomposition(prob, obs))

        if ensemble is not None:
            # ensemble may be 2D (n_members, n_samples)
            if np.asarray(ensemble).ndim == 2:
                results["crps"] = float(np.mean(crps_ensemble(ensemble, obs)))
                results["ensemble_mean"] = float(np.mean(np.mean(ensemble, axis=0)))

        return results
