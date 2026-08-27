"""
EmailTemplateRepository — Phase 5.3 / C-8.
==========================================

Canonical owner of the ``db.email_templates`` Mongo collection
— the editable per-(event, audience, lang) library of email
templates that drives every customer-facing and staff-facing
notification email in BIBI Cars. After this commit, every
mutation to that collection flows through this class.

Scope (per architect's C-8 mandate, 2026-05-18, post-C-7
reframing)
---------------------------------------------------------

This commit owns ONLY ``db.email_templates``.

C-8 lands under the **architect's reframing** recorded in
``PHASE5_MIDPOINT_ARCHITECTURE_NOTES.md §10``:

  > Repository ≠ pattern. Repository = ownership boundary.
  > Repositories are scaffolding for ownership reconstruction.
  > The real targets are runtime legibility, orchestration
  > visibility, side-effect formalization, bounded change
  > surfaces.

C-8 is the first commit in the notification-family cluster
(`email_templates` → `notification_rules` → `notifications` /
`email_outbox`). Each member of this cluster is extracted in
isolation per the boring-precision rhythm. The architectural
significance is not "another repository" but **one more piece
of the notification-domain ownership coming into view.**

**Inventory vs ownership map** (``PHASE5_1_OWNERSHIP_MAP.md
§1.3``):

| Map prediction (§1.3)                                                  | Inventory actual                                              |
|------------------------------------------------------------------------|---------------------------------------------------------------|
| ``email_templates`` — 10 ops, owner=notifications.py (clean!), 4 w, 0 readers | **7 raw Motor sites** (4 R + 3 W), **all in ``notifications.py``**, **0 external direct accessors** |

**Verdict: CONFIRMED** on collection ownership. Op-count
overshot by ~30% (map: 10, actual: 7) — counting-method
discrepancy, not falsification. Same pattern observed in C-7
(8 vs 4). The ownership column remains load-bearing and
correct across all 8 extractions.

Writer / reader contexts
-------------------------

::

  ┌──────────────────────────────────────────────────────────────┐
  │ Writer 1 — boot-time bulk seed (lifecycle)                    │
  │   notifications.NotificationService.seed_defaults             │
  │     • Gates on ``count_all() == 0`` → bulk inserts            │
  │       DEFAULT_TEMPLATES (a code-side constant of seeded       │
  │       per-event/audience/lang docs).                           │
  │     • Idempotent — never overwrites user edits.                │
  │     • Mirrors legacy lines 638 (gate) + 647 (insert_many).     │
  ├──────────────────────────────────────────────────────────────┤
  │ Writer 2 — admin runtime PATCH                                │
  │   notifications.update_email_template (router endpoint)       │
  │     • Driven by                                                │
  │       PATCH /api/admin/email-templates/{template_id}          │
  │       (require_master_admin guard)                            │
  │     • $set on whitelisted fields (subject, html,              │
  │       text_template, active) + updated_at stamp.              │
  │     • Mirrors legacy line 1048.                               │
  │     • Uses ``matched_count``-driven 404 idiom; C-8 replaces   │
  │       with ``exists_by_id`` guard (same pattern as C-5/C-6).  │
  ├──────────────────────────────────────────────────────────────┤
  │ Writer 3 — admin runtime POST (create-or-replace)             │
  │   notifications.create_email_template (router endpoint)       │
  │     • Driven by                                                │
  │       POST /api/admin/email-templates                         │
  │       (require_master_admin guard)                            │
  │     • $set on the FULL composed doc with ``upsert=True``.     │
  │     • The id is DETERMINISTICALLY DERIVED from                │
  │       (event, audience, lang) at the caller side, so a        │
  │       POST with the same triplet idempotently replaces the    │
  │       existing template — admin UI workflow expectation.     │
  │     • Mirrors legacy line 1079.                               │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 1 — boot-time existence gate                           │
  │   notifications.NotificationService.seed_defaults             │
  │     • ``count_all()`` (filter-less) at legacy line 638.       │
  │     • Same physical function as Writer 1; the gate is the     │
  │       same code path but a distinct reader CONTEXT.           │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 2 — runtime dispatch template lookup                   │
  │   notifications.NotificationService.get_template              │
  │     • Multi-key fetch by ``(event, audience, lang)``.         │
  │     • Called repeatedly in the language-fallback chain        │
  │       (norm → en → ua → bg). Returns the FIRST matching       │
  │       template, otherwise falls through to in-module code     │
  │       defaults (``DEFAULT_TEMPLATES``).                       │
  │     • Mirrors legacy line 673.                                │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 3 — admin list (filtered + sorted)                     │
  │   notifications.list_email_templates (router endpoint)        │
  │     • Driven by                                                │
  │       GET /api/admin/email-templates?event=&audience=&lang=   │
  │       (require_admin guard)                                   │
  │     • Optional 3-axis filter; sort by                          │
  │       (event asc, audience asc, lang asc); cap 500.           │
  │     • Mirrors legacy line 1035.                               │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 4 — admin re-read after PATCH                          │
  │   notifications.update_email_template (router endpoint)       │
  │     • Mirrors legacy line 1051 — re-fetches the doc by id     │
  │       after the $set lands, so the response carries the        │
  │       updated full shape.                                      │
  └──────────────────────────────────────────────────────────────┘

Net runtime topology: **single owner module**
(``notifications.py``), **3 writer contexts** (boot bulk seed +
admin PATCH + admin POST/upsert), **4 reader contexts** (boot
existence gate + runtime dispatch lookup + admin list + admin
re-read). All 7 sites live in the same file. Two caller
contexts inside that file: the ``NotificationService`` class
(which holds ``self.db``) and the router endpoints (which use a
lazy ``_db()`` resolver). C-8 wires both contexts through this
repository.

Adjacent findings
-----------------

**None on ``db.email_templates``.** The collection is a clean
Type A:

* No cross-domain WRITE pressure from outside ``notifications.py``.
* No cross-domain READ from outside ``notifications.py``.
* No cross-domain WRITE from ``notifications.py`` to other
  collections within the email_templates code paths (the
  ``get_template`` fallback uses in-module ``DEFAULT_TEMPLATES``
  constants, NOT another collection).
* No adjacent infrastructure leak (no ``ensure_indexes`` in
  ``notifications.py`` touches other collections — there are
  no Mongo index management calls in this module).

The ``notifications`` collection (a sibling in the
notification-family cluster) carries the documented drift
annotations from ``PHASE5_1_OWNERSHIP_MAP.md §1.3``
(``server.py 3 w — drift!``, ``calculations.py 1 w — drift!``).
**Those drifts are NOT on ``email_templates``** — they are on
``notifications`` and belong to a future commit (C-9 or C-10
target). C-8 deliberately does NOT touch them.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``count_all()``                       boot existence gate
                                            — filter-less count
                                            used as a 0-vs-nonzero
                                            sentinel by
                                            ``seed_defaults``.
    - ``find_for_dispatch(event, *,         runtime dispatch
        audience, lang)``                   lookup — exact 3-key
                                            match, ``_id``
                                            projected out.
                                            Returns ``dict`` or
                                            ``None``; the
                                            language-fallback
                                            chain lives at the
                                            caller side (this
                                            verb is the
                                            primitive, NOT the
                                            chain).
    - ``list_filtered(*, event,             admin list — all
        audience, lang)``                   three filters are
                                            optional (empty
                                            string treated as
                                            absent — legacy
                                            quirk). Sort by
                                            (event, audience,
                                            lang) ascending,
                                            cap 500. ``_id``
                                            projected out.
    - ``get_by_id(template_id)``            single fetch by
                                            ``id`` — used by
                                            admin PATCH for the
                                            after-write re-read.
                                            ``_id`` projected
                                            out.
    - ``exists_by_id(template_id) -> bool`` 404-guard idiom
                                            replacement (added
                                            in C-8 — same
                                            precedent as C-5
                                            and C-6). Light
                                            projection.

* Writes:
    - ``bulk_create(docs)``                 boot seed bulk
                                            insert — caller
                                            composes the list
                                            of complete docs;
                                            repo writes them
                                            via ``insert_many``.
                                            Mirrors legacy line
                                            647. Race window
                                            same as C-7 insert:
                                            preserved.
    - ``apply_patch(template_id, *,         admin PATCH —
        set_doc)``                          ``$set`` partial
                                            update on
                                            whitelisted fields
                                            composed at the
                                            caller side. Silent
                                            on not-found per
                                            ``update_one``
                                            semantics. Admin
                                            PATCH GATES on
                                            ``exists_by_id``
                                            before calling.
    - ``upsert_by_id(template_id, *,        admin POST —
        doc)``                              ``$set=doc`` with
                                            ``upsert=True``.
                                            Caller composes the
                                            full doc including
                                            the deterministically-
                                            derived id; repo
                                            writes the $set
                                            shape verbatim.
                                            Idempotent by id
                                            — re-POSTing the
                                            same
                                            (event, audience,
                                            lang) triplet
                                            replaces the
                                            existing template.

**8 named verbs.** Falls into the "standard-large" band of the
§6.3 morphology observation (5–9 verbs for collections with
multiple reader / writer contexts). Verb count proportional
to caller-context count, matching the C-5 / C-6 pattern.

Legacy behaviour preserved 1:1 (C-8 mandate)
--------------------------------------------

These quirks live in the legacy ``notifications.py`` sites and
are reproduced here verbatim. Changing any of them is OUT OF
SCOPE.

* **``id`` is the natural primary key.** Derived
  deterministically from
  ``"tpl_{event}_{audience}_{lang}"`` at the caller side
  (lines 642 and 1067 of the legacy code). The repository
  does NOT generate ids.
* **``_id`` IS projected out of all reads.** Legacy lines
  673, 1035, 1051 all use ``{"_id": 0}``. Preserved verbatim.
* **``find_for_dispatch`` returns the FIRST match.** Legacy
  semantics are "exact match on the 3-key tuple". The
  language-fallback chain (``norm → en → ua → bg``, and the
  legacy ``uk → ua`` alias) lives at the CALLER side
  (``NotificationService.get_template``) and is OUT OF SCOPE
  for the repository — it is dispatch orchestration, not
  collection ownership.
* **``list_filtered`` treats empty strings as absent filters.**
  Legacy lines 1031-1034 use ``if event:`` / ``if audience:``
  / ``if lang:`` (truthiness checks). Empty strings, ``None``,
  and missing arguments are all equivalent. Preserved.
* **``list_filtered`` sort order is ``[(event, 1),
  (audience, 1), (lang, 1)]``.** Legacy line 1035. Cap is
  ``to_list(length=500)``. Both preserved.
* **``apply_patch`` is silent on not-found.** Standard
  ``update_one`` semantics — the legacy admin PATCH endpoint
  surfaces 404 via the ``matched_count == 0`` idiom (line
  1049). C-8 migrates the legacy idiom to ``exists_by_id``
  guard BEFORE the patch (same precedent as C-5 and C-6).
* **``upsert_by_id`` writes the FULL doc shape via $set.**
  Legacy line 1079 does ``update_one({"id": tid}, {"$set":
  doc}, upsert=True)`` where ``doc`` is the freshly composed
  9-field shape (id, event, audience, lang, subject, html,
  text_template, active, created_at). Preserved verbatim.
  The repository accepts ``doc`` as-is; does NOT inject any
  field; does NOT validate the shape.
* **``bulk_create`` does no validation, no id check, no
  dedup.** Legacy line 647 calls ``insert_many(docs)`` on the
  list composed by the caller. The repository preserves this
  — duplicates, missing fields, malformed entries are the
  caller's responsibility. The collection has NO unique
  index on ``id`` in production (same pattern as C-7
  ``app_settings``).
* **Timestamps are ISO strings.** Legacy ``created_at`` and
  ``updated_at`` use
  ``datetime.now(timezone.utc).isoformat()`` (lines 644,
  1016, 1047, 1077). C-8 preserves this (matches C-5 / C-6
  ISO-string convention; differs from C-7 BSON-datetime
  convention — the legacy site dictates, NOT the
  repository).

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No hard-delete operation (no legacy delete site; YAGNI).
*  No HTTP exceptions — repository raises only on programmer
   error.
*  No DTO normalisation — accepts / returns dicts in the
   exact legacy shape.
*  No id generation / timestamp injection.
*  No language-fallback chain (lives in
   ``NotificationService.get_template``).
*  No event/audience/lang vocabulary validation (lives at the
   admin POST/PATCH endpoints — ``ALL_EVENTS`` / ``AUDIENCES``
   / ``LANGUAGES``).
*  No code-default fallback to ``DEFAULT_TEMPLATES`` (also
   lives in ``NotificationService.get_template``).
*  No bulk-deletion / bulk-update primitives.
*  No service-layer orchestration (notification dispatch
   pipeline lives in ``NotificationService.dispatch`` and
   stays there).
*  No touch on ``db.notification_rules``, ``db.notifications``,
   ``db.email_outbox`` (sibling collections in the
   notification family — each is a separate future commit).
*  No BaseRepository.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class EmailTemplateRepository:
    """Owner of ``db.email_templates`` (per-(event, audience, lang)
    notification template library).

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). Two caller contexts
    instantiate it ad-hoc: ``NotificationService`` (stored as
    ``self._templates_repo`` at service construction) and the
    router endpoints (constructed via the lazy ``_db()`` bridge).
    Both bridges dissolve in Phase 5.8 with DI.
    """

    COLLECTION = "email_templates"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def count_all(self) -> int:
        """Filter-less document count — boot existence sentinel.

        Mirrors legacy line 638 of ``notifications.py`` — used by
        ``seed_defaults`` to detect a fresh install (count == 0).
        """
        return await self._db[self.COLLECTION].count_documents({})

    async def find_for_dispatch(
        self,
        event: str,
        *,
        audience: str,
        lang: str,
    ) -> Optional[Dict[str, Any]]:
        """Exact 3-key lookup for runtime dispatch.

        Mirrors legacy line 673 of ``notifications.py``. Returns
        the first (and only — the 3-key tuple is the natural
        primary) matching template with ``_id`` projected out, or
        ``None`` if no match exists at this (event, audience,
        lang) triplet.

        The language-fallback chain (``norm → en → ua → bg``)
        lives at the CALLER side (``NotificationService.get_template``)
        and is intentionally NOT in the repository — it is
        dispatch orchestration, not collection ownership.
        """
        return await self._db[self.COLLECTION].find_one(
            {"event": event, "audience": audience, "lang": lang},
            {"_id": 0},
        )

    async def list_filtered(
        self,
        *,
        event: str = "",
        audience: str = "",
        lang: str = "",
    ) -> list[Dict[str, Any]]:
        """Admin list with optional 3-axis filter.

        Mirrors legacy lines 1031-1036 of ``notifications.py``.
        Empty-string filters are treated as absent (legacy
        truthiness quirk: ``if event:`` etc.). Sort by
        ``[(event, 1), (audience, 1), (lang, 1)]``. Cap
        ``to_list(length=500)``. ``_id`` projected out.
        """
        q: Dict[str, Any] = {}
        if event:
            q["event"] = event
        if audience:
            q["audience"] = audience
        if lang:
            q["lang"] = lang
        cursor = (
            self._db[self.COLLECTION]
            .find(q, {"_id": 0})
            .sort([("event", 1), ("audience", 1), ("lang", 1)])
        )
        return await cursor.to_list(length=500)

    async def get_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Single fetch by ``id`` — admin re-read after PATCH.

        Mirrors legacy line 1051. ``_id`` projected out.
        Returns ``None`` if no document matches.
        """
        return await self._db[self.COLLECTION].find_one(
            {"id": template_id}, {"_id": 0}
        )

    async def exists_by_id(self, template_id: str) -> bool:
        """Lightweight existence check.

        Replaces the legacy ``matched_count == 0`` 404-guard
        idiom (line 1049) with the same projection-light
        primitive introduced by C-5 and C-6. Projection
        ``{"id": 1}`` keeps the round-trip cheap.
        """
        doc = await self._db[self.COLLECTION].find_one(
            {"id": template_id}, {"id": 1}
        )
        return doc is not None

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def bulk_create(self, docs: list[Dict[str, Any]]) -> None:
        """Bulk insert via ``insert_many`` — boot seed only.

        Mirrors legacy line 647. The caller composes the full
        list of docs (with deterministic ids and ISO timestamps
        already in place). The repository writes them as-is —
        no validation, no id generation, no dedup, no race
        protection. Race window (concurrent boots) is preserved
        from legacy; mitigation is a unique index on ``id``
        which is an infra concern (Phase 5.4 / 5.5).

        Empty list is a no-op (matches the legacy ``if docs:``
        gate at line 646).
        """
        if not docs:
            return
        await self._db[self.COLLECTION].insert_many(docs)

    async def apply_patch(self, template_id: str, *, set_doc: Dict[str, Any]) -> None:
        """``$set`` partial update — admin PATCH.

        Mirrors legacy line 1048 of ``notifications.py``. Caller
        composes ``set_doc`` (typically the whitelisted
        ``subject`` / ``html`` / ``text_template`` / ``active``
        fields plus ``updated_at``). SILENT on not-found per
        ``update_one`` semantics — the admin PATCH endpoint
        guards with ``exists_by_id`` BEFORE calling.

        Same shape as ``InvoiceTemplateRepository.apply_patch``
        (C-5) and ``ServiceCatalogRepository.apply_patch``
        (C-6). Vocabulary stability confirmed by §6.3
        morphology review.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": template_id}, {"$set": set_doc}
        )

    async def upsert_by_id(self, template_id: str, *, doc: Dict[str, Any]) -> None:
        """``$set=doc`` with ``upsert=True`` — admin POST
        (create-or-replace).

        Mirrors legacy line 1079 of ``notifications.py``.
        Caller composes the full ``doc`` shape including the
        deterministically-derived ``id`` (``tpl_{event}_{audience}_{lang}``)
        and the ``created_at`` ISO timestamp. The repository
        writes the $set shape verbatim with ``upsert=True``.
        Idempotent by id — re-POSTing the same
        ``(event, audience, lang)`` triplet replaces the
        existing template under the same id.

        NOTE: this is distinct from ``apply_patch`` because of
        the ``upsert=True`` semantic. The admin POST endpoint
        relies on idempotent-replace behavior; the admin
        PATCH endpoint relies on must-exist behavior. Two
        verbs, two semantics.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": template_id}, {"$set": doc}, upsert=True
        )


__all__ = ["EmailTemplateRepository"]
