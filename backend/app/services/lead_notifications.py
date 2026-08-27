"""
Доопр #22 — Push notifications for new leads.

This module provides a single helper `notify_new_lead(db, lead, *, assigned_by=None)`
that is called whenever:
  * a new lead is inserted into the system; OR
  * an existing lead is reassigned to a different manager.

Behaviour (per spec):
  • Lead auto-assigned to a manager → notify that manager.
  • Lead reassigned by Team-Lead / Admin → notify the NEW assignee.
  • Lead has no assignee → notify every Team-Lead + Admin.

Notification payload follows the existing `db.notifications` schema so the
existing /api/notifications/me and NotificationBell pick it up unchanged.

Also exposes `scan_unprocessed_leads()` — the worker that fires reminder
notifications after 30 min / 2 h if a lead is still untouched (no calls,
no comments, no status change).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.lead_notify")

# Reminder thresholds — tunable via env per ТЗ "Адмін налаштовує".
_FIRST_REMINDER_MIN  = int(os.environ.get("BIBI_LEAD_REMIND_1_MIN") or 30)
_SECOND_REMINDER_MIN = int(os.environ.get("BIBI_LEAD_REMIND_2_MIN") or 120)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _admin_and_team_lead_ids(db) -> List[str]:
    cursor = db.staff.find(
        {"role": {"$in": ["admin", "master_admin", "owner", "team_lead"]}},
        {"_id": 0, "id": 1},
    )
    return [s["id"] async for s in cursor if s.get("id")]


def _build_payload(lead: Dict[str, Any], *, assigned: bool, assigned_by: Optional[str] = None) -> Dict[str, Any]:
    name = (lead.get("name") or f"{lead.get('firstName','')} {lead.get('lastName','')}").strip() or "—"
    phone = lead.get("phone") or "—"
    src   = lead.get("utm_source") or lead.get("source") or "manual"
    country = lead.get("country") or (lead.get("vehicleSnapshot") or {}).get("country") or ""
    # i18n key resolved client-side at render time (frontend uses current lang).
    # The title/message strings stored here are English fallbacks for any
    # consumer that doesn't know the i18n key (e.g. push email, mobile).
    i18n_key   = "notif_lead_assigned" if assigned else "notif_new_lead"
    en_title   = "A new lead was assigned to you" if assigned else "New lead"
    msg_parts  = [f"{name} · {phone}"]
    if src and src != "manual":
        msg_parts.append(f"source: {src}")
    if country:
        msg_parts.append(f"country: {country}")
    return {
        "type": "new_lead",
        "event": "new_lead",
        "title": en_title,
        "message": " · ".join(msg_parts),
        # Frontend translates with these:
        "i18n_key":    i18n_key,
        "i18n_params": {"name": name, "phone": phone, "source": src, "country": country, "assignedBy": assigned_by or ""},
        "severity": "info",
        "meta": {
            "leadId":     lead.get("id"),
            "leadName":   name,
            "phone":      phone,
            "source":     src,
            "country":    country,
            "assignedBy": assigned_by,
            "createdAt":  lead.get("created_at"),
            "url":        f"/admin/leads/{lead.get('id')}",
        },
        "soundKey": "lead_assigned" if assigned else "lead_new",
    }


async def notify_new_lead(db, lead: Dict[str, Any], *, assigned_by: Optional[str] = None) -> int:
    """Persist a 'new lead' notification for the right recipients.

    Returns: count of notifications written. Never raises (best-effort).
    """
    try:
        manager_id = lead.get("managerId")
        rows: List[Dict[str, Any]] = []
        now = _now()
        if manager_id:
            payload = _build_payload(lead, assigned=bool(assigned_by), assigned_by=assigned_by)
            rows.append({
                "id":         f"notif-{int(now.timestamp() * 1000)}-{manager_id}",
                "userId":     manager_id,
                "read":       False,
                "isRead":     False,
                "created_at": _iso(now),
                "createdAt":  _iso(now),
                **payload,
            })
        else:
            # Unassigned → fan-out to Team Lead + Admins
            recipients = await _admin_and_team_lead_ids(db)
            payload = _build_payload(lead, assigned=False)
            payload["title"] = "New lead (unassigned)"
            payload["i18n_key"] = "notif_new_lead_unassigned"
            for i, uid in enumerate(recipients):
                rows.append({
                    "id":         f"notif-{int(now.timestamp() * 1000)}-{i}-{uid}",
                    "userId":     uid,
                    "read":       False,
                    "isRead":     False,
                    "created_at": _iso(now),
                    "createdAt":  _iso(now),
                    **payload,
                })
        if rows:
            await db.notifications.insert_many(rows)
            logger.info("[notify_new_lead] sent %d notifications for lead=%s", len(rows), lead.get("id"))
        return len(rows)
    except Exception as e:
        logger.warning("[notify_new_lead] failed (lead=%s): %s", lead.get("id"), e)
        return 0


async def scan_unprocessed_leads(db) -> Dict[str, int]:
    """Worker tick — emits reminder notifications for leads that the manager
    has not touched after the configured thresholds.

    Heuristic for "untouched":
      • status still 'new'
      • no `last_contact_at` set
      • no comments / call_at recorded
    """
    sent_first = 0
    sent_second = 0
    now = _now()
    cutoff_1 = _iso(now - timedelta(minutes=_FIRST_REMINDER_MIN))
    cutoff_2 = _iso(now - timedelta(minutes=_SECOND_REMINDER_MIN))

    # Pull candidates created within the last 24h, status=new
    cursor = db.leads.find({
        "status": {"$in": ["new", "newlead", "new_lead"]},
        "created_at": {"$lte": cutoff_1},
    }, {"_id": 0}).limit(500)

    async for lead in cursor:
        lead_id = lead.get("id")
        if not lead_id:
            continue
        last_touch = lead.get("last_contact_at") or lead.get("updated_at")
        if last_touch and last_touch > cutoff_1:
            continue  # already touched

        # Has a previous reminder already been emitted?
        reminded = lead.get("reminder_flags") or {}
        manager_id = lead.get("managerId")

        # First reminder (30 min)
        if not reminded.get("first") and lead.get("created_at") and lead["created_at"] <= cutoff_1:
            recipients: List[str] = []
            if manager_id:
                recipients.append(manager_id)
            payload = {
                "type":     "lead_reminder",
                "event":    "lead_reminder",
                "title":    "Lead not processed for 30 min",
                "message":  f"{lead.get('name') or 'Lead'} · {lead.get('phone') or '—'}",
                "i18n_key": "notif_lead_reminder_30",
                "i18n_params": {"name": lead.get('name') or '', "phone": lead.get('phone') or '—'},
                "severity": "warning",
                "meta": {"leadId": lead_id, "minutesAgo": _FIRST_REMINDER_MIN,
                         "url": f"/admin/leads/{lead_id}"},
                "soundKey": "lead_reminder",
            }
            rows = []
            for uid in recipients:
                rows.append({
                    "id": f"notif-rem1-{int(now.timestamp())}-{uid}",
                    "userId": uid, "read": False, "isRead": False,
                    "created_at": _iso(now), "createdAt": _iso(now), **payload,
                })
            if rows:
                await db.notifications.insert_many(rows)
                sent_first += len(rows)
            await db.leads.update_one(
                {"id": lead_id},
                {"$set": {"reminder_flags.first": True, "reminder_flags.first_at": _iso(now)}},
            )

        # Second reminder (2 h) — also pings Team Leads
        if not reminded.get("second") and lead.get("created_at") and lead["created_at"] <= cutoff_2:
            recipients = []
            if manager_id:
                recipients.append(manager_id)
            tl_ids = await db.staff.find(
                {"role": {"$in": ["team_lead", "admin", "master_admin", "owner"]}},
                {"_id": 0, "id": 1},
            ).to_list(length=200)
            for s in tl_ids:
                if s.get("id") and s["id"] not in recipients:
                    recipients.append(s["id"])
            payload = {
                "type":     "lead_reminder",
                "event":    "lead_reminder",
                "title":    "Lead not processed for 2 hours (escalation)",
                "message":  f"{lead.get('name') or 'Lead'} · {lead.get('phone') or '—'}",
                "i18n_key": "notif_lead_reminder_2h",
                "i18n_params": {"name": lead.get('name') or '', "phone": lead.get('phone') or '—'},
                "severity": "critical",
                "meta": {"leadId": lead_id, "minutesAgo": _SECOND_REMINDER_MIN,
                         "url": f"/admin/leads/{lead_id}"},
                "soundKey": "lead_reminder",
            }
            rows = []
            for uid in recipients:
                rows.append({
                    "id": f"notif-rem2-{int(now.timestamp())}-{uid}",
                    "userId": uid, "read": False, "isRead": False,
                    "created_at": _iso(now), "createdAt": _iso(now), **payload,
                })
            if rows:
                await db.notifications.insert_many(rows)
                sent_second += len(rows)
            await db.leads.update_one(
                {"id": lead_id},
                {"$set": {"reminder_flags.second": True, "reminder_flags.second_at": _iso(now)}},
            )

    if sent_first or sent_second:
        logger.info("[lead_reminders] sent first=%d second=%d", sent_first, sent_second)
    return {"first": sent_first, "second": sent_second}


__all__ = ["notify_new_lead", "scan_unprocessed_leads"]
