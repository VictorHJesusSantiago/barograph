"""Barograph command-line interface.

A richer Click-based CLI exposing commands for data ingestion, downscaling,
nowcasting, verification, alerts, raster analysis, notifications, reporting
and output.
"""

from __future__ import annotations

from pathlib import Path

import click
import numpy as np

from barograph.core.config import load_config
from barograph.utils.logging import setup_logging


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), default=None,
              help="Path to YAML config file.")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: bool) -> None:
    """Barograph: weather forecast modeling, post-processing and verification."""
    ctx.ensure_object(dict)
    settings = load_config(config)
    level = "DEBUG" if verbose else settings.log_level
    setup_logging(level)
    ctx.obj["settings"] = settings
    ctx.obj["verbose"] = verbose


def _echo_title(text: str) -> None:
    click.echo("=" * 60)
    click.echo(text)
    click.echo("=" * 60)


@cli.command()
@click.option("--gfs-file", type=click.Path(exists=True), help="Path to GFS GRIB2 file.")
@click.option("--ecmwf-file", type=click.Path(exists=True), help="Path to ECMWF GRIB file.")
@click.option("--variable", "-var", required=True, default="temperature",
              help="Variable name (temperature, precipitation, ...).")
@click.pass_context
def ingest(ctx, gfs_file, ecmwf_file, variable):
    """Ingest and parse NWP model files."""
    settings = ctx.obj.get("settings")

    if gfs_file:
        from barograph.ingestion import GFSIngester
        ingester = GFSIngester(settings.ingestion)
        field = ingester.parse_grib(gfs_file, variable)
        click.echo(f"Parsed GFS: {field.shape} | var={field.variable.value} | "
                   f"valid={field.valid_time}")
        ctx.obj["last_field"] = field

    if ecmwf_file:
        from barograph.ingestion import ECMWFIngester
        ingester = ECMWFIngester(settings.ingestion)
        field = ingester.parse_grib(ecmwf_file, variable)
        click.echo(f"Parsed ECMWF: {field.shape} | var={field.variable.value} | "
                   f"valid={field.valid_time}")
        ctx.obj["last_field"] = field

    if not gfs_file and not ecmwf_file:
        click.echo("No input files provided. Use --gfs-file or --ecmwf-file.")
        raise click.Abort()


@cli.command()
@click.option("--field", "-f", type=click.Path(exists=True),
              help="Path to a saved forecast NetCDF.")
@click.option("--variable", "-var", default="precipitation",
              help="Variable to downscale.")
@click.pass_context
def downscale(ctx, field, variable):
    """Statistically downscale a coarse forecast using QDT or bias correction."""
    settings = ctx.obj.get("settings")
    from barograph.utils.storage import load_gridded_field

    if field:
        coarse_field = load_gridded_field(field)
    elif "last_field" in ctx.obj:
        coarse_field = ctx.obj["last_field"]
    else:
        click.echo("Need --field or prior ingest.")
        raise click.Abort()

    method = settings.downscaling.method
    if method == "quantile_delta_transform":
        click.echo(f"Requested QDT downscaling of {coarse_field.variable.value} "
                   f"({coarse_field.shape})")
    else:
        click.echo(f"Bias correction downscaling requested for {variable} "
                   f"({coarse_field.shape})")


@cli.command()
@click.option("--field", "-f", type=click.Path(exists=True),
              help="Path to saved NetCDF field to check.")
@click.option("--threshold", type=float, required=True)
@click.option("--variable", "-var", default="precipitation")
@click.option("--lat-range", type=(float, float), default=None,
              help="Latitude min,max for region.")
@click.option("--lon-range", type=(float, float), default=None,
              help="Longitude min,max for region.")
@click.option("--format", "-fmt", "out_format", type=click.Choice(
    ["json", "csv", "markdown", "netcdf"]), default="json",
    help="Output format for the alert report.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file for the alert report.")
@click.pass_context
def check_alerts(ctx, field, threshold, variable, lat_range, lon_range,
                 out_format, output):
    """Check a gridded forecast against threshold alert rules."""
    from barograph.alerts import AlertEngine
    from barograph.alerts.rules import AlertRule, Operator, Severity
    from barograph.core.models import Variable
    from barograph.utils.storage import load_gridded_field

    field_obj = load_gridded_field(field) if field else ctx.obj.get("last_field")
    if field_obj is None:
        click.echo("No field available. Provide --field or ingest first.")
        raise click.Abort()

    settings = ctx.obj.get("settings")
    engine = AlertEngine(
        cooldown_minutes=settings.alerts.cooldown_minutes,
        notification_channels=settings.alerts.notification_channels,
    )
    rule = AlertRule(
        variable=Variable(variable),
        threshold=threshold,
        operator=Operator.GREATER_OR_EQUAL,
        severity=Severity.WARNING,
        name=f"{variable}_gt_{threshold}",
    )
    engine.add_rule(rule)

    alerts = engine.evaluate_field(field_obj, lat_range, lon_range)
    click.echo(f"Found {len(alerts)} alert(s):")
    for a in alerts:
        click.echo(f"  {a.severity}: {a.message}")

    if alerts and output:
        from barograph.reports.renderer import ReportRenderer
        if out_format == "json":
            ReportRenderer.alerts_to_json(alerts, output)
        elif out_format == "csv":
            ReportRenderer.alerts_to_csv(alerts, output)
        elif out_format == "markdown":
            Path(output).write_text(ReportRenderer.alerts_to_markdown(alerts),
                                    encoding="utf-8")
        click.echo(f"Report written to {output}")


@cli.command()
@click.option("--members-dir", "-d", type=click.Path(exists=True),
              help="Directory of member NetCDF files.")
@click.option("--metric", "-m", default="crps",
              help="Verification metric to compute.")
@click.option("--dashboard", "-db", type=click.Path(), default=None,
              help="Path to write a verification dashboard (JSON or .html).")
@click.pass_context
def verify(ctx, members_dir, metric, dashboard):
    """Run verification on forecast ensembles and emit a dashboard."""
    _ = ctx.obj
    click.echo(f"Verification requested with metric={metric}, dir={members_dir}")
    if dashboard:
        from barograph.reports.dashboard import VerificationDashboard
        db = VerificationDashboard(title="Barograph Verification")
        db.add_metrics("demo",
                       {"mae": 1.2, "rmse": 1.8, "bias": 0.4, "correlation": 0.93})
        db.add_series("demo", {"mae": [1.1, 1.3, 1.2, 1.0]})
        out = Path(dashboard)
        if out.suffix == ".html":
            db.to_html(out)
        else:
            db.to_json(out)
        click.echo(f"Dashboard written to {dashboard}")


@cli.command()
@click.option("--radar-dir", "-r", type=click.Path(exists=True),
              help="Directory of radar sweep NetCDF files.")
@click.option("--lead-minutes", "-l", default=60,
              help="Lead time in minutes for nowcast.")
@click.pass_context
def nowcast(ctx, radar_dir, lead_minutes):
    """Run radar nowcasting via optical flow."""
    from barograph.ingestion import RadarIngester
    from barograph.nowcasting import Extrapolator

    _ = ctx.obj
    ingester = RadarIngester()
    sweeps = ingester.parse_directory(radar_dir) if radar_dir else []

    if len(sweeps) < 2:
        click.echo("Need at least 2 radar sweeps for motion estimation.")
        raise click.Abort()

    ext = Extrapolator()
    u, v, dt_hours = ext.estimate_motion(sweeps)
    click.echo(f"Estimated motion: mean_u={u.mean():.3f} px/h, "
               f"mean_v={v.mean():.3f} px/h, dt={dt_hours:.2f}h")

    from datetime import timedelta
    results = ext.nowcast(sweeps, [timedelta(minutes=lead_minutes)])
    click.echo(f"Nowcast produced for +{lead_minutes} min: "
               f"shape={results[0].shape}")


@cli.command()
@click.option("--rule-file", "-r", type=click.Path(exists=True),
              help="YAML file of alert rules.")
@click.pass_context
def load_rules(ctx, rule_file):
    """Load alert rules from a YAML file."""
    from barograph.alerts import AlertEngine

    _ = ctx.obj
    engine = AlertEngine()
    engine.load_rules(rule_file)
    click.echo(f"Loaded {len(engine.rules)} alert rules:")
    for rule in engine.rules:
        click.echo(f"  - {rule.name} ({rule.severity.value})")


@cli.group()
def raster():
    """Raster data layer operations."""


@raster.command("summary")
@click.option("--file", "-f", "path", type=click.Path(exists=True), required=True,
              help="Path to a NetCDF/PyNIO raster file.")
@click.option("--lat", type=click.FloatRange(-90, 90), default=None,
              help="Latitude of a point to sample.")
@click.option("--lon", type=click.FloatRange(-180, 180), default=None,
              help="Longitude of a point to sample.")
@click.pass_context
def raster_summary(ctx, path, lat, lon):
    """Print a summary of a raster layer, optionally sampling a point."""
    layer = _load_raster(path)
    _echo_title(f"Raster summary: {layer.name}")
    for key, value in layer.summary().items():
        click.echo(f"  {key}: {value}")
    if lat is not None and lon is not None:
        row, col = layer.pixel_nearest(lat, lon)
        val = layer.value_at(lat, lon)
        click.echo(f"  sample({lat},{lon}) -> row={row}, col={col}, value={val}")


@raster.command("rainfall")
@click.option("--file", "-f", "path", type=click.Path(exists=True), required=True,
              help="dBZ raster file.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Where to write the rainfall-rate raster.")
@click.option("--format", "-fmt", "fmt", type=click.Choice(
    ["netcdf", "npy", "json"]), default="netcdf")
@click.pass_context
def raster_rainfall(ctx, path, output, fmt):
    """Convert a radar dBZ raster to rainfall rate (Z-R)."""
    from barograph.output.serializers import OutputWriter
    from barograph.raster.reflectivity import Reflectivity
    layer = _load_raster(path)
    rate = Reflectivity().to_raster(layer)
    used = settings(ctx).output
    if output:
        used.base_dir = Path(output)
    used.format = fmt
    writer = OutputWriter(fmt=fmt, base_dir=Path(output or used.base_dir))
    p = writer.write_grid(rate, output)
    click.echo(f"Rainfall rate raster written to {p}")


@raster.command("terrain")
@click.option("--file", "-f", "path", type=click.Path(exists=True), required=True,
              help="DEM raster file.")
@click.option("--variable", "-v", "voi", type=click.Choice(
    ["slope", "aspect", "curvature", "hillshade", "ruggedness"]),
    default="slope")
@click.option("--output", "-o", type=click.Path(), default=None)
@click.pass_context
def raster_terrain(ctx, path, voi, output):
    """Derive a terrain parameter from a DEM."""
    from barograph.output.serializers import OutputWriter
    from barograph.raster.algebra import RasterAlgebra
    from barograph.raster.layer import RasterLayer
    from barograph.raster.terrain import Terrain

    dem = _load_raster(path)
    func = getattr(Terrain, voi)
    result = func(dem)
    layer = RasterLayer(data=result[np.newaxis, ...], lats=dem.lats, lons=dem.lons,
                        name=voi)
    if output:
        writer = OutputWriter(fmt="netcdf", base_dir=Path(output).parent)
        p = writer.write_grid(layer, output)
        click.echo(f"{voi} written to {p}")
    else:
        _echo_title(f"Terrain: {voi}")
        for key, value in RasterAlgebra.stats(layer).items():
            click.echo(f"  {key}: {value:.4f}")


@cli.command("notify")
@click.option("--title", "-t", required=True)
@click.option("--body", "-b", required=True)
@click.option("--severity", "-s", type=click.Choice(
    ["info", "warning", "critical"]), default="info")
@click.pass_context
def notify_cmd(ctx, title, body, severity):
    """Send a test notification through configured channels."""
    from barograph.notifications import NotificationManager, NotificationMessage
    cfg = settings(ctx).notifications
    manager = NotificationManager(
        channels=cfg.channels,
        webhook_url=cfg.webhook_url or None,
        max_retries=cfg.max_retries,
        backoff_base=cfg.backoff_base,
        timeout_seconds=cfg.timeout_seconds,
        file_path=cfg.file_path or None,
    )
    results = manager.notify(NotificationMessage(title=title, body=body,
                                                 severity=severity))
    for r in results:
        status = "OK" if r.delivered else f"FAILED ({r.error})"
        click.echo(f"  [{r.channel}] {status} (attempts={r.attempts})")
    click.echo(f"Delivery: {manager.delivery_metrics()}")


@cli.command("export")
@click.option("--field", "-f", "path", type=click.Path(exists=True),
              help="Path to a NetCDF grid field to export.")
@click.option("--format", "-fmt", "fmt", type=click.Choice(
    ["json", "csv", "netcdf", "zarr", "npy", "png"]), default="json")
@click.option("--output", "-o", type=click.Path(), default=None)
@click.pass_context
def export_cmd(ctx, path, fmt, output):
    """Export a field/analysis to a chosen format (incl. PNG rendering)."""
    if fmt == "png":
        from barograph.output.plots import FieldPlotter
        from barograph.utils.storage import load_gridded_field
        field = load_gridded_field(path) if path else ctx.obj.get("last_field")
        if field is None:
            click.echo("No field available.")
            raise click.Abort()
        out = output or f"{field.variable.value}.png"
        FieldPlotter().save(field, out)
        click.echo(f"Rendered PNG to {out}")
        return

    from barograph.output.serializers import OutputWriter
    from barograph.utils.storage import load_gridded_field
    field = load_gridded_field(path) if path else ctx.obj.get("last_field")
    if field is None:
        click.echo("No field available.")
        raise click.Abort()
    writer = OutputWriter(fmt=fmt, base_dir=Path(output).parent if output else Path("output"))
    p = writer.write(field, output)
    click.echo(f"Exported to {p}")


@cli.command("config-show")
@click.pass_context
def config_show(ctx):
    """Print the active configuration as YAML."""
    import yaml
    cfg = _config_to_dict(settings(ctx))
    click.echo(yaml.safe_dump(cfg, sort_keys=False))


def _config_to_dict(settings) -> dict:
    from dataclasses import asdict
    return asdict(settings)


@cli.command("climate")
@click.option("--lats", "-la", type=click.FloatRange(-90, 90), required=True,
              help="Latitude of the point.")
@click.option("--lons", "-lo", type=click.FloatRange(-180, 180), required=True,
              help="Longitude of the point.")
@click.option("--days", "-d", type=int, default=10,
              help="Number of forecast days to fetch.")
def climate_cmd(lats, lons, days):
    """Fetch and summarize daily weather for a point (Open-Meteo)."""
    from barograph.api import OpenMeteo

    daily = OpenMeteo().daily(lats, lons, forecast_days=days)
    if len(daily) == 0:
        click.echo("No daily data returned.")
        raise click.Abort()
    temps = [v for v in daily.temperature_max if v is not None]
    if not temps:
        click.echo("No forecast temperatures available.")
        return
    mean = sum(temps) / len(temps)
    precip = sum(v for v in daily.precipitation_sum if v)
    _echo_title(f"Daily summary: {lats:.2f}, {lons:.2f} ({len(daily)} days)")
    click.echo(f"  n_days: {len(daily)}")
    click.echo(f"  max_t_mean: {mean:.1f} C")
    click.echo(f"  precipitation_sum: {precip:.1f} mm")


@cli.command("risk")
@click.option("--file", "-f", "path", type=click.Path(exists=True),
              help="NetCDF raster field to evaluate.")
@click.option("--kind", "-k", type=click.Choice(["hail", "wind", "flood"]),
              required=True)
@click.pass_context
def risk_cmd(ctx, path, kind):
    """Compute a hazard index from a raster field."""
    from barograph.risk import HailIndex, WindRiskIndex, flood_risk_score

    layer = _load_raster(path)
    band = layer.band(0).astype(np.float64)
    if kind == "hail":
        score = HailIndex().compute(cape=band, srh=band * 0.1, shear=band * 0.01)
        label = "hail index"
    elif kind == "wind":
        score = WindRiskIndex().compute(band)
        label = "wind risk (0..1)"
    else:
        score = flood_risk_score(rainfall=band, antecedent=band * 2,
                                 soil_moisture=np.full(band.shape, 0.5))
        label = "flood risk (0..1)"
    _echo_title(f"{label} of {layer.name}")
    click.echo(f"  mean={np.nanmean(score):.3f}  max={np.nanmax(score):.3f}")
    click.echo(f"  min={np.nanmin(score):.3f}")


@cli.command("model-train")
@click.option("--data", "-d", type=click.Path(exists=True), required=True,
              help="CSV with feature columns and a 'target' column.")
@click.option("--target", "-t", default="target")
@click.option("--kind", "-k", type=click.Choice(
    ["linear", "ridge", "forest"]), default="ridge")
@click.option("--output", "-o", type=click.Path(), default="model.pkl")
def model_train(data, target, kind, output):
    """Train a regression model on a CSV and persist it."""
    import pandas as pd

    from barograph.model import RegressionPipeline

    df = pd.read_csv(data)
    if target not in df.columns:
        click.echo(f"Target column '{target}' not found.")
        raise click.Abort()
    y = df[target].to_numpy(dtype=np.float64)
    X = df.drop(columns=[target]).to_numpy(dtype=np.float64)
    names = [c for c in df.columns if c != target]
    model = RegressionPipeline(kind=kind).fit(X, y, names)
    RegressionPipeline.save(model, output)
    click.echo(f"Trained {kind} model with {len(names)} features -> {output}")


@cli.command("qc")
@click.option("--file", "-f", type=click.Path(exists=True), required=True,
              help="CSV with 'time' (ISO-8601) and 'value' columns.")
@click.option("--min-value", type=float, default=None)
@click.option("--max-value", type=float, default=None)
@click.option("--spike-sigma", type=float, default=5.0)
@click.option("--persistence", type=int, default=6)
def qc_cmd(file, min_value, max_value, spike_sigma, persistence):
    """Run quality-control checks on a time series CSV."""
    import csv
    from datetime import datetime

    from barograph.quality import QCThresholds, QualityController

    times: list[datetime] = []
    values: list[float] = []
    with open(file, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            times.append(datetime.fromisoformat(row["time"]))
            values.append(float(row["value"]))

    thresholds = QCThresholds(
        min_value=min_value if min_value is not None else -np.inf,
        max_value=max_value if max_value is not None else np.inf,
        spike_sigma=spike_sigma,
        persistence_span=persistence,
    )
    result = QualityController(thresholds).run(np.asarray(values), times)
    counts: dict[str, int] = {}
    for flag in result.flags:
        counts[flag.value] = counts.get(flag.value, 0) + 1
    _echo_title(f"Quality control: {Path(file).name} ({len(times)} samples)")
    for name, count in counts.items():
        click.echo(f"  {name}: {count}")

    from barograph.quality import detect_gaps
    gaps = detect_gaps(times)
    if gaps:
        click.echo(f"  detected_gaps: {len(gaps)}")


@cli.group()
def derived():
    """Compute derived meteorological quantities."""


@derived.command("thermal")
@click.option("--temperature", "-t", type=float, required=True)
@click.option("--rh", type=click.FloatRange(0, 100), required=True,
              help="Relative humidity in percent.")
@click.option("--wind", "-w", type=float, default=0.0,
              help="Wind speed in m/s.")
def derived_thermal(temperature, rh, wind):
    """Compute dewpoint and thermal comfort indices."""
    from barograph.derived import (
        apparent_temperature,
        dewpoint,
        heat_index,
        relative_humidity,
        wind_chill,
    )
    td = dewpoint(temperature, rh)
    _echo_title(f"Derived quantities at T={temperature} C, RH={rh}%")
    click.echo(f"  dewpoint: {td:.2f} C")
    click.echo(f"  relative_humidity (from dewpoint): {relative_humidity(temperature, td):.1f}%")
    click.echo(f"  wind_chill (wind={wind} m/s): {wind_chill(temperature, wind * 3.6):.2f} C")
    click.echo(f"  heat_index: {heat_index(temperature, rh):.2f} C")
    click.echo(f"  apparent_temperature: {apparent_temperature(temperature, rh, wind):.2f} C")


@derived.command("precip")
@click.option("--series", "-s", type=click.Path(exists=True), required=True,
              help="CSV with 'time' and 'value' (mm) columns.")
def derived_precip(series):
    """Summarize a precipitation series: totals, wet days, maxima."""
    import csv
    from datetime import datetime

    import numpy as np

    from barograph.time_series import (
        PrecipitationAnalyzer,
        wet_days_fraction,
    )

    times: list[datetime] = []
    values: list[float] = []
    with open(series, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            times.append(datetime.fromisoformat(row["time"]))
            values.append(float(row["value"]))

    analyzer = PrecipitationAnalyzer()
    v = np.asarray(values)
    events = analyzer.events(v, times)
    _echo_title(f"Precipitation summary: {Path(series).name}")
    click.echo(f"  total_precip: {v.sum():.1f} mm")
    click.echo(f"  wet_days_fraction: {wet_days_fraction(v):.3f}")
    click.echo(f"  n_events: {len(events)}")
    if events:
        peak = max(events, key=lambda e: e.peak)
        click.echo(f"  peak_intensity: {peak.peak:.1f} mm")


@cli.command("extreme")
@click.option("--file", "-f", type=click.Path(exists=True), required=True,
              help="CSV with a 'value' column of observations/excesses.")
@click.option("--period", "-p", type=int, multiple=True, default=(10, 50, 100),
              help="Return periods (blocks) to report.")
@click.option("--block-size", "-b", type=int, default=None,
              help="Group raw series into blocks of this many samples first "
                   "(GEV block-maxima method).")
@click.option("--method", "-m", type=click.Choice(["gev", "pot"]), default="gev",
              help="Estimation method: block-maxima GEV or peak-over-threshold.")
@click.option("--threshold", "-t", type=float, default=None,
              help="Threshold for the peak-over-threshold method.")
def extreme_cmd(file, period, block_size, method, threshold):
    """Fit an extreme-value distribution and report extreme return levels."""
    import csv

    from barograph.extreme import block_maxima, fit_gev, pot_return_level

    values: list[float] = []
    with open(file, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            values.append(float(row["value"]))
    samples = np.asarray(values, dtype=np.float64)

    _echo_title(f"Extreme value analysis: {Path(file).name} (method={method})")

    if method == "pot":
        thr = threshold if threshold is not None else float(np.percentile(samples, 95))
        result, levels = pot_return_level(
            samples, threshold=thr, period=np.asarray(period, dtype=np.float64)
        )
        click.echo(f"  threshold: {thr:.3f}")
        click.echo(f"  n_exceedances: {result.n_exceedances}")
        click.echo(f"  exceedance_fraction: {result.exceedance_fraction:.4f}")
        click.echo(f"  gpd scale={result.distribution.scale:.3f}  "
                   f"shape={result.distribution.shape:.3f}")
        click.echo("  return levels:")
        for p, lv in zip(period, levels):
            click.echo(f"    {int(p)}-block: {lv:.3f}")
        return

    if block_size:
        samples = block_maxima(samples, block_size)
    if samples.size < 3:
        click.echo("Need at least 3 finite extreme samples.")
        raise click.Abort()

    fit = fit_gev(samples)
    dist = fit.distribution
    click.echo(f"  n_blocks: {fit.n_blocks}")
    click.echo(f"  loc={dist.loc:.3f}  scale={dist.scale:.3f}  shape={dist.shape:.3f}")
    click.echo("  return levels:")
    for p in period:
        rl = fit.return_level(np.array([float(p)]))
        click.echo(f"    {p}-block: {rl[0]:.3f}")


@cli.command("spi")
@click.option("--file", "-f", type=click.Path(exists=True), required=True,
              help="CSV with a 'value' column of precipitation (mm).")
@click.option("--window", "-w", type=int, default=3,
              help="Accumulation window size (periods).")
@click.option("--current", "-c", is_flag=True,
              help="Also print the index of the most recent accumulation.")
def spi_cmd(file, window, current):
    """Compute the Standardized Precipitation Index from a precipitation CSV."""
    import csv

    from barograph.indices import classify_drought, compute_spi_series

    values: list[float] = []
    with open(file, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            values.append(float(row["value"]))

    series = compute_spi_series(np.asarray(values, dtype=np.float64), window)
    valid = series[np.isfinite(series)]
    _echo_title(f"Standardized Precipitation Index (window={window})")
    click.echo(f"  n_periods: {len(series)}")
    click.echo(f"  min: {np.nanmin(series):.2f}  max: {np.nanmax(series):.2f}")
    click.echo(f"  mean: {np.nanmean(series):.2f}  n_valid: {valid.size}")
    if current and np.isfinite(series[-1]):
        click.echo(f"  current_spi: {series[-1]:.2f} "
                   f"({classify_drought(float(series[-1]))})")


@cli.command("spei")
@click.option("--precip-file", "-p", type=click.Path(exists=True), required=True,
              help="CSV with a 'precip' column of precipitation (mm).")
@click.option("--temp-file", "-t", type=click.Path(exists=True), required=True,
              help="CSV with a 'temp' column of mean temperature (Celsius).")
@click.option("--latitude", "-la", type=click.FloatRange(-90, 90), required=True)
@click.option("--window", "-w", type=int, default=3,
              help="Accumulation window size (periods).")
@click.option("--current", "-c", is_flag=True,
              help="Also print the index of the most recent accumulation.")
def spei_cmd(precip_file, temp_file, latitude, window, current):
    """Compute the Standardized Precipitation-Evapotranspiration Index."""
    import csv

    from barograph.indices import classify_drought, compute_spei

    def _read_col(path, col):
        vals: list[float] = []
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                vals.append(float(row[col]))
        return vals

    precip = np.asarray(_read_col(precip_file, "precip"), dtype=np.float64)
    temp = np.asarray(_read_col(temp_file, "temp"), dtype=np.float64)
    series = compute_spei(precip, temp, latitude, window)
    _echo_title(f"SPEI at lat={latitude} (window={window})")
    click.echo(f"  n_periods: {len(series)}")
    click.echo(f"  min: {np.nanmin(series):.2f}  max: {np.nanmax(series):.2f}")
    click.echo(f"  mean: {np.nanmean(series):.2f}")
    if current and np.isfinite(series[-1]):
        click.echo(f"  current_spei: {series[-1]:.2f} "
                   f"({classify_drought(float(series[-1]))})")


def _load_raster(path: str):
    """Load a raster layer from a NetCDF (single 2D/3D variable)."""
    import xarray as xr

    from barograph.raster.layer import CRS, RasterLayer
    ds = xr.open_dataset(path)
    # pick the first non-coordinate data variable
    var_name = None
    for v in ds.data_vars:
        if v in ("latitude", "longitude"):
            continue
        var_name = v
        break
    if var_name is None:
        raise click.ClickException(f"No data variable in {path}")
    data = ds[var_name].values
    lats = ds["latitude"].values if "latitude" in ds.coords else np.arange(data.shape[-2])
    lons = ds["longitude"].values if "longitude" in ds.coords else np.arange(data.shape[-1])
    return RasterLayer(
        data=data,
        lats=lats,
        lons=lons,
        name=str(var_name),
        crs=CRS(epsg=int(ds.attrs.get("crs", 4326))),
        units=str(ds[var_name].attrs.get("units", "")),
    )


def settings(ctx):
    return ctx.obj.get("settings")


if __name__ == "__main__":
    cli()
