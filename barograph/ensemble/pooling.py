"""Ensemble pooling and distribution estimation."""

from __future__ import annotations

import numpy as np


class EnsemblePooler:
    """Convert raw ensemble members into a probabilistic distribution.

    Supports parametric fitting (normal, truncated_normal) and non-parametric
    empirical CDF pooling.
    """

    def __init__(
        self,
        distribution: str = "normal",
        method: str = "parametric",
        n_quantiles: int = 1000,
    ):
        if distribution not in ("normal", "truncated_normal", "lognormal"):
            raise ValueError(f"Unsupported distribution: {distribution}")
        if method not in ("parametric", "empirical", "kernel"):
            raise ValueError(f"Unsupported method: {method}")
        self.distribution = distribution
        self.method = method
        self.n_quantiles = n_quantiles

    def fit_members(self, members: np.ndarray, axis: int = 0) -> dict[str, np.ndarray]:
        """Fit distribution parameters across members.

        Args:
            members: Array of shape (n_members, ...).
            axis: The member axis.

        Returns:
            dict with arrays of 'mean', 'std', and optionally quantiles.
        """
        mean = np.nanmean(members, axis=axis)
        std = np.nanstd(members, axis=axis)
        std = np.where(std <= 0, np.finfo(float).eps, std)

        result = {"mean": mean, "std": std}

        if self.method == "empirical":
            sorted_members = np.sort(members, axis=axis)
            quantiles = np.linspace(
                1.0 / (len(sorted_members) + 1),
                1.0 - 1.0 / (len(sorted_members) + 1),
                self.n_quantiles,
            )
            result["quantiles"] = quantiles
            result["sorted_members"] = sorted_members

        return result

    def quantile_function(
        self,
        params: dict[str, np.ndarray],
        probs: np.ndarray,
    ) -> np.ndarray:
        """Evaluate the quantile (inverse CDF) at given probabilities."""
        if self.method == "empirical" and "sorted_members" in params:
            sorted_members = params["sorted_members"]
            emp_quantiles = np.linspace(
                1.0 / (len(sorted_members) + 1),
                1.0 - 1.0 / (len(sorted_members) + 1),
                len(sorted_members),
            )
            out = np.empty((len(probs),) + sorted_members.shape[1:])
            for k, p in enumerate(probs):
                out[k] = np.interp(
                    p, emp_quantiles, sorted_members, left=sorted_members[0],
                    right=sorted_members[-1],
                )
            return out

        from scipy import stats
        mean = params["mean"]
        std = params["std"]

        out = np.empty((len(probs),) + np.shape(mean))
        for k, p in enumerate(probs):
            if self.distribution == "normal":
                out[k] = stats.norm.ppf(p, loc=mean, scale=std)
            elif self.distribution == "lognormal":
                out[k] = stats.lognorm.ppf(p, s=std, scale=np.exp(mean))
            else:
                out[k] = stats.truncnorm.ppf(
                    p, a=-3, b=3, loc=mean, scale=std
                )
        return out

    def cdf(self, params: dict[str, np.ndarray], x: np.ndarray) -> np.ndarray:
        """Evaluate the CDF at given values."""
        from scipy import stats
        mean = params["mean"]
        std = params["std"]

        if self.distribution == "normal":
            return stats.norm.cdf(x, loc=mean, scale=std)
        elif self.distribution == "lognormal":
            return stats.lognorm.cdf(x, s=std, scale=np.exp(mean))
        else:
            return stats.truncnorm.cdf(x, a=-3, b=3, loc=mean, scale=std)

    def probability_exceed(self, params: dict[str, np.ndarray], threshold: float) -> np.ndarray:
        """Probability that the variable exceeds a threshold."""
        return 1.0 - self.cdf(params, threshold)

    def probability_between(
        self,
        params: dict[str, np.ndarray],
        lower: float,
        upper: float,
    ) -> np.ndarray:
        """Probability the variable falls in [lower, upper]."""
        return self.cdf(params, upper) - self.cdf(params, lower)
