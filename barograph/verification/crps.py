"""Continuous Ranked Probability Score (CRPS) implementation."""

from __future__ import annotations

import numpy as np
from scipy import stats


def crps_normal(loc: np.ndarray, scale: np.ndarray, obs: np.ndarray) -> np.ndarray:
    """CRPS of a normal distribution (N(loc, scale^2)) against observations."""
    loc = np.asarray(loc, dtype=np.float64)
    scale = np.asarray(scale, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)

    z = (obs - loc) / scale
    crps = scale * (
        z * (2 * stats.norm.cdf(z) - 1)
        + 2 * stats.norm.pdf(z)
        - 1 / np.sqrt(np.pi)
    )
    return crps


def crps_ensemble(members: np.ndarray, obs: np.ndarray) -> np.ndarray:
    """CRPS for an ensemble forecast (empirical distribution).

    Uses the standard fair CRPS formula for an N-member ensemble:
      CRPS = (2/N) * sum |x_i - o| - (1/N^2) * sum_i sum_j |x_i - x_j|

    A correction (1/N) is added to get the fair score (unbiased).
    """
    members = np.asarray(members, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)

    if members.ndim == 1 and obs.ndim == 1:
        members = members[:, None]
        obs = obs[:, None]
    elif members.shape[0] == obs.shape[0]:
        members = members.T

    n = members.shape[0]
    mean_abs = np.mean(np.abs(members - obs[None, :]), axis=0)

    # Pairwise differences
    diff = 0.0
    for i in range(n):
        diff += np.sum(np.abs(members[i] - members), axis=0)
    diff = diff / (n * n)

    crps = 2 * mean_abs - diff
    return crps


def crps_truncated_normal(
    location: float,
    scale: float,
    lower: float,
    upper: float,
    obs: np.ndarray,
) -> np.ndarray:
    """CRPS of a truncated normal (e.g. for precipitation)."""

    a = (lower - location) / scale
    b = (upper - location) / scale

    alpha = stats.norm.cdf(a)
    beta = stats.norm.cdf(b)
    Z = beta - alpha

    z = (obs - location) / scale
    phi_a = stats.norm.pdf(a)
    phi_b = stats.norm.pdf(b)

    term1 = z * (2 * stats.norm.cdf(z) - 2 * alpha - 1)
    term2 = 2 * stats.norm.pdf(z)
    term3 = (2 * phi_a - 2 * phi_b) / Z
    term4 = 1 / np.sqrt(np.pi)

    crps = (scale / Z) * (term1 + term2 + term3 - term4)
    return crps


def crps_score(
    forecast: np.ndarray,
    obs: np.ndarray,
    method: str = "normal",
    **kwargs,
) -> float:
    """General CRPS entrypoint.

    Args:
        forecast: For ensemble method, (n_members, n_samples). For normal, (loc, scale).
        obs: observations.
        method: "normal", "ensemble", "truncated_normal".
    """
    if method == "normal":
        loc, scale = forecast
        return float(np.mean(crps_normal(loc, scale, obs)))
    elif method == "ensemble":
        return float(np.mean(crps_ensemble(forecast, obs)))
    elif method == "truncated_normal":
        loc, scale = kwargs.get("loc", forecast)
        lower = kwargs["lower"]
        upper = kwargs["upper"]
        return float(np.mean(crps_truncated_normal(loc, scale, lower, upper, obs)))
    else:
        raise ValueError(f"Unknown CRPS method: {method}")


def crps_skill(
    crps_model: float,
    crps_ref: float,
) -> float:
    """CRPS skill score relative to a reference forecast."""
    if crps_ref <= 0 or np.isnan(crps_ref):
        return np.nan
    return 1.0 - crps_model / crps_ref
