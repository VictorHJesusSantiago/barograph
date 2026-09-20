"""Tests for the time-series analysis module."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from barograph.time_series import (
    PrecipitationAnalyzer,
    TimeSeriesAnalyzer,
    linear_trend,
    rolling_precip,
    seasonal_climatology,
    standard_anomalies,
    wet_days_fraction,
)


def hourly_times(n, start=None):
    start = start or datetime(2026, 1, 1, 0)
    return [start + timedelta(hours=i) for i in range(n)]


def test_linear_trend_positive_slope():
    times = hourly_times(72)
    values = np.linspace(0.0, 10.0, 72)
    slope, intercept, r2 = linear_trend(values, times)
    assert slope > 0
    assert r2 > 0.99


def test_linear_trend_flat_series():
    times = hourly_times(10)
    slope, _, _ = linear_trend(np.full(10, 5.0), times)
    assert abs(slope) < 1e-9


def test_rolling_precip_window():
    values = np.ones(10)
    out = rolling_precip(values, window=3)
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2] == 3.0
    assert out[9] == 3.0


def test_wet_days_fraction():
    values = np.array([0.0, 0.5, 1.0, 0.0, 0.0])
    assert wet_days_fraction(values) == 0.4


def test_wet_days_fraction_all_nan():
    assert wet_days_fraction(np.array([np.nan, np.nan])) == 0.0


def test_precipitation_events_detected():
    times = hourly_times(24)
    values = np.zeros(24)
    values[5:8] = [2.0, 3.0, 1.0]  # one event, 3h
    values[12] = 4.0  # second event, 1h
    events = PrecipitationAnalyzer().events(values, times)
    assert len(events) == 2
    assert events[0].total == 6.0
    assert events[0].duration_hours == 3


def test_precipitation_events_gap_separates():
    times = hourly_times(24)
    values = np.zeros(24)
    values[2] = 5.0
    values[20] = 3.0  # large gap -> separate event
    events = PrecipitationAnalyzer(min_gap_hours=3.0).events(values, times)
    assert len(events) == 2


def test_analyzer_summary():
    analyzer = TimeSeriesAnalyzer(np.array([1.0, 2.0, 3.0, 4.0]), hourly_times(4))
    s = analyzer.summary()
    assert s["mean"] == 2.5
    assert s["n_obs"] == 4.0


def test_daily_means():
    times = hourly_times(48)  # 2 full days
    analyzer = TimeSeriesAnalyzer(np.arange(48.0, dtype=np.float64), times)
    means = analyzer.daily_means()
    assert set(means.keys()) == {f"{h:02d}" for h in range(24)}
    # hour 0: 0 and 24
    assert means["00"] == 12.0


def test_seasonal_climatology_and_anomalies():
    days = 400
    times = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(days)]
    values = 15.0 + 10.0 * np.sin(np.arange(days) / 365.0 * 2 * np.pi)
    clim = seasonal_climatology(values, times)
    assert clim.shape == (366,)
    anom = standard_anomalies(values, times, clim)
    assert anom.shape == (days,)
    assert np.all(np.isfinite(anom))
