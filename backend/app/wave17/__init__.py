"""BIBI Cars — Wave 17 — Action Center.

First Wave with its own business entity (the `actions` collection). Every
risk / bottleneck exposed by Operations360, Forecast360, Contract360 or
Delivery360 can be promoted to an Action with an explicit owner, deadline
and resolution audit trail.

Public surface (see ``router.py``):

    GET    /api/actions/inbox         — Tab 1: all open actions (severity-ordered)
    GET    /api/actions/my            — Tab 2: actions assigned to caller
    GET    /api/actions/team          — Tab 3: actions for the caller's team (team_lead)
    GET    /api/actions/analytics     — Tab 4: resolution analytics (created/resolved/avg time/overdue %)
    GET    /api/actions               — list with filters
    GET    /api/actions/sources       — catalogue of suggestion rules (no DB hit)
    POST   /api/actions               — create manual action
    GET    /api/actions/{id}          — detail bundle
    PATCH  /api/actions/{id}          — edit fields
    POST   /api/actions/{id}/assign   — reassign
    POST   /api/actions/{id}/start    — open → in_progress
    POST   /api/actions/{id}/resolve  — → resolved
    POST   /api/actions/{id}/snooze   — → snoozed (with snooze_until)
    POST   /api/actions/{id}/escalate — marks escalated + reassigns up the chain
    POST   /api/actions/{id}/reopen   — resolved/snoozed → open
    POST   /api/actions/sync          — idempotent: scan sources → upsert open actions
"""
from .router import router as wave17_router

__all__ = ["wave17_router"]
