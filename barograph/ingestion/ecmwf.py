"""ECMWF IFS data ingestion."""

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


class ECMWFIngester:
    """Ingest GRIB data from ECMWF IFS."""

    VARIABLE_MAP: dict[str, str] = {
        "temperature": "2t",
        "precipitation": "tp",
        "wind_u": "10u",
        "wind_v": "10v",
        "wind_speed": "10si",
        "humidity": "2d",
        "pressure": "msl",
        "cloud_cover": "tcc",
        "cape": "cape",
    }

    def __init__(self, config: IngestionConfig | None = None):
        self.config = config or IngestionConfig()
        self.data_dir = Path(self.config.data_dir) / "ecmwf"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def parse_grib(
        self,
        file_path: str | Path,
        variable: str,
        level: float | None = None,
    ) -> GriddedField:
        """Parse a single GRIB file into a GriddedField."""
        require_cfgrib()
        short_name = self.VARIABLE_MAP.get(variable, variable)

        ds = xr.open_dataset(
            file_path,
            engine="cfgrib",
            backend_kwargs={
                "indexpath": "",
                "filter_by_keys": {"shortName": short_name},
            },
        )

        if short_name not in ds.data_vars and len(ds.data_vars) > 0:
            ds_var = list(ds.data_vars.values())[0]
        else:
            ds_var = ds[short_name]

        data = ds_var.values
        lats = ds_var.latitude.values
        lons = ds_var.longitude.values

        if data.ndim == 3:
            data = data[0]

        var_enum = Variable.from_value(variable)

        return GriddedField(
            data=data.astype(np.float32),
            lats=lats.astype(np.float32),
            lons=lons.astype(np.float32),
            variable=var_enum,
            source=ModelSource.ECMWF,
            init_time=self._extract_init_time(ds),
            valid_time=self._extract_valid_time(ds),
            meta={"file": str(file_path)},
        )

    def parse_directory(
        self,
        directory: str | Path,
        variable: str,
        pattern: str = "*.grib",
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

    def parse_multilevel_grib(
        self,
        file_path: str | Path,
        variable: str,
        levels: list[float],
    ) -> list[GriddedField]:
        """Parse a GRIB file with multiple pressure levels."""
        require_cfgrib()
        results = []
        for lev in levels:
            try:
                ds = xr.open_dataset(
                    file_path,
                    engine="cfgrib",
                    backend_kwargs={
                        "indexpath": "",
                        "filter_by_keys": {
                            "shortName": self.VARIABLE_MAP.get(variable, variable),
                            "level": int(lev),
                        },
                    },
                )
                ds_var = list(ds.data_vars.values())[0]
                data = ds_var.values
                lats = ds_var.latitude.values
                lons = ds_var.longitude.values

                if data.ndim == 3:
                    data = data[0]

                var_enum = Variable.from_value(variable)

                results.append(GriddedField(
                    data=data.astype(np.float32),
                    lats=lats.astype(np.float32),
                    lons=lons.astype(np.float32),
                    variable=var_enum,
                    source=ModelSource.ECMWF,
                    init_time=self._extract_init_time(ds),
                    valid_time=self._extract_valid_time(ds),
                    level=lev,
                    meta={"file": str(file_path)},
                ))
            except Exception as e:
                logger.warning(f"Failed to parse level {lev}: {e}")
        return results

    @staticmethod
    def _extract_init_time(ds: xr.Dataset) -> datetime:
        if "time" in ds.coords:
            return ds.time.values.item()
        return utcnow()

    @staticmethod
    def _extract_valid_time(ds: xr.Dataset) -> datetime:
        if "step" in ds.coords:
            ref = ds.time.values.item()
            step = ds.step.values.item()
            if hasattr(step, "total_seconds"):
                from datetime import timedelta
                return ref + timedelta(seconds=step.total_seconds())
            return ref
        return utcnow()
