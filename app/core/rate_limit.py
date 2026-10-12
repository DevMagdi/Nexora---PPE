from __future__ import annotations

import asyncio
import ipaddress
import time
from collections import OrderedDict, deque

from fastapi import Request

from app.core.config import settings


class SlidingWindowRateLimiter:
    """Process-local rolling-window limiter; the deployment uses one API worker."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> int | None:
        """Return retry-after seconds when over limit; otherwise record the request."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            bucket = self._requests.get(key)
            if bucket is None:
                bucket = deque()
                self._requests[key] = bucket
            else:
                self._requests.move_to_end(key)
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return max(1, int(bucket[0] + self.window_seconds - now + 0.999))
            bucket.append(now)

            # Expire idle addresses, then enforce a hard cap against high-cardinality traffic.
            if len(self._requests) > 4096:
                for host, entries in list(self._requests.items()):
                    while entries and entries[0] <= cutoff:
                        entries.popleft()
                    if not entries:
                        self._requests.pop(host, None)
                while len(self._requests) > 4096:
                    self._requests.popitem(last=False)
            return None


def get_client_ip(request: Request) -> str:
    """Use forwarded addresses only when the direct peer is a trusted proxy."""
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer

    trusted_networks = settings.trusted_proxy_networks
    if not any(peer_ip in network for network in trusted_networks):
        return str(peer_ip)

    forwarded = request.headers.get("x-forwarded-for", "")
    chain: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for item in forwarded.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            chain.append(ipaddress.ip_address(item))
        except ValueError:
            continue
    chain.append(peer_ip)

    for address in reversed(chain):
        if not any(address in network for network in trusted_networks):
            return str(address)
    return str(peer_ip)
