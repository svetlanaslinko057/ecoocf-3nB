"""BIBI Cars — Wave 16 — Executive Center.

Top-level governance surface that mounts ABOVE every operational 360:
  * Operations360, Forecasting360, Contract360, Finance360, Delivery360.

Pure read-only orchestrator — it does not own any business logic, it just
stitches Wave12C / Wave13 / Wave14 / Wave15 aggregators into one
company-wide owner dashboard.

Public surface (see ``router.py``):

    GET /api/executive/dashboard    — 5 tab “what is happening today” KPIs
    GET /api/executive/forecast     — 30/60/90 outlook from Wave 12C
    GET /api/executive/bottlenecks  — unified Ops + Delivery + Contract + Finance table
    GET /api/executive/risks        — unified Lead / Financial / Delivery / Contract risk feed
    GET /api/executive/team         — Wave14 team perf + forecast accuracy + ops score
"""
from .router import router as wave16_router

__all__ = ["wave16_router"]
