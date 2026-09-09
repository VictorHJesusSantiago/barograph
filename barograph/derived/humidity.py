"""Humidity-related derived quantities using Magnus-type saturation curves."""

from __future__ import annotations

import numpy as np


def saturation_vapor_pressure(temperature: float) -> float:
    """Saturation vapour pressure (hPa) via the Magnus formula.

    Args:
        temperature: Air temperature in degrees Celsius.
    """
    return 6.1094 * np.exp((17.625 * temperature) / (temperature + 243.04))


def vapor_pressure(
    temperature: float, relative_humidity_in: float
) -> float:
    """Actual vapour pressure (hPa).

    Args:
        temperature: Air temperature in degrees Celsius.
        relative_humidity_in: Relative humidity in percent (0..100).
    """
    rh = np.clip(relative_humidity_in, 0.0, 100.0)
    return rh / 100.0 * saturation_vapor_pressure(temperature)


def dewpoint(
    temperature: float, relative_humidity_in: float
) -> float:
    """Dewpoint temperature (Celsius) from temperature and relative humidity."""
    rh = np.clip(relative_humidity_in, 0.0, 100.0)
    if rh <= 1e-9:
        return float("-inf")
    gamma = np.log(rh / 100.0) + (17.625 * temperature) / (
        temperature + 243.04
    )
    return 243.04 * gamma / (17.625 - gamma)


def relative_humidity(temperature: float, dewpoint_in: float) -> float:
    """Relative humidity (percent) from temperature and dewpoint."""
    es = saturation_vapor_pressure(temperature)
    e = saturation_vapor_pressure(dewpoint_in)
    rh = 100.0 * e / es
    return float(np.clip(rh, 0.0, 100.0))


def absolute_humidity(temperature: float, relative_humidity_in: float) -> float:
    """Absolute humidity (g/m^3) from temperature and relative humidity."""
    rh = np.clip(relative_humidity_in, 0.0, 100.0)
    e_hpa = vapor_pressure(temperature, rh)
    # ideal gas: 1 hPa = 100 Pa; Rw = 461.5 J/(kg·K); g/m^3
    return 1000.0 * (100.0 * e_hpa) / (461.5 * (temperature + 273.15))


__all__ = [
    "saturation_vapor_pressure",
    "vapor_pressure",
    "dewpoint",
    "relative_humidity",
    "absolute_humidity",
]
