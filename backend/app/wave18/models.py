"""
BIBI Cars — Wave 18 — Notification models + dispatch rules
=============================================================
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

NOTIFICATION_EVENTS = (
    "action_created", "action_assigned", "action_started",
    "action_snoozed", "action_escalated", "action_reopened",
    "action_resolved", "action_cancelled", "action_commented",
    "action_overdue",                         # produced by Wave 18.1 scanner
    "action_critical_overdue",                # > 7d overdue
)
NOTIFICATION_CHANNELS = ("in_app", "email", "telegram", "slack", "sms")
NOTIFICATION_STATUSES = ("queued", "sent", "failed", "read", "dismissed")


# Dispatch rules: event → [(recipient_role, channels)]
# `recipient_role` is one of:
#   owner               — action.owner_id
#   previous_owner      — meta.previous_owner_id (assign / escalate)
#   creator             — action.created_by
#   team_lead           — team_lead of owner (looked up via staff.team_lead_id)
#   admin               — every user with role == "admin" / "master_admin"
#
# This dict is intentionally explicit, not data-driven — it should be
# easy to reason about in code review.
DISPATCH_RULES: Dict[str, List[Dict[str, Any]]] = {
    "action_created":          [{"recipient": "owner",          "channels": ["in_app"]}],
    "action_assigned":         [{"recipient": "owner",          "channels": ["in_app", "email"]},
                                  {"recipient": "previous_owner", "channels": ["in_app"]}],
    "action_started":          [],   # internal state change, no notification needed
    "action_snoozed":          [],
    "action_escalated":        [{"recipient": "owner",          "channels": ["in_app", "email"]},
                                  {"recipient": "previous_owner", "channels": ["in_app"]},
                                  {"recipient": "admin",          "channels": ["in_app"]}],
    "action_reopened":         [{"recipient": "owner",          "channels": ["in_app"]}],
    "action_resolved":         [{"recipient": "creator",        "channels": ["in_app"]}],
    "action_cancelled":        [{"recipient": "creator",        "channels": ["in_app"]}],
    "action_commented":        [{"recipient": "owner",          "channels": ["in_app"]}],
    "action_overdue":          [{"recipient": "owner",          "channels": ["in_app", "email"]}],
    "action_critical_overdue": [{"recipient": "owner",          "channels": ["in_app", "email"]},
                                  {"recipient": "admin",          "channels": ["in_app", "email"]}],
}


# SLA Escalation thresholds (Wave 18.1). All values are HOURS overdue.
SLA_THRESHOLDS = {
    "remind_owner":     24,    # > 1d: notify owner
    "escalate_team_lead": 72,  # > 3d: re-assign + escalate to team_lead
    "escalate_admin":   168,   # > 7d: escalate to admin + critical_overdue
}


class NotificationPreferences(BaseModel):
    user_id:  str
    channels: Dict[str, bool] = Field(default_factory=lambda: {"in_app": True, "email": True, "telegram": False, "slack": False, "sms": False})
    mute_until:  Optional[str] = None
    digest:      str = "realtime"   # realtime | daily | weekly
    quiet_hours: Optional[Dict[str, str]] = None   # { from: "22:00", to: "08:00" }


class PreferencesPatch(BaseModel):
    channels:    Optional[Dict[str, bool]] = None
    mute_until:  Optional[str] = None
    digest:      Optional[str] = None
    quiet_hours: Optional[Dict[str, str]] = None


__all__ = [
    "NOTIFICATION_EVENTS", "NOTIFICATION_CHANNELS", "NOTIFICATION_STATUSES",
    "DISPATCH_RULES", "SLA_THRESHOLDS",
    "NotificationPreferences", "PreferencesPatch",
]
