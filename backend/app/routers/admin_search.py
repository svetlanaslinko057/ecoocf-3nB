"""
admin_search — /api/admin/search HTTP surface
==============================================

Wave 2B / Batch 8 / Commit 14 (Bottom singletons, 2/4).

Mechanical 1:1 extraction of the admin search-analytics endpoint.
The original endpoint at server.py:12135 is preserved byte-for-byte.

Architectural note — read-only analytics over `search_logs`:
  The `search_logs` collection is WRITTEN by the public VIN-search
  endpoint in server.py (`log_vin_search()`).  This router only READS
  it for aggregation/analytics, so collection ownership is NOT
  transferred here — same pattern as `admin_orders` (Batch 8 sibling)
  and the pre-emptive Batch 9 `read aggregation allowed` rule.

Auth: `require_admin` (hoisted via APIRouter `dependencies=[]`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from security import require_admin

logger = logging.getLogger("bibi.admin_search")


def _db():
    """Lazy bridge to the live Mongo handle in server.py (Wave 1 pattern)."""
    from app.core.db_runtime import get_db  # noqa: E402 (C-4e: lazy-bridge → accessor)
    return get_db()


router = APIRouter(
    prefix="/api/admin/search",
    tags=["admin-search"],
    dependencies=[Depends(require_admin)],
)


@router.get("/analytics")
async def admin_search_analytics(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
):
    """Return search-demand analytics for the last `days` days.

    - totals: total searches, found vs missed
    - top VINs searched (hot demand — drive sourcing decisions)
    - top missed VINs (pure demand signal → potential leads)
    """
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=int(days))
    try:
        total = await db.search_logs.count_documents({"ts": {"$gte": since}})
        misses = await db.search_logs.count_documents({"ts": {"$gte": since}, "found": False})
        # Top queried VINs (any kind)
        top_cursor = db.search_logs.aggregate([
            {"$match": {"ts": {"$gte": since}, "clean": {"$ne": ""}}},
            {"$group": {"_id": "$clean", "count": {"$sum": 1}, "miss": {"$sum": {"$cond": ["$found", 0, 1]}}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ])
        top = await top_cursor.to_list(length=limit)
        # Top missed (pure demand)
        miss_cursor = db.search_logs.aggregate([
            {"$match": {"ts": {"$gte": since}, "clean": {"$ne": ""}, "found": False}},
            {"$group": {"_id": "$clean", "count": {"$sum": 1}, "last_ts": {"$max": "$ts"}}},
            {"$sort": {"count": -1, "last_ts": -1}},
            {"$limit": limit},
        ])
        top_misses = await miss_cursor.to_list(length=limit)

        # Serialize
        def _fmt(rows):
            out = []
            for r in rows:
                row = {"query": r.get("_id"), "count": r.get("count", 0)}
                if "miss" in r:
                    row["miss"] = r["miss"]
                if "last_ts" in r and hasattr(r["last_ts"], "isoformat"):
                    row["last_ts"] = r["last_ts"].isoformat()
                out.append(row)
            return out

        return {
            "success": True,
            "range_days": int(days),
            "totals": {"total": total, "misses": misses, "found": total - misses},
            "top_queries": _fmt(top),
            "top_misses": _fmt(top_misses),
        }
    except Exception as e:
        logger.warning(f"[search-analytics] failed: {e}")
        return {"success": False, "error": str(e)[:120]}
