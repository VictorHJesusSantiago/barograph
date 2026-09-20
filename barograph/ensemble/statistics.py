"""Ensemble statistics: mean, spread, severity indices, percentile maps."""

from __future__ import annotations

import numpy as np

from barograph.core.models import EnsembleForecast, GriddedField


class EnsembleStatistics:
    """Compute standard ensemble products."""

    @staticmethod
    def ensemble_mean(ens: EnsembleForecast) -> GriddedField:
        return ens.ensemble_mean

    @staticmethod
    def ensemble_spread(ens: EnsembleForecast) -> GriddedField:
        """Ensemble spread (std across members)."""
        return ens.ensemble_spread

    @staticmethod
    def interquartile_range(ens: EnsembleForecast) -> GriddedField:
        """Interquartile range as spread metric robust to outliers."""
        arr = ens.member_array
        q25 = np.percentile(arr, 25, axis=0)
        q75 = np.percentile(arr, 75, axis=0)
        data = q75 - q25
        ref = ens.members[0]
        return GriddedField(
            data=data,
            lats=ref.lats,
            lons=ref.lons,
            variable=ens.variable,
            source=ens.source,
            valid_time=ens.valid_time,
            init_time=ens.init_time,
        )

    @staticmethod
    def member_rank(ens: EnsembleForecast, observation: np.ndarray) -> np.ndarray:
        """Rank of an observation relative to the ensemble (for rank histograms)."""
        arr = ens.member_array
        return np.sum(arr < observation, axis=0).astype(np.float32)

    @staticmethod
    def ensemble_percentile(ens: EnsembleForecast, percentile: float) -> GriddedField:
        """Field of a specific percentile across members."""
        arr = ens.member_array
        data = np.percentile(arr, percentile, axis=0)
        ref = ens.members[0]
        return GriddedField(
            data=data,
            lats=ref.lats,
            lons=ref.lons,
            variable=ens.variable,
            source=ens.source,
            valid_time=ens.valid_time,
            init_time=ens.init_time,
        )

    @staticmethod
    def probability_above(ens: EnsembleForecast, threshold: float) -> GriddedField:
        """Probability of exceeding a threshold, computed empirically."""
        arr = ens.member_array
        data = np.mean(arr > threshold, axis=0)
        ref = ens.members[0]
        return GriddedField(
            data=data,
            lats=ref.lats,
            lons=ref.lons,
            variable=ens.variable,
            source=ens.source,
            valid_time=ens.valid_time,
            init_time=ens.init_time,
        )

    @staticmethod
    def mean_of_extremes(ens: EnsembleForecast) -> GriddedField:
        """Mean of the most extreme members (perturbed members)."""
        arr = ens.member_array
        data = np.nanmax(arr, axis=0)
        ref = ens.members[0]
        return GriddedField(
            data=data,
            lats=ref.lats,
            lons=ref.lons,
            variable=ens.variable,
            source=ens.source,
            valid_time=ens.valid_time,
            init_time=ens.init_time,
        )

    @staticmethod
    def exceedance_fraction(ens: EnsembleForecast, threshold: float) -> float:
        """Fraction of the domain exceeding threshold (single scalar)."""
        return float(np.mean(ens.member_array > threshold))

    @staticmethod
    def spread_error_correlation(
        ens: EnsembleForecast, obs_fields: list[GriddedField]
    ) -> tuple[float, float]:
        """Spatial correlation between ensemble spread and absolute error."""
        if len(obs_fields) == 0:
            raise ValueError("Need at least one observation field")

        spread_sum = np.zeros_like(ens.members[0].data)
        err_sum = np.zeros_like(spread_sum)
        ref = ens.members[0]

        count = 0
        for obs in obs_fields:
            if obs.shape != ref.shape:
                continue
            mean_pred = ens.ensemble_mean.data
            spread = np.std(ens.member_array, axis=0)
            spread_sum += spread
            err_sum += np.abs(mean_pred - obs.data)
            count += 1

        if count == 0:
            return 0.0, 0.0

        spread_mean = spread_sum / count
        err_mean = err_sum / count

        spread_std = np.std(spread_mean)
        err_std = np.std(err_mean)
        if spread_std == 0 or err_std == 0:
            return 0.0, float(np.mean(spread_mean * err_mean))

        corr = np.corrcoef(spread_mean.ravel(), err_mean.ravel())[0, 1]
        return float(corr), float(np.mean(spread_mean * err_mean))
