"""Periods service — schedule CRUD, line overrides, extra-works management.

Everything a manager does to the schedule funnels through here so we always
recompute period totals + contract financials consistently.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

from . import constants as K
from . import financials as FIN
from . import pricing as PR
from . import schedule as SCH
from .calc import recompute_period
from .util import gen_id, now_iso, num, round2


async def _seed_line(db, code: str, region: Optional[str], planned_kg: float = 0.0) -> Dict[str, Any]:
    calc = await PR.calc_for_code(code, region=region, db=db)
    return {
        "waste_code": code,
        "name": calc.get("name") or code,
        "hazardous": calc.get("hazardous"),
        "planned_kg": round2(planned_kg),
        "actual_kg": 0.0,
        "price_source": "calculated",
        "calc_price_per_kg": calc.get("calc_price_per_kg"),
        "price_per_kg": calc.get("calc_price_per_kg"),
        "actual_price_per_kg": None,
        "minimum_charge": num(calc.get("minimum_charge"), 0.0),
        "planned_amount": 0.0,
        "actual_amount": 0.0,
        "deviation_kg": 0.0,
        "deviation_amount": 0.0,
    }


async def get_periods(contract_id: str, *, db=None) -> List[Dict[str, Any]]:
    db = get_db() if db is None else db
    return await db[K.C_PERIODS].find({"contract_id": contract_id}, {"_id": 0}).sort("index", 1).to_list(length=500)


async def get_period(period_id: str, *, db=None) -> Optional[Dict[str, Any]]:
    db = get_db() if db is None else db
    return await db[K.C_PERIODS].find_one({"id": period_id}, {"_id": 0})


async def generate(contract_id: str, *, replace: bool = True, custom_windows=None, db=None) -> List[Dict[str, Any]]:
    """(Re)generate the schedule for a contract from its schedule_config.

    Seeds one line per contract waste_code (planned_kg=0) with Calculated
    pricing. ``replace=True`` wipes existing periods first (fresh schedule).
    """
    db = get_db() if db is None else db
    contract = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract:
        raise ValueError("Contract not found")

    cfg = contract.get("schedule_config") or {}
    period_type = cfg.get("period_type") or "quarter"
    if period_type not in K.PERIOD_TYPES:
        period_type = "quarter"
    region = contract.get("region")
    codes: List[str] = contract.get("waste_codes") or []
    if not codes:
        # fall back to codes referenced by any existing contract items
        codes = [it.get("waste_code") for it in (contract.get("items") or []) if it.get("waste_code")]

    windows = SCH.build_windows(
        period_type, contract.get("valid_from"), contract.get("valid_to"),
        custom_windows=custom_windows or cfg.get("custom_windows"),
    )

    if replace:
        await db[K.C_PERIODS].delete_many({"contract_id": contract_id})

    out: List[Dict[str, Any]] = []
    for idx, w in enumerate(windows):
        lines = [await _seed_line(db, c, region) for c in codes]
        period = {
            "id": gen_id("cper"),
            "contract_id": contract_id,
            "company_id": contract.get("company_id"),
            "index": idx,
            "period_type": period_type,
            "label": w.get("label"),
            "date_from": w.get("date_from"),
            "date_to": w.get("date_to"),
            "status": "planned",
            "lines": lines,
            "extra_works": [],
            "linked_act_ids": [],
            "linked_invoice_ids": [],
            "linked_pickup_ids": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        recompute_period(period)
        await db[K.C_PERIODS].insert_one(dict(period))
        period.pop("_id", None)
        out.append(period)

    await FIN.recompute(contract_id, db=db)
    return out


async def _save_period(db, period: Dict[str, Any]) -> Dict[str, Any]:
    recompute_period(period)
    period["updated_at"] = now_iso()
    await db[K.C_PERIODS].update_one({"id": period["id"]}, {"$set": {
        "lines": period["lines"],
        "extra_works": period.get("extra_works", []),
        "totals": period["totals"],
        "status": period.get("status", "planned"),
        "updated_at": period["updated_at"],
    }})
    return period


ASSIGNABLE_LINE_FIELDS = (
    "planned_kg", "price_per_kg", "minimum_charge", "name", "actual_price_per_kg",
)


async def update_line(period_id: str, waste_code: str, patch: Dict[str, Any], *, db=None) -> Dict[str, Any]:
    """Override a period line. Setting price_per_kg flips price_source->manual."""
    db = get_db() if db is None else db
    period = await get_period(period_id, db=db)
    if not period:
        raise ValueError("Period not found")
    line = next((l for l in period.get("lines", []) if l.get("waste_code") == waste_code), None)
    if not line:
        # allow adding a brand-new code line to this period
        line = await _seed_line(db, waste_code, period.get("region"))
        period.setdefault("lines", []).append(line)
    for f in ASSIGNABLE_LINE_FIELDS:
        if f in patch and patch[f] is not None:
            line[f] = patch[f]
    if "price_source" in patch and patch["price_source"] in ("calculated", "manual"):
        line["price_source"] = patch["price_source"]
    elif "price_per_kg" in patch and patch["price_per_kg"] is not None:
        line["price_source"] = "manual"
    if line.get("price_source") == "calculated":
        line["price_per_kg"] = line.get("calc_price_per_kg")
    await _save_period(db, period)
    fin = await FIN.recompute(period["contract_id"], db=db)
    return {"period": await get_period(period_id, db=db), "financials": fin}


async def remove_line(period_id: str, waste_code: str, *, db=None) -> Dict[str, Any]:
    db = get_db() if db is None else db
    period = await get_period(period_id, db=db)
    if not period:
        raise ValueError("Period not found")
    period["lines"] = [l for l in period.get("lines", []) if l.get("waste_code") != waste_code]
    await _save_period(db, period)
    fin = await FIN.recompute(period["contract_id"], db=db)
    return {"period": await get_period(period_id, db=db), "financials": fin}


async def add_extra_work(period_id: str, data: Dict[str, Any], *, db=None) -> Dict[str, Any]:
    """Add a SEPARATE extra-work position to a period (visible in history/PDF)."""
    db = get_db() if db is None else db
    period = await get_period(period_id, db=db)
    if not period:
        raise ValueError("Period not found")
    etype = (data.get("type") or "other").strip()
    if etype not in K.EXTRA_WORK_TYPES:
        etype = "other"
    stage = (data.get("stage") or "planned").strip()
    if stage not in K.EXTRA_WORK_STAGES:
        stage = "planned"
    qty = num(data.get("qty"), 1.0) or 1.0
    unit_price = num(data.get("unit_price"), None) if data.get("unit_price") is not None else None
    amount = num(data.get("amount"), None) if data.get("amount") is not None else None
    if amount is None and unit_price is not None:
        amount = round2(unit_price * qty)
    extra = {
        "id": gen_id("cxw"),
        "type": etype,
        "label": (data.get("label") or K.EXTRA_WORK_LABELS_UK.get(etype, etype)).strip(),
        "qty": qty,
        "unit_price": unit_price,
        "amount": round2(amount or 0.0),
        "stage": stage,
        "source": data.get("source") or "manual",
        "note": data.get("note"),
        "created_at": now_iso(),
    }
    period.setdefault("extra_works", []).append(extra)
    await _save_period(db, period)
    fin = await FIN.recompute(period["contract_id"], db=db)
    return {"period": await get_period(period_id, db=db), "financials": fin, "extra": extra}


async def remove_extra_work(period_id: str, extra_id: str, *, db=None) -> Dict[str, Any]:
    db = get_db() if db is None else db
    period = await get_period(period_id, db=db)
    if not period:
        raise ValueError("Period not found")
    period["extra_works"] = [e for e in period.get("extra_works", []) if e.get("id") != extra_id]
    await _save_period(db, period)
    fin = await FIN.recompute(period["contract_id"], db=db)
    return {"period": await get_period(period_id, db=db), "financials": fin}


async def set_status(period_id: str, status: str, *, db=None) -> Dict[str, Any]:
    db = get_db() if db is None else db
    if status not in K.PERIOD_STATUSES:
        raise ValueError(f"status must be one of {K.PERIOD_STATUSES}")
    period = await get_period(period_id, db=db)
    if not period:
        raise ValueError("Period not found")
    await db[K.C_PERIODS].update_one({"id": period_id}, {"$set": {"status": status, "updated_at": now_iso()}})
    return await get_period(period_id, db=db)
