"""Act → period auto-accumulation (idempotent).

Rather than incrementally add weights (which double-counts on retries), we
REBUILD every period's actuals from ALL currently-signed acts for the contract.
Calling this any number of times yields the same result.

Act line shape accepted (best-effort, tolerant):
    act.lines / act.items = [ { waste_code|code, actual_kg|qty, price_per_kg? } ]
    act.extra_works = [ { type, label, amount, qty?, unit_price?, note? } ]
    act.period_id (optional) — else matched by act_date within a period window.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

from . import constants as K
from . import financials as FIN
from . import schedule as SCH
from .calc import recompute_period
from .util import gen_id, now_iso, num, round2


def _act_lines(act: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = act.get("lines") or act.get("items") or []
    out = []
    for it in raw:
        code = (it.get("waste_code") or it.get("code") or "").strip()
        if not code:
            continue
        kg = it.get("actual_kg")
        if kg is None:
            kg = it.get("qty")
        out.append({
            "waste_code": code,
            "actual_kg": num(kg, 0.0),
            "price_per_kg": (num(it.get("price_per_kg")) if it.get("price_per_kg") is not None else None),
        })
    # Single-total fallback: act.total_weight_kg with one code
    if not out and act.get("total_weight_kg") is not None:
        code = None
        items = act.get("items") or []
        if items:
            code = (items[0].get("waste_code") or items[0].get("code") or "").strip() or None
        if code:
            out.append({"waste_code": code, "actual_kg": num(act.get("total_weight_kg")), "price_per_kg": None})
    return out


def _resolve_period(periods: List[Dict[str, Any]], act: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pid = act.get("period_id")
    if pid:
        for p in periods:
            if p.get("id") == pid:
                return p
    when = act.get("act_date") or act.get("signed_at") or act.get("created_at")
    for p in periods:
        if SCH.window_contains(p, when):
            return p
    return periods[0] if periods else None


async def recompute_actuals(contract_id: str, *, db=None) -> Dict[str, Any]:
    """Rebuild all period actuals from signed acts, then recompute financials."""
    db = get_db() if db is None else db
    periods = await db[K.C_PERIODS].find({"contract_id": contract_id}, {"_id": 0}).sort("index", 1).to_list(length=500)
    if not periods:
        return await FIN.recompute(contract_id, db=db)

    # 1) reset actuals + drop act-sourced executed extras
    for p in periods:
        for ln in p.get("lines", []):
            ln["actual_kg"] = 0.0
            ln["actual_price_per_kg"] = None
        p["extra_works"] = [e for e in p.get("extra_works", []) if e.get("source") != "act"]
        p["linked_act_ids"] = []

    # 2) replay all signed acts
    acts = await db[K.C_ACTS].find(
        {"contract_id": contract_id, "status": {"$in": list(K.SIGNED_ACT_STATUSES)}}, {"_id": 0},
    ).sort("created_at", 1).to_list(length=1000)

    for act in acts:
        period = _resolve_period(periods, act)
        if not period:
            continue
        for al in _act_lines(act):
            line = next((l for l in period.get("lines", []) if l.get("waste_code") == al["waste_code"]), None)
            if not line:
                line = {
                    "waste_code": al["waste_code"], "name": al["waste_code"],
                    "planned_kg": 0.0, "actual_kg": 0.0, "price_source": "calculated",
                    "calc_price_per_kg": al.get("price_per_kg"), "price_per_kg": al.get("price_per_kg"),
                    "actual_price_per_kg": None, "minimum_charge": 0.0,
                    "planned_amount": 0.0, "actual_amount": 0.0,
                    "deviation_kg": 0.0, "deviation_amount": 0.0,
                }
                period.setdefault("lines", []).append(line)
            line["actual_kg"] = round2(num(line.get("actual_kg")) + al["actual_kg"])
            if al.get("price_per_kg") is not None:
                line["actual_price_per_kg"] = al["price_per_kg"]
        for e in (act.get("extra_works") or []):
            period.setdefault("extra_works", []).append({
                "id": gen_id("cxw"),
                "type": (e.get("type") or "other"),
                "label": e.get("label") or K.EXTRA_WORK_LABELS_UK.get(e.get("type"), "Інші послуги"),
                "qty": num(e.get("qty"), 1.0) or 1.0,
                "unit_price": (num(e.get("unit_price")) if e.get("unit_price") is not None else None),
                "amount": round2(num(e.get("amount"))),
                "stage": "executed",
                "source": "act",
                "act_id": act.get("id"),
                "note": e.get("note"),
                "created_at": now_iso(),
            })
        period.setdefault("linked_act_ids", []).append(act.get("id"))

    # 3) persist + recompute financials
    for p in periods:
        recompute_period(p)
        await db[K.C_PERIODS].update_one({"id": p["id"]}, {"$set": {
            "lines": p["lines"], "extra_works": p.get("extra_works", []),
            "totals": p["totals"], "linked_act_ids": p.get("linked_act_ids", []),
            "updated_at": now_iso(),
        }})
    return await FIN.recompute(contract_id, db=db)


async def on_act_changed(act: Dict[str, Any], *, db=None) -> None:
    """Hook: call after an act is created/updated/signed. No-op if not linked."""
    db = get_db() if db is None else db
    cid = act.get("contract_id")
    if not cid:
        return
    await recompute_actuals(cid, db=db)
