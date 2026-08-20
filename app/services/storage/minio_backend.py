"""
MinIO object-storage backend.

Implements :class:`StorageClient` against an S3-compatible MinIO server.
This is the initial production backend; future AWS S3 / GCS backends can
subclass / reimplement the same interface.

The MinIO SDK imports lazily inside ``__init__`` so that importing the
factory module (and hence ``app.services.storage``) does NOT require the
``minio`` package at app boot time when STORAGE_BACKEND != "minio".
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings as settings_module
from app.services.storage.base import StorageClient, StorageError, StorageObject

logger = logging.getLogger(__name__)


class MinIOStorageClient(StorageClient):
    """S3-compatible storage client backed by the MinIO Python SDK."""

    def __init__(self) -> None:
        # Resolve via module attribute so tests can monkeypatch config.
        settings = settings_module.settings
        try:
            # Imported lazily so that STORAGE_BACKEND != "minio" deployments
            # do not pay the (small but non-zero) SDK import cost, and so the
            # abstraction package remains importable in test environments
            # without the SDK installed.
            from minio import Minio  # type: ignore
        except ImportError as e:  # pragma: no cover — import-time check
            raise StorageError(
                "MinIO Python SDK is not installed (pip install minio)."
            ) from e

        # Defensive production guards — settings also validates upfront but
        # belt-and-braces here prevents a partial-config problem in tests/dev.
        if not settings.MINIO_ENDPOINT:
            raise StorageError("MINIO_ENDPOINT must be configured for MinIO backend.")
        if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
            raise StorageError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be configured for MinIO backend."
            )

        self._endpoint = settings.MINIO_ENDPOINT
        self._secure = bool(settings.MINIO_SECURE)
        self._region = settings.MINIO_REGION or None
        self._client = Minio(
            self._endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=self._secure,
            region=self._region,
        )

    # ── interface methods ───────────────────────────────────────────────
    def ensure_bucket(self, bucket: str) -> None:
        try:
            from minio.error import S3Error  # type: ignore
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket, location=self._region or None)
                logger.info("MinIO: created bucket=%s", bucket)
        except S3Error as e:  # pragma: no cover — environment dependent
            raise StorageError(f"Failed to ensure bucket {bucket}") from e
        except Exception as e:
            raise StorageError(f"Failed to ensure bucket {bucket}") from e

    def bucket_exists(self, bucket: str) -> bool:
        try:
            return bool(self._client.bucket_exists(bucket))
        except Exception as e:  # pragma: no cover — environment dependent
            raise StorageError(f"Failed to check bucket {bucket}") from e

    def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> StorageObject:
        import io
        try:
            self.ensure_bucket(bucket)
            stream = io.BytesIO(data)
            self._client.put_object(
                bucket_name=bucket,
                object_name=key,
                data=stream,
                length=len(data),
                content_type=content_type or "application/octet-stream",
            )
            scheme = "https" if self._secure else "http"
            uri = f"{scheme}://{self._endpoint}/{bucket}/{key}"
            return StorageObject(
                bucket=bucket,
                key=key,
                size=len(data),
                content_type=content_type,
                uri=uri,
            )
        except Exception as e:
            raise StorageError(f"Failed to put object {bucket}/{key}") from e

    def get(self, bucket: str, key: str) -> bytes:
        try:
            response = self._client.get_object(bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception as e:
            raise StorageError(f"Failed to get object {bucket}/{key}") from e

    def delete(self, bucket: str, key: str) -> None:
        try:
            # remove_object is idempotent — no error when object is missing.
            self._client.remove_object(bucket, key)
        except Exception as e:
            raise StorageError(f"Failed to delete object {bucket}/{key}") from e

    def presigned_get_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        from datetime import timedelta
        try:
            return self._client.presigned_get_object(
                bucket_name=bucket,
                object_name=key,
                expires=timedelta(seconds=expires),
            )
        except Exception as e:
            raise StorageError(
                f"Failed to presign url for {bucket}/{key}"
            ) from e
