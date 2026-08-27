"""
Shipment journey helpers (Phase 5.4 / C-5a, extended in C-5e).
==============================================================

This module owns the shipment-domain helpers that were previously
defined inside ``server.py`` and bridged via ``from server import …``.

Public surface (C-5a + C-5e retirement targets)
-----------------------------------------------

``_smooth_eta_iso(prev_iso, new_iso, source_type) -> Optional[str]``
    Exponential moving-average smoother for shipment ETA timestamps.
    Prevents the UI from seeing "jumpy" arrival times when a new
    provider tick comes in.

``is_valid_movement(prev, new, elapsed_seconds) -> bool``
    GPS-spike rejection for live vessel positions. Returns ``True``
    if the new position is physically plausible given the elapsed
    time since the previous position; ``False`` if it implies an
    impossible cruise speed.

``get_current_stage(shipment) -> Optional[Dict]``           [C-5e]
    Return the active stage dict from ``shipment["stages"]``:
    first whose ``id == currentStageId``; fallback to first
    stage with ``status == "active"``; fallback to first stage.
    Pure read — no I/O, no side effects.

``serialize_journey(shipment) -> Dict``                     [C-5e]
    Public-safe journey view for the cabinet UI. Combines
    ``serialize_doc`` (from ``app.utils.serialization``) +
    ``get_current_stage`` (sibling) + region label + tracking
    health classification + emotional status text. Pure dict
    construction — no I/O, no side effects.

Constants moved with the functions (exclusively used by them)
-------------------------------------------------------------

``JOURNEY_SPIKE_MAX_KM_PER_120S``
    Maximum great-circle distance (km) two consecutive position
    samples may differ by when the gap is under 120 seconds.
    ~200 km / 120 s ≈ 100 knots — physically impossible for a
    cargo ship; treated as a GPS spike and rejected.

``JOURNEY_ETA_SMOOTH_ALPHA``
    EMA weight on the freshly-calculated ETA in the smoother:
    ``smoothed = old * (1 - alpha) + new * alpha``.

Module-private helpers (verbatim copies of server.py originals)
---------------------------------------------------------------

``__haversine_km`` and ``__source_category`` are byte-identical
copies of the server.py originals (C-5a). They are duplicated here ON
PURPOSE during C-5a because the canonical definitions in
``server.py`` still serve **non-shipment** callers (route-distance
sums, port-distance, source-change emit-throttle). Moving the
canonical versions out of ``server.py`` would either:

  * make ``server.py`` import from a shipments module to compute
    non-shipment distances (incorrect layering); or
  * require a parallel "generic geo / source-category util"
    refactor — explicitly forbidden by the C-5a mandate
    ("не превращать в generic geo util", "no geo helper cleanup").

``__location_label`` (C-5e) is a byte-identical copy of
``server.get_location_label`` (server.py:5089). Same duplication
rationale: ``server.py`` still calls ``get_location_label`` from
its tracking tick at ~line 6177 (non-journey-serialization caller).
Moving the canonical version would either inject a back-import or
require a "generic ui-label util" refactor — explicitly forbidden
by the C-5e mandate ("no journey schema redesign", "no thresholds
changes"). The duplication is **expected** and is reconciled in a
later phase (5.5 or 5.6).

The duplication is documented in ``PHASE5_4_C5A_CLOSED.md`` and
``PHASE5_4_C5E_CLOSED.md`` §"What was NOT changed".

Forbidden in C-5a (mandate verbatim)
------------------------------------

  * no behaviour changes
  * no threshold changes
  * no ETA logic cleanup
  * no geo helper cleanup
  * no route changes
  * no worker changes
  * no shipment orchestration movement
  * no journey serialization movement       ← lifted in C-5e for the two helpers
  * no generic shipment service abstraction
  * no Base utility abstraction
  * no static path movement
  * no audit / aggregator movement

Forbidden in C-5e (mandate verbatim)
------------------------------------

  * no shipment orchestration movement
  * no db access movement
  * no emit movement
  * no worker movement
  * no stage transition redesign
  * no journey schema redesign
  * no response shape changes
  * no route changes
  * no thresholds/ETA changes
  * no movement validation changes
  * no combining with ensure_shipment_stages
  * no moving identity_runtime helpers
  * no Tier-C wave 1 work

Phase trail
-----------

  * Phase 5.4 / C-5  — planned this move (PHASE5_4_C5_TIER_B_PLAN.md).
  * Phase 5.4 / C-5a — executed (_smooth_eta_iso, is_valid_movement).
  * Phase 5.4 / C-5e — extended (get_current_stage, serialize_journey).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ═════════════════════════════════════════════════════════════════════
# Constants (moved from server.py — single exclusive owner each)
# ═════════════════════════════════════════════════════════════════════

JOURNEY_SPIKE_MAX_KM_PER_120S: float = 200.0
"""Maximum kilometres two consecutive position samples may differ by
when the time gap is under 120 seconds. Threshold unchanged from
server.py:5302. Forbidden to mutate per C-5a mandate."""


JOURNEY_ETA_SMOOTH_ALPHA: float = 0.3
"""EMA weight on the freshly-calculated ETA. Threshold unchanged from
server.py:5305 (``weight of new_calc in EMA; old carries 1-alpha``).
Forbidden to mutate per C-5a mandate."""


# ─────────────────────────────────────────────────────────────────────
# Phase 6.2.ACTUAL (2026-05-20) — Shell Thinning execution.
# The two constants below + the two helpers further down
# (``_normalize_stage``, ``build_default_stages``) were moved VERBATIM
# from server.py (server.py:5413-5414 / 5460-5512) under the
# Phase 6.2.ACTUAL "Shell Thinning" mandate. They retired the last 2
# SHIPMENTS_DEP aux-bridges registered by 5.5/I.
#
# Semantic freeze contract preserved (PHASE6_2_SHELL_THINNING_PREP.md §4):
#   * output dict shape + key order   (PREP §4.1.1)
#   * id default: f"stage_{idx+1}"    (PREP §4.1.2, 1-based)
#   * type whitelist coercion         (PREP §4.1.3, invalid → "vessel")
#   * status whitelist coercion       (PREP §4.1.4, invalid → "pending")
#   * Ukrainian label default         (PREP §4.1.5, "Етап {idx+1}")
#   * container key + comment         (PREP §4.1.6, load-bearing doc)
#   * total arg unused-but-required   (PREP §4.1.7, signature parity)
#   * build_default_stages 1-element  (PREP §4.2.1)
#   * id shape "stage_{ts}_1"         (PREP §4.2.2, clock-derived)
#   * em-dash U+2014 in label         (PREP §4.2.3)
#   * status default "active"         (PREP §4.2.4)
#   * vessel default None             (PREP §4.2.5)
#   * datetime.now(timezone.utc)      (PREP §4.2.6, tz-aware)
#
# Phase 6.3.A architecture-invariants composite at boot will now report
# AUX=45 instead of 47 — auto-passes the <= 47 ratchet-down floor.
# ─────────────────────────────────────────────────────────────────────

JOURNEY_STAGE_TYPES = {"land", "vessel", "port"}
"""Whitelist of valid stage-type values. Single exclusive caller is
``_normalize_stage`` below; moved verbatim from server.py:5413 in
Phase 6.2.ACTUAL (Shell Thinning). Frozen per PREP §4.1.3."""

JOURNEY_STAGE_STATUSES = {"pending", "active", "done", "skipped"}
"""Whitelist of valid stage-status values. Single exclusive caller is
``_normalize_stage`` below; moved verbatim from server.py:5414 in
Phase 6.2.ACTUAL (Shell Thinning). Frozen per PREP §4.1.4."""


# ═════════════════════════════════════════════════════════════════════
# Module-private helpers (verbatim copies — see module docstring)
# ═════════════════════════════════════════════════════════════════════

def __haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometers.

    VERBATIM COPY of ``server._haversine_km`` (server.py:5058). The
    duplication is intentional during C-5a (see module docstring).
    The double-underscore prefix protects against accidental
    ``from app.utils.shipments import _haversine_km`` — only the
    public helpers below should be imported."""
    R = 6371.0  # Earth radius km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def __source_category(src: Optional[str]) -> str:
    """Group tracking sources into coarse categories for UI / change detection.

    VERBATIM COPY of ``server._source_category`` (server.py:5317).
    The duplication is intentional during C-5a (see module docstring).
    Same name-mangling guard as ``__haversine_km`` above."""
    if not src:
        return "unknown"
    if src.startswith("real"):
        return "real"
    if src == "interpolated":
        return "interpolated"
    return "simulated"


def __location_label(progress: Any) -> str:
    """Human-readable region label derived from journey progress (0..1).

    VERBATIM COPY of ``server.get_location_label`` (server.py:5089).
    The duplication is intentional during C-5e (see module docstring):
    ``server.py`` still calls ``get_location_label`` from its tracking
    tick at ~line 6177 (non-journey-serialization caller). Moving the
    canonical version would inject a back-import or require a "generic
    ui-label util" refactor — explicitly forbidden by the C-5e mandate
    ("no journey schema redesign", "no thresholds changes"). The
    duplication is reconciled in a later phase (5.5 or 5.6).

    Same name-mangling guard as ``__haversine_km`` / ``__source_category``
    above — only the public ``serialize_journey`` should call this."""
    if progress < 0.1:
        return "Origin Port"
    elif progress < 0.3:
        return "Leaving Coast"
    elif progress < 0.7:
        return "Mid-Ocean"
    elif progress < 0.9:
        return "Approaching Destination"
    else:
        return "Near Port"


# ═════════════════════════════════════════════════════════════════════
# Public helpers (C-5a retirement targets — were in server.py)
# ═════════════════════════════════════════════════════════════════════

def _smooth_eta_iso(
    prev_iso: Optional[str],
    new_iso: Optional[str],
    source_type: str,
) -> Optional[str]:
    """
    Smooth ETA with EMA so the client never sees 'jumpy' arrival times.
        new_eta = prev*(1-alpha) + new*alpha
    Cases:
      * no prev / no new → pass-through
      * prev or new unparseable → return the parseable one (or None)
      * REAL tracking source gets slightly more weight (alpha * 1.4, capped at 0.9)
        so real-world speed changes propagate faster.

    VERBATIM port from ``server._smooth_eta_iso`` (server.py:5328).
    Behaviour parity validated by
    ``tests/test_phase5_4_c5a_pure_utility_retirement.py``.
    """
    if not new_iso:
        return prev_iso
    if not prev_iso:
        return new_iso
    try:
        p = datetime.fromisoformat(str(prev_iso).replace("Z", "+00:00"))
        n = datetime.fromisoformat(str(new_iso).replace("Z", "+00:00"))
    except Exception:
        return new_iso
    alpha = JOURNEY_ETA_SMOOTH_ALPHA
    if __source_category(source_type) == "real":
        alpha = min(alpha * 1.4, 0.9)
    ts_prev = p.timestamp()
    ts_new = n.timestamp()
    blended = ts_prev * (1 - alpha) + ts_new * alpha
    smoothed = datetime.fromtimestamp(blended, tz=timezone.utc)
    return smoothed.isoformat().replace("+00:00", "Z")


def is_valid_movement(
    prev: Optional[Dict[str, Any]],
    new: Dict[str, Any],
    elapsed_seconds: Optional[float],
) -> bool:
    """
    Reject implausible GPS jumps: > 200 km in < 120 s.
    For larger gaps we use an implied max cruise speed of ~50 knots = ~93 km/h.

    VERBATIM port from ``server.is_valid_movement`` (server.py:5461).
    Behaviour parity validated by
    ``tests/test_phase5_4_c5a_pure_utility_retirement.py``.
    """
    try:
        if not prev or prev.get("lat") is None or prev.get("lng") is None:
            return True
        if new.get("lat") is None or new.get("lng") is None:
            return False
        dist = __haversine_km(prev["lat"], prev["lng"], new["lat"], new["lng"])
        elapsed = float(elapsed_seconds) if elapsed_seconds is not None else None
        # Short window — cargo ships physically can't exceed ~45 knots
        if elapsed is not None and elapsed < 120:
            if dist > JOURNEY_SPIKE_MAX_KM_PER_120S:
                return False
        # Longer window — use ~93 km/h cap with 30% tolerance
        elif elapsed is not None and elapsed > 0:
            max_km = (elapsed / 3600.0) * 93.0 * 1.3
            if dist > max(max_km, JOURNEY_SPIKE_MAX_KM_PER_120S):
                return False
        return True
    except Exception:
        return True  # permissive — never block a real update over a helper bug


# ═════════════════════════════════════════════════════════════════════
# Public helpers (C-5e retirement targets — were in server.py)
# ═════════════════════════════════════════════════════════════════════

def get_current_stage(shipment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the active stage dict from ``shipment["stages"]``.

    Resolution order (VERBATIM from server.py:5492):
      1. First stage whose ``id == shipment["currentStageId"]``
      2. First stage whose ``status == "active"``
      3. First stage of any kind
      4. ``None`` if ``stages`` is empty / missing.

    Pure read — no I/O, no side effects. Used by the cabinet UI
    (via ``serialize_journey``) and by ``admin_shipments`` /
    ``admin_resolver`` route handlers for read-only stage queries.

    VERBATIM port from ``server.get_current_stage`` (server.py:5492).
    Behaviour parity asserted by
    ``tests/test_phase5_4_c5e_shipment_helpers.py``.
    """
    stages = shipment.get("stages") or []
    cur_id = shipment.get("currentStageId")
    if cur_id:
        for s in stages:
            if s.get("id") == cur_id:
                return s
    # fallback: first 'active'
    for s in stages:
        if s.get("status") == "active":
            return s
    # fallback: first
    return stages[0] if stages else None


def serialize_journey(shipment: Dict[str, Any]) -> Dict[str, Any]:
    """Public-safe journey view for the cabinet UI.

    Composes:
      * ``serialize_doc`` (canonical: ``app.utils.serialization``) —
        deep-converts Mongo ObjectIds, datetimes, etc. to JSON-safe forms.
      * ``get_current_stage`` (sibling helper) — current stage dict.
      * ``__location_label`` (module-private) — coarse region label
        from progress (0..1).
      * ``trackingHealth`` classification into 4 buckets:
        ``ok`` / ``estimated`` / ``stale`` / ``no_data`` — computed
        live from ``lastTrackingUpdate`` age so it always reflects
        real freshness.
      * ``emotionalText`` — human-readable Ukrainian status line
        derived from current stage type + destination name.

    Returns a fixed-shape dict for the cabinet response (load-bearing
    UI contract — forbidden to mutate per C-5e mandate "no journey
    schema redesign", "no response shape changes").

    Pure dict construction — no ``db``, no ``sio``, no ``audit``, no
    ``await``. The function is sync. Side effects in calling code
    (persistence, emit) MUST stay in the caller — out of C-5e scope.

    VERBATIM port from ``server.serialize_journey`` (server.py:5584).
    Behaviour parity asserted by
    ``tests/test_phase5_4_c5e_shipment_helpers.py``.
    """
    from app.utils.serialization import serialize_doc  # canonical (C-5a)
    s = serialize_doc(dict(shipment))
    # always include the computed current stage even if client doesn't
    # fetch stages separately
    cur = get_current_stage(shipment)
    # Region label (e.g. "Origin Port", "Mid-Ocean", "Near Port")
    # derived from progress.
    try:
        region_label = __location_label(shipment.get("progress") or 0)
    except Exception:
        region_label = None

    # ── trackingHealth ─────────────────────────────────────────────
    # Classify shipment freshness into 4 buckets the UI can render:
    #   ok          — real data, < 10 min old
    #   estimated   — interpolated / simulated OR real 10 min – 3 h old
    #   stale       — any source, last update > 3 h ago (red pill)
    #   no_data     — no source at all / no position / tracking off
    # Computed live here (not persisted) so it always reflects real age.
    def _parse_dt(v):
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except Exception:
                return None
        return None
    src = shipment.get('trackingSource') or (shipment.get('currentPosition') or {}).get('source')
    last_real = shipment.get('lastRealPosition') or {}
    last_upd = (
        _parse_dt((shipment.get('currentPosition') or {}).get('updatedAt'))
        or _parse_dt(shipment.get('lastTrackingUpdate'))
        or _parse_dt(last_real.get('fetched_at'))
    )
    now_ts = datetime.now(timezone.utc)
    age_sec = (now_ts - last_upd).total_seconds() if last_upd else None

    if not shipment.get('trackingActive'):
        health = 'no_data'
    elif src is None or shipment.get('currentPosition') is None:
        health = 'no_data'
    elif age_sec is not None and age_sec > 3 * 3600:
        health = 'stale'
    elif isinstance(src, str) and src.startswith('real') and (age_sec is None or age_sec < 600):
        health = 'ok'
    else:
        health = 'estimated'

    # Emotional status line (for client UI):
    #   «Автомобіль в Атлантичному океані»
    #   «Приближається до порту Rotterdam»
    #   «В порту Rotterdam, очікує розвантаження»
    #   «Доставляється до клієнта» (land stage)
    emotional_text = None
    try:
        cur_stage_type = (cur or {}).get('type')
        prog = shipment.get('progress') or 0
        dest_name = (shipment.get('destination') or {}).get('name')
        if cur_stage_type == 'vessel':
            if prog >= 0.95 and dest_name:
                emotional_text = f"Приближається до порту {dest_name}"
            else:
                emotional_text = region_label and f"Автомобіль в пути: {region_label}"
        elif cur_stage_type == 'port':
            emotional_text = f"В порту {dest_name}" if dest_name else "В порту призначення"
        elif cur_stage_type == 'land':
            emotional_text = "Доставляється до клієнта"
    except Exception:
        pass

    return {
        "id": s.get("id"),
        "vin": s.get("vin"),
        "dealId": s.get("dealId"),
        "customerId": s.get("customerId"),
        "managerId": s.get("managerId"),
        "origin": s.get("origin"),
        "destination": s.get("destination"),
        "route": s.get("route") or [],
        "stages": s.get("stages") or [],
        "currentStageId": s.get("currentStageId"),
        "currentStage": serialize_doc(cur) if cur else None,
        # Convenience: current container + current vessel pulled out for UI.
        "currentContainer": (cur or {}).get("container") if cur else None,
        "currentVessel": (cur or {}).get("vessel") or s.get("vessel"),
        "currentPosition": s.get("currentPosition"),
        "lastRealPosition": s.get("lastRealPosition"),
        "progress": s.get("progress", 0),
        "location": region_label,
        "liveEta": s.get("liveEta"),
        "eta": s.get("eta"),
        "trackingActive": s.get("trackingActive", False),
        "trackingSource": s.get("trackingSource"),
        "trackingHealth": health,                     # NEW: ok/estimated/stale/no_data
        "trackingAgeSec": int(age_sec) if age_sec is not None else None,
        "emotionalText": emotional_text,              # NEW: human-readable status
        "lastTrackingUpdate": s.get("lastTrackingUpdate"),
        "events": (s.get("events") or [])[-20:],
        "updated_at": s.get("updated_at"),
        "created_at": s.get("created_at"),
    }


# ═════════════════════════════════════════════════════════════════════
# Phase 6.2.ACTUAL (2026-05-20) — Shell Thinning movers
# ═════════════════════════════════════════════════════════════════════
#
# The two helpers below were moved VERBATIM from server.py (server.py:5460
# and server.py:5489) under the Phase 6.2.ACTUAL "Shell Thinning" mandate.
# They retired the last 2 SHIPMENTS_DEP aux-bridges registered by 5.5/I.
#
# Their target home was decided by PREP §5.1 ("sibling extraction" pattern,
# mirroring 5.5/F2): this module already owns adjacent shipment-shape
# utilities (``get_current_stage``, ``serialize_journey``), making it the
# natural canonical home. The alternative — ``app/services/shipments.py``
# — was rejected because it IS the orchestration home, and moving these
# helpers in would INCREASE its gravity (anti-pattern; see PREP §5.1).
#
# Forbidden categories (PREP §8, signed declaration):
#   * no body edits (verbatim move)
#   * no signature edits (``total`` kept unused-but-required)
#   * no schema/key-order edits
#   * no whitelist edits (JOURNEY_STAGE_TYPES / JOURNEY_STAGE_STATUSES frozen)
#   * no Ukrainian label edits
#   * no em-dash → hyphen substitution
#   * no clock-source edits
#   * no async wrappers (these stay sync)
#
# Compatibility shape:
#   * server.py keeps thin compat shims for both helpers (< 10 LOC each)
#     for in-file caller chains; shims delegate 1:1 to canonical home.
#   * server.py keeps re-exports of JOURNEY_STAGE_TYPES + JOURNEY_STAGE_STATUSES
#     for any qualified-name caller (``server.JOURNEY_STAGE_TYPES``).
# ─────────────────────────────────────────────────────────────────────

def build_default_stages(
    origin: Optional[Dict[str, Any]],
    destination: Optional[Dict[str, Any]],
    vessel: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Default single-stage journey: one 'vessel' stage from origin → destination.
    Manager can always replace / edit stages later.

    VERBATIM port from ``server.build_default_stages`` (server.py:5460).
    Behaviour parity validated by ``tests/test_phase6_2_shell_thinning.py``
    (B6 + B7 + B-block semantics from PREP §4.2).
    """
    ogin_name = (origin or {}).get("name") or "Origin"
    dest_name = (destination or {}).get("name") or "Destination"
    now = datetime.now(timezone.utc)
    return [
        {
            "id": f"stage_{int(now.timestamp())}_1",
            "type": "vessel",
            "label": f"Морське перевезення — {ogin_name} → {dest_name}",
            "from": ogin_name,
            "to": dest_name,
            "fromPoint": origin,
            "toPoint": destination,
            "status": "active",
            "vessel": vessel or None,
            "startedAt": now,
            "completedAt": None,
        }
    ]


def _normalize_stage(stage: Dict[str, Any], idx: int, total: int) -> Dict[str, Any]:
    """Ensure required keys are present on a stage dict.

    VERBATIM port from ``server._normalize_stage`` (server.py:5489).
    The ``total`` parameter is unused inside the body — it is preserved
    in the signature for signature-parity with the 5 in-file callsites
    that pass it positionally (PREP §4.1.7).

    Behaviour parity validated by ``tests/test_phase6_2_shell_thinning.py``
    (B1-B5 + S-block structural pins).
    """
    stage = dict(stage or {})
    if not stage.get("id"):
        stage["id"] = f"stage_{idx+1}"
    stype = str(stage.get("type") or "vessel").lower()
    if stype not in JOURNEY_STAGE_TYPES:
        stype = "vessel"
    stage["type"] = stype
    stage.setdefault("label", f"Етап {idx + 1}")
    stage.setdefault("from", None)
    stage.setdefault("to", None)
    status = str(stage.get("status") or "pending").lower()
    if status not in JOURNEY_STAGE_STATUSES:
        status = "pending"
    stage["status"] = status
    stage.setdefault("vessel", None)
    # Container layer — can change independently from vessel (vessel swap without
    # transshipment = same container continues on new ship). Structure:
    #   {"number": "MSKU1234567", "sealNumber": "...", "boundAt": <datetime>}
    stage.setdefault("container", None)
    stage.setdefault("startedAt", None)
    stage.setdefault("completedAt", None)
    return stage


__all__ = [
    "JOURNEY_SPIKE_MAX_KM_PER_120S",
    "JOURNEY_ETA_SMOOTH_ALPHA",
    "JOURNEY_STAGE_TYPES",
    "JOURNEY_STAGE_STATUSES",
    "_smooth_eta_iso",
    "is_valid_movement",
    "get_current_stage",
    "serialize_journey",
    "build_default_stages",
    "_normalize_stage",
]
