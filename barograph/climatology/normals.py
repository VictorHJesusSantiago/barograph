"""Computation of climatological normals and deviations from normal.

A climatological "normal" is the long-term average of a variable for a given
calendar window (e.g. a specific month), used as a baseline to quantify how
unusual a current observation is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class ClimatologyNormal:
    """A stored climatological baseline for a station/variable."""

    variable: str
    baseline_start: int
    baseline_end: int
    monthly_mean: dict[int, float]  # month index (1..12) -> mean
    monthly_std: dict[int, float] = field(default_factory=dict)
    annual_mean: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def mean_for_month(self, month: int) -> float | None:
        """Return the normal-mean for a 1-based month, or ``None``."""
        return self.monthly_mean.get(int(month))

    def deviation(self, value: float, month: int) -> float:
        """Return the departure of *value* from the monthly normal (raw)."""
        normal = self.mean_for_month(month)
        if normal is None:
            raise ValueError(f"No normal available for month {month}")
        return value - normal

    def standardized_deviation(self, value: float, month: int) -> float:
        """Return the departure normalized by the monthly standard deviation."""
        normal = self.mean_for_month(month)
        std = self.monthly_std.get(int(month))
        if normal is None or not std:
            return 0.0
        return (value - normal) / std


def monthly_climatology(
    values: np.ndarray,
    times: list[datetime],
    years: tuple[int, int] | None = None,
) -> dict[int, tuple[float, float]]:
    """Compute a monthly climatology mapping each month to ``(mean, std)``.

    Args:
        values: Series values.
        times: Corresponding timestamps.
        years: Optional ``(start, end)`` baseline window; samples outside are ignored.

    Returns:
        A dict mapping each month (1..12) to its ``(mean, std)`` pair.
    """
    months = np.array([t.month for t in times])
    arr = np.asarray(values, dtype=np.float64)
    if years is not None:
        keep = np.array(
            [years[0] <= t.year <= years[1] for t in times]
        )
        months = months[keep]
        arr = arr[keep]
    result: dict[int, tuple[float, float]] = {}
    for m in range(1, 13):
        vals = arr[months == m]
        vals = vals[np.isfinite(vals)]
        if vals.size:
            result[m] = (float(np.mean(vals)), float(np.std(vals)))
    return result


def annual_climatology(
    values: np.ndarray,
    times: list[datetime],
    years: tuple[int, int] | None = None,
) -> tuple[float, float]:
    """Compute the overall ``(mean, std)`` over the baseline window."""
    arr = np.asarray(values, dtype=np.float64)
    if years is not None:
        keep = np.array([years[0] <= t.year <= years[1] for t in times])
        arr = arr[keep]
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return (float("nan"), float("nan"))
    return (float(np.mean(arr)), float(np.std(arr)))


def deviation_from_normal(
    normal: ClimatologyNormal, value: float, month: int
) -> float:
    """Raw deviation of *value* from the stored *normal* for a month."""
    return normal.deviation(value, month)
