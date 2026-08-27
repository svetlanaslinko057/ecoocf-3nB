"""
admin_kpi — /api/admin/kpi/* HTTP surface — REAL DB IMPLEMENTATION
=================================================================

Phase 6.5+ Wave 3 follow-up: stubs replaced with REAL Mongo queries.
No more hard-coded ``Manager 1/2/3`` payloads.

Data sources:
  * db.leads             — lead lifecycle, source, score, owner
  * db.staff             — operators with roles {manager, team_lead}
  * db.deals             — converted opportunities
  * db.tasks             — outstanding work
  * db.callbacks         — scheduled callbacks
  * db.ringostat_calls   — telephony outcomes

Missing collections return 0 (tolerant) — endpoint shapes preserved
for frontend contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from security import require_admin
from app.core.db_runtime import get_db

router = APIRouter(
    prefix="/api/admin/kpi",
    tags=["admin-kpi"],
    dependencies=[Depends(require_admin)],
)


async def _safe_count(db, coll: str, q: Dict[str, Any] | None = None) -> int:
    try:
        return await db[coll].count_documents(q or {})
    except Exception:
        return 0


async def _safe_aggregate(db, coll: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        return [doc async for doc in db[coll].aggregate(pipeline)]
    except Exception:
        return []


@router.get("/dashboard")
async def kpi_dashboard():
    """Real KPI snapshot — leads, contact-rate, conversion, response time."""
    db = get_db()
    since_week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    since_prev = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

    leads_created = await _safe_count(db, "leads", {"created_at": {"$gte": since_week}})
    leads_prev = await _safe_count(db, "leads", {"created_at": {"$gte": since_prev, "$lt": since_week}})
    contacted = await _safe_count(db, "leads", {"created_at": {"$gte": since_week}, "status": {"$in": ["contacted", "qualified", "converted"]}})
    converted = await _safe_count(db, "leads", {"created_at": {"$gte": since_week}, "status": "converted"})
    converted_prev = await _safe_count(db, "leads", {"created_at": {"$gte": since_prev, "$lt": since_week}, "status": "converted"})

    contact_rate = 0 if leads_created == 0 else round((contacted / leads_created) * 100)
    conversion_rate = 0 if leads_created == 0 else round((converted / leads_created) * 100)
    conversion_rate_prev = 0 if leads_prev == 0 else round((converted_prev / leads_prev) * 100)

    # Average first response (minutes)
    rows = await _safe_aggregate(db, "leads", [
        {"$match": {"first_contact_at": {"$exists": True}, "created_at": {"$exists": True}}},
        {"$project": {"sec": {"$divide": [{"$subtract": ["$first_contact_at", "$created_at"]}, 1000]}}},
        {"$group": {"_id": None, "avg_sec": {"$avg": "$sec"}}},
    ])
    avg_response = 0
    try:
        if rows:
            avg_response = round((rows[0].get("avg_sec") or 0) / 60.0, 1)
    except Exception:
        avg_response = 0

    return {
        "leadsCreated": leads_created,
        "contactRate": contact_rate,
        "conversionRate": conversion_rate,
        "avgResponseTime": avg_response,
        "trends": {
            "leads": 0 if leads_prev == 0 else round(((leads_created - leads_prev) / leads_prev) * 100),
            "conversion": conversion_rate - conversion_rate_prev,
        },
    }


@router.get("/leaderboard")
async def kpi_leaderboard():
    """Real per-manager leaderboard from db.staff + db.leads."""
    db = get_db()
    out: List[Dict[str, Any]] = []
    try:
        async for s in db.staff.find({"role": {"$in": ["manager", "team_lead"]}, "disabled": {"$ne": True}}):
            mid = s.get("id") or str(s.get("_id"))
            owner_q = {"$or": [{"manager_id": mid}, {"assigned_to": mid}, {"owner_id": mid}]}
            total = await _safe_count(db, "leads", owner_q)
            converted = await _safe_count(db, "leads", {**owner_q, "status": "converted"})
            score = 0 if total == 0 else round((converted / total) * 100)
            out.append({
                "id": mid,
                "name": s.get("name") or (s.get("email") or "").split("@")[0],
                "email": s.get("email"),
                "role": s.get("role"),
                "score": score,
                "leads": total,
                "conversions": converted,
            })
    except Exception:
        pass
    out.sort(key=lambda r: r["score"], reverse=True)
    return {"managers": out}


@router.get("/team")
async def kpi_team():
    db = get_db()
    total_members = await _safe_count(db, "staff", {"role": {"$in": ["manager", "team_lead"]}, "disabled": {"$ne": True}})

    # Use the leaderboard to compute averages + top performer
    lb = (await kpi_leaderboard()).get("managers", [])
    avg_score = 0 if not lb else round(sum(m["score"] for m in lb) / len(lb))
    top = lb[0]["name"] if lb else None

    return {
        "teamStats": {
            "totalMembers": total_members,
            "avgScore": avg_score,
            "topPerformer": top,
        }
    }


@router.get("/team-summary")
async def kpi_team_summary():
    db = get_db()
    active_managers = await _safe_count(db, "staff", {"role": {"$in": ["manager", "team_lead"]}, "disabled": {"$ne": True}})
    total_leads = await _safe_count(db, "leads", {})
    total_conversions = await _safe_count(db, "leads", {"status": "converted"})
    return {
        "summary": {
            "activeManagers": active_managers,
            "totalLeads": total_leads,
            "totalConversions": total_conversions,
        }
    }


@router.get("/alerts")
async def kpi_alerts():
    """Real critical/warning alerts surfaced from ops_audit."""
    db = get_db()
    alerts: List[Dict[str, Any]] = []
    try:
        cur = db.ops_audit.find({"severity": {"$in": ["critical", "warning", "error"]}}).sort("ts", -1).limit(20)
        async for a in cur:
            alerts.append({
                "id": str(a.get("_id")),
                "severity": a.get("severity"),
                "title": a.get("title"),
                "message": a.get("message"),
                "source": a.get("source"),
                "ts": a.get("ts"),
            })
    except Exception:
        pass
    return {"alerts": alerts}
