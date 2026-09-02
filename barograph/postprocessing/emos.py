"""Ensemble Model Output Statistics (EMOS).

Implements the classical NGR (Non-homogeneous Gaussian Regression) approach
(Gneiting et al. 2005): a parametric distribution whose location is a linear
function of the ensemble mean and whose scale is a linear function of the
ensemble spread. Scipy optimization is used to fit parameters by minimizing CRPS.
"""

from __future__ import annotations

import numpy as np
from scipy import optimize, stats
from scipy.special import erf


class EMOSCalibrator:
    """Calibrate ensemble forecasts using Non-homogeneous Gaussian Regression.

    Fits location a1 + a2 * ens_mean and scale b1 + b2 * ens_var (or b1 + b2*std).
    Parameters are fitted separately per grid point or station.
    """

    def __init__(
        self,
        distribution: str = "normal",
        optimize_crps: bool = True,
        tolerance: float = 1e-6,
        max_iter: int = 1000,
    ):
        if distribution not in ("normal", "truncated_normal"):
            raise ValueError(f"Unsupported distribution: {distribution}")
        self.distribution = distribution
        self.optimize_crps = optimize_crps
        self.tolerance = tolerance
        self.max_iter = max_iter
        self._params: np.ndarray | None = None
        self._fitted = False
        self._spatial_dim: tuple[int, ...] | None = None

    def _nps(self, z):
        """Normalized CRPS contribution for a single scalar ensemble.

        z is the standardized ensemble value assuming location = ens_mean.
        This helper only enables a closed-form gradient where constants apply.
        """
        return z * erf(z / np.sqrt(2)) - np.sqrt(2 / np.pi) * (1 - np.exp(-z**2 / 2))

    def crps_normal(
        self,
        params: np.ndarray,
        ens_mean: np.ndarray,
        ens_var: np.ndarray,
        obs: np.ndarray,
    ) -> float:
        """CRPS of ensemble (mean, var) against observations with EMOS params."""
        a1, a2, b1, b2 = params
        # enforce positive scale via non-negativity on variance contributions
        scale2 = b1 + b2 * ens_var
        scale2 = np.clip(scale2, 1e-6, None)
        scale = np.sqrt(scale2)

        mu = a1 + a2 * ens_mean
        z = (obs - mu) / scale
        crps = scale * (z * (2 * stats.norm.cdf(z) - 1)
                        + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
        return float(np.mean(crps))

    def fit(
        self,
        ens_mean: np.ndarray,
        ens_var: np.ndarray,
        obs: np.ndarray,
    ) -> EMOSCalibrator:
        """Fit EMOS parameters.

        Args:
            ens_mean: (n_samples,) or (n_samples, ny, nx) ensemble mean over training.
            ens_var: ensemble variance over training.
            obs: observations.
        """
        ens_mean = np.asarray(ens_mean, dtype=np.float64)
        ens_var = np.asarray(ens_var, dtype=np.float64)
        obs = np.asarray(obs, dtype=np.float64)

        if ens_mean.ndim == 1:
            ens_mean = ens_mean[:, None]
            ens_var = ens_var[:, None]
            obs = obs[:, None]
            self._spatial_dim = None
        else:
            self._spatial_dim = ens_mean.shape[1:]

        flat_obs = obs.reshape(obs.shape[0], -1)
        flat_mean = ens_mean.reshape(ens_mean.shape[0], -1)
        flat_var = ens_var.reshape(ens_var.shape[0], -1)

        self._params = np.empty((4,) + flat_mean.shape[1:], dtype=np.float64)

        for k in range(flat_mean.shape[1]):
            m = flat_mean[:, k]
            v = flat_var[:, k]
            o = flat_obs[:, k]

            valid = ~(np.isnan(m) | np.isnan(v) | np.isnan(o))
            if valid.sum() < 5:
                self._params[:, k] = np.nan
                continue

            p0 = np.array([0.0, 1.0, 0.0, 1.0])

            def loss(p):
                return self.crps_normal(p, m[valid], v[valid], o[valid])

            result = optimize.minimize(
                loss, p0, method="Nelder-Mead",
                options={"maxiter": self.max_iter,
                         "xatol": self.tolerance, "fatol": self.tolerance},
            )
            self._params[:, k] = result.x

        self._fitted = True
        return self

    def predict_distribution(
        self,
        ens_mean: np.ndarray,
        ens_var: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return calibrated forecast location and scale arrays."""
        if not self._fitted:
            raise RuntimeError("Must fit before predict.")
        if self._params is None:
            raise RuntimeError("EMOS calibration parameters are unavailable.")

        ens_mean = np.asarray(ens_mean, dtype=np.float64)
        ens_var = np.asarray(ens_var, dtype=np.float64)
        flat_mean = ens_mean.reshape(-1)
        flat_var = ens_var.reshape(-1)
        flat_params = self._params.reshape(4, -1)

        loc = np.empty_like(flat_mean)
        scale2 = np.empty_like(flat_mean)

        # If params have a single spatial column (fit was scalar/site-level),
        # broadcast them to all requested points.
        if flat_params.shape[1] == 1:
            p = flat_params[:, 0]
            if np.isnan(p).any():
                loc[:] = flat_mean
                scale2[:] = np.maximum(flat_var, 1e-6)
            else:
                loc[:] = p[0] + p[1] * flat_mean
                scale2[:] = np.maximum(p[2] + p[3] * flat_var, 1e-6)
        else:
            for k in range(len(flat_mean)):
                p = flat_params[:, k]
                if np.isnan(p).any():
                    loc[k] = flat_mean[k]
                    scale2[k] = max(flat_var[k], 1e-6)
                    continue
                loc[k] = p[0] + p[1] * flat_mean[k]
                s2 = p[2] + p[3] * flat_var[k]
                scale2[k] = max(s2, 1e-6)

        loc = loc.reshape(ens_mean.shape)
        scale = np.sqrt(scale2.reshape(ens_mean.shape))
        return loc, scale

    def predict_quantiles(
        self,
        ens_mean: np.ndarray,
        ens_var: np.ndarray,
        quantiles: np.ndarray,
    ) -> np.ndarray:
        """Predict the requested distributional quantiles."""
        loc, scale = self.predict_distribution(ens_mean, ens_var)
        out = np.empty((len(quantiles),) + loc.shape)
        for k, q in enumerate(quantiles):
            out[k] = loc + scale * stats.norm.ppf(q)
        return out

    def predict_probability_above(
        self,
        ens_mean: np.ndarray,
        ens_var: np.ndarray,
        threshold: float,
    ) -> np.ndarray:
        """Probability of exceeding a threshold under the calibrated distribution."""
        loc, scale = self.predict_distribution(ens_mean, ens_var)
        z = (threshold - loc) / scale
        return 1.0 - stats.norm.cdf(z)

    def crps_score(
        self,
        ens_mean: np.ndarray,
        ens_var: np.ndarray,
        obs: np.ndarray,
    ) -> float:
        """Average CRPS of the calibrated forecast points against obs."""
        loc, scale = self.predict_distribution(ens_mean, ens_var)
        z = (obs - loc) / scale
        crps = scale * (z * (2 * stats.norm.cdf(z) - 1)
                        + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
        return float(np.mean(crps))
