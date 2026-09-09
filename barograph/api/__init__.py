"""Clients for fetching real-time meteorological data over HTTP.

The :mod:`barograph.api` package provides lightweight HTTP clients for a few
public data sources (Open-Meteo), with injectable HTTP transports so callers
can substitute a cache or a test stub without touching the network.
"""

from barograph.api.client import HTTPClient, HTTPError
from barograph.api.meteo import (
    CurrentWeather,
    DailyForecast,
    HourlyForecast,
    OpenMeteo,
)

__all__ = [
    "HTTPClient",
    "HTTPError",
    "OpenMeteo",
    "CurrentWeather",
    "HourlyForecast",
    "DailyForecast",
]
