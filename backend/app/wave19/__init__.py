"""
BIBI Cars — Wave 19 — Customer Portal View (staff side)
=======================================================

Mounted at `/api/customer-portal/*` — accessible to manager / team_lead /
master_admin (existing staff auth). Returns the same trimmed projections that
the customer would see, scoped by the `customer_id` path parameter.

This is a STAFF view of "what the customer is seeing" — there is no
customer-side login. Cross-cutting for the three admin cabinets (manager,
team_lead, admin) so each role can answer the same question:

    "What's happening with this customer's order right now?"
"""
from __future__ import annotations
from .router import router  # noqa: F401

__all__ = ["router"]
