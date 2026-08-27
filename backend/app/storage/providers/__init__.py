"""Storage providers — pluggable backends behind a single interface.

Selected via ``STORAGE_PROVIDER`` env var (``local`` | ``minio`` | ``r2``).
The S3-compatible backends (MinIO / R2) are wired by class but require
the corresponding env credentials. Until those are set we keep using
the local-disk implementation; switching is a 10-minute env-only change.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from .base import StorageProvider, StoredObject
from .local import LocalStorageProvider
from .mongo import MongoStorageProvider
from .s3 import MinioProvider, R2Provider
from .emergent import EmergentProvider

logger = logging.getLogger("bibi.storage.providers")

_singleton: Optional[StorageProvider] = None


def get_storage_provider() -> StorageProvider:
    global _singleton
    if _singleton is not None:
        return _singleton
    kind = (os.environ.get("STORAGE_PROVIDER") or "emergent").strip().lower()
    try:
        if kind == "minio":
            _singleton = MinioProvider.from_env()
        elif kind in ("r2", "cloudflare", "cloudflare_r2"):
            _singleton = R2Provider.from_env()
        elif kind == "local":
            _singleton = LocalStorageProvider()
        elif kind == "mongo":
            _singleton = MongoStorageProvider()
        else:
            # Deployment-safe default: Emergent managed object storage
            # (durable, off-pod). Falls back to Mongo below on any init error.
            _singleton = EmergentProvider()
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        logger.warning("[storage] provider '%s' init failed (%s); falling back to mongo", kind, e)
        _singleton = MongoStorageProvider()
    logger.info("[storage] active provider: %s", _singleton.name)
    return _singleton


__all__ = ["StorageProvider", "StoredObject", "LocalStorageProvider", "MongoStorageProvider", "MinioProvider", "R2Provider", "EmergentProvider", "get_storage_provider"]
