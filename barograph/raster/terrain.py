"""Terrain analysis for digital elevation models (DEM) encoded as rasters."""

from __future__ import annotations

import numpy as np

from barograph.raster.layer import RasterLayer


class Terrain:
    """Derive terrain parameters from an elevation ``RasterLayer``."""

    @staticmethod
    def slope(dem: RasterLayer) -> np.ndarray:
        """Slope in degrees from a DEM, using central differences."""
        z = dem.band(0).astype(np.float64)
        dzdy = np.gradient(z, axis=0)
        dzdx = np.gradient(z, axis=1)

        # metres per pixel assuming plate carrée at the domain centre latitude
        mean_lat = float(np.mean(dem.lats))
        m_per_deg_lat = 111320.0
        m_per_deg_lon = 111320.0 * np.cos(np.radians(mean_lat))
        res_lat_m = dem.res_lat * m_per_deg_lat
        res_lon_m = dem.res_lon * m_per_deg_lon
        if res_lat_m == 0 or res_lon_m == 0:
            return np.zeros_like(z)

        sx = dzdx / res_lon_m
        sy = dzdy / res_lat_m
        slope = np.degrees(np.arctan(np.sqrt(sx**2 + sy**2)))
        return slope

    @staticmethod
    def aspect(dem: RasterLayer) -> np.ndarray:
        """Aspect (azimuth from north, 0-360) from a DEM."""
        z = dem.band(0).astype(np.float64)
        dzdy = np.gradient(z, axis=0)
        dzdx = np.gradient(z, axis=1)
        aspect = np.degrees(np.arctan2(-dzdx, -dzdy))
        aspect = np.mod(aspect, 360.0)
        return aspect

    @staticmethod
    def curvature(dem: RasterLayer) -> np.ndarray:
        """Profile curvature (second spatial derivative)."""
        z = dem.band(0).astype(np.float64)
        d2zdy2 = np.gradient(np.gradient(z, axis=0), axis=0)
        d2zdx2 = np.gradient(np.gradient(z, axis=1), axis=1)
        return d2zdx2 + d2zdy2

    @staticmethod
    def hillshade(
        dem: RasterLayer,
        azimuth: float = 315.0,
        altitude: float = 45.0,
    ) -> np.ndarray:
        """Standard hillshade value in 0..255 (255 = brightest)."""
        slope = Terrain.slope(dem)
        aspect = Terrain.aspect(dem)

        az_rad = np.radians(azimuth)
        alt_rad = np.radians(altitude)
        slp_rad = np.radians(slope)
        asp_rad = np.radians(aspect)

        shaded = (
            np.sin(alt_rad) * np.cos(slp_rad)
            + np.cos(alt_rad) * np.sin(slp_rad) * np.cos(az_rad - asp_rad)
        )
        shaded = np.clip(shaded, 0, 1)
        return shaded * 255.0

    @staticmethod
    def ruggedness(dem: RasterLayer) -> np.ndarray:
        """Terrain ruggedness (std of elevation in a 3x3 window)."""
        from scipy.ndimage import generic_filter

        z = dem.band(0).astype(np.float64)
        return generic_filter(z, np.nanstd, size=3)

    @staticmethod
    def elevation_stats(dem: RasterLayer) -> dict[str, float]:
        z = dem.band(0).astype(np.float64)
        valid = z[np.isfinite(z)]
        return {
            "min": float(valid.min()) if valid.size else np.nan,
            "max": float(valid.max()) if valid.size else np.nan,
            "mean": float(valid.mean()) if valid.size else np.nan,
            "range": (float(valid.max()) - float(valid.min())) if valid.size else np.nan,
        }
