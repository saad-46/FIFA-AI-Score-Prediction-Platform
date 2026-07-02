"""
Tests for app/core/cache.py's async_ttl_cache decorator.
"""

import asyncio
import pytest

from app.core.cache import async_ttl_cache


@pytest.mark.asyncio
async def test_cache_hit_within_ttl_does_not_recall_function():
    calls = []

    @async_ttl_cache(ttl_seconds=60)
    async def compute(x):
        calls.append(x)
        return x * 2

    result1 = await compute(5)
    result2 = await compute(5)

    assert result1 == 10
    assert result2 == 10
    # Second call should have hit the cache, not re-executed the function.
    assert calls == [5]


@pytest.mark.asyncio
async def test_cache_miss_after_ttl_expiry_recalls_function():
    calls = []

    @async_ttl_cache(ttl_seconds=0.05)
    async def compute(x):
        calls.append(x)
        return x * 2

    result1 = await compute(5)
    assert result1 == 10
    assert calls == [5]

    # Wait past the TTL so the entry expires.
    await asyncio.sleep(0.1)

    result2 = await compute(5)
    assert result2 == 10
    # Function should have been called again since the cached entry expired.
    assert calls == [5, 5]


@pytest.mark.asyncio
async def test_cache_different_args_produce_different_entries():
    calls = []

    @async_ttl_cache(ttl_seconds=60)
    async def compute(x):
        calls.append(x)
        return x * 2

    result_a = await compute(1)
    result_b = await compute(2)
    result_a_again = await compute(1)

    assert result_a == 2
    assert result_b == 4
    assert result_a_again == 2
    # Only two distinct calls should have actually executed the function body.
    assert calls == [1, 2]


@pytest.mark.asyncio
async def test_cache_different_kwargs_produce_different_entries():
    calls = []

    @async_ttl_cache(ttl_seconds=60)
    async def compute(x, label="a"):
        calls.append((x, label))
        return f"{x}-{label}"

    r1 = await compute(1, label="a")
    r2 = await compute(1, label="b")

    assert r1 == "1-a"
    assert r2 == "1-b"
    assert calls == [(1, "a"), (1, "b")]


@pytest.mark.asyncio
async def test_cache_ignore_args_excludes_leading_positional_from_key():
    calls = []

    @async_ttl_cache(ttl_seconds=60, ignore_args={0})
    async def compute(session, x):
        calls.append(x)
        return x * 10

    # Two different "sessions" (ignored) but the same meaningful arg x=1
    # should be treated as the same cache entry.
    result1 = await compute("session-A", 1)
    result2 = await compute("session-B", 1)

    assert result1 == 10
    assert result2 == 10
    assert calls == [1]


@pytest.mark.asyncio
async def test_cache_clear_forces_recompute():
    calls = []

    @async_ttl_cache(ttl_seconds=60)
    async def compute(x):
        calls.append(x)
        return x * 2

    await compute(5)
    compute.cache_clear()
    await compute(5)

    assert calls == [5, 5]


@pytest.mark.asyncio
async def test_cache_max_size_evicts_when_exceeded():
    calls = []

    @async_ttl_cache(ttl_seconds=60, max_size=2)
    async def compute(x):
        calls.append(x)
        return x

    await compute(1)
    await compute(2)
    await compute(3)  # should trigger eviction of an existing entry

    # After exceeding max_size, at least one earlier entry should have been
    # evicted, so re-calling it must recompute rather than hit cache.
    await compute(1)
    await compute(2)

    # We can't assert exact eviction order (FIFO in practice via dict
    # insertion order), but total calls must exceed the 3 unique args since
    # eviction forces at least one recompute.
    assert len(calls) > 3
