"""Radar reflectivity conversions and rainfall estimation (Z-R relations)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from barograph.raster.layer import RasterLayer

_MARSHALL_PALMER_A = 200.0
_MARSHALL_PALMER_B = 1.6


class Reflectivity:
    """Convert radar reflectivity (dBZ) to rainfall rate using Z-R relations."""

    def __init__(
        self,
        a: float = _MARSHALL_PALMER_A,
        b: float = _MARSHALL_PALMER_B,
    ):
        self.a = a
        self.b = b

    def z_to_linear(self, dbz: np.ndarray) -> np.ndarray:
        """Convert dBZ to linear reflectivity Z = 10^(dBZ/10)."""
        return 10.0 ** (np.asarray(dbz) / 10.0)

    def linear_to_z(self, z: np.ndarray) -> np.ndarray:
        return 10.0 * np.log10(np.maximum(np.asarray(z), 1e-12))

    def rainfall_rate(self, dbz: np.ndarray) -> np.ndarray:
        """Rainfall rate (mm/h) from dBZ via Z = a * R^b."""
        z = self.z_to_linear(dbz)
        r = (z / self.a) ** (1.0 / self.b)
        return np.where(np.asarray(dbz) <= 0, 0.0, r)

    def accumulated(self, rate: np.ndarray, minutes: float) -> np.ndarray:
        """Accumulated precipitation (mm) over a period from a steady rate."""
        return np.asarray(rate) * (minutes / 60.0)

    def attenuation(self, dbz: np.ndarray, range_km: np.ndarray) -> np.ndarray:
        """Simple two-way attenuation estimate along range."""
        km_per_px = 1.0
        # cumulative sum approximates path-integrated attenuation
        z_lin = self.z_to_linear(np.asarray(dbz))
        _ = range_km
        atten = np.cumsum(z_lin, axis=-1)[..., -1] * (km_per_px / 1e8)
        return np.log10(np.maximum(atten, 1e-12)) * 10.0

    def to_raster(self, dbz_layer: RasterLayer) -> RasterLayer:
        """Produce a rainfall-rate ``RasterLayer`` from a dBZ layer."""
        rate = self.rainfall_rate(dbz_layer.band(0))
        return RasterLayer(
            data=rate[np.newaxis, ...],
            lats=dbz_layer.lats,
            lons=dbz_layer.lons,
            name="rainfall_rate",
            crs=dbz_layer.crs,
            units="mm/h",
            meta={**dbz_layer.meta, "zr_a": self.a, "zr_b": self.b},
        )


class ZRRelation:
    """Configurable Z-R relation with pluggable coefficient lookup."""

    def __init__(
        self,
        coefficient_fn: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]] | None = None,
    ):
        self._fn = coefficient_fn

    def rainfall_rate(self, dbz: np.ndarray) -> np.ndarray:
        dbz = np.asarray(dbz)
        if self._fn is None:
            a, b = (
                np.full_like(dbz, _MARSHALL_PALMER_A, dtype=float),
                np.full_like(dbz, _MARSHALL_PALMER_B, dtype=float),
            )
        else:
            a, b = self._fn(dbz)
            a = np.broadcast_to(a, dbz.shape)
            b = np.broadcast_to(b, dbz.shape)
        z = 10.0 ** (dbz / 10.0)
        r = (z / a) ** (1.0 / b)
        return np.where(dbz <= 0, 0.0, r)
