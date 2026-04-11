"""Shared in-memory result cache for expensive API queries.

All cached data is invalidated when POST /admin/reload is called.
Thread-safe via a single lock — suitable for single-instance deployments.
"""

from __future__ import annotations

import threading
import time
from typing import Any

_result_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()

DEFAULT_TTL = 300  # 5 minutes


def get_cached(key: str, ttl: int = DEFAULT_TTL) -> Any | None:
    """Return cached value if present and not expired, else None."""
    with _cache_lock:
        entry = _result_cache.get(key)
        if entry is not None:
            cached_at, data = entry
            if time.monotonic() - cached_at < ttl:
                return data
            del _result_cache[key]
    return None


def set_cached(key: str, value: Any) -> None:
    """Store a value in the cache."""
    with _cache_lock:
        _result_cache[key] = (time.monotonic(), value)


def clear_all() -> None:
    """Invalidate all cached results. Called by admin/reload."""
    with _cache_lock:
        _result_cache.clear()
