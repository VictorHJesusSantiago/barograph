"""Ingestion of NWP model data (GFS, ECMWF, ERA5)."""

from barograph.ingestion.ecmwf import ECMWFIngester
from barograph.ingestion.era5 import ERA5Ingester
from barograph.ingestion.gfs import GFSIngester

__all__ = ["GFSIngester", "ECMWFIngester", "ERA5Ingester"]
