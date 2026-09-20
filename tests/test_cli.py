"""Tests for the barograph CLI."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from barograph.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Barograph" in result.output


def test_cli_no_config(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_ingest_no_files(runner):
    result = runner.invoke(cli, ["ingest"])
    assert result.exit_code != 0 or "No input files" in result.output


def test_check_alerts_no_field(runner):
    result = runner.invoke(cli, ["check-alerts", "--threshold", "50"])
    assert result.exit_code != 0 or "No field available" in result.output


def test_nowcast_no_radar(runner):
    result = runner.invoke(cli, ["nowcast"])
    assert result.exit_code != 0 or "Need at least 2 radar sweeps" in result.output


def test_load_rules_missing_file(runner):
    result = runner.invoke(cli, ["load-rules", "--rule-file", "nonexistent.yaml"])
    assert result.exit_code != 0


def test_downscale_no_field(runner):
    result = runner.invoke(cli, ["downscale"])
    assert result.exit_code != 0 or "Need --field or prior ingest" in result.output


def test_verify(runner):
    result = runner.invoke(cli, ["verify", "--metric", "crps"])
    assert result.exit_code == 0
    assert "Verification requested" in result.output


def test_config_show(runner):
    result = runner.invoke(cli, ["config-show"])
    assert result.exit_code == 0
    assert "raster:" in result.output
    assert "notifications:" in result.output
    assert "output:" in result.output


def test_notify_console(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["notify", "-t", "Hello", "-b", "World"])
    assert result.exit_code == 0
    assert "Delivery:" in result.output
    assert "console" in result.output


def test_export_no_field(runner):
    result = runner.invoke(cli, ["export", "--format", "json"])
    assert result.exit_code != 0 or "No field available" in result.output


def test_raster_summary_missing_file(runner):
    result = runner.invoke(cli, ["raster", "summary", "--file", "nope.nc"])
    assert result.exit_code != 0


def test_raster_group_help(runner):
    result = runner.invoke(cli, ["raster", "--help"])
    assert result.exit_code == 0
    assert "summary" in result.output
    assert "rainfall" in result.output
    assert "terrain" in result.output


def test_cli_help_lists_new_commands(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "climate",
        "risk",
        "model-train",
        "export",
        "notify",
        "qc",
        "derived",
        "extreme",
        "spi",
    ):
        assert cmd in result.output


def test_risk_requires_file(runner):
    result = runner.invoke(cli, ["risk", "-k", "hail"])
    assert result.exit_code != 0


def test_model_train_missing_csv(runner):
    result = runner.invoke(cli, ["model-train", "-d", "nope.csv"])
    assert result.exit_code != 0


def test_risk_cmd_smoke(runner, tmp_path):
    import numpy as np
    import xarray as xr

    path = tmp_path / "cape.nc"
    lat = np.linspace(-26, -20, 4)
    lon = np.linspace(-48, -44, 5)
    data = np.full((4, 5), 2000.0, dtype=np.float32)
    ds = xr.Dataset(
        {"cape": (("latitude", "longitude"), data)}, coords={"latitude": lat, "longitude": lon}
    )
    ds.attrs["crs"] = 4326
    ds.to_netcdf(path)
    result = runner.invoke(cli, ["risk", "-f", str(path), "-k", "hail"])
    assert result.exit_code == 0
    assert "hail index" in result.output


def test_qc_cmd_smoke(runner, tmp_path):

    path = tmp_path / "series.csv"
    path.write_text(
        "time,value\n"
        "2024-01-01T00:00:00,10\n"
        "2024-01-01T01:00:00,10\n"
        "2024-01-01T02:00:00,10\n"
        "2024-01-01T03:00:00,999\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        cli,
        ["qc", "-f", str(path), "--min-value", "-50", "--max-value", "50", "--persistence", "2"],
    )
    assert result.exit_code == 0
    assert "gross_error" in result.output
    assert "persistent" in result.output


def test_qc_cmd_missing_file(runner):
    result = runner.invoke(cli, ["qc", "-f", "nope.csv"])
    assert result.exit_code != 0


def test_derived_precip_smoke(runner, tmp_path):
    path = tmp_path / "precip.csv"
    path.write_text(
        "time,value\n"
        "2024-01-01T00:00:00,0\n"
        "2024-01-01T01:00:00,5\n"
        "2024-01-01T02:00:00,8\n"
        "2024-01-01T03:00:00,0\n",
        encoding="utf-8",
    )
    result = runner.invoke(cli, ["derived", "precip", "-s", str(path)])
    assert result.exit_code == 0
    assert "total_precip" in result.output


def test_derived_thermal(runner):
    result = runner.invoke(cli, ["derived", "thermal", "-t", "35", "--rh", "80"])
    assert result.exit_code == 0
    assert "dewpoint" in result.output
    assert "heat_index" in result.output


def test_extreme_cmd_smoke(runner, tmp_path):
    path = tmp_path / "extremes.csv"
    path.write_text(
        "value\n" + "\n".join(str(float(v)) for v in [10, 20, 15, 18, 12, 22, 9, 16, 30, 14]),
        encoding="utf-8",
    )
    result = runner.invoke(cli, ["extreme", "-f", str(path), "-p", "10"])
    assert result.exit_code == 0
    assert "n_blocks" in result.output
    assert "return levels" in result.output


def test_extreme_cmd_too_few(runner, tmp_path):
    path = tmp_path / "few.csv"
    path.write_text("value\n1\n2\n", encoding="utf-8")
    result = runner.invoke(cli, ["extreme", "-f", str(path)])
    assert result.exit_code != 0


def test_extreme_cmd_pot_method(runner, tmp_path):
    import numpy as np

    rng = np.random.default_rng(5)
    path = tmp_path / "series.csv"
    path.write_text(
        "value\n" + "\n".join(str(float(v)) for v in rng.exponential(scale=3.0, size=5000)),
        encoding="utf-8",
    )
    result = runner.invoke(cli, ["extreme", "-f", str(path), "-m", "pot", "-p", "20"])
    assert result.exit_code == 0
    assert "gpd scale" in result.output
    assert "return levels" in result.output


def test_spi_cmd_smoke(runner, tmp_path):
    path = tmp_path / "precip.csv"
    path.write_text(
        "time,value\n" + "".join(f"2021-01-01T00:00:00,{1.0 + (i % 3) * 0.5}\n" for i in range(30)),
        encoding="utf-8",
    )
    result = runner.invoke(cli, ["spi", "-f", str(path), "-w", "4", "--current"])
    assert result.exit_code == 0
    assert "Standardized Precipitation Index" in result.output
    assert "current_spi" in result.output


def test_spi_cmd_missing_file(runner):
    result = runner.invoke(cli, ["spi", "-f", "nope.csv"])
    assert result.exit_code != 0


def test_spei_cmd_smoke(runner, tmp_path):
    precip = tmp_path / "precip.csv"
    temp = tmp_path / "temp.csv"
    precip.write_text("time,precip\n" + "".join(f"{i},5.0\n" for i in range(40)), encoding="utf-8")
    temp.write_text("time,temp\n" + "".join(f"{i},20.0\n" for i in range(40)), encoding="utf-8")
    result = runner.invoke(
        cli,
        [
            "spei",
            "-p",
            str(precip),
            "-t",
            str(temp),
            "-la",
            "-15",
            "-w",
            "4",
            "--current",
        ],
    )
    assert result.exit_code == 0
    assert "SPEI" in result.output


def test_spei_cmd_missing_file(runner, tmp_path):
    temp = tmp_path / "temp.csv"
    temp.write_text("time,temp\n0,20.0\n", encoding="utf-8")
    result = runner.invoke(cli, ["spei", "-p", "nope.csv", "-t", str(temp), "-la", "0"])
    assert result.exit_code != 0


def test_spei_cmd_invalid_latitude(runner, tmp_path):
    precip = tmp_path / "precip.csv"
    temp = tmp_path / "temp.csv"
    precip.write_text("time,precip\n0,5.0\n", encoding="utf-8")
    temp.write_text("time,temp\n0,20.0\n", encoding="utf-8")
    result = runner.invoke(cli, ["spei", "-p", str(precip), "-t", str(temp), "-la", "120"])
    assert result.exit_code != 0
