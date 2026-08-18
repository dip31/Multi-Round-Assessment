"""
StorageClient interface.

Concrete backends (e.g. ``app.services.storage.minio_backend.MinIOStorageClient``)
implement this interface. Business code never imports the backend directly.

Why a small abstract interface (and not just MinIO's API):
- We want to be able to swap MinIO → AWS S3 → local FS without touching any
  caller.
- Keep the method surface minimal: only what resume/audio/report flows will
  need in Stage 6.

All methods raise :class:`StorageError` on backend failure so callers can
catch a single platform-agnostic exception.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional


class StorageError(Exception):
    """Raised by storage backends on any put/get/delete failure.

    Carries the original backend error as ``__cause__`` for diagnostics but
    does not leak provider-specific message format to callers.
    """


@dataclass(frozen=True)
class StorageObject:
    """Locates stored content — opaque to callers from other backends.

    ``bucket`` and ``key`` together uniquely identify an object. ``size`` and
    ``content_type`` are provided when known. ``uri`` is a backend-specific URI
    suitable for logging but not for direct HTTP retrieval — use
    ``presigned_get_url`` when a temporary download URL is needed.
    """
    bucket: str
    key: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    uri: Optional[str] = None


class StorageClient(abc.ABC):
    """Backend-agnostic object-storage client."""

    @abc.abstractmethod
    def ensure_bucket(self, bucket: str) -> None:
        """Create ``bucket`` if it doesn't exist; no-op otherwise."""

    @abc.abstractmethod
    def bucket_exists(self, bucket: str) -> bool:
        """Return True if ``bucket`` exists."""

    @abc.abstractmethod
    def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> StorageObject:
        """Upload ``data`` under ``(bucket, key)``; return a StorageObject."""

    @abc.abstractmethod
    def get(self, bucket: str, key: str) -> bytes:
        """Download all bytes for ``(bucket, key)``."""

    @abc.abstractmethod
    def delete(self, bucket: str, key: str) -> None:
        """Delete ``(bucket, key)``; idempotent (no error if absent)."""

    @abc.abstractmethod
    def presigned_get_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """Return a temporary URL for downloading ``(bucket, key)``.

        ``expires`` is in seconds. Clients must use this URL before it
        expires; backends are free to cap/extend the policy as appropriate.
        """
