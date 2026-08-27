"""Per-line + per-period recomputation math (pure functions).

Kept free of DB access so it is trivially unit-testable and reused by both the
periods service and the accumulation hook.

Money model
-----------
* line.planned_amount  = max(eff_price * planned_kg, minimum_charge)
* line.actual_amount   = max(act_price * actual_kg, minimum_charge)   (from acts)
* period.planned_amount  = Σ line.planned_amount  + Σ extra(stage=planned)
* period.executed_amount = Σ line.actual_amount   + Σ extra(stage=executed)
"""
from __future__ import annotations

from typing import Any, Dict, List

from .util import num, round2


def effective_price(line: Dict[str, Any]) -> float:
    if (line.get("price_source") or "calculated") == "manual" and line.get("price_per_kg") is not None:
        return num(line.get("price_per_kg"))
    return num(line.get("calc_price_per_kg"))


def recompute_line(line: Dict[str, Any]) -> Dict[str, Any]:
    planned_kg = num(line.get("planned_kg"))
    actual_kg = num(line.get("actual_kg"))
    minc = num(line.get("minimum_charge"))
    eff = effective_price(line)
    line["effective_price_per_kg"] = round2(eff)

    planned_amount = eff * planned_kg
    if minc and planned_kg > 0 and planned_amount < minc:
        planned_amount = minc
    line["planned_amount"] = round2(planned_amount)

    act_price = line.get("actual_price_per_kg")
    act_price = num(act_price) if act_price is not None else eff
    actual_amount = act_price * actual_kg
    if minc and actual_kg > 0 and actual_amount < minc:
        actual_amount = minc
    line["actual_amount"] = round2(actual_amount)

    line["deviation_kg"] = round2(actual_kg - planned_kg)
    line["deviation_amount"] = round2(line["actual_amount"] - line["planned_amount"])
    return line


def _extra_sum(extras: List[Dict[str, Any]], stage: str) -> float:
    total = 0.0
    for e in extras or []:
        if (e.get("stage") or "planned") == stage:
            total += num(e.get("amount"))
    return round2(total)


def recompute_period(period: Dict[str, Any]) -> Dict[str, Any]:
    lines = period.get("lines") or []
    for ln in lines:
        recompute_line(ln)
    extras = period.get("extra_works") or []

    planned_kg = round2(sum(num(l.get("planned_kg")) for l in lines))
    actual_kg = round2(sum(num(l.get("actual_kg")) for l in lines))
    planned_lines = round2(sum(num(l.get("planned_amount")) for l in lines))
    actual_lines = round2(sum(num(l.get("actual_amount")) for l in lines))
    planned_extra = _extra_sum(extras, "planned")
    executed_extra = _extra_sum(extras, "executed")

    planned_amount = round2(planned_lines + planned_extra)
    executed_amount = round2(actual_lines + executed_extra)

    period["totals"] = {
        "planned_kg": planned_kg,
        "actual_kg": actual_kg,
        "planned_lines_amount": planned_lines,
        "actual_lines_amount": actual_lines,
        "planned_extra_amount": planned_extra,
        "executed_extra_amount": executed_extra,
        "extra_amount": round2(planned_extra + executed_extra),
        "planned_amount": planned_amount,
        "executed_amount": executed_amount,
        "deviation_kg": round2(actual_kg - planned_kg),
        "deviation_amount": round2(executed_amount - planned_amount),
    }
    return period
