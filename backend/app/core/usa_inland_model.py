"""
app/core/usa_inland_model.py
============================

Wave 4 (2026-05-26) — Proper USA inland logistics model.

Replaces the legacy flat ``VEHICLE_USA_INLAND = {sedan:350, suv:400, …}``
look-up (where USA inland was the same number regardless of *where in the
USA the vehicle was picked up*) with a real distance-based bucket model:

    state                        ──┐
                                   ├──► pickup state determines the
    pickup auction (fallback) ──┘    preferred export port

    state + preferred_export_port ──► miles  (looked up from a static
                                              51×8 distance matrix —
                                              derived data, NOT admin-
                                              editable)

    miles ──► distance bucket  (local / short / medium / long / extreme)

    bucket × vehicle_size_class_multiplier ──► inland USD

Why a *static* distance matrix and not Google Maps routing?
-----------------------------------------------------------
*  predictable margins (controllable by admin, not by Google's API)
*  no API dependency, no rate limits, no per-request cost
*  fast (zero IO at calc time — pure dict lookup)
*  reasonable accuracy for car shipping (truckers price by zone, not by
   exact mile)

Why is ``miles`` NOT admin-editable?
------------------------------------
Miles is *derived data* (a function of state + port). If admin could
edit miles independently of port, they could create physically
impossible combinations (e.g., Seattle + 350 mi from Alabama) which
would silently corrupt every quote. The matrix is computed once from
geographic centres + haversine × 1.25 road-factor + 25-mi rounding,
which is good enough for trucking ESTIMATION. The admin's job is to
pick the PREFERRED PORT per state (rare, one-off configuration) and to
tune bucket prices + vehicle multipliers (pricing knobs). Distances
are physics, not policy.

Public API
----------
``USA_EXPORT_PORTS``      ─ 8 export ports (code, name, state, region)
``USA_STATE_TO_PORT``     ─ 51 entries (50 states + DC):
                            { state_code: { port } }  # miles is derived
``STATE_PORT_DISTANCES``  ─ 51×8 distance matrix:
                            { state_code: { port_code: miles } }
``USA_INLAND_BUCKETS_DEFAULT`` ─ 5 distance buckets
                            (local / short / medium / long / extreme)
                            each: { minMiles, maxMiles, basePrice }
``USA_INLAND_VEHICLE_MULTIPLIERS_DEFAULT`` ─ 7 vehicle types
                            (sedan / suv / bigSUV / pickup / van /
                             motorcycle / trailer) → multiplier
``AUCTION_DEFAULT_STATE``  ─ legacy fallback: copart→FL, iaai→TX
``USA_DESTINATION_PORTS``  ─ 8 EU destination ports actually used
                            (Wave 4 reduced from 16 to 8)
``bucket_for_miles(miles, buckets)`` ─ which bucket does N miles fit?
``miles_between(state, port_code, overrides)`` ─ matrix lookup.
``compute_usa_inland(state, vehicle_type, model)`` ─ the engine.
                            Returns dict with all derivation rows so the
                            UI can show the breakdown the user wants.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════
# Section 1 — Export ports (USA side)
# ═══════════════════════════════════════════════════════════════════════
# Eight real export ports used by USED-car exporters. Region is the
# coarse coverage area (so the UI can group ports geographically).

USA_EXPORT_PORTS: List[Dict[str, str]] = [
    {"code": "newark",       "name": "Newark",       "state": "NJ", "region": "North-East"},
    {"code": "baltimore",    "name": "Baltimore",    "state": "MD", "region": "East"},
    {"code": "savannah",     "name": "Savannah",     "state": "GA", "region": "South-East"},
    {"code": "miami",        "name": "Miami",        "state": "FL", "region": "Florida"},
    {"code": "new_orleans",  "name": "New Orleans",  "state": "LA", "region": "Gulf"},
    {"code": "houston",      "name": "Houston",      "state": "TX", "region": "South"},
    {"code": "los_angeles",  "name": "Los Angeles",  "state": "CA", "region": "West"},
    {"code": "seattle",      "name": "Seattle",      "state": "WA", "region": "North-West"},
]


# ═══════════════════════════════════════════════════════════════════════
# Section 2 — Geographic anchors (used to derive the distance matrix)
# ═══════════════════════════════════════════════════════════════════════
# (lat, lon) of port cities + state geographic centres. These are NOT
# admin-editable — they are physical-world facts. Used at module-load
# time to populate STATE_PORT_DISTANCES via haversine × road-factor.

_PORT_COORDS: Dict[str, tuple] = {
    "newark":       (40.7357, -74.1724),
    "baltimore":    (39.2904, -76.6122),
    "savannah":     (32.0809, -81.0912),
    "miami":        (25.7617, -80.1918),
    "new_orleans":  (29.9511, -90.0715),
    "houston":      (29.7604, -95.3698),
    "los_angeles":  (34.0522, -118.2437),
    "seattle":      (47.6062, -122.3321),
}

# State geographic centre (approximate "centre of population" point —
# more useful for trucking estimates than the geometric centre).
_STATE_COORDS: Dict[str, tuple] = {
    "AL": (32.7794, -86.8287),
    "AK": (64.0685, -152.2782),
    "AZ": (34.2744, -111.6602),
    "AR": (34.8938, -92.4426),
    "CA": (37.1841, -119.4696),
    "CO": (38.9972, -105.5478),
    "CT": (41.6219, -72.7273),
    "DE": (38.9896, -75.5050),
    "DC": (38.9101, -77.0147),
    "FL": (28.6305, -82.4497),
    "GA": (32.6415, -83.4426),
    "HI": (20.2927, -156.3737),
    "ID": (44.3509, -114.6130),
    "IL": (40.0417, -89.1965),
    "IN": (39.8942, -86.2816),
    "IA": (42.0751, -93.4960),
    "KS": (38.4937, -98.3804),
    "KY": (37.5347, -85.3021),
    "LA": (31.0689, -91.9968),
    "ME": (45.3695, -69.2428),
    "MD": (39.0550, -76.7909),
    "MA": (42.2596, -71.8083),
    "MI": (44.3467, -85.4102),
    "MN": (46.2807, -94.3053),
    "MS": (32.7364, -89.6678),
    "MO": (38.3566, -92.4580),
    "MT": (47.0527, -109.6333),
    "NE": (41.5378, -99.7951),
    "NV": (39.3289, -116.6312),
    "NH": (43.6805, -71.5811),
    "NJ": (40.1907, -74.6728),
    "NM": (34.4071, -106.1126),
    "NY": (42.9538, -75.5268),
    "NC": (35.5557, -79.3877),
    "ND": (47.4501, -100.4659),
    "OH": (40.2862, -82.7937),
    "OK": (35.5889, -97.4943),
    "OR": (43.9336, -120.5583),
    "PA": (40.8781, -77.7996),
    "RI": (41.6762, -71.5562),
    "SC": (33.9169, -80.8964),
    "SD": (44.4443, -100.2263),
    "TN": (35.8580, -86.3505),
    "TX": (31.4757, -99.3312),
    "UT": (39.3055, -111.6703),
    "VT": (44.0687, -72.6658),
    "VA": (37.5215, -78.8537),
    "WA": (47.3826, -120.4472),
    "WV": (38.6409, -80.6227),
    "WI": (44.6243, -89.9941),
    "WY": (42.9957, -107.5512),
}


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    R = 3958.8  # earth radius in miles
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _road_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Approximate practical trucking distance.

    haversine × 1.25 road-factor (interstate corridors are rarely
    straight-line, this is the well-known trucking heuristic), then
    rounded to the nearest 25-mile increment so the matrix stays
    "human-readable" and matches industry pricing tables.
    """
    hav = _haversine_miles(lat1, lon1, lat2, lon2)
    road = hav * 1.25
    rounded = int(round(road / 25.0)) * 25
    return max(25, rounded)  # never let it collapse to 0


# Build the 51 × 8 distance matrix at module-load (zero IO at request-
# time). The result is an immutable mapping consumed by both the
# engine and the admin-defaults endpoint.

def _build_distance_matrix() -> Dict[str, Dict[str, int]]:
    matrix: Dict[str, Dict[str, int]] = {}
    for state, (slat, slon) in _STATE_COORDS.items():
        row: Dict[str, int] = {}
        for port, (plat, plon) in _PORT_COORDS.items():
            row[port] = _road_miles(slat, slon, plat, plon)
        matrix[state] = row
    return matrix


STATE_PORT_DISTANCES: Dict[str, Dict[str, int]] = _build_distance_matrix()


def miles_between(state: str, port_code: str, overrides: Optional[Dict[str, Dict[str, int]]] = None) -> int:
    """Look up miles for a (state, port) pair.

    Admin can override individual cells via ``overrides`` (rarely needed
    — only when the haversine + road-factor heuristic disagrees with
    reality for a specific lane).
    """
    code = (state or "").upper().strip()
    port = (port_code or "").strip()
    if overrides and code in overrides and port in overrides[code]:
        return int(overrides[code][port])
    row = STATE_PORT_DISTANCES.get(code)
    if not row:
        return 0
    return int(row.get(port, 0))


# ═══════════════════════════════════════════════════════════════════════
# Section 3 — State → preferred export port (the only admin-editable
# routing decision: which port we DEFAULT-route this state through)
# ═══════════════════════════════════════════════════════════════════════
# 50 states + DC = 51 rows. NO miles here — miles are derived from
# ``STATE_PORT_DISTANCES`` based on the chosen port. Admin can override
# the preferred port via profile.usaInlandModel.stateOverrides.
# Defaults pick the geographically nearest port from the 8 available
# (some are intentional non-nearest choices — e.g., ND routed to Seattle
# because the rail/intermodal link from Minneapolis to Seattle is real-
# world cheaper than trucking to Houston).

USA_STATE_TO_PORT: Dict[str, Dict[str, Any]] = {}
for _state in _STATE_COORDS:
    # Pick the closest port from the matrix for each state by default.
    _row = STATE_PORT_DISTANCES[_state]
    _nearest = min(_row.items(), key=lambda kv: kv[1])[0]
    USA_STATE_TO_PORT[_state] = {"port": _nearest}
del _state, _row, _nearest


# Hand-picked overrides where the nearest port is NOT the right business
# choice (intermodal economics, customs throughput, etc.). These are
# baked-in product decisions, not admin tweaks.
_PRODUCT_PREFERRED_OVERRIDES = {
    "ND": "seattle",       # Northern-Pacific rail corridor
    "SD": "seattle",       # same corridor
    "MT": "seattle",       # nearest is LA but Seattle is the real lane
    "WY": "seattle",       # Same
    "NM": "houston",       # Houston has more EU-bound vessel space than LA
    "CO": "houston",       # Houston intermodal
    "KS": "houston",       # Houston intermodal
    "NE": "houston",       # Houston intermodal
    "MN": "houston",       # Mississippi barge → Gulf is cheap
    "IA": "new_orleans",   # Mississippi corridor
    "MO": "new_orleans",   # Mississippi corridor
    "IL": "newark",        # Chicago has direct rail to NJ
    "MI": "newark",        # Detroit → NJ rail lane
    "WI": "newark",        # Same lane
    "OH": "baltimore",     # Pennsylvania Turnpike → Baltimore is faster
    "IN": "baltimore",     # Same
    "KY": "savannah",      # Crow-flies to Savannah is shortest
    "TN": "savannah",      # Same
}
for _s, _p in _PRODUCT_PREFERRED_OVERRIDES.items():
    if _s in USA_STATE_TO_PORT:
        USA_STATE_TO_PORT[_s] = {"port": _p}
del _s, _p


# ═══════════════════════════════════════════════════════════════════════
# Section 4 — Distance buckets (admin-editable)
# ═══════════════════════════════════════════════════════════════════════
# Five buckets, sedan-baseline price. Reading: anything from 0–299 mi
# falls into the "local" bucket and a sedan there costs $250 inland.
# Bucket boundaries are half-open: [minMiles, maxMiles).

USA_INLAND_BUCKETS_DEFAULT: List[Dict[str, Any]] = [
    {"code": "local",   "name": "Local",   "minMiles": 0,    "maxMiles": 300,    "basePrice": 250},
    {"code": "short",   "name": "Short",   "minMiles": 300,  "maxMiles": 700,    "basePrice": 450},
    {"code": "medium",  "name": "Medium",  "minMiles": 700,  "maxMiles": 1200,   "basePrice": 700},
    {"code": "long",    "name": "Long",    "minMiles": 1200, "maxMiles": 1800,   "basePrice": 1000},
    {"code": "extreme", "name": "Extreme", "minMiles": 1800, "maxMiles": 99999,  "basePrice": 1400},
]


# ═══════════════════════════════════════════════════════════════════════
# Section 5 — Vehicle-size multipliers (admin-editable)
# ═══════════════════════════════════════════════════════════════════════
# These are MULTIPLIERS over the sedan base price for the chosen bucket.
# Real-world container-space ratios; admin can fine-tune per fleet mix.
#   Sedan      = 1.0  baseline
#   SUV        = 1.2  (R-class crossover)
#   Big SUV    = 1.45 (Escalade / Tahoe / X7)
#   Pickup     = 1.5  (Silverado / F-150 / RAM)
#   Van        = 1.8  (Sprinter / Transit)
#   Motorcycle = 0.6  (sub-fraction of a slot)
#   Trailer    = 2.0  (custom — admin sets per case)

USA_INLAND_VEHICLE_MULTIPLIERS_DEFAULT: Dict[str, float] = {
    "sedan":      1.0,
    "suv":        1.2,
    "bigSUV":     1.45,
    "pickup":     1.5,
    "van":        1.8,
    "motorcycle": 0.6,
    "trailer":    2.0,
}


# ═══════════════════════════════════════════════════════════════════════
# Section 6 — Legacy auction → state fallback
# ═══════════════════════════════════════════════════════════════════════
# When the request payload lacks an explicit ``state``, fall back to the
# auction's flagship yard's state. This preserves backwards compatibility
# with the legacy ``{auction: copart}`` payload — Copart's marketing HQ is
# in Dallas TX but their largest yard activity (and the historical default
# for our pipeline) is Miami FL; IAAI's largest yard is Houston TX.

AUCTION_DEFAULT_STATE: Dict[str, str] = {
    "copart": "FL",
    "iaai":   "TX",
    "manheim": "GA",   # Manheim Atlanta
}


# ═══════════════════════════════════════════════════════════════════════
# Section 7 — Destination ports actually used (Wave 4 reduction)
# ═══════════════════════════════════════════════════════════════════════
# The public calculator now exposes only these 8 destination ports
# (down from 16) — they account for ~99% of real bookings. The other 8
# ports stay in ``CALCULATOR_PORTS`` (legacy) for admin profile back-compat
# but the UI no longer surfaces them.

USA_DESTINATION_PORTS: List[Dict[str, str]] = [
    # ─ Main (most-used) ─────────────────────────────────────────────────
    {"code": "rotterdam",   "name": "Rotterdam",   "country": "NL", "region": "North Sea", "tier": "main"},
    {"code": "hamburg",     "name": "Hamburg",     "country": "DE", "region": "North Sea", "tier": "main"},
    {"code": "bremerhaven", "name": "Bremerhaven", "country": "DE", "region": "North Sea", "tier": "main"},
    {"code": "klaipeda",    "name": "Klaipeda",    "country": "LT", "region": "Baltic",    "tier": "main"},
    # ─ Secondary ────────────────────────────────────────────────────────
    {"code": "gdansk",      "name": "Gdansk",      "country": "PL", "region": "Baltic",      "tier": "secondary"},
    {"code": "constanta",   "name": "Constanta",   "country": "RO", "region": "Black Sea",   "tier": "secondary"},
    {"code": "poti",        "name": "Poti",        "country": "GE", "region": "Black Sea",   "tier": "secondary"},
    {"code": "batumi",      "name": "Batumi",      "country": "GE", "region": "Black Sea",   "tier": "secondary"},
]


# ═══════════════════════════════════════════════════════════════════════
# Section 8 — Engine helpers
# ═══════════════════════════════════════════════════════════════════════

def bucket_for_miles(miles: float, buckets: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Find the bucket that contains ``miles``.

    Buckets are half-open intervals ``[minMiles, maxMiles)`` and MUST be
    sorted ascending by minMiles. If ``miles`` exceeds every bucket we
    return the last bucket (catch-all). If ``buckets`` is ``None`` the
    default ladder is used.
    """
    src = buckets if buckets else USA_INLAND_BUCKETS_DEFAULT
    if not src:
        return {"code": "default", "name": "Default", "minMiles": 0, "maxMiles": 99999, "basePrice": 0}
    safe_miles = max(0.0, float(miles or 0))
    for b in src:
        lo = float(b.get("minMiles", 0))
        hi = float(b.get("maxMiles", 0))
        if lo <= safe_miles < hi:
            return b
    return src[-1]  # extreme catch-all


def resolve_state(
    requested_state: Optional[str],
    auction: Optional[str] = None,
    fallback_map: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Normalise + resolve the pickup state.

    Priority:
      1. explicit ``requested_state`` (uppercased, trimmed)
      2. ``auction`` → default state via ``AUCTION_DEFAULT_STATE``
      3. ``None`` (caller should fall back to legacy flat lookup)
    """
    s = (requested_state or "").strip().upper()
    if s and len(s) == 2:
        return s
    if auction:
        src = fallback_map if fallback_map else AUCTION_DEFAULT_STATE
        v = src.get(auction.strip().lower())
        if v:
            return v.upper()
    return None


def compute_usa_inland(
    *,
    state: Optional[str],
    vehicle_type: str,
    auction: Optional[str] = None,
    profile_model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute the USA-inland leg as a dict with full derivation.

    Flow
    ----
    1. Resolve **state** (explicit > auction fallback > unknown).
    2. Resolve **preferred export port** for that state — from admin
       overrides if present, otherwise the bundled default.
    3. Look up **miles** from the static ``STATE_PORT_DISTANCES`` matrix
       (or a row-level admin override — rarely set).
    4. Pick **bucket** by ``bucket_for_miles(miles)``.
    5. ``amount = bucket.basePrice × vehicle_multiplier``.

    Notes
    -----
    *  Returns ``enabled=False`` when neither an explicit state nor an
       auction fallback could resolve a known state — the caller (the
       USA pipeline in ``calculator.py``) then falls back to the legacy
       per-port route lookup. This keeps existing profiles working.
    *  Miles is **never** read from the profile's per-state overrides as
       a free-form integer — it is always a function of the chosen port
       (via the matrix). Admin can override a specific (state, port)
       cell via ``profile_model.distanceOverrides[state][port]``, but
       they cannot float a state's miles independently of its port.
    """
    model = profile_model or {}
    if model.get("enabled") is False:
        return {
            "enabled": False, "state": state, "exportPort": None,
            "miles": 0.0, "bucket": None, "basePrice": 0.0,
            "multiplier": 0.0, "amount": 0.0, "fallback": "disabled",
        }

    buckets: List[Dict[str, Any]] = model.get("buckets") or USA_INLAND_BUCKETS_DEFAULT
    multipliers: Dict[str, float] = {
        **USA_INLAND_VEHICLE_MULTIPLIERS_DEFAULT,
        **(model.get("vehicleMultipliers") or {}),
    }
    fallback_map: Dict[str, str] = {
        **AUCTION_DEFAULT_STATE,
        **(model.get("auctionFallback") or {}),
    }
    # Per-state preferred-port overrides. Shape: { "AL": { "port": "houston" } }
    # Anything else in the dict is ignored (e.g., a stale "miles" field
    # left over from an old profile shape — we no longer trust admin-
    # entered miles).
    state_overrides: Dict[str, Dict[str, Any]] = model.get("stateOverrides") or {}
    # Optional per-cell distance overrides — rarely needed. Shape:
    # { "AL": { "houston": 510 } }
    distance_overrides: Dict[str, Dict[str, int]] = model.get("distanceOverrides") or {}

    # 1) Resolve state
    explicit = (state or "").strip().upper()
    resolved = explicit if (explicit and len(explicit) == 2) else None
    fallback_used: Optional[str] = "state" if resolved else None
    if not resolved and auction:
        v = fallback_map.get(auction.strip().lower())
        if v:
            resolved = v.upper()
            fallback_used = "auction"
    if not resolved:
        return {
            "enabled": False, "state": None, "exportPort": None,
            "miles": 0.0, "bucket": None, "basePrice": 0.0,
            "multiplier": 0.0, "amount": 0.0, "fallback": "missing",
        }

    # 2) Resolve preferred port (admin override > bundled default)
    default_entry = USA_STATE_TO_PORT.get(resolved) or {}
    override_entry = state_overrides.get(resolved) or {}
    export_port = str(override_entry.get("port") or default_entry.get("port") or "")
    if not export_port:
        return {
            "enabled": False, "state": resolved, "exportPort": None,
            "miles": 0.0, "bucket": None, "basePrice": 0.0,
            "multiplier": 0.0, "amount": 0.0, "fallback": "unknown_state",
        }

    # 3) Derive miles from the matrix (single source of truth)
    miles = float(miles_between(resolved, export_port, distance_overrides))

    # 4) Bucket
    b = bucket_for_miles(miles, buckets)
    try:
        base_price = float(b.get("basePrice") or 0)
    except (TypeError, ValueError):
        base_price = 0.0

    # 5) Multiplier
    try:
        mult = float(multipliers.get(vehicle_type, multipliers.get("sedan", 1.0)))
    except (TypeError, ValueError):
        mult = 1.0

    amount = round(base_price * mult, 2)

    return {
        "enabled": True,
        "state": resolved,
        "exportPort": export_port,
        "miles": miles,
        "bucket": str(b.get("code") or "default"),
        "bucketName": str(b.get("name") or b.get("code") or "Default"),
        "basePrice": round(base_price, 2),
        "multiplier": round(mult, 3),
        "amount": amount,
        "fallback": fallback_used or "state",
    }


__all__ = [
    "USA_EXPORT_PORTS",
    "USA_STATE_TO_PORT",
    "STATE_PORT_DISTANCES",
    "USA_INLAND_BUCKETS_DEFAULT",
    "USA_INLAND_VEHICLE_MULTIPLIERS_DEFAULT",
    "AUCTION_DEFAULT_STATE",
    "USA_DESTINATION_PORTS",
    "bucket_for_miles",
    "miles_between",
    "resolve_state",
    "compute_usa_inland",
]

