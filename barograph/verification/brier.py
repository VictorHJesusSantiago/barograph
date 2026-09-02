"""Brier score and Brier skill score."""

from __future__ import annotations

import numpy as np


def brier_score(prob: np.ndarray, obs: np.ndarray) -> np.ndarray:
    """Brier score for probabilistic forecasts of a binary event.

    Args:
        prob: Forecast probability of the event (n_samples,).
        obs: Binary occurrence (1 if event occurred, else 0).

    Returns:
        Per-sample Brier score.
    """
    prob = np.asarray(prob, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)

    if np.any((obs != 0) & (obs != 1)):
        raise ValueError("obs must contain only binary values 0/1")

    return (prob - obs) ** 2


def brier_decomposition(prob: np.ndarray, obs: np.ndarray, n_bins: int = 10):
    """Decompose Brier score into Reliability, Resolution, and Uncertainty.

    Returns dict with keys brier, reliability, resolution, uncertainty.
    """
    prob = np.asarray(prob, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)

    bins = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.digitize(prob, bins[1:-1])

    o_bar = float(np.mean(obs))
    uncertainty = o_bar * (1 - o_bar)

    reliability = 0.0
    resolution = 0.0
    for k in range(1, n_bins + 1):
        mask = bin_idx == k
        n_k = np.sum(mask)
        if n_k == 0:
            continue
        prob_k = np.mean(prob[mask])
        obs_k = np.mean(obs[mask])
        reliability += n_k / len(prob) * (prob_k - obs_k) ** 2
        resolution += n_k / len(prob) * (obs_k - o_bar) ** 2

    return {
        "brier": float(np.mean(brier_score(prob, obs))),
        "reliability": float(reliability),
        "resolution": float(resolution),
        "uncertainty": float(uncertainty),
    }


def brier_skill_score(prob: np.ndarray, obs: np.ndarray, clim_prob: float | None = None) -> float:
    """Brier skill score based on reference climatology probability."""
    brier = float(np.mean(brier_score(prob, obs)))

    if clim_prob is None:
        clim_prob = float(np.mean(obs))
    ref_brier = clim_prob * (1 - clim_prob)

    if ref_brier <= 0:
        return np.nan
    return 1.0 - brier / ref_brier
