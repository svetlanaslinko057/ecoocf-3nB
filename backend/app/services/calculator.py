"""Phase 5.5/B — Calculator engines (CANONICAL HOME).
=========================================================

This module owns the two calculator engines extracted from
``server.py`` on 2026-05-19 per the 5.5/B mandate:

  * ``_calculate_korea``      — Korea → Romania → Bulgaria turnkey cost
  * ``calculator_calculate``  — full turnkey cost (USA pipeline + Korea
                                dispatch). The FastAPI route
                                ``POST /api/calculator/calculate`` is
                                registered against this very function
                                object from ``server.py`` (imperative
                                ``fastapi_app.post(...)`` registration
                                — see server.py around line 9872).
                                The function name (``calculator_calculate``)
                                drives the OpenAPI operationId, so the
                                route surface is byte-identical to the
                                pre-extraction state.

Byte-identical extraction discipline
------------------------------------
Function bodies are byte-identical to their pre-extraction versions
(server.py:9872 + server.py:10126). Per the 5.5/B mandate, **none** of
the following were changed:

  * formulas
  * rounding
  * response payload shapes / keys / order
  * naming
  * Korea-specific logic
  * engine boundaries (NOT merged)

The ONLY mechanical substitutions applied during the move:

  * ``db.calculator_profile.find_one(...)``  → ``get_db().calculator_profile.find_one(...)``
  * ``db.calculator_routes.find(...)``       → ``get_db().calculator_routes.find(...)``
  * ``logger.warning(...)`` inside the bodies now binds to the
    **module-local** ``logger = logging.getLogger("bibi.calculator")``
    (was ``server.logger`` at module-load time — same handler chain,
    different namespace label).

These mechanical substitutions follow the established C-4i precedent
(``db.X`` → ``get_db().X``) and the 5.5/A precedent (per-module
``logging.getLogger("bibi.<domain>")``). Both substitution categories
were validated against the pinned golden-parity hashes captured
pre-extraction (see ``tests/test_phase5_5_b_calculator_extraction.py``
::``PINNED_HASHES``).

Dependencies (constants + helpers) after Phase 6.5+ Wave 2
-----------------------------------------------------------

Per the latest mandate, the constants/helpers ownership has been
fully restructured:

  * **38 PURE_CONSTANT** (catalog tables + USA + Korea constants) live
    in ``app/core/calculator_constants.py`` — pure-data module created
    by Wave 2 (2026-05-20). This module imports them at the top.
  * **1 internal-only constant** (``AUCTION_TIERED_FEES``) also lives
    in ``app/core/calculator_constants.py``.
  * **3 pure helpers** (``_find_route_amount``, ``_tiered_buyer_fee``,
    ``_tiered_buyer_fee_from_db``) live in
    ``app/services/calculator_pure.py`` — Wave 1 + Wave 2 retirement.
    This module imports them at the top.
  * **2 SERVER_STATE-coupled helpers** (``_ensure_calculator_seed``,
    ``_load_calc_config``) remain in ``server.py`` for Wave 3. This
    module accesses them lazily via ``import server`` inside the
    engine functions (NOT via ``from server import …`` at module-load).

The Wave 2 mandate ("constants и ``_tiered_buyer_fee*`` structurally
coupled — single coordinated retirement") was honoured: 38 + 1 + 2 =
41 symbols retired in one wave.

No classes. No DI. No services abstraction. Bare async functions —
the identical shape they had in server.py.

Circular-import note (RESOLVED Phase 6.5+ Wave 2)
-------------------------------------------------
Pre-Wave-2 (i.e., between 5.5/B and Wave 2), this module had a
``from server import (42 symbols)`` block at module-load that created
a latent circular-import shape: standalone ``import
app.services.calculator`` triggered ``from server import …``, which
in turn triggered ``import app.services.calculator`` via
``server.py:9789``'s ``from app.services.calculator import
_calculate_korea, …`` line; that re-entry caught the partially
initialised calculator module and raised ``ImportError: partially
initialized``. Production boot order avoided this because ``server.py``
was always loaded first by uvicorn (server first → triggers calculator
load → calculator's ``from server import …`` resolves against the
fully-defined symbols above the engine-extraction point).

Wave 2 resolved the cycle by:

  1. Moving the 38 PURE_CONSTANT + AUCTION_TIERED_FEES to a dedicated
     pure-data module ``app/core/calculator_constants.py`` (zero deps).
  2. Moving 2 ``_tiered_buyer_fee*`` helpers into the Wave-1 sibling
     ``app/services/calculator_pure.py``.
  3. Converting the remaining 2 server-coupled calls
     (``_ensure_calculator_seed`` + ``_load_calc_config``) to **lazy
     ``import server``** inside the engine function bodies — these
     resolve at call-time (long after server.py has finished loading)
     instead of at module-load.

Net effect: this module has **zero** ``from server import X``
ImportFrom nodes. Standalone ``import app.services.calculator`` now
succeeds cleanly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Body

from app.core.db_runtime import get_db

# ─────────────────────────────────────────────────────────────────────
# Phase 6.5+ Wave 2 (LANDING 2026-05-20) — import topology resolved
# ─────────────────────────────────────────────────────────────────────
# Pre-Wave-2 this module had ``from server import (42 symbols)`` at
# module-load, which created a latent circular-import shape: standalone
# ``import app.services.calculator`` triggered ``from server import …``,
# which triggered ``import app.services.calculator`` via server.py:9789's
# ``from app.services.calculator import _calculate_korea, …`` line, which
# caught the partially-initialised calculator module and raised
# ``ImportError: partially initialized``.
#
# Wave 2 resolution:
#   * 38 PURE_CONSTANT + AUCTION_TIERED_FEES (39 symbols) moved to
#     ``app/core/calculator_constants.py`` (NEW canonical home).
#   * 2 ``_tiered_buyer_fee*`` helpers folded into
#     ``app/services/calculator_pure.py`` (EXTENDED — Wave 1's sibling).
#   * 2 SERVER_STATE-coupled helpers (``_ensure_calculator_seed``,
#     ``_load_calc_config``) retained in server.py for Wave 3; now
#     accessed lazily via ``import server`` inside the engine functions
#     (NOT via ``from server import …`` at module-load).
#
# Result: zero ``from server import X`` AST nodes in this file.
# Standalone ``import app.services.calculator`` now succeeds — the
# latent cycle is resolved. ``import server`` (lazy, inside functions)
# only happens at call-time, when server.py has long since finished
# loading.
from app.core.calculator_constants import (  # noqa: E402
    # Catalog tables (3)
    VEHICLE_TYPES,
    CALCULATOR_PORTS,
    AUCTION_FEES,
    # USA-pipeline constants (14)
    DEFAULT_PROFILE_CODE,
    VEHICLE_USA_INLAND,
    VEHICLE_OCEAN_BASE,
    PORT_OCEAN_ADJUST,
    VEHICLE_EU_DELIVERY,
    PORT_FORWARDING,
    PORT_PARKING,
    PARKING_BULGARIA,
    COMPANY_SERVICES,
    CUSTOMS_DOCUMENTATION,
    CUSTOMS_DUTY_RATE,
    INSURANCE_RATE,
    DAMAGED_CUSTOMS_FACTOR,
    DAMAGE_HANDLING_FEE_USD,
    # Korea-pipeline constants (21)
    KOREA_PROFILE_CODE,
    KOREA_USE_LOGISTICS_PACKAGE,
    KOREA_AUCTION_FEE_PERCENT,
    KOREA_LOGISTICS_PACKAGE,
    KOREA_INLAND_DEFAULT,
    KOREA_SEA_DEFAULT,
    KOREA_INSURANCE_DEFAULT,
    KOREA_FORWARDER_FEE_DEFAULT,
    KOREA_DOCUMENTS_MAIL_DEFAULT,
    KOREA_CUSTOMS_DUTY_RATE,
    KOREA_VAT_RATE,
    KOREA_UNDERVALUE_PERCENT,
    KOREA_DAMAGED_CUSTOMS_FACTOR,
    KOREA_DAMAGE_HANDLING_FEE_USD,
    KOREA_OFFICIAL_FEES_USD,
    KOREA_BIBI_SERVICE_FEE,
    KOREA_FX_USD_TO_EUR,
    KOREA_BG_TRANSPORT_EUR,
    KOREA_ADDITIONAL_FEES_EUR,
    KOREA_TECH_INSPECTION_EUR,
    KOREA_BB_CARS_COMMISSION_EUR,
)

# Phase 6.5+ Wave 1 + Wave 2 — pure helpers canonical home.
# ``_find_route_amount`` moved in Wave 1 (server.py:9679 → here).
# ``_tiered_buyer_fee`` + ``_tiered_buyer_fee_from_db`` moved in Wave 2
# (server.py:9725, 9703 → here). All three are truly pure (zero
# module-globals, zero DB access).
# Phase 6.5+ Wave 3 (LANDING 2026-05-20) — calc-engine SERVER_STATE
# closure. The 2 remaining server-coupled helpers
# (``_ensure_calculator_seed`` + ``_load_calc_config``) are now in
# their canonical home ``app/services/calculator_config_cache``.
# The Wave-2 cycle-break ``import server`` allowance is RETIRED —
# calculator.py reaches everything via canonical homes directly.
from app.services.calculator_pure import (  # noqa: E402
    _find_route_amount,
    _tiered_buyer_fee,
    _tiered_buyer_fee_from_db,
)
from app.services.calculator_config_cache import (  # noqa: E402
    ensure_calculator_seed as _ensure_calculator_seed,
    get_calc_config as _load_calc_config,
)

# Wave 4 (2026-05-26) — proper USA inland logistics model
# (state → export port → bucket × vehicle multiplier).  Replaces the
# legacy flat ``VEHICLE_USA_INLAND`` look-up.  The new model is enabled
# by default and admin-tunable via ``calculator_profile.usaInlandModel``;
# when it cannot resolve (no state, no auction fallback, model disabled)
# we silently fall back to the legacy per-port route table so existing
# deployments keep working.
from app.core.usa_inland_model import (  # noqa: E402
    compute_usa_inland as _compute_usa_inland,
    USA_INLAND_VEHICLE_MULTIPLIERS_DEFAULT as _DEFAULT_VEHICLE_MULTIPLIERS,
)

# Wave 4 — Ocean freight model (export port → ocean bucket × shared
# vehicle multiplier + destination port delta). Replaces magic
# per-port-per-vehicle numbers. Falls back to legacy route lookup when
# the bucket model can't resolve (admin disabled OR unknown export port).
from app.core.ocean_freight_model import (  # noqa: E402
    compute_ocean_freight as _compute_ocean_freight,
)

# Wave 4.2 — EU Delivery model (matrix[eu_port][vehicle] EUR → USD).
# Replaces the legacy flat per-vehicle "eu_delivery" route lookup, which
# treated trucking from any EU port to Sofia as the same number. Falls
# back to the legacy route lookup when the matrix model is disabled OR
# the eu port doesn't have a cell for the requested vehicle.
from app.core.eu_delivery_model import (  # noqa: E402
    compute_eu_delivery as _compute_eu_delivery,
)

# Phase 5.5/B — module-local logger. Replaces the implicit binding
# to ``server.logger`` that the pre-extraction bodies used. The
# message strings, levels, and arguments are byte-identical.
logger = logging.getLogger("bibi.calculator")


# ════════════════════════════════════════════════════════════════════
# _calculate_korea — Korea → Romania → Bulgaria turnkey cost engine
# Extracted byte-identically from server.py:9872 (2026-05-19, 5.5/B)
# ════════════════════════════════════════════════════════════════════
async def _calculate_korea(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Korea → Romania → Bulgaria turnkey cost.

    Pipeline (per spec):
      Calc 1: vehicle_price + 5% auction commission
      Calc 2: korea_logistics_package (3850$ default) OR sum of itemized
              (inland + sea + insurance + forwarder + documents)
      Calc 3: customs_duty (%) + VAT (%) on customs_base
              + bibi_service_fee (940$) + bg_transport (1000€)
              + additional_fees + technical_inspection + bb_cars_commission

      customs_base = invoice_price (if > 0) else (vehicle_price * (1 - undervalue_percent))
                     undervalue_percent for KR = USA logic × 30%
    """
    try:
        price = float(data.get("price") or data.get("vehiclePrice") or 0)
    except (TypeError, ValueError):
        price = 0.0
    try:
        invoice_price = float(data.get("invoicePrice") or 0)
    except (TypeError, ValueError):
        invoice_price = 0.0

    vehicle_type = data.get("vehicleType") or "sedan"
    damaged = bool(data.get("damaged") or False)
    valid_vehicle_codes = {v["code"] for v in VEHICLE_TYPES}
    if vehicle_type not in valid_vehicle_codes:
        vehicle_type = "sedan"

    # Load Korea profile + routes (with seed/cache).
    # Phase 6.5+ Wave 3 — ``ensure_calculator_seed`` reached directly
    # from its canonical home ``app.services.calculator_config_cache``
    # (NOT via server). Cycle-break allowance from Wave 2 is now
    # retired — this module is fully decoupled from server.py.
    try:
        await _ensure_calculator_seed()
    except Exception as e:
        logger.warning(f"[calc-korea] seed check failed: {e}")

    profile = await get_db().calculator_profile.find_one(
        {"code": KOREA_PROFILE_CODE}, {"_id": 0}
    ) or {}
    routes_cursor = get_db().calculator_routes.find(
        {"profileCode": KOREA_PROFILE_CODE, "isActive": {"$ne": False}}, {"_id": 0}
    )
    routes = await routes_cursor.to_list(length=500)

    # Override flags from request body
    use_package_req = data.get("useLogisticsPackage")
    use_package = (
        bool(use_package_req)
        if use_package_req is not None
        else bool(profile.get("useLogisticsPackage", KOREA_USE_LOGISTICS_PACKAGE))
    )

    # ═══ Calc 1 — vehicle price + auction fee (5%) ═════════════════
    auction_fee_pct = float(profile.get("auctionFeePercent", KOREA_AUCTION_FEE_PERCENT))
    auction_fee = round(price * auction_fee_pct / 100.0, 2)
    calc1_total = price + auction_fee

    # ═══ Calc 2 — Korea logistics ═══════════════════════════════
    if use_package:
        logistics_package = float(profile.get("logisticsPackage", KOREA_LOGISTICS_PACKAGE))
        korea_inland = 0.0
        sea_shipping = 0.0
        insurance_amt = 0.0
        forwarder_fee = 0.0
        documents_mail = 0.0
        calc2_total = logistics_package
    else:
        # Itemized (per-vehicle-type from routes, fallbacks to profile)
        korea_inland = _find_route_amount(
            routes, "korea_inland", vehicle_type,
            default=float(profile.get("koreaInlandTransport", KOREA_INLAND_DEFAULT)),
        )
        sea_shipping = _find_route_amount(
            routes, "korea_sea", vehicle_type,
            destination_code="constanta",
            default=float(profile.get("seaShipping", KOREA_SEA_DEFAULT)),
        )
        insurance_amt = float(profile.get("insurance", KOREA_INSURANCE_DEFAULT))
        forwarder_fee = float(profile.get("forwarderFee", KOREA_FORWARDER_FEE_DEFAULT))
        documents_mail = float(profile.get("documentsMailFee", KOREA_DOCUMENTS_MAIL_DEFAULT))
        calc2_total = (
            korea_inland + sea_shipping + insurance_amt + forwarder_fee + documents_mail
        )
        logistics_package = calc2_total

    # ═══ Calc 3 — Customs (Romania), VAT, fixed fees ═══════════════
    customs_duty_rate = float(profile.get("customsDutyRate", KOREA_CUSTOMS_DUTY_RATE))
    vat_rate = float(profile.get("vatRate", KOREA_VAT_RATE))
    undervalue_pct = float(profile.get("undervaluePercent", KOREA_UNDERVALUE_PERCENT))

    # customs_base: prefer invoice price; otherwise reduce vehicle price by undervalue%
    if invoice_price > 0:
        customs_base = invoice_price
    else:
        customs_base = price * (1.0 - undervalue_pct)

    # ── Damage adjustment (Korea) ──────────────────────────────────
    # Salvage / damaged vehicles → reduced customs valuation (industry
    # standard EU practice). Configurable via profile.damagedCustomsFactor.
    # Also adds a fixed damage-handling surcharge (port reinspection +
    # extra forwarder paperwork in Romania).
    damaged_customs_factor = float(profile.get("damagedCustomsFactor", KOREA_DAMAGED_CUSTOMS_FACTOR)) if damaged else 1.0
    damage_handling_fee_usd = float(profile.get("damageHandlingFeeKoreaUsd", KOREA_DAMAGE_HANDLING_FEE_USD)) if damaged else 0.0
    declared_value = customs_base * damaged_customs_factor

    # ── Customs duty & VAT per spec ───────────────────────────────
    #   declared_value = customs_base × (1 − undervalue_pct)   ← already applied via customs_base path above
    #                    (damaged: additional × damaged_customs_factor)
    #   customs_duty   = declared_value × customs_duty_rate
    #   vat            = (declared_value + customs_duty + official_fees) × vat_rate
    # Official fees default 0 — admin can override via profile.officialFeesUsd.
    official_fees = float(profile.get("officialFeesUsd", KOREA_OFFICIAL_FEES_USD))

    customs_duty = round(declared_value * customs_duty_rate, 2)
    vat_amount = round((declared_value + customs_duty + official_fees) * vat_rate, 2)

    bibi_service_fee = float(profile.get("bibiServiceFee", KOREA_BIBI_SERVICE_FEE))  # USD

    # FX rate
    try:
        fx = float(profile.get("fxUsdToEur", KOREA_FX_USD_TO_EUR))
    except (TypeError, ValueError):
        fx = KOREA_FX_USD_TO_EUR
    if fx <= 0:
        fx = KOREA_FX_USD_TO_EUR

    # Romania→BG transport (EUR) — prefer per-vehicle route, fallback profile
    bg_transport_eur = _find_route_amount(
        routes, "korea_bg_transport", vehicle_type,
        destination_code="BG",
        default=float(profile.get("bgTransportEur", KOREA_BG_TRANSPORT_EUR)),
    )

    # Per-request override: additional fees in EUR
    try:
        extra_additional_eur = float(data.get("additionalFees") or 0)
    except (TypeError, ValueError):
        extra_additional_eur = 0.0
    additional_fees_eur = float(profile.get("additionalFeesEur", KOREA_ADDITIONAL_FEES_EUR)) + extra_additional_eur
    technical_inspection_eur = float(profile.get("technicalInspectionEur", KOREA_TECH_INSPECTION_EUR))
    bb_cars_commission_eur = float(profile.get("bbCarsCommissionEur", KOREA_BB_CARS_COMMISSION_EUR))

    # Convert EUR fixed fees to USD for unified sum
    bg_transport_usd = round(bg_transport_eur / fx, 2)
    additional_fees_usd = round(additional_fees_eur / fx, 2)
    technical_inspection_usd = round(technical_inspection_eur / fx, 2)
    bb_cars_commission_usd = round(bb_cars_commission_eur / fx, 2)

    calc3_total = (
        customs_duty + vat_amount
        + bibi_service_fee
        + bg_transport_usd
        + additional_fees_usd
        + technical_inspection_usd
        + bb_cars_commission_usd
        + damage_handling_fee_usd
    )

    # ═══ FINAL ══════════════════════════════════════════════════════════
    grand_total = calc1_total + calc2_total + calc3_total

    def r(x: float) -> float:
        return round(float(x), 2)

    # Visibility taxonomy on each breakdown row:
    #   "client"     — visible to public/customer (catalog calculator, customer cabinet)
    #   "manager"    — visible to manager/teamlead/admin only (internal logistics decomposition)
    #   "admin_only" — visible to teamlead/admin only (margins, customs base, damage coeffs, hidden fees)
    breakdown = [
        {"key": "vehiclePrice",        "label": "Vehicle Price",                        "value": r(price),                "currency": "USD", "visibility": "client",     "category": "cost"},
        {"key": "auctionFee",          "label": f"Auction Commission ({auction_fee_pct:g}%)", "value": r(auction_fee),    "currency": "USD", "visibility": "client",     "category": "cost"},
    ]
    if use_package:
        breakdown.append({"key": "logisticsPackage", "label": "Korea Logistics Package (incl. inland, sea, insurance, forwarder, docs)", "value": r(logistics_package), "currency": "USD", "visibility": "client", "category": "cost"})
    else:
        breakdown += [
            {"key": "koreaInland",     "label": "Korea Inland Transport",      "value": r(korea_inland),      "currency": "USD", "visibility": "client",     "category": "cost"},
            {"key": "seaShipping",     "label": "Sea Shipping (Korea → Romania)", "value": r(sea_shipping),   "currency": "USD", "visibility": "client",     "category": "cost"},
            {"key": "insurance",       "label": "Insurance",                   "value": r(insurance_amt),    "currency": "USD", "visibility": "manager",    "category": "cost"},
            {"key": "forwarderFee",    "label": "Forwarder / Broker Fee",     "value": r(forwarder_fee),     "currency": "USD", "visibility": "admin_only", "category": "cost"},
            {"key": "documentsMail",   "label": "Documents / Mail",            "value": r(documents_mail),   "currency": "USD", "visibility": "admin_only", "category": "cost"},
        ]
    breakdown += [
        # ── Customs side ────────────────────────────────────────
        # customsBase / declaredValue are internal accounting concepts — never shown to the client,
        # never contribute to total (they're derivation rows).
        {"key": "customsBase",         "label": "Customs Base",                "value": r(customs_base),     "currency": "USD", "visibility": "admin_only", "category": "info"},
        {"key": "declaredValue",       "label": f"Declared Value (after {undervalue_pct*100:g}% undervalue{' + salvage' if damaged else ''})", "value": r(declared_value), "currency": "USD", "visibility": "admin_only", "category": "info"},
        {"key": "customsDuty",         "label": f"Customs Duty ({customs_duty_rate * 100:g}%)", "value": r(customs_duty), "currency": "USD", "visibility": "client",     "category": "tax"},
        {"key": "vat",                 "label": f"VAT ({vat_rate * 100:g}%)",  "value": r(vat_amount),       "currency": "USD", "visibility": "client",     "category": "tax"},
        # ── BIBI Cars services + delivery to BG ────────────────────────
        {"key": "bibiServiceFee",      "label": "BIBI Cars Service Fee",       "value": r(bibi_service_fee), "currency": "USD", "visibility": "client",     "category": "revenue"},
        {"key": "bgTransport",         "label": f"Transport to Bulgaria (€{bg_transport_eur:g})", "value": r(bg_transport_usd), "currency": "USD", "visibility": "client",     "category": "cost"},
        {"key": "technicalInspection", "label": f"Technical Inspection (€{technical_inspection_eur:g})", "value": r(technical_inspection_usd), "currency": "USD", "visibility": "client",     "category": "cost"},
        {"key": "bbCarsCommission",    "label": f"BB Cars Commission (€{bb_cars_commission_eur:g})", "value": r(bb_cars_commission_usd), "currency": "USD", "visibility": "admin_only", "category": "revenue"},
        {"key": "additionalFees",      "label": f"Additional Fees (€{additional_fees_eur:g})", "value": r(additional_fees_usd), "currency": "USD", "visibility": "manager",    "category": "cost"},
    ]
    if damaged:
        breakdown.append(
            {"key": "damageHandling", "label": "Damage Handling (Salvage Inspection)", "value": r(damage_handling_fee_usd), "currency": "USD", "visibility": "admin_only", "category": "cost"}
        )

    calculation = {
        "origin":          "korea",
        "vehiclePrice":    r(price),
        "invoicePrice":    r(invoice_price),
        "customsBase":     r(customs_base),
        "declaredValue":   r(declared_value),
        "officialFees":    r(official_fees),
        "auctionTotal":    r(auction_fee),
        "deliveryTotal":   r(calc2_total + calc3_total),
        "calc1Total":      r(calc1_total),
        "calc2Total":      r(calc2_total),
        "calc3Total":      r(calc3_total),
        "total":           r(grand_total),
        "totalEur":        r(grand_total * fx),
        "currency":        "USD",
        "fxUsdToEur":      fx,
        "vehicleType":     vehicle_type,
        "damaged":         damaged,
        "damageHandling":  r(damage_handling_fee_usd),
        "useLogisticsPackage": use_package,
        "breakdown":       breakdown,
        "profileCode":     profile.get("code", KOREA_PROFILE_CODE),
        # legacy flat keys
        "auctionFees":     r(auction_fee),
        "shippingSea":     r(sea_shipping if not use_package else 0.0),
        "customs":         r(customs_duty + vat_amount),
    }
    # Phase Final / Block 5 — apply admin visibility overrides.
    try:
        from app.services.calculator_visibility import load_overrides, apply_overrides
        _overrides = await load_overrides()
        breakdown[:] = apply_overrides(breakdown, _overrides)
        calculation["breakdown"] = breakdown
    except Exception:
        pass  # never block calculation on overrides failure
    return {
        "success": True,
        "calculation": calculation,
        "formattedBreakdown": breakdown,
        "totals": {"visible": r(grand_total), "internal": r(grand_total)},
        "hiddenBreakdown": {"hiddenFee": 0},
        "margin": {"controllableMargin": 0},
    }


# ════════════════════════════════════════════════════════════════════
# calculator_calculate — USA pipeline + Korea dispatch engine
# Extracted byte-identically from server.py:10126 (2026-05-19, 5.5/B)
#
# The FastAPI route `POST /api/calculator/calculate` is registered
# against this function object in server.py (imperative registration,
# at the spot of the old definition) — see server.py around
# line 9872 (post-5.5/B).
# ════════════════════════════════════════════════════════════════════
async def calculator_calculate(data: Dict[str, Any] = Body(...)):
    """Calculate full turnkey delivery cost (DB-backed, admin-editable).

    Accepts:
      origin (usa|korea, default usa) — switches calculation pipeline
      price (USD), port (dest), auction (copart|iaai|korean),
      vehicleType (sedan|suv|bigSUV|pickup), vin/lot (optional)
      damaged (bool) — when true, customs base is reduced (salvage valuation)
                       and an extra Damage Handling line is added
      For Korea: invoicePrice (USD/EUR), additionalFees (EUR), useLogisticsPackage (bool)

    Returns a detailed breakdown plus legacy flat fields for BC.
    """
    origin = (data.get("origin") or "usa").lower()
    if origin in ("korea", "kr", "korea_bg"):
        return await _calculate_korea(data)
    # default: USA flow (legacy behavior preserved)
    try:
        price = float(data.get("price") or 0)
    except (TypeError, ValueError):
        price = 0.0
    # Wave 4.1b — when payload omits ``port`` we DELIBERATELY leave it
    # empty so the admin-configured default destination port can kick
    # in below (instead of hardcoding "burgas" which is no longer in
    # the Wave-4 destination set).
    port = (data.get("port") or "").lower()
    auction = (data.get("auction") or "copart").lower()
    vehicle_type = data.get("vehicleType") or "sedan"
    damaged = bool(data.get("damaged") or False)
    valid_vehicle_codes = {v["code"] for v in VEHICLE_TYPES}
    if vehicle_type not in valid_vehicle_codes:
        vehicle_type = "sedan"
    if auction not in AUCTION_FEES:
        auction = "copart"

    # Load admin-configured values (with fallback to constants).
    # Phase 6.5+ Wave 3 — ``get_calc_config`` reached directly from
    # its canonical home ``app.services.calculator_config_cache``
    # (NOT via server).
    cfg = await _load_calc_config()
    profile = cfg["profile"] or {}
    routes = cfg["routes"] or []
    fees_tiers = cfg["fees"] or []

    # Wave 4 — accept the new 8 destination ports (Rotterdam/Hamburg/
    # Bremerhaven/Klaipeda/Gdansk/Constanta/Poti/Batumi) in addition to
    # the legacy 16-port list.
    # Wave 4.1b — when the call has no explicit port (the public UI just
    # says "Europe"), fall back to the admin-configured default
    # destination port (Rotterdam by default).
    from app.core.usa_inland_model import USA_DESTINATION_PORTS as _W4_DEST_PORTS
    from app.core.ocean_freight_model import (
        DEFAULT_DESTINATION_PORT as _OCEAN_DEFAULT_PORT,
        resolve_destination_port as _resolve_dst_port,
    )
    _valid_ports = {p["code"] for p in CALCULATOR_PORTS} | {p["code"] for p in _W4_DEST_PORTS}
    _ocean_cfg = profile.get("oceanFreightModel") or {}
    _admin_default_port = _ocean_cfg.get("defaultDestinationPort") or _OCEAN_DEFAULT_PORT
    if not port or port == "default" or port not in _valid_ports:
        port = _resolve_dst_port(port, _admin_default_port)

    # Per-auction fee config (gate/title/%) — admin-editable via profile
    auction_fee_cfg = (profile.get("auctionFees") or {}).get(auction) or AUCTION_FEES[auction]

    # Auction side --------------------------------------------------------
    if fees_tiers:
        # Admin has configured a tiered ladder → it is authoritative.
        buyer_fee = _tiered_buyer_fee_from_db(price, fees_tiers)
    else:
        # Legacy fallback: hardcoded ladder with percentage override above 10k.
        buyer_fee = _tiered_buyer_fee(price)
        pct_fee = price * float(auction_fee_cfg.get("buyer_fee_percent", 0)) / 100.0
        if price >= 10000:
            buyer_fee = max(buyer_fee, pct_fee)
    gate_fee = float(auction_fee_cfg.get("gate_fee", 0))
    title_fee = float(auction_fee_cfg.get("title_fee", 0))
    auction_total = buyer_fee + gate_fee + title_fee

    # USA inland ---------------------------------------------------------
    # Wave 4 — proper logistics model: state → nearest export port → distance
    # bucket × vehicle-class multiplier.  Replaces the legacy flat lookup
    # (per-port route or VEHICLE_USA_INLAND default), which produced the
    # same number for a Texas pickup and a Maine pickup.  Profile overrides
    # live under ``profile.usaInlandModel``.  When the new model can't
    # resolve (no state, no auction fallback) we silently fall back to the
    # legacy route lookup so existing pipelines stay green.
    requested_state = data.get("state") or data.get("originState") or data.get("pickupState")
    inland_resolution = _compute_usa_inland(
        state=requested_state,
        vehicle_type=vehicle_type,
        auction=auction,
        profile_model=profile.get("usaInlandModel") or {},
    )
    if inland_resolution.get("enabled"):
        usa_inland = float(inland_resolution["amount"])
    else:
        usa_inland = _find_route_amount(
            routes, "usa_inland", vehicle_type,
            default=VEHICLE_USA_INLAND.get(vehicle_type, 0),
        )

    # Ocean shipping -----------------------------------------------------
    # Wave 4 — bucket model: export_port → ocean_bucket × shared vehicle
    # multiplier + destination port adjustment. Replaces the legacy
    # per-(port,vehicle) flat lookup. Vehicle multipliers are shared with
    # the USA-inland model — single source of truth so SUVs/pickups/etc.
    # have one footprint coefficient across both legs.
    inland_model_cfg = profile.get("usaInlandModel") or {}
    shared_multipliers = {
        **_DEFAULT_VEHICLE_MULTIPLIERS,
        **(inland_model_cfg.get("vehicleMultipliers") or {}),
    }
    ocean_resolution = _compute_ocean_freight(
        export_port=inland_resolution.get("exportPort"),
        destination_port=port,
        vehicle_type=vehicle_type,
        ocean_model=profile.get("oceanFreightModel") or {},
        shared_vehicle_multipliers=shared_multipliers,
    )
    if ocean_resolution.get("enabled"):
        ocean = float(ocean_resolution["amount"])
    else:
        ocean = _find_route_amount(
            routes, "ocean", vehicle_type,
            destination_code=port,
            default=VEHICLE_OCEAN_BASE.get(vehicle_type, 0) + PORT_OCEAN_ADJUST.get(port, 0),
        )

    # EU delivery --------------------------------------------------------
    # Wave 4.2 — matrix model: matrix[eu_port][vehicle] EUR → USD via FX.
    # ``eu_port`` comes from the ocean resolution (whichever EU port the
    # car actually landed at). Final destination is always Sofia (BG).
    # Legacy route lookup remains the fallback when the matrix is off or
    # the cell is missing.
    eu_fx = float(profile.get("fxUsdToEur", KOREA_FX_USD_TO_EUR) or KOREA_FX_USD_TO_EUR)
    eu_resolution = _compute_eu_delivery(
        eu_port=ocean_resolution.get("destinationPort") or port,
        vehicle_type=vehicle_type,
        eu_delivery_model=profile.get("euDeliveryModel") or {},
        fx_usd_to_eur=eu_fx,
    )
    if eu_resolution.get("enabled"):
        eu_delivery = float(eu_resolution["amountUsd"])
    else:
        eu_delivery = _find_route_amount(
            routes, "eu_delivery", vehicle_type,
            destination_code="BG",
            default=VEHICLE_EU_DELIVERY.get(vehicle_type, 0),
        )

    # Fixed fees from profile -------------------------------------------
    port_forwarding = float(profile.get("portForwarding", PORT_FORWARDING))
    port_parking = float(profile.get("portParking", PORT_PARKING))
    parking_bg = float(profile.get("parkingBulgaria", PARKING_BULGARIA))
    company_services = float(profile.get("companyServices", COMPANY_SERVICES))
    customs_docs = float(profile.get("customsDocumentation", CUSTOMS_DOCUMENTATION))
    customs_duty_rate = float(profile.get("customsDutyRate", CUSTOMS_DUTY_RATE))
    insurance_rate = float(profile.get("insuranceRate", INSURANCE_RATE))

    # ── Damage adjustment ───────────────────────────────────────
    # Salvage / damaged vehicles get reduced customs valuation (industry
    # standard EU practice). Configurable via profile.damagedCustomsFactor
    # (default 0.70 = 30% off the price). Also add a fixed "Damage
    # Handling" surcharge for extra port inspection / paperwork.
    damaged_customs_factor = float(profile.get("damagedCustomsFactor", DAMAGED_CUSTOMS_FACTOR)) if damaged else 1.0
    damage_handling_fee = float(profile.get("damageHandlingFeeUsd", DAMAGE_HANDLING_FEE_USD)) if damaged else 0.0

    customs_base = price * damaged_customs_factor
    customs_duty = customs_base * customs_duty_rate
    customs_total = customs_duty + customs_docs
    insurance = price * insurance_rate

    delivery_total = (
        usa_inland + ocean + port_forwarding + port_parking + eu_delivery
        + customs_total + parking_bg + company_services + insurance
        + damage_handling_fee
    )
    grand_total = price + auction_total + delivery_total

    def r(x: float) -> float:
        return round(float(x), 2)

    insurance_pct_label = f"Cargo Insurance ({insurance_rate * 100:.2f}%)".rstrip("0").rstrip(".")
    if "(" in insurance_pct_label and insurance_pct_label.endswith(")"):
        # keep the "%)" suffix after trailing-zero trim
        insurance_pct_label = insurance_pct_label.replace("%)", "%)")

    # Visibility taxonomy:
    #   "client"     — shown to public + customer (catalog calculator, customer cabinet, deal-attached estimate)
    #   "manager"    — shown to manager/teamlead/admin only (internal logistics breakdown)
    #   "admin_only" — shown to teamlead/admin only (margins, hidden fees, cash/off-books, damage coefficients)
    #
    # Category taxonomy (drives the profitability widget):
    #   "cost"     — actual cash going out (vehicle, auction fees, ocean, inland, port fees, customs documentation, insurance, parking, forwarder, damage handling)
    #   "tax"      — government / customs (customs duty, VAT)
    #   "revenue"  — BIBI Cars' own income (company services, BB Cars commission)
    #   "info"     — derivation row, never contributes to total (customsBase, declaredValue)
    #   "discount" — manager-applied reduction (added at projection time, not by engine)
    breakdown = [
        # ─ Auction side: client sees a single CAR & AUCTION total composed of price + auctionTotal.
        #   We expose the 3 auction sub-fees as "manager" so internal staff can audit them.
        {"key": "auctionBuyerFee",   "label": "Auction Buyer Fee",                 "value": r(buyer_fee),       "visibility": "manager",    "category": "cost"},
        {"key": "auctionGateFee",    "label": "Auction Gate Fee",                  "value": r(gate_fee),        "visibility": "manager",    "category": "cost"},
        {"key": "auctionTitleFee",   "label": "Auction Title Fee",                 "value": r(title_fee),       "visibility": "manager",    "category": "cost"},
        # ─ Logistics (USA pipeline)
        #   Wave 4 — usaInland is now state-aware: amount = bucket_base × vehicle_multiplier
        #   with state→port→miles resolution. The breakdown row carries the
        #   resolved state / port / bucket under ``meta`` so internal
        #   consumers (admin live-preview, breakdown audit) can show *why*
        #   the number is what it is, while the public label stays byte
        #   identical to pre-Wave-4 ("Delivery By Truck Across The USA").
        {
            "key": "usaInland",
            "label": "Delivery By Truck Across The USA",
            "value": r(usa_inland),
            "visibility": "client",
            "category": "cost",
            "meta": {
                "state":       inland_resolution.get("state"),
                "exportPort":  inland_resolution.get("exportPort"),
                "miles":       inland_resolution.get("miles"),
                "bucket":      inland_resolution.get("bucket"),
                "bucketName":  inland_resolution.get("bucketName"),
                "basePrice":   inland_resolution.get("basePrice"),
                "multiplier":  inland_resolution.get("multiplier"),
                "fallback":    inland_resolution.get("fallback"),
                "modelUsed":   bool(inland_resolution.get("enabled")),
            },
        },
        {
            "key": "ocean",
            "label": "Delivery By Ship",
            "value": r(ocean),
            "visibility": "client",
            "category": "cost",
            "meta": {
                "exportPort":      ocean_resolution.get("exportPort"),
                "destinationPort": ocean_resolution.get("destinationPort"),
                "lanePrice":       ocean_resolution.get("lanePrice"),
                "multiplier":      ocean_resolution.get("multiplier"),
                "fallback":        ocean_resolution.get("fallback"),
                "modelUsed":       bool(ocean_resolution.get("enabled")),
            },
        },
        {"key": "portForwarding",    "label": "Forwarding At The Port & Customs",  "value": r(port_forwarding), "visibility": "admin_only", "category": "cost"},
        {"key": "portParking",       "label": "Port Parking Lot",                  "value": r(port_parking),    "visibility": "admin_only", "category": "cost"},
        {
            "key": "euDelivery",
            "label": "Delivery To Bulgaria",
            "value": r(eu_delivery),
            "visibility": "client",
            "category": "cost",
            "meta": {
                "euPort":      eu_resolution.get("euPort"),
                "destination": eu_resolution.get("destination"),
                "amountEur":   eu_resolution.get("amountEur"),
                "amountUsd":   eu_resolution.get("amountUsd"),
                "fxRate":      eu_resolution.get("fxRate"),
                "fallback":    eu_resolution.get("fallback"),
                "modelUsed":   bool(eu_resolution.get("enabled")),
            },
        },
        # ─ Final fees
        {"key": "customs",           "label": "Customs Clearance (Duty + Docs)",   "value": r(customs_total),   "visibility": "client",     "category": "tax"},
        {"key": "parkingBG",         "label": "Parking In Bulgaria",               "value": r(parking_bg),      "visibility": "admin_only", "category": "cost"},
        {"key": "insurance",         "label": f"Cargo Insurance ({insurance_rate * 100:g}%)", "value": r(insurance),       "visibility": "manager",    "category": "cost"},
        {"key": "companyServices",   "label": "The Cost Of A'CARS Services",       "value": r(company_services),"visibility": "client",     "category": "revenue"},
    ]
    if damaged:
        breakdown.append({"key": "damageHandling", "label": "Damage Handling (Salvage Inspection)", "value": r(damage_handling_fee), "visibility": "admin_only", "category": "cost"})

    return {
        "success": True,
        "calculation": {
            "vehiclePrice":     r(price),
            "auctionTotal":     r(auction_total),
            "deliveryTotal":    r(delivery_total),
            "total":            r(grand_total),
            "currency":         "USD",
            "port":             port,
            "auction":          auction,
            "vehicleType":      vehicle_type,
            "damaged":          damaged,
            "customsBase":      r(customs_base),
            "customsDuty":      r(customs_duty),
            "damageHandling":   r(damage_handling_fee),
            "breakdown":        breakdown,
            "profileCode":      profile.get("code", DEFAULT_PROFILE_CODE),
            # Wave 4 — surfaced state-aware inland resolution so the UI
            # can render "Texas → Houston · 250 mi · Short · ×1.5 pickup"
            # next to the inland line without re-parsing the breakdown.
            "usaInland":        {
                "amount":      r(usa_inland),
                "state":       inland_resolution.get("state"),
                "exportPort":  inland_resolution.get("exportPort"),
                "miles":       inland_resolution.get("miles"),
                "bucket":      inland_resolution.get("bucket"),
                "bucketName":  inland_resolution.get("bucketName"),
                "basePrice":   inland_resolution.get("basePrice"),
                "multiplier":  inland_resolution.get("multiplier"),
                "fallback":    inland_resolution.get("fallback"),
                "modelUsed":   bool(inland_resolution.get("enabled")),
            },
            # Wave 4 — surfaced ocean-freight resolution so the admin
            # live-preview / breakdown audit can show the lane bucket and
            # destination delta without re-parsing the breakdown row.
            "oceanFreight":     {
                "amount":          r(ocean),
                "exportPort":      ocean_resolution.get("exportPort"),
                "destinationPort": ocean_resolution.get("destinationPort"),
                "lanePrice":       ocean_resolution.get("lanePrice"),
                "multiplier":      ocean_resolution.get("multiplier"),
                "fallback":        ocean_resolution.get("fallback"),
                "modelUsed":       bool(ocean_resolution.get("enabled")),
            },
            # Wave 4.2 — surfaced EU-delivery resolution for admin
            # live-preview / breakdown audit.
            "euDelivery":       {
                "amount":      r(eu_delivery),
                "euPort":      eu_resolution.get("euPort"),
                "destination": eu_resolution.get("destination"),
                "amountEur":   eu_resolution.get("amountEur"),
                "amountUsd":   eu_resolution.get("amountUsd"),
                "fxRate":      eu_resolution.get("fxRate"),
                "fallback":    eu_resolution.get("fallback"),
                "modelUsed":   bool(eu_resolution.get("enabled")),
            },
            # legacy flat keys (backwards compatibility)
            "auctionFees":      r(auction_total),
            "shippingUSA":      r(usa_inland),
            "shippingSea":      r(ocean),
            "customs":          r(customs_total),
        },
        # ── Legacy admin Live Preview shape ───────────────────────────────────
        # CalculatorAdmin.js (and a few older managers) expect these keys at
        # the response root. There is no margin/hidden-fee model in the
        # current calculator, so the "internal" view simply mirrors the
        # client view (hiddenFee=0, controllableMargin=0).
        "formattedBreakdown": breakdown,
        "totals": {
            "visible": r(grand_total),
            "internal": r(grand_total),
        },
        "hiddenBreakdown": {
            "hiddenFee": 0,
        },
        "margin": {
            "controllableMargin": 0,
        },
    }


async def _apply_usa_visibility_overrides(result: dict) -> dict:
    """Phase Final / Block 5 — wrap USA calculator result with overrides."""
    try:
        from app.services.calculator_visibility import load_overrides, apply_overrides
        overrides = await load_overrides()
        if overrides:
            calc = result.get("calculation") or {}
            bd = calc.get("breakdown") or []
            new_bd = apply_overrides(bd, overrides)
            calc["breakdown"] = new_bd
            result["calculation"] = calc
            result["formattedBreakdown"] = new_bd
    except Exception:
        pass
    return result


__all__ = ["_calculate_korea", "calculator_calculate"]
