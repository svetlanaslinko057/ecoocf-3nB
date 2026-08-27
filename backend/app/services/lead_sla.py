"""
BIBI Cars — Block 6.2 — Lead SLA service
==========================================

Pure business logic. No HTTP routing here.

Responsibilities
----------------
1. **Configuration loading** from the ``settings`` collection (admin can
   override remind/escalate minutes at runtime).
2. **mark_lead_responded()** — atomic, idempotent “first response” stamp.
3. **scan_overdue_leads()** — idempotent background scan that emits
   reminder / escalation notifications exactly once per lead.
4. **get_lead_sla_state()** — read-only computed status used by both the
   per-lead UI badge and the “overdue list” endpoint.

Notification dispatch
---------------------
We do **not** reuse the Wave-18 ``dispatch_event`` because that helper is
hard-bound to the ``action`` document shape (it walks ``action.owner_id``,
``action.created_by`` etc.). Instead we write directly to the
``notifications`` collection — the same collection the rest of the app
already reads from — using a small in-module dispatcher. This keeps Wave 18
unmodified and avoids accidental coupling.

Idempotency
-----------
Two embedded markers on the lead document protect against duplicate
notifications:

    sla_reminded_at      ISO-8601 string when reminder was emitted
    sla_escalated_at     ISO-8601 string when escalation was emitted

The scan ignores leads where the relevant marker is already set. The
``mark_lead_responded()`` helper sets ``first_response_at`` (used by
the scan as the master “stop SLA” flag).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.constants.lead_sla import (
    DEFAULT_REMIND_MINUTES,
    DEFAULT_ESCALATE_MINUTES,
    MIN_THRESHOLD_MINUTES,
    MAX_THRESHOLD_MINUTES,
    SETTING_REMIND_KEY,
    SETTING_ESCALATE_KEY,
    SETTING_AUTO_REASSIGN_KEY,
    EVENT_LEAD_SLA_WARNING,
    EVENT_LEAD_SLA_ESCALATED,
    SLA_STATE_GREEN,
    SLA_STATE_AMBER,
    SLA_STATE_OVERDUE,
    SLA_STATE_ESCALATED,
    SLA_STATE_OK,
    SLA_STATE_NA,
)

logger = logging.getLogger("bibi.lead_sla")

# Lead statuses that DO NOT need SLA tracking — terminal/converted states.
TERMINAL_LEAD_STATUSES = {
    "converted", "lost", "rejected", "archived", "cancelled",
    "duplicate", "spam",
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        if isinstance(iso, datetime):
            if iso.tzinfo is None:
                return iso.replace(tzinfo=timezone.utc)
            return iso
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception:
        return None


def _clamp(v: int) -> int:
    return max(MIN_THRESHOLD_MINUTES, min(MAX_THRESHOLD_MINUTES, int(v)))


async def get_thresholds(db) -> Dict[str, Any]:
    """Read current thresholds from the settings collection with defaults."""
    out: Dict[str, Any] = {
        "remind_minutes":   DEFAULT_REMIND_MINUTES,
        "escalate_minutes": DEFAULT_ESCALATE_MINUTES,
        "auto_reassign":    False,
    }
    try:
        for key, field in (
            (SETTING_REMIND_KEY,   "remind_minutes"),
            (SETTING_ESCALATE_KEY, "escalate_minutes"),
        ):
            doc = await db.settings.find_one({"key": key}, {"_id": 0, "value": 1})
            if doc and doc.get("value") is not None:
                try:
                    out[field] = _clamp(int(doc["value"]))
                except Exception:
                    pass
        doc = await db.settings.find_one({"key": SETTING_AUTO_REASSIGN_KEY}, {"_id": 0, "value": 1})
        if doc:
            out["auto_reassign"] = bool(doc.get("value"))
    except Exception as e:
        logger.warning("[lead_sla] threshold load failed: %s — using defaults", e)
    # safety: escalate must be > remind
    if out["escalate_minutes"] <= out["remind_minutes"]:
        out["escalate_minutes"] = out["remind_minutes"] + 30
    return out


async def set_thresholds(
    db,
    remind_minutes: Optional[int] = None,
    escalate_minutes: Optional[int] = None,
    auto_reassign: Optional[bool] = None,
) -> Dict[str, Any]:
    """Admin setter for SLA thresholds (used by router)."""
    updates: List[Tuple[str, Any]] = []
    if remind_minutes is not None:
        updates.append((SETTING_REMIND_KEY, _clamp(remind_minutes)))
    if escalate_minutes is not None:
        updates.append((SETTING_ESCALATE_KEY, _clamp(escalate_minutes)))
    if auto_reassign is not None:
        updates.append((SETTING_AUTO_REASSIGN_KEY, bool(auto_reassign)))
    for key, value in updates:
        await db.settings.update_one(
            {"key": key},
            {"$set": {"id": key, "key": key, "value": value, "updated_at": _now_iso()}},
            upsert=True,
        )
    return await get_thresholds(db)


# ──────────────────────────────────────────────────────────────────────
# SLA state computation (read-only)
# ──────────────────────────────────────────────────────────────────────
def compute_lead_sla(
    lead: Dict[str, Any],
    *,
    remind_minutes: int,
    escalate_minutes: int,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Return a dict with computed SLA state. Pure function. Safe for any lead shape."""
    now = now or _now()
    state = SLA_STATE_NA
    minutes_elapsed: Optional[float] = None
    minutes_remaining: Optional[float] = None
    deadline_at: Optional[str] = None

    status = str(lead.get("status") or "").lower()
    manager_id = lead.get("managerId") or lead.get("manager_id")
    first_response_at = _parse(lead.get("first_response_at"))
    created_at = _parse(lead.get("created_at"))
    reminded_at = _parse(lead.get("sla_reminded_at"))
    escalated_at = _parse(lead.get("sla_escalated_at"))

    if first_response_at:
        state = SLA_STATE_OK
    elif status in TERMINAL_LEAD_STATUSES:
        state = SLA_STATE_NA
    elif not manager_id:
        state = SLA_STATE_NA
    elif not created_at:
        state = SLA_STATE_NA
    else:
        elapsed = (now - created_at).total_seconds() / 60.0
        minutes_elapsed = round(elapsed, 1)
        deadline = created_at + _timedelta_minutes(remind_minutes)
        deadline_at = deadline.isoformat()
        if elapsed >= escalate_minutes:
            state = SLA_STATE_ESCALATED
            minutes_remaining = 0.0
        elif elapsed >= remind_minutes:
            state = SLA_STATE_OVERDUE
            minutes_remaining = 0.0
        elif elapsed >= remind_minutes * 0.5:
            state = SLA_STATE_AMBER
            minutes_remaining = round(remind_minutes - elapsed, 1)
        else:
            state = SLA_STATE_GREEN
            minutes_remaining = round(remind_minutes - elapsed, 1)

    return {
        "state": state,
        "minutes_elapsed": minutes_elapsed,
        "minutes_remaining": minutes_remaining,
        "deadline_at": deadline_at,
        "first_response_at": lead.get("first_response_at"),
        "sla_reminded_at": lead.get("sla_reminded_at"),
        "sla_escalated_at": lead.get("sla_escalated_at"),
        "thresholds": {
            "remind_minutes": remind_minutes,
            "escalate_minutes": escalate_minutes,
        },
    }


def _timedelta_minutes(n: int):
    from datetime import timedelta
    return timedelta(minutes=int(n))


async def get_lead_sla_state(db, lead_id: str) -> Optional[Dict[str, Any]]:
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        return None
    cfg = await get_thresholds(db)
    state = compute_lead_sla(
        lead,
        remind_minutes=cfg["remind_minutes"],
        escalate_minutes=cfg["escalate_minutes"],
    )
    state["lead_id"] = lead_id
    state["managerId"] = lead.get("managerId")
    return state


# ──────────────────────────────────────────────────────────────────────
# First-response stamp
# ──────────────────────────────────────────────────────────────────────
async def mark_lead_responded(
    db,
    lead_id: str,
    by_user_id: Optional[str] = None,
    *,
    source: str = "manual",
) -> bool:
    """Idempotently set ``first_response_at`` on the lead.

    Returns True if this call actually set the field, False if it was
    already set (or the lead does not exist).

    Safe to call from many hooks (notes, calls, status changes) — only
    the first call will write, all subsequent calls are no-ops.
    """
    if not lead_id:
        return False
    try:
        now_iso = _now_iso()
        result = await db.leads.update_one(
            {"id": lead_id, "first_response_at": {"$in": [None, ""]}},
            {"$set": {
                "first_response_at":      now_iso,
                "first_response_by":      by_user_id,
                "first_response_source":  source,
                "updated_at":             now_iso,
            }},
        )
        return result.modified_count > 0
    except Exception as e:
        logger.warning("[lead_sla] mark_lead_responded failed for %s: %s", lead_id, e)
        return False


# ──────────────────────────────────────────────────────────────────────
# Inline notification dispatcher (no Wave-18 dependency)
# ──────────────────────────────────────────────────────────────────────
async def _user_brief(db, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    doc = await db.staff.find_one(
        {"id": user_id},
        {"_id": 0, "id": 1, "name": 1, "role": 1, "email": 1, "team_lead_id": 1},
    )
    return doc


async def _team_lead_of(db, manager_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not manager_id:
        return None
    staff = await db.staff.find_one({"id": manager_id}, {"_id": 0, "team_lead_id": 1})
    tl_id = (staff or {}).get("team_lead_id")
    if not tl_id:
        return None
    return await _user_brief(db, tl_id)


async def _emit_lead_notif(
    db,
    *,
    event: str,
    lead: Dict[str, Any],
    recipient: Dict[str, Any],
    title: str,
    body: str,
    href: Optional[str] = None,
    channel: str = "in_app",
    i18n_key: Optional[str] = None,
    i18n_params: Optional[Dict[str, Any]] = None,
) -> None:
    row = {
        "id":              f"notif_{uuid.uuid4().hex[:12]}",
        "event":           event,
        "lead_id":         lead.get("id"),
        "entity_type":     "lead",
        "entity_id":       lead.get("id"),
        "recipient_id":    recipient.get("id"),
        "recipient_name":  recipient.get("name"),
        "recipient_role":  recipient.get("role"),
        "recipient_email": recipient.get("email"),
        "userId":          recipient.get("id"),  # legacy compat for /api/notifications/me
        "channel":         channel,
        "status":          "sent" if channel == "in_app" else "queued",
        "priority":        "high" if event == EVENT_LEAD_SLA_ESCALATED else "medium",
        "title":           title,
        "body":            body,
        "message":         body,  # legacy compat
        # Доопр #22 — i18n payload so frontend renders in user's lang
        "i18n_key":        i18n_key,
        "i18n_params":     i18n_params or {},
        "href":            href or f"/admin/leads/{lead.get('id')}",
        "meta": {
            "lead_id":        lead.get("id"),
            "lead_first_name": lead.get("firstName") or lead.get("first_name"),
            "lead_last_name":  lead.get("lastName") or lead.get("last_name"),
            "manager_id":     lead.get("managerId"),
            "url":            href or f"/admin/leads/{lead.get('id')}",
        },
        "created_at":   _now_iso(),
        "sent_at":      _now_iso() if channel == "in_app" else None,
        "read_at":      None,
        "dismissed_at": None,
    }
    try:
        await db.notifications.insert_one(row)
    except Exception as e:
        logger.warning("[lead_sla] notification insert failed: %s", e)


# ──────────────────────────────────────────────────────────────────────
# Reassign on escalation (optional, gated by setting)
# ──────────────────────────────────────────────────────────────────────
async def _reassign_to_tl(db, lead: Dict[str, Any], tl: Dict[str, Any]) -> bool:
    try:
        now_iso = _now_iso()
        prev = lead.get("managerId")
        await db.leads.update_one(
            {"id": lead["id"]},
            {"$set": {
                "managerId":               tl["id"],
                "last_status_change_at":   now_iso,
                "last_status_change_by":   "system:lead_sla",
                "last_status_change_reason": "sla_auto_escalation",
                "updated_at":              now_iso,
            }},
        )
        # Audit trail (best-effort)
        try:
            await db.reassignments.insert_one({
                "id":            f"reas_{uuid.uuid4().hex[:12]}",
                "entity":        "lead",
                "entityId":      lead["id"],
                "fromManagerId": prev,
                "toManagerId":   tl["id"],
                "reason":        "auto_sla_escalation",
                "performedBy":   "system",
                "performedByRole": "system",
                "createdAt":     now_iso,
            })
        except Exception:
            pass
        return True
    except Exception as e:
        logger.warning("[lead_sla] auto-reassign to TL failed for %s: %s", lead.get("id"), e)
        return False


# ──────────────────────────────────────────────────────────────────────
# Overdue scan (idempotent worker tick)
# ──────────────────────────────────────────────────────────────────────
async def scan_overdue_leads(db) -> Dict[str, int]:
    """Scan leads that have NOT received first response yet and emit
    reminder / escalation notifications based on configured thresholds.

    Returns a small report dict for logging:

        {"scanned": N, "reminded": R, "escalated": E, "auto_reassigned": A}
    """
    cfg = await get_thresholds(db)
    remind = int(cfg["remind_minutes"])
    escalate = int(cfg["escalate_minutes"])
    auto_reassign = bool(cfg["auto_reassign"])

    now = _now()
    from datetime import timedelta
    remind_cutoff = now - timedelta(minutes=remind)
    escalate_cutoff = now - timedelta(minutes=escalate)

    # Pull only candidate leads (first_response_at unset + has manager + not terminal)
    query = {
        "$and": [
            {"$or": [{"first_response_at": None}, {"first_response_at": {"$exists": False}}, {"first_response_at": ""}]},
            {"managerId": {"$nin": [None, ""]}},
            {"status": {"$nin": list(TERMINAL_LEAD_STATUSES)}},
            {"$or": [{"created_at": {"$lte": remind_cutoff.isoformat()}}, {"created_at": {"$lte": remind_cutoff}}]},
        ]
    }
    rows = await db.leads.find(query, {"_id": 0}).limit(2000).to_list(length=2000)

    reminded = 0
    escalated = 0
    auto_reassigned = 0
    scanned = len(rows)

    for lead in rows:
        created_at = _parse(lead.get("created_at"))
        if not created_at:
            continue
        manager_id = lead.get("managerId")
        manager = await _user_brief(db, manager_id)
        tl = await _team_lead_of(db, manager_id)
        first_name = lead.get("firstName") or lead.get("first_name") or ""
        last_name = lead.get("lastName") or lead.get("last_name") or ""
        lead_label = f"{first_name} {last_name}".strip() or lead.get("id", "(lead)")

        # ── Escalation check first (more severe wins) ─────────────────
        if created_at <= escalate_cutoff and not lead.get("sla_escalated_at"):
            now_iso = _now_iso()
            # Also set sla_reminded_at to prevent a later reminder pass
            # from firing on an already-escalated lead.
            await db.leads.update_one(
                {"id": lead["id"]},
                {"$set": {
                    "sla_escalated_at": now_iso,
                    "sla_reminded_at":  lead.get("sla_reminded_at") or now_iso,
                    "updated_at":       now_iso,
                }},
            )
            # notify manager
            if manager:
                await _emit_lead_notif(
                    db,
                    event=EVENT_LEAD_SLA_ESCALATED,
                    lead=lead,
                    recipient=manager,
                    title="Lead escalated — SLA breach (2h)",
                    body=f"Lead «{lead_label}» has no response for >{escalate} min. Escalated to your team lead.",
                    i18n_key="notif_sla_escalated_mgr",
                    i18n_params={"lead": lead_label, "minutes": escalate},
                )
            if tl:
                await _emit_lead_notif(
                    db,
                    event=EVENT_LEAD_SLA_ESCALATED,
                    lead=lead,
                    recipient=tl,
                    title="Lead escalated to you (SLA 2h breach)",
                    body=f"Lead «{lead_label}» owned by {manager.get('name') if manager else 'a manager'} hit the {escalate}-min escalation threshold.",
                    i18n_key="notif_sla_escalated_tl",
                    i18n_params={"lead": lead_label, "manager": (manager or {}).get("name") or "—", "minutes": escalate},
                )
            if auto_reassign and tl:
                if await _reassign_to_tl(db, lead, tl):
                    auto_reassigned += 1
            escalated += 1
            continue

        # ── Reminder ──────────────────────────────────────────────────
        if created_at <= remind_cutoff and not lead.get("sla_reminded_at"):
            now_iso = _now_iso()
            await db.leads.update_one(
                {"id": lead["id"]},
                {"$set": {"sla_reminded_at": now_iso, "updated_at": now_iso}},
            )
            if manager:
                await _emit_lead_notif(
                    db,
                    event=EVENT_LEAD_SLA_WARNING,
                    lead=lead,
                    recipient=manager,
                    title=f"Lead SLA warning ({remind} min)",
                    body=f"Lead «{lead_label}» still has no first response after {remind} min. Reach out now.",
                    i18n_key="notif_sla_warning_mgr",
                    i18n_params={"lead": lead_label, "minutes": remind},
                )
            if tl:
                await _emit_lead_notif(
                    db,
                    event=EVENT_LEAD_SLA_WARNING,
                    lead=lead,
                    recipient=tl,
                    title=f"Team SLA warning: {remind} min without response",
                    body=f"{manager.get('name') if manager else 'A manager'} has not responded to lead «{lead_label}» yet.",
                    i18n_key="notif_sla_warning_tl",
                    i18n_params={"lead": lead_label, "manager": (manager or {}).get("name") or "—", "minutes": remind},
                )
            reminded += 1

    return {
        "scanned": scanned,
        "reminded": reminded,
        "escalated": escalated,
        "auto_reassigned": auto_reassigned,
    }


# ──────────────────────────────────────────────────────────────────────
# Overdue listing for TL/admin dashboards
# ──────────────────────────────────────────────────────────────────────
async def list_overdue_leads(
    db,
    *,
    only_escalated: bool = False,
    manager_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List leads currently in OVERDUE or ESCALATED state, newest first."""
    cfg = await get_thresholds(db)
    remind = int(cfg["remind_minutes"])
    escalate = int(cfg["escalate_minutes"])
    now = _now()
    from datetime import timedelta
    cutoff = now - timedelta(minutes=escalate if only_escalated else remind)
    q: Dict[str, Any] = {
        "$and": [
            {"$or": [{"first_response_at": None}, {"first_response_at": {"$exists": False}}, {"first_response_at": ""}]},
            {"managerId": {"$nin": [None, ""]}},
            {"status": {"$nin": list(TERMINAL_LEAD_STATUSES)}},
            {"$or": [{"created_at": {"$lte": cutoff.isoformat()}}, {"created_at": {"$lte": cutoff}}]},
        ]
    }
    if manager_id:
        q["managerId"] = manager_id
    rows = await db.leads.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    out: List[Dict[str, Any]] = []
    for lead in rows:
        sla = compute_lead_sla(
            lead, remind_minutes=remind, escalate_minutes=escalate, now=now,
        )
        out.append({
            "lead_id":    lead.get("id"),
            "firstName":  lead.get("firstName") or lead.get("first_name"),
            "lastName":   lead.get("lastName") or lead.get("last_name"),
            "phone":      lead.get("phone"),
            "email":      lead.get("email"),
            "status":     lead.get("status"),
            "source":     lead.get("source"),
            "managerId":  lead.get("managerId"),
            "created_at": lead.get("created_at"),
            "sla":        sla,
        })
    return out


__all__ = [
    "TERMINAL_LEAD_STATUSES",
    "get_thresholds", "set_thresholds",
    "compute_lead_sla", "get_lead_sla_state",
    "mark_lead_responded",
    "scan_overdue_leads", "list_overdue_leads",
]
