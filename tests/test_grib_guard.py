"""Test GRIB/ecCodes degradation guard."""

import builtins

import pytest


@pytest.fixture
def block_grib_imports(monkeypatch):
    orig = builtins.__import__

    def fake_import(name, *a, **kw):
        if name in ("cfgrib", "eccodes"):
            raise ImportError(f"No module named '{name}'")
        return orig(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_require_cfgrib_raises_when_unavailable(block_grib_imports):
    from barograph.ingestion._grib import require_cfgrib

    with pytest.raises(
        Exception,
        match="ecCodes|cfgrib|GRIB parsing",
    ):
        require_cfgrib()


def test_require_cfgrib_noop_when_available(monkeypatch):
    import importlib

    try:
        importlib.import_module("eccodes")
    except Exception:
        pytest.skip("ecCodes library not available in this environment")
    from barograph.ingestion._grib import require_cfgrib

    orig = builtins.__import__

    def normal_import(name, *a, **kw):
        return orig(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", normal_import)
    require_cfgrib()
