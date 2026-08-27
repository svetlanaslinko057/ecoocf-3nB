"""
admin_engagement — /api/admin/engagement HTTP surface (UNIFIED)
================================================================

Wave 7.5 — Engagement Consolidation
-----------------------------------

This module is now the **single source of truth** for customer-engagement
data (favorites / compare / shares). The Wave-2 sibling
``manager_engagement`` is DELETED — its endpoints have been folded in
here, gated by ``require_manager_or_admin`` so the whole staff hierarchy
(manager / team_lead / admin / master_admin / moderator) can read the
same numbers without a duplicated router or duplicated page.

Surface (all PURE READ-ONLY — Phase 3 preview rule):

  * GET /analytics            → KPIs over customers/favorites/compare/shares
  * GET /top-users            → ranked customers (name+email+phone+score+level)
  * GET /top-vehicles         → ranked vehicles (incl. current_bid)
  * GET /vin-stats?vin=…      → exact counts for ONE VIN
  * GET /customer/{id}        → per-customer drill-down (full activity trail)

Dropped (Wave 7.5):

  * /audience, /campaign, /history, /templates  — were MOCK stubs returning
    hard-coded empties; they masqueraded as a "campaign engine" that did
    not exist. Removed to comply with the freeze discipline (no fake UI).

Collections read:
    customers, favorites, compare, shares, vin_data
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from security import require_manager_or_admin

logger = logging.getLogger("bibi.admin_engagement")


def _db():
    """Lazy resolver for the live Motor handle via the runtime accessor."""
    from app.core.db_runtime import get_db  # noqa: E402 (lazy-bridge → accessor)
    return get_db()


router = APIRouter(
    prefix="/api/admin/engagement",
    tags=["admin-engagement"],
    dependencies=[Depends(require_manager_or_admin)],
)


# ─────────────────────────────────────────────────────────────────────────
# /analytics  — KPI cards: Total / Active / Hot / Engagement%
# ─────────────────────────────────────────────────────────────────────────
@router.get("/analytics")
async def engagement_analytics():
    """Real-time engagement KPIs aggregated from `favorites`, `compare`,
    `shares` and `customers` collections. No mock data — empty values
    mean the corresponding collection has nothing yet."""
    db = _db()
    try:
        total_users  = await db.customers.count_documents({})
        fav_users    = await db.favorites.distinct("customerId") or []
        cmp_users    = await db.compare.distinct("userId") or []
        share_users  = await db.shares.distinct("createdBy") or []
        active_set   = {u for u in (list(fav_users) + list(cmp_users) + list(share_users)) if u}
        active_users = len(active_set)
        engagement   = round((active_users / total_users) * 100, 1) if total_users else 0
        hot = warm = cold = 0
        for cid in active_set:
            score = 0
            score += await db.favorites.count_documents({"$or": [{"customerId": cid}, {"userId": cid}]})
            score += await db.compare.count_documents({"$or": [{"customerId": cid}, {"userId": cid}]})
            score += await db.shares.count_documents({"createdBy": cid})
            if score >= 5: hot += 1
            elif score >= 2: warm += 1
            else: cold += 1
        page_views = await db.shares.count_documents({})  # proxy
        return {
            "totalUsers":     total_users,
            "activeUsers":    active_users,
            "engagementRate": engagement,
            "pageViews":      page_views,
            "hotUsers":       hot,
            "warmUsers":      warm,
            "coldUsers":      max(0, total_users - active_users),
        }
    except Exception as e:
        logger.warning(f"[engagement/analytics] {e}")
        return {"totalUsers": 0, "activeUsers": 0, "engagementRate": 0,
                "pageViews": 0, "hotUsers": 0, "warmUsers": 0, "coldUsers": 0}


# ─────────────────────────────────────────────────────────────────────────
# /top-users  — ranked customers (with phone for outbound calls)
# ─────────────────────────────────────────────────────────────────────────
@router.get("/top-users")
async def engagement_top_users(limit: int = 50):
    """Top customers by combined favorites+compare+shares score.

    Score formula: ``favoritesCount × 10 + comparesCount × 5 + sharesCount × 3``
    Heat level: hot ≥ 50, warm ≥ 20, cold < 20.

    Aggregated directly from collections — no mock data. Includes
    ``phone`` so the UI can drive outbound-call workflows.
    """
    db = _db()
    try:
        scores: Dict[str, Dict[str, Any]] = {}

        async for f in db.favorites.find({}, {"customerId": 1, "userId": 1}):
            cid = f.get("customerId") or f.get("userId")
            if not cid: continue
            scores.setdefault(cid, {"id": cid, "favoritesCount": 0, "comparesCount": 0, "sharesCount": 0})
            scores[cid]["favoritesCount"] += 1

        async for c in db.compare.find({}, {"customerId": 1, "userId": 1}):
            cid = c.get("customerId") or c.get("userId")
            if not cid: continue
            scores.setdefault(cid, {"id": cid, "favoritesCount": 0, "comparesCount": 0, "sharesCount": 0})
            scores[cid]["comparesCount"] += 1

        async for s in db.shares.find({"createdBy": {"$ne": None}}, {"createdBy": 1}):
            cid = s.get("createdBy")
            if not cid: continue
            scores.setdefault(cid, {"id": cid, "favoritesCount": 0, "comparesCount": 0, "sharesCount": 0})
            scores[cid]["sharesCount"] += 1

        out: List[Dict[str, Any]] = []
        for cid, agg in scores.items():
            cust = await db.customers.find_one(
                {"$or": [{"customerId": cid}, {"id": cid}, {"user_id": cid}]},
                {"_id": 0, "name": 1, "email": 1, "phone": 1}
            )
            score = agg["favoritesCount"] * 10 + agg["comparesCount"] * 5 + agg["sharesCount"] * 3
            level = "hot" if score >= 50 else ("warm" if score >= 20 else "cold")
            out.append({
                "id":             cid,
                "name":           (cust or {}).get("name")  or cid,
                "email":          (cust or {}).get("email") or "",
                "phone":          (cust or {}).get("phone") or "",
                "level":          level,
                "score":          score,
                "favoritesCount": agg["favoritesCount"],
                "comparesCount":  agg["comparesCount"],
                "sharesCount":    agg["sharesCount"],
            })
        out.sort(key=lambda r: r["score"], reverse=True)
        return out[:limit]
    except Exception as e:
        logger.warning(f"[engagement/top-users] {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────
# /top-vehicles  — ranked stock (with currentBid for sales context)
# ─────────────────────────────────────────────────────────────────────────
@router.get("/top-vehicles")
async def engagement_top_vehicles(limit: int = 50):
    """Top vehicles by favorites+compare+shares — real aggregation from
    the three collections, joined with `vin_data` for make/model/year
    and ``current_bid`` (gives the sales team commercial context next to
    raw engagement counts)."""
    db = _db()
    try:
        counts: Dict[str, Dict[str, int]] = {}

        async for f in db.favorites.find({}, {"vin": 1}):
            vin = (f.get("vin") or "").upper()
            if not vin: continue
            counts.setdefault(vin, {"f": 0, "c": 0, "s": 0})["f"] += 1

        async for c in db.compare.find({}, {"vin": 1, "vehicleId": 1}):
            vin = (c.get("vin") or c.get("vehicleId") or "").upper()
            if not vin: continue
            counts.setdefault(vin, {"f": 0, "c": 0, "s": 0})["c"] += 1

        async for s in db.shares.find({}, {"vin": 1}):
            vin = (s.get("vin") or "").upper()
            if not vin: continue
            counts.setdefault(vin, {"f": 0, "c": 0, "s": 0})["s"] += 1

        out: List[Dict[str, Any]] = []
        for vin, k in counts.items():
            v = await db.vin_data.find_one(
                {"vin": vin},
                {"_id": 0, "make": 1, "model": 1, "year": 1, "title": 1, "images": 1, "current_bid": 1},
            )
            out.append({
                "vin":            vin,
                "favoritesCount": k["f"],
                "comparesCount":  k["c"],
                "sharesCount":    k["s"],
                "viewsCount":     k["f"] + k["c"] + k["s"],   # heuristic proxy
                "make":           (v or {}).get("make"),
                "model":          (v or {}).get("model"),
                "year":           (v or {}).get("year"),
                "title":          (v or {}).get("title"),
                "image":          ((v or {}).get("images") or [None])[0],
                "currentBid":     (v or {}).get("current_bid"),
            })
        out.sort(key=lambda r: r["viewsCount"], reverse=True)
        return out[:limit]
    except Exception as e:
        logger.warning(f"[engagement/top-vehicles] {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────
# /vin-stats  — exact counts for one VIN
# ─────────────────────────────────────────────────────────────────────────
@router.get("/vin-stats")
async def engagement_vin_stats(vin: str = ""):
    """Exact engagement counts for ONE VIN, joined with vehicle metadata.
    Manager uses this to gauge interest before quoting a specific lot."""
    db = _db()
    raw = (vin or "").strip().upper().replace(" ", "").replace("-", "")
    if not raw:
        return {"vin": "", "favoritesCount": 0, "comparesCount": 0, "sharesCount": 0, "viewsCount": 0}
    try:
        f = await db.favorites.count_documents({"vin": raw})
        c = await db.compare.count_documents({"$or": [{"vin": raw}, {"vehicleId": raw}]})
        s = await db.shares.count_documents({"vin": raw})
        meta = await db.vin_data.find_one(
            {"vin": raw},
            {"_id": 0, "make": 1, "model": 1, "year": 1, "title": 1, "images": 1, "current_bid": 1},
        ) or {}
        return {
            "vin":            raw,
            "favoritesCount": f,
            "comparesCount":  c,
            "sharesCount":    s,
            "viewsCount":     f + c + s,
            "make":           meta.get("make"),
            "model":          meta.get("model"),
            "year":           meta.get("year"),
            "title":          meta.get("title"),
            "image":          (meta.get("images") or [None])[0],
            "currentBid":     meta.get("current_bid"),
        }
    except Exception as e:
        logger.warning(f"[engagement/vin-stats] {e}")
        return {"vin": raw, "favoritesCount": 0, "comparesCount": 0, "sharesCount": 0, "viewsCount": 0}


# ─────────────────────────────────────────────────────────────────────────
# /customer/{id}  — per-customer drill-down (full activity trail)
# Ported from the deleted manager_engagement router (Wave 7.5).
# ─────────────────────────────────────────────────────────────────────────
@router.get("/customer/{customer_id}")
async def engagement_customer_activity(customer_id: str, limit: int = 50):
    """Per-customer activity drill-down — the FULL trail of one customer.

    Returns the customer's favorites, comparisons, and shares ordered by
    most recent so a manager can see exactly which cars a client
    interacted with and when they abandoned the journey.
    """
    db = _db()
    try:
        cust = await db.customers.find_one(
            {"$or": [{"customerId": customer_id}, {"id": customer_id}, {"user_id": customer_id}]},
            {"_id": 0, "name": 1, "email": 1, "phone": 1, "createdAt": 1},
        )

        async def _enrich(vin: str) -> Dict[str, Any]:
            if not vin:
                return {}
            v = await db.vin_data.find_one(
                {"vin": vin},
                {"_id": 0, "make": 1, "model": 1, "year": 1, "title": 1, "images": 1, "current_bid": 1},
            )
            return v or {}

        favs: List[Dict[str, Any]] = []
        async for f in db.favorites.find(
            {"$or": [{"customerId": customer_id}, {"userId": customer_id}]}
        ).sort("createdAt", -1).limit(limit):
            vin = (f.get("vin") or "").upper()
            meta = await _enrich(vin)
            favs.append({
                "vin":        vin,
                "createdAt":  f.get("createdAt") or f.get("created_at"),
                "make":       meta.get("make"),
                "model":      meta.get("model"),
                "year":       meta.get("year"),
                "title":      meta.get("title"),
                "image":      (meta.get("images") or [None])[0],
                "currentBid": meta.get("current_bid"),
            })

        cmps: List[Dict[str, Any]] = []
        async for c in db.compare.find(
            {"$or": [{"customerId": customer_id}, {"userId": customer_id}]}
        ).sort("createdAt", -1).limit(limit):
            vin = (c.get("vin") or c.get("vehicleId") or "").upper()
            meta = await _enrich(vin)
            cmps.append({
                "vin":        vin,
                "createdAt":  c.get("createdAt") or c.get("created_at"),
                "make":       meta.get("make"),
                "model":      meta.get("model"),
                "year":       meta.get("year"),
                "title":      meta.get("title"),
                "image":      (meta.get("images") or [None])[0],
                "currentBid": meta.get("current_bid"),
            })

        shares: List[Dict[str, Any]] = []
        async for s in db.shares.find({"createdBy": customer_id}).sort("createdAt", -1).limit(limit):
            vin = (s.get("vin") or "").upper()
            meta = await _enrich(vin)
            shares.append({
                "vin":       vin,
                "channel":   s.get("channel") or s.get("medium") or "link",
                "createdAt": s.get("createdAt") or s.get("created_at"),
                "make":      meta.get("make"),
                "model":     meta.get("model"),
                "year":      meta.get("year"),
                "title":     meta.get("title"),
                "image":     (meta.get("images") or [None])[0],
            })

        score = len(favs) * 10 + len(cmps) * 5 + len(shares) * 3
        level = "hot" if score >= 50 else ("warm" if score >= 20 else "cold")

        return {
            "customerId": customer_id,
            "profile":    cust or {"name": customer_id},
            "level":      level,
            "score":      score,
            "favorites":  favs,
            "compares":   cmps,
            "shares":     shares,
            "counts": {
                "favorites": len(favs),
                "compares":  len(cmps),
                "shares":    len(shares),
            },
        }
    except Exception as e:
        logger.warning(f"[engagement/customer] {e}")
        return {
            "customerId": customer_id,
            "profile":    {},
            "level":      "cold",
            "score":      0,
            "favorites":  [],
            "compares":   [],
            "shares":     [],
            "counts":     {"favorites": 0, "compares": 0, "shares": 0},
        }
