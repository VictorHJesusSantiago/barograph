"""Tests for the climatology module."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from barograph.climatology import (
    ClimatologyNormal,
    annual_climatology,
    deviation_from_normal,
    monthly_climatology,
)


def test_monthly_climatology_means():
    times = [datetime(2020, m, 15) for m in range(1, 13)]
    values = np.array([float(m) for m in range(1, 13)])
    monthly = monthly_climatology(values, times, years=(2020, 2020))
    assert monthly[1][0] == 1.0
    assert monthly[12][0] == 12.0
    full = monthly_climatology(values, times)
    assert full[6][0] == 6.0


def test_annual_climatology():
    times = [datetime(2020, 1, 1), datetime(2020, 6, 1)]
    values = np.array([10.0, 20.0])
    mean, std = annual_climatology(values, times, years=(2020, 2020))
    assert mean == 15.0
    assert std > 0


def test_climatology_normal_deviation():
    normal = ClimatologyNormal(
        variable="temperature",
        baseline_start=1991,
        baseline_end=2020,
        monthly_mean={1: 22.0, 7: 15.0},
        monthly_std={1: 1.0, 7: 2.0},
        annual_mean=20.0,
    )
    assert normal.mean_for_month(1) == 22.0
    assert normal.deviation(25.0, 1) == 3.0
    assert normal.standardized_deviation(25.0, 1) == 3.0
    assert deviation_from_normal(normal, 25.0, 1) == 3.0


def test_climatology_normal_unknown_month_raises():
    normal = ClimatologyNormal(
        variable="t",
        baseline_start=1991,
        baseline_end=2020,
        monthly_mean={},
    )
    try:
        normal.deviation(1.0, 5)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_standardized_zero_std():
    normal = ClimatologyNormal(
        variable="t",
        baseline_start=1991,
        baseline_end=2020,
        monthly_mean={1: 10.0},
        monthly_std={1: 0.0},
    )
    assert normal.standardized_deviation(12.0, 1) == 0.0
