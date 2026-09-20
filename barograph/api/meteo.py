"""Client for the public Open-Meteo forecast and history APIs.

Open-Meteo (https://open-meteo.com) provides free, attribution-free forecast
and historical weather data without an API key. This module wraps a small
subset of its endpoints into typed objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from barograph.api.client import HTTPClient

_DEFAULT_BASE = "https://api.open-meteo.com/v1"


@dataclass
class CurrentWeather:
    """Current conditions at a point."""

    time: datetime
    temperature_2m: float | None = None
    relative_humidity_2m: float | None = None
    wind_speed_10m: float | None = None
    wind_direction_10m: float | None = None
    precipitation: float | None = None
    weather_code: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class HourlyForecast:
    """A single variable's hourly series for a location."""

    times: list[datetime]
    values: list[float | None]
    variable: str

    def __len__(self) -> int:
        return len(self.times)

    def to_series_data(self) -> tuple[list[datetime], list[float]]:
        """Return ``(times, values)`` pairs dropping missing entries."""
        times: list[datetime] = []
        values: list[float] = []
        for t, v in zip(self.times, self.values):
            if v is not None:
                times.append(t)
                values.append(v)
        return times, values


@dataclass
class DailyForecast:
    """Daily aggregates for a location."""

    dates: list[datetime]
    temperature_max: list[float | None]
    temperature_min: list[float | None]
    precipitation_sum: list[float | None]
    wind_speed_max: list[float | None]

    def __len__(self) -> int:
        return len(self.dates)


class OpenMeteo:
    """Thin typed client for the Open-Meteo API.

    Args:
        base_url: Override the API base URL (useful for tests/vendors).
        client: An :class:`HTTPClient`; defaults to a retrying client.
    """

    def __init__(self, base_url: str = _DEFAULT_BASE, client: HTTPClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.client = client or HTTPClient()

    def current(
        self,
        latitude: float,
        longitude: float,
    ) -> CurrentWeather:
        """Fetch current conditions at a point."""
        payload = self.client.get_json(
            f"{self.base_url}/forecast",
            latitude=latitude,
            longitude=longitude,
            current="temperature_2m,relative_humidity_2m,wind_speed_10m,"
            "wind_direction_10m,precipitation,weather_code",
        )
        cur = payload.get("current", {})
        cur_time = _parse_single_time(cur.get("time"))
        return CurrentWeather(
            time=cur_time or datetime.now(),
            temperature_2m=cur.get("temperature_2m"),
            relative_humidity_2m=cur.get("relative_humidity_2m"),
            wind_speed_10m=cur.get("wind_speed_10m"),
            wind_direction_10m=cur.get("wind_direction_10m"),
            precipitation=cur.get("precipitation"),
            weather_code=cur.get("weather_code"),
            raw=cur,
        )

    def hourly(
        self,
        latitude: float,
        longitude: float,
        variables: list[str],
        forecast_days: int = 3,
    ) -> dict[str, HourlyForecast]:
        """Fetch an hourly forecast series for the requested variables."""
        payload = self.client.get_json(
            f"{self.base_url}/forecast",
            latitude=latitude,
            longitude=longitude,
            hourly=",".join(variables),
            forecast_days=forecast_days,
            timezone="UTC",
        )
        hourly = payload.get("hourly", {})
        times = _parse_times(hourly.get("time", []))
        out: dict[str, HourlyForecast] = {}
        for var in variables:
            raw_values = hourly.get(var, [])
            values: list[float | None] = []
            for v in raw_values:
                values.append(None if v is None else float(v))
            out[var] = HourlyForecast(times=times, values=values, variable=var)
        return out

    def daily(
        self,
        latitude: float,
        longitude: float,
        past_days: int = 0,
        forecast_days: int = 5,
    ) -> DailyForecast:
        """Fetch a daily forecast series."""
        payload = self.client.get_json(
            f"{self.base_url}/forecast",
            latitude=latitude,
            longitude=longitude,
            daily="temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            forecast_days=forecast_days,
            past_days=past_days,
            timezone="UTC",
        )
        daily = payload.get("daily", {})
        return DailyForecast(
            dates=_parse_dates(daily.get("time", [])),
            temperature_max=_to_float_list(daily.get("temperature_2m_max")),
            temperature_min=_to_float_list(daily.get("temperature_2m_min")),
            precipitation_sum=_to_float_list(daily.get("precipitation_sum")),
            wind_speed_max=_to_float_list(daily.get("wind_speed_10m_max")),
        )


def _to_float_list(raw: Any) -> list[float | None]:
    if not isinstance(raw, list):
        return []
    out: list[float | None] = []
    for v in raw:
        out.append(None if v is None else float(v))
    return out


def _parse_single_time(raw: Any) -> datetime | None:
    """Parse a single ISO timestamp string, or ``None`` if missing/bad."""
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_times(raw: Any) -> list[datetime]:
    if not isinstance(raw, list):
        return []
    out: list[datetime] = []
    for item in raw:
        try:
            out.append(datetime.fromisoformat(str(item).replace("Z", "+00:00")))
        except ValueError:
            continue
    return out


def _parse_dates(raw: Any) -> list[datetime]:
    if not isinstance(raw, list):
        return []
    out: list[datetime] = []
    for item in raw:
        try:
            out.append(datetime.fromisoformat(str(item)))
        except ValueError:
            continue
    return out
