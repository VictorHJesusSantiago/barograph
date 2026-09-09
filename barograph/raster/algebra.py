"""Raster algebra: band math, statistics, resampling and rasterization.

Provides elementwise operations between rasters (matching grids), spatial
statistics, nearest-neighbour resampling to a target grid, and conversion of
point values to a raster grid.
"""

from __future__ import annotations

import numpy as np

from barograph.raster.layer import RasterLayer


class RasterAlgebra:
    """Operations on one or more aligned ``RasterLayer`` instances."""

    @staticmethod
    def _check_aligned(*layers: RasterLayer) -> None:
        ref_shape = layers[0].data.shape
        ref_lats = layers[0].lats
        ref_lons = layers[0].lons
        for layer in layers[1:]:
            if layer.data.shape != ref_shape:
                raise ValueError(
                    f"Rasters must be aligned: {ref_shape} vs {layer.data.shape}"
                )
            if not np.allclose(layer.lats, ref_lats) or not np.allclose(layer.lons, ref_lons):
                raise ValueError("Rasters must share the same lat/lon grid")

    @staticmethod
    def add(a: RasterLayer, b: RasterLayer) -> RasterLayer:
        RasterAlgebra._check_aligned(a, b)
        return RasterAlgebra._combine(a, b, a.data + b.data, name=f"{a.name}+{b.name}")

    @staticmethod
    def subtract(a: RasterLayer, b: RasterLayer) -> RasterLayer:
        RasterAlgebra._check_aligned(a, b)
        return RasterAlgebra._combine(a, b, a.data - b.data, name=f"{a.name}-{b.name}")

    @staticmethod
    def multiply(a: RasterLayer, b: RasterLayer) -> RasterLayer:
        RasterAlgebra._check_aligned(a, b)
        return RasterAlgebra._combine(a, b, a.data * b.data, name=f"{a.name}*{b.name}")

    @staticmethod
    def divide(a: RasterLayer, b: RasterLayer) -> RasterLayer:
        RasterAlgebra._check_aligned(a, b)
        with np.errstate(divide="ignore", invalid="ignore"):
            result = np.where(b.data == 0, np.nan, a.data / b.data)
        return RasterAlgebra._combine(a, b, result, name=f"{a.name}/{b.name}")

    @staticmethod
    def _combine(
        a: RasterLayer, b: RasterLayer, data: np.ndarray, name: str
    ) -> RasterLayer:
        return RasterLayer(
            data=data,
            lats=a.lats,
            lons=a.lons,
            name=name,
            crs=a.crs,
            nodata=a.nodata,
            meta={**a.meta, **b.meta},
        )

    @staticmethod
    def scale(layer: RasterLayer, factor: float, offset: float = 0.0) -> RasterLayer:
        result = layer.copy()
        result.data = layer.data * factor + offset
        result.name = f"{layer.name}_scaled"
        return result

    @staticmethod
    def mean(a: RasterLayer, b: RasterLayer) -> RasterLayer:
        RasterAlgebra._check_aligned(a, b)
        return RasterAlgebra._combine(a, b, (a.data + b.data) / 2.0, name="mean")

    @staticmethod
    def stack(layers: list[RasterLayer]) -> RasterLayer:
        """Stack multiple single-band layers into a single multi-band layer."""
        if not layers:
            raise ValueError("Need at least one layer")
        RasterAlgebra._check_aligned(*layers)
        data = np.concatenate([layer.data for layer in layers], axis=0)
        return RasterLayer(
            data=data,
            lats=layers[0].lats,
            lons=layers[0].lons,
            name="stack",
            crs=layers[0].crs,
            meta={"bands": [layer.name for layer in layers]},
        )

    @staticmethod
    def stats(layer: RasterLayer, band: int = 0) -> dict[str, float]:
        """Summary statistics for a band, ignoring NaNs."""
        arr = np.asarray(layer.band(band), dtype=np.float64)
        valid = arr[np.isfinite(arr)]
        if valid.size == 0:
            return {"min": np.nan, "max": np.nan, "mean": np.nan, "std": np.nan,
                    "p5": np.nan, "p95": np.nan}
        return {
            "min": float(valid.min()),
            "max": float(valid.max()),
            "mean": float(valid.mean()),
            "std": float(valid.std()),
            "p5": float(np.percentile(valid, 5)),
            "p95": float(np.percentile(valid, 95)),
        }

    @staticmethod
    def resample_nearest(
        layer: RasterLayer, target_lats: np.ndarray, target_lons: np.ndarray
    ) -> RasterLayer:
        """Nearest-neighbour resample to a new regular grid."""
        src_rows = np.searchsorted(layer.lats, target_lats, side="left")
        src_cols = np.searchsorted(layer.lons, target_lons, side="left")
        src_rows = np.clip(src_rows, 0, layer.ny - 1)
        src_cols = np.clip(src_cols, 0, layer.nx - 1)

        out = np.empty((layer.nbands, len(target_lats), len(target_lons)),
                       dtype=np.float32)
        for b in range(layer.nbands):
            out[b] = layer.data[b][np.ix_(src_rows, src_cols)]
        return RasterLayer(
            data=out,
            lats=target_lats.copy(),
            lons=target_lons.copy(),
            name=f"{layer.name}_resampled",
            crs=layer.crs,
            nodata=layer.nodata,
            units=layer.units,
        )

    @staticmethod
    def from_points(
        lats: np.ndarray,
        lons: np.ndarray,
        values: np.ndarray,
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        method: str = "nearest",
        name: str = "points",
    ) -> RasterLayer:
        """Rasterize scattered point values onto a regular grid."""
        from scipy.interpolate import griddata

        if method == "nearest":
            out = griddata(
                (lons, lats), values, (grid_lons[None, :], grid_lats[:, None]),
                method="nearest",
            )
        elif method in ("linear", "cubic"):
            out = griddata(
                (lons, lats), values,
                (np.meshgrid(grid_lons, grid_lats, indexing="xy")[0],
                 np.meshgrid(grid_lons, grid_lats, indexing="xy")[1]),
                method=method,
            )
        else:
            raise ValueError(f"Unsupported method: {method}")

        return RasterLayer(
            data=out[np.newaxis, ...],
            lats=grid_lats,
            lons=grid_lons,
            name=name,
        )
