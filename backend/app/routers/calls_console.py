"""
Calls Console router — unified call-management surface for the ECO CRM
(admin + manager).  Built on top of the existing `ringostat_calls`
collection and the Ringostat webhook/outcome pipeline already present in
`server.py`.

Endpoints (all under /api/manager/calls/*, manager_or_admin scope):
  GET  /summary           — compact counters for the admin/manager banner
  GET  /feed              — unified, filterable call list (enriched)
  GET  /awaiting-outcome  — answered calls > threshold without an outcome
  GET  /callbacks         — scheduled call-backs (outcome=callback + date)

Scope rules:
  • role == "manager"  → only the caller's own calls (manager_id == user.id)
  • role in (admin)    → all calls; may narrow via ?manager_id=

These paths do NOT collide with the existing routes registered directly on
`fastapi_app` in server.py (/my, /missed, POST /{call_id}/outcome).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from security import require_manager_or_admin

logger = logging.getLogger("bibi.calls_console")

# Answered calls longer than this many seconds REQUIRE an outcome.
DEFAULT_OUTCOME_THRESHOLD = 10


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _serialize():
    from app.utils.serialization import serialize_doc
    return serialize_doc


def _user_id(user: Dict[str, Any]) -> Optional[str]:
    return (user or {}).get("id") or (user or {}).get("_id") or (user or {}).get("sub")


def _is_admin(user: Dict[str, Any]) -> bool:
    return (user or {}).get("role") in ("admin", "master_admin", "team_lead")


def _period_start(period: str, now: datetime) -> Optional[datetime]:
    period = (period or "").lower()
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return None  # "all"


async def _scope_query(user: Dict[str, Any], manager_id: Optional[str]) -> Dict[str, Any]:
    """Build the base Mongo query honouring role scope."""
    q: Dict[str, Any] = {}
    if not _is_admin(user):
        q["manager_id"] = _user_id(user)
    elif manager_id:
        q["manager_id"] = manager_id
    return q


async def _enrich(calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach lead + manager display info to a list of calls."""
    db = _db()
    serialize_doc = _serialize()

    # Collect ids
    lead_ids = {c.get("lead_id") for c in calls if c.get("lead_id")}
    mgr_ids = {c.get("manager_id") for c in calls if c.get("manager_id")}

    leads_map: Dict[str, Any] = {}
    if lead_ids:
        async for ld in db.leads.find({"_id": {"$in": list(lead_ids)}}):
            leads_map[ld["_id"]] = ld

    staff_map: Dict[str, Any] = {}
    if mgr_ids:
        # staff may key by a human `id` field OR a BSON ObjectId `_id`.
        from bson import ObjectId
        str_ids = [str(m) for m in mgr_ids if m]
        obj_ids = []
        for m in str_ids:
            if len(m) == 24:
                try:
                    obj_ids.append(ObjectId(m))
                except Exception:
                    pass
        or_clauses = [{"id": {"$in": str_ids}}]
        if obj_ids:
            or_clauses.append({"_id": {"$in": obj_ids}})
        async for st in db.staff.find({"$or": or_clauses}):
            key_id = st.get("id") or str(st.get("_id"))
            staff_map[key_id] = st
            staff_map[str(st.get("_id"))] = st

    out = []
    for c in calls:
        ld = leads_map.get(c.get("lead_id"))
        if ld:
            c["lead"] = {"id": ld.get("_id"), "name": ld.get("name"),
                         "phone": ld.get("phone"), "status": ld.get("status")}
        st = staff_map.get(c.get("manager_id"))
        if st:
            c["manager_name"] = st.get("name") or st.get("email")
        out.append(serialize_doc(c))
    return out


router = APIRouter(prefix="/api/manager/calls", tags=["calls-console"])


@router.get("/summary")
async def calls_summary(
    manager_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Compact counters that power the global call banner + console KPIs."""
    db = _db()
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    base = await _scope_query(user, manager_id)

    def merged(extra: Dict[str, Any]) -> Dict[str, Any]:
        q = dict(base)
        q.update(extra)
        return q

    today_q = {"started_at": {"$gte": today}}

    today_total = await db.ringostat_calls.count_documents(merged(today_q))
    today_inbound = await db.ringostat_calls.count_documents(merged({**today_q, "direction": "inbound"}))
    today_outbound = await db.ringostat_calls.count_documents(merged({**today_q, "direction": "outbound"}))
    today_missed = await db.ringostat_calls.count_documents(
        merged({**today_q, "status": {"$in": ["MISSED", "NO ANSWER", "NO_ANSWER"]}}))
    today_answered = await db.ringostat_calls.count_documents(
        merged({**today_q, "status": {"$in": ["ANSWERED", "PROPER", "COMPLETED"]}}))

    awaiting = await db.ringostat_calls.count_documents(merged({
        "status": {"$in": ["ANSWERED", "PROPER", "COMPLETED"]},
        "duration": {"$gt": DEFAULT_OUTCOME_THRESHOLD},
        "$or": [{"outcome": {"$exists": False}}, {"outcome": None}, {"outcome": ""}],
    }))

    cb_base = merged({"outcome": "callback", "callback_at": {"$nin": [None, ""]}})
    scheduled_callbacks = await db.ringostat_calls.count_documents(cb_base)

    overdue_callbacks = await db.ringostat_calls.count_documents(merged({
        "outcome": "callback",
        "callback_at": {"$lt": now.isoformat()},
    }))

    return {
        "success": True,
        "today_total": today_total,
        "today_inbound": today_inbound,
        "today_outbound": today_outbound,
        "today_missed": today_missed,
        "today_answered": today_answered,
        "awaiting_outcome": awaiting,
        "scheduled_callbacks": scheduled_callbacks,
        "overdue_callbacks": overdue_callbacks,
        "scope": "self" if not _is_admin(user) else "all",
    }


@router.get("/feed")
async def calls_feed(
    period: str = Query("week"),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    awaiting: bool = Query(False),
    q: Optional[str] = Query(None),
    manager_id: Optional[str] = Query(None),
    limit: int = Query(150, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Unified, filterable, enriched call list for the console table."""
    db = _db()
    now = datetime.now(timezone.utc)
    query = await _scope_query(user, manager_id)

    start = _period_start(period, now)
    if start is not None:
        query["started_at"] = {"$gte": start}
    if direction in ("inbound", "outbound"):
        query["direction"] = direction
    if status:
        query["status"] = status.upper()
    if outcome:
        query["outcome"] = outcome
    if awaiting:
        query["status"] = {"$in": ["ANSWERED", "PROPER", "COMPLETED"]}
        query["duration"] = {"$gt": DEFAULT_OUTCOME_THRESHOLD}
        query["$or"] = [{"outcome": {"$exists": False}}, {"outcome": None}, {"outcome": ""}]
    if q:
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"from": rx}, {"to": rx}]

    calls = await db.ringostat_calls.find(query).sort("started_at", -1).limit(limit).to_list(limit)
    enriched = await _enrich(calls)
    return {"success": True, "calls": enriched, "total": len(enriched)}


@router.get("/awaiting-outcome")
async def calls_awaiting_outcome(
    manager_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Answered calls (> threshold) that still need an outcome filled."""
    db = _db()
    query = await _scope_query(user, manager_id)
    query.update({
        "status": {"$in": ["ANSWERED", "PROPER", "COMPLETED"]},
        "duration": {"$gt": DEFAULT_OUTCOME_THRESHOLD},
        "$or": [{"outcome": {"$exists": False}}, {"outcome": None}, {"outcome": ""}],
    })
    calls = await db.ringostat_calls.find(query).sort("started_at", -1).limit(limit).to_list(limit)
    enriched = await _enrich(calls)
    return {"success": True, "calls": enriched, "total": len(enriched)}


@router.get("/callbacks")
async def calls_scheduled_callbacks(
    manager_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Scheduled call-backs (outcome=callback with a callback_at date)."""
    db = _db()
    now = datetime.now(timezone.utc)
    query = await _scope_query(user, manager_id)
    query.update({"outcome": "callback", "callback_at": {"$nin": [None, ""]}})
    calls = await db.ringostat_calls.find(query).sort("callback_at", 1).limit(limit).to_list(limit)
    enriched = await _enrich(calls)
    # mark overdue
    now_iso = now.isoformat()
    for c in enriched:
        cb = c.get("callback_at")
        c["overdue"] = bool(cb and str(cb) < now_iso)
    return {"success": True, "calls": enriched, "total": len(enriched)}
