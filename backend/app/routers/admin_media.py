"""Admin Media Library router — Phase D1.

Uploads land in GridFS (`content_media` bucket) so we don't leak disk state
across deploys. Metadata (alt/caption/tags/focus point) lives in
`media_assets` collection. Public URL is `/api/media/{asset_id}` (proxy).
"""
from __future__ import annotations

import logging
import io
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from security import require_master_admin
from app.content.service import MediaLibraryService

logger = logging.getLogger("bibi.admin_media")

admin_router = APIRouter(prefix="/api/admin/media", tags=["admin-media"])
public_router = APIRouter(prefix="/api/media", tags=["public-media"])

_ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB — enough for OG banners / product shots


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _svc() -> MediaLibraryService:
    return MediaLibraryService(_db())


def _bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(_db(), bucket_name="content_media")


@admin_router.get("", dependencies=[Depends(require_master_admin)])
async def list_media(q: Optional[str] = Query(None),
                     tag: Optional[str] = Query(None),
                     limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    svc = _svc()
    await svc._ensure_indexes()
    items = await svc.list(q=q, tag=tag, limit=limit)
    return {"items": items, "count": len(items)}


@admin_router.post("/upload", dependencies=[Depends(require_master_admin)])
async def upload_media(file: UploadFile = File(...),
                        actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    mime = (file.content_type or "application/octet-stream").lower()
    if not any(mime.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=415, detail=f"unsupported media type: {mime}")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large (>{_MAX_UPLOAD_BYTES // (1024*1024)} MB)")

    # Probe image dimensions best-effort (Pillow already in requirements)
    width, height = None, None
    if mime.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
        except Exception:
            pass

    bucket = _bucket()
    file_id = await bucket.upload_from_stream(
        file.filename or "asset",
        io.BytesIO(data),
        metadata={"mime": mime, "size": len(data)},
    )
    asset = await _svc().register(
        filename=file.filename or "asset",
        url=f"/api/media/{file_id}",
        mime=mime,
        size=len(data),
        width=width,
        height=height,
        actor=actor,
    )
    # store the raw GridFS id so we can delete later
    await _svc().col.update_one({"id": asset["id"]}, {"$set": {"gridfs_id": str(file_id)}})
    asset["gridfs_id"] = str(file_id)
    return {"success": True, "asset": asset}


@admin_router.patch("/{asset_id}", dependencies=[Depends(require_master_admin)])
async def update_media(asset_id: str,
                       payload: Dict[str, Any] = Body(...),
                       actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    asset = await _svc().update(asset_id, payload, actor)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return {"success": True, "asset": asset}


@admin_router.delete("/{asset_id}", dependencies=[Depends(require_master_admin)])
async def delete_media(asset_id: str) -> Dict[str, Any]:
    asset = await _svc().get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    # remove the GridFS blob first
    fid_raw = asset.get("gridfs_id")
    if fid_raw:
        try:
            from bson import ObjectId
            await _bucket().delete(ObjectId(fid_raw))
        except Exception as e:  # pragma: no cover
            logger.debug("gridfs delete failed: %s", e)
    await _svc().delete(asset_id)
    return {"success": True}


# --- Public: stream raw bytes from GridFS (used by <img src>) ---

@public_router.get("/{file_id}")
async def stream_media(file_id: str):
    try:
        from bson import ObjectId
        fid = ObjectId(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")
    bucket = _bucket()
    try:
        stream = await bucket.open_download_stream(fid)
    except Exception:
        raise HTTPException(status_code=404, detail="not found")
    md = getattr(stream, "metadata", {}) or {}
    mime = md.get("mime") or "application/octet-stream"

    async def _iter():
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk

    headers = {"Cache-Control": "public, max-age=31536000, immutable"}
    return StreamingResponse(_iter(), media_type=mime, headers=headers)
