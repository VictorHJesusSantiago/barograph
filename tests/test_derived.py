import numpy as np
import pytest

from barograph.derived.humidity import (
    absolute_humidity,
    dewpoint,
    relative_humidity,
    saturation_vapor_pressure,
    vapor_pressure,
)
from barograph.derived.thermal import (
    apparent_temperature,
    heat_index,
    wind_chill,
)


def test_saturation_vapor_pressure_positive():
    assert saturation_vapor_pressure(0.0) > 0
    assert saturation_vapor_pressure(20.0) > saturation_vapor_pressure(0.0)


def test_vapor_pressure_scales_with_rh():
    e50 = vapor_pressure(20.0, 50.0)
    e100 = vapor_pressure(20.0, 100.0)
    assert e100 == pytest.approx(2 * e50, rel=1e-3)


def test_dewpoint_roundtrip_relative_humidity():
    t = 20.0
    rh = 65.0
    td = dewpoint(t, rh)
    assert td < t
    assert td >= 0.0
    assert relative_humidity(t, td) == pytest.approx(rh, abs=0.5)


def test_dewpoint_zero_rh():
    assert np.isneginf(dewpoint(20.0, 0.0))


def test_relative_humidity_100_at_dewpoint():
    assert relative_humidity(25.0, 25.0) == pytest.approx(100.0, abs=0.1)


def test_absolute_humidity_positive():
    assert absolute_humidity(20.0, 60.0) > 0


def test_wind_chill_lower_in_wind():
    still = wind_chill(5.0, 3.0)
    windy = wind_chill(5.0, 40.0)
    assert windy < still


def test_wind_chill_returns_temperature_when_warm():
    assert wind_chill(15.0, 50.0) == 15.0


def test_heat_index_hot_humid():
    hi = heat_index(35.0, 80.0)
    assert hi > 35.0


def test_heat_index_not_applicable_cool():
    assert heat_index(20.0, 80.0) == 20.0


def test_apparent_temperature_wind_cools():
    calm = apparent_temperature(25.0, 10.0, wind_speed=0.0)
    windy = apparent_temperature(25.0, 10.0, wind_speed=10.0)
    # Steadman apparent temperature with strong wind lowers the value
    assert windy < calm


def test_apparent_temperature_humidity_warms_in_heat():
    dry = apparent_temperature(32.0, 20.0)
    humid = apparent_temperature(32.0, 80.0)
    assert humid > dry
