"""
Wave 3 — Operations Center HTTP surface
=======================================

Adds the operational cycle that actually sells the service:

    Waste Contract   draft -> sent -> agreed -> signed -> active -> closed
    Pickup Order     planning -> route -> driver_assigned -> picked_up -> delivered
    Utilization Act  expected -> created -> signed -> archived

Plus Company360 supporting tabs: timeline (activity), tasks, comments; and the
Waste Object Center object-detail aggregate. All routes under /api/waste and
staff-guarded (manager/admin) — they are NOT in the public access-gate whitelist.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_manager_or_admin
from app.core.db_runtime import get_db
from app.waste import service as S

logger = logging.getLogger("eco.waste.ops")


async def _engine_recompute_for_act(doc: Dict[str, Any]) -> None:
    """Contract Execution Engine hook: rebuild period actuals whenever an act
    linked to a contract is created / updated / transitions. Best-effort."""
    try:
        if doc and doc.get("contract_id"):
            from app.contract_engine import accumulation as _ACC
            await _ACC.recompute_actuals(doc["contract_id"])
    except Exception:
        logger.exception("[ops] contract-engine act hook failed (non-fatal)")


# Contract fields understood by the Contract Execution Engine (persisted on create).
_CONTRACT_ENGINE_FIELDS = (
    "customer_id", "customerId", "object_ids", "waste_codes", "valid_from", "valid_to",
    "total_limit_kg", "region", "schedule_config", "financial_terms", "contract_value",
)

router = APIRouter(prefix="/api/waste", tags=["waste-operations"])

_ENTITY = {
    "contract": (S.C_CONTRACTS, S.CONTRACT_STAGES, "draft", "Договір", "WC"),
    "pickup": (S.C_PICKUPS, S.PICKUP_STAGES, "planning", "Вивіз", "PU"),
    "act": (S.C_ACTS, S.ACT_STAGES, "expected", "Акт утилізації", "ACT"),
}


def _uid(user: Dict[str, Any]) -> str:
    return user.get("email") or user.get("id") or "system"


async def _enrich_items(db, items: Any) -> List[Dict[str, Any]]:
    """Normalise + license/hazard-enrich a list of {waste_code, qty, ...}."""
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in items:
        code = (it.get("waste_code") or it.get("code") or "").strip()
        if not code:
            continue
        chk = await S.license_check(db, code)
        out.append({
            "waste_code": code,
            "name": it.get("name") or chk.get("name"),
            "qty": it.get("qty"),
            "unit": it.get("unit") or "kg",
            "packaging": it.get("packaging"),
            "hazardous": chk.get("hazardous"),
            "accepted": chk.get("accepted"),
            "notes": it.get("notes"),
        })
    return out


# ════════════════════════════════════════════════════════════════════════════
#  Generic lifecycle entity factory (contract / pickup / act)
# ════════════════════════════════════════════════════════════════════════════
async def _create_entity(kind: str, data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    coll, stages, initial, label, prefix = _ENTITY[kind]
    db = get_db()
    company_id = data.get("company_id")
    if not company_id:
        raise HTTPException(400, "company_id is required")
    if not await db[S.C_COMPANIES].find_one({"id": company_id}):
        raise HTTPException(404, "Компанію не знайдено")
    now = S.now_iso()
    by = _uid(user)
    status = data.get("status") if data.get("status") in stages else initial
    items = await _enrich_items(db, data.get("items"))
    doc: Dict[str, Any] = {
        "id": S.gen_id(kind),
        "number": data.get("number") or await S.next_number(db, kind, prefix),
        "company_id": company_id,
        "object_id": data.get("object_id"),
        "request_id": data.get("request_id"),
        "status": status,
        "items": items,
        "notes": data.get("notes"),
        "created_at": now, "updated_at": now, "created_by": by,
        "status_history": [{"status": status, "at": now, "by": by}],
    }
    # kind-specific fields
    if kind == "contract":
        doc.update({
            "title": data.get("title") or f"{label} {doc['number']}",
            "amount": data.get("amount"),
            "currency": data.get("currency") or "UAH",
            "valid_from": data.get("valid_from"),
            "valid_to": data.get("valid_to"),
            "signed_at": None, "signed_by": None, "file_id": data.get("file_id"),
        })
        # Contract Execution Engine fields (schedule/financial terms/codes/limits)
        for _f in _CONTRACT_ENGINE_FIELDS:
            if data.get(_f) is not None:
                doc[_f] = data.get(_f)
        if doc.get("customerId") and not doc.get("customer_id"):
            doc["customer_id"] = doc.get("customerId")
    elif kind == "pickup":
        doc.update({
            "contract_id": data.get("contract_id"),
            "scheduled_at": data.get("scheduled_at"),
            "route": data.get("route"),
            "driver": data.get("driver"),          # {name, phone, vehicle}
            "transport_type": data.get("transport_type"),
            "container_type": data.get("container_type"),
            "weight_kg": data.get("weight_kg"),
            "picked_up_at": None, "delivered_at": None,
        })
    elif kind == "act":
        doc.update({
            "contract_id": data.get("contract_id"),
            "period_id": data.get("period_id"),
            "pickup_id": data.get("pickup_id"),
            "total_weight_kg": data.get("total_weight_kg"),
            "utilization_method": data.get("utilization_method"),
            "act_date": data.get("act_date"),
            "lines": data.get("lines") or [],
            "extra_works": data.get("extra_works") or [],
            "signed_at": None, "signed_by": None, "file_id": data.get("file_id"),
        })
    await db[coll].insert_one(doc)
    await S.log_activity(
        db, company_id=company_id, object_id=doc.get("object_id"),
        entity_type=kind, entity_id=doc["id"], event="created",
        message=f"{label} {doc['number']} створено", by=by,
    )
    if kind == "act":
        await _engine_recompute_for_act(doc)
    return S.serialize(doc)


async def _transition(kind: str, entity_id: str, data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    coll, stages, _initial, label, _prefix = _ENTITY[kind]
    db = get_db()
    status = (data.get("status") or "").strip()
    if status not in stages:
        raise HTTPException(400, f"status must be one of {stages}")
    doc = await db[coll].find_one({"id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"{label} не знайдено")
    now = S.now_iso()
    by = _uid(user)
    set_fields: Dict[str, Any] = {"status": status, "updated_at": now}
    # lifecycle side-effects
    if status == "signed" and kind in ("contract", "act"):
        set_fields["signed_at"] = now
        set_fields["signed_by"] = data.get("signed_by") or by
    # Zero-price protection: an engine contract may NOT be signed while any
    # planned line lacks a price (a code without a tariff needs a manual override).
    if status == "signed" and kind == "contract" and doc.get("schedule_config"):
        from app.contract_engine import invoicing as _INV
        try:
            await _INV.assert_contract_signable(entity_id, db=db)
        except _INV.BillingError as _e:
            raise HTTPException(400, str(_e))
        except Exception:
            logger.exception("[ops] sign guard check failed (non-fatal)")
    if kind == "pickup" and status == "picked_up":
        set_fields["picked_up_at"] = now
    if kind == "pickup" and status == "delivered":
        set_fields["delivered_at"] = now
    hist = {"status": status, "at": now, "by": by, "note": data.get("note")}
    await db[coll].update_one({"id": entity_id}, {"$set": set_fields, "$push": {"status_history": hist}})
    await S.log_activity(
        db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
        entity_type=kind, entity_id=entity_id, event="stage_changed",
        message=f"{label} {doc.get('number','')}: статус → {status}", by=by,
    )
    fresh = await db[coll].find_one({"id": entity_id}, {"_id": 0})
    if kind == "act":
        await _engine_recompute_for_act(fresh or doc)
    return fresh


async def _list_entity(kind: str, company_id: Optional[str], status: Optional[str], limit: int):
    coll = _ENTITY[kind][0]
    db = get_db()
    q: Dict[str, Any] = {}
    if company_id:
        q["company_id"] = company_id
    if status:
        q["status"] = status
    rows = await db[coll].find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    return {"success": True, "items": rows, "count": len(rows)}


async def _update_entity(kind: str, entity_id: str, patch: Dict[str, Any]):
    coll = _ENTITY[kind][0]
    db = get_db()
    if not await db[coll].find_one({"id": entity_id}):
        raise HTTPException(404, "Не знайдено")
    for k in ("id", "status_history", "number", "created_at"):
        patch.pop(k, None)
    if "items" in patch:
        patch["items"] = await _enrich_items(db, patch["items"])
    patch["updated_at"] = S.now_iso()
    await db[coll].update_one({"id": entity_id}, {"$set": patch})
    fresh = await db[coll].find_one({"id": entity_id}, {"_id": 0})
    if kind == "act":
        await _engine_recompute_for_act(fresh)
    return {"success": True, "item": fresh}


# ════════════════════════════════════════════════════════════════════════════
#  CONTRACTS
# ════════════════════════════════════════════════════════════════════════════
@router.get("/contracts", dependencies=[Depends(require_manager_or_admin)])
async def list_contracts(company_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(200, ge=1, le=1000)):
    return await _list_entity("contract", company_id, status, limit)


@router.post("/contracts", dependencies=[Depends(require_manager_or_admin)])
async def create_contract(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    return {"success": True, "contract": await _create_entity("contract", data, user)}


@router.get("/contracts/{entity_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_contract(entity_id: str):
    doc = await get_db()[S.C_CONTRACTS].find_one({"id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Договір не знайдено")
    return {"success": True, "contract": doc}


@router.post("/contracts/{entity_id}/status", dependencies=[Depends(require_manager_or_admin)])
async def contract_status(entity_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    return {"success": True, "contract": await _transition("contract", entity_id, data, user)}


@router.put("/contracts/{entity_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_contract(entity_id: str, patch: Dict[str, Any] = Body(...)):
    res = await _update_entity("contract", entity_id, patch)
    return {"success": True, "contract": res["item"]}


# ════════════════════════════════════════════════════════════════════════════
#  PICKUPS
# ════════════════════════════════════════════════════════════════════════════
@router.get("/pickups", dependencies=[Depends(require_manager_or_admin)])
async def list_pickups(company_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(200, ge=1, le=1000)):
    return await _list_entity("pickup", company_id, status, limit)


@router.post("/pickups", dependencies=[Depends(require_manager_or_admin)])
async def create_pickup(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    return {"success": True, "pickup": await _create_entity("pickup", data, user)}


@router.get("/pickups/{entity_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_pickup(entity_id: str):
    doc = await get_db()[S.C_PICKUPS].find_one({"id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Замовлення на вивіз не знайдено")
    return {"success": True, "pickup": doc}


@router.post("/pickups/{entity_id}/status", dependencies=[Depends(require_manager_or_admin)])
async def pickup_status(entity_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    return {"success": True, "pickup": await _transition("pickup", entity_id, data, user)}


@router.put("/pickups/{entity_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_pickup(entity_id: str, patch: Dict[str, Any] = Body(...)):
    res = await _update_entity("pickup", entity_id, patch)
    return {"success": True, "pickup": res["item"]}


# ════════════════════════════════════════════════════════════════════════════
#  UTILIZATION ACTS
# ════════════════════════════════════════════════════════════════════════════
@router.get("/acts", dependencies=[Depends(require_manager_or_admin)])
async def list_acts(company_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(200, ge=1, le=1000)):
    return await _list_entity("act", company_id, status, limit)


@router.post("/acts", dependencies=[Depends(require_manager_or_admin)])
async def create_act(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    return {"success": True, "act": await _create_entity("act", data, user)}


@router.get("/acts/{entity_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_act(entity_id: str):
    doc = await get_db()[S.C_ACTS].find_one({"id": entity_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Акт не знайдено")
    return {"success": True, "act": doc}


@router.post("/acts/{entity_id}/status", dependencies=[Depends(require_manager_or_admin)])
async def act_status(entity_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    return {"success": True, "act": await _transition("act", entity_id, data, user)}


@router.put("/acts/{entity_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_act(entity_id: str, patch: Dict[str, Any] = Body(...)):
    res = await _update_entity("act", entity_id, patch)
    return {"success": True, "act": res["item"]}


# ════════════════════════════════════════════════════════════════════════════
#  OPERATIONAL FLOW — generate downstream docs from a request
# ════════════════════════════════════════════════════════════════════════════
async def _request_or_404(db, request_id: str) -> Dict[str, Any]:
    req = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "Заявку не знайдено")
    return req


@router.post("/requests/{request_id}/contract", dependencies=[Depends(require_manager_or_admin)])
async def gen_contract(request_id: str, data: Dict[str, Any] = Body(default={}), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    req = await _request_or_404(db, request_id)
    items = req.get("items", []) or []
    codes = []
    for it in items:
        c = (it.get("waste_code") or it.get("code") or "").strip()
        if c and c not in codes:
            codes.append(c)

    from datetime import date, timedelta
    today = date.today()
    default_from = today.isoformat()
    default_to = (today + timedelta(days=365)).isoformat()

    payload = {
        "company_id": req.get("company_id"), "object_id": req.get("object_id"),
        "request_id": request_id, "items": items,
        # ── Contract Execution Engine auto-config ──
        "waste_codes": codes,
        "customer_id": req.get("customer_id") or req.get("customerId"),
        "valid_from": data.get("valid_from") or default_from,
        "valid_to": data.get("valid_to") or default_to,
        "region": req.get("region") or data.get("region"),
        "schedule_config": data.get("schedule_config") or {"period_type": "quarter", "auto_generate": True},
        "financial_terms": data.get("financial_terms") or {"invoice_scope": data.get("invoice_scope") or "per_period"},
        **(data or {}),
    }
    contract = await _create_entity("contract", payload, user)

    # Auto-generate the schedule and seed planned volumes from the request items.
    periods = []
    try:
        from app.contract_engine import periods as _PERIODS
        periods = await _PERIODS.generate(contract["id"], replace=True)
        if periods:
            first = periods[0]
            qty_by_code = {}
            for it in items:
                c = (it.get("waste_code") or it.get("code") or "").strip()
                q = it.get("qty")
                if c and q:
                    qty_by_code[c] = (qty_by_code.get(c) or 0) + float(q)
            for code, q in qty_by_code.items():
                try:
                    await _PERIODS.update_line(first["id"], code, {"planned_kg": q})
                except Exception:
                    logger.warning("[ops] seed planned_kg failed for %s", code)
            periods = await _PERIODS.get_periods(contract["id"])
    except Exception:
        logger.exception("[ops] auto-schedule generation failed (non-fatal)")

    return {"success": True, "contract": contract, "periods": periods}


@router.post("/requests/{request_id}/pickup", dependencies=[Depends(require_manager_or_admin)])
async def gen_pickup(request_id: str, data: Dict[str, Any] = Body(default={}), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    req = await _request_or_404(db, request_id)
    payload = {"company_id": req.get("company_id"), "object_id": req.get("object_id"),
               "request_id": request_id, "items": req.get("items", []), **(data or {})}
    return {"success": True, "pickup": await _create_entity("pickup", payload, user)}


@router.post("/requests/{request_id}/act", dependencies=[Depends(require_manager_or_admin)])
async def gen_act(request_id: str, data: Dict[str, Any] = Body(default={}), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    req = await _request_or_404(db, request_id)
    payload = {"company_id": req.get("company_id"), "object_id": req.get("object_id"),
               "request_id": request_id, "items": req.get("items", []), **(data or {})}
    return {"success": True, "act": await _create_entity("act", payload, user)}


# ════════════════════════════════════════════════════════════════════════════
#  WASTE OBJECT CENTER — object detail aggregate
# ════════════════════════════════════════════════════════════════════════════
@router.get("/objects/{object_id}/detail", dependencies=[Depends(require_manager_or_admin)])
async def object_detail(object_id: str):
    db = get_db()
    obj = await db[S.C_OBJECTS].find_one({"id": object_id}, {"_id": 0})
    if not obj:
        raise HTTPException(404, "Об'єкт не знайдено")
    company = await db[S.C_COMPANIES].find_one({"id": obj.get("company_id")}, {"_id": 0})
    requests = await db[S.C_REQUESTS].find({"object_id": object_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    pickups = await db[S.C_PICKUPS].find({"object_id": object_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    acts = await db[S.C_ACTS].find({"object_id": object_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    branches = await db[S.C_OBJECTS].find({"parent_id": object_id}, {"_id": 0}).to_list(length=200)
    # distinct waste types handled at this object (from its requests)
    waste_types = sorted({it.get("waste_code") for r in requests for it in r.get("items", []) if it.get("waste_code")})
    return {
        "success": True,
        "object": obj,
        "company": company,
        "branches": branches,
        "requests": requests,
        "pickups": pickups,
        "acts": acts,
        "waste_types": waste_types,
        "pickup_schedule": obj.get("pickup_schedule"),
        "stats": {
            "requests": len(requests), "pickups": len(pickups), "acts": len(acts),
            "branches": len(branches), "waste_types": len(waste_types),
            "next_pickup": next((p.get("scheduled_at") for p in pickups
                                 if p.get("status") in ("planning", "route", "driver_assigned") and p.get("scheduled_at")), None),
        },
    }


# ════════════════════════════════════════════════════════════════════════════
#  COMPANY360 — timeline / tasks / comments
# ════════════════════════════════════════════════════════════════════════════
@router.get("/companies/{company_id}/timeline", dependencies=[Depends(require_manager_or_admin)])
async def company_timeline(company_id: str, limit: int = Query(100, ge=1, le=500)):
    db = get_db()
    rows = await db[S.C_ACTIVITY].find({"company_id": company_id}, {"_id": 0}).sort("at", -1).limit(int(limit)).to_list(length=int(limit))
    return {"success": True, "items": rows, "count": len(rows)}


@router.get("/companies/{company_id}/tasks", dependencies=[Depends(require_manager_or_admin)])
async def list_tasks(company_id: str):
    db = get_db()
    rows = await db[S.C_TASKS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/companies/{company_id}/tasks", dependencies=[Depends(require_manager_or_admin)])
async def create_task(company_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    if not await db[S.C_COMPANIES].find_one({"id": company_id}):
        raise HTTPException(404, "Компанію не знайдено")
    if not (data.get("title") or "").strip():
        raise HTTPException(400, "title is required")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("task"), "company_id": company_id, "object_id": data.get("object_id"),
        "title": data["title"].strip(), "status": data.get("status") or "open",
        "due_at": data.get("due_at"), "assigned_to": data.get("assigned_to"),
        "notes": data.get("notes"), "created_at": now, "updated_at": now, "created_by": _uid(user),
    }
    await db[S.C_TASKS].insert_one(doc)
    await S.log_activity(db, company_id=company_id, entity_type="task", entity_id=doc["id"],
                         event="created", message=f"Задача: {doc['title']}", by=_uid(user))
    return {"success": True, "task": S.serialize(doc)}


@router.put("/tasks/{task_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_task(task_id: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    if not await db[S.C_TASKS].find_one({"id": task_id}):
        raise HTTPException(404, "Задачу не знайдено")
    patch.pop("id", None)
    patch["updated_at"] = S.now_iso()
    await db[S.C_TASKS].update_one({"id": task_id}, {"$set": patch})
    return {"success": True, "task": await db[S.C_TASKS].find_one({"id": task_id}, {"_id": 0})}


@router.delete("/tasks/{task_id}", dependencies=[Depends(require_manager_or_admin)])
async def delete_task(task_id: str):
    db = get_db()
    res = await db[S.C_TASKS].delete_one({"id": task_id})
    if not res.deleted_count:
        raise HTTPException(404, "Задачу не знайдено")
    return {"success": True}


@router.get("/companies/{company_id}/comments", dependencies=[Depends(require_manager_or_admin)])
async def list_comments(company_id: str):
    db = get_db()
    rows = await db[S.C_COMMENTS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/companies/{company_id}/comments", dependencies=[Depends(require_manager_or_admin)])
async def create_comment(company_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    if not await db[S.C_COMPANIES].find_one({"id": company_id}):
        raise HTTPException(404, "Компанію не знайдено")
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("cmt"), "company_id": company_id,
        "entity_type": data.get("entity_type"), "entity_id": data.get("entity_id"),
        "text": text, "author": _uid(user), "created_at": now,
    }
    await db[S.C_COMMENTS].insert_one(doc)
    return {"success": True, "comment": S.serialize(doc)}


__all__ = ["router"]
