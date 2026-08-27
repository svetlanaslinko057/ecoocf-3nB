"""
app/core/calculator_constants.py
=================================

Phase 6.5+ Wave 2 (LANDING) — calculator-constants cluster canonical home.

Canonical home for the **38 PURE_CONSTANT** symbols + the
**1 internal-only constant** (``AUCTION_TIERED_FEES``) that together
constitute the calculator-engine cluster's static data layer. Created
in 2026-05-20 per the Phase 6.5+ Wave 2 mandate (the second calc-engine
cluster reduction wave; the first one — Wave 1 — retired
``_find_route_amount`` to ``app/services/calculator_pure.py``).

Why a separate module under ``app/core/``
─────────────────────────────────────────

  * No deps. Module has ZERO imports beyond the stdlib (it doesn't
    import anything at all — these are literal data). This is the
    structural property that lets it sit at the very bottom of the
    dependency DAG and break the calc-engine ↔ server.py latent cycle.
  * Co-tenants. ``app/core/`` already hosts the inventory module
    (``app_state_targets.py``), the runtime contracts module
    (``architecture_invariants.py``), the db accessor
    (``db_runtime.py``), the socket accessor (``socket_runtime.py``).
    Calculator constants slot in cleanly as the data-layer sibling.
  * No new tier created — fits the existing ``app/core/`` discipline.

Scope (locked verbatim by Wave 2 PREP freeze tests, 2026-05-20)
───────────────────────────────────────────────────────────────

  * **38 PURE_CONSTANT** symbols:
      - 3 catalog tables: ``VEHICLE_TYPES``, ``CALCULATOR_PORTS``,
        ``AUCTION_FEES``
      - 14 USA-pipeline constants: ``DEFAULT_PROFILE_CODE``,
        ``VEHICLE_USA_INLAND``, ``VEHICLE_OCEAN_BASE``,
        ``PORT_OCEAN_ADJUST``, ``VEHICLE_EU_DELIVERY``,
        ``PORT_FORWARDING``, ``PORT_PARKING``, ``PARKING_BULGARIA``,
        ``COMPANY_SERVICES``, ``CUSTOMS_DOCUMENTATION``,
        ``CUSTOMS_DUTY_RATE``, ``INSURANCE_RATE``,
        ``DAMAGED_CUSTOMS_FACTOR``, ``DAMAGE_HANDLING_FEE_USD``
      - 21 Korea-pipeline constants: ``KOREA_PROFILE_CODE``,
        ``KOREA_USE_LOGISTICS_PACKAGE``, ``KOREA_AUCTION_FEE_PERCENT``,
        ``KOREA_LOGISTICS_PACKAGE``, ``KOREA_INLAND_DEFAULT``,
        ``KOREA_SEA_DEFAULT``, ``KOREA_INSURANCE_DEFAULT``,
        ``KOREA_FORWARDER_FEE_DEFAULT``,
        ``KOREA_DOCUMENTS_MAIL_DEFAULT``, ``KOREA_CUSTOMS_DUTY_RATE``,
        ``KOREA_VAT_RATE``, ``KOREA_UNDERVALUE_PERCENT``,
        ``KOREA_DAMAGED_CUSTOMS_FACTOR``,
        ``KOREA_DAMAGE_HANDLING_FEE_USD``,
        ``KOREA_OFFICIAL_FEES_USD``, ``KOREA_BIBI_SERVICE_FEE``,
        ``KOREA_FX_USD_TO_EUR``, ``KOREA_BG_TRANSPORT_EUR``,
        ``KOREA_ADDITIONAL_FEES_EUR``, ``KOREA_TECH_INSPECTION_EUR``,
        ``KOREA_BB_CARS_COMMISSION_EUR``
  * **1 internal-only constant**: ``AUCTION_TIERED_FEES`` (the tiered
    auction buyer-fee ladder used by the legacy fallback in
    ``_tiered_buyer_fee*`` helpers). NOT part of the original 43-symbol
    ``CALC_ENGINE_DEP`` cluster (it never had its own bridge row); folded
    into Wave 2 by user-locked mandate ("constants и ``_tiered_buyer_fee*``
    structurally coupled; отдельная 1.5 только увеличит transient
    topology; now the economically rational move = single coordinated
    retirement").

Values are VERBATIM ports from ``server.py`` (lines 9265–9411 +
line 9308 for ``AUCTION_TIERED_FEES``). No semantic change. No
formula change. No rounding change. server.py keeps a re-export
block at the old def-site lines (38 + 1 = 39 names) for back-compat
and in-file consumers (``_ensure_calculator_seed`` references
``DEFAULT_PROFILE_CODE``, ``PORT_FORWARDING``, ``AUCTION_TIERED_FEES``,
etc.).

Successor extraction work (Wave 3)
──────────────────────────────────

  * ``_ensure_calculator_seed`` + ``_load_calc_config`` together
    (SERVER_STATE — they reference ``db``, ``logger``, and module
    globals ``_CALC_CACHE``/``_CALC_CACHE_TTL`` that need own runtime
    accessor pattern).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ══════════════════════════════════════════════════════════════════════
# Catalog tables (3) — verbatim from server.py:9265-9304
# ══════════════════════════════════════════════════════════════════════

CALCULATOR_PORTS: List[Dict[str, Any]] = [
    # ── Black Sea (closest to BG) ───────────────────────────────────────
    {"id": "burgas",      "code": "burgas",      "name": "Burgas",       "country": "BG", "region": "Black Sea"},
    {"id": "varna",       "code": "varna",       "name": "Varna",        "country": "BG", "region": "Black Sea"},
    {"id": "constanta",   "code": "constanta",   "name": "Constanta",    "country": "RO", "region": "Black Sea"},
    {"id": "odessa",      "code": "odessa",      "name": "Odessa",       "country": "UA", "region": "Black Sea"},
    # ── Mediterranean ──────────────────────────────────────────────────
    {"id": "piraeus",     "code": "piraeus",     "name": "Piraeus",      "country": "GR", "region": "Mediterranean"},
    {"id": "thessaloniki","code": "thessaloniki","name": "Thessaloniki", "country": "GR", "region": "Mediterranean"},
    {"id": "trieste",     "code": "trieste",     "name": "Trieste",      "country": "IT", "region": "Mediterranean"},
    {"id": "genoa",       "code": "genoa",       "name": "Genoa",        "country": "IT", "region": "Mediterranean"},
    # ── North Sea / Baltic (most common from US) ───────────────────────
    {"id": "bremerhaven", "code": "bremerhaven", "name": "Bremerhaven",  "country": "DE", "region": "North Sea"},
    {"id": "hamburg",     "code": "hamburg",     "name": "Hamburg",      "country": "DE", "region": "North Sea"},
    {"id": "antwerp",     "code": "antwerp",     "name": "Antwerp",      "country": "BE", "region": "North Sea"},
    {"id": "rotterdam",   "code": "rotterdam",   "name": "Rotterdam",    "country": "NL", "region": "North Sea", "default": True},
    {"id": "zeebrugge",   "code": "zeebrugge",   "name": "Zeebrugge",    "country": "BE", "region": "North Sea"},
    # ── Baltic ─────────────────────────────────────────────────────────
    {"id": "klaipeda",    "code": "klaipeda",    "name": "Klaipeda",     "country": "LT", "region": "Baltic"},
    {"id": "gdansk",      "code": "gdansk",      "name": "Gdansk",       "country": "PL", "region": "Baltic"},
    {"id": "gdynia",      "code": "gdynia",      "name": "Gdynia",       "country": "PL", "region": "Baltic"},
]

VEHICLE_TYPES: List[Dict[str, str]] = [
    {"code": "sedan",      "name": "Sedan"},
    {"code": "suv",        "name": "SUV / Crossover"},
    {"code": "bigSUV",     "name": "Big SUV / 4x4"},
    {"code": "pickup",     "name": "Pickup"},
    {"code": "van",        "name": "Van"},
    {"code": "motorcycle", "name": "Motorcycle"},
    {"code": "trailer",    "name": "Trailer"},
]

AUCTION_FEES: Dict[str, Dict[str, float]] = {
    "copart": {"buyer_fee_percent": 10, "gate_fee": 79, "title_fee": 55},
    "iaai": {"buyer_fee_percent": 9, "gate_fee": 69, "title_fee": 45},
}

# ══════════════════════════════════════════════════════════════════════
# Internal-only constant — tiered auction buyer-fee ladder
# Verbatim from server.py:9308
# ══════════════════════════════════════════════════════════════════════

AUCTION_TIERED_FEES: List[Tuple[float, float, float]] = [
    (0, 99.99, 25),
    (100, 499.99, 49),
    (500, 999.99, 75),
    (1000, 1499.99, 110),
    (1500, 1999.99, 135),
    (2000, 3999.99, 200),
    (4000, 5999.99, 280),
    (6000, 7999.99, 360),
    (8000, 9999.99, 400),
    (10000, 14999.99, 450),
    (15000, 19999.99, 550),
    (20000, 29999.99, 650),
    (30000, 49999.99, 800),
    (50000, 99999.99, 1000),
    (100000, 10_000_000, 1200),
]

# ══════════════════════════════════════════════════════════════════════
# USA-pipeline per-vehicle / per-port defaults (3) — verbatim
# server.py:9326-9348
# ══════════════════════════════════════════════════════════════════════

VEHICLE_USA_INLAND: Dict[str, float] = {
    "sedan": 350, "suv": 400, "bigSUV": 450, "pickup": 500,
    # New types — admin must configure via UI; 0 = "not set yet"
    "motorcycle": 0, "trailer": 0,
}
VEHICLE_OCEAN_BASE: Dict[str, float] = {
    "sedan": 1100, "suv": 1250, "bigSUV": 1400, "pickup": 1500,
    "motorcycle": 0, "trailer": 0,
}
PORT_OCEAN_ADJUST: Dict[str, float] = {
    # Black Sea
    "burgas": 0, "varna": 0, "constanta": 50, "odessa": 100,
    # Mediterranean
    "piraeus": 80, "thessaloniki": 90, "trieste": 120, "genoa": 130,
    # North Sea
    "bremerhaven": -50, "hamburg": -40, "antwerp": -30, "rotterdam": -30, "zeebrugge": -20,
    # Baltic
    "klaipeda": 0, "gdansk": 50, "gdynia": 60,
}
VEHICLE_EU_DELIVERY: Dict[str, float] = {
    "sedan": 400, "suv": 450, "bigSUV": 500, "pickup": 550,
    "motorcycle": 0, "trailer": 0,
}

# ══════════════════════════════════════════════════════════════════════
# USA-pipeline fixed-fee defaults (8) — verbatim server.py:9350-9360
# ══════════════════════════════════════════════════════════════════════

PORT_FORWARDING: float = 200
PORT_PARKING: float = 75
PARKING_BULGARIA: float = 50
COMPANY_SERVICES: float = 1500
CUSTOMS_DOCUMENTATION: float = 100
INSURANCE_RATE: float = 0.015
CUSTOMS_DUTY_RATE: float = 0.10

# Damage adjustments (USA flow) — verbatim server.py:9359-9360
DAMAGED_CUSTOMS_FACTOR: float = 0.70    # salvage valuation: customs base × 0.70
DAMAGE_HANDLING_FEE_USD: float = 200.0  # extra USA port-side damage handling

# Default profile code — verbatim server.py:9363
DEFAULT_PROFILE_CODE: str = "standard_bg"

# ══════════════════════════════════════════════════════════════════════
# KOREA-pipeline constants (21) — verbatim server.py:9371-9411
# ══════════════════════════════════════════════════════════════════════

KOREA_PROFILE_CODE: str = "korea_bg"

# Korea-side fixed defaults (admin-editable)
KOREA_AUCTION_FEE_PERCENT: float = 5.0   # 5% of vehicle_price
KOREA_LOGISTICS_PACKAGE: float = 3850.0  # USD — fix bundle
KOREA_USE_LOGISTICS_PACKAGE: bool = True  # if True → use 3850, else sum itemized
KOREA_INLAND_DEFAULT: float = 600.0
KOREA_SEA_DEFAULT: float = 1800.0
KOREA_INSURANCE_DEFAULT: float = 350.0
KOREA_FORWARDER_FEE_DEFAULT: float = 300.0
KOREA_DOCUMENTS_MAIL_DEFAULT: float = 200.0
KOREA_CUSTOMS_DUTY_RATE: float = 0.10
KOREA_VAT_RATE: float = 0.20
KOREA_UNDERVALUE_PERCENT: float = 0.30  # 30% of US logic
KOREA_BIBI_SERVICE_FEE: float = 940.0   # USD
KOREA_BG_TRANSPORT_EUR: float = 1000.0  # EUR
KOREA_TECH_INSPECTION_EUR: float = 100.0  # EUR
KOREA_BB_CARS_COMMISSION_EUR: float = 500.0  # EUR
KOREA_ADDITIONAL_FEES_EUR: float = 0.0
KOREA_FX_USD_TO_EUR: float = 0.885

# Korea damage adjustments + official fees (admin-editable per profile)
KOREA_DAMAGED_CUSTOMS_FACTOR: float = 0.70    # salvage valuation reducer
KOREA_DAMAGE_HANDLING_FEE_USD: float = 250.0  # Romania-side extra reinspection
KOREA_OFFICIAL_FEES_USD: float = 0.0          # extra govt fees included in VAT base


# ══════════════════════════════════════════════════════════════════════
# Out-of-scope-Wave-2, in-scope-Wave-3 constants (5)
# ══════════════════════════════════════════════════════════════════════
# These 5 symbols were NOT part of the original 43-symbol CALC_ENGINE_DEP
# cluster (they had 0 cross-module consumers; only in-file references in
# ``_ensure_calculator_seed``). Wave 2 PREP excluded them; Wave 3 folds
# them in because they're co-tenants of the seed routine which is itself
# moving to ``app/services/calculator_config_cache.py``.

# AUCTIONS list — verbatim from server.py
AUCTIONS: List[Dict[str, str]] = [
    {"code": "copart", "name": "Copart"},
    {"code": "iaai", "name": "IAAI"},
]

# Per-vehicle-type defaults for Korea inland transport (USD).
# Verbatim from server.py.
VEHICLE_KOREA_INLAND: Dict[str, float] = {
    "sedan": 500, "suv": 600, "bigSUV": 700, "pickup": 800,
    "motorcycle": 0, "trailer": 0,
}
# Per-vehicle-type defaults for Korea→Romania sea shipping (USD).
VEHICLE_KOREA_SEA: Dict[str, float] = {
    "sedan": 1800, "suv": 2000, "bigSUV": 2300, "pickup": 2500,
    "motorcycle": 0, "trailer": 0,
}
# Per-vehicle-type defaults for Romania→Bulgaria transport (EUR).
VEHICLE_KOREA_BG: Dict[str, float] = {
    "sedan": 1000, "suv": 1100, "bigSUV": 1200, "pickup": 1300,
    "motorcycle": 0, "trailer": 0,
}

# Official-fees default (USA flow VAT-base addition; was at server.py).
OFFICIAL_FEES_USD: float = 0.0


__all__ = [
    # Catalog tables (3)
    "VEHICLE_TYPES",
    "CALCULATOR_PORTS",
    "AUCTION_FEES",
    # USA-pipeline constants (14)
    "DEFAULT_PROFILE_CODE",
    "VEHICLE_USA_INLAND",
    "VEHICLE_OCEAN_BASE",
    "PORT_OCEAN_ADJUST",
    "VEHICLE_EU_DELIVERY",
    "PORT_FORWARDING",
    "PORT_PARKING",
    "PARKING_BULGARIA",
    "COMPANY_SERVICES",
    "CUSTOMS_DOCUMENTATION",
    "CUSTOMS_DUTY_RATE",
    "INSURANCE_RATE",
    "DAMAGED_CUSTOMS_FACTOR",
    "DAMAGE_HANDLING_FEE_USD",
    # Korea-pipeline constants (21)
    "KOREA_PROFILE_CODE",
    "KOREA_USE_LOGISTICS_PACKAGE",
    "KOREA_AUCTION_FEE_PERCENT",
    "KOREA_LOGISTICS_PACKAGE",
    "KOREA_INLAND_DEFAULT",
    "KOREA_SEA_DEFAULT",
    "KOREA_INSURANCE_DEFAULT",
    "KOREA_FORWARDER_FEE_DEFAULT",
    "KOREA_DOCUMENTS_MAIL_DEFAULT",
    "KOREA_CUSTOMS_DUTY_RATE",
    "KOREA_VAT_RATE",
    "KOREA_UNDERVALUE_PERCENT",
    "KOREA_DAMAGED_CUSTOMS_FACTOR",
    "KOREA_DAMAGE_HANDLING_FEE_USD",
    "KOREA_OFFICIAL_FEES_USD",
    "KOREA_BIBI_SERVICE_FEE",
    "KOREA_FX_USD_TO_EUR",
    "KOREA_BG_TRANSPORT_EUR",
    "KOREA_ADDITIONAL_FEES_EUR",
    "KOREA_TECH_INSPECTION_EUR",
    "KOREA_BB_CARS_COMMISSION_EUR",
    # Internal-only constant (1)
    "AUCTION_TIERED_FEES",
    # Wave 3 additions (5) — folded in to support the seed-routine
    # canonical home migration from server.py
    "AUCTIONS",
    "VEHICLE_KOREA_INLAND",
    "VEHICLE_KOREA_SEA",
    "VEHICLE_KOREA_BG",
    "OFFICIAL_FEES_USD",
]
