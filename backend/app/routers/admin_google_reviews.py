"""
admin_google_reviews — HTTP surface for Google Reviews integration.

Routes:
   ADMIN (require role admin / master_admin):
     GET    /api/admin/google-reviews/config
     PUT    /api/admin/google-reviews/config
     POST   /api/admin/google-reviews/sync
     GET    /api/admin/google-reviews
     POST   /api/admin/google-reviews/manual
     PATCH  /api/admin/google-reviews/{review_id}
     DELETE /api/admin/google-reviews/{review_id}

   PUBLIC:
     GET    /api/public/google-reviews

The router delegates all business logic to
`app.services.google_reviews_service`. This file only does:
   • auth gating (admin endpoints)
   • request body validation (pydantic-light: plain dict checks)
   • mapping service exceptions → HTTP status codes
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from app.core.db_runtime import get_db
from app.services import google_reviews_service as svc
from security import require_user

logger = logging.getLogger("bibi.admin_google_reviews")

router = APIRouter(tags=["google-reviews"])


def _db():
    return get_db()


def _admin_only(user: Dict[str, Any]) -> None:
    role = ((user or {}).get("role") or "").lower()
    if role not in ("admin", "master_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Admin: config ───────────────────────────────────────────────────────
@router.get("/api/admin/google-reviews/config")
async def admin_get_config(user: Dict[str, Any] = Depends(require_user)):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    return await svc.get_config_for_admin(db)


@router.put("/api/admin/google-reviews/config")
async def admin_update_config(
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    return await svc.update_config(db, payload or {})


# ── Admin: sync ─────────────────────────────────────────────────────────
@router.post("/api/admin/google-reviews/sync")
async def admin_sync(user: Dict[str, Any] = Depends(require_user)):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    try:
        result = await svc.sync_from_google(db)
        return {"success": True, **result}
    except RuntimeError as e:
        # Controlled failure mode — config missing or upstream API error.
        msg = str(e)
        if msg.startswith("Google Places API key"):
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=502, detail=msg)
    except Exception as e:
        logger.exception("Google Reviews sync failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


# ── Admin: list / mutate cached reviews ────────────────────────────────
@router.get("/api/admin/google-reviews")
async def admin_list_reviews(user: Dict[str, Any] = Depends(require_user)):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    items = await svc.list_reviews(db, include_hidden=True)
    return {"items": items, "count": len(items)}


@router.post("/api/admin/google-reviews/manual")
async def admin_add_manual(
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    return await svc.add_manual_review(db, payload or {})


@router.patch("/api/admin/google-reviews/{review_id}")
async def admin_patch_review(
    review_id: str = Path(...),
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    try:
        return await svc.set_review_state(
            db,
            review_id,
            hidden=payload.get("hidden"),
            pinned=payload.get("pinned"),
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/admin/google-reviews/{review_id}")
async def admin_delete_review(
    review_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_user),
):
    _admin_only(user)
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    ok = await svc.delete_review(db, review_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"success": True}


# ── Public: feed ────────────────────────────────────────────────────────
@router.get("/api/public/google-reviews")
async def public_feed():
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    return await svc.public_feed(db)
