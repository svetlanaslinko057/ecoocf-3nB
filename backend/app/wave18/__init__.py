"""BIBI Cars — Wave 18 — Communication & Notification Center.

First delivery channel layer. Source of every notification is the
Action lifecycle (Wave 17), not the risk feeds directly. Plus a built-in
SLA Escalation Engine (Wave 18.1) that scans overdue actions and
automatically promotes them up the chain (manager → team_lead → admin).

Public surface (see ``router.py``):

    GET  /api/notifications/inbox          — caller's notifications (paged)
    GET  /api/notifications/unread-count   — cheap badge counter
    POST /api/notifications/{id}/read      — mark single notification as read
    POST /api/notifications/read-all       — mark every unread as read
    POST /api/notifications/{id}/dismiss   — hide from inbox
    GET  /api/notifications/preferences    — caller channel/digest prefs
    PATCH /api/notifications/preferences   — update preferences
    GET  /api/notifications/rules          — dispatch-rule catalogue (no DB)
    GET  /api/notifications/analytics      — per-channel/per-event volume
    POST /api/notifications/escalation/scan — Wave 18.1 SLA scan (idempotent)

On import this module also REGISTERS itself as an Action-lifecycle event
handler, so any state change in Wave 17 automatically produces the right
notifications. Errors in dispatch never propagate — actions stay
authoritative even if the notification layer is wedged.
"""
from .dispatcher import register   # auto-registers the handler on import

register()

from .router import router as wave18_router

__all__ = ["wave18_router"]
