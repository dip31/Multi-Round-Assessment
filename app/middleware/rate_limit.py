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

from app.config.security import decode_access_token


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
        read_max_requests: int | None = None,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Read-only dashboards may fan out over paginated data and existing
        # per-record APIs. Keep a higher read ceiling without loosening the
        # mutation ceiling.
        self.read_max_requests = read_max_requests or max_requests * 6
        self._requests: Dict[str, List[float]] = defaultdict(list)

    @staticmethod
    def _client_key(request: Request) -> str:
        """Isolate authenticated users while retaining an IP bucket for anon traffic."""
        client_ip = request.client.host if request.client else "unknown"
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            payload = decode_access_token(token)
            user_id = payload.get("sub") if payload else None
            if user_id is not None:
                return f"user:{user_id}"
        return f"ip:{client_ip}"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check the rate limit for the client IP before proceeding."""
        client_key = self._client_key(request)
        read_only = request.method in {"GET", "HEAD", "OPTIONS"}
        request_limit = self.read_max_requests if read_only else self.max_requests
        bucket_key = f"{client_key}:{'read' if read_only else 'write'}"
        now = time.time()
        window_start = now - self.window_seconds

        # Purge stale timestamps
        self._requests[bucket_key] = [
            ts for ts in self._requests[bucket_key] if ts > window_start
        ]

        if len(self._requests[bucket_key]) >= request_limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

        self._requests[bucket_key].append(now)
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
