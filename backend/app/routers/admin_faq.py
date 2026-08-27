"""Admin FAQ Engine router — Phase D1.

Endpoints (`/api/admin/faq`):

    GET    /            list (filter group/page_path/lang/q)
    POST   /            create
    PATCH  /{id}        update
    DELETE /{id}        delete
    POST   /reorder     bulk reorder [{id, order}]

Every mutation invalidates the prerender cache.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_master_admin
from app.content.service import FAQService

router = APIRouter(prefix="/api/admin/faq", tags=["admin-faq"])


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _svc() -> FAQService:
    return FAQService(_db())


@router.get("", dependencies=[Depends(require_master_admin)])
async def list_faq(group: Optional[str] = Query(None),
                   page_path: Optional[str] = Query(None),
                   lang: Optional[str] = Query(None),
                   q: Optional[str] = Query(None),
                   limit: int = Query(200, ge=1, le=500)) -> Dict[str, Any]:
    svc = _svc()
    await svc._ensure_indexes()
    items = await svc.list(group=group, page_path=page_path, lang=lang, q=q, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("", dependencies=[Depends(require_master_admin)])
async def create_faq(payload: Dict[str, Any] = Body(...),
                     actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    svc = _svc()
    await svc._ensure_indexes()
    try:
        faq = await svc.create(payload, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "faq": faq}


@router.patch("/{faq_id}", dependencies=[Depends(require_master_admin)])
async def update_faq(faq_id: str,
                     payload: Dict[str, Any] = Body(...),
                     actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    faq = await _svc().update(faq_id, payload, actor)
    if not faq:
        raise HTTPException(status_code=404, detail="faq not found")
    return {"success": True, "faq": faq}


@router.delete("/{faq_id}", dependencies=[Depends(require_master_admin)])
async def delete_faq(faq_id: str) -> Dict[str, Any]:
    ok = await _svc().delete(faq_id)
    if not ok:
        raise HTTPException(status_code=404, detail="faq not found")
    return {"success": True}


@router.post("/reorder", dependencies=[Depends(require_master_admin)])
async def reorder_faq(payload: Dict[str, Any] = Body(...),
                      actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    items = (payload or {}).get("items") or []
    updated = 0
    svc = _svc()
    for it in items:
        if not isinstance(it, dict):
            continue
        fid = it.get("id")
        if not fid:
            continue
        r = await svc.update(fid, {"order": int(it.get("order") or 100)}, actor)
        if r:
            updated += 1
    return {"success": True, "updated": updated}
