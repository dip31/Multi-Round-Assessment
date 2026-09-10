"""
Storage client factory.

Returns the configured backend instance per bucket type (or ``None`` when
storage is disabled). Calling sites should always code-defensively for a
``None`` return so the existing synchronous resume flow continues to work in
environments where storage isn't configured yet.

Resolution order:
    STORAGE_BACKEND="none"   -> None  (current assessment flow / local dev)
    STORAGE_BACKEND="minio"  -> MinIOStorageClient (local dev / rollback)
    STORAGE_BACKEND="gcs"    -> GCSStorageClient   (production; Firebase/GCS)

DEPLOYMENT_MODE="demo":
    bucket_type="resumes" -> LocalStorageClient (temporary /tmp storage)
    bucket_type="audio"   -> configured backend (gcs/minio/none)
    bucket_type="reports" -> configured backend (gcs/minio/none)

DEPLOYMENT_MODE="production":
    all bucket types -> configured backend (gcs/minio)

If a future backend ("s3") is added, it is plugged in here ONLY,
with NO changes to :class:`StorageClient` consumers.
"""

from __future__ import annotations

import logging
from typing import Optional, Literal

from app.config import settings as settings_module
from app.services.storage.base import StorageClient

logger = logging.getLogger(__name__)

BucketType = Literal["resumes", "audio", "reports"]

# Per-bucket-type client cache
_clients: dict[BucketType, Optional[StorageClient]] = {}
_initialized: dict[BucketType, bool] = {}
_disabled: dict[BucketType, bool] = {}


def get_storage_client(bucket_type: BucketType = "resumes") -> Optional[StorageClient]:
    """Return the :class:`StorageClient` instance for the given bucket type, or ``None``.

    Idempotent per bucket type. When STORAGE_BACKEND is unset/``none``, returns ``None``
    so callers can fall back to their current (synchronous, in-memory) behavior.

    In demo mode, resume bucket uses LocalStorageClient regardless of STORAGE_BACKEND.
    Audio and reports buckets use the configured backend.

    Args:
        bucket_type: One of "resumes", "audio", "reports"

    Returns:
        StorageClient instance or None if disabled/unavailable.
    """
    global _clients, _initialized, _disabled

    if _initialized.get(bucket_type, False):
        return _clients.get(bucket_type)

    settings = settings_module.settings
    backend = (getattr(settings, "STORAGE_BACKEND", "none") or "none").strip().lower()
    is_demo = getattr(settings, "is_demo", False)

    # Demo mode: resumes use local storage, others use configured backend
    if is_demo and bucket_type == "resumes":
        backend = "local"

    if backend in ("", "none", "disabled"):
        _disabled[bucket_type] = True
        logger.info("Storage disabled for %s (STORAGE_BACKEND=%r).", bucket_type, backend)
        _clients[bucket_type] = None
    elif backend == "local":
        from app.services.storage.local_backend import LocalStorageClient
        try:
            _clients[bucket_type] = LocalStorageClient()
            logger.info(
                "Storage backend initialized: local (path=/tmp/edi5) for %s",
                bucket_type,
            )
        except Exception as e:
            logger.warning(
                "Storage backend 'local' failed to initialize for %s: %s — "
                "calls to get_storage_client() return None until corrected.",
                bucket_type, e
            )
            _clients[bucket_type] = None
    elif backend == "minio":
        from app.services.storage.minio_backend import MinIOStorageClient
        try:
            _clients[bucket_type] = MinIOStorageClient()
            logger.info(
                "Storage backend initialized: minio (endpoint=%s) for %s",
                getattr(settings, "MINIO_ENDPOINT", "n/a"),
                bucket_type,
            )
        except Exception as e:
            logger.warning(
                "Storage backend 'minio' failed to initialize for %s: %s — "
                "calls to get_storage_client() return None until corrected.",
                bucket_type, e
            )
            _clients[bucket_type] = None
    elif backend == "gcs":
        from app.services.storage.gcs_backend import GCSStorageClient
        try:
            _clients[bucket_type] = GCSStorageClient()
            logger.info(
                "Storage backend initialized: gcs (bucket=%s) for %s",
                getattr(settings, "GCS_BUCKET_NAME", "n/a"),
                bucket_type,
            )
        except Exception as e:
            logger.warning(
                "Storage backend 'gcs' failed to initialize for %s: %s — "
                "calls to get_storage_client() return None until corrected.",
                bucket_type, e
            )
            _clients[bucket_type] = None
    else:
        logger.warning(
            "Unknown STORAGE_BACKEND=%r for %s — storage remains disabled.",
            backend, bucket_type
        )
        _disabled[bucket_type] = True
        _clients[bucket_type] = None

    _initialized[bucket_type] = True
    return _clients.get(bucket_type)


def reset_storage_client(bucket_type: Optional[BucketType] = None) -> None:
    """Test hook: reset the cached client(s) so the next call re-resolves config.

    Args:
        bucket_type: If provided, reset only that bucket type. Otherwise reset all.
    """
    global _clients, _initialized, _disabled
    if bucket_type:
        _clients.pop(bucket_type, None)
        _initialized[bucket_type] = False
        _disabled[bucket_type] = False
    else:
        _clients.clear()
        _initialized.clear()
        _disabled.clear()