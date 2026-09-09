"""Standardized Precipitation-Evapotranspiration Index (SPEI).

The SPEI (Vicente-Serrano et al., 2010) is a drought index based on the
climatic water balance: the difference between precipitation and potential
evapotranspiration (PET). It is computed similarly to the SPI, but the
fitted distribution is applied to the water-balance series, which can take
negative values. A three-parameter distribution is not fitted here; instead
the standardized series is obtained by transforming the empirical
probabilities of a generalized logistic fit to the standard normal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from barograph.indices.spi import (
    _norm_ppf,
    classify_drought,  # noqa: F401
)


@dataclass
class SPEIResult:
    """Result of a single SPEI computation.

    Args:
        water_balance: The accumulated precipitation-minus-PET (mm).
        spei: The standardized index value.
        class_label: Drought classification of the value.
    """

    water_balance: float
    spei: float
    class_label: str


def pet_thornthwaite(
    temperature: np.ndarray,
    latitude: float,
    i_index: float | None = None,
) -> np.ndarray:
    """Potential evapotranspiration (mm/month) by the Thornthwaite (1948) formula.

    Args:
        temperature: Mean monthly air temperature (Celsius).
        latitude: Latitude in degrees (used for day-length adjustment).
        i_index: Annual heat index; computed from *temperature* if omitted.

    Returns:
        Monthly potential evapotranspiration in millimetres (clipped to zero
        for freezing months).
    """
    temp = np.asarray(temperature, dtype=np.float64)
    if i_index is None:
        i_index = _heat_index(temp)
    i = i_index
    if i <= 0 or np.isnan(i):
        return np.zeros_like(temp)
    a = 6.75e-7 * i**3 - 7.71e-5 * i**2 + 1.79e-2 * i + 0.49
    t = np.clip(temp, 0.0, None)
    days = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    n_daylight = _daylight_hours(latitude)
    ratio = (n_daylight / 12.0) * (days / 30.0)
    # unadjusted monthly PET
    base = 16.0 * (10.0 * t / i) ** a
    base = np.where(temp <= 0.0, 0.0, base)
    return base * ratio


def _heat_index(temperature: np.ndarray) -> float:
    """Annual heat index: sum of (T/5)^1.514 over positive months."""
    t = np.asarray(temperature, dtype=np.float64)
    positive = t[t > 0.0]
    if positive.size == 0:
        return 0.0
    return float(np.sum((positive / 5.0) ** 1.514))


def _daylight_hours(latitude: float) -> np.ndarray:
    """Approximate monthly mean daylight hours for a latitude."""
    # Monthly fractional solar declination (mean day of each month)
    mean_days = np.array([15, 45, 74, 105, 135, 162, 198, 228, 258, 288, 318, 344])
    declination = 23.44 * np.sin(np.deg2rad((360.0 / 365.0) * (mean_days - 81)))
    phi = np.deg2rad(np.clip(latitude, -89.0, 89.0))
    delta = np.deg2rad(declination)
    cos_omega = -np.tan(phi) * np.tan(delta)
    cos_omega = np.clip(cos_omega, -1.0, 1.0)
    hour_angle = np.arccos(cos_omega)
    return 2.0 * hour_angle / np.pi * 12.0


def compute_spei(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    latitude: float,
    window: int,
    accumulation_label: str | None = None,
) -> np.ndarray:
    """Compute the SPEI series over a moving water-balance window.

    Args:
        precipitation: Precipitation per period (mm).
        temperature: Mean temperature per period (Celsius).
        latitude: Latitude in degrees.
        window: Number of periods in the accumulation window.
        accumulation_label: Optional label describing the accumulation scale.

    Returns:
        An array of SPEI values (NaN where the window is incomplete).
    """
    prec = np.asarray(precipitation, dtype=np.float64)
    temp = np.asarray(temperature, dtype=np.float64)
    n = min(prec.size, temp.size)
    if n < 1 or window < 1:
        raise ValueError("Need non-empty series and a positive window")
    out = np.full(n, np.nan, dtype=np.float64)
    if n < window:
        return out
    # Apply the monthly PET climatology (min(12, n) months), cycling by month.
    nmonths = min(12, n)
    pet_clim = pet_thornthwaite(temp[:nmonths], latitude)
    pet = np.tile(pet_clim, int(np.ceil(n / nmonths)))[:n]
    balance = prec[:n] - pet
    cum = np.concatenate([[0.0], np.cumsum(balance)])
    rolling = cum[window:] - cum[:-window]
    if np.nanstd(rolling) < 1e-9:
        out[window - 1:] = 0.0
        return out
    alpha, beta = _logistic_fit(rolling)
    if not np.isfinite(alpha) or not np.isfinite(beta):
        out[window - 1:] = 0.0
        return out
    for i in range(window - 1, n):
        acc = rolling[i - window + 1]
        p = _logistic_cdf(acc, alpha, beta)
        out[i] = _norm_ppf(np.clip(np.array([p]), 1e-12, 1.0 - 1e-12))[0]
    return out


def _logistic_fit(values: np.ndarray) -> tuple[float, float]:
    """Location-scale fit for the generalized logistic via robust quantiles.

    Uses the median and the interquartile range to set the location and scale
    of the logistic distribution, which is robust to outliers common in
    water-balance series.
    """
    loc = float(np.nanmedian(values))
    q1 = np.nanpercentile(values, 25)
    q3 = np.nanpercentile(values, 75)
    if abs(q3 - q1) < 1e-12:
        raise ValueError("Water-balance distribution has no dispersion")
    scale = (q3 - q1) / (np.log(3.0) - np.log(1.0 / 3.0))
    return loc, float(scale)


def _logistic_cdf(x: float, loc: float, scale: float) -> float:
    """Cumulative probability of a logistic distribution at *x*."""
    z = (x - loc) / scale
    return 1.0 / (1.0 + np.exp(-z))


__all__ = [
    "SPEIResult",
    "pet_thornthwaite",
    "compute_spei",
    "classify_drought",
]
