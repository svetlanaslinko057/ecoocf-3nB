"""
HistoryReportRepository — Phase 5.3 / C-2.
==========================================

Canonical owner of the ``db.history_reports`` Mongo collection.
After this commit, every mutation to that collection flows through
this class. The router ``app/routers/admin_history_reports.py``
owns the admin HTTP surface; ``server.py`` retains the customer
HTTP surface (request submission + single-report fetch) and calls
into the SAME repository for collection access.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``list_pending(*, limit)``       admin moderation queue
    - ``get_report(report_id)``        customer single fetch by id

* Writes:
    - ``submit_request(*, vin)``       customer submits a new pending
                                       report (server-generated id +
                                       created_at)
    - ``mark_approved(report_id)``     admin approves a report
    - ``mark_denied(report_id)``       admin denies a report

Legacy behaviour preserved 1:1 (Phase 5.3 / C-2 mandate)
--------------------------------------------------------

These quirks live in the legacy router + server.py site and are
reproduced here verbatim. Changing any of them is OUT OF SCOPE
for this commit.

* **Id shape is ``report-<unix_timestamp_float>``** — not UUID.
  This is the legacy id format and changing it would break
  whatever consumer indexes / logs it. Generated server-side via
  ``datetime.now(timezone.utc).timestamp()``. Two concurrent
  submissions within the same microsecond MAY collide; legacy
  has this race and we do not fix it (Phase 6 hardening concern).
* **``vin`` is permissive.** Legacy stores whatever ``data.get("vin")``
  returns, including ``None``. We do not introduce input validation.
* **``mark_approved`` / ``mark_denied`` are SILENT on not-found.**
  Legacy issues ``update_one({"id": ...}, ...)`` and returns
  ``{"success": True}`` unconditionally — there is no 404 on missing
  report. The repository methods preserve this by returning ``None``
  (no boolean signal); the router does NOT translate matched_count
  into HTTP status.
* **``_id`` is projected out of every read.**
* **``list_pending`` uses BOTH cursor ``.limit(50)`` AND
  ``to_list(length=50)``** — redundant per Motor docs but matches
  legacy line 59-60 of ``admin_history_reports.py``. Preserved.
* **``status`` is a free-form string column.** Legacy writes
  ``"pending"`` / ``"approved"`` / ``"denied"``. No enum, no
  validation. We do not introduce one.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No HTTP exceptions — repository raises only on programmer error.
*  No DTO normalisation — returns dicts in the exact legacy shape.
*  No ``_id`` leak — every projection / pop matches legacy.
*  No BaseRepository (per architect mandate).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    """UTC now as ISO-8601 string (matches legacy)."""
    return datetime.now(timezone.utc).isoformat()


def _new_report_id() -> str:
    """Generate a new report id (`report-<unix_timestamp_float>`).

    Legacy shape: ``f"report-{datetime.now(timezone.utc).timestamp()}"``.
    Float-second precision. Not UUID. Do not change without an
    invariant update — consumer indexing / log-grep relies on it.
    """
    return f"report-{datetime.now(timezone.utc).timestamp()}"


class HistoryReportRepository:
    """Owner of ``db.history_reports``.

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). The router constructs per call
    via the Wave-1 lazy-bridge pattern; that bridge is the only
    remaining ``from server import db`` site in this surface and
    will dissolve in Phase 5.8 with DI.
    """

    COLLECTION = "history_reports"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_pending(self, *, limit: int = 50) -> list[dict]:
        """Return the admin moderation queue.

        Filters by ``status == "pending"``. ``_id`` is projected out.
        Legacy ``limit(50)`` is applied on the cursor; ``to_list``
        uses ``length=limit`` as the secondary safety bound.
        """
        cursor = (
            self._db[self.COLLECTION]
            .find({"status": "pending"}, {"_id": 0})
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def get_report(self, report_id: str) -> dict | None:
        """Fetch a single report by id, or ``None`` if not found.

        ``_id`` is projected out. Used by the customer-facing
        ``GET /api/history/report/{report_id}`` endpoint.
        """
        return await self._db[self.COLLECTION].find_one(
            {"id": report_id}, {"_id": 0}
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def submit_request(self, *, vin: str | None) -> dict:
        """Customer submits a new pending history report.

        Server-set fields: ``id`` (legacy ``report-<unix_ts_float>``
        shape), ``status="pending"``, ``created_at`` (ISO-8601).
        Caller-supplied: ``vin`` (permissive — may be ``None``).

        Returns the inserted document. The Mongo ``_id`` is popped
        before returning to mirror the legacy route behaviour
        (the route returned ``{"success": True, "reportId": report["id"]}``
        and did NOT expose the document to the caller; we return
        the doc here so future callers can inspect it without an
        extra round-trip — same approach as ``create_template``).
        """
        doc = {
            "id":         _new_report_id(),
            "vin":        vin,
            "status":     "pending",
            "created_at": _now_iso(),
        }
        await self._db[self.COLLECTION].insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def mark_approved(self, report_id: str) -> None:
        """Admin approves a report (``status="approved"``).

        SILENT on not-found per legacy contract (no boolean signal,
        no exception). If the caller needs to verify presence, it
        must call ``get_report`` first.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": report_id},
            {"$set": {"status": "approved"}},
        )

    async def mark_denied(self, report_id: str) -> None:
        """Admin denies a report (``status="denied"``).

        SILENT on not-found per legacy contract — same shape as
        ``mark_approved``.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": report_id},
            {"$set": {"status": "denied"}},
        )


__all__ = ["HistoryReportRepository"]
