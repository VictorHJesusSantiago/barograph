"""Quantile Mapping (QM) post-processing."""

from __future__ import annotations

import numpy as np

from barograph.core.models import GriddedField


class QuantileMapper:
    """Empirical quantile or quantile mapping bias correction.

    Fits CDFs of the model and observation reference (either climatology of
    the same variable or a high-resolution reference), then maps each forecast
    value through model-CDF -> observed-CDF.
    """

    def __init__(
        self,
        n_bins: int = 100,
        method: str = "empirical",  # "empirical", "parametric_matrix"
        parametric_family: str = "gamma",  # for precipitation
        tail_extrapolation: str = "constant",
    ):
        self.n_bins = n_bins
        self.method = method
        self.parametric_family = parametric_family
        self.tail_extrapolation = tail_extrapolation

        self._model_quantiles: np.ndarray | None = None
        self._obs_quantiles: np.ndarray | None = None
        self._quantile_levels: np.ndarray | None = None
        self._fitted = False

    def fit(
        self,
        model_data: np.ndarray,
        obs_data: np.ndarray,
    ) -> QuantileMapper:
        """Fit the mapping from paired model and observation samples.

        Args:
            model_data: (n_samples*spatial,) or (n_samples, ...) flattened model.
            obs_data: matching observed/reference values.
        """
        model_data = np.asarray(model_data, dtype=np.float64).ravel()
        obs_data = np.asarray(obs_data, dtype=np.float64).ravel()

        valid = ~(np.isnan(model_data) | np.isnan(obs_data))
        if valid.sum() < 2:
            raise ValueError("Need at least 2 valid paired samples to fit QM")

        model_data = model_data[valid]
        obs_data = obs_data[valid]

        self._quantile_levels = np.linspace(
            1.0 / (self.n_bins + 1), 1.0 - 1.0 / (self.n_bins + 1), self.n_bins
        )

        self._model_quantiles = np.quantile(model_data, self._quantile_levels)
        self._obs_quantiles = np.quantile(obs_data, self._quantile_levels)

        self._fitted = True
        return self

    def transform_data(self, model_data: np.ndarray) -> np.ndarray:
        """Apply the fitted bias correction."""

        if not self._fitted:
            raise RuntimeError("QuantileMapper must be fit before transform.")

        model_data = np.asarray(model_data, dtype=np.float64)
        flat = model_data.ravel()

        # Map each model value to its empirical quantile, then to obs value
        mapped = np.empty_like(flat)

        for k, val in enumerate(flat):
            mapped[k] = self._single_map(val)

        return mapped.reshape(model_data.shape)

    def transform(self, field: GriddedField) -> GriddedField:
        """Apply QM to a gridded field."""
        new_data = self.transform_data(field.data)
        return GriddedField(
            data=new_data.astype(np.float32),
            lats=field.lats,
            lons=field.lons,
            variable=field.variable,
            source=field.source,
            valid_time=field.valid_time,
            init_time=field.init_time,
            level=field.level,
            meta={**field.meta, "postprocessing": "quantile_mapping"},
        )

    def _single_map(self, value: float) -> float:
        """Map a single value through the fitted quantile transforms."""
        q_levels = self._quantile_levels
        model_q = self._model_quantiles
        obs_q = self._obs_quantiles

        if value <= model_q[0]:
            tau = 0.0
        elif value >= model_q[-1]:
            tau = 1.0
        else:
            tau = float(np.interp(value, model_q, q_levels))

        mapped = float(np.interp(tau, q_levels, obs_q))

        # Tail extrapolation
        if self.tail_extrapolation == "constant":
            if value < model_q[0]:
                mapped = obs_q[0] + (value - model_q[0])
            elif value > model_q[-1]:
                mapped = obs_q[-1] + (value - model_q[-1])

        return mapped

    def inverse_transform(self, corrected_value: float) -> float:
        """Inverse mapping (obs-space back to model-space) if needed."""
        q_levels = self._quantile_levels
        tau = float(np.interp(corrected_value, self._obs_quantiles, q_levels))
        return float(np.interp(tau, q_levels, self._model_quantiles))
