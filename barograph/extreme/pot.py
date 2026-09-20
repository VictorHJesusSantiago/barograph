"""High-level Peaks-Over-Threshold (POT) return-level workflow."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from barograph.extreme.gpd import GPDDistribution, excess_rate, fit_gpd
from barograph.extreme.gpd import return_level as _gpd_return_level
from barograph.extreme.peak import peak_over_threshold


@dataclass(frozen=True)
class POTResult:
    """Result of a full Peaks-Over-Threshold analysis.

    Args:
        distribution: The fitted GPD for the excesses.
        threshold: The chosen threshold level.
        n_exceedances: Number of samples above the threshold.
        excess_rate_per_block: Mean number of excesses per block.
        exceedance_fraction: Fraction of samples exceeding the threshold.
    """

    distribution: GPDDistribution
    threshold: float
    n_exceedances: int
    excess_rate_per_block: float
    exceedance_fraction: float

    def return_level(self, period: np.ndarray) -> np.ndarray:
        """Return level for a return period given in blocks."""
        return _gpd_return_level(self.distribution, period)


def pot_return_level(
    values: np.ndarray,
    threshold: float,
    period: np.ndarray,
    n_blocks: float | None = None,
) -> tuple[POTResult, np.ndarray]:
    """Estimate extreme return levels with the Peaks-Over-Threshold method.

    Fits a Generalized Pareto Distribution to the excesses above *threshold*
    and computes return levels using a Poisson point-process model.

    Args:
        values: The observed series.
        threshold: The exceedance threshold.
        period: Return periods (in blocks, e.g. years) to evaluate.
        n_blocks: Block count; when omitted, the rate is the empirical fraction per sample.

    Returns:
        A tuple ``(result, levels)`` with the analysis result and the return
        levels for each requested period.
    """
    values = np.asarray(values, dtype=np.float64)
    valid = values[np.isfinite(values)]
    if valid.size == 0:
        raise ValueError("No finite values supplied")
    excess = peak_over_threshold(valid, threshold)
    if excess.size < 3:
        raise ValueError(f"Need at least 3 excesses above threshold {threshold}, got {excess.size}")
    dist = fit_gpd(excess, threshold=threshold)
    exceedance_fraction = excess_rate(valid, threshold)
    rate_per_block = (
        exceedance_fraction * valid.size / n_blocks if n_blocks else (exceedance_fraction)
    )
    dist = GPDDistribution(
        scale=dist.scale,
        shape=dist.shape,
        threshold=threshold,
        n_year=rate_per_block,
    )
    result = POTResult(
        distribution=dist,
        threshold=threshold,
        n_exceedances=int(excess.size),
        excess_rate_per_block=float(rate_per_block),
        exceedance_fraction=float(exceedance_fraction),
    )
    levels = _gpd_return_level(dist, period)
    return result, np.asarray(levels, dtype=np.float64)


__all__ = ["POTResult", "pot_return_level"]
