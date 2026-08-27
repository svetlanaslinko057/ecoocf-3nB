"""
ProviderStatsRepository — Phase 5.3 / C-4.
==========================================

Canonical owner of the ``db.provider_stats`` Mongo collection.
After this commit, every mutation to that collection flows through
this class. The service class ``provider_stats.ProviderStatsService``
owns the business logic (tier scoring, cooldown, notifications) and
calls into THIS repository for ALL `provider_stats` collection
access.

Scope (per architect's C-4 mandate, 2026-05-18 part 4)
------------------------------------------------------

This commit owns ONLY ``db.provider_stats``. The ``provider_stats.py``
module ALSO writes to ``db.orders`` (4 sites — see §"Phase 5.4
blocker") and reads ``db.users`` / ``db.staff`` (cross-domain
manager lookup). Those touches are **deliberately left in place**:

  * orders WRITES inside provider_stats.py represent a real
    cross-domain ownership violation that belongs to a SERVICE/
    EVENT-CONTRACT discussion, NOT to a clean repository
    extraction. Pulling them into this commit would turn C-4
    into Phase 5.4 work — and the architect's mandate is to
    preserve the boring-precision cadence first.
  * users / staff READS are cross-domain READS which are
    acceptable per Phase 5.1 §7.1 (only writes are restricted).
    They will tighten when the IdentityDomain repository lands
    in Phase 5.5.

The single-writer rule for ``provider_stats`` is achievable IN
ISOLATION because **no external module writes to
``db.provider_stats``**. The only direct call sites are the 6
inside ``provider_stats.py`` itself. (The test file
``test_provider_pressure.py`` also touches the collection
directly, but per ownership-map §0 the AST/grep scan
explicitly excludes tests; production code is the contract.)

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``get_for_provider(provider_id)``    fetch single snapshot
                                            doc; ``None`` on miss
    - ``list_ranked()``                    full list sorted by
                                            ``score`` desc (admin
                                            visibility surface)
    - ``find_for_providers(provider_ids)`` dict of provider_id →
                                            snapshot for a candidate
                                            list (matching engine)

* Writes:
    - ``upsert_snapshot(provider_id, *, stats, created_at_iso)``
                                            full-replace snapshot;
                                            preserves the
                                            ``createdAt`` on first
                                            insert via $setOnInsert
                                            (idempotent, no
                                            increment).

Legacy behaviour preserved 1:1 (C-4 mandate)
--------------------------------------------

These quirks live in the legacy `provider_stats.py` site and are
reproduced here verbatim. Changing any of them is OUT OF SCOPE
for this commit.

* **``_id`` IS projected out of every read.** Legacy lines 168,
  344, 350, 369 all carry ``{"_id": 0}``. Preserved.
* **``providerId`` is the natural primary key.** No separate
  ``id`` column. Both reads and writes select by
  ``{"providerId": provider_id}``.
* **``upsert_snapshot`` uses ``$set + $setOnInsert``.** The first
  write of a snapshot installs ``createdAt``; subsequent writes
  do NOT touch it (the ``updatedAt`` lives inside ``stats``).
  Both legacy write sites (L190 empty-orders branch + L323 main
  path) use identical Mongo shape. Preserved 1:1 as a single
  named verb.
* **``list_ranked`` uses ``to_list(length=1000)``.** Legacy
  line 353 caps at 1000; preserved verbatim.
* **``find_for_providers`` returns a dict** (provider_id →
  snapshot) for O(1) lookup by the matching engine. Legacy
  line 372-373 builds this exact dict from an async cursor.
* **No score / tier / payload normalisation.** Whatever the
  service hands us in ``stats`` goes straight to Mongo. The
  service owns scoring; the repository owns persistence.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` shortcut.
*  No HTTP exceptions — repository raises only on programmer error.
*  No DTO normalisation — returns / accepts dicts in the exact
   legacy shape.
*  No scoring, no tier resolution, no cooldown logic. Those
   are service concerns and stay in ``provider_stats.py``.
*  No touch on ``db.orders``, ``db.users``, ``db.staff``. Those
   live on the service side and are the Phase 5.4 / 5.5 boundary.
*  No BaseRepository (per architect mandate).

Phase 5.4 blocker (documented here for the next slice)
------------------------------------------------------

When ``provider_stats.py`` runs ``recompute(provider_id)`` it
issues, in addition to its own collection ops, the following
cross-domain Mongo calls — ALL OF WHICH STAY ON THE SERVICE SIDE
IN C-4:

| Line | Call                                                    | Domain | Type | Phase 5 slice |
|------|---------------------------------------------------------|--------|------|---------------|
| 144  | ``db.orders.update_one(...)``  (stamp startedAt/completedAt) | Orders | **WRITE** | Phase 5.4 |
| 151  | ``db.orders.update_one(...)``  (stamp assignedAt first-touch)| Orders | **WRITE** | Phase 5.4 |
| 164  | ``db.orders.find({"managerId": pid}, ...).to_list``     | Orders | READ  | Phase 5.4 |
| 333  | ``db.orders.distinct("managerId")``  (in recompute_all) | Orders | READ  | Phase 5.4 |
| 295  | ``db.users.find_one({"id": pid}, ...)``                 | Identity | READ  | Phase 5.5 |
| 297  | ``db.staff.find_one({"id": pid}, ...)``                 | Identity | READ  | Phase 5.5 |

The two orders **WRITES** (L144, L151) are the first real
cross-domain ownership violation in the Phase 5 work. Per the
single-writer rule in `PHASE5_1_OWNERSHIP_MAP.md §7.1`, only the
OrdersDomain owner is permitted to mutate ``db.orders``. The
correct resolution is a Phase 5.4 work item:

    "publish an event from provider_stats (e.g.
     ``provider_order_timing_stamped``) and have the OrdersDomain
     owner consume it, OR expose an OrdersRepository operation
     ``stamp_lifecycle_timing(order_id, *, field, value)`` and
     call that from provider_stats. The architect will pick
     between event-driven vs direct-service-call in 5.4 once
     the orders ownership is itself extracted."

For C-4 this is **documented and deferred**, not fixed.
"""
from __future__ import annotations

from typing import Any


class ProviderStatsRepository:
    """Owner of ``db.provider_stats``.

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). ``ProviderStatsService``
    constructs one per call via ``self._stats_repo`` and never
    touches the collection directly. The bridge to the Motor
    handle (`self.db`) inside the service is the only remaining
    direct-Mongo reference in this surface and will dissolve in
    Phase 5.8 with DI.
    """

    COLLECTION = "provider_stats"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_for_provider(self, provider_id: str) -> dict | None:
        """Fetch the latest stats snapshot for a single provider.

        Returns ``None`` on miss. Legacy line 168 of `provider_stats.py`
        applies ``... or {}`` at the call site (inside `recompute`,
        where a missing prior snapshot is normal); legacy line 344
        of the `get()` method checks ``if not doc:`` and triggers
        a recompute. Both call-site idioms remain at the service
        side. ``_id`` is projected out per legacy.
        """
        return await self._db[self.COLLECTION].find_one(
            {"providerId": provider_id}, {"_id": 0}
        )

    async def list_ranked(self) -> list[dict]:
        """Return all snapshots sorted by ``score`` descending.

        Legacy `list_all(sort_by_score=True)` path. The
        ``sort_by_score=False`` branch is preserved via
        :py:meth:`list_unsorted` for back-compat (no production
        caller today but the public API parameter still accepts
        ``False``). Cap is ``to_list(length=1000)`` per legacy
        line 353. ``_id`` is projected out.
        """
        cursor = self._db[self.COLLECTION].find({}, {"_id": 0}).sort("score", -1)
        return await cursor.to_list(length=1000)

    async def list_unsorted(self) -> list[dict]:
        """Return all snapshots in natural order.

        Legacy `list_all(sort_by_score=False)` path. No production
        caller routes through this today (admin uses ``=True``
        unconditionally), but the public API parameter remains
        for back-compat — we preserve the unsorted shape via a
        dedicated named verb rather than re-exposing a raw
        ``find()`` cursor to the service. Cap is
        ``to_list(length=1000)`` per legacy. ``_id`` is projected
        out.
        """
        cursor = self._db[self.COLLECTION].find({}, {"_id": 0})
        return await cursor.to_list(length=1000)

    async def find_for_providers(self, provider_ids: list[str]) -> dict[str, dict]:
        """Return a ``{providerId: snapshot}`` dict for the candidates.

        Used by the matching engine (`pick_best_provider`) for O(1)
        lookup as it iterates the candidate list. Providers without
        a snapshot are silently absent from the result (legacy
        line 376-378 substitutes a neutral default at the service
        side). ``_id`` is projected out.
        """
        out: dict[str, dict] = {}
        cursor = self._db[self.COLLECTION].find(
            {"providerId": {"$in": list(provider_ids)}}, {"_id": 0}
        )
        async for d in cursor:
            out[d["providerId"]] = d
        return out

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def upsert_snapshot(
        self,
        provider_id: str,
        *,
        stats: dict,
        created_at_iso: str,
    ) -> None:
        """Persist a freshly computed snapshot.

        Mirrors legacy lines 190-194 (empty-orders branch) and
        323-327 (main path) — both have the identical Mongo
        shape:

            update_one(
                {"providerId": provider_id},
                {"$set": stats, "$setOnInsert": {"createdAt": created_at_iso}},
                upsert=True,
            )

        ``stats`` is written as-is (no normalisation). ``createdAt``
        is installed only on first insert (idempotent — repeat
        snapshots do NOT touch it). ``updatedAt`` lives inside
        ``stats`` (service responsibility).
        """
        await self._db[self.COLLECTION].update_one(
            {"providerId": provider_id},
            {"$set": stats, "$setOnInsert": {"createdAt": created_at_iso}},
            upsert=True,
        )


__all__ = ["ProviderStatsRepository"]
