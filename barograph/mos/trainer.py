"""MOS trainer: builds feature matrices from paired NWP and observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from loguru import logger

from barograph.core.models import GriddedField, StationObs
from barograph.mos.regressor import MOSRegressor


@dataclass
class MOSDataset:
    """Paired NWP-observation dataset ready for MOS training."""
    X: np.ndarray
    y: np.ndarray
    feature_names: list[str]
    times: list[datetime]
    station_ids: list[str]


class MOSTrainer:
    """Build MOS feature matrices and train regressors.

    Features are extracted from a neighborhood of coarse-grid points around
    each station, along with derived predictors (log precipitation, wind speed,
    diurnal harmonics, etc.).
    """

    def __init__(
        self,
        feature_radius: int = 2,
        include_derived: bool = True,
        category_bounds: dict | None = None,
    ):
        self.feature_radius = feature_radius
        self.include_derived = include_derived
        self.category_bounds = category_bounds or {}

    def build_dataset(
        self,
        coarse_fields: list[GriddedField],
        observations: list[StationObs],
        forecast_hour_ahead: int | None = None,
    ) -> MOSDataset:
        """Build MOS dataset.

        Args:
            coarse_fields: Paired model fields aligned with observations.
            observations: Aligned station observations.
            forecast_hour_ahead: Optional filter for short-range training.
        """
        if len(coarse_fields) != len(observations):
            raise ValueError("coarse_fields and observations must be aligned")

        X_rows = []
        y_vals = []
        feat_names: list[str] | None = None
        times = []
        station_ids = []

        for field, obs in zip(coarse_fields, observations):
            if len(obs.values) == 0:
                continue
            if np.isnan(obs.values[0]):
                continue

            features = self._extract_features(field, obs)
            if feat_names is None:
                feat_names = features[2]
            X_rows.append(features[0])
            y_vals.append(features[1])
            times.append(obs.times[0])
            station_ids.append(obs.station_id)

        if not X_rows:
            raise ValueError("No valid samples")

        return MOSDataset(
            X=np.array(X_rows, dtype=np.float64),
            y=np.array(y_vals, dtype=np.float64),
            feature_names=feat_names or [],
            times=times,
            station_ids=station_ids,
        )

    def train(
        self,
        coarse_fields: list[GriddedField],
        observations: list[StationObs],
        target_variable: str,
        algorithm: str = "gradient_boosting",
        hyperparameters: dict | None = None,
    ) -> MOSRegressor:
        """Train a single MOS regressor for a target variable."""
        dataset = self.build_dataset(coarse_fields, observations)
        reg = MOSRegressor(algorithm=algorithm, hyperparameters=hyperparameters)
        reg.fit(dataset.X, dataset.y, feature_names=dataset.feature_names)
        return reg

    def train_per_station(
        self,
        coarse_fields: list[GriddedField],
        observations: list[StationObs],
        algorithm: str = "gradient_boosting",
        hyperparameters: dict | None = None,
    ) -> dict[str, MOSRegressor]:
        """Train one MOS regressor per station."""
        stations: dict[str, list[StationObs]] = {}
        for obs in observations:
            stations.setdefault(obs.station_id, []).append(obs)

        models: dict[str, MOSRegressor] = {}
        for sid, obs_list in stations.items():
            idx = [i for i, f in enumerate(coarse_fields) if i < len(obs_list)]
            fields = [coarse_fields[i] for i in idx]
            samples = [obs_list[i] for i in idx]
            try:
                models[sid] = self.train(
                    fields, samples, target_variable="", algorithm=algorithm,
                    hyperparameters=hyperparameters,
                )
            except Exception as e:
                logger.warning(f"Failed to train MOS for {sid}: {e}")
        return models

    def _extract_features(
        self,
        field: GriddedField,
        obs: StationObs,
    ) -> tuple[np.ndarray, float, list[str]]:
        from barograph.core.coordinates import find_nearest_grid_point

        i, j = find_nearest_grid_point(obs.coord, field.lats, field.lons)
        r = self.feature_radius
        i0, i1 = max(0, i - r), min(field.data.shape[-2], i + r + 1)
        j0, j1 = max(0, j - r), min(field.data.shape[-1], j + r + 1)

        # Center cell
        center = float(field.data[i, j])

        # Neighborhood
        window_data = field.data[i0:i1, j0:j1]
        neighborhood_stats = [
            float(np.nanmean(window_data)),
            float(np.nanstd(window_data)),
            float(np.nanmin(window_data)),
            float(np.nanmax(window_data)),
        ]

        feat_names = ["center", "neigh_mean", "neigh_std", "neigh_min", "neigh_max"]
        features = [center] + neighborhood_stats

        if self.include_derived and field.variable.value == "precipitation":
            features.append(float(np.nanmean(window_data)) + 0.1)
            features.append(float(np.log(np.nanmean(window_data) + 0.01)))
            feat_names += ["precip_mean", "log_precip_mean"]

        # Diurnal harmonics from validity time
        hour = field.valid_time.hour
        features.append(float(np.sin(2 * np.pi * hour / 24)))
        features.append(float(np.cos(2 * np.pi * hour / 24)))
        feat_names += ["sin_diurnal", "cos_diurnal"]

        return np.array(features), float(obs.values[0]), feat_names
