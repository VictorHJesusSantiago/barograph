"""Extraction of extreme samples from a time series.

Provides block-maxima (used to feed GEV fitting) and peak-over-threshold
extraction for use with distributional tail analysis.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np


def block_maxima(
    values: np.ndarray, block_size: int, times: list[datetime] | None = None
) -> np.ndarray:
    """Return the maximum of each contiguous block of *block_size* samples.

    Args:
        values: Observed series.
        block_size: Number of samples per block.
        times: Optional timestamps (only the final partial block is dropped).

    Returns:
        Array of block maxima.
    """
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    if block_size < 1:
        raise ValueError("block_size must be a positive integer")
    n_blocks = n // block_size
    if n_blocks == 0:
        return np.empty(0, dtype=np.float64)
    reshaped = values[: n_blocks * block_size].reshape(n_blocks, block_size)
    return np.nanmax(reshaped, axis=1)


def annual_maxima(values: np.ndarray, times: list[datetime]) -> np.ndarray:
    """Return the maximum value in each calendar year of *times*.

    Sorts by year and returns one maximum per year present.
    """
    values = np.asarray(values, dtype=np.float64)
    if len(times) != len(values):
        raise ValueError("values and times must have equal length")
    years: dict[int, float] = {}
    for t, v in zip(times, values):
        if np.isnan(v):
            continue
        year = t.year
        years[year] = max(years.get(year, -np.inf), float(v))
    return np.array(list(years.values()), dtype=np.float64)


def peak_over_threshold(
    values: np.ndarray, threshold: float
) -> np.ndarray:
    """Return the exceedances of *threshold* (peaks over threshold).

    Only the positive deviation (excess) above the threshold is returned,
    which is the quantity modelled by a Generalized Pareto distribution.
    """
    values = np.asarray(values, dtype=np.float64)
    excess = values[values > threshold] - threshold
    return np.asarray(excess, dtype=np.float64)


__all__ = ["block_maxima", "annual_maxima", "peak_over_threshold"]
