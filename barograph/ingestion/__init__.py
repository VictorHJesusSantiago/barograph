"""Ingestion of NWP model data (GFS, ECMWF, ERA5) and radar."""

from barograph.ingestion.ecmwf import ECMWFIngester
from barograph.ingestion.era5 import ERA5Ingester
from barograph.ingestion.gfs import GFSIngester
from barograph.ingestion.radar import RadarIngester

__all__ = ["GFSIngester", "ECMWFIngester", "ERA5Ingester", "RadarIngester"]
