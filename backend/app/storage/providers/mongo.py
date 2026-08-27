"""MongoStorageProvider — MongoDB-backed StorageProvider.

Makes the File Manager (``app/storage``) deployment-safe: uploaded bytes are
stored in MongoDB instead of the pod's local disk, so they persist across pod
restarts and are reachable from every replica. Read/write both go through this
provider, so the existing ``/api/storage/files/*`` URLs keep working unchanged.

A synchronous pymongo handle is used because the StorageProvider interface is
synchronous.
"""
from __future__ import annotations

import base64
import os
import uuid
from typing import Optional

from pymongo import MongoClient

from .base import StorageProvider, StoredObject, guess_mime, safe_name, sha256_hex

MAX_FILE_SIZE_MB = int(os.environ.get("FILE_MAX_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
_COLLECTION = "fs_objects"


class MongoStorageProvider(StorageProvider):
    name = "mongo"

    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None

    def _coll(self):
        if self._client is None:
            self._client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbname = os.environ.get("DB_NAME", "test_database")
        return self._client[dbname][_COLLECTION]

    def put_bytes(self, data: bytes, *, filename: str, mime: Optional[str] = None,
                  prefix: str = "uploads") -> StoredObject:
        if not data:
            raise ValueError("Файл порожній")
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл перевищує максимум {MAX_FILE_SIZE_MB} МБ")
        mime = guess_mime(filename, mime)
        prefix = (prefix or "uploads").strip("/") or "uploads"
        sname = safe_name(filename)
        key = f"{prefix}/{uuid.uuid4().hex}__{sname}"
        self._coll().insert_one({
            "storage_key": key,
            "data": base64.b64encode(data).decode("ascii"),
            "size": len(data),
            "mime": mime,
            "filename": filename,
        })
        return StoredObject(
            storage_key=key, size=len(data), sha256=sha256_hex(data),
            mime=mime, filename=filename, provider=self.name,
        )

    def get_bytes(self, storage_key: str) -> bytes:
        doc = self._coll().find_one({"storage_key": storage_key}, {"_id": 0, "data": 1})
        if not doc:
            raise FileNotFoundError(storage_key)
        return base64.b64decode(doc.get("data") or "")

    def delete(self, storage_key: str) -> None:
        try:
            self._coll().delete_one({"storage_key": storage_key})
        except Exception:
            pass

    def exists(self, storage_key: str) -> bool:
        return self._coll().count_documents({"storage_key": storage_key}, limit=1) > 0
