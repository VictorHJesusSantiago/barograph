"""Coordinate utilities."""

from __future__ import annotations

import numpy as np

from barograph.core.models import Coordinate


def haversine_distance(coord1: Coordinate, coord2: Coordinate) -> float:
    """Great-circle distance in km between two points."""
    R = 6371.0
    lat1, lon1 = np.radians(coord1.latitude), np.radians(coord1.longitude)
    lat2, lon2 = np.radians(coord2.latitude), np.radians(coord2.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def find_nearest_grid_point(
    target: Coordinate,
    lats: np.ndarray,
    lons: np.ndarray,
) -> tuple[int, int]:
    """Find indices of nearest grid point to target coordinate."""
    lat_diff = np.abs(lats - target.latitude)
    lon_diff = np.abs(lons - target.longitude)
    combined = lat_diff[:, np.newaxis] + lon_diff[np.newaxis, :]
    idx = np.unravel_index(np.argmin(combined), combined.shape)
    return int(idx[0]), int(idx[1])


def extract_point_series(
    data: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    target: Coordinate,
) -> np.ndarray:
    """Extract time series at nearest grid point."""
    i, j = find_nearest_grid_point(target, lats, lons)
    if data.ndim == 2:
        return data[i, j]
    elif data.ndim == 3:
        return data[:, i, j]
    elif data.ndim == 4:
        return data[:, :, i, j]
    return data[..., i, j]


def reproject_field(
    data: np.ndarray,
    src_lats: np.ndarray,
    src_lons: np.ndarray,
    dst_lats: np.ndarray,
    dst_lons: np.ndarray,
    method: str = "linear",
) -> np.ndarray:
    """Reproject a gridded field to a new grid using interpolation."""
    from scipy.interpolate import RegularGridInterpolator

    src_lats_sorted = np.sort(src_lats)
    src_lons_sorted = np.sort(src_lons)

    if not np.allclose(src_lats, src_lats_sorted):
        if src_lats[0] > src_lats[-1]:
            data = data[::-1]
        src_lats = src_lats_sorted

    if not np.allclose(src_lons, src_lons_sorted):
        if src_lons[0] > src_lons[-1]:
            data = data[..., ::-1]
        src_lons = src_lons_sorted

    if data.ndim == 2:
        interp = RegularGridInterpolator(
            (src_lats, src_lons), data, method=method, bounds_error=False
        )
        dst_grid = np.column_stack([dst_lats.ravel(), dst_lons.ravel()])
        result = interp(dst_grid).reshape(dst_lats.shape)
    else:
        raise ValueError("Only 2D reprojection is currently supported")

    return result


def create_grid(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    resolution_km: float = 25.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a regular latitude/longitude grid."""
    deg_per_km = 1.0 / 111.0
    lat_step = resolution_km * deg_per_km
    lon_step = resolution_km * deg_per_km / np.cos(np.radians((lat_min + lat_max) / 2))

    lats = np.arange(lat_min, lat_max + lat_step, lat_step)
    lons = np.arange(lon_min, lon_max + lon_step, lon_step)
    return lats, lons


def clip_to_bbox(
    lats: np.ndarray,
    lons: np.ndarray,
    data: np.ndarray,
    bbox: tuple[float, float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Clip grid and data to bounding box (lat_min, lat_max, lon_min, lon_max)."""
    lat_min, lat_max, lon_min, lon_max = bbox
    lat_mask = (lats >= lat_min) & (lats <= lat_max)
    lon_mask = (lons >= lon_min) & (lons <= lon_max)

    clipped_lats = lats[lat_mask]
    clipped_lons = lons[lon_mask]

    if data.ndim == 2:
        clipped_data = data[np.ix_(lat_mask, lon_mask)]
    elif data.ndim == 3:
        clipped_data = data[:, np.ix_(lat_mask, lon_mask)]
    else:
        clipped_data = data

    return clipped_lats, clipped_lons, clipped_data
