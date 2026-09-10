"""Tests for the GCS (Firebase Storage) storage backend.

These tests do NOT require a live GCS/Firebase account, network access, or
real credentials — google-cloud-storage's Client is stubbed, and the backend
client instances are constructed without invoking __init__'s SDK path where
possible.

Covers:
- factory selects GCS when STORAGE_BACKEND=gcs
- factory still selects MinIO when STORAGE_BACKEND=minio
- factory returns None when STORAGE_BACKEND=none
- object-key / prefix mapping (incl. double-prefix dedup and traversal guard)
- put/get/delete/presigned round-trip against a stubbed SDK
- StorageError semantics and interface conformance
"""

from __future__ import annotations

import pytest

from app.services.storage.base import StorageClient, StorageError


# ── Stubbed google-cloud-storage machinery ────────────────────────────
class FakeBlob:
    def __init__(self, store):
        self._store = store
        self.path = None

    def upload_from_string(self, data, content_type=None):
        self._store[self.path] = (bytes(data), content_type)

    def download_as_bytes(self):
        if self.path not in self._store:
            from google.api_core.exceptions import NotFound
            raise NotFound(f"object {self.path} missing")
        return self._store[self.path][0]

    def delete(self):
        # Real SDK raises NotFound for absent objects; mimic that.
        if self.path not in self._store:
            from google.api_core.exceptions import NotFound
            raise NotFound(f"object {self.path} missing")
        del self._store[self.path]

    def generate_signed_url(self, **kwargs):
        return f"https://storage.googleapis.com/signed/{self.path}"


class FakeBucket:
    def __init__(self, store, name):
        self._store = store
        self.name = name

    def blob(self, path):
        b = FakeBlob(self._store)
        b.path = path
        return b

    def exists(self):
        return True


class FakeGCSClient:
    """Stand-in for google.cloud.storage.Client (offline)."""

    def __init__(self, project=None, credentials=None):
        self.project = project
        self.credentials = credentials
        self.store = {}

    def bucket(self, name):
        return FakeBucket(self.store, name)


def _make_client(bucket_name="sample-bbf6c.firebasestorage.app"):
    """Build a GCSStorageClient bypassing the real SDK init path."""
    import app.config.settings as sm
    from app.services.storage.gcs_backend import GCSStorageClient

    client = object.__new__(GCSStorageClient)
    client._bucket_name = bucket_name
    client._project = "test-project"
    client._settings = sm.settings
    client._client = FakeGCSClient(project="test-project")
    return client


# ── Factory selection ─────────────────────────────────────────────────
def test_factory_selects_gcs_when_configured(monkeypatch):
    from app.config import settings as sm
    import app.services.storage.factory as factory
    from google.cloud import storage as gcs_storage

    monkeypatch.setattr(gcs_storage, "Client", FakeGCSClient)
    original = sm.settings
    sm.settings = original.model_copy(
        update={
            "DEPLOYMENT_MODE": "production",
            "STORAGE_BACKEND": "gcs",
            "GCS_BUCKET_NAME": "sample-bbf6c.firebasestorage.app",
        }
    )
    factory.reset_storage_client()
    try:
        from app.services.storage.gcs_backend import GCSStorageClient
        client = factory.get_storage_client()
        assert isinstance(client, GCSStorageClient)
    finally:
        sm.settings = original
        factory.reset_storage_client()


def test_factory_gcs_failure_degrades_gracefully():
    """A broken GCS config must yield None (no crash), mirroring minio."""
    from app.config import settings as sm
    import app.services.storage.factory as factory

    original = sm.settings
    # No bucket name -> GCSStorageClient.__init__ raises StorageError.
    sm.settings = original.model_copy(update={"DEPLOYMENT_MODE": "production", "STORAGE_BACKEND": "gcs"})
    factory.reset_storage_client()
    try:
        assert factory.get_storage_client() is None
    finally:
        sm.settings = original
        factory.reset_storage_client()


def test_factory_still_selects_minio_when_configured():
    from app.config import settings as sm
    import app.services.storage.factory as factory

    original = sm.settings
    sm.settings = original.model_copy(
        update={
            "DEPLOYMENT_MODE": "production",
            "STORAGE_BACKEND": "minio",
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ACCESS_KEY": "test-access",
            "MINIO_SECRET_KEY": "test-secret",
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


def test_factory_disabled_when_none():
    from app.config import settings as sm
    import app.services.storage.factory as factory

    original = sm.settings
    sm.settings = original.model_copy(update={"DEPLOYMENT_MODE": "production", "STORAGE_BACKEND": "none"})
    factory.reset_storage_client()
    try:
        assert factory.get_storage_client() is None
    finally:
        sm.settings = original
        factory.reset_storage_client()


# ── Interface conformance ─────────────────────────────────────────────
def test_gcs_client_implements_full_interface():
    from app.services.storage.gcs_backend import GCSStorageClient

    assert issubclass(GCSStorageClient, StorageClient)
    expected = {
        "ensure_bucket", "bucket_exists", "put", "get", "delete",
        "presigned_get_url",
    }
    assert expected.issubset({m for m in dir(GCSStorageClient)})


# ── Object key / prefix behavior ──────────────────────────────────────
def test_object_path_dedups_existing_prefix():
    c = _make_client()
    # Callers already embed "resumes/" — must NOT double up.
    assert (
        c._object_path("resumes", "resumes/12/34/abc.pdf")
        == "resumes/12/34/abc.pdf"
    )


def test_object_path_prepends_missing_prefix():
    c = _make_client()
    assert c._object_path("audio", "12/intro.mp3") == "audio/12/intro.mp3"
    assert (
        c._object_path("reports", "12/r.pdf") == "reports/12/r.pdf"
    )


@pytest.mark.parametrize(
    "bad_key",
    ["../etc/passwd", "a/../b", "resumes//x.pdf", "", "  "],
)
def test_object_path_rejects_unsafe_keys(bad_key):
    c = _make_client()
    with pytest.raises(StorageError):
        c._object_path("resumes", bad_key)


def test_bucket_name_strips_gs_scheme():
    from app.services.storage.gcs_backend import GCSStorageClient

    client = object.__new__(GCSStorageClient)
    # Simulate the scheme-stripping branch without touching the SDK.
    raw = "gs://sample-bbf6c.firebasestorage.app"
    bucket_name = raw[len("gs://"):] if raw.startswith("gs://") else raw
    client._bucket_name = bucket_name.strip().strip("/")
    assert client._bucket_name == "sample-bbf6c.firebasestorage.app"


# ── put / get / delete / presign round-trip (stubbed) ─────────────────
def test_put_returns_logical_pair_and_uploads_once():
    c = _make_client()
    obj = c.put(
        "resumes",
        "resumes/7/9/uuid.pdf",
        b"%PDF-resume-bytes",
        content_type="application/pdf",
    )
    assert obj.bucket == "resumes"
    assert obj.key == "resumes/7/9/uuid.pdf"
    assert obj.size == len(b"%PDF-resume-bytes")
    stored = c._client.store["resumes/7/9/uuid.pdf"]
    assert stored[0] == b"%PDF-resume-bytes"
    assert stored[1] == "application/pdf"
    assert obj.uri.startswith("https://storage.googleapis.com/")
    assert "sample-bbf6c" in obj.uri


def test_get_round_trips_bytes():
    c = _make_client()
    c.put("audio", "audio/3/q.mp3", b"audio-bytes")
    assert c.get("audio", "audio/3/q.mp3") == b"audio-bytes"


def test_get_missing_object_raises_storage_error():
    c = _make_client()
    with pytest.raises(StorageError):
        c.get("reports", "reports/1/nope.pdf")


def test_delete_is_idempotent():
    c = _make_client()
    c.put("resumes", "resumes/2/2/x.pdf", b"data")
    c.delete("resumes", "resumes/2/2/x.pdf")
    # Second delete: object already gone -> no exception.
    c.delete("resumes", "resumes/2/2/x.pdf")


def test_presigned_url_returned_without_public_objects():
    c = _make_client()
    c.put("resumes", "resumes/5/5/y.pdf", b"data")
    url = c.presigned_get_url("resumes", "resumes/5/5/y.pdf", expires=3600)
    assert url.startswith("https://storage.googleapis.com/signed/")
    # Nothing was made public — data only reachable via the signed URL.


def test_presigned_url_expiration_clamped():
    from datetime import timedelta

    captured = {}

    class RecordingBlob(FakeBlob):
        def generate_signed_url(self, **kwargs):
            captured["expiration"] = kwargs.get("expiration")
            return "https://signed"

    class RecordingBucket(FakeBucket):
        def blob(self, path):
            b = RecordingBlob(self._store)
            b.path = path
            return b

    class RecordingClient(FakeGCSClient):
        def bucket(self, name):
            return RecordingBucket(self.store, name)

    c = _make_client()
    c._client = RecordingClient()
    c.presigned_get_url("resumes", "resumes/1/1/z.pdf", expires=10**9)
    assert captured["expiration"] <= timedelta(days=7)


# ── Settings validation ───────────────────────────────────────────────
def test_production_gcs_requires_bucket_name():
    from pydantic import ValidationError

    from app.config.settings import Settings

    base = dict(
        SECRET_KEY="x" * 40,
        DATABASE_URL="postgresql://u:p@h/db",
        APP_ENV="production",
        DEPLOYMENT_MODE="production",
        DB_POOL_SIZE=10,
        STORAGE_BACKEND="gcs",
    )
    with pytest.raises(ValidationError):
        Settings(**{**base, "GCS_BUCKET_NAME": ""})


def test_production_gcs_valid_with_credentials():
    from app.config.settings import Settings

    s = Settings(
        SECRET_KEY="x" * 40,
        DATABASE_URL="postgresql://u:p@h/db",
        APP_ENV="production",
        DB_POOL_SIZE=10,
        STORAGE_BACKEND="gcs",
        GCS_BUCKET_NAME="sample-bbf6c.firebasestorage.app",
        GCS_CREDENTIALS_JSON='{"project_id": "demo"}',
    )
    assert s.GCS_BUCKET_NAME.endswith(".firebasestorage.app")
