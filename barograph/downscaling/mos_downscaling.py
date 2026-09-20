"""MOS-based statistical downscaling wrapping the MOS trainer."""

from __future__ import annotations

import numpy as np

from barograph.core.models import Coordinate, GriddedField
from barograph.downscaling.base import BaseDownscaler
from barograph.mos.regressor import MOSRegressor


class MOSDownscaler(BaseDownscaler):
    """Downscale coarse predictions to station-level point forecasts using MOS."""

    name = "mos_downscaling"

    def __init__(
        self,
        station_coords: list[tuple[float, float]],
        station_ids: list[str] | None = None,
        feature_radius_cells: int = 2,
    ):
        self.station_coords = station_coords
        self.station_ids = station_ids or [f"st{i}" for i in range(len(station_coords))]
        self.feature_radius_cells = feature_radius_cells
        self.regressors: dict[str, MOSRegressor] = {}

    def fit(
        self,
        coarse: list[GriddedField],
        fine: list[GriddedField],
    ) -> MOSDownscaler:
        """Train a MOS regressor per station using coarse neighbors as features."""
        self.validate_shapes(coarse, fine)
        raise NotImplementedError(
            "MOSDownscaler.fit requires raw station observations. "
            "Train MOSRegressor directly with MOSTrainer instead."
        )

    def transform(self, coarse: GriddedField) -> GriddedField:
        raise NotImplementedError

    def fit_from_stations(
        self,
        coarse_fields: list[GriddedField],
        station_obs: list[list[float]],
    ) -> MOSDownscaler:
        """Train per-station regressors."""
        for coord, sid, obs in zip(self.station_coords, self.station_ids, station_obs):
            feat_matrix = np.array(
                [self._extract_neighborhood(f, coord).ravel() for f in coarse_fields]
            )
            reg = MOSRegressor()
            reg.fit(feat_matrix, np.array(obs))
            self.regressors[sid] = reg
        return self

    def predict_point(
        self,
        coarse: GriddedField,
        station_index: int = 0,
    ) -> float:
        sid = self.station_ids[station_index]
        reg = self.regressors[sid]
        feat = self._extract_neighborhood(coarse, self.station_coords[station_index]).ravel()
        return float(reg.predict(feat.reshape(1, -1))[0])

    def _extract_neighborhood(
        self,
        field: GriddedField,
        coord: tuple[float, float],
    ) -> np.ndarray:
        from barograph.core.coordinates import find_nearest_grid_point

        i, j = find_nearest_grid_point(
            Coordinate(latitude=coord[0], longitude=coord[1]),
            field.lats,
            field.lons,
        )
        r = self.feature_radius_cells
        i0, i1 = max(0, i - r), min(field.data.shape[0], i + r + 1)
        j0, j1 = max(0, j - r), min(field.data.shape[1], j + r + 1)
        return field.data[i0:i1, j0:j1]
