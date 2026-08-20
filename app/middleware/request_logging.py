"""
Request logging middleware.

Logs every incoming HTTP request with method, path, status code, and
processing time in milliseconds.
"""

import logging
import time

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("app.middleware.request_logging")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request method, path, status, and duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request, measure duration, and log the result."""
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def add_request_logging_middleware(app: FastAPI) -> None:
    """Register the request-logging middleware on *app*."""
    app.add_middleware(RequestLoggingMiddleware)
