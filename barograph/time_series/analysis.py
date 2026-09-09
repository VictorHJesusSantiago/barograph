"""General time-series analysis: trends, seasonality and anomalies."""

from __future__ import annotations

from datetime import datetime

import numpy as np


def linear_trend(
    values: np.ndarray, times: list[datetime]
) -> tuple[float, float, float]:
    """Fit a linear trend ``value = a + b * t`` by least squares.

    Returns:
        ``(slope, intercept, r_squared)`` where the slope is per day.
    """
    x = np.array(
        [(t - times[0]).total_seconds() / 86400.0 for t in times],
        dtype=np.float64,
    )
    y = np.asarray(values, dtype=np.float64)
    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(intercept), r2


def constant_trend(values: np.ndarray) -> float:
    """Return the baseline (mean) of a series."""
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def seasonal_climatology(
    values: np.ndarray,
    times: list[datetime],
    day_of_year: np.ndarray | None = None,
) -> np.ndarray:
    """Compute a day-of-year climatology as a moving average.

    Args:
        values: Series values.
        times: Corresponding timestamps.
        day_of_year: Precomputed day-of-year (0..365); inferred from *times* if omitted.

    Returns:
        A 366-length array of climatological values (index 0 unused).
    """
    if day_of_year is None:
        doy = np.array([t.timetuple().tm_yday for t in times])
    else:
        doy = np.asarray(day_of_year)
    if len(doy) < 366:
        raise ValueError("Need at least 366 samples for a full climatology")
    climat = np.full(366, np.nan, dtype=np.float64)
    for d in range(1, 367):
        window = values[(doy >= d - 10) & (doy <= d + 10)]
        climat[d - 1] = np.nanmean(window)
    # circular wrap for the last days of the year
    for d in range(1, 12):
        climat[d - 1] = np.nanmean(values[(doy >= 356) | (doy <= d + 10)])
    return climat


def standard_anomalies(
    values: np.ndarray, times: list[datetime], climatology: np.ndarray
) -> np.ndarray:
    """Compute standardized anomalies relative to a day-of-year climatology.

    Args:
        values: Series values.
        times: Corresponding timestamps.
        climatology: 366-length day-of-year climatology from :func:`seasonal_climatology`.

    Returns:
        ``(value - climatology[doy]) / std(climatology around doy)`` per point.
    """
    values = np.asarray(values, dtype=np.float64)
    doy = np.array([t.timetuple().tm_yday for t in times])
    anomalies = np.empty(values.shape, dtype=np.float64)
    for i, d in enumerate(doy):
        base = climatology[d - 1]
        window = climatology[max(0, d - 11):d + 10]
        std = np.nanstd(window)
        anomalies[i] = (values[i] - base) / std if std > 0 else 0.0
    return anomalies


class TimeSeriesAnalyzer:
    """Bundle of common time-series computations for a meteorological series."""

    def __init__(self, values: np.ndarray, times: list[datetime]) -> None:
        if len(values) != len(times):
            raise ValueError("values and times must have equal length")
        self.values = np.asarray(values, dtype=np.float64)
        self.times = times

    def summary(self) -> dict[str, float]:
        """Compute a compact numeric summary of the series."""
        slope, _intercept, r2 = linear_trend(self.values, self.times)
        return {
            "min": float(np.nanmin(self.values)),
            "max": float(np.nanmax(self.values)),
            "mean": float(np.nanmean(self.values)),
            "std": float(np.nanstd(self.values)),
            "trend_per_day": slope,
            "trend_r2": r2,
            "n_obs": float(len(self.times)),
        }

    def daily_means(self) -> dict[str, float]:
        """Mean value grouped by clock hour (0..23)."""
        hours = np.array([t.hour for t in self.times])
        out: dict[str, float] = {}
        for h in range(24):
            mask = hours == h
            if np.any(mask):
                out[str(h).zfill(2)] = float(np.nanmean(self.values[mask]))
        return out
