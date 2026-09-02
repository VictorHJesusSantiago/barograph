"""Bias correction downscaling via anomaly / additive and multiplicative factors."""

from __future__ import annotations

import numpy as np

from barograph.core.models import GriddedField
from barograph.downscaling.base import BaseDownscaler


class BiasCorrectionDownscaler(BaseDownscaler):
    """Simple additive / multiplicative bias correction downscaling.

    Computes per-grid-cell bias between coarse and fine climatology and
    corrects forecasts by removing the mean (additive) and/or scaling the
    variance (multiplicative) of the coarse distribution toward the fine one.
    """

    name = "bias_correction"

    def __init__(self, mode: str = "additive"):
        if mode not in ("additive", "multiplicative", "hybrid"):
            raise ValueError(f"Unknown correction mode: {mode}")
        self.mode = mode
        self._bias: np.ndarray | None = None
        self._scale: np.ndarray | None = None
        self._fine_mean: np.ndarray | None = None
        self._fitted = False

    def fit(
        self,
        coarse: list[GriddedField],
        fine: list[GriddedField],
    ) -> BiasCorrectionDownscaler:
        self.validate_shapes(coarse, fine)

        c_arr, _, _ = self._aggregate_arrays(coarse)
        f_arr, _, _ = self._aggregate_arrays(fine)

        c_mean = np.nanmean(c_arr, axis=0)
        f_mean = np.nanmean(f_arr, axis=0)
        c_std = np.nanstd(c_arr, axis=0)
        f_std = np.nanstd(f_arr, axis=0)

        self._bias = f_mean - c_mean
        self._fine_mean = f_mean

        with np.errstate(divide="ignore", invalid="ignore"):
            self._scale = np.where(c_std > 1e-10, f_std / c_std, 1.0)
            self._scale = np.nan_to_num(self._scale, nan=1.0, posinf=1.0, neginf=1.0)

        self._fitted = True
        return self

    def transform(self, coarse: GriddedField) -> GriddedField:
        if not self._fitted:
            raise RuntimeError("BiasCorrectionDownscaler must be fit before transform.")

        data = coarse.data.astype(np.float32)
        if self.mode == "additive":
            corrected = data + self._bias
        elif self.mode == "multiplicative":
            corrected = data * self._scale
        else:
            corrected = (data - np.nanmean(data)) * self._scale + self._fine_mean

        return GriddedField(
            data=corrected,
            lats=coarse.lats,
            lons=coarse.lons,
            variable=coarse.variable,
            source=coarse.source,
            valid_time=coarse.valid_time,
            init_time=coarse.init_time,
            level=coarse.level,
            meta={**coarse.meta, "downscaling": self.name, "mode": self.mode},
        )
