"""Reliability diagrams."""

from __future__ import annotations

import numpy as np


def reliability_diagram(
    prob: np.ndarray,
    obs: np.ndarray,
    n_bins: int = 10,
    return_hist: bool = True,
):
    """Compute reliability diagram data for probabilistic forecasts.

    Args:
        prob: Forecast probabilities (n_samples,).
        obs: Binary observations (0/1).
        n_bins: Number of probability bins.
        return_hist: Whether to also return sample counts per bin.

    Returns:
        dict with forecast_prob (bin center), observed_freq, and optional hist.
    """
    prob = np.asarray(prob, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)

    bins = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.digitize(prob, bins[1:-1])

    forecast_prob = []
    observed_freq = []
    hist = []

    for k in range(1, n_bins + 1):
        mask = bin_idx == k
        n_k = int(np.sum(mask))
        if n_k == 0:
            forecast_prob.append(bins[k - 1] + (bins[k] - bins[k - 1]) / 2)
            observed_freq.append(np.nan)
        else:
            forecast_prob.append(float(np.mean(prob[mask])))
            observed_freq.append(float(np.mean(obs[mask])))
        hist.append(n_k)

    result = {
        "forecast_prob": np.array(forecast_prob),
        "observed_freq": np.array(observed_freq),
    }
    if return_hist:
        result["hist"] = np.array(hist)

    return result


def reliability_index(prob: np.ndarray, obs: np.ndarray, n_bins: int = 10) -> float:
    """Reliability index (mean squared reliability component)."""
    decomp = _brier_components(prob, obs, n_bins)
    return decomp["reliability"]


def accuracy_curve(prob: np.ndarray, obs: np.ndarray, n_bins: int = 10):
    """Sharpness vs calibration accuracy curve data."""
    prob = np.asarray(prob, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)

    bins = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.digitize(prob, bins[1:-1])

    freq = []
    for k in range(1, n_bins + 1):
        mask = bin_idx == k
        obs_k = obs[mask]
        if len(obs_k) > 0:
            freq.append(float(np.mean(obs_k)))
        else:
            freq.append(np.nan)

    return {
        "bin_prob": (bins[1:] + bins[:-1]) / 2,
        "obs_frequency": np.array(freq),
    }


def _brier_components(prob: np.ndarray, obs: np.ndarray, n_bins: int) -> dict[str, float]:
    """Internal helper computing Brier decomposition components."""
    from barograph.verification.brier import brier_decomposition
    return brier_decomposition(prob, obs, n_bins)
