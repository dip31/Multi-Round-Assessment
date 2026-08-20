"""
Celery application factory.

Centralizes all Celery configuration so task authors import tasks from
``app.worker`` and never need to re-configure the broker/backend.

Imports of task modules must be done lazily / explicitly inside the worker
process so that importing this module during web-serving does NOT force
the entire task dependency tree (e.g. RAG / YOLO) to load eagerly.
"""

from __future__ import annotations

import logging

from celery import Celery

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _resolve_broker_url() -> str:
    """CELERY_BROKER_URL overrides, else fall back to REDIS_URL."""
    if settings.CELERY_BROKER_URL and settings.CELERY_BROKER_URL.strip():
        return settings.CELERY_BROKER_URL.strip()
    return settings.REDIS_URL


def _resolve_result_backend() -> str:
    """CELERY_RESULT_BACKEND overrides, else fall back to REDIS_URL."""
    if settings.CELERY_RESULT_BACKEND and settings.CELERY_RESULT_BACKEND.strip():
        return settings.CELERY_RESULT_BACKEND.strip()
    return settings.REDIS_URL


# Modules imported when the Celery WORKER starts up. Listed explicitly rather
# than relying on glob-based autodiscovery so the boot order is deterministic
# and nothing imports heavy optional dependencies (RAG / YOLO) at web startup.
_TASK_INCLUDE = ["app.worker.tasks"]

# The Celery app object. Both name and broker URL are required.
celery_app: Celery = Celery(
    "ai_placement_platform",
    broker=_resolve_broker_url(),
    backend=_resolve_result_backend(),
    include=_TASK_INCLUDE,
)

# ── Configuration ─────────────────────────────────────────────────────
celery_app.conf.update(
    # Eager mode runs tasks synchronously inside the caller. Useful for tests.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    # Default serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone — leave Celery default (UTC) to avoid DST surprises.
    timezone="UTC",
    enable_utc=True,
    # Worker reliability defaults
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Don't silently keep results forever — sane TTL for the result backend
    result_expires=60 * 60 * 24,  # 24 hours
    # Safety: refuse to start a worker if the broker is unreachable
    # (so misconfiguration fails loud, instead of silently no-oping tasks)
    broker_connection_retry_on_startup=True,
)


# Health-bound introspection helpers (used by tests / worker startup).
def get_celery_app() -> Celery:
    """Return the configured Celery instance (factory-style accessor)."""
    return celery_app


__all__ = ["celery_app", "get_celery_app"]
