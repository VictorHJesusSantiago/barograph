"""Tests for the risk/hazard indices module."""

from __future__ import annotations

import numpy as np

from barograph.risk import (
    HailIndex,
    WindRiskIndex,
    flood_risk_score,
    hail_index,
    wind_risk_score,
)


def test_hail_index_scale():
    # High CAPE + helicity + shear should give a high score
    high = hail_index(cape=np.array([3000.0]), srh=np.array([400.0]),
                      wind_shear=np.array([40.0]))
    low = hail_index(cape=np.array([100.0]), srh=np.array([0.0]),
                     wind_shear=np.array([5.0]))
    assert high[0] > low[0]
    assert 0.0 <= high[0] <= 10.0


def test_hail_index_broadcast():
    cape = np.full((3, 3), 2000.0)
    srh = np.full((3, 3), 200.0)
    shear = np.full((3, 3), 25.0)
    out = HailIndex().compute(cape, srh, shear)
    assert out.shape == (3, 3)


def test_hail_classification():
    assert HailIndex.classify(5.0) in ("extreme", "high", "moderate", "low")
    assert HailIndex.classify(np.array([3.0])) == "high"


def test_wind_risk_threshold():
    gust = np.array([15.0, 30.0, 50.0])
    score = wind_risk_score(gust)
    assert score[0] == 0.0  # below threshold
    assert 0.0 < score[1] < 1.0
    assert score[2] > score[1]


def test_wind_classification():
    assert WindRiskIndex.classify(0.0) == "low"
    assert WindRiskIndex.classify(0.6) == "high"


def test_flood_risk_saturated():
    score = flood_risk_score(np.array([100.0]), np.array([300.0]),
                             np.array([1.0]))
    assert score[0] == 1.0
    low = flood_risk_score(np.array([0.0]), np.array([0.0]), np.array([0.0]))
    assert low[0] == 0.0
