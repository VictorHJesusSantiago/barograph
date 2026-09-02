"""Unit tests for core data models."""

from datetime import datetime

import numpy as np
import pytest

from barograph.core.models import (
    Coordinate,
    EnsembleForecast,
    GriddedField,
    ModelSource,
    Variable,
)


def test_coordinate_properties():
    c = Coordinate(latitude=-23.5, longitude=-46.5)
    assert c.latitude == -23.5
    assert c.longitude == -46.5
    assert c.elevation is None


def test_gridded_field_basic():
    lats = np.linspace(-25, -20, 10)
    lons = np.linspace(-50, -45, 12)
    data = np.random.rand(10, 12)

    field = GriddedField(
        data=data,
        lats=lats,
        lons=lons,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, 12),
        init_time=datetime(2026, 1, 1, 0),
    )
    assert field.shape == (10, 12)


def test_gridded_field_mismatched_shape():
    lats = np.linspace(-25, -20, 10)
    lons = np.linspace(-50, -45, 11)
    data = np.random.rand(10, 12)

    with pytest.raises(ValueError):
        GriddedField(
            data=data,
            lats=lats,
            lons=lons,
            variable=Variable.TEMPERATURE,
            source=ModelSource.GFS,
            valid_time=datetime(2026, 1, 1, 12),
            init_time=datetime(2026, 1, 1, 0),
        )


def test_gridded_field_2d_min():
    lats = np.linspace(-25, -20, 2)
    lons = np.linspace(-50, -45, 2)
    data = np.full((2, 2), 5.0)

    field = GriddedField(
        data=data, lats=lats, lons=lons,
        variable=Variable.TEMPERATURE, source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, 12),
        init_time=datetime(2026, 1, 1, 0),
    )
    assert field.shape == (2, 2)


def test_ensemble_forecast_mean():
    lats = np.linspace(-25, -20, 4)
    lons = np.linspace(-50, -45, 5)
    t = datetime(2026, 1, 1, 12)

    fields = []
    for m in range(3):
        data = np.full((4, 5), float(m + 1))
        fields.append(GriddedField(
            data=data, lats=lats, lons=lons,
            variable=Variable.TEMPERATURE, source=ModelSource.GFS,
            valid_time=t, init_time=t,
        ))

    ens = EnsembleForecast(
        members=fields,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        init_time=t,
        valid_time=t,
    )

    mean_field = ens.ensemble_mean
    assert np.allclose(mean_field.data, 2.0)

    spread_field = ens.ensemble_spread
    assert np.allclose(spread_field.data, np.sqrt(2 / 3))


def test_ensemble_member_ids():
    lats = np.linspace(-25, -20, 2)
    lons = np.linspace(-50, -45, 2)
    t = datetime(2026, 1, 1, 12)

    fields = [
        GriddedField(
            data=np.full((2, 2), float(i)), lats=lats, lons=lons,
            variable=Variable.TEMPERATURE, source=ModelSource.GFS,
            valid_time=t, init_time=t,
        )
        for i in range(2)
    ]

    ens = EnsembleForecast(
        members=fields,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        init_time=t,
        valid_time=t,
    )
    assert ens.member_ids == [0, 1]
    assert ens.member_array.shape == (2, 2, 2)
