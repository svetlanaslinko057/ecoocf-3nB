"""StorageProvider ABC — single interface used by file repository + PDF engine.

Deliberately minimal so any S3-compatible backend (MinIO, R2, AWS S3) or
a local-disk backend implements the same 5 methods. Higher layers never
touch filesystem paths or boto3 directly.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.\-]+")


def safe_name(name: str) -> str:
    name = (name or "file").strip()
    name = SAFE_NAME_RE.sub("_", name) or "file"
    return name[-120:]


def guess_mime(filename: str, fallback: Optional[str] = None) -> str:
    return fallback or mimetypes.guess_type(filename)[0] or "application/octet-stream"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class StoredObject:
    """Provider-agnostic descriptor of a single stored file."""
    storage_key: str  # unique key within the provider (e.g. relative path or S3 key)
    size: int
    sha256: str
    mime: str
    filename: str
    provider: str


class StorageProvider(ABC):
    """Pluggable storage backend."""

    name: str = "abstract"

    @abstractmethod
    def put_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        mime: Optional[str] = None,
        prefix: str = "uploads",
    ) -> StoredObject:
        """Persist ``data`` and return a descriptor.

        ``prefix`` is a logical bucket-folder (``uploads``, ``generated``,
        ``photos`` etc) — providers map it to a subdir / S3 key prefix.
        """

    @abstractmethod
    def get_bytes(self, storage_key: str) -> bytes:
        """Return the binary content of ``storage_key`` or raise FileNotFoundError."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Best-effort delete — must not raise if the object is already gone."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:  # pragma: no cover — trivial in subclasses
        ...
