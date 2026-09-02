"""Temporal interpolation and resampling utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime.

    Avoids the deprecated ``datetime.utcnow()`` (removed in Python 3.14+).
    The result is naive (no tzinfo) to stay compatible with the rest of the
    codebase which stores naive UTC datetimes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def temporal_interpolate(
    values: list[float],
    times: list[datetime],
    target_times: list[datetime],
    method: str = "linear",
) -> np.ndarray:
    """Interpolate values to target times."""
    from scipy.interpolate import interp1d

    times_numeric = np.array([(t - times[0]).total_seconds() for t in times])
    target_numeric = np.array([(t - times[0]).total_seconds() for t in target_times])

    fill_value: str | tuple[float, float]
    if method == "linear":
        fill_value = "extrapolate"
    else:
        fill_value = (values[0], values[-1])

    f = interp1d(times_numeric, values, kind=method, fill_value=fill_value)
    return f(target_numeric)


def resample_temporal(
    data: np.ndarray,
    src_times: list[datetime],
    target_step_hours: float,
    method: str = "mean",
) -> tuple[np.ndarray, list[datetime]]:
    """Resample temporally to a coarser time step."""
    data = np.asarray(data, dtype=np.float64)
    if len(src_times) < 2:
        return data, src_times

    total_hours = (src_times[-1] - src_times[0]).total_seconds() / 3600
    n_steps = int(total_hours / target_step_hours) + 1
    target_times = [
        src_times[0] + timedelta(hours=i * target_step_hours)
        for i in range(n_steps)
    ]

    if data.ndim == 1:
        result = np.zeros(len(target_times), dtype=np.float64)
        for k, t_start in enumerate(target_times):
            t_end = t_start + timedelta(hours=target_step_hours)
            mask = np.array(
                [(t_start <= t < t_end) for t in src_times]
            )
            if np.any(mask):
                result[k] = np.mean(data[mask]) if method == "mean" else np.sum(data[mask])
        return result, target_times

    raise ValueError("Only 1D temporal resampling is currently supported")


def time_weights(times: list[datetime]) -> np.ndarray:
    """Compute integration weights (hours) for irregular time series."""
    if len(times) < 2:
        return np.ones(len(times))

    weights = np.zeros(len(times))
    for i in range(len(times)):
        if i == 0:
            dt = (times[1] - times[0]).total_seconds() / 3600
            weights[i] = dt / 2
        elif i == len(times) - 1:
            dt = (times[-1] - times[-2]).total_seconds() / 3600
            weights[i] = dt / 2
        else:
            dt_prev = (times[i] - times[i - 1]).total_seconds() / 3600
            dt_next = (times[i + 1] - times[i]).total_seconds() / 3600
            weights[i] = (dt_prev + dt_next) / 2
    return weights
