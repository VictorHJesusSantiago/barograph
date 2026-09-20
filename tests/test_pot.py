import numpy as np
import pytest

from barograph.extreme.pot import POTResult, pot_return_level


def test_pot_return_level_returns_result_and_levels():
    rng = np.random.default_rng(10)
    values = rng.exponential(scale=5.0, size=4000)
    result, levels = pot_return_level(values, threshold=5.0, period=np.array([10.0, 50.0]))
    assert isinstance(result, POTResult)
    assert result.n_exceedances > 3
    assert levels.shape == (2,)
    assert np.all(np.isfinite(levels))
    assert levels[1] > levels[0]


def test_pot_only_returns_levels_above_threshold():
    rng = np.random.default_rng(11)
    values = rng.uniform(0.0, 10.0, 3000)
    _, levels = pot_return_level(values, threshold=8.0, period=np.array([20.0]))
    assert levels[0] > 8.0


def test_pot_insufficient_excesses_raises():
    with pytest.raises(ValueError):
        pot_return_level(
            np.array([1.0, 2.0, 3.0, 4.0, 5.0]), threshold=4.5, period=np.array([10.0])
        )


def test_pot_returns_levels_increase_with_period():
    rng = np.random.default_rng(12)
    values = rng.exponential(scale=4.0, size=6000)
    _, levels = pot_return_level(values, threshold=3.0, period=np.array([10.0, 100.0, 500.0]))
    assert levels[2] > levels[1] > levels[0]


def test_pot_meta_fields():
    rng = np.random.default_rng(13)
    values = rng.exponential(scale=3.0, size=2000)
    result, _ = pot_return_level(values, threshold=3.0, period=np.array([10.0]))
    assert 0.0 < result.exceedance_fraction < 1.0
    assert result.n_exceedances == int(np.sum(values > 3.0))
    assert result.threshold == 3.0
