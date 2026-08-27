"""BIBI Cars backend — modular application package.

This package is the destination of the Controlled Modular Monolith refactoring
started on 2026-05-17. New routers, services, repositories, workers,
integrations and utilities should live here — never inside ``server.py``.

Layout:
    routers/        FastAPI APIRouter modules (one per /api/<domain> prefix)
    services/       Domain services / business logic facades
    repositories/   Thin DAO layer over Motor (added in P3)
    models/         Pydantic request/response models
    events/         Event bus + event types (added in P5)
    workers/        Background asyncio workers (added in P3)
    integrations/   External services (Ringostat, Carfax, Stripe, ...)
    core/           Cross-cutting concerns (deps, security wiring, config)
    utils/          Pure helpers (serialization, money, datetime, validation)
"""
