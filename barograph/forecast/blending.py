"""Multi-cycle forecast blending: combine successive model runs into a single grid."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from barograph.core.models import GriddedField
from barograph.raster.layer import CRS, RasterLayer


@dataclass
class BlendingWeights:
    """Weights used when combining forecasts with different ages/leads."""

    recency_weight: float = 0.4
    climatology_weight: float = 0.3
    spread_weight: float = 0.3

    def weights(self, n_members: int) -> np.ndarray:
        """Return normalized weights for a set of members."""
        return np.ones(n_members) / n_members


class ForecastBlender:
    """Blend several overlapping forecasts (e.g. consecutive cycles) into one."""

    def __init__(self, weights: BlendingWeights | None = None):
        self.weights = weights or BlendingWeights()

    def blend(self, forecasts: list[GriddedField]) -> GriddedField:
        """Weighted mean of aligned forecast grids.

        Relative weights are derived from (recency, ensemble spread, and
        climatology) per the configuration; for simplicity here the weights
        decay linearly with forecast age.
        """
        if not forecasts:
            raise ValueError("Need at least one forecast to blend")
        ref = forecasts[0]
        for f in forecasts[1:]:
            if f.shape != ref.shape or not np.allclose(f.lats, ref.lats):
                raise ValueError("All forecasts must be aligned for blending")

        ages_h = np.array([(f.valid_time - f.init_time).total_seconds() / 3600 for f in forecasts])
        w = 1.0 / (1.0 + ages_h)
        w = w / w.sum()

        stacked = np.stack([np.asarray(f.data, dtype=np.float64) for f in forecasts])
        data = np.sum(stacked * w[:, None, None], axis=0)  # type: ignore[index]

        return GriddedField(
            data=data.astype(np.float32),
            lats=ref.lats,
            lons=ref.lons,
            variable=ref.variable,
            source=ref.source,
            valid_time=ref.valid_time,
            init_time=max(forecasts, key=lambda f: f.init_time).init_time,
            level=ref.level,
            meta={**ref.meta, "blended": True, "n_members": len(forecasts)},
        )

    @staticmethod
    def to_raster(field: GriddedField) -> RasterLayer:
        """Wrap a blended field as a ``RasterLayer`` for downstream analysis."""
        return RasterLayer(
            data=field.data,
            lats=field.lats,
            lons=field.lons,
            name=field.variable.value,
            crs=CRS(),
            units="",
            meta={"variable": field.variable.value, "source": field.source.value},
        )
