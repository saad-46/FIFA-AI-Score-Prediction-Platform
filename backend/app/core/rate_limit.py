"""
Cross-worker rate limiting for the expensive public endpoints.

WHY NOT AN IN-MEMORY LIMITER
----------------------------
``render.yaml`` starts uvicorn with ``--workers 2``. A per-process counter
would let a client take 2x the configured limit — and inconsistently,
depending on which worker the load balancer picked — which defeats the point.
There is no Redis in this stack (a documented architectural decision; see
``app/core/cache.py``), but Postgres is already a hard startup dependency
shared by every worker, so it is the available shared state.

MECHANISM
---------
Fixed-window counter in ``public.rate_limit_buckets``, incremented by a single
atomic statement:

    INSERT ... ON CONFLICT (bucket_key, window_start) DO UPDATE
      SET request_count = rate_limit_buckets.request_count + 1
    RETURNING request_count

One round trip, no read-then-write race, correct under concurrency across any
number of workers. A fixed window (rather than a sliding log) keeps this to one
row and one statement per request; the tradeoff is the standard fixed-window
boundary burst, which is acceptable here because the limits exist to prevent
sustained abuse of expensive compute, not to enforce a precise QPS contract.

FAIL-OPEN
---------
If the limiter's own query fails, the request is allowed and the error logged.
A rate limiter that takes the API down when its bookkeeping table has a problem
is worse than the abuse it prevents.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import text

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int          # requests allowed per window
    window_seconds: int


def _client_identity(request: Request, user: Optional[dict]) -> str:
    """
    Authenticated users are limited per-account; anonymous clients per-IP.

    Render terminates TLS at a proxy, so ``request.client.host`` is the
    proxy's address for every caller — the real client is the first entry of
    X-Forwarded-For. Using the proxy IP would rate-limit the entire internet
    as a single client.
    """
    if user and user.get("sub"):
        return f"user:{user['sub']}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


async def check_rate_limit(
    db,
    rule: RateLimitRule,
    request: Request,
    user: Optional[dict] = None,
) -> None:
    """Raise 429 when the caller is over ``rule``; otherwise return silently."""
    settings = get_settings()
    if not settings.RATE_LIMIT_ENABLED:
        return

    identity = _client_identity(request, user)
    window_start = int(time.time()) // rule.window_seconds * rule.window_seconds
    bucket_key = f"{rule.name}:{identity}"

    try:
        result = await db.execute(
            text("""
                INSERT INTO public.rate_limit_buckets
                    (bucket_key, window_start, request_count)
                VALUES (:key, to_timestamp(:ws), 1)
                ON CONFLICT (bucket_key, window_start)
                DO UPDATE SET request_count = public.rate_limit_buckets.request_count + 1
                RETURNING request_count
            """),
            {"key": bucket_key, "ws": window_start},
        )
        count = result.scalar_one()
    except Exception as exc:
        # Fail open — see module docstring.
        logger.warning("rate limiter unavailable, allowing request: %s", exc)
        return

    if count > rule.limit:
        retry_after = window_start + rule.window_seconds - int(time.time())
        retry_after = max(retry_after, 1)
        logger.info("rate limit hit: %s (%d/%d)", bucket_key, count, rule.limit)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded for this endpoint "
                f"({rule.limit} requests per {rule.window_seconds}s). "
                f"Retry in {retry_after}s."
            ),
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(rule.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(window_start + rule.window_seconds),
            },
        )


def prediction_rule() -> RateLimitRule:
    """
    Individual match predictions.

    Sized against real frontend behaviour: the predict page issues exactly one
    request per form submission, and a user exploring matchups might reasonably
    fire off a dozen in a minute. The default leaves generous headroom for that
    while stopping bulk scraping of the model.
    """
    s = get_settings()
    return RateLimitRule("predict", s.RATE_LIMIT_PREDICT_PER_MINUTE, 60)


def simulation_rule() -> RateLimitRule:
    """
    Tournament simulation — deliberately far stricter.

    A single call is 5-9 seconds of multi-process CPU and accepts up to 100,000
    iterations, so a handful of concurrent callers can saturate a starter-plan
    instance. The frontend runs this on an explicit button press, not on page
    load, so a small per-minute allowance does not affect legitimate use.
    """
    s = get_settings()
    return RateLimitRule("simulate", s.RATE_LIMIT_SIMULATE_PER_MINUTE, 60)
