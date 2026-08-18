"""
Shared Redis client helper.

Provides a single, lazily-initialized Redis connection used by:
- the interview router question-rephrase cache        (cache-only; optional)
- the Sarvam TTS cache                                 (cache-only; optional)
- (Stage 4+) the Celery broker / result backend        (LOAD-BEARING for async jobs)

Reliability contract (DO NOT confuse these two roles):
- For CACHE-ONLY callers (interview rephrase cache, TTS cache), this helper
  returns ``None`` when Redis is unconfigured/unreachable so callers can
  keep working without a cache. The existing synchronous assessment flow
  therefore continues to function even if Redis is briefly unavailable.
- For CELERY callers (Stage 6 async resume pipeline), Redis is load-bearing:
  if Redis is down, background jobs CANNOT be queued or executed. Celery is
  configured with ``broker_connection_retry_on_startup=True`` so a missing
  broker FAILS the worker on startup rather than silently no-oping tasks.
  Celery code paths must NOT treat a missing Redis client as "skip the job";

``get_redis_client()`` is process-wide singleton (idempotent).
``close_redis_client()`` is provided for clean shutdown / tests so importing
the module in dev does not leak a connection.

This module purposefully does NOT raise on connection failure during normal
runtime. Production-mode strictness is enforced at the settings layer
(``app.config.settings``) instead, so misconfiguration fails at startup
rather than silently.
"""

from __future__ import annotations

import logging
from typing import Optional

import redis

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None
_initialized: bool = False


def _build_client() -> Optional[redis.Redis]:
    """Create a redis.Redis from REDIS_URL and verify connectivity via PING."""
    redis_url = settings.REDIS_URL
    if not redis_url:
        logger.info("Redis disabled: REDIS_URL not configured")
        return None
    try:
        client = redis.from_url(redis_url, decode_responses=False)
        client.ping()
        logger.info("Redis client connected")
        return client
    except Exception as e:  # pragma: no cover — environment dependent
        logger.info(f"Redis unavailable; continuing without cache: {e}")
        return None


def get_redis_client() -> Optional[redis.Redis]:
    """Return the process-wide Redis client, or ``None`` if unavailable.

    Idempotent and safe to call from any module. Callers must tolerate a
    ``None`` return (graceful degradation).
    """
    global _client, _initialized
    if _initialized:
        return _client
    _client = _build_client()
    _initialized = True
    return _client


def redis_available() -> bool:
    """Return ``True`` if a live Redis client has been initialized.

    Use this for startup diagnostics / health checks; do not rely on it to
    decide request behavior (use ``get_redis_client()`` instead so the client
    is created on first call).
    """
    return get_redis_client() is not None


def close_redis_client() -> None:
    """Close the cached client and reset state so a new client can be built."""
    global _client, _initialized
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _initialized = False
