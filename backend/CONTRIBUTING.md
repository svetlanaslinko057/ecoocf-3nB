# Backend Contribution Guide — Controlled Modular Monolith

> Status: **active refactoring** (started 2026-05-17).
> See `/app/plan.md` for the full audit and refactor roadmap.

---

## ⛔ Hard rules

1. **`server.py` is feature-frozen.** No new routes, no new business logic.
   The only allowed edits in `server.py` are:
   - removing endpoints being extracted (cut-and-paste into `app/routers/`),
   - adding `fastapi_app.include_router(...)` calls,
   - critical bug fixes (with explicit reviewer sign-off).
2. **Every new endpoint goes into `backend/app/routers/<domain>.py`.**
3. **Mechanical extraction only.** During P1 we *move* code, we do not *rewrite* code.
   - Do not refactor imports.
   - Do not "fix obvious things" while extracting.
   - Do not change DB collection names, response shapes, or error messages.
   - Behavior change goes into a separate commit *after* the extraction lands.
4. **One domain = one commit.**
5. **Surgical diffs.** No `ruff --fix`, no `black .`, no mass import reorder.

---

## 🗂 Target layout

```
backend/
├── server.py                       # legacy bootstrap (shrinks every commit)
├── app/
│   ├── __init__.py
│   ├── routers/                    # @APIRouter modules, 1 file per /api/<domain>
│   │   ├── __init__.py
│   │   └── <domain>.py
│   ├── services/                   # domain services (P2+)
│   ├── repositories/               # Mongo DAO layer (P3)
│   ├── models/                     # Pydantic schemas (extracted gradually)
│   ├── workers/                    # background asyncio tasks (P3)
│   ├── integrations/               # Ringostat / Stripe / Carfax / ... (P4)
│   ├── events/                     # event bus + event types (P5)
│   ├── core/
│   │   └── deps.py                 # get_db(), get_sio(), etc.
│   └── utils/                      # pure helpers (P6)
└── (existing legacy modules:        # already extracted, keep as-is until P7
     legal_workflow.py, notifications.py, payments_tracking.py,
     cabinet_financials.py, financial_breakdown.py, multisource_resolver.py,
     shipment_identity_resolver.py, resolver_engine.py, settings_service.py,
     security.py, ops_guardian.py, ...)
```

---

## 📦 Router file header (ownership marker)

Every extracted router **must** start with:

```python
"""<domain>: <short description>

OWNER:  <domain>-domain
SOURCE: extracted from legacy server.py on YYYY-MM-DD
WAVE:   1 | 2 | 3
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/<domain>", tags=["<domain>"])
```

---

## 🔁 Extraction recipe (per domain)

For each `/api/<domain>/*` group:

1. **Inventory** — `grep -nE '@fastapi_app\.[a-z]+\("/api/<domain>' server.py`.
2. **Snapshot** — `curl -s http://localhost:8001/api/openapi.json > before.json`.
3. **Create** `app/routers/<domain>.py` with the ownership header and `router = APIRouter(prefix="/api/<domain>")`.
4. **Cut & paste** each endpoint, replacing `@fastapi_app.X("/api/<domain>/Y")` → `@router.X("/Y")`.
5. **Imports** — duplicate only what the router actually needs (BaseModel, Depends, Body, etc.). For shared globals (db, sio, parser instance) use `app.core.deps`.
6. **Wire** — in `server.py`, add `from app.routers.<domain> import router as <domain>_router` and `fastapi_app.include_router(<domain>_router)`.
7. **Smoke**:
   - `supervisorctl restart backend` and check `/var/log/supervisor/backend.err.log` is clean.
   - `curl http://localhost:8001/api/openapi.json > after.json` and diff against `before.json` — route count and paths must match exactly.
   - Manually `curl` 3–5 representative endpoints.
8. **Commit** — one focused commit per domain, message: `extract <domain> router (Wave N)`.

---

## 🚨 What NOT to do during P1

- ❌ Do not introduce `Depends(get_db)` everywhere — that's a P2 task. For now keep the legacy global `db` available via `app.core.deps.get_db()` *only where needed*.
- ❌ Do not change Pydantic models. Move them into the router file 1-to-1.
- ❌ Do not split a single domain into multiple commits — extract atomically.
- ❌ Do not rename collections, fields, or response keys.
- ❌ Do not change `dependencies=[Depends(require_*)]` decorators.

---

## 🛡 CI guardrail — `scripts/check_server_freeze.sh`

This script counts `@fastapi_app.{get,post,put,delete,patch,websocket,on_event}` decorators in `server.py` and compares against `backend/.server_freeze_baseline`.

  * **Increase → FAIL** (someone tried to add a new endpoint to server.py)
  * **Decrease → auto-update baseline** (legitimate extraction commit)
  * **No change → OK**

Wire it into CI as the very first job. Pre-commit hook stub:

```bash
# .git/hooks/pre-commit  (optional local enforcement)
#!/usr/bin/env bash
exec backend/scripts/check_server_freeze.sh
```

If the script complains, your fix is ALWAYS to move the endpoint into a router.

---

## 🗺 Router → server.py dependency map

Every extraction commit must update `backend/REFACTOR_DEPENDENCIES.md` so that Phase 2 (app.state migration) has a complete edge inventory. A router with **zero** entries in that table is a Phase 1 graduation candidate.

---

## 📅 Wave plan

| Wave | Domains | Risk |
|---|---|---|
| **1** | calculations, payments, legal, cabinet, notifications | low (semi-isolated) |
| **2** | calculator, leads, tasks, marketing | medium |
| **3** | ingestion, bidcars, copart, carfast, socket.io, ringostat, shipments | high (workers, global state) |

After each wave: full regression sweep via `testing_agent_v3`.
