"""
app/core/eu_delivery_model.py
==============================

Wave 4.2 (2026-05-27) — EU Delivery model.

After the ocean leg lands at an EU port (Rotterdam by default), the car
needs to be trucked from there to **Sofia, Bulgaria** (our single
business endpoint). This module prices that last leg.

Why a matrix and not a multiplier system
----------------------------------------
The user explicitly asked for explicit EUR prices per (eu_port, vehicle)
pair rather than a multiplier model, because:

*  motorcycle and trailer rates don't scale linearly with the shared
   footprint multipliers used for Inland / Ocean (motorcycles ride on
   small trailers, trailers ride on heavy trucks — different commercial
   reality);
*  the user wants direct admin control of every cell;
*  the EU trucking market quotes per lane, per vehicle, in EUR;
*  the matrix is small (8 × 7 = 56 cells) so editability beats
   abstraction.

Formula
-------

    EU_DELIVERY_MATRIX[ eu_port ][ vehicle_type ]  EUR

    → converted to USD via ``profile.fxUsdToEur`` for the unified total

    = EU DELIVERY LEG

There's no destination dimension — destination is always Sofia/BG.

Defaults (EUR)
--------------
Rotterdam is the bundled-default EU port and represents the cheapest
practical lane to Sofia. Other ports scale up/down based on real
trucking distance and ferry/intermodal overhead:

           Sedan SUV  BigSUV Pickup Van  Motorcycle Trailer
Rotterdam  1200  1400  1600   1700  1900  700        2200
Bremerhaven1200  1400  1600   1700  1900  700        2200
Hamburg    1150  1350  1550   1650  1850  650        2100
Klaipeda   1300  1500  1700   1800  2000  750        2400
Gdansk     1100  1300  1500   1600  1800  600        2000
Constanta   700   850  1000   1100  1300  400        1500   ← closest
Poti       1800  2100  2400   2550  2850 1100        3200   ← farthest (ferry)
Batumi     1800  2100  2400   2550  2850 1100        3200

Public API
----------
``EU_DELIVERY_FINAL_HUB``           ─ "sofia_bg" (fixed)
``EU_DELIVERY_MATRIX_DEFAULT_EUR``  ─ Dict[eu_port, Dict[vehicle, eur]]
``compute_eu_delivery(...)``        ─ engine: matrix lookup + FX → USD
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

EU_DELIVERY_FINAL_HUB: str = "sofia_bg"  # always Sofia / Bulgaria
EU_DELIVERY_FINAL_HUB_LABEL: str = "Sofia (BG)"

# Bundled-default starting EU port for the EU-delivery leg.
# When the calculator caller didn't pass an explicit eu_port (the public
# UI doesn't ask the customer to pick — they just say "from Europe"),
# the engine routes through this single configurable port. Admin can
# override via ``profile.euDeliveryModel.defaultEuPort``.
#
# Rotterdam is the bundled default because:
#  * matches the Ocean Freight bundled-default destination — so the
#    full ocean → EU delivery chain stays coherent out of the box;
#  * cheapest North-Sea trucking-onward gateway to Sofia among the 8;
#  * 90%+ of US→EU used-car traffic flows through Rotterdam first.
DEFAULT_EU_PORT: str = "rotterdam"


def resolve_eu_port(
    requested: Optional[str],
    profile_default: Optional[str] = None,
) -> str:
    """Resolve which EU starting port to use for the trucking leg.

    Priority:
      1. explicit ``requested`` (typically comes from ocean_resolution
         .destinationPort — the port where the car actually lands)
         **only** when non-empty and not the literal string ``"default"``.
      2. ``profile_default`` (admin's chosen default in
         ``euDeliveryModel.defaultEuPort``).
      3. ``DEFAULT_EU_PORT`` (bundled fallback: rotterdam).

    The literal ``"default"`` token lets callers explicitly say
    "use whatever the admin configured" without pre-resolving the value.
    """
    r = (requested or "").strip().lower()
    if r and r != "default":
        return r
    pd = (profile_default or "").strip().lower()
    if pd:
        return pd
    return DEFAULT_EU_PORT



# ═══════════════════════════════════════════════════════════════════════
# Default lane matrix (EUR, sedan-baseline-friendly per row)
# ═══════════════════════════════════════════════════════════════════════
# Rows  = 8 EU destination ports (same set as Ocean Freight destinations)
# Cols  = 7 vehicle types (sedan / suv / bigSUV / pickup / van /
#                          motorcycle / trailer)
# Cells = EUR for that (port, vehicle) trucking from the port to Sofia.

EU_DELIVERY_MATRIX_DEFAULT_EUR: Dict[str, Dict[str, int]] = {
    # ── North Sea hubs ──────────────────────────────────────────────────
    "rotterdam":   {"sedan": 1200, "suv": 1400, "bigSUV": 1600, "pickup": 1700, "van": 1900, "motorcycle":  700, "trailer": 2200},
    "bremerhaven": {"sedan": 1200, "suv": 1400, "bigSUV": 1600, "pickup": 1700, "van": 1900, "motorcycle":  700, "trailer": 2200},
    "hamburg":     {"sedan": 1150, "suv": 1350, "bigSUV": 1550, "pickup": 1650, "van": 1850, "motorcycle":  650, "trailer": 2100},
    # ── Baltic ──────────────────────────────────────────────────────────
    "klaipeda":    {"sedan": 1300, "suv": 1500, "bigSUV": 1700, "pickup": 1800, "van": 2000, "motorcycle":  750, "trailer": 2400},
    "gdansk":      {"sedan": 1100, "suv": 1300, "bigSUV": 1500, "pickup": 1600, "van": 1800, "motorcycle":  600, "trailer": 2000},
    # ── Black Sea (closest to Sofia) ────────────────────────────────────
    "constanta":   {"sedan":  700, "suv":  850, "bigSUV": 1000, "pickup": 1100, "van": 1300, "motorcycle":  400, "trailer": 1500},
    # ── Black Sea (Caucasus — includes ferry) ───────────────────────────
    "poti":        {"sedan": 1800, "suv": 2100, "bigSUV": 2400, "pickup": 2550, "van": 2850, "motorcycle": 1100, "trailer": 3200},
    "batumi":      {"sedan": 1800, "suv": 2100, "bigSUV": 2400, "pickup": 2550, "van": 2850, "motorcycle": 1100, "trailer": 3200},
}


# ═══════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════

def compute_eu_delivery(
    *,
    eu_port: Optional[str],
    vehicle_type: str,
    eu_delivery_model: Optional[Dict[str, Any]] = None,
    fx_usd_to_eur: float = 0.91,
) -> Dict[str, Any]:
    """Compute EU delivery as matrix[port][vehicle] EUR → USD.

    Parameters
    ----------
    eu_port : str | None
        EU destination port code (the port where the car lands after
        ocean — comes from ``ocean_resolution.destinationPort``).
    vehicle_type : str
        Canonical vehicle code.
    eu_delivery_model : dict | None
        ``calculator_profile.euDeliveryModel`` — admin overrides.
        Recognised keys:
            ``matrix``    Dict[eu_port, Dict[vehicle, eur]]
                          (sparse — only changed cells stored)
            ``enabled``   bool (default True)
    fx_usd_to_eur : float
        USD→EUR conversion (e.g., 0.91 means 1 USD = 0.91 EUR, so to
        convert EUR back to USD we do ``eur / fx``).

    Returns
    -------
    dict
        {
          "enabled":     bool,
          "euPort":      str | None,
          "vehicleType": str,
          "destination": "sofia_bg",
          "amountEur":   float,
          "amountUsd":   float,
          "fxRate":      float,
          "fallback":    "ok" | "missing_cell" | "disabled",
        }
    """
    model = eu_delivery_model or {}
    if model.get("enabled") is False:
        return {
            "enabled": False, "euPort": eu_port, "vehicleType": vehicle_type,
            "destination": EU_DELIVERY_FINAL_HUB,
            "amountEur": 0.0, "amountUsd": 0.0, "fxRate": fx_usd_to_eur,
            "fallback": "disabled", "resolvedDefault": False,
        }

    # Resolve which EU port to use: explicit > admin default > rotterdam.
    profile_default = model.get("defaultEuPort")
    resolved_port = resolve_eu_port(eu_port, profile_default)
    resolved_via_default = (
        not (eu_port or "").strip()
        or (eu_port or "").strip().lower() == "default"
    )

    # Build the working matrix (defaults overlaid with sparse admin overrides)
    overrides = model.get("matrix") or {}
    port_code = resolved_port
    default_row = EU_DELIVERY_MATRIX_DEFAULT_EUR.get(port_code) or {}
    override_row = overrides.get(port_code) or {}

    eur_raw = override_row.get(vehicle_type, default_row.get(vehicle_type))
    if eur_raw is None:
        return {
            "enabled": False, "euPort": port_code or None,
            "vehicleType": vehicle_type,
            "destination": EU_DELIVERY_FINAL_HUB,
            "amountEur": 0.0, "amountUsd": 0.0, "fxRate": fx_usd_to_eur,
            "fallback": "missing_cell", "resolvedDefault": resolved_via_default,
        }

    try:
        eur_amount = float(eur_raw)
    except (TypeError, ValueError):
        eur_amount = 0.0

    try:
        fx = float(fx_usd_to_eur) or 0.91
    except (TypeError, ValueError):
        fx = 0.91
    if fx <= 0:
        fx = 0.91

    usd_amount = round(eur_amount / fx, 2)

    return {
        "enabled":         True,
        "euPort":          port_code,
        "vehicleType":     vehicle_type,
        "destination":     EU_DELIVERY_FINAL_HUB,
        "amountEur":       round(eur_amount, 2),
        "amountUsd":       usd_amount,
        "fxRate":          round(fx, 4),
        "fallback":        "ok",
        "resolvedDefault": resolved_via_default,
    }


__all__ = [
    "EU_DELIVERY_FINAL_HUB",
    "EU_DELIVERY_FINAL_HUB_LABEL",
    "DEFAULT_EU_PORT",
    "EU_DELIVERY_MATRIX_DEFAULT_EUR",
    "resolve_eu_port",
    "compute_eu_delivery",
]
