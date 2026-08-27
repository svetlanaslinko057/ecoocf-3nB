"""
admin_workflow_templates — /api/admin/workflow-templates HTTP surface
=====================================================================

Wave 2B / Batch 10 / Commit 16 — auth-mixed yellow (2/2) — original
mechanical extraction from server.py:14328-14412.

**Phase 5.3 / C-1 — repository extraction (2026-05-18).**
This router is now a **pure HTTP-surface boundary**: it parses input,
validates HTTP-level shape, calls into `WorkflowTemplateRepository`
for every collection touch, and translates business-result booleans
into HTTP status codes.

────────────────────────────────────────────────────────────────────────
Ownership contract (per PHASE5_1_OWNERSHIP_MAP.md §7.1)
────────────────────────────────────────────────────────────────────────

  * `db.workflow_templates` is OWNED by `WorkflowTemplateRepository`.
  * This router is the SINGLE WRITER's HTTP surface (mutations).
  * The public read endpoint in `server.py` (line ~14427,
    `public_workflow_templates`) reads via the SAME repository —
    not via raw `db.workflow_templates.find(...)`.
  * No other module touches `db.workflow_templates` after Phase 5.3 / C-1.

────────────────────────────────────────────────────────────────────────
Auth-mixed yellow — same discipline as `admin_services` sibling
────────────────────────────────────────────────────────────────────────

  * GET    /api/admin/workflow-templates           → require_admin
  * POST   /api/admin/workflow-templates           → require_master_admin
  * PATCH  /api/admin/workflow-templates/{tpl_id}  → require_master_admin
  * DELETE /api/admin/workflow-templates/{tpl_id}  → require_master_admin

Per-endpoint `dependencies=[...]` preserved verbatim.  Redundant
`Depends(require_master_admin)` in POST signature preserved for
`created_by` attribution.

────────────────────────────────────────────────────────────────────────
Behavioural contract (every legacy quirk preserved 1:1)
────────────────────────────────────────────────────────────────────────

  * GET admin returns `{"success": True, "items": [...]}` — items
    sorted by `created_at` DESC, max 200.
  * First-hit seed (empty collection) inserts the 3 default templates
    and returns them in the same response (race preserved).
  * POST returns `{"success": True, "template": <new_doc>}`.
  * PATCH returns `{"success": True, "template": <updated_doc>}` or
    HTTP 404 if id not found.
  * DELETE returns `{"success": True}` or HTTP 404 (combined "not
    found OR is default" message preserved).
  * Steps normalisation drops items without `label` — still permissive
    (empty after normalisation is silently stored).

See `app/repositories/workflow_templates.py` for the detailed
behavioural contract of each repository method.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_admin, require_master_admin
from app.repositories.workflow_templates import WorkflowTemplateRepository


def _repo() -> WorkflowTemplateRepository:
    """Lazy repository factory.

    Phase 5.4 / C-4f — migrated from the legacy ``from server import db``
    lazy bridge to ``app.core.db_runtime.get_db()``. Object identity is
    preserved 1:1: the canonical ``server.db`` and ``get_db()`` reference
    the same Motor handle (pinned by the startup-time identity assertion
    in ``server.py`` and by ``tests/test_phase5_4_c4f_db_repo_batch2.py``).
    The ``_repo()`` wrapper, the ``WorkflowTemplateRepository`` constructor,
    and the endpoint signatures are byte-for-byte unchanged.

    The bridge import was the ONLY remaining ``from server import`` site
    in this module; ``db.workflow_templates.*`` direct calls were already
    removed at Phase 5.3 extraction time.
    """
    from app.core.db_runtime import get_db  # noqa: E402 (C-4f: lazy-bridge → accessor)
    return WorkflowTemplateRepository(get_db())


router = APIRouter(
    prefix="/api/admin/workflow-templates",
    tags=["admin-workflow-templates"],
)


# ── Workflow templates (reusable step recipes) ───────────────────────
@router.get("", dependencies=[Depends(require_admin)])
async def list_workflow_templates():
    """Admin listing — newest first; seeds defaults on first hit."""
    repo = _repo()
    items = await repo.list_templates(order="desc")
    # Legacy first-hit seed: if empty, seed and return the seed docs
    # (same race as legacy — two concurrent first-hits both seed).
    if not items:
        items = await repo.seed_default_templates()
    return {"success": True, "items": items}


@router.post("", dependencies=[Depends(require_master_admin)])
async def create_workflow_template(
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_master_admin),
):
    """Create a new (non-default) workflow template."""
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    steps = data.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise HTTPException(400, "steps must be a non-empty list")

    repo = _repo()
    doc = await repo.create_template(
        name=name,
        description=(data.get("description") or "").strip(),
        steps=steps,
        created_by=user.get("email") or user.get("id"),
    )
    return {"success": True, "template": doc}


@router.patch("/{tpl_id}", dependencies=[Depends(require_master_admin)])
async def update_workflow_template(tpl_id: str, data: Dict[str, Any] = Body(...)):
    """Patch name/description/steps of an existing template."""
    allowed = {"name", "description", "steps"}
    upd = {k: v for k, v in (data or {}).items() if k in allowed}
    if "steps" in upd:
        if not isinstance(upd["steps"], list) or not upd["steps"]:
            raise HTTPException(400, "steps must be a non-empty list")
    if not upd:
        raise HTTPException(400, "Nothing to update")

    repo = _repo()
    template = await repo.update_template(
        tpl_id,
        name=upd.get("name"),
        description=upd.get("description"),
        steps=upd.get("steps"),
    )
    if template is None:
        raise HTTPException(404, "Template not found")
    return {"success": True, "template": template}


@router.delete("/{tpl_id}", dependencies=[Depends(require_master_admin)])
async def delete_workflow_template(tpl_id: str):
    """Delete a NON-default template (Mongo-level default-protection)."""
    repo = _repo()
    deleted = await repo.delete_template(tpl_id)
    if not deleted:
        # Legacy combined message: id missing OR is_default==True
        raise HTTPException(
            404,
            "Template not found (or is default — defaults cannot be deleted)",
        )
    return {"success": True}
