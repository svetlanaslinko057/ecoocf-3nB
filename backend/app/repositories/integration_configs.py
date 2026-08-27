"""
IntegrationConfigsRepository — Phase 5.4 / C-2.
================================================

Canonical owner of the ``db.integration_configs`` Mongo collection.

**Second Phase 5.4 extraction.** **Thirteenth extraction
overall.** This is the FIRST extraction whose collection is a
genuinely *shared* configuration boundary — five logical
providers (``google_oauth``, ``stripe``, ``email``, ``shipping``,
``openai``) coexist as DIFFERENT documents discriminated by the
``provider`` field, with **provider-specific credentials shapes**,
provider-specific secret-redaction policies, and a provider-
specific MIRROR TENSION (google_oauth dual-stored across
``app_settings`` and ``integration_configs``).

Architectural answer to the C-2 mandate question
-------------------------------------------------

> "Is ``integration_configs`` a clean shared config repository,
>  or a multi-owner runtime config surface?"

**Answer: PARTIALLY SHARED CONFIG WITH MULTI-OWNER MIRROR TENSION
FOR google_oauth ONLY.**

* For 4 of 5 providers (``stripe``, ``email``, ``shipping``,
  ``openai``), the collection is a **clean shared config
  repository** — single owner (admin_integrations router for
  writes; webhook/admin endpoints for reads), no mirror, no
  cross-domain write into this collection from outside the owner.
* For 1 of 5 providers (``google_oauth``), the collection is a
  **multi-owner runtime config surface** — the same logical
  data point (``clientId``) lives in BOTH
  ``app_settings.auth.google.clientId`` (owned by C-7's
  ``AppSettingsRepository``, source-of-truth) AND
  ``integration_configs.{provider:google_oauth}.credentials.clientId``
  (legacy storage). The two are reconciled by a **one-way
  write mirror** (settings PATCH endpoint at ``server.py:10943``
  writes to BOTH on every save) and a **fallback read chain**
  in ``settings_service.get_google_client_id`` (priority:
  app_settings → integration_configs → env var).
* For 1 "synthetic provider" (``ringostat``), the collection
  contains NO row at all — the admin GET endpoint synthesizes
  a ringostat block from the sibling ``ringostat_config``
  collection (see §1.4 below; **this is NOT a Type V tension
  with integration_configs** — ringostat_config is a separate
  ownership concern outside C-2 scope).

The mandate's instruction "Не пытаться 'починить' Google
ClientID mirror из settings. Только: expose it, route it through
repository if safe, document ownership tension, do not redesign"
is honoured: C-2 EXPOSES the mirror with a NAMED VERB
(``mirror_google_client_id``) so the tension is visible at the
repository contract, but C-2 does NOT redesign the dual-storage,
does NOT collapse it into a single source of truth, and does NOT
touch the fallback read chain. **The mirror remains; the surface
makes it legible.**

Implication for Phase 5.4 / C-3 (app.state migration prep)
----------------------------------------------------------

The Google ClientID dual-storage **IS a blocker** for the
app.state migration as currently planned, because the write-
mirror at ``server.py:10943`` creates a synchronous cross-
collection write inside a router handler — moving to
``app.state``-bound services without first reconciling this
mirror would introduce a race window (settings writes COULD
land before mirror writes, leaving the two collections briefly
inconsistent during normal operation). **Recommendation: C-3
should start with a small precursor commit that unifies the
Google ClientID storage policy (either retire the integration_configs
copy or formalize the mirror as a transactional emit) BEFORE
the lifespan/app.state migration begins.**

Other than this one blocker, the C-2 inventory found NO new
blockers — the other four providers route cleanly through
``find_by_provider`` + the four write verbs, with no cross-
domain writes into the collection and no other dual-storage.

Inventory (12 production sites across 4 files)
-----------------------------------------------

::

  File                                     | Sites | Concern
  -----------------------------------------|-------|------------------------
  server.py                                | 3     | Google ClientID fallback
                                           |       | (×2 read) + mirror write
                                           |       | from settings PATCH (×1)
  app/routers/admin_integrations.py        | 7     | Primary admin owner —
                                           |       | 4 reads + 3 writes
                                           |       | (PATCH, test outcome,
                                           |       | toggle)
  app/routers/payments.py                  | 1     | Stripe webhook key
                                           |       | lookup (READ only)
  settings_service.py                      | 1     | Google ClientID
                                           |       | fallback chain
                                           |       | (READ, app_settings →
                                           |       | here → env var)
  -----------------------------------------|-------|------------------------
                                  TOTAL    | 12    |

Lifecycle-context classification (CRUD-shaped collection; the
mandate from observation 7 §6.3 of the midpoint notes places
configuration registries in the CRUD-shaped family — but C-2
still audits all 8 categories for completeness)
---------------------------------------------------------------

::

  Category                    | Sites
  ────────────────────────────┼──────────────────────────────
  enqueue contexts            | 4 distinct write verbs:
                              |   1) upsert_provider_config — PATCH
                              |   2) record_test_outcome   — POST .../test
                              |   3) set_enabled           — POST .../toggle
                              |   4) mirror_google_client_id — settings PATCH
                              |                                cross-domain
                              |                                write site
  dispatch contexts           | 0
  retry contexts              | 0
  failure contexts            | 0
  success/finalization        | terminal-at-write
  cleanup/TTL contexts        | 0 (configs persist forever)
  boot/startup contexts       | 0 (no index ensured; no boot
                              |   seed for any provider —
                              |   admin must configure)
  worker contexts             | 0
  ────────────────────────────┴──────────────────────────────
  admin reader contexts       | 4 logical use-cases collapsed
                              | onto 1 read verb (find_by_provider):
                              |   - admin GET list (5 providers ×1)
                              |   - admin /health (×2 providers)
                              |   - admin PATCH pre-read merge (×1)
                              |   - admin /test pre-read (×1)
                              |   - stripe webhook (payments.py)
                              |   - settings_service mirror chain

**Of 8 lifecycle write-path categories, 1 is populated**
(enqueue, 4 verb-variants). The collection is CRUD-shaped per
the §6.3 observation 7 rule — collection name (``integration_configs``)
suggests configuration registry, not pipeline/queue/log. The
sparse lifecycle profile confirms this classification.

Provider-key topology (preserved verbatim per C-2 mandate)
-----------------------------------------------------------

Each provider's ``credentials`` dict has a different schema.
**The repository does NOT validate credentials shape.** All
shape knowledge lives at the admin-integrations router (the
SECRET_FIELDS / PUBLIC_DEFAULTS dicts at
``app/routers/admin_integrations.py:141-155``). C-2 preserves
this 100% — the repository accepts ``Dict[str, Any]`` and
trusts the caller.

::

  google_oauth:
    credentials: { clientId (public), clientSecret (SECRET) }
    settings:    { } (empty by default)
    mode:        "disabled" by default
    Cross-collection tension: app_settings.auth.google.clientId
                              is the primary source-of-truth
                              for clientId; this collection is
                              the legacy mirror.

  stripe:
    credentials: {
      publishableKey (public),
      secretKey      (SECRET),
      restrictedKey  (SECRET),
      webhookSecret  (SECRET),
    }
    settings:    { currency: "USD" by default }
    mode:        "sandbox" by default

  email:
    credentials: { ..., smtpPassword (SECRET) }
    settings:    { }
    mode:        "disabled" by default

  shipping:
    credentials: { apiKey, vesselFinderKey, shipsGoKey (ALL SECRET) }
    settings:    { }
    mode:        "disabled" by default
    NOTE: tracking provider keys for VesselFinder/ShipsGo/AfterShip
          live in OS env vars + TrackingConfigService (P3.1) —
          THIS collection's "shipping" provider is a SEPARATE
          settings surface (admin can configure shipping
          credentials, but the runtime workers read from
          TrackingConfigService — divergent storage paths,
          Phase 5.5+ reconciliation candidate).

  openai:
    credentials: { apiKey (SECRET) }
    settings:    { model: "gpt-4o" by default }
    mode:        "sandbox" by default

  ringostat:
    NO ROW IN THIS COLLECTION.
    Configuration lives in db.ringostat_config (separate ownership).
    The admin GET endpoint SYNTHESIZES a ringostat block from
    ringostat_config — preserved verbatim.

Business operations vocabulary (5 named verbs)
-----------------------------------------------

* ``find_by_provider(provider)`` —
    Returns the provider's full document OR an empty dict
    (preserves the legacy ``... or {}`` quirk at every call
    site). Used by 9 callers across 4 files: the 4 admin
    reads, the stripe webhook, the settings mirror chain,
    and the 2 google ClientID fallbacks. Single read verb
    consolidates ALL read contexts.

* ``upsert_provider_config(provider, *, credentials=None,
  settings=None, mode=None, is_enabled=None, ts_iso)`` —
    PATCH endpoint write. Conditionally sets fields based
    on which kwargs the caller provided (mirrors the legacy
    ``if isinstance(data.get('credentials'), dict): ...``
    logic). The masked-secret-preservation logic (caller
    replaces ``…suffix`` masked values with the existing
    secret before calling this verb) stays at the router
    layer — the repository accepts whatever credentials
    dict the caller composes. Always upserts with
    ``provider`` and ``updated_at``.

* ``record_test_outcome(provider, *, success, message, ts_iso)`` —
    POST ``/api/admin/integrations/{provider}/test`` outcome
    persistence. Writes ``lastTest`` + ``lastTestStatus`` +
    ``lastTestError`` to the provider's document. Caller
    composes the test logic; repo only persists the outcome.

* ``set_enabled(provider, is_enabled, *, ts_iso)`` —
    POST ``/api/admin/integrations/{provider}/toggle`` write.
    Sets ``isEnabled`` + ``provider`` + ``updated_at``.
    Upserts (so a provider can be toggled before its
    credentials are configured — preserved legacy behaviour).

* ``mirror_google_client_id(client_id, *, ts)`` —
    The Google ClientID write-mirror from settings PATCH
    endpoint (``server.py:10943``). **This verb's name
    EXPOSES the cross-collection mirror tension** —
    collapsing it into ``upsert_provider_config`` would
    hide the architectural fact that this write is a
    mirror, not a primary edit. Sets ``provider`` +
    ``credentials.clientId`` + ``isEnabled=True`` +
    ``updatedAt`` (note: ``updatedAt`` not ``updated_at``
    — legacy casing preserved). Upserts.

**5 named verbs.** "Standard" band of the §6.3 morphology
observation — verb count matches populated lifecycle-category
count (1 enqueue family × 4 variants + 1 read consolidation).

Vocabulary continuity vs prior 12 repositories:

* ``find_by_provider``        — NEW (provider-keyed read pattern; future provider-keyed repositories may repeat).
* ``upsert_provider_config``  — NEW (verb naming the conditional-set semantics).
* ``record_test_outcome``     — NEW (lifecycle-shaped: ``record_<event>``).
* ``set_enabled``             — NEW.
* ``mirror_google_client_id`` — NEW (the verb name makes the cross-collection mirror tension visible — methodology rule from C-10/C-11).

**5 NEW.** First CRUD-shaped extraction in Phase 5.4. The
``record_test_outcome`` verb echoes the C-10/C-11/P5.4-C-1
``record_<event>`` pattern even though this collection is
CRUD-shaped overall — the test-outcome write is structurally
an event (test happened at ts), not a config edit.

Legacy quirks preserved 1:1
---------------------------

1. **Every read uses the ``... or {}`` fallback pattern** at
   the call site. The repository's ``find_by_provider``
   returns ``{}`` (not ``None``) when the document is missing,
   matching the legacy idiom verbatim across all 9 callers.
2. **Per-provider secret-redaction policy** lives at the
   admin router (``SECRET_FIELDS`` dict), NOT in the repo.
   Migrating it into the repo would (a) duplicate the
   knowledge and (b) force the stripe-webhook caller in
   payments.py to opt out of redaction. Repository remains
   shape-agnostic.
3. **The masked-secret preservation** at PATCH (when caller
   sends ``"…abc12345"`` instead of the real secret, the
   router merges with the existing doc's secret) lives at
   the router, NOT the repo. Repository accepts whatever
   the caller composes.
4. **Timestamp casing inconsistency** between
   ``updated_at`` (used by admin PATCH/test/toggle) and
   ``updatedAt`` (used by the Google ClientID mirror) is
   PRESERVED verbatim — the legacy two-spelling system has
   lived for ~9 months and any consumer that filters by
   ``updated_at`` would silently exclude the mirror writes
   (and vice versa). Documenting, NOT fixing.
5. **No unique index on ``provider``** — concurrent upserts
   from PATCH + toggle + mirror could in theory race on
   the same provider. Legacy accepts this because all 3
   write paths are upserts (MongoDB's upsert IS atomic at
   the document level for the matched-and-update case);
   the only race window is the find_one→insert case which
   is rare enough to be ignored. NOT fixing.
6. **The fallback read chain** (settings.auth.google.clientId
   → integration_configs.{provider:google_oauth}.credentials.clientId
   → env GOOGLE_CLIENT_ID) lives at the CALLER
   (``settings_service.get_google_client_id`` and
   ``server.py:6943``). The repository does NOT participate
   in fallback orchestration — it only answers
   "what's persisted for this provider?".
7. **The ringostat synthesized block** in the admin GET
   response (a ringostat entry constructed from the SIBLING
   ``ringostat_config`` collection) lives at the admin
   router. Repository does NOT touch ``ringostat_config``.

What this repository does NOT do (deliberately)
------------------------------------------------

* No ``IntegrationsService`` facade.
* No config normalization across providers.
* No provider-schema unification or Pydantic model.
* No secret-redaction logic (stays at admin router).
* No encryption / decryption changes.
* No id generation (``provider`` IS the natural primary key).
* No timestamp normalization (the ``updated_at`` vs ``updatedAt``
  divergence is preserved).
* No HTTP exception raise — all errors propagate to the
  caller, which handles them per-endpoint.
* No event emission / Socket.IO / event bus.
* No touch on ``app_settings`` (C-7's collection — the Google
  mirror SOURCE).
* No touch on ``ringostat_config`` (separate ownership).
* No merging with ``app_settings`` for google_oauth (mandate
  forbidden — the dual-storage is a Phase 5.4 / C-3-precursor
  concern, not a C-2 concern).
* No ``BaseRepository`` / inheritance.
* No ``app.state`` migration (Phase 5.4 / C-3 territory).
* No Stripe/Ringostat behaviour changes.
* No settings-system redesign.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_iso() -> str:
    """ISO-8601 UTC timestamp helper. Mirrors the per-call legacy idiom
    ``datetime.now(timezone.utc).isoformat()`` used everywhere at the
    call sites."""
    return datetime.now(timezone.utc).isoformat()


class IntegrationConfigsRepository:
    """Owner of ``db.integration_configs`` (shared provider configuration
    registry: google_oauth / stripe / email / shipping / openai).

    See module docstring for the architectural answer to the C-2 mandate
    question and the dual-storage tension documentation for google_oauth.
    """

    COLLECTION = "integration_configs"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read — single verb consolidating all 9 callers across 4 files
    # ------------------------------------------------------------------

    async def find_by_provider(self, provider: str) -> Dict[str, Any]:
        """Return the document for ``provider`` or an empty dict.

        Preserves the legacy ``... or {}`` idiom verbatim at every
        call site. Returns ``{}`` (not ``None``) when no document
        exists for the provider; callers MUST treat ``{}`` as
        "not configured".
        """
        doc = await self._db[self.COLLECTION].find_one({"provider": provider})
        return doc or {}

    # ------------------------------------------------------------------
    # Writes — four distinct verbs reflecting four distinct write
    # contexts (3 admin-router + 1 settings-mirror cross-domain)
    # ------------------------------------------------------------------

    async def upsert_provider_config(
        self,
        provider: str,
        *,
        credentials: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        ts_iso: Optional[str] = None,
    ) -> None:
        """PATCH ``/api/admin/integrations/{provider}`` write.

        Conditionally sets fields based on which kwargs the caller
        provides — mirrors the legacy ``if isinstance(data.get(...), dict):``
        logic at ``app/routers/admin_integrations.py:312-325``.
        Always sets ``provider`` + ``updated_at`` (caller-provided
        or repo-default).

        Masked-secret preservation (when caller sends ``"…suffix"``
        instead of the real secret, the router merges with the
        existing document's secret BEFORE calling this verb) lives
        at the router layer — this verb accepts whatever the
        caller composes.
        """
        update: Dict[str, Any] = {
            "provider": provider,
            "updated_at": ts_iso or _utc_iso(),
        }
        if credentials is not None:
            update["credentials"] = credentials
        if settings is not None:
            update["settings"] = settings
        if mode is not None:
            update["mode"] = mode
        if is_enabled is not None:
            update["isEnabled"] = bool(is_enabled)
        await self._db[self.COLLECTION].update_one(
            {"provider": provider}, {"$set": update}, upsert=True
        )

    async def record_test_outcome(
        self,
        provider: str,
        *,
        success: bool,
        message: str,
        ts_iso: Optional[str] = None,
    ) -> None:
        """POST ``/api/admin/integrations/{provider}/test`` outcome
        persistence.

        Writes ``lastTest`` + ``lastTestStatus`` + ``lastTestError``
        verbatim per the legacy site at
        ``app/routers/admin_integrations.py:507-515``. Caller
        composes the test logic; repository persists the outcome
        atomically. Upserts (so a test can persist even if no
        prior config exists — preserved legacy behaviour).
        """
        await self._db[self.COLLECTION].update_one(
            {"provider": provider},
            {"$set": {
                "lastTest":        ts_iso or _utc_iso(),
                "lastTestStatus":  "ok" if success else "failed",
                "lastTestError":   "" if success else message,
            }},
            upsert=True,
        )

    async def set_enabled(
        self,
        provider: str,
        is_enabled: bool,
        *,
        ts_iso: Optional[str] = None,
    ) -> None:
        """POST ``/api/admin/integrations/{provider}/toggle`` write.

        Sets ``isEnabled`` + ``provider`` + ``updated_at``. Upserts
        (so a provider can be toggled before its credentials are
        configured — preserved per
        ``app/routers/admin_integrations.py:529-534``).
        """
        await self._db[self.COLLECTION].update_one(
            {"provider": provider},
            {"$set": {
                "provider":    provider,
                "isEnabled":   bool(is_enabled),
                "updated_at":  ts_iso or _utc_iso(),
            }},
            upsert=True,
        )

    async def mirror_google_client_id(
        self,
        client_id: str,
        *,
        ts: Optional[datetime] = None,
    ) -> None:
        """Write-mirror of ``app_settings.auth.google.clientId`` into
        this collection.

        ─────────────────────────────────────────────────────────────────
        🔻 DEPRECATED — Phase 5.4 / C-3A (mirror retired)
        ─────────────────────────────────────────────────────────────────
        As of Phase 5.4 / C-3A the production call site at
        ``server.py:10947`` (settings PATCH endpoint) has been removed.
        ``app_settings.auth.google.clientId`` is now the SOLE source-
        of-truth for the Google OAuth Client ID. This verb is preserved
        on the repository surface per the C-3A mandate ("verb retirement
        в отдельном коммите") and currently has **ZERO production
        callers** (verified by `test_9_no_production_caller_in_server_py`
        and `test_10_no_production_caller_in_routers` in the C-3A
        test suite).

        Retirement timeline:

        * **C-3A (this commit):** mirror writes stopped, startup
          backfill copies any legacy ``integration_configs.{provider:
          google_oauth}.credentials.clientId`` into ``app_settings``
          on first boot after deploy. Verb kept on surface.
        * **C-3B:** ``app.state`` migration prep. Verb still kept.
        * **Post-stabilization (separate commit, NOT C-3A/B):** verb
          removed; the ``record_test_outcome`` / ``set_enabled`` /
          ``upsert_provider_config`` surface for ``google_oauth``
          may also be reviewed at that point. Until then this verb
          remains as a recovery hook for any operator who needs to
          force-write the legacy mirror (e.g., during disaster
          recovery from a backup that predates C-3A).

        ─────────────────────────────────────────────────────────────────
        Original docstring (preserved for reference)
        ─────────────────────────────────────────────────────────────────

        Mirrors the body of ``server.py:10943-10954`` verbatim.
        Called by the settings PATCH endpoint AFTER persisting
        the canonical ``app_settings`` document — so this collection
        stays consistent with the legacy Google OAuth flow that
        still reads from here.

        Legacy quirk preserved: uses ``updatedAt`` (camelCase)
        NOT ``updated_at`` (snake_case used by all other verbs
        in this repo). The casing divergence is the original
        write site's choice; documenting, not fixing.
        Also writes ``credentials.clientId`` using dot-notation
        path (NOT the full ``credentials`` dict replacement) —
        preserved to avoid clobbering ``credentials.clientSecret``.
        """
        await self._db[self.COLLECTION].update_one(
            {"provider": "google_oauth"},
            {
                "$set": {
                    "provider":             "google_oauth",
                    "credentials.clientId": client_id,
                    "isEnabled":            True,
                    "updatedAt":            ts or datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )


__all__ = ["IntegrationConfigsRepository"]
