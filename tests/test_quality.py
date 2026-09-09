from datetime import datetime, timedelta

import numpy as np

from barograph.quality.qc import (
    QCThresholds,
    QualityController,
    QualityFlag,
    check_duplicates,
    check_gross_range,
    check_persistence,
    check_spikes,
    detect_gaps,
)


def base_times(n):
    t0 = datetime(2024, 1, 1, 0, 0)
    return [t0 + timedelta(hours=i) for i in range(n)]


def test_gross_range_flags_out_of_bounds():
    values = np.array([0.0, 15.0, -5.0, 200.0, 12.0])
    th = QCThresholds(min_value=-20.0, max_value=50.0)
    flag = check_gross_range(values, th)
    assert flag.tolist() == [False, False, False, True, False]


def test_gross_range_flags_nan():
    values = np.array([1.0, np.nan, 3.0])
    flag = check_gross_range(values, QCThresholds())
    assert flag.tolist() == [False, True, False]


def test_spike_detection():
    values = np.array([10.0, 10.1, 9.9, 40.0, 10.0, 10.2, 10.0])
    flag = check_spikes(values, QCThresholds(spike_sigma=5.0))
    assert bool(flag[3]) is True
    assert sum(flag) == 1


def test_spike_short_series_returns_zeros():
    flag = check_spikes(np.array([1.0, 2.0]), QCThresholds())
    assert flag.tolist() == [False, False]


def test_persistence_flags_long_runs():
    values = np.array([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 1.0, 1.0])
    flag = check_persistence(values, QCThresholds(persistence_span=4))
    # the run of 7 identical fives (indices 0-6) is flagged
    assert bool(flag[:7].all())
    # the tail is a different constant, short run, not flagged
    assert bool(flag[7]) is False
    assert bool(flag[8]) is False


def test_duplicate_timestamps():
    times = base_times(3)
    dup = [times[0], times[0], times[1]]
    flag = check_duplicates(dup, np.zeros(3))
    assert flag.tolist() == [False, True, False]


def test_detect_gaps():
    times = base_times(6)
    times = times[:3] + [times[3] + timedelta(hours=24)] + times[4:]
    gaps = detect_gaps(times, max_gap_hours=8.0)
    assert (2, 3) in gaps


def test_controller_flags_gross():
    times = base_times(4)
    values = np.array([1.0, 2.0, 500.0, 4.0])
    result = QualityController(QCThresholds(max_value=100.0)).run(values, times)
    assert result.flags[2] == QualityFlag.GROSS
    assert result.is_good(2) is False


def test_controller_flags_spike():
    times = base_times(8)
    # clean series except one obvious spike at index 3
    values = np.array([10.0, 10.1, 9.9, 30.0, 10.1, 10.0, 10.2, 9.9])
    result = QualityController(QCThresholds(spike_sigma=5.0)).run(values, times)
    assert result.flags[3] == QualityFlag.SPIKE


def test_controller_flags_persistence():
    times = base_times(8)
    values = np.array([8.0, 8.0, 8.0, 8.0, 8.0, 2.0, 2.0, 4.0])
    result = QualityController(QCThresholds(persistence_span=3)).run(values, times)
    assert result.flags[0] == QualityFlag.PERSISTENT


def test_controller_counts_good():
    times = base_times(4)
    values = np.array([1.0, 2.0, 3.0, 4.0])
    result = QualityController().run(values, times)
    assert result.n_good == 4
