"""Generalized Extreme Value (GEV) distribution and return levels.

The GEV distribution models the distribution of block maxima of a random
process. Parameters are estimated with the method of L-moments, which is
robust to outliers and free of iterative optimisation. Return levels are
inverted from the fitted cumulative distribution function.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GEVDistribution:
    """A fitted Generalized Extreme Value distribution.

    Args:
        loc: Location parameter (mu).
        scale: Scale parameter (sigma), strictly positive.
        shape: Shape parameter (xi); zero indicates the Gumbel case.
    """

    loc: float
    scale: float
    shape: float

    def cdf(self, x: np.ndarray) -> np.ndarray:
        """Return the GEV cumulative probability at *x*."""
        return gevcdf(np.asarray(x, dtype=np.float64), self.loc, self.scale, self.shape)

    def quantile(self, p: np.ndarray) -> np.ndarray:
        """Return the quantile for probability *p* (inverse CDF)."""
        p = np.asarray(p, dtype=np.float64)
        xi = self.shape
        if abs(xi) < 1e-12:
            return self.loc - self.scale * np.log(-np.log(np.clip(p, 1e-12, 1 - 1e-12)))
        y = -np.log(np.clip(p, 1e-12, 1 - 1e-12))
        return self.loc + self.scale * (y ** (-xi) - 1.0) / xi

    def return_level(self, period: np.ndarray) -> np.ndarray:
        """Return level for a given return period (e.g. 100-year event)."""
        return return_level(self, period)


def gevcdf(x: np.ndarray, loc: float, scale: float, shape: float) -> np.ndarray:
    """Evaluate the GEV cumulative distribution function."""
    x = np.asarray(x, dtype=np.float64)
    if scale <= 0:
        raise ValueError("GEV scale must be positive")
    if abs(shape) < 1e-12:
        z = (x - loc) / scale
        return np.exp(-np.exp(-z))
    z = 1.0 + shape * (x - loc) / scale
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(z > 0, np.exp(-(z ** (-1.0 / shape))), np.nan)


def _l_moments(samples: np.ndarray) -> tuple[float, float, float]:
    """Estimate the first three probability-weighted moments (L-moments).

    Returns:
        ``(l1, l2, tau3)``: the mean, the L-scale and the L-skewness.
    """
    x = np.sort(np.asarray(samples, dtype=np.float64))
    if x.size < 3:
        raise ValueError("A GEV fit requires at least 3 samples")
    n = x.size
    b0 = x.mean()
    # second and third probability weighted moments (Hosking convention)
    b1 = np.mean(x * (np.arange(1, n + 1) - 1.0) / (n - 1.0))
    b2 = np.mean(
        x * (np.arange(1, n + 1) - 1.0) * (np.arange(1, n + 1) - 2.0) / ((n - 1.0) * (n - 2.0))
    )
    l1 = b0
    l2 = 2.0 * b1 - b0
    l3 = 6.0 * b2 - 6.0 * b1 + b0
    tau3 = l3 / l2 if abs(l2) > 1e-12 else 0.0
    return l1, l2, tau3


def _gev_param_from_lmoments(loc: float, scale: float, tau3: float) -> tuple[float, float, float]:
    """Invert GEV parameters from L-moments (Hosking et al., 1985).

    The GEV parameter recovery uses the exact theoretical relations between
    the first three L-moments and the GEV parameters, with the shape parameter
    obtained from an accurate rational approximation of the L-skewness.
    """
    t3 = float(np.clip(tau3, -0.5, 0.65))
    euler = 0.5772156649015329
    ln23 = float(np.log(2.0) / np.log(3.0))
    if abs(t3) <= 1e-9:
        # For k=0 (Gumbel) the L-scale relation is l2 = sigma * ln(2).
        sigma = scale / float(np.log(2.0))
        mu = loc - euler * sigma
        return mu, sigma, 0.0

    c = 2.0 / (3.0 + t3) - ln23
    k = 7.8590 * c + 2.9554 * c * c

    def gamma1mk(kk: float) -> float:
        return np.exp(_lgamma_series(1.0 - kk))

    if abs(k) < 1e-9:
        sigma = scale / float(np.log(2.0))
        mu = loc - euler * sigma
        return mu, sigma, 0.0

    g1mk = gamma1mk(k)
    two_k = 2.0 ** (-k)
    sigma = k * scale / (g1mk * (1.0 - two_k))
    if sigma <= 0:
        raise ValueError("Estimated GEV scale is not positive")
    mu = loc - sigma / k * (g1mk - 1.0)
    return mu, sigma, float(k)


def _lgamma_series(z: float) -> float:
    """ln(Gamma(z)) for z slightly above 1 used in GEV L-moment relations."""
    # Use scipy.special when available, else a Lanczos approximation.
    try:
        import scipy.special  # type: ignore

        return float(scipy.special.gammaln(z))
    except Exception:  # pragma: no cover - scipy is an optional dependency
        return np.log(_lanczos_gamma(z))


def _lanczos_gamma(z: float) -> float:
    """Lanczos approximation of Gamma(z) for z > 0."""
    g = 7
    coeff = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7,
    ]
    if z < 0.5:
        return np.pi / (np.sin(np.pi * z) * _lanczos_gamma(1.0 - z))
    z -= 1.0
    x = coeff[0]
    for i in range(1, g + 2):
        x += coeff[i] / (z + i)
    t = z + g + 0.5
    return np.sqrt(2 * np.pi) * t ** (z + 0.5) * np.exp(-t) * x


@dataclass
class GEVFit:
    """Result of fitting a GEV distribution to block maxima."""

    distribution: GEVDistribution
    n_blocks: int
    block_size: int | None = None

    def return_level(self, period: np.ndarray) -> np.ndarray:
        return self.distribution.return_level(period)


def fit_gev(samples: np.ndarray, block_size: int | None = None) -> GEVFit:
    """Fit a GEV distribution to a sample of block maxima by L-moments."""
    values = np.asarray(samples, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size < 3:
        raise ValueError("At least 3 finite samples are required for a GEV fit")
    loc, scale, tau3 = _l_moments(values)
    mu, sigma, k = _gev_param_from_lmoments(loc, scale, tau3)
    if sigma <= 0:
        raise ValueError("Estimated GEV scale is not positive")
    return GEVFit(
        distribution=GEVDistribution(loc=mu, scale=sigma, shape=k),
        n_blocks=int(values.size),
        block_size=block_size,
    )


def return_level_of_probability(dist: GEVDistribution, p: np.ndarray) -> np.ndarray:
    """Return level associated with non-exceedance probability *p*."""
    return dist.quantile(p)


def return_level(dist: GEVDistribution, period: np.ndarray) -> np.ndarray:
    """Return level for an average return period (in the time unit of blocks).

    A period of 100 corresponds to the level exceeded on average once per 100
    blocks; its non-exceedance probability is ``1 - 1/period``.
    """
    period = np.asarray(period, dtype=np.float64)
    if np.any(period < 1.0):
        raise ValueError("Return period must be at least 1")
    p = 1.0 - 1.0 / period
    return dist.quantile(p)


def return_period(dist: GEVDistribution, level: np.ndarray) -> np.ndarray:
    """Average return period (blocks) for a given extreme level."""
    level = np.asarray(level, dtype=np.float64)
    p = dist.cdf(level)
    with np.errstate(divide="ignore"):
        return np.where(p < 1.0, 1.0 / (1.0 - p), np.inf)


def return_period_of_level(dist: GEVDistribution, level: np.ndarray) -> np.ndarray:
    """Alias of :func:`return_period` for a single level."""
    return return_period(dist, level)


__all__ = [
    "GEVDistribution",
    "GEVFit",
    "fit_gev",
    "gevcdf",
    "return_level",
    "return_period",
    "return_period_of_level",
]
