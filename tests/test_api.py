"""Tests for the real-time data API clients."""

from __future__ import annotations

import json

import pytest

from barograph.api import HTTPClient, HTTPError
from barograph.api.meteo import OpenMeteo


def fake_transport(payload: dict, status: int = 200):
    def transport(url, **kwargs):
        return status, json.dumps(payload)
    return transport


def test_http_client_get_json_success():
    transport = fake_transport({"ok": True})
    client = HTTPClient(transport=transport)
    assert client.get_json("http://example.invalid/x") == {"ok": True}


def test_http_client_retries_then_raises():
    calls = {"n": 0}

    def transport(url, **kwargs):
        calls["n"] += 1
        return 500, "boom"

    client = HTTPClient(transport=transport, max_retries=2, backoff_seconds=0.0)
    with pytest.raises(HTTPError):
        client.get_text("http://example.invalid/x")
    assert calls["n"] == 3  # initial + 2 retries


def test_http_client_query_params_encoded():
    seen = {}

    def transport(url, **kwargs):
        seen["url"] = url
        return 200, "{}"

    HTTPClient(transport=transport).get_json("http://example.invalid/x", lat=-23.5)
    assert "lat=-23.5" in seen["url"]


def test_http_client_transport_exception_retried():
    calls = {"n": 0}

    def transport(url, **kwargs):
        calls["n"] += 1
        raise ConnectionError("refused")

    client = HTTPClient(transport=transport, max_retries=1, backoff_seconds=0.0)
    with pytest.raises(HTTPError):
        client.get_text("http://example.invalid/x")
    assert calls["n"] == 2


def test_openmeteo_current_parsing():
    base = "http://meteo.test"
    payload = {
        "current": {
            "time": "2026-01-01T12:00",
            "temperature_2m": 21.5,
            "relative_humidity_2m": 63.0,
            "wind_speed_10m": 12.0,
            "precipitation": 0.0,
            "weather_code": 1,
        }
    }
    client = OpenMeteo(base_url=base, client=HTTPClient(transport=fake_transport(payload)))
    cur = client.current(-23.5, -46.6)
    assert cur.temperature_2m == 21.5
    assert cur.relative_humidity_2m == 63.0
    assert cur.wind_speed_10m == 12.0
    assert cur.time.year == 2026


def test_openmeteo_hourly_parsing():
    base = "http://meteo.test"
    payload = {
        "hourly": {
            "time": ["2026-01-01T00:00", "2026-01-01T01:00"],
            "temperature_2m": [10.0, None],
        }
    }
    client = OpenMeteo(base_url=base,
                       client=HTTPClient(transport=fake_transport(payload)))
    hf = client.hourly(-23.5, -46.6, ["temperature_2m"], forecast_days=1)
    ts, vs = hf["temperature_2m"].to_series_data()
    assert ts[0].hour == 0
    assert vs == [10.0]  # None dropped


def test_openmeteo_daily_parsing():
    base = "http://meteo.test"
    payload = {
        "daily": {
            "time": ["2026-01-01"],
            "temperature_2m_max": [28.0],
            "temperature_2m_min": [15.0],
            "precipitation_sum": [4.0],
            "wind_speed_10m_max": [22.0],
        }
    }
    client = OpenMeteo(base_url=base,
                       client=HTTPClient(transport=fake_transport(payload)))
    daily = client.daily(-23.5, -46.6, forecast_days=1)
    assert len(daily) == 1
    assert daily.temperature_max == [28.0]
    assert daily.precipitation_sum == [4.0]
