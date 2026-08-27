"""
BIBI Cars — Wave 18.1 — SLA Escalation Engine
=================================================

Idempotent background scan that finds overdue actions and:

  *  > 24h overdue → emits ``action_overdue`` (notification only).
  *  > 72h overdue → reassigns to team_lead (if not already) + emits
     ``action_escalated``.
  *  > 7d  overdue → reassigns to admin (if not already) + emits
     ``action_critical_overdue`` (admin notified in-app + email).

Dedup is per-action via embedded ``escalation_log`` markers, so two scans
in a row produce **no** duplicate notifications.

This is what closes the loop:
    Risk → Action → Notification → Escalation → Resolution → Analytics
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from app.wave18.dispatcher import dispatch_event
from app.wave18.models import SLA_THRESHOLDS


def _parse(iso: Optional[str]) -> Optional[datetime]:
    if not iso: return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None


async def _find_team_lead(db, owner_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not owner_id: return None
    staff = await db.staff.find_one({"id": owner_id}, {"_id": 0, "team_lead_id": 1})
    tl_id = (staff or {}).get("team_lead_id")
    if not tl_id:
        return None
    tl = await db.staff.find_one({"id": tl_id}, {"_id": 0, "id": 1, "name": 1, "role": 1})
    return tl


async def _find_first_admin(db) -> Optional[Dict[str, Any]]:
    return await db.staff.find_one(
        {"role": {"$in": ["admin", "master_admin"]}, "active": {"$ne": False}},
        {"_id": 0, "id": 1, "name": 1, "role": 1}
    )


async def scan_overdue(db) -> Dict[str, int]:
    """Scan every open/in_progress action and apply SLA escalation.

    Returns a small report:
        { reminded, escalated_to_tl, escalated_to_admin, scanned }
    """
    now = datetime.now(timezone.utc)
    reminded = 0; esc_tl = 0; esc_admin = 0
    rows = await db.actions.find(
        {"status": {"$in": ["open", "in_progress"]}, "due_at": {"$ne": None}},
        {"_id": 0}
    ).to_list(length=5000)
    for a in rows:
        due = _parse(a.get("due_at"))
        if not due or due >= now:
            continue
        hours = (now - due).total_seconds() / 3600.0
        log: Dict[str, Any] = a.get("escalation_log") or {}

        # > 24h → remind owner (once)
        if hours >= SLA_THRESHOLDS["remind_owner"] and not log.get("reminded_at"):
            log["reminded_at"] = now.isoformat()
            await db.actions.update_one(
                {"id": a["id"]},
                {"$set": {"escalation_log": log, "updated_at": now.isoformat()},
                 "$push": {"events": {"kind": "sla_remind", "at": now.isoformat(),
                                        "note": f"Overdue {int(hours)}h"}}}
            )
            await dispatch_event(db, "action_overdue", {**a, "escalation_log": log}, None, {"hours_overdue": int(hours)})
            reminded += 1

        # > 72h → escalate to team_lead (once)
        if hours >= SLA_THRESHOLDS["escalate_team_lead"] and not log.get("escalated_to_tl_at"):
            tl = await _find_team_lead(db, a.get("owner_id"))
            new_owner_id = tl.get("id") if tl else a.get("owner_id")
            new_owner_nm = tl.get("name") if tl else a.get("owner_name")
            log["escalated_to_tl_at"] = now.isoformat()
            setter = {"escalation": "team_lead", "escalated": True,
                       "escalation_log": log,
                       "priority":  "high" if a.get("priority") not in ("critical",) else a.get("priority"),
                       "updated_at": now.isoformat()}
            if tl: setter["owner_id"] = new_owner_id; setter["owner_name"] = new_owner_nm
            await db.actions.update_one({"id": a["id"]},
                {"$set": setter,
                 "$push": {"events": {"kind": "sla_escalated", "at": now.isoformat(),
                                        "note": f"SLA escalation to team_lead ({int(hours)}h overdue)"}}}
            )
            fresh = await db.actions.find_one({"id": a["id"]}, {"_id": 0})
            await dispatch_event(db, "action_escalated", fresh or a, None,
                                  {"to_step": "team_lead",
                                   "previous_owner_id": a.get("owner_id"),
                                   "hours_overdue": int(hours)})
            esc_tl += 1
            a = fresh or a   # so the next threshold uses updated doc

        # > 7d → escalate to admin + critical_overdue (once)
        if hours >= SLA_THRESHOLDS["escalate_admin"] and not log.get("escalated_to_admin_at"):
            admin = await _find_first_admin(db)
            new_owner_id = admin.get("id") if admin else a.get("owner_id")
            new_owner_nm = admin.get("name") if admin else a.get("owner_name")
            log["escalated_to_admin_at"] = now.isoformat()
            setter = {"escalation": "admin", "escalated": True,
                       "priority":  "critical",
                       "escalation_log": log,
                       "updated_at": now.isoformat()}
            if admin: setter["owner_id"] = new_owner_id; setter["owner_name"] = new_owner_nm
            await db.actions.update_one({"id": a["id"]},
                {"$set": setter,
                 "$push": {"events": {"kind": "sla_critical", "at": now.isoformat(),
                                        "note": f"SLA admin escalation ({int(hours)}h overdue)"}}}
            )
            fresh = await db.actions.find_one({"id": a["id"]}, {"_id": 0})
            await dispatch_event(db, "action_critical_overdue", fresh or a, None,
                                  {"hours_overdue": int(hours)})
            esc_admin += 1

    return {
        "scanned":              len(rows),
        "reminded":             reminded,
        "escalated_to_tl":      esc_tl,
        "escalated_to_admin":   esc_admin,
    }


__all__ = ["scan_overdue"]
