"""
Object-storage abstraction.

Business logic interacts with file storage only through
``get_storage_client()`` returning a :class:`StorageClient` instance,
or ``None`` when storage is not configured (``STORAGE_BACKEND=none``).

This keeps the storage implementation replaceable from configuration alone
(local MinIO today; AWS S3 / GCS tomorrow) without callers touching
provider-specific APIs.

Stage 5 ships ONLY this non-user-visible infrastructure. No endpoint,
service, or business flow imports it yet — the synchronous resume-upload
endpoint's behavior is unchanged until Stage 6.
"""

from app.services.storage.base import StorageClient, StorageError, StorageObject
from app.services.storage.factory import get_storage_client

__all__ = [
    "StorageClient",
    "StorageError",
    "StorageObject",
    "get_storage_client",
]
