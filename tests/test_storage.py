"""Unit tests for storage utilities (NetCDF / Zarr round-trips)."""

import numpy as np
import pytest

from barograph.utils.storage import (
    load_gridded_field,
    save_ensemble,
    save_gridded_field,
    to_zarr,
)
from tests.conftest import make_forecast_field

pytest.importorskip("xarray")
pytest.importorskip("netCDF4")


def test_save_and_load_gridded_field(tmp_path):
    field = make_forecast_field(size=8)
    path = save_gridded_field(field, tmp_path / "field.nc")

    loaded = load_gridded_field(path)
    assert loaded.variable == field.variable
    assert loaded.source == field.source
    assert loaded.valid_time == field.valid_time
    assert np.allclose(loaded.data, field.data)
    assert np.allclose(loaded.lats, field.lats)
    assert np.allclose(loaded.lons, field.lons)


def test_save_ensemble(tmp_path):
    fields = [make_forecast_field(size=8) for _ in range(3)]
    path = save_ensemble(fields, tmp_path / "ensemble.nc")
    assert path.exists()


def test_to_zarr(tmp_path):
    fields = [make_forecast_field(size=8) for _ in range(2)]
    path = to_zarr(fields, tmp_path / "data.zarr")
    assert path.exists()

    import xarray as xr
    ds = xr.open_zarr(path)
    assert "data" in ds.data_vars
    assert ds.sizes["time"] == 2
