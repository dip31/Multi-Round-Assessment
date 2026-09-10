"""
Stage 5 infrastructure smoke tests.

Verifies the non-user-visible async infrastructure added in Stages 3-5:

- Stage 3: Redis client lifecycle (`app.services.redis_client`)
- Stage 4: Celery app configuration + health-check task (eager mode)
- Stage 5: Storage abstraction + factory selection (`app.services.storage`)

Test goal: catch regressions in the configuration plumbing so settings
typos or refactor mistakes break loudly. None of these tests touch the
synchronous assessment flow or any HTTP endpoint.
"""

from __future__ import annotations


# ── Stage 3: Redis client ──────────────────────────────────────────────
RED = None
_redis_available_calls = []


def test_redis_client_is_lazy_and_idempotent():
    """First call resolves; subsequent calls return the same cached client."""
    global RED
    from app.services.redis_client import (
        get_redis_client,
        redis_available,
        close_redis_client,
    )

    # Ensure clean state (other tests may have initialized it).
    close_redis_client()

    c1 = get_redis_client()
    c2 = get_redis_client()
    # Idempotent — must be exactly the same object handle (singleton).
    assert c1 is c2
    # available() reflects whatever the first call resolved to (None or client).
    assert redis_available() == (c1 is not None)

    close_redis_client()
    RED = c1


# ── Stage 4: Celery app & health-check task ────────────────────────────
def test_celery_app_points_to_redis_when_broker_not_overridden():
    """When CELERY_BROKER_URL is empty, Celery falls back to REDIS_URL."""
    from app.config import settings as sm
    from app.worker.celery_app import _resolve_broker_url, _resolve_result_backend

    # When the override env vars are empty, resolution falls back to REDIS_URL.
    if not sm.settings.CELERY_BROKER_URL:
        assert _resolve_broker_url() == sm.settings.REDIS_URL
    if not sm.settings.CELERY_RESULT_BACKEND:
        assert _resolve_result_backend() == sm.settings.REDIS_URL


def test_health_check_task_runs_eager():
    """health_check.delay() runs synchronously in eager mode and returns JSON."""
    from app.worker.celery_app import celery_app
    from app.worker.tasks import health_check

    # Preserve and flip to eager for the duration of the assertion only.
    saved_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        r = health_check.delay()
        result = r.get()
        assert result["status"] == "ok"
        assert result["worker"] == "alive"
        assert result["eager"] is True
    finally:
        celery_app.conf.task_always_eager = saved_eager


# ── Stage 5: Storage abstraction ──────────────────────────────────────
def test_storage_factory_disabled_by_default():
    """STORAGE_BACKEND=none (or unset) returns None — sync resume flow unaffected."""
    from app.config import settings as sm
    import app.services.storage.factory as factory

    # Force "none" + reset so we're testing the factory path, not a cached result.
    original = sm.settings.STORAGE_BACKEND
    sm.settings = sm.settings.model_copy(update={"DEPLOYMENT_MODE": "production", "STORAGE_BACKEND": "none"})
    factory.reset_storage_client()
    try:
        assert factory.get_storage_client() is None
    finally:
        sm.settings = sm.settings.model_copy(update={"STORAGE_BACKEND": original})
        factory.reset_storage_client()


def test_storage_factory_returns_minio_when_configured():
    """With STORAGE_BACKEND=minio + creds, factory returns a MinIOStorageClient.

    We do NOT actually connect to MinIO; the client only constructs on init.
    """
    from app.config import settings as sm
    import app.services.storage.factory as factory

    original = sm.settings
    sm.settings = sm.settings.model_copy(
        update={
            "DEPLOYMENT_MODE": "production",
            "STORAGE_BACKEND": "minio",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "test-access",
            "MINIO_SECRET_KEY": "test-secret",
            "MINIO_SECURE": False,
            "MINIO_REGION": "",
        }
    )
    factory.reset_storage_client()
    try:
        from app.services.storage.minio_backend import MinIOStorageClient
        client = factory.get_storage_client()
        assert isinstance(client, MinIOStorageClient)
    finally:
        sm.settings = original
        factory.reset_storage_client()


def test_storage_client_interface_minimal_contract():
    """MinIOStorageClient implements all abstract methods of StorageClient."""
    from app.services.storage.base import StorageClient
    from app.services.storage.minio_backend import MinIOStorageClient

    # issubclass catches accidental renames + dropped abstractmethods.
    assert issubclass(MinIOStorageClient, StorageClient)
    expected = {"ensure_bucket", "bucket_exists", "put", "get", "delete", "presigned_get_url"}
    assert expected.issubset({m for m in dir(MinIOStorageClient)})


def test_production_mode_rejects_storage_none():
    """APP_ENV=production + STORAGE_BACKEND=none fails fast (no silent fallback)."""
    import os
    from pydantic import ValidationError

    from app.config.settings import Settings

    # Snapshot & override env; restore on exit.
    orig_env = os.environ.get("APP_ENV"), os.environ.get("STORAGE_BACKEND"), os.environ.get("DEPLOYMENT_MODE")
    os.environ["APP_ENV"] = "production"
    os.environ["STORAGE_BACKEND"] = "none"
    os.environ["DEPLOYMENT_MODE"] = "production"
    try:
        try:
            Settings()
            assert False, "expected ValidationError"
        except ValidationError as e:
            msgs = " ".join(err["msg"] for err in e.errors())
            assert "STORAGE_BACKEND" in msgs
    finally:
        for k, v in zip(("APP_ENV", "STORAGE_BACKEND", "DEPLOYMENT_MODE"), orig_env):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── Stage 6 prep: resume_processing_jobs model ────────────────────────
def test_resume_processing_jobs_model_registered():
    """ResumeProcessingJob maps to Base.metadata so alembic autogenerate works."""
    from app.database.base import Base
    from app.models.resume_processing import ResumeProcessingJob

    assert "resume_processing_jobs" in Base.metadata.tables
    table = Base.metadata.tables["resume_processing_jobs"]
    expected_cols = {
        "id", "user_id", "session_id", "storage_key", "original_filename",
        "status", "progress_step", "error_message", "retry_count",
        "created_at", "started_at", "completed_at", "job_metadata",
    }
    assert expected_cols == set(table.columns.keys())
    # Indexes — confirm the four documented indexes exist (without over-checking).
    col_indexed = {idx.columns.keys()[0] for idx in table.indexes}
    assert {"user_id", "session_id", "status", "created_at"}.issubset(col_indexed)


def test_resume_processing_jobs_status_default_is_pending():
    """The 'status' column defaults to PENDING at INSERT time.

    Stage 6 endpoint contract: when a job row is created it sits unpicked
    until a worker claims it; this default encodes the PENDING lifecycle
    without forcing callers to set status explicitly.
    """
    from app.models.resume_processing import ResumeProcessingJob

    table = ResumeProcessingJob.__table__
    # server_default text on the String column carries 'PENDING' (with quotes
    # stripped). Verify it parses to a PENDING literal in SQL.
    server_default = table.c.status.server_default
    assert server_default is not None
    rendered = server_default.arg.text if hasattr(server_default, "arg") else str(server_default)
    assert "PENDING" in rendered.upper()
