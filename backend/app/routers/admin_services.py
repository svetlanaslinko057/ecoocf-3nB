"""
admin_services — /api/admin/services HTTP surface
==================================================

Wave 2B / Batch 10 / Commit 16 — auth-mixed yellow (1/2).

Mechanical 1:1 extraction of the admin services management surface
(4 endpoints).  The originals at server.py:14266-14324 are preserved
byte-for-byte (only `db = _db()` line added inside each handler).

────────────────────────────────────────────────────────────────────────
Auth-mixed yellow handling — the central discipline of this batch
────────────────────────────────────────────────────────────────────────

Unlike Batch 8/9 routers which had uniform `require_admin`, this surface
mixes TWO auth tiers within a single domain:

  * GET    /api/admin/services              → require_admin
  * POST   /api/admin/services              → require_master_admin
  * PATCH  /api/admin/services/{id}         → require_master_admin
  * DELETE /api/admin/services/{id}         → require_master_admin

Discipline: **per-endpoint `dependencies=[...]` decoration is preserved
verbatim.** Router-level hoisting would either downgrade master_admin
writes to admin OR upgrade the read to master_admin — both would change
behavior. **No auth normalisation in this batch.**  Auth normalisation,
if ever desired, must be a separate mini-commit with OpenAPI/behavior
smoke; this batch is mechanical-only.

────────────────────────────────────────────────────────────────────────
Preserved verbatim — redundant dep signature on POST
────────────────────────────────────────────────────────────────────────

The original POST endpoint (server.py:14273-14274) declares
`Depends(require_master_admin)` TWICE:
  1. as a route dependency: `dependencies=[Depends(require_master_admin)]`
  2. as a parameter:        `user: dict = Depends(require_master_admin)`

The parameter form is used for `created_by` attribution
(`user.get("email") or user.get("id")`).  The route-level form provides
the 401/403 guard.  Both invocations are preserved exactly — this is
Wave 2B mechanical extraction, not "while we're here" cleanup.

────────────────────────────────────────────────────────────────────────
Ownership of `services` collection — PARTIAL transfer
────────────────────────────────────────────────────────────────────────

This router becomes the **runtime mutation owner** of `db.services`:
  - POST inserts new service docs
  - PATCH updates service docs
  - DELETE soft-deletes (sets `is_active=False`)

However, ownership is **partial**, by design.  Residual writers /
readers remain in server.py:

  * `_ensure_services_seed()` (server.py:14195 — startup hook):
      idempotent seed of DEFAULT_SERVICES catalog + backfill of
      multi-language translation fields on first boot.  Same benign
      pattern as `blog_seeder.py` in Batch 7 — startup-only,
      idempotent, no runtime mutation graph.  Phase 5 will colocate
      this seed alongside admin_services.

  * `list_services_public()` (server.py:14253 — `GET /api/services`):
      public/staff read-only listing.  Stays in server.py — extracting
      it would require a Batch 10½ scope-widening to "full services
      domain", which is outside the Batch 10 mandate.  Documented as
      residual cross-auth-boundary reader.

  * `manager_invoice_builder` reader (server.py:14462 onwards):
      reads `db.services.find({id: {$in: ids}})` to attach service
      catalog data to invoice line items.  This is a true cross-domain
      reader (invoice-builder domain).  Stays in server.py until the
      invoice-builder batch.

These residual edges are recorded in REFACTOR_DEPENDENCIES.md for
Phase 3 ownership matrix.

────────────────────────────────────────────────────────────────────────
Bridge surface
────────────────────────────────────────────────────────────────────────

Single bridge: lazy `_db()` — same pattern as Batch 8/9.  Owns its own
collection (`services`) for mutations.  No server.py helper imports
(the original endpoints called only Mongo + stdlib).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_admin, require_master_admin

from app.repositories import ServiceCatalogRepository


def _repo() -> ServiceCatalogRepository:
    """Lazy repository factory.

    Phase 5.4 / C-4f — migrated from the legacy ``from server import db
    as _server_db`` lazy bridge to ``app.core.db_runtime.get_db()``.
    Object identity is preserved 1:1: the canonical ``server.db`` and
    ``get_db()`` reference the same Motor handle (pinned by the
    startup-time identity assertion in ``server.py`` and by
    ``tests/test_phase5_4_c4f_db_repo_batch2.py``).

    Phase 5.3 / C-6 still holds: all ``db.services`` access flows
    through ``ServiceCatalogRepository`` — only the source of the
    Motor handle inside this wrapper changes. The ``_repo()`` wrapper,
    the ``ServiceCatalogRepository`` constructor, and the endpoint
    signatures are byte-for-byte unchanged.
    """
    from app.core.db_runtime import get_db  # noqa: E402 (C-4f: lazy-bridge → accessor)
    return ServiceCatalogRepository(get_db())


router = APIRouter(
    prefix="/api/admin/services",
    tags=["admin-services"],
)


@router.get("", dependencies=[Depends(require_admin)])
async def admin_list_services():
    items = await _repo().list_all()
    return {"success": True, "items": items}


@router.post("", dependencies=[Depends(require_master_admin)])
async def admin_create_service(data: Dict[str, Any] = Body(...), user: dict = Depends(require_master_admin)):
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    code = (data.get("code") or name.lower().replace(" ", "_"))[:64]
    sid = f"svc_{code}_{int(datetime.now(timezone.utc).timestamp())}"
    doc = {
        "id": sid,
        "code": code,
        "name": name,
        "name_en": (data.get("name_en") or "").strip() or name,
        "description": (data.get("description") or "").strip(),
        "category": (data.get("category") or "custom"),
        "default_price": float(data.get("default_price") or 0),
        "currency": (data.get("currency") or "USD").upper(),
        "default_qty": int(data.get("default_qty") or 1),
        "workflow": data.get("workflow") if isinstance(data.get("workflow"), list) else [
            {"key": "pending",     "label": "Очікує"},
            {"key": "in_progress", "label": "В роботі"},
            {"key": "completed",   "label": "Готово"},
        ],
        # Phase Final / Block 1 (Workflow Binding) — live link to
        # workflow_templates. When set, the resolver fetches steps from
        # the template at invoice-creation time; inline ``workflow`` is
        # ignored. ``None`` means "use inline workflow" (legacy services).
        "workflow_template_id": (data.get("workflow_template_id") or data.get("workflowTemplateId") or None),
        "is_active": bool(data.get("is_active", True)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email") or user.get("id"),
    }
    await _repo().create(doc)
    doc.pop("_id", None)
    return {"success": True, "service": doc}


@router.patch("/{service_id}", dependencies=[Depends(require_master_admin)])
async def admin_update_service(service_id: str, data: Dict[str, Any] = Body(...)):
    allowed = {"name", "name_en", "description", "category", "default_price", "currency", "default_qty", "workflow", "workflow_template_id", "is_active"}
    upd = {k: v for k, v in (data or {}).items() if k in allowed}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo = _repo()
    if not await repo.exists_by_id(service_id):
        raise HTTPException(404, "Service not found")
    await repo.apply_patch(service_id, set_doc=upd)
    s = await repo.get_by_id(service_id)
    return {"success": True, "service": s}


@router.delete("/{service_id}", dependencies=[Depends(require_master_admin)])
async def admin_delete_service(service_id: str):
    """Soft delete: just mark inactive so historical invoices keep working."""
    repo = _repo()
    if not await repo.exists_by_id(service_id):
        raise HTTPException(404, "Service not found")
    await repo.soft_delete(
        service_id, at_iso=datetime.now(timezone.utc).isoformat(),
    )
    return {"success": True}
