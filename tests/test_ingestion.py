"""Unit tests for data ingestion (ERA5 / radar NetCDF)."""

import numpy as np

from barograph.core.models import ModelSource, RadarSweep, Variable
from barograph.ingestion import ERA5Ingester, RadarIngester
from tests.conftest import make_radar_netcdf


def test_era5_parse_netcdf(era5_file):
    ingester = ERA5Ingester()
    field = ingester.parse_netcdf(era5_file, "temperature")

    assert field.source == ModelSource.ERA5
    assert field.variable == Variable.TEMPERATURE
    assert field.data.shape == (10, 10)
    assert field.lats.shape == (10,)
    assert field.lons.shape == (10,)
    assert isinstance(field.data, np.ndarray)


def test_era5_parse_directory(tmp_path, era5_file):
    ingester = ERA5Ingester()
    fields = ingester.parse_directory(tmp_path, "temperature")
    assert len(fields) == 1
    assert fields[0].data.shape == (10, 10)


def test_era5_parse_unknown_variable(era5_file):
    ingester = ERA5Ingester()
    # When the requested variable isn't mapped, it should pick the first data var
    field = ingester.parse_netcdf(era5_file, "not_a_real_var")
    assert field.data.shape == (10, 10)


def test_radar_parse_netcdf(radar_file):
    ingester = RadarIngester()
    sweep = ingester.parse_netcdf(radar_file)

    assert isinstance(sweep, RadarSweep)
    assert sweep.shape == (32, 32)
    assert sweep.dbz.shape == (32, 32)
    assert sweep.reflectivity_linear.shape == (32, 32)


def test_radar_composite_max(tmp_path):
    ingester = RadarIngester()
    p1 = tmp_path / "r1.nc"
    p2 = tmp_path / "r2.nc"
    make_radar_netcdf(p1)
    make_radar_netcdf(p2)

    s1 = ingester.parse_netcdf(p1)
    s2 = ingester.parse_netcdf(p2)
    composite = ingester.composite_sweeps([s1, s2], method="max")
    assert composite.shape == (32, 32)


def test_radar_parse_directory(tmp_path):
    make_radar_netcdf(tmp_path / "a.nc")
    make_radar_netcdf(tmp_path / "b.nc")
    ingester = RadarIngester()
    sweeps = ingester.parse_directory(tmp_path)
    assert len(sweeps) == 2


def test_era5_zarr_roundtrip(tmp_path, era5_file):
    import xarray as xr

    ds = xr.open_dataset(era5_file)
    zarr_path = tmp_path / "era5.zarr"
    ds.to_zarr(zarr_path, mode="w")

    ingester = ERA5Ingester()
    fields = ingester.parse_era5_zarr(zarr_path, "temperature")
    assert len(fields) == 1
    assert fields[0].data.shape == (10, 10)
