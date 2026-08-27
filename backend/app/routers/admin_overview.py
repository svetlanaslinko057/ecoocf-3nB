"""
admin_overview — /api/admin/overview HTTP surface
==================================================

Wave 2B / Batch 11 / Commit 17 — read-only aggregators bundle (3/5).

Mechanical 1:1 extraction of the admin overview endpoint.  The original
at server.py:14866-14877 is preserved byte-for-byte (only `db = _db()`
lazy line added).

────────────────────────────────────────────────────────────────────────
Audit verdict — PURE READ-ONLY (Phase 3 preview rule satisfied)
────────────────────────────────────────────────────────────────────────

Single endpoint computes 4 counts in parallel:
  GET /api/admin/overview
    → db.leads.count_documents({})
    → db.customers.count_documents({})
    → db.deals.count_documents({})
    → db.vin_data.count_documents({})

All 4 are Cluster #1 collections.  This is a 4-way cross-domain reader
under the `admin_metrics` (Batch 9) precedent.  All 4 conditions of
the Phase 3 preview rule hold (count_documents only — no mutation, no
index manipulation, no writer bridge, no transactional coupling).

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
    prefix="/api/admin/overview",
    tags=["admin-overview"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
async def admin_overview():
    """Admin overview"""
    db = _db()
    return {
        "success": True,
        "overview": {
            "leads": await db.leads.count_documents({}),
            "customers": await db.customers.count_documents({}),
            "deals": await db.deals.count_documents({}),
            "vehicles": await db.vin_data.count_documents({})
        }
    }
