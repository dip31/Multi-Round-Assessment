"""
Google Cloud Storage backend (also serves Firebase Storage buckets).

Implements :class:`StorageClient` against a single, private GCS bucket
(e.g. the Firebase Storage default bucket ``gs://sample-bbf6c.firebasestorage.app``).
The logical areas ``resumes/``, ``audio/`` and ``reports/`` are implemented
as key *prefixes* inside that one bucket — NOT as separate GCS buckets.

Mapping of the existing interface:
    (logical_bucket, key) -> object path inside GCS_BUCKET_NAME

Because existing callers already build keys like
``resumes/{user_id}/{session_id}/{uuid}.pdf`` and pass the logical bucket
name (e.g. ``"resumes"``), :meth:`_object_path` deduplicates: when the key
already starts with ``{logical_bucket}/`` it is used verbatim; otherwise the
prefix is prepended. Either way the resulting path is
``<area>/<student-id>/...`` — exactly the desired layout.

Credentials (in priority order, all environment-based — nothing hardcoded):
1. ``GCS_CREDENTIALS_JSON``   — full service-account JSON as one env var.
                                Preferred on Render (stored as a Secret).
2. ``GCS_CREDENTIALS_FILE``   — path to a mounted key file (local dev).
3. Application Default Credentials — ``GOOGLE_APPLICATION_CREDENTIALS``,
   attached service account / workload identity, etc.

Credential values are NEVER logged.

The google-cloud-storage SDK is imported lazily inside ``__init__`` so that
STORAGE_BACKEND != "gcs" deployments never pay the import cost and this
module stays importable in test environments without the SDK installed.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from app.config import settings as settings_module
from app.services.storage.base import StorageClient, StorageError, StorageObject

logger = logging.getLogger(__name__)

# V4 signed URLs are hard-capped at 7 days by Google; clamp defensively so a
# misconfigured ``expires`` cannot produce a 400 from the signing API.
_MAX_SIGNED_URL_SECONDS = 7 * 24 * 3600
_MIN_SIGNED_URL_SECONDS = 60


def _validate_object_key(key: str) -> None:
    """Reject empty keys and any traversal/empty segments before use."""
    if not key or not key.strip():
        raise StorageError("Object key must be non-empty.")
    parts = key.split("/")
    if any(part in ("", ".", "..") for part in parts):
        # Deliberately generic message — do not echo untrusted key material.
        raise StorageError("Unsafe object key rejected.")


class GCSStorageClient(StorageClient):
    """StorageClient backed by the official google-cloud-storage SDK.

    All objects live in ONE private physical bucket (``GCS_BUCKET_NAME``);
    the interface's ``bucket`` argument selects the logical prefix.
    """

    def __init__(self) -> None:
        settings = settings_module.settings
        self._settings = settings

        bucket_name = (getattr(settings, "GCS_BUCKET_NAME", "") or "").strip()
        if not bucket_name:
            raise StorageError(
                "GCS_BUCKET_NAME must be configured for the GCS backend."
            )
        # Accept both "my-bucket" and "gs://my-bucket" forms.
        if bucket_name.startswith("gs://"):
            bucket_name = bucket_name[len("gs://"):]
        self._bucket_name = bucket_name.strip().strip("/")

        project = (getattr(settings, "GCS_PROJECT_ID", "") or "").strip() or None
        self._project = project
        self._client = self._build_client()
        logger.info(
            "GCS storage client initialized (bucket=%s)", self._bucket_name
        )

    def _build_client(self):
        """Construct a google.cloud.storage.Client from env configuration."""
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
        except ImportError as e:  # pragma: no cover — import-time check
            raise StorageError(
                "google-cloud-storage is not installed "
                "(pip install google-cloud-storage)."
            ) from e

        creds_json = (
            getattr(self._settings, "GCS_CREDENTIALS_JSON", "") or ""
        ).strip()
        creds_file = (
            getattr(self._settings, "GCS_CREDENTIALS_FILE", "") or ""
        ).strip()

        try:
            if creds_json:
                info = json.loads(creds_json)
                credentials = service_account.Credentials.from_service_account_info(
                    info
                )
                return storage.Client(
                    project=self._project or info.get("project_id"),
                    credentials=credentials,
                )
            if creds_file:
                return storage.Client.from_service_account_json(
                    creds_file, project=self._project
                )
            # Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS,
            # Render/GCP attached service account, workload identity, ...).
            return storage.Client(project=self._project)
        except StorageError:
            raise
        except Exception as e:
            # Generic message on purpose: parse errors can embed fragments of
            # the credential material, which must never reach logs.
            raise StorageError(
                "Failed to initialize GCS client — check credentials "
                "configuration (GCS_CREDENTIALS_JSON / GCS_CREDENTIALS_FILE / ADC)."
            ) from e

    # ── helpers ──────────────────────────────────────────────────────────
    def _object_path(self, bucket: str, key: str) -> str:
        """Map (logical area, caller key) -> concrete object path.

        - Strips leading slashes from the key.
        - Rejects traversal / empty segments.
        - Deduplicates the prefix: callers already embed ``resumes/`` etc. in
          their keys, so only prepend the logical bucket when absent.
        """
        k = (key or "").lstrip("/")
        _validate_object_key(k)
        prefix = (bucket or "").strip().strip("/")
        if not prefix or k.startswith(f"{prefix}/"):
            return k
        return f"{prefix}/{k}"

    def _physical_bucket(self):
        return self._client.bucket(self._bucket_name)

    # ── interface methods ────────────────────────────────────────────────
    def ensure_bucket(self, bucket: str) -> None:
        """Validate the single physical bucket exists.

        Unlike MinIO, GCS/Firebase buckets are provisioned externally
        (Firebase console / gcloud / Terraform) and application credentials
        typically lack bucket-creation rights — so this deliberately does NOT
        auto-create. Prefixes require no provisioning.
        """
        if not self.bucket_exists(bucket):
            raise StorageError(
                f"GCS bucket {self._bucket_name!r} does not exist or is "
                "not accessible with the configured credentials."
            )

    def bucket_exists(self, bucket: str) -> bool:
        """True when the physical GCS bucket exists.

        The logical ``bucket`` argument is ignored: prefixes need no check.
        """
        try:
            return bool(self._physical_bucket().exists())
        except Exception as e:
            raise StorageError(
                f"Failed to check bucket {self._bucket_name!r}"
            ) from e

    def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type=None,
    ) -> StorageObject:
        path = self._object_path(bucket, key)
        try:
            blob = self._physical_bucket().blob(path)
            blob.upload_from_string(
                data,
                content_type=content_type or "application/octet-stream",
            )
        except Exception as e:
            raise StorageError(
                f"Failed to put object {self._bucket_name}/{path}"
            ) from e
        uri = f"https://storage.googleapis.com/{self._bucket_name}/{path}"
        # Return the ORIGINAL (logical bucket, key) pair so callers can
        # round-trip through get()/delete()/presigned_get_url() unchanged.
        return StorageObject(
            bucket=bucket,
            key=key,
            size=len(data),
            content_type=content_type,
            uri=uri,
        )

    def get(self, bucket: str, key: str) -> bytes:
        path = self._object_path(bucket, key)
        try:
            return self._physical_bucket().blob(path).download_as_bytes()
        except Exception as e:
            raise StorageError(
                f"Failed to get object {self._bucket_name}/{path}"
            ) from e

    def delete(self, bucket: str, key: str) -> None:
        """Idempotent delete — a missing object is not an error."""
        path = self._object_path(bucket, key)
        try:
            from google.api_core.exceptions import NotFound
            try:
                self._physical_bucket().blob(path).delete()
            except NotFound:
                return
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to delete object {self._bucket_name}/{path}"
            ) from e

    def presigned_get_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """Return a temporary V4 signed GET URL (bucket stays private)."""
        path = self._object_path(bucket, key)
        try:
            expires = max(
                _MIN_SIGNED_URL_SECONDS,
                min(int(expires), _MAX_SIGNED_URL_SECONDS),
            )
            url = self._physical_bucket().blob(path).generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expires),
                method="GET",
            )
            return url
        except Exception as e:
            raise StorageError(
                f"Failed to presign url for {self._bucket_name}/{path}"
            ) from e
