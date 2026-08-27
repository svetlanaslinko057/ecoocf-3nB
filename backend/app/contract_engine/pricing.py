"""Pricing adapter — the engine's single source of *Calculated* prices.

Wraps the existing ECO pricing engine (``app/waste/service.py::price_estimate``)
so every period line gets a ``calc_price_per_kg`` + ``minimum_charge`` derived
from the real price rules. Managers may later Override any parameter; we keep
BOTH the calculated and the effective (manual) values on the line so the UI can
show "Calculated vs Manual Override".
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.db_runtime import get_db
from app.waste import service as S

from .util import num


async def calc_for_code(
    code: str,
    *,
    region: Optional[str] = None,
    db=None,
) -> Dict[str, Any]:
    """Return the calculated pricing basis for a waste code.

    Uses a stable reference quantity so ``price_per_kg`` reflects the pure
    per-kg utilization tariff (transport/urgent/container are handled as
    SEPARATE extra-works, never folded into the line tariff here).
    """
    db = get_db() if db is None else db
    try:
        est = await S.price_estimate(
            db, code, 1000.0,
            region=region, container="provided", transport=False, urgent=False,
        )
    except Exception:
        est = {"ok": False}
    if not est or not est.get("ok"):
        return {
            "calc_price_per_kg": None,
            "minimum_charge": 0.0,
            "name": None,
            "currency": "UAH",
            "hazardous": None,
            "price_source_note": est.get("reason") if isinstance(est, dict) else None,
        }
    return {
        "calc_price_per_kg": num(est.get("price_per_kg"), None) if est.get("price_per_kg") is not None else None,
        "minimum_charge": num(est.get("minimum_charge"), 0.0),
        "name": est.get("name"),
        "currency": est.get("currency") or "UAH",
        "hazardous": est.get("hazardous"),
        "price_source_note": est.get("note"),
    }
