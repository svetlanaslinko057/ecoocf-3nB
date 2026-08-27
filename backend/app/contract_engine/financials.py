"""Contract financial engine — the FIVE distinct values.

    Contract Value  — frozen at signing (contract.contract_value) or, before
                      signing, the live planned total (Σ period planned).
    Executed Value  — Σ period executed amounts (driven by SIGNED acts + executed extras).
    Invoiced Value  — Σ non-cancelled invoices linked to the contract.
    Paid Value      — Σ PAID invoices linked to the contract.
    Remaining Value — Contract Value − Paid Value.

Also exposes outstanding (Invoiced − Paid) and extra totals for the UI.
The result is cached onto ``waste_contracts.financials`` and returned.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.db_runtime import get_db

from . import constants as K
from .util import num, round2, now_iso


async def _contract(db, contract_id: str) -> Dict[str, Any]:
    return await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})


async def _periods(db, contract_id: str) -> List[Dict[str, Any]]:
    return await db[K.C_PERIODS].find({"contract_id": contract_id}, {"_id": 0}).sort("index", 1).to_list(length=500)


async def _invoice_totals(db, contract_id: str) -> Dict[str, float]:
    invoiced = 0.0
    paid = 0.0
    cursor = db[K.C_INVOICES].find({"contract_id": contract_id}, {"_id": 0})
    async for inv in cursor:
        status = (inv.get("status") or "").lower()
        amount = num(inv.get("amount") if inv.get("amount") is not None else inv.get("total"))
        if status in K.CANCELLED_INVOICE_STATUSES:
            continue
        invoiced += amount
        # Support partial payments: an explicit amount_paid wins; otherwise a
        # 'paid' status means fully paid.
        if inv.get("amount_paid") is not None:
            paid += num(inv.get("amount_paid"))
        elif status in K.PAID_INVOICE_STATUSES:
            paid += amount
    return {"invoiced": round2(invoiced), "paid": round2(paid)}


async def recompute(contract_id: str, *, db=None) -> Dict[str, Any]:
    """Recompute + persist contract.financials. Returns the financials block."""
    db = get_db() if db is None else db
    contract = await _contract(db, contract_id)
    if not contract:
        return {}
    periods = await _periods(db, contract_id)

    planned_total = round2(sum(num((p.get("totals") or {}).get("planned_amount")) for p in periods))
    executed_total = round2(sum(num((p.get("totals") or {}).get("executed_amount")) for p in periods))
    extra_total = round2(sum(num((p.get("totals") or {}).get("extra_amount")) for p in periods))

    inv = await _invoice_totals(db, contract_id)
    invoiced_value = inv["invoiced"]
    paid_value = inv["paid"]

    # Contract Value: frozen value wins; otherwise the live planned total.
    frozen = contract.get("contract_value")
    contract_value = round2(frozen) if frozen is not None else planned_total

    remaining_value = round2(contract_value - paid_value)
    outstanding_value = round2(invoiced_value - paid_value)

    currency = contract.get("currency") or "UAH"
    financials = {
        "contract_value": contract_value,
        "contract_value_frozen": frozen is not None,
        "planned_total": planned_total,
        "executed_value": executed_total,
        "invoiced_value": invoiced_value,
        "paid_value": paid_value,
        "remaining_value": remaining_value,
        "outstanding_value": outstanding_value,
        "extra_total": extra_total,
        "currency": currency,
        "periods_count": len(periods),
        "computed_at": now_iso(),
    }
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"financials": financials, "updated_at": now_iso()}})
    return financials


async def freeze_contract_value(contract_id: str, *, value: float = None, db=None) -> Dict[str, Any]:
    """Freeze the Contract Value at signing. If value omitted, freeze the current
    planned total. Idempotent-ish: overwrites the frozen value."""
    db = get_db() if db is None else db
    if value is None:
        fin = await recompute(contract_id, db=db)
        value = fin.get("planned_total", 0.0)
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"contract_value": round2(value), "contract_value_frozen_at": now_iso(), "updated_at": now_iso()}},
    )
    return await recompute(contract_id, db=db)
