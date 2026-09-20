"""Categorical forecast verification scores for binary alerts.

Scores are derived from a 2x2 contingency table: hits, misses, false alarms
and correct negatives. All functions accept a :class:`ContingencyTable` or the
four counts directly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ContingencyTable:
    """2x2 contingency table for a binary (yes/no) forecast.

    Args:
        hits: Event forecast and observed.
        misses: Event observed but not forecast.
        false_alarms: Event forecast but not observed.
        correct_negatives: Event neither forecast nor observed.
    """

    hits: int = 0
    misses: int = 0
    false_alarms: int = 0
    correct_negatives: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses + self.false_alarms + self.correct_negatives


def contingency_table(forecast: np.ndarray, observed: np.ndarray) -> ContingencyTable:
    """Build a contingency table from aligned binary forecast/observed arrays."""
    f = np.asarray(forecast).astype(bool)
    o = np.asarray(observed).astype(bool)
    if f.shape != o.shape:
        raise ValueError("forecast and observed must have matching shapes")
    hits = int(np.sum(f & o))
    misses = int(np.sum(~f & o))
    false_alarms = int(np.sum(f & ~o))
    correct_negatives = int(np.sum(~f & ~o))
    return ContingencyTable(hits, misses, false_alarms, correct_negatives)


def _extract(
    table: ContingencyTable | None,
    hits: int = 0,
    misses: int = 0,
    false_alarms: int = 0,
    correct_negatives: int = 0,
) -> ContingencyTable:
    if table is not None:
        return table
    return ContingencyTable(hits, misses, false_alarms, correct_negatives)


def probability_of_detection(table: ContingencyTable | None = None, **counts: int) -> float:
    """POD (hit rate): fraction of observed events that were forecast; 1 is best."""
    t = _extract(table, **counts)
    denom = t.hits + t.misses
    if denom == 0:
        return np.nan
    return t.hits / denom


def false_alarm_ratio(table: ContingencyTable | None = None, **counts: int) -> float:
    """FAR: fraction of forecasts that did not occur; 0 is best."""
    t = _extract(table, **counts)
    denom = t.hits + t.false_alarms
    if denom == 0:
        return np.nan
    return t.false_alarms / denom


def critical_success_index(table: ContingencyTable | None = None, **counts: int) -> float:
    """CSI (threat score); 1 is best, 0 is worst."""
    t = _extract(table, **counts)
    denom = t.hits + t.misses + t.false_alarms
    if denom == 0:
        return np.nan
    return t.hits / denom


def equitable_threat_score(table: ContingencyTable | None = None, **counts: int) -> float:
    """ETS (Gilbert skill score); random forecasts score zero."""
    t = _extract(table, **counts)
    total = t.total
    if total == 0:
        return np.nan
    hits_random = (t.hits + t.misses) * (t.hits + t.false_alarms) / total
    denom = t.hits + t.misses + t.false_alarms - hits_random
    if denom == 0:
        return np.nan
    return (t.hits - hits_random) / denom


def frequency_bias(table: ContingencyTable | None = None, **counts: int) -> float:
    """Bias score: ratio of forecast to observed event frequency; 1 is perfect."""
    t = _extract(table, **counts)
    denom = t.hits + t.misses
    if denom == 0:
        return np.nan
    return (t.hits + t.false_alarms) / denom


def peirce_skill_score(table: ContingencyTable | None = None, **counts: int) -> float:
    """PSS (true skill statistic): POD minus false alarm rate; 1 is perfect."""
    t = _extract(table, **counts)
    hits, misses, false_alarms, correct_negatives = (
        t.hits,
        t.misses,
        t.false_alarms,
        t.correct_negatives,
    )
    pod_denom = hits + misses
    far_denom = false_alarms + correct_negatives
    if pod_denom == 0 or far_denom == 0:
        return np.nan
    pod = hits / pod_denom
    false_alarm_rate = false_alarms / far_denom
    return pod - false_alarm_rate


__all__ = [
    "ContingencyTable",
    "contingency_table",
    "probability_of_detection",
    "false_alarm_ratio",
    "critical_success_index",
    "equitable_threat_score",
    "frequency_bias",
    "peirce_skill_score",
]
