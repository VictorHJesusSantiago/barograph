"""Data I/O helpers (NetCDF, Zarr, GRIB)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

if TYPE_CHECKING:
    from barograph.core.models import GriddedField


def save_gridded_field(field, path: str | Path) -> Path:
    """Save a GriddedField to NetCDF."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ds = xr.Dataset(
        data_vars={
            "data": (("latitude", "longitude"), field.data),
        },
        coords={
            "latitude": field.lats,
            "longitude": field.lons,
        },
        attrs={
            "variable": field.variable.value,
            "source": field.source.value,
            "valid_time": field.valid_time.isoformat(),
            "init_time": field.init_time.isoformat(),
            "level": str(field.level),
        },
    )
    ds.to_netcdf(path)
    return path


def load_gridded_field(path: str | Path) -> GriddedField:
    """Load a GriddedField from NetCDF."""
    from datetime import datetime

    from barograph.core.models import GriddedField, ModelSource, Variable
    from barograph.core.temporal import utcnow

    ds = xr.open_dataset(path)
    data = ds["data"].values

    variable = Variable.from_value(str(ds.attrs.get("variable", "temperature")))
    try:
        source = ModelSource(str(ds.attrs.get("source", "gfs")))
    except ValueError:
        source = ModelSource.GFS

    valid_time = datetime.fromisoformat(
        ds.attrs.get("valid_time", utcnow().isoformat())
    )
    init_time = datetime.fromisoformat(
        ds.attrs.get("init_time", valid_time.isoformat())
    )

    level = ds.attrs.get("level")
    try:
        level = float(level) if level not in (None, "None", "") else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        level = None

    return GriddedField(
        data=data,
        lats=ds["latitude"].values,
        lons=ds["longitude"].values,
        variable=variable,
        source=source,
        valid_time=valid_time,
        init_time=init_time,
        level=level,
    )


def save_ensemble(fields, path: str | Path) -> Path:
    """Save list of GriddedFields to a NetCDF with a member dimension."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = np.stack([f.data for f in fields])
    ds = xr.Dataset(
        data_vars={"ens_data": (("member", "latitude", "longitude"), arrays)},
        coords={
            "member": np.arange(len(fields)),
            "latitude": fields[0].lats,
            "longitude": fields[0].lons,
        },
        attrs={"variable": fields[0].variable.value,
               "source": fields[0].source.value},
    )
    ds.to_netcdf(path)
    return path


def to_zarr(fields, path: str | Path) -> Path:
    """Store list of GriddedFields to a Zarr store."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = np.stack([f.data for f in fields])
    ds = xr.Dataset(
        data_vars={"data": (("time", "latitude", "longitude"), arrays)},
        coords={
            "time": [f.valid_time.isoformat() for f in fields],
            "latitude": fields[0].lats,
            "longitude": fields[0].lons,
        },
    )
    ds.to_zarr(path)
    return path
