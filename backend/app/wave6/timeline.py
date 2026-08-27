"""
Wave 6 — Deal Timeline (key events only, human-readable).

Writes into a brand-new MongoDB collection ``deal_timeline``. We intentionally
do NOT reuse ``audit_events`` (that's the security/audit stream) nor
``stage_history`` (sub-array on the deal doc, limited to stage transitions).

Design rules:
  * Only key business events are written (see ``KEY_EVENT_TYPES``).
  * Each event carries a pre-rendered ``message`` (English baseline) and an
    ``i18n_key`` so the frontend can localise without re-deriving facts.
  * Field changes / saves / form edits are NOT timeline events — keep this
    stream small and meaningful.
  * Writes are best-effort: if the DB is briefly unavailable we log and move on
    rather than break the underlying transaction (timeline must never block
    operational endpoints).

Indexes are ensured at module-load via ``ensure_indexes(db)``.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.wave6.timeline")

COLLECTION = "deal_timeline"

# Closed set of allowed event types (Wave 6).
KEY_EVENT_TYPES: List[str] = [
    "deal_created",
    "stage_changed",
    "deposit_requested",
    "deposit_confirmed",
    "deposit_refunded",
    "deposit_forfeited",
    "contract_sent",
    "contract_signed",
    "payment_received",
    "auction_won",
    "auction_lost",
    "shipping_started",
    "customs_cleared",
    "delivered",
    "cancelled",
    "note_added",
    "owner_changed",
]


@dataclass
class TimelineEvent:
    id: str
    deal_id: str
    event_type: str
    message: str
    i18n_key: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "event_type": self.event_type,
            "message": self.message,
            "i18n_key": self.i18n_key,
            "data": self.data or {},
            "actor": {"email": self.actor_email, "role": self.actor_role},
            "at": self.at,
        }


async def ensure_indexes(db) -> None:
    """Idempotent index setup. Safe to call on every startup."""
    try:
        await db[COLLECTION].create_index("deal_id")
        await db[COLLECTION].create_index([("deal_id", 1), ("at", -1)])
        await db[COLLECTION].create_index("event_type")
        await db[COLLECTION].create_index("at")
        logger.info("[wave6.timeline] indexes ensured on %s", COLLECTION)
    except Exception as e:
        logger.warning("[wave6.timeline] index ensure failed: %s", e)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def write_event(
    db,
    *,
    deal_id: str,
    event_type: str,
    message: str,
    i18n_key: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, Any]] = None,
) -> Optional[TimelineEvent]:
    """Persist one timeline event. Best-effort; never raises.

    Args:
        db:          Motor DB handle.
        deal_id:     Deal id (string).
        event_type:  One of KEY_EVENT_TYPES (else logs warn + still writes).
        message:     Human-readable EN string (e.g. "Deposit of €1,500 confirmed by John").
        i18n_key:    Optional i18n key for the frontend to localise.
        data:        Structured payload (amounts, ids, stages…).
        actor:       Dict with at least `email` / `role` (taken from the auth user).
    """
    if not deal_id or not event_type:
        return None
    if event_type not in KEY_EVENT_TYPES:
        logger.debug("[wave6.timeline] non-canonical event_type=%s for deal=%s",
                     event_type, deal_id)

    ev = TimelineEvent(
        id=f"tl_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}",
        deal_id=str(deal_id),
        event_type=event_type,
        message=message,
        i18n_key=i18n_key,
        data=data or {},
        actor_email=(actor or {}).get("email"),
        actor_role=(actor or {}).get("role"),
        at=_now_iso(),
    )

    try:
        await db[COLLECTION].insert_one(ev.to_dict())
        return ev
    except Exception as e:
        logger.warning("[wave6.timeline] write failed deal=%s type=%s err=%s",
                       deal_id, event_type, e)
        return None


async def list_events(
    db,
    *,
    deal_id: str,
    limit: int = 100,
    event_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return newest-first timeline entries for a deal."""
    if not deal_id:
        return []
    q: Dict[str, Any] = {"deal_id": str(deal_id)}
    if event_type:
        q["event_type"] = event_type
    cur = (
        db[COLLECTION]
        .find(q, {"_id": 0})
        .sort("at", -1)
        .limit(max(1, min(limit, 500)))
    )
    return await cur.to_list(length=limit)


# ─── high-level message renderers (used by hooks in legal_workflow / server) ───
def render_stage_change(
    *, from_stage: str, to_stage: str, by_email: str
) -> str:
    return f"Stage changed: {from_stage} → {to_stage} (by {by_email or 'system'})"


def render_deposit_confirmed(
    *, amount_eur: float, by_email: str
) -> str:
    try:
        amt = f"€{float(amount_eur):,.2f}"
    except Exception:
        amt = f"€{amount_eur}"
    return f"Deposit of {amt} confirmed by {by_email or 'manager'}"


def render_deal_created(*, title: str, vin: Optional[str], by_email: str) -> str:
    head = title or "Deal"
    if vin:
        head = f"{head} (VIN {vin})"
    return f"Deal created: {head} — by {by_email or 'system'}"
