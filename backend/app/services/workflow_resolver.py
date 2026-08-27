"""
Workflow Resolver — Phase Final / Block 1 (Workflow Binding).
================================================================

Single source of truth for resolving the workflow step list of a service
at invoice-creation time.

Resolution priority (top-down):
  1. ``service.workflow_template_id`` is set AND template exists →
     return ``template.steps`` (LIVE link — editing template propagates).
  2. ``service.workflow`` is a non-empty inline list →
     return it verbatim (legacy embedded snapshot).
  3. Final fallback → canonical 3-step default ("Pending / In progress
     / Completed").

The resolver intentionally returns the **raw step list as stored** —
no normalisation, no field stripping — so the existing
``_build_order_steps_from_invoice`` consumer in ``app.services.orders``
keeps working byte-for-byte.

Why a separate module
---------------------
``app.services.orders`` already consumes ``invoice.items[*].workflow``.
The binding happens **at invoice creation time** (manager builder in
``server.py``) and at any other site that creates invoice items.
Centralising the resolution here keeps the binding rule in one place
and lets us swap the rule later (e.g. cache, add tenancy) without
touching call sites.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.workflow_resolver")

DEFAULT_STEPS: List[Dict[str, Any]] = [
    {"key": "pending",     "label": "Очікує",   "label_en": "Pending",     "label_bg": "Изчакване"},
    {"key": "in_progress", "label": "В роботі", "label_en": "In progress", "label_bg": "В процес"},
    {"key": "completed",   "label": "Готово",   "label_en": "Completed",   "label_bg": "Завършено"},
]


async def resolve_workflow_for_service(
    service: Optional[Dict[str, Any]],
    db: Any,
) -> List[Dict[str, Any]]:
    """Return the canonical workflow step list for a given service doc.

    Args:
        service: The service catalog document (may be ``None`` for free
            line items without a service binding).
        db: Motor handle used to look up the template when
            ``workflow_template_id`` is set.

    Returns:
        A list of step dicts (always a copy — callers may mutate freely).
    """
    if not service:
        return [dict(s) for s in DEFAULT_STEPS]

    tpl_id = service.get("workflow_template_id") or service.get("workflowTemplateId")
    if tpl_id:
        try:
            tpl = await db.workflow_templates.find_one(
                {"id": tpl_id},
                {"_id": 0, "steps": 1},
            )
            if tpl and isinstance(tpl.get("steps"), list) and tpl["steps"]:
                return [dict(s) for s in tpl["steps"]]
            logger.warning(
                "[workflow_resolver] template_id=%s not found or has no steps; "
                "falling back to inline workflow for service id=%s",
                tpl_id, service.get("id"),
            )
        except Exception:
            logger.exception(
                "[workflow_resolver] template lookup failed (template_id=%s); "
                "falling back to inline workflow",
                tpl_id,
            )

    inline = service.get("workflow")
    if isinstance(inline, list) and inline:
        return [dict(s) for s in inline]

    return [dict(s) for s in DEFAULT_STEPS]


def resolve_workflow_sync_from_template(
    template: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Sync helper for tests and one-shot scripts that already loaded
    a template document. Returns a copy of ``template.steps`` or the
    default fallback if the template is empty.
    """
    if template and isinstance(template.get("steps"), list) and template["steps"]:
        return [dict(s) for s in template["steps"]]
    return [dict(s) for s in DEFAULT_STEPS]


__all__ = [
    "DEFAULT_STEPS",
    "resolve_workflow_for_service",
    "resolve_workflow_sync_from_template",
]
