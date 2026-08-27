"""
AppSettingsRepository — Phase 5.3 / C-7.
========================================

Canonical owner of the ``db.app_settings`` Mongo collection — the
single document store for dynamic admin-editable runtime
configuration (currently the ``"auth"`` document; the schema is
key-based so future config families — ``"branding"``,
``"notifications-defaults"``, … — can land here without a
collection migration). After this commit, every mutation to the
collection flows through this class.

Scope (per architect's C-7 mandate, 2026-05-18 part 7)
------------------------------------------------------

This commit owns ONLY ``db.app_settings``.

**Inventory vs ownership map** (``PHASE5_1_OWNERSHIP_MAP.md
§1.3``):

| Map prediction (§1.3)                           | Inventory actual                                                          |
|--------------------------------------------------|---------------------------------------------------------------------------|
| ``app_settings`` — 8 ops, 4w in ``settings_service.py``, 0 readers | **4 raw Motor sites** (2 R + 2 W), **all in ``settings_service.py``**, **0 external direct accessors** |

**Verdict: CONFIRMED** on collection ownership (the owner module
is correct; no external direct ``db.app_settings`` access).
The map's op-count overshoots reality by ~2× (8 vs 4) but this
is a count-method discrepancy, not a falsification of ownership.

Writer / reader contexts (mirrors C-6 §"Architectural shape"
shape)
------------------------------------------------------------

::

  ┌──────────────────────────────────────────────────────────────┐
  │ Writer 1 — boot-time idempotent seed                          │
  │   settings_service.SettingsService.ensure_defaults()          │
  │     • Called from server.py:18239 inside the lifespan         │
  │       follow-up startup function ``_vin_search_engine_startup``│
  │     • Gates on ``get_by_key("auth") is None`` → writes once.  │
  │     • Mirrors legacy lines 162 (read gate) + 174 (insert).    │
  ├──────────────────────────────────────────────────────────────┤
  │ Writer 2 — runtime admin / programmatic write                 │
  │   settings_service.SettingsService.set(key, value, by)        │
  │     • Driven by                                                │
  │       PATCH /api/admin/settings/auth  (admin UI, server.py)   │
  │       (which calls SettingsService.patch_auth → .set)         │
  │     • Driven by                                                │
  │       direct ``set()`` calls from any future caller that      │
  │       wishes to write a non-"auth" key (none today).          │
  │     • Mirrors legacy line 207.                                │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 1 — runtime cached read                                │
  │   settings_service.SettingsService.get(key)                   │
  │     • Read-through cache (30s TTL, per-process), invalidated  │
  │       on every write via ``_invalidate(key)``.                │
  │     • Drives ``get_auth()`` → ``resolve_base_url`` /          │
  │       ``resolve_frontend_url`` / ``resolve_google_client_id`` │
  │       / ``resolve_jwt_secret`` and the public/admin endpoints.│
  │     • Mirrors legacy line 191.                                │
  ├──────────────────────────────────────────────────────────────┤
  │ Reader 2 — boot-time existence gate (same code path as W-1)   │
  │   settings_service.SettingsService.ensure_defaults()          │
  │     • Inline ``find_one({"key":"auth"})`` truthiness check    │
  │       at legacy line 162. The repository surfaces this as     │
  │       a ``get_by_key("auth")`` call whose result is checked   │
  │       for truthiness by the caller. NO separate               │
  │       ``exists_by_key`` verb is introduced — the legacy       │
  │       semantics return the doc, not a bool, and any caller    │
  │       that needs the doc shape (logging, audit, etc.) MUST    │
  │       receive the doc. C-6 added ``exists_by_id`` only        │
  │       because the legacy site checked ``matched_count`` on    │
  │       an UpdateResult, not because it inspected the doc.      │
  │       Here the legacy site already inspects the doc, so the   │
  │       primitive stays.                                         │
  └──────────────────────────────────────────────────────────────┘

Net runtime topology: **single writer module** (``settings_service.py``),
**two write code paths** (idempotent boot seed + runtime set),
**single read primitive** (``get(key)``) that fans out to all
``resolve_*`` consumers via cache, **zero external direct
``db.app_settings`` access**.

Adjacent findings (NOT in scope of C-7)
---------------------------------------

Inventory revealed two cross-domain interactions that are
**visible at app_settings sites but belong to a different
collection** (``integration_configs`` — owned by Phase 5.4 per
``PHASE5_1_OWNERSHIP_MAP.md §1.2``):

* **Type II cross-domain READ** —
  ``settings_service.resolve_google_client_id()`` reads
  ``db.integration_configs.find_one({"provider":"google_oauth"})``
  (legacy line 275) as the 2nd fallback in a 3-step lookup
  chain (app_settings → integration_configs → env var). This is
  acceptable per ``§7.1`` (writes restricted, reads permitted)
  but the read MUST route through the (future) integrations
  repository when Phase 5.4 lands. NOT solved here; documented
  for Phase 5.4 entry.
* **Type I cross-domain WRITE** —
  ``server.py:10931`` (inside the admin PATCH settings endpoint)
  writes ``db.integration_configs.update_one({"provider":"google_oauth"}, ...)``
  as a mirror of the Google Client ID. The write happens
  immediately after a successful app_settings patch as a
  best-effort sync. The write site is in ``server.py``, not in
  ``settings_service.py``, but the write is **triggered by an
  app_settings update**. NOT solved here; documented for
  Phase 5.4 entry (when ``integration_configs`` extracts, this
  write migrates to the IntegrationsRepository).

Neither finding contradicts C-7's app_settings ownership claim.
Both are recorded in ``PHASE5_MIDPOINT_ARCHITECTURE_NOTES.md §4.1``
under the Phase 5.4 forward-blocker entry.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``get_by_key(key)``                       single fetch by
                                                ``key`` — used
                                                both as the
                                                cached runtime
                                                read AND the
                                                boot-time
                                                existence gate.
                                                Returns Mongo
                                                doc verbatim
                                                (``_id``
                                                included — legacy
                                                quirk).

* Writes:
    - ``insert(key, *, value,                   ``insert_one``
              updated_at, updated_by)``          (NO upsert) —
                                                used ONLY by the
                                                boot-time seed
                                                path which has
                                                already verified
                                                via
                                                ``get_by_key``
                                                that the row is
                                                absent. Caller
                                                composes the
                                                ``value`` dict
                                                and the
                                                timestamp; repo
                                                writes the
                                                4-field doc
                                                shape verbatim.

    - ``upsert_value(key, *, value,             ``$set`` partial
                     updated_at, updated_by)``   update with
                                                ``upsert=True``
                                                — used by the
                                                runtime ``set()``
                                                path (admin
                                                PATCH and any
                                                programmatic
                                                config write).
                                                Caller composes
                                                ``value`` and
                                                timestamp; repo
                                                writes the
                                                3-field
                                                ``$set`` shape
                                                verbatim.

Legacy behaviour preserved 1:1 (C-7 mandate)
--------------------------------------------

These quirks live in the legacy ``settings_service.py`` and are
reproduced here verbatim. Changing any of them is OUT OF SCOPE.

* **``key`` is the natural primary key.** The collection has no
  unique index on ``key`` in production (a side-effect of the
  no-migration history). The seed path GATES on
  ``get_by_key(key) is None`` BEFORE inserting; the runtime
  ``set`` path uses ``upsert=True``. Both paths therefore work
  in practice. The repository **does NOT add a unique index**
  — index management is an infra concern handled at startup,
  and changing it would change the operational shape of the
  collection.
* **``_id`` is NOT projected out of reads.** Legacy lines 162
  and 191 use ``find_one({"key": key})`` with no projection.
  Both callers ignore ``_id`` in the returned dict; the
  cache stores the inner ``value`` only (line 195). Preserving
  the projection-omission keeps the Mongo round-trip shape
  identical to legacy. Tests pin this quirk.
* **``insert`` is non-upsert.** The seed path is GUARDED by an
  explicit ``get_by_key(key) is None`` check (line 162-164),
  so concurrent boots could in theory both pass the gate and
  attempt to insert — a race that legacy has, and which C-7
  preserves. The right resolution is a unique index in Phase
  5.4 / 5.5 (an infra concern); C-7 does NOT add one.
* **``upsert_value`` performs a $set on EXACTLY 3 fields**:
  ``value``, ``updatedAt``, ``updatedBy``. Other fields in the
  existing doc (if any) are NOT touched. Legacy line 210-214.
  The repository does NOT inject any field; the caller passes
  the timestamp.
* **``updatedAt`` is a ``datetime`` (NOT ISO string).** Both
  legacy writes use ``datetime.now(timezone.utc)`` and Motor
  serialises to BSON datetime. Other repositories in Phase 5.3
  (C-6 ``soft_delete``, C-5 ``apply_patch``) use ISO strings
  because their legacy sites did. ``app_settings`` differs by
  legacy; C-7 preserves this inconsistency rather than
  normalising it.
* **``updated_by`` defaults are at the caller side.** The
  legacy ``set()`` has ``by: str = "admin"`` and
  ``ensure_defaults()`` uses ``"system"``. The repository does
  NOT carry a default — every call site passes the value
  explicitly. This matches the C-6 pattern (caller composes
  the metadata).

Why NO ``set_value()`` short-hand that hides the upsert
-------------------------------------------------------

A tempting one-line wrapper would be:

::

    async def set_value(self, key, value):
        return await self.upsert_value(
            key, value=value,
            updated_at=datetime.now(timezone.utc),
            updated_by="system",
        )

We do NOT introduce it. Reasons:

1. It would hide the timestamp / updater composition that the
   legacy site does explicitly — and hiding ``updated_by``
   reduces auditability of who wrote.
2. It would create two doors into the same write — the named
   ``upsert_value`` and the shortcut — and Phase 5 has been
   strict that the repository surface is **one door per
   business operation**.
3. ``settings_service.SettingsService.set`` is already that
   wrapper — it composes the timestamp inline at the caller
   layer where it belongs.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No hard-delete (the collection has no delete path in any
   legacy site; C-7 mirrors this — there is NO ``delete_by_key``
   verb).
*  No HTTP exceptions — repository raises only on programmer
   error (e.g. missing kwargs).
*  No DTO normalisation — accepts / returns dicts in the exact
   legacy shape.
*  No timestamp injection — caller passes ``updated_at``.
*  No deep-merge / partial-value logic — that lives in
   ``SettingsService.patch_auth`` (composition at caller side).
*  No cache invalidation logic — ``SettingsService`` owns its
   own process-local cache; the repository writes to Mongo
   only.
*  No public-subset / secret-masking logic — that lives in
   ``settings_service.public_subset`` and at the HTTP
   endpoints in ``server.py``.
*  No env-var fallback chain (``baseUrl`` / ``GOOGLE_CLIENT_ID``
   / ``JWT_SECRET``) — those live in
   ``SettingsService.resolve_*`` (composition at caller side).
*  No touch on ``db.integration_configs`` (Phase 5.4 concern
   per §4.1 of the midpoint architecture notes).
*  No service-layer extraction (Phase 5.6+).
*  No index creation / unique-key constraint (Phase 5.4 / 5.5
   infra concern).
*  No BaseRepository.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


class AppSettingsRepository:
    """Owner of ``db.app_settings`` (BIBI dynamic admin-editable config).

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). The single caller context
    (``SettingsService``) instantiates it once at service
    construction time.
    """

    COLLECTION = "app_settings"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Fetch the full settings document for ``key``.

        Mirrors legacy lines 162 (boot existence gate) and 191
        (cached runtime read) of ``settings_service.py``. Returns
        the Mongo document **as-is** (``_id`` included — legacy
        quirk preserved). Returns ``None`` if no document exists
        for the given key.

        The two callers use the result differently:

        * ``ensure_defaults`` checks ``if doc:`` (truthiness gate).
        * ``get(key)`` accesses ``doc.get("value")`` and caches
          the inner value (not the wrapper).

        Both are satisfied by returning the raw doc.
        """
        return await self._db[self.COLLECTION].find_one({"key": key})

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def insert(
        self,
        key: str,
        *,
        value: Dict[str, Any],
        updated_at: datetime,
        updated_by: str,
    ) -> None:
        """Insert a NEW settings document (NO upsert).

        Mirrors legacy line 174 of ``settings_service.py``
        (boot-time seed write). Used ONLY by the seed path which
        has verified via ``get_by_key(key) is None`` that no
        document exists. Caller composes ``value`` and timestamp.

        The 4-field document shape (``key``, ``value``,
        ``updatedAt``, ``updatedBy``) is written verbatim. The
        repository does NOT inject any field.

        Race condition note: two concurrent boots could both
        pass the existence gate and both call ``insert``. This
        race exists in legacy and is intentionally preserved.
        The collection currently has no unique index on ``key``.
        Resolution is a Phase 5.4 / 5.5 infra concern, NOT a
        C-7 fix.
        """
        await self._db[self.COLLECTION].insert_one(
            {
                "key": key,
                "value": value,
                "updatedAt": updated_at,
                "updatedBy": updated_by,
            }
        )

    async def upsert_value(
        self,
        key: str,
        *,
        value: Dict[str, Any],
        updated_at: datetime,
        updated_by: str,
    ) -> None:
        """Upsert the settings document for ``key`` with a $set on
        ``value``, ``updatedAt``, ``updatedBy``.

        Mirrors legacy lines 207-217 of ``settings_service.py``
        (runtime ``set`` path — admin PATCH and any
        programmatic config write). Caller composes ``value``
        and timestamp.

        Touches EXACTLY 3 fields. Other fields in the existing
        document (if any) are preserved. The repository does NOT
        inject any field. ``upsert=True`` matches legacy
        semantics — runtime ``set`` is happy to create the
        document if it does not exist yet.
        """
        await self._db[self.COLLECTION].update_one(
            {"key": key},
            {
                "$set": {
                    "value": value,
                    "updatedAt": updated_at,
                    "updatedBy": updated_by,
                }
            },
            upsert=True,
        )


__all__ = ["AppSettingsRepository"]
