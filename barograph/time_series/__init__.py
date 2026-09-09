"""Time-series analysis for meteorological observations and forecasts."""

from barograph.time_series.analysis import (
    TimeSeriesAnalyzer,
    constant_trend,
    linear_trend,
    seasonal_climatology,
    standard_anomalies,
)
from barograph.time_series.precip import (
    PrecipitationAnalyzer,
    PrecipitationEvent,
    rolling_precip,
    wet_days_fraction,
)

__all__ = [
    "TimeSeriesAnalyzer",
    "constant_trend",
    "linear_trend",
    "seasonal_climatology",
    "standard_anomalies",
    "PrecipitationAnalyzer",
    "PrecipitationEvent",
    "rolling_precip",
    "wet_days_fraction",
]
