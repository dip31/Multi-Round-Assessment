"""
Local filesystem storage backend for demo resume processing.

Implements StorageClient using a temporary directory (/tmp/edi5/).
This is ONLY for temporary resume file storage during demo mode processing.
Files are automatically cleaned up after processing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.services.storage.base import StorageClient, StorageError, StorageObject

logger = logging.getLogger(__name__)


def _validate_object_key(key: str) -> None:
    """Reject empty keys and any traversal/empty segments before use."""
    if not key or not key.strip():
        raise StorageError("Object key must be non-empty.")
    parts = key.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise StorageError("Unsafe object key rejected.")


class LocalStorageClient(StorageClient):
    """Local filesystem storage client for demo mode resume processing.

    Uses /tmp/edi5/ as the base directory. All operations are scoped to this
    directory to prevent path traversal. This is temporary storage only -
    files should be deleted after processing.
    """

    def __init__(self, base_path: str = "/tmp/edi5") -> None:
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageClient initialized at %s", self.base_path)

    def _resolve_path(self, bucket: str, key: str) -> Path:
        """Resolve and validate the full path for a bucket/key pair."""
        _validate_object_key(key)
        # Validate bucket name too
        _validate_object_key(bucket)

        full = (self.base_path / bucket / key).resolve()

        # Ensure path stays within base_path (prevent traversal)
        try:
            full.relative_to(self.base_path)
        except ValueError:
            raise StorageError("Path traversal attempt rejected")

        # Create parent directories if needed
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    # ── StorageClient interface methods ────────────────────────────────

    def ensure_bucket(self, bucket: str) -> None:
        """Create bucket directory if it doesn't exist."""
        _validate_object_key(bucket)
        (self.base_path / bucket).mkdir(parents=True, exist_ok=True)

    def bucket_exists(self, bucket: str) -> bool:
        """Check if bucket directory exists."""
        _validate_object_key(bucket)
        return (self.base_path / bucket).exists()

    def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> StorageObject:
        """Upload data to local file."""
        path = self._resolve_path(bucket, key)
        path.write_bytes(data)
        logger.debug("LocalStorage: put %s/%s (%d bytes)", bucket, key, len(data))
        return StorageObject(
            bucket=bucket,
            key=key,
            size=len(data),
            content_type=content_type,
            uri=f"file://{path}",
        )

    def get(self, bucket: str, key: str) -> bytes:
        """Download data from local file."""
        path = self._resolve_path(bucket, key)
        if not path.exists():
            raise StorageError(f"Object not found: {bucket}/{key}")
        data = path.read_bytes()
        logger.debug("LocalStorage: get %s/%s (%d bytes)", bucket, key, len(data))
        return data

    def delete(self, bucket: str, key: str) -> None:
        """Delete local file (idempotent)."""
        path = self._resolve_path(bucket, key)
        if path.exists():
            path.unlink()
            logger.debug("LocalStorage: deleted %s/%s", bucket, key)

    def presigned_get_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """Return a file:// URI for local files (not a true presigned URL).

        This is a best-effort implementation for the interface. Local files
        don't have expiring signed URLs, so we return the file:// URI directly.
        The expires parameter is ignored.
        """
        path = self._resolve_path(bucket, key)
        return f"file://{path}"