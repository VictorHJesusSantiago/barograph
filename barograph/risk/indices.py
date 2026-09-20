"""Composable hazard indices using thermodynamic and dynamic parameters.

Each index is a pure function of basic fields (CAPE, shear, wind, rain) and
can be applied element-wise over a grid via numpy broadcasting, giving both
scalar and :class:`GriddedField` use.
"""

from __future__ import annotations

import numpy as np

from barograph.core.models import GriddedField


def hail_index(
    cape: np.ndarray,
    srh: np.ndarray,
    wind_shear: np.ndarray,
) -> np.ndarray:
    """A dimensionless large-hail threat index (0..~10 scale).

    Combines CAPE, storm-relative helicity (SRH) and deep-layer wind shear,
    normalised so that typical severe values sit near 1.
    """
    cape = np.asarray(cape, dtype=np.float64)
    srh = np.asarray(srh, dtype=np.float64)
    shear = np.asarray(wind_shear, dtype=np.float64)
    score = (0.004 * cape + 0.01 * srh + 0.02 * shear) / 100.0
    return np.clip(score, 0.0, 10.0)


def wind_risk_score(
    wind_gust: np.ndarray,
    threshold: float = 25.0,
    max_gust: float = 60.0,
) -> np.ndarray:
    """A 0..1 wind risk score from peak gust speed (m/s)."""
    gust = np.asarray(wind_gust, dtype=np.float64)
    scale = (gust - threshold) / (max_gust - threshold)
    return np.clip(scale, 0.0, 1.0)


def flood_risk_score(
    rainfall: np.ndarray,
    antecedent: np.ndarray,
    soil_moisture: np.ndarray,
) -> np.ndarray:
    """A 0..1 flash-flood risk score.

    Args:
        rainfall: Short-term accumulated rainfall (mm).
        antecedent: Antecedent rainfall over the prior days (mm).
        soil_moisture: Top-layer soil moisture as a 0..1 fraction.
    """
    rain = np.asarray(rainfall, dtype=np.float64)
    ant = np.asarray(antecedent, dtype=np.float64)
    soil = np.asarray(soil_moisture, dtype=np.float64)
    # piecewise ramp for rainfall (significant at >= 30 mm)
    r = np.clip((rain - 10.0) / 40.0, 0.0, 1.0)
    a = np.clip(ant / 120.0, 0.0, 1.0)
    s = np.clip(soil, 0.0, 1.0)
    return np.clip(0.55 * r + 0.25 * a + 0.20 * s, 0.0, 1.0)


class HailIndex:
    """Object oriented helper for the large-hail threat index."""

    def compute(self, cape: np.ndarray, srh: np.ndarray, shear: np.ndarray) -> np.ndarray:
        """Return the hail index for the supplied fields."""
        return hail_index(cape, srh, shear)

    @staticmethod
    def classify(score: float | np.ndarray) -> str:
        """Map a hail-index value to a categorical threat level."""
        s = float(np.max(score)) if np.ndim(score) else float(score)
        if s >= 4.0:
            return "extreme"
        if s >= 2.5:
            return "high"
        if s >= 1.0:
            return "moderate"
        return "low"


class WindRiskIndex:
    """Object oriented helper for the wind risk score."""

    def compute(self, gust: np.ndarray) -> np.ndarray:
        """Return the wind risk score for a gust field."""
        return wind_risk_score(gust)

    @staticmethod
    def classify(score: float | np.ndarray) -> str:
        s = float(np.max(score)) if np.ndim(score) else float(score)
        if s >= 0.75:
            return "extreme"
        if s >= 0.5:
            return "high"
        if s >= 0.25:
            return "moderate"
        return "low"


def _as_2d(arr: np.ndarray) -> np.ndarray:
    """Coerce a (n_lat, n_lon) array, guarding against 1D input."""
    a = np.asarray(arr)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    return a


def hail_index_field(cape: GriddedField, srh: GriddedField, shear: GriddedField) -> GriddedField:
    """Apply the hail index to three aligned :class:`GriddedField` inputs."""
    score = hail_index(cape.data, srh.data, shear.data)
    return GriddedField(
        data=_as_2d(score),
        lats=cape.lats,
        lons=cape.lons,
        variable=cape.variable,
        source=cape.source,
        valid_time=cape.valid_time,
        init_time=cape.init_time,
        meta={"index": "hail"},
    )
