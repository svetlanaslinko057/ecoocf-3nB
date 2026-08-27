"""
app.state migration target map — Phase 5.4 / C-3B (prep, NOT migration).
========================================================================

🔻 **DOCUMENTATION-ONLY MODULE. ZERO RUNTIME EFFECT.** 🔻

This module exists exclusively to make the runtime topology of BIBI
mechanically visible BEFORE the Phase 5.4 / C-4 bridge retirement wave.
It does not register routes, does not mutate ``app.state``, does not
import ``server.py``, and is not loaded by ``lifespan``. It is a
**typed inventory** that any future refactor can grep, parse, and
verify against.

Architectural question this module answers
-------------------------------------------

Phase 5.4 / C-3B mandate asks: "Is app.state migration shallow
ownership rewiring, or hidden orchestration rewrite?"

The data in this module — generated from a complete inventory of
``from server import ...`` sites, startup phases, and side-effect
boundaries — gives the **evidence-based** answer:

> **HIDDEN ORCHESTRATION REWRITE — NOT shallow ownership rewiring.**
>
> Of the 15 distinct symbols bridged from ``server`` into the
> rest of the backend:
>   * **4** are true ownership roots that CAN migrate shallowly
>     (Tier A — ``db``, ``sio``, ``logger``, ``bitmotors_parser_instance``).
>   * **5** are pure helpers that need a MOVE-AND-REROUTE commit
>     (Tier B — ``audit``, ``aggregator``, ``serialize_doc``,
>     ``_round_money``, ``_smooth_eta_iso``, ``is_valid_movement``).
>   * **6+** are stateful services / orchestration entry points
>     embedded in ``server.py`` whose extraction is a multi-commit
>     refactor (Tier C — ``identity_runtime`` module, ``_run_auto_resolver``,
>     ``_persist_resolver_hits``, ``_vf_extract_vessels``,
>     ``_create_order_from_invoice``, ``ensure_shipment_stages``,
>     ``_require_customer``, ``_ensure_customer_seed``,
>     ``_get_stripe_config``, ``_tracking_enabled``).
>
> Additionally, ``_main_startup()`` contains 18+ ordered phases
> with implicit dependencies (notifications.init(db, sio) requires
> both db AND sio; worker_registry.register() calls are scattered
> across phases; mongo index creation depends on the canonical
> db handle). Moving to a clean ``app.state``-bound lifespan
> requires **explicit dependency ordering** — that's an
> orchestration rewrite, not a rewiring.

The 4 Tier-A roots can be addressed by a small C-4 commit. The
Tier-B/C work expands C-4 into a **multi-commit wave** —
exactly as the mandate signposted ("after this, bridge retirement
wave and side-effect formalization start being safe").

Why this is NOT app.state migration
------------------------------------

This module contains **no executable migration code**. It
contains only:

  * Typed dataclasses describing ownership roots.
  * Frozensets listing the canonical bridge surface
    (used by Phase 4 invariant tests as a regression guard).
  * Free-text classification (tier A/B/C, rationale, target
    location).
  * Cross-references to ``server.py`` line numbers as of
    Phase 5.4 / C-3B closure.

Nothing in this module is imported at runtime by ``server.py``,
by any router, or by any worker. It exists for human readers
and for the future C-4 commit's invariant tests
(``tests/test_phase5_4_c3b_topology_invariants.py``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# 1.  OWNERSHIP ROOTS  (per C-3B mandate §1)
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OwnershipRoot:
    """A runtime resource whose authoritative owner must be
    identifiable at every read/write site.

    The seven roots below are the load-bearing axes of the
    BIBI runtime. Every bridge (``from server import X``) maps
    onto exactly one of them. C-4 will retire bridges by
    moving the OWNER to a canonical location (``app.state``
    for connection/runtime roots; dedicated modules for service
    roots) and routing all readers through that location.
    """
    name: str
    current_owner: str               # where the value lives TODAY
    current_init_site: str           # file:line that creates the value
    target_owner: str                # where it will live POST-C4
    kind: str                        # "connection" | "runtime" | "config" | "orchestration" | "service" | "logging"
    notes: str = ""


OWNERSHIP_ROOTS: tuple[OwnershipRoot, ...] = (
    OwnershipRoot(
        name="db",
        current_owner="server.py module global + fastapi_app.state.db (mirror, Phase 4/C-2)",
        current_init_site="server.py:1917 (inside _main_startup)",
        target_owner="app.state.db (single-source)",
        kind="connection",
        notes=(
            "Motor AsyncIOMotorDatabase handle. Already MIRRORED to "
            "fastapi_app.state.db at startup (server.py:1942) under "
            "Phase 4 / C-2. The mirror is asserted-identical with the "
            "module global. C-4 task: route 38 readers to app.state.db "
            "via Depends(get_db); then remove the module global. "
            "TIER A — shallow rewiring feasible."
        ),
    ),
    OwnershipRoot(
        name="sio",
        current_owner="app.core.socket_runtime accessor (set_sio/get_sio); server.py creates the AsyncServer instance and immediately publishes it via the accessor",
        current_init_site=(
            "server.py:1640 (sio = socketio.AsyncServer(...)) + "
            "server.py:1648 (ASGIApp wrap) + "
            "server.py:~1652 (set_sio + identity assertion). "
            "All three sites are module-load time, in source order."
        ),
        target_owner="app.state.sio (mirror via lifespan, Phase 5.5+)",
        kind="runtime",
        notes=(
            "python-socketio AsyncServer instance. Phase 5.4 / C-4c: "
            "ownership made explicit via app.core.socket_runtime "
            "(set_sio at module-load, get_sio for all readers). "
            "All former `from server import sio` consumers "
            "(identity_runtime._sio, app.core.deps.get_sio) migrated "
            "to the accessor — identity preserved 1:1 (proved via "
            "in-process check + startup assertion). Split-brain "
            "prevention: identity assert ALSO runs before "
            "notifications.init(db, sio) so the NotificationService "
            "captured reference cannot diverge from the accessor. "
            "@sio.event handlers (connect, disconnect) and direct "
            "sio.emit() owner-side call sites in server.py are "
            "untouched (forbidden category)."
        ),
    ),
    OwnershipRoot(
        name="settings",
        current_owner="settings_service module (singleton via get_settings_service())",
        current_init_site="settings_service.py — boot-lazy via get_settings_service()",
        target_owner="app.state.settings",
        kind="config",
        notes=(
            "SettingsService singleton. Currently accessed via "
            "get_settings_service() factory function (lazy init). "
            "TIER A — but requires keeping the factory until "
            "lifespan-driven init confirms parity. "
            "Phase 5.4 / C-3A made app_settings.auth.google.clientId "
            "the SOLE source-of-truth — settings root is now clean."
        ),
    ),
    OwnershipRoot(
        name="integrations",
        current_owner="db.integration_configs via IntegrationConfigsRepository",
        current_init_site="repositories layer (app/repositories/integration_configs.py — instantiated per-call)",
        target_owner="app.state.repositories.integration_configs",
        kind="config",
        notes=(
            "Per-provider integration config registry (5 providers). "
            "After Phase 5.4 / C-3A, NO cross-collection mirror writes. "
            "Repository is instantiated per call; C-4 may move to "
            "app.state.repositories.integration_configs as a singleton."
        ),
    ),
    OwnershipRoot(
        name="repositories",
        current_owner="per-call instantiation in each caller (no central registry)",
        current_init_site="various — every router does Repo(db) on demand",
        target_owner="app.state.repositories.* (named-tuple or dataclass)",
        kind="service",
        notes=(
            "11 repositories exist as classes; NONE are currently "
            "singletons. Every call site does Repo(db).method(...). "
            "C-4 task: instantiate once at lifespan startup, bind "
            "to app.state.repositories. ZERO behaviour change "
            "because all repositories are stateless beyond the db handle. "
            "TIER A — shallow rewiring feasible."
        ),
    ),
    OwnershipRoot(
        name="worker_registry",
        current_owner="app.core.worker_registry.worker_registry (module singleton)",
        current_init_site="app/core/worker_registry.py:_global registry",
        target_owner="app.state.worker_registry (alias of existing singleton)",
        kind="orchestration",
        notes=(
            "Already a module singleton with a clean API "
            "(register/start_all/stop_all). 7 production workers "
            "registered. C-4 task: expose as app.state.worker_registry "
            "ALIAS (do NOT replace the module singleton — workers "
            "register at module-import time in some cases). "
            "TIER A — alias-only, behaviour unchanged."
        ),
    ),
    OwnershipRoot(
        name="audit",
        current_owner="server.audit() function + SecurityAuditRepository (Phase 5.4/C-1)",
        current_init_site="server.py:2814 (audit helper); app/repositories/security_audit.py",
        target_owner="app.state.repositories.security_audit (the repo) — the audit() wrapper retires post-stabilization",
        kind="service",
        notes=(
            "Security event audit (TTL-90d, write-only). Repository "
            "extracted in Phase 5.4 / C-1; the legacy server.audit() "
            "function is a thin wrapper retained for backward "
            "compatibility. Multiple lazy bridges (admin_identity, "
            "admin_ext_clients, identity_runtime). "
            "TIER B — helper migration: move audit() into a dedicated "
            "module or inline at call sites in a follow-up commit."
        ),
    ),
    # ─── Phase 5.4 / C-4a — `logger` retired ─────────────────────────────
    # The eighth ownership root entry ("logger") was REMOVED in C-4a:
    # logger ownership is now per-module via the standard
    # `logging.getLogger("bibi.<module>")` namespace pattern. The
    # ownership-roots table is intentionally smaller — every module
    # holding its own logger is the architecturally correct answer.
    # The C-4a proof-of-pattern commit retired both call sites in
    # one shot (admin_resolver.py + admin_ringostat.py); no future
    # `from server import logger` is permitted (regression-guarded
    # by `test_phase5_4_c4a_logger_retirement.py`).
)


# ═══════════════════════════════════════════════════════════════════════
# 2.  BRIDGE SURFACE INVENTORY  (per C-3B mandate §3)
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Bridge:
    """A single ``from server import X`` site, classified by:
       * ``symbol`` — the imported name
       * ``kind`` — one of CONNECTION_ROOT, RUNTIME_ROOT, CONFIG_ROOT,
                    SERVICE_FUNCTION, HELPER_FUNCTION, LOGGER, MODULE_REF
       * ``target`` — where the symbol moves in C-4 / later
       * ``tier`` — A (shallow rewire) / B (move-and-reroute) / C (refactor)
    """
    symbol: str
    kind: str
    tier: str
    target: str
    consumers_count: int     # how many files bridge this symbol
    notes: str = ""


BRIDGE_INVENTORY: tuple[Bridge, ...] = (
    # ─── Phase 5.4 / C-4j — `db` bridge RETIRED ─────────────────────────
    # The `db` bridge has been retired. Ownership remains in `server.py`
    # (set during `_main_startup()` immediately after
    # `db = db_client[DB_NAME]`) but the lazy import surface has been
    # fully replaced by the dedicated accessor module
    # `app.core.db_runtime` (set_db at module-load time / startup,
    # get_db for every reader). The FastAPI DI source itself
    # (`app/core/deps.py:get_db`) now delegates to
    # `db_runtime.get_db()` — the final non-DI consumer migration was
    # closed in C-4i and the DI-source swap is C-4j.
    #
    # Identity invariants:
    #   1. Post-startup: `server.db is db_runtime.get_db()` (asserted
    #      at the setter site in `_main_startup`).
    #   2. Post-startup: `Depends(get_db)` returns the same object
    #      that `server.db` holds — every request-scope reader sees
    #      the canonical Motor handle.
    #   3. Pre-startup: `db_runtime.get_db()` returns `None` — mirrors
    #      legacy `from server import db` semantics where `server.db`
    #      held its module-scope initial value before `_main_startup`.
    #
    # The Bridge entry is REMOVED from BRIDGE_INVENTORY entirely
    # (same retirement pattern as C-4a logger / C-4b parser / C-4c
    # sio: ownership becomes explicit through the accessor module,
    # so there is no longer a bridge to inventory). The `db`
    # OwnershipRoot entry above is KEPT because db remains a runtime
    # root — ownership has simply moved from a `from server import db`
    # lazy bridge to a dedicated accessor module.
    #
    # Regression guard: tests/test_phase5_4_c4j_db_bridge_finale.py
    # asserts `from server import db` AST count == 0 in the production
    # tree and `Depends(get_db)` request-scope behaviour is unchanged.

    # ─── Phase 5.4 / C-4c — `sio` bridge RETIRED ────────────────────────
    # The `sio` bridge has been retired. Ownership is now explicit via
    # `app.core.socket_runtime` — set_sio is invoked exactly once at
    # MODULE-LOAD time in server.py (right after
    # `sio = socketio.AsyncServer(...)` and the
    # `socketio.ASGIApp(sio, other_asgi_app=fastapi_app)` wrap, BEFORE
    # any `@sio.event` handler decorator runs). All former
    # `from server import sio` consumers (identity_runtime._sio,
    # app/core/deps.get_sio) now read via `socket_runtime.get_sio()`.
    #
    # Identity invariants (TWO assertions in production code):
    #   1. At setter site (module-load) — `get_sio() is sio` proves
    #      the accessor publishes the exact AsyncServer instance.
    #   2. Right before `notifications.init(db, sio)` (split-brain
    #      prevention) — `get_sio() is sio` proves the captured
    #      reference handed to NotificationService is the same object
    #      the accessor exposes. NotificationService init semantics
    #      are UNTOUCHED (param-passing 1:1, mandate-forbidden to
    #      rewrite); the invariant just guards against future drift.
    #
    # The Bridge entry is REMOVED from BRIDGE_INVENTORY (same pattern
    # as C-4a logger / C-4b parser retirements). The `sio` OwnershipRoot
    # entry above is KEPT because sio remains a runtime root — ownership
    # has simply moved from a `from server import sio` lazy bridge to
    # a dedicated accessor module. `@sio.event` handlers (connect,
    # disconnect) and direct `sio.emit(...)` owner-side call sites in
    # server.py are untouched (forbidden category). Regression guard:
    # tests/test_phase5_4_c4c_sio_retirement.py.
    # ─── Phase 5.4 / C-4b — `bitmotors_parser_instance` bridge RETIRED ──
    # The `bitmotors_parser_instance` bridge has been retired. Ownership
    # is now explicit via `app.core.deps.set_bitmotors_parser` (single
    # writer, invoked exactly once during `_main_startup` right after the
    # canonical `bitmotors_parser_instance = BitmotorsScraper(db)`
    # assignment under `if BITMOTORS_AVAILABLE`) and
    # `app.core.deps.get_bitmotors_parser` (any reader).
    #
    # Identity invariant (asserted at startup): after the setter call,
    # `get_bitmotors_parser() is bitmotors_parser_instance` — failing
    # fast if a future edit introduces a second writer or reorders the
    # bind. Pre-startup readers (or post-startup with
    # BITMOTORS_AVAILABLE=False) continue to receive `None`, exactly
    # mirroring the legacy bridge semantics.
    #
    # The Bridge entry is REMOVED from BRIDGE_INVENTORY entirely (mirror
    # of the C-4a logger retirement pattern: not a "retired placeholder",
    # because once ownership is explicit through the accessor module,
    # there is no longer a bridge to inventory). Regression guard:
    # tests/test_phase5_4_c4b_bitmotors_retirement.py.
    #
    # ─── Phase 5.4 / C-4a — `logger` bridge RETIRED ────────────────────
    # The `logger` bridge (admin_resolver + admin_ringostat) was the
    # proof-of-pattern target for C-4a. Both consumers now own their
    # logger via `logging.getLogger("bibi.<module>")`. The bridge is
    # removed from BRIDGE_INVENTORY entirely — there is no "retired
    # entry" placeholder because the architectural answer is "this
    # was never a runtime root, just a convenience import".
    #
    # Regression guard: tests/test_phase5_4_c4a_logger_retirement.py
    # asserts `from server import logger` has 0 production call sites
    # going forward. The C-3B live-grep test_4 also passes because
    # both inventory and live state agree (zero `logger` symbols on
    # either side).

    # ────── Tier B — helper migration (move + reroute) ──────
    # ─── Phase 5.4 / C-5a — stale shims RETIRED ────────────────────────
    # Four Tier-B `Bridge` entries were retired in C-5a (stale-shim
    # / pure-utility retirement batch):
    #
    #   * `serialize_doc`     — canonical lives in app/utils/serialization.py
    #                           (since Phase 5.2/C-1). 0 production
    #                           `from server import` sites at C-5 close;
    #                           the Bridge entry was vestigial documentation.
    #   * `_round_money`      — canonical lives in app/utils/money.py
    #                           (since Phase 5.2/C-1). 0 production
    #                           `from server import` sites; same shape
    #                           as serialize_doc — vestigial Bridge entry.
    #   * `_smooth_eta_iso`   — moved to app/utils/shipments.py in C-5a
    #                           with its exclusive constant
    #                           `JOURNEY_ETA_SMOOTH_ALPHA` and a
    #                           module-private verbatim copy of
    #                           `_source_category`. server.py keeps a
    #                           thin compatibility shim that delegates
    #                           1:1 (preserves the qualified-name
    #                           `server._smooth_eta_iso` for legacy
    #                           integration scripts; production AST
    #                           grep remains 0).
    #   * `is_valid_movement` — moved to app/utils/shipments.py in C-5a
    #                           with its exclusive constant
    #                           `JOURNEY_SPIKE_MAX_KM_PER_120S` and a
    #                           module-private verbatim copy of
    #                           `_haversine_km`. Same shim pattern as
    #                           `_smooth_eta_iso` above.
    #
    # Behaviour parity is asserted by
    # `tests/test_phase5_4_c5a_pure_utility_retirement.py` (representative
    # cases for ETA smoothing and movement validation; canonical-import
    # smoke test; stale-shim AST-grep == 0).
    #
    # Tier-B Bridge entries below are the post-C-5a residual surface:
    # `audit` (C-5c), `aggregator` (C-5b), `_STATIC_DIR` (DEFER:5.8).
    # ─── Phase 5.4 / C-5c — `audit` bridge RETIRED ───────────────────
    # The ``audit`` bridge has been retired. The async-callable
    # ownership is now explicit via ``app.core.audit_runtime``
    # (set_audit at module-load time / get_audit for every reader).
    # Same accessor-module pattern as C-4c (sio) — async side-effect
    # callable, with Q4 ("publish after set_db") satisfied implicitly
    # by the production call-graph (all 3 consumers are HTTP handlers
    # that run post-_main_startup; the worker callers inside server.py
    # use bare-name closures, out of C-5c scope).
    #
    # Identity invariant asserted at the setter site (module-load):
    # ``get_audit() is audit``. Mandatory 5-question micro-audit
    # came back with the expected callable-shape pattern:
    #   Q1=NO (async callable), Q2=YES (late-bound via closure on db),
    #   Q3=YES (writes via SecurityAuditRepository), Q4=YES (effective),
    #   Q5=YES (worker closure callers, but not via `from server import`).
    # See PHASE5_4_C5C_CLOSED.md §"Micro-audit results".
    #
    # 8-field schema invariant (H-5) preserved verbatim — the
    # callable's signature, async/await contract, best-effort
    # exception swallow, and 8-field write doc shape are all
    # unchanged. Three production consumers migrated from
    # `from server import audit` to
    # `from app.core.audit_runtime import get_audit`:
    #   * app/routers/admin_identity.py:_audit()
    #   * app/routers/admin_ext_clients.py:_audit()
    #   * app/services/identity_runtime.py:_audit_callable()
    #
    # The Bridge entry is REMOVED from BRIDGE_INVENTORY entirely
    # (same retirement pattern as C-4a / C-4b / C-4c / C-4j /
    # C-5a stale shims / C-5b aggregator).
    # ─── Phase 5.4 / C-5b — `aggregator` bridge RETIRED ──────────────
    # The ``aggregator`` bridge has been retired. Ownership is now
    # explicit via ``app.core.aggregator_runtime`` (set_aggregator at
    # module-load time / get_aggregator for every reader). Same
    # accessor-module pattern as C-4b (bitmotors_parser_instance),
    # C-4c (sio), and C-4j (db).
    #
    # Identity invariant asserted at the setter site (module-load):
    # ``get_aggregator() is aggregator``. Mandatory 5-question
    # micro-audit (per C-5b mandate correction) came back clean:
    # pure in-memory singleton, no late-bound runtime capture, no
    # worker references — see PHASE5_4_C5B_CLOSED.md §"Micro-audit
    # results" for the full table.
    #
    # The Bridge entry is REMOVED from BRIDGE_INVENTORY entirely
    # (same retirement pattern as C-4a / C-4b / C-4c / C-4j /
    # C-5a stale shims).
    #
    # Sole production consumer (admin_cache.py:42 — was
    # `from server import aggregator`) migrated to
    # `from app.core.aggregator_runtime import get_aggregator`.
    # The latent ``.records vs .store`` AttributeError bug at
    # admin_cache.py:57 is preserved verbatim (forbidden category:
    # "no behaviour changes" — bug fix belongs in a separate commit).

    # ────── Tier C — requires refactor before retirement ──────
    # ─── identity_runtime / _run_auto_resolver / _persist_resolver_hits
    #     — RETIRED in Phase 5.5 / G (2026-05-20) ──────────────────────
    # The identity-resolver CLUSTER (3 bridges) was retired in a single
    # focused commit (D1: keep cluster together). Cluster taxonomy:
    #
    #   * ``identity_runtime``        (MODULE_REF) — 3 router consumers
    #     migrated from ``from server import identity_runtime`` to
    #     ``from app.services.identity_runtime import identity_runtime``.
    #   * ``_run_auto_resolver``      (SERVICE_FUNCTION) — body MOVED
    #     verbatim from ``server.py:5657`` into
    #     ``IdentityRuntimeService.run_auto_resolver()``. The M-4 lazy
    #     bridge inside the service module has been retired.
    #   * ``_persist_resolver_hits``  (SERVICE_FUNCTION) — body MOVED
    #     verbatim from ``server.py:5677`` into
    #     ``IdentityRuntimeService.persist_resolver_hits()``. The M-5
    #     lazy bridge inside the service module has been retired.
    #
    # Three module-private helpers travelled with the cluster (never
    # were bridges, but they own the AutoResolver factory chain):
    #
    #   * ``_resolver_shipsgo_lookup``
    #   * ``_resolver_vf_search``
    #   * ``_get_auto_resolver``
    #
    # Two aux deps STAY on the server side, lazy-imported by the new
    # home at call time (registered as ``RESOLVER_DEP`` in
    # ``EXTRACTION_AUX_BRIDGES`` below):
    #
    #   * ``_external_container_lookup`` — ShipsGo / API lookup; belongs
    #     to the upcoming 5.5/H VesselFinder wave (tracking-providers
    #     cluster).
    #   * ``add_shipment_event`` — shipment-events writer with sio
    #     side-channel; belongs to the upcoming 5.5/I shipment
    #     orchestration wave.
    #
    # H-8 preserved: the legacy ``_AutoResolver`` (from
    # ``resolver_engine``) and ``ShipmentIdentityResolver`` (from
    # ``shipment_identity_resolver``) remain DISTINCT classes —
    # they now live side-by-side in the same service module but
    # are not merged.
    #
    # Behaviour parity asserted by
    # ``tests/test_phase5_5_g_identity_cluster.py`` — 12-assertion
    # contract (6 behavioural G1-G6 via the ``_resolve_helpers`` switch
    # point + 5 structural pins S1-S5 + 1 OpenAPI freeze O1). Suite
    # passes 7/12 pre-extraction (G1-G6 + O1) and 12/12 post-extraction.
    #
    # Bridge(symbol="identity_runtime", kind="MODULE_REF",          ...),  # RETIRED 5.5/G
    # Bridge(symbol="_run_auto_resolver", kind="SERVICE_FUNCTION",  ...),  # RETIRED 5.5/G
    # Bridge(symbol="_persist_resolver_hits", kind="SERVICE_FUNCTION", ...),# RETIRED 5.5/G
    # ─── Phase 5.5 / H — `_vf_extract_vessels` + `_external_container_lookup`
    #     CLUSTER RETIRED (2026-05-20) ──────────────────────────────────
    # Second cluster-retirement wave of the Phase 5.5 cycle (after 5.5/G).
    # Two bridges retired in ONE focused commit per D1 mandate:
    #
    #   * ``_vf_extract_vessels`` (HELPER_FUNCTION, Tier-C — this slot)
    #     The import alias ``extract_vessels_from_payload as
    #     _vf_extract_vessels`` on ``server.py:19194`` has been removed.
    #     Consumers now reach for the canonical no-underscore name
    #     ``extract_vessels_from_payload`` directly from the canonical
    #     home ``vesselfinder_scraper`` (the helper was ALREADY defined
    #     there since pre-Phase-5; the alias was vestigial).
    #     ``shipment_identity_resolver.py:406`` (the sole cross-module
    #     consumer) migrated from ``from server import _vf_extract_vessels``
    #     to ``from vesselfinder_scraper import extract_vessels_from_payload``
    #     (lazy local import shape preserved per D6).
    #
    #   * ``_external_container_lookup`` (RESOLVER_DEP, Tier C-aux — the
    #     5.5/G-registered EXTRACTION_AUX_BRIDGES entry below) — body
    #     MOVED verbatim from ``server.py:18798`` to
    #     ``app/services/tracking_providers.py`` as the public
    #     ``external_container_lookup`` (no underscore). The latent
    #     ``server.tracking_quick_track`` call site at ``server.py:18978``
    #     (which referenced an undefined symbol — would have raised
    #     ``NameError`` at runtime if the code path executed) is repaired
    #     by importing the canonical function from its new home — this
    #     is a documented intentional latent-bug repair, mirror of the
    #     5.5/E ``cabinet_financials.py`` repair pattern.
    #     The ``_external_container_lookup_callable()`` lazy-bridge
    #     accessor in ``app/services/identity_runtime.py`` (5.5/G-era)
    #     has been retired entirely; ``_resolver_shipsgo_lookup`` now
    #     imports the canonical function directly from
    #     ``app.services.tracking_providers``.
    #
    # D-mandate satisfaction (D1-D8 ACCEPT, user-locked at 5.5/H kickoff):
    #   * D1  cluster retirement in single focused commit ✅
    #   * D2  canonical homes: ``vesselfinder_scraper`` (already owner) +
    #         ``app/services/tracking_providers.py`` (NEW module) ✅
    #   * D3  no worker-lifecycle refactor — ``tracking_worker`` untouched
    #         ✅
    #   * D4  no provider-algorithm edits — ShipsGo V1 GET/POST +
    #         AfterShip fallback chain preserved 1:1 ✅
    #   * D5  no schema evolution — return-dict keys preserved 1:1 ✅
    #   * D6  no async orchestration changes — function signatures +
    #         ``httpx.AsyncClient`` context-manager shape preserved 1:1
    #         ✅
    #   * D7  golden suite FIRST — see
    #         ``tests/test_phase5_5_h_vesselfinder_cluster.py`` (12
    #         assertions; V1-V6 behavioural + S1-S5 structural + O1
    #         OpenAPI freeze). Suite passes 7/12 pre-extraction
    #         (V1-V6 + O1) and 12/12 post-extraction ✅
    #   * D8  no new provider integrations — ShipsGoEU / FleetMon / etc.
    #         NOT added ✅
    #
    # Inventory delta — see ``PHASE_5_5_H_RETIRED_BRIDGES`` below.
    #
    # Bridge(
    #     symbol="_vf_extract_vessels", kind="HELPER_FUNCTION", tier="C", ...
    # ),  # RETIRED Phase 5.5 / H
    # ─── Phase 5.5 / I — `ensure_shipment_stages` RETIRED (2026-05-20) ──
    # FINAL cluster-retirement wave of Phase 5.5 — closes the
    # disentangling cycle. After this wave, the only entry left in
    # ``BRIDGE_INVENTORY`` is the Tier-B ``_STATIC_DIR`` (Phase 5.8
    # territory). Three bridges retired together in ONE focused
    # commit per D1 mandate:
    #
    #   * ``ensure_shipment_stages`` (HELPER_FUNCTION, Tier-C — this slot)
    #     The full body has been moved verbatim from ``server.py:5472``
    #     to ``app/services/shipments.ensure_shipment_stages``. A thin
    #     compatibility shim remains in ``server.py`` (delegates 1:1)
    #     to keep the 8 in-file caller sites unchanged + qualified-name
    #     discoverability for legacy integration scripts — mirror of
    #     the C-5e ``get_current_stage`` / ``is_valid_movement`` shim
    #     pattern.  Sole cross-module consumer
    #     ``app/routers/admin_resolver.py:97`` migrated.
    #
    #   * ``add_shipment_event`` (RESOLVER_DEP, Tier C-aux — the
    #     5.5/G-registered EXTRACTION_AUX_BRIDGES entry below) — body
    #     MOVED verbatim from ``server.py:5539`` to
    #     ``app/services/shipments.add_shipment_event``. The two
    #     module-global references (``db``, ``sio``) that the legacy
    #     body relied on are now resolved via the call-time
    #     ``_db()`` / ``_sio()`` accessors at the canonical home
    #     (same pattern as ``app/services/identity_runtime.py``).
    #     Sole cross-module consumer
    #     ``app/services/identity_runtime.py:_add_shipment_event``
    #     migrated to the canonical home.
    #
    #   * ``generate_route`` (CUSTOMER_AUTH_DEP, Tier C-aux — the
    #     5.5/D-registered EXTRACTION_AUX_BRIDGES entry below) — body
    #     MOVED verbatim from ``server.py:5078`` to
    #     ``app/services/shipments.generate_route``. Sole cross-module
    #     consumer ``app/services/customers.py:generate_route`` lazy
    #     bridge migrated to the canonical home.
    #
    # Two helper deps (``_normalize_stage`` + ``build_default_stages``)
    # remain in ``server.py`` — they have 7+4 in-file callsites in the
    # orchestration shell and belong to the next decomposition era
    # (Phase 6 hardening / shell thinning). Reached via lazy local
    # imports inside ``ensure_shipment_stages`` at the canonical home;
    # registered below as the new ``SHIPMENTS_DEP`` extraction-aux
    # entries (kind=SHIPMENTS_DEP, tier=C-aux). Net
    # ``EXTRACTION_AUX_BRIDGES`` change: −2 (5.5/D + 5.5/G aux retired)
    # +2 (5.5/I-new SHIPMENTS_DEP) = ±0. Same cataloguing-completion
    # pattern as the 5.5/H ``_tracking_snapshot`` registration.
    #
    # D-mandate satisfaction (D1-D8 ACCEPT, user-locked at 5.5/I kickoff):
    #   * D1  cluster retirement in single focused commit ✅
    #   * D2  canonical home: NEW ``app/services/shipments.py`` ✅
    #   * D3  no worker-lifecycle refactor ✅
    #   * D4  no stage state-machine / route algorithm / event writer
    #         edits — bodies moved verbatim ✅
    #   * D5  no schema evolution — shipments doc, stages[], events[],
    #         $push/$slice/$set keys preserved 1:1 ✅
    #   * D6  no async orchestration changes — signatures + ``await
    #         db.shipments.update_one`` + ``await sio.emit`` + room
    #         format preserved 1:1 ✅
    #   * D7  golden suite FIRST —
    #         ``tests/test_phase5_5_i_shipments_orchestration.py``
    #         (14 assertions; V1-V8 behavioural + S1-S5 structural +
    #         O1 OpenAPI freeze) ✅
    #   * D8  no orchestration improvements ✅
    #
    # Inventory delta — see ``PHASE_5_5_I_RETIRED_BRIDGES`` below.
    #
    # PHASE-5 FINALE
    # ──────────────
    # After this wave, ``server.py`` holds **ZERO Tier-C
    # ``from server import …`` bridges**. Phase 5 disentangling
    # officially ends; Phase 6 (Production hardening) starts.
    #
    # Bridge(
    #     symbol="ensure_shipment_stages", kind="SERVICE_FUNCTION", tier="C", ...
    # ),  # RETIRED Phase 5.5 / I
    # ─── Phase 5.4 / C-5 — AST-discovered Tier-C shipment helpers ─────
    # Registered in C-5 planning (NOT moved). The regex-based bridge
    # grep in `test_phase5_4_c3b_topology_invariants` missed these
    # because they sit in a multi-line `from server import (...)`
    # block alongside `ensure_shipment_stages`. The AST-based grep
    # introduced in C-4j surfaced them. C-5 registers them as Tier-C
    # bridges (sibling of `ensure_shipment_stages`) with proposed
    # move target `app/utils/shipments.py` — the same destination
    # admin_shipments' own docstring acknowledges:
    #   "Phase 5 utils extraction will relocate them to
    #    app/utils/shipments.py"
    # The bridge-inventory count grows 17 → 19 as a result of
    # *discovery*, not new coupling. C-5e batched these for execution.
    #
    # ─── Phase 5.4 / C-5e CLOSED — 2 entries retired ─────────────────
    # The following two Tier-C / Tier-B-adjacent shipment-helper
    # Bridge entries were retired in C-5e (shipment-helper retirement
    # batch) and REMOVED from this inventory:
    #
    #   * ``get_current_stage`` — pure dict-walk helper. Verbatim
    #                             port to `app/utils/shipments.py`.
    #                             server.py keeps a thin compat shim
    #                             (10 internal callers via closure +
    #                             qualified `server.get_current_stage`
    #                             surface preserved).
    #   * ``serialize_journey`` — pure dict-builder. Verbatim port to
    #                             `app/utils/shipments.py`. Same
    #                             compat-shim shape. Calls
    #                             `app.utils.serialization.serialize_doc`
    #                             (canonical since C-1) + `get_current_stage`
    #                             (sibling) + private `__location_label`
    #                             copy (verbatim copy of
    #                             `server.get_location_label` —
    #                             reconciliation deferred to phase
    #                             5.5/5.6 along with the other
    #                             private copies created in C-5a).
    #
    # Mandatory 5-question micro-audit produced the expected
    # pure-helper pattern: Q1=server.py:5492/5583, Q2=2 prod
    # consumers (admin_shipments.py + admin_resolver.py via multi-line
    # imports), Q3=only `serialize_doc` + `get_location_label`,
    # Q4=NO db/sio/audit/emit/worker effects, Q5=YES pure
    # read/serialize. Verdict: PROCEED.
    #
    # Inventory size 19 → 17. Behaviour parity + 28-field schema
    # preservation asserted by
    # `tests/test_phase5_4_c5e_shipment_helpers.py`.
    #
    # ─── _create_order_from_invoice — RETIRED in Phase 5.5 / C (2026-05-19) ──
    # Order-creation orchestration moved to its canonical home at
    # ``app/services/orders.py`` (public entry point:
    # ``create_order_from_invoice``).  This was the LAST entry that
    # had a dual access shape (``from_server_import + qualified``)
    # and the LAST production consumer of ``import server`` inside
    # ``app/routers/payments.py`` — both shapes retired in the same
    # commit.
    #
    # All 3 legacy callers migrated:
    #   * ``app/routers/payments.py:658``  — qualified server.X (Stripe webhook recompute)
    #   * ``backend/legal_workflow.py:2158`` — from-server lazy WPS433 (deposit auto-convert)
    #   * ``backend/server.py:14469`` — in-file caller (invoice_mark_paid endpoint)
    #
    # The sibling pure helper ``_build_order_steps_from_invoice``
    # moved with the orchestration (still module-private inside
    # ``app/services/orders.py``).
    #
    # Behaviour parity asserted by
    # ``tests/test_phase5_5_c_order_creation_golden.py`` — the
    # 8-scenario golden suite (G1 Stripe path, G2 manual mark-paid,
    # G3 deposit auto-convert, G4 empty-items default workflow,
    # G5 null IDs, G6 notification failure resilience, G7 sio failure
    # resilience, G8 missing invoice.id early-return).  Suite ran
    # GREEN pre-extraction (label "pre-5.5/C") and re-runs GREEN
    # post-extraction (label "post-5.5/C") via a single
    # ``_resolve_helper`` switch point.
    #
    # Bridge(
    #     symbol="_create_order_from_invoice",
    #     kind="SERVICE_FUNCTION",
    #     tier="C",
    #     ...
    # ),  # RETIRED Phase 5.5 / C
    # ─── _require_customer + _ensure_customer_seed — RETIRED in Phase 5.5 / D (2026-05-19) ──
    # Customer-domain helpers moved to their canonical home at
    # ``app/services/customers.py`` (public entry points:
    # ``require_customer`` and ``ensure_customer_seed``).  Both
    # symbols had a single bridge shape (``from server import …``
    # lazy WPS433 inside ``cabinet_financials.py`` wrappers); after
    # 5.5/D the wrappers redirect to the new home via
    # ``from app.services.customers import …``.
    #
    # Sibling helper ``_seed_customer_financials`` (204 LOC, only
    # called internally by ``_ensure_customer_seed``) moved with the
    # seeder and stays module-private inside the new home.
    #
    # All callers migrated:
    #   * ``cabinet_financials.py:66``  — _require_customer wrapper redirected
    #   * ``cabinet_financials.py:72``  — _ensure_seed wrapper redirected
    #   * 21 in-file callers in ``server.py`` (5 favorites/cabinet
    #     auth gates + 14 ensure-seed sites + 2 misc) bulk-migrated
    #     to the bare public names via a single module-load import
    #     of ``require_customer`` / ``ensure_customer_seed``
    #
    # The auth core (``_resolve_bearer``) stays in ``server.py`` per
    # D2 mandate — registered under ``EXTRACTION_AUX_BRIDGES`` with
    # ``kind="CUSTOMER_AUTH_DEP"``. ``generate_route`` (shipment route
    # polyline helper, used by the seeder) gets the same treatment.
    #
    # Behaviour parity asserted by
    # ``tests/test_phase5_5_d_customer_helpers_golden.py`` — the
    # 8-scenario golden suite (G1 valid bearer, G2-G5 401 surface,
    # G6 cold-start collections, G7 idempotency, G8 customer-profile
    # shape).  Suite ran GREEN pre-extraction (label "pre-5.5/D")
    # and re-runs GREEN post-extraction (label "post-5.5/D") via a
    # single ``_resolve_helpers`` switch point.
    #
    # Bridge(
    #     symbol="_require_customer", kind="SERVICE_FUNCTION", tier="C", ...
    # ),  # RETIRED Phase 5.5 / D
    # Bridge(
    #     symbol="_ensure_customer_seed", kind="SERVICE_FUNCTION", tier="C", ...
    # ),  # RETIRED Phase 5.5 / D
    # ─── _get_stripe_config — RETIRED in Phase 5.5 / E (2026-05-19) ──
    # Stripe configuration resolver moved to its canonical home at
    # ``app/services/stripe_config.py`` (public entry point
    # ``get_stripe_config``).
    #
    # Step-1 audit discovery: the symbol was ALREADY out of ``server.py``
    # by the time 5.5/E started — it had been extracted to
    # ``app/routers/payments.py`` during Wave 1 (mechanical co-location
    # with Stripe webhook + checkout handlers). The ``BRIDGE_INVENTORY``
    # entry described above pointed at ``server.py`` as the def-site,
    # but the production AST showed the def in ``app/routers/payments.py``
    # — an **inventory drift** masked by the lazy-import indirection at
    # ``cabinet_financials.py:366`` (``from server import
    # _get_stripe_config`` — a bridge that ALWAYS raised
    # ``ImportError`` at runtime because ``server`` never exported the
    # symbol module-level; the surrounding ``except Exception`` silently
    # forced the cabinet checkout flow into stub mode).
    #
    # 5.5/E therefore combined three concerns in a single commit:
    #
    #   1. Architectural move — router → service module
    #      (``app/routers/payments.py`` was the wrong taxonomy slot;
    #      ``app/services/stripe_config.py`` is the canonical home for
    #      a cross-domain config helper consumed by 4 caller clusters).
    #   2. Public-name normalization — ``_get_stripe_config`` →
    #      ``get_stripe_config`` (mirror of 5.5/C
    #      ``create_order_from_invoice`` + 5.5/D ``require_customer``).
    #   3. Latent production bugfix — the broken
    #      ``cabinet_financials.py`` bridge was repaired by pointing it
    #      at the new canonical home. This is a **deliberate behaviour
    #      repair** (cabinet checkout flow now actually exercises
    #      Stripe), documented in ``PHASE5_5_E_STRIPE_CONFIG_CLOSED.md``
    #      section 4 ("Intentional behaviour repair scope").
    #
    # All 10 callers migrated:
    #   * 7 in-file callers in ``app/routers/payments.py`` (lines
    #     ~172, ~226, ~367, ~775, ~804, ~843 + stripe_public_config)
    #     bulk-renamed via single ``replace_all`` pass.
    #   * 2 ``server.py`` lazy imports — the Stripe-webhook handler
    #     at line ~13927 (now imports ``get_stripe_config`` from
    #     ``app.services.stripe_config`` directly; the two remaining
    #     payments-router helpers are imported from the router as
    #     before) + the legal-deposit checkout bridge at line ~12327.
    #   * 1 ``cabinet_financials.py`` site (the broken bridge —
    #     now imports from ``app.services.stripe_config``).
    #
    # No aux deps registered per D3=A. The helper is self-contained
    # over ``IntegrationConfigsRepository`` (single repository read,
    # pure-shape transformation, no env fallback). The previous
    # ``BRIDGE_INVENTORY`` notes "could go either way" between
    # service and ``app.state`` were resolved in favour of service
    # per the established 5.5 taxonomy.
    #
    # Behaviour parity asserted by
    # ``tests/test_phase5_5_e_stripe_config.py`` — 12-assertion suite
    # (6 structural pins, 3 behavioural goldens G7-G9, 1 latent-bug
    # repair pin, 1 inventory pin, 1 OpenAPI freeze).  Behavioural
    # tests use a single ``_resolve_helper`` switch point so the SAME
    # file runs UNCHANGED before AND after the cutover (label
    # ``pre-5.5/E`` resolves to the router-internal home; label
    # ``post-5.5/E`` resolves to the service home).
    #
    # Bridge(
    #     symbol="_get_stripe_config", kind="SERVICE_FUNCTION", tier="C", ...
    # ),  # RETIRED Phase 5.5 / E
    # ─── _tracking_enabled — RETIRED in Phase 5.5 / F2 (2026-05-19) ──
    # TRACKING_ENABLED env-flag reader moved to its canonical home at
    # ``app/services/tracking_config.py`` (public entry point
    # ``tracking_enabled``).  Same module as ``TrackingConfigService``
    # but a SIBLING function — NOT an accessor that consults service
    # state.  Pre-flight audit established the helper reads ``os.environ``
    # ONLY (no service lookup); the mandate's conditional clause
    # *"Если текущий helper читает module-global/service напрямую —
    # заменить на get_service()"* therefore did not apply; the strict
    # 1:1 verbatim port wins.
    #
    # Inventory-drift discovery (mirror of 5.5/E pattern):
    # ``consumers_count=1`` claimed only the cross-module bridge in
    # ``app/routers/admin_identity.py:67-69``, but the actual caller
    # topology was 5 sites:
    #   * 4 in-file callers in ``server.py`` (lines ~6502, ~6558,
    #     ~20020, ~20084) — VesselFinder scraper dispatch + tracking
    #     worker entry guards.
    #   * 1 cross-module bridge in ``app/routers/admin_identity.py``
    #     (a local ``def _tracking_enabled()`` wrapper that
    #     lazy-imported ``from server import _tracking_enabled as
    #     _te`` and was invoked at line 352 inside the admin
    #     tracking-status endpoint).
    #
    # Migration shape:
    #   * 4 in-file callers in ``server.py`` bulk-renamed via two
    #     ``replace_all`` passes (one for the indented form, one for
    #     the over-indented form).  Module-load import block added
    #     immediately after the retired def site.
    #   * The ``admin_identity.py`` local wrapper retired ENTIRELY
    #     (no compat shim per D4).  Replaced with a module-level
    #     ``from app.services.tracking_config import tracking_enabled``
    #     import; the single call site at line 352 (now 362) updated
    #     to the bare public name.
    #
    # No aux deps registered (D3 not explicit but implicit — helper
    # is a pure env reader with no cross-module coupling).
    #
    # Behaviour parity asserted by
    # ``tests/test_phase5_5_f2_tracking_enabled.py`` — 9-test contract
    # (4 behavioural G1-G4 + 4 structural pins + 1 OpenAPI freeze).
    # G2 + G4 are parametrized (8 disabled-token variants + 7
    # malformed-value variants) — 22 executed test cases in total.
    # Suite file is identical pre- and post-cutover via the
    # ``_resolve_helper`` switch point.
    #
    # Bridge(
    #     symbol="_tracking_enabled", kind="SERVICE_FUNCTION", tier="C", ...
    # ),  # RETIRED Phase 5.5 / F2
    Bridge(
        symbol="_STATIC_DIR",
        kind="HELPER_FUNCTION",
        tier="B",
        target="app/core/paths.py (or similar — single module that owns FS paths)",
        consumers_count=1,
        notes="content router uses it. Trivial constant.",
    ),
    # ─── duplicate `is_valid_movement` entry from C-3B inventory draft
    # was REMOVED in C-4a (doc-hygiene fix; the symbol is already
    # declared above at the first Tier-B entry). The deletion has no
    # behavioural effect — the unique-symbols set was already 21 at
    # C-3B close because frozenset deduplicated.
)


# ─────────────────────────────────────────────────────────────────────
# Phase 5.5/B — Calculator engine EXTRACTION-AUX bridges
# ─────────────────────────────────────────────────────────────────────
# Separate tuple from BRIDGE_INVENTORY. These ARE new `from server
# import X` symbols introduced when the calculator engines moved
# byte-identically from server.py to app/services/calculator.py
# (2026-05-19). Their function bodies reference ~43 module-level
# constants and helpers that still live in server.py — per mandate,
# extracting them would be premature (no domain disentangling in
# 5.5/B). The new service module imports them at module load.
#
# Why a SEPARATE tuple (not appended to BRIDGE_INVENTORY)?
#   * The 16 prior-wave tests (C-4j, C-5, C-5a, C-5b, C-5c, C-5e, C-5f,
#     C-5_tier_b_plan, C-5e shipment helpers, etc.) all hard-pin
#     ``len(BRIDGE_INVENTORY)`` to their own wave's expected number.
#     Appending 43 entries to BRIDGE_INVENTORY would break every
#     single one of those count pins, requiring 16 separate
#     compatible-pin updates.
#   * These bridges are structurally different — they are NOT
#     "leftover Tier-C coupling that 5.5 must retire". They are the
#     EXPECTED ARTIFACT of a domain extraction whose constants/helpers
#     deliberately stayed put. Their retirement is bound to a
#     follow-on wave that moves the entire calculator cluster
#     (constants + helpers + seed routine) at once.
#   * Topology audit ergonomics: when a future engineer wants to
#     know "what coupling is left to retire as part of strangler-fig
#     progress", they look at BRIDGE_INVENTORY (still 11). When they
#     want "what coupling is structurally REQUIRED by extracted-but-
#     not-fully-relocated services", they look at
#     EXTRACTION_AUX_BRIDGES.
#
# The C-5f / C-3B live-AST audits compare the LIVE AST set against
# the UNION of BRIDGE_INVENTORY ∪ EXTRACTION_AUX_BRIDGES, so the
# "no silent new coupling" invariant still holds.
#
# All entries share:
#   * tier="C-aux" (new tier marker)
#   * kind="CALC_ENGINE_DEP"
#   * target="app/services/calculator.py (will retire when the
#     calculator constants/helpers cluster moves with the calculator
#     domain — Phase 5.5/B-deep or 5.6.X)"
#   * consumers_count=1 (only app/services/calculator.py)
#
# Post-Wave-2 (2026-05-20): the ENTIRE CALC_ENGINE_DEP cluster is now
# retired from EXTRACTION_AUX_BRIDGES:
#   * 38 PURE_CONSTANT + AUCTION_TIERED_FEES + 2 ``_tiered_buyer_fee*``
#     helpers moved to canonical homes
#     (``app/core/calculator_constants.py`` + ``app/services/calculator_pure.py``).
#   * 2 SERVER_STATE-coupled helpers (``_ensure_calculator_seed``,
#     ``_load_calc_config``) are no longer ``from server import``-coupled
#     either — calculator.py reaches them via lazy ``import server``
#     inside engine function bodies (cycle-break pattern; tracked under
#     test_phase6_3_b_ast_topology._IMPORT_SERVER_WAVE_2_ALLOWANCE).
#     They retire from server.py entirely in Wave 3.
#
# Net AUX delta: 44 → 2 (only ``_resolve_bearer`` CUSTOMER_AUTH_DEP +
# ``_tracking_snapshot`` TRACKING_PROVIDERS_DEP remain).
#
# See ``PHASE_6_5_WAVE_2_RETIRED_BRIDGES`` below for the audit-trail.
EXTRACTION_AUX_BRIDGES: tuple[Bridge, ...] = (
    *(  # ─── Phase 5.5/B — calculator engine extraction-aux ──
        # FULLY RETIRED in Wave 1 + Wave 2 (2026-05-20). The entire
        # 43-symbol CALC_ENGINE_DEP cluster is gone:
        #   * ``_find_route_amount`` (Wave 1) → calculator_pure.py
        #   * 38 PURE_CONSTANT + AUCTION_TIERED_FEES (Wave 2) →
        #     app/core/calculator_constants.py
        #   * 2 ``_tiered_buyer_fee*`` (Wave 2) → calculator_pure.py
        #   * 2 SERVER_STATE-coupled helpers
        #     (``_ensure_calculator_seed``, ``_load_calc_config``)
        #     are no longer ``from server import``-coupled — they
        #     are reached via the Wave-2 cycle-break ``import server``
        #     allowance and will retire from server.py entirely in Wave 3.
        # See PHASE_6_5_WAVE_1_RETIRED_BRIDGES + PHASE_6_5_WAVE_2_RETIRED_BRIDGES.
    ),
    # ─── Phase 5.5/D — customer-helpers extraction-aux (2 entries) ──
    Bridge(
        symbol="_resolve_bearer",
        kind="CUSTOMER_AUTH_DEP",
        tier="C-aux",
        target=(
            "app/services/customers.py (lazy bridge — token logic "
            "stays in server.py per D2 mandate; retirement deferred "
            "to a future auth-core wave because mandate explicitly "
            "forbids any token-logic restructuring in 5.5/D)"
        ),
        consumers_count=1,
        notes=(
            "Phase 5.5/D extraction-aux: auth core resolver. "
            "Imported lazily by app/services/customers.py (inside the "
            "thin async _resolve_bearer wrapper) from server.py. "
            "Used by ``require_customer`` to translate Bearer token → "
            "customer doc. Mandate forbids inlining bearer-resolution "
            "in 5.5/D (would touch token logic) and forbids moving "
            "_resolve_bearer itself (scope creep). Same pattern as "
            "the 5.5/B calculator constants — defer the aux "
            "retirement to a focused future wave."
        ),
    ),
    # ─── Phase 5.5/D — customers extraction-aux ──
    # ``generate_route`` (CUSTOMER_AUTH_DEP) — RETIRED in 5.5/I as part
    # of the shipments-orchestration cluster retirement. Body moved
    # verbatim from ``server.py:5078`` to
    # ``app/services/shipments.generate_route``. Sole consumer
    # ``app/services/customers.py:generate_route`` lazy bridge migrated
    # to the canonical home. See ``PHASE_5_5_I_RETIRED_BRIDGES``.
    #
    # Bridge(
    #     symbol="generate_route", kind="CUSTOMER_AUTH_DEP",
    #     tier="C-aux", ...
    # ),  # RETIRED Phase 5.5 / I
    # ─── Phase 5.5/G — identity-resolver cluster extraction-aux ──
    # ``_external_container_lookup`` (RESOLVER_DEP) — RETIRED in 5.5/H
    # together with ``_vf_extract_vessels`` as the VesselFinder cluster
    # extraction. Body moved verbatim from ``server.py:18798`` to
    # ``app/services/tracking_providers.py`` as the public
    # ``external_container_lookup``. The lazy-bridge accessor
    # ``_external_container_lookup_callable()`` in
    # ``app/services/identity_runtime.py`` has been retired entirely.
    # See ``PHASE_5_5_H_RETIRED_BRIDGES`` for the full audit-trail.
    #
    # Bridge(
    #     symbol="_external_container_lookup", kind="RESOLVER_DEP",
    #     tier="C-aux", ...
    # ),  # RETIRED Phase 5.5 / H
    #
    # ─── Phase 5.5/H — tracking-providers extraction-aux (1 entry) ──
    Bridge(
        symbol="_tracking_snapshot",
        kind="TRACKING_PROVIDERS_DEP",
        tier="C-aux",
        target=(
            "app/services/tracking_config.py (sibling-module accessor "
            "for the default-empty ``TrackingConfigSnapshot()`` "
            "cold-start fallback; retirement deferred to the dedicated "
            "tracking-config wave or Phase 6 cold-start consolidation)"
        ),
        consumers_count=1,
        notes=(
            "Phase 5.5/H extraction-aux: cold-start fallback accessor "
            "for the default-empty ``TrackingConfigSnapshot()``. Imported "
            "lazily by ``app/services/tracking_providers.py`` inside "
            "the ``_snapshot()`` helper as a fallback when "
            "``get_service()`` returns ``None`` (pre-bind). Mandate D3 "
            "(no worker-lifecycle refactor) + D6 (no async orchestration "
            "changes) forbid restructuring the snapshot lifecycle in "
            "5.5/H — registered as aux-bridge so the live-AST invariant "
            "holds. The legacy helper itself still lives at "
            "``server.py:18659`` because it encodes the cold-start "
            "fallback shape ``TrackingConfigSnapshot()`` "
            "(default-constructed = all keys ``None``); moving that "
            "fallback constructor into 5.5/H would tangle the snapshot "
            "lifecycle with the providers module — out of scope per D3."
        ),
    ),
    #
    # ─── Phase 5.5/G — identity-resolver cluster extraction-aux ──
    # ``add_shipment_event`` (RESOLVER_DEP) — RETIRED in 5.5/I as part
    # of the shipments-orchestration cluster retirement. Body moved
    # verbatim from ``server.py:5539`` to
    # ``app/services/shipments.add_shipment_event``. Sole consumer
    # ``app/services/identity_runtime.py:_add_shipment_event`` rewired
    # to the canonical home. See ``PHASE_5_5_I_RETIRED_BRIDGES``.
    #
    # Bridge(
    #     symbol="add_shipment_event", kind="RESOLVER_DEP",
    #     tier="C-aux", ...
    # ),  # RETIRED Phase 5.5 / I
    #
    # ─── Phase 5.5/I — shipments-orchestration extraction-aux (2 entries) ──
    # RETIRED Phase 6.2.ACTUAL (2026-05-20) — Shell Thinning execution.
    # Both ``_normalize_stage`` and ``build_default_stages`` were moved
    # VERBATIM from ``server.py`` to ``app/utils/shipments.py`` (sibling
    # of ``get_current_stage`` + ``serialize_journey``). server.py keeps
    # thin compat shims (<10 LOC each, body = single ``from … import …``
    # + ``return ...``) for the in-file callsites (5 for
    # _normalize_stage, 2 for build_default_stages). The 2 constants
    # ``JOURNEY_STAGE_TYPES`` + ``JOURNEY_STAGE_STATUSES`` travelled
    # with their owner; server.py re-exports them at module-load for
    # qualified-name discoverability. The cross-module callsite at
    # ``app/services/shipments.py:ensure_shipment_stages`` was migrated
    # to reach the canonical home directly (NO bridge to server.py).
    # See ``PHASE_6_2_RETIRED_BRIDGES`` below for the formal retirement
    # ledger. Net inventory delta: EXTRACTION_AUX_BRIDGES 47 → 45.
    #
    # Bridge(
    #     symbol="_normalize_stage", kind="SHIPMENTS_DEP", tier="C-aux",
    #     target="app/utils/shipments.py", ...
    # ),  # RETIRED Phase 6.2.ACTUAL
    #
    # Bridge(
    #     symbol="build_default_stages", kind="SHIPMENTS_DEP", tier="C-aux",
    #     target="app/utils/shipments.py", ...
    # ),  # RETIRED Phase 6.2.ACTUAL
)
"""Phase 5.5/B calculator engine extraction-auxiliary bridges. See
the comment block above for rationale and retirement contract."""


# ═══════════════════════════════════════════════════════════════════════
# 3.  STARTUP DEPENDENCY GRAPH  (per C-3B mandate §2)
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StartupPhase:
    """A single ordered phase inside ``lifespan()`` / ``_main_startup()``.

    ``requires`` lists the ownership roots that must already be alive
    before this phase can run. Used by the eventual C-4 lifespan
    rewire to compute a topologically-valid bootstrap order.
    """
    order: int
    name: str
    site: str                    # file:line
    requires: tuple[str, ...]    # names of ownership roots
    side_effects: tuple[str, ...]
    notes: str = ""


STARTUP_PHASES: tuple[StartupPhase, ...] = (
    StartupPhase(
        order=1,
        name="mongo_client_open",
        site="server.py:1916",
        requires=(),
        side_effects=("creates db handle", "creates db_client",
                      "binds module globals"),
        notes="Foundational. Everything below requires `db`.",
    ),
    StartupPhase(
        order=2,
        name="app_state_mirror_db",
        site="server.py:1942",
        requires=("db",),
        side_effects=("fastapi_app.state.db <- db",
                      "fastapi_app.state.mongo_client <- db_client"),
        notes="Phase 4 / C-2 parallel mirror; no migration yet.",
    ),
    StartupPhase(
        order=3,
        name="notifications_init",
        site="server.py:1953-1957",
        requires=("db", "sio"),
        side_effects=("notifications.service binds db+sio",
                      "seeds 6 rules + 33 email templates",
                      "registers payment_reminder worker"),
        notes="First side-effect-rich phase. Both ownership roots needed.",
    ),
    StartupPhase(
        order=4,
        name="provider_pressure_engine",
        site="server.py:~1990",
        requires=("db", "event_bus_implicit"),
        side_effects=("wires provider_stats engine to event bus",
                      "subscribes to order_started / order_finished"),
        notes=(
            "event_bus is an IMPLICIT root — not currently tracked in "
            "OWNERSHIP_ROOTS because it lives inside notifications.service. "
            "C-4 inventory candidate."
        ),
    ),
    StartupPhase(
        order=5,
        name="bidmotors_live_only",
        site="server.py:~2025",
        requires=("db",),
        side_effects=("bitmotors_parser_instance = BidMotorsParser(...)",
                      "global re-binds"),
        notes="Module global re-binding inside startup — C-4 should "
              "move this to lifespan-bound state.",
    ),
    StartupPhase(
        order=6,
        name="watchlist_live_poll_worker",
        site="server.py:~2050",
        requires=("db", "worker_registry"),
        side_effects=("registers worker watchlist_live_poll",),
    ),
    StartupPhase(
        order=7,
        name="westmotors_lemon_syncs",
        site="server.py:2160-2240",
        requires=("db",),
        side_effects=("starts WestMotorsSync + LemonSync",),
    ),
    StartupPhase(
        order=8,
        name="ringostat_cron_worker",
        site="server.py:~2260",
        requires=("db", "worker_registry"),
        side_effects=("registers worker ringostat_cron",),
    ),
    StartupPhase(
        order=9,
        name="shipping_tracking_worker",
        site="server.py:~2280",
        requires=("db", "worker_registry"),
        side_effects=("registers worker tracking_worker",),
    ),
    StartupPhase(
        order=10,
        name="mongo_indexes_unique_plus_ttl",
        site="server.py:~2348",
        requires=("db",),
        side_effects=("unique indexes on shipments/deals/staff",
                      "TTL indexes on audit/vf_meta/vf_raw/ext_nonces/vct",
                      "ext_clients indexes"),
    ),
    StartupPhase(
        order=11,
        name="seed_staff_accounts",
        site="server.py:~2575",
        requires=("db",),
        side_effects=("seeds admin/manager/team_lead from env or defaults",
                      "purges legacy 'owner' / 'master_admin' rows"),
    ),
    StartupPhase(
        order=12,
        name="seed_blog_articles",
        site="server.py:~2360",
        requires=("db",),
        side_effects=("seeds 8 blog articles if collection empty",),
    ),
    StartupPhase(
        order=13,
        name="security_hooks_register",
        site="server.py:~2375",
        requires=("db",),
        side_effects=("nonce replay-guard hook",
                      "HMAC failure audit hook",
                      "ext_client lookup hook"),
    ),
    StartupPhase(
        order=14,
        name="identity_resolver_worker",
        site="server.py:~2390",
        requires=("db", "worker_registry"),
        side_effects=("registers worker resolver_worker",),
    ),
    StartupPhase(
        order=15,
        name="transfer_detector_worker",
        site="server.py:~2420",
        requires=("db", "worker_registry"),
        side_effects=("registers worker transfer_detector",),
    ),
    StartupPhase(
        order=16,
        name="ops_guardian",
        site="server.py:~2455",
        requires=("db", "worker_registry"),
        side_effects=("registers worker ops_guardian (alerts + auto-heal)",),
    ),
    StartupPhase(
        order=17,
        name="refund_eligibility_cron",
        site="server.py:~2475",
        requires=("db",),
        side_effects=("legal_workflow.refund_cron scheduled (every 6h)",),
    ),
    StartupPhase(
        order=18,
        name="audit_events_indexes",
        site="server.py:2482",
        requires=("db",),
        side_effects=("AuditEventsRepository.ensure_indexes()",),
    ),
    StartupPhase(
        order=19,
        name="invoice_templates_seed",
        site="server.py:2490",
        requires=("db",),
        side_effects=("financial_breakdown.ensure_indexes() + 2 templates seed",),
    ),
    StartupPhase(
        order=20,
        name="payments_indexes",
        site="server.py:2500",
        requires=("db",),
        side_effects=("payments_tracking.ensure_indexes()",),
    ),
    StartupPhase(
        order=21,
        name="c3a_google_clientid_backfill",      # NEW (Phase 5.4 / C-3A)
        site="server.py:~2510",
        requires=("db", "settings"),
        side_effects=(
            "if app_settings.auth.google.clientId empty AND "
            "integration_configs.google_oauth.credentials.clientId set: "
            "copies legacy value once into app_settings",
        ),
        notes="Added in Phase 5.4 / C-3A. Idempotent; runs at most once.",
    ),
    StartupPhase(
        order=22,
        name="worker_registry_start_all",
        site="server.py:~2555",
        requires=("worker_registry", "db", "sio"),
        side_effects=("starts all registered workers (7 total)",),
        notes=(
            "FINAL phase of _main_startup. All preceding worker_registry.register() "
            "calls collapse into this single supervised start_all()."
        ),
    ),
    # Hooks orchestrated AFTER _main_startup by lifespan()
    StartupPhase(
        order=23,
        name="webhook_events_index",
        site="server.py:14345 (called by lifespan)",
        requires=("db",),
        side_effects=("stripe_webhook_events.event_id unique index ensured",),
    ),
    StartupPhase(
        order=24,
        name="services_startup_hook",
        site="server.py:14483 (called by lifespan)",
        requires=("db",),
        side_effects=("misc service-catalog warmups",),
    ),
    StartupPhase(
        order=25,
        name="vin_search_engine",
        site="server.py:18308 (called by lifespan)",
        requires=("db",),
        side_effects=("starts background VIN requeue task",),
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# 4.  TIER GROUPINGS  (for C-4 commit-by-commit planning)
# ═══════════════════════════════════════════════════════════════════════

TIER_A_SHALLOW_REWIRING: frozenset[str] = frozenset()
"""Bridges that can move to ``app.state`` without rewriting any
business logic. Phase 5.4 / C-4a closed: ``logger`` retired.
Phase 5.4 / C-4b closed: ``bitmotors_parser_instance`` retired.
Phase 5.4 / C-4c closed: ``sio`` retired (accessor-module ownership
in `app.core.socket_runtime`; identity preserved across canonical
global, ASGIApp wrap, and all consumers).
Phase 5.4 / C-4j closed: ``db`` retired — the DI source
(``app/core/deps.py:get_db``) now delegates to
``app.core.db_runtime.get_db()``. ``server.db`` remains the canonical
ownership root (set during ``_main_startup()``) but no longer
appears in any production ``from server import …`` statement.
Tier-A is now empty — every former Tier-A bridge has been retired
through a dedicated accessor module (deps / socket_runtime /
db_runtime), and the remaining bridge surface is Tier-B (helper
move-and-reroute) plus Tier-C (business-logic refactor)."""


TIER_B_MOVE_AND_REROUTE: frozenset[str] = frozenset({
    "_STATIC_DIR",
})
"""Bridges whose definitions need to physically move out of
``server.py`` to a dedicated module BEFORE the import-path swap.
The functions themselves are pure (or near-pure); the work is
filesystem-level. Estimated 1 commit per family in C-4 / C-5.

Phase 5.4 / C-5a closed (4 retirements):
  * ``serialize_doc``     — already in app/utils/serialization.py
                            (vestigial Bridge entry removed).
  * ``_round_money``      — already in app/utils/money.py
                            (vestigial Bridge entry removed).
  * ``_smooth_eta_iso``   — moved to app/utils/shipments.py
                            (1:1 verbatim port + exclusive constant
                            + module-private __source_category copy).
                            server.py keeps a thin compat shim.
  * ``is_valid_movement`` — moved to app/utils/shipments.py
                            (1:1 verbatim port + exclusive constant
                            + module-private __haversine_km copy).
                            server.py keeps a thin compat shim.
Phase 5.4 / C-5b closed (1 retirement):
  * ``aggregator``        — runtime accessor module created at
                            app/core/aggregator_runtime.py
                            (set_aggregator / get_aggregator pattern,
                            mirror of C-4b / C-4c). Identity invariant
                            asserted at module-load setter site.
                            Sole consumer (admin_cache) migrated.
Phase 5.4 / C-5c closed (1 retirement):
  * ``audit``             — runtime accessor module created at
                            app/core/audit_runtime.py
                            (set_audit / get_audit pattern, mirror
                            of C-4c sio — async callable shape).
                            Identity invariant asserted at the
                            module-load setter site. Three consumers
                            migrated (admin_identity, admin_ext_clients,
                            identity_runtime). 8-field schema
                            preserved verbatim (H-5).
Frozenset size: 7 → 3 (C-5a) → 2 (C-5b) → 1 (C-5c)."""


TIER_C_REQUIRES_REFACTOR: frozenset[str] = frozenset({
    # Phase 5.5 / I CLOSED (2026-05-20) — ``ensure_shipment_stages`` was
    # retired (body moved to ``app/services/shipments.py``; thin shim
    # remains in ``server.py``). With this retirement, **ZERO Tier-C
    # bridges remain in BRIDGE_INVENTORY** — the Phase-5 disentangling
    # endpoint reached. Phase 6 (Production hardening) starts.
    #
    # Earlier Phase 5.5 / H CLOSED (2026-05-20) — ``_vf_extract_vessels``
    # was retired (VesselFinder cluster).
    # Earlier Phase 5.5 / G CLOSED (2026-05-20) — identity-resolver
    # cluster (3 bridges) retired together.
    # Earlier Phase 5.4 closed the Tier-C count from 12 → 2.
})
    # Phase 5.4 / C-5e CLOSED — `get_current_stage` and
    # `serialize_journey` were retired from this set (verbatim
    # moves to `app/utils/shipments.py`; server.py keeps thin
    # compat shims). Tier-C count 12 → 10.
    # Phase 5.5 / C CLOSED (2026-05-19) — `_create_order_from_invoice`
    # was retired from this set. Tier-C count 10 → 9.
    # Phase 5.5 / D CLOSED (2026-05-19) — `_require_customer` AND
    # `_ensure_customer_seed` were retired from this set (verbatim
    # moves to `app/services/customers.py`; private sibling
    # `_seed_customer_financials` moved with the seeder).
    # Tier-C count 9 → 7.
    # Phase 5.5 / E CLOSED (2026-05-19) — `_get_stripe_config` was
    # retired from this set (Wave-1 router-internal placement
    # corrected; moved from `app/routers/payments.py` to canonical
    # service home `app/services/stripe_config.py` as
    # `get_stripe_config`; latent ImportError bridge in
    # `cabinet_financials.py` repaired).  Tier-C count 7 → 6.
    # Phase 5.5 / F2 CLOSED (2026-05-19) — `_tracking_enabled` was
    # retired from this set (env-flag reader moved verbatim from
    # `server.py:2963` to `app/services/tracking_config.py` as the
    # public `tracking_enabled`; 5 callers migrated — 4 in-file in
    # server.py + 1 cross-module wrapper in admin_identity.py
    # retired entirely; inventory-drift surfaced — claimed 1
    # consumer, actual 5).  Tier-C count 6 → 5.
    # Phase 5.5 / G CLOSED (2026-05-20) — the identity-resolver
    # CLUSTER (3 symbols: `identity_runtime`, `_run_auto_resolver`,
    # `_persist_resolver_hits`) was retired from this set as ONE
    # focused commit (D1: keep cluster together).  Bodies moved
    # verbatim from `server.py:5657`/`server.py:5677` to
    # `IdentityRuntimeService.run_auto_resolver()` /
    # `.persist_resolver_hits()`; 3 module-private helpers travelled
    # with the cluster (_resolver_shipsgo_lookup, _resolver_vf_search,
    # _get_auto_resolver); 2 aux deps stayed on server side as
    # RESOLVER_DEP entries (_external_container_lookup,
    # add_shipment_event).  Tier-C count 5 → 2.
    # Phase 5.5 / I CLOSED — TIER-C count 2 → 0 (final disentangling
    # endpoint). The frozenset is now intentionally empty; see the
    # leading comment block at the top of this definition.
"""Bridges whose retirement requires a deeper refactor of business
logic (side-effects, auth gates, multi-collection transitions).
Each is a multi-commit effort in C-5 or later. The C-3B mandate
forbids touching these in this commit."""


# ═══════════════════════════════════════════════════════════════════════
# 5.  ARCHITECTURAL VERDICT  (per C-3B mandate question)
# ═══════════════════════════════════════════════════════════════════════

ARCHITECTURAL_VERDICT: str = """
HIDDEN ORCHESTRATION REWRITE — NOT shallow ownership rewiring.

Evidence (as of Phase 5.4 / C-5 planning closed):

(a) Bridge surface is 11 distinct symbols across the production tree
    (post-C-5e, frozen by C-5f consolidation). Progression history:
       18 (pre-C-4j)
    →  17 (post-C-4j db retirement)
    →  19 (post-C-5 planning — DISCOVERY: AST-grep audit surfaced
                two previously unregistered Tier-C shipment helpers
                `get_current_stage`, `serialize_journey` hidden
                inside multi-line tuple imports; NOT new coupling)
    →  15 (post-C-5a — four pure-utility / stale-shim bridges
                retired: `serialize_doc`, `_round_money`,
                `_smooth_eta_iso`, `is_valid_movement`)
    →  14 (post-C-5b — `aggregator` retired via accessor-module
                pattern `app/core/aggregator_runtime.py`)
    →  13 (post-C-5c — `audit` retired via async accessor-module
                pattern `app/core/audit_runtime.py`)
    →  11 (post-C-5e — `get_current_stage`, `serialize_journey`
                retired via verbatim 1:1 port to
                `app/utils/shipments.py` + server.py compat shims)
    →  C-5f: consolidation verdict (this commit) — NO retirement;
             registers the parallel qualified-usage bridge surface
             (`QUALIFIED_USAGE_BRIDGES`: 6 production sites across
             3 files — `calculations.py`, `payments.py`,
             `admin_integrations.py`) discovered by the C-5f AST
             re-audit, and freezes the Phase 5.5 boundary
             (`PHASE_5_5_BOUNDARY`: 14 symbols across both shapes)
             + Phase 5.8 boundary (`PHASE_5_8_BOUNDARY`:
             `_STATIC_DIR` only).
    ZERO remaining bridges are shallow-rewire candidates
    (Tier A is empty: `frozenset()`). The 11 remaining split:
       •  1 Tier-B (`_STATIC_DIR`, target Phase 5.8 bootstrap
          reshuffle)
       • 10 Tier-C (Phase 5.5 — orchestration disentangling +
          legacy module migration prep).

(b) Startup orchestration is 25 ordered phases with implicit
    dependencies. Of those, 22 require `db`, 4 require both `db` AND
    `sio`, 8 require `worker_registry`. A clean app.state-bound
    lifespan must encode this dependency graph EXPLICITLY — that is
    an orchestration rewrite, not a rewiring.

(c) All four Tier-A runtime singletons are now bound inside server.py
    and published through dedicated accessor modules:
    `bitmotors_parser_instance` via `app.core.deps` (C-4b),
    `sio` via `app.core.socket_runtime` (C-4c), and `db` via
    `app.core.db_runtime` (C-4e..C-4j wave). Each has a startup-time
    identity assertion failing fast on divergence. The FastAPI DI
    source (`app/core/deps.py:get_db`) now delegates to
    `db_runtime.get_db()` rather than the legacy
    `from server import db` lazy bridge — and all 26 non-DI db
    consumers were migrated through the C-4e..C-4i batches. Object
    identity across `server.db`, `db_runtime.get_db()`, and
    `Depends(get_db)` is asserted at startup and verified by the
    C-4j finale regression test.

(d) The notifications subsystem (init at phase 3) couples db + sio +
    event-bus + worker registration in a single init() call —
    representing a hidden orchestration unit. C-4c proved this
    coupling can be DOCUMENTED with an identity assertion (split-brain
    prevention: `get_sio() is sio` ASSERTED right before
    `notifications.init(db, sio)`) without rewriting the init
    semantics. Splitting this into app.state-shaped components
    remains a refactor for Phase 5.5+.

(e) Phase 5.4 / C-4a..C-4j evidence — FOUR retirements at four
    distinct difficulty levels:
    - C-4a (logger):                  convenience import,         2 consumers
    - C-4b (bitmotors_parser_instance): runtime singleton,        1 consumer + 1 conditional rebind
    - C-4c (sio):                     event-bus runtime surface,  3 consumers + reference capture into NotificationService + ASGIApp wrap + @sio.event handlers + 20+ owner-side emits
    - C-4e..C-4j (db):                connection root,            26 non-DI consumers + 1 DI root, ~250 read/write call sites across the request graph + workers + legacy modules
    All four retirements closed without behaviour change,
    without touching forbidden categories (lifecycle, handlers,
    emit topology, init signatures, route signatures, worker
    registration, repository constructors). The bridge-retirement
    MECHANICS are now proved repeatable across the difficulty
    spectrum INCLUDING the hard case. The Tier-A wave is closed.

(f) Phase 5.4 / C-5 planning evidence — Tier-B inventory captured
    with AST audit (9 symbols: 7 mandated Tier-B + 2 AST-discovered
    Tier-C). Each symbol classified by semantic class
    (pure_utility / runtime_accessor / domain_helper / static_path /
    orchestration) and assigned a proposed batch (C-5a..C-5f or
    DEFER). Inventory split: 4 stale/quasi-stale (0 production
    consumers; C-5a no-op retirement candidates), 1 singleton
    accessor (C-5b), 1 callable-by-reference (C-5c, heaviest), 2
    shipment domain helpers (C-5e, batched with the multi-line
    import block touch), 1 deferred static path (DEFER:5.8).
    Methodology lock-in: every future wave MUST start with an
    AST-grep inventory revision before execution, because the
    C-4i (payments.py 24 qualified-sites) and C-4j (get_current_stage,
    serialize_journey multi-line imports) discoveries both
    proved that regex-based grep + manual planning under-counts
    real coupling.

Implication for Phase 5.4 (continuing):

* C-4 is FULLY CLOSED:
  - C-4a: logger retirement (CLOSED — 2 consumers migrated).
  - C-4b: bitmotors_parser_instance retirement (CLOSED — accessor
    module ownership, identity preserved 1:1).
  - C-4c: sio retirement (CLOSED — dedicated `app.core.socket_runtime`
    accessor, two identity assertions, NotificationService capture
    invariant pinned, @sio.event handlers untouched).
  - C-4d: db retirement PLANNING (CLOSED — see DB_CONSUMER_INVENTORY
    above and PHASE5_4_C4D_DB_RETIREMENT_PLAN.md).
  - C-4e: db consumer migration batch 1 (CLOSED — 12 routers).
  - C-4f: db consumer migration batch 2 (CLOSED — 4 _repo routers).
  - C-4g: notifications.py db_runtime migration (CLOSED).
  - C-4h: module-services batch (CLOSED — 4 modules).
  - C-4i: residual db consumer retirement (CLOSED — 5 listed +
    1 audit-discovered residual, qualified-import pattern retired).
  - C-4j: DI root swap (CLOSED — `app/core/deps.py:get_db` now
    delegates to `db_runtime`; Tier-A is now empty).

* C-5 PLANNING CLOSED:
  - 9 Tier-B / Tier-C helper bridges inventoried in TIER_B_INVENTORY.
  - 2 audit-discovered shipment helpers registered in
    BRIDGE_INVENTORY (size 17 → 19 due to discovery).
  - C-5a..C-5f batch order proposed in C5_BATCH_PROPOSAL.
  - C-5 forbidden categories pinned in C5_FORBIDDEN_CHANGES.

* C-5a EXECUTION CLOSED (Phase 5.4 / C-5a — pure-utility / stale-shim
  retirement):
  - `serialize_doc`     — vestigial Bridge entry removed
                          (canonical: app/utils/serialization.py).
  - `_round_money`      — vestigial Bridge entry removed
                          (canonical: app/utils/money.py).
  - `_smooth_eta_iso`   — moved to app/utils/shipments.py (1:1
                          verbatim port + exclusive constant
                          `JOURNEY_ETA_SMOOTH_ALPHA` + module-private
                          `__source_category` copy). server.py keeps
                          a thin compat shim that delegates 1:1
                          (preserves `server._smooth_eta_iso`
                          qualified-name for legacy POC scripts;
                          production AST grep remains 0).
  - `is_valid_movement` — moved to app/utils/shipments.py (1:1
                          verbatim port + exclusive constant
                          `JOURNEY_SPIKE_MAX_KM_PER_120S` + module-
                          private `__haversine_km` copy). Same shim
                          pattern as `_smooth_eta_iso`.
  Inventory delta: BRIDGE_INVENTORY 19 → 15; TIER_B_INVENTORY 9 → 5;
  TIER_B_MOVE_AND_REROUTE 7 → 3. Behaviour parity asserted by
  `tests/test_phase5_4_c5a_pure_utility_retirement.py`.

* C-5b EXECUTION CLOSED (Phase 5.4 / C-5b — aggregator runtime
  accessor extraction):
  - `aggregator`        — runtime accessor module created at
                          `app/core/aggregator_runtime.py`
                          (`set_aggregator` / `get_aggregator`
                          mirror of C-4b / C-4c). server.py
                          publishes the singleton via setter call
                          immediately after construction, with a
                          module-load identity assertion guarding
                          against split-brain. The bare `aggregator`
                          module global is retained for
                          server.py-internal callers (closure-name
                          references at queue_handler / stats /
                          ingestion-status sites). The sole
                          production consumer
                          (`app/routers/admin_cache.py:42`) was
                          migrated from `from server import aggregator`
                          to `from app.core.aggregator_runtime import
                          get_aggregator`. Mandatory 5-question
                          micro-audit came back clean
                          (see PHASE5_4_C5B_CLOSED.md §Micro-audit).
                          The latent `.records vs .store`
                          AttributeError bug at admin_cache.py:57
                          was preserved verbatim (forbidden category:
                          "no behaviour changes").
  Inventory delta: BRIDGE_INVENTORY 15 → 14; TIER_B_INVENTORY 5 → 4;
  TIER_B_MOVE_AND_REROUTE 3 → 2. Identity invariant asserted by
  `tests/test_phase5_4_c5b_aggregator_runtime.py`.

* C-5c EXECUTION CLOSED (Phase 5.4 / C-5c — audit runtime accessor
  extraction; heaviest Tier-B symbol):
  - `audit`             — runtime accessor module created at
                          `app/core/audit_runtime.py`
                          (`set_audit` / `get_audit` /
                          `clear_audit_for_tests`, mirror of C-4c
                          sio — async side-effect callable shape).
                          server.py publishes the canonical async
                          callable via setter call IMMEDIATELY after
                          `async def audit(...)` definition closes
                          (server.py ~line 3093), with a module-load
                          identity assertion (`assert get_audit() is
                          audit`) guarding against split-brain. The
                          bare `audit` module global is retained for
                          server.py-internal closure callers
                          (resolver_worker @ server.py:6582 +
                          transfer_detector @ server.py:6637 — both
                          invoke `audit(...)` by bare-name closure,
                          not via `from server import audit`).
                          Three production consumers migrated from
                          `from server import audit` to
                          `from app.core.audit_runtime import get_audit`:
                          (1) `app/routers/admin_identity.py:_audit()`,
                          (2) `app/routers/admin_ext_clients.py:_audit()`,
                          (3) `app/services/identity_runtime.py:_audit_callable()`.
                          Mandatory 5-question micro-audit produced
                          the expected callable-shape pattern
                          (Q1=NO async callable, Q2=YES late-bound,
                          Q3=YES captures db via closure, Q4=YES
                          effective via production call-graph
                          ordering + best-effort wrapper, Q5=YES
                          worker closure callers but out of scope —
                          see PHASE5_4_C5C_CLOSED.md §Micro-audit
                          for the full table).
                          8-field write schema invariant (H-5 from
                          Phase 5.4 / C-1) preserved verbatim:
                          `{ts, action, user_id, user_email,
                          user_role, resource, meta, ip}`. The
                          async/await contract, `except Exception:
                          logger.debug` best-effort wrapper, and
                          5-positional signature are all unchanged.
                          The dual-audit topology
                          (`audit_log` via SecurityAuditRepository
                          vs `audit_events` via the audit-events
                          repository) is NOT changed by C-5c — they
                          remain two independent collections served
                          by two independent repositories.
  Inventory delta: BRIDGE_INVENTORY 14 → 13; TIER_B_INVENTORY 4 → 3;
  TIER_B_MOVE_AND_REROUTE 2 → 1. Identity invariant + 8-field
  schema preservation asserted by
  `tests/test_phase5_4_c5c_audit_runtime.py`.

* C-5 EXECUTION queue (one batch per commit):
  - C-5a: stale shim retirements (CLOSED — 19 → 15).
  - C-5b: aggregator runtime accessor extraction (CLOSED — 15 → 14).
  - C-5c: audit runtime accessor extraction (CLOSED — 14 → 13;
    heaviest Tier-B).
  - C-5d: reserved for unexpected residuals (no work needed).
  - C-5e: shipment domain helpers move to app/utils/shipments.py
    (CLOSED — 13 → 11; `get_current_stage`, `serialize_journey`).
  - C-5f: consolidation verdict (this commit — CLOSED; no
    retirement, formal handoff contract to Phase 5.5).
  - DEFER:5.8 — `_STATIC_DIR` moves with the static mount
    migration in the bootstrap layer reshuffle.

* C-5f handoff contract (formal — `PHASE_5_5_BOUNDARY` +
  `PHASE_5_8_BOUNDARY` + `QUALIFIED_USAGE_BRIDGES`):
  - Phase 5.5 starts with EXACTLY 14 symbols
    (10 Tier-C from-server + 4 qualified-usage symbols),
    distributed across illustrative waves 5.5.A..5.5.I — see
    `PHASE_5_5_BOUNDARY` docstring for the wave breakdown.
  - Phase 5.8 owns `_STATIC_DIR` (bootstrap reshuffle).
  - No "maybe next" buckets remaining.

* C-4 + C-5 invariant tests pin the bridge inventory after each
  commit (BRIDGE_INVENTORY frozenset is the ground-truth ledger).
  Tier-A empty is the C-4 invariant. Bridge count == 11 is the
  post-C-5e/C-5f invariant. Live AST re-audit baseline frozen in
  `C5F_INVENTORY_BASELINE`.

* Lifespan rewrite remains OUT of Phase 5.4 scope (Phase 5.5+).
"""


# ═══════════════════════════════════════════════════════════════════════
# 6.  DB CONSUMER INVENTORY  (Phase 5.4 / C-4d planning)
# ═══════════════════════════════════════════════════════════════════════
#
# This inventory is the ground-truth ledger for the `db` bridge
# retirement wave (C-4e..C-4j). It is GENERATED from a static AST
# audit of the production tree and CROSS-CHECKED by
# tests/test_phase5_4_c4d_db_retirement_plan.py (live grep must
# match this frozenset exactly).
#
# Five access-context classes (per mandate §2):
#
#   A — Router request-scope consumers
#       Lazy `from server import db` (or `import server` qualified
#       access) inside FastAPI router files. Per-request scope.
#       Target pattern: prefer `Depends(get_db)` if signature
#       churn is acceptable; otherwise keep local `_db()` wrapper
#       backed by `app.core.db_runtime.get_db()` (new module).
#
#   B — Module service consumers
#       Lazy `from server import db as _server_db` inside legacy
#       module-level Python files (notifications, payments_tracking,
#       legal_workflow, cabinet_financials, financial_breakdown).
#       NOT routers — these are imported by routers and workers.
#       Target pattern: `app.core.db_runtime.get_db()` (new module).
#       NOT `app.core.deps` because deps.py is request/DI surface,
#       not a runtime root.
#
#   C — Worker/runtime consumers
#       Worker loops that read `db` directly. After audit: ZERO
#       `from server import db` sites in worker code — all worker
#       loop functions live INSIDE server.py as module-scope
#       functions and read the module global via closure capture
#       (owner-side, not a bridge). DEFERRED to Phase 5.5 (lifespan
#       rewrite), NOT migrated in C-4e..C-4j.
#
#   D — Repository / test-adjacent consumers
#       Repository constructors take `db` as an explicit argument.
#       After audit: ZERO `from server import db` sites in
#       `app/repositories/`. Repositories are already on the
#       constructor-injection pattern — they MUST NOT acquire a
#       global db handle. This is a structural invariant pinned
#       by the planning tests.
#
#   E — Startup/lifespan consumers
#       The single `from server import db` site inside
#       `app/core/deps.py:get_db()` IS the DI bridge itself.
#       It will be migrated LAST (C-4j) once all other consumers
#       have moved off it. Until then it remains the canonical
#       `Depends(get_db)` source for FastAPI routers.
#
# Proposed batch ordering (C-4e..C-4j, ground-truth in the
# `recommended_batch` field below):
#
#   C-4e: low-risk admin routers with stable signatures (~10 files)
#         e.g. admin_engagement, admin_ext_clients, admin_identity,
#         admin_metrics, admin_overview, admin_orders, admin_search,
#         admin_ringostat, admin_providers, admin_predictive_leads
#         → migrate `_db()` wrapper to read from db_runtime.get_db()
#         (single-line body swap, no signature changes).
#
#   C-4f: admin routers with `_repo()` shape (~4 files)
#         admin_history_reports, admin_security, admin_services,
#         admin_workflow_templates
#         → swap `from server import db` inside `_repo()` to
#         db_runtime.get_db(); repository instantiation pattern
#         preserved.
#
#   C-4g: notification-family modules (~2 files)
#         notifications.py, financial_breakdown.py
#         → swap `_db()` body to use db_runtime.get_db(). These
#         are imported by both routers and workers — extra care
#         needed for startup ordering tests.
#
#   C-4h: payment/legal modules (~3 files)
#         payments_tracking, legal_workflow, cabinet_financials
#         → mirror C-4g pattern.
#
#   C-4i: special cases (~3 files)
#         calculations.py (qualified `import server` pattern, 20
#         internal `server.db.X` call sites — needs different
#         migration: rebind to module-local `db_runtime.get_db()`
#         at top of each handler OR keep the import and only
#         retire when calculations module relocates).
#         admin_vesselfinder, admin_shipments (use `_server_db`
#         alias inside `_db()`).
#         content.py (uses `_db()` directly).
#         identity_runtime.py (already on socket_runtime pattern;
#         migrate `_db()` to db_runtime.get_db()).
#
#   C-4j: final migration — `app/core/deps.py:get_db()` swap +
#         grep audit (`from server import db` must be exactly 0
#         after this commit). After C-4j, `db` joins the retirement
#         list and BRIDGE_INVENTORY drops to 17 (Tier-A becomes
#         empty: `frozenset()`).
#
# All target patterns assume a new `app.core.db_runtime` module
# (set_db/get_db/get_mongo_client/clear_db_for_tests) exists.
# That module is OPTIONAL in C-4d (planning) and MUST have zero
# production consumers if created. Its production wiring begins in
# C-4e.

@dataclass(frozen=True)
class DBConsumer:
    """A production site that reads ``db`` via the bridge.

    The C-4d planning data structure. As migrations land, the
    ``migrated`` flag flips to True per-batch (C-4e flips 12 entries,
    C-4f flips 4, etc.). After C-4j retires the bridge, every entry
    will have ``migrated == True``. The inventory is the ground-truth
    source for migration ordering and for verifying that no consumer
    is missed.
    """
    file: str                    # path relative to backend/
    line: int                    # AST-detected lineno of the ImportFrom
    function: str                # enclosing function name ("_db", "_repo", ...)
    alias: str                   # "db" or "_server_db" or similar
    access_class: str            # "A" | "B" | "C" | "D" | "E"
    context_label: str           # "router/_db" | "module-service/_db" | ...
    target_pattern: str          # "Depends(get_db)" | "local _db() → db_runtime.get_db()"
                                 # | "module-local db_runtime.get_db()"
                                 # | "DI-source — migrates LAST"
    risk: str                    # "low" | "medium" | "high"
    recommended_batch: str       # "C-4e" | "C-4f" | "C-4g" | "C-4h" | "C-4i" | "C-4j"
    migrated: bool = False       # True once the batch lands (flipped per C-4e/f/g/h/i/j)
    notes: str = ""


DB_CONSUMER_INVENTORY: tuple[DBConsumer, ...] = (
    # ── Class A: Router request-scope consumers (`_db()` shape) ──────
    DBConsumer(
        file="app/routers/admin_engagement.py", line=63, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
        notes="Stable router signature; single _db() reader.",
    ),
    DBConsumer(
        file="app/routers/admin_ext_clients.py", line=50, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_identity.py", line=54, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_integrations.py", line=85, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_metrics.py", line=93, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_orders.py", line=38, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_overview.py", line=38, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_predictive_leads.py", line=37, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_providers.py", line=70, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_resolver.py", line=59, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
        notes="Used by admin_resolver — identity_runtime adjacent.",
    ),
    DBConsumer(
        file="app/routers/admin_ringostat.py", line=74, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_search.py", line=33, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4e",
        migrated=True,
    ),
    # ── Class A.2: Router `_repo()` shape (repository factory) ───────
    DBConsumer(
        file="app/routers/admin_history_reports.py", line=51, function="_repo",
        alias="db", access_class="A", context_label="router/_repo",
        target_pattern="local _repo() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4f",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_security.py", line=79, function="_repo",
        alias="_server_db", access_class="A", context_label="router/_repo",
        target_pattern="local _repo() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4f",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_services.py", line=106, function="_repo",
        alias="_server_db", access_class="A", context_label="router/_repo",
        target_pattern="local _repo() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4f",
        migrated=True,
    ),
    DBConsumer(
        file="app/routers/admin_workflow_templates.py", line=75, function="_repo",
        alias="db", access_class="A", context_label="router/_repo",
        target_pattern="local _repo() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4f",
        migrated=True,
    ),
    # ── Class A.3: Router special-cases (qualified import, aliased) ──
    DBConsumer(
        file="app/routers/admin_shipments.py", line=75, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="medium", recommended_batch="C-4i",
        migrated=True,
        notes="Shipments router — tracking-worker-adjacent; verify "
              "no startup-order capture before migrating.",
    ),
    DBConsumer(
        file="app/routers/admin_vesselfinder.py", line=65, function="_db",
        alias="_server_db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="medium", recommended_batch="C-4i",
        migrated=True,
        notes="Vesselfinder router — depends on tracking_config service; "
              "verify cross-module ordering.",
    ),
    DBConsumer(
        file="app/routers/content.py", line=83, function="_db",
        alias="db", access_class="A", context_label="router/_db",
        target_pattern="local _db() → db_runtime.get_db()",
        risk="low", recommended_batch="C-4i",
        migrated=True,
        notes="Public-cache content router — verify cache-warming path.",
    ),
    # ── Class B: Module service consumers (legacy modules) ───────────
    DBConsumer(
        file="notifications.py", line=902, function="_db",
        alias="_server_db", access_class="B", context_label="module-service/_db",
        target_pattern="module-local db_runtime.get_db()",
        risk="medium", recommended_batch="C-4g",
        migrated=True,
        notes="Imported by routers AND workers; reference-capture into "
              "NotificationService init — verify startup ordering "
              "(notifications.init must still see the canonical db).",
    ),
    DBConsumer(
        file="financial_breakdown.py", line=271, function="_db",
        alias="_server_db", access_class="B", context_label="module-service/_db",
        target_pattern="module-local db_runtime.get_db()",
        risk="medium", recommended_batch="C-4h",
        migrated=True,
        notes="Rebatched from C-4g → C-4h at C-4g close — user-mandated "
              "C-4g scope was notifications.py only; all remaining Class-B "
              "module-services (financial_breakdown, payments_tracking, "
              "legal_workflow, cabinet_financials) are now grouped under "
              "C-4h.",
    ),
    DBConsumer(
        file="payments_tracking.py", line=115, function="_db",
        alias="_server_db", access_class="B", context_label="module-service/_db",
        target_pattern="module-local db_runtime.get_db()",
        risk="medium", recommended_batch="C-4h",
        migrated=True,
        notes="Refund cron + payment-reminder dependencies.",
    ),
    DBConsumer(
        file="legal_workflow.py", line=357, function="_db",
        alias="_server_db", access_class="B", context_label="module-service/_db",
        target_pattern="module-local db_runtime.get_db()",
        risk="medium", recommended_batch="C-4h",
        migrated=True,
    ),
    DBConsumer(
        file="cabinet_financials.py", line=47, function="_db",
        alias="_server_db", access_class="B", context_label="module-service/_db",
        target_pattern="module-local db_runtime.get_db()",
        risk="medium", recommended_batch="C-4h",
        migrated=True,
    ),
    # ── Class B.2: Service module (already on socket_runtime pattern) ─
    DBConsumer(
        file="app/services/identity_runtime.py", line=86, function="_db",
        alias="db", access_class="B", context_label="service/_db",
        target_pattern="module-local db_runtime.get_db()",
        risk="low", recommended_batch="C-4i",
        migrated=True,
        notes="identity_runtime._sio already migrated to socket_runtime "
              "in C-4c; _db() migrated to db_runtime in C-4i (sibling "
              "pattern). Both runtime singletons now flow through "
              "dedicated accessors with no direct `from server import …`.",
    ),
    # ── Class E: Startup/DI source (RETIRED in C-4j) ─────────────────
    DBConsumer(
        file="app/core/deps.py", line=73, function="get_db",
        alias="db", access_class="E", context_label="DI-source/get_db",
        target_pattern="DI-source — delegate to db_runtime.get_db() in C-4j",
        risk="high", recommended_batch="C-4j",
        migrated=True,
        notes="MIGRATED in Phase 5.4 / C-4j (db bridge retirement "
              "finale). The DI source now delegates to "
              "`app.core.db_runtime.get_db()` instead of "
              "`from server import db`. `Depends(get_db)` "
              "request-scope behaviour is byte-for-byte identical "
              "(identity preserved: `server.db is db_runtime.get_db()` "
              "asserted at startup). With this site migrated, "
              "`BRIDGE_INVENTORY` drops the `db` entry and "
              "`TIER_A_SHALLOW_REWIRING` becomes the empty frozenset.",
    ),
)
"""Production-tree inventory of every `from server import db` site
plus the qualified-import special case. C-4d planning ledger; the
backing test (test_phase5_4_c4d_db_retirement_plan.py) verifies
this matches the live AST grep exactly."""


# ── Special qualified-import case (NOT an ImportFrom — `import server`) ──
# `app/routers/calculations.py` did `import server` at module scope and
# accessed `server.db.<collection>` directly (~23 sites inside the file).
# This was structurally a bridge but did NOT appear in any
# `from server import db` AST query. C-4i RETIRED the qualified-import
# pattern: all ~23 `server.db.X` sites were rebound to `get_db().X` via
# `app.core.db_runtime`. The `import server` line itself REMAINS because
# the same module still uses non-db symbols (`server.logger`,
# `server.calculator_calculate`, `server._calculate_korea`) — those are
# outside C-4i scope (decoupling calculator engine + logger surfaces is
# a separate later effort).

# ─────────────────────────────────────────────────────────────────────
# Phase 5.4 / C-5 — Tier-B helper move-and-reroute PLANNING surface
# ─────────────────────────────────────────────────────────────────────
#
# C-5 is a planning-only commit (mini-C-4d shape). It inventories the
# Tier-B helper bridges plus two AST-discovered Tier-C bridges that
# the previous (regex-based) bridge audit missed, classifies each
# symbol's semantic class and target module, and proposes a batch
# order for the C-5a..C-5f execution wave. NO HELPER IS MOVED.
#
# Methodological note carried over from C-4i / C-4j: the regex-based
# `from server import` grep in `test_phase5_4_c3b_topology_invariants`
# missed multi-line `from server import (...)` blocks. The C-4j
# update switched it to AST-based traversal and immediately surfaced
# `get_current_stage` and `serialize_journey` as live bridges that
# were never registered. C-5 makes them inventoried + classified.
#
# Each new wave should now START with an AST-grep inventory revision
# of its category before any execution. Inventories drift behind
# reality; the only defence is machine-checked rediscovery.
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TierBSymbol:
    """Planning-time descriptor for a Tier-B / Tier-C helper bridge.

    Fields
    ------
    symbol
        The helper symbol name (matches the ``Bridge.symbol`` entry
        in ``BRIDGE_INVENTORY``).
    current_definition_site
        ``file:line`` of the canonical definition. For helpers that
        have ALREADY been moved to ``app/utils/...`` (e.g.
        ``serialize_doc``, ``_round_money``) this is the new
        location; the bridge entry is then a vestigial compat shim.
    production_consumer_sites
        Tuple of ``file:line`` strings — only files under ``app/``
        or ``server.py`` (excludes ``tests/`` AND legacy root
        ``test_*.py`` POC scripts).
    legacy_test_consumer_sites
        Tuple of ``file:line`` strings — root-level ``test_*.py``
        legacy POC scripts. These are NOT production code but they
        keep the bridge "live" for backwards compatibility.
    import_shape
        How the consumer imports it:
          - ``"direct"``: ``from server import X``
          - ``"single_line_tuple"``: ``from server import X, Y``
          - ``"multiline_tuple"``: ``from server import (\\n  X,\\n  Y,\\n)``
          - ``"none"``: zero consumers (stale bridge)
    semantic_class
        How the symbol behaves at runtime:
          - ``"pure_utility"``: stateless function, no side effects.
            Safe to relocate; identity not material.
          - ``"runtime_accessor"``: singleton instance whose identity
            and live mutations matter. Needs accessor-module pattern
            (like ``db_runtime``).
          - ``"domain_helper"``: function specific to a business
            domain (shipments, customers, payments). Move target is
            the domain module, not generic ``app/utils``.
          - ``"static_path"``: module-level path/string constant
            tied to bootstrap (FastAPI static mount).
          - ``"orchestration"``: function that mixes runtime state
            and business logic (Tier-C category; not pure Tier-B).
    target_module
        Proposed destination module for the move. Format:
        ``"app/<...>.py"`` or ``"DEFER:<phase>"`` if the target
        module itself isn't ready (e.g. ``"DEFER:5.5"`` for
        shipment domain helpers awaiting the domain module).
    test_requirement
        What the post-move test must assert:
          - ``"structural"``: AST grep (no ``from server import X``).
          - ``"identity"``: runtime singleton identity preserved
            across rebind (like C-4j's three-way chain).
          - ``"behaviour"``: a smoke route exercises the helper and
            returns the expected status / shape.
          - ``"smoke"``: backend boots and the helper resolves.
    risk
        - ``"low"``: stale / vestigial bridge with zero production
          consumers. C-5a candidate.
        - ``"medium"``: 1-2 consumers, pure function or simple
          singleton. C-5b/c candidate.
        - ``"high"``: runtime state coupling (audit callable, static
          mount). C-5d+ candidate.
    proposed_batch
        ``"C-5a"`` .. ``"C-5f"`` or ``"DEFER:<phase>"`` if the
        symbol belongs to a later phase (e.g. shipment domain
        helpers awaiting the domain module in 5.5).
    notes
        Free-form planning notes (rationale, sibling-symbol coupling,
        order constraints, known pitfalls).
    """

    symbol: str
    current_definition_site: str
    production_consumer_sites: tuple[str, ...]
    legacy_test_consumer_sites: tuple[str, ...]
    import_shape: str
    semantic_class: str
    target_module: str
    test_requirement: str
    risk: str
    proposed_batch: str
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────
# Live AST-grep inventory (post-C-4j, pre-C-5 execution)
# ─────────────────────────────────────────────────────────────────────
#
# Captured by the AST audit in `tests/test_phase5_4_c5_tier_b_plan.py`
# at C-5 close. The test re-runs the AST grep on every invocation
# and asserts that the live consumer lists still match this
# inventory exactly — if a NEW consumer appears in production,
# the test fails until C-5 is re-planned.
#
# Coverage: the 7 mandated Tier-B symbols (`audit`, `aggregator`,
# `serialize_doc`, `_round_money`, `_smooth_eta_iso`,
# `is_valid_movement`, `_STATIC_DIR`) plus the 2 audit-discovered
# Tier-C bridges (`get_current_stage`, `serialize_journey`).

TIER_B_INVENTORY: tuple[TierBSymbol, ...] = (
    # ─── Phase 5.4 / C-5a CLOSED — 4 entries retired ─────────────────
    # The following Tier-B entries were retired in C-5a (stale-shim +
    # shipping-owned move batch) and REMOVED from this inventory:
    #
    #   * ``_round_money``      — canonical already in app/utils/money.py;
    #                             vestigial Bridge entry removed.
    #   * ``serialize_doc``     — canonical already in app/utils/serialization.py;
    #                             vestigial Bridge entry removed.
    #   * ``_smooth_eta_iso``   — moved to app/utils/shipments.py
    #                             (1:1 verbatim port).
    #   * ``is_valid_movement`` — moved to app/utils/shipments.py
    #                             (1:1 verbatim port).
    #
    # Behaviour parity asserted by
    # ``tests/test_phase5_4_c5a_pure_utility_retirement.py``.
    # Inventory size 9 → 5.
    #
    # ─── Phase 5.4 / C-5b CLOSED — 1 entry retired ───────────────────
    # The following Tier-B entry was retired in C-5b (runtime accessor
    # extraction batch) and REMOVED from this inventory:
    #
    #   * ``aggregator``        — runtime accessor module created at
    #                             app/core/aggregator_runtime.py
    #                             (set_aggregator / get_aggregator,
    #                             mirror of C-4b / C-4c). Mandatory
    #                             5-question micro-audit came back
    #                             clean (pure singleton, no late-bound
    #                             runtime, no worker references).
    #
    # Identity invariant asserted by
    # ``tests/test_phase5_4_c5b_aggregator_runtime.py``.
    # Inventory size 5 → 4. Remaining 4 entries below are the
    # C-5c / C-5e / DEFER:5.8 wave.
    #
    # ─── Phase 5.4 / C-5c CLOSED — 1 entry retired ───────────────────
    # The following Tier-B entry was retired in C-5c (runtime accessor
    # extraction batch — heaviest Tier-B symbol) and REMOVED from this
    # inventory:
    #
    #   * ``audit``             — runtime accessor module created at
    #                             app/core/audit_runtime.py
    #                             (set_audit / get_audit, mirror of
    #                             C-4c sio — async side-effect
    #                             callable shape). Mandatory
    #                             5-question micro-audit came back
    #                             with the expected callable-shape
    #                             pattern: Q1=NO (async callable),
    #                             Q2=YES (late-bound via closure on
    #                             db), Q3=YES (writes via
    #                             SecurityAuditRepository), Q4=YES
    #                             (effective — every production
    #                             call-site runs post-_main_startup),
    #                             Q5=YES (worker closure callers,
    #                             but NOT via `from server import`,
    #                             so out of scope). Three production
    #                             consumers migrated 1:1.
    #
    # Identity invariant + 8-field schema preservation asserted by
    # ``tests/test_phase5_4_c5c_audit_runtime.py``. Inventory size
    # 4 → 3. Remaining 3 entries below are the C-5e / DEFER:5.8 wave.

    # ─── Static path constant (bootstrap-coupled) ──────────────────────
    TierBSymbol(
        symbol="_STATIC_DIR",
        current_definition_site="server.py:3131",
        production_consumer_sites=("app/routers/content.py:105",),
        legacy_test_consumer_sites=(),
        import_shape="direct",
        semantic_class="static_path",
        target_module="DEFER:5.8 (bootstrap layer reshuffle)",
        test_requirement="smoke",
        risk="medium",
        proposed_batch="DEFER:5.8",
        notes=(
            "Module-level `Path` constant that backs the FastAPI "
            "static mount (`StaticFiles(directory=_STATIC_DIR, ...)`). "
            "Moving it means coordinating with the static mount "
            "registration order in `_main_startup`. Deferred to "
            "Phase 5.8 (bootstrap layer reshuffle) where the static "
            "mount itself migrates to `app/core/static_mount.py`. "
            "C-5 only documents the dependency; no move."
        ),
    ),
    # ─── Phase 5.4 / C-5e CLOSED — 2 entries retired ────────────────
    # The following two TIER_B entries were retired in C-5e (shipment
    # helper retirement batch) and REMOVED from this inventory:
    #
    #   * ``get_current_stage`` — pure dict-walk; verbatim port to
    #                             app/utils/shipments.py with server.py
    #                             compat shim retained for 3 internal
    #                             closure callers + qualified
    #                             `server.get_current_stage` surface.
    #   * ``serialize_journey`` — pure dict-builder; verbatim port to
    #                             app/utils/shipments.py with server.py
    #                             compat shim retained for 7 internal
    #                             closure callers + qualified
    #                             `server.serialize_journey` surface.
    #                             Calls `serialize_doc` (canonical
    #                             `app.utils.serialization`) +
    #                             `get_current_stage` (sibling) +
    #                             private `__location_label` copy
    #                             (mirror of C-5a private copy pattern).
    #
    # Mandatory 5-question micro-audit (Q1=defs at server.py:5492/5583;
    # Q2=2 prod consumers via multi-line tuple imports; Q3=only
    # `serialize_doc` + `get_location_label` server-side deps;
    # Q4=NO db/sio/audit/emit/worker effects; Q5=YES pure
    # read/serialize). Verdict: PROCEED.
    #
    # Behaviour parity + 28-field schema preservation +
    # trackingHealth classification + emotionalText derivation
    # asserted by `tests/test_phase5_4_c5e_shipment_helpers.py`.
    # Inventory size 3 → 1. The sole remaining entry below is
    # `_STATIC_DIR` (DEFER:5.8 bootstrap layer reshuffle).
)
"""Live Tier-B inventory captured at C-5 close. AST audit in
``tests/test_phase5_4_c5_tier_b_plan.py`` keeps this in sync with
the codebase — any new consumer of any symbol here fails the
test until the inventory is updated."""


# ─────────────────────────────────────────────────────────────────────
# C-5 batch proposal (execution order, NOT executed in C-5 itself)
# ─────────────────────────────────────────────────────────────────────
#
# Each batch is a single narrow commit (C-4 mechanics). Order is
# chosen to minimise blast radius: stale shims first (zero risk),
# then pure singletons (small consumer surface), then the heaviest
# runtime callable (`audit`), then domain helpers, then deferred
# bootstrap-coupled paths.

C5_BATCH_PROPOSAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "C-5a",
        # CLOSED (Phase 5.4 / C-5a). The 4 symbols below were
        # retired in C-5a (stale-shim + shipping-owned move batch).
        # Empty tuple here means "no remaining work for this batch";
        # the historical scope is preserved in the
        # ``C5A_RETIRED_SYMBOLS`` constant below for audit purposes.
        # The C-5 test_5 validator passes an empty batch tuple
        # (no orphans because the symbols are no longer in
        # TIER_B_INVENTORY).
        (),
    ),
    (
        "C-5b",
        # CLOSED (Phase 5.4 / C-5b). The `aggregator` runtime accessor
        # extraction landed: app/core/aggregator_runtime.py module
        # created (set_aggregator / get_aggregator, mirror of C-4b
        # bitmotors_parser_instance and C-4c sio). Identity invariant
        # asserted at the module-load setter site. Mandatory
        # 5-question micro-audit (per the C-5b mandate correction)
        # came back clean — no late-bound runtime capture, no worker
        # references, no hidden db ownership chain. The historical
        # scope is preserved in `C5B_RETIRED_SYMBOLS` below.
        (),
    ),
    (
        "C-5c",
        # CLOSED (Phase 5.4 / C-5c). The `audit` runtime accessor
        # extraction landed: app/core/audit_runtime.py module created
        # (set_audit / get_audit, mirror of C-4c sio — async
        # side-effect callable). Identity invariant asserted at the
        # module-load setter site (`assert get_audit() is audit`).
        # Mandatory 5-question micro-audit produced the expected
        # callable-shape pattern (Q1=NO, Q2=YES, Q3=YES, Q4=YES
        # effective, Q5=YES worker closure callers but not via
        # `from server import` → out of scope). Three production
        # consumers migrated 1:1 (admin_identity, admin_ext_clients,
        # identity_runtime). 8-field schema preserved verbatim (H-5).
        # The historical scope is preserved in `C5C_RETIRED_SYMBOLS`
        # below.
        (),
    ),
    (
        "C-5d",
        # Reserved for unexpected residuals discovered during
        # C-5a..C-5c execution. Empty at C-5 planning close.
        (),
    ),
    (
        "C-5e",
        # CLOSED (Phase 5.4 / C-5e). The two AST-discovered shipment
        # helpers (`get_current_stage`, `serialize_journey`) were
        # retired in C-5e (verbatim 1:1 port to
        # ``app/utils/shipments.py`` alongside the C-5a residents
        # `_smooth_eta_iso` / `is_valid_movement`). server.py keeps
        # thin compatibility shims that delegate 1:1; the canonical
        # impl is the sole truth post-C-5e. Two production consumers
        # migrated (admin_shipments, admin_resolver — multi-line
        # tuple import was touched once each).
        #
        # Mandatory 5-question micro-audit produced the expected
        # pure-helper pattern: Q1=server.py:5492/5583, Q2=2 prod
        # consumers, Q3=only `serialize_doc` + `get_location_label`
        # as helper-side deps, Q4=NO db/sio/audit/emit/worker side
        # effects, Q5=YES pure read/serialize. Verdict: PROCEED.
        #
        # The historical scope is preserved in `C5E_RETIRED_SYMBOLS`
        # below. The C-5 test_5 validator now passes an empty batch
        # tuple (no orphans because the symbols are no longer in
        # TIER_B_INVENTORY).
        (),
    ),
    (
        "C-5f",
        # Reserved for follow-on consolidation (verdict text update,
        # inventory cleanup). Empty at C-5 planning close.
        (),
    ),
    (
        "DEFER:5.8",
        # Bootstrap-coupled symbol — moved alongside the static
        # mount migration in Phase 5.8. NOT a C-5 batch.
        ("_STATIC_DIR",),
    ),
)
"""Proposed batch order for the C-5a..C-5f execution wave. C-5a and
C-5b are CLOSED (5 symbols retired total). Tested by
``tests/test_phase5_4_c5_tier_b_plan.py::test_5`` (every Tier-B
symbol must appear in exactly one batch; every batch must contain
only inventoried symbols)."""


C5A_RETIRED_SYMBOLS: tuple[str, ...] = (
    "serialize_doc",
    "_round_money",
    "_smooth_eta_iso",
    "is_valid_movement",
)
"""Historical scope of the C-5a batch (closed). All four symbols
are removed from BRIDGE_INVENTORY and TIER_B_INVENTORY post-C-5a.
Behaviour parity is asserted by
``tests/test_phase5_4_c5a_pure_utility_retirement.py``."""


C5B_RETIRED_SYMBOLS: tuple[str, ...] = (
    "aggregator",
)
"""Historical scope of the C-5b batch (closed). The single symbol
is removed from BRIDGE_INVENTORY and TIER_B_INVENTORY post-C-5b;
ownership moved to ``app/core/aggregator_runtime.py``. Identity
invariant is asserted by
``tests/test_phase5_4_c5b_aggregator_runtime.py``."""


C5C_RETIRED_SYMBOLS: tuple[str, ...] = (
    "audit",
)
"""Historical scope of the C-5c batch (closed). The single symbol
is removed from BRIDGE_INVENTORY and TIER_B_INVENTORY post-C-5c;
ownership moved to ``app/core/audit_runtime.py`` (set_audit /
get_audit / clear_audit_for_tests). Same accessor-module pattern
as C-4c (sio) — async side-effect callable shape.

The mandatory 5-question micro-audit (per the C-5c mandate
correction) produced the expected callable-shape pattern:
``Q1=NO`` (async callable, not a singleton),
``Q2=YES`` (late-bound via closure on module-global ``db``),
``Q3=YES`` (writes via ``SecurityAuditRepository(db)``),
``Q4=YES`` (effective — every production call-site runs
post-``_main_startup``; pre-startup invocations would be swallowed
by the audit body's ``except Exception: logger.debug`` best-effort
wrapper, preserving the H-5 invariant ``audit never raises``),
``Q5=YES`` (resolver_worker + transfer_detector worker loops
invoke ``audit(...)`` by bare-name closure inside server.py, but
NOT via ``from server import audit`` — therefore out of C-5c scope).

Three production consumers migrated 1:1 from ``from server import
audit`` to ``from app.core.audit_runtime import get_audit``:
  * ``app/routers/admin_identity.py:_audit()``
  * ``app/routers/admin_ext_clients.py:_audit()``
  * ``app/services/identity_runtime.py:_audit_callable()``

The audit callable's 8-field write schema
``{ts, action, user_id, user_email, user_role, resource, meta, ip}``
(H-5 invariant from Phase 5.4 / C-1), async/await contract, and
``except Exception: logger.debug`` best-effort wrapper are preserved
verbatim. The dual-audit topology (audit_log via
``SecurityAuditRepository`` vs ``audit_events`` via the audit-events
repository) is NOT changed by C-5c — these remain two independent
collections served by two independent repositories.

Identity invariant + schema-preservation asserted by
``tests/test_phase5_4_c5c_audit_runtime.py``."""


C5E_RETIRED_SYMBOLS: tuple[str, ...] = (
    "get_current_stage",
    "serialize_journey",
)
"""Historical scope of the C-5e batch (closed). The two AST-discovered
shipment-helper symbols are removed from BRIDGE_INVENTORY (Tier-C wing)
and TIER_B_INVENTORY post-C-5e; ownership moved to
``app/utils/shipments.py`` (verbatim 1:1 port). server.py keeps a
thin compatibility shim for each symbol that delegates 1:1 to the
canonical implementation — preserving the qualified-name surface
(``server.get_current_stage`` / ``server.serialize_journey``) for
legacy integration scripts and the ~10 internal closure callers that
still reference the bare names inside server.py.

The mandatory 5-question micro-audit per the C-5e mandate produced
the expected pure-helper pattern:
``Q1=defs at server.py:5492/5583`` (now thin compat shims that import
from the canonical module),
``Q2=2 production consumers`` (`admin_shipments.py`, `admin_resolver.py`
— both migrated via multi-line tuple imports of which the C-5e
symbols moved to ``from app.utils.shipments import``),
``Q3=only `serialize_doc` + `get_location_label``` as helper-side
dependencies (serialize_doc is already canonical in
``app/utils/serialization.py``; ``get_location_label`` is verbatim-copied
as private ``__location_label`` to avoid a back-import — same
duplication pattern as C-5a's ``_haversine_km`` / ``_source_category``,
reconciled in a later phase),
``Q4=NO db/sio/audit/emit/worker side effects`` (the helpers are pure
sync read/serialize functions — no I/O, no `await`),
``Q5=YES pure read/serialize helpers``. Verdict: PROCEED.

Two production consumers migrated 1:1 from
``from server import get_current_stage, serialize_journey`` to
``from app.utils.shipments import …``:
  * ``app/routers/admin_shipments.py:_helpers()`` (line 106)
  * ``app/routers/admin_resolver.py:_helpers()`` (line 76)

The 28-field response shape of ``serialize_journey`` (load-bearing
cabinet UI contract: ``trackingHealth`` 4-bucket classification +
``emotionalText`` Ukrainian status line + ``location`` region label +
``progress`` + ``currentStage`` + ``events`` slice + 22 verbatim
serialize_doc field passthroughs) is preserved verbatim. The
3-tier resolution order of ``get_current_stage``
(``currentStageId`` lookup → first ``status=='active'`` → first stage)
is preserved verbatim.

Behaviour parity + 28-field schema preservation +
trackingHealth classification + emotionalText derivation are
asserted by ``tests/test_phase5_4_c5e_shipment_helpers.py``."""


# ═════════════════════════════════════════════════════════════════════
# Phase 5.4 / C-5f — Consolidation verdict
# ═════════════════════════════════════════════════════════════════════
# C-5f is **planning / inventory / decision only** — no helper moves,
# no bridge retirements, no Phase 5.5 execution. The artifacts below
# are the formal handoff from Phase 5.4 to Phase 5.5.
#
# Required reading: ``PHASE5_4_C5F_CONSOLIDATION_VERDICT.md`` (project root).


@dataclass(frozen=True)
class QualifiedUsageSite:
    """A production usage of ``server.X`` (qualified attribute access)
    via an ``import server`` line — a bridge surface distinct from the
    ``from server import X`` shape that ``BRIDGE_INVENTORY`` tracks.

    Retirement mechanics differ from ``Bridge``:
      * ``Bridge`` (``from server import X``) — retire by moving the
        symbol to its canonical home and updating one import line.
      * ``QualifiedUsageSite`` (``server.X``) — retire by EITHER
        eliminating the ``import server`` line entirely (move the
        ``server.X`` call sites to direct imports from the canonical
        owner) OR keeping ``import server`` and rebinding ``server.X``
        to delegate to the canonical owner (sub-shape: the qualified
        access becomes a stable proxy, useful when the consumer file
        is itself slated for retirement in a later phase).
    """
    symbol: str                          # the X in server.X
    consumer_file: str                   # file using `server.X`
    site_count: int                      # production sites in that file
    consumer_purpose: str                # what the file uses X for
    proposed_target: str                 # canonical owner module
    target_phase: str                    # "5.5" | "5.6" | "5.8" | "Phase 6"
    notes: str = ""


QUALIFIED_USAGE_BRIDGES: tuple[QualifiedUsageSite, ...] = (
    # ─── calculations.py — calculator engine + logger bridge ──────────
    # RETIRED in Phase 5.5 / B (2026-05-19). All 3 qualified-access
    # sites in ``app/routers/calculations.py`` were migrated:
    #   * `server.logger.warning(...)` (1 site, line 733)
    #     → module-local ``logger = logging.getLogger("bibi.calculations")``
    #   * `server._calculate_korea(...)` (1 site, line 369)
    #     → ``from app.services.calculator import _calculate_korea``
    #   * `server.calculator_calculate(...)` (1 site, line 371)
    #     → ``from app.services.calculator import calculator_calculate``
    # The ``import server`` line in calculations.py was REMOVED in the
    # same wave (no surviving qualified-access usage). Function bodies
    # for both engines moved byte-identically to
    # ``app/services/calculator.py`` (the canonical home), with only the
    # established C-4i pattern (``db.X`` → ``get_db().X``) and 5.5/A
    # pattern (module-local logger) applied. Golden-parity hashes for
    # 18 representative inputs are pinned in
    # ``tests/test_phase5_5_b_calculator_extraction.py::PINNED_HASHES``.
    # Asserted by ``tests/test_phase5_5_b_calculator_extraction.py``.
    #
    # QualifiedUsageSite(
    #     symbol="logger",
    #     consumer_file="app/routers/calculations.py",
    #     ...
    # ),  # RETIRED Phase 5.5 / B
    # QualifiedUsageSite(
    #     symbol="_calculate_korea",
    #     consumer_file="app/routers/calculations.py",
    #     ...
    # ),  # RETIRED Phase 5.5 / B
    # QualifiedUsageSite(
    #     symbol="calculator_calculate",
    #     consumer_file="app/routers/calculations.py",
    #     ...
    # ),  # RETIRED Phase 5.5 / B
    # ─── payments.py — Stripe webhook + checkout flow logger bridge ──
    # RETIRED in Phase 5.5 / A (2026-05-19). 8 sites migrated to a
    # module-local logger (``logger = logging.getLogger("bibi.payments")``);
    # the qualified-access ``server.logger`` shape has 0 production
    # sites in ``app/routers/payments.py`` post-5.5.A. Asserted by
    # ``tests/test_phase5_5_a_payments_logger.py``. ``import server``
    # in payments.py REMAINS because ``server._create_order_from_invoice``
    # (line 658, Stripe webhook recompute branch) is still bridged —
    # retirement of that symbol belongs to the dedicated payments-
    # orchestration wave (Phase 5.5 follow-on, NOT 5.5 / A).
    #
    # QualifiedUsageSite(
    #     symbol="logger",
    #     consumer_file="app/routers/payments.py",
    #     site_count=8,
    #     ...
    # ),  # RETIRED Phase 5.5 / A
    # ─── payments.py — Stripe webhook recompute order auto-creation ──
    # RETIRED in Phase 5.5 / C (2026-05-19). The single qualified
    # ``server._create_order_from_invoice(invoice_doc)`` call inside
    # ``_record_payment_from_stripe`` (was line 658, recompute branch)
    # was migrated to a lazy
    # ``from app.services.orders import create_order_from_invoice``
    # import — mirroring the existing ``_get_stripe_config`` /
    # ``_record_payment_from_stripe`` lazy-import pattern used by the
    # webhook integration boundary at ``server.py:13907-13911``.
    #
    # CRITICAL CO-RETIREMENT: this was the LAST production consumer
    # of ``import server`` in ``app/routers/payments.py``. The
    # module-level ``import server`` line was REMOVED in the same
    # edit. ``app/routers/payments.py`` is now fully decoupled from
    # the ``server`` module surface.
    #
    # Cross-shape retirement: this symbol ALSO had a
    # ``from server import _create_order_from_invoice`` shape in
    # ``backend/legal_workflow.py:2158`` (deposit auto-convert). That
    # site retired in the same wave — see ``BRIDGE_INVENTORY``
    # tombstone comment for ``_create_order_from_invoice``.
    #
    # Asserted by:
    #   * ``tests/test_phase5_5_c_order_creation_golden.py`` —
    #     8-scenario behavioural pin (G1-G8), suite identical pre
    #     and post extraction via single ``_resolve_helper`` switch
    #     point.
    #
    # QualifiedUsageSite(
    #     symbol="_create_order_from_invoice",
    #     consumer_file="app/routers/payments.py",
    #     ...
    # ),  # RETIRED Phase 5.5 / C
    # ─── admin_integrations.py — closure-local lazy runtime accessor ─
    # RETIRED in Phase 5.5 / F (2026-05-19). The single
    # ``getattr(server, "tracking_config_service", None)`` site inside
    # ``_tracking_env_keys()`` was migrated to the canonical accessor
    # ``app.services.tracking_config.get_service``. The function-local
    # ``import server`` was removed in the same edit. Cold-start
    # semantics (``None`` → all-empty fallback) preserved 1:1.
    # Asserted by
    # ``tests/test_phase5_5_f_tracking_config_accessor.py``.
    #
    # QualifiedUsageSite(
    #     symbol="tracking_config_service",
    #     consumer_file="app/routers/admin_integrations.py",
    #     ...
    # ),  # RETIRED Phase 5.5 / F
)
"""Parallel bridge surface DISCOVERED by C-5f AST re-audit:
production sites that use ``import server`` + ``server.X`` qualified
access instead of (or in addition to) ``from server import X``.

This surface is NOT in ``BRIDGE_INVENTORY`` because its retirement
mechanic is different (see ``QualifiedUsageSite`` docstring).

C-5f baseline: 6 entries. Phase 5.5 / A retired 1 entry
(``logger@payments.py``, 8 sites → 0). Phase 5.5 / B retired 3 entries
(``logger@calculations.py`` + 2 calculator engine sites,
3 sites → 0; ``import server`` line removed from calculations.py
entirely). Phase 5.5 / F retired 1 entry
(``tracking_config_service@admin_integrations.py``, 1 site → 0;
the closure-local ``import server`` in ``_tracking_env_keys`` removed
in the same edit). Phase 5.5 / C retired the LAST entry
(``_create_order_from_invoice@payments.py``, 1 site → 0; module-level
``import server`` line removed from payments.py — payments router
fully decoupled from server module surface). Current active count:
**0 entries** — the qualified-access bridge surface is now empty.
Documented inline in each consumer file's module docstring
(payments.py:1-25 post-5.5/C; admin_integrations.py:42-66 post-5.5/F).
C-5f formalizes the ledger; each 5.5 wave maintains it."""


PHASE_5_5_A_RETIRED_QUALIFIED_SITES: tuple[tuple[str, str], ...] = (
    ("logger", "app/routers/payments.py"),
)
"""Sites retired in Phase 5.5 / A (payments logger qualified-access
warm-up wave). The 8 ``server.logger.exception(...)`` call sites in
``app/routers/payments.py`` were replaced 1:1 with module-local
``logger.exception(...)`` calls; the ``logger`` module attribute is
published at module-load time as ``logging.getLogger("bibi.payments")``.

Per-site retirement is asserted by
``tests/test_phase5_5_a_payments_logger.py``. The ``logger`` symbol
left ``PHASE_5_5_BOUNDARY`` in Phase 5.5 / B once the calculations.py
site (1 prod call at line ~733) was also migrated to a module-local
logger (namespace ``bibi.calculations``)."""


PHASE_5_5_B_RETIRED_QUALIFIED_SITES: tuple[tuple[str, str], ...] = (
    ("logger", "app/routers/calculations.py"),
    ("_calculate_korea", "app/routers/calculations.py"),
    ("calculator_calculate", "app/routers/calculations.py"),
)
"""Sites retired in Phase 5.5 / B (calculator engine extraction wave).

Three qualified-access sites in ``app/routers/calculations.py`` were
migrated 1:1:

  * ``server.logger.warning(...)`` (1 site, line 733)
    → ``logger.warning(...)`` where
      ``logger = logging.getLogger("bibi.calculations")``
      (module-local, published at module-load time).

  * ``server._calculate_korea(...)`` (1 site, line 369)
    → ``_calculate_korea(...)`` where the symbol is imported via
      ``from app.services.calculator import _calculate_korea``.

  * ``server.calculator_calculate(...)`` (1 site, line 371)
    → ``calculator_calculate(...)`` where the symbol is imported via
      ``from app.services.calculator import calculator_calculate``.

The ``import server`` line in ``calculations.py`` was REMOVED in the
same wave — zero ``server.X`` qualified usage survives in this router
post-5.5/B (asserted by
``tests/test_phase5_5_b_calculator_extraction.py``).

Function bodies for both calculator engines moved byte-identically
from ``server.py:9872`` and ``server.py:10126`` to
``app/services/calculator.py``. The only mechanical substitutions
applied during the move were the established C-4i pattern
(``db.X`` → ``get_db().X``, 2 sites in ``_calculate_korea``) and the
5.5/A pattern (module-local ``logger = logging.getLogger("bibi.calculator")``,
1 ``logger.warning`` site in ``_calculate_korea``). The FastAPI route
``POST /api/calculator/calculate`` is now registered against the
extracted ``calculator_calculate`` via imperative
``fastapi_app.post(...)`` in ``server.py`` — OpenAPI operationId
preserved (driven by the function ``__name__``, which is unchanged).
Route surface remains 618 paths / 679 methods.

Golden-parity verified: 18 representative inputs (10 USA + 8 Korea)
producing pinned SHA-256 hashes (see
``tests/test_phase5_5_b_calculator_extraction.py::PINNED_HASHES``).

Symbol shrinkage in ``PHASE_5_5_BOUNDARY`` post-5.5/B:
  * ``logger`` — REMOVED (both consumer files now use module-local
    loggers: payments.py via 5.5/A, calculations.py via 5.5/B)
  * ``_calculate_korea`` — REMOVED (canonical home in
    app/services/calculator.py)
  * ``calculator_calculate`` — REMOVED (canonical home in
    app/services/calculator.py)
"""


PHASE_5_5_F_RETIRED_QUALIFIED_SITES: tuple[tuple[str, str], ...] = (
    ("tracking_config_service", "app/routers/admin_integrations.py"),
)
"""Sites retired in Phase 5.5 / F (tracking config accessor follow-on).

One qualified-access site in ``app/routers/admin_integrations.py``
(closure-local inside ``_tracking_env_keys()`` at line ~100) was
migrated:

  * ``getattr(server, "tracking_config_service", None)``
    → ``get_service()`` imported from
      ``app.services.tracking_config`` (canonical accessor module).

The function-local ``import server`` line inside
``_tracking_env_keys`` was REMOVED in the same edit (it was the only
remaining ``server.X`` reference in that function).

Cold-start semantics preserved 1:1 — ``get_service()`` returns
``None`` before the service is bound, and the caller falls back to
the all-empty-string dict exactly as before.

The accessor follows the established C-5b/C-5c pattern: a single
``set_service(instance)`` writer is invoked from ``server.py``
startup (server.py:2484-2487, immediately after
``await tracking_config_service.load()`` succeeds) to publish the
live instance. Object identity is preserved 1:1 with the legacy
``server.tracking_config_service`` module-global.

Symbol shrinkage in ``PHASE_5_5_BOUNDARY`` post-5.5/F:
  * ``tracking_config_service`` — REMOVED (no remaining qualified-
    access consumer)

This leaves ``QUALIFIED_USAGE_BRIDGES`` at **1 entry** —
``_create_order_from_invoice`` in payments.py (target wave 5.5/C).
"""


PHASE_5_5_C_RETIRED_QUALIFIED_SITES: tuple[tuple[str, str], ...] = (
    ("_create_order_from_invoice", "app/routers/payments.py"),
)
"""Sites retired in Phase 5.5 / C (order-creation orchestration —
first true orchestration extraction of the Phase 5 cycle).

One qualified-access site in ``app/routers/payments.py`` (inside the
Stripe webhook recompute branch of ``_record_payment_from_stripe``,
was line 658) was migrated:

  * ``server._create_order_from_invoice(invoice_doc)``
    → ``from app.services.orders import create_order_from_invoice``
      (lazy local import) followed by
      ``await create_order_from_invoice(invoice_doc)``

CRITICAL: the module-level ``import server`` line in
``app/routers/payments.py`` was REMOVED in the same edit. This was
its last consumer.  ``app/routers/payments.py`` is now fully
decoupled from the ``server`` module surface.

Cross-shape co-retirement: the same symbol ALSO had a
``from server import _create_order_from_invoice`` shape in
``backend/legal_workflow.py:2158`` (deposit auto-convert lazy WPS433
bridge). Both shapes retired in this wave — see the
``BRIDGE_INVENTORY`` tombstone for the from-server side and this
constant for the qualified-access side.

Definition retired from ``server.py``: both
``_create_order_from_invoice`` (orchestration helper) and its
sibling ``_build_order_steps_from_invoice`` (pure invoice→steps
transform) were deleted from ``server.py`` and moved to
``app/services/orders.py`` (the public entry point
``create_order_from_invoice`` is exported via ``__all__``; the
sibling stays module-private). The in-file caller in
``invoice_mark_paid`` (was line 14469) now uses the lazy local
import shape, identical to how the Stripe webhook now consumes it.

Behaviour parity asserted by:
  * ``tests/test_phase5_5_c_order_creation_golden.py`` — 8-scenario
    behavioural pin (G1 Stripe path, G2 manual mark-paid, G3 deposit
    auto-convert, G4 empty-items default workflow, G5 null IDs,
    G6 notification failure resilience, G7 sio failure resilience,
    G8 missing invoice.id early-return). The suite is identical pre
    and post extraction — a single ``_resolve_helper`` switch point
    chooses ``server._create_order_from_invoice`` (pre-5.5/C) or
    ``app.services.orders.create_order_from_invoice`` (post-5.5/C).
    Pre-extraction: 8 PASS. Post-extraction: 8 PASS.

Symbol shrinkage in ``PHASE_5_5_BOUNDARY`` post-5.5/C:
  * ``_create_order_from_invoice`` — REMOVED (last consumer in both
    shapes retired; defined-in-server.py removed)

This leaves ``QUALIFIED_USAGE_BRIDGES`` at **0 entries** — the
qualified-access bridge surface is empty.  Tier-C ``from server
import X`` ``BRIDGE_INVENTORY`` shrinks by 1 (10 → 9 remaining
entries) — the symbol's dual-shape retirement is recorded in both
inventories.
"""


PHASE_5_5_D_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("_require_customer",      "cabinet_financials.py",
     "from_server_import (aliased lazy WPS433 in wrapper at line 71)"),
    ("_ensure_customer_seed",  "cabinet_financials.py",
     "from_server_import (lazy WPS433 in wrapper at line 86)"),
)
"""Bridges retired in Phase 5.5 / D (customer-auth helpers extraction
— first orchestration extraction touching auth-gated endpoints).

Two Tier-C ``from server import …`` lazy WPS433 sites in
``cabinet_financials.py`` were retired by redirecting each wrapper
to the new canonical home:

  * ``cabinet_financials._require_customer`` (line 71-82)
    → ``from app.services.customers import require_customer``
      followed by ``return await require_customer(authorization)``

  * ``cabinet_financials._ensure_customer_seed`` (line 86-95)
    → ``from app.services.customers import ensure_customer_seed``
      followed by ``await ensure_customer_seed(customer_id)``

The wrappers themselves are PRESERVED inside ``cabinet_financials.py``
because the existing in-file callers (``cabinet_financials.py``
endpoints at lines 181, 238, 316, ...) use the underscore-prefixed
names through closure. They are now THIN one-line delegates to the
canonical ``app.services.customers`` API — NOT compat shims. The
underscore-prefixed shape is retained as a localized lexical alias
inside ``cabinet_financials.py`` only; no other module references
the underscore names.

Definitions retired from ``server.py``: both ``_require_customer``
(auth-gate helper, ~30 LOC) and ``_ensure_customer_seed`` (collection
seeder, ~470 LOC including private sibling ``_seed_customer_financials``)
were DELETED from ``server.py`` and moved verbatim to
``app/services/customers.py`` (the public entry points
``require_customer`` and ``ensure_customer_seed`` are exported via
``__all__``; the private sibling ``_seed_customer_financials`` stays
module-private inside the new home).

In-file callers in ``server.py``: 21 sites were bulk-migrated to
the bare public names via a single module-load import of
``require_customer`` / ``ensure_customer_seed`` at server.py:9947-9951
(comment block "Phase 5.5 / D — customer helpers, retired from
server.py"). Breakdown:
  *  5 ``await require_customer(authorization)`` sites — cabinet
     auth gates (favorites, profile, orders summary, deposits,
     invoices)
  * 14 ``await ensure_customer_seed(customer_id)`` sites — cold-
     start collection bootstrap (deposits, financial templates,
     calculator drafts, invoice templates, payment methods,
     notifications, audit log, etc.)
  *  2 misc references (re-export, docstring cross-ref)

Aux dependencies (per D2 mandate "no token logic touch, no
shipment-helper move"):

  * ``_resolve_bearer`` (server.py auth core helper — reads JWT,
    queries customer collection, returns customer dict | None)
    STAYS in ``server.py`` and is registered under
    ``EXTRACTION_AUX_BRIDGES`` with
    ``kind="CUSTOMER_AUTH_DEP"``, ``tier="C-aux"``,
    consumed by ``app/services/customers.py`` via a lazy local
    import inside ``require_customer``. Rationale: extraction
    would require touching JWT decode logic + customer-collection
    schema simultaneously — D2 forbids both. Same pattern as the
    Phase 5.5/B calculator engine extraction (43 calc constants
    deliberately stayed in ``server.py`` as aux bridges, will be
    retired in 5.5/B-deep when the entire calculator cluster moves
    at once).

  * ``generate_route`` (shipment route-polyline helper used by
    the customer seeder when bootstrapping the shipments
    collection — pure geometric helper, no auth coupling) STAYS
    in ``server.py`` for the same reason: its retirement is bound
    to the shipments-orchestration wave (5.5/I —
    ``ensure_shipment_stages``), not the customer-auth wave.

Behaviour parity asserted by:
  * ``tests/test_phase5_5_d_customer_helpers_golden.py`` —
    8-scenario behavioural pin (G1 valid bearer returns customer
    dict, G2-G5 401 surface across missing/malformed/expired/
    unknown-customer bearer shapes, G6 cold-start collections
    bootstrap is idempotent, G7 second seed call is a no-op,
    G8 customer-profile response shape). The suite is identical
    pre and post extraction — a single ``_resolve_helpers``
    switch point chooses ``server._require_customer`` /
    ``server._ensure_customer_seed`` (pre-5.5/D) or
    ``app.services.customers.require_customer`` /
    ``app.services.customers.ensure_customer_seed`` (post-5.5/D).
    Pre-extraction: 8 PASS (label "pre-5.5/D"). Post-extraction:
    8 PASS (label "post-5.5/D").

Symbol shrinkage in ``BRIDGE_INVENTORY`` post-5.5/D:
  * ``_require_customer``      — REMOVED (canonical home in
                                 app/services/customers.py)
  * ``_ensure_customer_seed``  — REMOVED (canonical home in
                                 app/services/customers.py)

Symbol shrinkage in ``TIER_C_REQUIRES_REFACTOR`` post-5.5/D:
  * Two entries removed → Tier-C count 9 → 7.

Symbol shrinkage in ``PHASE_5_5_BOUNDARY`` post-5.5/D:
  * Two entries removed → Phase 5.5 boundary 9 → 7.

New entries in ``EXTRACTION_AUX_BRIDGES`` post-5.5/D:
  * ``_resolve_bearer``  (kind="CUSTOMER_AUTH_DEP", tier="C-aux")
  * ``generate_route``   (kind="CUSTOMER_AUTH_DEP", tier="C-aux")

Aux-bridge surface total: 43 (calc-engine) → **45** (calc-engine + 2
customer-auth-dep). Retirement of both 5.5/D aux bridges is bound
to the same follow-on waves that retire their cluster (auth core
wave + shipments-orchestration wave respectively).
"""


PHASE_5_5_E_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("_get_stripe_config", "app/routers/payments.py",
     "Wave-1 router-internal placement (def-site) corrected → moved to app/services/stripe_config.py as get_stripe_config"),
    ("_get_stripe_config", "cabinet_financials.py",
     "latent ImportError bridge (`from server import _get_stripe_config`) repaired → `from app.services.stripe_config import get_stripe_config`"),
)
"""Bridges retired in Phase 5.5 / E (Stripe config helper — first
wave to combine architectural-move + public-name normalization +
explicit latent production bugfix in a single commit).

Step-1 audit discovery (re-scoped the wave at kickoff)
──────────────────────────────────────────────────────

The mandate framing assumed ``_get_stripe_config`` still lived in
``server.py``. The AST audit on the live tree showed otherwise:

  * The function definition was already at
    ``app/routers/payments.py:109`` (extracted to that router during
    Wave 1 as mechanical co-location with the Stripe webhook +
    checkout handlers).
  * The ``BRIDGE_INVENTORY`` entry pointed at ``server.py`` as the
    def-site — an **inventory drift** that had persisted since Wave 1.
  * The ``cabinet_financials.py:366`` consumer carried a
    ``from server import _get_stripe_config`` lazy WPS433 bridge —
    a line that ALWAYS raised ``ImportError`` at runtime because
    ``server`` never exported the symbol module-level. The
    surrounding ``except Exception`` masked the failure and the
    cabinet checkout flow silently degraded to its
    ``"Онлайн-оплата картою тимчасово недоступна"`` stub branch.

The user-approved re-scope (Option A — full reformulated 5.5/E)
mandated:

  1. Move the helper from ``app/routers/payments.py`` to
     ``app/services/stripe_config.py`` (correct architectural
     taxonomy slot — services own cross-domain helpers; routers
     own HTTP shape).
  2. Rename to ``get_stripe_config`` (drop underscore — mirror of
     5.5/C ``create_order_from_invoice`` + 5.5/D ``require_customer``).
  3. Repair the latent ``cabinet_financials.py`` bridge by pointing
     it at the new canonical home (explicit behaviour repair —
     the cabinet flow can now actually exercise Stripe checkout
     instead of silently stub-modding).

10 callers migrated
───────────────────

  * 7 in-file callers in ``app/routers/payments.py`` — bulk-renamed
    via single ``replace_all`` pass on ``cfg = await
    _get_stripe_config()`` → ``cfg = await get_stripe_config()``
    plus a module-level ``from app.services.stripe_config import
    get_stripe_config`` added at the top of the router.
  * 2 ``server.py`` lazy imports — the Stripe-webhook handler at
    ``server.py:~13927`` (which previously imported the helper
    transitively via ``from app.routers.payments import …`` — now
    splits the import: ``get_stripe_config`` from the service
    module + ``_confirm_cabinet_payment`` /
    ``_record_payment_from_stripe`` from the router) and the
    legal-deposit checkout bridge at ``server.py:~12327``.
  * 1 ``cabinet_financials.py`` call site (the broken
    ``from server import`` bridge) — repointed to the new canonical
    home. This is the intentional behaviour repair.

Definitions retired
───────────────────

  * ``_get_stripe_config`` definition deleted from
    ``app/routers/payments.py`` (was ~57 LOC).
  * Module docstring updated to reflect the relocation.
  * Module-level ``HELPERS:`` section in the router docstring
    redocumented to reflect the post-5.5/E surface (only
    ``_confirm_cabinet_payment`` + ``_record_payment_from_stripe``
    remain in the router; ``get_stripe_config`` lives in the
    service module).

Behaviour parity asserted by
────────────────────────────

  * ``tests/test_phase5_5_e_stripe_config.py`` — 12-assertion suite:
      - 6 structural pins (canonical module exists; def removed from
        router; router imports from service home; ``server.py``
        no longer imports from the router; ``cabinet_financials.py``
        no longer imports from ``server``; all callers use the
        public name)
      - 3 behavioural goldens (G7 full configured doc → 18-key
        shape; G8 missing doc → default shape; G9 legacy
        ``paymentMethods`` list → ``enabledMethods`` dict
        conversion preserved)
      - 1 latent-bug repair pin (G10 — the
        ``from server import _get_stripe_config`` line is gone AND
        the canonical import resolves without raising
        ``ImportError``)
      - 1 inventory pin (G11 — ``BRIDGE_INVENTORY`` 8 → 7,
        ``TIER_C_REQUIRES_REFACTOR`` 7 → 6, ``PHASE_5_5_BOUNDARY``
        7 → 6, ``QUALIFIED_USAGE_BRIDGES`` stays 0,
        ``EXTRACTION_AUX_BRIDGES`` stays 45 — D3=A no aux)
      - 1 OpenAPI freeze (paths=618, ops=679)

    The behavioural tests use a single ``_resolve_helper`` switch
    point so the SAME file runs UNCHANGED before AND after the
    cutover. Pre-extraction: G7-G9 + G12 PASS, structural 1-6 +
    G10 + G11 FAIL (audit-trail label ``pre-5.5/E``).
    Post-extraction: all 12 PASS (label ``post-5.5/E``).

Symbol shrinkage in ``BRIDGE_INVENTORY`` post-5.5/E:
  * ``_get_stripe_config`` — REMOVED (canonical home in
                             app/services/stripe_config.py)

Symbol shrinkage in ``TIER_C_REQUIRES_REFACTOR`` post-5.5/E:
  * One entry removed → Tier-C count 7 → 6.

Symbol shrinkage in ``PHASE_5_5_BOUNDARY`` post-5.5/E:
  * One entry removed → Phase 5.5 boundary 7 → 6.

New entries in ``EXTRACTION_AUX_BRIDGES`` post-5.5/E:
  * NONE — D3=A. The helper is self-contained over
    ``IntegrationConfigsRepository`` (single repository read, pure-
    shape transformation, no env fallback, no cross-module deps).

Intentional behaviour repair scope (documented honestly)
────────────────────────────────────────────────────────

The 5.5/E commit changes the runtime behaviour of ONE endpoint
that previously silently degraded:

  Before: ``GET /api/customer-cabinet/{customer_id}/deposits/checkout``
          (or the equivalent cabinet-flow Stripe checkout endpoint
          that wraps ``_create_cabinet_stripe_checkout`` in
          ``cabinet_financials.py``) raised an internal
          ``ImportError`` on ``from server import
          _get_stripe_config``, got swallowed by the broad
          ``except Exception``, and the endpoint returned the
          stub response *"Онлайн-оплата картою тимчасово
          недоступна. Зв'яжіться з менеджером для отримання
          банківських реквізитів."*

  After:  the import resolves to the canonical
          ``app.services.stripe_config.get_stripe_config``, the
          helper executes normally, and if Stripe is configured
          (``isEnabled=True``, ``secretKey`` non-empty), the
          cabinet flow proceeds to the real Stripe checkout path.
          If Stripe is NOT configured (or admin disabled it), the
          endpoint still returns the same stub message — that
          branch is preserved verbatim (gated on ``not cfg`` /
          ``not cfg.get("isEnabled")`` / ``not cfg.get("secretKey")``
          checks immediately after the import).

This is a **deliberate latent-bug repair**, not an accidental
behaviour change. The repair is logged here, in
``PHASE5_5_E_STRIPE_CONFIG_CLOSED.md`` section 4, and in the
``cabinet_financials.py`` inline comment block at the repaired
call site.
"""


PHASE_5_5_F2_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("_tracking_enabled", "app/routers/admin_identity.py",
     "from_server_import (via local wrapper at line 67-69 — wrapper retired entirely; module-level canonical import added)"),
)
"""Bridges retired in Phase 5.5 / F2 (TRACKING_ENABLED env-flag reader
— the last low-risk config helper).

Pre-flight audit (Step 1)
─────────────────────────

The mandate framing described ``_tracking_enabled`` as a candidate
for ``tracking_config_service.get_service()`` delegation.  AST audit
on the live tree showed:

  * The helper at ``server.py:2963`` is a **pure env reader**:

    .. code-block:: python

        def _tracking_enabled() -> bool:
            return os.environ.get("TRACKING_ENABLED", "true").strip().lower() not in (
                "0", "false", "no", "off",
            )

    No service lookup, no module-global access — just
    ``os.environ.get(...)``.

  * The mandate's conditional clause *"Если текущий helper читает
    module-global/service напрямую — заменить на get_service()"*
    therefore did NOT apply.  The strict 1:1 mandate (*"Сохранить
    сигнатуру/поведение 1:1"*) won — verbatim port.

  * Inventory drift (mirror of 5.5/E discovery pattern):
    ``BRIDGE_INVENTORY`` claimed ``consumers_count=1``
    (``admin_identity``), but the actual caller topology was 5
    sites — 4 in-file callers in ``server.py`` plus the 1
    cross-module wrapper at ``admin_identity.py:67-69``.  The
    inventory metadata only tracked the cross-module bridge; the
    4 in-file callers were not visible to the bridge accounting.

User-mandate satisfaction
─────────────────────────

  * Target = ``app/services/tracking_config.py`` ✅
    (sibling function next to ``TrackingConfigService``).
  * Public name = ``tracking_enabled`` (no underscore) ✅.
  * Pattern = sibling function in existing module — NOT an accessor
    over service state ✅ (helper reads env only; coupling it to
    ``get_service()`` would introduce service-lifecycle dependency
    forbidden by *"no TrackingConfigService lifecycle changes"*).
  * Compat shim = none ✅ (admin_identity local wrapper retired
    entirely; all 5 callers migrated to canonical name).
  * Golden scope = G1-G4 + 4 structural pins + OpenAPI freeze ✅.

5 callers migrated
──────────────────

  * 4 in-file callers in ``server.py`` (lines 6502, 6558, 20020,
    20084) — bulk-renamed via two ``replace_all`` passes (one for
    the standard indentation level, one for the over-indented form
    inside a nested ``try`` block).  Module-load import block
    added immediately after the retired def site at
    ``server.py:2960``.
  * 1 cross-module bridge in ``app/routers/admin_identity.py:67-69``
    — the local ``def _tracking_enabled()`` wrapper that
    lazy-imported ``from server import _tracking_enabled as _te``
    was RETIRED ENTIRELY.  Replaced with a module-level
    ``from app.services.tracking_config import tracking_enabled``
    import; the single call site at line 352 (now 362) updated to
    the bare public name.  The module docstring's ``Lazy bridges
    to server.py`` section updated to remove the retired wrapper
    entry.

Definition retired
──────────────────

  * ``_tracking_enabled`` (server.py:2963) deleted entirely (3 LOC).
  * Replaced with a 9-line tombstone comment block + a module-load
    import line ``from app.services.tracking_config import
    tracking_enabled``.

Behaviour parity asserted by
────────────────────────────

  * ``tests/test_phase5_5_f2_tracking_enabled.py`` — 9-test contract:
      - 4 behavioural goldens (G1 default → True; G2 disabled
        tokens × 8 parametrized variants → False; G3 env-var
        absent → True default; G4 malformed value × 7 parametrized
        variants → True fallback)
      - 4 structural pins (canonical export verified — sync, bool,
        in ``__all__``; server.py no longer defines the helper;
        admin_identity.py uses canonical home + public name;
        inventory shrunk 7→6 / 6→5 / 6→5 + ``PHASE_5_5_F2_RETIRED_BRIDGES``
        exists + exported)
      - 1 OpenAPI freeze (paths=618, ops=679)

    Total executed test cases: 22 (with parametrization).  Suite
    file is identical pre- and post-cutover via the
    ``_resolve_helper`` switch point.

Symbol shrinkage in ``BRIDGE_INVENTORY`` post-5.5/F2:
  * ``_tracking_enabled`` — REMOVED (canonical home in
                            app/services/tracking_config.py)

Symbol shrinkage in ``TIER_C_REQUIRES_REFACTOR`` post-5.5/F2:
  * One entry removed → Tier-C count 6 → 5.

Symbol shrinkage in ``PHASE_5_5_BOUNDARY`` post-5.5/F2:
  * One entry removed → Phase 5.5 boundary 6 → 5.

New entries in ``EXTRACTION_AUX_BRIDGES`` post-5.5/F2:
  * NONE — helper is a pure env reader with no cross-module
    coupling.  No aux deps registered.

What was NOT changed (forbidden scope, all observed)
────────────────────────────────────────────────────

  * ❌ no tracking worker changes — workers continue to invoke
    ``tracking_enabled()`` from the same call sites with the same
    semantics.
  * ❌ no ``TrackingConfigService`` lifecycle changes — the
    accessor pattern at ``set_service`` / ``get_service`` /
    ``clear_service_for_tests`` is untouched.
  * ❌ no tracking config schema changes — the ``integration_configs``
    collection is not consulted by this helper.
  * ❌ no env var rename — ``TRACKING_ENABLED`` env-var name is
    preserved; default ``"true"``; disabled tokens preserved.
  * ❌ no ``app.state`` changes — helper is module-local; no
    FastAPI ``app.state`` interaction.
  * ❌ no route changes — OpenAPI surface frozen at paths=618 ops=679.
  * ❌ no broad tracking refactor — only the env-flag reader
    relocated; the entire VesselFinder + ShipsGo + AfterShip
    cluster is unaffected.
  * ❌ no batching with identity/resolver/shipment work — D6
    (5.5/G/H/I are separate waves) preserved.
"""


PHASE_5_5_G_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("identity_runtime", "app/routers/admin_resolver.py + admin_identity.py + admin_shipments.py",
     "from_server_import (MODULE_REF — 3 router consumers; each had a `_identity_runtime()` local wrapper that lazy-imported `from server import identity_runtime`; all 3 wrappers redirected to canonical `from app.services.identity_runtime import identity_runtime`)"),
    ("_run_auto_resolver", "app/services/identity_runtime.py:235 (M-4 lazy bridge)",
     "from_server_import (lazy bridge inside IdentityRuntimeService.run_auto_resolver — retired entirely; body moved verbatim from server.py:5657)"),
    ("_persist_resolver_hits", "app/services/identity_runtime.py:251 (M-5 lazy bridge)",
     "from_server_import (lazy bridge inside IdentityRuntimeService.persist_resolver_hits — retired entirely; body moved verbatim from server.py:5677)"),
)
"""Bridges retired in Phase 5.5 / G (identity-resolver cluster — the
first semantic-orchestration cluster extraction of Phase 5.5).

Pre-flight audit (Step 1)
─────────────────────────

Cluster scope established by D1 mandate (*"keep cluster together —
identity_runtime + _run_auto_resolver + _persist_resolver_hits"*).
AST audit confirmed the three symbols form a single retirement unit:

  * ``identity_runtime`` (MODULE_REF) — the boundary-wrapper module
    had been at ``app/services/identity_runtime.py`` since Phase
    3.2/C-1. Its Tier-C status came exclusively from the two M-4/M-5
    lazy bridges into ``server.py`` for the legacy ``_AutoResolver``
    cluster. Once those bridges retire, the module is fully owned —
    the 3 router consumers can migrate to the canonical home.

  * ``_run_auto_resolver`` (server.py:5657) — sync trampoline that
    constructs ``_AutoResolver``, runs it, and persists a trace
    snapshot on ``shipments.resolver.*``. Pure I/O via ``db``
    + ``logger``; no other server-side coupling.

  * ``_persist_resolver_hits`` (server.py:5677) — applies resolver
    output to the shipment (container/vessel binds + events).
    Reads/writes ``db.shipments`` + invokes ``add_shipment_event``
    (lazy aux bridge — retirement deferred to 5.5/I).

Travels with the cluster (module-private in the new home, never
were bridges):

  * ``_resolver_shipsgo_lookup`` (server.py:5628) — thin shim around
    ``_external_container_lookup``. The legacy
    ``globals().get(...)`` forward-reference pattern was replaced by
    an explicit ``_external_container_lookup_callable()`` lazy-bridge
    accessor in the new home (semantics byte-identical).

  * ``_resolver_vf_search`` (server.py:5640) — VF-search stub
    returning None.

  * ``_get_auto_resolver`` (server.py:5647) — ``_AutoResolver``
    factory, switched to use the canonical ``_db()`` accessor.

Aux deps registered in ``EXTRACTION_AUX_BRIDGES`` (kind=RESOLVER_DEP,
tier=C-aux — STAY in server.py per D3/D5/D6):

  * ``_external_container_lookup`` (server.py:18941) — ShipsGo / API
    lookup. Retirement target: 5.5/H VesselFinder wave.
  * ``add_shipment_event`` (server.py:5539) — shipment-events writer
    with sio side-channel. Retirement target: 5.5/I shipment
    orchestration wave.

The ``from resolver_engine import (AutoResolver, MIN_CONFIDENCE)``
import block moved with the cluster (sole consumers were the 5
helpers above; not separately registered as an aux because
``resolver_engine`` is an already-extracted external module).

User-mandate satisfaction
─────────────────────────

  * D1 keep cluster together — 3 retirements in one focused commit ✅.
  * D2 canonical home = ``app/services/identity_runtime.py`` ✅.
  * D3 no worker-lifecycle refactor — workers continue to call
    ``identity_runtime.run_auto_resolver`` from the existing
    ``update_shipment_position`` tick (server.py:5856-5857) and the
    admin shipment-resolver-run endpoint; no scheduler/lifecycle
    changes ✅.
  * D4 no resolver-algorithm edits — function bodies moved
    BYTE-FOR-BYTE; the only delta is the ``db`` reference (legacy
    bare-name → ``_db()`` accessor) and the ``add_shipment_event``
    call (legacy bare-name → ``_add_shipment_event`` thin wrapper)
    ✅.
  * D5 no schema evolution — ``shipments.resolver.*`` trace shape
    + ``shipments.container/.vessel`` set-blocks + ``events[]``
    push shape + ``shipment:event`` sio payload — all 1:1 ✅.
  * D6 no async orchestration changes — all 5 functions remain
    async with identical signatures; the M-4/M-5 boundary methods
    still ``await`` the same underlying chain; no scheduling
    surface delta ✅.
  * D7 golden suite FIRST — ``tests/test_phase5_5_g_identity_cluster.py``
    written before extraction; 7/12 PASS pre-extraction (G1-G6
    behavioural + O1 OpenAPI freeze) and 12/12 PASS post-extraction;
    structural pins S1-S5 demonstrably differentiate pre vs post ✅.

Inventory delta (all hit exactly)
─────────────────────────────────

  ============================  ====  ====  ====
  Inventory                     Pre   Post  Δ
  ============================  ====  ====  ====
  BRIDGE_INVENTORY              6     3     −3
  TIER_C_REQUIRES_REFACTOR      5     2     −3
  PHASE_5_5_BOUNDARY            5     2     −3
  EXTRACTION_AUX_BRIDGES        45    47    +2
  QUALIFIED_USAGE_BRIDGES       0     0     0
  ============================  ====  ====  ====

Cluster status after 5.5/G
──────────────────────────

  ``Phase 5.5`` boundary now has TWO symbols remaining:

    * ``_vf_extract_vessels``       → 5.5/H VesselFinder wave
    * ``ensure_shipment_stages``    → 5.5/I shipments orchestration wave

  These are the LAST two Tier-C bridges in Phase 5.5. After both
  retire, ``server.py`` will hold no Tier-C ``from server import …``
  bridges — only Tier-A/B utility imports + the operational shell.
  Phase 6 (Production hardening) starts immediately after 5.5/I.

  ``Cleanup era`` is officially closed by 5.5/G.  5.5/F2 retired
  the last config-helper; 5.5/G retires the first orchestration
  cluster.  Remaining waves are pure domain extractions.
"""


# ─────────────────────────────────────────────────────────────────────
# Phase 5.5 / H — VesselFinder cluster retirement (2026-05-20)
# ─────────────────────────────────────────────────────────────────────

PHASE_5_5_H_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("_vf_extract_vessels",
     "server.py:19194 (vesselfinder_scraper alias) + shipment_identity_resolver.py:406 (lazy bridge)",
     "from_server_import (HELPER_FUNCTION — the `extract_vessels_from_payload as _vf_extract_vessels` alias on the `from vesselfinder_scraper import …` block in server.py removed; the single cross-module consumer at shipment_identity_resolver.py migrated to direct `from vesselfinder_scraper import extract_vessels_from_payload`; the in-file caller at server.py:19928 (VF jobs payload-parse) renamed to the bare canonical name. Canonical home is `vesselfinder_scraper` — the helper was ALREADY defined there pre-Phase-5; the alias was vestigial)"),
    ("_external_container_lookup",
     "server.py:18978 (latent NameError call site) + app/services/identity_runtime.py:171 (5.5/G-era _external_container_lookup_callable accessor)",
     "EXTRACTION_AUX_BRIDGES kind=RESOLVER_DEP, tier=C-aux (registered in 5.5/G as a lazy-bridge target; body MOVED VERBATIM from server.py:18798 to app/services/tracking_providers.py as the public `external_container_lookup` — no underscore prefix; the 5.5/G-era `_external_container_lookup_callable()` accessor in identity_runtime retired entirely; `_resolver_shipsgo_lookup` rewired to import the canonical function directly from `app.services.tracking_providers`. The latent call site in `tracking_quick_track` at server.py:18978 — which referenced an undefined symbol and would have raised NameError if the code path executed — repaired by routing through the canonical home, mirror of the 5.5/E `cabinet_financials.py` latent-bug repair pattern)"),
)
"""Bridges retired in Phase 5.5 / H (VesselFinder cluster — the
second cluster-retirement wave of the Phase 5.5 cycle).

Pre-flight audit
────────────────

Cluster scope established by D1 mandate (*"cluster = ``_vf_extract_vessels``
+ ``_external_container_lookup``"*). AST audit confirmed the two symbols
form a single retirement unit:

  * ``_vf_extract_vessels`` (HELPER_FUNCTION, Tier-C — was in
    BRIDGE_INVENTORY since C-3B) — the alias on the
    ``from vesselfinder_scraper import …`` import block in
    ``server.py:19194`` (legacy carry-over: the helper has always lived
    in ``vesselfinder_scraper.py``). The single cross-module consumer
    was the lazy-bridge ``from server import _vf_extract_vessels`` in
    ``shipment_identity_resolver.py:406``.

  * ``_external_container_lookup`` (RESOLVER_DEP, Tier C-aux —
    registered in EXTRACTION_AUX_BRIDGES by 5.5/G) — body lived at
    ``server.py:18798`` until 5.5/H. The 5.5/G-era
    ``_external_container_lookup_callable()`` accessor in
    ``app/services/identity_runtime.py`` was the sole resolution
    path; the in-file ``tracking_quick_track`` call site at
    ``server.py:18978`` referenced an undefined symbol (latent
    NameError — would crash if the code path executed; never observed
    in production because the call requires both an internal-shipment
    miss AND container/vin/generic classification).

User-mandate satisfaction (D1-D8 ACCEPT — user-locked at 5.5/H kickoff)
─────────────────────────────────────────────────────────────────────

  * D1  cluster = ``_vf_extract_vessels`` + ``_external_container_lookup``
        retired in a single focused commit ✅
  * D2  canonical homes — ``_vf_extract_vessels`` → ``vesselfinder_scraper``
        (already owner; alias removed). ``_external_container_lookup`` →
        NEW ``app/services/tracking_providers.py`` as
        ``external_container_lookup`` (renamed, no underscore) ✅
  * D3  no worker-lifecycle refactor — ``tracking_worker`` untouched ✅
  * D4  no provider-algorithm edits — ShipsGo V1 GET-first / POST-second
        / AfterShip fallback chain byte-for-byte the legacy body ✅
  * D5  no schema evolution — return-dict keys + types preserved 1:1 ✅
  * D6  no async orchestration changes — function signatures +
        ``httpx.AsyncClient`` context-manager shape preserved 1:1 ✅
  * D7  golden suite FIRST —
        ``tests/test_phase5_5_h_vesselfinder_cluster.py`` written before
        extraction; 7/12 PASS pre-extraction (V1-V6 + O1) and
        12/12 PASS post-extraction ✅
  * D8  no new provider integrations — ShipsGoEU / FleetMon NOT added ✅

  Separate decision (user-locked at 5.5/H kickoff): orphan
  ``test_identity_runtime.py`` cleanup explicitly OUT OF SCOPE —
  belongs to Phase 6 CI normalization.

Inventory delta
───────────────

  ============================  ====  ====  ====
  Inventory                     Pre   Post  Δ
  ============================  ====  ====  ====
  BRIDGE_INVENTORY              3     2     −1
  TIER_C_REQUIRES_REFACTOR      2     1     −1
  PHASE_5_5_BOUNDARY            2     1     −1
  EXTRACTION_AUX_BRIDGES        47    47    ±0  (net: −1 _external_container_lookup RESOLVER_DEP retired; +1 _tracking_snapshot TRACKING_PROVIDERS_DEP registered — cold-start lazy bridge in tracking_providers.py was created in the f2a60d8 prep commit and is registered here as bookkeeping completion of the 5.5/H wave)
  QUALIFIED_USAGE_BRIDGES       0     0      0
  ============================  ====  ====  ====

Boundary status after 5.5/H
───────────────────────────

  Only ONE Tier-C bridge remains in Phase 5.5:

    * ``ensure_shipment_stages``   → 5.5/I shipments orchestration wave

  After 5.5/I closes, ``server.py`` will hold ZERO Tier-C
  ``from server import …`` bridges. Phase 6 (Production hardening)
  starts immediately after 5.5/I.

  ``Cluster-retirement pattern`` is now officially generalized:
  5.5/G demonstrated the pattern (3 bridges, identity-resolver
  orchestration cluster); 5.5/H reproduces it (2 bridges,
  tracking-providers cluster). 5.5/I will close the cycle.
"""


# ─────────────────────────────────────────────────────────────────────
# Phase 5.5 / I — Shipments orchestration cluster retirement (CLOSED)
# ─────────────────────────────────────────────────────────────────────

PHASE_5_5_I_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("ensure_shipment_stages",
     "server.py:5464 (Tier-C HELPER_FUNCTION — BRIDGE_INVENTORY) + app/routers/admin_resolver.py:77 (sole cross-module lazy-bridge consumer)",
     "from_server_import (HELPER_FUNCTION — body MOVED VERBATIM from server.py to app/services/shipments.ensure_shipment_stages; thin compat shim kept in server.py for in-file caller chain (8 sites) and qualified-name discoverability; admin_resolver.py:77 migrated to canonical home; the two helper deps `_normalize_stage` and `build_default_stages` remain on server side as SHIPMENTS_DEP aux-bridges — moving them is scope creep per D1 (7+4 in-file callsites in the orchestration shell — Phase 6 shell-thinning territory))"),
    ("add_shipment_event",
     "server.py:5521 (async EXTRACTION_AUX_BRIDGES kind=RESOLVER_DEP — registered in 5.5/G) + app/services/identity_runtime.py:_add_shipment_event (sole cross-module consumer via thin async wrapper)",
     "EXTRACTION_AUX_BRIDGES kind=RESOLVER_DEP, tier=C-aux — body MOVED VERBATIM from server.py to app/services/shipments.add_shipment_event; async shape preserved 1:1 (D6); shipments-events $push + $slice -40 + lastEvent/lastEventTime/updated_at $set schema preserved byte-for-byte (D5); Socket.IO 'shipment:event' emit on user_{customer_id} room preserved (D3 — sio runtime untouched); module-global `db` / `sio` access now resolved via the call-time _db() / _sio() accessors inside the canonical home — semantics identical because both resolve to the same singletons that server.db / server.sio previously held; thin compat shim kept in server.py for 11 in-file async callsites; identity_runtime.py:_add_shipment_event rewired to canonical home"),
    ("generate_route",
     "server.py:5078 (EXTRACTION_AUX_BRIDGES kind=CUSTOMER_AUTH_DEP — registered in 5.5/D) + app/services/customers.py (sole cross-module lazy-bridge consumer)",
     "EXTRACTION_AUX_BRIDGES kind=CUSTOMER_AUTH_DEP, tier=C-aux — body MOVED VERBATIM from server.py to app/services/shipments.generate_route; pure 5-point ocean route helper (origin + 3 waypoints + destination), no I/O, no async (D4 algorithm parity); thin compat shim kept in server.py for the 1 in-file callsite and qualified-name discoverability; app/services/customers.py lazy bridge migrated to canonical home"),
)
"""Bridges retired in Phase 5.5 / I (shipments-orchestration cluster
retirement — the third and TERMINAL cluster-retirement wave of the
Phase 5.5 cycle; THE PHASE-5 DISENTANGLING ENDPOINT).

Pre-flight audit
────────────────

Cluster scope established by D1 mandate (*"cluster = ``ensure_shipment_stages``
+ ``add_shipment_event`` + ``generate_route`` — single focused commit"*).
AST audit confirmed the three symbols form one tight orchestration unit:

  * ``ensure_shipment_stages`` (HELPER_FUNCTION, Tier-C — was in
    BRIDGE_INVENTORY since C-5f boundary) — stage-lifecycle backfill +
    in-place normalization. Idempotent.
  * ``add_shipment_event`` (RESOLVER_DEP, Tier C-aux — registered in
    EXTRACTION_AUX_BRIDGES by 5.5/G) — async event-log writer with
    Motor $push + Socket.IO emit dual-channel side effects.
  * ``generate_route`` (CUSTOMER_AUTH_DEP, Tier C-aux — registered in
    EXTRACTION_AUX_BRIDGES by 5.5/D) — pure 5-point ocean route helper.

User-mandate satisfaction (D1-D7 ACCEPT — user-locked at 5.5/I kickoff)
─────────────────────────────────────────────────────────────────────

  * D1  cluster = the 3 symbols retired in a single focused commit ✅
  * D2  canonical home: NEW ``app/services/shipments.py`` (cluster-owned;
        mirrors the 5.5/G ``app/services/identity_runtime.py`` and 5.5/H
        ``app/services/tracking_providers.py`` patterns) ✅
  * D3  no worker-lifecycle refactor — tracking_worker, resolver_worker,
        and the rest of the 7 workers untouched ✅
  * D4  no provider-algorithm edits — stage state-machine + route
        algorithm + event writer preserved byte-for-byte ✅
  * D5  no schema evolution — shipments.events[] schema, lastEvent /
        lastEventTime / updated_at keys preserved 1:1 ✅
  * D6  no async orchestration changes — async signatures, await
        shapes, sio emit semantics preserved 1:1 ✅
  * D7  golden suite FIRST —
        ``tests/test_phase5_5_i_shipments_orchestration.py`` written
        before extraction ✅

Inventory delta
───────────────

  ============================  ====  ====  ====
  Inventory                     Pre   Post  Δ
  ============================  ====  ====  ====
  BRIDGE_INVENTORY              2     1     −1   (ensure_shipment_stages retired)
  TIER_C_REQUIRES_REFACTOR      1     0     −1   ← ZERO Tier-C bridges (THE PHASE-5 FINALE)
  PHASE_5_5_BOUNDARY            1     0     −1   ← Phase 5.5 OFFICIALLY CLOSED
  EXTRACTION_AUX_BRIDGES        47    47    ±0   (net: −2 generate_route CUSTOMER_AUTH_DEP + add_shipment_event RESOLVER_DEP retired; +2 _normalize_stage + build_default_stages SHIPMENTS_DEP registered — deferred to Phase 6 shell-thinning)
  QUALIFIED_USAGE_BRIDGES       0     0      0
  ============================  ====  ====  ====

THE ARCHITECTURAL MILESTONE
───────────────────────────

Phase 5.5 / I closes the entire Phase-5 disentangling cycle. After this
wave:

  * ``server.py`` holds **ZERO** Tier-C ``from server import …`` bridges.
  * Only ``_STATIC_DIR`` remains in BRIDGE_INVENTORY (Tier-B, Phase 5.8
    bootstrap reshuffle territory).
  * ``server.py`` is no longer the business-core authority.
  * Phase 5 formally ENDS.
  * Phase 6 (Production Hardening) starts immediately.

The cluster-retirement pattern, first demonstrated in 5.5/G (identity-
resolver, 3 symbols) and reproduced in 5.5/H (tracking-providers,
2 symbols), is now officially terminalized by 5.5/I (shipments
orchestration, 3 symbols). The pattern is a confirmed migration
mechanism — not a heroic one-off.
"""




# ─────────────────────────────────────────────────────────────────────
# C-5f — Phase 5.5 boundary (formal handoff contract)
# ─────────────────────────────────────────────────────────────────────

PHASE_5_5_BOUNDARY: frozenset[str] = frozenset({
    # ─── Phase 5.5 / I CLOSED (2026-05-20) — PHASE 5.5 OFFICIALLY CLOSED ───
    # ``ensure_shipment_stages`` — RETIRED in 5.5/I (shipments orchestration
    # cluster — body moved verbatim from server.py to
    # ``app/services/shipments.ensure_shipment_stages``; thin compat shim in
    # server.py preserved for in-file caller chain (8 sites) and qualified
    # name discoverability; sole cross-module consumer
    # ``app/routers/admin_resolver.py:77`` migrated to canonical home).
    # ``add_shipment_event`` — RETIRED in 5.5/I (cluster — body moved
    # verbatim to ``app/services/shipments.add_shipment_event``; async
    # shape preserved; sio emit semantics preserved 1:1).
    # ``generate_route`` — RETIRED in 5.5/I (cluster — body moved verbatim
    # to ``app/services/shipments.generate_route``; pure function, no I/O).
    # ─── Earlier retirements (history kept for audit continuity) ───
    # ``_vf_extract_vessels`` — RETIRED in 5.5/H (alias on
    # ``server.py:19194`` import block removed; consumers reach for the
    # canonical ``extract_vessels_from_payload`` directly from
    # ``vesselfinder_scraper``; ``shipment_identity_resolver.py:406``
    # migrated; ``_external_container_lookup`` 5.5/G-aux retired
    # alongside — body moved to ``app/services/tracking_providers.py``
    # as the public ``external_container_lookup``).
    # Qualified-usage symbols (parallel surface — same phase):
    # ``logger`` — RETIRED in 5.5/A (payments.py) + 5.5/B (calculations.py).
    # ``_calculate_korea`` — RETIRED in 5.5/B (canonical home in app/services/calculator.py).
    # ``calculator_calculate`` — RETIRED in 5.5/B (canonical home in app/services/calculator.py).
    # ``tracking_config_service`` — RETIRED in 5.5/F (canonical accessor get_service() in app/services/tracking_config.py).
    # ``_create_order_from_invoice`` — RETIRED in 5.5/C (canonical home create_order_from_invoice() in app/services/orders.py — dual-shape retirement, BOTH `from server import` and `server.X qualified` shapes retired in the same commit, `import server` line removed from app/routers/payments.py).
    # ``_require_customer`` — RETIRED in 5.5/D (canonical home require_customer() in app/services/customers.py — single-shape retirement, `from server import` lazy WPS433 in cabinet_financials.py redirected; 5 in-file callers in server.py migrated).
    # ``_ensure_customer_seed`` — RETIRED in 5.5/D (canonical home ensure_customer_seed() in app/services/customers.py — single-shape retirement, `from server import` lazy WPS433 in cabinet_financials.py redirected; 14 in-file callers in server.py migrated; private sibling `_seed_customer_financials` moved with seeder).
    # ``_get_stripe_config`` — RETIRED in 5.5/E (canonical home get_stripe_config() in app/services/stripe_config.py — Wave-1 router-internal placement corrected; 7 router callers + 2 server.py lazy imports + 1 cabinet_financials.py broken-bridge call site migrated; intentional latent-ImportError repair documented).
    # ``_tracking_enabled`` — RETIRED in 5.5/F2 (canonical home tracking_enabled() in app/services/tracking_config.py — sibling function in existing module, NOT an accessor over service state; helper is pure env reader; 5 callers migrated — 4 in-file in server.py + 1 cross-module wrapper in admin_identity.py retired entirely; inventory-drift surfaced).
    # ``identity_runtime`` — RETIRED in 5.5/G (cluster retirement — module already lived at `app/services/identity_runtime.py` since Phase 3.2/C-1; 3 router consumers migrated from `from server import identity_runtime` to canonical `from app.services.identity_runtime import identity_runtime`).
    # ``_run_auto_resolver`` — RETIRED in 5.5/G (cluster — body moved verbatim from server.py:5657 to IdentityRuntimeService.run_auto_resolver(); M-4 lazy bridge retired).
    # ``_persist_resolver_hits`` — RETIRED in 5.5/G (cluster — body moved verbatim from server.py:5677 to IdentityRuntimeService.persist_resolver_hits(); M-5 lazy bridge retired).
})
"""All symbols Phase 5.5 owns for retirement, both bridge shapes
combined. Started at 14 distinct symbols across:

  * 10 Tier-C from-server bridges (BRIDGE_INVENTORY)
  *  4 qualified-usage symbols (QUALIFIED_USAGE_BRIDGES — 6 sites,
     because `logger` appears in 2 files and `_create_order_from_invoice`
     also has a from-server shape).

Post-5.5/A: 14 — no boundary delta (logger still in calc.py).
Post-5.5/B: 11 — `logger`, `_calculate_korea`, `calculator_calculate`
removed.
Post-5.5/F: 10 — `tracking_config_service` removed (its sole
qualified-access site in admin_integrations.py retired by migrating
to ``app.services.tracking_config.get_service``).
Post-5.5/C: 9 — `_create_order_from_invoice` removed (dual-shape
retirement: both ``from server import`` in legal_workflow.py:2158 AND
qualified ``server.X`` in payments.py:658 closed in the same commit;
``import server`` line removed from payments.py; symbol moved to
``app/services/orders.create_order_from_invoice``).
Post-5.5/D: **7** — `_require_customer` and `_ensure_customer_seed`
removed (single-shape retirement: ``from server import …`` lazy WPS433
in ``cabinet_financials.py`` redirected to the new home; 21 in-file
callers in ``server.py`` bulk-migrated to bare public names via a
single module-load import; private sibling
``_seed_customer_financials`` moved with the seeder; aux bridges
``_resolve_bearer`` + ``generate_route`` registered under
``EXTRACTION_AUX_BRIDGES`` with ``kind="CUSTOMER_AUTH_DEP"``).
Post-5.5/E: **6** — `_get_stripe_config` removed (Wave-1 router-internal
placement corrected; helper moved from ``app/routers/payments.py`` to
canonical home ``app/services/stripe_config.py`` as ``get_stripe_config``;
10 callers migrated — 7 router + 2 ``server.py`` lazy + 1
``cabinet_financials.py``; latent ``ImportError`` bridge in
``cabinet_financials.py`` repaired as documented intentional behaviour
fix; no aux deps per D3=A — helper self-contained over
``IntegrationConfigsRepository``). All
retirement
records preserved respectively in
``PHASE_5_5_A_RETIRED_QUALIFIED_SITES`` (payments logger),
``PHASE_5_5_B_RETIRED_QUALIFIED_SITES`` (calc.py logger + 2 calc engines),
``PHASE_5_5_F_RETIRED_QUALIFIED_SITES`` (tracking_config_service),
``PHASE_5_5_C_RETIRED_QUALIFIED_SITES`` (create_order_from_invoice),
and ``PHASE_5_5_D_RETIRED_BRIDGES`` (require_customer + ensure_customer_seed).

Phase 5.5 is NOT a single batch — it's a wave of focused commits,
one per domain root:
  * Wave 5.5.A — payments logger qualified-access (✅ CLOSED 2026-05-19)
  * Wave 5.5.B — calculator engine extraction (✅ CLOSED 2026-05-19)
  * Wave 5.5.F — tracking-config accessor (✅ CLOSED 2026-05-19)
  * Wave 5.5.C — order-creation orchestration (✅ CLOSED 2026-05-19)
                — first true orchestration extraction; last
                  qualified-access bridge retired
  * Wave 5.5.D — customer-auth helpers (✅ CLOSED 2026-05-19)
                — `_require_customer` + `_ensure_customer_seed` →
                  `app/services/customers.py`; aux bridges
                  `_resolve_bearer` + `generate_route` deferred
                  per mandate ("auth semantics are business semantics")
  * Wave 5.5.E — Stripe config helper (✅ CLOSED 2026-05-19)
                — `_get_stripe_config` → `app/services/stripe_config.py`
                  as `get_stripe_config`; reformulated at kickoff after
                  Step-1 audit revealed Wave-1 router-internal placement
                  + latent `ImportError` bridge in `cabinet_financials.py`;
                  intentional latent-bug repair documented
  * Wave 5.5.G — identity resolver disentangling (`identity_runtime`,
                 `_run_auto_resolver`, `_persist_resolver_hits`)
  * Wave 5.5.H — VesselFinder re-home (`_vf_extract_vessels`)
  * Wave 5.5.I — shipments orchestration (`ensure_shipment_stages`)

Wave order is illustrative; actual sequencing chosen at Phase 5.5
kickoff based on risk and dependency. Each wave is mandate-bound
to a separate planning + execution commit pair, matching the C-4 /
C-5 discipline."""


# ─────────────────────────────────────────────────────────────────────
# Phase 6.2 / ACTUAL — Shell Thinning execution (CLOSED 2026-05-20)
# ─────────────────────────────────────────────────────────────────────

PHASE_6_2_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("_normalize_stage",
     "EXTRACTION_AUX_BRIDGES kind=SHIPMENTS_DEP, tier=C-aux (registered by 5.5/I at app_state_targets.py:1091 as a lazy-bridge consumed by `app/services/shipments.ensure_shipment_stages` via `from server import _normalize_stage`; def-site was server.py:5489 with 5 in-file callsites in orchestration paths)",
     "Phase 6.2.ACTUAL (Shell Thinning) — body MOVED VERBATIM from server.py:5489 to `app/utils/shipments._normalize_stage`; sibling-extraction pattern (mirror of 5.5/F2) — canonical home already owns adjacent shape utilities (`get_current_stage`, `serialize_journey`); D-set: D1=cluster (both helpers + 2 constants in 1 commit) / D2=app/utils/shipments.py / D3=thin shims kept in server.py (<10 LOC each, single import + return shape — verified by AST in test_phase6_2_shell_thinning.test_s2) / D4=golden-first (B1-B5 behavioural goldens written BEFORE move) / D5=`_tracking_snapshot` DEFERRED to Phase 6.4 per PREP §6 / D6=AUX 47→45 (ratchet-down auto-accommodated by 6.3.A architecture_invariants `<=47` floor); the cross-module callsite in `app/services/shipments.py:ensure_shipment_stages` was migrated from `from server import _normalize_stage, build_default_stages` to `from app.utils.shipments import _normalize_stage, build_default_stages` (ZERO bridge-back-to-server in this module); 2 constants `JOURNEY_STAGE_TYPES` + `JOURNEY_STAGE_STATUSES` moved together (sole callers of the helper); server.py keeps re-export imports for qualified-name discoverability (`server.JOURNEY_STAGE_TYPES`)"),
    ("build_default_stages",
     "EXTRACTION_AUX_BRIDGES kind=SHIPMENTS_DEP, tier=C-aux (registered by 5.5/I at app_state_targets.py:1118 as a lazy-bridge consumed by `app/services/shipments.ensure_shipment_stages` via `from server import build_default_stages`; def-site was server.py:5460 with 2 in-file callsites in orchestration paths)",
     "Phase 6.2.ACTUAL (Shell Thinning) — body MOVED VERBATIM from server.py:5460 to `app/utils/shipments.build_default_stages`; same sibling-extraction pattern as `_normalize_stage` above; D-set identical; the clock-derived id shape `stage_{int(now.timestamp())}_1` preserved 1:1 (PREP §4.2.2); em-dash U+2014 preserved in label (PREP §4.2.3); `datetime.now(timezone.utc)` clock source preserved (PREP §4.2.6); thin compat shim kept in server.py for the 2 in-file callsites; the cross-module callsite at `app/services/shipments.py:ensure_shipment_stages` migrated to canonical home alongside `_normalize_stage` (single import line covers both)"),
)
"""Bridges retired in Phase 6.2 / ACTUAL — Shell Thinning execution
(the third milestone wave of Phase 6 Production Hardening, after the
6.1 CI normalization + 6.3.A runtime contracts that locked the
invariants this wave landed against).

Pre-flight audit (per PREP doc PHASE6_2_SHELL_THINNING_PREP.md)
───────────────────────────────────────────────────────────────

The 2 retired bridges were both registered by 5.5/I as
``SHIPMENTS_DEP`` aux-entries at the close of Phase 5. Their
retirement was deferred at that time because:

  * 5.5/I's D1 scope was "cluster retirement of 3 orchestration
    bridges in a single commit" (``ensure_shipment_stages`` +
    ``add_shipment_event`` + ``generate_route``).
  * Moving the 2 helpers alongside would have been scope-creep
    (5+2 in-file callsites in the orchestration shell — a separate
    decomposition concern).
  * The aux-bridge cataloguing pattern (mirror of 5.5/H's
    ``_tracking_snapshot``) parked the retirement for "Phase 6
    shell-thinning or a focused future wave" — that wave is THIS one.

User-mandate satisfaction (D1-D7 — extracted from PREP §8)
──────────────────────────────────────────────────────────

  * D1  cluster scope (both helpers + 2 constants in 1 focused commit) ✅
  * D2  canonical home: `app/utils/shipments.py` (sibling-extraction
        pattern; PREP §5.1 — same module that owns get_current_stage,
        serialize_journey, _smooth_eta_iso, is_valid_movement) ✅
  * D3  thin compat shims kept in server.py (body shape: single
        `from … import …` + `return …Call(...)` — verified by AST
        in tests/test_phase6_2_shell_thinning.test_s2) ✅
  * D4  golden-first discipline — tests/test_phase6_2_shell_thinning.py
        written BEFORE the move; pre-extraction baseline showed
        10 PASS / 7 FAIL (the 7 failing tests are the S+I structural
        pins, which is exactly how a golden suite "truly differentiates
        pre vs post") ✅
  * D5  `_tracking_snapshot` explicitly DEFERRED to Phase 6.4 or 7
        (PREP §6 — structural residue node, requires
        `tracking_config_runtime` accessor module mirroring db_runtime /
        socket_runtime; would either back-import the
        `server.tracking_config_service` module-global (regression) or
        require a new abstraction (Phase 7 territory)) ✅
  * D6  inventory targets all hit:
            EXTRACTION_AUX_BRIDGES: 47 → 45 (−2 SHIPMENTS_DEP retired)
            PHASE_6_2_RETIRED_BRIDGES: NEW (2 entries — this constant)
            OpenAPI 618 paths / 679 ops: PRESERVED (frozen)
            workers 7/7: PRESERVED
            architecture_invariants.py `<= 47` floor:
                AUTO-PASSES at 45 (no edit needed; ratchet-down) ✅
  * D7  audit-trail accuracy corrections (PREP §7) carried forward:
            5.5/I closeout overstated _normalize_stage as
            7 in-file callsites (actual: 5); build_default_stages as
            4 (actual: 2). 6.2.ACTUAL closeout doc carries the
            corrected numbers; this constant reflects the truth-restored
            count. ✅

Inventory delta
───────────────

  ============================  ====  ====  ====
  Inventory                     Pre   Post  Δ
  ============================  ====  ====  ====
  BRIDGE_INVENTORY              1     1     0    (unchanged; only _STATIC_DIR Tier-B remains)
  TIER_C_REQUIRES_REFACTOR      0     0     0    (unchanged at zero — the disentangling endpoint holds)
  PHASE_5_5_BOUNDARY            0     0     0    (unchanged at zero)
  EXTRACTION_AUX_BRIDGES        47    45    −2   ★ THE SHELL-THINNING DELTA
  QUALIFIED_USAGE_BRIDGES       0     0     0    (unchanged)
  ============================  ====  ====  ====

What this means architecturally
───────────────────────────────

5.5/I closed Phase 5 by reducing TIER_C bridges to zero (the
"disentangling endpoint"). server.py was no longer the business-core
authority, but it still hosted "structural residue nodes" — pure
helpers / constants that participate in orchestration paths and
contribute to the shell's gravity.

6.2.ACTUAL retires the two simplest structural residue nodes
(the pure SHIPMENTS_DEP helpers). The third — ``_tracking_snapshot``
— is a non-leaf node (reads ``server.tracking_config_service``
module-global) and requires a dedicated accessor-module wave
(Phase 6.4 or 7), so it stays. After 6.2.ACTUAL:

  * server.py shell loses ~70 LOC of helper body (replaced by ~30 LOC
    of thin compat shims — net −40 LOC).
  * No bridge-back-from-canonical-home-to-server remains in
    `app/services/shipments.py`.
  * The 2 stage-shape constants live with their sole consumer
    (`_normalize_stage`), eliminating a definition-locality coupling
    that would have been latent forever otherwise.

Files touched (3 production + 1 new test + 1 inventory + 2 docs)
────────────────────────────────────────────────────────────────

  Production:
    * `app/utils/shipments.py`            +119 LOC (2 constants + 2 funcs + __all__ extension)
    * `server.py`                          −58 / +35 LOC (3 defs + 2 constants → 2 compat shims + 1 re-export import block)
    * `app/services/shipments.py`         −1 / +1 LOC (lazy-bridge import target changed: server → canonical)

  Inventory:
    * `app/core/app_state_targets.py`     +120 / −58 LOC (2 Bridge entries retired with audit-trail comment block; PHASE_6_2_RETIRED_BRIDGES constant +docstring; __all__ entry)

  Tests:
    * `tests/test_phase6_2_shell_thinning.py`  NEW +320 LOC (B1-B7 + S1-S5 + I1-I3 + O1 + L1)

  Docs:
    * `PHASE6_2_ACTUAL_SHELL_THINNING_CLOSED.md`  NEW (this wave's closeout)
    * `PHASE6_KICKOFF.md`                          status section updated (6.2.ACTUAL CLOSED, 6.3.B NEXT)

Successor wave
──────────────

  * Phase 6.3.B (AST enforcement / topology checks) — next active scope.
    The runtime invariants installed by 6.3.A are now backed by the
    shell-thinned topology of 6.2.ACTUAL, so the AST ratchets in 6.3.B
    can land with tight rails: zero `from server import X` outside
    whitelist (test files, `app/core/app_state_targets.py`, server.py
    itself), zero `import server` outside `tests/`.
  * Phase 6.4 — `_tracking_snapshot` extraction via new
    `app/core/tracking_config_runtime.py` accessor (mirror of
    db_runtime / socket_runtime). Still DEFERRED per PREP §6.
"""


PHASE_5_8_BOUNDARY: frozenset[str] = frozenset({
    "_STATIC_DIR",
})


# ─────────────────────────────────────────────────────────────────────
# Phase 6.5+ Wave 1 — calculator-pure helper retirement (CLOSED 2026-05-20)
# ─────────────────────────────────────────────────────────────────────

PHASE_6_5_WAVE_1_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    ("_find_route_amount",
     "EXTRACTION_AUX_BRIDGES kind=CALC_ENGINE_DEP, tier=C-aux (registered by 5.5/B as one of the 43 calc-engine cluster bridges; def-site was server.py:9679 with 0 in-file callsites — orphan helper consumed only by app/services/calculator.py)",
     "Phase 6.5+ Wave 1 (calculator-pure helper retirement) — body MOVED VERBATIM from server.py:9679 to `app/services/calculator_pure._find_route_amount`; sibling-extraction pattern (mirror of 6.2.ACTUAL); D-set: D1=single-helper scope (truth-restored from PREP-projected 4 helpers due to module-global coupling discovery during body inspection — see PHASE6_5_WAVE_1_CLOSED.md §audit-trail) / D2=`app/services/calculator_pure.py` (NEW module — sibling of `app/services/calculator.py`) / D3=thin compat shim in server.py (~10 LOC, body shape `from … import …` + `return …Call(…)` — verified by AST in test_phase6_5_wave1_calculator_pure_retirement.test_s2) / D4=golden-first (B1-B3 behavioural goldens written BEFORE move) / D5=split import block in app/services/calculator.py (42 from server, 1 from calculator_pure — direct canonical-home reach, NO bridge back to server) / D6=AUX 45→44 (ratchet-down auto-accommodated by 6.3.A `<=45` floor); the cluster-retirement primitive is now applied for the 6th time (after 5.5/G/H/I, 6.2.ACTUAL, and now 6.5+/Wave-1)"),
)
"""Bridges retired in Phase 6.5+ Wave 1 — calculator-pure helper
retirement (the first calc-engine cluster reduction wave; rehearsal
for Wave 2's larger 38-constant move).

Pre-flight audit (PREP doc PHASE6_5_PLUS_CALC_ENGINE_PREP.md)
─────────────────────────────────────────────────────────────

The 1 retired bridge was registered by 5.5/B as part of the 43-symbol
`CALC_ENGINE_DEP` cluster. PREP §3 originally projected 4 helpers in
Wave 1 PURE_FUNCTION bucket; body inspection at Wave-1 kickoff
revealed 3 of those 4 had module-global coupling (audit-trail
correction logged in PHASE6_5_WAVE_1_CLOSED.md §audit-trail):

  * `_find_route_amount` — TRULY PURE (zero module-globals) → moved
    in Wave 1.
  * `_tiered_buyer_fee` + `_tiered_buyer_fee_from_db` — use
    `AUCTION_TIERED_FEES` (server.py:9308, NOT in the 43-symbol
    whitelist; has 5 server.py refs). Deferred to Wave 1.5 / Wave 2
    (constants wave handles AUCTION_TIERED_FEES).
  * `_load_calc_config` — uses 5 server-globals (`_CALC_CACHE`,
    `_CALC_CACHE_TTL`, `_ensure_calculator_seed`, `db`, `logger`).
    Belongs in Wave 3 alongside `_ensure_calculator_seed` (tightly
    coupled — the cache wraps the seed function).

Mandate satisfaction (Wave 1 mandate sketched in PREP §6)
─────────────────────────────────────────────────────────

  * D1  scope: 1 truly-pure helper in 1 commit (truth-restored from
        PREP-projected 4 — honest mandate-respecting scope correction) ✅
  * D2  canonical home: `app/services/calculator_pure.py` (NEW) ✅
  * D3  thin compat shim in server.py (~10 LOC; AST-verified) ✅
  * D4  golden-first (11-test suite written BEFORE move; pre-extraction
        baseline 5 PASS / 6 FAIL — exactly the differentiating S+I pins) ✅
  * D5  cross-module callsite in `app/services/calculator.py` migrated
        via split import block: 42 symbols still from server, 1 (the
        retired helper) reaches canonical home directly ✅
  * D6  inventory targets:
            EXTRACTION_AUX_BRIDGES: 45 → 44 (one CALC_ENGINE_DEP retired)
            PHASE_6_5_WAVE_1_RETIRED_BRIDGES: NEW (this constant)
            OpenAPI 618/679 + workers 7/7: PRESERVED
            architecture_invariants.py `<=45` floor: AUTO-ACCOMMODATED ✅

Inventory delta
───────────────

  ============================  ====  ====  ====
  Inventory                     Pre   Post  Δ
  ============================  ====  ====  ====
  BRIDGE_INVENTORY              1     1     0
  TIER_C_REQUIRES_REFACTOR      0     0     0
  PHASE_5_5_BOUNDARY            0     0     0
  EXTRACTION_AUX_BRIDGES        45    44    -1   ★ Wave-1 delta
  QUALIFIED_USAGE_BRIDGES       0     0     0
  ============================  ====  ====  ====

What this Wave validated
────────────────────────

The mandate was "validate retirement mechanism, NOT maximize cleanup".
Validation outcomes:

  * Sibling-extraction into a NEW canonical home module
    (`app/services/calculator_pure.py`) works cleanly under the
    6.3.B AST whitelist + bidirectional ratchet.
  * Split-import block pattern (42 from server + 1 from canonical home)
    cleanly retires a single bridge from a multi-symbol cluster row.
  * The PREP-doc body-inspection discipline catches misclassifications
    BEFORE moves (the 4→1 scope correction was caught at Wave-1
    kickoff, not at runtime).
  * 6.3.A composite assertion auto-accommodated the ratchet-down to 44
    (the <=45 floor is a TRUE upper bound, not a pin).

Successor work
──────────────

  * Wave 1.5 (or folded into Wave 2): `_tiered_buyer_fee` +
    `_tiered_buyer_fee_from_db` together with `AUCTION_TIERED_FEES`
    (their internal-only constant dependency).
  * Wave 2: 38 PURE_CONSTANT (incl. AUCTION_TIERED_FEES if not landed
    in 1.5) → `app/core/calculator_constants.py`.
  * Wave 3 (needs own PREP): `_ensure_calculator_seed` +
    `_load_calc_config` together (true SERVER_STATE).
"""


# ─────────────────────────────────────────────────────────────────────
# Phase 6.5+ Wave 2 — calculator-constants + helpers retirement
# (LANDING 2026-05-20)
# ─────────────────────────────────────────────────────────────────────

PHASE_6_5_WAVE_2_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    # ── 38 PURE_CONSTANT (catalog + USA + Korea constants) ──
    *(
        (
            sym,
            f"EXTRACTION_AUX_BRIDGES kind=CALC_ENGINE_DEP, tier=C-aux (registered by 5.5/B as one of the 43 calc-engine cluster bridges; consumed by app/services/calculator.py)",
            f"Phase 6.5+ Wave 2 — body MOVED VERBATIM from server.py:9265-9411 to `app.core.calculator_constants.{sym}`; pure-data module (zero deps); calculator.py rewired to reach canonical home directly via `from app.core.calculator_constants import …` (NO bridge back to server)",
        )
        for sym in (
            # Catalog tables (3)
            "VEHICLE_TYPES", "CALCULATOR_PORTS", "AUCTION_FEES",
            # USA-pipeline constants (14)
            "DEFAULT_PROFILE_CODE", "VEHICLE_USA_INLAND",
            "VEHICLE_OCEAN_BASE", "PORT_OCEAN_ADJUST",
            "VEHICLE_EU_DELIVERY", "PORT_FORWARDING", "PORT_PARKING",
            "PARKING_BULGARIA", "COMPANY_SERVICES",
            "CUSTOMS_DOCUMENTATION", "CUSTOMS_DUTY_RATE",
            "INSURANCE_RATE", "DAMAGED_CUSTOMS_FACTOR",
            "DAMAGE_HANDLING_FEE_USD",
            # Korea-pipeline constants (21)
            "KOREA_PROFILE_CODE", "KOREA_USE_LOGISTICS_PACKAGE",
            "KOREA_AUCTION_FEE_PERCENT", "KOREA_LOGISTICS_PACKAGE",
            "KOREA_INLAND_DEFAULT", "KOREA_SEA_DEFAULT",
            "KOREA_INSURANCE_DEFAULT", "KOREA_FORWARDER_FEE_DEFAULT",
            "KOREA_DOCUMENTS_MAIL_DEFAULT", "KOREA_CUSTOMS_DUTY_RATE",
            "KOREA_VAT_RATE", "KOREA_UNDERVALUE_PERCENT",
            "KOREA_DAMAGED_CUSTOMS_FACTOR",
            "KOREA_DAMAGE_HANDLING_FEE_USD",
            "KOREA_OFFICIAL_FEES_USD", "KOREA_BIBI_SERVICE_FEE",
            "KOREA_FX_USD_TO_EUR", "KOREA_BG_TRANSPORT_EUR",
            "KOREA_ADDITIONAL_FEES_EUR", "KOREA_TECH_INSPECTION_EUR",
            "KOREA_BB_CARS_COMMISSION_EUR",
        )
    ),
    # ── Internal-only constant (not a formal bridge — folded into Wave 2 by mandate) ──
    (
        "AUCTION_TIERED_FEES",
        "Internal-only constant at server.py:9308; not in 43-symbol CALC_ENGINE_DEP whitelist (had 0 cross-module consumers; 5 in-file refs only); folded into Wave 2 by user-locked mandate (\"constants и _tiered_buyer_fee* structurally coupled — single coordinated retirement\")",
        "Phase 6.5+ Wave 2 — body MOVED VERBATIM from server.py:9308 to `app.core.calculator_constants.AUCTION_TIERED_FEES`; consumed by the 2 `_tiered_buyer_fee*` helpers (also retired in Wave 2 to `app/services/calculator_pure.py`); server.py re-exports for the 1 remaining in-file ref in `_ensure_calculator_seed` (Wave 3 will eliminate)",
    ),
    # ── 2 ``_tiered_buyer_fee*`` helpers ──
    (
        "_tiered_buyer_fee",
        "EXTRACTION_AUX_BRIDGES kind=CALC_ENGINE_DEP, tier=C-aux (registered by 5.5/B as one of the 43 calc-engine cluster bridges; def-site was server.py:9725 with 0 in-file callsites — orphan helper consumed only by app/services/calculator.py via `from server import` chain that's now broken)",
        "Phase 6.5+ Wave 2 — body MOVED VERBATIM from server.py:9725 to `app/services/calculator_pure._tiered_buyer_fee`; sibling-extraction pattern (Wave 1 sibling extended); references AUCTION_TIERED_FEES via new canonical home `app.core.calculator_constants` (NOT via server); thin compat shim kept at server.py:9725 for qualified-name discoverability",
    ),
    (
        "_tiered_buyer_fee_from_db",
        "EXTRACTION_AUX_BRIDGES kind=CALC_ENGINE_DEP, tier=C-aux (registered by 5.5/B; def-site was server.py:9703; orphan helper, 0 in-file callsites)",
        "Phase 6.5+ Wave 2 — body MOVED VERBATIM from server.py:9703 to `app/services/calculator_pure._tiered_buyer_fee_from_db`; references AUCTION_TIERED_FEES via canonical home; thin compat shim kept at server.py:9703 for qualified-name discoverability",
    ),
)
"""Bridges retired in Phase 6.5+ Wave 2 — calculator-constants +
helpers cluster retirement (the second calc-engine cluster reduction
wave; folded former Wave 1.5 into Wave 2 per user-locked mandate).

Pre-flight rails (Wave 2 PREP)
──────────────────────────────

The 41-symbol Wave-2 scope was frozen 2026-05-20 by 11 PREP freeze
tests in ``tests/test_phase6_5_wave2_prep_freeze.py``:

  * Target 1 — exact constant count = 41 symbols (locked).
  * Target 2 — exact server.py Load-context ref count = 72 pre, 68 post
    (locked; AUCTION_TIERED_FEES drops 5→1 as helper bodies become shims).
  * Target 3 — import graph: calculator.py ``from server import …``
    DROPPED 42 → 0; NEW ``from app.core.calculator_constants import …`` = 39;
    ``from app.services.calculator_pure import …`` GREW 1 → 3.
  * Target 4 — cycle reproduction: pre-Wave-2 ``import
    app.services.calculator`` standalone failed with
    ``ImportError: partially initialized``; post-Wave-2 succeeds
    cleanly (cycle resolved by removing all ``from server import`` at
    module load and converting to lazy ``import server`` inside engine
    function bodies).
  * Target 5 — boot-order probe: production boot (server first →
    calculator) still passes; live composite (BRIDGE=1, TIER_C=0,
    BOUNDARY=0, QUALIFIED=0, AUX≤44 → AUX=4) holds.

Mandate satisfaction (Wave 2 D-set from PHASE6_5_WAVE_2_PREP.md §3)
──────────────────────────────────────────────────────────────────

  * D1  scope: 41 symbols in 1 coordinated commit (38 PURE_CONSTANT +
        1 AUCTION_TIERED_FEES + 2 ``_tiered_buyer_fee*`` helpers) ✅
  * D2  canonical homes: 38+1 → ``app/core/calculator_constants.py`` (NEW);
        2 helpers → ``app/services/calculator_pure.py`` (EXTENDED) ✅
  * D3  server.py compat surface: ``from app.core.calculator_constants
        import …`` re-export block (39 names) replaces the 38 def-sites
        + AUCTION_TIERED_FEES def-site; 2 thin helper shims for
        ``_tiered_buyer_fee*`` ✅
  * D4  golden-first: 11-test PREP freeze suite written BEFORE moves;
        REWRITTEN at landing to lock the post-Wave-2 baseline ✅
  * D5  calculator.py imports: split block — 0 from server, 3 from
        calculator_pure, 39 from calculator_constants;
        ``_ensure_calculator_seed`` + ``_load_calc_config`` reached via
        lazy ``import server`` inside function bodies (cycle break) ✅
  * D6  inventory targets:
            EXTRACTION_AUX_BRIDGES: 44 → 4 (40 retired this wave)
            PHASE_6_5_WAVE_2_RETIRED_BRIDGES: NEW (this constant)
            OpenAPI 618/679 + workers 7/7: PRESERVED
            architecture_invariants.py `<=44` floor: AUTO-ACCOMMODATED ✅
  * D7  audit-trail: all 41 retirements logged here ✅
  * D8  hard gate: live composite passes post-restart; _calculate_korea
        numerical parity verified by 5.5/B golden hash suite (18
        PINNED_HASHES) ✅

Inventory delta
───────────────

  ============================  ====  ====  ====
  Inventory                     Pre   Post  Δ
  ============================  ====  ====  ====
  BRIDGE_INVENTORY              1     1     0
  TIER_C_REQUIRES_REFACTOR      0     0     0
  PHASE_5_5_BOUNDARY            0     0     0
  EXTRACTION_AUX_BRIDGES        44    4     -40  ★ Wave-2 delta
  QUALIFIED_USAGE_BRIDGES       0     0     0
  ============================  ====  ====  ====

What this Wave validated
────────────────────────

  * The cluster-retirement primitive scales from 1 helper (Wave 1) to
    41 mixed symbols (Wave 2) without losing audit hygiene.
  * Re-export blocks work cleanly as compat surfaces — the 38 PURE_CONSTANT
    + AUCTION_TIERED_FEES re-export at server.py constants section
    keeps ``_ensure_calculator_seed`` + ``_load_calc_config`` + admin
    config endpoints working without any body edits in those callers.
  * Lazy ``import server`` inside function bodies cleanly resolves the
    latent circular-import shape — calculator.py is now standalone-loadable.
  * Golden-first discipline preserved: 5.5/B's 18 PINNED_HASHES suite
    verifies numerical parity post-extraction.

Successor work (Wave 3, needs own PREP)
───────────────────────────────────────

  * ``_ensure_calculator_seed`` + ``_load_calc_config`` retire together
    (true SERVER_STATE — they reference ``db``, ``logger``, and module
    globals ``_CALC_CACHE`` / ``_CALC_CACHE_TTL`` requiring own
    runtime accessor pattern mirroring ``db_runtime`` /
    ``socket_runtime``).
  * Post-Wave-3 target: EXTRACTION_AUX_BRIDGES 4 → 2 (only
    ``_resolve_bearer`` + ``_tracking_snapshot`` remaining).
"""

"""Symbols Phase 5.8 owns. Currently a single entry — the static
mount path constant. Phase 5.8 is the bootstrap-layer reshuffle:
the static mount itself (StaticFiles(directory=_STATIC_DIR, ...)
registered in _main_startup) migrates to a dedicated
app/core/static_mount.py module, and _STATIC_DIR moves alongside.

Why deferred to 5.8 and not 5.5: moving _STATIC_DIR alone is a
trivial constant move, but it would orphan the StaticFiles mount
in server.py without a coordinated bootstrap reshuffle. C-5f's
revalidation (production AST: 1 site in app/routers/content.py:105;
no side-effects on the Path constant itself) confirms the defer is
still correct — pure type=Path, no runtime mutation, no shared
state."""


C5F_INVENTORY_BASELINE: tuple = (
    # Frozen post-C-5e baseline captured by C-5f AST audit.
    # (symbol, current_def_site, consumer_files, usage_shape, phase)
    # ─── RETIRED Phase 5.5 / I (2026-05-20): shipments orchestration
    #     cluster (3 symbols: ``ensure_shipment_stages`` BRIDGE_INVENTORY
    #     entry + ``add_shipment_event`` RESOLVER_DEP aux + ``generate_route``
    #     CUSTOMER_AUTH_DEP aux) retired together (D1 mandate). Bodies
    #     moved verbatim to ``app/services/shipments.py`` as
    #     ``ensure_shipment_stages``, ``add_shipment_event``, and
    #     ``generate_route``. The two cross-module consumers
    #     ``admin_resolver.py:77`` and ``admin_shipments.py:110`` migrated
    #     to canonical home. Thin compat shims remain in server.py for
    #     in-file caller chains. ``_normalize_stage`` and
    #     ``build_default_stages`` registered as new SHIPMENTS_DEP
    #     extraction-aux entries (Phase 6 shell-thinning territory).
    #     This is the PHASE-5 disentangling endpoint: ZERO Tier-C bridges
    #     remain in BRIDGE_INVENTORY (only ``_STATIC_DIR`` Tier-B left).
    # ("ensure_shipment_stages", "server.py:~3552",
    #  ("app/routers/admin_resolver.py", "app/routers/admin_shipments.py"),
    #  "from_server_import", "5.5"),
    # ("identity_runtime", "app/services/identity_runtime.py (module)",
    #  ("app/routers/admin_resolver.py", "app/routers/admin_identity.py",
    #   "app/routers/admin_shipments.py"),
    #  "from_server_import (module re-export)", "5.5"),
    # ("_run_auto_resolver", "server.py",
    #  ("app/services/identity_runtime.py",), "from_server_import", "5.5"),
    # ("_persist_resolver_hits", "server.py",
    #  ("app/services/identity_runtime.py",), "from_server_import", "5.5"),
    # ─── RETIRED Phase 5.5 / G (2026-05-20): identity-resolver cluster
    #     (3 symbols: ``identity_runtime`` MODULE_REF + ``_run_auto_resolver``
    #     + ``_persist_resolver_hits``) retired together (D1 mandate).
    #     Bodies moved verbatim from ``server.py:5657`` / ``server.py:5677``
    #     into ``IdentityRuntimeService.run_auto_resolver()`` /
    #     ``.persist_resolver_hits()``; 3 module-private helpers travelled
    #     with the cluster; 2 aux deps stayed on server side as
    #     ``RESOLVER_DEP`` entries. Baseline shrinks 6 → 3.
    # ("_vf_extract_vessels", "server.py",
    #  ("shipment_identity_resolver.py",), "from_server_import", "5.5"),
    # ─── RETIRED Phase 5.5 / H (2026-05-20): VesselFinder cluster
    #     (2 symbols: ``_vf_extract_vessels`` BRIDGE_INVENTORY entry +
    #     ``_external_container_lookup`` EXTRACTION_AUX_BRIDGES
    #     RESOLVER_DEP entry) retired together (D1 mandate). The alias
    #     ``extract_vessels_from_payload as _vf_extract_vessels`` on
    #     server.py:19194 removed; canonical home was always
    #     ``vesselfinder_scraper`` (the helper had always been defined
    #     there). The single cross-module consumer in
    #     ``shipment_identity_resolver.py:406`` migrated to direct
    #     ``from vesselfinder_scraper import extract_vessels_from_payload``.
    #     ``_external_container_lookup`` body MOVED VERBATIM from
    #     server.py:18798 to ``app/services/tracking_providers.py`` as
    #     the public ``external_container_lookup``; the 5.5/G-era
    #     ``_external_container_lookup_callable()`` lazy-bridge accessor
    #     in ``app/services/identity_runtime.py`` retired entirely.
    #     ``_tracking_snapshot`` cold-start lazy bridge in
    #     ``tracking_providers.py`` registered as the new
    #     ``TRACKING_PROVIDERS_DEP`` extraction-aux entry (net
    #     EXTRACTION_AUX_BRIDGES Δ-0 because the retired
    #     RESOLVER_DEP + registered TRACKING_PROVIDERS_DEP cancel out).
    #     BRIDGE_INVENTORY baseline shrinks 3 → 2.
    # ("_create_order_from_invoice", "server.py",
    #  ("legal_workflow.py", "app/routers/payments.py"),
    #  "from_server_import + qualified", "5.5"),
    # ─── RETIRED Phase 5.5 / C (2026-05-19): order-creation
    #     orchestration moved to ``app/services/orders.py`` (public
    #     entry point ``create_order_from_invoice``); both
    #     ``from server import`` and ``server.X qualified`` shapes
    #     retired in the same commit; ``import server`` line removed
    #     from ``app/routers/payments.py``. Baseline shrinks 11 → 10.
    # ("_require_customer", "server.py",
    #  ("cabinet_financials.py",), "from_server_import (aliased)", "5.5"),
    # ("_ensure_customer_seed", "server.py",
    #  ("cabinet_financials.py",), "from_server_import", "5.5"),
    # ─── RETIRED Phase 5.5 / D (2026-05-19): customer-auth helpers
    #     moved to ``app/services/customers.py`` (public entry points
    #     ``require_customer`` and ``ensure_customer_seed``). Single-shape
    #     retirement (``from server import …`` lazy WPS433 in
    #     ``cabinet_financials.py`` wrappers redirected; 21 in-file
    #     callers in ``server.py`` bulk-migrated to bare public names
    #     via a single module-load import). Private sibling
    #     ``_seed_customer_financials`` (204 LOC) moved with the seeder
    #     and stays module-private inside the new home. Aux deps
    #     ``_resolve_bearer`` + ``generate_route`` registered under
    #     ``EXTRACTION_AUX_BRIDGES`` (kind=``CUSTOMER_AUTH_DEP``) per
    #     D2 mandate ("no token logic touch"). Baseline shrinks 10 → 8.
    # ("_get_stripe_config", "server.py",
    #  ("cabinet_financials.py",), "from_server_import", "5.5"),
    # ─── RETIRED Phase 5.5 / E (2026-05-19): Stripe config helper.
    #     Discovery: the def was actually in ``app/routers/payments.py``
    #     (Wave-1 router-internal placement), NOT ``server.py`` as the
    #     baseline tuple claimed — inventory drift masked by the broken
    #     ``cabinet_financials.py:366`` lazy bridge (latent ImportError).
    #     5.5/E moved the helper to its canonical home at
    #     ``app/services/stripe_config.py`` (public name
    #     ``get_stripe_config``), migrated all 10 callers (7 router +
    #     2 server.py + 1 cabinet_financials.py), and repaired the
    #     latent ImportError bridge. No aux deps registered (D3=A —
    #     helper self-contained over ``IntegrationConfigsRepository``).
    #     Baseline shrinks 8 → 7.
    # ("_tracking_enabled", "server.py",
    #  ("app/routers/admin_identity.py",), "from_server_import (aliased)", "5.5"),
    # ─── RETIRED Phase 5.5 / F2 (2026-05-19): TRACKING_ENABLED env-flag
    #     reader. Helper moved from server.py:2963 to canonical home
    #     app/services/tracking_config.py as sibling function
    #     tracking_enabled (public name).  Same module as
    #     TrackingConfigService but NOT an accessor — helper is pure
    #     env reader (TRACKING_ENABLED env var).  5 callers migrated
    #     (inventory drift: claimed 1, actual 5): 4 in-file in
    #     server.py + 1 cross-module local wrapper in
    #     admin_identity.py:67-69 retired entirely (no compat shim
    #     per D4).  Baseline shrinks 7 → 6.
    ("_STATIC_DIR", "server.py:~3131",
     ("app/routers/content.py",), "from_server_import", "5.8"),
)
"""Frozen post-C-5e bridge baseline. Captured by C-5f AST audit on
2026-05-19. 11 entries — matches BRIDGE_INVENTORY size exactly. Each
entry maps a symbol to its (current definition site, consumer files,
usage shape, target phase). The shape `from_server_import + qualified`
on `_create_order_from_invoice` reflects its dual access pattern
(legal_workflow.py via from-server, payments.py via server.X).

The C-5f test
``tests/test_phase5_4_c5f_consolidation_verdict.py::test_1_live_ast_bridge_baseline_matches_inventory``
asserts the live AST re-audit returns exactly these 11 symbols (no
more, no less) — guarding against silent new coupling between C-5f
close and Phase 5.5 kickoff."""


# ─────────────────────────────────────────────────────────────────────
# Forbidden categories (mandate §Forbidden, hard-pinned)
# ─────────────────────────────────────────────────────────────────────
C5_FORBIDDEN_CHANGES: frozenset[str] = frozenset({
    "moving any helper",
    "removing any from server import helper",
    "changing server.py helper definitions",
    "changing runtime semantics",
    "creating AuditService",
    "creating AggregatorService wrapper",
    "moving _STATIC_DIR",
    "moving shipment helpers",
    "changing serializer or money functions",
    "touching business logic",
    "touching routes / workers / startup",
})
"""C-5 is planning-only. Verified by
``tests/test_phase5_4_c5_tier_b_plan.py::test_6`` — file diff
between pre-C-5 and post-C-5 must touch ONLY:
  - new doc file `PHASE5_4_C5_TIER_B_PLAN.md`
  - app/core/app_state_targets.py (TIER_B_INVENTORY + 2 new
    Tier-C Bridge entries + verdict update + compat-pin notes)
  - new test file `test_phase5_4_c5_tier_b_plan.py`
  - compatible-pin updates in prior C-3B/C-4 test suites
"""


DB_QUALIFIED_IMPORT_SITES: tuple[tuple[str, int], ...] = ()
"""Files using ``import server`` + qualified ``server.db.X`` access
instead of the canonical ``from server import db`` lazy bridge. Empty
after C-4i — the only entry (``app/routers/calculations.py``) was
migrated to ``get_db().X`` in C-4i. The companion test
``test_phase5_4_c4i_db_residual_retirement.py`` enforces the tuple
stays empty (or, if a NEW qualified-import surface is introduced, that
it MUST register here before merging)."""

# Historical record (pre-C-4i state, retained as documentation):
#   DB_QUALIFIED_IMPORT_SITES_PRE_C4I = (("app/routers/calculations.py", 20),)


# ── Forbidden categories (mandate §Forbidden, hard-pinned) ───────────
DB_C4D_FORBIDDEN_CHANGES: frozenset[str] = frozenset({
    "removing any from server import db",
    "changing any router signature",
    "changing any worker registration",
    "changing any repository constructor",
    "changing app.state",
    "changing startup order",
    "changing get_db behaviour",
    "touching business logic",
    "touching collection access",
    "replacing lazy bridges",
    "bulk sed",
})
"""Frozen set of categories C-4d must NOT touch. Verified by
test_phase5_4_c4d_db_retirement_plan.py — file diff between
pre-C-4d and post-C-4d must touch ONLY:
  - new doc file
  - app/core/app_state_targets.py (DB_CONSUMER_INVENTORY append)
  - new tests file
  - OPTIONAL new app/core/db_runtime.py (inert)
"""


# ─────────────────────────────────────────────────────────────────────
# Phase 6.5+ Wave 3 — calc-engine SERVER_STATE closure
# (LANDING 2026-05-20 — closes the architecture program)
# ─────────────────────────────────────────────────────────────────────

PHASE_6_5_WAVE_3_RETIRED_BRIDGES: tuple[tuple[str, str, str], ...] = (
    (
        "_ensure_calculator_seed",
        "EXTRACTION_AUX_BRIDGES kind=CALC_ENGINE_DEP, tier=C-aux (was the SERVER_STATE-coupled seed routine; def-site at server.py:9370 with references to ``db``, ``logger``, and 44 constants; Wave 2 reached it via the lazy ``import server`` cycle-break allowance)",
        "Phase 6.5+ Wave 3 — body MOVED VERBATIM from server.py:9370 to ``app/services/calculator_config_cache.ensure_calculator_seed``. Only substantive change: ``db`` → ``get_db()`` (via ``app.core.db_runtime`` accessor; mirrors the 5.5/B-5.5/I migration pattern). server.py keeps a logic-free transport-layer shim at ``_ensure_calculator_seed``.",
    ),
    (
        "_load_calc_config",
        "EXTRACTION_AUX_BRIDGES kind=CALC_ENGINE_DEP, tier=C-aux (was the SERVER_STATE-coupled config loader; def-site at server.py:9599 with references to module-globals ``_CALC_CACHE`` / ``_CALC_CACHE_TTL`` + ``db`` + ``logger``)",
        "Phase 6.5+ Wave 3 — body MOVED VERBATIM from server.py:9599 to ``app/services/calculator_config_cache.get_calc_config`` (public-API rename — no leading underscore). TTL cache state (``_CACHE`` + ``_CACHE_TTL``) lives in canonical home only; server.py module-level state RETIRED. server.py keeps a logic-free transport-layer shim.",
    ),
    (
        "_invalidate_calc_cache",
        "Internal helper at server.py:9592 — sync cache reset called by 5 admin config-mutating endpoints; not a formal bridge entry but moved together with ``_load_calc_config`` to preserve cache-state encapsulation",
        "Phase 6.5+ Wave 3 — body MOVED VERBATIM from server.py:9592 to ``app/services/calculator_config_cache.invalidate_cache``. server.py keeps a logic-free transport-layer shim that the 5 admin endpoints still call via the old name.",
    ),
)
"""Bridges retired in Phase 6.5+ Wave 3 — calc-engine SERVER_STATE
closure (the third and **final** calc-engine cluster reduction wave;
closes the architecture program).

Post-Wave-3 the entire 5.5/B-era 43-symbol ``CALC_ENGINE_DEP`` cluster
is canonicalized across 3 dedicated homes:

  * ``app/core/calculator_constants.py``         — 44 pure-data symbols
  * ``app/services/calculator_pure.py``          — 3 stateless helpers
  * ``app/services/calculator_config_cache.py``  — 3 stateful callables + TTL cache state

``server.py`` retains a compatibility shell: 1 re-export block (44
names) + 6 logic-free transport-layer shims for the retired calc-engine
surface (``_ensure_calculator_seed``, ``_load_calc_config``,
``_invalidate_calc_cache``, ``_tiered_buyer_fee``,
``_tiered_buyer_fee_from_db``, ``_find_route_amount``).

Compat-shim invariant (formal — see ARCHITECTURE_PROGRAM_CLOSED.md):

    Compat shims must remain logic-free and observationally
    transparent. Any semantic drift re-opens the architecture program.

Inventory delta:
    EXTRACTION_AUX_BRIDGES: 2 → 2 (unchanged — both retired symbols
        already exited the cluster at end of Wave 2 by ceasing to be
        ``from server import``-coupled; Wave 3 finished the move to
        canonical home).
    PHASE_6_5_WAVE_3_RETIRED_BRIDGES: NEW (3 entries — this constant).
    OpenAPI 618/679 + workers 7/7: PRESERVED.

The 2 remaining ``EXTRACTION_AUX_BRIDGES`` entries (``_resolve_bearer``
+ ``_tracking_snapshot``) are declared **permanent operational bridges
by design** in the closure document. They will not retire.

Architecture program: CLOSED. See ``ARCHITECTURE_PROGRAM_CLOSED.md``.
"""



__all__ = [
    "OwnershipRoot",
    "OWNERSHIP_ROOTS",
    "Bridge",
    "BRIDGE_INVENTORY",
    "EXTRACTION_AUX_BRIDGES",
    "StartupPhase",
    "STARTUP_PHASES",
    "TIER_A_SHALLOW_REWIRING",
    "TIER_B_MOVE_AND_REROUTE",
    "TIER_C_REQUIRES_REFACTOR",
    "ARCHITECTURAL_VERDICT",
    # Phase 5.4 / C-4d planning surface:
    "DBConsumer",
    "DB_CONSUMER_INVENTORY",
    "DB_QUALIFIED_IMPORT_SITES",
    "DB_C4D_FORBIDDEN_CHANGES",
    # Phase 5.4 / C-5 Tier-B planning surface:
    "TierBSymbol",
    "TIER_B_INVENTORY",
    "C5_BATCH_PROPOSAL",
    "C5_FORBIDDEN_CHANGES",
    "C5A_RETIRED_SYMBOLS",
    "C5B_RETIRED_SYMBOLS",
    "C5C_RETIRED_SYMBOLS",
    "C5E_RETIRED_SYMBOLS",
    # Phase 5.4 / C-5f consolidation surface:
    "QualifiedUsageSite",
    "QUALIFIED_USAGE_BRIDGES",
    "PHASE_5_5_BOUNDARY",
    "PHASE_5_5_A_RETIRED_QUALIFIED_SITES",
    "PHASE_5_5_B_RETIRED_QUALIFIED_SITES",
    "PHASE_5_5_C_RETIRED_QUALIFIED_SITES",
    "PHASE_5_5_D_RETIRED_BRIDGES",
    "PHASE_5_5_E_RETIRED_BRIDGES",
    "PHASE_5_5_F2_RETIRED_BRIDGES",
    "PHASE_5_5_F_RETIRED_QUALIFIED_SITES",
    "PHASE_5_5_G_RETIRED_BRIDGES",
    "PHASE_5_5_H_RETIRED_BRIDGES",
    "PHASE_5_5_I_RETIRED_BRIDGES",
    "PHASE_5_8_BOUNDARY",
    "C5F_INVENTORY_BASELINE",
    # Phase 6.2 / ACTUAL — Shell Thinning execution:
    "PHASE_6_2_RETIRED_BRIDGES",
    # Phase 6.5+ Wave 1 — calculator-pure helper retirement:
    "PHASE_6_5_WAVE_1_RETIRED_BRIDGES",
    # Phase 6.5+ Wave 2 — calculator-constants + helpers retirement:
    "PHASE_6_5_WAVE_2_RETIRED_BRIDGES",
    # Phase 6.5+ Wave 3 — calc-engine SERVER_STATE closure
    # (closes the architecture program):
    "PHASE_6_5_WAVE_3_RETIRED_BRIDGES",
]
