"""LocalStorageProvider — disk-backed implementation of StorageProvider.

This is the only provider wired by default. Files live under
``STORAGE_ROOT`` (env, default ``/app/backend/storage``) and the
``storage_key`` returned to upper layers is the *relative* path so a
future migration to MinIO/R2 is a key-by-key copy.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from .base import StorageProvider, StoredObject, guess_mime, safe_name, sha256_hex

MAX_FILE_SIZE_MB = int(os.environ.get("FILE_MAX_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class LocalStorageProvider(StorageProvider):
    name = "local"

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = Path(root or os.environ.get("STORAGE_ROOT") or "/app/backend/storage")
        self.root.mkdir(parents=True, exist_ok=True)

    # ----- helpers -----------------------------------------------------
    def _resolve(self, storage_key: str) -> Path:
        """Map a relative storage_key onto the actual filesystem path.

        Accepts both relative keys (``uploads/abc__name.pdf``) and legacy
        absolute paths produced by the old LocalStorage class (so the
        backfill migration does not break inline-view URLs while it runs).
        """
        p = Path(storage_key)
        if p.is_absolute():
            return p
        return self.root / storage_key

    # ----- API ---------------------------------------------------------
    def put_bytes(self, data: bytes, *, filename: str, mime: Optional[str] = None, prefix: str = "uploads") -> StoredObject:
        if not data:
            raise ValueError("Файл порожній")
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл перевищує максимум {MAX_FILE_SIZE_MB} МБ")
        mime = guess_mime(filename, mime)
        prefix = (prefix or "uploads").strip("/") or "uploads"
        target_dir = self.root / prefix
        target_dir.mkdir(parents=True, exist_ok=True)
        sname = safe_name(filename)
        rel = f"{prefix}/{uuid.uuid4().hex}__{sname}"
        path = self.root / rel
        with path.open("wb") as f:
            f.write(data)
        return StoredObject(
            storage_key=rel,
            size=len(data),
            sha256=sha256_hex(data),
            mime=mime,
            filename=filename,
            provider=self.name,
        )

    def get_bytes(self, storage_key: str) -> bytes:
        p = self._resolve(storage_key)
        if not p.exists():
            raise FileNotFoundError(storage_key)
        return p.read_bytes()

    def delete(self, storage_key: str) -> None:
        p = self._resolve(storage_key)
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).exists()
