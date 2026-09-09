"""Automated quality-control checks on meteorological data series.

The module provides independent, testable QC routines plus a single
:class:`QualityController` that runs a configured set of checks and returns a
per-sample :class:`QualityResult`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np


class QualityFlag(Enum):
    """Per-sample quality classification."""

    GOOD = "good"
    GROSS = "gross_error"
    SPIKE = "spike"
    PERSISTENT = "persistent"
    DUPLICATE = "duplicate"
    MISSING = "missing"


@dataclass
class QCThresholds:
    """Bounds and sensitivity used by the individual checks."""

    min_value: float = -np.inf
    max_value: float = np.inf
    spike_sigma: float = 5.0
    persistence_span: int = 6
    duplicate_tol: float = 1e-12


def check_gross_range(
    values: np.ndarray, thresholds: QCThresholds
) -> np.ndarray:
    """Flag samples falling outside the allowed physical range.

    Returns:
        A boolean array with ``True`` for gross-error samples.
    """
    values = np.asarray(values, dtype=np.float64)
    flag = ~np.isfinite(values)
    flag |= values < thresholds.min_value
    flag |= values > thresholds.max_value
    return flag


def check_spikes(
    values: np.ndarray, thresholds: QCThresholds
) -> np.ndarray:
    """Flag isolated spikes relative to a robust local baseline.

    A sample is a spike if it deviates from the median of its neighbours by
    more than ``spike_sigma`` times the local median absolute deviation.
    """
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    if n < 5:
        return np.zeros(n, dtype=bool)
    flag = np.zeros(n, dtype=bool)
    for i in range(2, n - 2):
        window = values[i - 2:i + 3]
        center = window[2]
        baseline = np.median(window[(np.arange(5) != 2)])  # exclude center
        mad = np.median(np.abs(window - np.median(window)))
        if mad < 1e-12:
            continue  # near-constant window cannot produce a spike
        if abs(center - baseline) > thresholds.spike_sigma * mad:
            flag[i] = True
    return flag


def check_persistence(
    values: np.ndarray, thresholds: QCThresholds
) -> np.ndarray:
    """Flag runs of identical values longer than ``persistence_span``."""
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    flag = np.zeros(n, dtype=bool)
    if n == 0:
        return flag
    run_start = 0
    for i in range(1, n + 1):
        if i == n or values[i] != values[i - 1]:
            if i - run_start > thresholds.persistence_span:
                flag[run_start:i] = True
            run_start = i
    return flag


def check_duplicates(
    times: list[datetime], values: np.ndarray
) -> np.ndarray:
    """Flag samples sharing an identical timestamp."""
    n = len(times)
    flag = np.zeros(n, dtype=bool)
    seen: dict[datetime, int] = {}
    for i, t in enumerate(times):
        if t in seen:
            flag[i] = True
        else:
            seen[t] = i
    return flag


def detect_gaps(
    times: list[datetime], max_gap_hours: float = 8.0
) -> list[tuple[int, int]]:
    """Return intervals of missing data.

    Returns:
        A list of ``(start_index, end_index)`` covering the samples that
        surround a detected gap (the samples before and after the missing
        block are included to denote the gap extent).
    """
    gaps: list[tuple[int, int]] = []
    if len(times) < 2:
        return gaps
    for i in range(1, len(times)):
        delta = (times[i] - times[i - 1]).total_seconds() / 3600.0
        if delta > max_gap_hours:
            gaps.append((i - 1, i))
    return gaps


def _combine(arrays: Iterable[np.ndarray]) -> np.ndarray:
    """Element-wise logical OR of boolean flag arrays."""
    return np.logical_or.reduce(list(arrays))


@dataclass
class QualityResult:
    """Result of running the quality controller on a series."""

    flags: list[QualityFlag]
    per_check: dict[str, np.ndarray]
    n_good: int

    def is_good(self, index: int) -> bool:
        return self.flags[index] == QualityFlag.GOOD


class QualityController:
    """Run a configured set of QC checks and classify each sample.

    The final flag for a sample is the most severe of the individual check
    flags (gross > spike > persistent > duplicate > good).
    """

    _SEVERITY = {
        QualityFlag.GOOD: 0,
        QualityFlag.DUPLICATE: 1,
        QualityFlag.PERSISTENT: 2,
        QualityFlag.SPIKE: 3,
        QualityFlag.GROSS: 4,
        QualityFlag.MISSING: 5,
    }

    def __init__(self, thresholds: QCThresholds | None = None) -> None:
        self.thresholds = thresholds or QCThresholds()

    def run(
        self,
        values: np.ndarray,
        times: list[datetime],
        *,
        do_gross: bool = True,
        do_spikes: bool = True,
        do_persistence: bool = True,
        do_duplicates: bool = True,
    ) -> QualityResult:
        """Run the configured checks and return a :class:`QualityResult`."""
        values = np.asarray(values, dtype=np.float64)
        n = len(values)
        per_check: dict[str, np.ndarray] = {}

        gross = np.zeros(n, dtype=bool)
        spike = np.zeros(n, dtype=bool)
        persistent = np.zeros(n, dtype=bool)
        duplicate = np.zeros(n, dtype=bool)
        missing = ~np.isfinite(values)

        if do_gross:
            gross = check_gross_range(values, self.thresholds)
        if do_spikes:
            spike = check_spikes(values, self.thresholds)
        if do_persistence:
            persistent = check_persistence(values, self.thresholds)
        if do_duplicates:
            duplicate = check_duplicates(times, values)

        per_check["gross"] = gross
        per_check["spike"] = spike
        per_check["persistent"] = persistent
        per_check["duplicate"] = duplicate
        per_check["missing"] = missing

        flags: list[QualityFlag] = []
        for i in range(n):
            flag = QualityFlag.GOOD
            if missing[i]:
                flag = QualityFlag.MISSING
            elif gross[i]:
                flag = QualityFlag.GROSS
            elif spike[i]:
                flag = QualityFlag.SPIKE
            elif persistent[i]:
                flag = QualityFlag.PERSISTENT
            elif duplicate[i]:
                flag = QualityFlag.DUPLICATE
            flags.append(flag)

        n_good = sum(1 for f in flags if f == QualityFlag.GOOD)
        return QualityResult(flags=flags, per_check=per_check, n_good=n_good)
