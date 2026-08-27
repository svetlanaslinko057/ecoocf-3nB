"""
NotificationRuleRepository — Phase 5.3 / C-9.
=============================================

Canonical owner of the ``db.notification_rules`` Mongo
collection — the editable per-event mapping of audience and
channel targets that gates every notification dispatch in BIBI
Cars. After this commit, every mutation to that collection
flows through this class.

Scope (per architect's C-9 mandate, 2026-05-18, post-C-7
reframing)
---------------------------------------------------------

This commit owns ONLY ``db.notification_rules``.

C-9 is the **second commit in the notification-family
cluster** (C-8 was `email_templates`). It lands under the same
architect's reframing recorded in
``PHASE5_MIDPOINT_ARCHITECTURE_NOTES.md §10``: repositories are
scaffolding for ownership reconstruction. The architectural
significance is not "another repository" but **the second
piece of notification-domain ownership coming into view as a
coherent boundary**.

**Inventory vs ownership map** (``PHASE5_1_OWNERSHIP_MAP.md
§1.3``):

| Map prediction (§1.3)                                                | Inventory actual                                              |
|----------------------------------------------------------------------|---------------------------------------------------------------|
| ``notification_rules`` — 9 ops, owner=notifications.py (clean!), 3 w, 0 readers | **6 raw Motor sites** (4 R + 2 W), **all in ``notifications.py``**, **0 external direct accessors** |

**Verdict: CONFIRMED** on collection ownership. Op-count
overshot by ~1.5× (map: 9, actual: 6) — same count-method
discrepancy as C-7 (~2×) and C-8 (~1.4×). Writer count
overshot by 1 (map: 3, actual: 2 distinct write sites).
The ownership column remains load-bearing and correct across
all 9 extractions. The "owner correct, op-count loose"
pattern from C-7/C-8 holds in C-9.

Writer / reader contexts
-------------------------

::

  ┌──────────────────────────────────────────────────────────────┐
  │ Writer 1 — boot-time bulk seed (lifecycle)                    │
  │   notifications.NotificationService.seed_defaults             │
  │     • Gates on ``count_all() == 0`` → bulk inserts            │
  │       DEFAULT_RULES (a code-side constant — 6 default rules   │
  │       covering the legacy event vocabulary).                  │
  │     • Idempotent — never overwrites user edits.                │
  │     • Mirrors legacy lines 631 (gate) + 640 (insert_many).    │
  ├──────────────────────────────────────────────────────────────┤
  │ Writer 2 — admin runtime upsert by event                      │
  │   notifications.update_notification_rule (router endpoint)    │
  │     • Driven by                                                │
  │       PATCH /api/admin/notification-rules/{event}             │
  │       (require_master_admin guard)                            │
  │     • $set with ``upsert=True``; caller composes the          │
  │       full $set shape including the deterministic             │
  │       ``id = f"rule_{event}"`` and re-injects ``event``       │
  │       (so a fresh upsert-insert ends up with those fields).   │
  │     • Mirrors legacy lines 1022-1026.                         │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 1 — boot-time existence gate                           │
  │   notifications.NotificationService.seed_defaults             │
  │     • ``count_all()`` (filter-less) at legacy line 631.       │
  │     • Same physical function as Writer 1; distinct reader     │
  │       CONTEXT (the 0-vs-nonzero gate).                        │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 2 — runtime dispatch rule lookup                       │
  │   notifications.NotificationService.get_rule                  │
  │     • Single-key fetch by ``event``.                          │
  │     • Called by ``NotificationService.dispatch`` (line 741)   │
  │       to read ``rule.enabled`` and walk ``rule.targets[]``.   │
  │     • Falls back to ``DEFAULT_RULES`` code constants if the   │
  │       collection has no document for the event — fallback     │
  │       lives at the CALLER side, NOT in the repository.        │
  │     • Mirrors legacy line 656.                                │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 3 — admin list (sorted, defaults-merged)               │
  │   notifications.list_notification_rules (router endpoint)     │
  │     • Driven by                                                │
  │       GET /api/admin/notification-rules                       │
  │       (require_admin guard)                                   │
  │     • Sort by ``event`` ascending. No filters, no cap.        │
  │     • After the list comes back, the endpoint merges          │
  │       DEFAULT_RULES for any ALL_EVENTS not in the DB (each    │
  │       merged entry stamped ``missing_in_db: True``). The      │
  │       merge-with-defaults logic lives at the CALLER side,    │
  │       NOT in the repository.                                  │
  │     • Mirrors legacy line 990 (async-for cursor pattern,      │
  │       preserved in repo as ``to_list(length=None)``).         │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 4 — admin re-read after upsert                         │
  │   notifications.update_notification_rule (router endpoint)    │
  │     • Same primitive as Reader 2 (find_one by event), but     │
  │       a distinct context: re-read after Writer 2 completes,   │
  │       so the response carries the fresh shape.                │
  │     • Mirrors legacy line 1027.                               │
  └──────────────────────────────────────────────────────────────┘

Net runtime topology: **single owner module**
(``notifications.py``), **2 writer contexts** (boot bulk seed +
admin upsert-by-event), **4 reader contexts** (boot gate +
runtime dispatch lookup + admin list + admin re-read). All 6
sites live in the same file. Two caller contexts inside that
file: the ``NotificationService`` class (which holds ``self.db``)
and the router endpoints (which use the lazy ``_db()`` resolver).
C-9 wires both contexts through this repository.

Adjacent findings
-----------------

**None on ``db.notification_rules``.** Clean Type A — same
shape as C-8 / `email_templates`:

* No cross-domain WRITE pressure from outside ``notifications.py``.
* No cross-domain READ from outside ``notifications.py``.
* No cross-domain WRITE from ``notifications.py`` to other
  collections within the notification_rules code paths.
* No adjacent infrastructure leak.

The ``notifications`` collection — a sibling in this cluster —
carries the documented drift annotations
(``server.py 3 w — drift!``, ``calculations.py 1 w — drift!``)
per ``PHASE5_1_OWNERSHIP_MAP.md §1.3``. **Those drifts are NOT
on ``notification_rules``** — they are on ``notifications`` and
belong to C-10 (next commit in the family). C-9 deliberately
does NOT touch them.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``count_all()``                       boot existence gate
                                            — filter-less count
                                            used as a 0-vs-nonzero
                                            sentinel by
                                            ``seed_defaults``.
                                            Same name as C-6 and
                                            C-8 with identical
                                            semantics
                                            (vocabulary
                                            continuity per §6.3
                                            morphology audit).
    - ``find_by_event(event)``              single-key fetch by
                                            ``event``. Used both
                                            by runtime dispatch
                                            and by admin re-read
                                            (4-reader-context
                                            consolidation onto a
                                            single primitive
                                            because the lookup
                                            shape is identical
                                            in both).
                                            ``_id`` projected
                                            out.
    - ``list_all_sorted()``                 filter-less admin
                                            list. Sort by
                                            ``[(event, 1)]``.
                                            ``_id`` projected
                                            out. NO ``cap``
                                            argument because
                                            legacy used
                                            async-for iteration
                                            with no explicit
                                            limit (the
                                            collection holds at
                                            most ~|ALL_EVENTS|
                                            documents — order
                                            of 10s, not 1000s).
                                            The legacy
                                            no-limit behavior is
                                            preserved here as
                                            ``to_list(length=None)``.

* Writes:
    - ``bulk_create(docs)``                 boot seed bulk
                                            insert. Same name as
                                            C-8 with identical
                                            semantics (no
                                            validation, no id
                                            generation, no race
                                            protection, empty
                                            list = no-op).
                                            Mirrors legacy line
                                            640.
    - ``upsert_by_event(event, *,           admin upsert by
        set_doc)``                          event filter.
                                            ``$set=set_doc``
                                            with ``upsert=True``.
                                            Caller composes the
                                            full $set shape
                                            including the
                                            deterministic
                                            ``id = "rule_{event}"``
                                            and the re-injected
                                            ``event`` field (so
                                            an upsert-insert
                                            produces a doc with
                                            ``id`` and ``event``
                                            populated — Mongo
                                            normally fills
                                            filter fields from
                                            the filter, but the
                                            legacy quirk
                                            duplicates them in
                                            $set as a defensive
                                            shape, and C-9
                                            preserves this
                                            verbatim).

**5 named verbs.** Falls into the "standard" band of the §6.3
morphology observation (5 verbs for collections with 2 writer +
4 reader contexts consolidated onto 3 read primitives + 2 write
primitives). The verb-count-proportional-to-context-count rule
from §6.3 observation 1 continues to hold (8 verbs for 7
contexts in C-8, 5 verbs for 6 contexts in C-9 with
reader-shape consolidation).

Legacy behaviour preserved 1:1 (C-9 mandate)
--------------------------------------------

These quirks live in the legacy ``notifications.py`` sites and
are reproduced here verbatim.

* **``event`` is the natural primary key.** The lookup
  primitive is by ``event`` (NOT by ``id``). The ``id`` field
  is a deterministic derivation
  (``f"rule_{event}"``) composed at the caller side. The
  collection has NO unique index on ``event`` in production
  (same race-window pattern as C-7 / C-8 — preserved as
  Phase 5.4 / 5.5 infra concern).
* **``_id`` IS projected out of all reads.** Legacy lines
  656, 990, 1027 all use ``{"_id": 0}``. Preserved verbatim.
* **``find_by_event`` returns the FIRST (and only) match.**
  Legacy semantics: one document per event. No fallback to
  defaults inside the repository — the fallback chain lives
  at the CALLER side (``NotificationService.get_rule`` at
  legacy lines 657-663).
* **``list_all_sorted`` returns ALL documents, no cap.**
  Legacy line 990 uses ``async for r in cursor`` without any
  ``.limit()``. The collection is naturally bounded by
  ``|ALL_EVENTS|``. The defaults-merge logic for events not
  in the DB lives at the CALLER side (legacy lines 992-999).
* **``upsert_by_event`` accepts the full $set shape from
  the caller.** The legacy site composes
  ``{**upd, "event": event, "id": f"rule_{event}"}`` and
  passes it as the $set value. The repository writes it
  verbatim. The repository does NOT inject any field. The
  defensive duplication of filter fields inside $set
  (event, id) is a legacy quirk and is preserved.
* **``bulk_create`` does no validation, no id check, no
  dedup.** Same shape as C-8. Empty list = no-op (matches
  legacy ``if docs:`` guard at line 639). Race window
  (concurrent boots) preserved.
* **Timestamps are ISO strings.** Legacy uses
  ``datetime.now(timezone.utc).isoformat()`` (lines 637,
  1021). Matches C-5 / C-6 / C-8 convention. Differs from
  C-7 BSON-datetime convention — legacy dictates, NOT the
  repository.
* **No ``exists_by_event`` verb.** Unlike C-5 / C-6 / C-8
  (which use ``exists_by_*`` as a 404-guard), the legacy
  ``update_notification_rule`` endpoint uses
  ``upsert=True`` and therefore never needs a 404 guard —
  every PATCH either updates or creates. The
  ``exists_by_*`` primitive is intentionally absent from
  this repository. **Adding it would be premature: there is
  no legacy site that would call it.**

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No hard-delete operation (no legacy delete site).
*  No HTTP exceptions — repository raises only on programmer
   error.
*  No DTO normalisation.
*  No id generation (caller composes ``f"rule_{event}"``).
*  No timestamp injection (caller composes ISO string).
*  No default-rules fallback chain (lives in
   ``NotificationService.get_rule``).
*  No defaults-merge logic for missing events (lives in
   ``list_notification_rules`` router endpoint at legacy
   lines 992-999).
*  No event vocabulary validation (lives at the admin
   endpoint with ``ALL_EVENTS`` / ``AUDIENCES`` / ``CHANNELS``
   constants — legacy lines 1008, 1015, 1018).
*  No targets/audience/channels structural validation.
*  No dispatch-pipeline logic — ``NotificationService.dispatch``
   stays where it is.
*  No touch on ``db.email_templates``, ``db.notifications``,
   ``db.email_outbox``.
*  No service-layer extraction (notification dispatch
   orchestration stays in ``NotificationService``).
*  No exists_by_event verb (no legacy caller for it).
*  No BaseRepository.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class NotificationRuleRepository:
    """Owner of ``db.notification_rules`` (per-event notification
    dispatch rule store).

    Two caller contexts instantiate the repository ad-hoc:
    ``NotificationService`` (stored as ``self._rules_repo`` at
    service construction) and the router endpoints (constructed
    via the lazy ``_db()`` bridge). Both bridges dissolve in
    Phase 5.8 with DI.
    """

    COLLECTION = "notification_rules"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def count_all(self) -> int:
        """Filter-less document count — boot existence sentinel.

        Mirrors legacy line 631 of ``notifications.py`` — used by
        ``seed_defaults`` to detect a fresh install (count == 0).
        Same name and semantics as
        ``ServiceCatalogRepository.count_all`` (C-6) and
        ``EmailTemplateRepository.count_all`` (C-8) — vocabulary
        continuity per §6.3 morphology audit.
        """
        return await self._db[self.COLLECTION].count_documents({})

    async def find_by_event(self, event: str) -> Optional[Dict[str, Any]]:
        """Single-key fetch by ``event``.

        Mirrors legacy lines 656 (runtime dispatch lookup) and
        1027 (admin re-read after upsert) of ``notifications.py``.
        Returns the document with ``_id`` projected out, or
        ``None`` if no rule exists for the event.

        The default-rules fallback chain
        (``DEFAULT_RULES`` constant lookup) lives at the CALLER
        side (``NotificationService.get_rule``) and is
        intentionally NOT in the repository — it is dispatch
        orchestration, not collection ownership.
        """
        return await self._db[self.COLLECTION].find_one(
            {"event": event}, {"_id": 0}
        )

    async def list_all_sorted(self) -> list[Dict[str, Any]]:
        """Filter-less admin list with ``[(event, 1)]`` sort.

        Mirrors legacy line 990 of ``notifications.py``. No cap
        — the collection is naturally bounded by
        ``|ALL_EVENTS|`` and the legacy endpoint never set
        ``.limit()``. ``_id`` projected out.

        The defaults-merge logic for events not present in the
        DB lives at the CALLER side (legacy lines 992-999) and
        is intentionally NOT in the repository — it is admin-UI
        orchestration that composes the response shape
        (``missing_in_db: True`` stamping etc.), not collection
        ownership.
        """
        cursor = (
            self._db[self.COLLECTION]
            .find({}, {"_id": 0})
            .sort([("event", 1)])
        )
        return await cursor.to_list(length=None)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def bulk_create(self, docs: list[Dict[str, Any]]) -> None:
        """Bulk insert via ``insert_many`` — boot seed only.

        Mirrors legacy line 640. Same name and semantics as
        ``EmailTemplateRepository.bulk_create`` (C-8) —
        vocabulary continuity per §6.3 morphology audit. Empty
        list = no-op (preserves the legacy ``if docs:`` gate at
        line 639). No id generation, no validation, no dedup, no
        race protection. Race window (concurrent boots)
        preserved from legacy; mitigation is a unique index on
        ``event`` which is an infra concern (Phase 5.4 / 5.5).
        """
        if not docs:
            return
        await self._db[self.COLLECTION].insert_many(docs)

    async def upsert_by_event(
        self, event: str, *, set_doc: Dict[str, Any]
    ) -> None:
        """``$set=set_doc`` with ``upsert=True`` — admin upsert by event.

        Mirrors legacy lines 1022-1026 of ``notifications.py``.
        Caller composes the full ``$set`` shape, which by
        legacy convention includes the deterministic
        ``id = f"rule_{event}"`` and the re-injected
        ``event`` field (defensive duplication so an
        upsert-insert produces a doc with these fields
        populated even when Mongo's filter-fill is partial).

        The repository writes the ``$set`` shape verbatim;
        does NOT inject any field; does NOT validate.

        Distinct from ``apply_patch`` of C-5/C-6/C-8 because:
        * the filter is by ``event`` (NOT by ``id``);
        * ``upsert=True`` semantic;
        * the caller's $set shape contains the filter field
          duplicated (which ``apply_patch`` callers do NOT
          do — they assume the doc exists).
        """
        await self._db[self.COLLECTION].update_one(
            {"event": event}, {"$set": set_doc}, upsert=True
        )


__all__ = ["NotificationRuleRepository"]
