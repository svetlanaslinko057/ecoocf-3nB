"""Unified Admin Platform — HTTP surface (Slice 1).

All endpoints require an admin/manager JWT (`require_admin`) and live under
`/api/admin/unified`. Read-only aggregation — no mutations to domain data.

    GET /search       ?q=&types=csv&per_type=   → global cross-domain search
    GET /dashboard                              → unified KPI + recent activity
    GET /relations    ?type=&q=&limit=          → picker source for one entity
    GET /relation-types                         → list of pickable entity types
"""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from security import require_admin
from app.unified.service import UnifiedService
from app.unified.universal import UniversalService, DraftAdapter

logger = logging.getLogger("bibi.unified.router")

router = APIRouter(
    prefix="/api/admin/unified",
    tags=["unified-admin"],
    dependencies=[Depends(require_admin)],
)


def _svc() -> UnifiedService:
    from app.core.db_runtime import get_db
    return UnifiedService(get_db())


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _usvc() -> UniversalService:
    return UniversalService(_db())


def _bucket() -> AsyncIOMotorGridFSBucket:
    # Reuse the EXISTING content_media GridFS bucket — no new storage system.
    return AsyncIOMotorGridFSBucket(_db(), bucket_name="content_media")


_MAX_ATTACH_BYTES = 20 * 1024 * 1024  # 20 MB


@router.get("/search")
async def unified_search(
    q: str = Query("", min_length=0),
    types: Optional[str] = Query(None, description="comma-separated entity types"),
    per_type: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    type_list = [t.strip() for t in types.split(",")] if types else None
    return await _svc().global_search(q=q, types=type_list, per_type=per_type)


@router.get("/dashboard")
async def unified_dashboard() -> Dict[str, Any]:
    return await _svc().dashboard()


@router.get("/relations")
async def unified_relations(
    type: str = Query(..., description="entity type key"),
    q: str = Query(""),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    return await _svc().relations(type=type, q=q, limit=limit)


@router.get("/relation-types")
async def unified_relation_types() -> Dict[str, Any]:
    return {"types": _svc().relation_types()}


# ═══════════════════════════════════════════════════════════════════════════
# Slice 2 — Universal subsystems (Activity / Comments / Attachments / Audit /
# Draft-adapter / Timeline / Notifications). Additive; new u_* collections only.
# ═══════════════════════════════════════════════════════════════════════════

# ── Activity Feed ───────────────────────────────────────────────────────────
@router.get("/activity")
async def activity_feed(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(40, ge=1, le=100),
):
    svc = _usvc(); await svc.ensure_indexes()
    return await svc.activity_feed(entity_type=entity_type, entity_id=entity_id, limit=limit)


# ── Comments ────────────────────────────────────────────────────────────────
@router.get("/comments")
async def list_comments(entity_type: str = Query(...), entity_id: str = Query(...),
                        limit: int = Query(100, ge=1, le=300)):
    svc = _usvc(); await svc.ensure_indexes()
    items = await svc.list_comments(entity_type, entity_id, limit)
    return {"items": items, "count": len(items)}


@router.post("/comments")
async def create_comment(payload: Dict[str, Any] = Body(...),
                         actor: Dict[str, Any] = Depends(require_admin)):
    svc = _usvc(); await svc.ensure_indexes()
    et, eid, text = payload.get("entity_type"), payload.get("entity_id"), payload.get("text")
    if not et or not eid:
        raise HTTPException(status_code=400, detail="entity_type and entity_id required")
    try:
        c = await svc.create_comment(et, eid, text, _actor_of(actor), payload.get("attachments"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "comment": c}


@router.patch("/comments/{comment_id}")
async def update_comment(comment_id: str, payload: Dict[str, Any] = Body(...),
                         actor: Dict[str, Any] = Depends(require_admin)):
    svc = _usvc()
    try:
        c = await svc.update_comment(comment_id, payload.get("text"), _actor_of(actor))
    except LookupError:
        raise HTTPException(status_code=404, detail="comment not found")
    return {"success": True, "comment": c}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, actor: Dict[str, Any] = Depends(require_admin)):
    svc = _usvc()
    try:
        await svc.delete_comment(comment_id, _actor_of(actor))
    except LookupError:
        raise HTTPException(status_code=404, detail="comment not found")
    return {"success": True}


# ── Attachments (reuse content_media GridFS; no new storage) ────────────────
@router.get("/attachments")
async def list_attachments(entity_type: str = Query(...), entity_id: str = Query(...),
                           limit: int = Query(100, ge=1, le=300)):
    svc = _usvc(); await svc.ensure_indexes()
    items = await svc.list_attachments(entity_type, entity_id, limit)
    return {"items": items, "count": len(items)}


@router.post("/attachments/upload")
async def upload_attachment(entity_type: str = Query(...), entity_id: str = Query(...),
                            file: UploadFile = File(...),
                            actor: Dict[str, Any] = Depends(require_admin)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_ATTACH_BYTES:
        raise HTTPException(status_code=413, detail="file too large (>20 MB)")
    bucket = _bucket()
    file_id = await bucket.upload_from_stream(
        file.filename or "attachment", io.BytesIO(data),
        metadata={"mime": file.content_type or "application/octet-stream", "size": len(data)},
    )
    svc = _usvc(); await svc.ensure_indexes()
    att = await svc.register_attachment(
        entity_type, entity_id, filename=file.filename or "attachment",
        url=f"/api/media/{file_id}", mime=(file.content_type or "application/octet-stream"),
        size=len(data), actor=_actor_of(actor), file_id=str(file_id),
    )
    return {"success": True, "attachment": att}


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str, actor: Dict[str, Any] = Depends(require_admin)):
    svc = _usvc()
    try:
        raw = await svc.delete_attachment(attachment_id, _actor_of(actor))
    except LookupError:
        raise HTTPException(status_code=404, detail="attachment not found")
    fid = raw.get("file_id")
    if fid:
        try:
            from bson import ObjectId
            await _bucket().delete(ObjectId(fid))
        except Exception:
            pass
    return {"success": True}


# ── Audit ───────────────────────────────────────────────────────────────────
@router.get("/audit")
async def list_audit(entity_type: str = Query(...), entity_id: str = Query(...),
                     limit: int = Query(100, ge=1, le=300)):
    svc = _usvc(); await svc.ensure_indexes()
    items = await svc.list_audit(entity_type, entity_id, limit)
    return {"items": items, "count": len(items)}


# ── Draft adapter / lifecycle ────────────────────────────────────────────────
@router.get("/lifecycle-map")
async def lifecycle_map():
    return {"lifecycles": DraftAdapter.lifecycle_map()}


@router.get("/lifecycle")
async def resolve_lifecycle(entity_type: str = Query(...), entity_id: str = Query(...)):
    return await _usvc().resolve_lifecycle(entity_type, entity_id)


# ── Universal Timeline ───────────────────────────────────────────────────────
@router.get("/timeline")
async def timeline(entity_type: str = Query(...), entity_id: str = Query(...),
                   limit: int = Query(100, ge=1, le=300)):
    svc = _usvc(); await svc.ensure_indexes()
    return await svc.timeline(entity_type, entity_id, limit)


# ── Header Notifications (aggregated) ────────────────────────────────────────
@router.get("/notifications")
async def notifications(actor: Dict[str, Any] = Depends(require_admin)):
    svc = _usvc(); await svc.ensure_indexes()
    return await svc.notifications(actor)


@router.post("/notifications/seen")
async def notifications_seen(payload: Dict[str, Any] = Body(default={}),
                             actor: Dict[str, Any] = Depends(require_admin)):
    svc = _usvc()
    return await svc.mark_notifications_seen(actor, (payload or {}).get("signature", ""))


def _actor_of(user: Dict[str, Any]) -> Dict[str, Any]:
    from app.unified.universal import _actor
    return _actor(user)
