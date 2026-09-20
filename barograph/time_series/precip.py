"""Precipitation time-series analysis: events, rolling sums and wet-day stats."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np


@dataclass
class PrecipitationEvent:
    """A detected precipitation episode."""

    start: datetime
    end: datetime
    peak: float
    total: float
    duration_hours: int


def rolling_precip(values: np.ndarray, window: int, period_hours: float = 1.0) -> np.ndarray:
    """Cumulative precipitation over a rolling window of *window* samples.

    Args:
        values: Precipitation per sample.
        window: Number of samples in the rolling window.
        period_hours: Duration of each sample in hours (for doc/reporting).

    Returns:
        NaN-padded rolling sum array (same length as *values*).
    """
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    if window > n:
        window = n
    out = np.full(n, np.nan, dtype=np.float64)
    if n == 0:
        return out
    cumsum = np.concatenate([[0.0], np.nancumsum(values)])
    for i in range(window - 1, n):
        out[i] = cumsum[i + 1] - cumsum[i + 1 - window]
    return out


def wet_days_fraction(values: np.ndarray, threshold: float = 0.1) -> float:
    """Fraction of samples with precipitation above *threshold* (0..1)."""
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(values)
    if not np.any(valid):
        return 0.0
    return float(np.mean(values[valid] > threshold))


class PrecipitationAnalyzer:
    """Segment a precipitation series into individual events.

    Args:
        min_gap_hours: Max gap between wet samples before a new event starts.
        min_wet: Threshold below which a sample is considered dry.
    """

    def __init__(
        self,
        min_gap_hours: float = 6.0,
        min_wet: float = 0.1,
        period_hours: float = 1.0,
    ) -> None:
        self.min_gap_hours = min_gap_hours
        self.min_wet = min_wet
        self.period_hours = period_hours

    def events(self, values: np.ndarray, times: list[datetime]) -> list[PrecipitationEvent]:
        """Detect contiguous precipitation events in the series."""
        values = np.asarray(values, dtype=np.float64)
        result: list[PrecipitationEvent] = []
        current: list[int] = []
        max_gap = timedelta(hours=self.min_gap_hours)
        for i, (t, v) in enumerate(zip(times, values)):
            wet = v >= self.min_wet
            if wet:
                if current and (times[i] - times[i - 1]) > max_gap:
                    self._flush(current, times, values, result)
                    current = []
                current.append(i)
            else:
                if current and current[-1] == i - 1:
                    self._flush(current, times, values, result)
                    current = []
        if current:
            self._flush(current, times, values, result)
        return result

    @staticmethod
    def _flush(
        indices: list[int],
        times: list[datetime],
        values: np.ndarray,
        result: list[PrecipitationEvent],
    ) -> None:
        if not indices:
            return
        peak = float(np.nanmax(values[indices]))
        total = float(np.nansum(values[indices]))
        result.append(
            PrecipitationEvent(
                start=times[indices[0]],
                end=times[indices[-1]],
                peak=peak,
                total=total,
                duration_hours=int(indices[-1] - indices[0] + 1),
            )
        )
