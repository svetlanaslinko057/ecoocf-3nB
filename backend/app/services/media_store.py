"""Deployment-safe media store (MongoDB-backed).

Replaces pod-local ``static/`` disk writes for user uploads (avatars, blog /
review / hero / partner / certificate images, certificate & signed-contract
PDFs, payment proofs). Bytes live in MongoDB so they survive pod restarts and
are reachable from every replica in a deployed environment.

Served publicly (read-only) via ``GET /api/media/{id}``.

A synchronous pymongo handle is used so the helper can be called from both
sync and async code paths without awaiting.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pymongo import MongoClient

logger = logging.getLogger("eco.media_store")

_client: Optional[MongoClient] = None
_COLLECTION = "media_uploads"


def _coll():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    dbname = os.environ.get("DB_NAME", "test_database")
    return _client[dbname][_COLLECTION]


def save_media(category: str, filename: str, content: bytes,
               content_type: Optional[str] = None) -> dict:
    """Persist ``content`` in MongoDB and return ``{id, url, size, content_type}``.

    ``url`` is a public path (``/api/media/{id}``) suitable for storing on the
    referencing document and rendering in the browser.
    """
    if not content:
        raise ValueError("Файл порожній")
    cat = (category or "misc").strip().replace("/", "_") or "misc"
    mid = f"{cat}_{uuid.uuid4().hex}"
    ct = content_type or mimetypes.guess_type(filename or "")[0] or "application/octet-stream"
    _coll().insert_one({
        "id": mid,
        "category": cat,
        "filename": filename or mid,
        "content_type": ct,
        "size": len(content),
        "data": base64.b64encode(content).decode("ascii"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"id": mid, "url": f"/api/uploads/{mid}", "size": len(content), "content_type": ct}


media_router = APIRouter(prefix="/api/uploads", tags=["media"])


@media_router.get("/{media_id}")
async def get_media(media_id: str):
    doc = _coll().find_one({"id": media_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Файл не знайдено")
    data = base64.b64decode(doc.get("data") or "")
    return Response(
        content=data,
        media_type=doc.get("content_type", "application/octet-stream"),
        headers={
            "Cache-Control": "public, max-age=31536000",
            "Content-Disposition": f"inline; filename=\"{doc.get('filename', 'file')}\"",
        },
    )
