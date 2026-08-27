"""
Customer Timeline router — Sprint 4
====================================

Returns the unified Timeline view for a customer. We combine two
sources:

* ``customer_timeline_events`` — explicit events recorded by other
  services (the new canonical store).
* Legacy synthesis from invoices / orders / payments / customer
  themselves — so that customers created BEFORE Sprint 4 still have
  a populated timeline without backfilling.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.db_runtime import get_db
from app.services import customer_timeline as svc
from security import require_manager_or_admin

router = APIRouter(tags=["customer-timeline"])


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


async def _synthesise_legacy_events(customer_id: str) -> List[Dict[str, Any]]:
    """Build events from base CRM collections for backwards-compat.

    Cheap best-effort projection — only the most useful fields. Each
    synthesised event reuses the same kind taxonomy so the FE renders
    them identically.
    """
    db = get_db()
    out: List[Dict[str, Any]] = []

    # Customer created
    try:
        cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
        if cust and cust.get("created_at"):
            out.append({
                "id": f"legacy_cust_{customer_id}",
                "customer_id": customer_id,
                "kind": "customer_created",
                "title": "Customer created",
                "body": cust.get("firstName") or cust.get("email"),
                "ref": {"collection": "customers", "id": customer_id},
                "created_at": _iso(cust["created_at"]),
                "actor": None, "meta": {},
            })
    except Exception:
        pass

    # Invoices (created + paid)
    try:
        async for inv in db.invoices.find({"customerId": customer_id}, {"_id": 0}):
            iid = inv.get("id")
            if inv.get("created_at"):
                out.append({
                    "id": f"legacy_inv_c_{iid}",
                    "customer_id": customer_id,
                    "kind": "invoice_created",
                    "title": f"Invoice #{inv.get('number') or iid[:8]} created",
                    "ref": {"collection": "invoices", "id": iid},
                    "created_at": _iso(inv["created_at"]),
                    "meta": {"amount": inv.get("amount") or inv.get("total"), "currency": inv.get("currency")},
                    "actor": None,
                })
            paid_at = inv.get("paid_at") or inv.get("paidAt")
            if (inv.get("status") or "").lower() in {"paid", "completed"} and paid_at:
                out.append({
                    "id": f"legacy_inv_p_{iid}",
                    "customer_id": customer_id,
                    "kind": "invoice_paid",
                    "title": f"Invoice #{inv.get('number') or iid[:8]} paid",
                    "ref": {"collection": "invoices", "id": iid},
                    "created_at": _iso(paid_at),
                    "meta": {"amount": inv.get("amount") or inv.get("total"), "currency": inv.get("currency")},
                    "actor": None,
                })
    except Exception:
        pass

    # Orders
    try:
        async for o in db.orders.find({"customerId": customer_id}, {"_id": 0}):
            if o.get("created_at"):
                out.append({
                    "id": f"legacy_ord_{o.get('id')}",
                    "customer_id": customer_id,
                    "kind": "order_created",
                    "title": f"Order #{(o.get('id') or '')[-8:]} created",
                    "ref": {"collection": "orders", "id": o.get("id")},
                    "created_at": _iso(o["created_at"]),
                    "meta": {"items": len(o.get("items") or [])},
                    "actor": None,
                })
    except Exception:
        pass

    # Payments
    try:
        async for p in db.payments.find({"customerId": customer_id}, {"_id": 0}):
            if p.get("created_at") or p.get("paidAt"):
                out.append({
                    "id": f"legacy_pay_{p.get('id')}",
                    "customer_id": customer_id,
                    "kind": "payment_received",
                    "title": f"Payment received",
                    "ref": {"collection": "payments", "id": p.get("id")},
                    "created_at": _iso(p.get("paidAt") or p.get("created_at")),
                    "meta": {"amount": p.get("amount"), "currency": p.get("currency")},
                    "actor": None,
                })
    except Exception:
        pass

    # Deals (for backwards-compat with legacy /timeline consumers)
    try:
        async for d in db.deals.find(
            {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            {"_id": 0},
        ).sort("created_at", -1):
            out.append({
                "id": f"legacy_deal_{d.get('id')}",
                "customer_id": customer_id,
                "kind": "lead_converted",
                "title": d.get("title") or d.get("name") or "Deal",
                "ref": {"collection": "deals", "id": d.get("id")},
                "created_at": _iso(d.get("created_at")),
                "meta": {"stage": d.get("stage"), "value": d.get("value")},
                "actor": None,
            })
    except Exception:
        pass

    return out


@router.get("/api/customers/{customer_id}/timeline",
            dependencies=[Depends(require_manager_or_admin)])
async def get_customer_timeline(
    customer_id: str,
    kinds: Optional[str] = Query(None, description="comma-separated kinds filter"),
    limit: int = 200,
):
    db = get_db()
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")

    kind_filter = [k.strip() for k in kinds.split(",")] if kinds else None
    explicit = await svc.list_for_customer(customer_id, kinds=kind_filter, limit=limit)
    legacy = await _synthesise_legacy_events(customer_id)
    if kind_filter:
        legacy = [e for e in legacy if e.get("kind") in kind_filter]

    # Merge & sort by created_at desc, dedupe by id
    by_id: Dict[str, Dict[str, Any]] = {}
    for ev in explicit + legacy:
        if ev.get("id"):
            by_id[ev["id"]] = ev
    merged = list(by_id.values())
    merged.sort(key=lambda e: (e.get("created_at") or ""), reverse=True)
    merged = merged[:limit]

    # Kind breakdown for the FE filter pills
    breakdown: Dict[str, int] = {}
    for e in merged:
        k = e.get("kind") or "unknown"
        breakdown[k] = breakdown.get(k, 0) + 1

    # Backwards-compat: legacy consumers expect ``events`` with
    # ``{type, at, title, ref}`` shape — synthesise that view too.
    legacy_view = [{
        "type": e.get("kind"),
        "at": e.get("created_at"),
        "title": e.get("title"),
        "ref": (e.get("ref") or {}).get("id"),
        "data": e,
    } for e in merged]

    return {
        "success": True,
        "items": merged,
        "events": legacy_view,
        "data": legacy_view,
        "total": len(merged),
        "breakdown": breakdown,
        "available_kinds": sorted(svc.EVENT_KINDS),
    }
