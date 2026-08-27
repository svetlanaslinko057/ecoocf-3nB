"""
BIBI Cars — Wave 18 — Notification dispatcher
================================================

Responds to Action lifecycle events emitted by Wave 17 and writes
notification rows. Channels are pluggable; the in-app channel is the only
one that actually persists fully right now — email/telegram/slack/sms
flows write the row with status="queued" so a future SMTP/Telegram bridge
can pick them up and flip to sent/failed.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.wave18.models import DISPATCH_RULES, NotificationPreferences

logger = logging.getLogger("bibi.wave18")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_recipients(db, recipient_role: str, action: Dict[str, Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map a recipient_role string to one or more concrete user docs.

    Returns dicts shaped like {"id", "name", "role", "email"}.
    """
    out: List[Dict[str, Any]] = []
    if recipient_role == "owner":
        oid = action.get("owner_id")
        if oid:
            doc = await _user_doc(db, oid)
            if doc: out.append(doc)
    elif recipient_role == "previous_owner":
        pid = (meta or {}).get("previous_owner_id")
        if pid and pid != action.get("owner_id"):
            doc = await _user_doc(db, pid)
            if doc: out.append(doc)
    elif recipient_role == "creator":
        cid = action.get("created_by")
        if cid and cid != action.get("owner_id"):
            doc = await _user_doc(db, cid)
            if doc: out.append(doc)
    elif recipient_role == "team_lead":
        oid = action.get("owner_id")
        if oid:
            staff = await db.staff.find_one({"id": oid}, {"_id": 0, "team_lead_id": 1})
            tl_id = (staff or {}).get("team_lead_id")
            if tl_id:
                doc = await _user_doc(db, tl_id)
                if doc: out.append(doc)
    elif recipient_role == "admin":
        admins = await db.staff.find(
            {"role": {"$in": ["admin", "master_admin"]}, "active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "role": 1, "email": 1}
        ).to_list(length=20)
        for a in admins:
            out.append({"id": a.get("id"), "name": a.get("name"), "role": a.get("role"), "email": a.get("email")})
    return out


async def _user_doc(db, user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    doc = await db.staff.find_one({"id": user_id},
                                    {"_id": 0, "id": 1, "name": 1, "role": 1, "email": 1})
    if not doc:
        return {"id": user_id, "name": user_id, "role": None, "email": None}
    return {"id": doc.get("id"), "name": doc.get("name"), "role": doc.get("role"), "email": doc.get("email")}


async def get_preferences(db, user_id: str) -> Dict[str, Any]:
    if not user_id:
        return NotificationPreferences(user_id="").model_dump()
    doc = await db.notification_preferences.find_one({"user_id": user_id}, {"_id": 0})
    if doc:
        return doc
    default = NotificationPreferences(user_id=user_id).model_dump()
    return default


async def patch_preferences(db, user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    if not user_id:
        return NotificationPreferences(user_id="").model_dump()
    cur = await get_preferences(db, user_id)
    new = {**cur, **{k: v for k, v in (patch or {}).items() if v is not None}}
    new["user_id"] = user_id
    if cur.get("channels") and patch.get("channels"):
        new["channels"] = {**cur["channels"], **patch["channels"]}
    await db.notification_preferences.update_one({"user_id": user_id}, {"$set": new}, upsert=True)
    return new


def _muted(prefs: Dict[str, Any]) -> bool:
    until = prefs.get("mute_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception:
        return False


async def _channel_enabled(db, user_id: str, channel: str) -> bool:
    if not user_id: return False
    prefs = await get_preferences(db, user_id)
    if _muted(prefs):
        # mute does not affect in_app inbox — you still see them when you open it
        return channel == "in_app"
    return bool((prefs.get("channels") or {}).get(channel, False))


def _title_body(event: str, action: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, str]:
    a_title = action.get("title") or "Action"
    priority = action.get("priority") or "medium"
    due = action.get("due_at") or ""
    base = {
        "action_created":           ("New action created",        f"“{a_title}” — priority {priority}"),
        "action_assigned":          ("Action assigned to you",    f"“{a_title}” — priority {priority}, due {due[:10]}"),
        "action_started":           ("Action started",            f"“{a_title}” is now in progress"),
        "action_snoozed":           ("Action snoozed",            f"“{a_title}” snoozed until {(meta or {}).get('snooze_until','')}"),
        "action_escalated":         ("Action escalated",          f"“{a_title}” escalated to {(meta or {}).get('to_step','team_lead')}"),
        "action_reopened":          ("Action reopened",           f"“{a_title}” was reopened"),
        "action_resolved":          ("Action resolved",           f"“{a_title}” marked resolved"),
        "action_cancelled":         ("Action cancelled",          f"“{a_title}” cancelled"),
        "action_commented":         ("New comment on action",     (meta or {}).get("comment") or ""),
        "action_overdue":           ("Action overdue",            f"“{a_title}” is past due"),
        "action_critical_overdue": ("Action critically overdue",  f"“{a_title}” > 7 days overdue — admin escalation"),
    }
    t, b = base.get(event, (event.replace("_", " ").title(), a_title))
    return {"title": t, "body": b}


async def dispatch_event(db, event: str, action: Dict[str, Any],
                        user: Optional[Dict[str, Any]] = None,
                        meta: Optional[Dict[str, Any]] = None) -> int:
    """Resolve recipients + channels and persist notification rows.

    Returns the number of rows inserted.
    """
    rules = DISPATCH_RULES.get(event)
    if not rules:
        return 0
    meta = meta or {}
    now = _now_iso()
    dedup: Set[str] = set()
    rows: List[Dict[str, Any]] = []
    for rule in rules:
        recipients = await _resolve_recipients(db, rule["recipient"], action, meta)
        for r in recipients:
            uid = r.get("id")
            if not uid:
                continue
            for ch in rule["channels"]:
                # skip channels the user disabled (in_app is always allowed)
                if ch != "in_app" and not await _channel_enabled(db, uid, ch):
                    continue
                k = f"{uid}:{ch}:{event}:{action.get('id')}"
                if k in dedup:
                    continue
                dedup.add(k)
                tb = _title_body(event, action, meta)
                rows.append({
                    "id":           f"notif_{uuid.uuid4().hex[:12]}",
                    "event":        event,
                    "action_id":    action.get("id"),
                    "deal_id":      action.get("deal_id"),
                    "recipient_id":   uid,
                    "recipient_name": r.get("name"),
                    "recipient_role": r.get("role"),
                    "recipient_email": r.get("email"),
                    "channel":      ch,
                    "status":       "sent" if ch == "in_app" else "queued",
                    "priority":     action.get("priority"),
                    "title":        tb["title"],
                    "body":         tb["body"],
                    "href":         action.get("href") or f"/admin/actions?id={action.get('id')}",
                    "meta":         {**meta, "actor_id": (user or {}).get("id")},
                    "created_at":   now,
                    "sent_at":      now if ch == "in_app" else None,
                    "read_at":      None,
                    "dismissed_at": None,
                })
    if rows:
        await db.notifications.insert_many(rows)
    return len(rows)


async def _handler(db, event: str, action: Dict[str, Any], user: Dict[str, Any], meta: Dict[str, Any]) -> None:
    try:
        await dispatch_event(db, event, action, user, meta)
    except Exception:
        logger.warning("notification dispatch failed for %s", event, exc_info=True)


def register() -> None:
    """Register this dispatcher with Wave 17. Called once on import."""
    from app.wave17.service import register_event_handler
    register_event_handler(_handler)


__all__ = ["dispatch_event", "register", "get_preferences", "patch_preferences"]
