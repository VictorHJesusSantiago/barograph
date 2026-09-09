"""Tests for the forecast cycle and blending module."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from barograph.core.models import GriddedField, ModelSource, Variable
from barograph.forecast.blending import ForecastBlender
from barograph.forecast.cycle import ForecastCycle


def make_field(init, valid, val):
    lats = np.linspace(-25.0, -20.0, 8)
    lons = np.linspace(-50.0, -45.0, 8)
    return GriddedField(
        data=np.full((8, 8), val, dtype=np.float32),
        lats=lats, lons=lons,
        variable=Variable.TEMPERATURE, source=ModelSource.GFS,
        valid_time=valid, init_time=init,
    )


def test_cycle_assemble_and_leads():
    init = datetime(2026, 1, 1, 0)
    fields = [
        make_field(init, init + timedelta(hours=6), 1.0),
        make_field(init, init + timedelta(hours=12), 2.0),
        make_field(init, init + timedelta(hours=18), 3.0),
    ]
    cycle = ForecastCycle(init_time=init, fields=fields)
    assert cycle.leads_hours() == [6.0, 12.0, 18.0]
    assert len(cycle.valid_times) == 3
    got = cycle.get(12.0)
    assert got is not None
    assert np.allclose(got.data, 2.0)
    assert cycle.get(99.0) is None


def test_cycle_mask_within():
    init = datetime(2026, 1, 1, 0)
    field = make_field(init, init + timedelta(hours=6), 5.0)
    cycle = ForecastCycle(init_time=init, fields=[field])
    clipped = cycle.mask_within(-23.0, -21.0, -48.0, -46.0)
    assert len(clipped.fields) == 1
    assert clipped.fields[0].lats.shape[0] < field.lats.shape[0]
    assert clipped.fields[0].lons.shape[0] < field.lons.shape[0]


def test_cycle_summary():
    init = datetime(2026, 1, 1, 0)
    cycle = ForecastCycle(init_time=init,
                          fields=[make_field(init, init + timedelta(hours=6), 1.0)])
    summary = cycle.summary()
    assert summary["n_fields"] == 1
    assert summary["leading_hours"] == [6.0]


def test_blend_weighted_mean():
    init1 = datetime(2026, 1, 1, 0)
    init2 = datetime(2026, 1, 1, 6)
    valid = datetime(2026, 1, 1, 12)
    f1 = make_field(init1, valid, 10.0)
    f2 = make_field(init2, valid, 20.0)
    blended = ForecastBlender().blend([f1, f2])
    # recency weighting: f2 is newer (6h age) vs f1 (12h age)
    assert blended.data.mean() > 10.0
    assert blended.data.mean() < 20.0
    assert blended.data.mean() != 15.0  # not a plain average
    assert "blended" in blended.meta


def test_blend_single_field():
    init = datetime(2026, 1, 1, 0)
    f = make_field(init, init + timedelta(hours=6), 7.0)
    out = ForecastBlender().blend([f])
    assert np.allclose(out.data, 7.0)


def test_blend_requires_alignment():
    init = datetime(2026, 1, 1, 0)
    f1 = make_field(init, init + timedelta(hours=6), 1.0)
    lats = np.linspace(-20.0, -10.0, 8)
    f2 = GriddedField(
        data=np.full((8, 8), 2.0, dtype=np.float32),
        lats=lats, lons=f1.lons,
        variable=Variable.TEMPERATURE, source=ModelSource.GFS,
        valid_time=f1.valid_time, init_time=init,
    )
    with pytest.raises(ValueError):
        ForecastBlender().blend([f1, f2])


def test_blend_to_raster():
    init = datetime(2026, 1, 1, 0)
    blended = ForecastBlender().blend([make_field(init, init + timedelta(hours=6), 3.0)])
    layer = ForecastBlender.to_raster(blended)
    assert layer.shape == blended.shape
    assert layer.name == "temperature"
