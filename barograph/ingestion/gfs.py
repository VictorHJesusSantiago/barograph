"""GFS data ingestion."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import xarray as xr
from loguru import logger

from barograph.core.config import IngestionConfig
from barograph.core.models import GriddedField, ModelSource, Variable
from barograph.core.temporal import utcnow
from barograph.ingestion._grib import require_cfgrib


class GFSIngester:
    """Ingest GRIB2 data from NOAA GFS."""

    VARIABLE_MAP: dict[str, str] = {
        "temperature": "TMP:2 m above ground",
        "precipitation": "APCP:surface",
        "wind_u": "UGRD:10 m above ground",
        "wind_v": "VGRD:10 m above ground",
        "wind_speed": "TMP:2 m above ground",
        "humidity": "RH:2 m above ground",
        "pressure": "PRES:surface",
        "cloud_cover": "TCDC:entire atmosphere",
        "cape": "CAPE:surface",
    }

    def __init__(self, config: IngestionConfig | None = None):
        self.config = config or IngestionConfig()
        self.data_dir = Path(self.config.data_dir) / "gfs"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def parse_grib(
        self,
        file_path: str | Path,
        variable: str,
        level: float | None = None,
    ) -> GriddedField:
        """Parse a single GRIB2 file into a GriddedField."""
        require_cfgrib()
        ds = xr.open_dataset(
            file_path,
            engine="cfgrib",
            backend_kwargs={"indexpath": ""},
        )

        short_name = self.VARIABLE_MAP.get(variable, variable)

        if ":" in short_name:
            param, level_str = short_name.split(":", 1)
            if "2 m" in level_str:
                ds_var = ds[param].sel(heightAboveGround=2.0)
            elif "10 m" in level_str:
                ds_var = ds[param].sel(heightAboveGround=10.0)
            elif "entire" in level_str:
                ds_var = ds[param]
            elif "surface" in level_str:
                ds_var = ds[param]
            else:
                ds_var = ds[param]
        else:
            ds_var = ds[short_name] if short_name in ds else ds.data_vars[list(ds.data_vars)[0]]

        data = ds_var.values
        lats = ds_var.latitude.values
        lons = ds_var.longitude.values

        if data.ndim == 2:
            pass
        elif data.ndim == 3:
            data = data[0]

        var_enum = Variable.from_value(variable)

        return GriddedField(
            data=data.astype(np.float32),
            lats=lats.astype(np.float32),
            lons=lons.astype(np.float32),
            variable=var_enum,
            source=ModelSource.GFS,
            init_time=self._extract_init_time(ds),
            valid_time=self._extract_valid_time(ds),
            meta={"file": str(file_path)},
        )

    def parse_directory(
        self,
        directory: str | Path,
        variable: str,
        pattern: str = "*.grib2",
    ) -> list[GriddedField]:
        """Parse all GRIB files in a directory."""
        results = []
        for f in sorted(Path(directory).glob(pattern)):
            try:
                field = self.parse_grib(f, variable)
                results.append(field)
            except Exception as e:
                logger.warning(f"Failed to parse {f}: {e}")
        return results

    @staticmethod
    def _extract_init_time(ds: xr.Dataset) -> datetime:
        if "time" in ds.coords:
            return ds.time.values.item()
        if "forecast_reference_time" in ds.coords:
            return ds.forecast_reference_time.values.item()
        return utcnow()

    @staticmethod
    def _extract_valid_time(ds: xr.Dataset) -> datetime:
        if "step" in ds.coords:
            ref = ds.get("forecast_reference_time", ds.time).values.item()
            step = ds.step.values.item()
            if hasattr(step, "total_seconds"):
                from datetime import timedelta
                return ref + timedelta(seconds=step.total_seconds())
            return ref
        if "time" in ds.coords:
            return ds.time.values.item()
        return utcnow()

    def download_gfs(
        self,
        run_date: datetime,
        forecast_hour: int,
        variables: list[str] | None = None,
        output_dir: str | Path | None = None,
    ) -> Path:
        """Download GFS data from NOMADS."""
        import urllib.request

        date_str = run_date.strftime("%Y%m%d")
        cycle = f"{run_date.hour:02d}"
        fh_str = f"{forecast_hour:03d}"

        base = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
        params = (
            f"?file=gfs.t{cycle}z.pgrb2.0p25.f{fh_str}"
            f"&dir=%2Fgfs.{date_str}%2F{cycle}%2Fatmos"
        )

        out = Path(output_dir or self.data_dir)
        out.mkdir(parents=True, exist_ok=True)

        url = base + params
        dest = out / f"gfs_{date_str}_{cycle}z_f{fh_str}.grib2"

        if not dest.exists():
            logger.info(f"Downloading {url}")
            urllib.request.urlretrieve(url, dest)

        return dest
