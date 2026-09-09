"""Spatial interpolation of sparse station observations onto a grid."""

from __future__ import annotations

from typing import Any

import numpy as np

from barograph.core.models import GriddedField, ModelSource, Variable
from barograph.geospatial.projection import _as_xy, haversine_distance


class IDWInterpolator:
    """Inverse-distance-weighting interpolator.

    A grid value is a distance-weighted average of the nearest ``k``
    observations, with an optional minimum power ``p`` for the inverse
    distance weighting.
    """

    def __init__(
        self,
        max_points: int = 8,
        power: float = 2.0,
        smoothing: float = 0.0,
    ) -> None:
        self.max_points = max_points
        self.power = power
        self.smoothing = smoothing

    def fit_predict(
        self,
        obs_lons: np.ndarray,
        obs_lats: np.ndarray,
        obs_values: np.ndarray,
        grid_lons: np.ndarray,
        grid_lats: np.ndarray,
    ) -> np.ndarray:
        """Interpolate observations (lon, lat, value) onto a grid.

        Args:
            obs_lons: Observation longitudes ``(M,)``.
            obs_lats: Observation latitudes ``(M,)``.
            obs_values: Observation values ``(M,)``.
            grid_lons: Lon coordinates of grid points.
            grid_lats: Lat coordinates of grid points.

        Returns:
            ``len(grid_lons) x len(grid_lats)`` array of interpolated values.
        """
        obs_xy = _as_xy(list(zip(obs_lons, obs_lats)))
        values = np.asarray(obs_values, dtype=np.float64)
        out = np.empty((len(grid_lons), len(grid_lats)), dtype=np.float64)
        for j, glat in enumerate(grid_lats):
            for i, glon in enumerate(grid_lons):
                out[i, j] = self._value_at(glon, glat, obs_xy, values)
        return out

    def _value_at(
        self,
        lon: float,
        lat: float,
        obs_xy: np.ndarray,
        values: np.ndarray,
    ) -> float:
        dists = np.array(
            [haversine_distance(lon, lat, float(p[0]), float(p[1]))
             for p in obs_xy]
        )
        order = np.argsort(dists)[: self.max_points]
        nearest = dists[order] + self.smoothing
        weights = 1.0 / np.maximum(nearest, 1e-9) ** self.power
        weights = weights / weights.sum()
        return float(np.sum(values[order] * weights))


class NearestInterpolator:
    """Assigns each grid cell the value of the nearest observation."""

    def fit_predict(
        self,
        obs_lons: np.ndarray,
        obs_lats: np.ndarray,
        obs_values: np.ndarray,
        grid_lons: np.ndarray,
        grid_lats: np.ndarray,
    ) -> np.ndarray:
        obs_xy = _as_xy(list(zip(obs_lons, obs_lats)))
        values = np.asarray(obs_values, dtype=np.float64)
        out = np.empty((len(grid_lons), len(grid_lats)), dtype=np.float64)
        for j, glat in enumerate(grid_lats):
            for i, glon in enumerate(grid_lons):
                dists = [
                    haversine_distance(glon, glat, float(p[0]), float(p[1]))
                    for p in obs_xy
                ]
                out[i, j] = values[int(np.argmin(dists))]
        return out


class SimpleKriging:
    """Ordinary-kriging-like interpolator with a spherical variogram.

    This is a lightweight, dependency-free approximation of ordinary kriging:
    it fits a spherical variogram to the empirical semivariance of the
    observations and solves the kriging weights via a linear system.
    """

    def __init__(self, nugget: float = 0.1, range_km: float = 50.0,
                 sill: float | None = None) -> None:
        self.nugget = nugget
        self.range_km = range_km
        self.sill = sill

    def fit_predict(
        self,
        obs_lons: np.ndarray,
        obs_lats: np.ndarray,
        obs_values: np.ndarray,
        grid_lons: np.ndarray,
        grid_lats: np.ndarray,
    ) -> np.ndarray:
        obs_xy = _as_xy(list(zip(obs_lons, obs_lats)))
        values = np.asarray(obs_values, dtype=np.float64)
        m = len(values)
        sill = self.sill if self.sill is not None else float(np.var(values)) * 1.1
        # Build the augmented kriging matrix (M+1 x M+1)
        A = np.ones((m + 1, m + 1))
        A[m, m] = 0.0
        for i in range(m):
            for j in range(m):
                d = haversine_distance(
                    float(obs_xy[i, 0]), float(obs_xy[i, 1]),
                    float(obs_xy[j, 0]), float(obs_xy[j, 1]),
                )
                A[i, j] = self._variogram(d, sill)
            A[i, m] = 1.0
            A[m, i] = 1.0

        out = np.empty((len(grid_lons), len(grid_lats)), dtype=np.float64)
        for j, glat in enumerate(grid_lats):
            for i, glon in enumerate(grid_lons):
                b = np.ones(m + 1)
                for k in range(m):
                    d = haversine_distance(
                        glon, glat,
                        float(obs_xy[k, 0]), float(obs_xy[k, 1]),
                    )
                    b[k] = self._variogram(d, sill)
                b[m] = 1.0
                try:
                    w = np.linalg.solve(A, b)
                except np.linalg.LinAlgError:
                    w = np.zeros(m + 1)
                    w[:m] = 1.0 / m
                out[i, j] = float(np.sum(w[:m] * values))
        return out

    def _variogram(self, distance_km: float, sill: float) -> float:
        """Spherical variogram model value."""
        h = distance_km
        r = self.range_km
        if h == 0:
            return 0.0
        if h >= r:
            gamma = sill
        else:
            gamma = self.nugget + (sill - self.nugget) * (
                1.5 * h / r - 0.5 * (h / r) ** 3
            )
        return gamma


def interpolate_station_field(
    obs_lons: np.ndarray,
    obs_lats: np.ndarray,
    obs_values: np.ndarray,
    grid_lons: np.ndarray,
    grid_lats: np.ndarray,
    variable: Variable,
    source: ModelSource,
    valid_time: Any,
    init_time: Any,
    method: str = "idw",
) -> GriddedField:
    """Interpolate station observations into a :class:`GriddedField`.

    Args:
        method: One of ``"idw"`` or ``"nearest"``.
    """
    if method == "idw":
        data = IDWInterpolator().fit_predict(
            obs_lons, obs_lats, obs_values, grid_lons, grid_lats
        )
    elif method == "nearest":
        data = NearestInterpolator().fit_predict(
            obs_lons, obs_lats, obs_values, grid_lons, grid_lats
        )
    else:
        raise ValueError(f"Unknown interpolation method: {method!r}")

    # GriddedField expects (n_lat, n_lon) data.
    data = data.T
    return GriddedField(
        data=data,
        lats=np.asarray(grid_lats),
        lons=np.asarray(grid_lons),
        variable=variable,
        source=source,
        valid_time=valid_time,
        init_time=init_time,
        meta={"interpolation": method},
    )
