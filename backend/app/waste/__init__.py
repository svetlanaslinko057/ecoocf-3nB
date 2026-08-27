"""
ECO Waste domain package
=========================

Wave 2 — Waste Core for the hazardous-waste utilization platform.

This package is intentionally self-contained and decoupled from the legacy
car-domain monolith (``server.py``). It owns the new Mongo collections:

    waste_codes          — National Waste List directory (the SEO/calculator base)
    waste_companies      — B2B clients (Company360)
    waste_objects        — company sites/branches (hospital, factory, lab, ...)
    waste_license_matrix — code -> can we accept? under which license? valid until
    waste_requests       — request lifecycle: new -> quote -> contract -> pickup
                           -> utilization -> act -> archive

All HTTP routes live under the ``/api/waste`` prefix and are mounted into the
existing FastAPI app via ``app.waste.router.router``.
"""
