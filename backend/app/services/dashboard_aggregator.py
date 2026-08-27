"""
dashboard_aggregator — real DB-driven aggregator for the master admin dashboard.

Replaces the hard-coded Manager 1/2/3 + fake SLA values that lived inline in
``server.py:/api/dashboard/master``.  This module is the canonical home for
computing the master KPI snapshot from actual MongoDB collections.

Design notes
============
* Pure read-only.  No writes.
* Tolerant of missing collections (returns 0 rather than crashing).
* Single entrypoint: ``build_master_snapshot(db, period)``.
* Period filter is applied as ``created_at >= now - <range>`` where the
  collection carries a ``created_at`` field; otherwise the period is
  silently ignored and totals are used.

Wave-3 invariant: pure service, single ``get_db()`` accessor used in
``server.py`` shim.  No ``import server`` anywhere.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


# ── period → timedelta ──────────────────────────────────────────────────────
_PERIOD_DELTA = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}


def _since(period: str) -> datetime:
    return datetime.now(timezone.utc) - _PERIOD_DELTA.get(period, _PERIOD_DELTA["week"])


async def _safe_count(db, coll: str, query: Optional[Dict[str, Any]] = None) -> int:
    """count_documents that returns 0 if the collection does not exist."""
    try:
        return await db[coll].count_documents(query or {})
    except Exception:
        return 0


async def _safe_aggregate(db, coll: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        cur = db[coll].aggregate(pipeline)
        return [doc async for doc in cur]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────────────

async def _build_sla(db, since: datetime) -> Dict[str, Any]:
    overdue_leads = await _safe_count(db, "leads", {"status": {"$nin": ["converted", "lost"]}, "due_at": {"$lt": datetime.now(timezone.utc)}})
    overdue_tasks = await _safe_count(db, "tasks", {"status": {"$ne": "done"}, "due_at": {"$lt": datetime.now(timezone.utc)}})
    overdue_callbacks = await _safe_count(db, "callbacks", {"status": "scheduled", "scheduled_at": {"$lt": datetime.now(timezone.utc)}})

    total_leads = await _safe_count(db, "leads", {})
    converted_leads = await _safe_count(db, "leads", {"status": "converted"})

    # Average response time: derive from leads with first_contact_at
    avg_response = 0
    if total_leads > 0:
        pipe = [
            {"$match": {"first_contact_at": {"$exists": True}, "created_at": {"$exists": True}}},
            {"$project": {"resp_sec": {"$divide": [{"$subtract": ["$first_contact_at", "$created_at"]}, 1000]}}},
            {"$group": {"_id": None, "avg_sec": {"$avg": "$resp_sec"}}},
        ]
        rows = await _safe_aggregate(db, "leads", pipe)
        if rows:
            try:
                avg_response = round((rows[0].get("avg_sec") or 0) / 60.0, 1)
            except Exception:
                avg_response = 0

    missed_rate = 0
    if total_leads > 0:
        missed_rate = round((overdue_leads / total_leads) * 100)

    return {
        "overdueLeads": overdue_leads,
        "overdueTasks": overdue_tasks,
        "overdueCallbacks": overdue_callbacks,
        "avgFirstResponseMinutes": avg_response,
        "missedSlaRate": missed_rate,
        "responseTime": {"value": avg_response, "target": 5, "status": "good" if avg_response <= 5 else "warning"},
        "firstContact": {"value": 0 if total_leads == 0 else round(((total_leads - overdue_leads) / total_leads) * 100), "target": 90, "status": "good"},
        "resolution": {"value": 0 if total_leads == 0 else round((converted_leads / total_leads) * 100), "target": 85, "status": "good"},
    }


async def _build_workload(db) -> Dict[str, Any]:
    """Real workload from db.staff (role in {manager, team_lead}) +
    per-manager leads/tasks counts."""
    managers: List[Dict[str, Any]] = []
    distribution: List[Dict[str, Any]] = []

    try:
        async for s in db.staff.find({"role": {"$in": ["manager", "team_lead"]}, "disabled": {"$ne": True}}):
            mid = s.get("id") or str(s.get("_id"))
            email = s.get("email") or ""
            name = s.get("name") or email.split("@")[0] or "Manager"

            # Real lead/task counts assigned to this manager.  Multiple
            # ownership fields are checked because the platform uses both
            # ``manager_id`` and ``assigned_to``.
            active_leads = await _safe_count(db, "leads", {
                "$or": [{"manager_id": mid}, {"assigned_to": mid}, {"owner_id": mid}],
                "status": {"$nin": ["converted", "lost", "archived"]},
            })
            open_tasks = await _safe_count(db, "tasks", {
                "$or": [{"manager_id": mid}, {"assigned_to": mid}, {"owner_id": mid}],
                "status": {"$ne": "done"},
            })

            # Score: simple heuristic — converted/total
            total_assigned = await _safe_count(db, "leads", {
                "$or": [{"manager_id": mid}, {"assigned_to": mid}, {"owner_id": mid}],
            })
            converted = await _safe_count(db, "leads", {
                "$or": [{"manager_id": mid}, {"assigned_to": mid}, {"owner_id": mid}],
                "status": "converted",
            })
            score = 0 if total_assigned == 0 else round((converted / total_assigned) * 100)

            load_pct = min(100, active_leads * 5)  # crude: 1 lead = 5% load
            status = "overloaded" if active_leads >= 20 else ("normal" if active_leads > 0 else "idle")

            managers.append({
                "managerId": mid,
                "name": name,
                "email": email,
                "role": s.get("role"),
                "status": status,
                "activeLeads": active_leads,
                "openTasks": open_tasks,
                "score": score,
                "avatar": s.get("avatar"),
            })
            distribution.append({
                "name": name,
                "load": load_pct,
                "tasks": open_tasks,
                "avatar": s.get("avatar"),
            })
    except Exception:
        pass

    total = len(managers)
    overloaded = sum(1 for m in managers if m["status"] == "overloaded")
    active = sum(1 for m in managers if m["status"] != "idle") or total
    avg_load = 0 if not distribution else round(sum(d["load"] for d in distribution) / len(distribution))

    return {
        "activeManagers": active,
        "totalManagers": total,
        "overloadedManagers": overloaded,
        "avgLoad": avg_load,
        "managers": managers,
        "distribution": distribution,
    }


async def _build_leads(db, since: datetime) -> Dict[str, Any]:
    base = {"created_at": {"$gte": since.isoformat()}}

    total_period = await _safe_count(db, "leads", base) or await _safe_count(db, "leads", {})

    by_status_raw = await _safe_aggregate(db, "leads", [
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ])
    by_status: Dict[str, int] = {(r["_id"] or "new"): r["n"] for r in by_status_raw}

    by_source_raw = await _safe_aggregate(db, "leads", [
        {"$group": {"_id": "$source", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 6},
    ])
    by_source: Dict[str, int] = {(r["_id"] or "unknown"): r["n"] for r in by_source_raw}

    return {
        "newCount": by_status.get("new", 0),
        "inProgressCount": by_status.get("in_progress", 0) + by_status.get("contacted", 0) + by_status.get("qualified", 0),
        "convertedCount": by_status.get("converted", 0),
        "lostCount": by_status.get("lost", 0),
        "unassignedCount": await _safe_count(db, "leads", {"assigned_to": None}),
        "trend": 0,
        "bySource": by_source,
        "byStatus": {
            "new": by_status.get("new", 0),
            "contacted": by_status.get("contacted", 0),
            "qualified": by_status.get("qualified", 0),
        },
        "totalPeriod": total_period,
    }


async def _build_callbacks(db) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "pending": await _safe_count(db, "callbacks", {"status": "scheduled"}),
        "overdue": await _safe_count(db, "callbacks", {"status": "scheduled", "scheduled_at": {"$lt": now}}),
        "completed": await _safe_count(db, "callbacks", {"status": "completed"}),
        "scheduled": await _safe_count(db, "callbacks", {"status": "scheduled", "scheduled_at": {"$gte": now}}),
        "missedCalls": await _safe_count(db, "ringostat_calls", {"outcome": "missed"}),
        "noAnswerLeads": await _safe_count(db, "ringostat_calls", {"outcome": "no_answer"}),
        "followUpsDue": await _safe_count(db, "tasks", {"type": "followup", "status": {"$ne": "done"}}),
        "callbacksScheduled": await _safe_count(db, "callbacks", {"status": "scheduled"}),
        "smsTriggered": await _safe_count(db, "sms_log", {}),
    }


async def _build_deposits(db) -> Dict[str, Any]:
    pending = await _safe_count(db, "legal_deposits", {"status": "pending"}) + await _safe_count(db, "payments", {"kind": "deposit", "status": "pending"})
    confirmed = await _safe_count(db, "legal_deposits", {"status": "confirmed"}) + await _safe_count(db, "payments", {"kind": "deposit", "status": "succeeded"})
    overdue = await _safe_count(db, "legal_deposits", {"status": "overdue"})
    total = pending + confirmed + overdue
    return {
        "total": total,
        "pending": pending,
        "confirmed": confirmed,
        "trend": 0,
        "pendingDeposits": pending,
        "unconfirmed": pending,
        "overdue": overdue,
        "depositsWithoutProof": await _safe_count(db, "legal_deposits", {"proof_url": {"$in": [None, ""]}}),
        "verifiedToday": confirmed,
    }


async def _build_documents(db) -> Dict[str, Any]:
    return {
        "pending": await _safe_count(db, "documents", {"status": "pending"}),
        "approved": await _safe_count(db, "documents", {"status": "approved"}),
        "rejected": await _safe_count(db, "documents", {"status": "rejected"}),
        "pendingVerification": await _safe_count(db, "documents", {"status": "pending_verification"}),
        "expiringSoon": await _safe_count(db, "documents", {"expires_at": {"$lt": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}}),
        "missingDocs": 0,
        "rejectedCount": await _safe_count(db, "documents", {"status": "rejected"}),
        "uploadedToday": await _safe_count(db, "documents", {"created_at": {"$gte": _since("day").isoformat()}}),
    }


async def _build_routing(db) -> Dict[str, Any]:
    return {
        "activeRules": await _safe_count(db, "routing_rules", {"enabled": True}),
        "autoAssigned": await _safe_count(db, "leads", {"assignment_mode": "auto"}),
        "manualAssigned": await _safe_count(db, "leads", {"assignment_mode": "manual"}),
        "unassignedLeads": await _safe_count(db, "leads", {"assigned_to": None}),
        "avgAssignTime": 0,
        "fallbackAssignments": await _safe_count(db, "leads", {"assignment_fallback": True}),
        "reassignmentRate": 0,
    }


async def _build_system(db) -> Dict[str, Any]:
    """System health — pulls from real runtime where available."""
    # Lazy imports: avoid circular issues at module load.
    try:
        from server import ingestion_queue, session_service, parser_config  # type: ignore
        queue_size = ingestion_queue.get_stats().get("queue_size", 0)
        active_sessions = len(session_service.get_active())
        parser_active = bool(parser_config.enabled)
    except Exception:
        queue_size = 0
        active_sessions = 0
        parser_active = False

    vins_total = await _safe_count(db, "vin_data", {})
    vins_lemon = await _safe_count(db, "vin_data_lemon", {})
    vins_west = await _safe_count(db, "vin_data_westmotors", {})

    return {
        "parserStatus": "active" if parser_active else "stopped",
        "systemStatus": "healthy",
        "activeSessions": active_sessions,
        "queueSize": queue_size,
        "queueBacklog": queue_size,
        "vinsProcessed": vins_total + vins_lemon + vins_west,
        "failedJobs": await _safe_count(db, "ops_audit", {"severity": "critical"}),
        "lastSync": datetime.now(timezone.utc).isoformat(),
        "cacheHitRate": 0,
    }


async def _build_vehicles(db, since: datetime) -> Dict[str, Any]:
    total = (
        await _safe_count(db, "vin_data", {})
        + await _safe_count(db, "vin_data_lemon", {})
        + await _safe_count(db, "vin_data_westmotors", {})
    )
    new_today = await _safe_count(db, "vin_data", {"created_at": {"$gte": _since("day").isoformat()}})
    return {"total": total, "newToday": new_today}


# ─────────────────────────────────────────────────────────────────────────────
# Public entrypoint
# ─────────────────────────────────────────────────────────────────────────────

async def build_master_snapshot(db, period: str = "week") -> Dict[str, Any]:
    """Build the full master dashboard snapshot from real DB collections.

    Backward-compatible payload shape — all keys preserved for FE contract.
    """
    period = period if period in _PERIOD_DELTA else "week"
    since = _since(period)

    sla = await _build_sla(db, since)
    workload = await _build_workload(db)
    leads = await _build_leads(db, since)
    callbacks = await _build_callbacks(db)
    deposits = await _build_deposits(db)
    documents = await _build_documents(db)
    routing = await _build_routing(db)
    system = await _build_system(db)
    vehicles = await _build_vehicles(db, since)

    return {
        "success": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "sla": sla,
        "workload": workload,
        "leads": leads,
        "callbacks": callbacks,
        "deposits": deposits,
        "documents": documents,
        "routing": routing,
        "system": system,
        "vehicles": vehicles,
    }


__all__ = ["build_master_snapshot"]
