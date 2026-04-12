"""Lightweight in-memory rate limiter middleware.

Uses a sliding-window counter per client IP.  No external dependencies.
Suitable for single-instance deployments (Cloud Run with max-instances=5
still benefits because each instance limits independently).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# Defaults: 60 requests per 60 seconds per IP
DEFAULT_RATE = 60
DEFAULT_WINDOW = 60  # seconds


class _TokenBucket:
    """Per-client token bucket."""

    __slots__ = ("tokens", "last_refill", "rate", "window")

    def __init__(self, rate: int, window: int) -> None:
        self.tokens = float(rate)
        self.last_refill = time.monotonic()
        self.rate = rate
        self.window = window

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.window))
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that rejects clients exceeding the configured rate."""

    def __init__(
        self,
        app: object,
        *,
        rate: int = DEFAULT_RATE,
        window: int = DEFAULT_WINDOW,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.rate = rate
        self.window = window
        self._buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(rate, window)
        )
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self) -> None:
        """Evict stale buckets every 5 minutes to prevent memory growth."""
        now = time.monotonic()
        if now - self._last_cleanup < 300:
            return
        self._last_cleanup = now
        cutoff = now - self.window * 2
        stale = [ip for ip, b in self._buckets.items() if b.last_refill < cutoff]
        for ip in stale:
            del self._buckets[ip]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = self._client_ip(request)

        with self._lock:
            self._cleanup()
            bucket = self._buckets[client_ip]
            allowed = bucket.allow()

        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
            return Response(
                content='{"detail":"Rate limit exceeded. Try again shortly."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window)},
            )

        return await call_next(request)
