"""BIBI Cars — Wave 15 — Contract Lifecycle Management (Contract360).

Fills the contractual vacuum between Deal360 and Finance360.

Public surface (see ``router.py``):

    GET    /api/contracts/overview          — Contract360 dashboard.
    GET    /api/contracts                   — list (scope-aware, filters).
    POST   /api/contracts                   — create from template or deal.
    GET    /api/contracts/templates         — 4 default templates.
    GET    /api/contracts/risk              — at-risk contracts.
    GET    /api/contracts/{id}              — full Contract360 bundle.
    PATCH  /api/contracts/{id}              — update terms / parties.
    POST   /api/contracts/{id}/send         — push to next approver / customer.
    POST   /api/contracts/{id}/approve      — manager → team_lead → admin step.
    POST   /api/contracts/{id}/reject       — reject step (sets back to draft).
    POST   /api/contracts/{id}/sign         — record customer signature.
    POST   /api/contracts/{id}/amend        — create amended version.
    POST   /api/contracts/{id}/archive      — terminal archive.
    POST   /api/contracts/{id}/attachments  — upload attachment.
    DELETE /api/contracts/{id}/attachments/{aid} — remove attachment.

All endpoints are scope-aware (admin = all, team_lead = team, manager = own).
Mutations require manager-or-admin auth.
"""
from .router import router as wave15_router

__all__ = ["wave15_router"]
