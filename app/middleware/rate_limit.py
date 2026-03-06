"""
Simple in-memory rate-limiting middleware.

Limits each client IP to a configurable number of requests per window.
This is a **placeholder** — swap for a Redis-backed implementation
(e.g. ``slowapi``) in production.
"""

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket-style rate limiter keyed by client IP.

    Args:
        app: The ASGI application.
        max_requests: Maximum requests allowed per *window_seconds*.
        window_seconds: Rolling window duration in seconds.
    """

    def __init__(
        self,
        app: FastAPI,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check the rate limit for the client IP before proceeding."""
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        # Purge stale timestamps
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip] if ts > window_start
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


def add_rate_limit_middleware(
    app: FastAPI,
    max_requests: int = 100,
    window_seconds: int = 60,
) -> None:
    """Register the rate-limit middleware on *app*."""
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
