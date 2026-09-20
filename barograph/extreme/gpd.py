"""Generalized Pareto Distribution (GPD) for peak-over-threshold extremes.

By the Pickands-Balkema-de Haan theorem, the distribution of excesses above a
high threshold converges to a Generalized Pareto Distribution. A Poisson point
process model links the exceedance rate to return levels, giving a coherent
Peaks-Over-Threshold (POT) estimator of extreme quantiles.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GPDDistribution:
    """A fitted Generalized Pareto distribution for excesses.

    Args:
        scale: Scale parameter (sigma), strictly positive.
        shape: Shape parameter (xi).
        threshold: The level above which excesses were sampled.
        n_year: Expected number of excesses per block (year), for return levels.
    """

    scale: float
    shape: float
    threshold: float
    n_year: float = 1.0

    def excess_quantile(self, p: np.ndarray) -> np.ndarray:
        """Return the excess quantile for non-exceedance probability *p*."""
        p = np.asarray(p, dtype=np.float64)
        xi = self.shape
        if abs(xi) < 1e-12:
            return self.scale * np.log(1.0 / (1.0 - np.clip(p, 0.0, 1 - 1e-9)))
        return self.scale / xi * ((1.0 - np.clip(p, 0.0, 1 - 1e-9)) ** (-xi) - 1.0)

    def return_level(self, period: np.ndarray) -> np.ndarray:
        """Return level for an average return period (blocks)."""
        return return_level(self, period)


def fit_gpd(excesses: np.ndarray, threshold: float) -> GPDDistribution:
    """Fit a GPD to the excesses above *threshold* via probability-weighted moments.

    Uses the peak-over-threshold method: the excesses are the positive
    deviations above the threshold (see :func:`barograph.extreme.peak.
    peak_over_threshold`). Parameter estimates are obtained robustly with
    probability-weighted moments, avoiding iterative optimisation.

    Args:
        excesses: Positive excesses above the threshold.
        threshold: The applied threshold level.

    Returns:
        A fitted :class:`GPDDistribution`.

    Raises:
        ValueError: If fewer than 3 positive excesses are supplied.
    """
    values = np.asarray(excesses, dtype=np.float64)
    values = values[values > 0]
    if values.size < 3:
        raise ValueError("At least 3 positive excesses are required")
    n = values.size
    s = np.sort(values)
    # probability weighted moments (unbiased plotting positions)
    j = np.arange(1, n + 1)
    b0 = s.mean()
    b1 = np.mean(s * (j - 1.0) / (n - 1.0))
    b2 = np.mean(s * (j - 1.0) * (j - 2.0) / ((n - 1.0) * (n - 2.0))) if n > 2 else b1
    # L-moments
    lam2 = 2.0 * b1 - b0
    lam3 = 6.0 * b2 - 6.0 * b1 + b0
    if abs(lam2) < 1e-12:
        return GPDDistribution(scale=0.0, shape=0.0, threshold=threshold)
    tau3 = lam3 / lam2
    denom = 1.0 - tau3
    if abs(denom) < 1e-12 or not np.isfinite(tau3):
        return GPDDistribution(scale=lam2, shape=0.0, threshold=threshold)
    shape = (3.0 * tau3 - 1.0) / denom
    scale = lam2 * (1.0 - shape) * (2.0 - shape)
    if not np.isfinite(scale) or scale <= 0:
        return GPDDistribution(scale=lam2, shape=0.0, threshold=threshold)
    return GPDDistribution(scale=float(scale), shape=float(shape), threshold=float(threshold))


def return_level(dist: GPDDistribution, period: np.ndarray) -> np.ndarray:
    """Return level for an average return period in blocks.

    Uses the Poisson process model: the excess quantile at non-exceedance
    probability ``1 - 1/(n_year * period)`` is added to the threshold.
    """
    period = np.asarray(period, dtype=np.float64)
    if np.any(period < 1.0):
        raise ValueError("Return period must be at least 1")
    p = 1.0 - 1.0 / (dist.n_year * period)
    p = np.clip(p, 0.0, 1 - 1e-9)
    return dist.threshold + dist.excess_quantile(p)


def excess_rate(values: np.ndarray, threshold: float) -> float:
    """Empirical exceedance rate (excesses per sample) above *threshold*."""
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(values)
    if not np.any(valid):
        return 0.0
    return float(np.mean(values[valid] > threshold))


__all__ = ["GPDDistribution", "fit_gpd", "return_level", "excess_rate"]
