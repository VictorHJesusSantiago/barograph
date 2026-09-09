"""Caching helpers for ingestion."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from loguru import logger


class TTLCache:
    """A simple file-based TTL cache for ingested data."""

    def __init__(self, cache_dir: str | Path, ttl_hours: float = 6.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours

    def _key_path(self, key: str) -> Path:
        import hashlib
        digest = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{digest}.pkl"

    def _meta_path(self, key: str) -> Path:
        return Path(str(self._key_path(key)) + ".meta")

    def get(self, key: str) -> Any | None:
        """Retrieve from cache if not expired."""
        data_path = self._key_path(key)

        if not data_path.exists():
            return None

        # Check TTL
        mtime = data_path.stat().st_mtime
        if time.time() - mtime > self.ttl_hours * 3600:
            return None

        try:
            import pickle
            with open(data_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.debug(f"Cache read failed for {key}: {e}")
            return None

    def set(self, key: str, value: Any) -> None:
        """Store in cache."""
        import pickle
        try:
            with open(self._key_path(key), "wb") as f:
                pickle.dump(value, f)
        except Exception as e:
            logger.debug(f"Cache write failed for {key}: {e}")

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink()
        for f in self.cache_dir.glob("*.meta"):
            f.unlink()

    def is_fresh(self, key: str) -> bool:
        path = self._key_path(key)
        if not path.exists():
            return False
        return time.time() - path.stat().st_mtime <= self.ttl_hours * 3600


def memoize(ttl_hours: float = 6.0, cache_dir: str | Path | None = None):
    """Decorator to cache function results by file key.

    Args:
        ttl_hours: Cache time-to-live in hours.
        cache_dir: Directory for cache files (default: barograph_cache in tmp).
    """
    import tempfile

    target_dir = cache_dir or Path(tempfile.gettempdir()) / "barograph_cache"

    def decorator(func):
        cache = TTLCache(target_dir, ttl_hours)

        def wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__name__}:{args}:{sorted(kwargs.items())}"
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result
        return wrapper
    return decorator
