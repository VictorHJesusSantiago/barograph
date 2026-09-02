"""Core data models for meteorological fields and forecasts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np


class ModelSource(Enum):
    GFS = "gfs"
    ECMWF = "ecmwf"
    ERA5 = "era5"
    HRRR = "hrrr"


class Variable(Enum):
    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    WIND_U = "wind_u"
    WIND_V = "wind_v"
    WIND_SPEED = "wind_speed"
    WIND_GUST = "wind_gust"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    CLOUD_COVER = "cloud_cover"
    CAPE = "cape"
    CIN = "cin"
    SRH = "srh"
    LIFTED_INDEX = "lifted_index"
    VISIBILITY = "visibility"
    SNOWFALL = "snowfall"

    @classmethod
    def from_value(cls, value: str, default: Variable | None = None) -> Variable:
        """Resolve a Variable by string value, returning default if unknown."""
        for var in cls:
            if var.value == value:
                return var
        return default if default is not None else cls.TEMPERATURE


@dataclass
class Coordinate:
    latitude: float
    longitude: float
    elevation: float | None = None


@dataclass
class TimeRange:
    start: datetime
    end: datetime
    step_hours: float = 1.0

    @property
    def steps(self) -> list[datetime]:
        from datetime import timedelta
        current = self.start
        result = []
        while current <= self.end:
            result.append(current)
            current += timedelta(hours=self.step_hours)
        return result


@dataclass
class GriddedField:
    """A 2D or 3D gridded meteorological field."""
    data: np.ndarray
    lats: np.ndarray
    lons: np.ndarray
    variable: Variable
    source: ModelSource
    valid_time: datetime
    init_time: datetime
    level: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, ...]:
        return self.data.shape

    def __post_init__(self):
        if self.data.ndim < 2:
            raise ValueError("GriddedField data must be at least 2D")
        if self.data.shape[-2:] != (self.lats.shape[0], self.lons.shape[0]):
            raise ValueError("Data spatial dimensions must match lat/lon arrays")


@dataclass
class EnsembleForecast:
    """Ensemble forecast with multiple members."""
    members: list[GriddedField]
    variable: Variable
    source: ModelSource
    init_time: datetime
    valid_time: datetime
    member_ids: list[int] | None = None

    def __post_init__(self):
        if self.member_ids is None:
            self.member_ids = list(range(len(self.members)))
        if len(self.members) != len(self.member_ids):
            raise ValueError("members and member_ids must have the same length")

    @property
    def ensemble_mean(self) -> GriddedField:
        data = np.mean([m.data for m in self.members], axis=0)
        return GriddedField(
            data=data,
            lats=self.members[0].lats,
            lons=self.members[0].lons,
            variable=self.variable,
            source=self.source,
            valid_time=self.valid_time,
            init_time=self.init_time,
        )

    @property
    def ensemble_spread(self) -> GriddedField:
        data = np.std([m.data for m in self.members], axis=0)
        return GriddedField(
            data=data,
            lats=self.members[0].lats,
            lons=self.members[0].lons,
            variable=self.variable,
            source=self.source,
            valid_time=self.valid_time,
            init_time=self.init_time,
        )

    @property
    def member_array(self) -> np.ndarray:
        return np.array([m.data for m in self.members])


@dataclass
class PointForecast:
    """Forecast at a single point."""
    coord: Coordinate | None
    variable: Variable | None
    values: list[float]
    times: list[datetime]
    source: ModelSource | None
    init_time: datetime | None
    member_id: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StationObs:
    """Observation at a weather station."""
    station_id: str
    coord: Coordinate
    variable: Variable
    values: list[float]
    times: list[datetime]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RadarSweep:
    """Single radar sweep / composite."""
    data: np.ndarray
    lats: np.ndarray
    lons: np.ndarray
    scan_time: datetime
    elevation: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def dbz(self) -> np.ndarray:
        return self.data

    @property
    def shape(self) -> tuple[int, ...]:
        return self.data.shape

    @property
    def reflectivity_linear(self) -> np.ndarray:
        return 10.0 ** (self.data / 10.0)


@dataclass
class ThresholdAlert:
    """Alert triggered by threshold exceedance."""
    variable: Variable
    threshold: float
    operator: str  # "gt", "lt", "ge", "le"
    location: Coordinate
    trigger_time: datetime
    forecast_time: datetime
    value: float
    severity: str = "warning"
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationReport:
    """Results from forecast verification."""
    metric_name: str
    value: float
    variable: Variable
    source: ModelSource
    period_start: datetime
    period_end: datetime
    n_samples: int
    meta: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
