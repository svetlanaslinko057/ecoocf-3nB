"""Neutral domain-audit backbone.

Relocated out of the (now removed) car-import ``legal_workflow.py`` so that
the still-live financial modules (``payments_tracking.py``,
``financial_breakdown.py``) keep their append-only audit trail and the
deal-stage ordering they reference — without dragging the auction/import
domain back in.

Owns:
  * ``_audit(...)``  — append-only domain audit writer (db.audit_events,
    routed through ``AuditEventsRepository``). Never raises.
  * ``DEAL_STAGES``  — canonical forward ordering of generic deal stages.
    Kept for the payment auto-advance guard in ``payments_tracking``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db


#: Canonical forward ordering of deal stages (index-comparison only).
DEAL_STAGES: List[str] = [
    "lead",
    "qualified",
    "variants_sent",
    "deposit_contract_drafted",
    "deposit_contract_signed",
    "deposit_paid",
    "negotiation",
    "contract_sent",
    "contract_signed",
    "payment_paid",
    "in_progress",
    "delivered",
    "closed",
    "cancelled",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(
    event_type: str,
    entity_type: str,
    entity_id: str,
    user: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    deal_id: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> None:
    """Append-only audit trail. Never breaks the main request.

    Collection: ``db.audit_events`` (via ``AuditEventsRepository``). Used for
    accounting, legal disputes and incident RCA — never edited by hand in prod.
    """
    try:
        db = get_db()
        doc = {
            "id": f"audit_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "deal_id": deal_id,
            "customer_id": customer_id,
            "user_id": (user or {}).get("id"),
            "user_email": (user or {}).get("email"),
            "user_role": (user or {}).get("role"),
            "payload": payload or {},
            "at": _now_iso(),
            "ts": datetime.now(timezone.utc),
        }
        from app.repositories import AuditEventsRepository
        await AuditEventsRepository(db).record_domain_event(doc)
    except Exception:
        import logging as _lg
        _lg.getLogger("bibi.domain.audit").warning(
            "[audit] failed to write event=%s entity=%s/%s",
            event_type, entity_type, entity_id, exc_info=True,
        )
