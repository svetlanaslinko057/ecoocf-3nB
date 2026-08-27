"""
BIBI Cars — Block 7.1 — Field-level Change History
====================================================

Generic helper that records who changed which field, the old value,
the new value, and when — for any entity (lead / customer / deal).

The CRM already has:

  * **timeline events**  (db.customer_events, db.lead_notes, ...)
    — narrative, human-readable events

  * **audit log**  (db.audit_events, app.repositories.audit_events)
    — high-level action log (e.g. ``customer.update``)

What it was missing:

  * **field-level diff history**  — *“who set lead.managerId from X to Y”*

This module owns the new collection ``db.field_changes`` and exposes
``record_field_changes()`` for the existing PATCH/PUT handlers.

Schema
------

::

    {
        "id":           "fch_<hex>",
        "entity_type":  "lead" | "customer" | "deal",
        "entity_id":    "<id>",
        "field":        "managerId",
        "old_value":    <jsonable>,
        "new_value":    <jsonable>,
        "changed_at":   "<iso>",
        "changed_by":   "<user-id-or-email>",
        "changed_by_name": "<display name>",
        "changed_by_role": "<role>",
        "source":       "api"     # 'api' | 'system' | 'migration' | etc.
    }

Indexes (ensured on startup):

::

    [(entity_type, 1), (entity_id, 1), (changed_at, -1)]
    [(changed_at, -1)]
    [(field, 1), (changed_at, -1)]
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger("bibi.change_history")

COLLECTION = "field_changes"

# Common allowed fields per entity (whitelist to avoid noise on every PUT).
DEFAULT_ALLOWED: Dict[str, set[str]] = {
    "lead": {
        "firstName", "lastName", "name", "email", "phone",
        "status", "source", "managerId", "company",
        "vehicleInterest", "budgetEur", "budgetUsd", "value",
        "notes", "vin", "lossReason", "priority",
    },
    "customer": {
        "firstName", "lastName", "name", "email", "phone",
        "status", "type", "address", "city", "country",
        "managerId", "notes", "tags",
    },
    "deal": {
        "status", "vin", "carBrand", "carModel", "carYear",
        "amount", "currency", "totalCost", "profit",
        "managerId", "stage", "delivery_status",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(v: Any) -> Any:
    """Make value JSON-safe (no datetime / ObjectId leaks)."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


async def ensure_indexes(db) -> None:
    try:
        await db[COLLECTION].create_index([("entity_type", 1), ("entity_id", 1), ("changed_at", -1)])
        await db[COLLECTION].create_index([("changed_at", -1)])
        await db[COLLECTION].create_index([("field", 1), ("changed_at", -1)])
        await db[COLLECTION].create_index([("entity_id", 1)])
        logger.info("[change_history] indexes ensured")
    except Exception as e:
        logger.warning("[change_history] index ensure failed: %s", e)


async def record_field_changes(
    db,
    *,
    entity_type: str,
    entity_id: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
    user: Optional[Dict[str, Any]] = None,
    allowed_fields: Optional[Iterable[str]] = None,
    source: str = "api",
) -> int:
    """Diff ``before`` and ``after`` and write a row per changed field.

    Returns the number of rows inserted (0 = no changes).

    Best-effort: never raises. Failures are logged but do not affect the
    business path.
    """
    if not entity_type or not entity_id:
        return 0
    try:
        allowed = set(allowed_fields) if allowed_fields else DEFAULT_ALLOWED.get(entity_type, set())
        rows: List[Dict[str, Any]] = []
        now_iso = _now_iso()
        user = user or {}
        actor_id   = user.get("id")    or user.get("email")
        actor_name = user.get("name")  or actor_id
        actor_role = (user.get("role") or "").lower()

        for field in allowed:
            old_v = before.get(field) if isinstance(before, dict) else None
            new_v = after.get(field)  if isinstance(after,  dict) else None
            # Treat None == "" == missing as equal
            if old_v in (None, "", []) and new_v in (None, "", []):
                continue
            if old_v == new_v:
                continue
            rows.append({
                "id":               f"fch_{uuid.uuid4().hex[:14]}",
                "entity_type":      entity_type,
                "entity_id":        entity_id,
                "field":            field,
                "old_value":        _jsonable(old_v),
                "new_value":        _jsonable(new_v),
                "changed_at":       now_iso,
                "changed_by":       actor_id,
                "changed_by_name":  actor_name,
                "changed_by_role":  actor_role,
                "source":           source,
            })
        if rows:
            await db[COLLECTION].insert_many(rows)
        return len(rows)
    except Exception as e:
        logger.warning("[change_history] write failed (%s/%s): %s", entity_type, entity_id, e)
        return 0


async def list_field_changes(
    db,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Return newest-first change history for a single entity."""
    if not entity_type or not entity_id:
        return []
    cur = (
        db[COLLECTION]
        .find({"entity_type": entity_type, "entity_id": entity_id}, {"_id": 0})
        .sort("changed_at", -1)
        .limit(int(limit))
    )
    return await cur.to_list(length=int(limit))


__all__ = [
    "COLLECTION", "DEFAULT_ALLOWED",
    "ensure_indexes",
    "record_field_changes",
    "list_field_changes",
]
