"""
Celery application and worker infrastructure.

This package contains the Celery application and the task registry. The
worker is intentionally minimal at this stage: it only declares the Celery
app, configures the broker/result backend, and registers a no-op health
check task. No task is imported by any FastAPI endpoint or web request
path yet. Business tasks (resume parsing, etc.) will be added in Stage 6
behind an async API surface that is independent of the synchronous flow.

Resolution order for broker / result backend:
    1. CELERY_BROKER_URL  / CELERY_RESULT_BACKEND  (if non-empty)
    2. REDIS_URL            (Celery installs a redis transport)

Eager mode (CELERY_TASK_ALWAYS_EAGER) runs tasks synchronously inside the
calling process. Useful for unit tests but never valid in production — the
settings layer enforces this in ``_enforce_production_mode``.
"""

from app.worker.celery_app import celery_app

__all__ = ["celery_app"]
