"""
admin_predictive_leads — /api/admin/predictive-leads HTTP surface
===================================================================

Wave 2B / Batch 11 / Commit 17 — read-only aggregators bundle (4/5).

Mechanical 1:1 extraction of the predictive-leads bucket endpoint.
The original at server.py:14879-14886 is preserved byte-for-byte
(only `db = _db()` lazy line added).

────────────────────────────────────────────────────────────────────────
Audit verdict — PURE READ-ONLY (Phase 3 preview rule satisfied)
────────────────────────────────────────────────────────────────────────

Single endpoint reads `db.leads.find()` with a score-bucket filter:
  GET /api/admin/predictive-leads/bucket/{bucket}

Reads Cluster #1 `leads` collection — `find` with projection + `limit`
only, no mutation, no helpers, no bridge to writers.  All 4 conditions
of the Phase 3 preview rule hold.

Note: `admin_metrics` (Batch 9) and `admin_orders` (Batch 8) already
established the precedent of read-only `find` over Cluster #1
collections.  This is a direct application of the same rule.

Auth: `require_admin` (router-level, same as original decorator).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from security import require_admin


def _db():
    """Lazy bridge to the live Mongo handle in server.py (Wave 1 pattern)."""
    from app.core.db_runtime import get_db  # noqa: E402 (C-4e: lazy-bridge → accessor)
    return get_db()


router = APIRouter(
    prefix="/api/admin/predictive-leads",
    tags=["admin-predictive-leads"],
    dependencies=[Depends(require_admin)],
)


@router.get("/bucket/{bucket}")
async def predictive_leads_bucket(bucket: str):
    """Get predictive leads by bucket"""
    db = _db()
    score_range = {"hot": {"$gte": 80}, "warm": {"$gte": 50, "$lt": 80}, "cold": {"$lt": 50}}
    query = {"score": score_range.get(bucket, {})} if bucket in score_range else {}
    cursor = db.leads.find(query, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}
