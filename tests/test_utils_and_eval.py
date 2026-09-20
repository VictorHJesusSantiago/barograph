"""Unit tests for cache, MOS evaluation, and logging utilities."""

import numpy as np
import pytest

from barograph.utils.cache import TTLCache, memoize


# ---------- Cache ----------
def test_ttl_cache_set_get(tmp_path):
    cache = TTLCache(tmp_path / "cache")
    cache.set("a", {"x": 1})
    assert cache.get("a") == {"x": 1}


def test_ttl_cache_miss(tmp_path):
    cache = TTLCache(tmp_path / "cache")
    assert cache.get("missing") is None


def test_ttl_cache_clear(tmp_path):
    cache = TTLCache(tmp_path / "cache")
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_ttl_cache_is_fresh(tmp_path):
    cache = TTLCache(tmp_path / "cache")
    assert not cache.is_fresh("a")
    cache.set("a", 1)
    assert cache.is_fresh("a")


def test_ttl_cache_expiry(tmp_path):
    cache = TTLCache(tmp_path / "cache", ttl_hours=0.0)
    cache.set("a", 1)
    assert cache.get("a") is None  # expired immediately


def test_ttl_cache_expired_get(tmp_path, monkeypatch):
    cache = TTLCache(tmp_path / "cache", ttl_hours=6.0)
    cache.set("a", 1)
    data_path = cache._key_path("a")
    old_mtime = data_path.stat().st_mtime - 3600 * 8  # 8h ago
    import os

    os.utime(data_path, (old_mtime, old_mtime))
    assert cache.get("a") is None


def test_memoize_decorator(tmp_path, monkeypatch):
    calls = {"n": 0}

    @memoize(ttl_hours=6.0, cache_dir=tmp_path / "memo")
    def add(a, b):
        calls["n"] += 1
        return a + b

    assert add(2, 3) == 5
    assert add(2, 3) == 5
    assert calls["n"] == 1  # cached
    assert add(5, 5) == 10
    assert calls["n"] == 2  # different args


# ---------- MOS evaluation ----------
def test_skill_vs_reference_perfect():
    from barograph.mos.evaluation import skill_vs_reference

    obs = np.array([1.0, 2.0, 3.0, 4.0])
    preds = obs.copy()
    reference = np.full(4, 2.5)
    result = skill_vs_reference(preds, reference, obs)
    assert result["skill_mse"] == pytest.approx(1.0)
    assert result["skill_mae"] == pytest.approx(1.0)


def test_skill_vs_reference_worse_than_ref():
    from barograph.mos.evaluation import skill_vs_reference

    obs = np.array([1.0, 2.0, 3.0, 4.0])
    preds = np.array([9.0, 9.0, 9.0, 9.0])
    reference = np.array([2.0, 2.0, 3.0, 4.0])
    result = skill_vs_reference(preds, reference, obs)
    assert result["skill_mse"] < 0


def test_mse_reduction():
    from barograph.mos.evaluation import mse_reduction

    obs = np.array([1.0, 2.0, 3.0, 4.0])
    preds = obs.copy()
    reference = np.full(4, 2.5)
    assert mse_reduction(preds, reference, obs) == pytest.approx(100.0)


def test_cross_validate_mos_linear(tmp_path):
    from barograph.mos.evaluation import cross_validate_mos

    rng = np.random.default_rng(0)
    X = rng.normal(size=(80, 5))
    y = X @ np.array([1.0, -2.0, 0.5, 3.0, -1.0]) + rng.normal(0, 0.1, 80)
    results = cross_validate_mos(X, y, algorithm="linear", n_folds=4)
    assert results["n_samples"] == 80
    assert results["correlation"] > 0.99
    assert results["mae"] < 0.5


# ---------- Logging ----------
def test_setup_logging():
    from barograph.utils.logging import get_logger, setup_logging

    setup_logging(level="DEBUG")
    logger = get_logger("barograph.test")
    assert logger is not None
