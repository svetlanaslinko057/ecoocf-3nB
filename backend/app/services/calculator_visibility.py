"""
Calculator Visibility Overrides — Phase Final / Block 5.
=========================================================

Stores admin-controlled per-row visibility overrides for the calculator
breakdown. Each calculator row has a key (e.g. ``vehiclePrice``,
``auctionFee``, ``customsDuty``, ``bibiServiceFee``) and a built-in
visibility (``client | manager | admin_only``).

This module lets a master_admin override any row's visibility without
touching code:

    overrides[row_key] = "client" | "manager" | "admin_only" | "hidden"

The special value ``"hidden"`` removes the row from the breakdown
entirely (useful for fees that the customer must never see and even
managers shouldn't see for some flows).

Storage
-------
``db.app_settings`` document with ``id == "calculator_visibility"``::

    {
      "id":         "calculator_visibility",
      "overrides":  {"vehiclePrice": "client", "wireFee": "hidden", ...},
      "updated_at": ISO,
      "updated_by": email
    }

Effect on calculator
--------------------
Both ``_calculate_usa`` and ``_calculate_korea`` call
``apply_overrides(breakdown)`` just before assembling the response
payload. The function mutates rows in-place and drops "hidden" rows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

ALLOWED_VISIBILITIES = {"client", "manager", "admin_only", "hidden"}
SETTING_ID = "calculator_visibility"


async def load_overrides() -> Dict[str, str]:
    """Return the active visibility override map.

    Cheap to call — single Mongo round trip on a single document.
    Returns ``{}`` if no overrides are configured.
    """
    db = get_db()
    if db is None:
        return {}
    doc = await db.app_settings.find_one({"id": SETTING_ID}, {"_id": 0, "overrides": 1})
    if not doc:
        return {}
    overrides = doc.get("overrides") or {}
    return {str(k): str(v) for k, v in overrides.items() if v in ALLOWED_VISIBILITIES}


def apply_overrides(
    breakdown: List[Dict[str, Any]],
    overrides: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Mutate ``breakdown`` rows in-place based on the override map.

    * If ``overrides[row.key] == "hidden"`` the row is dropped.
    * Otherwise ``row["visibility"]`` is replaced.
    * Returns a NEW list (the same row dicts, minus hidden ones) so
      callers can chain safely.
    """
    if not overrides:
        return breakdown
    out: List[Dict[str, Any]] = []
    for row in breakdown:
        key = row.get("key")
        ov = overrides.get(key)
        if ov == "hidden":
            continue
        if ov and ov != row.get("visibility"):
            row["visibility"] = ov
        out.append(row)
    return out


async def save_overrides(
    overrides: Dict[str, str],
    *,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist (overwrite) the visibility override map. Returns the
    saved document."""
    db = get_db()
    clean: Dict[str, str] = {}
    for k, v in (overrides or {}).items():
        if v not in ALLOWED_VISIBILITIES:
            raise ValueError(f"Invalid visibility {v!r} for row {k!r}; allowed: {sorted(ALLOWED_VISIBILITIES)}")
        clean[str(k)] = v
    doc = {
        "id": SETTING_ID,
        "overrides": clean,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": updated_by,
    }
    await db.app_settings.update_one(
        {"id": SETTING_ID},
        {"$set": doc},
        upsert=True,
    )
    return doc


__all__ = ["load_overrides", "save_overrides", "apply_overrides", "ALLOWED_VISIBILITIES"]
