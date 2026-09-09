"""Raster grid data model with geographic projection support.

A ``RasterLayer`` is a geographic raster — a 2D (single band) or 3D
(``(nband, ny, nx)``) numeric array aligned to a regular latitude/longitude
(plate carrée) grid. It adds geospatial metadata (resolution, coordinate
reference system / EPSG code, geotransform origin) and provides convenient
accessors for pixel coordinates and geographic extent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Common EPSG codes used across the toolkit.
EPSG_WGS84 = 4326
EPSG_MERCATOR = 3857
EPSG_UTM_23S = 32723


@dataclass(frozen=True)
class CRS:
    """A coordinate reference system identifier (EPSG code + optional name)."""

    epsg: int = EPSG_WGS84
    name: str | None = None

    @property
    def is_geographic(self) -> bool:
        """True for latitude/longitude (angular) coordinate systems."""
        return self.epsg == EPSG_WGS84


@dataclass
class RasterLayer:
    """A geospatial raster with regular lat/lon grid and projection info."""

    data: np.ndarray
    lats: np.ndarray
    lons: np.ndarray
    name: str = "layer"
    crs: CRS = CRS()
    nodata: float | None = None
    units: str = ""
    transform: tuple[float, float, float, float, float, float] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.data = np.asarray(self.data, dtype=np.float32)
        self.lats = np.asarray(self.lats, dtype=np.float64)
        self.lons = np.asarray(self.lons, dtype=np.float64)
        if self.data.ndim == 2:
            self.data = self.data[np.newaxis, ...]  # promote single band
        if self.data.ndim != 3:
            raise ValueError(f"RasterLayer data must be 2D or 3D, got ndim={self.data.ndim}")

        ny, nx = self.lats.shape[0], self.lons.shape[0]
        if self.data.shape[-2:] != (ny, nx):
            raise ValueError("Raster data spatial dims must match lat/lon arrays")

    @property
    def nbands(self) -> int:
        return self.data.shape[0]

    @property
    def nx(self) -> int:
        return self.lons.shape[0]

    @property
    def ny(self) -> int:
        return self.lats.shape[0]

    @property
    def shape(self) -> tuple[int, int]:
        return (self.ny, self.nx)

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """(lon_min, lon_max, lat_min, lat_max)."""
        return (
            float(self.lons.min()),
            float(self.lons.max()),
            float(self.lats.min()),
            float(self.lats.max()),
        )

    @property
    def res_lat(self) -> float:
        if self.ny < 2:
            return float("nan")
        return float(np.abs(np.diff(self.lats)).mean())

    @property
    def res_lon(self) -> float:
        if self.nx < 2:
            return float("nan")
        return float(np.abs(np.diff(self.lons)).mean())

    def band(self, index: int) -> np.ndarray:
        """Return a single band as a 2D array."""
        return np.asarray(self.data[index])

    def set_band(self, index: int, values: np.ndarray) -> None:
        self.data[index] = values

    def copy(self) -> RasterLayer:
        return RasterLayer(
            data=self.data.copy(),
            lats=self.lats.copy(),
            lons=self.lons.copy(),
            name=self.name,
            crs=self.crs,
            nodata=self.nodata,
            units=self.units,
            transform=self.transform,
            meta=dict(self.meta),
        )

    def pixel_nearest(self, lat: float, lon: float) -> tuple[int, int]:
        """Return (row, col) of the nearest pixel to a lat/lon point."""
        row = int(np.abs(self.lats - float(lat)).argmin())
        col = int(np.abs(self.lons - float(lon)).argmin())
        return row, col

    def value_at(self, lat: float, lon: float, band: int = 0) -> float:
        row, col = self.pixel_nearest(lat, lon)
        return float(self.data[band, row, col])

    def as_masked_array(self, band: int = 0) -> np.ma.MaskedArray:
        """Return a numpy masked array, masking nodata and NaN values."""
        arr = np.asarray(self.data[band])
        mask = np.isnan(arr)
        if self.nodata is not None and np.isfinite(self.nodata):
            mask |= np.isclose(arr, self.nodata)
        return np.ma.masked_array(arr, mask=mask)

    def to_point_cloud(self, band: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Flatten a band into (lats, lons, values) point tuples."""
        arr = self.data[band]
        arr = np.ma.masked_invalid(arr) if np.issubdtype(arr.dtype, np.floating) else arr
        lats2, lons2 = np.meshgrid(self.lats, self.lons, indexing="ij")
        mask = np.isnan(arr) if hasattr(arr, "mask") is False else ~arr.mask
        if isinstance(mask, bool):
            mask = ~np.isnan(arr)
        return lats2[mask], lons2[mask], arr[mask]

    def summary(self) -> dict[str, Any]:
        """A compact description of the layer."""
        band0 = np.asarray(self.data[0])
        valid = band0[np.isfinite(band0)]
        return {
            "name": self.name,
            "nbands": self.nbands,
            "shape": list(self.shape),
            "crs": self.crs.epsg,
            "extent": list(self.extent),
            "dtype": str(band0.dtype),
            "min": float(valid.min()) if valid.size else None,
            "max": float(valid.max()) if valid.size else None,
            "mean": float(valid.mean()) if valid.size else None,
        }
