"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

sys.path.insert(0, str(Path(__file__).parent.parent))


def make_era5_netcdf(path, variable: str = "2m_temperature", size: int = 10) -> None:
    """Create an ERA5-style NetCDF file (time/latitude/longitude dims)."""
    lats = np.linspace(-25.0, -20.0, size)
    lons = np.linspace(-50.0, -45.0, size)
    times = np.array([np.datetime64("2026-01-01T00:00")])
    data = np.random.default_rng(0).normal(20.0, 2.0, (1, size, size))
    ds = xr.Dataset(
        data_vars={variable: (("time", "latitude", "longitude"), data)},
        coords={"time": times, "latitude": lats, "longitude": lons},
    )
    ds.to_netcdf(path)


def make_radar_netcdf(path, variable: str = "reflectivity", size: int = 32) -> None:
    """Create a radar NetCDF file with reflectivity."""
    lats = np.linspace(-25.0, -20.0, size)
    lons = np.linspace(-50.0, -40.0, size)
    times = np.array([np.datetime64("2026-01-01T00:00")])
    data = np.random.default_rng(1).uniform(0.0, 50.0, (1, size, size))
    ds = xr.Dataset(
        data_vars={variable: (("time", "latitude", "longitude"), data)},
        coords={"time": times, "latitude": lats, "longitude": lons},
    )
    ds.to_netcdf(path)


def make_forecast_field(size: int = 10):
    from barograph.core.models import GriddedField, ModelSource, Variable

    lats = np.linspace(-25.0, -20.0, size)
    lons = np.linspace(-50.0, -45.0, size)
    data = np.random.default_rng(2).normal(24.0, 3.0, (size, size))
    return GriddedField(
        data=data.astype(np.float32),
        lats=lats,
        lons=lons,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, 12),
        init_time=datetime(2026, 1, 1, 0),
    )


@pytest.fixture
def era5_file(tmp_path):
    p = tmp_path / "era5_sample.nc"
    make_era5_netcdf(p)
    return p


@pytest.fixture
def radar_file(tmp_path):
    p = tmp_path / "radar_sample.nc"
    make_radar_netcdf(p)
    return p


@pytest.fixture
def forecast_field():
    return make_forecast_field()
