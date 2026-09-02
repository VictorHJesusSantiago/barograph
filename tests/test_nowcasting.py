"""Unit tests for nowcasting optical flow and advection."""

import numpy as np

from barograph.nowcasting.extrapolation import Extrapolator
from barograph.nowcasting.optical_flow import OpticalFlowNowcaster


def make_sweeps(n_sweeps=2, size=32):
    from datetime import datetime, timedelta

    from barograph.core.models import RadarSweep

    sweeps = []
    base_time = datetime(2026, 1, 1, 0, 0)
    for k in range(n_sweeps):
        # Storm blob moving right by 3 px per frame
        center_x = 8 + k * 3
        y, x = np.mgrid[0:size, 0:size]
        data = 60.0 * np.exp(-(((x - center_x) / 4) ** 2 + ((y - 16) / 4) ** 2))

        sweeps.append(RadarSweep(
            data=data,
            lats=np.linspace(-30, -20, size),
            lons=np.linspace(-50, -40, size),
            scan_time=base_time + k * timedelta(minutes=10),
        ))
    return sweeps


def test_optical_flow_block_mapping():
    size = 32
    y, x = np.mgrid[0:size, 0:size]
    f1 = np.exp(-(((x - 8) / 5) ** 2 + ((y - 16) / 5) ** 2))
    f2 = np.exp(-(((x - 10) / 5) ** 2 + ((y - 16) / 5) ** 2))

    nw = OpticalFlowNowcaster(method="block", winsize=3)
    u, v = nw.compute_flow(f1, f2)
    # Expected horizontal motion +2, vertical 0
    assert u.shape == (size, size)
    assert np.nanmean(u) > 0.5


def test_extrapolator_nowcast_produces_fields():
    sweeps = make_sweeps(2)
    ext = Extrapolator(nowcaster=OpticalFlowNowcaster(method="block", winsize=3))

    from datetime import timedelta
    leads = [timedelta(minutes=30)]
    out = ext.nowcast(sweeps, leads)
    assert len(out) == 1
    assert out[0].shape == (32, 32)


def test_extrapolator_motion_positive_x():
    sweeps = make_sweeps(2)
    ext = Extrapolator(nowcaster=OpticalFlowNowcaster(method="block", winsize=3))
    u, v, dt = ext.estimate_motion(sweeps)
    assert np.nanmean(u) > 0  # storm moving right
    assert dt > 0


def test_rainfall_rate():
    ext = Extrapolator()
    dbz = np.array([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    rate = ext.rainfall_rate(dbz)
    assert rate[0] == 0.0  # 0 dBZ -> 0 mm/h
    assert rate[-1] > rate[0]  # monotonic increasing
