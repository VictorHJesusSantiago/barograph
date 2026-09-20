"""Masking and boolean algebra for raster layers."""

from __future__ import annotations

import numpy as np

from barograph.raster.layer import RasterLayer


class RasterMasker:
    """Build and apply boolean masks to raster layers."""

    @staticmethod
    def threshold(
        layer: RasterLayer,
        operator: str,
        value: float,
        band: int = 0,
    ) -> np.ndarray:
        """Return a 2D boolean mask from a comparison against a threshold."""
        arr = layer.band(band)
        ops = {
            ">": np.greater,
            ">=": np.greater_equal,
            "<": np.less,
            "<=": np.less_equal,
            "==": np.equal,
            "!=": np.not_equal,
        }
        if operator not in ops:
            raise ValueError(f"Unsupported operator: {operator}")
        return ops[operator](arr, value)

    @staticmethod
    def combine_and(*masks: np.ndarray) -> np.ndarray:
        mask = np.ones_like(masks[0], dtype=bool)
        for m in masks:
            mask &= m.astype(bool)
        return mask

    @staticmethod
    def combine_or(*masks: np.ndarray) -> np.ndarray:
        mask = np.zeros_like(masks[0], dtype=bool)
        for m in masks:
            mask |= m.astype(bool)
        return mask

    @staticmethod
    def invert(mask: np.ndarray) -> np.ndarray:
        return ~mask.astype(bool)

    @staticmethod
    def morphology(mask: np.ndarray, operation: str = "erode", iterations: int = 1) -> np.ndarray:
        """Apply binary morphological opening/closing to smooth a mask."""
        from scipy import ndimage

        if operation in ("erode", "open"):
            mask = ndimage.binary_erosion(mask, iterations=iterations)
        if operation in ("dilate", "close"):
            mask = ndimage.binary_dilation(mask, iterations=iterations)
        return mask

    @staticmethod
    def largest_components(mask: np.ndarray, n: int = 1) -> np.ndarray:
        """Keep only the ``n`` largest connected components of a mask."""
        from scipy import ndimage

        labeled, nlabels = ndimage.label(mask)
        if nlabels == 0:
            return np.zeros_like(mask, dtype=bool)
        sizes = ndimage.sum(mask, labeled, range(1, nlabels + 1))
        order = np.argsort(sizes)[::-1]
        keep = order[:n] + 1
        return np.isin(labeled, keep)

    @staticmethod
    def apply(layer: RasterLayer, mask: np.ndarray, fill: float = np.nan) -> RasterLayer:
        """Return a copy of the layer with masked cells set to ``fill``."""
        result = layer.copy()
        for b in range(result.nbands):
            result.data[b] = np.where(mask.astype(bool), result.data[b], fill)
        return result

    @staticmethod
    def cloud_mask(
        layer: RasterLayer,
        visible_band: int = 0,
        cloud_band: int | None = None,
        threshold: float = 0.4,
        method: str = "threshold",
    ) -> np.ndarray:
        """Estimate a cloud mask.

        With ``method='threshold'`` a cloud-band (or a luminance proxy) above
        ``threshold`` is considered cloudy. With ``method='otsu'`` a simple
        quantile split is used when no cloud band is available.
        """
        if cloud_band is not None:
            score = layer.band(cloud_band)
        else:
            score = layer.band(visible_band)

        if method == "threshold":
            return score >= threshold
        if method == "otsu":
            thresh = float(np.percentile(np.ma.masked_invalid(score), 70))
            return score >= thresh
        raise ValueError(f"Unsupported method: {method}")
