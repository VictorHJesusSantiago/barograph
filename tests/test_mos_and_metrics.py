"""Unit tests for MOS trainer and verification metrics."""

from datetime import datetime

import numpy as np

from barograph.core.models import Coordinate, GriddedField, ModelSource, StationObs, Variable
from barograph.mos import MOSTrainer
from barograph.verification import VerificationMetrics


def make_field(variable: Variable, size=8, base=25.0, seed=0, hour=12):
    rng = np.random.default_rng(seed)
    lats = np.linspace(-25, -20, size)
    lons = np.linspace(-50, -45, size)
    data = base + rng.standard_normal((size, size))
    return GriddedField(
        data=data,
        lats=lats,
        lons=lons,
        variable=variable,
        source=ModelSource.GFS,
        valid_time=datetime(2026, 1, 1, hour),
        init_time=datetime(2026, 1, 1, 0),
    )


def test_mos_trainer_builds_dataset():
    n = 30
    coord = Coordinate(latitude=-22.5, longitude=-47.5)
    fields = [make_field(Variable.TEMPERATURE, seed=i) for i in range(n)]
    obs = [
        StationObs(
            station_id="ST1",
            coord=coord,
            variable=Variable.TEMPERATURE,
            values=[20.0 + i * 0.1],
            times=[datetime(2026, 1, 1, 12)],
        )
        for i in range(n)
    ]

    trainer = MOSTrainer(feature_radius=2, include_derived=True)
    dataset = trainer.build_dataset(fields, obs)

    assert dataset.X.shape[0] == n
    assert dataset.y.shape[0] == n
    assert "center" in dataset.feature_names
    assert "sin_diurnal" in dataset.feature_names
    assert len(dataset.feature_names) == dataset.X.shape[1]


def test_mos_trainer_trains_regressor():
    n = 60
    coord = Coordinate(latitude=-22.5, longitude=-47.5)
    fields = [make_field(Variable.TEMPERATURE, seed=i) for i in range(n)]
    obs = [
        StationObs(
            station_id="A",
            coord=coord,
            variable=Variable.TEMPERATURE,
            values=[18.0 + i * 0.05],
            times=[datetime(2026, 1, 1, 12)],
        )
        for i in range(n)
    ]

    trainer = MOSTrainer(feature_radius=1)
    reg = trainer.train(fields, obs, target_variable="temperature", algorithm="linear")

    # Predict on a new field
    new_field = make_field(Variable.TEMPERATURE, seed=999)
    data = trainer.build_dataset(
        [new_field],
        [
            StationObs(
                station_id="A",
                coord=coord,
                variable=Variable.TEMPERATURE,
                values=[0.0],
                times=[datetime(2026, 1, 1, 12)],
            ),
        ],
    )
    preds = reg.predict(data.X)
    assert np.all(np.isfinite(preds))


def test_verification_metrics_core():
    rng = np.random.default_rng(3)
    obs = rng.normal(10, 2, 100)
    fcst = obs + rng.normal(0, 1, 100)
    vm = VerificationMetrics()

    mae = vm.mae(obs, fcst)
    rmse = vm.rmse(obs, fcst)
    bias = vm.bias(obs, fcst)
    corr = vm.correlation(obs, fcst)
    assert mae > 0
    assert rmse > mae  # rmse >= mae generally
    assert 0.5 < corr < 1.0
    assert abs(bias) < 5


def test_verification_metrics_2x2_skill():
    vm = VerificationMetrics()
    hss = vm.heidke_skill_score(hits=60, false_alarms=15, misses=10, correct_negatives=200)
    assert -1 <= hss <= 1


def test_verification_compute_all():
    rng = np.random.default_rng(1)
    obs = rng.random(50)
    fcst = obs + rng.normal(0, 0.1, 50)
    bin_obs = (obs > 0.5).astype(float)
    prob = rng.random(50)
    team = VerificationMetrics()
    results = team.compute_all(obs, fcst, prob=prob, ensemble=np.random.rand(20, 50))
    assert "mae" in results
    assert "rmse" in results
    assert "correlation" in results

    bin_results = team.compute_all(bin_obs, fcst, prob=prob)
    assert "brier" in bin_results
