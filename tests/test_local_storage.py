"""
Tests for LocalStorageClient.
"""

import pytest
import tempfile
import os
from pathlib import Path

from app.services.storage.local_backend import LocalStorageClient
from app.services.storage.base import StorageError


class TestLocalStorageClient:
    """Test LocalStorageClient implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def storage(self, temp_dir):
        """Create a LocalStorageClient instance."""
        return LocalStorageClient(base_path=temp_dir)

    def test_put_get_delete(self, storage):
        """Test basic put, get, delete operations."""
        bucket = "test"
        key = "file.txt"
        data = b"Hello, World!"
        
        # Put
        obj = storage.put(bucket, key, data, content_type="text/plain")
        assert obj.bucket == bucket
        assert obj.key == key
        assert obj.size == len(data)
        assert obj.content_type == "text/plain"
        assert obj.uri.startswith("file://")
        
        # Get
        retrieved = storage.get(bucket, key)
        assert retrieved == data
        
        # Delete
        storage.delete(bucket, key)
        with pytest.raises(StorageError, match="not found"):
            storage.get(bucket, key)

    def test_put_creates_directories(self, storage):
        """Test that put creates nested directories."""
        bucket = "resumes"
        key = "user123/session456/file.pdf"
        data = b"PDF content"
        
        obj = storage.put(bucket, key, data)
        assert obj.size == len(data)
        
        retrieved = storage.get(bucket, key)
        assert retrieved == data

    def test_path_traversal_rejected(self, storage):
        """Test that path traversal attempts are rejected."""
        with pytest.raises(StorageError, match="Unsafe object key"):
            storage.put("bucket", "../escape.txt", b"data")
        
        with pytest.raises(StorageError, match="Unsafe object key"):
            storage.get("bucket", "../../etc/passwd")
        
        with pytest.raises(StorageError, match="Unsafe object key"):
            storage.delete("bucket", "foo/../../bar")

    def test_empty_key_rejected(self, storage):
        """Test that empty keys are rejected."""
        with pytest.raises(StorageError, match="non-empty"):
            storage.put("bucket", "", b"data")
        
        with pytest.raises(StorageError, match="non-empty"):
            storage.get("bucket", "   ")

    def test_bucket_operations(self, storage):
        """Test bucket_exists and ensure_bucket."""
        assert storage.bucket_exists("new_bucket") is False
        storage.ensure_bucket("new_bucket")
        assert storage.bucket_exists("new_bucket") is True

    def test_delete_idempotent(self, storage):
        """Test that delete is idempotent (no error if missing)."""
        storage.delete("bucket", "nonexistent.txt")  # Should not raise

    def test_presigned_get_url(self, storage):
        """Test presigned_get_url returns file:// URI."""
        bucket = "test"
        key = "file.txt"
        storage.put(bucket, key, b"data")
        
        url = storage.presigned_get_url(bucket, key)
        assert url.startswith("file://")
        assert key in url

    def test_unsafe_bucket_name_rejected(self, storage):
        """Test that unsafe bucket names are rejected."""
        with pytest.raises(StorageError, match="Unsafe object key"):
            storage.put("../bucket", "key", b"data")
        
        with pytest.raises(StorageError, match="Unsafe object key"):
            storage.get("bucket/../other", "key")

    def test_default_base_path(self):
        """Test default base path is /tmp/edi5 (or D:\\tmp\\edi5 on Windows)."""
        storage = LocalStorageClient()
        assert "edi5" in str(storage.base_path)
        assert storage.base_path.exists()

    def test_custom_base_path(self, temp_dir):
        """Test custom base path."""
        custom_path = os.path.join(temp_dir, "custom")
        storage = LocalStorageClient(base_path=custom_path)
        assert str(storage.base_path) == str(Path(custom_path).resolve())
        assert storage.base_path.exists()