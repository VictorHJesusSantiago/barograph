"""Thermal comfort indices derived from temperature, wind and humidity.

Implements the wind chill (Bluestein & Zecher / NWS), heat index
(Rothfusz regression, NWS) and apparent temperature (Steadman) formulas.
"""

from __future__ import annotations

import numpy as np

from barograph.derived.humidity import vapor_pressure


def wind_chill(temperature: float, wind_speed: float) -> float:
    """Wind chill (Celsius) from air temperature and 10-m wind speed (km/h).

    The NWS formula is only defined for temperatures at or below 10C and
    winds of at least 4.8 km/h; otherwise the air temperature is returned.
    """
    if temperature > 10.0 or wind_speed < 4.8:
        return temperature
    v_kmh = wind_speed
    t_c = temperature
    return 13.12 + 0.6215 * t_c - 11.37 * v_kmh**0.16 + 0.3965 * t_c * v_kmh**0.16


def heat_index(temperature: float, relative_humidity_in: float) -> float:
    """Heat index (Celsius) using the NWS Rothfusz regression.

    Returns the air temperature when the index is not applicable
    (temperature below 27C or relative humidity below 40%).
    """
    if temperature < 27.0 or relative_humidity_in < 40.0:
        return temperature
    t = temperature
    rh = np.clip(relative_humidity_in, 0.0, 100.0)
    hi = (
        -8.78469475556
        + 1.61139411 * t
        + 2.33854883889 * rh
        - 0.14611605 * t * rh
        - 0.012308094 * t * t
        - 0.0164248277778 * rh * rh
        + 0.002211732 * t * t * rh
        + 0.00072546 * t * rh * rh
        - 0.000003582 * t * t * rh * rh
    )
    return float(hi)


def apparent_temperature(
    temperature: float,
    relative_humidity_in: float,
    wind_speed: float = 0.0,
) -> float:
    """Apparent (Steadman) temperature (Celsius) combining humidity and wind.

    Args:
        temperature: Air temperature in Celsius.
        relative_humidity_in: Relative humidity in percent (0..100).
        wind_speed: 10-m wind speed in metres per second (0 disables wind).
    """
    e = vapor_pressure(temperature, relative_humidity_in)
    v = wind_speed
    at = (
        temperature + 0.33 * e - 0.70 * wind_chill(temperature, v * 3.6) - 4.00
        if v > 0.0
        else temperature + 0.33 * e
    )
    return float(at)


__all__ = ["wind_chill", "heat_index", "apparent_temperature"]
