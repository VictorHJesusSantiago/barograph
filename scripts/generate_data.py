"""Generate synthetic test data for the Barograph CLI/pipeline.

Creates a NetCDF forecast field, a few radar sweeps, and synthetic paired
coarse/fine series for demonstrating downscaling and post-processing.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from barograph.core.models import GriddedField, ModelSource, Variable
from barograph.utils.storage import save_gridded_field


def gen_forecast(
    out: str,
    variable: str = "temperature",
    shape: tuple[int, int] = (50, 60),
    base: float = 25.0,
    noise: float = 2.5,
    seed: int = 0,
) -> None:
    rng = np.random.default_rng(seed)
    lats = np.linspace(-25.0, -20.0, shape[0])
    lons = np.linspace(-50.0, -45.0, shape[1])
    data = base + noise * rng.standard_normal(shape)

    # Add a broad warm/cool gradient for a more realistic field
    lat_w = np.linspace(-1, 1, shape[0])[:, None]
    data += lat_w * 6.0

    t = datetime(2026, 1, 2, 12)
    field = GriddedField(
        data=data.astype(np.float32),
        lats=lats,
        lons=lons,
        variable=Variable.from_value(variable),
        source=ModelSource.GFS,
        valid_time=t,
        init_time=t,
    )
    save_gridded_field(field, out)
    print(f"Wrote forecast field to {out} (shape={shape}, var={variable})")


def gen_radar_sweeps(out_dir: str, n: int = 4, size: int = 64) -> None:
    """Generate a sequence of radar sweeps showing an eastward-moving storm."""
    from pathlib import Path

    import xarray as xr

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_time = datetime(2026, 1, 2, 0, 0)
    lats = np.linspace(-25, -20, size)
    lons = np.linspace(-50, -40, size)
    y, x = np.mgrid[0:size, 0:size]
    rng = np.random.default_rng(0)

    for k in range(n):
        cx = 16 + k * 6
        data = (
            60.0 * np.exp(-(((x - cx) / 5) ** 2 + ((y - 24) / 5) ** 2))
            + rng.standard_normal((size, size)) * 2.0
        )

        ds = xr.Dataset(
            {"reflectivity": (("latitude", "longitude"), data)},
            coords={"latitude": lats, "longitude": lons},
            attrs={"scan_time": (base_time + k * timedelta(minutes=10)).isoformat()},
        )
        ds.to_netcdf(out_dir / f"sweep_{k:02d}.nc")
    print(f"Wrote {n} radar sweeps to {out_dir}")


def gen_mos_pairs(out: str, n: int = 2000) -> None:
    """Generate synthetic paired coarse model / fine observed arrays for MOS.

    Writes a CSV with columns: model_temp, model_precip, obs_temp.
    """
    from pathlib import Path

    import pandas as pd

    rng = np.random.default_rng(7)
    model_temp = rng.normal(24, 3.5, n)
    model_precip = np.clip(rng.gamma(2.0, 2.5, n), 0, None)
    obs_temp = 0.85 * model_temp + rng.normal(1.5, 2.0, n)

    df = pd.DataFrame(
        {
            "model_temp": model_temp,
            "model_precip": model_precip,
            "obs_temp": obs_temp,
        }
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {n} MOS training pairs to {out}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Generate Barograph test data")
    sub = p.add_subparsers(dest="cmd", required=True)

    fc = sub.add_parser("forecast")
    fc.add_argument("--out", default="data/gen/forecast.nc")
    fc.add_argument("--variable", default="temperature")
    fc.set_defaults(func=gen_forecast)

    ra = sub.add_parser("radar")
    ra.add_argument("--dir", dest="out_dir", default="data/gen/radar")
    ra.add_argument("--n", type=int, default=4)
    ra.set_defaults(func=gen_radar_sweeps)

    mp = sub.add_parser("mos")
    mp.add_argument("--out", default="data/gen/mos_pairs.csv")
    mp.add_argument("--n", type=int, default=2000)
    mp.set_defaults(func=gen_mos_pairs)

    args = p.parse_args()
    kws = {k: v for k, v in vars(args).items() if k not in ("cmd", "func")}
    args.func(**kws)
