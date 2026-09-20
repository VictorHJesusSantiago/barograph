"""Tests for the raster data layer module."""

from __future__ import annotations

import numpy as np
import pytest

from barograph.raster.algebra import RasterAlgebra
from barograph.raster.layer import CRS, EPSG_WGS84, RasterLayer
from barograph.raster.masking import RasterMasker
from barograph.raster.reflectivity import Reflectivity
from barograph.raster.terrain import Terrain


def make_layer(ny=10, nx=12, value=5.0, name="t"):
    lats = np.linspace(-25.0, -20.0, ny)
    lons = np.linspace(-50.0, -45.0, nx)
    data = np.full((ny, nx), value, dtype=np.float32)
    return RasterLayer(data=data, lats=lats, lons=lons, name=name)


def test_layer_promotes_2d_to_single_band():
    layer = make_layer()
    assert layer.nbands == 1
    assert layer.shape == (10, 12)
    assert layer.data.ndim == 3


def test_layer_requires_matching_grid():
    lats = np.linspace(-25, -20, 10)
    lons = np.linspace(-50, -45, 12)
    data = np.full((10, 11), 1.0)
    with pytest.raises(ValueError):
        RasterLayer(data=data, lats=lats, lons=lons)


def test_extent_and_resolution():
    layer = make_layer()
    ext = layer.extent
    assert ext[0] == -50.0
    assert ext[1] == -45.0
    assert layer.res_lat > 0 and layer.res_lon > 0


def test_pixel_nearest_and_value_at():
    layer = make_layer(value=7.0)
    row, col = layer.pixel_nearest(-22.5, -47.5)
    assert 0 <= row < 10 and 0 <= col < 12
    assert layer.value_at(-22.5, -47.5) == 7.0


def test_summary():
    layer = make_layer(value=3.0)
    summary = layer.summary()
    assert summary["min"] == 3.0
    assert summary["max"] == 3.0
    assert summary["nbands"] == 1


def test_crs_defaults():
    assert CRS().epsg == EPSG_WGS84
    assert CRS().is_geographic
    assert not CRS(epsg=3857).is_geographic


def test_algebra_add_subtract():
    a = make_layer(value=5.0)
    b = make_layer(value=2.0)
    assert np.allclose(RasterAlgebra.add(a, b).data, 7.0)
    assert np.allclose(RasterAlgebra.subtract(a, b).data, 3.0)
    assert np.allclose(RasterAlgebra.multiply(a, b).data, 10.0)
    assert np.allclose(RasterAlgebra.divide(a, b).data, 2.5)


def test_algebra_divide_by_zero_gives_nan():
    a = make_layer(value=5.0)
    b = make_layer(value=0.0)
    assert np.isnan(RasterAlgebra.divide(a, b).data).all()


def test_algebra_requires_alignment():
    a = make_layer(ny=10, nx=12)
    b = make_layer(ny=11, nx=12)
    with pytest.raises(ValueError):
        RasterAlgebra.add(a, b)


def test_algebra_scale_and_stats():
    layer = make_layer(value=3.0)
    scaled = RasterAlgebra.scale(layer, factor=2.0, offset=1.0)
    assert np.allclose(scaled.data, 7.0)
    stats = RasterAlgebra.stats(scaled)
    assert stats["mean"] == pytest.approx(7.0)


def test_stack_layers():
    a = make_layer(value=1.0, name="a")
    b = make_layer(value=2.0, name="b")
    stack = RasterAlgebra.stack([a, b])
    assert stack.nbands == 2
    assert np.allclose(stack.data[0], 1.0)
    assert np.allclose(stack.data[1], 2.0)


def test_resample_nearest():
    layer = make_layer(ny=10, nx=10)
    target_lats = np.linspace(-24.0, -21.0, 4)
    target_lons = np.linspace(-49.0, -46.0, 4)
    out = RasterAlgebra.resample_nearest(layer, target_lats, target_lons)
    assert out.shape == (4, 4)


def test_from_points_nearest():
    lats = np.array([-24.0, -22.0, -20.0])
    lons = np.array([-49.0, -47.0, -45.0])
    values = np.array([1.0, 2.0, 3.0])
    grid_lats = np.linspace(-25.0, -20.0, 6)
    grid_lons = np.linspace(-50.0, -45.0, 6)
    layer = RasterAlgebra.from_points(lats, lons, values, grid_lats, grid_lons)
    assert layer.shape == (6, 6)
    assert np.isfinite(layer.band(0)).all()


def test_masker_threshold():
    layer = make_layer(value=5.0)
    mask = RasterMasker.threshold(layer, ">", 3.0)
    assert mask.all()
    mask2 = RasterMasker.threshold(layer, "<", 3.0)
    assert not mask2.any()


def test_masker_combine_and_apply():
    a = np.array([[True, False], [True, True]])
    b = np.array([[True, True], [True, False]])
    assert (RasterMasker.combine_and(a, b) == np.array([[True, False], [True, False]])).all()
    assert (RasterMasker.combine_or(a, b) == np.ones((2, 2), dtype=bool)).all()
    assert (RasterMasker.invert(a) == ~a).all()


def test_masker_apply_fill():
    layer = make_layer(value=5.0)
    mask = np.ones_like(layer.band(0), dtype=bool)
    mask[0, 0] = False
    out = RasterMasker.apply(layer, mask, fill=0.0)
    assert out.data[0, 0, 0] == 0.0
    assert out.data[0, 1, 1] == 5.0


def test_reflectivity():
    refl = Reflectivity()
    dbz = np.array([0.0, 20.0, 30.0, 40.0])
    rate = refl.rainfall_rate(dbz)
    assert rate[0] == 0.0  # zero reflectivity -> zero rate
    assert np.all(rate >= 0)
    assert np.all(np.isfinite(rate))
    assert (rate[1:] > 0).all()


def test_reflectivity_to_raster():
    layer = make_layer(value=35.0, name="dbz")
    rate_layer = Reflectivity().to_raster(layer)
    assert rate_layer.name == "rainfall_rate"
    assert rate_layer.units == "mm/h"
    assert rate_layer.shape == layer.shape


def test_terrain_slope_and_hillshade():
    lats = np.linspace(-25.0, -20.0, 20)
    lons = np.linspace(-50.0, -45.0, 20)
    x, y = np.meshgrid(lons, lats, indexing="ij")
    # plane with gentle slope
    dem_data = (x * 0.5 + y * 0.3)[np.newaxis, ...].astype(np.float32)
    dem = RasterLayer(data=dem_data, lats=lats, lons=lons, name="dem")
    slope = Terrain.slope(dem)
    assert slope.shape == (20, 20)
    assert np.all(slope >= 0)
    hill = Terrain.hillshade(dem)
    assert hill.shape == (20, 20)
    assert np.all(hill >= 0) and np.all(hill <= 255)


def test_terrain_stats():
    lats = np.linspace(-25.0, -20.0, 10)
    lons = np.linspace(-50.0, -45.0, 10)
    dem = RasterLayer(
        data=np.full((1, 10, 10), 100.0, dtype=np.float32), lats=lats, lons=lons, name="dem"
    )
    stats = Terrain.elevation_stats(dem)
    assert stats["min"] == 100.0


def test_layer_to_masked_array_nodata():
    layer = make_layer(value=5.0)
    layer.nodata = -9999.0
    layer.data[0, 0, 0] = -9999.0
    masked = layer.as_masked_array()
    assert masked.mask[0, 0]
    assert not masked.mask[1, 1]
