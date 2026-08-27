"""
app/services/calculator_config_cache.py
========================================

Phase 6.5+ Wave 3 (LANDING 2026-05-20) — calc-engine SERVER_STATE closure.

Canonical home for the calculator-engine **stateful** layer: the
TTL-cache + seed routine + config loader. Final piece of the
5.5/B-era 43-symbol ``CALC_ENGINE_DEP`` cluster retirement (Waves 1+2
handled the stateless pieces; Wave 3 retires this stateful tail).

Architectural rationale
───────────────────────

Pre-Wave-3 these 3 callables lived in ``server.py``:

  * ``_ensure_calculator_seed`` (server.py:9370) — async; seeds 7
    calculator collections on first call; references ``db``, ``logger``,
    and 44 constants.
  * ``_load_calc_config`` (server.py:9599) — async; reads cache or
    loads profile + routes + fees from DB; references ``db``, ``logger``,
    and the module-level ``_CALC_CACHE`` + ``_CALC_CACHE_TTL``.
  * ``_invalidate_calc_cache`` (server.py:9592) — sync; resets the
    module-level cache state; called by admin config-mutating endpoints.

What made them "SERVER_STATE-coupled" was NOT the constants (those
moved cleanly in Wave 2 via re-export). It was:

  1. **Module-level mutable state** — ``_CALC_CACHE`` is a per-process
     dict mutated in-place. Three callables share a single binding.
  2. **db global** — ``db`` is the AsyncIOMotorDatabase server.py
     references directly.
  3. **logger global** — ``logger`` is the module-level
     ``logging.getLogger("bibi-v3.2")`` instance.

Wave 3 resolution — the runtime-accessor pattern (mirror of
``app.core.db_runtime`` + ``app.core.socket_runtime``):

  1. **Cache state lives here.** ``_CACHE`` + ``_CACHE_TTL`` are
     module-level in THIS file. Callers cannot access the dict
     directly — only via ``get_calc_config()`` and ``invalidate_cache()``.
  2. **db accessed via** ``app.core.db_runtime.get_db()`` accessor.
     Zero ``import server``.
  3. **logger via** ``logging.getLogger(__name__)`` — owns its own
     logger, doesn't borrow from server.

Public API (3 callables — these are now FORMAL public API, no
leading underscore):

  * ``async def ensure_calculator_seed() -> None``
  * ``async def get_calc_config(profile_code: str = DEFAULT_PROFILE_CODE)
                              -> Dict[str, Any]``
  * ``def invalidate_cache() -> None``

server.py keeps 3 thin compat shims (``_ensure_calculator_seed``,
``_load_calc_config``, ``_invalidate_calc_cache``) — provably
semantics-free transport-layer wrappers per the compat-shim invariant
(see PHASE6_5_WAVE_2_CLOSED.md): each shim is exactly the form
``from app.services.calculator_config_cache import X as _impl; return _impl(args)``.

Wave 3 closes the architecture program
───────────────────────────────────────

Post-Wave-3 the calc-engine cluster is FULLY canonicalized:

  * All constants  → ``app/core/calculator_constants.py``
  * Pure helpers   → ``app/services/calculator_pure.py``
  * Stateful trio  → ``app/services/calculator_config_cache.py`` (this module)
  * Engine bodies  → ``app/services/calculator.py``

``server.py`` becomes a *compatibility shell* for the calc-engine
surface — it owns 5 thin shims and a re-export block, nothing else.

EXTRACTION_AUX_BRIDGES stays at 2 by design — ``_resolve_bearer``
(CUSTOMER_AUTH_DEP, semantics-sensitive) and ``_tracking_snapshot``
(TRACKING_PROVIDERS_DEP, cold-start fallback) are declared
**permanent operational bridges** in the closure document.

See ``ARCHITECTURE_PROGRAM_CLOSED.md`` for the final program-level
audit.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.db_runtime import get_db
from app.core.calculator_constants import (
    # USA-pipeline constants
    AUCTION_FEES,
    AUCTION_TIERED_FEES,
    CALCULATOR_PORTS,
    COMPANY_SERVICES,
    CUSTOMS_DOCUMENTATION,
    CUSTOMS_DUTY_RATE,
    DAMAGE_HANDLING_FEE_USD,
    DAMAGED_CUSTOMS_FACTOR,
    DEFAULT_PROFILE_CODE,
    INSURANCE_RATE,
    OFFICIAL_FEES_USD,
    PARKING_BULGARIA,
    PORT_FORWARDING,
    PORT_OCEAN_ADJUST,
    PORT_PARKING,
    VEHICLE_EU_DELIVERY,
    VEHICLE_OCEAN_BASE,
    VEHICLE_USA_INLAND,
    # Korea-pipeline constants
    KOREA_ADDITIONAL_FEES_EUR,
    KOREA_AUCTION_FEE_PERCENT,
    KOREA_BB_CARS_COMMISSION_EUR,
    KOREA_BG_TRANSPORT_EUR,
    KOREA_BIBI_SERVICE_FEE,
    KOREA_CUSTOMS_DUTY_RATE,
    KOREA_DAMAGE_HANDLING_FEE_USD,
    KOREA_DAMAGED_CUSTOMS_FACTOR,
    KOREA_DOCUMENTS_MAIL_DEFAULT,
    KOREA_FORWARDER_FEE_DEFAULT,
    KOREA_FX_USD_TO_EUR,
    KOREA_INLAND_DEFAULT,
    KOREA_INSURANCE_DEFAULT,
    KOREA_LOGISTICS_PACKAGE,
    KOREA_OFFICIAL_FEES_USD,
    KOREA_PROFILE_CODE,
    KOREA_SEA_DEFAULT,
    KOREA_TECH_INSPECTION_EUR,
    KOREA_USE_LOGISTICS_PACKAGE,
    KOREA_VAT_RATE,
    KOREA_UNDERVALUE_PERCENT,
    VEHICLE_KOREA_BG,
    VEHICLE_KOREA_INLAND,
    VEHICLE_KOREA_SEA,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Module-level TTL cache state — owned here (NOT server.py)
# ═══════════════════════════════════════════════════════════════════════

_CACHE: Dict[str, Any] = {
    "ts": 0.0,
    "profile": None,
    "routes": None,
    "fees": None,
}
_CACHE_TTL: float = 15.0  # seconds


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def invalidate_cache() -> None:
    """Reset the calculator config TTL cache. Called by admin
    config-mutating endpoints in server.py (5 callsites).

    VERBATIM port from server.py:9592 (Phase 6.5+ Wave 3 — calc-engine
    SERVER_STATE closure, 2026-05-20).
    """
    _CACHE["ts"] = 0.0
    _CACHE["profile"] = None
    _CACHE["routes"] = None
    _CACHE["fees"] = None


async def ensure_calculator_seed() -> None:
    """Seed calculator_profile / routes / auction_fees collections if empty.
    Also forward-fills any newly-added fields on existing profiles (idempotent).

    VERBATIM port from server.py:9370 (Phase 6.5+ Wave 3 — calc-engine
    SERVER_STATE closure, 2026-05-20). The only substantive change vs
    the server.py original: ``db`` → ``get_db()`` (via the
    ``app.core.db_runtime`` accessor); ``logger`` → module-local.
    Semantics, ordering, idempotency, and field-set are byte-identical.
    """
    db = get_db()
    prof = await db.calculator_profile.find_one({"code": DEFAULT_PROFILE_CODE})
    if not prof:
        await db.calculator_profile.insert_one({
            "code": DEFAULT_PROFILE_CODE,
            "name": "Standard Bulgaria",
            "currency": "USD",
            "destinationCountry": "BG",
            "isActive": True,
            # Fixed fees
            "portForwarding": PORT_FORWARDING,
            "portParking": PORT_PARKING,
            "parkingBulgaria": PARKING_BULGARIA,
            "companyServices": COMPANY_SERVICES,
            "customsDocumentation": CUSTOMS_DOCUMENTATION,
            "customsDutyRate": CUSTOMS_DUTY_RATE,
            "insuranceRate": INSURANCE_RATE,
            # Damage adjustments (admin-editable)
            "damagedCustomsFactor": DAMAGED_CUSTOMS_FACTOR,
            "damageHandlingFeeUsd": DAMAGE_HANDLING_FEE_USD,
            "officialFees": OFFICIAL_FEES_USD,
            # Per-auction gate/title fees
            "auctionFees": AUCTION_FEES,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # Forward-fill newly added fields on existing USA profile (idempotent).
        usa_defaults = {
            "damagedCustomsFactor": DAMAGED_CUSTOMS_FACTOR,
            "damageHandlingFeeUsd": DAMAGE_HANDLING_FEE_USD,
            "officialFees": OFFICIAL_FEES_USD,
        }
        usa_patch = {k: v for k, v in usa_defaults.items() if prof.get(k) is None}
        if usa_patch:
            await db.calculator_profile.update_one(
                {"code": DEFAULT_PROFILE_CODE},
                {"$set": usa_patch},
            )

    # Routes — UPSERT each known (rateType, port, vehicleType) so newly added
    # ports/vehicle types appear automatically without wiping admin overrides.
    for vtype, amount in VEHICLE_USA_INLAND.items():
        rid = f"usa-{vtype}"
        existing = await db.calculator_routes.find_one({"id": rid})
        if not existing:
            await db.calculator_routes.insert_one({
                "id": rid,
                "profileCode": DEFAULT_PROFILE_CODE,
                "rateType": "usa_inland",
                "vehicleType": vtype,
                "amount": amount,
                "currency": "USD",
                "isActive": True,
            })

    for port in CALCULATOR_PORTS:
        for vtype, base in VEHICLE_OCEAN_BASE.items():
            rid = f"ocean-{port['code']}-{vtype}"
            existing = await db.calculator_routes.find_one({"id": rid})
            if existing:
                continue
            amount = (base + PORT_OCEAN_ADJUST.get(port["code"], 0)) if base else 0
            await db.calculator_routes.insert_one({
                "id": rid,
                "profileCode": DEFAULT_PROFILE_CODE,
                "rateType": "ocean",
                "destinationCode": port["code"],
                "vehicleType": vtype,
                "amount": amount,
                "currency": "USD",
                "isActive": True,
            })

    for vtype, amount in VEHICLE_EU_DELIVERY.items():
        rid = f"eu-{vtype}"
        existing = await db.calculator_routes.find_one({"id": rid})
        if not existing:
            await db.calculator_routes.insert_one({
                "id": rid,
                "profileCode": DEFAULT_PROFILE_CODE,
                "rateType": "eu_delivery",
                "destinationCode": "BG",
                "vehicleType": vtype,
                "amount": amount,
                "currency": "USD",
                "isActive": True,
            })

    # Deduplicate any pre-existing auction-fee tier docs (older versions
    # inserted them twice because the seeder ran without an idempotency check).
    try:
        seen_keys = set()
        async for doc in db.calculator_auction_fees.find(
            {"profileCode": DEFAULT_PROFILE_CODE}, {"_id": 1, "id": 1}
        ).sort("_id", 1):
            key = doc.get("id")
            if not key:
                continue
            if key in seen_keys:
                await db.calculator_auction_fees.delete_one({"_id": doc["_id"]})
            else:
                seen_keys.add(key)
    except Exception as _dedup_err:
        logger.warning(f"[CALC] auction_fees dedupe skipped: {_dedup_err}")

    if await db.calculator_auction_fees.count_documents({"profileCode": DEFAULT_PROFILE_CODE}) == 0:
        tier_docs = []
        for lo, hi, fee in AUCTION_TIERED_FEES:
            tier_docs.append({
                "id": f"tier-{lo}",
                "profileCode": DEFAULT_PROFILE_CODE,
                "minBid": lo,
                "maxBid": hi,
                "fee": fee,
                "currency": "USD",
                "isActive": True,
            })
        if tier_docs:
            await db.calculator_auction_fees.insert_many(tier_docs)

    # ──────────────────────────────────────────────────────────────────
    # KOREA → ROMANIA → BULGARIA profile + routes (independent from USA)
    # ──────────────────────────────────────────────────────────────────
    korea_prof = await db.calculator_profile.find_one({"code": KOREA_PROFILE_CODE})
    if not korea_prof:
        await db.calculator_profile.insert_one({
            "code": KOREA_PROFILE_CODE,
            "name": "Korea → Romania → Bulgaria",
            "currency": "USD",
            "destinationCountry": "BG",
            "originCountry": "KR",
            "isActive": True,
            # Korea-specific configurable fields
            "auctionFeePercent": KOREA_AUCTION_FEE_PERCENT,
            "useLogisticsPackage": KOREA_USE_LOGISTICS_PACKAGE,
            "logisticsPackage": KOREA_LOGISTICS_PACKAGE,
            "koreaInlandTransport": KOREA_INLAND_DEFAULT,
            "seaShipping": KOREA_SEA_DEFAULT,
            "insurance": KOREA_INSURANCE_DEFAULT,
            "forwarderFee": KOREA_FORWARDER_FEE_DEFAULT,
            "documentsMailFee": KOREA_DOCUMENTS_MAIL_DEFAULT,
            "customsDutyRate": KOREA_CUSTOMS_DUTY_RATE,
            "vatRate": KOREA_VAT_RATE,
            "undervaluePercent": KOREA_UNDERVALUE_PERCENT,
            "bibiServiceFee": KOREA_BIBI_SERVICE_FEE,
            "bgTransportEur": KOREA_BG_TRANSPORT_EUR,
            "technicalInspectionEur": KOREA_TECH_INSPECTION_EUR,
            "bbCarsCommissionEur": KOREA_BB_CARS_COMMISSION_EUR,
            "additionalFeesEur": KOREA_ADDITIONAL_FEES_EUR,
            "fxUsdToEur": KOREA_FX_USD_TO_EUR,
            # Damage + official fees (admin-editable per profile)
            "damagedCustomsFactor": KOREA_DAMAGED_CUSTOMS_FACTOR,
            "damageHandlingFeeKoreaUsd": KOREA_DAMAGE_HANDLING_FEE_USD,
            "officialFeesUsd": KOREA_OFFICIAL_FEES_USD,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # Forward-fill newly added fields on existing Korea profile (idempotent).
        kr_defaults = {
            "damagedCustomsFactor": KOREA_DAMAGED_CUSTOMS_FACTOR,
            "damageHandlingFeeKoreaUsd": KOREA_DAMAGE_HANDLING_FEE_USD,
            "officialFeesUsd": KOREA_OFFICIAL_FEES_USD,
        }
        kr_patch = {k: v for k, v in kr_defaults.items() if korea_prof.get(k) is None}
        if kr_patch:
            await db.calculator_profile.update_one(
                {"code": KOREA_PROFILE_CODE},
                {"$set": kr_patch},
            )

    # Korea inland transport rates (per vehicle type)
    for vtype, amount in VEHICLE_KOREA_INLAND.items():
        rid = f"korea-inland-{vtype}"
        existing = await db.calculator_routes.find_one({"id": rid})
        if not existing:
            await db.calculator_routes.insert_one({
                "id": rid,
                "profileCode": KOREA_PROFILE_CODE,
                "rateType": "korea_inland",
                "vehicleType": vtype,
                "amount": amount,
                "currency": "USD",
                "isActive": True,
            })

    # Korea→Romania sea shipping rates (per vehicle type)
    for vtype, amount in VEHICLE_KOREA_SEA.items():
        rid = f"korea-sea-{vtype}"
        existing = await db.calculator_routes.find_one({"id": rid})
        if not existing:
            await db.calculator_routes.insert_one({
                "id": rid,
                "profileCode": KOREA_PROFILE_CODE,
                "rateType": "korea_sea",
                "originCode": "KR",
                "destinationCode": "constanta",
                "vehicleType": vtype,
                "amount": amount,
                "currency": "USD",
                "isActive": True,
            })

    # Romania→Bulgaria delivery (per vehicle type, EUR)
    for vtype, amount in VEHICLE_KOREA_BG.items():
        rid = f"korea-bg-{vtype}"
        existing = await db.calculator_routes.find_one({"id": rid})
        if not existing:
            await db.calculator_routes.insert_one({
                "id": rid,
                "profileCode": KOREA_PROFILE_CODE,
                "rateType": "korea_bg_transport",
                "originCode": "constanta",
                "destinationCode": "BG",
                "vehicleType": vtype,
                "amount": amount,
                "currency": "EUR",
                "isActive": True,
            })


async def get_calc_config(profile_code: str = DEFAULT_PROFILE_CODE) -> Dict[str, Any]:
    """Load calculator config (profile + routes + tiered fees) with TTL cache.

    VERBATIM port from server.py:9599 (Phase 6.5+ Wave 3 — calc-engine
    SERVER_STATE closure, 2026-05-20). Same ``db`` → ``get_db()``
    substitution; cache state lives in module-local ``_CACHE``.

    NOTE: pre-Wave-3 callers used the name ``_load_calc_config``. The
    leading underscore was a "module-private" marker that's no longer
    appropriate now that this is a formal public API surface for the
    canonical home. server.py keeps the old name as a thin compat shim.
    """
    now = time.time()
    if now - _CACHE["ts"] < _CACHE_TTL and _CACHE["profile"]:
        return {
            "profile": _CACHE["profile"],
            "routes": _CACHE["routes"],
            "fees": _CACHE["fees"],
        }
    try:
        await ensure_calculator_seed()
    except Exception as e:  # pragma: no cover
        logger.warning(f"[calc] seed check failed: {e}")

    db = get_db()
    profile = await db.calculator_profile.find_one({"code": profile_code}, {"_id": 0}) or {}
    routes_cursor = db.calculator_routes.find(
        {"profileCode": profile_code, "isActive": {"$ne": False}}, {"_id": 0}
    )
    routes = await routes_cursor.to_list(length=500)
    fees_cursor = db.calculator_auction_fees.find(
        {"profileCode": profile_code, "isActive": {"$ne": False}}, {"_id": 0}
    ).sort("minBid", 1)
    fees = await fees_cursor.to_list(length=100)

    _CACHE.update({"ts": now, "profile": profile, "routes": routes, "fees": fees})
    return {"profile": profile, "routes": routes, "fees": fees}


__all__ = [
    "ensure_calculator_seed",
    "get_calc_config",
    "invalidate_cache",
]
