"""Contract Execution Engine — invoicing.

Generates invoices from the schedule, tied to the contract:
  * per PERIOD  (invoice_scope="per_period")
  * per ACT     (invoice_scope="per_act")

Invoices are written to the canonical ``invoices`` collection with the same
core shape used across the app (so CrmInvoices / client cabinet render them)
PLUS engine links: ``contract_id`` / ``period_id`` / ``act_id`` /
``invoice_scope``. Financials (invoiced / paid / remaining) then pick them up
via ``financials.recompute``.

Guarantees:
  * IDEMPOTENT — one active (non-cancelled) invoice per (period) or (act).
  * ZERO-PRICE PROTECTION — refuses to bill any line that has quantity > 0 but
    no effective price (requires a manual override first).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

from . import constants as K
from . import financials as FIN
from .calc import effective_price
from .util import now_iso, num, round2


class BillingError(Exception):
    """Raised for zero-price / empty-invoice / duplicate billing problems."""


def _billable_price(line: Dict[str, Any]) -> float:
    p = effective_price(line)
    ap = line.get("actual_price_per_kg")
    if (p is None or p <= 0) and ap is not None:
        p = num(ap)
    return num(p)


def _bill_price(line: Dict[str, Any], basis: str) -> float:
    """Price used for billing a line. PLANNED billing uses the planned/effective
    price only (a code with no tariff -> 0 -> must be overridden). ACTUAL billing
    may fall back to the price recorded on the act."""
    if basis == "actual":
        return _billable_price(line)
    return num(effective_price(line))


def assert_no_zero_price(lines: List[Dict[str, Any]], basis: str) -> None:
    """Every line with qty>0 must have a billing price>0 (else needs override)."""
    field = "actual_kg" if basis == "actual" else "planned_kg"
    bad = []
    for l in lines or []:
        if num(l.get(field)) > 0 and _bill_price(l, basis) <= 0:
            bad.append(l.get("waste_code") or l.get("name") or "?")
    if bad:
        raise BillingError(
            "Ціна не встановлена (потрібен ручний override) для кодів: " + ", ".join(bad)
        )


async def assert_contract_signable(contract_id: str, *, db=None) -> None:
    """Guard used before a contract is signed: an engine contract with a
    schedule may NOT be signed while any planned line lacks a price."""
    db = get_db() if db is None else db
    periods = await db[K.C_PERIODS].find({"contract_id": contract_id}, {"_id": 0}).to_list(length=500)
    for p in periods:
        assert_no_zero_price(p.get("lines") or [], "planned")


def _next_invoice_number(seq: int) -> str:
    return f"INV-{datetime.now(timezone.utc).year}-{seq:05d}"


async def _customer_stamp(db, contract: Dict[str, Any]) -> Dict[str, Any]:
    cid = contract.get("customer_id") or contract.get("customerId")
    stamp = {"customerId": cid, "company_id": contract.get("company_id")}
    try:
        q = [{"id": cid}, {"customerId": cid}]
        if contract.get("company_id"):
            q.append({"company_id": contract["company_id"]})
        cust = await db["customers"].find_one({"$or": q}, {"_id": 0})
        if cust:
            stamp["customerId"] = cust.get("id") or cust.get("customerId") or cid
            stamp["customerEmail"] = cust.get("email")
            stamp["customerName"] = cust.get("name") or cust.get("company_name")
            if cust.get("company_id"):
                stamp["company_id"] = cust.get("company_id")
    except Exception:
        pass
    return stamp


def _period_items(period: Dict[str, Any], basis: str) -> List[Dict[str, Any]]:
    qty_field = "actual_kg" if basis == "actual" else "planned_kg"
    items: List[Dict[str, Any]] = []
    for l in period.get("lines") or []:
        qty = num(l.get(qty_field))
        if qty <= 0:
            continue
        price = _bill_price(l, basis)
        items.append({
            "id": str(uuid.uuid4()),
            "waste_code": l.get("waste_code"),
            "name": f"{l.get('waste_code')} · {l.get('name') or ''}".strip(" ·"),
            "price": round2(price), "qty": qty, "unit": "kg",
            "line_total": round2(price * qty),
        })
    for e in period.get("extra_works") or []:
        amt = num(e.get("amount"))
        if amt == 0:
            continue
        items.append({
            "id": str(uuid.uuid4()),
            "name": e.get("label") or K.EXTRA_WORK_LABELS_UK.get(e.get("type"), "Дод. роботи"),
            "extra_type": e.get("type"), "price": round2(amt), "qty": num(e.get("qty"), 1.0) or 1.0,
            "line_total": round2(amt), "workflow": "extra",
        })
    return items


def _act_items(act: Dict[str, Any], period: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    plines = {l.get("waste_code"): l for l in ((period or {}).get("lines") or [])}
    raw = act.get("lines") or act.get("items") or []
    for it in raw:
        code = (it.get("waste_code") or it.get("code") or "").strip()
        qty = num(it.get("actual_kg") if it.get("actual_kg") is not None else it.get("qty"))
        if not code or qty <= 0:
            continue
        price = num(it.get("price_per_kg")) if it.get("price_per_kg") is not None else 0.0
        if price <= 0 and code in plines:
            price = _billable_price(plines[code])
        items.append({
            "id": str(uuid.uuid4()), "waste_code": code,
            "name": f"{code} (акт {act.get('number','')})".strip(),
            "price": round2(price), "qty": qty, "unit": "kg", "line_total": round2(price * qty),
        })
    for e in act.get("extra_works") or []:
        amt = num(e.get("amount"))
        if amt == 0:
            continue
        items.append({
            "id": str(uuid.uuid4()), "extra_type": e.get("type"),
            "name": e.get("label") or K.EXTRA_WORK_LABELS_UK.get(e.get("type"), "Дод. роботи"),
            "price": round2(amt), "qty": 1.0, "line_total": round2(amt), "workflow": "extra",
        })
    return items


async def _insert_invoice(db, contract, links, items, by, due_date) -> Dict[str, Any]:
    total = round2(sum(num(i.get("line_total")) for i in items))
    if total <= 0 or not items:
        raise BillingError("Немає позицій для виставлення рахунку")
    seq = await db[K.C_INVOICES].count_documents({}) + 1
    stamp = await _customer_stamp(db, contract)
    inv = {
        "id": f"inv_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}",
        "invoice_number": _next_invoice_number(seq),
        "number": _next_invoice_number(seq),
        "items": items, "amount": total, "total": total,
        "currency": contract.get("currency") or "UAH",
        "status": "pending",
        "contract_id": contract["id"],
        "created_at": now_iso(),
        "created_by": (by or {}).get("email") or (by or {}).get("id"),
        "description": f"Договір {contract.get('number','')}",
        **links, **stamp,
    }
    await db[K.C_INVOICES].insert_one(dict(inv))
    inv.pop("_id", None)
    return inv


async def generate_period_invoice(
    contract_id: str, period_id: str, *, basis: str = "planned",
    due_date=None, by=None, force: bool = False, db=None,
) -> Dict[str, Any]:
    db = get_db() if db is None else db
    contract = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract:
        raise BillingError("Договір не знайдено")
    period = await db[K.C_PERIODS].find_one({"id": period_id, "contract_id": contract_id}, {"_id": 0})
    if not period:
        raise BillingError("Період не знайдено")

    existing = await db[K.C_INVOICES].find_one({
        "contract_id": contract_id, "period_id": period_id, "invoice_scope": "per_period",
        "status": {"$nin": list(K.CANCELLED_INVOICE_STATUSES)},
    }, {"_id": 0})
    if existing and not force:
        return {"invoice": existing, "idempotent": True,
                "financials": await FIN.recompute(contract_id, db=db)}

    assert_no_zero_price(period.get("lines") or [], basis)
    items = _period_items(period, basis)
    inv = await _insert_invoice(
        db, contract,
        {"period_id": period_id, "invoice_scope": "per_period", "basis": basis},
        items, by, due_date,
    )
    await db[K.C_PERIODS].update_one({"id": period_id}, {"$addToSet": {"linked_invoice_ids": inv["id"]}})
    fin = await FIN.recompute(contract_id, db=db)
    return {"invoice": inv, "idempotent": False, "financials": fin}


async def generate_act_invoice(
    contract_id: str, act_id: str, *, by=None, force: bool = False, db=None,
) -> Dict[str, Any]:
    db = get_db() if db is None else db
    contract = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract:
        raise BillingError("Договір не знайдено")
    act = await db[K.C_ACTS].find_one({"id": act_id, "contract_id": contract_id}, {"_id": 0})
    if not act:
        raise BillingError("Акт не знайдено")
    if act.get("status") not in K.SIGNED_ACT_STATUSES:
        raise BillingError("Рахунок можна виставити лише за підписаним актом")

    existing = await db[K.C_INVOICES].find_one({
        "contract_id": contract_id, "act_id": act_id, "invoice_scope": "per_act",
        "status": {"$nin": list(K.CANCELLED_INVOICE_STATUSES)},
    }, {"_id": 0})
    if existing and not force:
        return {"invoice": existing, "idempotent": True,
                "financials": await FIN.recompute(contract_id, db=db)}

    period = None
    if act.get("period_id"):
        period = await db[K.C_PERIODS].find_one({"id": act["period_id"]}, {"_id": 0})
    items = _act_items(act, period)
    # zero-price guard on the act items themselves
    for it in items:
        if it.get("waste_code") and num(it.get("qty")) > 0 and num(it.get("price")) <= 0:
            raise BillingError(f"Ціна не встановлена для коду {it.get('waste_code')} (потрібен ручний override)")
    inv = await _insert_invoice(
        db, contract,
        {"act_id": act_id, "period_id": act.get("period_id"), "invoice_scope": "per_act"},
        items, by, None,
    )
    if act.get("period_id"):
        await db[K.C_PERIODS].update_one({"id": act["period_id"]}, {"$addToSet": {"linked_invoice_ids": inv["id"]}})
    fin = await FIN.recompute(contract_id, db=db)
    return {"invoice": inv, "idempotent": False, "financials": fin}


async def set_invoice_status(contract_id: str, invoice_id: str, status: str, *, db=None) -> Dict[str, Any]:
    """Update a linked invoice's status (pending/paid/partial/cancelled) and reconcile.
    For partial payments pass status='partial' with amount_paid handled by caller."""
    db = get_db() if db is None else db
    inv = await db[K.C_INVOICES].find_one({"id": invoice_id, "contract_id": contract_id}, {"_id": 0})
    if not inv:
        raise BillingError("Рахунок не знайдено")
    await db[K.C_INVOICES].update_one({"id": invoice_id}, {"$set": {"status": status, "updated_at": now_iso()}})
    fin = await FIN.recompute(contract_id, db=db)
    return {"success": True, "financials": fin}
