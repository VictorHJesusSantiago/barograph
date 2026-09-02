"""End-to-end example showing the Barograph pipeline on synthetic data."""

from datetime import datetime

import numpy as np

from barograph.alerts import AlertEngine
from barograph.alerts.rules import AlertRule, Operator, Severity
from barograph.core.config import load_config
from barograph.core.models import (
    EnsembleForecast,
    GriddedField,
    ModelSource,
    Variable,
)
from barograph.ensemble.pooling import EnsemblePooler
from barograph.postprocessing.emos import EMOSCalibrator
from barograph.postprocessing.quantile_mapping import QuantileMapper
from barograph.utils.logging import setup_logging
from barograph.verification.brier import brier_score
from barograph.verification.crps import crps_score


def make_toy_field(
    variable: Variable,
    shape: tuple[int, int] = (40, 50),
    base: float = 10.0,
    noise: float = 1.0,
    seed: int = 0,
) -> GriddedField:
    rng = np.random.default_rng(seed)
    lats = np.linspace(-25.0, -20.0, shape[0])
    lons = np.linspace(-50.0, -45.0, shape[1])
    data = base + noise * rng.standard_normal(shape)
    t = datetime(2026, 1, 2, 12)
    return GriddedField(
        data=data, lats=lats, lons=lons, variable=variable,
        source=ModelSource.GFS, valid_time=t, init_time=t,
    )


def main():
    setup_logging("INFO")

    cfg = load_config()
    print(f"Loaded config (alerts cooldown={cfg.alerts.cooldown_minutes} min)")

    # --- 1. Ingest ---
    # In practice: GFSIngester().parse_grib(...)
    forecast = make_toy_field(Variable.TEMPERATURE, base=25.0, noise=2.0)

    # --- 2. Ensemble ---
    members = [
        make_toy_field(Variable.TEMPERATURE, base=24.0 + i, noise=1.5, seed=i)
        for i in range(5)
    ]
    ens = EnsembleForecast(
        members=members,
        variable=Variable.TEMPERATURE,
        source=ModelSource.GFS,
        init_time=forecast.init_time,
        valid_time=forecast.valid_time,
    )
    pooler = EnsemblePooler()
    members_arr = np.stack([m.data for m in members])
    params = pooler.fit_members(members_arr)
    ens_mean = ens.ensemble_mean
    print(f"Ensemble mean field max: {ens_mean.data.max():.2f}")
    print(f"Ensemble spread mean: {ens.ensemble_spread.data.mean():.2f}")

    p_above_30 = pooler.probability_exceed(params, 30.0)
    print(f"Fraction of grid with >30C: {np.mean(p_above_30):.3f}")

    # --- 3. Post-processing: quantile mapping ---
    rng = np.random.default_rng(42)
    model_hist = rng.normal(6, 2, 5000)   # raw model precipitation
    obs_hist = rng.normal(8, 2.5, 5000)   # observed precipitation
    qm = QuantileMapper(n_bins=100).fit(model_hist, obs_hist)
    print(f"QM mean shift sample: {qm.transform_data(np.array([6.0]))[0]:.2f}")

    # --- 4. EMOS calibration ---
    rng = np.random.default_rng(7)
    n = 500
    ens_mean_train = rng.normal(10, 2, n)
    ens_var_train = rng.uniform(0.5, 3.0, n)
    obs_train = rng.normal(ens_mean_train * 1.2 + 2, np.sqrt(ens_var_train))

    emos = EMOSCalibrator().fit(ens_mean_train, ens_var_train, obs_train)
    loc, scale = emos.predict_distribution(ens_mean_train, ens_var_train)
    print(f"EMOS calibrated loc sd: {loc.std():.2f}")

    # --- 5. Verification ---
    obs = rng.normal(10, 2, 100)
    fcst = rng.normal(10, 2, 100)
    crps = crps_score((fcst, np.full(100, 1.0)), obs, method="normal")
    print(f"Deterministic CRPS: {crps:.3f}")

    prob = rng.uniform(0, 1, 1000)
    bin_obs = (rng.uniform(0, 1, 1000) < prob).astype(float)
    print(f"Mean Brier score: {brier_score(prob, bin_obs).mean():.3f}")

    # --- 6. Alerts ---
    engine = AlertEngine(cooldown_minutes=0, notification_channels=["stdout"])
    engine.add_rule(AlertRule(
        variable=Variable.TEMPERATURE,
        threshold=29.0,
        operator=Operator.GREATER_OR_EQUAL,
        severity=Severity.WARNING,
        name="warm_spots",
    ))
    alerts = engine.evaluate_field(forecast)
    print(f"Fired {len(alerts)} alerts")

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
