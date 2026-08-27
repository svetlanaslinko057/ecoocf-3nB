"""
Wave 6 — FastAPI router (mounted at /api/admin/deals/* and
/api/admin/settings/legal-policy).

Endpoints:
  GET  /api/admin/deals/{deal_id}                 → deal + customer + counts + health
  GET  /api/admin/deals/{deal_id}/timeline        → list timeline events (newest first)
  GET  /api/admin/deals/{deal_id}/health          → computed health badge
  POST /api/admin/deals/{deal_id}/notes           → write a note_added timeline entry
  GET  /api/admin/pipeline/stages                 → canonical 10-stage catalog + mapping
  GET  /api/admin/settings/legal-policy           → small admin config (5 fields)
  PUT  /api/admin/settings/legal-policy           → replace admin config (admin-only)

Access model (matches the user's spec):
  - admin / owner / master_admin → everything
  - team_lead                    → own deals + deals where assignee is on their team
  - manager                      → only deals where managerId == self
  - anyone else                  → 403
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from security import require_admin, require_manager_or_admin

from .pipeline import (
    PIPELINE_STAGES,
    PIPELINE_STAGE_LABELS,
    LEGACY_TO_PIPELINE,
    derive_pipeline_stage,
)
from .timeline import (
    write_event,
    list_events,
    ensure_indexes as ensure_timeline_indexes,
    KEY_EVENT_TYPES,
)
from .health import compute_health
from .legal_policy import get_policy, set_policy, LegalPolicyIn, DEFAULTS as LP_DEFAULTS

logger = logging.getLogger("bibi.wave6.router")
router = APIRouter()


# ─────────── DB helper ─────────────────────────────────────────────────────
def _db(request: Request):
    """Use the same DB handle as the rest of the app."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


# ─────────── Access scoping ────────────────────────────────────────────────
def _is_admin(role: str) -> bool:
    return role in ("admin", "owner", "master_admin")


def _is_team_lead(role: str) -> bool:
    return role == "team_lead"


def _manager_self_id(user: Dict[str, Any]) -> str:
    return user.get("managerId") or user.get("id") or user.get("email") or ""


async def _check_deal_access(db, deal: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Raise 403 if the user is not allowed to view this deal.

    - admin/owner/master_admin: anything
    - team_lead: own + team
    - manager: own only
    """
    role = (user.get("role") or "").lower()
    if _is_admin(role):
        return
    me = _manager_self_id(user)

    # Manager → managerId/assigneeId == me
    deal_owner = deal.get("managerId") or deal.get("manager_id") or deal.get("assigned_to") or deal.get("assigneeId")
    if not _is_team_lead(role):
        if deal_owner == me:
            return
        raise HTTPException(403, "You do not own this deal")

    # Team lead → own deals OR deals of managers in their team
    if deal_owner == me:
        return
    if deal_owner:
        try:
            owner_doc = await db.staff.find_one(
                {"$or": [{"id": deal_owner}, {"managerId": deal_owner}, {"email": deal_owner}]},
                {"_id": 0, "team_lead_id": 1, "teamLeadId": 1},
            )
            tl = (owner_doc or {}).get("team_lead_id") or (owner_doc or {}).get("teamLeadId")
            if tl == me:
                return
        except Exception:
            pass
    raise HTTPException(403, "Deal is outside your team scope")


# ─────────── Deal workspace endpoints ──────────────────────────────────────
@router.get("/admin/pipeline/stages")
async def get_pipeline_catalog(user: Dict[str, Any] = Depends(require_manager_or_admin)):
    """Return the canonical 10-stage pipeline + legacy mapping."""
    return {
        "success": True,
        "stages": [
            {
                "id": s,
                "label": PIPELINE_STAGE_LABELS[s]["en"],
                "labels": PIPELINE_STAGE_LABELS[s],
            }
            for s in PIPELINE_STAGES
        ],
        "legacy_mapping": LEGACY_TO_PIPELINE,
    }


@router.get("/admin/deals/{deal_id}")
async def get_deal_workspace(
    deal_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Full deal payload for the operational workspace page.

    Returns: deal, customer (light), counts (deposits, contracts, payments,
    shipments), computed pipeline_stage + health.
    """
    db = _db(request)
    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"_id": 0},
    )
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")

    await _check_deal_access(db, deal, user)

    pipeline_stage = derive_pipeline_stage(deal)
    health = compute_health(deal).to_dict()

    # Customer (light)
    customer_id = deal.get("customer_id") or deal.get("customerId")
    customer = None
    if customer_id:
        customer = await db.customers.find_one(
            {"$or": [{"id": customer_id}, {"_id": customer_id}]},
            {
                "_id": 0,
                "id": 1,
                "name": 1,
                "first_name": 1,
                "last_name": 1,
                "email": 1,
                "phone": 1,
                "company": 1,
                "created_at": 1,
            },
        )

    # Counts (cheap aggregates, no payload bloat)
    async def _count(coll: str, q: Dict[str, Any]) -> int:
        try:
            return await db[coll].count_documents(q)
        except Exception:
            return 0

    counts = {
        "deposits": await _count("legal_deposits", {"deal_id": deal_id})
                   + await _count("deposits", {"deal_id": deal_id}),
        "contracts": await _count("contracts", {"deal_id": deal_id})
                    + await _count("legal_contracts", {"deal_id": deal_id}),
        "payments": await _count("payments", {"deal_id": deal_id}),
        "shipments": await _count("shipments", {"$or": [{"dealId": deal_id}, {"deal_id": deal_id}]}),
        "timeline_events": await _count("deal_timeline", {"deal_id": deal_id}),
    }

    return {
        "success": True,
        "data": {
            "deal": deal,
            "customer": customer,
            "pipeline_stage": pipeline_stage,
            "stage_legacy": deal.get("stage") or deal.get("status"),
            "health": health,
            "counts": counts,
        },
    }


@router.get("/admin/deals/{deal_id}/timeline")
async def get_deal_timeline(
    deal_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    event_type: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"_id": 0, "id": 1, "managerId": 1, "manager_id": 1, "assigned_to": 1, "assigneeId": 1},
    )
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")
    await _check_deal_access(db, deal, user)

    events = await list_events(db, deal_id=deal_id, limit=limit, event_type=event_type)
    return {"success": True, "events": events, "data": events, "total": len(events)}


@router.get("/admin/deals/{deal_id}/health")
async def get_deal_health(
    deal_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"_id": 0},
    )
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")
    await _check_deal_access(db, deal, user)
    return {"success": True, "data": compute_health(deal).to_dict()}


@router.post("/admin/deals/{deal_id}/notes")
async def add_deal_note(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Add a free-form note to the deal timeline. Notes are key events too."""
    text = (body or {}).get("text") or ""
    text = text.strip()
    if not text:
        raise HTTPException(400, "Note text is required")
    if len(text) > 4000:
        raise HTTPException(400, "Note is too long (max 4000 chars)")

    db = _db(request)
    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"_id": 0, "id": 1, "managerId": 1, "manager_id": 1, "assigned_to": 1, "assigneeId": 1},
    )
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")
    await _check_deal_access(db, deal, user)

    ev = await write_event(
        db,
        deal_id=deal_id,
        event_type="note_added",
        message=text,
        i18n_key="timeline.note",
        data={"text": text},
        actor={"email": user.get("email"), "role": user.get("role")},
    )
    return {"success": True, "data": ev.to_dict() if ev else None}


# ─────────── Legal policy (admin-only config) ──────────────────────────────
@router.get("/admin/settings/legal-policy")
async def read_legal_policy(
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Any staff role can READ the policy (used to render forms / defaults)."""
    db = _db(request)
    value = await get_policy(db)
    return {"success": True, "data": value, "defaults": LP_DEFAULTS}


@router.put("/admin/settings/legal-policy", dependencies=[Depends(require_admin)])
async def write_legal_policy(
    request: Request,
    payload: LegalPolicyIn = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin-only WRITE. Replaces the whole doc atomically."""
    db = _db(request)
    by_email = user.get("email") or user.get("id") or "admin"
    value = await set_policy(db, payload, by_email)
    return {"success": True, "data": value}


# ─────────── Startup helper ─────────────────────────────────────────────────
async def on_startup(db) -> None:
    """Hook called from server.py startup to ensure indexes + seed policy."""
    await ensure_timeline_indexes(db)
    try:
        await get_policy(db)  # seeds defaults if missing
        logger.info("[wave6] legal_policy defaults ensured")
    except Exception as e:
        logger.warning("[wave6] legal_policy seed failed: %s", e)
