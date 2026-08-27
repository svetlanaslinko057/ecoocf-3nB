"""
admin_history_reports — /api/admin/history-reports/* HTTP surface
==================================================================

Wave 2B / Batch 2 / Commit 8 — original mechanical extraction.

**Phase 5.3 / C-2 — repository extraction (2026-05-18).**
This router is now a pure HTTP-surface boundary: it parses the
URL segment / path parameter, calls into ``HistoryReportRepository``
for every collection touch, and returns the legacy response shape.

Ownership contract (per PHASE5_1_OWNERSHIP_MAP.md §7.1)
--------------------------------------------------------

  * ``db.history_reports`` is OWNED by ``HistoryReportRepository``.
  * This router is the admin mutator's HTTP surface (approve / deny).
  * Customer-facing reads + submission live in ``server.py`` and
    use the SAME repository (see ``request_history_report`` and
    ``get_history_report`` near server.py:11184–11202).
  * No other module touches ``db.history_reports`` after Phase 5.3 / C-2.

What's preserved (legacy contract — all load-bearing)
-----------------------------------------------------

  * The two top-of-file stub endpoints (``/analytics``, ``/abuse-check/...``)
    return hard-coded responses — untouched by C-2.
  * ``/pending`` returns ``{"success": True, "data": [...]}``.
  * ``/approve/{id}`` and ``/deny/{id}`` return ``{"success": True}``
    UNCONDITIONALLY — they do NOT 404 on missing id (legacy quirk).
  * ``require_admin`` auth at router level — untouched.

What's NOT touched
------------------

  * no schema, no DTO
  * no audit-trail injection
  * no rate-limit changes
  * no validation of report_id format
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from security import require_admin  # noqa: E402
from app.repositories.history_reports import HistoryReportRepository


def _repo() -> HistoryReportRepository:
    """Lazy repository factory.

    Phase 5.4 / C-4f — migrated from the legacy ``from server import db``
    lazy bridge to ``app.core.db_runtime.get_db()``. Object identity is
    preserved 1:1: the canonical ``server.db`` and ``get_db()`` reference
    the same Motor handle (pinned by the startup-time identity assertion
    in ``server.py`` and by ``tests/test_phase5_4_c4f_db_repo_batch2.py``).
    The ``_repo()`` wrapper, the ``HistoryReportRepository`` constructor,
    and the endpoint signatures are byte-for-byte unchanged.
    """
    from app.core.db_runtime import get_db  # noqa: E402 (C-4f: lazy-bridge → accessor)
    return HistoryReportRepository(get_db())


router = APIRouter(
    prefix="/api/admin/history-reports",
    tags=["admin-history-reports"],
    dependencies=[Depends(require_admin)],
)


@router.get("/analytics")
async def history_reports_analytics():
    return {
        "totalReports": 100,
        "pendingReports": 5,
        "completedReports": 95,
    }


@router.post("/abuse-check/{report_id}")
async def history_reports_abuse_check(report_id: str):
    return {"success": True, "isAbuse": False}


@router.get("/pending")
async def history_reports_pending():
    """Pending history reports — admin moderation queue."""
    items = await _repo().list_pending(limit=50)
    return {"success": True, "data": items}


@router.post("/approve/{report_id}")
async def approve_history_report(report_id: str):
    """Approve history report. Silent on not-found (legacy quirk)."""
    await _repo().mark_approved(report_id)
    return {"success": True}


@router.post("/deny/{report_id}")
async def deny_history_report(report_id: str):
    """Deny history report. Silent on not-found (legacy quirk)."""
    await _repo().mark_denied(report_id)
    return {"success": True}
