"""ERA5 reanalysis data ingestion."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
from loguru import logger

from barograph.core.config import IngestionConfig
from barograph.core.models import GriddedField, ModelSource, Variable
from barograph.core.temporal import utcnow


class ERA5Ingester:
    """Ingest ERA5 reanalysis data from CDS or local files."""

    CDS_VARIABLE_MAP: dict[str, str] = {
        "temperature": "2m_temperature",
        "precipitation": "total_precipitation",
        "wind_u": "10m_u_component_of_wind",
        "wind_v": "10m_v_component_of_wind",
        "humidity": "2m_dewpoint_temperature",
        "pressure": "mean_sea_level_pressure",
        "cloud_cover": "total_cloud_cover",
        "cape": "convective_available_potential_energy",
    }

    def __init__(self, config: IngestionConfig | None = None):
        self.config = config or IngestionConfig()
        self.data_dir = Path(self.config.data_dir) / "era5"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def parse_netcdf(
        self,
        file_path: str | Path,
        variable: str,
    ) -> GriddedField:
        """Parse a NetCDF file into a GriddedField."""
        ds = xr.open_dataset(file_path)

        var_name = self.CDS_VARIABLE_MAP.get(variable, variable)
        if var_name not in ds.data_vars:
            if len(ds.data_vars) > 0:
                var_name = str(list(ds.data_vars.keys())[0])
            else:
                raise ValueError(f"No data variables found in {file_path}")

        ds_var = ds[var_name]
        data = ds_var.values

        lat_dim = "latitude" if "latitude" in ds_var.dims else "lat"
        lon_dim = "longitude" if "longitude" in ds_var.dims else "lon"
        lats = ds_var[lat_dim].values
        lons = ds_var[lon_dim].values

        time_dim = None
        for dim in ds_var.dims:
            if dim in ("time", "valid_time", "forecast_reference_time"):
                time_dim = dim
                break

        if time_dim and data.ndim >= 3:
            data = data[0]
        elif data.ndim == 3:
            data = data[0]

        var_enum = Variable.from_value(variable)

        return GriddedField(
            data=data.astype(np.float32),
            lats=lats.astype(np.float32),
            lons=lons.astype(np.float32),
            variable=var_enum,
            source=ModelSource.ERA5,
            init_time=self._extract_time(ds),
            valid_time=self._extract_time(ds),
            meta={"file": str(file_path)},
        )

    def parse_directory(
        self,
        directory: str | Path,
        variable: str,
        pattern: str = "*.nc",
    ) -> list[GriddedField]:
        """Parse all NetCDF files in a directory."""
        results = []
        for f in sorted(Path(directory).glob(pattern)):
            try:
                field = self.parse_netcdf(f, variable)
                results.append(field)
            except Exception as e:
                logger.warning(f"Failed to parse {f}: {e}")
        return results

    def parse_era5_zarr(
        self,
        zarr_path: str | Path,
        variable: str,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[GriddedField]:
        """Parse ERA5 data stored in Zarr format."""
        ds = xr.open_zarr(zarr_path)

        var_name = self.CDS_VARIABLE_MAP.get(variable, variable)
        if var_name not in ds.data_vars:
            var_name = list(ds.data_vars.keys())[0]

        ds_var = ds[var_name]

        if time_range:
            start, end = time_range
            ds_var = ds_var.sel(time=slice(start, end))

        lats = ds_var.latitude.values if "latitude" in ds_var.dims else ds_var.lat.values
        lons = ds_var.longitude.values if "longitude" in ds_var.dims else ds_var.lon.values

        results = []
        if "time" in ds_var.dims:
            for t in range(ds_var.sizes["time"]):
                data = ds_var.isel(time=t).values
                var_enum = Variable.from_value(variable)
                valid_time = ds_var.time.values[t].item()
                results.append(
                    GriddedField(
                        data=data.astype(np.float32),
                        lats=lats.astype(np.float32),
                        lons=lons.astype(np.float32),
                        variable=var_enum,
                        source=ModelSource.ERA5,
                        init_time=valid_time,
                        valid_time=valid_time,
                        meta={"zarr_path": str(zarr_path), "time_index": t},
                    )
                )
        else:
            data = ds_var.values
            var_enum = Variable.from_value(variable)
            now = utcnow()
            results.append(
                GriddedField(
                    data=data.astype(np.float32),
                    lats=lats.astype(np.float32),
                    lons=lons.astype(np.float32),
                    variable=var_enum,
                    source=ModelSource.ERA5,
                    init_time=now,
                    valid_time=now,
                )
            )

        return results

    def download_era5(
        self,
        variables: list[str],
        start_date: datetime,
        end_date: datetime,
        pressure_level: float | None = None,
    ) -> Path:
        """Download ERA5 data from CDS API."""
        import cdsapi

        client = cdsapi.Client()

        cds_vars = [self.CDS_VARIABLE_MAP.get(v, v) for v in variables]
        product = (
            "reanalysis-era5-single-levels"
            if pressure_level is None
            else "reanalysis-era5-pressure-levels"
        )

        request_params: dict[str, Any] = {
            "product_type": "reanalysis",
            "variable": cds_vars,
            "year": str(start_date.year),
            "month": f"{start_date.month:02d}",
            "day": [f"{d:02d}" for d in range(start_date.day, end_date.day + 1)],
            "time": [f"{h:02d}:00" for h in range(0, 24, 3)],
            "format": "netcdf",
        }

        if pressure_level is not None:
            request_params["pressure_level"] = str(int(pressure_level))

        fname = f"era5_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.nc"
        out_path = self.data_dir / fname
        client.retrieve(product, request_params, str(out_path))

        return out_path

    @staticmethod
    def _extract_time(ds: xr.Dataset) -> datetime:
        for key in ["time", "valid_time", "forecast_reference_time"]:
            if key in ds.coords:
                return ds[key].values.item()
        return utcnow()
