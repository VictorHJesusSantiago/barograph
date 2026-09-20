import numpy as np
import pytest

from barograph.verification.categorical import (
    ContingencyTable,
    contingency_table,
    critical_success_index,
    equitable_threat_score,
    false_alarm_ratio,
    frequency_bias,
    peirce_skill_score,
    probability_of_detection,
)


def test_contingency_table_from_arrays():
    fcst = np.array([1, 0, 1, 1, 0, 1])
    obs = np.array([1, 1, 0, 1, 0, 0])
    t = contingency_table(fcst, obs)
    assert t.hits == 2
    assert t.misses == 1
    assert t.false_alarms == 2
    assert t.correct_negatives == 1


def test_contingency_table_shape_mismatch():
    with pytest.raises(ValueError):
        contingency_table(np.array([1, 0]), np.array([1, 0, 1]))


def test_pod():
    assert probability_of_detection(hits=3, misses=1) == pytest.approx(0.75)
    assert probability_of_detection(ContingencyTable(hits=2, misses=2)) == 0.5


def test_pod_undefined_no_events():
    assert np.isnan(probability_of_detection(hits=0, misses=0))


def test_far():
    assert false_alarm_ratio(hits=2, false_alarms=2) == pytest.approx(0.5)


def test_csi():
    assert critical_success_index(hits=3, misses=1, false_alarms=2) == pytest.approx(0.5)


def test_ets_perfect_is_one():
    assert equitable_threat_score(
        hits=5, misses=0, false_alarms=0, correct_negatives=5
    ) == pytest.approx(1.0)


def test_ets_zero_for_no_samples():
    assert np.isnan(equitable_threat_score())


def test_frequency_bias_perfect_is_one():
    # balanced forecasts/observations -> bias 1
    assert frequency_bias(hits=4, misses=1, false_alarms=1, correct_negatives=2) == pytest.approx(
        1.0, rel=1e-6
    )


def test_peirce_skill_score():
    # POD=1, FAR rate = 0 -> PSS=1
    assert peirce_skill_score(
        hits=4, misses=0, false_alarms=0, correct_negatives=6
    ) == pytest.approx(1.0)
    # POD=0.5, false alarm rate=0 -> PSS=0.5
    pss = peirce_skill_score(hits=2, misses=2, false_alarms=0, correct_negatives=6)
    assert pss == pytest.approx(0.5)
