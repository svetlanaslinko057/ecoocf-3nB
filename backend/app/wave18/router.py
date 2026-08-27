"""
BIBI Cars — Wave 18 — HTTP surface
=====================================

Mounted at `/api/notifications/*`.
"""
from __future__ import annotations
import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave18 import queries as q
from app.wave18.dispatcher import get_preferences, patch_preferences
from app.wave18.escalation import scan_overdue
from app.wave18.models import DISPATCH_RULES, SLA_THRESHOLDS, PreferencesPatch

logger = logging.getLogger("bibi.wave18")
router = APIRouter(prefix="/api/notifications", tags=["Wave18:NotificationCenter"])

from security import require_user  # type: ignore


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


def _uid(user: Dict[str, Any]) -> str:
    return user.get("id") or user.get("sub") or user.get("managerId") or ""


# ────────────────────────────────────────────────────────────────────
# STATIC
# ────────────────────────────────────────────────────────────────────
@router.get("/rules")
async def rules_endpoint(_: Dict[str, Any] = Depends(require_user)):
    flat = []
    for ev, rules in DISPATCH_RULES.items():
        for r in rules:
            flat.append({"event": ev, "recipient": r["recipient"], "channels": r["channels"]})
    return {"success": True, "events": list(DISPATCH_RULES.keys()),
            "rules": flat, "sla_thresholds_hours": SLA_THRESHOLDS}


# ────────────────────────────────────────────────────────────────────
# INBOX
# ────────────────────────────────────────────────────────────────────
@router.get("/inbox")
async def inbox_endpoint(
    request: Request,
    only_unread:      bool = Query(False),
    include_dismissed: bool = Query(False),
    limit:            int  = Query(100, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    data = await q.inbox(db, _uid(current_user),
                          only_unread=only_unread,
                          include_dismissed=include_dismissed,
                          limit=limit)
    return {"success": True, "data": data}


@router.get("/unread-count")
async def unread_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    count = await q.unread_count(_db(request), _uid(current_user))
    return {"success": True, "unread": count}


@router.post("/{notif_id}/read")
async def read_endpoint(
    notif_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    n = await q.mark_read(_db(request), _uid(current_user), notif_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    return {"success": True, "data": n}


@router.post("/read-all")
async def read_all_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    n = await q.mark_all_read(_db(request), _uid(current_user))
    return {"success": True, "marked": n}


@router.post("/{notif_id}/dismiss")
async def dismiss_endpoint(
    notif_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    n = await q.dismiss(_db(request), _uid(current_user), notif_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    return {"success": True, "data": n}


# ────────────────────────────────────────────────────────────────────
# PREFERENCES
# ────────────────────────────────────────────────────────────────────
@router.get("/preferences")
async def prefs_get(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    p = await get_preferences(_db(request), _uid(current_user))
    return {"success": True, "data": p}


@router.patch("/preferences")
async def prefs_patch(
    payload: PreferencesPatch, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    p = await patch_preferences(_db(request), _uid(current_user),
                                 payload.model_dump(exclude_none=True))
    return {"success": True, "data": p}


# ────────────────────────────────────────────────────────────────────
# ANALYTICS  +  ESCALATION (Wave 18.1)
# ────────────────────────────────────────────────────────────────────
@router.get("/analytics")
async def analytics_endpoint(
    request: Request, days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(require_user),
):
    data = await q.analytics(_db(request), days=days)
    return {"success": True, "data": data}


@router.post("/escalation/scan")
async def escalation_scan_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    report = await scan_overdue(_db(request))
    return {"success": True, "data": report}


__all__ = ["router"]
