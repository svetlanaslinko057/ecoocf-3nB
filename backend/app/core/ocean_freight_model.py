"""
app/core/ocean_freight_model.py
================================

Wave 4.1 (2026-05-26) — Ocean Freight as a **route matrix**, not a layered
pricing system.

Why we dropped buckets / port-to-bucket / destination deltas
-----------------------------------------------------------
Freight companies don't price by bucket + delta — they publish lane
rates. A lane is the pair (USA export port → EU destination port). The
operator sees ONE number per lane, edits it directly, and that's the
production reality.

The previous bucket model (atlantic_short / atlantic_medium / atlantic_
long / pacific_extreme + per-port bucket assignment + per-destination
USD delta) was internally elegant but UX-wrong: it made admin think
like a freight engineer instead of a sales operator.

New model (1-page mental model)
-------------------------------

    OCEAN_LANE_MATRIX[ usa_export_port ][ eu_destination_port ]  USD

    × shared vehicle multiplier  (from USA-inland model)

    = FINAL OCEAN FREIGHT

That's it. No buckets, no deltas, no derived layers. 8 USA × 8 EU = 64
cells. Each cell is a real lane price.

Default destination port (Wave 4.1b)
------------------------------------
When the calculator call has no explicit destination (the public UI
doesn't ask the customer to pick — the customer just says "Europe"),
the engine routes through a single configurable **default destination
port** (Rotterdam by default).

This is intentional product behaviour: the public UI must collapse 8
EU ports into a single visible price point, otherwise the customer is
confused and conversion drops.  Internally we can still price any of
the 64 lanes — the default is only the fallback used when the customer
gave no destination.

Default values
--------------
Rotterdam is the cheapest EU baseline (largest hub) and the bundled
default destination. Other ports ascend in cost the further East you
go. Black-Sea ports (Constanta / Poti / Batumi) are the priciest
because vessels transit the Bosporus.

Lane prices are sedan-baseline; bigger vehicles multiply via the
shared ``vehicleMultipliers`` table on the inland model.

Public API
----------
``OCEAN_LANE_MATRIX_DEFAULT``     ─ Dict[usa_port_code, Dict[eu_port_code, int]]
``DEFAULT_DESTINATION_PORT``       ─ str — single public-facing EU port
``compute_ocean_freight(...)``    ─ engine: lane × multiplier
``resolve_destination_port(...)`` ─ helper: explicit > admin default > bundled default
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════
# Default public-facing destination port
# ═══════════════════════════════════════════════════════════════════════
# The public calculator collapses 8 EU ports into ONE visible price
# point — this is that point. Admin can change it via
# ``profile.oceanFreightModel.defaultDestinationPort``.
#
# Rotterdam is the bundled default because:
#  * it's the largest EU port (most direct vessel calls)
#  * cheapest terminal handling among the 8
#  * 90%+ of US→EU used-car cargo flows through Rotterdam first
#  * onward feeder/truck/rail to BG/RO/DE is trivial from Rotterdam

DEFAULT_DESTINATION_PORT: str = "rotterdam"


def resolve_destination_port(
    requested: Optional[str],
    profile_default: Optional[str] = None,
) -> str:
    """Resolve which destination port to use for a given call.

    Priority:
      1. explicit ``requested`` (from the API payload — manager UI,
         live preview, etc.) **only** when non-empty and not the literal
         string ``"default"``.
      2. ``profile_default`` (admin's chosen default).
      3. ``DEFAULT_DESTINATION_PORT`` (bundled fallback: rotterdam).

    The literal ``"default"`` token lets callers explicitly say
    "I don't know, use whatever the admin configured" without having to
    pre-resolve the value on the client.
    """
    r = (requested or "").strip().lower()
    if r and r != "default":
        return r
    pd = (profile_default or "").strip().lower()
    if pd:
        return pd
    return DEFAULT_DESTINATION_PORT


# ═══════════════════════════════════════════════════════════════════════
# Lane matrix — 8 USA export ports × 8 EU destination ports = 64 lanes
# ═══════════════════════════════════════════════════════════════════════
# Sedan-baseline USD per lane. Admin edits these directly.

OCEAN_LANE_MATRIX_DEFAULT: Dict[str, Dict[str, int]] = {
    # ── East Coast (short Atlantic crossing) ───────────────────────────
    "newark": {
        "rotterdam":   900,
        "hamburg":     950,
        "bremerhaven": 950,
        "klaipeda":   1050,
        "gdansk":     1075,
        "constanta":  1300,
        "poti":       1700,
        "batumi":     1700,
    },
    "baltimore": {
        "rotterdam":   900,
        "hamburg":     950,
        "bremerhaven": 950,
        "klaipeda":   1050,
        "gdansk":     1075,
        "constanta":  1300,
        "poti":       1700,
        "batumi":     1700,
    },
    "savannah": {
        "rotterdam":   900,
        "hamburg":     950,
        "bremerhaven": 950,
        "klaipeda":   1050,
        "gdansk":     1075,
        "constanta":  1300,
        "poti":       1700,
        "batumi":     1700,
    },
    # ── Florida / Gulf / South (medium Atlantic crossing) ──────────────
    "miami": {
        "rotterdam":  1200,
        "hamburg":    1250,
        "bremerhaven":1250,
        "klaipeda":   1350,
        "gdansk":     1375,
        "constanta":  1550,
        "poti":       2000,
        "batumi":     2000,
    },
    "new_orleans": {
        "rotterdam":  1200,
        "hamburg":    1250,
        "bremerhaven":1250,
        "klaipeda":   1350,
        "gdansk":     1375,
        "constanta":  1550,
        "poti":       2000,
        "batumi":     2000,
    },
    "houston": {
        "rotterdam":  1200,
        "hamburg":    1250,
        "bremerhaven":1250,
        "klaipeda":   1350,
        "gdansk":     1375,
        "constanta":  1550,
        "poti":       2000,
        "batumi":     2000,
    },
    # ── West Coast (long Atlantic via Panama) ──────────────────────────
    "los_angeles": {
        "rotterdam":  1800,
        "hamburg":    1850,
        "bremerhaven":1850,
        "klaipeda":   1950,
        "gdansk":     1975,
        "constanta":  2200,
        "poti":       2600,
        "batumi":     2600,
    },
    # ── Pacific North-West (extreme — Seattle via Panama) ──────────────
    "seattle": {
        "rotterdam":  2500,
        "hamburg":    2550,
        "bremerhaven":2550,
        "klaipeda":   2650,
        "gdansk":     2675,
        "constanta":  2900,
        "poti":       3400,
        "batumi":     3400,
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Engine — pure-function lane lookup × vehicle multiplier
# ═══════════════════════════════════════════════════════════════════════

def compute_ocean_freight(
    *,
    export_port: Optional[str],
    destination_port: Optional[str],
    vehicle_type: str,
    ocean_model: Optional[Dict[str, Any]] = None,
    shared_vehicle_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute ocean freight as a flat lane lookup × shared multiplier.

    Parameters
    ----------
    export_port : str | None
        USA export port code (``newark``, ``houston``, …). Comes from
        the USA-inland resolution.
    destination_port : str | None
        EU destination port code (``rotterdam`` is baseline).
    vehicle_type : str
        Canonical vehicle code (sedan / suv / bigSUV / pickup / van /
        motorcycle / trailer).
    ocean_model : dict | None
        ``calculator_profile.oceanFreightModel`` — admin overrides.
        Recognised keys:
            ``laneMatrix``    Dict[export_port, Dict[destination_port, int]]
                              (sparse overrides applied on top of defaults)
            ``enabled``       bool (default True)
    shared_vehicle_multipliers : dict | None
        Vehicle multipliers reused from the USA-inland model.

    Returns
    -------
    dict
        {
          "enabled":         bool,
          "exportPort":      str | None,
          "destinationPort": str | None,
          "lanePrice":       float,    ─ sedan baseline for this lane
          "multiplier":      float,    ─ vehicle footprint multiplier
          "amount":          float,    ─ lanePrice × multiplier
          "fallback":        str,      ─ "ok" / "missing_lane" / "disabled"
        }
    """
    model = ocean_model or {}
    if model.get("enabled") is False:
        return {
            "enabled": False, "exportPort": export_port,
            "destinationPort": destination_port,
            "lanePrice": 0.0, "multiplier": 0.0, "amount": 0.0,
            "fallback": "disabled", "resolvedDefault": False,
        }

    # Wave 4.1b — destination port falls through to the admin-chosen
    # default when the caller didn't pick one (public UI behaviour).
    profile_default = model.get("defaultDestinationPort")
    resolved_dst = resolve_destination_port(destination_port, profile_default)
    resolved_via_default = (
        not (destination_port or "").strip()
        or (destination_port or "").strip().lower() == "default"
    )

    # Merge defaults with admin overrides (sparse — only changed cells
    # are stored in the profile).
    overrides = model.get("laneMatrix") or {}
    src_port = (export_port or "").strip()
    dst_port = resolved_dst

    default_row = OCEAN_LANE_MATRIX_DEFAULT.get(src_port) or {}
    override_row = overrides.get(src_port) or {}
    lane_price_raw = override_row.get(dst_port, default_row.get(dst_port))

    if lane_price_raw is None:
        return {
            "enabled": False, "exportPort": src_port or None,
            "destinationPort": dst_port or None,
            "lanePrice": 0.0, "multiplier": 0.0, "amount": 0.0,
            "fallback": "missing_lane", "resolvedDefault": resolved_via_default,
        }

    try:
        lane_price = float(lane_price_raw)
    except (TypeError, ValueError):
        lane_price = 0.0

    multipliers = shared_vehicle_multipliers or {}
    try:
        mult = float(multipliers.get(vehicle_type, multipliers.get("sedan", 1.0)))
    except (TypeError, ValueError):
        mult = 1.0

    amount = round(lane_price * mult, 2)

    return {
        "enabled":         True,
        "exportPort":      src_port,
        "destinationPort": dst_port,
        "lanePrice":       round(lane_price, 2),
        "multiplier":      round(mult, 3),
        "amount":          amount,
        "fallback":        "ok",
        "resolvedDefault": resolved_via_default,
    }


__all__ = [
    "OCEAN_LANE_MATRIX_DEFAULT",
    "DEFAULT_DESTINATION_PORT",
    "resolve_destination_port",
    "compute_ocean_freight",
]
