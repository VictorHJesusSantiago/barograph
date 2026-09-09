"""Spatial masking of gridded data by polygons and radial distances."""

from __future__ import annotations

import numpy as np

from barograph.geospatial.projection import point_in_polygon
from barograph.raster.layer import RasterLayer


class PolygonMasker:
    """Masks a raster outside of one or more polygons.

    Args:
        polygons: List of polygons, each a list of ``(lon, lat)`` vertices.
        keep_inside: When ``True`` (default) keep cells inside, else outside.
    """

    def __init__(
        self, polygons: list[list[tuple[float, float]]], keep_inside: bool = True
    ) -> None:
        if not polygons:
            raise ValueError("At least one polygon is required")
        self.polygons = polygons
        self.keep_inside = keep_inside

    def mask(self, layer: RasterLayer) -> RasterLayer:
        """Return a copy of *layer* with out-of-region cells set to NaN."""
        lats, lons = np.meshgrid(
            np.asarray(layer.lats), np.asarray(layer.lons), indexing="ij"
        )
        keep = np.zeros(lats.shape, dtype=bool)
        for poly in self.polygons:
            for i in range(lats.shape[0]):
                for j in range(lats.shape[1]):
                    if point_in_polygon(lons[i, j], lats[i, j], poly):
                        keep[i, j] = True
        if not self.keep_inside:
            keep = ~keep
        data = np.array(layer.data, dtype=np.float64, copy=True)
        if data.ndim == 3:
            data[:, ~keep] = np.nan
        else:
            data[~keep] = np.nan
        return RasterLayer(
            data=data,
            lats=layer.lats,
            lons=layer.lons,
            name=layer.name,
            crs=layer.crs,
            units=layer.units,
            meta=layer.meta,
        )


def mask_outside_polygon(
    layer: RasterLayer, polygon: list[tuple[float, float]]
) -> RasterLayer:
    """Set all cells outside *polygon* to NaN."""
    return PolygonMasker([polygon], keep_inside=True).mask(layer)


def mask_radius(
    layer: RasterLayer,
    center_lon: float,
    center_lat: float,
    radius_km: float,
) -> RasterLayer:
    """Set all cells farther than *radius_km* from the center to NaN."""
    from barograph.geospatial.projection import haversine_distance

    lats, lons = np.meshgrid(
        np.asarray(layer.lats), np.asarray(layer.lons), indexing="ij"
    )
    dist = np.vectorize(
        lambda lo, la: haversine_distance(center_lon, center_lat, lo, la)
    )(lons, lats)
    data = np.array(layer.data, dtype=np.float64, copy=True)
    if data.ndim == 3:
        data[:, dist > radius_km] = np.nan
    else:
        data[dist > radius_km] = np.nan
    return RasterLayer(
        data=data,
        lats=layer.lats,
        lons=layer.lons,
        name=layer.name,
        crs=layer.crs,
        units=layer.units,
        meta=layer.meta,
    )
