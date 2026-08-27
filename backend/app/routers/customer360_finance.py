"""
customer360_finance.py - Customer-360 finance aggregation endpoints.

Provides 4 read-only endpoints that the Customer360 page consumes to
render new tabs (Invoices / Orders / Payments / Summary):

  GET  /api/customers/{customer_id}/invoices  - all invoices for customer
  GET  /api/customers/{customer_id}/orders    - all orders for customer
  GET  /api/customers/{customer_id}/payments  - all payments + refunds
  GET  /api/customers/{customer_id}/finance-summary - aggregate stats

Written as a focused Sprint 1.5 closeout for the Finance Core to surface
in Customer360 without changing any existing endpoint contracts.
"""
from __future__ import annotations

from typing import Any, Dict, List

import asyncio
from fastapi import APIRouter, HTTPException, Depends

from app.core.db_runtime import get_db
from security import require_user
from app.services.staff_acl import staff_can_see_customer

router = APIRouter(tags=["customer-360-finance"])


async def _load_customer_or_403(customer_id: str, current_user: Dict[str, Any]):
    """Fetch the customer and enforce staff object-ownership (S2.2).

    404 when the customer does not exist; 403 when the staff user is not
    allowed to see this customer (e.g. a manager requesting another
    manager's client). Returns the customer doc on success.
    """
    db = get_db()
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    if not staff_can_see_customer(current_user, customer):
        raise HTTPException(403, "Access denied: customer not in your book")
    return customer


async def _safe(coro, default=None):
    try:
        return await coro
    except Exception:
        return default if default is not None else []


def _customer_or_filter(customer: Dict[str, Any]) -> Dict[str, Any]:
    """Build flexible filter matching customer by id / customer_id / customerId."""
    cid = customer.get("id")
    or_clauses: List[dict] = [
        {"customerId": cid},
        {"customer_id": cid},
    ]
    if customer.get("email"):
        or_clauses.append({"customerEmail": customer["email"]})
    if customer.get("phone"):
        or_clauses.append({"customerPhone": customer["phone"]})
    return {"$or": or_clauses}


@router.get("/api/customers/{customer_id}/invoices")
async def customer360_invoices(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Return all invoices for a customer (newest first).

    Each invoice carries:
      id, customerId, managerId, items[], subtotal, total, currency,
      status (draft/sent/pending/paid/cancelled/refunded), due_date,
      created_at, paid_at, stripe_session_id, payment_url, utm_*
    """
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)

    flt = _customer_or_filter(customer)
    invoices = await _safe(
        db.invoices.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    )

    # Compact summary for the tab badge
    summary = {
        "total":   len(invoices),
        "paid":    sum(1 for i in invoices if (i.get("status") or "").lower() == "paid"),
        "pending": sum(1 for i in invoices if (i.get("status") or "").lower() in {"sent", "pending", "draft"}),
        "refunded": sum(1 for i in invoices if (i.get("status") or "").lower() == "refunded"),
        "totalAmount":   round(sum(float(i.get("total") or i.get("amount") or 0) for i in invoices), 2),
        "paidAmount":    round(sum(float(i.get("total") or i.get("amount") or 0) for i in invoices if (i.get("status") or "").lower() == "paid"), 2),
    }
    return {"success": True, "items": invoices, "summary": summary}


@router.get("/api/customers/{customer_id}/orders")
async def customer360_orders(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Return all orders (service workflows) for a customer.

    An order is born from a paid invoice via
    ``app/services/orders.py::create_order_from_invoice``.

    Each order doc carries: id, invoiceId, status, items[], steps[],
    managerId, amount, currency, started_at, completed_at.
    """
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)

    flt = _customer_or_filter(customer)
    orders = await _safe(
        db.orders.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    )

    def _progress(o: Dict[str, Any]) -> int:
        steps = o.get("steps") or []
        if not steps:
            return 0
        done = sum(1 for s in steps if (s.get("status") or "").lower() in {"done", "completed"})
        return round((done / max(len(steps), 1)) * 100)

    for o in orders:
        o["progress_pct"] = _progress(o)

    summary = {
        "total":       len(orders),
        "inProgress":  sum(1 for o in orders if (o.get("status") or "").lower() in {"in_progress", "new", "waiting_client"}),
        "completed":   sum(1 for o in orders if (o.get("status") or "").lower() == "completed"),
        "cancelled":   sum(1 for o in orders if (o.get("status") or "").lower() == "cancelled"),
    }
    return {"success": True, "items": orders, "summary": summary}


@router.get("/api/customers/{customer_id}/payments")
async def customer360_payments(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Return all Stripe payment records for a customer.

    Payments live in ``db.payments`` and are written by Stripe webhooks
    (``checkout.session.completed``, ``payment_intent.succeeded``,
    ``charge.refunded``). Each carries amount, currency, status,
    invoice_id, payment_intent, refunded_amount.
    """
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)

    flt = _customer_or_filter(customer)
    payments = await _safe(
        db.payments.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    )

    summary = {
        "total":          len(payments),
        "succeeded":      sum(1 for p in payments if (p.get("status") or "").lower() in {"succeeded", "paid"}),
        "refunded":       sum(1 for p in payments if (p.get("status") or "").lower() == "refunded"),
        "failed":         sum(1 for p in payments if (p.get("status") or "").lower() in {"failed", "canceled"}),
        "totalAmount":    round(sum(float(p.get("amount") or 0) for p in payments if (p.get("status") or "").lower() in {"succeeded", "paid"}), 2),
        "refundedAmount": round(sum(float(p.get("refunded_amount") or 0) for p in payments), 2),
    }
    return {"success": True, "items": payments, "summary": summary}


@router.get("/api/customers/{customer_id}/finance-summary")
async def customer360_finance_summary(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Aggregate finance health for Customer360 header KPIs.

    Pulls invoices + orders + payments + deposits in parallel and
    returns one compact summary object.
    """
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)

    flt = _customer_or_filter(customer)
    by_cid = {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}]}

    invoices, orders, payments, deposits = await asyncio.gather(
        _safe(db.invoices.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.orders.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.payments.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.legal_deposits.find(by_cid, {"_id": 0}).to_list(length=200)),
    )

    def _num(v): 
        try: return float(v or 0)
        except Exception: return 0.0

    inv_paid = sum(_num(i.get("total") or i.get("amount")) for i in invoices if (i.get("status") or "").lower() == "paid")
    inv_open = sum(_num(i.get("total") or i.get("amount")) for i in invoices if (i.get("status") or "").lower() in {"sent", "pending"})

    pay_in   = sum(_num(p.get("amount")) for p in payments if (p.get("status") or "").lower() in {"succeeded", "paid"})
    pay_ref  = sum(_num(p.get("refunded_amount") or p.get("amount")) for p in payments if (p.get("status") or "").lower() == "refunded")

    dep_active = sum(_num(d.get("amount")) for d in deposits if (d.get("status") or "").lower() in {"confirmed", "paid", "received"})

    return {
        "success": True,
        "summary": {
            "invoicesTotal":        len(invoices),
            "invoicesPaid":         sum(1 for i in invoices if (i.get("status") or "").lower() == "paid"),
            "invoicesPending":      sum(1 for i in invoices if (i.get("status") or "").lower() in {"sent", "pending", "draft"}),
            "invoicesPaidAmount":   round(inv_paid, 2),
            "invoicesOpenAmount":   round(inv_open, 2),
            "ordersTotal":          len(orders),
            "ordersInProgress":     sum(1 for o in orders if (o.get("status") or "").lower() in {"in_progress", "new", "waiting_client"}),
            "ordersCompleted":      sum(1 for o in orders if (o.get("status") or "").lower() == "completed"),
            "paymentsTotal":        len(payments),
            "paymentsCollected":    round(pay_in, 2),
            "paymentsRefunded":     round(pay_ref, 2),
            "depositsActive":       sum(1 for d in deposits if (d.get("status") or "").lower() in {"confirmed", "paid", "received"}),
            "depositsActiveAmount": round(dep_active, 2),
        },
    }
