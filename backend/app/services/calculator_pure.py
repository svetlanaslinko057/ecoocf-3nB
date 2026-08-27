"""
app/services/calculator_pure.py
================================

Phase 6.5+ Wave 1 (CLOSED 2026-05-20) — calculator-pure helper module.
Phase 6.5+ Wave 2 (LANDING 2026-05-20) — extended with the 2
``_tiered_buyer_fee*`` helpers (folded from former Wave 1.5 per
user-locked mandate).

Canonical home for **truly pure** calculator engine helpers — those
with zero module-globals, zero DB access, zero FastAPI app reference,
and zero server-state coupling. Sibling-extraction pattern (mirror of
6.2.ACTUAL ``app/utils/shipments`` for the 2 shipment helpers).

Scope post-Wave-2
─────────────────

  * ``_find_route_amount`` — Wave 1; pure routing-table lookup
    (verbatim port from server.py:9679). Zero deps.
  * ``_tiered_buyer_fee`` — Wave 2; legacy ladder fallback used when
    no admin-configured tiers exist. Reads ``AUCTION_TIERED_FEES`` from
    its new canonical home in ``app.core.calculator_constants`` (NOT
    from ``server``). Verbatim port from server.py:9725.
  * ``_tiered_buyer_fee_from_db`` — Wave 2; admin-configured ladder
    with fallback to ``AUCTION_TIERED_FEES`` when ``fees`` empty.
    Verbatim port from server.py:9703.

Audit-trail correction logged in:
  * Wave 1 closeout — PHASE6_5_WAVE_1_CLOSED.md §audit-trail.
  * Wave 2 closeout — PHASE6_5_WAVE_2_CLOSED.md.

Successor extraction work (Wave 3, needs own PREP)
──────────────────────────────────────────────────

  * ``_ensure_calculator_seed`` + ``_load_calc_config`` together
    (true SERVER_STATE — they need ``db``, ``logger``, and a runtime
    accessor pattern mirroring ``db_runtime`` / ``socket_runtime``).
"""
from __future__ import annotations

from typing import Optional

# ─────────────────────────────────────────────────────────────────────
# Wave 2 dependency — AUCTION_TIERED_FEES lives in its Wave-2 canonical
# home. Imported at module load (pure data, zero side effects).
# ─────────────────────────────────────────────────────────────────────
from app.core.calculator_constants import AUCTION_TIERED_FEES


def _find_route_amount(
    routes: list,
    rate_type: str,
    vehicle_type: str,
    *,
    destination_code: Optional[str] = None,
    origin_code: Optional[str] = None,
    default: float = 0.0,
) -> float:
    """Return the ``amount`` of the first route row matching the
    requested ``rate_type`` + ``vehicle_type`` (and optional
    destination/origin filters).

    VERBATIM port from server.py:9679 (Phase 6.5+ Wave 1 — Shell
    Thinning execution, 2026-05-20).

    Pure: zero module-globals, zero DB access, zero side-effects.
    First-hit-wins (NOT best-match — see B-block goldens).

    Behaviour parity validated by
    ``tests/test_phase6_5_wave1_calculator_pure_retirement.py``
    (B1-B3 — first-hit, vehicleType-wildcard, default + type coercion).
    """
    for r_ in routes:
        if r_.get("rateType") != rate_type:
            continue
        if r_.get("vehicleType") not in (None, vehicle_type):
            continue
        if destination_code and r_.get("destinationCode") not in (None, destination_code):
            continue
        if origin_code and r_.get("originCode") not in (None, origin_code):
            continue
        amount = r_.get("amount")
        if amount is not None:
            return float(amount)
    return float(default)


def _tiered_buyer_fee_from_db(price: float, fees: list) -> float:
    """Tiered buyer-fee resolver — admin-configured ladder first,
    legacy ladder fallback when ``fees`` empty.

    VERBATIM port from server.py:9703 (Phase 6.5+ Wave 2 — calculator
    constants & helpers retirement, 2026-05-20). Pure: zero
    module-globals, zero DB access (the DB query is the caller's job;
    this function only consumes the loaded list).

    Reads ``AUCTION_TIERED_FEES`` from ``app.core.calculator_constants``
    (its canonical Wave-2 home) when no admin tiers configured.

    Behaviour pinned by 5.5/B golden parity (18 PINNED_HASHES) — Wave 2
    must preserve byte-identical responses.
    """
    try:
        p = float(price or 0)
    except (TypeError, ValueError):
        p = 0.0
    if not fees:
        # Fall back to hard-coded ladder
        for lo, hi, fee in AUCTION_TIERED_FEES:
            if lo <= p <= hi:
                return float(fee)
        return float(AUCTION_TIERED_FEES[-1][2])
    for row in fees:
        try:
            lo = float(row.get("minBid", 0))
            hi = float(row.get("maxBid", 10_000_000))
        except (TypeError, ValueError):
            continue
        if lo <= p <= hi:
            return float(row.get("fee", 0))
    return float(fees[-1].get("fee", 0)) if fees else 0.0


def _tiered_buyer_fee(price: float) -> float:
    """Back-compat helper used by a few legacy callers — uses hardcoded ladder.

    VERBATIM port from server.py:9725 (Phase 6.5+ Wave 2).
    """
    try:
        p = float(price or 0)
    except (TypeError, ValueError):
        p = 0.0
    for lo, hi, fee in AUCTION_TIERED_FEES:
        if lo <= p <= hi:
            return float(fee)
    return float(AUCTION_TIERED_FEES[-1][2])


__all__ = [
    "_find_route_amount",
    "_tiered_buyer_fee",
    "_tiered_buyer_fee_from_db",
]
