"""
BIBI Cars - Object Storage Abstraction (Sprint 2 expansion)
============================================================

Provides a swappable storage backend so File Manager doesn't care
where bytes physically live. Default backend is the local filesystem
rooted at ``/app/backend/uploads``; an S3 stub is included for the
future env-switch (set ``STORAGE_PROVIDER=s3`` + AWS creds).

Public API:
    storage = get_storage()
    info = await storage.put(prefix, filename, data, content_type)
        # -> {key, url, size, content_type, filename, backend}
    stream = storage.open(key)              # binary file-like
    storage.delete(key)
    storage.path(key)                       # absolute fs path (Local only)

Key convention:  ``<prefix>/<uuid>__<safe_filename>``
Files are served back through ``/api/files/<key>`` (handled by server.py).
"""
from __future__ import annotations
import logging
import os
import re
import uuid
import shutil
import mimetypes
from pathlib import Path
from typing import BinaryIO, Dict, Any, Optional

UPLOAD_ROOT = Path(os.environ.get("BIBI_UPLOAD_ROOT", "/app/backend/uploads")).resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
logger = logging.getLogger("bibi.storage")


def _sanitize_filename(name: str) -> str:
    name = (name or "file").strip().split("/")[-1].split("\\")[-1]
    name = _SAFE_NAME_RE.sub("_", name)[:120]
    return name or "file"


def _safe_prefix(prefix: str) -> str:
    parts = [p for p in (prefix or "misc").split("/") if p and p not in (".", "..")]
    return "/".join(_SAFE_NAME_RE.sub("_", p) for p in parts) or "misc"


class StorageProvider:
    """Abstract surface every backend must implement."""
    backend: str = "abstract"

    async def put(self, prefix: str, filename: str, data: bytes,
                  content_type: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        raise NotImplementedError

    def path(self, key: str) -> Path:
        raise NotImplementedError("path() is local-only")


class LocalStorage(StorageProvider):
    backend = "local"

    def __init__(self, root: Path = UPLOAD_ROOT):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def put(self, prefix: str, filename: str, data: bytes,
                  content_type: Optional[str] = None) -> Dict[str, Any]:
        safe_prefix = _safe_prefix(prefix)
        safe_name = _sanitize_filename(filename)
        key = f"{safe_prefix}/{uuid.uuid4().hex[:12]}__{safe_name}"
        dest = (self.root / key).resolve()
        if not str(dest).startswith(str(self.root)):
            raise ValueError("unsafe path")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            f.write(data)
        size = dest.stat().st_size
        ct = content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        return {
            "key":          key,
            "url":          f"/api/files/{key}",
            "size":         size,
            "content_type": ct,
            "filename":     safe_name,
            "backend":      self.backend,
        }

    def open(self, key: str) -> BinaryIO:
        p = self.path(key)
        return p.open("rb")

    def path(self, key: str) -> Path:
        clean = key.lstrip("/")
        if ".." in clean.split("/"):
            raise ValueError("unsafe key")
        p = (self.root / clean).resolve()
        if not str(p).startswith(str(self.root)):
            raise ValueError("unsafe key")
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(key)
        return p

    def delete(self, key: str) -> bool:
        try:
            p = self.path(key)
        except FileNotFoundError:
            return False
        try:
            p.unlink()
            parent = p.parent
            try:
                next(parent.iterdir())
            except StopIteration:
                shutil.rmtree(parent, ignore_errors=True)
            return True
        except Exception:
            return False


class S3Storage(StorageProvider):
    """AWS S3 backend stub.

    Currently inert - it will refuse to operate unless AWS_* env vars
    are present. Set STORAGE_PROVIDER=s3 + AWS_ACCESS_KEY_ID +
    AWS_SECRET_ACCESS_KEY + S3_BUCKET to enable.
    """
    backend = "s3"

    def __init__(self) -> None:
        self.bucket = os.environ.get("S3_BUCKET")
        self.region = os.environ.get("AWS_REGION") or os.environ.get("S3_REGION") or "us-east-1"
        self.endpoint = os.environ.get("S3_ENDPOINT_URL")
        if not self.bucket:
            raise RuntimeError(
                "S3Storage: S3_BUCKET env var is required to enable S3 backend"
            )
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise RuntimeError("S3Storage: boto3 is not installed") from exc
        self._client = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )

    async def put(self, prefix: str, filename: str, data: bytes,
                  content_type: Optional[str] = None) -> Dict[str, Any]:
        safe_prefix = _safe_prefix(prefix)
        safe_name = _sanitize_filename(filename)
        key = f"{safe_prefix}/{uuid.uuid4().hex[:12]}__{safe_name}"
        ct = content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=ct)
        return {
            "key":          key,
            "url":          f"/api/files/{key}",
            "size":         len(data),
            "content_type": ct,
            "filename":     safe_name,
            "backend":      self.backend,
        }

    def open(self, key: str) -> BinaryIO:
        from io import BytesIO
        obj = self._client.get_object(Bucket=self.bucket, Key=key)
        return BytesIO(obj["Body"].read())

    def delete(self, key: str) -> bool:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


_storage: Optional[StorageProvider] = None


def get_storage() -> StorageProvider:
    """Returns the configured storage provider singleton.

    Selection logic:
      * STORAGE_PROVIDER=local (default)  ->  LocalStorage
      * STORAGE_PROVIDER=s3               ->  S3Storage (requires AWS creds)
    """
    global _storage
    if _storage is not None:
        return _storage
    provider = (os.environ.get("STORAGE_PROVIDER") or "local").strip().lower()
    if provider == "s3":
        try:
            _storage = S3Storage()
            logger.info("[storage] using S3 backend (bucket=%s)", _storage.bucket)
        except Exception as exc:
            logger.warning("[storage] S3 init failed (%s) - falling back to LocalStorage", exc)
            _storage = LocalStorage()
    else:
        _storage = LocalStorage()
        logger.info("[storage] using LocalStorage backend at %s", _storage.root)
    return _storage


__all__ = ["StorageProvider", "LocalStorage", "S3Storage", "get_storage", "UPLOAD_ROOT"]
