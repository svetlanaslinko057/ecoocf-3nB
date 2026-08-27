"""
ServiceCatalogRepository — Phase 5.3 / C-6.
===========================================

Canonical owner of the ``db.services`` Mongo collection (BIBI
service catalog — managed list of orderable line-items such as
"inspection", "delivery to Rotterdam", "checked_in workflow"
etc.). After this commit, every mutation to that collection
flows through this class.

Scope (per architect's C-6 mandate, 2026-05-18 part 6)
------------------------------------------------------

This commit owns ONLY ``db.services``. **A hidden coupling was
found** during inventory: the ownership map §1.3 listed
`services` as a "clean Type A — 5 writes in admin_services.py,
zero readers". The actual production state at C-6 inventory
shows:

| Owner module / function                       | Sites | Type |
|-----------------------------------------------|------:|------|
| `app/routers/admin_services.py` (admin CRUD)  | 5     | 3 W + 2 R |
| `server.py:_ensure_services_seed()` (seed)    | 4     | 2 W + 2 R |
| `server.py:list_services_public()`            | 1     | 1 R       |
| `server.py:manager_create_invoice()`          | 1     | 1 R       |

Total: **3 distinct writers** (admin CRUD, startup seed, startup
backfill) and **3 reader contexts** (admin list, public list,
invoice line-item resolution). This is a **multi-writer
collection** in the legacy state — NOT the clean Type-A the
ownership map predicted.

The C-6 resolution (per architect mandate "expose, document,
freeze, do not solve prematurely"):

* ALL 11 production sites route through THIS repository →
  the single-writer rule per §7.1 is restored at the Mongo
  driver level (every mutation goes through one class even
  if three caller-contexts use it).
* The `_ensure_services_seed()` helper REMAINS in `server.py`
  as a lifespan hook (its orchestration responsibility — boot
  ordering, retry semantics, log line — is server-level, not
  collection-level).
* The `list_services_public()` endpoint REMAINS in `server.py`
  (the public/staff list of services is a transport concern;
  collection ownership has been satisfied).
* The `manager_create_invoice()` function REMAINS in
  `server.py` (it composes a cross-domain workflow:
  customers + services + invoices; collection ownership of
  services is satisfied by routing through the repository).

The architectural follow-up (NOT done in C-6) is a future
"service-lookup orchestration" extraction (Phase 5.6+) where
the three reader contexts collapse into one service surface.
That work would be a SERVICE-layer extraction, not a
repository extraction, and the architect's mandate is explicit
about NOT introducing service layers prematurely.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``count_all()``                       seed existence check
                                            (boot path)
    - ``list_by_name(*, category,           public/staff list —
                     active_only)``         optional ``is_active``
                                            and ``category``
                                            filters, sort by
                                            ``name`` asc, cap 200
    - ``list_all()``                        admin list — no
                                            filter, sort by
                                            ``created_at`` desc,
                                            cap 500
    - ``get_by_id(service_id)``             single fetch with
                                            ``_id`` projected out
    - ``find_by_ids(service_ids)``          batch fetch by id
                                            (manager invoice
                                            builder)
    - ``list_seed_managed(seed_ids)``       seed-reconciliation
                                            read — NO ``_id``
                                            projection (legacy
                                            quirk preserved —
                                            seed loop iterates
                                            full docs)

* Writes:
    - ``create(doc)``                       ``insert_one`` —
                                            seeder + admin POST
    - ``apply_patch(service_id, *,          ``$set`` partial
                    set_doc)``              update — admin PATCH
                                            + seed translation
                                            backfill
    - ``soft_delete(service_id, *, at_iso)``mark ``is_active=False``
                                            + stamp ``deleted_at``
                                            (admin DELETE)

Legacy behaviour preserved 1:1 (C-6 mandate)
--------------------------------------------

These quirks live in the legacy `admin_services.py` and
`server.py` sites and are reproduced here verbatim. Changing
any of them is OUT OF SCOPE.

* **``id`` is the natural primary key.** Mongo `_id` is
  auto-allocated but never used as the application identifier
  in any of the 11 sites.
* **``_id`` is projected out of MOST reads.** Exception:
  ``list_seed_managed`` — legacy line 14366 of `server.py`
  has no projection and the seed loop iterates the raw cursor
  doc (it accesses ``doc["id"]`` and ``doc["workflow"]`` but
  never ``_id``; the projection-omission is a legacy quirk).
* **``list_by_name`` caps at ``to_list(length=200)``** — legacy
  line 14419. Sort is by ``name`` ascending. Both
  ``active_only=True`` (production) and ``active_only=False``
  (no production caller but contract retained) branches route
  through this verb.
* **``list_all`` caps at ``to_list(length=500)``** — legacy
  line 111-112 of `admin_services.py`. Sort is by
  ``created_at`` descending.
* **``find_by_ids`` returns a list (not a dict).** Legacy
  line 14489 builds a dict at the caller side via
  ``services_index[s["id"]] = s``; we return a list and let
  the caller index it. This matches the
  ``InvoiceTemplateRepository`` precedent (caller composes
  whatever shape it needs from the list).
* **``count_all`` accepts no filter.** Legacy line 14357 calls
  ``count_documents({})`` — the seeder uses 0 as the
  "fresh-install" sentinel.
* **``create`` accepts the caller-composed doc as-is** — no
  id generation, no timestamp injection, no validation. Both
  the seeder path (line 14362) and the admin POST path
  (line 143) compose the full dict at the caller side.
* **``apply_patch`` is silent on not-found** per ``update_one``
  semantics. Admin PATCH guards with an existence check; the
  seed backfill loop reads first via ``list_seed_managed``
  and only patches rows that were returned by the cursor.
* **``soft_delete`` sets EXACTLY two fields**: ``is_active=False``
  and ``deleted_at``. Legacy line 167. Does NOT touch other
  fields, does NOT remove the doc.

Hidden coupling exposed (C-6 SIGNATURE)
---------------------------------------

The collection was predicted to be clean Type A. Inventory
showed THREE writer contexts. The architect's mandate is to
EXPOSE this signature, not solve it. This commit:

* Restores the §7.1 single-writer rule by routing all three
  writer contexts through THIS class.
* Documents the THREE writer contexts in the repository
  module docstring (this section + §"Scope" above).
* Leaves the THREE reader contexts at their original sites
  with their original orchestration responsibilities.
* Flags the future SERVICE-layer extraction as Phase 5.6+
  work — explicitly NOT C-6 scope.

Cross-domain READS still acceptable per §7.1
--------------------------------------------

* `manager_create_invoice()` in `server.py` reads the catalog
  to attach service metadata to invoice line-items. This is a
  cross-domain READ from BillingDomain → ServiceCatalog. Per
  §7.1 it is permitted; routed through the repository as a
  read-projection.
* The public `/api/services` endpoint is a transport read —
  not a domain crossing. Stays in `server.py` as a thin
  delegate to the repository.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No hard-delete (soft delete is the contract).
*  No HTTP exceptions — repository raises only on programmer error.
*  No DTO normalisation — accepts / returns dicts in the exact
   legacy shape.
*  No id generation / timestamp injection.
*  No workflow-step validation (the engine that consumes
   ``workflow[]`` lives outside this collection's concern).
*  No translation backfill logic — the diff-computation lives
   in the seeder caller; the repository persists the set-doc.
*  No service-layer orchestration (Phase 5.6+).
*  No touch on `db.invoices`, `db.customers`, `db.deals`.
*  No BaseRepository.
"""
from __future__ import annotations

from typing import Any, Optional


class ServiceCatalogRepository:
    """Owner of ``db.services`` (the BIBI service catalog).

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). Three caller contexts
    instantiate it ad-hoc via the Wave-1 lazy-bridge pattern.
    The bridge dissolves in Phase 5.8 with DI.
    """

    COLLECTION = "services"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def count_all(self) -> int:
        """Return total document count (filter-less).

        Mirrors legacy line 14357 of `server.py` — used by
        ``_ensure_services_seed`` to detect a fresh install
        (count == 0). Preserved verbatim.
        """
        return await self._db[self.COLLECTION].count_documents({})

    async def list_by_name(
        self,
        *,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict]:
        """Public / staff list — public endpoint contract.

        Mirrors legacy lines 14411-14420 of `server.py`. Builds
        a query from optional ``is_active`` (when ``active_only``)
        and optional ``category``, sorts by ``name`` ascending,
        caps at ``to_list(length=200)``. ``_id`` projected out.

        Both production callers and the rarely-used
        ``active_only=False`` branch (no production caller, but
        public contract retains the flag) route through this
        verb to preserve the §7.1 single-reader-path rule.
        """
        q: dict[str, Any] = {}
        if active_only:
            q["is_active"] = True
        if category:
            q["category"] = category
        cursor = self._db[self.COLLECTION].find(q, {"_id": 0}).sort("name", 1)
        return await cursor.to_list(length=200)

    async def list_all(self) -> list[dict]:
        """Admin list — no filter.

        Mirrors legacy lines 111-112 of `admin_services.py`.
        Sort by ``created_at`` descending. Caps at
        ``to_list(length=500)`` (legacy default). ``_id``
        projected out.
        """
        cursor = self._db[self.COLLECTION].find({}, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(length=500)

    async def get_by_id(self, service_id: str) -> Optional[dict]:
        """Single fetch by id, ``_id`` projected out.

        Mirrors legacy line 159 of `admin_services.py` (re-read
        after admin PATCH).
        """
        return await self._db[self.COLLECTION].find_one(
            {"id": service_id}, {"_id": 0}
        )

    async def exists_by_id(self, service_id: str) -> bool:
        """Lightweight existence check (NOT in legacy — added for
        404 guard symmetry with C-5).

        The legacy admin PATCH and DELETE paths used the
        ``matched_count == 0`` idiom on the ``update_one`` result
        to surface 404. Routing the write through a repository
        method that returns ``None`` introduces a tiny race
        (delete-then-update between guard and write) that the
        legacy single-call did not have. ``exists_by_id`` is the
        idiomatic guard for the new shape and matches the C-5
        ``InvoiceTemplateRepository.exists_by_id`` precedent.
        Projection ``{"id": 1}`` keeps the round-trip
        light-weight.
        """
        doc = await self._db[self.COLLECTION].find_one(
            {"id": service_id}, {"id": 1}
        )
        return doc is not None

    async def find_by_ids(self, service_ids: list[str]) -> list[dict]:
        """Batch fetch by id list.

        Mirrors legacy lines 14488-14490 of `server.py`
        (``manager_create_invoice`` line-item resolution). The
        caller builds a ``{id: service}`` dict from the returned
        list — that idiom stays at the caller side. ``_id``
        projected out.
        """
        if not service_ids:
            return []
        cursor = self._db[self.COLLECTION].find(
            {"id": {"$in": list(service_ids)}}, {"_id": 0}
        )
        return await cursor.to_list(length=len(service_ids))

    async def list_seed_managed(self, seed_ids: list[str]) -> list[dict]:
        """Seed-reconciliation read — NO ``_id`` projection.

        Mirrors legacy line 14366 of `server.py`. The seed loop
        iterates the raw cursor and inspects ``doc["id"]`` plus
        ``doc["workflow"]`` for translation backfill. The
        omission of ``_id`` projection in the legacy site is
        preserved here — caller never reads ``_id``, but the
        Mongo round-trip shape is identical to the legacy state.
        """
        if not seed_ids:
            return []
        cursor = self._db[self.COLLECTION].find(
            {"id": {"$in": list(seed_ids)}}
        )
        return await cursor.to_list(length=len(seed_ids))

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def create(self, doc: dict) -> None:
        """Insert a fully composed service document.

        Mirrors legacy line 14362 (seed insert) and line 143
        (admin POST insert). Both pass a complete dict at the
        caller side — the repository does NOT inject id,
        timestamps, or any field.
        """
        await self._db[self.COLLECTION].insert_one(doc)

    async def apply_patch(self, service_id: str, *, set_doc: dict) -> None:
        """``$set`` partial update.

        Mirrors legacy line 14394 (seed translation backfill)
        and line 156 (admin PATCH). Caller composes ``set_doc``.
        SILENT on not-found per ``update_one`` semantics.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": service_id}, {"$set": set_doc}
        )

    async def soft_delete(self, service_id: str, *, at_iso: str) -> None:
        """Mark service inactive + stamp deletion time.

        Mirrors legacy line 167. Sets exactly two fields:
        ``is_active=False`` and ``deleted_at``. Does NOT remove
        the document. Does NOT touch other fields.
        """
        await self._db[self.COLLECTION].update_one(
            {"id": service_id},
            {"$set": {"is_active": False, "deleted_at": at_iso}},
        )


__all__ = ["ServiceCatalogRepository"]
