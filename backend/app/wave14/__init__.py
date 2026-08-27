"""BIBI Cars — Wave 14 — Operations 360.

CEO/Owner-grade overview that aggregates everything built in Waves 1–13:

* Company Health Dashboard (KPI grid)
* Bottleneck Engine (“where is the company stuck right now?”)
* Team Performance 360 (Manager P&L + operational quality)
* SLA Monitor (lead response / deal stagnation / deposit / carrier / customs)
* Risk Center (unified Lead/Customer/Financial/Delivery risk)

Public surface (see `router.py`):
    GET /api/operations/dashboard
    GET /api/operations/bottlenecks
    GET /api/operations/team
    GET /api/operations/sla
    GET /api/operations/risk
"""
from .router import router as wave14_router

__all__ = ["wave14_router"]
