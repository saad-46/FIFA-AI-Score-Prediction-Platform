"""
Rate-limiting tests.

The limiter's correctness argument rests on shared state (Postgres) rather
than per-process counters, because Render runs `uvicorn --workers 2`. These
tests exercise the limiter logic against a fake DB session that emulates the
atomic INSERT ... ON CONFLICT DO UPDATE ... RETURNING contract, so they run
without a live database while still proving the behaviour that matters:

  * the counter is keyed per (endpoint, client, window)
  * exceeding the limit raises 429 with usable retry information
  * distinct clients don't interfere
  * a *shared* counter store produces one consistent limit no matter which
    worker serves the request — the property an in-memory limiter lacks
  * limiter failure fails OPEN rather than taking the endpoint down
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.rate_limit import (
    RateLimitRule, _client_identity, check_rate_limit,
    prediction_rule, simulation_rule,
)


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class FakeSharedStore:
    """
    Stands in for the Postgres table. Crucially this is a single store that
    several FakeSession instances share — the same way two uvicorn workers
    share one database — so tests can prove cross-worker behaviour.
    """

    def __init__(self):
        self.counts: dict[tuple[str, int], int] = {}

    def incr(self, key: str, window_start: int) -> int:
        k = (key, window_start)
        self.counts[k] = self.counts.get(k, 0) + 1
        return self.counts[k]


class FakeSession:
    """Emulates the single atomic upsert-and-return the limiter relies on."""

    def __init__(self, store: FakeSharedStore, fail: bool = False):
        self.store = store
        self.fail = fail
        self.calls = 0

    async def execute(self, statement, params=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated database failure")
        return FakeResult(self.store.incr(params["key"], int(params["ws"])))


class FakeRequest:
    def __init__(self, ip: str = "203.0.113.5", forwarded: str | None = None):
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.client = type("C", (), {"host": ip})()


@pytest.fixture(autouse=True)
def _enable_rate_limiting(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    get_settings.cache_clear()


RULE = RateLimitRule("test", limit=3, window_seconds=60)


# ═══════════════════════════════════════════════════════════════════════════
# Core behaviour
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_requests_under_limit_succeed():
    db = FakeSession(FakeSharedStore())
    request = FakeRequest()
    for _ in range(RULE.limit):
        await check_rate_limit(db, RULE, request, user=None)   # must not raise


@pytest.mark.asyncio
async def test_request_over_limit_is_rejected_with_429():
    db = FakeSession(FakeSharedStore())
    request = FakeRequest()
    for _ in range(RULE.limit):
        await check_rate_limit(db, RULE, request, user=None)

    with pytest.raises(HTTPException) as exc:
        await check_rate_limit(db, RULE, request, user=None)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_429_carries_retry_information():
    db = FakeSession(FakeSharedStore())
    request = FakeRequest()
    for _ in range(RULE.limit + 1):
        try:
            await check_rate_limit(db, RULE, request, user=None)
        except HTTPException as exc:
            headers = exc.headers
            assert "Retry-After" in headers
            assert int(headers["Retry-After"]) >= 1
            assert headers["X-RateLimit-Limit"] == str(RULE.limit)
            assert headers["X-RateLimit-Remaining"] == "0"
            assert int(headers["X-RateLimit-Reset"]) > int(time.time())
            assert str(RULE.limit) in exc.detail
            return
    pytest.fail("limit was never exceeded")


# ═══════════════════════════════════════════════════════════════════════════
# Client isolation — legitimate users must not be blocked by someone else
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_distinct_ips_have_independent_budgets():
    store = FakeSharedStore()
    db = FakeSession(store)
    noisy = FakeRequest(forwarded="198.51.100.1")
    quiet = FakeRequest(forwarded="198.51.100.2")

    for _ in range(RULE.limit):
        await check_rate_limit(db, RULE, noisy, user=None)
    with pytest.raises(HTTPException):
        await check_rate_limit(db, RULE, noisy, user=None)

    # the second client is unaffected
    await check_rate_limit(db, RULE, quiet, user=None)


@pytest.mark.asyncio
async def test_authenticated_users_limited_per_account_not_per_ip():
    """Two users behind one NAT/office IP must not consume each other's
    budget."""
    store = FakeSharedStore()
    db = FakeSession(store)
    shared_ip = FakeRequest(forwarded="198.51.100.9")

    for _ in range(RULE.limit):
        await check_rate_limit(db, RULE, shared_ip, user={"sub": "user-a"})
    with pytest.raises(HTTPException):
        await check_rate_limit(db, RULE, shared_ip, user={"sub": "user-a"})

    await check_rate_limit(db, RULE, shared_ip, user={"sub": "user-b"})


@pytest.mark.asyncio
async def test_separate_endpoints_have_separate_budgets():
    store = FakeSharedStore()
    db = FakeSession(store)
    request = FakeRequest()
    other = RateLimitRule("other", limit=3, window_seconds=60)

    for _ in range(RULE.limit):
        await check_rate_limit(db, RULE, request, user=None)
    with pytest.raises(HTTPException):
        await check_rate_limit(db, RULE, request, user=None)

    await check_rate_limit(db, other, request, user=None)


def test_forwarded_header_is_used_over_proxy_ip():
    """Render terminates TLS at a proxy — using request.client.host would
    rate-limit the whole internet as one client."""
    request = FakeRequest(ip="10.0.0.1", forwarded="203.0.113.77, 10.0.0.1")
    assert _client_identity(request, None) == "ip:203.0.113.77"


def test_authenticated_identity_takes_precedence():
    request = FakeRequest(forwarded="203.0.113.77")
    assert _client_identity(request, {"sub": "abc-123"}) == "user:abc-123"


# ═══════════════════════════════════════════════════════════════════════════
# Cross-worker behaviour — the reason this is DB-backed at all
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_limit_is_shared_across_workers():
    """
    Two sessions = two uvicorn workers hitting one shared store. The combined
    budget must still be `limit`, not `limit` per worker. A per-process
    limiter would let 2x through here — which is exactly the bug this design
    exists to avoid.
    """
    store = FakeSharedStore()
    worker_a = FakeSession(store)
    worker_b = FakeSession(store)
    request = FakeRequest(forwarded="203.0.113.42")

    allowed = 0
    rejected = 0
    for i in range(RULE.limit + 3):
        db = worker_a if i % 2 == 0 else worker_b     # alternate workers
        try:
            await check_rate_limit(db, RULE, request, user=None)
            allowed += 1
        except HTTPException:
            rejected += 1

    assert allowed == RULE.limit, f"expected {RULE.limit} allowed across both workers, got {allowed}"
    assert rejected == 3


# ═══════════════════════════════════════════════════════════════════════════
# Failure modes and configuration
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_limiter_failure_fails_open():
    """A broken bookkeeping table must not take the API down."""
    db = FakeSession(FakeSharedStore(), fail=True)
    request = FakeRequest()
    for _ in range(RULE.limit + 5):
        await check_rate_limit(db, RULE, request, user=None)   # must not raise


@pytest.mark.asyncio
async def test_disabled_flag_skips_limiting(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    db = FakeSession(FakeSharedStore())
    request = FakeRequest()
    for _ in range(RULE.limit + 5):
        await check_rate_limit(db, RULE, request, user=None)
    assert db.calls == 0, "limiter should not touch the database when disabled"


def test_configured_limits_are_sane_for_frontend_usage():
    """
    Guards against someone setting a limit so low that normal use breaks.
    The predict page issues one request per form submission; the simulator is
    an explicit button press taking 5-9s server-side.
    """
    settings = get_settings()
    predict = prediction_rule()
    simulate = simulation_rule()

    assert predict.limit >= 10, "too low for a user exploring several matchups"
    assert simulate.limit >= 3, "too low for a user re-running a simulation"
    assert simulate.limit < predict.limit, (
        "simulation is far more expensive than prediction and must be stricter"
    )
    assert predict.window_seconds == simulate.window_seconds == 60
    assert settings.RATE_LIMIT_PREDICT_PER_MINUTE == predict.limit
    assert settings.RATE_LIMIT_SIMULATE_PER_MINUTE == simulate.limit
