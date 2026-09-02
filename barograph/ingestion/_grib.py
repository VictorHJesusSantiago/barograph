"""Shared guard for GRIB parsing support.

GRIB parsing via xarray relies on the ``cfgrib`` backend, which in turn
requires the native ecCodes C library. On systems where that library is not
installed we surface a clear, actionable error instead of an opaque backend
failure.
"""

from __future__ import annotations


class EcCodesUnavailableError(RuntimeError):
    """Raised when GRIB parsing is requested but ecCodes is not available."""


def require_cfgrib() -> None:
    """Raise :class:`EcCodesUnavailableError` if GRIB parsing is unavailable."""
    try:
        import cfgrib  # noqa: F401
        import eccodes  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on environment
        raise EcCodesUnavailableError(
            "GRIB parsing requires the cfgrib Python package and the native "
            "ecCodes C library, which could not be loaded on this system "
            f"({exc}). Install ecCodes (e.g. `conda install -c conda-forge "
            "eccodes` or a system package `libeccodes`) and ensure it is "
            "available on the library search path. Use NetCDF/Zarr ingestion "
            "(ERA5 or radar) instead if GRIB is not required."
        ) from exc
