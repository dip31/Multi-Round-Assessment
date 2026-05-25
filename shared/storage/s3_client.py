"""
Storage client — local filesystem for development, S3 for production.
Shared by Intake (docs) and Sourcing (resumes).
"""
import os
import shutil
from pathlib import Path
from config import STORAGE_BACKEND, UPLOAD_DIR


class StorageClient:
    """Unified file storage interface."""

    def __init__(self):
        self.backend = STORAGE_BACKEND
        self.upload_dir = UPLOAD_DIR

    async def save_file(self, file_bytes: bytes, filename: str, folder: str = "resumes") -> str:
        """Save a file and return its storage path/URL."""
        if self.backend == "local":
            return self._save_local(file_bytes, filename, folder)
        else:
            return await self._save_s3(file_bytes, filename, folder)

    def _save_local(self, file_bytes: bytes, filename: str, folder: str) -> str:
        """Save to local filesystem."""
        target_dir = self.upload_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / filename
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        return str(filepath)

    async def _save_s3(self, file_bytes: bytes, filename: str, folder: str) -> str:
        """Save to S3 (placeholder — needs boto3 in production)."""
        # In production, this would use boto3
        # For now, fall back to local storage
        print(f"⚠️ S3 not configured, falling back to local storage")
        return self._save_local(file_bytes, filename, folder)

    async def get_file(self, path: str) -> bytes:
        """Retrieve a file by path."""
        if self.backend == "local":
            with open(path, "rb") as f:
                return f.read()
        raise NotImplementedError("S3 get not implemented in dev mode")

    async def delete_file(self, path: str):
        """Delete a file."""
        if self.backend == "local" and os.path.exists(path):
            os.remove(path)


# Global singleton
storage_client = StorageClient()
