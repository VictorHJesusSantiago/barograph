"""Quantile Delta Transform (QDT) downscaling."""

from __future__ import annotations

import numpy as np

from barograph.core.models import GriddedField
from barograph.downscaling.base import BaseDownscaler


class QDTDownscaler(BaseDownscaler):
    """Quantile Delta Transform statistical downscaling.

    Applies quantile mapping between coarse (NWP) and fine (e.g. ERA5 / station)
    climatology, then adds the forecast perturbation / delta back. This preserves
    the climate-change / forecast signal while correcting the distribution.
    """

    name = "quantile_delta_transform"

    def __init__(self, quantiles: np.ndarray | None = None):
        self.quantiles = (
            np.arange(0.001, 1.0, 0.002) if quantiles is None else quantiles
        )
        self._coarse_quantiles: np.ndarray | None = None
        self._fine_quantiles: np.ndarray | None = None
        self._fitted = False

    def fit(
        self,
        coarse: list[GriddedField],
        fine: list[GriddedField],
    ) -> QDTDownscaler:
        """Fit quantile relationships per grid cell."""
        self.validate_shapes(coarse, fine)

        c_arr, c_lat, c_lon = self._aggregate_arrays(coarse)
        f_arr, f_lat, f_lon = self._aggregate_arrays(fine)

        if c_arr.shape[-2:] != f_arr.shape[-2:]:
            raise ValueError(
                "QDT requires matching grid shapes between coarse and fine "
                f"({c_arr.shape[-2:]} vs {f_arr.shape[-2:]})"
            )

        ny, nx = c_arr.shape[-2:]
        self._coarse_quantiles = np.full(
            (len(self.quantiles), ny, nx), np.nan, dtype=np.float32
        )
        self._fine_quantiles = np.full(
            (len(self.quantiles), ny, nx), np.nan, dtype=np.float32
        )

        for i in range(ny):
            for j in range(nx):
                series_c = c_arr[:, i, j]
                series_f = f_arr[:, i, j]
                valid_c = series_c[~np.isnan(series_c)]
                valid_f = series_f[~np.isnan(series_f)]
                if len(valid_c) < 2 or len(valid_f) < 2:
                    continue
                self._coarse_quantiles[:, i, j] = np.quantile(valid_c, self.quantiles)
                self._fine_quantiles[:, i, j] = np.quantile(valid_f, self.quantiles)

        self._fitted = True
        return self

    def transform(self, coarse: GriddedField) -> GriddedField:
        if not self._fitted:
            raise RuntimeError("QDTDownscaler must be fit before transform.")
        if self._coarse_quantiles is None or self._fine_quantiles is None:
            raise RuntimeError("QDTDownscaler is not fitted.")

        result = np.empty_like(coarse.data, dtype=np.float32)
        ny, nx = coarse.data.shape[-2:]

        for i in range(ny):
            for j in range(nx):
                fc = self._coarse_quantiles[:, i, j]
                ff = self._fine_quantiles[:, i, j]
                if np.isnan(fc).any() or np.isnan(ff).any():
                    result[..., i, j] = coarse.data[..., i, j]
                    continue

                pred = self._transform_cell(coarse.data[..., i, j], fc, ff)
                result[..., i, j] = pred

        return GriddedField(
            data=result,
            lats=coarse.lats,
            lons=coarse.lons,
            variable=coarse.variable,
            source=coarse.source,
            valid_time=coarse.valid_time,
            init_time=coarse.init_time,
            level=coarse.level,
            meta={**coarse.meta, "downscaling": self.name},
        )

    def _transform_cell(
        self,
        pred: np.ndarray,
        qc: np.ndarray,
        qf: np.ndarray,
    ) -> np.ndarray:
        """Transform a single cell time series via CDF-mapping + delta."""
        scalar_input = np.ndim(pred) == 0
        if scalar_input:
            pred = np.array([pred])

        flat = pred.ravel()
        mapped = np.empty_like(flat, dtype=np.float64)

        for k in range(len(flat)):
            val = flat[k]
            # 1) map the forecast value to its quantile in the coarse CDF
            q_pred = float(np.interp(val, qc, self.quantiles))
            # 2) historical fine value at that same quantile (bias correction)
            hist_fine = float(np.interp(q_pred, self.quantiles, qf))
            # 3) coarse reference value at that quantile (what the model predicts)
            coarse_ref = float(np.interp(q_pred, self.quantiles, qc))
            # 4) delta / climate signal of this forecast vs model climatology
            delta = val - coarse_ref
            # 5) corrected = bias-corrected climatology + model signal
            mapped[k] = hist_fine + delta

        if scalar_input:
            return mapped[0]
        return mapped.reshape(pred.shape)
