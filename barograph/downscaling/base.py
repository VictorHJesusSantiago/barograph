"""Statistical downscaling base class and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from barograph.core.models import GriddedField


class BaseDownscaler(ABC):
    """Base class for all statistical downscalers."""

    name: str = "base"

    @abstractmethod
    def fit(
        self,
        coarse: list[GriddedField],
        fine: list[GriddedField],
    ) -> BaseDownscaler:
        """Fit the downscaler to paired coarse/fine fields."""
        raise NotImplementedError

    @abstractmethod
    def transform(self, coarse: GriddedField) -> GriddedField:
        """Downscale a single coarse field to fine resolution."""
        raise NotImplementedError

    def fit_transform(
        self,
        coarse: list[GriddedField],
        fine: list[GriddedField],
    ) -> list[GriddedField]:
        """Fit and transform on the training data."""
        self.fit(coarse, fine)
        return [self.transform(c) for c in coarse]

    def validate_shapes(
        self,
        coarse: list[GriddedField],
        fine: list[GriddedField],
    ) -> None:
        if len(coarse) != len(fine):
            raise ValueError(f"Mismatched training samples: coarse={len(coarse)}, fine={len(fine)}")

    def _aggregate_arrays(
        self, fields: list[GriddedField]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Aggregate a list of fields into data, lat, lon arrays."""
        data = np.array([f.data for f in fields])
        lats = fields[0].lats.copy()
        lons = fields[0].lons.copy()
        return data, lats, lons
