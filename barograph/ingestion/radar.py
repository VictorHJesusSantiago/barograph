"""Radar data ingestion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
from loguru import logger

from barograph.core.models import RadarSweep
from barograph.core.temporal import utcnow


class RadarIngester:
    """Ingest radar composite / sweep data."""

    def __init__(self, data_dir: str = "./data/radar"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def parse_netcdf(self, file_path: str | Path) -> RadarSweep:
        """Parse a radar NetCDF file."""
        ds = xr.open_dataset(file_path)

        if "reflectivity" in ds.data_vars:
            refl_var = "reflectivity"
        elif "dBZ" in ds.data_vars:
            refl_var = "dBZ"
        elif "dbz" in ds.data_vars:
            refl_var = "dbz"
        else:
            refl_var = str(list(ds.data_vars.keys())[0])

        data = ds[refl_var].values
        if data.ndim == 3:
            data = data[0]

        lat_dim = next((d for d in ds[refl_var].dims if "lat" in str(d).lower()), None)
        lon_dim = next((d for d in ds[refl_var].dims if "lon" in str(d).lower()), None)

        lats = ds[lat_dim].values if lat_dim else np.linspace(-90, 90, data.shape[-2])
        lons = ds[lon_dim].values if lon_dim else np.linspace(-180, 180, data.shape[-1])

        scan_time = utcnow()
        for key in ["time", "scan_time", "datetime"]:
            if key in ds.coords:
                scan_time = ds[key].values.item()
                break

        return RadarSweep(
            data=data.astype(np.float32),
            lats=lats.astype(np.float32),
            lons=lons.astype(np.float32),
            scan_time=scan_time,
            meta={"file": str(file_path), "variable": refl_var},
        )

    def parse_directory(
        self,
        directory: str | Path | None = None,
        pattern: str = "*.nc",
    ) -> list[RadarSweep]:
        """Parse all radar files in a directory."""
        d = Path(directory) if directory else self.data_dir
        results = []
        for f in sorted(d.glob(pattern)):
            try:
                results.append(self.parse_netcdf(f))
            except Exception as e:
                logger.warning(f"Failed to parse radar file {f}: {e}")
        return results

    def composite_sweeps(
        self,
        sweeps: list[RadarSweep],
        method: str = "max",
    ) -> RadarSweep:
        """Create composite from multiple sweeps."""
        if not sweeps:
            raise ValueError("No sweeps provided")

        ref = sweeps[0]
        all_data = np.array([s.data for s in sweeps])

        if method == "max":
            comp_data = np.nanmax(all_data, axis=0)
        elif method == "mean":
            comp_data = np.nanmean(all_data, axis=0)
        else:
            comp_data = np.nanmax(all_data, axis=0)

        return RadarSweep(
            data=comp_data,
            lats=ref.lats,
            lons=ref.lons,
            scan_time=ref.scan_time,
            meta={"composite_method": method, "n_sweeps": len(sweeps)},
        )
