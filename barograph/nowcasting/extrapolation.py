"""Advection-based extrapolation of radar fields."""

from __future__ import annotations

from datetime import timedelta

import numpy as np

from barograph.core.models import RadarSweep
from barograph.nowcasting.optical_flow import OpticalFlowNowcaster


class Extrapolator:
    """Extrapolate the most recent radar sweep forward in time using optical flow.

    Uses a semi-Lagrangian advection with the estimated motion field.
    """

    def __init__(
        self,
        nowcaster: OpticalFlowNowcaster | None = None,
        timescale_hours: float = 1.0,
    ):
        self.nowcaster = nowcaster or OpticalFlowNowcaster()
        self.timescale_hours = timescale_hours

    def estimate_motion(
        self,
        sweeps: list[RadarSweep],
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """Estimate storm motion from a sequence of radar sweeps.

        Returns (u, v) motion in pixels/hour and the dt in hours.
        """
        if len(sweeps) < 2:
            raise ValueError("Need at least 2 sweeps to estimate motion")

        # Use the last two frames
        f1 = sweeps[-2]
        f2 = sweeps[-1]
        dt_hours = (f2.scan_time - f1.scan_time).total_seconds() / 3600.0
        if dt_hours <= 0:
            dt_hours = self.timescale_hours

        # Ensure equal shapes
        if f1.shape != f2.shape:
            raise ValueError("Radar sweeps must have identical grid shapes")

        u, v = self.nowcaster.compute_flow(f1.data, f2.data)
        return u, v, dt_hours

    def advect(
        self,
        field: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        """Advect reflectivity forward by dt (in hours)."""
        ny, nx = field.shape

        # Movement distance in pixels
        dx = u * dt
        dy = v * dt

        y_idx, x_idx = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")

        # Source coordinates (semi-Lagrangian): trace backwards
        sx = x_idx.astype(np.float64) - dx
        sy = y_idx.astype(np.float64) - dy

        from scipy.ndimage import map_coordinates

        coords = np.array([sy.ravel(), sx.ravel()])
        extrapolated = map_coordinates(field, coords, order=1, mode="nearest").reshape(ny, nx)

        # Preserve original NaN structure
        extrapolated[~np.isfinite(extrapolated)] = np.nan
        return extrapolated

    def nowcast(
        self,
        sweeps: list[RadarSweep],
        lead_times: list[timedelta] | None = None,
    ) -> list[RadarSweep]:
        """Produce nowcast sweeps at the given lead times."""
        u, v, dt_hours = self.estimate_motion(sweeps)

        if lead_times is None:
            default_minutes = [15, 30, 45, 60, 90, 120]
            lead_times = [timedelta(minutes=m) for m in default_minutes]

        last = sweeps[-1]
        results = []
        for lead in lead_times:
            lead_hours = lead.total_seconds() / 3600.0
            data = self.advect(last.data, u, v, lead_hours)
            results.append(
                RadarSweep(
                    data=data,
                    lats=last.lats,
                    lons=last.lons,
                    scan_time=last.scan_time + lead,
                    elevation=last.elevation,
                    meta={
                        **last.meta,
                        "lead_minutes": lead.total_seconds() / 60.0,
                        "method": "optical_flow_advection",
                    },
                )
            )
        return results

    def rainfall_rate(
        self,
        reflectivity_dbz: np.ndarray,
        zr_a: float = 300.0,
        zr_b: float = 1.4,
    ) -> np.ndarray:
        """Convert reflectivity (dBZ) to rainfall rate (mm/h) using Z-R relation."""
        linear_z = 10.0 ** (reflectivity_dbz / 10.0)
        rate = (linear_z / zr_a) ** (1.0 / zr_b)
        rate[reflectivity_dbz <= 0] = 0.0
        return rate

    def accumulated_precip(
        self,
        reflectivity_series: list[np.ndarray],
        dt_minutes: float = 10.0,
    ) -> np.ndarray:
        """Accumulate precipitation from a series of reflectivity fields."""
        total = np.zeros_like(reflectivity_series[0])
        dt_hours = dt_minutes / 60.0
        for field in reflectivity_series:
            total += self.rainfall_rate(field) * dt_hours
        return total
