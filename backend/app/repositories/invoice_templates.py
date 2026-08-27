"""
InvoiceTemplateRepository — Phase 5.3 / C-5.
============================================

Canonical owner of the ``db.invoice_templates`` Mongo collection.
After this commit, every mutation to that collection flows
through this class. The owner module ``financial_breakdown.py``
owns the admin HTTP surface (admin CRUD + preview), the breakdown
engine itself, and the index management. The ``legal_workflow.py``
module is a read-only consumer (one site — see §"Cross-domain
reads" below).

Scope (per architect's C-5 mandate, 2026-05-18 part 5)
------------------------------------------------------

This commit owns ONLY ``db.invoice_templates``. The
``ensure_indexes(db)`` module-level helper in `financial_breakdown.py`
ALSO creates indexes on ``db.invoices`` — a different collection
that belongs to **BillingDomain** (Phase 5.7 per the ownership
map §1.1). Those index calls REMAIN in `financial_breakdown.py`
and are NOT migrated in C-5. The repository owns
``invoice_templates`` indexing; ``invoices`` indexing is left as
a Phase 5.7 entry point.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``list_filtered(*, kind, active)``        admin list with
                                                optional kind +
                                                active filters,
                                                sorted by ``kind``
                                                asc, cap 200
    - ``get_by_id(tpl_id)``                     single fetch with
                                                ``_id`` projected
                                                out; ``None`` on
                                                miss
    - ``get_current(tpl_id)``                   single fetch with
                                                NO projection
                                                (legacy quirk —
                                                used by patch path
                                                to read ``version``)
    - ``exists_by_id(tpl_id) -> bool``          lightweight
                                                existence check
                                                using ``{"id": 1}``
                                                projection
    - ``get_active_by_id(tpl_id)``              fetch active
                                                template by id;
                                                ``_id`` projected
                                                out; ``None`` if
                                                not found OR not
                                                active
    - ``get_active_by_kind(kind)``              first active
                                                template of given
                                                kind; ``_id``
                                                projected out;
                                                ``None`` on miss

* Writes:
    - ``create(doc)``                           insert a freshly
                                                composed template
                                                doc as-is (caller
                                                supplies the full
                                                shape including
                                                ``id``, ``version``,
                                                ``created_at``,
                                                ``updated_at``)
    - ``apply_patch(tpl_id, *, set_doc)``       ``$set`` partial
                                                update; caller
                                                pre-composes the
                                                set-doc including
                                                ``updated_at`` and
                                                ``version`` bump
    - ``soft_delete(tpl_id, *, deleted_by_id,   set ``active=False``
                    at_iso)``                   plus ``deleted_by``
                                                + ``deleted_at`` +
                                                ``updated_at``
                                                stamps (NO doc
                                                removal — soft
                                                delete by design)

* Infrastructure:
    - ``ensure_indexes()``                      create the two
                                                ``invoice_templates``
                                                indexes (unique on
                                                ``id`` + compound
                                                on ``kind+active``)

Legacy behaviour preserved 1:1 (C-5 mandate)
--------------------------------------------

These quirks live in the legacy
`financial_breakdown.py` + `legal_workflow.py` sites and are
reproduced here verbatim. Changing any of them is OUT OF SCOPE.

* **``id`` is the natural primary key** (a server-generated
  string like ``tpl_after_win_<hex8>`` or one of the two seeded
  ``tpl_after_win_default`` / ``tpl_final_default``). Mongo
  ``_id`` is auto-allocated but never used as the application
  identifier. Every business read filters by the application
  ``"id"`` field.
* **``_id`` is projected out of most reads** — except
  ``get_current`` (legacy line 440 of `financial_breakdown.py`
  has no projection and was relied on by the patch path to
  read ``version``). ``get_current`` returns the raw doc
  including ``_id``.
* **``exists_by_id`` returns a bool, not the doc.** Legacy uses
  the projection ``{"id": 1}`` and only treats the value as
  truthy. We expose a typed boolean so callers cannot
  accidentally rely on the (mostly empty) projected shape.
  Two legacy sites used this idiom (L405 creation guard,
  L473 delete guard — the L473 projection also included
  ``"active": 1`` but the caller never read ``active``;
  consolidating both into `exists_by_id` matches semantics
  exactly).
* **``list_filtered`` uses cursor ``.sort("kind", 1).to_list(200)``
  cap.** Legacy line 384-385. Preserved.
* **``get_active_by_id`` filters on BOTH ``id`` and
  ``active: True``** — a missing OR soft-deleted template
  returns ``None``. Legacy line 565.
* **``get_active_by_kind`` returns the FIRST active template
  of a given kind** (Mongo's natural ``find_one`` semantics —
  no sort order specified). If multiple active templates of
  the same kind exist (which the unique-id index does not
  prevent), behaviour is unspecified. This is a known legacy
  property; we do NOT fix it in C-5.
* **``apply_patch`` does NOT touch ``updated_at`` itself.** The
  caller is responsible for setting ``updated_at`` in the
  set-doc (legacy line 444 sets it before calling). The
  repository persists what the caller passes.
* **``soft_delete`` sets exactly 4 fields**: ``active=False``,
  ``updated_at``, ``deleted_by``, ``deleted_at``. It does NOT
  remove the document, does NOT touch ``version``, does NOT
  touch other fields. Legacy lines 477-482.
* **``create`` accepts the caller-composed doc as-is** — no
  ID generation, no version stamping, no timestamp injection.
  All shape concerns live in the router (admin CRUD path) or
  the seeder (`seed_default_templates`). Legacy lines 422 +
  793 both pass a fully-formed dict.
* **``ensure_indexes`` is silent on failure** — legacy
  line 805-807 swallows Mongo errors via a try/except. The
  repository preserves this (an index already present, a
  conflicting historical index, etc. should not crash startup).

Cross-domain reads (acceptable per Phase 5.1 §7.1)
--------------------------------------------------

| Site | Owner module | Method called |
|------|--------------|---------------|
| `legal_workflow.py` L1594 | LegalDomain | `get_active_by_kind("after_win")` |

This is a clean READ across domains and is permitted by the
single-writer rule (which restricts WRITES, not READS).
LegalDomain consumes the active "after_win" template to compose
the auction-won breakdown — exactly the read-projection pattern
the ownership map prescribes for Type B / shared read-model
collections.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No hard-delete operation — soft delete is the contract.
*  No HTTP exceptions — repository raises only on programmer error.
*  No DTO normalisation — accepts / returns dicts in the exact
   legacy shape.
*  No id generation, no timestamp injection — caller composes.
*  No version increment — caller does it (legacy quirk).
*  No touch on `db.invoices` (Phase 5.7 / BillingDomain).
*  No breakdown engine logic (`_compute_items_and_totals`,
   `BREAKDOWN_KINDS`, etc.) — that stays in
   `financial_breakdown.py`.
*  No BaseRepository (per architect mandate).
"""
from __future__ import annotations

from typing import Any, Optional


class InvoiceTemplateRepository:
    """Owner of ``db.invoice_templates``.

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). Callers construct one ad-hoc
    via the Wave-1 lazy-bridge pattern (`InvoiceTemplateRepository(_db())`)
    or are passed an explicit ``db`` (the seeder path) — both
    routes converge on this class. The bridge dissolves in
    Phase 5.8 with DI.
    """

    COLLECTION = "invoice_templates"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_filtered(
        self,
        *,
        kind: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[dict]:
        """Admin list with optional kind / active filters.

        Mirrors legacy lines 377-385: builds a Mongo query from
        the two optional fields (kind validation happens at the
        router layer — the repository accepts whatever string),
        sorts by ``kind`` ascending, caps at ``to_list(length=200)``.
        ``_id`` is projected out.
        """
        q: dict[str, Any] = {}
        if kind is not None:
            q["kind"] = kind
        if active is not None:
            q["active"] = bool(active)
        cursor = self._db[self.COLLECTION].find(q, {"_id": 0}).sort("kind", 1)
        return await cursor.to_list(length=200)

    async def get_by_id(self, tpl_id: str) -> Optional[dict]:
        """Fetch a single template by id with ``_id`` projected out.

        Used by: admin GET (L392), admin PATCH re-read after
        update (L456), preview path (L500). Returns ``None`` on
        miss (callers map this to HTTP 404).
        """
        return await self._db[self.COLLECTION].find_one(
            {"id": tpl_id}, {"_id": 0}
        )

    async def get_current(self, tpl_id: str) -> Optional[dict]:
        """Fetch a single template by id WITHOUT projection.

        Legacy quirk: line 440 of `financial_breakdown.py` has no
        projection — used by the patch path which needs the
        current ``version`` to compute the next one. The ``_id``
        is carried through but the caller never reads it.
        Preserved verbatim.
        """
        return await self._db[self.COLLECTION].find_one({"id": tpl_id})

    async def exists_by_id(self, tpl_id: str) -> bool:
        """Lightweight existence check.

        Mirrors legacy lines 405 (creation guard) and 473
        (delete guard). The L473 projection also includes
        ``"active": 1`` but the caller never reads the value —
        only the truthiness of the result. Consolidating both
        into a typed bool return matches the actual semantics.
        """
        doc = await self._db[self.COLLECTION].find_one(
            {"id": tpl_id}, {"id": 1}
        )
        return doc is not None

    async def get_active_by_id(self, tpl_id: str) -> Optional[dict]:
        """Fetch the template by id only if it is active.

        Returns ``None`` if not found OR not active. Used by the
        final-breakdown resolution path (L565) where an inactive
        or missing template must surface as a 404 to the caller.
        ``_id`` projected out.
        """
        return await self._db[self.COLLECTION].find_one(
            {"id": tpl_id, "active": True}, {"_id": 0}
        )

    async def get_active_by_kind(self, kind: str) -> Optional[dict]:
        """Fetch the first active template of the given kind.

        Used by: final-breakdown fallback (L571 — kind="final"),
        and `legal_workflow.py` auction_won path (L1594 —
        kind="after_win"). Mongo's natural ``find_one`` order —
        no sort specified. Multiple active templates of the same
        kind is an unspecified state preserved from legacy.
        ``_id`` projected out.
        """
        return await self._db[self.COLLECTION].find_one(
            {"kind": kind, "active": True}, {"_id": 0}
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def create(self, doc: dict) -> None:
        """Insert a fully composed template document.

        Mirrors legacy lines 422 (admin POST path) and 793
        (seeder path). Both pass an already-built dict containing
        ``id``, ``name``, ``kind``, ``items``, ``active``,
        ``notes``, ``version``, ``created_by``, ``created_at``,
        ``updated_at``. The repository does NOT generate id, does
        NOT inject timestamps, does NOT validate the shape — all
        of that lives at the caller side (router or seeder).
        """
        await self._db[self.COLLECTION].insert_one(doc)

    async def apply_patch(self, tpl_id: str, *, set_doc: dict) -> None:
        """Apply a ``$set`` partial update.

        Mirrors legacy line 455. Caller composes ``set_doc``
        including ``updated_at`` and (when ``items`` changed) the
        bumped ``version``. The repository persists the set-doc
        as-is. SILENT on not-found per ``update_one`` semantics —
        the caller guards via ``get_current`` before calling.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": tpl_id}, {"$set": set_doc}
        )

    async def soft_delete(
        self,
        tpl_id: str,
        *,
        deleted_by_id: str,
        at_iso: str,
    ) -> None:
        """Soft-delete: mark ``active=False`` + stamp audit fields.

        Mirrors legacy lines 477-482. Exactly four fields are
        set:

            * ``active``        ``False``
            * ``updated_at``    caller-supplied ISO string
            * ``deleted_by``    caller-supplied id (admin email)
            * ``deleted_at``    caller-supplied ISO string

        Does NOT remove the document. Does NOT touch ``version``.
        Does NOT touch other fields. Existing breakdowns that
        snapshotted this template are unaffected (they keep
        their own copy).
        """
        await self._db[self.COLLECTION].update_one(
            {"id": tpl_id},
            {"$set": {
                "active":     False,
                "updated_at": at_iso,
                "deleted_by": deleted_by_id,
                "deleted_at": at_iso,
            }},
        )

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Create the two ``invoice_templates`` indexes.

        Mirrors legacy lines 801-802:
            * unique index on ``id``
            * compound index on ``(kind, active)``

        Silent on failure per legacy line 805-807 — index
        conflicts at boot must not crash startup. The
        ``invoices`` indexes (legacy lines 803-804) are NOT
        managed here — they belong to BillingDomain (Phase 5.7).
        """
        try:
            await self._db[self.COLLECTION].create_index(
                [("id", 1)], unique=True,
            )
            await self._db[self.COLLECTION].create_index(
                [("kind", 1), ("active", 1)],
            )
        except Exception:
            import logging as _lg
            _lg.getLogger("bibi.financial").warning(
                "invoice_templates index creation failed",
                exc_info=True,
            )


__all__ = ["InvoiceTemplateRepository"]
