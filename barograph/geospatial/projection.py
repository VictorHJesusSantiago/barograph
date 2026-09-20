"""Distance and grid helpers used across the geospatial module."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

_EARTH_RADIUS_KM = 6371.0


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometres between two lon/lat points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def lon_lat_grid(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    n_lat: int,
    n_lon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a rectangular grid of ``(lats, lons)`` arrays."""
    lats = np.linspace(lat_min, lat_max, n_lat)
    lons = np.linspace(lon_min, lon_max, n_lon)
    return lons, lats  # broadcasting-friendly order: (n_lon, n_lat)


def bounding_box(
    lons: np.ndarray, lats: np.ndarray, margin_deg: float = 0.0
) -> tuple[float, float, float, float]:
    """Return ``(lon_min, lon_max, lat_min, lat_max)`` of a set of points."""
    return (
        float(np.min(lons)) - margin_deg,
        float(np.max(lons)) + margin_deg,
        float(np.min(lats)) - margin_deg,
        float(np.max(lats)) + margin_deg,
    )


def point_in_polygon(lon: float, lat: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test.

    Args:
        lon: Point longitude.
        lat: Point latitude.
        polygon: List of ``(lon, lat)`` vertices (closed automatically).
    """
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    x, y = lon, lat
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Standard even-odd rule: does a horizontal ray from (x, y) cross
        # the edge (xi, yi)-(xj, yj)?
        if (yi > y) != (yj > y):
            x_intersect = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


def _as_xy(points: Any) -> np.ndarray:
    """Convert a list of ``(lon, lat)`` pairs into an ``(N, 2)`` array."""
    arr = np.asarray(points, dtype=np.float64)
    if arr.ndim == 2 and arr.shape[1] == 2:
        return arr
    raise ValueError("points must be an Nx2 array of (lon, lat) pairs")
