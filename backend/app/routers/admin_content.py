"""Admin Content Center router — Phase D1.

Endpoints (all `require_master_admin`, prefix `/api/admin/content`):

    GET    /pages                  list pages (filter by status/kind/lang/q)
    POST   /pages                  create draft
    GET    /pages/{id}             get one
    PUT    /pages/{id}             update (creates version snapshot)
    DELETE /pages/{id}             delete (creates version snapshot)
    POST   /pages/{id}/transition  { status } — workflow transition
    GET    /pages/{id}/versions    list versions
    POST   /pages/{id}/restore     { version } — clone → draft
    GET    /block-types            introspect: list of supported block types

Every mutation that affects a currently-published page invalidates the
prerender cache so bots pick up the change on the next request.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_master_admin
from app.content.blocks import list_block_types
from app.content.service import ContentPageService, STATUSES

logger = logging.getLogger("bibi.admin_content")

router = APIRouter(prefix="/api/admin/content", tags=["admin-content"])


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _svc() -> ContentPageService:
    return ContentPageService(_db())


@router.get("/block-types", dependencies=[Depends(require_master_admin)])
async def get_block_types() -> Dict[str, Any]:
    return {"block_types": list_block_types(), "statuses": list(STATUSES)}


@router.get("/pages", dependencies=[Depends(require_master_admin)])
async def list_pages(
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    svc = _svc()
    await svc._ensure_indexes()
    items = await svc.list_pages(status=status, kind=kind, q=q, lang=lang, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/pages", dependencies=[Depends(require_master_admin)])
async def create_page(payload: Dict[str, Any] = Body(...),
                      actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    svc = _svc()
    await svc._ensure_indexes()
    try:
        page = await svc.create(payload, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "page": page}


@router.get("/pages/{page_id}", dependencies=[Depends(require_master_admin)])
async def get_page(page_id: str) -> Dict[str, Any]:
    page = await _svc().get_by_id(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="page not found")
    return {"page": page}


@router.put("/pages/{page_id}", dependencies=[Depends(require_master_admin)])
async def update_page(page_id: str,
                      payload: Dict[str, Any] = Body(...),
                      actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    svc = _svc()
    try:
        page = await svc.update(page_id, payload, actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="page not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "page": page}


@router.delete("/pages/{page_id}", dependencies=[Depends(require_master_admin)])
async def delete_page(page_id: str,
                      actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    ok = await _svc().delete(page_id, actor)
    if not ok:
        raise HTTPException(status_code=404, detail="page not found")
    return {"success": True}


@router.post("/pages/{page_id}/transition", dependencies=[Depends(require_master_admin)])
async def transition_page(page_id: str,
                          payload: Dict[str, Any] = Body(...),
                          actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    new_status = (payload or {}).get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")
    try:
        page = await _svc().transition(page_id, new_status, actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="page not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "page": page}


@router.get("/pages/{page_id}/versions", dependencies=[Depends(require_master_admin)])
async def list_versions(page_id: str, limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    svc = _svc()
    versions = await svc.list_versions(page_id, limit=limit)
    return {"items": versions, "count": len(versions)}


@router.post("/pages/{page_id}/restore", dependencies=[Depends(require_master_admin)])
async def restore_version(page_id: str,
                          payload: Dict[str, Any] = Body(...),
                          actor: Dict[str, Any] = Depends(require_master_admin)) -> Dict[str, Any]:
    version = (payload or {}).get("version")
    if version is None:
        raise HTTPException(status_code=400, detail="version is required")
    try:
        page = await _svc().restore_version(page_id, int(version), actor)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "page": page}
