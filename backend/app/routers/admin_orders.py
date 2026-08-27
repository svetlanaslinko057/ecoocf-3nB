"""
admin_orders — /api/admin/orders HTTP surface
=============================================

Wave 2B / Batch 8 / Commit 14 (Bottom singletons, 1/4).

Mechanical 1:1 extraction of a single admin READ-ONLY endpoint over the
`orders` Mongo collection.  The original endpoint at server.py:14714 is
preserved byte-for-byte.

Architectural note — cross-boundary read into Cluster #1:
  `orders` is part of the OPERATIONAL CORE (Cluster #1 in Wave 2A).
  Wave 2B discipline allows this extraction because the endpoint is a
  **read-only aggregation** (list + filter + count) over the collection,
  with NO writes, NO mutations, and NO ownership transfer.  This is the
  approved pattern that will be formalised more strongly in Batch 9
  (admin_metrics) as:

      "read aggregation is allowed; ownership mutation is not"

  Ownership of the `orders` collection remains in server.py until
  Phase 3 (operational-core disentangling) splits Cluster #1.  No
  bridge mutates `orders` from this router.

Auth: `require_admin` (hoisted via APIRouter `dependencies=[]`).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from security import require_admin


def _db():
    """Lazy bridge to the live Mongo handle in server.py (Wave 1 pattern)."""
    from app.core.db_runtime import get_db  # noqa: E402 (C-4e: lazy-bridge → accessor)
    return get_db()


router = APIRouter(
    prefix="/api/admin/orders",
    tags=["admin-orders"],
    dependencies=[Depends(require_admin)],
)


# Admin / staff order list (master admin sees everything)
@router.get("")
async def admin_list_orders(status: str = "", manager_id: str = "", q: str = "", limit: int = 200):
    db = _db()
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if manager_id:
        query["managerId"] = manager_id
    if q:
        query["$or"] = [
            {"customerId": {"$regex": q, "$options": "i"}},
            {"invoiceId": {"$regex": q, "$options": "i"}},
            {"id": {"$regex": q, "$options": "i"}},
        ]
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    return {"success": True, "items": items, "total": await db.orders.count_documents(query)}
