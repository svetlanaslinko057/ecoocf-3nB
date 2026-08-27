"""
BIBI Cars — Wave 17 — Action service
=======================================

Lifecycle:
    open ── start ──▶ in_progress ── resolve ──▶ resolved
      │── snooze ──▶ snoozed ── reopen ──▶ open
      │── escalate ──▶ (escalated=True, owner = team_lead/admin)
      │── cancel ──▶ cancelled (terminal, via resolve outcome=wont_do)

Every state change appends an event to events[] for full audit trail.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


# ────────────────────────────────────────────────────────────────────────
#  Event bus (Wave 18 hook)
#  Other waves (notably Wave 18 — Notification Center) can register an
#  async callback to react to every lifecycle event. We keep this in the
#  service module to avoid circular imports.
# ────────────────────────────────────────────────────────────────────────
_event_callbacks: List["Any"] = []


def register_event_handler(fn) -> None:
    if fn not in _event_callbacks:
        _event_callbacks.append(fn)


async def _emit(db, event: str, action: Dict[str, Any], user: Dict[str, Any] | None = None, **meta) -> None:
    """Fire-and-forget event emission. Errors in handlers never propagate."""
    for cb in _event_callbacks:
        try:
            await cb(db, event, action, user or {}, meta)
        except Exception:
            # Notification handlers must never block the action lifecycle.
            import logging
            logging.getLogger("bibi.wave17").warning("event handler failed for %s", event, exc_info=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _add_days(days: int) -> str:
    return (_now() + timedelta(days=days)).isoformat()


def _ev(kind: str, *, user: Dict[str, Any] | None = None, note: str | None = None, meta: dict | None = None) -> Dict[str, Any]:
    user = user or {}
    return {
        "kind":       kind,
        "at":         _now_iso(),
        "actor_id":   user.get("id") or user.get("sub"),
        "actor_name": user.get("name") or user.get("email"),
        "note":       note,
        "meta":       meta or {},
    }


async def get_action(db: AsyncIOMotorDatabase, action_id: str) -> Optional[Dict[str, Any]]:
    return await db.actions.find_one({"id": action_id}, {"_id": 0})


async def create_action(
    db: AsyncIOMotorDatabase,
    user: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    now = _now_iso()
    action_id = f"action_{uuid.uuid4().hex[:12]}"
    due_at = payload.get("due_at") or _add_days(2)
    doc = {
        "id":           action_id,
        "source":       (payload.get("source")   or "manual"),
        "type":         (payload.get("type")     or "manual"),
        "title":        payload.get("title")     or "Untitled action",
        "description":  payload.get("description"),
        "priority":     (payload.get("priority") or "medium"),
        "status":       "open",
        "escalation":   "none",
        "escalated":    False,
        "owner_id":     payload.get("owner_id"),
        "owner_name":   payload.get("owner_name"),
        "entity_type":  payload.get("entity_type"),
        "entity_id":    payload.get("entity_id"),
        "deal_id":      payload.get("deal_id"),
        "impact":       float(payload.get("impact") or 0.0),
        "currency":     payload.get("currency")   or "EUR",
        "due_at":       due_at,
        "href":         payload.get("href"),
        "tags":         list(payload.get("tags") or []),
        "meta":         payload.get("meta")       or {},
        # idempotency for sync‑from‑sources
        "source_key":   payload.get("source_key"),
        "created_at":   now,
        "updated_at":   now,
        "resolved_at":  None,
        "snooze_until": None,
        "created_by":   user.get("id") or user.get("sub"),
        "events":       [_ev("created", user=user, note=payload.get("title"))],
    }
    await db.actions.insert_one(dict(doc))
    await _emit(db, "action_created", doc, user)
    return doc


async def patch_action(db, action_id: str, user: Dict[str, Any], patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    if a.get("status") in ("resolved", "cancelled"):
        return a
    update = {k: v for k, v in (patch or {}).items() if v is not None}
    if not update:
        return a
    update["updated_at"] = _now_iso()
    await db.actions.update_one(
        {"id": action_id},
        {"$set": update,
         "$push": {"events": _ev("updated", user=user, meta={"fields": list(update.keys())})}},
    )
    return await get_action(db, action_id)


async def assign_action(db, action_id: str, user: Dict[str, Any], *, owner_id: str, owner_name: Optional[str], comment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    now = _now_iso()
    await db.actions.update_one(
        {"id": action_id},
        {"$set": {"owner_id": owner_id, "owner_name": owner_name, "updated_at": now},
         "$push": {"events": _ev("assigned", user=user, note=comment, meta={"owner_id": owner_id, "owner_name": owner_name})}}
    )
    fresh = await get_action(db, action_id)
    await _emit(db, "action_assigned", fresh or a, user,
                previous_owner_id=a.get("owner_id"))
    return fresh


async def start_action(db, action_id: str, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    if a.get("status") not in ("open", "snoozed"):
        return a
    now = _now_iso()
    await db.actions.update_one(
        {"id": action_id},
        {"$set": {"status": "in_progress", "updated_at": now,
                  "snooze_until": None},
         "$push": {"events": _ev("started", user=user)}}
    )
    fresh = await get_action(db, action_id)
    await _emit(db, "action_started", fresh or a, user)
    return fresh


async def resolve_action(db, action_id: str, user: Dict[str, Any], *, comment: Optional[str], outcome: str = "resolved") -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    now = _now_iso()
    new_status = "resolved" if outcome != "wont_do" else "cancelled"
    await db.actions.update_one(
        {"id": action_id},
        {"$set": {"status": new_status, "resolved_at": now, "updated_at": now,
                  "meta.outcome": outcome},
         "$push": {"events": _ev("resolved", user=user, note=comment, meta={"outcome": outcome})}}
    )
    fresh = await get_action(db, action_id)
    event = "action_cancelled" if new_status == "cancelled" else "action_resolved"
    await _emit(db, event, fresh or a, user, outcome=outcome)
    return fresh


async def snooze_action(db, action_id: str, user: Dict[str, Any], *, snooze_until: str, comment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    now = _now_iso()
    await db.actions.update_one(
        {"id": action_id},
        {"$set": {"status": "snoozed", "snooze_until": snooze_until, "updated_at": now},
         "$push": {"events": _ev("snoozed", user=user, note=comment, meta={"snooze_until": snooze_until})}}
    )
    fresh = await get_action(db, action_id)
    await _emit(db, "action_snoozed", fresh or a, user, snooze_until=snooze_until)
    return fresh


async def escalate_action(db, action_id: str, user: Dict[str, Any], *, to_step: str = "admin",
                           new_owner_id: Optional[str] = None, new_owner_name: Optional[str] = None,
                           comment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    now = _now_iso()
    setter: Dict[str, Any] = {
        "escalation": to_step,
        "escalated":  True,
        "priority":   "critical" if to_step == "admin" else ("high" if a.get("priority") not in ("critical",) else a.get("priority")),
        "updated_at": now,
    }
    if new_owner_id:
        setter["owner_id"]   = new_owner_id
        setter["owner_name"] = new_owner_name
    await db.actions.update_one(
        {"id": action_id},
        {"$set": setter,
         "$push": {"events": _ev("escalated", user=user, note=comment, meta={"to_step": to_step, "new_owner_id": new_owner_id})}}
    )
    fresh = await get_action(db, action_id)
    await _emit(db, "action_escalated", fresh or a, user,
                to_step=to_step,
                previous_owner_id=a.get("owner_id"))
    return fresh


async def reopen_action(db, action_id: str, user: Dict[str, Any], *, comment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    if a.get("status") not in ("resolved", "snoozed", "cancelled"):
        return a
    now = _now_iso()
    await db.actions.update_one(
        {"id": action_id},
        {"$set": {"status": "open", "resolved_at": None, "snooze_until": None, "updated_at": now},
         "$push": {"events": _ev("reopened", user=user, note=comment)}}
    )
    fresh = await get_action(db, action_id)
    await _emit(db, "action_reopened", fresh or a, user)
    return fresh


async def comment_action(db, action_id: str, user: Dict[str, Any], *, comment: str) -> Optional[Dict[str, Any]]:
    a = await get_action(db, action_id)
    if not a: return None
    await db.actions.update_one(
        {"id": action_id},
        {"$set": {"updated_at": _now_iso()},
         "$push": {"events": _ev("commented", user=user, note=comment)}}
    )
    fresh = await get_action(db, action_id)
    await _emit(db, "action_commented", fresh or a, user, comment=comment)
    return fresh


async def auto_resume_snoozed(db) -> int:
    """Background hook: any snoozed action whose snooze_until has passed
    bounces back to open. Returns the number resumed.
    """
    now_iso = _now_iso()
    res = await db.actions.update_many(
        {"status": "snoozed", "snooze_until": {"$lte": now_iso}},
        {"$set":  {"status": "open", "updated_at": now_iso, "snooze_until": None},
         "$push": {"events": {"kind": "auto_resumed", "at": now_iso, "note": "Snooze expired"}}}
    )
    return int(res.modified_count or 0)


__all__ = [
    "get_action", "create_action", "patch_action",
    "assign_action", "start_action", "resolve_action",
    "snooze_action", "escalate_action", "reopen_action",
    "comment_action", "auto_resume_snoozed",
]
