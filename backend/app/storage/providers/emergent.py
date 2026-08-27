"""EmergentProvider — durable object storage via Emergent's managed store.

Uploaded files live in Emergent object storage (NOT on the app pod), so they
survive redeploys and are reachable from deployed environments. Implements the
same 5-method StorageProvider interface as the local / mongo / s3 backends.

Wire via ``STORAGE_PROVIDER=emergent`` (the deployment-safe default). Requires:
  * ``EMERGENT_LLM_KEY``          — auth for the storage proxy
  * ``INTEGRATION_PROXY_URL``     — set by the platform (falls back to prod host)

The remote API has no delete/rename/HEAD verbs, so ``delete`` is a best-effort
no-op (soft-delete is handled in Mongo by the FileRepository/lifecycle layer)
and ``exists`` performs a lightweight GET.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import Optional

import requests

from .base import StorageProvider, StoredObject, guess_mime, safe_name, sha256_hex

logger = logging.getLogger("bibi.storage.emergent")

MAX_FILE_SIZE_MB = int(os.environ.get("FILE_MAX_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# App-name prefix isolates our objects inside the account bucket.
APP_PREFIX = (os.environ.get("STORAGE_APP_PREFIX") or "econova").strip("/") or "econova"


def _storage_url() -> str:
    base = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
    return base.rstrip("/") + "/objstore/api/v1/storage"


class EmergentProvider(StorageProvider):
    name = "emergent"

    def __init__(self) -> None:
        self._key: Optional[str] = None
        self._lock = threading.Lock()
        self._emergent_key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
        if not self._emergent_key:
            # Surface loudly so the caller can fall back to a safe provider.
            raise RuntimeError("EMERGENT_LLM_KEY not set — cannot init Emergent object storage")

    # ----- session key ------------------------------------------------
    def _init_storage(self, force: bool = False) -> str:
        with self._lock:
            if self._key and not force:
                return self._key
            resp = requests.post(
                f"{_storage_url()}/init",
                json={"emergent_key": self._emergent_key},
                timeout=30,
            )
            resp.raise_for_status()
            self._key = resp.json()["storage_key"]
            logger.info("[storage] emergent storage_key initialised")
            return self._key

    # ----- API --------------------------------------------------------
    def put_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        mime: Optional[str] = None,
        prefix: str = "uploads",
    ) -> StoredObject:
        if not data:
            raise ValueError("Файл порожній")
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл перевищує максимум {MAX_FILE_SIZE_MB} МБ")
        mime = guess_mime(filename, mime)
        prefix = (prefix or "uploads").strip("/") or "uploads"
        sname = safe_name(filename)
        path = f"{APP_PREFIX}/{prefix}/{uuid.uuid4().hex}__{sname}"

        key = self._init_storage()
        url = f"{_storage_url()}/objects/{path}"
        resp = requests.put(
            url,
            headers={"X-Storage-Key": key, "Content-Type": mime},
            data=data,
            timeout=120,
        )
        if resp.status_code == 404:
            # Stale/inactive storage_key → mint a fresh one and retry once.
            key = self._init_storage(force=True)
            resp = requests.put(
                url,
                headers={"X-Storage-Key": key, "Content-Type": mime},
                data=data,
                timeout=120,
            )
        resp.raise_for_status()
        stored_path = (resp.json() or {}).get("path") or path
        return StoredObject(
            storage_key=stored_path,
            size=len(data),
            sha256=sha256_hex(data),
            mime=mime,
            filename=filename,
            provider=self.name,
        )

    def get_bytes(self, storage_key: str) -> bytes:
        key = self._init_storage()
        url = f"{_storage_url()}/objects/{storage_key}"
        resp = requests.get(url, headers={"X-Storage-Key": key}, timeout=60)
        if resp.status_code == 404:
            # Could be a dead session key — refresh once before giving up.
            key = self._init_storage(force=True)
            resp = requests.get(url, headers={"X-Storage-Key": key}, timeout=60)
            if resp.status_code == 404:
                raise FileNotFoundError(storage_key)
        resp.raise_for_status()
        return resp.content

    def delete(self, storage_key: str) -> None:
        # Remote store exposes no delete verb — soft-delete is handled in Mongo.
        return None

    def exists(self, storage_key: str) -> bool:
        try:
            self.get_bytes(storage_key)
            return True
        except Exception:
            return False
