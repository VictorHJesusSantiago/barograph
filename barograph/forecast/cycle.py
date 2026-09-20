"""Forecast cycle management: group fields by run cycle and lead time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from barograph.core.models import GriddedField


@dataclass
class ForecastCycle:
    """A collection of ``GriddedField`` objects grouped by initialization time."""

    init_time: datetime
    fields: list[GriddedField] = field(default_factory=list)

    @property
    def valid_times(self) -> list[datetime]:
        return sorted({f.valid_time for f in self.fields})

    def lead(self, field: GriddedField) -> timedelta:
        return field.valid_time - field.init_time

    def leads_hours(self) -> list[float]:
        return sorted({self.lead(f).total_seconds() / 3600 for f in self.fields})

    def get(self, lead_hours: float) -> GriddedField | None:
        for f in self.fields:
            if abs(self.lead(f).total_seconds() / 3600 - lead_hours) < 1e-6:
                return f
        return None

    def mask_within(
        self, lat_min: float, lat_max: float, lon_min: float, lon_max: float
    ) -> ForecastCycle:
        """Return a new cycle clipped to a bounding box."""
        clipped = []
        for f in self.fields:
            lat_mask = (f.lats >= lat_min) & (f.lats <= lat_max)
            lon_mask = (f.lons >= lon_min) & (f.lons <= lon_max)
            if f.data.ndim == 2:
                data = f.data[np.ix_(lat_mask, lon_mask)]
            else:
                data = f.data[..., np.ix_(lat_mask, lon_mask)]
            clipped.append(
                GriddedField(
                    data=data.copy(),
                    lats=f.lats[lat_mask].copy(),
                    lons=f.lons[lon_mask].copy(),
                    variable=f.variable,
                    source=f.source,
                    valid_time=f.valid_time,
                    init_time=f.init_time,
                    level=f.level,
                    meta=f.meta,
                )
            )
        return ForecastCycle(init_time=self.init_time, fields=clipped)

    def sort(self) -> None:
        self.fields.sort(key=lambda f: (f.variable.value, f.valid_time))

    def summary(self) -> dict[str, Any]:
        return {
            "init_time": self.init_time.isoformat(),
            "n_fields": len(self.fields),
            "leading_hours": self.leads_hours(),
            "variables": sorted({f.variable.value for f in self.fields}),
        }
