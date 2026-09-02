# Barograph

Weather forecast **modeling**, **post-processing**, and **verification** toolkit.

Barograph ingests NWP model output (GFS, ECMWF, ERA5), applies statistical
downscaling, MOS, and ensemble calibration (EMOS, quantile mapping), verifies
forecasts (CRPS, Brier, reliability diagrams), performs radar nowcasting by
optical flow, and issues threshold-based alerts.

## Features

- **Data ingestion** (GRIB2 / NetCDF / Zarr): `GFSIngester`, `ECMWFIngester`,
  `ERA5Ingester`, `RadarIngester`
- **Statistical downscaling**: Quantile Delta Transform (QDT), bias correction
- **Model Output Statistics (MOS)**: linear / gradient boosting regressors,
  per-station training, cross-validation skill scores
- **Ensemble processing**: parametric & empirical pooling, quantile/probability
  products
- **Calibration / post-processing**: Non-homogeneous Gaussian Regression (EMOS),
  empirical quantile mapping
- **Verification**: CRPS (normal, ensemble, truncated-normal), Brier score +
  decomposition, reliability diagrams
- **Radar nowcasting**: Farneback / Lucas-Kanade / block-matching optical flow,
  semi-Lagrangian advection
- **Alerts**: threshold rules, regions/cooldowns, notification channels & webhooks

## Installation

```bash
pip install -e ".[dev]"
```

## Quick start

```python
from barograph.core.models import GriddedField
from barograph.alerts import AlertEngine
from barograph.alerts.rules import AlertRule, Operator, Severity
from barograph.core.models import Variable

engine = AlertEngine(notification_channels=["stdout"])
engine.add_rule(AlertRule(
    variable=Variable.PRECIPITATION,
    threshold=50.0,
    operator=Operator.GREATER_OR_EQUAL,
    severity=Severity.SEVERE,
))
alerts = engine.evaluate_field(field)  # some GriddedField
```

## CLI

```bash
barograph --config configs/settings.yaml ingest --gfs-file data/model.grib2 --variable temperature
barograph --config configs/settings.yaml check-alerts --field out.nc --threshold 50 --variable precipitation
barograph --config configs/settings.yaml nowcast --radar-dir data/radar --lead-minutes 60
barograph --config configs/settings.yaml load-rules --rule-file configs/alert_rules.yaml
```

## Test

```bash
pytest
```

## Layout

```
barograph/
  core/          models, config, coordinates, temporal
  ingestion/     GFS, ECMWF, ERA5, radar
  downscaling/   QDT, bias correction, MOS downscaling
  mos/           regressor, trainer, evaluation
  ensemble/      pooling, statistics
  postprocessing/EMOS, quantile mapping
  verification/  CRPS, Brier, reliability, metrics
  nowcasting/    optical flow, extrapolation
  alerts/        rules, engine
  cli/           click-based CLI
  utils/         storage, logging, cache
```

## License

MIT