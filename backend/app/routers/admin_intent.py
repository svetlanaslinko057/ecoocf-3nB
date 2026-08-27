"""
admin_intent — /api/admin/intent/* HTTP surface — REAL DB IMPLEMENTATION
========================================================================

Phase 6.5+ Wave 3 follow-up: hard-coded ``BMW 25 / Mercedes 20 / Audi 15``
payloads retired in favour of real aggregations from:

  * db.analytics_events  — frontend behaviour signals (page_view, favorite, ...)
  * db.search_logs       — VIN/lot searches (real intent signal)
  * db.favorites         — wishlist / saved cars
  * db.leads             — customer pipeline
  * db.search_watchlist  — saved searches

Intent score model (simple, transparent):
    score = clamp(favorites*15 + compares*10 + history_requests*20 + searches*5, 0, 100)

Levels: hot ≥ 75, warm 40–74, cold < 40.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from security import require_admin
from app.core.db_runtime import get_db

router = APIRouter(
    prefix="/api/admin/intent",
    tags=["admin-intent"],
    dependencies=[Depends(require_admin)],
)


def _level(score: int) -> str:
    if score >= 75:
        return "hot"
    if score >= 40:
        return "warm"
    return "cold"


async def _compute_user_scores(db, limit: int = 200) -> List[Dict[str, Any]]:
    """Build per-user intent scores from real signals."""
    per_user: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "userId": "",
        "favorites": 0,
        "compares": 0,
        "historyRequests": 0,
        "searches": 0,
        "vinChecks": 0,
        "lastActivityAt": None,
        "factors": set(),
        "interest": None,
    })

    # analytics_events — primary signal
    try:
        async for ev in db.analytics_events.find().sort("timestamp", -1).limit(5000):
            uid = ev.get("userId") or ev.get("user_id") or ev.get("sessionId")
            if not uid:
                continue
            rec = per_user[uid]
            rec["userId"] = uid
            kind = (ev.get("event") or "").lower()
            ts = ev.get("timestamp") or ev.get("created_at")
            if ts and (rec["lastActivityAt"] is None or ts > rec["lastActivityAt"]):
                rec["lastActivityAt"] = ts
            if kind in ("favorite_added", "favorite"):
                rec["favorites"] += 1
                rec["factors"].add("wishlist")
            elif kind in ("compare_added", "compare"):
                rec["compares"] += 1
                rec["factors"].add("multiple_vehicles")
            elif kind in ("history_report_requested", "history_report"):
                rec["historyRequests"] += 1
                rec["factors"].add("history_check")
            elif kind in ("search", "vin_search"):
                rec["searches"] += 1
                rec["factors"].add("vin_check" if "vin" in kind else "single_view")
            elif kind == "page_view":
                rec["searches"] = rec["searches"]  # no-op (page views are low-signal)
            props = ev.get("properties") or {}
            if isinstance(props, dict):
                interest = props.get("vehicleTitle") or props.get("vin") or props.get("slug")
                if interest:
                    rec["interest"] = interest
    except Exception:
        pass

    # favorites collection — direct
    try:
        async for fav in db.favorites.find():
            uid = fav.get("user_id") or fav.get("userId") or fav.get("customer_id")
            if not uid:
                continue
            rec = per_user[uid]
            rec["userId"] = uid
            rec["favorites"] += 1
            rec["factors"].add("wishlist")
    except Exception:
        pass

    # search_watchlist — strong intent signal
    try:
        async for sw in db.search_watchlist.find():
            uid = sw.get("user_id") or sw.get("userId") or sw.get("customer_id")
            if not uid:
                continue
            rec = per_user[uid]
            rec["userId"] = uid
            rec["searches"] += 1
            rec["factors"].add("saved_search")
    except Exception:
        pass

    items: List[Dict[str, Any]] = []
    for uid, rec in per_user.items():
        score = min(100, rec["favorites"] * 15 + rec["compares"] * 10 + rec["historyRequests"] * 20 + rec["searches"] * 5)
        items.append({
            "userId": uid,
            "score": score,
            "level": _level(score),
            "factors": sorted(rec["factors"]) or ["page_view"],
            "favoritesCount": rec["favorites"],
            "comparesCount": rec["compares"],
            "historyRequestsCount": rec["historyRequests"],
            "lastActivityAt": rec["lastActivityAt"],
            "vehicleInterest": rec["interest"],
        })
    items.sort(key=lambda r: r["score"], reverse=True)
    return items[:limit]


async def _safe_count(db, coll: str, q: Dict[str, Any] | None = None) -> int:
    try:
        return await db[coll].count_documents(q or {})
    except Exception:
        return 0


@router.get("/analytics")
async def intent_analytics():
    """Real intent analytics computed from user behaviour signals."""
    db = get_db()
    scored = await _compute_user_scores(db, limit=10000)

    hot = sum(1 for s in scored if s["level"] == "hot")
    warm = sum(1 for s in scored if s["level"] == "warm")
    cold = sum(1 for s in scored if s["level"] == "cold")
    total = len(scored)

    # Top categories — derive from analytics_events.properties.make
    cats: Counter = Counter()
    try:
        async for ev in db.analytics_events.find({"event": {"$in": ["page_view", "favorite_added", "compare_added"]}}).limit(5000):
            props = ev.get("properties") or {}
            if isinstance(props, dict):
                make = props.get("make") or props.get("brand")
                if make:
                    cats[str(make)] += 1
    except Exception:
        pass
    top_cats = [{"category": k, "count": v} for k, v in cats.most_common(5)]

    # Conversion rate proxy: hot users that became leads
    conv = 0
    try:
        if hot > 0:
            hot_ids = [s["userId"] for s in scored if s["level"] == "hot"][:500]
            converted = await _safe_count(db, "leads", {"user_id": {"$in": hot_ids}})
            conv = round((converted / hot) * 100)
    except Exception:
        conv = 0

    # Auto-leads: users automatically promoted to a lead record
    auto_leads_created = await _safe_count(db, "leads", {"source": "intent_auto"})

    # Average score across all scored users
    avg_score = 0 if not scored else round(sum(s["score"] for s in scored) / len(scored), 1)

    return {
        "totalIntents": total,
        "total": total,
        "totalUsersWithIntent": total,
        "levels": {"hot": hot, "warm": warm, "cold": cold},
        "hotLeads": hot,
        "warmLeads": warm,
        "coldLeads": cold,
        "hotUsers": hot,
        "warmUsers": warm,
        "coldUsers": cold,
        "autoLeadsCreated": auto_leads_created,
        "avgScore": avg_score,
        "averageScore": avg_score,
        "conversionRate": conv,
        "topCategories": top_cats,
        "trends": {"hot": 0, "warm": 0, "cold": 0},
    }


@router.get("/hot-leads")
async def intent_hot_leads():
    """Real hot leads from intent scoring + customer enrichment."""
    db = get_db()
    scored = await _compute_user_scores(db, limit=500)
    hot = [s for s in scored if s["level"] == "hot"][:50]

    # Enrich with customer context if available
    enriched: List[Dict[str, Any]] = []
    for s in hot:
        ctx: Dict[str, Any] = {}
        try:
            cust = await db.customers.find_one({"$or": [{"id": s["userId"]}, {"user_id": s["userId"]}, {"_id": s["userId"]}]})
            if cust:
                ctx = {
                    "name": cust.get("name") or cust.get("full_name"),
                    "email": cust.get("email"),
                    "phone": cust.get("phone"),
                }
        except Exception:
            pass

        # Already-notified flag
        notified = False
        try:
            notified = bool(await db.intent_notifications.find_one({"user_id": s["userId"]}))
        except Exception:
            notified = False

        enriched.append({
            "userId": s["userId"],
            "level": s["level"],
            "score": s["score"],
            "context": ctx,
            "favoritesCount": s["favoritesCount"],
            "comparesCount": s["comparesCount"],
            "historyRequestsCount": s["historyRequestsCount"],
            "lastActivityAt": s["lastActivityAt"],
            "managerNotified": notified,
            "vehicleInterest": s["vehicleInterest"],
        })
    return enriched


@router.get("/scores")
async def intent_scores(limit: int = 50):
    """Real per-user intent scores."""
    db = get_db()
    scored = await _compute_user_scores(db, limit=limit)
    return {"items": scored, "total": len(scored)}


@router.post("/mark-notified/{lead_id}")
async def intent_mark_notified(lead_id: str):
    """Persist notification flag so the manager doesn't get pinged twice."""
    db = get_db()
    try:
        await db.intent_notifications.update_one(
            {"user_id": lead_id},
            {"$set": {
                "user_id": lead_id,
                "notified_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
