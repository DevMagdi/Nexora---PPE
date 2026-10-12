from __future__ import annotations

import pytest

from app.core import rate_limit
from app.core.rate_limit import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_blocks_until_rolling_window_expires(monkeypatch):
    now = 100.0
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now)
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=30)

    assert await limiter.check("192.0.2.1") is None
    assert await limiter.check("192.0.2.1") is None
    assert await limiter.check("192.0.2.1") == 30

    now += 31
    assert await limiter.check("192.0.2.1") is None


@pytest.mark.asyncio
async def test_rate_limiter_bounds_memory_for_many_client_addresses():
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    for index in range(4100):
        assert await limiter.check(f"192.0.2.{index}") is None
    assert len(limiter._requests) <= 4096
