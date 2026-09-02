"""Barograph command-line interface."""

from __future__ import annotations

import click

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
        # Requires training data; for now just report
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
@click.pass_context
def check_alerts(ctx, field, threshold, variable, lat_range, lon_range):
    """Check a gridded forecast against threshold alert rules."""
    from barograph.alerts import AlertEngine
    from barograph.alerts.rules import AlertRule, Operator, Severity
    from barograph.core.models import Variable
    from barograph.utils.storage import load_gridded_field

    field_obj = load_gridded_field(field) if field else ctx.obj.get("last_field")
    if field_obj is None:
        click.echo("No field available. Provide --field or ingest first.")
        raise click.Abort()

    engine = AlertEngine(
        cooldown_minutes=settings_alerts(ctx),
        notification_channels=["stdout"],
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


def settings_alerts(ctx):
    cfg = ctx.obj.get("settings")
    return getattr(cfg.alerts, "cooldown_minutes", 60)


@cli.command()
@click.option("--members-dir", "-d", type=click.Path(exists=True),
              help="Directory of member NetCDF files.")
@click.option("--metric", "-m", default="crps",
              help="Verification metric to compute.")
@click.pass_context
def verify(ctx, members_dir, metric):
    """Run verification on forecast ensembles."""
    settings = ctx.obj.get("settings")
    _ = settings
    click.echo(f"Verification requested with metric={metric}, dir={members_dir}")
    click.echo("Provide paired observations to compute skill scores.")


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


if __name__ == "__main__":
    cli()
