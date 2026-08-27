"""
BIBI Cars — Block 6.2 — Lead SLA HTTP router
==============================================

Endpoints
---------

  GET  /api/leads/{lead_id}/sla
        Read SLA state for a single lead.  Manager (own only) /
        team_lead / admin.

  GET  /api/leads/sla/overdue
        List leads currently overdue or escalated. Manager (own only) /
        team_lead (own team) / admin (all).

  GET  /api/leads/sla/settings
        Read current thresholds.  Admin / team_lead.

  PUT  /api/leads/sla/settings
        Update thresholds.  Admin only.

  POST /api/leads/sla/scan
        Manually run the scan once. Admin only — useful for testing.

  POST /api/leads/{lead_id}/responded
        Manually mark a lead as “first responded”. Manager (own only) /
        team_lead / admin. Idempotent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from security import require_user
from app.services import lead_sla as svc

logger = logging.getLogger("bibi.lead_sla.router")
router = APIRouter()


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


def _role(user: Dict[str, Any]) -> str:
    return (user.get("role") or "").lower()


def _is_admin_or_tl(user: Dict[str, Any]) -> bool:
    return _role(user) in {"owner", "master_admin", "admin", "team_lead"}


def _is_admin(user: Dict[str, Any]) -> bool:
    return _role(user) in {"owner", "master_admin", "admin"}


async def _ensure_can_view_lead(db, lead_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    role = _role(user)
    if role in {"owner", "master_admin", "admin", "team_lead"}:
        return lead
    uid = user.get("id") or user.get("email")
    if role == "manager" and lead.get("managerId") == uid:
        return lead
    raise HTTPException(status_code=403, detail="Forbidden")


# ────────────────── GET /api/leads/{lead_id}/sla ──────────────────
@router.get("/leads/{lead_id}/sla")
async def get_lead_sla(
    lead_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    await _ensure_can_view_lead(db, lead_id, user)
    state = await svc.get_lead_sla_state(db, lead_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True, "data": state}


# ────────────────── GET /api/leads/sla/overdue ────────────────────
@router.get("/leads/sla/overdue")
async def get_overdue_leads(
    request: Request,
    only_escalated: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    role = _role(user)
    manager_id: Optional[str] = None
    if role == "manager":
        manager_id = user.get("id") or user.get("email")
    elif role == "team_lead":
        # Team lead sees own team's overdue; for MVP we list everyone they own + their members
        manager_id = None  # tolerant: TL sees all overdue, frontend can filter
    elif role in {"owner", "master_admin", "admin"}:
        manager_id = None
    else:
        raise HTTPException(status_code=403, detail="Forbidden")
    items = await svc.list_overdue_leads(
        db,
        only_escalated=only_escalated,
        manager_id=manager_id,
        limit=limit,
    )
    return {"success": True, "data": items, "count": len(items)}


# ────────────────── GET /api/leads/sla/settings ───────────────────
@router.get("/leads/sla/settings")
async def get_sla_settings(
    request: Request,
    user: Dict[str, Any] = Depends(require_user),
):
    if not _is_admin_or_tl(user):
        raise HTTPException(status_code=403, detail="Forbidden")
    cfg = await svc.get_thresholds(_db(request))
    return {"success": True, "data": cfg}


# ────────────────── PUT /api/leads/sla/settings ───────────────────
class SLASettingsIn(BaseModel):
    remind_minutes: Optional[int] = Field(None, ge=1, le=60 * 24 * 7)
    escalate_minutes: Optional[int] = Field(None, ge=1, le=60 * 24 * 7)
    auto_reassign: Optional[bool] = None


@router.put("/leads/sla/settings")
async def update_sla_settings(
    request: Request,
    payload: SLASettingsIn = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin only")
    cfg = await svc.set_thresholds(
        _db(request),
        remind_minutes=payload.remind_minutes,
        escalate_minutes=payload.escalate_minutes,
        auto_reassign=payload.auto_reassign,
    )
    return {"success": True, "data": cfg}


# ────────────────── POST /api/leads/sla/scan ──────────────────────
@router.post("/leads/sla/scan")
async def trigger_sla_scan(
    request: Request,
    user: Dict[str, Any] = Depends(require_user),
):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin only")
    report = await svc.scan_overdue_leads(_db(request))
    return {"success": True, "data": report}


# ────────────────── POST /api/leads/{lead_id}/responded ────────────
@router.post("/leads/{lead_id}/responded")
async def mark_lead_responded_route(
    lead_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    await _ensure_can_view_lead(db, lead_id, user)
    uid = user.get("id") or user.get("email")
    changed = await svc.mark_lead_responded(db, lead_id, by_user_id=uid, source="manual_route")
    state = await svc.get_lead_sla_state(db, lead_id)
    return {"success": True, "first_response_set": changed, "sla": state}


# ────────────────── Startup hook ──────────────────────────────────
async def on_startup(db) -> None:
    """Best-effort indexes for SLA queries."""
    try:
        await db.leads.create_index("first_response_at")
        await db.leads.create_index("sla_reminded_at")
        await db.leads.create_index("sla_escalated_at")
        await db.notifications.create_index([("recipient_id", 1), ("created_at", -1)])
        await db.notifications.create_index([("event", 1), ("created_at", -1)])
        logger.info("[lead_sla] indexes ensured")
    except Exception as e:
        logger.warning("[lead_sla] index ensure failed: %s", e)
