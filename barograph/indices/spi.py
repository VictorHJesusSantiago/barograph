"""Standardized Precipitation Index (SPI).

The SPI (McKee et al. 1993) measures how much precipitation at a given
accumulation scale deviates from the climatological expectation, expressed in
standard deviations of a fitted Gamma distribution transformed to the standard
normal distribution. Positive values indicate wetter-than-normal conditions,
negative values drought; the index is unitless and spatially comparable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SPIResult:
    """Result of a single SPI computation.

    Args:
        precip: The accumulation of interest (mm).
        spi: The standardized precipitation index value.
        class_label: Drought classification of the value.
    """

    precip: float
    spi: float
    class_label: str


def _fit_gamma_alpha_beta(precip: np.ndarray) -> tuple[float, float]:
    """Fit a two-parameter Gamma distribution to positive precipitation.

    Uses the maximum-likelihood estimator of Greenwood and Durand (1960):
    with A = log(xbar) - mean(log x), the shape is alpha = (1 + sqrt(1 + 4A/3))
    / (4A) and the scale is beta = xbar / alpha. Samples equal to zero are
    excluded from the fit; their probability mass is accounted for separately
    via the empirical zero frequency.
    """
    values = np.asarray(precip, dtype=np.float64)
    positive = values[values > 0]
    if positive.size < 3:
        raise ValueError("Need at least 3 positive samples to fit the Gamma")
    mean = float(np.mean(positive))
    ln_mean = float(np.mean(np.log(positive)))
    a0 = np.log(mean) - ln_mean
    if a0 <= 1e-9:
        raise ValueError("Gamma shape estimator requires positive A")
    alpha = (1.0 + np.sqrt(1.0 + 4.0 * a0 / 3.0)) / (4.0 * a0)
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("Fitted Gamma shape parameter is not positive")
    beta = mean / alpha
    return float(alpha), float(beta)


def _gamma_cdf_ppf(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """Cumulative distribution function of Gamma(a, b) at *x*."""
    try:
        import scipy.special  # type: ignore

        g = scipy.special.gammainc(a, x / b)
        return np.clip(g, 0.0, 1.0)
    except Exception:  # pragma: no cover - scipy is optional
        return _gamma_cdf_lanczos(x, a, b)


def _gamma_cdf_lanczos(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """Fallback Gamma CDF via a series expansion of the lower incomplete gamma."""
    x = np.asarray(x, dtype=np.float64)
    out = np.empty_like(x)
    for i, xi in enumerate(x):
        if xi <= 0:
            out[i] = 0.0
            continue
        out[i] = _incomplete_gamma_series(a, xi / b)
    return np.clip(out, 0.0, 1.0)


def _incomplete_gamma_series(a: float, x: float) -> float:
    """Regularized lower incomplete gamma via a truncated series."""
    if x <= 0:
        return 0.0
    ln_gamma = _approx_gammaln(a)
    term = a * np.log(x) - x - ln_gamma
    total = np.exp(term)
    for i in range(1, 300):
        term = term + np.log(x / (a + i))
        acc_i = np.exp(term)
        total += acc_i
        if abs(acc_i) < 1e-12 * abs(total):
            break
    return float(total)


def _approx_gammaln(z: float) -> float:
    """Lanczos approximation of ln(Gamma(z))."""
    try:
        import scipy.special  # type: ignore

        return float(scipy.special.gammaln(z))
    except Exception:
        pass
    g = 7
    coeff = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7,
    ]
    if z < 0.5:
        return np.log(np.pi) - np.log(np.sin(np.pi * z)) - _approx_gammaln(1.0 - z)
    z -= 1.0
    x = coeff[0]
    for i in range(1, g + 2):
        x += coeff[i] / (z + i)
    t = z + g + 0.5
    return np.float64(0.5 * np.log(2 * np.pi) + (z + 0.5) * np.log(t) - t + np.log(x))


def _norm_ppf(p: np.ndarray) -> np.ndarray:
    """Quantile function of the standard normal (Acklam approximation)."""
    p = np.asarray(p, dtype=np.float64)
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    plow = 0.02425
    phigh = 1 - plow
    out = np.empty_like(p)
    lo = p < plow
    hi = p > phigh
    mid = ~(lo | hi)
    pm = p[mid]
    q = pm - 0.5
    r = q * q
    out[mid] = (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )
    pl = p[lo]
    rl = np.sqrt(-2.0 * np.log(pl))
    out[lo] = (((((c[0] * rl + c[1]) * rl + c[2]) * rl + c[3]) * rl + c[4]) * rl + c[5]) / (
        (((d[0] * rl + d[1]) * rl + d[2]) * rl + d[3]) * rl + 1.0
    )
    ph = p[hi]
    rh = np.sqrt(-2.0 * np.log(1.0 - ph))
    out[hi] = -(((((c[0] * rh + c[1]) * rh + c[2]) * rh + c[3]) * rh + c[4]) * rh + c[5]) / (
        (((d[0] * rh + d[1]) * rh + d[2]) * rh + d[3]) * rh + 1.0
    )
    return out


def compute_spi(precip_window: np.ndarray, accumulation_label: str | None = None) -> np.ndarray:
    """Compute the SPI for each precipitation accumulation in a window.

    A Gamma distribution is fitted to the positive accumulations of *precip_window*
    (the climatological sample) and every accumulation is transformed to a
    standardized index. The returned array has the same length as the input.

    Args:
        precip_window: Accumulated precipitation for each season/window (mm).
        accumulation_label: Optional label describing the accumulation scale.

    Returns:
        An array of SPI values, one per precipitation accumulation.
    """
    values = np.asarray(precip_window, dtype=np.float64)
    n = values.size
    if n < 3:
        raise ValueError("Need at least 3 precipitation windows")
    if np.nanstd(values) < 1e-9:
        return np.zeros(n, dtype=np.float64)
    zero_frac = float(np.mean(values == 0.0))
    alpha, beta = _fit_gamma_alpha_beta(values)
    ppos = _gamma_cdf_ppf(values, alpha, beta)
    total_prob = zero_frac + (1.0 - zero_frac) * ppos
    return _norm_ppf(np.clip(total_prob, 1e-12, 1.0 - 1e-12))


def compute_spi_series(precip: np.ndarray, window: int) -> np.ndarray:
    """Compute a rolling SPI series over a moving accumulation window.

    Args:
        precip: Precipitation per period (mm).
        window: Number of periods in the accumulation window.

    Returns:
        An array of SPI values (NaN where the window is incomplete).
    """
    values = np.asarray(precip, dtype=np.float64)
    n = values.size
    if window < 1:
        raise ValueError("window must be a positive integer")
    out = np.full(n, np.nan, dtype=np.float64)
    if n < window:
        return out
    # rolling accumulation
    cum = np.concatenate([[0.0], np.cumsum(values)])
    rolling = cum[window:] - cum[:-window]
    # a window with no variability has no deviation from climatology
    if np.nanstd(rolling) < 1e-9:
        out[window - 1 :] = 0.0
        return out
    # fit the Gamma to all positive window accumulations once
    try:
        alpha, beta = _fit_gamma_alpha_beta(rolling)
    except ValueError:
        out[window - 1 :] = 0.0
        return out
    zero_frac = float(np.mean(rolling == 0.0))
    for i in range(window - 1, n):
        acc = rolling[i - window + 1]
        ppos = _gamma_cdf_ppf(np.array([acc]), alpha, beta)[0]
        total_prob = zero_frac + (1.0 - zero_frac) * ppos
        out[i] = _norm_ppf(np.clip(np.array([total_prob]), 1e-12, 1.0 - 1e-12))[0]
    return out


def classify_drought(spi: float) -> str:
    """Classify an SPI value per the standard drought severity categories."""
    if spi >= 2.0:
        return "extremely wet"
    if spi >= 1.5:
        return "severely wet"
    if spi >= 1.0:
        return "moderately wet"
    if spi > -1.0:
        return "near normal"
    if spi > -1.5:
        return "moderately dry"
    if spi > -2.0:
        return "severely dry"
    return "extremely dry"


__all__ = ["SPIResult", "compute_spi", "compute_spi_series", "classify_drought"]
