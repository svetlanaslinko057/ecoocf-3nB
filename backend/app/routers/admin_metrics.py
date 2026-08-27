"""
admin_metrics — /api/admin/metrics HTTP surface
================================================

Wave 2B / Batch 9 / Commit 15 — `admin_metrics` SOLO (reconnaissance).

Mechanical 1:1 extraction of the admin business-metrics endpoint
(`GET /api/admin/metrics`).  The original endpoint at server.py:14922
is preserved byte-for-byte.

────────────────────────────────────────────────────────────────────────
Why this is the **reconnaissance** batch — not just another singleton
────────────────────────────────────────────────────────────────────────

Batch 9 is the **first test** of the "read aggregation allowed,
ownership mutation NOT" rule formalised at the end of Batch 8
(REFACTOR_DEPENDENCIES.md → "Phase 3 preview rule").

Unlike Batch 8 (`admin_orders`, `admin_search`), which each touched a
single Cluster #1 collection in pure read mode, `admin_metrics` is
the first router that:

  * reads from **TWO Cluster #1 collections** in a single endpoint
    (`db.invoices` AND `db.orders`),
  * computes **cross-domain KPIs** (conversion = invoices vs orders,
    repeat-rate = customers vs orders),
  * is the structural template every future analytics router will
    follow (admin overview / KPI dashboards / management reports).

If `admin_metrics` extracts cleanly under the read-aggregation rule,
the rule is **proven** for cross-domain read models, and Batch 10
(`admin_services`, `admin_workflow_templates`) can proceed.

If `admin_metrics` reveals **any** mutation, helper coupling, or
shared-state side-effect — extraction halts and the endpoint is
recorded as a Phase 3 blocker, NOT extracted.

────────────────────────────────────────────────────────────────────────
Audit result (recorded for the topology report)
────────────────────────────────────────────────────────────────────────

| Probe                                       | Result    |
|---------------------------------------------|-----------|
| `update_one` / `update_many`                | NONE      |
| `insert_one` / `insert_many`                | NONE      |
| `delete_one` / `delete_many`                | NONE      |
| `find_one_and_update` / `replace` / `delete`| NONE      |
| `create_index` / `drop_index`               | NONE      |
| `bulk_write` / transactional ops            | NONE      |
| Lazy writer bridges (e.g. `_get_or_create_*`)| NONE     |
| `_ensure_*` / `_audit_*` side-effect calls  | NONE      |
| Server.py helper imports                    | NONE      |
| Foreign collections written                 | NONE      |
| Foreign collections read                    | invoices, orders (Cluster #1) |
| Operations used                             | count_documents ×2, find ×1, aggregate ×1 |

→ Verdict: **PURE READ-ONLY CROSS-DOMAIN AGGREGATION** — extraction
   matches Phase 3 preview rule exactly.  All 4 conditions hold:

   1. read-only access path                                 ✅
   2. no index manipulation on foreign collection           ✅
   3. no bridge to a writer                                 ✅
   4. no transactional coupling with a server.py writer     ✅

────────────────────────────────────────────────────────────────────────
Bridge surface (single bridge, lazy)
────────────────────────────────────────────────────────────────────────

`_db()` — lazy import of `db` from server.py, identical pattern as
`admin_orders`, `admin_search`, `admin_history_reports`, etc.  No new
bridge type introduced by Batch 9.  Ownership of `invoices` and
`orders` collections remains in server.py / Cluster #1 until Phase 3
operational-core disentangling assigns canonical owners.

────────────────────────────────────────────────────────────────────────
Auth
────────────────────────────────────────────────────────────────────────

`require_admin` (hoisted via APIRouter `dependencies=[...]`), identical
to original `@fastapi_app.get(..., dependencies=[Depends(require_admin)])`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from security import require_admin


def _db():
    """Lazy bridge to the live Mongo handle in server.py (Wave 1 pattern)."""
    from app.core.db_runtime import get_db  # noqa: E402 (C-4e: lazy-bridge → accessor)
    return get_db()


router = APIRouter(
    prefix="/api/admin/metrics",
    tags=["admin-metrics"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
async def admin_business_metrics():
    """Three KPI metrics requested by product spec:
      • conversion     = paid_invoices / sent_invoices
      • avg_order_time = avg(completedAt − created_at) of completed orders (hours)
      • repeat_rate    = users_with_2+_orders / users_with_any_order

    Plus raw counts so the UI can also show "8 / 12 invoices paid" etc.
    """
    db = _db()
    # ── conversion ───────────────────────────────────────────────
    # "sent" universe = everything that left the draft stage
    sent_statuses = ["sent", "pending", "paid", "overdue", "cancelled"]
    sent_count = await db.invoices.count_documents({"status": {"$in": sent_statuses}})
    paid_count = await db.invoices.count_documents({"status": "paid"})
    conversion = round(paid_count / sent_count, 4) if sent_count else 0.0

    # ── avg_order_time ───────────────────────────────────────────
    now = datetime.now(timezone.utc)
    completed_orders = []
    async for o in db.orders.find({"status": "completed"}, {"_id": 0, "created_at": 1, "completedAt": 1}):
        try:
            ca = o.get("created_at")
            co = o.get("completedAt")
            if not ca or not co:
                continue
            a = datetime.fromisoformat(str(ca).replace("Z", "+00:00"))
            b = datetime.fromisoformat(str(co).replace("Z", "+00:00"))
            delta_h = (b - a).total_seconds() / 3600.0
            if delta_h >= 0:
                completed_orders.append(delta_h)
        except Exception:
            continue
    avg_order_time_h = round(sum(completed_orders) / len(completed_orders), 2) if completed_orders else None

    # ── repeat_rate ──────────────────────────────────────────────
    pipeline = [
        {"$match": {"customerId": {"$ne": None}}},
        {"$group": {"_id": "$customerId", "cnt": {"$sum": 1}}},
    ]
    counts = [c async for c in db.orders.aggregate(pipeline)]
    total_customers = len(counts)
    repeat_customers = sum(1 for c in counts if (c.get("cnt") or 0) >= 2)
    repeat_rate = round(repeat_customers / total_customers, 4) if total_customers else 0.0

    return {
        "success": True,
        "generated_at": now.isoformat(),
        "metrics": {
            "conversion": {
                "value": conversion,
                "paid": paid_count,
                "sent": sent_count,
                "label": "paid / sent invoices",
            },
            "avg_order_time": {
                "value_hours": avg_order_time_h,
                "completed_orders": len(completed_orders),
                "label": "avg(completedAt − created_at) of completed orders",
            },
            "repeat_rate": {
                "value": repeat_rate,
                "repeat_customers": repeat_customers,
                "total_customers": total_customers,
                "label": "customers with 2+ orders / total customers",
            },
        },
    }
