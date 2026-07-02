"""
Lightweight in-process TTL cache for read-heavy, low-cardinality endpoints.

This stack has no Redis (see requirements.txt), so a process-local cache is
the appropriate tool for endpoints like analytics dashboards that are hit
frequently but only need to reflect the underlying match data within a
coarse freshness window (the match DataFrame itself already refreshes every
6 hours — see app/ml/data/loader.py).

Usage
-----
    from app.core.cache import async_ttl_cache

    @async_ttl_cache(ttl_seconds=60)
    async def dashboard_stats(...):
        ...

Not a general-purpose cache: keys are derived from the function's arguments
via ``repr()``, so it's intended for endpoints/services called with simple,
hashable-ish arguments (str/int/None), not arbitrary objects like DB
sessions. Pass ``ignore_args`` to exclude positional/keyword arguments that
shouldn't participate in the cache key (e.g. a leading AsyncSession).
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Optional


class _TTLEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at


def async_ttl_cache(
    ttl_seconds: float,
    max_size: int = 128,
    ignore_args: Optional[set[int]] = None,
    ignore_kwargs: Optional[set[str]] = None,
) -> Callable:
    """
    Decorator that caches an async function's return value for ``ttl_seconds``.

    Parameters
    ----------
    ttl_seconds   : How long a cached result stays valid.
    max_size      : Maximum number of distinct cache entries (simple FIFO
                     eviction once exceeded — this is a small-cardinality
                     cache for a handful of endpoint argument combos, not a
                     general LRU cache).
    ignore_args   : Positional-argument indices to exclude from the cache
                     key (e.g. {0} to skip a leading ``db: AsyncSession``).
    ignore_kwargs : Keyword-argument names to exclude from the cache key.
    """
    ignore_args = ignore_args or set()
    ignore_kwargs = ignore_kwargs or set()

    def decorator(func: Callable) -> Callable:
        store: dict[str, _TTLEntry] = {}

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key_args = tuple(a for i, a in enumerate(args) if i not in ignore_args)
            key_kwargs = tuple(
                sorted((k, v) for k, v in kwargs.items() if k not in ignore_kwargs)
            )
            key = repr((key_args, key_kwargs))

            now = time.monotonic()
            entry = store.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value

            result = await func(*args, **kwargs)

            if len(store) >= max_size:
                # Simple bounded eviction: drop an arbitrary (oldest-inserted
                # in practice, since dicts preserve insertion order) entry.
                store.pop(next(iter(store)), None)
            store[key] = _TTLEntry(result, now + ttl_seconds)
            return result

        def cache_clear() -> None:
            store.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
