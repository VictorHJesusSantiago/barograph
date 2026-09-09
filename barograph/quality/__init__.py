"""Data quality control for meteorological observation series."""

from barograph.quality.qc import (
    QCThresholds,
    QualityController,
    QualityFlag,
    QualityResult,
    check_duplicates,
    check_gross_range,
    check_persistence,
    check_spikes,
    detect_gaps,
)

__all__ = [
    "QualityFlag",
    "QualityResult",
    "QualityController",
    "QCThresholds",
    "check_gross_range",
    "check_spikes",
    "check_persistence",
    "check_duplicates",
    "detect_gaps",
]
