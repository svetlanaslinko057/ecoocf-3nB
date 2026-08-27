"""
Customer Timeline service — Sprint 4
====================================

Central "event bus" for everything that happens around a customer.
Other services (orders, file_manager, pdf_engine, roadmap, comments,
tasks) call ``record_event`` to drop a structured record into
``customer_timeline_events`` — Customer360's Timeline tab then reads
from there.

Design goals
------------
* **Never block the caller.** A failure to log a timeline event must
  not roll back the originating business action. Every call is wrapped
  in a try/except at the caller side.
* **Single source of truth.** No more reconstructing timelines from
  scattered "recent_invoices / recent_orders / ..." queries — just
  read this one collection.
* **Backwards compatible.** Existing CRM pages keep working; this
  collection is purely additive.

Schema (BSON)
-------------
{
  id: uuid,
  customer_id: str,            # canonical key (alias `customerId`)
  customerId: str,
  kind: str,                   # see EVENT_KINDS
  title: str,                  # short human label, e.g. 'Invoice paid'
  body: str|None,              # optional longer description
  ref: {                       # link back to the source entity
    collection: str,
    id: str,
    url: str|None,
  },
  actor: { id, email, name, role } | None,
  meta: dict,                  # free-form, e.g. {amount, currency, stage_key}
  created_at: iso8601 utc
}
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.customer_timeline")

COLLECTION = "customer_timeline_events"

# Canonical event taxonomy. Keep stable — the frontend keys icons/colors
# off of these. New events should be added here AND in the FE map.
EVENT_KINDS = {
    "invoice_created",
    "invoice_paid",
    "order_created",
    "payment_received",
    "document_generated",
    "file_uploaded",
    "file_deleted",
    "comment_added",
    "comment_pinned",
    "task_created",
    "task_completed",
    "task_overdue",
    "roadmap_created",
    "roadmap_updated",
    "roadmap_completed",
    "customer_created",
    "customer_assigned",
    "lead_converted",
    "call_logged",
    "deposit_received",
    "contract_signed",
    "iban_issued",
    # Phase Final / Block 2 — Sales lifecycle events
    "sale_created",
    "sale_updated",
    "sale_completed",
    "sale_cancelled",
    # Phase Final / Block 3 — Meeting lifecycle events
    "meeting_scheduled",
    "meeting_completed",
    "meeting_cancelled",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_event(
    *,
    customer_id: str,
    kind: str,
    title: str,
    body: Optional[str] = None,
    ref: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Insert a single timeline event. Returns the inserted doc (no `_id`).

    Best-effort: failures are logged and swallowed because timeline
    persistence is NEVER a critical path.
    """
    if not customer_id or not kind or kind not in EVENT_KINDS:
        if kind and kind not in EVENT_KINDS:
            logger.warning("[timeline] unknown kind=%s (event dropped)", kind)
        return None

    db = get_db()
    if db is None:
        return None

    doc = {
        "id": uuid.uuid4().hex,
        "customer_id": customer_id,
        "customerId": customer_id,
        "kind": kind,
        "title": title or kind.replace("_", " ").capitalize(),
        "body": body,
        "ref": ref or {},
        "actor": actor,
        "meta": meta or {},
        "created_at": _now(),
    }
    try:
        await db[COLLECTION].insert_one(dict(doc))
        doc.pop("_id", None)
        return doc
    except Exception:
        logger.exception("[timeline] insert failed (kind=%s, customer=%s)", kind, customer_id)
        return None


async def list_for_customer(
    customer_id: str,
    *,
    kinds: Optional[List[str]] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Return the latest events for a customer, newest first."""
    db = get_db()
    if db is None:
        return []
    flt: Dict[str, Any] = {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}]}
    if kinds:
        flt["kind"] = {"$in": list(kinds)}
    try:
        cursor = db[COLLECTION].find(flt, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500))
        return await cursor.to_list(length=min(limit, 500))
    except Exception:
        logger.exception("[timeline] list_for_customer failed (customer=%s)", customer_id)
        return []


async def ensure_indexes() -> None:
    db = get_db()
    if db is None:
        return
    try:
        await db[COLLECTION].create_index([("customer_id", 1), ("created_at", -1)])
        await db[COLLECTION].create_index([("customerId", 1), ("created_at", -1)])
        await db[COLLECTION].create_index([("kind", 1)])
        await db[COLLECTION].create_index("id", unique=True)
    except Exception:
        logger.exception("[timeline] index creation failed")


def extract_actor(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Project a staff/auth dict down to the actor sub-document."""
    if not user:
        return None
    return {
        "id": user.get("id") or user.get("managerId"),
        "email": user.get("email"),
        "name": user.get("name") or user.get("firstName") or user.get("email"),
        "role": (user.get("role") or "").lower() or None,
    }


__all__ = [
    "COLLECTION",
    "EVENT_KINDS",
    "record_event",
    "list_for_customer",
    "ensure_indexes",
    "extract_actor",
]
