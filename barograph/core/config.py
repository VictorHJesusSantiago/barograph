"""Configuration management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class IngestionConfig:
    gfs_base_url: str = "https://nomads.ncep.noaa.gov:443/cgi-bin/filter_gfs_0p25.pl"
    ecmwf_base_url: str = "https://apps.ecmwf.int/datasets/data/ifs"
    era5_base_url: str = "https:// cds.climate.copernicus.eu/api/v2"
    data_dir: str = "./data/ingested"
    cache_ttl_hours: int = 6
    max_retries: int = 3
    timeout_seconds: int = 120


@dataclass
class DownscalingConfig:
    method: str = "quantile_delta_transform"
    grid_resolution_km: float = 1.0
    training_years: tuple[int, int] = (2010, 2020)
    variables: list[str] = field(default_factory=lambda: ["temperature", "precipitation"])
    dem_path: str | None = None


@dataclass
class MOSConfig:
    algorithm: str = "gradient_boosting"
    feature_window_hours: int = 24
    forecast_hours_ahead: list[int] = field(default_factory=lambda: list(range(1, 241)))
    calibration_station_ids: list[str] = field(default_factory=list)
    retrain_interval_days: int = 7
    model_dir: str = "./models/mos"


@dataclass
class EnsembleConfig:
    pooling_method: str = "pit"
    crps_method: str = "nargessian"
    n_members: int = 51
    calibration: bool = True
    pooling_bins: int = 100


@dataclass
class PostprocessingConfig:
    emos_n_members: int = 51
    quantile_mapping_method: str = "empirical"
    n_bins: int = 1000
    training_window_days: int = 365
    min_training_samples: int = 30
    distribution: str = "truncated_normal"


@dataclass
class VerificationConfig:
    metrics: list[str] = field(
        default_factory=lambda: ["crps", "brier", "reliability", "bias", "mae", "rmse"]
    )
    brier_thresholds: list[float] = field(
        default_factory=lambda: [0.1, 1.0, 5.0, 10.0, 25.0, 50.0]
    )
    reliability_bins: int = 10
    output_dir: str = "./output/verification"


@dataclass
class NowcastingConfig:
    optical_flow_method: str = "lucas_kanade"
    flow_radius: int = 12
    extrapolation_minutes: list[int] = field(
        default_factory=lambda: [15, 30, 45, 60, 90, 120]
    )
    radar_composite_url: str = ""
    min_reflectivity_dbz: float = 0.0
    max_reflectivity_dbz: float = 70.0


@dataclass
class AlertsConfig:
    rules_file: str = "./configs/alert_rules.yaml"
    cooldown_minutes: int = 60
    notification_channels: list[str] = field(default_factory=lambda: ["log"])
    webhook_urls: list[str] = field(default_factory=list)


@dataclass
class Settings:
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    downscaling: DownscalingConfig = field(default_factory=DownscalingConfig)
    mos: MOSConfig = field(default_factory=MOSConfig)
    ensemble: EnsembleConfig = field(default_factory=EnsembleConfig)
    postprocessing: PostprocessingConfig = field(default_factory=PostprocessingConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    nowcasting: NowcastingConfig = field(default_factory=NowcastingConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    log_level: str = "INFO"
    n_workers: int = 4


def load_config(path: str | Path | None = None) -> Settings:
    """Load configuration from YAML file, falling back to defaults."""
    settings = Settings()

    if path is None:
        env_path = os.environ.get("BAROGRAPH_CONFIG")
        if env_path:
            path = Path(env_path)
        else:
            for candidate in ["configs/settings.yaml", "configs/settings.yml", "barograph.yaml"]:
                if Path(candidate).exists():
                    path = candidate
                    break

    if path and Path(path).exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        for section_name in [
            "ingestion", "downscaling", "mos", "ensemble",
            "postprocessing", "verification", "nowcasting", "alerts",
        ]:
            if section_name in raw:
                section = getattr(settings, section_name)
                for k, v in raw[section_name].items():
                    if hasattr(section, k):
                        setattr(section, k, v)

        for k in ["log_level", "n_workers"]:
            if k in raw:
                setattr(settings, k, raw[k])

    return settings
