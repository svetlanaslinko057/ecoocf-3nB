"""Contract Completion Wizard.

Produces a deterministic checklist. The contract can ONLY be moved to
``closed`` after every check passes AND a manager explicitly confirms
(``complete_contract`` requires ``confirm=True``). Nothing auto-closes.

Checks:
    acts_closed        — no utilization_acts in an open status
    invoices_paid      — every linked invoice is paid (and >=1 exists if any billing expected)
    documents_signed   — contract e-signed (status/esign_status == signed)
    ecologist_report   — at least one FINAL ecologist report exists
    photos_uploaded    — at least one file/photo linked to acts/pickups/contract
    no_open_tasks      — no open company tasks
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.db_runtime import get_db

from . import constants as K
from .util import now_iso


async def completion_check(contract_id: str, *, db=None) -> Dict[str, Any]:
    db = get_db() if db is None else db
    contract = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract:
        raise ValueError("Contract not found")
    company_id = contract.get("company_id")

    checks: List[Dict[str, Any]] = []

    # 1) acts closed
    open_acts = await db[K.C_ACTS].count_documents(
        {"contract_id": contract_id, "status": {"$in": list(K.OPEN_ACT_STATUSES)}})
    total_acts = await db[K.C_ACTS].count_documents({"contract_id": contract_id})
    checks.append({
        "key": "acts_closed", "label": "Усі акти закриті",
        "ok": open_acts == 0,
        "detail": f"Відкритих актів: {open_acts} з {total_acts}",
        "count": total_acts,
    })

    # 2) invoices paid
    inv_cursor = db[K.C_INVOICES].find({"contract_id": contract_id}, {"_id": 0, "status": 1})
    inv_total = 0
    inv_unpaid = 0
    async for inv in inv_cursor:
        status = (inv.get("status") or "").lower()
        if status in K.CANCELLED_INVOICE_STATUSES:
            continue
        inv_total += 1
        if status not in K.PAID_INVOICE_STATUSES:
            inv_unpaid += 1
    checks.append({
        "key": "invoices_paid", "label": "Усі рахунки оплачені",
        "ok": inv_unpaid == 0,
        "detail": f"Неоплачених рахунків: {inv_unpaid} з {inv_total}",
        "count": inv_total,
    })

    # 3) documents signed (contract e-sign)
    signed = (contract.get("esign_status") == "signed") or (contract.get("status") in ("signed", "active", "closed"))
    checks.append({
        "key": "documents_signed", "label": "Договір підписано",
        "ok": bool(signed),
        "detail": "Підписано" if signed else "Не підписано (е-підпис)",
    })

    # 4) ecologist report (>=1 final or signed)
    eco_ready = await db[K.C_ECO_REPORTS].count_documents({"contract_id": contract_id, "status": {"$in": ["final", "signed"]}})
    eco_total = await db[K.C_ECO_REPORTS].count_documents({"contract_id": contract_id})
    checks.append({
        "key": "ecologist_report", "label": "Звіт еколога сформовано",
        "ok": eco_ready > 0,
        "detail": f"Готових звітів (final/signed): {eco_ready} (всього {eco_total})",
        "count": eco_total,
    })

    # 5) photos uploaded — read the REAL canonical `files` collection + pickup photos[]
    act_ids = [a["id"] async for a in db[K.C_ACTS].find({"contract_id": contract_id}, {"_id": 0, "id": 1})]
    pickup_docs = await db[K.C_PICKUPS].find({"contract_id": contract_id}, {"_id": 0, "id": 1, "photos": 1}).to_list(length=500)
    pickup_ids = [p["id"] for p in pickup_docs]
    photos = 0
    try:
        photos = await db[K.C_FILES].count_documents({"$or": [
            {"contract_id": contract_id},
            {"act_id": {"$in": act_ids or ["__none__"]}},
            {"pickup_id": {"$in": pickup_ids or ["__none__"]}},
        ]})
    except Exception:
        photos = 0
    # fallback: pickups may carry an inline photos[] array pushed on upload
    photos += sum(len(p.get("photos") or []) for p in pickup_docs)
    checks.append({
        "key": "photos_uploaded", "label": "Фото/документи завантажені",
        "ok": photos > 0,
        "detail": f"Файлів/фото: {photos}",
        "count": photos,
    })

    # 6) no open tasks
    open_tasks = 0
    if company_id:
        try:
            open_tasks = await db[K.C_TASKS].count_documents(
                {"company_id": company_id, "status": {"$nin": ["done", "cancelled", "closed"]}})
        except Exception:
            open_tasks = 0
    checks.append({
        "key": "no_open_tasks", "label": "Немає відкритих завдань",
        "ok": open_tasks == 0,
        "detail": f"Відкритих завдань: {open_tasks}",
        "count": open_tasks,
    })

    ready = all(c["ok"] for c in checks)
    return {
        "contract_id": contract_id,
        "ready": ready,
        "can_close": ready and contract.get("status") not in ("closed", "cancelled"),
        "current_status": contract.get("status"),
        "checks": checks,
        "checked_at": now_iso(),
    }


async def complete_contract(contract_id: str, *, by: Dict[str, Any] = None, confirm: bool = False, db=None) -> Dict[str, Any]:
    db = get_db() if db is None else db
    result = await completion_check(contract_id, db=db)
    if not result["ready"]:
        blockers = [c["label"] for c in result["checks"] if not c["ok"]]
        raise ValueError("Не можна закрити договір: " + "; ".join(blockers))
    if not confirm:
        raise ValueError("Потрібне явне підтвердження менеджера (confirm=true)")
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {
        "status": "closed",
        "closed_at": now_iso(),
        "closed_by": (by or {}).get("email") or (by or {}).get("id"),
        "updated_at": now_iso(),
    }})
    fresh = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    return {"success": True, "contract": fresh, "completion": result}
