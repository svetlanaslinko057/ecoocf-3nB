"""
Wave 7 — Manual Workload Rebalancing — FastAPI router
======================================================

Mounted at ``/api`` (via ``fastapi_app.include_router(router, prefix="/api")``).

Endpoints:

  POST /api/admin/reassign
        Bulk reassign lead / customer / deal to a target manager.
        ACL: admin (any), team_lead (own team only), manager (403).

  GET  /api/admin/reassign/managers
        List managers + team_leads with their active workload counts
        (leads, customers, deals, tasks) and a derived loadScore.
        ACL: admin (all), team_lead (own team), manager (self only).

  GET  /api/admin/reassign/audit
        Newest-first audit history. Filter by entity/entityId.

ACL enforcement is done in ``app.services.reassignment``; this module is
intentionally a thin HTTP layer.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from security import require_user

from app.services import reassignment as rs

logger = logging.getLogger("bibi.wave7.router")
router = APIRouter()


# ─────────── DB helper ─────────────────────────────────────────────────────
def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


# ─────────── Request models ────────────────────────────────────────────────
class ReassignIn(BaseModel):
    entity: str = Field(..., description="lead | customer | deal")
    ids: List[str] = Field(..., min_items=1)
    toManagerId: str
    reason: Optional[str] = None


# ─────────── POST /api/admin/reassign ──────────────────────────────────────
@router.post("/admin/reassign")
async def admin_reassign(
    request: Request,
    payload: ReassignIn = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    actor = {
        "id":     user.get("id"),
        "email":  user.get("email"),
        "role":   user.get("role"),
        "name":   user.get("name"),
        "teamId": user.get("teamId"),
    }
    result = await rs.reassign(
        db,
        entity=payload.entity,
        ids=payload.ids,
        to_manager_id=payload.toManagerId,
        reason=payload.reason,
        actor=actor,
    )
    return result


# ─────────── GET /api/admin/reassign/managers ──────────────────────────────
@router.get("/admin/reassign/managers")
async def admin_reassign_managers(
    request: Request,
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    actor = {
        "id":     user.get("id"),
        "email":  user.get("email"),
        "role":   user.get("role"),
        "teamId": user.get("teamId"),
    }
    items = await rs.get_managers_with_workload(db, actor=actor)
    return {"success": True, "data": items}


# ─────────── GET /api/admin/reassign/audit ─────────────────────────────────
@router.get("/admin/reassign/audit")
async def admin_reassign_audit(
    request: Request,
    entity: Optional[str] = Query(None, description="Filter by entity"),
    entityId: Optional[str] = Query(None, description="Filter by entity id"),
    limit: int = Query(50, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_user),
):
    role = (user.get("role") or "").lower()
    if role not in {"owner", "master_admin", "admin", "team_lead"}:
        raise HTTPException(status_code=403, detail="Only admin/team_lead may read audit")
    db = _db(request)
    items = await rs.get_audit_history(
        db,
        entity=entity,
        entity_id=entityId,
        limit=limit,
    )
    return {"success": True, "data": items}


# ─────────── Startup hook (backfill + indexes) ─────────────────────────────
async def on_startup(db) -> None:
    """Wave 7 startup:

    1. Ensure useful indexes on ``reassignments`` / ``customers``.
    2. Best-effort backfill of ``customers.managerId`` from matching leads.
       Safe to re-run on every startup (only updates docs missing managerId).
    """
    try:
        await db.reassignments.create_index([("createdAt", -1)])
        await db.reassignments.create_index("entity")
        await db.reassignments.create_index("entityId")
        await db.reassignments.create_index("toManagerId")
        await db.reassignments.create_index("performedBy")

        await db.customers.create_index("managerId")
        await db.leads.create_index("managerId")
        await db.deals.create_index("managerId")
        logger.info("[wave7] indexes ensured (reassignments + ownership fields)")
    except Exception as e:
        logger.warning("[wave7] index ensure failed: %s", e)

    try:
        stats = await rs.backfill_customer_manager_id(db)
        logger.info("[wave7] customer.managerId backfill: %s", stats)
    except Exception as e:
        logger.warning("[wave7] customer.managerId backfill failed: %s", e)
