"""Tests for report/dashboard generation and output serialization."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from barograph.core.models import (
    Coordinate,
    GriddedField,
    ModelSource,
    ThresholdAlert,
    Variable,
)
from barograph.output.plots import FieldPlotter
from barograph.output.serializers import OutputWriter
from barograph.raster.layer import RasterLayer
from barograph.reports.dashboard import VerificationDashboard
from barograph.reports.renderer import ReportRenderer


def make_field(size=6, val=2.0):
    lats = np.linspace(-25.0, -20.0, size)
    lons = np.linspace(-50.0, -45.0, size)
    data = np.full((size, size), val, dtype=np.float32)
    return GriddedField(
        data=data,
        lats=lats,
        lons=lons,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, 12),
        init_time=datetime(2026, 1, 1, 0),
    )


def make_alert():
    return ThresholdAlert(
        variable=Variable.PRECIPITATION,
        threshold=50.0,
        operator="ge",
        location=Coordinate(-23.5, -46.5),
        trigger_time=datetime(2026, 1, 1, 12),
        forecast_time=datetime(2026, 1, 1, 15),
        value=70.0,
        severity="severe",
        message="Heavy rain",
    )


def test_alerts_to_json(tmp_path):
    path = ReportRenderer.alerts_to_json([make_alert()], tmp_path / "a.json")
    assert path.exists()
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["variable"] == "precipitation"
    assert data[0]["value"] == 70.0


def test_alerts_to_csv(tmp_path):
    path = ReportRenderer.alerts_to_csv([make_alert()], tmp_path / "a.csv")
    content = path.read_text(encoding="utf-8")
    assert "variable" in content
    assert "70.0" in content


def test_alerts_to_markdown():
    text = ReportRenderer.alerts_to_markdown([make_alert()])
    assert "Heavy rain" in text
    assert text.startswith("# Alerts")


def test_field_summary():
    summary = ReportRenderer.field_summary(make_field())
    assert "temperature" in summary
    assert "2.00" in summary


def test_dashboard_combined_and_json(tmp_path):
    db = VerificationDashboard()
    db.add_metrics("case_a", {"mae": 1.0, "rmse": 2.0})
    db.add_metrics("case_b", {"mae": 3.0, "rmse": 4.0})
    db.add_series("case_a", {"mae": [1.0, 2.0, 3.0]})
    combined = db.combined()
    assert combined["case_a"]["mae"] == pytest.approx(1.0)
    assert combined["case_b"]["rmse"] == pytest.approx(4.0)

    path = db.to_json(tmp_path / "db.json")
    loaded = VerificationDashboard.load_json(path)
    assert loaded.title == "Barograph Verification Dashboard"
    assert "case_a" in loaded.metric_samples


def test_dashboard_html(tmp_path):
    db = VerificationDashboard(title="My Dash")
    db.add_metrics("case_a", {"mae": 1.23})
    path = db.to_html(tmp_path / "db.html")
    content = path.read_text(encoding="utf-8")
    assert "My Dash" in content
    assert "mae" in content
    assert "1.2300" in content


def test_output_writer_json(tmp_path):
    writer = OutputWriter(fmt="json", base_dir=tmp_path)
    path = writer.write(make_field())
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metadata"]["variable"] == "temperature"
    assert "data" in data


def test_output_writer_csv(tmp_path):
    writer = OutputWriter(fmt="csv", base_dir=tmp_path)
    path = writer.write(make_field(size=4))
    content = path.read_text(encoding="utf-8")
    assert "lat\\lon" in content


def test_output_writer_netcdf(tmp_path):
    writer = OutputWriter(fmt="netcdf", base_dir=tmp_path)
    path = writer.write(make_field())
    import xarray as xr

    ds = xr.open_dataset(path)
    assert "temperature" in ds


def test_output_writer_npy(tmp_path):
    writer = OutputWriter(fmt="npy", base_dir=tmp_path)
    path = writer.write(make_field())
    arr = np.load(path)
    assert arr.shape == (6, 6)


def test_output_writer_raster(tmp_path):
    lats = np.linspace(-25, -20, 5)
    lons = np.linspace(-50, -45, 5)
    layer = RasterLayer(
        data=np.full((5, 5), 3.0, dtype=np.float32), lats=lats, lons=lons, name="precip"
    )
    writer = OutputWriter(fmt="json", base_dir=tmp_path)
    path = writer.write(layer)
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metadata"]["type"] == "raster"
    assert data["metadata"]["name"] == "precip"


def test_output_writer_zarr(tmp_path):
    writer = OutputWriter(fmt="zarr", base_dir=tmp_path)
    path = writer.write(make_field())
    assert path.exists()


def test_field_plotter_png_or_skip(tmp_path):
    try:
        FieldPlotter()
    except ImportError:
        pytest.skip("matplotlib not installed")
    path = FieldPlotter().save(make_field(), tmp_path / "field.png")
    assert path.exists()
    assert path.stat().st_size > 0


def test_field_plotter_missing_matplotlib(tmp_path):
    # monkeypatch import to simulate absence
    import barograph.output.plots as plots

    original = FieldPlotter.save
    _ = original

    def fake_require():
        raise ImportError("no matplotlib")

    plots.FieldPlotter._require_matplotlib = staticmethod(fake_require)  # type: ignore[assignment]
    with pytest.raises(ImportError):
        FieldPlotter().save(make_field(), tmp_path / "field.png")
