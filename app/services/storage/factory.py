"""
Storage client factory.

Returns the configured backend instance single-process-wide (or ``None`` when
storage is disabled). Calling sites should always code-defensively for a
``None`` return so the existing synchronous resume flow continues to work in
environments where storage isn't configured yet.

Resolution order:
    STORAGE_BACKEND="none"   -> None  (current assessment flow / local dev)
    STORAGE_BACKEND="minio"  -> MinIOStorageClient (local dev / rollback)
    STORAGE_BACKEND="gcs"    -> GCSStorageClient   (production; Firebase/GCS)

If a future backend ("s3") is added, it is plugged in here ONLY,
with NO changes to :class:`StorageClient` consumers.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings as settings_module
from app.services.storage.base import StorageClient

logger = logging.getLogger(__name__)

_client: Optional[StorageClient] = None
_initialized: bool = False
# Cache the absence-of-config state too, so we don't repeatedly compute the
# NothingBackend choice on every call.
_disabled: bool = False


def get_storage_client() -> Optional[StorageClient]:
    """Return the process-wide :class:`StorageClient` instance, or ``None``.

    Idempotent. When STORAGE_BACKEND is unset/``none``, returns ``None`` so
    callers can fall back to their current (synchronous, in-memory) behavior.

    Lazily importing the backend so a misconfigured or missing SDK only
    matters when the user has explicitly opted into that backend.

    Reads configuration via the module attribute each call (rather than a
    direct ``from app.config.settings import settings`` import) so that tests
    which monkeypatch ``app.config.settings.settings`` are reflected.
    """
    global _client, _initialized, _disabled
    if _initialized:
        return _client

    settings = settings_module.settings
    backend = (getattr(settings, "STORAGE_BACKEND", "none") or "none").strip().lower()

    if backend in ("", "none", "disabled"):
        _disabled = True
        logger.info("Storage disabled (STORAGE_BACKEND=%r).", backend)
    elif backend == "minio":
        from app.services.storage.minio_backend import MinIOStorageClient
        try:
            _client = MinIOStorageClient()
            logger.info(
                "Storage backend initialized: minio (endpoint=%s)",
                getattr(settings, "MINIO_ENDPOINT", "n/a"),
            )
        except Exception as e:
            # Log loudly but do not crash the process — the exportable contract is
            # "return None on failure", mirroring the graceful degradation of
            # other Stage-3 helpers.
            logger.warning(
                "Storage backend 'minio' failed to initialize: %s — "
                "calls to get_storage_client() return None until corrected.", e
            )
            _client = None
    elif backend == "gcs":
        from app.services.storage.gcs_backend import GCSStorageClient
        try:
            _client = GCSStorageClient()
            logger.info(
                "Storage backend initialized: gcs (bucket=%s)",
                getattr(settings, "GCS_BUCKET_NAME", "n/a"),
            )
        except Exception as e:
            # Same graceful-degradation contract as the minio branch: log the
            # failure and return None rather than crashing the process.
            # Callers (async resume router / Celery worker) already handle a
            # None storage client with safe, user-visible degradation paths.
            logger.warning(
                "Storage backend 'gcs' failed to initialize: %s — "
                "calls to get_storage_client() return None until corrected.", e
            )
            _client = None
    else:
        logger.warning(
            "Unknown STORAGE_BACKEND=%r — storage remains disabled.", backend
        )
        _disabled = True

    _initialized = True
    return _client


def reset_storage_client() -> None:
    """Test hook: reset the cached client so the next call re-resolves config."""
    global _client, _initialized, _disabled
    _client = None
    _initialized = False
    _disabled = False
