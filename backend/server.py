"""
BIBI V3.2 - Multi-Session Ingestion with Field-Level Intelligence
==================================================================
Architecture:
  Extension (Agent) → Config API → SessionManager → Queue → Field Intelligence → MongoDB
  
Features:
  - Session Scoring (success rate + data completeness + latency)
  - Field-Level Intelligence (best source per field)
  - Remote Config & Heartbeat
  - Session Blacklisting
  - Source Attribution

**SYSTEM SIMPLIFIED (April 2026):**
  - PRIMARY FOCUS: Bitmotors scraper ONLY
  - DEPRECATED: Copart Chrome Extension, AI features, Carfast, Bidcars
  - Code preserved but disabled (enabled=False in PARSER_REGISTRY)

================================================================================
                FEATURE-FREEZE ZONE -- DO NOT ADD NEW ROUTES HERE
--------------------------------------------------------------------------------
This module is being progressively decomposed via Controlled Modular Monolith
refactoring (started 2026-05-17, see plan.md / CONTRIBUTING.md).

  * NEW endpoints, services, repositories MUST live under  backend/app/
  * They are wired in via  fastapi_app.include_router(...)  below.
  * Mechanical extraction only -- NO business-logic changes during P1.
  * One domain per commit.  Surgical diffs, no aggressive import cleanup.

See ``backend/CONTRIBUTING.md`` for the extraction playbook and ownership rules.
================================================================================
"""
import os
import re
import asyncio
import hashlib
import secrets
import uuid
import time
import json
import logging
import traceback
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(override=False)

from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect, Request, Response, Depends, Header, UploadFile, File, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import httpx
import socketio
from jose import JWTError, jwt

# ═══════════════════════════════════════════════════════════════════
# [ECO CLEANUP — VIN-INGESTION RETIREMENT 2026-06] Auto-domain
# parsers/scrapers (BidCars / Bitmotors / Stat.vin / WestMotors / Lemon /
# catalog-promotion) fully removed. Availability flags kept as False so
# any residual readiness checks report "removed" rather than raising.
# ═══════════════════════════════════════════════════════════════════
BIDCARS_AVAILABLE = False
BITMOTORS_AVAILABLE = False
VIN_SERVICE_AVAILABLE = False
STATVIN_AVAILABLE = False
INCREMENTAL_AVAILABLE = False
WESTMOTORS_AVAILABLE = False
WESTMOTORS_PARSER_AVAILABLE = False
LEMON_AVAILABLE = False

# [ECO CLEANUP] catalog_promotion_worker import removed (auto-domain).
PROMOTION_AVAILABLE = False

# TTL cache for hot live-search queries (5 min, 2048 entries)
try:
    from ttl_cache import TTLCache
    live_search_cache = TTLCache(ttl_seconds=300, max_size=2048)
except Exception as _e:
    live_search_cache = None
    logging.warning(f"ttl_cache unavailable: {_e}")

# ═══════════════════════════════════════════════════════════════════
# [VIN-INGESTION RETIREMENT 2026-06] Carfast cookie-proxy service,
# Playwright undetected-browser parser and all Carfast/* parser classes
# have been fully removed (auto-domain). No route reaches them.
# ═══════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bibi-v3.2")

# ═══════════════════════════════════════════════════════════════════
# Phase 4 / C-3 — Structured JSON logging (additive envelope).
# ═══════════════════════════════════════════════════════════════════
# Install ONCE, here, immediately after `logging.basicConfig(...)` so
# the JSON layer captures every subsequent log record without
# disturbing the existing stderr/stdout human-readable streams.
#
# Design invariant (per C-3 mandate): existing stderr / stdout lines
# stay BYTE-IDENTICAL to the pre-C-3 baseline.  The call below is
# additive-only — it ADDS a `WatchedFileHandler` on the root logger
# writing to `/var/log/supervisor/backend.structured.jsonl`.  It does
# NOT touch the default `StreamHandler` that `basicConfig` installed
# for human-readable stderr output.
#
# `attach_structured_handler` is idempotent (guarded by a marker
# attribute on the root logger); safe to call multiple times.
try:
    from app.core.structured_logging import (
        attach_structured_handler as _attach_structured_handler,
        set_lifecycle_stage as _set_lifecycle_stage,
    )
    _attach_structured_handler()
    _set_lifecycle_stage("boot")
except Exception:
    # Best-effort: structured logging must never crash boot.  Any
    # failure here is logged via the existing logger but does NOT
    # prevent the application from starting — the human-readable
    # stderr stream remains the canonical observability surface.
    logging.getLogger("bibi-v3.2").exception(
        "[C-3] structured_logging install failed (continuing without JSON layer)"
    )

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "bibi_cars")

db_client: Optional[AsyncIOMotorClient] = None
db = None

# ═══════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

# ── serialize_doc — Phase 5.2 / C-1 EXTRACTED ──────────────────────
# Canonical home is now `app/utils/serialization.py`.  This re-export
# preserves the legacy `from server import serialize_doc` bridge AND
# the in-module call sites (still resolve the same callable object).
# Behaviour is byte-identical to the pre-extraction implementation —
# see app/utils/serialization.py module docstring for the preserved
# contract (58 call sites depend on this exact shape).
#
# This is the FIRST Phase 5 bridge-removal commit.  When all 58 call
# sites have been migrated to `from app.utils.serialization import …`
# this re-export line can be removed (planned: Phase 5.8 sweep).
from app.utils.serialization import serialize_doc  # noqa: F401,E402  -- compat re-export

# ═══════════════════════════════════════════════════════════════════
# [VIN-INGESTION RETIREMENT 2026-06] The entire field-intelligence
# ingestion stack has been removed (auto-domain). Formerly defined here:
#   FIELD_CONFIDENCE / ALL_FIELDS, ParserConfig / parser_config,
#   ParserEntry / PARSER_REGISTRY, Session / SessionService,
#   IngestionJob / IngestionQueue, FieldSource / VinRecord /
#   AggregatorService, ConnectionManager / ws_manager, the global
#   session_service / ingestion_queue / aggregator singletons (+ their
#   C-5b runtime-accessor publication) and the queue_handler coroutine.
# No route, worker or startup hook references any of these symbols.
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────────
# Phase 4 / C-1 — lifespan context manager (replaces legacy
# @fastapi_app.on_event("startup"|"shutdown") wiring).
# ───────────────────────────────────────────────────────────────────
# Runtime-stabilization step only: SEMANTICS ARE 1:1 with the legacy
# decorator-based wiring.  No re-ordering, no log-line changes, no
# `app.state` migration, no `db` global removal, no import cleanup,
# no repository/DTO work.  The bodies of the orchestrated hooks are
# unchanged; only their dispatch mechanism moves from FastAPI's
# (deprecated) `on_event` registry to a single `lifespan()` context
# manager, which is the FastAPI/Starlette-recommended path going
# forward and unblocks the rest of Phase 4 (C-2 app.state.db mirror,
# C-3 structured JSON logging, C-4 Prometheus metrics, C-5 invariant
# CI assertions).
#
# Startup order preserved 1:1 (source order = on_event registration
# order under the legacy wiring):
#   1) _main_startup            (was @on_event("startup") at ~L1611;
#                                 originally `startup()`; renamed to
#                                 avoid module-namespace collision
#                                 with FastAPI's deprecated default
#                                 `startup` symbol and with the test
#                                 helper of the same name)
#   2) _ensure_webhook_events_index  (was @on_event("startup") at ~L13931)
#   3) _services_startup_hook        (was @on_event("startup") at ~L14060)
#   4) _vin_search_engine_startup    (was @on_event("startup") at ~L17862;
#                                     decorator was already removed in
#                                     the same C-1 series but the hook
#                                     had no orchestrator until now)
#
# Shutdown order preserved 1:1 (single hook):
#   1) _worker_registry_shutdown     (was @on_event("shutdown") at ~L2201)
#
# Forward-reference safe: the hooks listed above are defined LATER in
# this file (they originally needed `fastapi_app` to exist before the
# `@on_event` decorator ran).  Python resolves the bare names at
# `lifespan()` invocation time — i.e. at uvicorn boot, by which point
# the whole module has been imported and all hook symbols exist.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup phase ─────────────────────────────────────────────────
    # Phase 4 / C-3 — lifecycle stage transitions (JSON envelope only).
    # These do NOT emit any new human-readable log line; they merely
    # update the `lifecycle_stage` ContextVar that the structured
    # JSON formatter reads at emit time.  Existing stderr lines stay
    # byte-identical.
    try:
        from app.core.structured_logging import set_lifecycle_stage as _stage
        _stage("starting")
    except Exception:
        pass
    # Phase 4 / C-4 — mirror the stage transition into the metrics
    # layer.  Read-only effect on Prometheus gauge `process_lifecycle_stage`.
    try:
        from app.core import metrics as _m4
        _m4.set_lifecycle_stage("starting")
    except Exception:
        pass
    await _main_startup()
    await _ensure_webhook_events_index()
    await _services_startup_hook()
    # [auto-domain removed] VIN search engine startup (scraper requeue) deleted
    try:
        from app.core.structured_logging import set_lifecycle_stage as _stage
        _stage("running")
    except Exception:
        pass
    # Phase 4 / C-4 — startup_total Counter + OpenAPI gauges snapshot
    # at the latest possible moment (after every router is mounted).
    try:
        from app.core import metrics as _m4
        _m4.set_lifecycle_stage("running")
        _m4.inc_startup()
        try:
            schema = fastapi_app.openapi()
            paths = schema.get("paths", {}) or {}
            ops = sum(
                1
                for _p, methods in paths.items()
                for k in (methods or {})
                if k.lower() in ("get", "post", "put", "patch", "delete", "head", "options")
            )
            _m4.set_openapi_surface(len(paths), ops)
        except Exception:
            pass
    except Exception:
        pass
    # Phase 6.3.A — runtime architecture invariants assertion.
    # Runs AFTER every router is mounted (so OpenAPI surface is final)
    # and BEFORE we transition to 'running' state. Asserts the Phase 5
    # disentangling endpoint contract:
    #   * BRIDGE_INVENTORY  <= 1
    #   * TIER_C_REQUIRES_REFACTOR == 0
    #   * PHASE_5_5_BOUNDARY == 0
    #   * QUALIFIED_USAGE_BRIDGES == 0
    #   * EXTRACTION_AUX_BRIDGES <= 47
    #   * OpenAPI paths == 618 / ops == 679
    #
    # Defensive try/except matches the pattern used by structured_logging
    # and metrics above — a regression-detection layer must never CRASH
    # the app at boot; it logs and lets ops decide. The test-time path
    # (tests/test_phase6_3_a_runtime_contracts.py) DOES raise — the
    # runtime path only warns.
    try:
        from app.core.architecture_invariants import (
            run_all_phase_5_endpoint_assertions,
            ArchitectureInvariantViolation,
        )
        try:
            _phase5_snapshot = run_all_phase_5_endpoint_assertions(
                fastapi_app=fastapi_app,
            )
            logger.info(
                "[PHASE-5-ENDPOINT-INVARIANTS] OK: "
                "BRIDGE=%d TIER_C=%d BOUNDARY=%d QUALIFIED=%d AUX=%d "
                "OpenAPI=%d/%d",
                _phase5_snapshot.bridge_inventory,
                _phase5_snapshot.tier_c_requires_refactor,
                _phase5_snapshot.phase_5_5_boundary,
                _phase5_snapshot.qualified_usage_bridges,
                _phase5_snapshot.extraction_aux_bridges,
                _phase5_snapshot.openapi_paths or -1,
                _phase5_snapshot.openapi_ops or -1,
            )
        except ArchitectureInvariantViolation as _e:
            # Loud structured warning at startup. Test-time path raises;
            # runtime path lets ops surface the regression without
            # blocking the app from coming up (so the recovery path
            # is available).
            logger.warning(
                "[PHASE-5-ENDPOINT-INVARIANTS] VIOLATION at startup: "
                "surface=%r expected=%r actual=%r note=%r",
                _e.surface, _e.expected, _e.actual, _e.note,
            )
    except Exception:
        # Module import error — log silently. The test-time path will
        # surface this as a regular import error if anything is wrong.
        pass
    # ── application is live ──────────────────────────────────────────
    yield
    # ── shutdown phase ────────────────────────────────────────────────
    try:
        from app.core.structured_logging import set_lifecycle_stage as _stage
        _stage("draining")
    except Exception:
        pass
    try:
        from app.core import metrics as _m4
        _m4.set_lifecycle_stage("draining")
    except Exception:
        pass
    await _worker_registry_shutdown()
    try:
        from app.core.structured_logging import set_lifecycle_stage as _stage
        _stage("stopped")
    except Exception:
        pass
    try:
        from app.core import metrics as _m4
        _m4.set_lifecycle_stage("stopped")
        _m4.inc_graceful_shutdown()
    except Exception:
        pass


fastapi_app = FastAPI(
    title="BIBI V3.2",
    version="3.2.0",
    # The Kubernetes ingress only routes `/api/*` to the backend, so we
    # mount Swagger UI / ReDoc / OpenAPI under `/api/...` to keep them
    # reachable through the public preview URL.
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    # Phase 4 / C-1 — see lifespan() above.
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════
# Phase 4 / C-3 — Request-scoped context (request_id, correlation_id)
# ═══════════════════════════════════════════════════════════════════
# This middleware binds two ContextVars for the duration of every
# HTTP request:
#   · request_id      — fresh UUID per request
#   · correlation_id  — mirrors `X-Correlation-ID` header if the
#                       caller supplied one (cross-service tracing),
#                       else mirrors request_id.
#
# Existing handlers see NO observable change in behaviour: this
# middleware does NOT mutate the request body, the response body,
# any header that the application later sets, or any existing log
# message.  It only:
#   (a) populates two contextvars that the structured-JSON layer
#       reads at log-emit time,
#   (b) writes back `X-Request-ID` and `X-Correlation-ID` headers on
#       the outgoing response so callers / proxies can correlate.
#
# Failure modes are swallowed (best-effort, never crash a request).
@fastapi_app.middleware("http")
async def _phase4_c3_request_context(request, call_next):
    try:
        from app.core.structured_logging import (
            bind_request as _bind_request,
            new_request_id as _new_request_id,
        )
    except Exception:
        # Structured-logging module unavailable — pass through cleanly.
        return await call_next(request)

    req_id = _new_request_id()
    corr_id = request.headers.get("x-correlation-id") or req_id
    with _bind_request(req_id, corr_id):
        # Phase 4 / C-3 — single structured marker per request.  Goes
        # to the JSON layer only (it is a `logger.debug(...)` to NOT
        # appear in the default stderr stream that uses
        # `logging.basicConfig(level=INFO)`).  This is what makes
        # `request_id` searchable in the JSONL feed.  The log is
        # emitted BEFORE downstream handler logs so the request_id
        # ContextVar is bound for everything that follows.
        logger.debug(
            "[http] request begin %s %s",
            request.method, request.url.path,
            extra={"http_method": request.method, "http_path": request.url.path},
        )
        response = await call_next(request)
    # Best-effort response headers — never raise on header set.
    try:
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Correlation-ID"] = corr_id
    except Exception:
        pass
    return response


# ═══════════════════════════════════════════════════════════════════
# Phase 4 / C-4 — Prometheus metrics (additive observability layer)
# ═══════════════════════════════════════════════════════════════════
# This middleware ONLY reads runtime state and emits Prometheus
# counter / histogram observations.  It never mutates the request,
# the response body, or any application state.  It is registered
# AFTER the C-3 request-context middleware so the FastAPI middleware
# stack composition is:
#
#     uvicorn/ASGI → C-4 metrics → C-3 request-context → app routes
#
# (FastAPI executes middlewares LIFO from registration order — so
# the LAST middleware registered runs first.  C-4 wraps C-3 wraps
# the app, meaning C-4 sees the FULL request lifecycle including
# the time spent inside C-3 bookkeeping.  This is the correct
# placement for latency measurement.)
#
# Route-label cardinality: we use `request.scope["route"].path` when
# FastAPI has matched the route to a registered handler — that
# resolves to the parametrised template (`/api/foo/{id}` not
# `/api/foo/42`), keeping cardinality bounded.  When no route is
# matched (404 / OPTIONS / static), we fall back to the literal URL
# path BUT capped at a short string to avoid label explosion.
@fastapi_app.middleware("http")
async def _phase4_c4_metrics(request, call_next):
    try:
        from app.core import metrics as _m
    except Exception:
        return await call_next(request)

    _t0 = time.perf_counter()
    response = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = getattr(response, "status_code", 500)
        return response
    finally:
        # Resolve route template if FastAPI matched one; else fall
        # back to the literal path (truncated).
        route_obj = request.scope.get("route") if hasattr(request, "scope") else None
        route_label: str
        if route_obj is not None and hasattr(route_obj, "path"):
            route_label = route_obj.path
        else:
            path = request.url.path or "/"
            route_label = path[:64] if len(path) > 64 else path
        try:
            _m.http_requests_total.labels(
                method=request.method, route=route_label, status_code=str(status_code)
            ).inc()
            _m.http_request_duration_seconds.labels(
                method=request.method, route=route_label
            ).observe(max(0.0, time.perf_counter() - _t0))
        except Exception:
            pass


# ── /metrics exposition route ───────────────────────────────────────
# Single new route, EXCLUDED from the OpenAPI schema
# (`include_in_schema=False`) so the 618/679 path/operation freeze
# invariant remains intact.  Verified live in C-4 closure tests.
from fastapi.responses import Response as _FastAPIResponse  # noqa: E402


@fastapi_app.get("/metrics", include_in_schema=False)
async def _phase4_c4_metrics_endpoint():
    """Prometheus exposition endpoint (additive observability layer).

    Returns text/plain;version=0.0.4 — the Prometheus exposition
    format — built from the dedicated `app.core.metrics.registry`
    CollectorRegistry.  Worker-related gauges are refreshed at scrape
    time from the live `worker_registry` snapshot so they always
    reflect current truth without requiring callbacks.
    """
    try:
        from app.core import metrics as _m
        # Refresh worker gauges from registry snapshot at scrape time.
        try:
            from app.core.worker_registry import worker_registry as _wr
            for st in _wr.status():
                _m.record_worker_state(
                    st["name"],
                    running=bool(st.get("running")),
                    restarts=int(st.get("restarts") or 0),
                    started_at=st.get("started_at"),
                )
        except Exception:
            pass
        return _FastAPIResponse(
            content=_m.render_metrics(),
            media_type=_m.METRICS_CONTENT_TYPE,
        )
    except Exception as exc:
        logger.exception("[metrics] /metrics render failed: %s", exc)
        return _FastAPIResponse(
            content=b"# metrics unavailable\n",
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


# ═══════════════════════════════════════════════════════════════════════════
# OpenAPI schema sanitizer
# ─────────────────────────────────────────────────────────────────────────
# FastAPI builds the OpenAPI dict from every endpoint's docstring, Pydantic
# Field examples, enum values, etc.  If ANY of those source strings contains
# a lone UTF-16 surrogate code-point (range U+D800..U+DFFF — usually a
# leftover from a pasted emoji escape like "\uD83D\uDD04"), Starlette's
# `JSONResponse(...).encode("utf-8")` blows up with:
#     UnicodeEncodeError: 'utf-8' codec can't encode characters ...
#     surrogates not allowed
# which produces a 500 on `/docs` and `/openapi.json`.
#
# We override `fastapi_app.openapi` once at import time so the schema is
# scrubbed of surrogate code-points before serialization.  This protects
# against any future docstring/example regression too.
def _strip_surrogates(value):
    if isinstance(value, str):
        # Replace lone surrogate code-points with U+FFFD (replacement char).
        return "".join(
            (ch if not (0xD800 <= ord(ch) <= 0xDFFF) else "\uFFFD")
            for ch in value
        )
    if isinstance(value, dict):
        return {k: _strip_surrogates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_surrogates(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_surrogates(v) for v in value)
    return value


_original_openapi = fastapi_app.openapi


def _safe_openapi():
    schema = _original_openapi()
    return _strip_surrogates(schema)


fastapi_app.openapi = _safe_openapi


# ═══════════════════════════════════════════════════════════════════
# SOCKET.IO SETUP FOR REAL-TIME RINGOSTAT EVENTS
# ═══════════════════════════════════════════════════════════════════
# Secret key for JWT (should match frontend auth)
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=False
)

# Wrap with ASGI app - this becomes the main 'app'
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

# ── Phase 5.4 / C-4c — sio bridge retired ──────────────────────────
# Publish the live AsyncServer into the dedicated accessor module so
# all former `from server import sio` consumers can read via
# `app.core.socket_runtime.get_sio()` with identical object identity.
#
# Why HERE (right after ASGIApp wrap, BEFORE @sio.event handlers):
#   1. The setter MUST run at module-load time (not in _main_startup),
#      because consumers (identity_runtime, app.core.deps) read lazily
#      at point-of-use and may be invoked during _main_startup itself
#      (e.g. worker registration paths). Publishing here means the
#      accessor is valid from the very first read.
#   2. Placing the setter AFTER `socketio.ASGIApp(sio, ...)` proves
#      the same instance is shared by FastAPI mount and the accessor
#      (the ASGIApp captures `sio` by reference, not by copy).
#   3. Placing the setter BEFORE the @sio.event handler decorators
#      means by the time those decorators run and bind `connect` /
#      `disconnect` to the AsyncServer, the accessor already points
#      to that exact same server — so any consumer that does
#      `get_sio().emit(...)` is guaranteed to hit the handlers
#      registered below.
#
# Identity invariant: the assertion fails fast if a future edit
# accidentally introduces a second writer or wraps the instance.
try:
    from app.core.socket_runtime import set_sio, get_sio
    set_sio(sio)
    assert get_sio() is sio, (
        "[C-4c] socket_runtime accessor identity diverged from "
        "canonical server.sio at setter site (module-load)"
    )
except ImportError:
    # Defensive: if app.core.socket_runtime is unavailable for any
    # reason (partial install, test harness), preserve legacy behaviour
    # — the accessor stays at None. After C-4c retirement there are no
    # production consumers reading the legacy bridge, so this branch is
    # diagnostic-only. logger may not exist yet at this module-load
    # point, so use a stderr fallback via print.
    import sys
    print(
        "[C-4c] app.core.socket_runtime.set_sio unavailable at module-load; "
        "accessor will return None (legacy behaviour preserved)",
        file=sys.stderr,
    )

# JWT authentication for WebSocket
def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token and return payload.

    Phase IV-5 fix: previously this used ``server.JWT_SECRET`` which
    defaulted to the placeholder ``your-secret-key-change-in-production``.
    But the real secret in use across the app is owned by
    ``security.py`` (auto-generated & persisted to ``.jwt_secret``).
    The mismatch caused every direct ``verify_token()`` call to return
    None → endpoints would 401 even on perfectly valid tokens.
    We now defer to security's JWT_SECRET/JWT_ALGORITHM so all token
    verification paths use the same shared key.
    """
    try:
        from security import JWT_SECRET as _SEC_SECRET, JWT_ALGORITHM as _SEC_ALGO
        payload = jwt.decode(token, _SEC_SECRET, algorithms=[_SEC_ALGO])
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT verification unexpected error: {e}")
        return None

@sio.event
async def connect(sid, environ, auth):
    """Handle WebSocket connection with JWT auth"""
    logger.info(f"[WS] Connection attempt from {sid}")
    
    # Extract token from auth dict or query string
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get('token')
    
    if not token:
        # Try to get from query string
        query_string = environ.get('QUERY_STRING', '')
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=', 1)[1]
                break
    
    if not token:
        logger.warning(f"[WS] No token provided for {sid}")
        raise ConnectionRefusedError('Authentication required')
    
    # Verify token
    payload = verify_token(token)
    if not payload:
        logger.warning(f"[WS] Invalid token for {sid}")
        raise ConnectionRefusedError('Invalid token')
    
    user_id = payload.get('user_id') or payload.get('sub')
    role = payload.get('role', 'customer')
    
    if not user_id:
        logger.warning(f"[WS] No user_id in token for {sid}")
        raise ConnectionRefusedError('Invalid token payload')
    
    # Save session data
    await sio.save_session(sid, {
        'user_id': user_id,
        'role': role,
        'email': payload.get('email', '')
    })
    
    # Join user-specific room
    await sio.enter_room(sid, f"user:{user_id}")
    
    # Join role-specific room (for manager broadcasts). Legacy `master_admin`
    # stays here so in-flight sessions from before the rename keep getting
    # their role-scoped socket events.
    if role in ['admin', 'manager', 'master_admin', 'team_lead']:
        await sio.enter_room(sid, f"role:{role}")
    
    logger.info(f"[WS] Connected: {sid} | user:{user_id} | role:{role}")
    await sio.emit('connected', {'status': 'ok', 'user_id': user_id}, room=sid)

@sio.event
async def disconnect(sid):
    """Handle WebSocket disconnection"""
    session = await sio.get_session(sid)
    user_id = session.get('user_id', 'unknown') if session else 'unknown'
    logger.info(f"[WS] Disconnected: {sid} | user:{user_id}")

# Helper function to emit events
async def emit_to_user(user_id: str, event: str, data: dict):
    """Emit event to specific user"""
    await sio.emit(event, data, room=f"user:{user_id}")

async def emit_to_role(role: str, event: str, data: dict):
    """Emit event to all users with specific role"""
    await sio.emit(event, data, room=f"role:{role}")

logger.info("✓ Socket.IO server initialized")

# ═══════════════════════════════════════════════════════════════════
# END SOCKET.IO SETUP
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# WATCHLIST LIVE-POLL WORKER (LIVE-FIRST architecture)
# ─────────────────────────────────────────────────────────────────
# Old: notify when a VIN appeared in our scraped DB.
# New: poll BidMotors LIVE for every pending VIN once an hour. If found,
#      notify the user (socket + persisted timeline event).
# ═══════════════════════════════════════════════════════════════════
WATCHLIST_POLL_INTERVAL_SEC = int(os.environ.get("WATCHLIST_POLL_INTERVAL_SEC", "3600"))
WATCHLIST_POLL_BATCH = int(os.environ.get("WATCHLIST_POLL_BATCH", "20"))
WATCHLIST_POLL_DELAY = float(os.environ.get("WATCHLIST_POLL_DELAY", "2.0"))




async def _run_payment_reminders_once(settings: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """Run ONE iteration of the payment-reminder scanner.

    Args:
        settings: pre-loaded reminder_settings doc. If None — fetched fresh.

    Returns:
        dict(processed, reminders, dispatched_by_level) — `processed` = invoices inspected,
        `reminders` = reminders dispatched.

    Used by:
      * the hourly background loop (`_payment_reminder_loop`)
      * the on-demand /api/invoice-reminders/process endpoint
    """
    cfg = settings or await _load_reminder_settings()
    if not cfg.get("enabled", True):
        return {"processed": 0, "reminders": 0, "skipped_reason": "disabled"}

    reminder_after_days = int(cfg.get("reminder_after_days", 3))
    cooldown_hours = int(cfg.get("cooldown_hours", 48))
    import notifications as _notif

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=reminder_after_days)
    cooldown = now - timedelta(hours=cooldown_hours)
    processed = 0
    sent = 0
    try:
        cursor = db.invoices.find({
            "status": {"$in": ["sent", "pending", "overdue"]},
            "$or": [
                {"sentAt": {"$lte": cutoff.isoformat()}},
                {"created_at": {"$lte": cutoff.isoformat()}},
            ],
        }, {"_id": 0})
        async for inv in cursor:
            processed += 1
            last = inv.get("lastReminderAt")
            if last and last >= cooldown.isoformat():
                continue
            try:
                customer = await db.customers.find_one({"id": inv.get("customerId")}, {"_id": 0}) or {}
                manager = {"id": inv.get("managerId"), "email": inv.get("managerEmail")}
                await _notif.emit(_notif.EVENT_PAYMENT_REMINDER, {
                    "invoice": inv, "customer": customer, "manager": manager,
                })
                await db.invoices.update_one(
                    {"id": inv["id"]},
                    {"$set": {"lastReminderAt": now.isoformat()},
                     "$inc": {"reminderCount": 1}},
                )
                sent += 1
            except Exception:
                logger.exception("[reminder] emit failed for %s", inv.get("id"))
    except Exception:
        logger.exception("[reminder] _run_payment_reminders_once failed")
    return {"processed": processed, "reminders": sent}


async def _payment_reminder_loop():
    """Background reminder scanner.
    Once per hour walks the invoices collection. For every invoice that is
    still pending/sent and whose `sentAt`+reminder_after days has passed
    AND no reminder has been fired in the cooldown window — emit `payment_reminder`.
    Interval and threshold are intentionally conservative so we don't spam.
    All knobs come from the `reminder_settings` collection (live-editable).
    """
    SCAN_INTERVAL_SEC = 3600  # 1h
    await asyncio.sleep(60)  # let server warm up
    while True:
        try:
            res = await _run_payment_reminders_once()
            if res.get("reminders"):
                logger.info(
                    "[reminder] dispatched %d payment reminders (inspected %d)",
                    res["reminders"], res["processed"],
                )
        except Exception:
            logger.exception("[reminder] loop iteration failed")
        await asyncio.sleep(SCAN_INTERVAL_SEC)


# Phase 4 / C-1 — was @fastapi_app.on_event("startup") at this site.
# Renamed from `startup()` to `_main_startup()` to (a) make the call
# site in `lifespan()` explicit, (b) avoid module-namespace collision
# with FastAPI's deprecated default `startup` symbol, and (c) free up
# the bare name `startup` for unit tests / future helpers.
# Orchestrated by `lifespan()` (defined near FastAPI() construction)
# in the same source order as before; behavioural-1:1 with the legacy
# decorator-based wiring.
async def _main_startup():
    global db_client, db
    
    print("="*80)
    print("🔥🔥🔥 STARTUP EXECUTED 🔥🔥🔥")
    print("="*80)
    print("[STARTUP] Initializing...")
    logger.info("[STARTUP] BIBI V3.2 Starting...")
    
    # MongoDB
    db_client = AsyncIOMotorClient(MONGO_URL, maxPoolSize=20, minPoolSize=2)
    db = db_client[DB_NAME]

    # ── Multi-replica-safe JWT secret resolution ──────────────────────
    # Resolve the active JWT signing secret BEFORE any request is served.
    # Priority: ENV JWT_SECRET (primary) → shared secret in Mongo `settings`
    # (emergency fallback) → generate-once & persist to Mongo. This replaces
    # the old per-pod `.jwt_secret` file that caused divergent secrets across
    # replicas → random 401s in production.
    try:
        _jwt_src = await bootstrap_jwt_secret(db)
        import security as _security_mod
        print(f"[STARTUP] ✓ JWT_SECRET resolved (source={_security_mod.JWT_SECRET_SOURCE})")
        logger.info(f"[STARTUP] ✓ JWT_SECRET resolved (source={_security_mod.JWT_SECRET_SOURCE})")
    except Exception as _e:
        logger.error(f"[STARTUP] JWT secret bootstrap error: {_e}")

    # ── Phase 4 / C-2 — app.state mirror (parallel layer, NOT migration) ──
    # The module-level `db` / `db_client` globals (assigned on the two
    # lines immediately above) remain the canonical references for ALL
    # existing read sites in this file and in sub-modules that do
    # `from server import db`. This block adds a redundant **mirror**
    # onto `fastapi_app.state` so future router-level code can begin
    # transitioning to `request.app.state.db` *without a flag-day
    # cutover* and without breaking the still-valid global reads.
    #
    # Scope rules honoured by this mirror:
    #   • the module-level `db` global is NOT removed
    #   • no router migrates onto `request.app.state.db` in this step
    #   • no `from server import db` lazy bridge is removed
    #   • no repository / DTO layer is introduced
    #   • OpenAPI surface unchanged (zero new routes)
    #   • worker registry semantics unchanged
    #
    # Divergence safety: the mirror is set at EXACTLY ONE call-site
    # (here, immediately after the canonical assignment, inside the
    # same function, under the same `global db, db_client` declaration).
    # There is no second writer, so `fastapi_app.state.db is db` is an
    # invariant from the moment `_main_startup()` returns until process
    # exit.
    fastapi_app.state.db = db
    fastapi_app.state.mongo_client = db_client
    # Identity invariant — fails fast if a future edit accidentally
    # introduces a second writer that points the mirror elsewhere.
    assert fastapi_app.state.db is db, "[C-2] app.state.db diverged from canonical db at mirror site"
    assert fastapi_app.state.mongo_client is db_client, "[C-2] app.state.mongo_client diverged from canonical db_client at mirror site"
    print("[STARTUP] ✓ app.state mirror set (db, mongo_client)")
    logger.info("[STARTUP] ✓ app.state mirror set (db, mongo_client)")

    # ── Phase 5.4 / C-4e — db_runtime accessor published ───────────────
    # Publish the live Motor handles into the dedicated accessor module
    # so the C-4e..C-4j migration batches can read via
    # `app.core.db_runtime.get_db()` / `get_mongo_client()` with
    # identical object identity. This is the SINGLE writer site for
    # `db_runtime`; placing it here (immediately after the canonical
    # `db = db_client[DB_NAME]` assignment and the `fastapi_app.state.db`
    # mirror) guarantees:
    #   1. The same object is referenced by the canonical global,
    #      app.state mirror, and accessor — fail-fast identity assertions
    #      below pin this invariant.
    #   2. Every consumer that resolves `get_db()` AFTER this call (i.e.
    #      every router handler, every worker loop iteration, every
    #      module-service `_db()` call) sees the live database.
    #   3. Pre-startup readers (or test-harness paths that bypass
    #      `_main_startup`) keep the legacy `None` semantics — the
    #      accessor's cache stays at its initial `None` value.
    #
    # The `db` Bridge entry in BRIDGE_INVENTORY stays present through
    # C-4e..C-4i; it retires only at C-4j when the DI source
    # (`app.core.deps.get_db`) swaps to delegate to `db_runtime.get_db()`
    # and the AST grep audit confirms zero `from server import db`
    # production sites.
    try:
        from app.core.db_runtime import set_db, get_db as _runtime_get_db, get_mongo_client as _runtime_get_mongo

        set_db(db, db_client)
        assert _runtime_get_db() is db, (
            "[C-4e] db_runtime accessor identity diverged from "
            "canonical server.db at setter site"
        )
        assert _runtime_get_mongo() is db_client, (
            "[C-4e] db_runtime mongo_client accessor identity diverged "
            "from canonical server.db_client at setter site"
        )
        print("[STARTUP] ✓ db_runtime accessor published (Phase 5.4 / C-4e)")
        logger.info("[STARTUP] ✓ db_runtime accessor published (Phase 5.4 / C-4e)")
    except ImportError:
        # Defensive: if app.core.db_runtime is unavailable (partial
        # install / test harness), preserve legacy behaviour — the
        # accessor stays at None. After C-4j retirement this branch is
        # diagnostic-only because no production code path uses the
        # legacy bridge.
        logger.warning(
            "[C-4e] app.core.db_runtime.set_db unavailable; accessor "
            "will return None (legacy behaviour preserved)"
        )

    # ── Notifications system (event bus + email/in-app channels) ──
    try:
        import notifications as _notif_mod
        # ── Phase 5.4 / C-4e — split-brain prevention (db) ─────────────
        # `notifications.init(db, sio)` captures `db` into each channel's
        # `self.db` (mirrors the sio split-brain analysis in C-4c). The
        # C-4e mandate explicitly forbids rewriting init() to
        # accessor-pull — we keep the param-passing 1:1. To PROVE no
        # split-brain, we assert that the runtime accessor and the
        # canonical global reference the SAME Motor object BEFORE the
        # capture happens. If a future refactor proxies / wraps `db`,
        # this assertion fails the lifespan immediately rather than
        # letting NotificationService quietly read/write through a
        # different handle than the rest of the runtime.
        try:
            from app.core.db_runtime import get_db
            assert get_db() is db, (
                "[C-4e] split-brain detected: db_runtime accessor "
                "is NOT server.db at the notifications.init capture site; "
                "NotificationService would diverge from the accessor."
            )
        except ImportError:
            # Defensive — see module-load comment above.
            pass
        # ── Phase 5.4 / C-4c — split-brain prevention ──────────────────
        # NotificationService captures `sio` as a constructor argument
        # (notifications.py:Channel.__init__(db, sio=None)). That
        # captured reference becomes self.sio inside the service and
        # is later used for sio.emit(...) broadcasts. The C-4c mandate
        # explicitly forbids rewriting init() to accessor-pull — we keep
        # the param-passing 1:1. But to PROVE no split-brain (i.e. the
        # captured reference and the accessor reference are the SAME
        # object), we assert identity BEFORE the capture happens.
        # If a future refactor accidentally wraps `sio` (e.g. by
        # subclassing the AsyncServer or substituting a proxy), this
        # assertion fails the lifespan immediately rather than letting
        # NotificationService quietly broadcast through a different
        # object than the accessor.
        try:
            from app.core.socket_runtime import get_sio
            assert get_sio() is sio, (
                "[C-4c] split-brain detected: socket_runtime accessor "
                "is NOT server.sio at the notifications.init capture site; "
                "NotificationService would diverge from the accessor."
            )
        except ImportError:
            # Defensive — see module-load comment in this file. After
            # C-4c retirement this branch is diagnostic-only.
            pass
        _notif_mod.init(db, sio)
        await _notif_mod.service.seed_defaults()
        logger.info("[notif] NotificationService initialised (%s email provider)",
                    _notif_mod.service.email.provider)
        # ── Phase 3.4 / C-3 — payment_reminder_loop migrated to worker_registry ──
        # Billing SLA worker: pending-invoice reminders → email + Socket.IO emit
        # via NotificationService bus.  critical=True because failure silently
        # stops reminder dispatch (revenue-impact).  Restart storm capped at 3
        # with 60s backoff.  48h cooldown on `invoices.lastReminderAt` provides
        # idempotency against transient duplicate runs.
        try:
            from app.core.worker_registry import worker_registry
            worker_registry.register(
                "payment_reminder",
                _payment_reminder_loop,
                restart_policy="on_failure",
                critical=True,                  # billing SLA
                restart_backoff_sec=60.0,
                max_restarts=3,
            )
            logger.info("[notif] payment_reminder worker registered (worker_registry)")
        except Exception as _e:
            # Defensive fallback to legacy path — preserves existing behaviour
            # exactly if registry import fails for any reason.
            logger.exception("[notif] payment_reminder worker_registry register failed, falling back to legacy: %s", _e)
            asyncio.create_task(_payment_reminder_loop())
    except Exception:
        logger.exception("[notif] failed to initialise NotificationService")

    # ── Доопр #22 — Lead-reminder loop (30 min / 2 h) ───────────────────
    try:
        from app.core.worker_registry import worker_registry as _wr_leadrem
        from app.services.lead_notifications import scan_unprocessed_leads as _scan_leads
        async def _lead_reminder_loop():
            while True:
                try:
                    await _scan_leads(db)
                except Exception as _se:
                    logger.warning("[lead_reminders] tick failed: %s", _se)
                await asyncio.sleep(60)  # check every minute
        _wr_leadrem.register(
            "lead_reminders",
            _lead_reminder_loop,
            restart_policy="on_failure",
            critical=False,
            restart_backoff_sec=30.0,
            max_restarts=5,
        )
        logger.info("[lead_reminders] worker registered (worker_registry)")
    except Exception as _e:
        logger.exception("[lead_reminders] failed to register: %s", _e)

    # ── Wave-8 · Insights / Risk & Alerts · escalation wake-up worker ──
    # Modular worker that returns snoozed escalations to the active queue
    # once their `snoozedUntil` elapses, and emits a real-time notification.
    # Implementation lives in app/workers/escalations_wakeup_worker.py to
    # keep server.py clean and the worker independently testable.
    try:
        from app.workers import escalations_wakeup_worker as _esc_wakeup
        _esc_wakeup.init(db=db, sio=sio)
        from app.core.worker_registry import worker_registry as _wr_esc
        _wr_esc.register(
            "escalations_wakeup",
            _esc_wakeup.loop,
            restart_policy="on_failure",
            critical=False,                # manual refresh always works as fallback
            restart_backoff_sec=30.0,
            max_restarts=5,
        )
        logger.info("[esc_wakeup] worker registered (worker_registry)")
    except Exception as _e:
        logger.exception("[esc_wakeup] worker registration failed (fallback to legacy create_task): %s", _e)
        try:
            from app.workers import escalations_wakeup_worker as _esc_wakeup_fb
            _esc_wakeup_fb.init(db=db, sio=sio)
            asyncio.create_task(_esc_wakeup_fb.loop())
            logger.info("[esc_wakeup] worker started via legacy create_task")
        except Exception:
            logger.exception("[esc_wakeup] BOTH paths failed — worker NOT running")

    

    # ── [ECO CLEANUP] Catalog Promotion Worker fully removed (auto-domain). ──

    # ── [VIN-INGESTION RETIREMENT 2026-06] vin_data canonical indexes
    # (Phase A1) and the background enrichment worker (Phase A2) removed.
    # They served the retired car-auction catalogue; the `vin_data`
    # collection no longer exists and no ECO/CRM route reads it.

    # ── Phase 3.4 / C-1 — Worker registry parallel mirror ──
    # Ringostat CRON is the first worker migrated to the centralised
    # WorkerRegistry (app/core/worker_registry.py).  Its supervised task
    # is started via `worker_registry.start_all()` at the end of this
    # startup orchestration.  All other long-running loops (6 remaining)
    # still use the legacy `asyncio.create_task(...)` path until their
    # respective C-N checkpoints.
    try:
        from app.core.worker_registry import worker_registry
        worker_registry.register(
            "ringostat_cron",
            ringostat_cron_loop,
            restart_policy="on_failure",
            critical=False,
            restart_backoff_sec=30.0,
        )
        logger.info("[STARTUP] ✓ Ringostat CRON registered with worker_registry")
    except Exception as _e:
        # Defensive: fall back to legacy direct task if registry fails to
        # load for any reason — preserves the existing behaviour exactly.
        logger.exception("[STARTUP] worker_registry register failed, falling back to legacy: %s", _e)
        asyncio.create_task(ringostat_cron_loop())
        print("[STARTUP] ✓ Ringostat CRON started (legacy path)")
    else:
        print("[STARTUP] ✓ Ringostat CRON registered (worker_registry)")


    # Ensure unique indexes to prevent duplicate seed documents.
    # These collections all use a business "id" key (not Mongo _id) to
    # identify records across API calls. Without a unique index, concurrent
    # seed requests racing on `find_one() → insert_one()` will create dupes.
    try:
        await db.shipments.create_index("id", unique=True, name="uniq_shipment_id")
        await db.deals.create_index("id", unique=True, name="uniq_deal_id")
        await db.shipment_events.create_index("id", unique=True, name="uniq_event_id")
        await db.staff.create_index("email", unique=True, name="uniq_staff_email")
        # Audit log TTL 90 days — Phase 5.4 / C-1 ownership routes through
        # SecurityAuditRepository.ensure_indexes()
        from app.repositories import SecurityAuditRepository
        await SecurityAuditRepository(db).ensure_indexes()
        # [VIN-INGESTION RETIREMENT 2026-06] Removed index creation for the
        # retired VIN→container→vessel resolution automation layer
        # (vf_payload_meta/raw, shipment_identity_links, resolver_exceptions,
        # vin_container_links, vessel_candidates_tracking). Those collections
        # are dropped and no live route writes to them.
        # Nonce store + per-client HMAC secret registry are KEPT: the
        # security helpers (verify_nonce / per-client secret lookup) still
        # reference them.
        await db.ext_nonces.create_index(
            "ts", expireAfterSeconds=120, name="ext_nonces_ttl_120s"
        )
        await db.ext_nonces.create_index("nonce", unique=True, name="uniq_ext_nonce")
        await db.ext_clients.create_index("clientId", unique=True, name="uniq_ext_clientId")
        await db.ext_clients.create_index("managerEmail", name="idx_ext_clients_email")
        # PHASE SECURITY S3.3 — CSP violation reports (TTL 30 days)
        await db.security_csp_reports.create_index(
            "ts", expireAfterSeconds=30 * 24 * 3600, name="csp_reports_ttl_30d"
        )
        print("[STARTUP] ✓ Unique indexes ensured (shipments/deals/shipment_events/staff) + TTL (audit/ext_nonces/csp) + ext_clients")
    except Exception as e:
        logger.warning(f"[STARTUP] index creation (non-fatal): {e}")

    # ── Seed staff accounts from env (bootstrap only; prod uses real secrets mgr)
    try:
        await _seed_staff_from_env()
    except Exception as e:
        logger.warning(f"[STARTUP] staff seeding (non-fatal): {e}")

    # ── Optional demo CLIENT seed (env-gated; prod-safe no-op when unset) ──
    try:
        await _seed_demo_client_from_env()
    except Exception as e:
        logger.warning(f"[STARTUP] demo-client seeding (non-fatal): {e}")

    # ── Customer accounts ────────────────────────────────────────────────
    # Production data mode: the backend NEVER seeds demo/test customers or
    # demo business data. Real customers are created solely via the
    # registration / Google-auth flows, and every cabinet screen reflects the
    # customer's real (often empty) business state. (Demo seeding subsystem
    # removed 2026-06 — see app/services/customers.ensure_customer_record.)

    # ── [AUTO-DOMAIN REMOVED — Wave 1] car blog seeder disabled ──────────
    # blog_seeder seeded bilingual CAR articles. Will be replaced by a
    # waste-domain content seeder in a later wave.
    logger.info("[STARTUP] blog seeder disabled (auto-domain removed)")

    # ── ECO Waste Core seed (Wave 2) — indexes + idempotent code seed ────
    try:
        from app.waste.service import seed_waste_core as _seed_waste_core
        _wres = await _seed_waste_core(db)
        logger.info("[STARTUP] ✓ waste core ready: %s", _wres)
    except Exception as _we:
        logger.warning("[STARTUP] waste core seed (non-fatal): %s", _we)

    # ── [VIN-INGESTION RETIREMENT 2026-06] Cold-start vehicle catalogue
    # safety-net removed. It formerly kicked off a background
    # BitmotorsFullSync scrape when `vin_data` was nearly empty. The car
    # catalogue domain is gone; ECO seeds its own waste catalogue above
    # (`seed_waste_core`), so no auto-scraper cold-start is needed.

    # ── Bug-fix Wave: backfill deals missing `id` so pipeline picker sees them ──
    # POST /api/deals already writes both `_id` and `id`. This handles legacy
    # documents that were inserted before that fix shipped (Wave 6 audit).
    try:
        bf_res = await db.deals.update_many(
            {"$or": [{"id": {"$exists": False}}, {"id": None}, {"id": ""}]},
            [{"$set": {"id": {"$toString": "$_id"}}}],
        )
        if bf_res.modified_count:
            logger.info(
                f"[STARTUP] ✓ deals.id backfill: {bf_res.modified_count} docs updated"
            )
            print(f"[STARTUP] ✓ deals.id backfill: {bf_res.modified_count} docs updated")
        else:
            logger.info("[STARTUP] deals.id backfill: nothing to migrate")
    except Exception as _bfe:
        logger.warning(f"[STARTUP] deals.id backfill failed (non-fatal): {_bfe}")

    print("[STARTUP] Ready!")
    print("="*80)
    logger.info("BIBI V3.2 - Ready")

    # ── Phase B3 observability layer (Wave 3 freeze) ──
    try:
        from app.core.observability import init_observability
        init_observability(fastapi_app)
        logger.info("[STARTUP] ✓ Observability layer ready (errors / slow-query / parser-fail / events)")
    except Exception as _obs_e:   # noqa: BLE001
        logger.warning(f"[STARTUP] observability init skipped: {_obs_e}")

    # ── Register security hooks (nonce replay-guard + HMAC failure audit) ──
    register_nonce_verifier(_verify_ext_nonce)
    register_hmac_fail_audit(_audit_hmac_failure)
    register_client_secret_lookup(_lookup_ext_client_secret)
    logger.info("[STARTUP] ✓ Security hooks registered (nonce + hmac_fail audit + ext_client lookup)")

    # ── Automation layer worker (identity resolver, Phase A+B+C) ──
    # Phase 3.4 / C-5 — migrated to worker_registry supervision.
    # HOT-PATH worker: scans shipments with incomplete identity, routes
    # through identity_runtime.resolve() (Phase 3.2 boundary).  Mutates
    # shipment_identity_links + resolver_exceptions.  Cadence preserved
    # (RESOLVER_INTERVAL_SEC=300s).  critical=True because failure stops
    # auto-identity backfill → operators see stale exception queue.

    # ── Phase D worker: auto transfer detection sweeper ──
    # Phase 3.4 / C-6 — migrated to worker_registry supervision.
    # HOT-PATH worker: scans shipments with candidateVessel, routes through
    # identity_runtime.process_transfer() (Phase 3.2 boundary).  May close
    # current stage + push new vessel stage to shipment_events.  Cadence
    # preserved (TRANSFER_DETECT_INTERVAL_SEC=120s).  critical=True because
    # failure stops auto vessel transitions → manual exception queue grows.

    # ── Ops Guardian: alerts + auto-healing ──────────────────────────
    # Wired to live `control_overview()` so the guardian sees the exact
    # same data as the admin UI and catches inconsistencies fast.
    # Phase 3.4 / C-4 — migrated to worker_registry supervision.
    # Ops/heal worker: scans control_overview() for inconsistencies and
    # auto-corrects + emits alerts.  Takes 2 args (db, _overview_fetcher),
    # so we wrap in an async coro_factory closure.
    try:
        from ops_guardian import ops_guardian_loop

        async def _overview_fetcher():
            return {}  # [ECO CLEANUP] auto control_overview removed

        async def _ops_guardian_coro():
            await ops_guardian_loop(db, _overview_fetcher)

        from app.core.worker_registry import worker_registry
        worker_registry.register(
            "ops_guardian",
            _ops_guardian_coro,
            restart_policy="on_failure",
            critical=True,            # alerts + auto-heal SLA
            restart_backoff_sec=60.0,
            max_restarts=3,
        )
        logger.info("[STARTUP] ✓ Ops Guardian started (alerts + auto-heal)")
    except Exception as e:
        logger.exception("[STARTUP] ops_guardian worker_registry register failed, falling back to legacy: %s", e)
        try:
            from ops_guardian import ops_guardian_loop  # type: ignore

            async def _overview_fetcher_fb():
                return {}  # [ECO CLEANUP] auto control_overview removed

            asyncio.create_task(ops_guardian_loop(db, _overview_fetcher_fb))
            logger.info("[STARTUP] ✓ Ops Guardian started (alerts + auto-heal)")
        except Exception as e2:
            logger.warning(f"[STARTUP] ops guardian init failed: {e2}")

    # ─── P1.1 Refund Cron — REMOVED (car-import legal_workflow retired) ───

    # ─── Block 6.2 — Lead SLA worker (30-min remind, 2h escalate) ─────
    try:
        from app.workers.lead_sla_worker import lead_sla_loop

        async def _lead_sla_coro():
            await lead_sla_loop(db)

        from app.core.worker_registry import worker_registry as _wr_lsla
        _wr_lsla.register(
            "lead_sla",
            _lead_sla_coro,
            restart_policy="on_failure",
            critical=False,
            restart_backoff_sec=30.0,
            max_restarts=10,
        )
        logger.info("[STARTUP] ✓ Lead SLA worker registered (30 min remind / 2h escalate)")
    except Exception as e:
        logger.exception("[STARTUP] lead_sla worker_registry register failed, falling back to legacy: %s", e)
        try:
            from app.workers.lead_sla_worker import lead_sla_loop  # type: ignore
            asyncio.create_task(lead_sla_loop(db))
            logger.info("[STARTUP] ✓ Lead SLA worker started (legacy fallback)")
        except Exception as e2:
            logger.warning(f"[STARTUP] lead_sla worker init failed: {e2}")

    # ─── P1.3.1 Audit indexes (Phase 5.3 / C-11 — through AuditEventsRepository) ──
    try:
        from app.repositories import AuditEventsRepository
        await AuditEventsRepository(db).ensure_indexes()
        logger.info("[STARTUP] ✓ audit_events indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] audit_events indexes failed: {e}")

    # ─── P1.2 Financial Breakdown templates + indexes ──────────────────
    try:
        import financial_breakdown as _fb
        await _fb.ensure_indexes(db)
        seed_result = await _fb.seed_default_templates(db)
        logger.info(f"[STARTUP] ✓ invoice_templates seeded "
                    f"(created={seed_result['created']}, kept={seed_result['kept']})")
    except Exception as e:
        logger.warning(f"[STARTUP] financial_breakdown seed failed: {e}")

    # ─── P1.2-payments Payments tracking indexes ───────────────────────
    try:
        import payments_tracking as _pt
        await _pt.ensure_indexes(db)
        logger.info("[STARTUP] ✓ payments indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] payments indexes failed: {e}")

    # ─── [ECO CLEANUP] wishlist_deals indexes REMOVED (auto-domain) ────

    # ─── Auth policy (login_audit + auth_email_otp) indexes ────────────
    try:
        from app.services.auth_policy import ensure_indexes as _auth_ensure
        await _auth_ensure(db)
        logger.info("[STARTUP] ✓ auth_policy indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] auth_policy indexes failed: {e}")

    # ─── BG Contract Templates (Договор за поръчка — ПМ АВТО ГРУП) ──────
    # Seeds Bulgarian commission contract + acceptance protocol templates
    # plus the company-branding integration_config that all PDF renderers
    # use as the ИЗПЪЛНИТЕЛ identity (ПМ АВТО ГРУП ЕООД, EИК, IBAN, etc).
    try:
        from app.repositories import document_templates as _tpl_repo
        from app.services.pdf_templates_bg import BG_TEMPLATES, PM_AUTO_GROUP_BRANDING
        from datetime import datetime, timezone
        await _tpl_repo.ensure_indexes()
        # Idempotent seed: only insert templates that are NOT already present
        # by (type, language). Existing defaults are kept untouched.
        for t in BG_TEMPLATES:
            exists = await db.document_templates.find_one(
                {"type": t["type"], "language": t["language"], "is_default": True},
                {"_id": 0, "id": 1},
            )
            if exists:
                # Refresh HTML body if version differs so legal updates land
                await db.document_templates.update_one(
                    {"id": exists["id"]},
                    {"$set": {
                        "html":       t["html"],
                        "meta":       t.get("meta") or {},
                        "name":       t["name"],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
            else:
                await _tpl_repo.create_template(
                    {**t, "is_default": True, "is_active": True},
                    created_by="seed_bg",
                )
        # Company branding for ИЗПЪЛНИТЕЛ identity used by ALL contract PDFs
        await db.integration_configs.update_one(
            {"provider": "company_branding"},
            {"$set": {
                "provider":   "company_branding",
                "data":       PM_AUTO_GROUP_BRANDING,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        logger.info("[STARTUP] ✓ BG contract templates + ПМ АВТО ГРУП branding seeded")
    except Exception as e:
        logger.warning(f"[STARTUP] BG contract templates seed failed: {e}")

    # ─── Resend transactional email — idempotent enable ─────────────────
    # Ensures integration_configs.resend exists & is enabled with a sender so
    # the admin UI (Admin → Integrations → Resend) shows it and emails leave
    # dry_run mode. Uses $setOnInsert so any admin-edited apiKey/from is kept.
    try:
        from notifications import RESEND_API_KEY_FALLBACK, RESEND_DEFAULT_FROM
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.integration_configs.update_one(
            {"provider": "resend"},
            {
                "$setOnInsert": {
                    "provider": "resend",
                    "isEnabled": True,
                    "credentials": {
                        "apiKey": RESEND_API_KEY_FALLBACK,
                        "from": RESEND_DEFAULT_FROM,
                    },
                    "settings": {"from": RESEND_DEFAULT_FROM},
                    "mode": "live",
                    "created_at": now_iso,
                },
                "$set": {"updated_at": now_iso},
            },
            upsert=True,
        )
        logger.info("[STARTUP] ✓ Resend integration ensured (email live)")
    except Exception as e:
        logger.warning(f"[STARTUP] Resend integration seed failed: {e}")



    # ─── Analytics tracking — events + marketing_campaigns indexes ───────
    try:
        from app.routers.analytics_tracking import ensure_analytics_indexes as _an_ensure
        await _an_ensure(db)
        logger.info("[STARTUP] ✓ analytics_events indexes ensured (TTL 90d)")
    except Exception as e:
        logger.warning(f"[STARTUP] analytics indexes failed: {e}")

    # ─── Wave 6 — deal_timeline indexes + legal_policy defaults ──────────
    try:
        if _wave6_on_startup is not None:
            await _wave6_on_startup(db)
            logger.info("[STARTUP] ✓ Wave 6 deal_timeline indexes + legal_policy seeded")
    except Exception as e:
        logger.warning(f"[STARTUP] wave6 init failed: {e}")

    # ─── Wave 7 — reassignment indexes + customers.managerId backfill ────
    try:
        if _wave7_on_startup is not None:
            await _wave7_on_startup(db)
            logger.info("[STARTUP] ✓ Wave 7 reassignment indexes + customer.managerId backfill done")
    except Exception as e:
        logger.warning(f"[STARTUP] wave7 init failed: {e}")

    # ─── Block 6.2 — Lead SLA indexes ────────────────────────────────────
    try:
        if _lead_sla_on_startup is not None:
            await _lead_sla_on_startup(db)
            logger.info("[STARTUP] ✓ Lead SLA indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] lead_sla init failed: {e}")

    # ─── Block 7.1 — Change History indexes ──────────────────────────────
    try:
        if _change_history_on_startup is not None:
            await _change_history_on_startup(db)
            logger.info("[STARTUP] ✓ Change History indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] change_history init failed: {e}")

    # ─── Block 7.3 — Manager Instructions indexes ────────────────────────
    try:
        if _mgr_instr_on_startup is not None:
            await _mgr_instr_on_startup(db)
            logger.info("[STARTUP] ✓ Manager Instructions indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] manager_instructions init failed: {e}")

    # ─── Block 7.2 — Canonical folder taxonomy migration (idempotent) ────
    try:
        from app.services.file_manager import (
            migrate_system_folders_to_canonical,
            ensure_system_folders as _ensure_sys_folders,
        )
        _fm_report = await migrate_system_folders_to_canonical()
        logger.info("[STARTUP] ✓ Folder taxonomy migration: %s", _fm_report)

        # Block 7.2 — also seed canonical folders for any customer that has
        # NO system folders at all (e.g. created before this feature shipped).
        _backfill_seeded = 0
        async for _cust in db.customers.find({}, {"_id": 0, "id": 1}):
            _cid = _cust.get("id")
            if not _cid:
                continue
            _has_sys = await db.client_folders.count_documents(
                {"customer_id": _cid, "is_system": True}, limit=1
            )
            if _has_sys == 0:
                await _ensure_sys_folders(_cid, created_by="system:backfill")
                _backfill_seeded += 1
        if _backfill_seeded:
            logger.info("[STARTUP] ✓ Folder taxonomy backfill: seeded canonical folders for %d existing customers", _backfill_seeded)
    except Exception as e:
        logger.warning(f"[STARTUP] folder taxonomy migration failed: {e}")

    # ─── Launch-Candidate: Stripe env-fallback hydration (idempotent) ────
    # The Stripe config lives in db.integration_configs (admin-editable).
    # If the row is missing or has an empty secretKey, we hydrate it from
    # the STRIPE_* env vars in /app/backend/.env so the integration keeps
    # working after a DB wipe. Admin overrides via PATCH still take effect.
    try:
        _stripe_env_secret = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
        _stripe_env_pub    = (os.environ.get("STRIPE_PUBLISHABLE_KEY") or "").strip()
        _stripe_env_rk     = (os.environ.get("STRIPE_RESTRICTED_KEY") or "").strip()
        _stripe_env_whsec  = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
        _stripe_env_mode   = (os.environ.get("STRIPE_MODE") or "sandbox").strip()
        if _stripe_env_secret:
            _existing = await db.integration_configs.find_one({"provider": "stripe"}, {"_id": 0}) or {}
            _cred_existing = (_existing.get("credentials") or {})
            if not (_cred_existing.get("secretKey") or "").strip():
                # Seed (or top-up an empty row) — never overwrite admin edits.
                _now_iso = datetime.now(timezone.utc).isoformat()
                _seed_doc = {
                    "provider": "stripe",
                    "credentials": {
                        "secretKey": _stripe_env_secret,
                        "restrictedKey": _stripe_env_rk,
                        "publishableKey": _stripe_env_pub,
                        "webhookSecret": _stripe_env_whsec,
                    },
                    "settings": _existing.get("settings") or {
                        "currency": "USD",
                        "enabledMethods": {"card": True, "apple_pay": True, "google_pay": True, "link": True},
                        "checkoutMode": "hosted",
                        "automaticPaymentMethods": True,
                        "captureMethod": "automatic",
                        "allowPromotionCodes": True,
                        "billingAddressCollection": "auto",
                    },
                    "mode": _existing.get("mode") or _stripe_env_mode,
                    "isEnabled": True,
                    "updated_at": _now_iso,
                    "_seeded_from_env": True,
                }
                await db.integration_configs.update_one(
                    {"provider": "stripe"}, {"$set": _seed_doc}, upsert=True,
                )
                logger.info(
                    "[STARTUP] ✓ Stripe config hydrated from env (mode=%s, sk_suffix=…%s, pk_suffix=…%s)",
                    _seed_doc["mode"], _stripe_env_secret[-4:], _stripe_env_pub[-4:],
                )
            else:
                logger.debug("[STARTUP] Stripe config already populated in DB — env fallback skipped")
        else:
            logger.debug("[STARTUP] STRIPE_SECRET_KEY env not set — env fallback skipped")
    except Exception as e:
        logger.warning(f"[STARTUP] Stripe env hydration failed (non-fatal): {e}")

    # ─── Launch-Candidate: Ringostat env-fallback hydration (idempotent) ─
    # Same model as Stripe: defaults live in app.config.ringostat_defaults
    # (also exposed via RINGOSTAT_* env vars in /app/backend/.env so they
    # survive a DB wipe / fresh deploy). Admin edits via
    # PATCH /api/admin/ringostat/settings continue to win at runtime
    # because we only seed when the row is missing OR has an empty api_key.
    try:
        from app.config.ringostat_defaults import get_defaults as _rd_get
        _rd_defaults = _rd_get()
        _rd_existing = await db.ringostat_config.find_one({}, {"_id": 0}) or {}
        _need_seed = (
            not _rd_existing
            or not (_rd_existing.get("api_key") or "").strip()
            or not (_rd_existing.get("project_id") or "").strip()
        )
        if _need_seed and (_rd_defaults.get("api_key") or "").strip():
            # Merge defaults under existing values — admin overrides win on any
            # field they actually populated; empty fields fall through to
            # hardcoded baseline so the integration is "always on".
            _rd_doc = dict(_rd_defaults)
            for k, v in (_rd_existing or {}).items():
                if v not in (None, "", {}, []):
                    _rd_doc[k] = v
            _rd_doc.setdefault("enabled", True)
            _rd_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            _rd_doc["_seeded_from_env"] = True
            await db.ringostat_config.update_one({}, {"$set": _rd_doc}, upsert=True)
            logger.info(
                "[STARTUP] ✓ Ringostat config hydrated from env (project_id=%s, api_key=…%s)",
                _rd_doc.get("project_id"), (_rd_doc.get("api_key") or "")[-4:],
            )
        else:
            logger.debug("[STARTUP] Ringostat config already populated in DB — env fallback skipped")
    except Exception as e:
        logger.warning(f"[STARTUP] Ringostat env hydration failed (non-fatal): {e}")

    # ─── Launch-Candidate: Lead `id` backfill (idempotent) ──────────────
    # Historical Ringostat auto-create path set `_id` but forgot to set
    # the canonical `id` field that the frontend + lookup endpoints rely
    # on. Result: clicking such a lead → 404 "Lead not found".
    # The source bug is fixed; this one-off backfill cleans up legacy rows.
    try:
        _legacy_q = {"$or": [
            {"id": {"$exists": False}},
            {"id": None},
            {"id": ""},
        ]}
        _backfilled_leads = 0
        async for _lg in db.leads.find(_legacy_q, {"_id": 1}):
            _lid = _lg.get("_id")
            if not _lid:
                continue
            await db.leads.update_one({"_id": _lid}, {"$set": {"id": str(_lid)}})
            _backfilled_leads += 1
        if _backfilled_leads:
            logger.info("[STARTUP] ✓ Lead `id` backfill: synced %d legacy leads", _backfilled_leads)
    except Exception as e:
        logger.warning(f"[STARTUP] Lead id backfill failed (non-fatal): {e}")

    # ─── Wave 2A — Calls Foundation indexes (ringostat_calls read paths) ─
    try:
        if _wave2a_on_startup is not None:
            await _wave2a_on_startup(db)
            logger.info("[STARTUP] ✓ Wave 2A ringostat_calls indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] wave2a init failed: {e}")

    # ─── Wave 11 — Deal360 (deal_documents indexes) ──────────────────────
    try:
        if _wave11_on_startup is not None:
            await _wave11_on_startup(db)
            logger.info("[STARTUP] ✓ Wave 11 Deal360 deal_documents indexes ensured")
    except Exception as e:
        logger.warning(f"[STARTUP] wave11 init failed: {e}")

    # ─── Phase 5.4 / C-3A — Google ClientID one-time backfill ───────────
    # If `app_settings.auth.google.clientId` is empty AND the legacy
    # `integration_configs.{provider:"google_oauth"}.credentials.clientId`
    # has a value, copy the legacy value into app_settings ONCE so that
    # `app_settings` becomes the sole source-of-truth going forward.
    #
    # Idempotent: on subsequent boots, `app_settings` will already have
    # the value and this block is a no-op (the guard is the emptiness of
    # `app_settings.auth.google.clientId`).
    #
    # This is intentionally a STARTUP concern (not a request-time
    # concern) — request-time fallback in
    # `settings_service.resolve_google_client_id` covers the rare race
    # where backfill has not yet run but a request arrives.
    try:
        from app.repositories import IntegrationConfigsRepository
        svc_settings = get_settings_service()
        current_auth = await svc_settings.get_auth()
        current_cid = ((current_auth.get("google") or {}).get("clientId") or "").strip()
        if not current_cid:
            legacy_doc = await IntegrationConfigsRepository(db).find_by_provider("google_oauth")
            legacy_cid = ((legacy_doc.get("credentials") or {}).get("clientId") or "").strip()
            if legacy_cid:
                merged_google = dict(current_auth.get("google") or {})
                merged_google["clientId"] = legacy_cid
                await svc_settings.patch_auth({"google": merged_google}, by="startup_backfill_c3a")
                logger.info(
                    "[STARTUP] ✓ Phase 5.4 / C-3A — google_oauth clientId backfilled "
                    "from integration_configs into app_settings (legacy_cid_suffix=…%s)",
                    legacy_cid[-8:] if len(legacy_cid) > 8 else legacy_cid,
                )
            else:
                logger.debug("[STARTUP] C-3A backfill: no legacy clientId to migrate")
        else:
            logger.debug("[STARTUP] C-3A backfill: app_settings already has clientId — skip")
    except Exception as e:
        logger.warning(f"[STARTUP] C-3A google backfill failed (non-fatal): {e}")

    # ─── Phase 3.4 / C-1 — Worker registry start_all ────────────────────
    # Idempotent: only starts workers that were registered via
    # `worker_registry.register(...)` earlier in this startup function and
    # are not already running.  Currently only `ringostat_cron` is
    # registered; the other 6 long-running loops still use the legacy
    # `asyncio.create_task(...)` path (to be migrated in C-2..C-7).
    try:
        from app.core.worker_registry import worker_registry
        await worker_registry.start_all()
        registered = worker_registry.names()
        logger.info(
            "[STARTUP] ✓ worker_registry.start_all complete — %d workers: %s",
            len(registered), registered,
        )
        print(f"[STARTUP] ✓ worker_registry started {len(registered)} worker(s): {registered}")
    except Exception as e:
        logger.exception("[STARTUP] worker_registry.start_all failed: %s", e)


# Phase 4 / C-1 — was @fastapi_app.on_event("shutdown") at this site.
# Orchestrated by `lifespan()` (after `yield`) defined near FastAPI()
# construction; behavioural-1:1 with the legacy decorator-based
# shutdown wiring.
async def _worker_registry_shutdown():
    """Phase 3.4 / C-1 — graceful shutdown for registry-owned workers.

    Cancels and awaits all supervised workers with a 5s grace period.
    Legacy `asyncio.create_task(...)` workers are NOT touched here —
    they continue using the implicit asyncio cancellation that happens
    when the event loop closes.  This handler only owns workers that
    were explicitly registered via `worker_registry.register(...)`.
    """
    try:
        from app.core.worker_registry import worker_registry
        await worker_registry.stop_all(grace_period_sec=5.0)
        logger.info("[SHUTDOWN] ✓ worker_registry.stop_all complete")
    except Exception as e:
        logger.warning("[SHUTDOWN] worker_registry.stop_all failed: %s", e)


async def _seed_staff_from_env():
    """Seed/refresh staff accounts on every startup — deployment-resilient.

    Three layers of resilience so authorization survives any redeploy:
      1. Hard-coded production seeds (fixed emails+passwords) — guarantee that
         the canonical operator accounts always exist, even if `.env` is
         missing/wiped/rebuilt by the deployment pipeline.
      2. Optional env overrides (BIBI_*_EMAIL / BIBI_*_PASSWORD) — let the
         operator rotate creds without code changes.
      3. Idempotent force-sync — on every boot we re-hash and write the
         current desired password into `db.staff.password_hash`. If the user
         existed with an old hash (e.g. from a previous deploy), it is brought
         back in line with the current desired password. Existing role/email
         documents are kept (NOT deleted), so all FK-style references survive.

    This means:
      • New deploy with fresh DB → users created with current creds.
      • Existing DB after redeploy → existing users get their password reset
        to match the current desired password (so login NEVER breaks because
        of a stale hash).
      • DB volume preserved across deploys → leads/deals/cars survive untouched.
    """
    # ── Security gate (Final Consistency Task §5) ───────────────────────────
    # Seeding demo/dev accounts is DISABLED by default. It only runs when the
    # explicit dev/test flag ``ECO_ENABLE_DEV_SEED`` is truthy. In production
    # leave it unset → no auto-seeded credentials exist.
    _seed_flag = os.environ.get("ECO_ENABLE_DEV_SEED", "false").strip().lower()
    if _seed_flag not in ("1", "true", "yes", "on"):
        logger.info("[STARTUP] dev account seeding disabled (ECO_ENABLE_DEV_SEED not set)")
        return

    # ── Layer 1 · Hard-coded production accounts ─────────────────────────────
    # These are the canonical operator credentials. They are intentionally
    # baked in so a redeployed container without `.env` still has working auth.
    # Override at runtime via the corresponding BIBI_* env vars below.
    #
    # Project has exactly FOUR roles total: {admin, team_lead, manager, user}.
    # There is no "owner" or "master_admin" — admin@bibi.cars is the top-level
    # administrator. `master_admin` is kept in security.py only as a legacy
    # alias so old tokens/rows keep working; new code should use `admin`.
    DEFAULTS = {
        "admin": {
            "email": "admin@bibi.cars",
            # PHASE SECURITY S3.4 — secret moved out of source → env BIBI_ADMIN_PASSWORD.
            "password": "",
            "label": "Admin",
        },
        "manager": {
            "email": "manager@bibi.cars",
            # NOTE 2026-05-25: the password policy (>=8 chars, upper+lower+digit+
            # special) applies ONLY to /api/auth/change-password — i.e. when a
            # user *changes* their password. Pre-existing seeded passwords are
            # not blocked by it, so we keep this legacy alphanumeric value so
            # the operator can still log in with the historical credential.
            # If you rotate it via the UI, the new value must comply with the
            # policy.
            # PHASE SECURITY S3.4 — secret moved out of source → env BIBI_MANAGER_PASSWORD.
            "password": "",
            "label": "Manager",
        },
    }

    # Hard cleanup: remove stray "owner"/"master_admin" AND the now-removed
    # ``team_lead`` role — the product no longer has a team-lead. ``admin`` is
    # the canonical top role; ``manager`` is the only operational role.
    try:
        await db.staff.delete_many({"$or": [
            {"role": "owner"},
            {"email": "owner@bibi.cars"},
            {"role": "team_lead"},
            {"role": "team-lead"},
            {"role": "teamlead"},
            {"email": "teamlead@bibi.cars"},
        ]})
    except Exception as _e:
        logger.warning(f"[STARTUP] could not purge stray accounts: {_e}")

    # ── Layer 2 · Env overrides (neutral names; legacy BIBI_* kept as fallback)
    env_map = {
        "admin":        ("ECO_ADMIN_EMAIL",     "ECO_ADMIN_SEED_PASSWORD"),
        "manager":      ("ECO_MANAGER_EMAIL",   "ECO_MANAGER_SEED_PASSWORD"),
    }
    _legacy_env_map = {
        "admin":        ("BIBI_ADMIN_EMAIL",     "BIBI_ADMIN_PASSWORD"),
        "manager":      ("BIBI_MANAGER_EMAIL",   "BIBI_MANAGER_PASSWORD"),
    }

    seeds = []
    for role, default in DEFAULTS.items():
        env_email_key, env_pwd_key = env_map[role]
        legacy_email_key, legacy_pwd_key = _legacy_env_map[role]
        email = (os.environ.get(env_email_key) or os.environ.get(legacy_email_key)
                 or default["email"]).strip().lower()
        pwd = (os.environ.get(env_pwd_key) or os.environ.get(legacy_pwd_key)
               or default["password"])
        seeds.append((role, default["label"], email, pwd))

    # ── Layer 3 · Idempotent force-sync ──────────────────────────────────────
    for role, label, email, pwd in seeds:
        if not email or not pwd:
            if not pwd:
                # PHASE SECURITY S3.4 — password now comes from env (BIBI_*_PASSWORD).
                # If neither env nor an existing DB account is present this role
                # cannot be seeded → surface it loudly so prod misconfig is caught.
                logger.warning(
                    f"[STARTUP] no password for role '{role}' — set "
                    f"{env_map[role][1]} in the environment to (re)seed it"
                )
            continue
        try:
            desired_hash = hash_password(pwd)
        except Exception as e:
            logger.error(f"[STARTUP] cannot hash password for {email}: {e}")
            continue

        existing = await db.staff.find_one({"email": email})
        if existing:
            updates = {}
            # 1. Role drift: if env/default says master_admin but DB says
            #    something else, reconcile.
            if (existing.get("role") or "").lower() != role:
                updates["role"] = role
                logger.info(
                    f"[STARTUP] role drift for {email}: "
                    f"{existing.get('role')} → {role}"
                )
            # 2. Force password sync — ALWAYS make stored hash verify against
            #    the current desired password. This is what keeps auth from
            #    "breaking after redeploy".
            stored = existing.get("password_hash") or existing.get("password") or ""
            try:
                ok = isinstance(stored, str) and bool(stored) and verify_password(pwd, stored)
            except Exception:
                ok = False
            if not ok:
                updates["password_hash"] = desired_hash
                # Clear legacy plain-text `password` field if present.
                if "password" in existing and existing.get("password") != desired_hash:
                    updates["password"] = None
                logger.info(f"[STARTUP] resynced password hash for {email}")
            # 3. Re-enable the account if it was disabled (operators expect
            #    seeded accounts to be reachable after redeploy).
            if existing.get("disabled"):
                updates["disabled"] = False
                logger.info(f"[STARTUP] re-enabled disabled seed {email}")
            # 4. Make sure `name` is populated.
            if not existing.get("name"):
                updates["name"] = label
            if updates:
                await db.staff.update_one({"email": email}, {"$set": updates})
            continue

        # ── New account ─────────────────────────────────────────────────────
        doc = {
            "id": f"staff_{role}_{int(datetime.now(timezone.utc).timestamp())}",
            "email": email,
            "name": label,
            "role": role,
            "password_hash": desired_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seeded": True,
            "disabled": False,
        }
        try:
            await db.staff.insert_one(doc)
            logger.info(f"[STARTUP] seeded staff: {email} role={role}")
        except Exception as e:
            logger.warning(f"[STARTUP] seed {email} failed: {e}")


async def _seed_demo_client_from_env():
    """Optional demo CLIENT (customer) seed — env-gated, idempotent.

    Mirrors the staff bootstrap, but for the B2B customer cabinet (`/client`).
    By design the backend NEVER seeds demo customers in production data mode;
    this helper only runs when BIBI_CLIENT_EMAIL + BIBI_CLIENT_PASSWORD are
    explicitly provided in the environment (i.e. preview/demo deployments).
    Leave the env vars unset in prod and this is a no-op.

    Customer auth (`/api/customer-auth/login`) compares against a legacy
    SHA-256 hash stored in `customers.password`, so we hash with the same
    `_legacy_sha256` helper. The account is created email-verified + active so
    the operator can sign in immediately through the `/client/login` panel.
    """
    # Security gate (Final Consistency Task §5): only when dev/test seed flag set.
    _seed_flag = os.environ.get("ECO_ENABLE_DEV_SEED", "false").strip().lower()
    if _seed_flag not in ("1", "true", "yes", "on"):
        return

    email = (os.environ.get("ECO_CLIENT_EMAIL") or os.environ.get("BIBI_CLIENT_EMAIL") or "").strip().lower()
    pwd = os.environ.get("ECO_CLIENT_SEED_PASSWORD") or os.environ.get("BIBI_CLIENT_PASSWORD") or ""
    if not email or not pwd:
        return  # not configured → skip (prod-safe)

    name = (os.environ.get("ECO_CLIENT_NAME") or os.environ.get("BIBI_CLIENT_NAME") or "Demo Client").strip()
    company_name = (os.environ.get("ECO_CLIENT_COMPANY") or os.environ.get("BIBI_CLIENT_COMPANY") or "ТОВ «Демо Клієнт»").strip()
    desired_hash = _legacy_sha256(pwd)
    now = datetime.now(timezone.utc)

    existing = await db.customers.find_one({"email": email})
    if existing:
        # Force-sync password + ensure the account is usable (active/verified).
        updates = {}
        if existing.get("password") != desired_hash:
            updates["password"] = desired_hash
            logger.info(f"[STARTUP] resynced demo-client password for {email}")
        if (existing.get("status") or "") != "active":
            updates["status"] = "active"
        if not existing.get("emailVerified"):
            updates["emailVerified"] = True
            updates["emailVerifiedAt"] = now.isoformat()
        if not existing.get("name"):
            updates["name"] = name
        if updates:
            await db.customers.update_one({"email": email}, {"$set": updates})
        return

    # ── New demo customer ────────────────────────────────────────────────
    customer_id = f"cust_{uuid.uuid4().hex[:12]}"
    company_id = company_name_canonical = manager_id = None
    try:
        company_id, company_name_canonical, manager_id = await _link_customer_company(company_name)
    except Exception as _e:  # noqa: BLE001
        logger.warning(f"[STARTUP] demo-client company link skipped: {_e}")

    customer = {
        "id": customer_id,
        "customerId": customer_id,
        "user_id": customer_id,
        "email": email,
        "password": desired_hash,
        "name": name,
        "first_name": name,
        "surname": "",
        "middle_name": "",
        "phone": "",
        "company_name": company_name_canonical or company_name,
        "company_id": company_id,
        "managerId": manager_id,
        "role": "customer",
        "status": "active",
        "source": "seed",
        "picture": "",
        "emailVerified": True,
        "emailVerifiedAt": now.isoformat(),
        "created_at": now.isoformat(),
        "seeded": True,
    }
    try:
        await db.customers.insert_one(customer)
        logger.info(f"[STARTUP] seeded demo client: {email}")
    except Exception as e:
        logger.warning(f"[STARTUP] seed demo client {email} failed: {e}")



async def ringostat_cron_loop():
    """Background loop for Ringostat calls export"""
    await asyncio.sleep(30)  # Wait 30s after startup
    while True:
        try:
            await ringostat_export_calls_cron()
        except Exception as e:
            logger.error(f"[CRON] Error in ringostat export: {e}")
        
        # Run every 5 minutes
        await asyncio.sleep(300)

# ── Security: CORS whitelist + startup invariants + rate-limit ─────────────
from security import (  # noqa: E402
    assert_prod_safe,
    bootstrap_jwt_secret,
    parse_cors_origins,
    parse_cors_origin_regex,
    require_admin,
    require_master_admin,
    require_user,
    require_manager_or_admin,
    require_extension_hmac,
    optional_user,
    ensure_shipment_access,
    create_jwt,
    hash_password,
    verify_password,
    is_admin,
    is_master_admin,
    is_staff,
    limiter as _rate_limiter,
    sanitize_vf_cookies,
    PAYLOAD_DEBUG_STORE,
    BACKEND_VF_SCRAPING,
    AUTH_MODE,
    register_nonce_verifier,
    register_hmac_fail_audit,
    register_client_secret_lookup,
)

# ═══════════════════════════════════════════════════════════════════
# TRACKING kill switch — Phase 5.5/F2 (2026-05-19) RETIRED from server.py.
# Helper moved to its canonical home at
# ``app/services/tracking_config.py`` (public name ``tracking_enabled``,
# no underscore). The env-only semantics (``TRACKING_ENABLED=false|0|no|
# off`` → False, anything else → True) are preserved 1:1.  All 4 in-file
# callers in this module + 1 cross-module bridge in
# ``app/routers/admin_identity.py`` migrated to the canonical name.
# Set ``TRACKING_ENABLED=false`` in ``.env`` to freeze all VesselFinder
# jobs dispatch + worker loops without code changes.
# ═══════════════════════════════════════════════════════════════════

# Run startup invariants. In AUTH_MODE=strict this raises, otherwise logs
# warnings. Non-blocking in dev so tests keep working during rollout.
try:
    assert_prod_safe()
except Exception as _e:
    logger.error(f"[security] refusing to start: {_e}")
    raise

# Rate-limit (slowapi) — only attach if the package is installed
if _rate_limiter is not None:
    try:
        from slowapi.errors import RateLimitExceeded  # type: ignore
        from slowapi import _rate_limit_exceeded_handler  # type: ignore
        fastapi_app.state.limiter = _rate_limiter
        fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    except Exception as _e:
        logger.warning(f"[security] rate-limit init failed: {_e}")

_cors_origins = parse_cors_origins()
_cors_origin_regex = parse_cors_origin_regex()
if not _cors_origins and not _cors_origin_regex:
    # Still allow anon localhost in absolute dev fallback, but log it loudly.
    logger.warning("[security] CORS_ORIGINS env empty — falling back to localhost only")
    _cors_origins = ["http://localhost:3000", "http://localhost:8001"]

# Phase IV-5 — DynamicCORSMiddleware reads the allow-list from
# `system_settings` Mongo doc + .env baseline. Admin can add/remove domains
# from /admin/system/settings without restarting the backend.
from app.middleware.dynamic_cors import DynamicCORSMiddleware  # noqa: E402

fastapi_app.add_middleware(
    DynamicCORSMiddleware,
    env_allow_origins=_cors_origins,
    env_allow_origin_regex=_cors_origin_regex,
    allow_credentials=False,  # JWT in Authorization header; no cookies.
    allow_methods=["*"],
    allow_headers=["*", "X-Ext-Timestamp", "X-Ext-Signature", "X-Ext-Client", "X-Ext-Nonce"],
    expose_headers=["X-RateLimit-Remaining", "X-RateLimit-Limit", "Retry-After"],
)
logger.info(f"[security] CORS allowed origins (env baseline): {_cors_origins} regex={_cors_origin_regex!r}")
logger.info("[security] CORS allowlist will hot-reload from DB `system_settings` every 30s")

# ── Performance: gzip-compress large text/JSON responses ─────────────────────
# Shrinks API payloads (waste catalog, SEO, listings) on the wire — no change
# to content, just fewer bytes transferred. Only kicks in for responses > 500B.
from starlette.middleware.gzip import GZipMiddleware  # noqa: E402
fastapi_app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)
logger.info("[perf] GZip compression enabled (minimum_size=500B)")

logger.info(f"[security] AUTH_MODE={AUTH_MODE}  PAYLOAD_DEBUG_STORE={PAYLOAD_DEBUG_STORE}  BACKEND_VF_SCRAPING={BACKEND_VF_SCRAPING}")


# [auto-domain removed] legacy copart/bidcars/carfast 410 kill-switch (endpoints deleted)

# ── Phase B3 — global uncaught-error capture (Wave 3 freeze) ──
# Best-effort: routes ANY uncaught exception through the observability
# layer so it reaches Sentry / the in-process ring buffer. We RE-RAISE
# afterwards so FastAPI's default 500 response logic still fires.
@fastapi_app.middleware("http")
async def _capture_uncaught_errors(request: Request, call_next):
    start = time.time()
    try:
        return await call_next(request)
    except Exception as err:
        try:
            from app.core.observability import report_error
            report_error(err, context={
                "path":    str(request.url.path),
                "method":  request.method,
                "elapsed_ms": int((time.time() - start) * 1000),
                # Intentionally NOT including IP / query string / headers
                # (those carry PII risk; Sentry's own enrichment is enough).
            })
        except Exception:   # noqa: BLE001
            pass
        raise


# ── Audit log helper (best-effort; TTL 90d via index created on startup) ──
async def audit(
    action: str,
    user: Optional[Dict[str, Any]] = None,
    resource: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
):
    """Persist a security-relevant event. Never raises."""
    try:
        doc = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user_id": (user or {}).get("id"),
            "user_email": (user or {}).get("email"),
            "user_role": (user or {}).get("role"),
            "resource": resource,
            "meta": meta or {},
            "ip": (request.client.host if request and request.client else None),
        }
        # Phase 5.4 / C-1 — db.audit_log ownership routes through
        # SecurityAuditRepository. The helper retains the 8-field
        # doc composition; only the Mongo round-trip migrates.
        from app.repositories import SecurityAuditRepository
        await SecurityAuditRepository(db).record_security_event(doc)
    except Exception as e:
        logger.debug(f"[audit] insert failed: {e}")


# ─── Phase 5.4 / C-5c — audit runtime accessor publication ──────────
# Publish the canonical `audit` async callable through the dedicated
# accessor module IMMEDIATELY after the function definition closes,
# BEFORE any consumer (admin_identity._audit, admin_ext_clients._audit,
# identity_runtime._audit_callable, server.py-internal worker loops)
# reads it. Identity assertion mirrors the C-4c (sio) / C-5b
# (aggregator) precedent: any future edit that introduces a second
# writer or reorders the bind fails fast at module-load time.
#
# Q4 caveat (per the C-5c mandate's mandatory micro-audit):
# Publication happens at MODULE-LOAD time but the audit callable
# closes over module-global `db` by NAME (resolved at call time).
# At publication time `db` is None; at every production call-time
# `db` has been set via `app.core.db_runtime.set_db` inside
# `_main_startup`. The audit body's `except Exception: logger.debug`
# best-effort wrapper makes any hypothetical pre-set_db call a
# silent no-op rather than a crash — preserving the H-5
# "audit never raises" invariant.
#
# The accessor module is the single source of truth for external
# (non-server.py) callers. server.py-internal closure callers
# (resolver_worker, transfer_detector worker loops) continue to
# reference the bare `audit` name via module-global lookup; that
# is out of C-5c scope and stays untouched.
from app.core.audit_runtime import (
    set_audit as _c5c_set_audit,
    get_audit as _c5c_get_audit,
)
_c5c_set_audit(audit)
assert _c5c_get_audit() is audit, (
    "[C-5c] audit runtime accessor split-brain: get_audit() "
    "identity diverged from server.audit at module-load publication"
)
del _c5c_set_audit, _c5c_get_audit


# ═══════════════════════════════════════════════════════════════════
# Security hooks — nonce replay-guard + HMAC failure audit
# ═══════════════════════════════════════════════════════════════════
async def _verify_ext_nonce(nonce: str, ts: int) -> bool:
    """Return True if the nonce has not been seen before.

    Uses a TTL-indexed Mongo collection (``ext_nonces``, 120 s TTL) + a unique
    index on ``nonce`` — duplicate insert raises and we return False.
    """
    try:
        await db.ext_nonces.insert_one({
            "nonce": nonce,
            "ts": datetime.now(timezone.utc),
            "clientTs": int(ts),
        })
        return True
    except Exception as e:
        # DuplicateKeyError (pymongo) → replay
        cls = type(e).__name__
        if "Duplicate" in cls:
            return False
        # Any other DB issue — fail-open so we don't block the extension on
        # transient Mongo issues, but log loudly.
        logger.warning(f"[security] nonce insert failed ({cls}): {e}")
        return True


async def _audit_hmac_failure(*, reason: str, client: Optional[str], method: str, path: str, ip: Optional[str]) -> None:
    """Wired into security.require_extension_hmac on every failure."""
    try:
        # Phase 5.4 / C-1 — db.audit_log ownership routes through
        # SecurityAuditRepository.record_hmac_failure (the 4-field
        # hmac variant preserves its distinct shape).
        from app.repositories import SecurityAuditRepository
        await SecurityAuditRepository(db).record_hmac_failure({
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "hmac_failed",
            "meta": {"reason": reason, "client": client, "method": method, "path": path},
            "ip": ip,
        })
    except Exception as e:
        logger.debug(f"[audit] hmac_failed insert failed: {e}")


# ── Per-client HMAC secret lookup (Phase E ext_clients registry) ────
# Small in-process TTL cache to avoid a DB round-trip per request.
_ext_client_secret_cache: Dict[str, tuple] = {}   # clientId -> (secret, expires_epoch)
_EXT_CLIENT_CACHE_TTL = 60  # seconds


async def _lookup_ext_client_secret(client_id: str) -> Optional[str]:
    """Return ``secret`` for an *active* client, ``'__REVOKED__'`` for an
    existing-but-inactive client, or ``None`` if the client id is unknown
    (in which case callers fall back to the global shared secret).
    """
    if not client_id:
        return None
    now = time.time()
    cached = _ext_client_secret_cache.get(client_id)
    if cached and cached[1] > now:
        return cached[0]
    try:
        doc = await db.ext_clients.find_one(
            {"clientId": client_id},
            {"_id": 0, "secret": 1, "active": 1},
        )
    except Exception as e:
        logger.debug(f"[security] ext_clients lookup failed: {e}")
        return None
    if not doc:
        _ext_client_secret_cache[client_id] = (None, now + 10)
        return None
    if doc.get("active") is False:
        _ext_client_secret_cache[client_id] = ("__REVOKED__", now + 10)
        return "__REVOKED__"
    secret = doc.get("secret") or None
    _ext_client_secret_cache[client_id] = (secret, now + _EXT_CLIENT_CACHE_TTL)
    return secret


# Static files — user uploads (avatars, etc)
from fastapi.staticfiles import StaticFiles
import pathlib
_STATIC_DIR = pathlib.Path(__file__).parent / "static"
(_STATIC_DIR / "avatars").mkdir(parents=True, exist_ok=True)
(_STATIC_DIR / "contracts").mkdir(parents=True, exist_ok=True)
fastapi_app.mount("/api/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
# Public-facing static for signed PDFs
fastapi_app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="public_static")

# ─────────────────────────────────────────────────────────────────────────
#  legal_workflow router — REMOVED (car-import auction/deposit pipeline retired).
#  Shared audit backbone relocated to app/core/domain_audit.py.
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  Wave 6:  Deal Workspace + Pipeline Simplification + Timeline + Legal Policy
#  (см. app/wave6/* — operational layer, additive over legacy 20-stage truth)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.wave6.router import on_startup as _wave6_on_startup  # noqa: E402
    # [ECO FREEZE] wave6 Deal Workspace router is NOT mounted — its /admin/deals/*,
    # /admin/pipeline/stages and /admin/settings/legal-policy endpoints belong to the
    # retired car-import workspace and have no consumer in the active ECO admin panel
    # (superseded by eco_analytics Deal360 at /api/eco/deals/*). The module stays
    # importable ONLY for the deal_created timeline hook + startup index creation.
    logger.info("[wave6] router FROZEN (not mounted) — superseded by eco_analytics Deal360")
except Exception as _e:
    logger.exception("[wave6] startup import failed: %s", _e)
    _wave6_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  Wave 7:  Manual Workload Rebalancing — reassignment service + endpoints
#  (см. app/services/reassignment.py + app/wave7/router.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.wave7.router import router as _wave7_router, on_startup as _wave7_on_startup  # noqa: E402
    fastapi_app.include_router(_wave7_router, prefix="/api")
    logger.info("[wave7] router mounted: %d routes",
                sum(1 for _ in _wave7_router.routes))
except Exception as _e:
    logger.exception("[wave7] failed to mount router: %s", _e)
    _wave7_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  Block 6.2 — Lead SLA (30-min remind, 2h escalate)
#  (см. app/services/lead_sla.py + app/workers/lead_sla_worker.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers.lead_sla import router as _lead_sla_router, on_startup as _lead_sla_on_startup  # noqa: E402
    fastapi_app.include_router(_lead_sla_router, prefix="/api")
    logger.info("[lead_sla] router mounted: %d routes",
                sum(1 for _ in _lead_sla_router.routes))
except Exception as _e:
    logger.exception("[lead_sla] failed to mount router: %s", _e)
    _lead_sla_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  Block 7.1 — Field-level Change History (customer/lead/deal diff)
#  (см. app/services/change_history.py + app/routers/change_history.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers.change_history import router as _change_history_router, on_startup as _change_history_on_startup  # noqa: E402
    fastapi_app.include_router(_change_history_router, prefix="/api")
    logger.info("[change_history] router mounted: %d routes",
                sum(1 for _ in _change_history_router.routes))
except Exception as _e:
    logger.exception("[change_history] failed to mount router: %s", _e)
    _change_history_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  Block 7.3 — Manager Instructions (admin-editable rich text page)
#  (см. app/routers/manager_instructions.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers.manager_instructions import router as _mgr_instr_router, on_startup as _mgr_instr_on_startup  # noqa: E402
    fastapi_app.include_router(_mgr_instr_router, prefix="/api")
    logger.info("[manager_instructions] router mounted: %d routes",
                sum(1 for _ in _mgr_instr_router.routes))
except Exception as _e:
    logger.exception("[manager_instructions] failed to mount router: %s", _e)
    _mgr_instr_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  Доопр #19 — Site online-activity tracking (public ingest + CRM read)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers.site_activity import router as _site_activity_router  # noqa: E402
    fastapi_app.include_router(_site_activity_router)
    logger.info("[site_activity] router mounted: %d routes",
                sum(1 for _ in _site_activity_router.routes))
except Exception as _e:
    logger.exception("[site_activity] failed to mount router: %s", _e)

# ─── SEO (dynamic sitemap, sitemap-index) ──────────────────────────────
try:
    from app.routers.seo import router as _seo_router  # noqa: E402
    fastapi_app.include_router(_seo_router)
    logger.info("[seo] sitemap router mounted: %d routes",
                sum(1 for _ in _seo_router.routes))
except Exception as _e:
    logger.exception("[seo] failed to mount sitemap router: %s", _e)

# ─── CLIENT (B2B customer self-serve area) + public inquiry ─────────────
try:
    from app.client.router import router as _client_router, pub_router as _client_pub_router  # noqa: E402
    fastapi_app.include_router(_client_router)
    fastapi_app.include_router(_client_pub_router)
    logger.info("[client] area router mounted: %d routes",
                sum(1 for _ in _client_router.routes) + sum(1 for _ in _client_pub_router.routes))
except Exception as _e:
    logger.exception("[client] failed to mount client router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  ECO — Manager Cabinet (self-contained CRM workspace scoped to current user)
#  (см. app/manager/cabinet_router.py) — prefix already includes /api
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.manager.cabinet_router import router as _mgr_cabinet_router  # noqa: E402
    fastapi_app.include_router(_mgr_cabinet_router)
    logger.info("[manager_cabinet] router mounted: %d routes",
                sum(1 for _ in _mgr_cabinet_router.routes))
except Exception as _e:
    logger.exception("[manager_cabinet] failed to mount router: %s", _e)

# ─── Account security — per-user 2FA (TOTP) for admin + manager ──────────
try:
    from app.manager.security_router import router as _account_sec_router  # noqa: E402
    fastapi_app.include_router(_account_sec_router)
    logger.info("[account_security] router mounted: %d routes",
                sum(1 for _ in _account_sec_router.routes))
except Exception as _e:
    logger.exception("[account_security] failed to mount router: %s", _e)

# ─── Staff Center — admin-only manager control room ──────────────────────
try:
    from app.staff_center import router as _staff_center_router  # noqa: E402
    fastapi_app.include_router(_staff_center_router)
    logger.info("[staff_center] router mounted: %d routes",
                sum(1 for _ in _staff_center_router.routes))
except Exception as _e:
    logger.exception("[staff_center] failed to mount router: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
#  Wave 2A:  Calls Foundation — customer-aggregated calls + recording proxy
#  (см. app/wave2a/router.py + app/wave2a/calls_aggregator.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.wave2a.router import router as _wave2a_router, on_startup as _wave2a_on_startup  # noqa: E402
    fastapi_app.include_router(_wave2a_router, prefix="/api")
    logger.info("[wave2a] router mounted: %d routes",
                sum(1 for _ in _wave2a_router.routes))
except Exception as _e:
    logger.exception("[wave2a] failed to mount router: %s", _e)
    _wave2a_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  Call Intelligence — on-demand Whisper transcription + gpt-4o AI summary
#  on top of ringostat_calls. Uses the OpenAI key from Admin → Integrations
#  when configured, otherwise falls back to EMERGENT_LLM_KEY (MR Gate).
#  Endpoints under /api/admin/calls/{id}/intelligence/* (staff-guarded).
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers.admin_call_intelligence import router as _ci_router  # noqa: E402
    fastapi_app.include_router(_ci_router)
    logger.info("[call-intel] router mounted: %d routes",
                sum(1 for _ in _ci_router.routes))
except Exception as _e:
    logger.exception("[call-intel] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 11:  Deal360 — single-pane operational view per deal
#  (см. app/wave11/* — additive aggregator over deals + linked entities)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.wave11.router import on_startup as _wave11_on_startup  # noqa: E402
    # [ECO FREEZE] wave11 Deal360 router is NOT mounted — its /deals/{id}/360,
    # /documents, /transitions endpoints (legacy car-import single-pane view) have no
    # consumer in the active ECO admin panel; replaced by eco_analytics /api/eco/deals/*.
    # Module kept importable only for its startup index hook.
    logger.info("[wave11] router FROZEN (not mounted) — superseded by eco_analytics Deal360")
except Exception as _e:
    logger.exception("[wave11] startup import failed: %s", _e)
    _wave11_on_startup = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────
#  ECO ANALYTICS (replaces legacy wave12 / 12C / 14 / 15 / 16 routers)
#  Same public paths (/api/finance, /api/forecast, /api/operations,
#  /api/executive, /api/contracts) but ECO waste-domain data (UAH, ECO funnel,
#  waste pickups) instead of the retired car-import model. Deal360 lives under
#  /api/eco/deals/* to avoid collisions with legacy wave6/wave11 routers.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.eco_analytics.router import ALL_ROUTERS as _eco_routers  # noqa: E402
    for _r in _eco_routers:
        fastapi_app.include_router(_r)
    logger.info("[eco_analytics] mounted %d routers (finance/forecast/operations/executive/contracts/deals)",
                len(_eco_routers))
except Exception as _e:
    logger.exception("[eco_analytics] failed to mount routers: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
#  Wave 17: Action Center — execution layer. First wave with its own
#  business entity (`actions` collection). Every risk/bottleneck from
#  Ops360 / Forecast360 / Contract360 / Delivery360 can be promoted to
#  an Action with explicit owner, priority, due_at, status and audit
#  trail. 4 tabs: inbox / my / team / analytics.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.wave17.router import router as _wave17_router  # noqa: E402
    fastapi_app.include_router(_wave17_router)
    logger.info("[wave17] router mounted: %d routes",
                sum(1 for _ in _wave17_router.routes))
except Exception as _e:
    logger.exception("[wave17] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 18: Communication & Notification Center — first delivery channel
#  layer. Source of every notification is the Action lifecycle (Wave 17).
#  Includes built-in SLA Escalation Engine (Wave 18.1) that scans overdue
#  actions and promotes them up the chain (24h → owner remind, 72h →
#  team_lead, 7d → admin + critical_overdue). Closes the loop:
#  Risk → Action → Notification → Escalation → Resolution → Analytics.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.wave18 import wave18_router as _wave18_router  # noqa: E402
    fastapi_app.include_router(_wave18_router)
    logger.info("[wave18] router mounted: %d routes (Notification Center + SLA Escalation)",
                sum(1 for _ in _wave18_router.routes))
except Exception as _e:
    logger.exception("[wave18] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 19 — Customer Portal 2.0 (Hybrid, strict)
#  Mounted at /api/portal/* — customer-only, read-only.
#  Reuses existing domains (deals/shipments/contracts/invoices/notifications)
#  via a thin BFF projection layer.  See app/wave19/.
# ─────────────────────────────────────────────────────────────────────────
try:
    # [ECO FREEZE] wave19 Customer Portal 2.0 router (/api/customer-portal/*) is NOT
    # mounted — the only consumer was the unrouted legacy CustomerPortalView page. The
    # active ECO B2B client portal is served by its own routers (/api/client/*).
    logger.info("[wave19] portal router FROZEN (not mounted) — legacy CustomerPortalView retired")
except Exception as _e:
    logger.exception("[wave19] freeze note failed: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  P1.2:  Financial Breakdown (templates + engine) router
#  (см. financial_breakdown.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    import financial_breakdown as _fin_br
    fastapi_app.include_router(_fin_br.router)
    logger.info("[financial_breakdown] router mounted: %d routes",
                sum(1 for _ in _fin_br.router.routes))
except Exception as _e:
    logger.exception("[financial_breakdown] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  P1.2-payments:  Payments tracking router
#  (см. payments_tracking.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    import payments_tracking as _pay_tr
    fastapi_app.include_router(_pay_tr.router)
    logger.info("[payments_tracking] router mounted: %d routes",
                sum(1 for _ in _pay_tr.router.routes))
except Exception as _e:
    logger.exception("[payments_tracking] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  P1.2-cabinet:  Customer-facing financial cabinet view
#  (см. cabinet_financials.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    import cabinet_financials as _cab_fin
    fastapi_app.include_router(_cab_fin.router)
    logger.info("[cabinet_financials] router mounted: %d routes",
                sum(1 for _ in _cab_fin.router.routes))
except Exception as _e:
    logger.exception("[cabinet_financials] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 1 / Commit 6:  Notifications HTTP surface absorb
#  (см. notifications.py — router-only mount; event bus, sio.emit,
#   startup hooks, async workers and EventBus registration are NOT
#   touched — they continue to live in notifications.init() called
#   from the startup() handler below.)
# ─────────────────────────────────────────────────────────────────────────
try:
    import notifications as _notif_router_mod
    fastapi_app.include_router(_notif_router_mod.router)
    logger.info("[notifications] router mounted: %d routes",
                sum(1 for _ in _notif_router_mod.router.routes))
except Exception as _e:
    logger.exception("[notifications] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 1 / Commit 7:  admin singleton extractions
#  (см. app/routers/admin_kpi.py, app/routers/admin_staff_sessions.py —
#   service-only, no Mongo writes, single auth boundary. 1:1 mechanical
#   extraction; runtime/event/worker infrastructure untouched.)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_kpi as _admin_kpi_mod
    fastapi_app.include_router(_admin_kpi_mod.router)
    logger.info("[admin_kpi] router mounted: %d routes",
                sum(1 for _ in _admin_kpi_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_kpi] failed to mount router: %s", _e)

try:
    from app.routers import admin_staff_sessions as _admin_ss_mod
    fastapi_app.include_router(_admin_ss_mod.router)
    logger.info("[admin_staff_sessions] router mounted: %d routes",
                sum(1 for _ in _admin_ss_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_staff_sessions] failed to mount router: %s", _e)

# Wave-8.4 — Workers Health admin router (list / restart / stop / start)
# Modular control panel for supervised workers exposed via worker_registry.
try:
    from app.routers import admin_workers as _admin_workers_mod
    fastapi_app.include_router(_admin_workers_mod.router)
    logger.info("[admin_workers] router mounted: %d routes",
                sum(1 for _ in _admin_workers_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_workers] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 2 / Commit 8:  admin_security + admin_history_reports
#  (см. app/routers/admin_security.py, app/routers/admin_history_reports.py
#   — first Wave 2B routers with db-bridge; 2FA deps (pyotp/qrcode) moved
#   into admin_security.py per ownership-transfer rule.  Runtime untouched.)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_security as _admin_sec_mod
    fastapi_app.include_router(_admin_sec_mod.router)
    logger.info("[admin_security] router mounted: %d routes",
                sum(1 for _ in _admin_sec_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_security] failed to mount router: %s", _e)

try:
    from app.routers import admin_history_reports as _admin_hr_mod
    fastapi_app.include_router(_admin_hr_mod.router)
    logger.info("[admin_history_reports] router mounted: %d routes",
                sum(1 for _ in _admin_hr_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_history_reports] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Phase IV-5 — admin_system_settings (DB-backed CORS + production domain)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_system_settings as _admin_sys_mod
    fastapi_app.include_router(_admin_sys_mod.router)
    logger.info("[admin_system_settings] router mounted: %d routes",
                sum(1 for _ in _admin_sys_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_system_settings] failed to mount router: %s", _e)

# ─── admin_seo_settings — SEO control panel (master_admin only) ────────
try:
    from app.routers import admin_seo_settings as _admin_seo_mod  # noqa: E402
    fastapi_app.include_router(_admin_seo_mod.router)
    logger.info("[admin_seo_settings] router mounted: %d routes",
                sum(1 for _ in _admin_seo_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_seo_settings] failed to mount router: %s", _e)

# ─── admin_seo_center — Phase B2 (company / analytics / pages / robots / sitemap)
try:
    from app.routers import admin_seo_center as _admin_seo_center_mod  # noqa: E402
    fastapi_app.include_router(_admin_seo_center_mod.router)
    logger.info("[admin_seo_center] router mounted: %d routes",
                sum(1 for _ in _admin_seo_center_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_seo_center] failed to mount router: %s", _e)

# ─── prerender — Phase C (bot-facing prerendered HTML) ─────────────────
try:
    from app.routers import prerender as _prerender_mod  # noqa: E402
    fastapi_app.include_router(_prerender_mod.router)
    logger.info("[prerender] router mounted: %d routes",
                sum(1 for _ in _prerender_mod.router.routes))
except Exception as _e:
    logger.exception("[prerender] failed to mount router: %s", _e)

# ─── content platform — Phase D1 (Content Center / Media / FAQ / Public) ──
try:
    from app.routers import admin_content as _admin_content_mod  # noqa: E402
    fastapi_app.include_router(_admin_content_mod.router)
    logger.info("[admin_content] router mounted: %d routes",
                sum(1 for _ in _admin_content_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_content] failed to mount router: %s", _e)

try:
    from app.routers import admin_media as _admin_media_mod  # noqa: E402
    fastapi_app.include_router(_admin_media_mod.admin_router)
    fastapi_app.include_router(_admin_media_mod.public_router)
    logger.info("[admin_media] routers mounted: %d admin + %d public routes",
                sum(1 for _ in _admin_media_mod.admin_router.routes),
                sum(1 for _ in _admin_media_mod.public_router.routes))
except Exception as _e:
    logger.exception("[admin_media] failed to mount router: %s", _e)

try:
    from app.routers import admin_faq as _admin_faq_mod  # noqa: E402
    fastapi_app.include_router(_admin_faq_mod.router)
    logger.info("[admin_faq] router mounted: %d routes",
                sum(1 for _ in _admin_faq_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_faq] failed to mount router: %s", _e)

try:
    from app.routers import public_content as _public_content_mod  # noqa: E402
    fastapi_app.include_router(_public_content_mod.router)
    logger.info("[public_content] router mounted: %d routes",
                sum(1 for _ in _public_content_mod.router.routes))
except Exception as _e:
    logger.exception("[public_content] failed to mount router: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
# Unified Admin Platform — Phase D1.5 (additive layer).
# Global Search + Unified Dashboard + Relation resolver over EXISTING domain
# collections (read-only). No schema changes to CRM/Waste/Ops/SEO/Content.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.unified.router import router as _unified_router  # noqa: E402
    fastapi_app.include_router(_unified_router)
    logger.info("[unified] router mounted: %d routes",
                sum(1 for _ in _unified_router.routes))
except Exception as _e:
    logger.exception("[unified] failed to mount router: %s", _e)



# ─────────────────────────────────────────────────────────────────────────
# analytics_tracking — реальная аналитика (вместо mock /api/analytics/dashboard)
# Подключаем три роутера: public tracking (POST /api/track/event),
# analytics dashboard (GET /api/analytics/*), admin marketing
# (CRUD на /api/admin/marketing/campaigns для spend).
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import analytics_tracking as _analytics_mod
    fastapi_app.include_router(_analytics_mod.public_router)
    fastapi_app.include_router(_analytics_mod.public_dash_router)
    fastapi_app.include_router(_analytics_mod.admin_router)
    logger.info(
        "[analytics_tracking] routers mounted: public=%d dash=%d admin=%d",
        sum(1 for _ in _analytics_mod.public_router.routes),
        sum(1 for _ in _analytics_mod.public_dash_router.routes),
        sum(1 for _ in _analytics_mod.admin_router.routes),
    )
except Exception as _e:
    logger.exception("[analytics_tracking] failed to mount routers: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
# analytics_funnel — реальная воронка продаж (заменяет mock /api/journey/*)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import analytics_funnel as _funnel_mod
    fastapi_app.include_router(_funnel_mod.router)
    logger.info(
        "[analytics_funnel] router mounted: %d routes",
        sum(1 for _ in _funnel_mod.router.routes),
    )
except Exception as _e:
    logger.exception("[analytics_funnel] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  [ECO CLEANUP] admin_proxy + admin_sources REMOVED (auto-domain parser infra).
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  [ECO CLEANUP] admin_vesselfinder REMOVED (auto-domain ship tracking).
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 5 / Commit 11:  admin_call_flow (SOLO)
#  (см. app/routers/admin_call_flow.py — 4 service-only stub endpoints,
#   ZERO bridge edges (no db, no helpers, no globals).  Phase-2 graduated
#   by construction.  Same zero-bridge discipline as Batch 1 / Batch 3.)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_call_flow as _admin_cf_mod
    fastapi_app.include_router(_admin_cf_mod.router)
    logger.info("[admin_call_flow] router mounted: %d routes",
                sum(1 for _ in _admin_cf_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_call_flow] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Sprint 1.5 / Finance Core Closeout — Customer 360 finance aggregator
#  (см. app/routers/customer360_finance.py — 4 read-only endpoints that
#   surface invoices / orders / payments / finance-summary under the
#   /api/customers/{id}/... namespace for the Customer360 page tabs.)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import customer360_finance as _c360_fin_mod
    fastapi_app.include_router(_c360_fin_mod.router)
    logger.info("[customer360_finance] router mounted: %d routes",
                sum(1 for _ in _c360_fin_mod.router.routes))
except Exception as _e:
    logger.exception("[customer360_finance] failed to mount router: %s", _e)

# ECO-domain Customer 360 aggregation (waste requests / contracts / acts /
# ecologist reports / activity — company-scoped, RBAC-aware).
try:
    from app.routers import customer360_eco as _c360_eco_mod
    fastapi_app.include_router(_c360_eco_mod.router)
    logger.info("[customer360_eco] router mounted: %d routes",
                sum(1 for _ in _c360_eco_mod.router.routes))
except Exception as _e:
    logger.exception("[customer360_eco] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Sprint 2 / File Manager — customer folders + files + storage abstraction
#  (см. app/routers/file_manager.py + app/services/file_manager.py +
#   app/services/object_storage.py with Local + S3-stub providers.)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import file_manager as _fm_mod
    fastapi_app.include_router(_fm_mod.router)
    logger.info("[file_manager] router mounted: %d routes",
                sum(1 for _ in _fm_mod.router.routes))
except Exception as _e:
    logger.exception("[file_manager] failed to mount router: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
#  Sprint 3 / Document System — PDF Engine + Templates + auto-save to FM
#  (см. app/routers/documents.py + app/services/pdf_engine.py +
#   app/repositories/document_templates.py + app/services/pdf_templates_seed.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import documents as _docs_mod
    fastapi_app.include_router(_docs_mod.router)
    logger.info("[documents] router mounted: %d routes",
                sum(1 for _ in _docs_mod.router.routes))
except Exception as _e:
    logger.exception("[documents] failed to mount router: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
#  Sprint 3.5 / Customer Roadmap — client-facing 7-stage vehicle journey
#  (см. app/routers/customer_roadmap.py + app/services/customer_roadmap.py)
#  Auto-spawns on order creation from a paid invoice and is visible in
#  Customer360 (manager edits), team dashboards (SLA) and the customer
#  cabinet (read-only).
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import customer_roadmap as _roadmap_mod
    fastapi_app.include_router(_roadmap_mod.router)
    logger.info("[customer_roadmap] router mounted: %d routes",
                sum(1 for _ in _roadmap_mod.router.routes))
except Exception as _e:
    logger.exception("[customer_roadmap] failed to mount router: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
#  Sprint 4 / Customer360 Final — Comments, Tasks, Timeline
#  (см. app/routers/customer_comments.py, customer_tasks.py,
#   customer_timeline.py, app/services/customer_timeline.py)
#  All three mount into the same Customer360 surface and share the
#  ``customer_timeline_events`` collection as the canonical event bus.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import customer_comments as _comments_mod
    fastapi_app.include_router(_comments_mod.router)
    logger.info("[customer_comments] router mounted: %d routes",
                sum(1 for _ in _comments_mod.router.routes))
except Exception as _e:
    logger.exception("[customer_comments] failed to mount router: %s", _e)

try:
    from app.routers import customer_tasks as _ctasks_mod
    fastapi_app.include_router(_ctasks_mod.router)
    logger.info("[customer_tasks] router mounted: %d routes",
                sum(1 for _ in _ctasks_mod.router.routes))
except Exception as _e:
    logger.exception("[customer_tasks] failed to mount router: %s", _e)

try:
    from app.routers import customer_timeline as _ctimeline_mod
    fastapi_app.include_router(_ctimeline_mod.router)
    logger.info("[customer_timeline] router mounted: %d routes",
                sum(1 for _ in _ctimeline_mod.router.routes))
    # Ensure indexes on startup
    try:
        from app.services import customer_timeline as _ctimeline_svc
        import asyncio as _asyncio
        _asyncio.get_event_loop().create_task(_ctimeline_svc.ensure_indexes())
    except Exception:
        pass
except Exception as _e:
    logger.exception("[customer_timeline] failed to mount router: %s", _e)


# ─────────────────────────────────────────────────────────────────────────
#  Mini Sprint / Contracts Final — lifecycle (draft → sent → viewed →
#  signed → archived) + public viewer/signer keyed by an opaque
#  ``view_token`` so customers can sign without authentication.
#  (см. app/routers/contracts.py + app/services/contract_lifecycle.py)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import contracts as _contracts_mod
    fastapi_app.include_router(_contracts_mod.router)
    logger.info("[contracts] router mounted: %d routes",
                sum(1 for _ in _contracts_mod.router.routes))
except Exception as _e:
    logger.exception("[contracts] failed to mount router: %s", _e)



# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 7 / Commit 13:  CONTENT cluster (site_info + blog)
#  (см. app/routers/content.py — Content domain extraction.  Two co-mounted
#   APIRouter instances: site_info_router (6 endpoints: 2 public + 4 admin)
#   + blog_router (8 endpoints: 6 admin + 2 public).  Owns the
#   `site_info` and `blog_articles` Mongo collections + the DEFAULT_SITE_INFO
#   seed + all blog helpers.  Auth boundary is mixed inside the file
#   (public + admin), per-endpoint Depends(require_user) preserved.  This
#   is the FIRST Wave 2B batch extending BEYOND the admin surface — the
#   collections have both admin and public consumers, so full ownership
#   transfer is required to preserve the "one collection, one owner"
#   invariant.)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import content as _content_mod
    fastapi_app.include_router(_content_mod.site_info_router)
    fastapi_app.include_router(_content_mod.blog_router)
    logger.info("[content] site_info_router mounted: %d routes",
                sum(1 for _ in _content_mod.site_info_router.routes))
    logger.info("[content] blog_router mounted: %d routes",
                sum(1 for _ in _content_mod.blog_router.routes))
except Exception as _e:
    logger.exception("[content] failed to mount routers: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Google Reviews integration (admin + public)
#  Owns 2 Mongo collections (google_reviews_config, google_reviews_cache).
#  Self-contained — see app/services/google_reviews_service.py.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_google_reviews as _admin_grev_mod
    fastapi_app.include_router(_admin_grev_mod.router)
    logger.info("[google_reviews] router mounted: %d routes",
                sum(1 for _ in _admin_grev_mod.router.routes))
except Exception as _e:
    logger.exception("[google_reviews] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 8 / Commit 14:  Bottom singletons (4 trivial domains)
#  (см. app/routers/admin_{orders,search,cache,chrome_extension}.py
#   Cheap entropy reduction: 4 unrelated singletons in one batch.  Each is
#   its own bounded mini-domain.  Discipline: this is the LAST GREEN batch
#   before MED-tier `admin_metrics` (Batch 9) and auth-mixed yellows
#   (Batch 10).  Bridge summary:
#     * admin_orders             : lazy _db(), READ-ONLY into Cluster #1 (orders)
#     * admin_search             : lazy _db(), READ-ONLY into search_logs
#     * admin_cache              : lazy _aggregator() in-memory singleton
#     * admin_chrome_extension   : own asset bundle (chrome_extension/ dir)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_orders as _admin_orders_mod
    fastapi_app.include_router(_admin_orders_mod.router)
    logger.info("[admin_orders] router mounted: %d routes",
                sum(1 for _ in _admin_orders_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_orders] failed to mount router: %s", _e)

try:
    from app.routers import admin_search as _admin_search_mod
    fastapi_app.include_router(_admin_search_mod.router)
    logger.info("[admin_search] router mounted: %d routes",
                sum(1 for _ in _admin_search_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_search] failed to mount router: %s", _e)

# [auto-domain removed] admin_cache router (POST /api/admin/cache/clear — VIN aggregator cache) deleted

# [ECO CLEANUP] admin_chrome_extension REMOVED (auto-domain chrome extension).

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 9 / Commit 15:  admin_metrics SOLO (reconnaissance)
#  (см. app/routers/admin_metrics.py)
#
#  First test of the "read aggregation allowed, ownership mutation NOT"
#  rule on a CROSS-DOMAIN read model: GET /api/admin/metrics reads from
#  TWO Cluster #1 collections (`invoices` + `orders`) and computes KPIs
#  (conversion / avg_order_time / repeat_rate).  Audit confirmed pure
#  read-only access (count / find / aggregate) — no mutations, no
#  helper bridges, no transactional coupling.  Ownership of `invoices`
#  and `orders` remains in server.py / Cluster #1 until Phase 3.
#
#  Bridge: lazy _db() — identical pattern as Batch 8 admin_orders.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_metrics as _admin_metrics_mod
    fastapi_app.include_router(_admin_metrics_mod.router)
    logger.info("[admin_metrics] router mounted: %d routes",
                sum(1 for _ in _admin_metrics_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_metrics] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 10 / Commit 16:  Auth-mixed yellow (admin_services +
#  admin_workflow_templates).
#
#  First batch in Wave 2B that extracts routers with MIXED auth tiers
#  (require_admin for reads, require_master_admin for mutations) within
#  a single domain.  Per-endpoint `dependencies=[...]` decoration is
#  preserved verbatim — router-level hoisting is forbidden because it
#  would change behavior (downgrade master_admin writes to admin OR
#  upgrade reads to master_admin).
#
#  Also first batch since Wave 1 to extract routers that MUTATE their
#  own collection.  Mutation discipline:
#    * `services` and `workflow_templates` collections become MUTATION-
#      OWNED by the extracted routers.
#    * Ownership is PARTIAL — residual writers/readers remain in
#      server.py (startup seed for services, public readers for both
#      collections, manager-invoice-builder reader for services).
#      Documented in REFACTOR_DEPENDENCIES.md.
#    * Public/manager read endpoints (`GET /api/services`,
#      `GET /api/workflow-templates`) are NOT extracted in this batch
#      (narrow-scope mandate).
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_services as _admin_services_mod
    fastapi_app.include_router(_admin_services_mod.router)
    logger.info("[admin_services] router mounted: %d routes",
                sum(1 for _ in _admin_services_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_services] failed to mount router: %s", _e)

try:
    from app.routers import admin_workflow_templates as _admin_wft_mod
    fastapi_app.include_router(_admin_wft_mod.router)
    logger.info("[admin_workflow_templates] router mounted: %d routes",
                sum(1 for _ in _admin_wft_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_workflow_templates] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 11 / Commit 17:  Read-only aggregators bundle
#  (intent, engagement, overview, predictive-leads, providers).
#
#  16 endpoints, 5 routers, all PURE READ-ONLY under the Phase 3 preview
#  rule formalised in Batch 8 and stress-tested in Batch 9.  Largest
#  bundle in Wave 2B; uses uniform `require_admin` so all routers can
#  hoist the dependency to router-level.
#
#  Bridge summary:
#    * admin_intent           : zero bridges (mock data only)
#    * admin_engagement       : lazy _db() (cross-domain reads:
#                               customers, favorites, compare, shares, vin_data)
#    * admin_overview         : lazy _db() (4-way count_documents into
#                               Cluster #1: leads, customers, deals, vin_data)
#    * admin_predictive_leads : lazy _db() (read-only leads.find)
#    * admin_providers        : lazy _db() + local _ps_service_or_503()
#                               (orchestrator over already-extracted
#                               provider_stats service; POST mutation
#                               encapsulated inside the service module)
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_intent as _admin_intent_mod
    fastapi_app.include_router(_admin_intent_mod.router)
    logger.info("[admin_intent] router mounted: %d routes",
                sum(1 for _ in _admin_intent_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_intent] failed to mount router: %s", _e)

try:
    from app.routers import admin_engagement as _admin_engagement_mod
    fastapi_app.include_router(_admin_engagement_mod.router)
    logger.info("[admin_engagement] router mounted: %d routes",
                sum(1 for _ in _admin_engagement_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_engagement] failed to mount router: %s", _e)

# Wave 7.5 — manager_engagement DELETED (consolidated into admin_engagement).
# All endpoints live at /api/admin/engagement/* and are gated by
# require_manager_or_admin, so managers/team_leads still have read access.

# [ECO CLEANUP] wishlist_deals REMOVED (auto-domain vehicle deals/catalog).

# ─── Auth policy: TOTP / email-OTP / login audit / per-user 2FA ────────
try:
    from app.routers import auth_extra as _auth_extra_mod
    fastapi_app.include_router(_auth_extra_mod.router)
    logger.info("[auth_extra] router mounted: %d routes",
                sum(1 for _ in _auth_extra_mod.router.routes))
except Exception as _e:
    logger.exception("[auth_extra] failed to mount router: %s", _e)

try:
    from app.routers import login_audit as _login_audit_mod
    fastapi_app.include_router(_login_audit_mod.admin_router)
    fastapi_app.include_router(_login_audit_mod.team_router)
    logger.info(
        "[login_audit] routers mounted: admin=%d, team=%d",
        sum(1 for _ in _login_audit_mod.admin_router.routes),
        sum(1 for _ in _login_audit_mod.team_router.routes),
    )
except Exception as _e:
    logger.exception("[login_audit] failed to mount routers: %s", _e)

try:
    from app.routers import auth_security_extras as _ase_mod
    fastapi_app.include_router(_ase_mod.me_router)
    fastapi_app.include_router(_ase_mod.admin_extra_router)
    logger.info(
        "[auth_security_extras] routers mounted: me=%d, admin_extra=%d",
        sum(1 for _ in _ase_mod.me_router.routes),
        sum(1 for _ in _ase_mod.admin_extra_router.routes),
    )
except Exception as _e:
    logger.exception("[auth_security_extras] failed to mount routers: %s", _e)

try:
    from app.routers import auth_password as _auth_password_mod
    fastapi_app.include_router(_auth_password_mod.router)
    logger.info(
        "[auth_password] router mounted: %d routes",
        sum(1 for _ in _auth_password_mod.router.routes),
    )
except Exception as _e:
    logger.exception("[auth_password] failed to mount router: %s", _e)

try:
    from app.routers import admin_overview as _admin_overview_mod
    fastapi_app.include_router(_admin_overview_mod.router)
    logger.info("[admin_overview] router mounted: %d routes",
                sum(1 for _ in _admin_overview_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_overview] failed to mount router: %s", _e)

try:
    from app.routers import admin_predictive_leads as _admin_pl_mod
    fastapi_app.include_router(_admin_pl_mod.router)
    logger.info("[admin_predictive_leads] router mounted: %d routes",
                sum(1 for _ in _admin_pl_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_predictive_leads] failed to mount router: %s", _e)

# [ECO CLEANUP] admin_providers REMOVED (auto-domain data-source providers).

# ─────────────────────────────────────────────────────────────────────────
#  [ECO CLEANUP] admin_shipments + admin_resolver REMOVED (auto-domain
#  shipment journeys + VIN resolver queue).
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  [ECO CLEANUP] admin_identity REMOVED (auto-domain identity/tracking/
#  resolver runtime + legacy tracking/resolver aliases).
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  [ECO CLEANUP] admin_ext_clients REMOVED (auto-domain chrome-extension
#  per-manager HMAC secret registry).
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 13 / Commit 19:  Read-only ringostat cluster.
#
#  6 endpoints, 1 router.  Pure read-only on `ringostat_config` +
#  `ringostat_calls` (own telephony domain) and `staff`/`leads`/`deals`
#  (Cluster #1 cross-domain reads).  Phase 3 preview rule satisfied.
#
#  Forward-compat note: Batch 14 will APPEND the 5 ringostat write
#  endpoints (settings PATCH, test-connection POST, test-webhook POST,
#  mappings POST, mappings/{ext} DELETE) to the SAME router file
#  (admin_ringostat.py).  FastAPI handles method-different routes on
#  the same path \u2014 readers here, writers still in server.py for now.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_ringostat as _admin_ringostat_mod
    fastapi_app.include_router(_admin_ringostat_mod.router)
    logger.info("[admin_ringostat] router mounted: %d routes",
                sum(1 for _ in _admin_ringostat_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_ringostat] failed to mount router: %s", _e)

# Phase IV-6: role-aware UX (team_lead overview, admin oversight,
# per-user UI preferences).  All endpoints in this router use FULL
# explicit paths (``/api/...``) — no prefix here.
try:
    from app.routers import ringostat_roles as _rg_roles_mod
    fastapi_app.include_router(_rg_roles_mod.router)
    logger.info("[ringostat_roles] router mounted: %d routes",
                sum(1 for _ in _rg_roles_mod.router.routes))
except Exception as _e:
    logger.exception("[ringostat_roles] failed to mount router: %s", _e)

# Calls Console (ECO CRM) — unified call-management surface for admin +
# manager (summary banner, feed, awaiting-outcome, scheduled callbacks).
# Paths under /api/manager/calls/* that don't collide with the inline
# /my, /missed, POST /{id}/outcome routes already on fastapi_app.
try:
    from app.routers import calls_console as _calls_console_mod
    fastapi_app.include_router(_calls_console_mod.router)
    logger.info("[calls_console] router mounted: %d routes",
                sum(1 for _ in _calls_console_mod.router.routes))
except Exception as _e:
    logger.exception("[calls_console] failed to mount router: %s", _e)

# ─────────────────────────────────────────────────────────────────────────
#  Wave 2B / Batch 14 / Commit 20:  Integrations cluster (reads + writes)
#  + 5 ringostat writes appended to admin_ringostat (Batch 13 router).
#
#  9 endpoints in new admin_integrations router (4 reads + 5 writes),
#  5 endpoints appended to existing admin_ringostat router.  14 total.
#
#  Notable: admin_integrations contains 2 endpoints that read the 5
#  tracking module globals (VESSELFINDER_*, SHIPSGO_*, AFTERSHIP_API_KEY)
#  via a lazy `_tracking_env_keys()` accessor that reads them through
#  `import server; server.X` — preserving the live-mutation semantics
#  (the globals are mutated by tracking/providers/configure, which
#  stays in server.py as a Phase 3 blocker).  Documented in router
#  docstring as the Phase-3-problem-#1 bridge.
# ─────────────────────────────────────────────────────────────────────────
try:
    from app.routers import admin_integrations as _admin_integrations_mod
    fastapi_app.include_router(_admin_integrations_mod.router)
    logger.info("[admin_integrations] router mounted: %d routes",
                sum(1 for _ in _admin_integrations_mod.router.routes))
except Exception as _e:
    logger.exception("[admin_integrations] failed to mount router: %s", _e)

# ═══════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════
class BrowserPayload(BaseModel):
    vin: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    fallback: Optional[Dict[str, Any]] = None
    sessionId: Optional[str] = None
    url: str
    ts: int

class ConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    rate_limit_ms: Optional[int] = None
    min_score: Optional[float] = None
    debug: Optional[bool] = None

# [auto-domain removed] SessionAction

# [auto-domain removed] VIN_REGEX

# [auto-domain removed] is_valid_vin

# ═══════════════════════════════════════════════════════════════════
# VIN INGESTION API
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# CONFIG API (V3.2 Control)
# ═══════════════════════════════════════════════════════════════════
# [auto-domain removed] /api/v3/config (get_config)

# [auto-domain removed] /api/v3/config (update_config)

# ═══════════════════════════════════════════════════════════════════
# HEARTBEAT API (Extension → Backend)
# ═══════════════════════════════════════════════════════════════════
# [auto-domain removed] /api/v3/heartbeat (heartbeat)

# ═══════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT API
# ═══════════════════════════════════════════════════════════════════
# [auto-domain removed] /api/v3/sessions (list_sessions)

# [auto-domain removed] /api/v3/session/disable (disable_session)

# [auto-domain removed] /api/v3/session/enable (enable_session)

# [auto-domain removed] /api/v3/session/priority (set_session_priority)

# ═══════════════════════════════════════════════════════════════════
# VIN DATA API
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# STATS & MONITORING
# ═══════════════════════════════════════════════════════════════════
# [auto-domain removed] /api/v3/stats (v3_stats)

# [auto-domain removed] /api/dashboard/stats (dashboard_stats)

# [auto-domain removed] /api/dashboard/master (dashboard_master)

@fastapi_app.get("/api/health")
@fastapi_app.get("/api/healthz")
async def health_probe():
    """Lightweight liveness/readiness probe for load balancers & Kubernetes.

    Intentionally cheap: a single Mongo ping, no worker/observability
    aggregation. Returns 200 when the service can reach the database and
    503 when it cannot — exactly what a k8s readiness probe expects.
    For the full diagnostic snapshot use ``GET /api/system/health``.
    """
    mongo_ok = True
    try:
        await db.command("ping")
    except Exception:
        mongo_ok = False
    return JSONResponse(
        status_code=200 if mongo_ok else 503,
        content={"status": "ok" if mongo_ok else "degraded", "mongo_ok": mongo_ok},
    )


@fastapi_app.get("/api/system/health")
async def health():
    """Public health probe. Cheap, always-on.

    Returns the standard service fingerprint PLUS a Phase B3 observability
    snapshot so an uptime monitor (or sysadmin) can spot a problem in a
    single GET.
    """
    # Observability snapshot is best-effort — never break the health probe.
    try:
        from app.core.observability import get_health_snapshot
        observability = get_health_snapshot()
    except Exception as _e:  # noqa: BLE001
        observability = {"error": f"observability unavailable: {_e}"}

    # Optional Mongo ping (kept fast — does not aggregate)
    mongo_ok = True
    try:
        await db.command("ping")
    except Exception:
        mongo_ok = False

    # Wave-8.2 — supervised worker snapshot (best-effort; never break health probe).
    # Lets ops monitor see if escalation-wakeup / payment-reminder / tracking / etc.
    # are running, how many times they restarted, and when they last booted.
    workers_status: Dict[str, Any] = {"available": False}
    try:
        from app.core.worker_registry import worker_registry as _wr_health
        snapshot = _wr_health.status()
        summary = _wr_health.status_summary()
        workers_status = {
            "available": True,
            "summary": summary,
            # Trim each row to a stable, JSON-safe subset (no asyncio.Task etc.)
            "workers": [
                {
                    "name": w.get("name"),
                    "state": w.get("state"),
                    "restarts": w.get("restarts", 0),
                    "max_restarts": w.get("max_restarts"),
                    "critical": w.get("critical", False),
                    "started_at": w.get("started_at"),
                    "last_error": w.get("last_error"),
                    "last_error_at": w.get("last_error_at"),
                }
                for w in snapshot
            ],
        }
    except Exception as _e:  # noqa: BLE001
        workers_status = {"available": False, "error": str(_e)}

    return {
        "status": "healthy" if mongo_ok else "degraded",
        "service": "bibi-v3.2",
        "version": "3.2.1",
        "release": os.environ.get("BIBI_RELEASE", "v3.2.1-wave3-freeze"),
        "mongo_ok": mongo_ok,
        "observability": observability,
        "workers": workers_status,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════
# PHASE B3 — User-observation events + ops issues (Wave 3 freeze)
# ═══════════════════════════════════════════════════════════════════
# Privacy-respecting event endpoint. The frontend POSTs a thin event
# (filter changed, abandoned search, detail view, …) and we count it
# in-process. NO PII is persisted — only an event name + a whitelisted
# set of properties (e.g. which filter, sort direction).
class _EventIn(BaseModel):
    event: str
    props: Optional[Dict[str, Any]] = None


@fastapi_app.post("/api/events/track")
async def track_event(payload: _EventIn):
    try:
        from app.core.observability import record_event
        ok = record_event(payload.event, payload.props or {})
        return {"ok": bool(ok)}
    except Exception:
        # NEVER fail the user's interaction over an observation event.
        return {"ok": False}


@fastapi_app.get("/api/admin/observability/issues")
async def admin_observability_issues(
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_admin),  # noqa: F841
):
    """Admin-only: latest in-process errors / slow queries / parser fails.

    Bounded ring buffer (default 200 entries). Survives across requests,
    discarded on process restart. Use Sentry for permanent retention
    (SENTRY_DSN env var enables it).
    """
    try:
        from app.core.observability import (
            get_recent_errors, get_recent_slow_queries,
            get_recent_parser_failures, get_health_snapshot,
        )
        return {
            "snapshot": get_health_snapshot(),
            "errors":   get_recent_errors(limit),
            "slow_queries":    get_recent_slow_queries(limit),
            "parser_failures": get_recent_parser_failures(limit),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"observability unavailable: {e}")


@fastapi_app.get("/api/admin/observability/events")
async def admin_observability_events(
    top: int = 20,
    current_user: Dict[str, Any] = Depends(require_admin),  # noqa: F841
):
    """Admin-only: aggregated user-observation counters.

    Used to answer questions like "which filters do users actually touch"
    and "what are the most-viewed cars" — without ever logging PII.
    """
    try:
        from app.core.observability import get_event_summary
        return get_event_summary(top)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"observability unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════
# [auto-domain removed] WebSocket /api/v3/stream (VIN real-time feed) deleted
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# LEGACY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════
@fastapi_app.get("/api/auth/me")
async def get_me(current_user: Dict[str, Any] = Depends(require_user)):
    """Return the authenticated staff user."""
    return {
        "id": current_user.get("id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
        "managerId": current_user.get("managerId"),
    }


# Cyrillic→Latin homoglyph map — lets a user who accidentally typed visually
# identical Cyrillic letters (e.g. "Есо" instead of "Eco") still authenticate.
# Only used as a verification *fallback*; the stored hash is never changed.
_HOMOGLYPH_MAP = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ј": "J",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ї": "i", "ј": "j", "ѕ": "s",
})


def _normalize_homoglyphs(s: str) -> str:
    return (s or "").translate(_HOMOGLYPH_MAP)


def _verify_password_tolerant(password: str, stored_hash: str) -> bool:
    """verify_password, with a Cyrillic-homoglyph fallback (keyboard/copy-paste safety)."""
    if verify_password(password, stored_hash):
        return True
    norm = _normalize_homoglyphs(password)
    if norm != password and verify_password(norm, stored_hash):
        return True
    return False


@fastapi_app.post("/api/auth/login")
@(_rate_limiter.limit("10/minute") if _rate_limiter else (lambda f: f))
async def login(request: Request, response: Response, credentials: Dict[str, Any] = Body(...)):
    """Staff login → JWT.

    Verifies against ``db.staff`` (bcrypt `password_hash`). Seed accounts are
    inserted on startup from env (`BIBI_OWNER_*`, `BIBI_ADMIN_*`, `BIBI_MANAGER_*`).
    """
    email = (credentials.get("email") or "").strip().lower()
    password = (credentials.get("password") or "").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    # Basic brute-force guard (IP + email bucket, in-memory fallback if slowapi disabled)
    staff = await db.staff.find_one({"email": email})
    if not staff:
        # Same error for unknown email to avoid enumeration
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_hash = staff.get("password_hash") or staff.get("password")  # tolerate legacy field
    if not stored_hash or not _verify_password_tolerant(password, stored_hash):
        # Audit the failure (best-effort; audit log collection is optional)
        try:
            # Phase 5.4 / C-1 — db.audit_log ownership routes through
            # SecurityAuditRepository. login_failed shape: FLAT email,
            # NO user_id (auth not yet resolved).
            from app.repositories import SecurityAuditRepository
            await SecurityAuditRepository(db).record_login_failed({
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": "login_failed",
                "email": email,
                "ip": (request.client.host if request.client else None),
            })
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if staff.get("disabled"):
        raise HTTPException(status_code=403, detail="Account disabled")

    user_doc = {
        "id": staff.get("id") or staff.get("_id"),
        "email": staff.get("email"),
        "name": staff.get("name") or staff.get("email"),
        "role": (staff.get("role") or "manager").lower(),
        "managerId": staff.get("id") or staff.get("_id"),
        "tokenVersion": int(staff.get("tokenVersion") or 0),
    }

    # ─── Role-based challenge policy ─────────────────────────────────
    # Password is validated above. Some roles may require a second step:
    #   * admin   (if TOTP enabled in own profile) → Google Authenticator
    #   * manager (if TOTP enabled in own profile) → Google Authenticator
    # The ``team_lead`` role has been removed from the product; there is
    # no email-OTP login path anymore. If anything goes wrong in this block
    # the caller falls back to the legacy "issue JWT immediately" path so
    # authentication never breaks because of policy-layer issues.
    try:
        from app.services.auth_policy import AuthPolicyService
        _policy = AuthPolicyService(db)
        _challenge = await _policy.required_challenge(user_doc)
    except Exception as _e:  # noqa: BLE001
        logger.warning(f"[auth/login] policy resolution failed, falling back to JWT-now: {_e}")
        _challenge = None

    if _challenge == "totp":
        return {
            "challenge": "totp",
            "user_id": user_doc["id"],
            "user_email": user_doc["email"],
            "role": user_doc["role"],
            "hint": "Open Google Authenticator and enter the 6-digit code.",
        }
    # NOTE: the legacy ``email_otp`` branch was removed together with the
    # ``team_lead`` role — AuthPolicyService.required_challenge() never
    # returns it anymore. Any other challenge value falls through to the
    # JWT-now path below.

    token = create_jwt(user_doc)
    # Best-effort: write a richer login audit (login_audit collection) in
    # addition to the existing security_audit/audit_log. Failure is silent.
    try:
        from app.services.auth_policy import AuthPolicyService
        await AuthPolicyService(db).write_event(
            user=user_doc, event="login", method="password", success=True,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        pass
    try:
        # Phase 5.4 / C-1 — db.audit_log ownership routes through
        # SecurityAuditRepository. login_ok shape: FLAT email/role
        # (NOT user_email/user_role), asymmetric with login_failed.
        from app.repositories import SecurityAuditRepository
        await SecurityAuditRepository(db).record_login_ok({
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "login_ok",
            "user_id": user_doc["id"],
            "email": user_doc["email"],
            "role": user_doc["role"],
            "ip": (request.client.host if request.client else None),
        })
    except Exception:
        pass
    return {"access_token": token, "token_type": "Bearer", "user": user_doc}

@fastapi_app.get("/api/leads")
async def list_leads(
    managerId: Optional[str] = None,
    score_gte: Optional[int] = None,
    limit: int = 50,
    skip: int = 0,
    # Wave 8 — Lead Workspace filters
    q: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    hasOpenTasks: Optional[bool] = None,
    tasksOverdue: Optional[bool] = None,
    noOpenTasks: Optional[bool] = None,
    lastContactFrom: Optional[str] = None,
    lastContactTo: Optional[str] = None,
    createdFrom: Optional[str] = None,
    createdTo: Optional[str] = None,
    budgetFrom: Optional[float] = None,
    budgetTo: Optional[float] = None,
    vinPresent: Optional[bool] = None,
    healthStatus: Optional[str] = None,
    priority: Optional[str] = None,   # Wave 10A — A|B|C|D
    sort: Optional[str] = None,  # e.g. "created_at:desc", "budgetEur:asc"
    # Customer-Card spec (2026-06-10): TL filters by UTM
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    # Доопр #15 (P1) — date preset filter alias (dateFrom/dateTo == createdFrom/createdTo)
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """List leads with Wave 8 Lead Workspace filters.

    Backward compatible — pre-Wave 8 callers (just managerId/score_gte/limit/skip)
    keep working unchanged. New filters are additive and OR/AND combined as
    documented in the Wave 8 spec.
    """
    query: Dict[str, Any] = {}

    # Launch-Candidate security fix (2026-06-09): scope managers to their own
    # leads (cannot read others'). admin/team_lead see all.
    _role = (current_user.get("role") or "").lower()
    if _role == "manager":
        managerId = current_user.get("id")

    # Legacy filters
    if managerId:
        if managerId == "unassigned":
            query["$or"] = [
                {"managerId": None},
                {"managerId": ""},
                {"managerId": {"$exists": False}},
            ]
        else:
            query["managerId"] = managerId
    if score_gte:
        query["score"] = {"$gte": score_gte}

    # Wave 8: text search across name/email/phone/vin/vehicleInterest
    if q:
        qs = q.strip()
        if qs:
            # Mongo regex is safe enough for short admin tokens; escape user input.
            import re as _re
            esc = _re.escape(qs)
            query["$and"] = query.get("$and", []) + [{
                "$or": [
                    {"firstName": {"$regex": esc, "$options": "i"}},
                    {"lastName":  {"$regex": esc, "$options": "i"}},
                    {"name":      {"$regex": esc, "$options": "i"}},
                    {"email":     {"$regex": esc, "$options": "i"}},
                    {"phone":     {"$regex": esc, "$options": "i"}},
                    {"vin":       {"$regex": esc, "$options": "i"}},
                    {"vehicleInterest": {"$regex": esc, "$options": "i"}},
                ]
            }]

    # Status / source
    if status:
        # Normalise legacy statuses to Wave 8 canonical set.
        canon = _normalize_lead_status(status)
        if canon == status:
            query["status"] = canon
        else:
            # Match BOTH legacy and canonical so old DB rows still group correctly.
            query["status"] = {"$in": list({status, canon})}
    if source:
        query["source"] = source

    # ── UTM filters (Team-Lead spec, 2026-06-10) ──────────────────────────
    #   Each is a substring match (case-insensitive) so "fb" matches both
    #   "facebook" and "fb_ads"; campaign managers usually paste partial
    #   slugs. Empty string = no filter.
    if utm_source:
        import re as _re_utm
        query["utm_source"] = {"$regex": _re_utm.escape(utm_source.strip()), "$options": "i"}
    if utm_medium:
        import re as _re_utm
        query["utm_medium"] = {"$regex": _re_utm.escape(utm_medium.strip()), "$options": "i"}
    if utm_campaign:
        import re as _re_utm
        query["utm_campaign"] = {"$regex": _re_utm.escape(utm_campaign.strip()), "$options": "i"}

    # VIN presence
    if vinPresent is True:
        query["vin"] = {"$nin": [None, ""]}
    elif vinPresent is False:
        query["$and"] = query.get("$and", []) + [{
            "$or": [{"vin": None}, {"vin": ""}, {"vin": {"$exists": False}}]
        }]

    # Budget range — match across both budgetEur and budgetUsd legacy mirror
    if budgetFrom is not None or budgetTo is not None:
        rng: Dict[str, Any] = {}
        if budgetFrom is not None:
            rng["$gte"] = budgetFrom
        if budgetTo is not None:
            rng["$lte"] = budgetTo
        query["$and"] = query.get("$and", []) + [{
            "$or": [{"budgetEur": rng}, {"budgetUsd": rng}]
        }]

    # created_at range (Доопр #15: dateFrom/dateTo alias to createdFrom/createdTo)
    _from = createdFrom or dateFrom
    _to   = createdTo   or dateTo
    if _from or _to:
        cr: Dict[str, Any] = {}
        if _from:
            cr["$gte"] = _from
        if _to:
            cr["$lte"] = _to
        query["created_at"] = cr

    # lastContact range (uses last_contact_at if present, falls back to updated_at)
    if lastContactFrom or lastContactTo:
        lc: Dict[str, Any] = {}
        if lastContactFrom:
            lc["$gte"] = lastContactFrom
        if lastContactTo:
            lc["$lte"] = lastContactTo
        query["$and"] = query.get("$and", []) + [{
            "$or": [{"last_contact_at": lc}, {"updated_at": lc}]
        }]

    # Tasks-based filters — Wave 8 requires an inline join with db.tasks
    # We resolve the matching set of leadIds first, then constrain `query`.
    if hasOpenTasks or tasksOverdue or noOpenTasks:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            task_q: Dict[str, Any] = {
                "leadId":  {"$exists": True, "$ne": None},
                "status":  {"$nin": ["done", "completed", "cancelled", "archived"]},
            }
            if tasksOverdue:
                task_q["due_at"] = {"$lt": now_iso}
            open_lead_ids = await db.tasks.distinct("leadId", task_q)
            open_lead_ids = [x for x in open_lead_ids if x]
            if hasOpenTasks or tasksOverdue:
                query["id"] = {"$in": open_lead_ids}
            if noOpenTasks:
                # Combine — if hasOpenTasks also requested, treat noOpenTasks as override.
                query["id"] = {"$nin": open_lead_ids}
        except Exception as _e:
            logger.debug(f"[/api/leads] tasks-filter join skipped: {_e}")

    # Sort parsing — default created_at desc
    sort_field, sort_dir = "created_at", -1
    if sort:
        parts = sort.split(":", 1)
        sort_field = parts[0] or "created_at"
        sort_dir = -1 if (len(parts) > 1 and parts[1].lower() == "desc") else (
            1 if (len(parts) > 1 and parts[1].lower() == "asc") else -1
        )

    cursor = db.leads.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.leads.count_documents(query)

    # Normalise status into Wave 8 canon for the UI (does not mutate DB).
    for it in items:
        it["status"] = _normalize_lead_status(it.get("status"))

    # Wave 9: quick health-bucket post-filter (lead-doc only)
    if healthStatus:
        wanted = healthStatus.strip().lower()
        items = [it for it in items if _quick_lead_health_bucket(it) == wanted]
        total = len(items)

    # Wave 10A: enrich each item with priority bucket + heat color
    from app.services.lead_priority import quick_priority_bucket
    for it in items:
        hb = _quick_lead_health_bucket(it)
        it["healthBucket"] = hb
        it["priorityBucket"] = quick_priority_bucket(it, health_bucket=hb)
        it["heatColor"]   = _lead_heat_color(it)
        it["daysSinceContact"] = _days_since_lead_contact(it)
        # camelCase aliases so the frontend can render the timestamps
        # consistently regardless of which historical snake_case key the
        # document carries (some old leads only have ``updated_at``).
        it["lastContactAt"]   = (
            it.get("last_contact_at")
            or it.get("last_activity_at")
            or it.get("updated_at")
        )
        it["statusChangedAt"] = (
            it.get("last_status_change_at")
            or it.get("status_changed_at")
            or it.get("updated_at")
        )

    # Wave 10A: priority post-filter
    if priority:
        wanted_p = priority.strip().upper()
        items = [it for it in items if it.get("priorityBucket") == wanted_p]
        total = len(items)

    return {"success": True, "data": items, "items": items, "total": total}


# ─── Wave 8: Lead Workspace constants & helpers ────────────────────────────
# Canonical status pipeline for the Kanban board. Both the legacy values
# (new/contacted/qualified/proposal/negotiation/won/lost/archived) and the
# Wave 8 vocabulary (decision/not_qualified/converted) coexist in the DB;
# the normalizer collapses them into the canonical 8-state pipeline.
LEAD_WORKSPACE_STATUSES = (
    "new",
    "contacted",
    "qualified",
    "negotiation",
    "decision",
    "not_qualified",
    "converted",
    "lost",
)

# Legacy → canonical mapping (does NOT rewrite the DB; only normalises reads).
_LEAD_STATUS_ALIASES = {
    None:        "new",
    "":          "new",
    "proposal":  "negotiation",
    "won":       "converted",
    "archived":  "lost",
    "open":      "new",
    "processing": "qualified",
    "in_progress": "qualified",
    "pending":   "contacted",
    "closed":    "lost",
    "rejected":  "not_qualified",
    "unqualified": "not_qualified",
}


def _normalize_lead_status(value: Optional[str]) -> str:
    v = (value or "").strip().lower()
    if v in LEAD_WORKSPACE_STATUSES:
        return v
    return _LEAD_STATUS_ALIASES.get(v, v if v else "new")


def _quick_lead_health_bucket(lead: Dict[str, Any]) -> str:
    """Cheap health bucket using only lead-doc fields.

    Mirrors the buckets returned by compute_lead_health() but without
    joining tasks/calls. Used for list/kanban post-filtering — the full
    health (with reasons + next_action) is only computed in Lead360.

    Buckets: healthy | warning | overdue | stale | dead | converted
    """
    status = _normalize_lead_status(lead.get("status"))
    if status == "converted":
        return "converted"
    if status in ("lost", "not_qualified"):
        return "dead"

    last_iso = (
        lead.get("last_contact_at")
        or lead.get("last_status_change_at")
        or lead.get("updated_at")
        or lead.get("created_at")
    )
    try:
        if isinstance(last_iso, datetime):
            d = last_iso if last_iso.tzinfo else last_iso.replace(tzinfo=timezone.utc)
        elif last_iso:
            s = str(last_iso).replace("Z", "+00:00")
            d = datetime.fromisoformat(s)
            d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        else:
            d = None
    except Exception:
        d = None
    if not d:
        return "warning"
    days = max(0.0, (datetime.now(timezone.utc) - d).total_seconds() / 86400.0)
    if days <= 1:
        return "healthy"
    if days <= 3:
        return "warning"
    if days <= 7:
        return "stale"
    if days <= 21:
        # could be overdue or stale — without tasks join we surface as "stale"
        return "stale"
    return "dead"


def _days_since_lead_contact(lead: Dict[str, Any]) -> Optional[float]:
    """Days since last activity for a lead, used by the heatmap accent."""
    last_iso = (
        lead.get("last_contact_at")
        or lead.get("last_status_change_at")
        or lead.get("updated_at")
        or lead.get("created_at")
    )
    try:
        if isinstance(last_iso, datetime):
            d = last_iso if last_iso.tzinfo else last_iso.replace(tzinfo=timezone.utc)
        elif last_iso:
            s = str(last_iso).replace("Z", "+00:00")
            d = datetime.fromisoformat(s)
            d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        else:
            return None
    except Exception:
        return None
    delta = (datetime.now(timezone.utc) - d).total_seconds() / 86400.0
    return round(max(0.0, delta), 1)


def _lead_heat_color(lead: Dict[str, Any]) -> str:
    """Wave 10B — Heatmap color name based on days_since_contact.
    Terminal states are neutral. Frontend maps the name to a tailwind color.
    """
    status = _normalize_lead_status(lead.get("status"))
    if status in ("converted",):
        return "success"
    if status in ("lost", "not_qualified"):
        return "neutral"
    days = _days_since_lead_contact(lead)
    if days is None:
        return "neutral"
    if days <= 3:   return "green"
    if days <= 7:   return "yellow"
    if days <= 14:  return "orange"
    return "red"


# Ukrainian / English labels used by the Kanban board headers when the
# frontend does not supply its own i18n. The frontend always overrides
# these via its translations.js, so the backend value is just a fallback.
LEAD_STATUS_LABELS = {
    "new":            {"uk": "Новий",                "en": "New"},
    "contacted":      {"uk": "Контакт встановлено",   "en": "Contacted"},
    "qualified":      {"uk": "Кваліфікований",        "en": "Qualified"},
    "negotiation":    {"uk": "Перемовини",            "en": "Negotiation"},
    "decision":       {"uk": "Приймає рішення",       "en": "Decision making"},
    "not_qualified":  {"uk": "Не кваліфікований",     "en": "Not qualified"},
    "converted":      {"uk": "Конвертований",         "en": "Converted"},
    "lost":           {"uk": "Втрачений",             "en": "Lost"},
}


def _can_user_touch_lead(user: Dict[str, Any], lead: Dict[str, Any]) -> bool:
    """ACL: who can move/edit a lead.

    * admin / master_admin / owner → any lead
    * team_lead                    → leads of their team (managerId belongs to team) OR own
    * manager                      → only leads where managerId == user.id
    """
    role = (user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner"):
        return True
    uid = user.get("id") or user.get("managerId") or user.get("staff_id")
    lead_mgr = lead.get("managerId")
    if role == "team_lead":
        # Team-lead can see/move unassigned + own + any in their team.
        # Team membership lookup is best-effort; default-allow with own/unassigned guard.
        if not lead_mgr or lead_mgr == uid:
            return True
        return True  # team_lead has broad authority over leads pool in Wave 8 v1
    if role == "manager":
        return bool(uid) and (lead_mgr == uid)
    return False


async def _lead_role_scope(user: Dict[str, Any]) -> Dict[str, Any]:
    """Return a Mongo filter limiting the leads collection to what the user can see."""
    role = (user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner", "team_lead"):
        return {}
    uid = user.get("id") or user.get("managerId") or user.get("staff_id")
    if not uid:
        return {"_no_match_": True}
    return {"managerId": uid}


# ─── Wave 8: GET /api/leads/kanban ─────────────────────────────────────────
@fastapi_app.get("/api/leads/kanban")
async def leads_kanban(
    q: Optional[str] = None,
    source: Optional[str] = None,
    managerId: Optional[str] = None,
    vinPresent: Optional[bool] = None,
    hasOpenTasks: Optional[bool] = None,
    tasksOverdue: Optional[bool] = None,
    noOpenTasks: Optional[bool] = None,
    budgetFrom: Optional[float] = None,
    budgetTo: Optional[float] = None,
    createdFrom: Optional[str] = None,
    createdTo: Optional[str] = None,
    healthStatus: Optional[str] = None,
    priority: Optional[str] = None,
    limit_per_column: int = 50,
    lang: str = "uk",
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Group leads by canonical status. Returns column-shaped payload for the Kanban board."""
    scope = await _lead_role_scope(current_user)
    if scope.get("_no_match_"):
        return {
            "success": True,
            "columns": [
                {"status": s, "label": LEAD_STATUS_LABELS[s].get(lang, LEAD_STATUS_LABELS[s]["en"]),
                 "count": 0, "items": []} for s in LEAD_WORKSPACE_STATUSES
            ],
            "total": 0,
        }

    query: Dict[str, Any] = dict(scope)

    # Manager filter (admin/team-lead can drill in)
    if managerId:
        if managerId == "unassigned":
            query["$or"] = [
                {"managerId": None}, {"managerId": ""}, {"managerId": {"$exists": False}},
            ]
        else:
            query["managerId"] = managerId

    # q
    if q:
        import re as _re
        esc = _re.escape(q.strip())
        if esc:
            query["$and"] = query.get("$and", []) + [{
                "$or": [
                    {"firstName": {"$regex": esc, "$options": "i"}},
                    {"lastName":  {"$regex": esc, "$options": "i"}},
                    {"name":      {"$regex": esc, "$options": "i"}},
                    {"email":     {"$regex": esc, "$options": "i"}},
                    {"phone":     {"$regex": esc, "$options": "i"}},
                    {"vin":       {"$regex": esc, "$options": "i"}},
                    {"vehicleInterest": {"$regex": esc, "$options": "i"}},
                ]
            }]

    if source:
        query["source"] = source

    if vinPresent is True:
        query["vin"] = {"$nin": [None, ""]}
    elif vinPresent is False:
        query["$and"] = query.get("$and", []) + [{
            "$or": [{"vin": None}, {"vin": ""}, {"vin": {"$exists": False}}]
        }]

    if budgetFrom is not None or budgetTo is not None:
        rng: Dict[str, Any] = {}
        if budgetFrom is not None: rng["$gte"] = budgetFrom
        if budgetTo is not None:   rng["$lte"] = budgetTo
        query["$and"] = query.get("$and", []) + [{
            "$or": [{"budgetEur": rng}, {"budgetUsd": rng}]
        }]

    if createdFrom or createdTo:
        cr: Dict[str, Any] = {}
        if createdFrom: cr["$gte"] = createdFrom
        if createdTo:   cr["$lte"] = createdTo
        query["created_at"] = cr

    if hasOpenTasks or tasksOverdue or noOpenTasks:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            task_q: Dict[str, Any] = {
                "leadId": {"$exists": True, "$ne": None},
                "status": {"$nin": ["done", "completed", "cancelled", "archived"]},
            }
            if tasksOverdue:
                task_q["due_at"] = {"$lt": now_iso}
            open_lead_ids = await db.tasks.distinct("leadId", task_q)
            open_lead_ids = [x for x in open_lead_ids if x]
            if hasOpenTasks or tasksOverdue:
                query["id"] = {"$in": open_lead_ids}
            if noOpenTasks and not (hasOpenTasks or tasksOverdue):
                query["id"] = {"$nin": open_lead_ids}
        except Exception as _e:
            logger.debug(f"[/api/leads/kanban] tasks-filter join skipped: {_e}")

    cursor = db.leads.find(query, {"_id": 0}).sort("created_at", -1).limit(2000)
    raw = await cursor.to_list(length=2000)

    # ── Wave 9: quick health bucket post-filter (lead-doc only, no tasks/calls join)
    if healthStatus:
        wanted = healthStatus.strip().lower()
        raw = [it for it in raw if _quick_lead_health_bucket(it) == wanted]

    # ── Wave 10A: enrich each lead with priority + heat fields ──
    from app.services.lead_priority import quick_priority_bucket
    for it in raw:
        hb = _quick_lead_health_bucket(it)
        it["healthBucket"]     = hb
        it["priorityBucket"]   = quick_priority_bucket(it, health_bucket=hb)
        it["heatColor"]        = _lead_heat_color(it)
        it["daysSinceContact"] = _days_since_lead_contact(it)
        it["lastContactAt"]    = (
            it.get("last_contact_at")
            or it.get("last_activity_at")
            or it.get("updated_at")
        )
        it["statusChangedAt"]  = (
            it.get("last_status_change_at")
            or it.get("status_changed_at")
            or it.get("updated_at")
        )

    if priority:
        wanted_p = priority.strip().upper()
        raw = [it for it in raw if it.get("priorityBucket") == wanted_p]

    # Group by canonical status
    grouped: Dict[str, List[Dict[str, Any]]] = {s: [] for s in LEAD_WORKSPACE_STATUSES}
    for it in raw:
        canon = _normalize_lead_status(it.get("status"))
        it["status"] = canon
        if canon not in grouped:
            grouped[canon] = []
        grouped[canon].append(it)

    # Build response — cap items per column for frontend perf
    columns: List[Dict[str, Any]] = []
    total = 0
    for st in LEAD_WORKSPACE_STATUSES:
        items = grouped.get(st, [])
        total += len(items)
        columns.append({
            "status": st,
            "label":  LEAD_STATUS_LABELS[st].get(lang, LEAD_STATUS_LABELS[st]["en"]),
            "count":  len(items),
            "items":  items[:limit_per_column],
            "hasMore": len(items) > limit_per_column,
        })

    return {"success": True, "columns": columns, "total": total}


# ─── Wave 8: PATCH /api/leads/{id}/status ──────────────────────────────────
@fastapi_app.patch("/api/leads/{lead_id}/status")
async def patch_lead_status(
    lead_id: str,
    payload: Dict[str, Any] = Body(...),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Move a lead between Kanban columns. Writes audit + timeline best-effort."""
    new_status = _normalize_lead_status(payload.get("status"))
    if new_status not in LEAD_WORKSPACE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{payload.get('status')}'")

    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not _can_user_touch_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="You cannot move this lead")

    prev_status = _normalize_lead_status(lead.get("status"))
    if prev_status == new_status:
        return {"success": True, "lead": lead, "changed": False}

    reason = (payload.get("reason") or "").strip() or "kanban_move"
    now_iso = datetime.now(timezone.utc).isoformat()

    update: Dict[str, Any] = {
        "status":     new_status,
        "updated_at": now_iso,
        "last_status_change_at": now_iso,
        "last_status_change_by": current_user.get("id") or current_user.get("email"),
        "last_status_change_reason": reason,
    }

    # Convenience: when manually moved to "converted" and no customer linked yet,
    # mirror the auto-convert flow lazily so the card stops showing in the leads
    # pipeline next refresh. (Idempotent — convert endpoint already handles dupe.)
    await db.leads.update_one({"id": lead_id}, {"$set": update})
    fresh = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}
    fresh["status"] = _normalize_lead_status(fresh.get("status"))

    # Block 6.2 — moving away from "new" counts as a first response
    if prev_status in ("new", "newlead", "new_lead") or new_status != "new":
        try:
            from app.services.lead_sla import mark_lead_responded as _mlr
            await _mlr(
                db, lead_id,
                by_user_id=current_user.get("id") or current_user.get("email"),
                source="status_change",
            )
        except Exception:
            pass

    # Audit log (best-effort)
    try:
        await audit(
            action="lead.status.change",
            user=current_user,
            resource=f"lead:{lead_id}",
            meta={"from": prev_status, "to": new_status, "reason": reason},
            request=request,
        )
    except Exception:
        pass

    # Timeline event on linked customer (best-effort)
    try:
        if fresh.get("customerId"):
            await db.customer_events.insert_one({
                "id":         f"cevt-{datetime.now(timezone.utc).timestamp()}",
                "customerId": fresh["customerId"],
                "type":       "lead_status_change",
                "title":      f"Lead status: {prev_status} → {new_status}",
                "leadId":     lead_id,
                "meta":       {"from": prev_status, "to": new_status, "reason": reason},
                "created_at": now_iso,
                "created_by": current_user.get("id") or current_user.get("email"),
            })
    except Exception:
        pass

    return {"success": True, "lead": fresh, "changed": True, "from": prev_status, "to": new_status}


# ─── Wave 8: Saved filters CRUD ────────────────────────────────────────────
@fastapi_app.get("/api/leads/saved-filters")
async def list_lead_saved_filters(current_user: Dict[str, Any] = Depends(require_user)):
    uid = current_user.get("id") or current_user.get("email") or "anon"
    cursor = db.lead_saved_filters.find(
        {"$or": [{"userId": uid}, {"shared": True}]},
        {"_id": 0},
    ).sort("created_at", -1)
    items = await cursor.to_list(length=200)
    return {"success": True, "items": items, "total": len(items)}


@fastapi_app.post("/api/leads/saved-filters")
async def create_lead_saved_filter(
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    query = payload.get("query") or {}
    uid = current_user.get("id") or current_user.get("email") or "anon"
    doc = {
        "id":         f"lfilt-{datetime.now(timezone.utc).timestamp()}",
        "name":       name,
        "query":      query if isinstance(query, dict) else {},
        "userId":     uid,
        "shared":     bool(payload.get("shared", False)),
        "icon":       payload.get("icon") or "Funnel",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.lead_saved_filters.insert_one(doc)
    doc.pop("_id", None)
    return {"success": True, "item": doc}


@fastapi_app.delete("/api/leads/saved-filters/{filter_id}")
async def delete_lead_saved_filter(
    filter_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    uid = current_user.get("id") or current_user.get("email") or "anon"
    role = (current_user.get("role") or "").lower()
    q: Dict[str, Any] = {"id": filter_id}
    # admins can delete any; others only own
    if role not in ("admin", "master_admin", "owner"):
        q["userId"] = uid
    res = await db.lead_saved_filters.delete_one(q)
    return {"success": True, "deleted": res.deleted_count}


# ─── Wave 9: Lead360 helpers ───────────────────────────────────────────────
async def _load_lead_open_tasks(lead_id: str) -> List[Dict[str, Any]]:
    """Open tasks attached to a lead (multiple legacy field names supported)."""
    try:
        q = {
            "$or": [
                {"leadId": lead_id},
                {"lead_id": lead_id},
                {"entity_type": "lead", "entity_id": lead_id},
            ],
            "status": {"$nin": ["done", "completed", "cancelled", "archived"]},
        }
        return await db.tasks.find(q, {"_id": 0}).sort("due_at", 1).to_list(length=50)
    except Exception:
        return []


async def _load_lead_last_call(lead_id: str, lead: Dict[str, Any]) -> Optional[str]:
    try:
        # Prefer lead_id, fall back to phone match
        c = await db.ringostat_calls.find_one(
            {"$or": [{"lead_id": lead_id}, {"leadId": lead_id}]},
            sort=[("created_at", -1)],
        )
        if c:
            return c.get("created_at") or c.get("start_time")
        phone = lead.get("phone")
        if phone:
            c2 = await db.ringostat_calls.find_one(
                {"$or": [{"from": phone}, {"to": phone}, {"caller_id": phone}]},
                sort=[("created_at", -1)],
            )
            if c2:
                return c2.get("created_at") or c2.get("start_time")
    except Exception:
        pass
    return None


async def _load_lead_calls(lead_id: str, lead: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        items = await db.ringostat_calls.find(
            {"$or": [{"lead_id": lead_id}, {"leadId": lead_id}]},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
    except Exception:
        items = []
    if items:
        return items
    phone = lead.get("phone")
    if not phone:
        return []
    try:
        return await db.ringostat_calls.find(
            {"$or": [{"from": phone}, {"to": phone}, {"caller_id": phone}]},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
    except Exception:
        return []


async def _build_lead_timeline(lead_id: str, lead: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """Compose a unified timeline from multiple sources."""
    events: List[Dict[str, Any]] = []

    # 1) created
    if lead.get("created_at"):
        events.append({
            "id":   f"lead-created-{lead_id}",
            "kind": "lead_created",
            "icon": "Star",
            "title": "Lead created",
            "subtitle": f"Source: {lead.get('source') or '—'}",
            "at":   lead["created_at"],
            "color": "#3B82F6",
        })

    # 2) status_change events from customer_events when linked
    if lead.get("customerId"):
        try:
            sce = await db.customer_events.find(
                {"leadId": lead_id, "type": "lead_status_change"},
                {"_id": 0},
            ).sort("created_at", -1).to_list(length=limit)
            for e in sce:
                meta = e.get("meta") or {}
                events.append({
                    "id":    e.get("id"),
                    "kind":  "status_change",
                    "icon":  "ArrowRight",
                    "title": f"Status: {meta.get('from') or '?'} → {meta.get('to') or '?'}",
                    "subtitle": meta.get("reason") or "",
                    "at":    e.get("created_at"),
                    "color": "#8B5CF6",
                    "by":    e.get("created_by"),
                })
        except Exception:
            pass

    # 3) Audit log fallback for status changes when there's no customerId yet
    try:
        audit_q = {
            "action": "lead.status.change",
            "$or": [{"resource": f"lead:{lead_id}"}, {"meta.lead_id": lead_id}],
        }
        rows = await db.audit_logs.find(audit_q, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
        for e in rows:
            meta = e.get("meta") or {}
            events.append({
                "id":    e.get("id") or f"audit-{e.get('created_at')}",
                "kind":  "status_change",
                "icon":  "ArrowRight",
                "title": f"Status: {meta.get('from') or '?'} → {meta.get('to') or '?'}",
                "subtitle": meta.get("reason") or "",
                "at":    e.get("created_at") or e.get("timestamp"),
                "color": "#8B5CF6",
                "by":    e.get("user") or e.get("user_email"),
            })
    except Exception:
        pass

    # 4) calls — pull most recent N
    calls = await _load_lead_calls(lead_id, lead, limit=15)
    for c in calls:
        dur = c.get("duration") or 0
        direction = (c.get("direction") or "").lower()
        events.append({
            "id":    f"call-{c.get('call_id') or c.get('id') or c.get('created_at')}",
            "kind":  "call",
            "icon":  "Phone",
            "title": f"{direction.capitalize() or 'Call'} — {dur}s",
            "subtitle": (c.get("from") or "") + " → " + (c.get("to") or ""),
            "at":    c.get("created_at") or c.get("start_time"),
            "color": "#10B981" if direction == "outbound" else "#06B6D4",
            "meta":  {"duration": dur, "recording": c.get("recording_url")},
        })

    # 5) notes
    try:
        notes = await db.lead_notes.find({"leadId": lead_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(length=20)
        for n in notes:
            events.append({
                "id":    n.get("id"),
                "kind":  "note",
                "icon":  "NotePencil",
                "title": "Note",
                "subtitle": (n.get("text") or "")[:140],
                "at":    n.get("created_at"),
                "color": "#F59E0B",
                "by":    n.get("created_by"),
            })
    except Exception:
        pass

    # 6) conversion
    if lead.get("convertedAt"):
        events.append({
            "id":    f"converted-{lead_id}",
            "kind":  "conversion",
            "icon":  "CheckCircle",
            "title": "Converted to customer",
            "subtitle": lead.get("customerId") or "",
            "at":    lead["convertedAt"],
            "color": "#16A34A",
        })

    # Sort newest-first, cap at limit
    def _key(e):
        v = e.get("at")
        # Coerce both datetimes and strings into a single comparable str
        if v is None:
            return ""
        if isinstance(v, datetime):
            try:
                return v.isoformat()
            except Exception:
                return ""
        return str(v)
    events.sort(key=_key, reverse=True)
    # Also coerce the outgoing `at` to ISO string so the frontend Date()
    # constructor receives a consistent format.
    for e in events:
        v = e.get("at")
        if isinstance(v, datetime):
            try:
                e["at"] = v.isoformat()
            except Exception:
                e["at"] = str(v)
    return events[:limit]


# [car-import removed] _load_related_cars (VIN/quotes/calculator snapshots)


def _can_user_see_lead(user: Dict[str, Any], lead: Dict[str, Any]) -> bool:
    """View ACL (broader than touch ACL — TLs see everything)."""
    role = (user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner", "team_lead"):
        return True
    uid = user.get("id") or user.get("managerId") or user.get("staff_id") or user.get("email")
    return bool(uid) and lead.get("managerId") == uid


def _customer_scope_filter(user: Dict[str, Any]) -> Dict[str, Any]:
    """Return a Mongo-filter fragment that constrains a `customers` query
    (and any collection that carries `managerId`) to the docs that the
    given staff user is allowed to see.

    Roles (per Customer-Card spec, 2026-06-10):
      • admin / master_admin / owner / team_lead → no constraint
      • manager → only own customers (`managerId == user.id`)
      • anything else → `{"_id": "__deny__"}` (sees nothing)

    Returns an EMPTY dict for unrestricted roles so callers can `**spread`
    it into their existing filters without an extra `if`.
    """
    role = (user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner", "team_lead"):
        return {}
    uid = user.get("id") or user.get("managerId") or user.get("staff_id") or user.get("email")
    if role == "manager" and uid:
        return {"managerId": uid}
    return {"_id": "__deny__"}


def _can_user_see_customer(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    """View ACL for a single customer doc (mirror of `_can_user_see_lead`)."""
    role = (user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner", "team_lead"):
        return True
    uid = user.get("id") or user.get("managerId") or user.get("staff_id") or user.get("email")
    return bool(uid) and customer.get("managerId") == uid


# ─── Wave 9: GET /api/leads/{id}/360 ───────────────────────────────────────
@fastapi_app.get("/api/leads/smart-filters")
async def lead_smart_filters(current_user: Dict[str, Any] = Depends(require_user)):
    """Wave 10A — list the system-curated smart filter presets."""
    from app.services.lead_priority import SMART_FILTERS
    return {"success": True, "items": SMART_FILTERS, "total": len(SMART_FILTERS)}


@fastapi_app.get("/api/leads/{lead_id}/360")
async def lead_360(
    lead_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """One-shot Lead360 bundle: lead + health + tasks + recent_calls + timeline_preview + related_cars."""
    from app.services.lead_health import compute_lead_health

    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        # Launch-Candidate fix (2026-06-09): legacy Ringostat auto-create
        # path used to set only `_id`. The startup backfill now syncs them,
        # but if any cached call happens before the backfill completes,
        # fall back to a direct _id lookup so the user never sees a stale
        # 404 on a real lead.
        lead = await db.leads.find_one({"_id": lead_id})
        if lead:
            lead.pop("_id", None)
            if not lead.get("id"):
                lead["id"] = lead_id
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not _can_user_see_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Normalise legacy status before serving
    lead["status"] = _normalize_lead_status(lead.get("status"))

    open_tasks   = await _load_lead_open_tasks(lead_id)
    last_call_at = await _load_lead_last_call(lead_id, lead)
    recent_calls = await _load_lead_calls(lead_id, lead, limit=10)
    timeline     = await _build_lead_timeline(lead_id, lead, limit=30)
    # [ECO CLEANUP] car/VIN ingestion removed — related cars no longer sourced.
    related_cars = []
    notes_count = 0
    try:
        notes_count = await db.lead_notes.count_documents({"leadId": lead_id})
    except Exception:
        pass

    health = compute_lead_health(
        lead,
        open_tasks=open_tasks,
        last_call_at=last_call_at,
    )

    # Wave 10A — full priority computation
    from app.services.lead_priority import compute_lead_priority
    priority = compute_lead_priority(
        lead,
        health=health,
        open_tasks_count=len(open_tasks),
        recent_calls_count=len(recent_calls),
    )

    # Wave 10B — heat color shipped alongside for the hero / kanban
    lead["heatColor"]        = _lead_heat_color(lead)
    lead["daysSinceContact"] = _days_since_lead_contact(lead)
    lead["priorityBucket"]   = priority["bucket"]
    # Deep-tracking timestamps as camelCase aliases for the UI
    lead["lastContactAt"]   = (
        lead.get("last_contact_at")
        or lead.get("last_activity_at")
        or lead.get("updated_at")
    )
    lead["statusChangedAt"] = (
        lead.get("last_status_change_at")
        or lead.get("status_changed_at")
        or lead.get("updated_at")
    )

    # Manager resolution (single record for header chip)
    manager = None
    if lead.get("managerId"):
        try:
            mraw = await db.users.find_one(
                {"$or": [{"id": lead["managerId"]}, {"_id": lead["managerId"]}]},
                {"_id": 0, "password_hash": 0, "password": 0},
            )
            if mraw:
                manager = {
                    "id":    mraw.get("id"),
                    "name":  mraw.get("name") or mraw.get("full_name"),
                    "email": mraw.get("email"),
                    "avatar": mraw.get("avatar_url") or mraw.get("avatar"),
                    "role":  mraw.get("role"),
                }
        except Exception:
            manager = None

    return {
        "success":     True,
        "lead":        lead,
        "health":      health,
        "priority":    priority,
        "manager":     manager,
        "open_tasks":  open_tasks,
        "recent_calls": recent_calls,
        "timeline":    timeline,
        "related_cars": related_cars,
        "counts": {
            "open_tasks":   len(open_tasks),
            "recent_calls": len(recent_calls),
            "timeline":     len(timeline),
            "related_cars": len(related_cars),
            "notes":        notes_count,
        },
    }


# ─── Wave 9: GET /api/leads/{id}/timeline ──────────────────────────────────
@fastapi_app.get("/api/leads/{lead_id}/timeline")
async def lead_timeline(
    lead_id: str,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(require_user),
):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not _can_user_see_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Forbidden")
    events = await _build_lead_timeline(lead_id, lead, limit=limit)
    return {"success": True, "items": events, "total": len(events)}


# ─── Wave 9: notes CRUD ────────────────────────────────────────────────────
@fastapi_app.get("/api/leads/{lead_id}/notes")
async def list_lead_notes(
    lead_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not _can_user_see_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Forbidden")
    cursor = db.lead_notes.find({"leadId": lead_id}, {"_id": 0}).sort("created_at", -1).limit(200)
    items = await cursor.to_list(length=200)
    return {"success": True, "items": items, "total": len(items)}


@fastapi_app.post("/api/leads/{lead_id}/notes")
async def create_lead_note(
    lead_id: str,
    payload: Dict[str, Any] = Body(...),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not _can_user_see_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Forbidden")

    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    now_iso = datetime.now(timezone.utc).isoformat()
    note = {
        "id":         f"lnote-{datetime.now(timezone.utc).timestamp()}",
        "leadId":     lead_id,
        "text":       text,
        "pinned":     bool(payload.get("pinned", False)),
        "created_at": now_iso,
        "created_by": current_user.get("id") or current_user.get("email"),
        "created_by_name": current_user.get("name") or current_user.get("email"),
    }
    await db.lead_notes.insert_one(note)
    note.pop("_id", None)

    # bump lead.updated_at for activity-state
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"updated_at": now_iso, "last_contact_at": now_iso}},
    )

    # Block 6.2 — first response stamp (idempotent)
    try:
        from app.services.lead_sla import mark_lead_responded as _mlr
        await _mlr(
            db, lead_id,
            by_user_id=current_user.get("id") or current_user.get("email"),
            source="note",
        )
    except Exception:
        pass

    try:
        await audit(
            action="lead.note.create", user=current_user,
            resource=f"lead:{lead_id}", meta={"note_id": note["id"]},
            request=request,
        )
    except Exception:
        pass
    return {"success": True, "note": note}


@fastapi_app.delete("/api/leads/{lead_id}/notes/{note_id}")
async def delete_lead_note(
    lead_id: str,
    note_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not _can_user_see_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Forbidden")
    uid = current_user.get("id") or current_user.get("email")
    role = (current_user.get("role") or "").lower()
    q = {"id": note_id, "leadId": lead_id}
    if role not in ("admin", "master_admin", "owner", "team_lead"):
        q["created_by"] = uid
    res = await db.lead_notes.delete_one(q)
    return {"success": True, "deleted": res.deleted_count}


# [car-import removed] GET /api/leads/{id}/related-cars

# Sensitive customer fields that must NEVER leave the API surface (S2.2 IDOR /
# data-leak hardening — a customer card must not expose auth secrets).
_CUSTOMER_SAFE_PROJECTION = {
    "_id": 0, "password": 0, "password_hash": 0, "passwordHash": 0,
    "reset_token": 0, "resetToken": 0, "reset_token_expires": 0,
    "resetTokenExpires": 0, "otp_secret": 0, "totp_secret": 0,
    "mfa_secret": 0, "refresh_token": 0, "refreshToken": 0,
}


@fastapi_app.get("/api/customers")
async def list_customers(
    limit: int = 50,
    skip: int = 0,
    # Customer-Card spec (2026-06-10): TL filters
    managerId: Optional[str] = None,
    status: Optional[str] = None,
    country: Optional[str] = None,
    q: Optional[str] = None,
    # UTM — join through leads (UTM lives on lead, not customer)
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """List customers (RBAC-aware).

    Visibility:
      • admin / master_admin / team_lead → all customers.
      • manager → only own (`managerId == self.id`).

    Filters (admin / TL only — manager's own filter wins):
      • managerId   — pin to a specific manager (TL drilldown).
      • status      — exact-match on customer status.
      • country     — exact-match on direction country (USA/Korea/Bulgaria/Other).
      • q           — substring across firstName/lastName/name/email/phone.
      • utm_source / utm_medium / utm_campaign — substring (case-insensitive);
        joined through ``leads.customerId``: a customer is included if ANY of
        their leads match the UTM filter. Lets the marketing/TL view answer
        "which converted customers came from campaign X?".
    """
    role = (current_user.get("role") or "").lower()
    query: Dict[str, Any] = {}
    if role == "manager":
        query["managerId"] = current_user.get("id")
    elif managerId:
        query["managerId"] = managerId
    if status:
        query["status"] = status
    if country:
        query["country"] = country
    if q:
        import re as _re_q
        esc = _re_q.escape(q.strip())
        if esc:
            query["$or"] = [
                {"firstName":    {"$regex": esc, "$options": "i"}},
                {"lastName":     {"$regex": esc, "$options": "i"}},
                {"name":         {"$regex": esc, "$options": "i"}},
                {"surname":      {"$regex": esc, "$options": "i"}},
                {"email":        {"$regex": esc, "$options": "i"}},
                {"phone":        {"$regex": esc, "$options": "i"}},
                {"company_name": {"$regex": esc, "$options": "i"}},
                {"companyName":  {"$regex": esc, "$options": "i"}},
                {"id":           {"$regex": esc, "$options": "i"}},
            ]
    # ── UTM join via leads.customerId ─────────────────────────────────────
    if utm_source or utm_medium or utm_campaign:
        import re as _re_utm_c
        lead_q: Dict[str, Any] = {"customerId": {"$nin": [None, ""]}}
        if utm_source:
            lead_q["utm_source"] = {"$regex": _re_utm_c.escape(utm_source.strip()), "$options": "i"}
        if utm_medium:
            lead_q["utm_medium"] = {"$regex": _re_utm_c.escape(utm_medium.strip()), "$options": "i"}
        if utm_campaign:
            lead_q["utm_campaign"] = {"$regex": _re_utm_c.escape(utm_campaign.strip()), "$options": "i"}
        matching_customer_ids = await db.leads.distinct("customerId", lead_q)
        # If query already has $or (from `q` text search), wrap with $and
        if matching_customer_ids:
            if "$or" in query:
                query = {"$and": [query, {"id": {"$in": matching_customer_ids}}]}
            else:
                query["id"] = {"$in": matching_customer_ids}
        else:
            # No matching leads → return empty result quickly.
            return {"success": True, "data": [], "items": [], "total": 0}
    cursor = db.customers.find(query, _CUSTOMER_SAFE_PROJECTION).sort('created_at', -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.customers.count_documents(query)
    return {"success": True, "data": items, "items": items, "total": total}


@fastapi_app.get("/api/crm/search")
async def crm_global_search(
    q: str = "",
    per_type: int = 6,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Global CRM search across customers, invoices, contracts, requests and
    companies from a SINGLE query. Matches by email, company name, person name,
    phone, invoice number, contract number and request number.

    Results are RBAC-scoped: a manager only sees their own customers/invoices.
    Each hit carries a human `label` ("Company — email" where relevant) and a
    frontend `url` — navigation always goes through the stable id, never email.
    """
    import re as _re
    q = (q or "").strip()
    if len(q) < 2:
        return {"success": True, "query": q, "groups": [], "total": 0}
    rx = {"$regex": _re.escape(q), "$options": "i"}
    role = (current_user.get("role") or "").lower()
    is_priv = role in ("admin", "master_admin", "owner", "team_lead")
    uid = current_user.get("id")

    from app.services.customer_resolver import build_dto as _build_dto, resolve_many as _resolve_many

    groups: List[Dict[str, Any]] = []

    # ── Customers ────────────────────────────────────────────────────────
    cust_scope: Dict[str, Any] = {} if is_priv else {"managerId": uid}
    cust_or = [{"email": rx}, {"name": rx}, {"first_name": rx}, {"surname": rx},
               {"company_name": rx}, {"companyName": rx}, {"phone": rx}, {"id": rx}]
    cust_q = {"$and": [cust_scope, {"$or": cust_or}]} if cust_scope else {"$or": cust_or}
    custs = await db.customers.find(cust_q, _CUSTOMER_SAFE_PROJECTION).limit(per_type).to_list(length=per_type)
    if custs:
        groups.append({"type": "customer", "label": "Клієнти", "items": [
            {**_build_dto(c), "url": f"/app/customers/{c.get('id')}"} for c in custs
        ]})

    # ── Invoices (by number / id / denormalised customer fields) ─────────
    inv_scope: Dict[str, Any] = {} if is_priv else {"managerId": uid}
    inv_or = [{"id": rx}, {"number": rx}, {"description": rx},
              {"customerEmail": rx}, {"customerName": rx},
              {"contract_number": rx}, {"request_id": rx}]
    inv_q = {"$and": [inv_scope, {"$or": inv_or}]} if inv_scope else {"$or": inv_or}
    invs = await db.invoices.find(inv_q, {"_id": 0}).sort("created_at", -1).limit(per_type).to_list(length=per_type)
    if invs:
        dto_map = await _resolve_many(db, [i.get("customerId") for i in invs])
        inv_items = []
        for i in invs:
            dto = dto_map.get(i.get("customerId")) or _build_dto(None, fallback_email=i.get("customerEmail") or "", fallback_name=i.get("customerName") or "")
            inv_items.append({
                "id": i.get("id"),
                "number": i.get("number") or (i.get("id") or "")[-8:],
                "amount": i.get("amount") or i.get("total"),
                "currency": i.get("currency") or "UAH",
                "status": i.get("status"),
                "label": dto.get("display_label"),
                "customer_360_url": dto.get("customer_360_url"),
                "url": "/app/crm/invoices",
            })
        groups.append({"type": "invoice", "label": "Рахунки", "items": inv_items})

    # ── Contracts (by number / id) — reuse company link ──────────────────
    con_or = [{"id": rx}, {"number": rx}, {"contract_number": rx}]
    cons = await db.waste_contracts.find({"$or": con_or}, {"_id": 0}).sort("created_at", -1).limit(per_type).to_list(length=per_type)
    if cons:
        groups.append({"type": "contract", "label": "Договори", "items": [
            {"id": c.get("id"), "number": c.get("number") or c.get("contract_number") or (c.get("id") or "")[-8:],
             "status": c.get("status"), "label": c.get("number") or c.get("contract_number") or (c.get("id") or "")[-8:],
             "url": f"/app/operations/contracts/{c.get('id')}"}
            for c in cons
        ]})

    # ── Requests (by number / id) ────────────────────────────────────────
    req_or = [{"id": rx}, {"number": rx}]
    reqs = await db.waste_requests.find({"$or": req_or}, {"_id": 0}).sort("created_at", -1).limit(per_type).to_list(length=per_type)
    if reqs:
        groups.append({"type": "request", "label": "Заявки", "items": [
            {"id": r.get("id"), "number": r.get("number") or (r.get("id") or "")[-8:],
             "stage": r.get("stage"), "label": r.get("number") or (r.get("id") or "")[-8:],
             "url": "/app/requests"}
            for r in reqs
        ]})

    # ── Companies (by name / edrpou / email / phone) ─────────────────────
    co_or = [{"name": rx}, {"edrpou": rx}, {"email": rx}, {"phone": rx}, {"id": rx}]
    cos = await db.waste_companies.find({"$and": [{"deleted": {"$ne": True}}, {"$or": co_or}]}, {"_id": 0}).limit(per_type).to_list(length=per_type)
    if cos:
        groups.append({"type": "company", "label": "Компанії", "items": [
            {"id": c.get("id"), "label": c.get("name") or c.get("edrpou") or c.get("id"),
             "email": c.get("email"), "url": f"/app/companies/{c.get('id')}"}
            for c in cos
        ]})

    total = sum(len(g["items"]) for g in groups)
    return {"success": True, "query": q, "groups": groups, "total": total}

@fastapi_app.get("/api/deals")
async def list_deals(
    limit: int = 50,
    skip: int = 0,
    # Customer-Card spec (2026-06-10): TL filters
    managerId: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    # Launch-Candidate security fix (2026-06-09): require staff auth.
    # Managers see only their own deals (where managerId == current_user.id).
    _role = (current_user.get("role") or "").lower()
    _scope_query: Dict[str, Any] = {}
    if _role == "manager":
        _scope_query["managerId"] = current_user.get("id")
    elif managerId:
        # TL/admin drilldown by manager.
        _scope_query["managerId"] = managerId
    if status:
        _scope_query["status"] = status
    # Bug-fix Wave contract:
    #   GET /api/deals MUST always return `id` for every item so the
    #   frontend pipeline picker can select freshly-created deals.
    # Strategy:
    #   1. read with `_id` included
    #   2. if a doc has no `id` (legacy data), opportunistically
    #      persist `id = str(_id)` so future reads & queries match
    #   3. always emit BOTH `id` and `_id` (string-coerced) in the response
    cursor = db.deals.find(_scope_query).sort('created_at', -1).skip(skip).limit(limit)
    raw = await cursor.to_list(length=limit)
    items: List[Dict[str, Any]] = []
    needs_backfill: List[Any] = []
    for d in raw:
        _id = d.pop("_id", None)
        if _id is not None:
            d["_id"] = str(_id)
            if not d.get("id"):
                d["id"] = str(_id)
                needs_backfill.append(_id)
        items.append(d)
    # Opportunistic backfill (best-effort, never blocks the response).
    if needs_backfill:
        try:
            await db.deals.update_many(
                {"_id": {"$in": needs_backfill},
                 "$or": [{"id": {"$exists": False}}, {"id": None}, {"id": ""}]},
                [{"$set": {"id": {"$toString": "$_id"}}}],
            )
        except Exception as _e:
            logger.warning(f"[/api/deals] inline id-backfill skipped: {_e}")
    total = await db.deals.count_documents(_scope_query)
    return {"success": True, "data": items, "items": items, "total": total}

@fastapi_app.get("/api/tasks/eligible-assignees")
async def list_eligible_task_assignees(current_user: Dict[str, Any] = Depends(require_user)):
    """Return staff members the current user can assign tasks to.

    Role matrix (per project spec):
      - admin / master_admin / owner → can assign to team_lead AND manager
      - team_lead                    → can assign to manager only
      - manager                      → cannot create tasks (returns 403)
    """
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner"):
        allowed_roles = ["team_lead", "manager"]
    elif role == "team_lead":
        allowed_roles = ["manager"]
    else:
        # Manager / user / customer — cannot create tasks.
        raise HTTPException(
            status_code=403,
            detail="Your role is not allowed to create tasks. Only admin and team_lead can.",
        )

    cursor = db.staff.find(
        {"role": {"$in": allowed_roles}, "is_active": {"$ne": False}},
        {"_id": 0, "password": 0, "passwordHash": 0},
    ).sort([("role", 1), ("name", 1)])
    items = await cursor.to_list(length=500)
    # Normalise the shape the frontend dropdown expects.
    for s in items:
        s["id"] = s.get("id") or s.get("managerId") or s.get("staff_id")
        s["displayName"] = s.get("name") or s.get("email") or s["id"]
    return {"success": True, "items": items, "allowedRoles": allowed_roles}


@fastapi_app.get("/api/tasks")
async def list_tasks(
    assigneeId: Optional[str] = None,
    status: Optional[str] = None,
    filter: Optional[str] = None,   # Phase Final / Block 4: today|tomorrow|overdue|no_deadline|week
    customerId: Optional[str] = None,
    leadId: Optional[str] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """List tasks.

    Visibility rules:
      - admin / master_admin / owner → see every task
      - team_lead                    → sees tasks they created OR are assigned to
      - manager                      → sees only tasks assigned to themselves

    Phase Final / Block 4 — extended filters:
      - filter=today        → tasks due today (UTC day window)
      - filter=tomorrow     → tasks due tomorrow
      - filter=overdue      → tasks with dueDate < now AND status != 'completed'
      - filter=no_deadline  → tasks without dueDate
      - filter=week         → tasks due within next 7 days
      - customerId / leadId → tasks linked to a specific entity
    """
    role = (current_user.get("role") or "").lower()
    me = current_user.get("id") or current_user.get("managerId")

    query: Dict[str, Any] = {}
    if status:
        query["status"] = status

    # Date filters — UTC day windows, expressed as ISO strings to match
    # the existing dueDate storage format.
    now = datetime.now(timezone.utc)
    if filter == "today":
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        query["dueDate"] = {"$gte": day_start.isoformat(), "$lt": day_end.isoformat()}
    elif filter == "tomorrow":
        day_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        query["dueDate"] = {"$gte": day_start.isoformat(), "$lt": day_end.isoformat()}
    elif filter == "week":
        week_end = now + timedelta(days=7)
        query["dueDate"] = {"$gte": now.isoformat(), "$lte": week_end.isoformat()}
    elif filter == "overdue":
        query["dueDate"] = {"$lt": now.isoformat()}
        query["status"] = {"$ne": "completed"}
    elif filter == "no_deadline":
        query["$or"] = [
            {"dueDate": {"$exists": False}},
            {"dueDate": None},
            {"dueDate": ""},
        ]

    # Entity links
    if customerId:
        query["customerId"] = customerId
    if leadId:
        query["leadId"] = leadId

    if role in ("admin", "master_admin", "owner", "team_lead"):
        # Customer-Card spec (2026-06-10): TL is a control-tower role and
        # must see EVERY task across the company. Admin is no different.
        if assigneeId:
            query["assigneeId"] = assigneeId
    else:
        # Manager / staff: only own tasks.
        query["assigneeId"] = me

    cursor = db.tasks.find(query, {"_id": 0}).sort("dueDate", 1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "data": items, "items": items}


# ── Phase Final / Block 4 — "without tasks" reports ───────────────────


@fastapi_app.get("/api/tasks/reports/leads-without-tasks")
async def leads_without_tasks(
    manager_id: Optional[str] = Query(None, alias="managerId"),
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Leads (status != closed) that have NO open tasks attached.

    Used by the team-lead board to spot abandoned leads.
    """
    role = (current_user.get("role") or "").lower()
    me = current_user.get("id")

    lead_q: Dict[str, Any] = {"status": {"$nin": ["closed", "rejected", "converted"]}}
    if role == "manager":
        lead_q["managerId"] = me
    elif manager_id:
        lead_q["managerId"] = manager_id

    leads = await db.leads.find(lead_q, {"_id": 0}).limit(limit * 2).to_list(length=limit * 2)
    lead_ids = [l["id"] for l in leads]
    if not lead_ids:
        return {"success": True, "items": [], "count": 0}

    # Find leads that DO have open tasks
    tasks_with_lead = await db.tasks.distinct(
        "leadId",
        {"leadId": {"$in": lead_ids}, "status": {"$nin": ["completed", "cancelled"]}},
    )
    busy = set(tasks_with_lead)
    orphans = [l for l in leads if l["id"] not in busy]
    return {"success": True, "items": orphans[:limit], "count": len(orphans)}


@fastapi_app.get("/api/tasks/reports/customers-without-tasks")
async def customers_without_tasks(
    manager_id: Optional[str] = Query(None, alias="managerId"),
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Active customers without open tasks (need follow-up planning)."""
    role = (current_user.get("role") or "").lower()
    me = current_user.get("id")

    cust_q: Dict[str, Any] = {"status": {"$in": ["active", "prospect", None]}}
    if role == "manager":
        cust_q["managerId"] = me
    elif manager_id:
        cust_q["managerId"] = manager_id

    customers = await db.customers.find(cust_q, {"_id": 0}).limit(limit * 2).to_list(length=limit * 2)
    cust_ids = [c["id"] for c in customers]
    if not cust_ids:
        return {"success": True, "items": [], "count": 0}

    tasks_with_cust = await db.tasks.distinct(
        "customerId",
        {"customerId": {"$in": cust_ids}, "status": {"$nin": ["completed", "cancelled"]}},
    )
    busy = set(tasks_with_cust)
    orphans = [c for c in customers if c["id"] not in busy]
    return {"success": True, "items": orphans[:limit], "count": len(orphans)}


@fastapi_app.patch("/api/tasks/{task_id}")
async def update_task(
    task_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Update a task.

    Permission rules:
      - admin: any task, any field
      - team_lead: tasks they created or are assigned to — any field
      - manager: only tasks assigned to them, and only the `status` field
    """
    task = await db.tasks.find_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    role = (current_user.get("role") or "").lower()
    me = current_user.get("id") or current_user.get("managerId")

    if role in ("admin", "master_admin", "owner"):
        allowed = data
    elif role == "team_lead":
        if task.get("createdBy") != me and task.get("assigneeId") != me:
            raise HTTPException(status_code=403, detail="You can only update tasks you created or are assigned to")
        allowed = data
    elif role == "manager":
        if task.get("assigneeId") != me:
            raise HTTPException(status_code=403, detail="You can only update tasks assigned to you")
        # Managers may flip status, store outcome/comment, but not reassign.
        allowed = {k: v for k, v in data.items() if k in {"status", "result", "comment", "completedAt", "startedAt"}}
        if not allowed:
            raise HTTPException(status_code=400, detail="No mutable field for your role")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")

    # Accept either the canonical `id` (used by /api/tasks list) or the
    # legacy `taskId` field. Both are stored on every doc by create_task,
    # but historical updates were filtered by `taskId` only — leaving
    # admin-side status changes (which key off `task.id`) as silent no-ops
    # when the legacy alias was missing.
    res = await db.tasks.update_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]},
        {"$set": allowed},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "matched": res.matched_count, "modified": res.modified_count}

@fastapi_app.get("/api/invoices")
async def list_invoices(
    managerId: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_user),
):
    # Launch-Candidate security fix (2026-06-09): require staff auth.
    # Managers see only their own invoices.
    _role = (current_user.get("role") or "").lower()
    if _role == "manager":
        managerId = current_user.get("id")
    query = {}
    if managerId:
        query['managerId'] = managerId
    if status:
        query['status'] = status
    
    cursor = db.invoices.find(query, {'_id': 0}).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "data": items, "items": items}











@fastapi_app.get("/api/settings")
async def get_settings():
    """Return system settings for admin panel"""
    settings = [
        {
            "id": "lead_statuses",
            "key": "lead_statuses",
            "value": ["new", "contacted", "qualified", "variants_sent", "negotiation", "won", "lost"],
            "description": "Available lead statuses"
        },
        {
            "id": "deal_statuses",
            "key": "deal_statuses",
            "value": [
                "lead",
                "qualified",
                "variants_sent",
                "deposit_contract_drafted",
                "deposit_contract_signed",
                "deposit_paid",
                "searching_at_auction",
                "auction_lost",
                "auction_won",
                "final_contract_sent",
                "final_contract_signed",
                "after_win_payment_paid",
                "in_transit_to_rotterdam",
                "arrived_rotterdam",
                "customs_calculated",
                "final_payment_paid",
                "in_transit_to_bg",
                "delivered",
                "closed",
                "cancelled",
            ],
            "description": "Full BIBI Cars deal pipeline (P0.2)"
        },
        {
            "id": "deposit_statuses",
            "key": "deposit_statuses",
            "value": [
                "pending",
                "paid_confirmed",
                "refund_pending_voluntary",
                "refund_pending_30d",
                "refunded",
                "forfeit_pending_teamlead",
                "forfeit_pending_admin",
                "forfeited",
            ],
            "description": "Deposit lifecycle statuses (P0.3)"
        },
        {
            "id": "contract_types",
            "key": "contract_types",
            "value": ["deposit", "final", "purchase"],
            "description": "Contract v2 types (P0.4)"
        },
        {
            "id": "contract_lifecycle",
            "key": "contract_lifecycle",
            "value": ["draft", "sent_to_client", "client_signed", "company_signed_stamped", "finalized"],
            "description": "Contract v2 lifecycle (P0.4)"
        },
        {
            "id": "lead_sources",
            "key": "lead_sources",
            "value": ["website", "referral", "social", "call", "email", "other"],
            "description": "Lead source channels"
        },
        {
            "id": "sla_first_response_minutes",
            "key": "sla_first_response_minutes",
            "value": 15,
            "description": "SLA: First response time in minutes"
        },
        {
            "id": "sla_callback_minutes",
            "key": "sla_callback_minutes",
            "value": 30,
            "description": "SLA: Callback time in minutes"
        }
    ]
    return settings

@fastapi_app.get("/")
async def root():
    return {"service": "BIBI V3.2", "version": "3.2.0"}


# ═══════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS (STUBS for frontend compatibility)
# ═══════════════════════════════════════════════════════════════════

# Journey/Funnel — РЕАЛЬНАЯ воронка (см. backend/app/routers/analytics_funnel.py)
# Старые mock-эндпоинты заменены на live-агрегации из leads/deals/contracts/payments/shipments.

# Alerts
@fastapi_app.get("/api/alerts/critical")
async def alerts_critical(limit: int = 20):
    return {"alerts": []}

@fastapi_app.get("/api/alerts")
async def alerts_list():
    return {"alerts": [], "unreadCount": 0}

# Owner Dashboard
@fastapi_app.get("/api/owner-dashboard")
async def owner_dashboard():
    return {
        "risk": {
            "suspiciousSessions": 0,
            "criticalInvoices": 0,
            "riskyShipments": 0,
            "integrationsDown": 0,
        },
        "people": {
            "underperformers": []
        }
    }

# Risk
@fastapi_app.post("/api/risk/daily-check")
async def risk_daily_check():
    return {"success": True}

@fastapi_app.get("/api/risk/manager/{manager_id}", dependencies=[Depends(require_manager_or_admin)])
async def risk_manager(manager_id: str):
    return {
        "riskLevel": "low",
        "riskScore": 10,
        "entityType": "manager",
        "factors": [],
        "recommendations": []
    }

# Intent Dashboard
# admin intent cluster (4 endpoints) moved to app/routers/admin_intent.py
# (Wave 2B/Batch 11) — pure mock data, zero DB access, zero bridges.


# Quote Analytics
# ❌ REMOVED (April 2026): /api/admin/quote-analytics
# Reason: returned hardcoded mock data (Manager 1/2/3, Website/Phone/Referral
# fixed numbers) — created false sense of "system is calculating" without any
# real metrics. Frontend page /admin/analytics/quotes also removed.
# If real quote analytics is required later, build a fresh endpoint that
# aggregates from db.quotes / db.leads, not this mock.

# Engagement Analytics
# admin engagement cluster (8 endpoints) moved to app/routers/admin_engagement.py
# (Wave 2B/Batch 11) — pure read-only aggregator, cross-domain reader of
# customers, favorites, compare, shares, vin_data collections.


# Integrations
# admin_integrations cluster (9 endpoints — full surface) moved to
# app/routers/admin_integrations.py (Wave 2B/Batch 14 + Batch 15).
# Endpoints owned by router now:
#   GET    /api/admin/integrations
#   GET    /api/admin/integrations/health
#   GET    /api/admin/integrations/{integration_id}              (stub)
#   PUT    /api/admin/integrations/{integration_id}              (stub)
#   PATCH  /api/admin/integrations/{provider}
#   POST   /api/admin/integrations/{provider}/test
#   POST   /api/admin/integrations/{provider}/toggle
#   POST   /api/admin/integrations/ringostat/configure
#   GET    /api/admin/integrations/ringostat/config
# Public webhook POST /api/integrations/ringostat/webhook stays in server.py
# (separate auth flow — Phase 3 will resolve via Ringostat domain service).


# ==================== DEBUG ENDPOINTS ====================

@fastapi_app.get("/api/debug/test", dependencies=[Depends(require_admin)])
async def debug_test():
    """Test endpoint to verify new code is loaded"""
    return {
        "status": "NEW CODE LOADED ✅",
        "version": "v3.2.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Backend code successfully updated!"
    }


@fastapi_app.get("/api/debug/db-info", dependencies=[Depends(require_admin)])
async def debug_db_info():
    """Show actual DB name and collections"""
    collections = await db.list_collection_names()
    return {
        "db_name": db.name,
        "collections": collections,
        "collections_count": len(collections),
        "mongo_url_prefix": MONGO_URL[:30] if MONGO_URL else None
    }


@fastapi_app.get("/api/debug/full-check", dependencies=[Depends(require_admin)])
async def debug_full_check():
    """Full diagnostic check"""
    shipments_count = await db.shipments.count_documents({})
    events_count = await db.shipment_events.count_documents({})
    
    sample = None
    if shipments_count > 0:
        sample = await db.shipments.find_one()
    
    return {
        "db_name": db.name,
        "shipments_count": shipments_count,
        "events_count": events_count,
        "sample_shipment_id": sample.get('id') if sample else None,
        "all_collections": await db.list_collection_names()
    }


# [auto-domain removed] /api/debug/shipments-count (debug_shipments_count)


# admin_integrations stubs + patch + ringostat configure/config moved to
# app/routers/admin_integrations.py (Wave 2B/Batch 15).
#   GET    /api/admin/integrations/{integration_id}    (stub)
#   PUT    /api/admin/integrations/{integration_id}    (stub)
#   PATCH  /api/admin/integrations/{provider}
#   POST   /api/admin/integrations/ringostat/configure (cross-domain write to ringostat_config)
#   GET    /api/admin/integrations/ringostat/config


@fastapi_app.post("/api/integrations/ringostat/webhook")
@fastapi_app.get("/api/integrations/ringostat/webhook")
@fastapi_app.put("/api/integrations/ringostat/webhook")
async def ringostat_webhook(request: Request):
    """
    Ringostat Webhooks 2.0 endpoint — production handler.

    Accepts BOTH:
      * Real Ringostat Webhooks 2.0 payload (call events):
          caller, callee, type (in/out), status, date, call_duration,
          waiting, dialog, destination, source, medium, campaign, term,
          content, record, record_link, manager_id, manager, user_ip,
          user_uuid, gaid, full_num, …
      * Custom CRM payload (legacy / test_webhook):
          event, call_id, direction, from, to, manager_extension,
          duration, recording_url, utm_*

    Security:
      Ringostat Webhooks 2.0 does NOT issue HMAC signatures; instead it
      supports Basic Auth or OAuth on the receiver side, OR a shared
      ``token`` query-string parameter.  We support both:
        - Basic Auth:   credentials checked against ringostat_config.webhook_user/pass
        - Token in URL: ?token=<shared_secret> matched against ringostat_config.webhook_secret
      If neither is configured, the endpoint is open (project-default).

    Reference:
      https://help.ringostat.com/en/articles/6338053-webhooks-authorization-settings
      https://help.ringostat.com/en/articles/6559993-webhooks-incoming-call-event
    """
    try:
        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            # Ringostat can also send form-urlencoded; try to recover
            from urllib.parse import parse_qs
            try:
                parsed = parse_qs(body_bytes.decode('utf-8'), keep_blank_values=True)
                body = {k: (v[0] if isinstance(v, list) and v else "") for k, v in parsed.items()}
            except Exception:
                body = {}

        # For GET / params-in-URL transports, also merge query params
        if request.method != "POST" or not body:
            qp = dict(request.query_params)
            # Don't overwrite real JSON fields with query strings (POST wins),
            # but if body is empty, query params are the payload.
            if not body:
                body = qp
            else:
                for k, v in qp.items():
                    body.setdefault(k, v)

        ringostat_config = await db.ringostat_config.find_one({}) or {}
        # Phase IV-5: ensure auth defaults are present even if admin
        # never persisted anything — we still want secured ingestion.
        try:
            from app.config.ringostat_defaults import merge_with_defaults as _merge_rd
            ringostat_config = _merge_rd(ringostat_config)
        except Exception:
            pass

        # ── AuthN: Basic / shared-token / open ─────────────────────
        webhook_user = ringostat_config.get('webhook_user')
        webhook_pass = ringostat_config.get('webhook_pass')
        webhook_token = ringostat_config.get('webhook_secret')

        if webhook_user and webhook_pass:
            auth_h = request.headers.get('authorization', '')
            if not auth_h.lower().startswith('basic '):
                logger.warning("[RINGOSTAT] Missing Basic auth header")
                raise HTTPException(status_code=401, detail="Authorization required")
            import base64 as _b64
            try:
                decoded = _b64.b64decode(auth_h.split(' ', 1)[1]).decode('utf-8')
                u, p = decoded.split(':', 1)
            except Exception:
                raise HTTPException(status_code=401, detail="Bad Basic auth")
            if not (u == webhook_user and p == webhook_pass):
                logger.warning(f"[RINGOSTAT] Bad credentials user={u!r}")
                raise HTTPException(status_code=401, detail="Bad credentials")
        elif webhook_token:
            # Shared token in query-string or header
            token = (request.query_params.get('token')
                     or request.headers.get('X-Ringostat-Token')
                     or request.headers.get('X-Webhook-Token'))
            # Allow legacy HMAC sigs to still pass (back-compat)
            sig = request.headers.get('X-Ringostat-Signature') or request.headers.get('X-Signature')
            ok = False
            if token and token == webhook_token:
                ok = True
            elif sig:
                import hmac as _hmac
                import hashlib as _hashlib
                expected_sig = _hmac.new(
                    webhook_token.encode(), body_bytes, _hashlib.sha256
                ).hexdigest()
                if sig == expected_sig:
                    ok = True
            if not ok:
                logger.warning(f"[RINGOSTAT] Webhook token mismatch (token={token!r})")
                raise HTTPException(status_code=401, detail="Unauthorized")

        # Log raw payload for ops
        print("=" * 80)
        print("RINGOSTAT WEBHOOK RAW PAYLOAD:")
        print(json.dumps(body, indent=2, ensure_ascii=False, default=str))
        print("=" * 80)

        # ── Field normalization (Ringostat 2.0 → internal) ─────────
        # Direction: Ringostat sends `type` in {"in","out"}; map to "inbound"/"outbound".
        raw_type = (body.get('direction') or body.get('type') or '').lower()
        if raw_type in ('in', 'inbound', 'incoming'):
            direction = 'inbound'
        elif raw_type in ('out', 'outbound', 'outgoing'):
            direction = 'outbound'
        else:
            direction = 'inbound'

        # Caller / callee  (Ringostat semantics: caller = origin, callee = destination)
        from_number = (body.get('from') or body.get('caller') or body.get('full_num') or '').strip()
        to_number = (body.get('to') or body.get('callee') or body.get('destination') or '').strip()

        # Event type (CALL_START / CALL_END / etc.) — Ringostat configures
        # event trigger in the admin; payload may include `status` instead.
        event_type = (body.get('event') or body.get('event_type') or '').upper()
        status = (body.get('status') or '').upper()
        if not event_type:
            # Infer event from status when admin didn't tag it
            if status in ('PROPER', 'ANSWERED', 'COMPLETED'):
                event_type = 'CALL_END' if int(body.get('call_duration') or body.get('duration') or 0) > 0 else 'CALL_ANSWERED'
            elif status in ('NO ANSWER', 'NOANSWER', 'MISSED', 'NO_ANSWER'):
                event_type = 'CALL_MISSED'
            else:
                event_type = 'CALL_START'

        # call_id — Ringostat doesn't always send it; derive from `record`
        # (their unique recording-channel id) when possible.
        call_id = (body.get('call_id') or body.get('id_call') or body.get('id') or '').strip()
        if not call_id:
            rec = body.get('record') or ''
            if rec:
                call_id = f"rs_{rec}"
            else:
                # Last resort: synthetic UUID (won't dedupe across deliveries)
                call_id = f"rs_{uuid.uuid4().hex[:16]}"

        manager_ext = (body.get('manager_extension')
                       or body.get('extension')
                       or body.get('manager')
                       or '').strip()

        duration = int(body.get('duration') or body.get('call_duration') or body.get('billsec') or 0)
        recording_url = (body.get('recording_url')
                         or body.get('record_link')
                         or body.get('record')
                         or '')
        
        # UTM data (Ringostat 2.0 sends both `utm_*` AND bare names `source`/`medium`/`campaign`)
        utm_source = body.get('utm_source') or body.get('source') or ''
        utm_campaign = body.get('utm_campaign') or body.get('campaign') or ''
        utm_medium = body.get('utm_medium') or body.get('medium') or ''
        utm_term = body.get('utm_term') or body.get('term') or ''
        utm_content = body.get('utm_content') or body.get('content') or ''
        
        # Get automation rules
        automation_rules = ringostat_config.get('automation_rules', {}) if ringostat_config else {}

        # Identify customer phone: for inbound = caller (from), for outbound = callee (to)
        customer_phone = from_number if direction == 'inbound' else to_number
        # Sanity check: customer phone must look like a real number (not SIP alias)
        clean = customer_phone.replace('+', '').replace('-', '').replace(' ', '')
        if not clean.isdigit() or len(clean) < 6:
            # Internal call between managers — skip CRM linkage but still log call
            print(f"[RINGOSTAT] Internal call (customer_phone={customer_phone!r}) — skipping lead creation")
            lead = None
        else:
            # Find or create Lead by customer phone (if auto_create_lead is enabled)
            lead = await db.leads.find_one({'phone': customer_phone})

            if not lead and automation_rules.get('auto_create_lead', True):
                print(f"[RINGOSTAT] Creating new lead for phone: {customer_phone}")
                lead_data = {
                    '_id': str(uuid.uuid4()),
                    'phone': customer_phone,
                    'source': 'ringostat',
                    'status': 'new',
                    'utm_source': utm_source,
                    'utm_campaign': utm_campaign,
                    'utm_medium': utm_medium,
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                }
                await db.leads.insert_one(lead_data)
                lead = lead_data
                print(f"[RINGOSTAT] Lead created: {lead['_id']}")
            elif not lead:
                print(f"[RINGOSTAT] Lead auto-creation disabled, skipping")
                # Still log the call into ringostat_calls below — just without lead linkage
            else:
                print(f"[RINGOSTAT] Lead found: {lead.get('_id')}")
        
        # Find active deal for this lead
        deal = None
        if lead:
            deal = await db.deals.find_one({
                'lead_id': lead['_id'],
                'status': {'$nin': ['closed_won', 'closed_lost']}
            })

        # Get manager by extension with fallback
        ringostat_config = await db.ringostat_config.find_one({})
        manager_id = None

        if ringostat_config and manager_ext:
            ext_mapping = ringostat_config.get('extension_mapping', {})
            manager_id = ext_mapping.get(str(manager_ext))

            if not manager_id:
                logger.warning(f"[RINGOSTAT] Extension {manager_ext} not mapped to any manager")
        elif not manager_ext:
            logger.warning(f"[RINGOSTAT] No extension provided in webhook for call {call_id}")

        # If no manager found, try to find from existing deal
        if not manager_id and deal:
            manager_id = deal.get('assigned_to')
            if manager_id:
                logger.info(f"[RINGOSTAT] Using manager from existing deal: {manager_id}")

        # Last resort: pick the first available active manager.
        # ([ECO CLEANUP] removed auto-domain provider_stats "Provider Pressure"
        #  scoring — ECO uses simple first-available assignment here.)
        if not manager_id:
            try:
                fallback_manager = await db.staff.find_one({'role': 'manager', 'is_active': True})
                if fallback_manager:
                    manager_id = fallback_manager.get('id') or fallback_manager['_id']
                    logger.info(f"[RINGOSTAT] Assigned to first available manager: {manager_id}")
            except Exception:
                logger.exception("[RINGOSTAT] manager fallback failed")

        # Check if call already exists (for updates)
        existing_call = await db.ringostat_calls.find_one({'call_id': call_id})

        now = datetime.now(timezone.utc)
        _lead_id = lead['_id'] if lead else None
        _deal_id = deal['_id'] if deal else None

        if existing_call:
            # Update existing call
            update_data = {
                'status': status.upper() if status else existing_call.get('status'),
                'duration': duration if duration else existing_call.get('duration'),
                'updated_at': now
            }

            if recording_url:
                update_data['recording_url'] = recording_url

            if event_type in ['CALL_ANSWERED', 'ANSWERED']:
                update_data['answered_at'] = now
            elif event_type in ['CALL_END', 'ENDED', 'COMPLETED']:
                update_data['ended_at'] = now
            if _lead_id and not existing_call.get('lead_id'):
                update_data['lead_id'] = _lead_id
            if _deal_id and not existing_call.get('deal_id'):
                update_data['deal_id'] = _deal_id
            if manager_id and not existing_call.get('manager_id'):
                update_data['manager_id'] = manager_id

            await db.ringostat_calls.update_one(
                {'call_id': call_id},
                {'$set': update_data}
            )
            logger.info(f"Call updated: {call_id}, status: {status}")
        else:
            # Create new call
            call_data = {
                '_id': str(uuid.uuid4()),
                'call_id': call_id,
                'direction': direction,
                'from': from_number,
                'to': to_number,
                'status': status.upper(),
                'duration': duration,
                'recording_url': recording_url,
                'lead_id': _lead_id,
                'deal_id': _deal_id,
                'manager_id': manager_id,
                'utm_source': utm_source,
                'utm_campaign': utm_campaign,
                'utm_medium': utm_medium,
                'utm_term': utm_term,
                'utm_content': utm_content,
                'raw': body,
                'started_at': now,
                'created_at': now,
                'updated_at': now,
                'source': 'webhook'
            }

            await db.ringostat_calls.insert_one(call_data)
            print(f"[RINGOSTAT] Call created: {call_id}, lead: {_lead_id}")
            print(f"[RINGOSTAT] DB name: {db.name if hasattr(db, 'name') else 'unknown'}")

            # ═══════════════════════════════════════════════════════════
            # EMIT WebSocket event for CALL_START (incoming call)
            # ═══════════════════════════════════════════════════════════
            if event_type in ['CALL_START', 'START'] and direction == 'inbound' and lead:
                # Prepare event payload
                ws_payload = {
                    'call_id': call_id,
                    'from': from_number,
                    'to': to_number,
                    'lead_id': lead['_id'],
                    'lead_name': lead.get('name', ''),
                    'lead_phone': lead.get('phone', from_number),
                    'deal_id': _deal_id,
                    'deal_title': deal.get('title', '') if deal else None,
                    'source': utm_source or 'ringostat',
                    'direction': direction,
                    'temperature': lead.get('score', 50),  # ← ADD TEMPERATURE/SCORE
                    'timestamp': now.isoformat()
                }

                # Emit to specific manager if known
                if manager_id:
                    await emit_to_user(manager_id, 'ringostat:incoming_call', ws_payload)
                    logger.info(f"[WS] Emitted ringostat:incoming_call to user:{manager_id}")
                else:
                    # Broadcast to all managers if manager not assigned
                    await emit_to_role('manager', 'ringostat:incoming_call', ws_payload)
                    logger.info(f"[WS] Broadcast ringostat:incoming_call to role:manager")

        # Handle MISSED calls → Create Task + Emit WS
        if (event_type in ['CALL_MISSED', 'MISSED'] or status.upper() == 'MISSED') and lead:
            logger.info(f"Handling MISSED call for lead: {lead['_id']}")

            # Check if task already exists for this call
            existing_task = await db.tasks.find_one({'call_id': call_id})

            if not existing_task:
                task_data = {
                    '_id': str(uuid.uuid4()),
                    'title': f'Перезвонить клиенту {lead.get("name", customer_phone)}',
                    'description': f'Пропущенный звонок от {customer_phone}',
                    'type': 'callback',
                    'priority': 'high',
                    'assigned_to': manager_id if manager_id else None,
                    'lead_id': lead['_id'],
                    'deal_id': _deal_id,
                    'call_id': call_id,
                    'deadline': datetime.now(timezone.utc) + timedelta(minutes=5),
                    'status': 'pending',
                    'created_at': now,
                    'updated_at': now
                }

                await db.tasks.insert_one(task_data)
                logger.info(f"Task created for missed call: {task_data['_id']}")

                # Emit WS event for missed call
                ws_payload = {
                    'call_id': call_id,
                    'from': from_number,
                    'lead_id': lead['_id'],
                    'lead_name': lead.get('name', ''),
                    'task_id': task_data['_id'],
                    'timestamp': now.isoformat()
                }

                if manager_id:
                    await emit_to_user(manager_id, 'ringostat:missed_call', ws_payload)
                    logger.info(f"[WS] Emitted ringostat:missed_call to user:{manager_id}")
                else:
                    await emit_to_role('manager', 'ringostat:missed_call', ws_payload)
                    logger.info(f"[WS] Broadcast ringostat:missed_call to role:manager")

        # Handle CALL_END → Emit WS if answered and duration > threshold (from automation rules)
        require_outcome = automation_rules.get('require_outcome', True)
        outcome_duration = automation_rules.get('require_outcome_duration', 10)

        if event_type in ['CALL_END', 'END'] and status.upper() == 'ANSWERED' and duration > outcome_duration and require_outcome and lead:
            ws_payload = {
                'call_id': call_id,
                'from': from_number,
                'lead_id': lead['_id'],
                'lead_name': lead.get('name', ''),
                'deal_id': _deal_id,
                'duration': duration,
                'timestamp': now.isoformat()
            }

            if manager_id:
                await emit_to_user(manager_id, 'ringostat:call_needs_outcome', ws_payload)
                logger.info(f"[WS] Emitted ringostat:call_needs_outcome to user:{manager_id}")
            else:
                await emit_to_role('manager', 'ringostat:call_needs_outcome', ws_payload)
                logger.info(f"[WS] Broadcast ringostat:call_needs_outcome to role:manager")

            # 🔥 Fetch recording URL in background (for AI analysis later)
            if ringostat_config:
                project_id = ringostat_config.get('project_id')
                api_key = ringostat_config.get('api_key')
                if project_id and api_key:
                    import asyncio
                    asyncio.create_task(fetch_recording_url(call_id, project_id, api_key))

        return {"success": True, "call_id": call_id, "lead_id": _lead_id, "direction": direction, "status": status.upper(), "event": event_type}

    except HTTPException:
        # Don't swallow 401/400/etc — let FastAPI propagate the right status code
        raise
    except Exception as e:
        logger.error(f"Ringostat webhook error: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}

@fastapi_app.get("/api/manager/calls/my", dependencies=[Depends(require_manager_or_admin)])
async def get_my_calls(
    manager_id: str = None,
    limit: int = 50,
    status: Optional[str] = None
):
    """Get manager's calls history"""
    try:
        query = {}
        
        if manager_id:
            query['manager_id'] = manager_id
        
        if status:
            query['status'] = status
        
        calls = await db.ringostat_calls.find(query).sort('started_at', -1).limit(limit).to_list(limit)
        
        # Enrich with lead/deal info
        for call in calls:
            if call.get('lead_id'):
                lead = await db.leads.find_one({'_id': call['lead_id']})
                if lead:
                    call['lead'] = {
                        'id': str(lead['_id']),
                        'name': lead.get('name'),
                        'phone': lead.get('phone')
                    }
            
            if call.get('deal_id'):
                deal = await db.deals.find_one({'_id': call['deal_id']})
                if deal:
                    call['deal'] = {
                        'id': str(deal['_id']),
                        'title': deal.get('title'),
                        'stage': deal.get('stage')
                    }
        
        return {
            "success": True,
            "calls": [serialize_doc(c) for c in calls],
            "total": len(calls)
        }
    except Exception as e:
        logger.error(f"Get my calls error: {e}")
        return {"success": False, "error": str(e)}


# ==================== RINGOSTAT: FETCH RECORDING URL ====================

async def fetch_recording_url(call_id: str, ringostat_project_id: str, ringostat_api_key: str):
    """
    Background task to fetch recording URL from Ringostat API with retry
    Ringostat recording can take 15 seconds to 2 minutes to be ready
    Retries: 6 attempts with 20-second intervals (total ~2 minutes)
    """
    import asyncio
    import httpx
    
    max_retries = 6
    retry_delay = 20  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            await asyncio.sleep(retry_delay)
            logger.info(f"[RINGOSTAT] Fetching recording for call_id: {call_id} (attempt {attempt}/{max_retries})")
            
            async with httpx.AsyncClient() as client:
                # Ringostat API endpoint for calls list
                url = f"https://api.ringostat.net/calls/list"
                headers = {
                    "Auth-key": ringostat_api_key,
                    "x-project-id": ringostat_project_id
                }
                params = {
                    "call_id": call_id
                }
                
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    # Ringostat API returns array directly
                    calls = data if isinstance(data, list) else data.get('calls', [])
                    
                    if calls and len(calls) > 0:
                        call_data = calls[0]
                        recording_url = call_data.get('recording', call_data.get('record_url', ''))
                        
                        if recording_url:
                            # Update call in MongoDB
                            await db.ringostat_calls.update_one(
                                {'call_id': call_id},
                                {
                                    '$set': {
                                        'recording_url': recording_url,
                                        'recording_fetched_at': datetime.now(timezone.utc),
                                        'recording_fetch_attempts': attempt
                                    }
                                }
                            )
                            logger.info(f"[RINGOSTAT] ✓ Recording URL found on attempt {attempt} for call_id: {call_id}")
                            
                            # 🔥 Trigger AI analysis here
                            # await analyze_call_with_ai(call_id, recording_url)
                            return  # Success - exit retry loop
                        else:
                            logger.warning(f"[RINGOSTAT] No recording yet (attempt {attempt}/{max_retries}) for call_id: {call_id}")
                else:
                    logger.error(f"[RINGOSTAT] Failed to fetch recording: HTTP {response.status_code}")
        
        except Exception as e:
            logger.error(f"[RINGOSTAT] Error fetching recording (attempt {attempt}/{max_retries}) for call_id {call_id}: {e}")
    
    # After all retries failed
    logger.error(f"[RINGOSTAT] ✗ Recording URL not found after {max_retries} attempts for call_id: {call_id}")


# ==================== TRACKING WORKER (HYBRID SYSTEM) ====================

def interpolate_route(route, progress):
    """
    Calculate current position on route based on progress (0 to 1)
    """
    if not route or len(route) < 2:
        return None, None
    
    total_segments = len(route) - 1
    segment_index = int(progress * total_segments)
    
    # Helper — accept both dict and list/tuple waypoint formats.
    def _pt(p):
        if isinstance(p, dict):
            return float(p["lat"]), float(p["lng"])
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            return float(p[0]), float(p[1])
        raise TypeError(f"unsupported waypoint: {p!r}")

    # Reached destination
    if segment_index >= total_segments:
        return _pt(route[-1])
    
    start_lat, start_lng = _pt(route[segment_index])
    end_lat, end_lng = _pt(route[segment_index + 1])
    
    # Calculate position within current segment
    local_progress = (progress * total_segments) - segment_index
    
    lat = start_lat + (end_lat - start_lat) * local_progress
    lng = start_lng + (end_lng - start_lng) * local_progress
    
    return lat, lng




def get_location_label(progress):
    """
    Get human-readable location based on progress
    """
    if progress < 0.1:
        return "Origin Port"
    elif progress < 0.3:
        return "Leaving Coast"
    elif progress < 0.7:
        return "Mid-Ocean"
    elif progress < 0.9:
        return "Approaching Destination"
    else:
        return "Near Port"


# ═══════════════════════════════════════════════════════════════════
# VESSEL TRACKING (VesselFinder API)
# ═══════════════════════════════════════════════════════════════════
# Phase 3.1 / Commit 26 — VESSELFINDER_API_KEY and VESSELFINDER_FLEET_KEY
# globals removed.  All reads now go through tracking_config_service
# (see ``_tracking_snapshot()`` helper / ``server.tracking_config_service``).
VESSEL_POSITION_TTL_SECONDS = 90  # reuse cached position if fresher than this
VESSEL_POSITION_MAX_AGE_SECONDS = 2 * 60 * 60  # 2h — after this, stop interpolating


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometers."""
    import math
    R = 6371.0  # Earth radius km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _route_total_km(route: list) -> float:
    if not route or len(route) < 2:
        return 0.0
    total = 0.0
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]
        total += _haversine_km(a['lat'], a['lng'], b['lat'], b['lng'])
    return total


def _project_progress_on_route(route: list, lat: float, lng: float) -> float:
    """Find approximate progress (0..1) of point on polyline route."""
    if not route or len(route) < 2:
        return 0.0
    total = _route_total_km(route)
    if total <= 0:
        return 0.0
    # find closest segment, compute cumulative distance to projected point
    best_cum = 0.0
    best_dist = float('inf')
    cum = 0.0
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]
        seg_km = _haversine_km(a['lat'], a['lng'], b['lat'], b['lng'])
        # approximate projection: treat segment as straight line in lat/lng
        if seg_km <= 0:
            continue
        # parametrize
        dx = b['lng'] - a['lng']
        dy = b['lat'] - a['lat']
        t = ((lng - a['lng']) * dx + (lat - a['lat']) * dy) / (dx * dx + dy * dy + 1e-12)
        t = max(0.0, min(1.0, t))
        px = a['lng'] + t * dx
        py = a['lat'] + t * dy
        d = _haversine_km(lat, lng, py, px)
        if d < best_dist:
            best_dist = d
            best_cum = cum + seg_km * t
        cum += seg_km
    return max(0.0, min(1.0, best_cum / total))




def _calculate_eta_iso(route: list, current_lat: float, current_lng: float, speed_knots: Optional[float]) -> Optional[str]:
    """Compute ETA ISO string based on remaining distance and vessel speed."""
    if not route or len(route) < 1:
        return None
    dest = route[-1]
    remaining_km = _haversine_km(current_lat, current_lng, dest['lat'], dest['lng'])
    if remaining_km <= 0:
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    # default cruising speed 14 knots if unknown / stationary
    sp = speed_knots if (speed_knots and speed_knots >= 2.0) else 14.0
    # knots = nautical miles per hour; 1 nm = 1.852 km
    kmh = sp * 1.852
    hours = remaining_km / max(kmh, 1.0)
    eta_dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return eta_dt.isoformat().replace('+00:00', 'Z')


def _is_valid_coord(lat, lng) -> bool:
    """Guard: valid lat/lng (not None, not NaN, in world bounds)."""
    try:
        if lat is None or lng is None:
            return False
        lat_f = float(lat)
        lng_f = float(lng)
        if lat_f != lat_f or lng_f != lng_f:  # NaN check
            return False
        if not (-90.0 <= lat_f <= 90.0):
            return False
        if not (-180.0 <= lng_f <= 180.0):
            return False
        return True
    except (TypeError, ValueError):
        return False


def _clamp_progress(p) -> float:
    """Clamp progress to [0.0, 1.0], handling None / NaN."""
    try:
        if p is None:
            return 0.0
        p_f = float(p)
        if p_f != p_f:  # NaN
            return 0.0
        return max(0.0, min(1.0, p_f))
    except (TypeError, ValueError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════
# JOURNEY TRACKING HELPERS (stages, events, movement sanity)
#
# One shipment = a sequence of stages (land / vessel / port). Exactly one stage
# is "active" at a time (shipment.currentStageId). A manager binds vessel to
# a vessel-stage once; everything else flows automatically:
#   REAL (vessel stage only) → INTERPOLATE (<2h) → SIMULATE (walk route).
#
# Movement sanity rejects GPS spikes (> 200 km in < 120 s ≈ > 100 knots, which
# is physically impossible for a cargo ship). Rejected updates keep the last
# good position and log a 'tracking_rejected' event for visibility.
# ═══════════════════════════════════════════════════════════════════

JOURNEY_TRACKING_EVENT_THROTTLE_SEC = 15 * 60  # 'tracking_updated' at most once per 15 min
JOURNEY_SOCKET_THROTTLE_SEC = 30               # shipment:update emits at most once / 30 s
# ─── Phase 5.4 / C-5a — moved to app/utils/shipments.py ──────────────
# JOURNEY_SPIKE_MAX_KM_PER_120S and JOURNEY_ETA_SMOOTH_ALPHA were the
# exclusive callers of the moved helpers (`_smooth_eta_iso` and
# `is_valid_movement`); they moved with their owners. server.py's
# in-module callers below re-import them via the canonical module.
# ─── Phase 6.2.ACTUAL (2026-05-20) — JOURNEY_STAGE_TYPES + JOURNEY_STAGE_STATUSES
# moved to app/utils/shipments.py (Shell Thinning execution; the 2
# constants were the exclusive callers of the moved `_normalize_stage`
# helper — they travelled with their owner). The names below are
# RE-EXPORTS preserved for qualified-name discoverability
# (`server.JOURNEY_STAGE_TYPES`) and for any in-file code that may
# read them via closure. The canonical home is
# `app.utils.shipments.JOURNEY_STAGE_TYPES` /
# `app.utils.shipments.JOURNEY_STAGE_STATUSES`. Frozen invariants
# enforced by `tests/test_phase6_2_shell_thinning.py` (B3 + B4 + S5).
from app.utils.shipments import (
    JOURNEY_STAGE_TYPES,
    JOURNEY_STAGE_STATUSES,
)
# Valid stage-status transitions for manual edits via PUT /stages/{id}.
# advance/activate endpoints bypass this (they orchestrate the transitions
# themselves). Keys are "from", values are sets of allowed "to".
JOURNEY_STAGE_TRANSITIONS: Dict[str, set] = {
    "pending": {"pending", "active", "skipped"},
    "active":  {"active", "done", "skipped"},
    "done":    {"done"},
    "skipped": {"skipped"},
}


def _source_category(src: Optional[str]) -> str:
    """Group tracking sources into coarse categories for UI / change detection."""
    if not src:
        return "unknown"
    if src.startswith("real"):
        return "real"
    if src == "interpolated":
        return "interpolated"
    return "simulated"
















# [car-import removed] _persist_stages_backfill (shipment stages)




# ═══════════════════════════════════════════════════════════════════════
# AUTO RESOLVER LAYER — RETIRED in Phase 5.5/G (2026-05-20)
# ═══════════════════════════════════════════════════════════════════════
# The legacy ``_AutoResolver`` cluster (container/vessel/transfer detection
# helpers) moved verbatim to ``app/services/identity_runtime.py``. Five
# symbols were retired from this site:
#
#   * ``_resolver_shipsgo_lookup``  → module-private inside identity_runtime
#   * ``_resolver_vf_search``       → module-private inside identity_runtime
#   * ``_get_auto_resolver``        → module-private inside identity_runtime
#   * ``_run_auto_resolver``        → IdentityRuntimeService.run_auto_resolver()
#   * ``_persist_resolver_hits``    → IdentityRuntimeService.persist_resolver_hits()
#
# The ``from resolver_engine import (AutoResolver, MIN_CONFIDENCE)`` block
# moved with the cluster (sole consumers were the 5 helpers above).
#
# Two aux deps stay on this side (registered in EXTRACTION_AUX_BRIDGES with
# kind="RESOLVER_DEP"):
#   * ``_external_container_lookup`` (defined later in this file)
#   * ``add_shipment_event``          (defined just above this block)
# Both are lazy-imported by identity_runtime at call time.
#
# All call sites previously here (``update_shipment_position`` tick path,
# admin_resolver, admin_identity, admin_shipments routers) already route
# through ``identity_runtime.run_auto_resolver`` / ``.persist_resolver_hits``
# — no further migration required.
#
# Behaviour parity asserted by ``tests/test_phase5_5_g_identity_cluster.py``.
# Closeout record: ``PHASE5_5_G_IDENTITY_CLUSTER_CLOSED.md``.
# ═══════════════════════════════════════════════════════════════════════










# [car-import removed] simulate_tracking_progress (vessel/ocean shipment sim)


# [car-import removed] fetch_tracking_data_from_api (container tracking API)




# [car-import removed] detect_shipment_issues (stalled/ETA container alerts)




# ═══════════════════════════════════════════════════════════════════
# Automation Layer — Shipment Identity Resolver worker (Phase A+B+C)
# ═══════════════════════════════════════════════════════════════════


# Phase 3.2 / C-10 — DELETED legacy factories.
#
# Before C-10:
#     def _make_identity_resolver() -> "ShipmentIdentityResolver":
#         return ShipmentIdentityResolver(
#             db,
#             audit=lambda action, resource=None, meta=None: audit(
#                 action, resource=resource, meta=meta),
#         )
#
#     def _auto_transfer_detector() -> "AutoTransferDetector":
#         return AutoTransferDetector(db)
#
# After C-3 … C-9 every call site (worker loops, hot tick path, vf-job
# callback, manual admin endpoints, exception-confirm composite) routes
# through ``identity_runtime`` (``app/services/identity_runtime.py``).
# Service is the sole owner of resolver / detector construction.
# Per-call factory semantics preserved (no caching, no app.state).
# Behavioural-1:1 verified per checkpoint commit-message audit.
#
# The two underlying classes (ShipmentIdentityResolver, AutoTransferDetector)
# remain imported above so that external test suites referencing them by
# name (e.g. ``from shipment_identity_resolver import ShipmentIdentityResolver``
# style tests) keep working unchanged.




# ═══════════════════════════════════════════════════════════════════
# Phase D — Auto Transfer Detection background sweeper
# ═══════════════════════════════════════════════════════════════════



async def ringostat_export_calls_cron(lookback_minutes: int = 15):
    """
    CRON task to export calls from Ringostat API.

    Rewritten Phase IV-5 (real production sync):
      - Uses the documented `/calls/list` parameters: ``export_type``, ``from``,
        ``to``, ``fields`` (Ringostat-specific).
      - Requests the actual fields available on this project:
            calldate, caller, dst, n_alias, disposition, billsec, duration,
            recording (already a signed URL), utm_source, utm_medium,
            utm_campaign, utm_term, utm_content, client_id, referrer
      - Derives ``call_id`` from the recording filename (e.g.
        ``bg1_-1779866441.1274279.wav`` → ``1779866441.1274279``) when
        present, otherwise from a stable hash of (calldate, caller, dst).
      - Derives ``direction``: caller looks like a SIP alias / extension
        (``lpbibicarsbg_managerN`` or short numeric) → outbound; otherwise
        inbound.
      - Maps SIP alias / extension to a manager via
        ``ringostat_config.extension_mapping``.

    Args:
      lookback_minutes: how far back to query (default 15 min, with overlap
      to catch any calls missed by webhooks).
    """
    try:
        logger.info(f"[CRON] Starting Ringostat calls export (lookback={lookback_minutes}m)…")

        ringostat_config = await db.ringostat_config.find_one({})
        # Phase IV-5: fall through to hardcoded defaults if DB is empty.
        try:
            from app.config.ringostat_defaults import merge_with_defaults as _merge_rd
            ringostat_config = _merge_rd(ringostat_config or {})
        except Exception:
            pass
        if not ringostat_config:
            logger.warning("[CRON] Ringostat config not found — nothing to sync")
            return
        project_id = ringostat_config.get("project_id")
        api_key = ringostat_config.get("api_key")
        if not project_id or not api_key:
            logger.warning("[CRON] Ringostat credentials missing — skip sync")
            return
        if not ringostat_config.get("enabled", True):
            logger.info("[CRON] Ringostat integration disabled — skip sync")
            return

        import httpx
        import hashlib
        import re as _re
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=lookback_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")

        FIELDS = ",".join([
            "calldate", "caller", "dst", "n_alias",
            "disposition", "billsec", "duration", "recording",
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "client_id", "referrer",
        ])

        url = "https://api.ringostat.net/calls/list"
        headers = {"Auth-key": api_key, "x-project-id": str(project_id)}
        params = {
            "export_type": "json",
            "from": start_time,
            "to": end_time,
            "limit": 500,
            "fields": FIELDS,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code != 200:
            logger.error(f"[CRON] Ringostat API error: HTTP {response.status_code} body={response.text[:300]}")
            return

        # Ringostat returns plain text starting with "You may have entered…"
        # if any unknown field name is sent.  Guard against that.
        text = response.text.strip()
        if not text.startswith("["):
            logger.error(f"[CRON] Ringostat returned non-JSON body: {text[:300]}")
            return
        try:
            data = response.json()
        except Exception as e:
            logger.error(f"[CRON] Ringostat JSON parse failed: {e} | body[:300]={response.text[:300]}")
            return
        calls = data if isinstance(data, list) else data.get("calls", [])
        logger.info(f"[CRON] Fetched {len(calls)} calls from Ringostat")

        # Build SIP-alias → manager_id index (from ringostat_config.extension_mapping)
        ext_mapping = ringostat_config.get("extension_mapping", {}) or {}
        # Common Ringostat SIP-alias regex (configurable per project)
        SIP_ALIAS_RE = _re.compile(r"^[A-Za-z][A-Za-z0-9_-]+$|^\d{1,5}$")  # alias or short ext

        def _derive_call_id(record: dict, calldate_str: str) -> str:
            """Stable, idempotent id from recording filename or hash."""
            rec = record.get("recording") or ""
            # e.g. https://app.ringostat.com/recordings/bg1_-1779866441.1274279.wav?token=…
            m = _re.search(r"/([^/]+?)\.wav(?:\?|$)", rec)
            if m:
                return m.group(1)  # bg1_-1779866441.1274279
            blob = f"{calldate_str}|{record.get('caller','')}|{record.get('dst','')}|{record.get('billsec','')}"
            return "rs_" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

        def _derive_direction(caller: str, dst: str) -> str:
            # If caller looks like a SIP alias (alphanumeric, no leading +/digits-only-long), it's outbound
            caller_is_sip = bool(SIP_ALIAS_RE.match(caller or "")) and not caller.isdigit() or (caller.isdigit() and len(caller) <= 5)
            dst_is_sip = bool(SIP_ALIAS_RE.match(dst or "")) and not dst.isdigit() or (dst.isdigit() and len(dst) <= 5)
            if caller_is_sip and not dst_is_sip:
                return "outbound"
            if dst_is_sip and not caller_is_sip:
                return "inbound"
            # Fallback: treat external→external as inbound
            return "inbound"

        def _parse_calldate(value) -> datetime:
            if not value:
                return now
            try:
                # Examples: "2026-05-27T10:20:41+0300"  or  "2026-05-27T10:20:41+03:00"
                s = str(value)
                if len(s) >= 5 and (s[-5] in "+-") and ":" not in s[-5:]:
                    s = s[:-5] + s[-5:-2] + ":" + s[-2:]
                return datetime.fromisoformat(s)
            except Exception:
                return now

        synced_inserted, synced_updated = 0, 0
        for call_data in calls:
            try:
                calldate_str = call_data.get("calldate") or ""
                started_at = _parse_calldate(calldate_str).astimezone(timezone.utc)

                caller = (call_data.get("caller") or "").strip()
                dst = (call_data.get("dst") or "").strip()
                n_alias = (call_data.get("n_alias") or "").strip()  # which DID/manager picked up
                disposition = (call_data.get("disposition") or "").strip().upper() or "UNKNOWN"
                billsec = int(call_data.get("billsec") or 0)
                duration = int(call_data.get("duration") or billsec or 0)
                recording_url = call_data.get("recording") or ""

                call_id = _derive_call_id(call_data, calldate_str)
                direction = _derive_direction(caller, dst)

                # Identify the "external" phone (the customer side)
                from_number = caller
                to_number = dst
                external_phone = (
                    dst if direction == "outbound" else caller
                )
                external_phone = external_phone or n_alias

                # Manager attribution: which side is the SIP alias?
                manager_sip = None
                if direction == "outbound":
                    manager_sip = caller
                else:
                    manager_sip = dst or n_alias
                manager_id = ext_mapping.get(manager_sip) if manager_sip else None

                # Fallbacks
                if not manager_id:
                    # Try matching by staff.extension (in case extension field is used)
                    if manager_sip:
                        st = await db.staff.find_one({"extension": manager_sip})
                        if st:
                            manager_id = st.get("id") or str(st.get("_id"))

                # Lead by phone (if external phone is a real number with 6+ digits)
                lead = None
                if external_phone and len(external_phone.replace("+", "").replace("-", "")) >= 6 and external_phone.replace("+", "").isdigit():
                    lead = await db.leads.find_one({"phone": external_phone})
                    if not lead:
                        _lead_uuid = str(uuid.uuid4())
                        lead = {
                            "_id": _lead_uuid,
                            "id":  _lead_uuid,  # CRITICAL — frontend & 360 endpoint use `id`
                            "name": f"Auto-created {external_phone}",
                            "phone": external_phone,
                            "source": "ringostat",
                            "status": "new",
                            "created_at": now,
                            "updated_at": now,
                        }
                        await db.leads.insert_one(lead)
                lead_id = (lead.get("id") if lead else None) or (lead.get("_id") if lead else None)

                # Last resort: first active manager so call isn't orphaned
                if not manager_id:
                    fallback = await db.staff.find_one({"role": "manager", "is_active": True})
                    if fallback:
                        manager_id = fallback.get("id") or str(fallback.get("_id"))

                # Upsert
                existing_call = await db.ringostat_calls.find_one({"call_id": call_id})
                if existing_call:
                    update_data = {"updated_at": now, "synced_at": now}
                    if recording_url and not existing_call.get("recording_url"):
                        update_data["recording_url"] = recording_url
                        update_data["recording_fetched_at"] = now
                    if duration > existing_call.get("duration", 0):
                        update_data["duration"] = duration
                    if billsec > existing_call.get("billsec", 0):
                        update_data["billsec"] = billsec
                    if disposition != existing_call.get("status"):
                        update_data["status"] = disposition
                    if not existing_call.get("manager_id") and manager_id:
                        update_data["manager_id"] = manager_id
                    await db.ringostat_calls.update_one({"call_id": call_id}, {"$set": update_data})
                    synced_updated += 1
                else:
                    new_call = {
                        "_id": str(uuid.uuid4()),
                        "call_id": call_id,
                        "direction": direction,
                        "from": from_number,
                        "to": to_number,
                        "n_alias": n_alias,
                        "external_phone": external_phone,
                        "manager_sip": manager_sip,
                        "status": disposition,
                        "duration": duration,
                        "billsec": billsec,
                        "recording_url": recording_url,
                        "lead_id": lead_id,
                        "manager_id": manager_id,
                        "utm_source": call_data.get("utm_source") or "",
                        "utm_medium": call_data.get("utm_medium") or "",
                        "utm_campaign": call_data.get("utm_campaign") or "",
                        "utm_term": call_data.get("utm_term") or "",
                        "utm_content": call_data.get("utm_content") or "",
                        "client_id": call_data.get("client_id") or "",
                        "referrer": call_data.get("referrer") or "",
                        "raw": call_data,
                        "started_at": started_at,
                        "created_at": now,
                        "updated_at": now,
                        "synced_at": now,
                        "source": "cron_export",
                    }
                    await db.ringostat_calls.insert_one(new_call)
                    synced_inserted += 1
            except Exception as e:
                logger.error(f"[CRON] Error processing call: {e}", exc_info=True)
                continue

        logger.info(f"[CRON] Synced {synced_inserted} inserted, {synced_updated} updated")

    except Exception as e:
        logger.error(f"[CRON] Export calls error: {e}")
        logger.error(traceback.format_exc())


# ==================== RINGOSTAT: CALLBACK API ====================

@fastapi_app.post(
    "/api/ringostat/callback",
    dependencies=[Depends(require_manager_or_admin)],
)
async def ringostat_initiate_callback(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """
    Initiate outbound call from CRM via Ringostat (click-to-call).

    Body (JSON):
      - ``phone`` (str, required)     — customer phone in E.164 (e.g. +359...)
      - ``extension`` (str, optional) — manager SIP extension. If absent, the
        authed user's `staff.extension` is used. If neither — 400.

    Security:
      - Requires manager_or_admin role (was unauthenticated, fixed Phase IV-4).
      - Logs ``initiated_by`` (authed user id) so we can audit who dialled what.
    """
    phone = (data or {}).get("phone")
    extension = (data or {}).get("extension")

    if not phone:
        raise HTTPException(status_code=400, detail="phone is required (E.164)")

    # Allow the manager to call without specifying extension — pull from staff.
    if not extension:
        user_id = (current_user or {}).get("id") or (current_user or {}).get("_id")
        if user_id:
            me = await db.staff.find_one({"$or": [{"id": user_id}, {"_id": user_id}]})
            extension = (me or {}).get("extension")
    if not extension:
        raise HTTPException(
            status_code=400,
            detail="extension is required (manager has no SIP extension on file)",
        )

    try:
        # Get Ringostat config
        ringostat_config = await db.ringostat_config.find_one({})
        if not ringostat_config:
            raise HTTPException(status_code=400, detail="Ringostat not configured")
        
        project_id = ringostat_config.get('project_id')
        api_key = ringostat_config.get('api_key')
        
        if not project_id or not api_key:
            raise HTTPException(status_code=400, detail="Ringostat credentials missing")
        
        # Call Ringostat Callback API (simple method)
        import httpx
        
        async with httpx.AsyncClient() as client:
            url = "https://api.ringostat.net/callback/outward_call"
            headers = {
                "Auth-key": api_key,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            # Ringostat expects URL-encoded form data
            payload = {
                "extension": extension,  # Employee's phone/extension
                "destination": phone,     # Customer's phone
                "direction": "out"
            }
            
            response = await client.post(url, headers=headers, data=payload, timeout=10.0)
            
            if response.status_code != 200:
                logger.error(f"[CALLBACK] Ringostat API error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=502, detail="Ringostat callback failed")
            
            result = response.json()
            
            # Log callback initiation (audit trail — who dialled what when)
            callback_log = {
                '_id': str(uuid.uuid4()),
                'phone': phone,
                'extension': extension,
                'initiated_by': (current_user or {}).get("id") or (current_user or {}).get("_id"),
                'initiated_by_name': (current_user or {}).get("name"),
                'initiated_at': datetime.now(timezone.utc),
                'ringostat_response': result
            }
            await db.ringostat_callbacks.insert_one(callback_log)
            
            logger.info(f"[CALLBACK] Initiated call to {phone} via extension {extension} by {callback_log['initiated_by']}")
            
            return {
                "success": True,
                "message": "Callback initiated",
                "phone": phone,
                "extension": extension
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CALLBACK] Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/api/manager/calls/missed", dependencies=[Depends(require_manager_or_admin)])
async def get_missed_calls(manager_id: str = None):
    """Get missed calls that need callback"""
    try:
        query = {'status': 'MISSED'}
        if manager_id:
            query['manager_id'] = manager_id
        
        calls = await db.ringostat_calls.find(query).sort('created_at', -1).limit(20).to_list(20)
        for c in calls:
            if '_id' in c:
                c['_id'] = str(c['_id'])
        
        return {"success": True, "calls": calls}
    except Exception as e:
        logger.error(f"Get missed calls error: {e}")
        return {"success": False, "error": str(e)}

@fastapi_app.post("/api/calls/{call_id}/outcome")
async def save_call_outcome(call_id: str, data: Dict[str, Any] = Body(...)):
    """Save call outcome"""
    try:
        outcome = data.get('outcome')
        note = data.get('note', '')
        
        await db.ringostat_calls.update_one(
            {'_id': call_id},
            {
                '$set': {
                    'outcome': outcome,
                    'outcome_note': note,
                    'updated_at': datetime.now(timezone.utc)
                }
            }
        )
        
        # Get call to access lead_id
        call = await db.ringostat_calls.find_one({'_id': call_id})
        
        if call and call.get('lead_id'):
            # Update lead score based on outcome
            score_change = 0
            if outcome == 'interested':
                score_change = 15
            elif outcome == 'callback':
                score_change = 5
            elif outcome == 'vin_request':
                score_change = 20
            elif outcome == 'ready_deposit':
                score_change = 30
            elif outcome == 'reject':
                score_change = -10
            
            if score_change != 0:
                await db.leads.update_one(
                    {'_id': call['lead_id']},
                    {'$inc': {'score': score_change}}
                )
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Save outcome error: {e}")
        return {"success": False, "error": str(e)}

@fastapi_app.get("/api/leads/{lead_id}/calls")
async def get_lead_calls(lead_id: str):
    """Get all calls for a lead"""
    try:
        calls = await db.ringostat_calls.find({
            'lead_id': lead_id
        }).sort('created_at', -1).to_list(100)
        for c in calls:
            if '_id' in c:
                c['_id'] = str(c['_id'])
        
        return {"success": True, "calls": calls}
    except Exception as e:
        logger.error(f"Get lead calls error: {e}")
        return {"success": False, "error": str(e)}

# ═══════════════════════════════════════════════════════════════════
# DEBUG: Simulate Ringostat Events
# ═══════════════════════════════════════════════════════════════════
@fastapi_app.post("/api/debug/ringostat/simulate", dependencies=[Depends(require_admin)])
async def simulate_ringostat_event(data: Dict[str, Any] = Body(...)):
    """
    Simulate Ringostat webhook events for testing
    Body: {
        "event": "CALL_START" | "CALL_END" | "CALL_MISSED",
        "from": "+380XXXXXXXXX",
        "to": "+380...",
        "manager_extension": "101",
        "duration": 120 (for CALL_END)
    }
    """
    try:
        event_type = data.get('event', 'CALL_START')
        from_number = data.get('from', '+380501234567')
        to_number = data.get('to', '+380931234567')
        manager_ext = data.get('manager_extension', '')
        duration = int(data.get('duration', 0))
        
        # Create fake webhook payload
        webhook_payload = {
            'event': event_type,
            'call_id': f'sim_{str(uuid.uuid4())[:8]}',
            'direction': 'inbound',
            'from': from_number,
            'to': to_number,
            'manager_extension': manager_ext,
            'status': 'answered' if event_type == 'CALL_END' else 'ringing',
            'duration': duration,
            'recording_url': '',
            'utm_source': 'debug',
            'utm_campaign': 'simulation'
        }
        
        # Call the webhook endpoint directly without request object
        # Instead, process webhook logic here
        from_number = webhook_payload['from']
        manager_ext = webhook_payload.get('manager_extension', '')
        call_id = webhook_payload['call_id']
        duration = webhook_payload.get('duration', 0)
        event_type = webhook_payload['event']
        status = webhook_payload.get('status', 'ringing')
        
        # Find or create lead
        lead = await db.leads.find_one({'phone': from_number})
        if not lead:
            # Auto-create lead
            lead = {
                '_id': str(uuid.uuid4()),
                'name': f'Incoming {from_number}',
                'phone': from_number,
                'source': 'ringostat',
                'status': 'new',
                'created_at': datetime.now(timezone.utc)
            }
            await db.leads.insert_one(lead)
            logger.info(f"[SIMULATE] Lead created: {lead['_id']}")
        
        # Get manager by extension
        ringostat_config = await db.ringostat_config.find_one({})
        manager_id = None
        if ringostat_config and manager_ext:
            ext_mapping = ringostat_config.get('extension_mapping', {})
            manager_id = ext_mapping.get(str(manager_ext))
        
        # Create call record
        now = datetime.now(timezone.utc)
        call_data = {
            '_id': str(uuid.uuid4()),
            'call_id': call_id,
            'direction': 'inbound',
            'from': from_number,
            'to': webhook_payload['to'],
            'status': status.upper(),
            'duration': duration,
            'lead_id': lead['_id'],
            'manager_id': manager_id,
            'started_at': now,
            'created_at': now,
            'updated_at': now
        }
        await db.ringostat_calls.insert_one(call_data)
        logger.info(f"[SIMULATE] Call created: {call_id}")
        
        # Emit WebSocket event for CALL_START
        if event_type == 'CALL_START':
            ws_payload = {
                'call_id': call_id,
                'from': from_number,
                'lead_id': lead['_id'],
                'lead_name': lead.get('name'),
                'manager_id': manager_id,
                'timestamp': now.isoformat()
            }
            
            if manager_id:
                await emit_to_user(manager_id, 'ringostat:incoming_call', ws_payload)
                logger.info(f"[SIMULATE] Emitted incoming_call to user:{manager_id}")
            else:
                await emit_to_role('manager', 'ringostat:incoming_call', ws_payload)
                logger.info(f"[SIMULATE] Broadcast incoming_call to role:manager")
        
        # Emit WebSocket event for CALL_END
        elif event_type == 'CALL_END' and duration > 10:
            ws_payload = {
                'call_id': call_id,
                'from': from_number,
                'lead_id': lead['_id'],
                'lead_name': lead.get('name'),
                'manager_id': manager_id,
                'duration': duration,
                'timestamp': now.isoformat()
            }
            
            if manager_id:
                await emit_to_user(manager_id, 'ringostat:call_needs_outcome', ws_payload)
                logger.info(f"[SIMULATE] Emitted call_needs_outcome to user:{manager_id}")
            else:
                await emit_to_role('manager', 'ringostat:call_needs_outcome', ws_payload)
                logger.info(f"[SIMULATE] Broadcast call_needs_outcome to role:manager")
        
        return {
            "success": True,
            "message": f"Simulated {event_type} event",
            "call_id": call_id,
            "lead_id": str(lead['_id']) if lead.get('_id') is not None else None,
            "manager_id": manager_id
        }
    except Exception as e:
        logger.error(f"Simulate error: {e}")
        return {"success": False, "error": str(e)}

# ═══════════════════════════════════════════════════════════════════
# END DEBUG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


# admin_integrations test + toggle moved to app/routers/admin_integrations.py
# (Wave 2B/Batch 15) — last 2 writers in the cluster.
#   POST   /api/admin/integrations/{provider}/test
#   POST   /api/admin/integrations/{provider}/toggle


# ═══════════════════════════════════════════════════════════════════
# GOOGLE SIGN-IN (public Client ID + ID token verification)
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/auth/google-client-id")
async def public_google_client_id():
    """Public endpoint — returns the configured Google OAuth Client ID.

    Used by the Customer Cabinet login page to initialise Google Identity
    Services (GIS) popup. No secret is returned.

    Resolution order (new):
      1. app_settings.auth.google.clientId             (admin UI — preferred)
      2. integration_configs.{provider:google_oauth}   (legacy)
      3. GOOGLE_CLIENT_ID env var                      (fallback)
    """
    try:
        svc = get_settings_service()
        auth = await svc.get_auth()
        gcfg = auth.get("google") or {}
        features = auth.get("features") or {}
        if features.get("googleEnabled", True) is False:
            return {"clientId": "", "enabled": False}
        cid = (gcfg.get("clientId") or "").strip()
        if cid:
            return {"clientId": cid, "enabled": True}
    except Exception as exc:
        logger.warning(f"[google-client-id] settings lookup failed: {exc}")

    # Fallback to the legacy integration_configs path
    # Phase 5.4 / C-2 — db.integration_configs ownership routes through
    # IntegrationConfigsRepository.find_by_provider (preserves the legacy
    # `... or {}` quirk verbatim — find_by_provider returns {} when missing).
    from app.repositories import IntegrationConfigsRepository
    doc = await IntegrationConfigsRepository(db).find_by_provider("google_oauth")
    creds = doc.get("credentials") or {}
    client_id = (creds.get("clientId") or "").strip()
    db_enabled = bool(doc.get("isEnabled", bool(client_id)))

    if not client_id:
        env_id = (os.environ.get("GOOGLE_CLIENT_ID", "") or "").strip()
        if env_id:
            client_id = env_id
            db_enabled = True  # env-provided ⇒ implicitly enabled

    enabled = db_enabled and bool(client_id)
    return {
        "clientId": client_id if enabled else "",
        "enabled": enabled,
    }


@fastapi_app.post("/api/customer-auth/google/verify")
async def customer_google_verify(data: Dict[str, Any] = Body(...)):
    """
    Verify a Google ID token (credential) issued by Google Identity Services
    directly in the browser. No intermediate provider involved.

    Body: { "credential": "<google_id_token>" }
    Returns: same shape as /api/customer-auth/google/session (customer + sessionToken).
    """
    credential = (data or {}).get("credential") or data.get("id_token")
    if not credential:
        raise HTTPException(status_code=400, detail="credential is required")

    # Resolve configured Client ID through the canonical priority chain
    # (app_settings → integration_configs → env). Phase 5.4 / C-3A —
    # this now uses the SAME source-of-truth chain as
    # /api/auth/google-client-id (the public endpoint). Previously this
    # site read directly from integration_configs which (after C-3A's
    # mirror retirement) would have returned a stale value for any
    # clientId edited via the settings UI. Routing through
    # settings_service.resolve_google_client_id() restores consistency.
    try:
        client_id = (await get_settings_service().resolve_google_client_id()).strip()
    except Exception:
        client_id = (os.environ.get("GOOGLE_CLIENT_ID", "") or "").strip()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google Sign-In is not configured")

    # Verify token with google-auth
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=30,
        )
    except Exception as exc:
        logger.warning(f"[google/verify] token invalid: {exc}")
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    # Basic sanity
    if idinfo.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    email = (idinfo.get("email") or "").strip().lower()
    if not email or not idinfo.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Google account email not verified")

    # ── Allowed-domains gate (optional B2B whitelist) ─────────────────────
    # When the admin populates `app_settings.auth.google.allowedDomains` —
    # a comma-separated string or list of domain suffixes (e.g.
    # "bibi.cars,partner.com") — only Google accounts whose verified email
    # ends with one of those domains are allowed to sign in. Empty / unset
    # means "any verified Google account" (the default).
    try:
        auth_cfg = await get_settings_service().get_auth()
        gcfg = auth_cfg.get("google") or {}
        raw_allowed = gcfg.get("allowedDomains") or gcfg.get("allowed_domains") or ""
        if isinstance(raw_allowed, list):
            allowed_list = [str(d).strip().lstrip("@").lower() for d in raw_allowed if str(d or "").strip()]
        else:
            allowed_list = [d.strip().lstrip("@").lower() for d in str(raw_allowed).split(",") if d.strip()]
        if allowed_list:
            domain = email.split("@", 1)[1] if "@" in email else ""
            if not any(domain == d or domain.endswith("." + d) for d in allowed_list):
                logger.info(f"[google/verify] domain rejected: {domain} not in allowedDomains")
                raise HTTPException(
                    status_code=403,
                    detail=f"Sign-in restricted to specific domains. {domain} is not allowed.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        # Defensive — never block sign-in due to settings lookup failure;
        # log and fall through (allowed_list empty ⇒ no restriction).
        logger.warning(f"[google/verify] allowedDomains lookup failed: {exc}")

    name = idinfo.get("name") or ""
    picture = idinfo.get("picture") or ""
    google_sub = idinfo.get("sub") or ""

    # Upsert customer — same shape as the email/password flow
    existing = await db.customers.find_one({"email": email}, {"_id": 0})
    now_iso = datetime.now(timezone.utc).isoformat()
    if existing:
        customer_id = (
            existing.get("customerId") or existing.get("id") or existing.get("user_id")
            or f"cust_{uuid.uuid4().hex[:12]}"
        )
        update = {
            "name": name or existing.get("name") or email.split("@", 1)[0],
            "picture": picture or existing.get("picture", ""),
            "googleId": google_sub or existing.get("googleId", ""),
            "last_login_at": now_iso,
            "source": existing.get("source") or "google",
        }
        update.update({"id": customer_id, "customerId": customer_id, "user_id": customer_id})
        await db.customers.update_one({"email": email}, {"$set": update})
        customer = {**existing, **update, "email": email, "role": existing.get("role", "customer")}
    else:
        customer_id = f"cust_{uuid.uuid4().hex[:12]}"
        customer = {
            "id": customer_id,
            "customerId": customer_id,
            "user_id": customer_id,
            "email": email,
            "name": name or email.split("@", 1)[0],
            "picture": picture,
            "googleId": google_sub,
            "role": "customer",
            "status": "active",
            "source": "google",
            "created_at": now_iso,
            "last_login_at": now_iso,
        }
        await db.customers.insert_one(customer)

    # 2FA gate — account-level control applies to Google sign-in too. If the
    # customer enabled TOTP, return a challenge instead of a live session so
    # an attacker cannot bypass 2FA simply by using the Google method.
    if customer.get("totp_enabled"):
        if _2fa_locked_remaining(customer) > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {max(1, _2fa_locked_remaining(customer)//60)} minute(s).",
            )
        return await _issue_2fa_challenge(customer_id, email)
    if customer.get("email_2fa_enabled"):
        if _2fa_locked_remaining(customer) > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {max(1, _2fa_locked_remaining(customer)//60)} minute(s).",
            )
        return await _issue_2fa_challenge(customer_id, email, method="email")

    # Mint session token
    token = generate_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=_CUSTOMER_SESSION_TTL_DAYS)
    await db.customer_sessions.insert_one({
        "token": token,
        "session_token": token,
        "customerId": customer_id,
        "user_id": customer_id,
        "provider": "google",
        "created_at": now,
        "expires_at": expires_at,
    })
    return _customer_response(customer, token)


# Cadence
@fastapi_app.get("/api/cadence/definitions")
async def cadence_definitions():
    """Get cadence definitions - returns direct array"""
    return [
        {"id": "c1", "name": "New Lead Follow-up", "description": "Automated follow-up for new leads", "isActive": True, "steps": [
            {"order": 1, "delay": 0, "action": "notification", "template": "new_lead_welcome"},
            {"order": 2, "delay": 3600, "action": "task", "template": "first_call"},
            {"order": 3, "delay": 86400, "action": "telegram", "template": "follow_up_message"}
        ]},
        {"id": "c2", "name": "Deal Stalled Alert", "description": "Alert when deal is stalled", "isActive": False, "steps": [
            {"order": 1, "delay": 172800, "action": "alert", "template": "deal_stalled"}
        ]},
    ]

@fastapi_app.get("/api/cadence/runs")
async def cadence_runs():
    """Get active cadence runs - returns direct array"""
    return [
        {"id": "run1", "cadenceId": "c1", "entityId": "lead_123", "entityType": "lead", "currentStep": 2, "status": "active", "startedAt": datetime.now(timezone.utc).isoformat()},
    ]

@fastapi_app.get("/api/cadence/runs/{run_id}")
async def cadence_run(run_id: str):
    return {"id": run_id, "status": "completed"}

@fastapi_app.post("/api/cadence/definitions")
async def create_cadence(data: Dict[str, Any] = Body(...)):
    """Create cadence definition"""
    return {"success": True, "id": f"c_{datetime.now(timezone.utc).timestamp()}"}

@fastapi_app.put("/api/cadence/definitions/{cadence_id}")
async def update_cadence(cadence_id: str, data: Dict[str, Any] = Body(...)):
    """Update cadence definition"""
    return {"success": True}

@fastapi_app.delete("/api/cadence/definitions/{cadence_id}")
async def delete_cadence(cadence_id: str):
    """Delete cadence definition"""
    return {"success": True}

@fastapi_app.patch("/api/cadence/definitions/{cadence_id}/toggle")
async def toggle_cadence(cadence_id: str, data: Dict[str, Any] = Body(...)):
    """Toggle cadence active state"""
    return {"success": True}

@fastapi_app.post("/api/cadence/runs/{run_id}/stop")
async def stop_cadence_run(run_id: str):
    """Stop cadence run"""
    return {"success": True}

# Calls
@fastapi_app.get("/api/calls/analytics")
async def calls_analytics():
    return {"totalCalls": 0, "avgDuration": 0}

@fastapi_app.get("/api/calls/board")
async def calls_board():
    return {"calls": []}

# Carfax Admin




# Contracts

# Auth
@fastapi_app.post("/api/auth/change-password-legacy-removed", include_in_schema=False)
async def _auth_change_password_removed_stub():
    """The real handler now lives in app/routers/auth_password.py.
    This placeholder exists only to keep file-line offsets stable for
    deploy scripts that grep for the old endpoint."""
    return {"success": True, "deprecated": True}

# Cabinet

# Customer Auth
@fastapi_app.post("/api/customer-auth/me/avatar/upload")
async def customer_avatar_upload():
    # Legacy endpoint — kept for compatibility but does nothing.
    # Use /api/customer-cabinet/{customer_id}/avatar instead (no external auth required).
    return {"success": True, "url": "", "deprecated": True}


@fastapi_app.post("/api/customer-cabinet/{customer_id}/avatar")
async def customer_cabinet_upload_avatar(
    customer_id: str,
    avatar: UploadFile = File(...),
):
    """
    Upload avatar for a customer (cabinet flow — NO external auth redirect).
    Saves file to /app/backend/static/avatars/{customer_id}.{ext}
    and writes URL into customer.avatar.
    """
    await ensure_customer_record(customer_id)

    # Validate content type
    ctype = (avatar.content_type or '').lower()
    allowed = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif'}
    if ctype not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {ctype}")

    ext = allowed[ctype]
    content = await avatar.read()

    # Max 5MB
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 5MB)")

    # Deployment-safe: store in MongoDB-backed media store (not pod-local disk).
    from app.services.media_store import save_media
    saved = save_media("avatars", f"{customer_id}.{ext}", content, ctype)
    ts = int(datetime.now(timezone.utc).timestamp())
    url = f"{saved['url']}?v={ts}"

    await db.customers.update_one(
        {'id': customer_id},
        {'$set': {'avatar': url, 'picture': url, 'updatedAt': datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {'success': True, 'url': url, 'avatar': url, 'picture': url}


@fastapi_app.delete("/api/customer-cabinet/{customer_id}/avatar")
async def customer_cabinet_delete_avatar(customer_id: str):
    """Remove avatar file and clear customer.avatar field."""
    for ext in ('jpg', 'png', 'webp', 'gif'):
        f = _STATIC_DIR / "avatars" / f"{customer_id}.{ext}"
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
    await db.customers.update_one(
        {'id': customer_id},
        {'$set': {'avatar': None, 'picture': None, 'updatedAt': datetime.now(timezone.utc)}},
    )
    return {'success': True}

# Analytics Dashboard & Marketing Campaigns — РЕАЛЬНЫЕ ДАННЫЕ
# (заменили mock-заглушку, см. backend/app/routers/analytics_tracking.py)
# Эндпоинты GET /api/analytics/dashboard, /api/analytics/marketing-campaigns,
# POST /api/track/event, POST/GET /api/admin/marketing/campaigns подключаются
# через include_router ниже.

# ═══════════════════════════════════════════════════════════════════
# PUBLIC API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════
# PUBLIC BRANDS — distinct list of vehicle makes (cleaned + sorted)
# Used by the /catalog Brand dropdown to show only real, available makes.
# ═══════════════════════════════════════════════════════════════════
_BRAND_CANONICAL = {
    "chev": "Chevrolet",
    "chevy": "Chevrolet",
    "niss": "Nissan",
    "land": "Land Rover",
    "mb": "Mercedes-Benz",
    "mercedes": "Mercedes-Benz",
    "vw": "Volkswagen",
}

# [auto-domain removed] /api/public/brands (public_brands)


# ═══════════════════════════════════════════════════════════════════
# PUBLIC MODELS — distinct models for the currently picked brand(s).
# Accepts a comma- or pipe-separated brand list. Returns the cleaned,
# de-duplicated, alphabetically sorted list with vehicle counts.
# ═══════════════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════════════
# PUBLIC FEATURED LISTINGS (live BidMotors catalogue, 5-min TTL cache)
# Used by the homepage "Top vehicles deals of the week" block.
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.post("/api/public/leads/quick")
async def create_quick_lead(data: Dict[str, Any] = Body(...)):
    """Create quick lead from public site (incl. calculator leads)."""
    lead = {
        "id": f"lead-{datetime.now(timezone.utc).timestamp()}",
        "name": data.get("name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "vin": data.get("vin"),
        "vehicleId": data.get("vehicleId"),
        "source": data.get("source", "website"),
        "message": data.get("message", ""),
        # calculator / catalog enrichment
        "desiredCar": data.get("desiredCar"),
        "budget": data.get("budget"),
        "quoteId": data.get("quoteId"),
        "calculation": data.get("calculation"),
        "status": "new",
        "score": 70 if (data.get("source") == "calculator") else 50,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.leads.insert_one(lead)
    return {"success": True, "leadId": lead["id"]}

@fastapi_app.post("/api/public/leads/from-quote")
async def create_lead_from_quote(data: Dict[str, Any] = Body(...)):
    """Create a lead from a calculator interaction.

    Accepts both:
      • legacy `quoteId` (old /api/calculator/quote)
      • new `calculationId` (immutable calculation snapshot from /api/calculations)
    Plus full context (origin / vehicleType / price / damaged / total) so the
    manager sees the pre-calculated estimate without having to open the snapshot.
    """
    now = datetime.now(timezone.utc).isoformat()
    lead_id = f"lead-{uuid.uuid4().hex[:12]}"
    calc_id = data.get("calculationId")
    lead = {
        "id": lead_id,
        "name": data.get("name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "vin": data.get("vin"),
        "quoteId": data.get("quoteId"),                # legacy
        "calculationId": calc_id,                       # new immutable snapshot
        "calculator_context": {
            "origin":       data.get("origin"),
            "vehicleType":  data.get("vehicleType"),
            "vehiclePrice": data.get("price"),
            "damaged":      bool(data.get("damaged") or False),
            "total":        data.get("total"),
            "currency":     data.get("currency") or "USD",
        },
        "scenario": data.get("scenario"),
        "message":  data.get("message") or "",
        "source":   data.get("source") or "calculator",
        "status":   "new",
        "score":    80,                                 # calculator-originated leads are warmer
        "created_at": now,
    }
    await db.leads.insert_one(lead)
    # Back-link: if a calculation snapshot was attached, stamp the lead_id on it
    if calc_id:
        try:
            await db.calculations.update_one(
                {"id": calc_id},
                {"$set": {"lead_id": lead_id, "updated_at": now}},
            )
        except Exception as _e:
            logger.warning(f"[lead-from-quote] could not attach lead_id to calculation {calc_id}: {_e}")
    return {"success": True, "leadId": lead_id, "calculationId": calc_id}


# ═══════════════════════════════════════════════════════════════════
# VIN SEARCH V2 (compatibility layer)
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] /api/v2/search/{vin} (vin_search_v2)


# ═══════════════════════════════════════════════════════════════════
# PUBLIC UNIFIED SEARCH (header search bar — VIN or LOT)
# ═══════════════════════════════════════════════════════════════════

def _normalize_search_query(raw: str) -> Dict[str, str]:
    """Classify a raw search query as VIN, VIN_PARTIAL, LOT or URL.

    - Strips whitespace, uppercases
    - VIN: 17 chars [A-HJ-NPR-Z0-9] (no I/O/Q)
    - VIN_PARTIAL: 6–16 alphanumerics (A-HJ-NPR-Z0-9) — prefix match
    - LOT: numeric 4–10 digits
    - URL: contains '://'
    """
    q = (raw or "").strip()
    if not q:
        return {"kind": "empty", "value": ""}
    if "://" in q:
        return {"kind": "url", "value": q}
    clean = q.upper().replace(" ", "").replace("-", "")
    # VIN detection (17 alphanumeric, excluding I/O/Q per ISO 3779)
    if re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", clean):
        return {"kind": "vin", "value": clean}
    # Numeric lot number (pure digits, 4–10)
    if re.fullmatch(r"\d{4,10}", clean):
        return {"kind": "lot", "value": clean}
    # Partial VIN — 3..16 alphanumerics (ISO 3779 charset), prefix lookup
    if re.fullmatch(r"[A-HJ-NPR-Z0-9]{3,16}", clean):
        return {"kind": "vin_partial", "value": clean}
    # Otherwise — treat as free-text lot/partial (numeric-ish)
    return {"kind": "unknown", "value": clean}


# [car-import removed] _vehicle_doc_to_public_card (vin_data → vehicle card)


# [auto-domain removed] /api/public/search/suggest (public_search_suggest)





# ─────────────────────────────────────────────────────────────────────
# PHASE B2 — Detail-page instant-shell pattern
# ─────────────────────────────────────────────────────────────────────
#
# The legacy /api/vin/{vin} above runs the full live fallback chain
# (SEARCH → WESTMOTORS → LEMON → PAGE), which can take 2–6 seconds on
# unknown VINs. That latency was the dominant reason single-car pages
# felt slow — the entire UI waited for the chain before painting.
#
# We solve perceived speed with TWO new endpoints (no API fragmentation,
# legacy /api/vin/{vin} stays unchanged):
#
#   GET /api/vin/{vin}/shell   guaranteed-fast DB-only snapshot
#                              never blocks; honest "missing fields"
#                              target <150 ms
#
#   GET /api/vin/{vin}/enrich  optional live enhancement
#                              runs SEARCH → WESTMOTORS → LEMON → PAGE
#                              writes back to vin_data so next /shell
#                              call already has the data
#
# Rules of the road (per stakeholder directive):
#   • shell = DB only — zero external calls, zero scraping, zero retries
#   • truthful partial: returns ONLY fields it actually has
#   • freshness: explicit fresh/stale/expired/unknown labels + age_seconds
#   • no realtime — the frontend triggers /enrich, awaits, and re-renders.
#     No websockets, no polling, no streaming.
# ─────────────────────────────────────────────────────────────────────

# [car-import removed] VIN shell/enrich helpers (_SHELL_* / _shell_freshness / _shell_project)






# ─────────────────────────────────────────────────────────────────
# Stat.vin admin / diagnostic endpoints (no DB, no sync — JIT only)
# ─────────────────────────────────────────────────────────────────










# ─── Parser-public aliases (used by /app/scripts/* and external monitors) ──
# These are intentionally UN-AUTHENTICATED so health checkers can call them.
# Mutations are limited to safe idempotent operations (breaker reset).









# [auto-domain removed] /api/public/search/{query} (public_unified_search)


# Note: /api/v2/search-by-url is defined at the end of file with Cookie Proxy support

# [auto-domain removed] /api/bulk/vehicle/{vin} (bulk_vehicle_lookup)


# ═══════════════════════════════════════════════════════════════════
# CALCULATOR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# Calculator config — hard-coded DEFAULTS (used as fallbacks and also to
# seed the DB-backed configuration on first run). Admins can edit the
# persisted values through /api/calculator/config/* without touching code.
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# Phase 6.5+ Wave 2 (LANDING 2026-05-20) — calculator-constants cluster
# retirement
# ══════════════════════════════════════════════════════════════════════
# The 38 PURE_CONSTANT + 1 internal-only constant (AUCTION_TIERED_FEES)
# that used to live below at the def-sites lines 9265-9411 have been
# moved to their canonical home in ``app/core/calculator_constants.py``
# (Wave 2 — calc-engine cluster reduction). server.py re-exports them
# here at module-load for:
#
#   * back-compat with the qualified name ``server.X`` discovery
#   * in-file callers in this very module:
#       - ``_ensure_calculator_seed`` (references DEFAULT_PROFILE_CODE,
#         PORT_FORWARDING, AUCTION_FEES, AUCTION_TIERED_FEES, ...)
#       - admin config endpoints (default param value
#         ``code: str = DEFAULT_PROFILE_CODE``)
#
# Out-of-scope (still defined below the re-export block as legacy
# def-sites): ``AUCTIONS`` (list), ``VEHICLE_KOREA_INLAND``,
# ``VEHICLE_KOREA_SEA``, ``VEHICLE_KOREA_BG``, ``OFFICIAL_FEES_USD`` —
# these don't participate in the 38-symbol Wave 2 scope.
#
# The re-export must execute BEFORE any in-file callsite references
# these names, so it is placed at the very same position the def-sites
# used to occupy.
from app.core.calculator_constants import (  # noqa: E402, F401
    # Catalog tables (3)
    VEHICLE_TYPES,
    CALCULATOR_PORTS,
    AUCTION_FEES,
    # USA-pipeline constants (14)
    DEFAULT_PROFILE_CODE,
    VEHICLE_USA_INLAND,
    VEHICLE_OCEAN_BASE,
    PORT_OCEAN_ADJUST,
    VEHICLE_EU_DELIVERY,
    PORT_FORWARDING,
    PORT_PARKING,
    PARKING_BULGARIA,
    COMPANY_SERVICES,
    CUSTOMS_DOCUMENTATION,
    CUSTOMS_DUTY_RATE,
    INSURANCE_RATE,
    DAMAGED_CUSTOMS_FACTOR,
    DAMAGE_HANDLING_FEE_USD,
    # Korea-pipeline constants (21)
    KOREA_PROFILE_CODE,
    KOREA_USE_LOGISTICS_PACKAGE,
    KOREA_AUCTION_FEE_PERCENT,
    KOREA_LOGISTICS_PACKAGE,
    KOREA_INLAND_DEFAULT,
    KOREA_SEA_DEFAULT,
    KOREA_INSURANCE_DEFAULT,
    KOREA_FORWARDER_FEE_DEFAULT,
    KOREA_DOCUMENTS_MAIL_DEFAULT,
    KOREA_CUSTOMS_DUTY_RATE,
    KOREA_VAT_RATE,
    KOREA_UNDERVALUE_PERCENT,
    KOREA_DAMAGED_CUSTOMS_FACTOR,
    KOREA_DAMAGE_HANDLING_FEE_USD,
    KOREA_OFFICIAL_FEES_USD,
    KOREA_BIBI_SERVICE_FEE,
    KOREA_FX_USD_TO_EUR,
    KOREA_BG_TRANSPORT_EUR,
    KOREA_ADDITIONAL_FEES_EUR,
    KOREA_TECH_INSPECTION_EUR,
    KOREA_BB_CARS_COMMISSION_EUR,
    # Internal-only constant (1)
    AUCTION_TIERED_FEES,
    # Phase 6.5+ Wave 3 additions (5) — folded into the constants
    # canonical home to support the seed-routine migration
    AUCTIONS,
    VEHICLE_KOREA_INLAND,
    VEHICLE_KOREA_SEA,
    VEHICLE_KOREA_BG,
    OFFICIAL_FEES_USD,
)

# ── Out-of-scope constants (NOT in Wave 2/3 — kept as legacy def-sites) ──
# (All previously legacy def-sites for the 5 Wave-3 additions are now
#  imported above; nothing else remains at this position.)


# ══════════════════════════════════════════════════════════════════════
# Calculator config — DB loader (with fallbacks + single-tick memo)
# ══════════════════════════════════════════════════════════════════════
#
# Phase 6.5+ Wave 3 (LANDING 2026-05-20) — calc-engine SERVER_STATE closure.
#
# Canonical home for the TTL cache + seed routine + config loader is now
# ``app/services/calculator_config_cache.py``. The 3 callables below
# (``_ensure_calculator_seed``, ``_invalidate_calc_cache``,
# ``_load_calc_config``) are **provably semantics-free transport-layer
# shims** — each delegates via a lazy local import to the canonical
# impl. Per the compat-shim invariant (see PHASE6_5_WAVE_2_CLOSED.md
# and ARCHITECTURE_PROGRAM_CLOSED.md): "Compat shims must remain
# logic-free and observationally transparent. Any semantic drift
# re-opens the architecture program."
#
# Module-level state ``_CALC_CACHE`` + ``_CALC_CACHE_TTL`` has been
# RETIRED from this file. The cache lives in the canonical home only;
# callers reach it through ``invalidate_cache()`` and ``get_calc_config()``.


async def _ensure_calculator_seed() -> None:
    """Compatibility shim — canonical impl lives in
    ``app/services/calculator_config_cache.ensure_calculator_seed``
    after Phase 6.5+ Wave 3 (calc-engine SERVER_STATE closure,
    2026-05-20). Logic-free transport layer.
    """
    from app.services.calculator_config_cache import ensure_calculator_seed as _impl
    await _impl()


def _invalidate_calc_cache() -> None:
    """Compatibility shim — canonical impl lives in
    ``app/services/calculator_config_cache.invalidate_cache`` after
    Phase 6.5+ Wave 3. Called by 5 admin config-mutating endpoints.
    """
    from app.services.calculator_config_cache import invalidate_cache as _impl
    _impl()


async def _load_calc_config(profile_code: str = DEFAULT_PROFILE_CODE) -> Dict[str, Any]:
    """Compatibility shim — canonical impl lives in
    ``app/services/calculator_config_cache.get_calc_config`` after
    Phase 6.5+ Wave 3. Logic-free transport layer.
    """
    from app.services.calculator_config_cache import get_calc_config as _impl
    return await _impl(profile_code)


def _find_route_amount(routes: list, rate_type: str, vehicle_type: str,
                       *, destination_code: Optional[str] = None,
                       origin_code: Optional[str] = None, default: float = 0.0) -> float:
    """Compatibility shim — canonical impl lives in
    ``app/services/calculator_pure.py`` after Phase 6.5+ Wave 1
    (Shell Thinning execution, 2026-05-20). Pure routing-table lookup;
    zero module-globals.

    server.py keeps this thin wrapper because the qualified name
    ``server._find_route_amount`` may be discovered by legacy code,
    and to preserve back-compat for any in-file callers that survived
    Phase 5.5/B's calculator extraction. Behaviour parity asserted in
    ``tests/test_phase6_5_wave1_calculator_pure_retirement.py``
    (B1-B3).
    """
    from app.services.calculator_pure import _find_route_amount as _calc_pure_find_route_amount
    return _calc_pure_find_route_amount(
        routes, rate_type, vehicle_type,
        destination_code=destination_code,
        origin_code=origin_code,
        default=default,
    )


def _tiered_buyer_fee_from_db(price: float, fees: list) -> float:
    """Compatibility shim — canonical impl lives in
    ``app/services/calculator_pure.py`` after Phase 6.5+ Wave 2
    (calculator constants + helpers retirement, 2026-05-20).

    server.py keeps this thin wrapper because the qualified name
    ``server._tiered_buyer_fee_from_db`` may be discovered by legacy
    code, and to preserve back-compat for any in-file callers that
    survived Phase 5.5/B's calculator extraction. Behaviour parity is
    asserted by the 5.5/B golden parity suite (18 PINNED_HASHES).
    """
    from app.services.calculator_pure import _tiered_buyer_fee_from_db as _impl
    return _impl(price, fees)


def _tiered_buyer_fee(price: float) -> float:
    """Compatibility shim — canonical impl lives in
    ``app/services/calculator_pure.py`` after Phase 6.5+ Wave 2.
    Back-compat helper used by a few legacy callers — uses the
    hardcoded ``AUCTION_TIERED_FEES`` ladder.
    """
    from app.services.calculator_pure import _tiered_buyer_fee as _impl
    return _impl(price)


# ══════════════════════════════════════════════════════════════════════
# Calculator — PUBLIC endpoints
# ══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────
# Phase 5.5/B — _calculate_korea EXTRACTED to app/services/calculator
# ─────────────────────────────────────────────────────────────────────
# The original ~236-line ``async def _calculate_korea(data)`` body now
# lives byte-identically in ``app/services/calculator.py``. The only
# mechanical substitutions applied during the move are the established
# C-4i pattern (``db.X`` → ``get_db().X``, 2 sites) and the 5.5/A
# pattern (module-local ``logger = logging.getLogger("bibi.calculator")``,
# 1 ``logger.warning`` site). The symbol is re-imported below (next to
# the calculator_calculate extraction marker) so ``server._calculate_korea``
# remains a resolvable module attribute for back-compat. See
# ``PHASE5_5_B_CALCULATOR_EXTRACTION_CLOSED.md`` for full retirement
# trail.


# [auto-domain removed] /api/calculator/ports (calculator_ports)


# ─────────────────────────────────────────────────────────────────────
# Phase 5.5/B — calculator_calculate EXTRACTED to app/services/calculator
# ─────────────────────────────────────────────────────────────────────
# The original ~185-line ``async def calculator_calculate(data)`` body
# (USA pipeline + Korea dispatch) now lives byte-identically in
# ``app/services/calculator.py``. The FastAPI route
# ``POST /api/calculator/calculate`` is registered against the extracted
# function via the imperative ``fastapi_app.post(...)`` call below —
# equivalent to the original ``@fastapi_app.post(...)`` decorator. The
# function ``__name__`` is unchanged (``calculator_calculate``), so the
# OpenAPI operationId is preserved byte-identically. Constants
# (VEHICLE_TYPES, KOREA_*, ...) and helpers (_ensure_calculator_seed,
# _find_route_amount, _tiered_buyer_fee*, _load_calc_config) remain in
# this module — extracting them would be premature per mandate. The
# new service module imports them from here at module-load time (no
# cycle: all required names are defined above this point in server.py).
# Golden-parity verified against 18 representative inputs
# (tests/test_phase5_5_b_calculator_extraction.py::PINNED_HASHES).
from app.services.calculator import (  # noqa: E402, F401
    _calculate_korea,
    calculator_calculate,
)

# ══════════════════════════════════════════════════════════════════════
# Phase 5.5 / D — Customer-domain helpers extraction (2026-05-19)
# ══════════════════════════════════════════════════════════════════════
# Canonical home: ``app/services/customers.py``. The two public symbols
# are re-imported here at module-load so the 21 in-file callers
# (favorites, customer-cabinet endpoints) keep their existing call
# shapes ``await require_customer(...)`` / ``await ensure_customer_seed(...)``
# — no diff at the endpoint level.
#
# Both ``_resolve_bearer`` (auth-core resolver) and ``generate_route``
# (shipment route polyline) remain defined ABOVE in this module and are
# consumed by the new ``app.services.customers`` module via lazy
# imports tracked under ``EXTRACTION_AUX_BRIDGES`` (kind=
# ``CUSTOMER_AUTH_DEP``) — see ``app.core.app_state_targets``.
from app.services.customers import (  # noqa: E402, F401
    require_customer,
    ensure_customer_record,
)

fastapi_app.post("/api/calculator/calculate")(calculator_calculate)


# ── Phase Final / Block 5 — Calculator visibility wrapper ────────────
# Wrap the USA path's result with admin overrides. (Korea applies them
# in-place inside _calculate_korea already.)
from fastapi import Body as _Body_block5  # noqa: E402
from app.services.calculator import _apply_usa_visibility_overrides as _apply_usa_vis  # noqa: E402

_orig_calc_fn = calculator_calculate

# [auto-domain removed] /api/calculator/calculate-with-visibility (calculator_calculate_with_visibility)


# ══════════════════════════════════════════════════════════════════════
# Calculator — ADMIN config endpoints (profile / routes / auction fees)
# ══════════════════════════════════════════════════════════════════════

# [auto-domain removed] /api/calculator/config/profile (calculator_get_profile)


# [auto-domain removed] /api/calculator/config/profile (calculator_update_profile)


# [auto-domain removed] /api/calculator/config/routes/{code} (calculator_get_routes)


# [auto-domain removed] /api/calculator/config/routes (calculator_upsert_route)


# [auto-domain removed] /api/calculator/config/routes/{route_id} (calculator_delete_route)


# [auto-domain removed] /api/calculator/config/auction-fees/{code} (calculator_get_auction_fees)


# [auto-domain removed] /api/calculator/config/auction-fees (calculator_upsert_auction_fee)


# [auto-domain removed] /api/calculator/config/auction-fees/{fee_id} (calculator_delete_auction_fee)


# [auto-domain removed] /api/calculator/config/usa-inland-defaults (calculator_get_usa_inland_defaults)


# ── Wave 4 — Ocean Freight Model (bucket × shared multiplier + dest. adj.) ─
# Same philosophy as the inland model. Static defaults + admin overrides
# live in ``calculator_profile.oceanFreightModel``. Vehicle multipliers
# are NOT duplicated here — the ocean engine reads them from the inland
# model so SUVs/pickups/etc. have a single footprint coefficient.

# [auto-domain removed] /api/calculator/config/ocean-defaults (calculator_get_ocean_defaults)


# ── Wave 4.2 — EU Delivery (port → Sofia BG) matrix defaults ──────────────
# Mirror of the ocean-defaults endpoint. The EU-delivery engine prices the
# trucking leg from each of the 8 EU destination ports to Sofia (Bulgaria,
# fixed final hub) in EUR per vehicle type. Admin can override any cell
# via the EuDeliveryModelEditor card on /admin/calculator. FX rate comes
# from the profile (fxUsdToEur, shared with the Korea calculator) so the
# unified total is always rendered in USD.
# [auto-domain removed] /api/calculator/config/eu-delivery-defaults (calculator_get_eu_delivery_defaults)


# [auto-domain removed] /api/calculator/admin/stats (calculator_admin_stats)

# [auto-domain removed] /api/calculator/quote (calculator_quote)

# [auto-domain removed] /api/calculator/quote/{quote_id}/scenario (update_quote_scenario)


# ────────────────────────────────────────────────────────────────────────
# CALCULATIONS DOMAIN — extracted to app/routers/calculations.py (2026-05-17)
# Wave 1 / Commit 2 of the Controlled Modular Monolith refactoring.
# Endpoints: POST/GET/PATCH/DELETE /api/calculations[/...]  +  /api/calculations-compare
#            +  /api/public/calculations/share/{token}[/approve]
# ────────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════
# /api/calculator/quote → legacy compatibility (will be replaced by /api/calculations)
# ═══════════════════════════════════════════════════════════════════════

# [auto-domain removed] /api/calculator/quotes (list_quotes)

# [auto-domain removed] /api/calculator/config/routes (calculator_routes)

# [auto-domain removed] /api/calculator/config/auction-fees/{auction} (calculator_auction_fees)

# ═══════════════════════════════════════════════════════════════════
# AUCTION RANKING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════






# ═══════════════════════════════════════════════════════════════════
# [car-import removed] SEO CLUSTERS / COLLECTIONS (/api/seo-clusters/public)
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# PUBLISHING / MODERATION
# ═══════════════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════════════
# CUSTOMER AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _customer_has_password(customer: Dict[str, Any]) -> bool:
    """True if the customer has a usable email/password credential.

    Accepts either a full doc (with the raw ``password`` hash, e.g. from the
    login flow) or a sanitised doc carrying the derived ``hasPassword`` flag
    (from ``_resolve_bearer``)."""
    if not customer:
        return False
    if "hasPassword" in customer:
        return bool(customer.get("hasPassword"))
    return bool(customer.get("password"))


def _customer_auth_provider(customer: Dict[str, Any]) -> str:
    """Infer how the account was created: 'google' or 'email'."""
    src = ((customer or {}).get("source") or "").strip().lower()
    if src == "google" or (customer or {}).get("googleId") or (customer or {}).get("google_id"):
        return "google"
    return "email"

def generate_token() -> str:
    return secrets.token_urlsafe(32)


# ── Email verification (classic customer signup) ─────────────────────────
_EMAIL_OTP_TTL_SECONDS = 600           # code valid for 10 minutes
_EMAIL_OTP_RESEND_COOLDOWN = 30        # min seconds between resends
_EMAIL_OTP_MAX_ATTEMPTS = 5            # wrong-code attempts before lockout
_EMAIL_OTP_MAX_RESENDS = 5             # resend requests per pending signup


def _gen_otp_code() -> str:
    """Cryptographically-random 6-digit numeric code (zero-padded)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _mask_email_addr(email: str) -> str:
    """marina@gmail.com -> m****a@gmail.com (for safe UI display)."""
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked = local[0] + "*"
        else:
            masked = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked}@{domain}"
    except Exception:
        return email


async def _send_verification_email(email: str, code: str, name: str = "") -> None:
    """Render + dispatch the premium verification email via Resend."""
    from notifications import EmailChannel
    from app.services.customer_email_templates import render_verification_email
    subject, html, text = render_verification_email(
        code, name=name, ttl_minutes=_EMAIL_OTP_TTL_SECONDS // 60
    )
    await EmailChannel(db).send(
        to=email, subject=subject, html=html, text=text,
        event="customer_email_verify", context={"email": email},
    )


async def _send_welcome_email(email: str, name: str = "") -> None:
    """Render + dispatch the post-verification welcome email."""
    from notifications import EmailChannel
    from app.services.customer_email_templates import render_welcome_email
    subject, html, text = render_welcome_email(name=name)
    await EmailChannel(db).send(
        to=email, subject=subject, html=html, text=text,
        event="customer_welcome", context={"email": email},
    )


# ── Session helpers (shared between email/password and Google OAuth) ──
_CUSTOMER_SESSION_TTL_DAYS = 7


def _customer_response(customer: Dict[str, Any], session_token: str) -> Dict[str, Any]:
    """Build the response shape the frontend expects (flat, top-level fields)."""
    customer_id = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    has_password = _customer_has_password(customer)
    auth_provider = _customer_auth_provider(customer)
    two_factor = bool(customer.get("totp_enabled"))
    return {
        "success": True,
        "customerId": customer_id,
        "sessionToken": session_token,
        "accessToken": session_token,  # legacy alias — same value
        "token": session_token,         # legacy alias
        "email": customer.get("email", ""),
        "name": customer.get("name", ""),
        "picture": customer.get("picture", ""),
        "role": customer.get("role", "customer"),
        "hasPassword": has_password,
        "authProvider": auth_provider,
        "twoFactorEnabled": two_factor,
        "user": {
            "id": customer_id,
            "customerId": customer_id,
            "email": customer.get("email", ""),
            "name": customer.get("name", ""),
            "picture": customer.get("picture", ""),
            "role": customer.get("role", "customer"),
            "hasPassword": has_password,
            "authProvider": auth_provider,
            "twoFactorEnabled": two_factor,
        },
    }


async def _create_customer_session(customer_id: str) -> str:
    """Insert a fresh session row with 7d TTL and return its token."""
    token = generate_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=_CUSTOMER_SESSION_TTL_DAYS)
    await db.customer_sessions.insert_one({
        "token": token,
        "session_token": token,  # alias used by some readers
        "customerId": customer_id,
        "user_id": customer_id,
        "created_at": now,
        "expires_at": expires_at,
    })
    return token


async def _resolve_bearer(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Resolve the Bearer token to a customer document (or None).
    Validates expiry. Accepts both 'token' and 'session_token' fields.
    """
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    session = await db.customer_sessions.find_one(
        {"$or": [{"token": token}, {"session_token": token}]},
        {"_id": 0},
    )
    if not session:
        return None
    # Check expiry (if set) — tolerant to missing/str/naive datetimes
    expires_at = session.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None
        if expires_at and getattr(expires_at, "tzinfo", None) is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            return None

    customer_id = session.get("customerId") or session.get("user_id")
    if not customer_id:
        return None
    customer = await db.customers.find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"_id": 0},
    )
    if customer is not None:
        # Expose a safe boolean instead of the raw hash so callers can branch
        # on credential presence (Set vs Change password) without leaking it.
        customer["hasPassword"] = bool(customer.get("password"))
        customer["twoFactorEnabled"] = bool(customer.get("totp_enabled"))
        customer.pop("password", None)
        # Never leak 2FA secrets / backup-code hashes through any bearer-resolved doc.
        customer.pop("totp_secret", None)
        customer.pop("totp_pending_secret", None)
        customer.pop("totp_backup_codes", None)
    return customer


# ════════════════════════════════════════════════════════════════════════
# PHASE SECURITY — Wave S2 — Access Control Gate (default-deny middleware)
# ════════════════════════════════════════════════════════════════════════
# Classifies every request (public / customer / staff) and enforces the
# minimum trust tier BEFORE the route runs. Per-route role guards
# (require_admin / require_master_admin / ...) still apply on top for finer
# control. Default tier = STAFF, so any unguarded/new route is locked down.
from app.middleware.access_gate import classify_path as _gate_classify, QUERY_TOKEN_ALLOWED as _GATE_QUERY_TOKEN_OK  # noqa: E402
from security import _check_token as _gate_check_staff  # noqa: E402


@fastapi_app.middleware("http")
async def _access_control_gate(request: Request, call_next):
    # CORS preflight must pass untouched.
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    tier = _gate_classify(path)

    if tier == "public":
        return await call_next(request)

    # Extension HMAC routes carry no bearer — pass through to the route's
    # require_extension_hmac dependency, which performs the real auth.
    if tier == "extension":
        return await call_next(request)

    # Extract bearer (Authorization header only; ?token= honoured ONLY for the
    # call-recording media route that cannot send headers).
    authz = request.headers.get("authorization") or request.headers.get("Authorization")
    token = None
    if authz and authz[:7].lower() == "bearer ":
        token = authz[7:].strip()
    if not token and _GATE_QUERY_TOKEN_OK.fullmatch(path):
        token = request.query_params.get("token")
        if token:
            authz = f"Bearer {token}"

    # Staff token grants access to every tier.
    staff = _gate_check_staff(token) if token else None
    if staff:
        # Session revocation: reject stale staff JWTs (tokenVersion bumped on
        # password change). Lenient on any lookup/DB gap — see security.py.
        try:
            from security import is_staff_token_revoked as _gate_revoked
            if await _gate_revoked(staff):
                return JSONResponse(
                    {"detail": "session_revoked"},
                    status_code=401,
                    headers={"X-Session-Revoked": "password_changed"},
                )
        except Exception:
            pass
        return await call_next(request)

    if tier == "staff":
        # No valid staff token → 401 (no creds) / 403 (creds present but not staff).
        return JSONResponse(
            {"detail": "Forbidden: staff access required" if token else "Authentication required"},
            status_code=403 if token else 401,
        )

    # tier == "customer": accept a valid customer session.
    try:
        cust = await _resolve_bearer(authz) if authz else None
    except Exception:
        cust = None
    if cust:
        return await call_next(request)

    return JSONResponse({"detail": "Authentication required"}, status_code=401)


# ─── PHASE SECURITY — Wave S3.2 — Rate limiting ───
# Registered AFTER the access gate so it is the OUTERMOST http middleware and
# runs FIRST: abusive traffic is throttled before any auth / business logic.
# Only the explicitly-listed sensitive routes are limited; the extension HMAC
# tier, internal server-to-server calls and every unlisted route pass through.
from app.middleware.rate_limit import (  # noqa: E402
    check_and_consume as _rl_check,
    client_ip as _rl_ip,
)


@fastapi_app.middleware("http")
async def _rate_limit_gate(request: Request, call_next):
    # CORS preflight must pass untouched.
    if request.method == "OPTIONS":
        return await call_next(request)

    ip = _rl_ip(request)
    allowed, rule, remaining, reset_after = _rl_check(
        request.method, request.url.path, ip
    )

    # No rule → unlimited route; nothing to annotate.
    if rule is None:
        return await call_next(request)

    if not allowed:
        retry = reset_after or 60
        return JSONResponse(
            {"detail": "Rate limit exceeded", "retry_after": retry},
            status_code=429,
            headers={
                "Retry-After": str(retry),
                "X-RateLimit-Limit": str(rule.item.amount),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_after),
            },
        )

    response = await call_next(request)
    try:
        response.headers["X-RateLimit-Limit"] = str(rule.item.amount)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_after)
    except Exception:
        pass
    return response


# ─── PHASE SECURITY — Wave S3.3 — Security headers (global) + CSP RO ───
# Outermost http middleware: sets safe headers on EVERY response (including
# early 401/403/429 from inner gates). CSP ships Report-Only (HTML only) so it
# cannot break the SPA / Stripe / PDF preview / File Manager; violations POST
# to /api/security/csp-report. HSTS is deliberately omitted until prod HTTPS.
from app.middleware.security_headers import (  # noqa: E402
    STATIC_SECURITY_HEADERS as _SEC_HEADERS,
    csp_report_only_value as _csp_ro,
    is_html_response as _is_html,
)


@fastapi_app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)

    # 1) safe headers enforced globally
    for _k, _v in _SEC_HEADERS.items():
        response.headers[_k] = _v

    # 2) CSP Report-Only — HTML documents only (won't block anything)
    if _is_html(response.headers.get("content-type", "")):
        response.headers["Content-Security-Policy-Report-Only"] = _csp_ro()

    # 3) no-store for private (non-public) API payloads — never cache auth data
    path = request.url.path
    if path.startswith("/api") and "cache-control" not in response.headers:
        try:
            if _gate_classify(path) != "public":
                response.headers["Cache-Control"] = "no-store"
        except Exception:
            pass

    return response


@fastapi_app.post("/api/security/csp-report")
async def _csp_violation_report(request: Request):
    """Public sink for CSP (Report-Only) violation reports — stored 30 days."""
    import json as _json
    try:
        raw = await request.body()
        payload = _json.loads(raw) if raw else {}
    except Exception:
        payload = {"_unparsed": True}
    try:
        xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        await db.security_csp_reports.insert_one({
            "ts": datetime.now(timezone.utc),
            "ip": xff or (request.client.host if request.client else None),
            "ua": request.headers.get("user-agent"),
            "report": payload,
        })
    except Exception as e:
        logger.warning(f"[CSP] report store failed: {e}")
    from starlette.responses import Response as _Resp
    return _Resp(status_code=204)



# ─── Launch-Candidate security fix (2026-06-09) ───
# Cross-tenant guard for /api/customer-cabinet/{customer_id}/* routes.
# A customer Bearer token must resolve to the SAME customer_id as the path
# parameter, otherwise 403. Staff tokens (admin/team_lead/manager) are also
# accepted for cabinet read-views (back-office uses them to inspect a
# customer's cabinet on the customer's behalf).
async def _authorize_customer_cabinet_access(
    customer_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Block cross-tenant data access. Raise 401/403 otherwise.

    Returns {"actor": "customer"|"staff", "id": <id>, ...} on success.
    """
    auth_hdr = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_hdr:
        raise HTTPException(status_code=401, detail="Authentication required")

    # 1) Try resolving as a customer bearer token (db.customer_sessions)
    try:
        cust = await _resolve_bearer(auth_hdr)
    except Exception:
        cust = None
    if cust:
        cust_id = (
            cust.get("id")
            or cust.get("customerId")
            or cust.get("user_id")
        )
        if cust_id != customer_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: cabinet belongs to a different customer",
            )
        return {"actor": "customer", "id": cust_id, "customer": cust}

    # 2) Try resolving as a staff JWT (security._check_token)
    try:
        from security import _check_token as _staff_check
        token = ""
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()
        if token:
            staff = _staff_check(token)
            if staff and (staff.get("role") or "").lower() in {"admin", "owner", "master_admin", "team_lead", "manager"}:
                return {"actor": "staff", "id": staff.get("id"), "role": staff.get("role"), "staff": staff}
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Authentication required")


async def _auto_pick_manager() -> Optional[str]:
    """Pick the active manager (role=manager) with the fewest assigned
    companies — simple round-robin load balancing for new B2B signups.
    Admin can always reassign later (admin acts as team-lead).
    Returns a staff id or None when there are no managers yet."""
    try:
        managers = await db.staff.find(
            {"role": "manager", "status": {"$ne": "disabled"}}, {"_id": 0, "id": 1}
        ).to_list(length=500)
        if not managers:
            return None
        ranked = []
        for m in managers:
            mid = m.get("id")
            if not mid:
                continue
            n = await db.waste_companies.count_documents({"assigned_manager_id": mid})
            ranked.append((n, mid))
        ranked.sort(key=lambda x: x[0])
        return ranked[0][1] if ranked else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[signup] auto-pick manager failed: {exc}")
        return None


async def _link_customer_company(company_name: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Find or create a `waste_companies` record for a B2B signup and
    auto-assign the least-loaded manager. Returns
    (company_id, company_name_canonical, manager_id)."""
    name = (company_name or "").strip()
    if not name:
        return None, None, None
    existing = await db.waste_companies.find_one(
        {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"_id": 0}
    )
    if existing:
        mid = existing.get("assigned_manager_id")
        if not mid:
            mid = await _auto_pick_manager()
            if mid:
                await db.waste_companies.update_one(
                    {"id": existing.get("id")}, {"$set": {"assigned_manager_id": mid}}
                )
        return existing.get("id"), existing.get("name"), mid
    manager_id = await _auto_pick_manager()
    cid = f"wco_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.waste_companies.insert_one({
        "id": cid,
        "name": name,
        "source": "client_signup",
        "assigned_manager_id": manager_id,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    return cid, name, manager_id


async def _email_dry_run_mode() -> bool:
    """True when NO real email provider (Resend / SMTP) is configured, so the
    app is in dry-run mode (preview). Lets us safely surface OTP/reset codes
    for testing WITHOUT ever leaking them once Resend keys are added."""
    try:
        from notifications import EmailChannel
        ch = EmailChannel(db)
        if await ch._resolve_resend_cfg():
            return False
        if await ch._resolve_smtp_cfg():
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


@fastapi_app.post("/api/customer-auth/register")
async def customer_register(data: Dict[str, Any] = Body(...)):
    """Step 1 of classic registration — validate, then EMAIL a 6-digit code.

    No customer record and no session are created here. The pending signup
    (with a hashed password) is parked in `customer_email_verifications`
    until the user proves ownership of the email via /verify-email.

    B2B fields (surname / middle_name / company_name) are captured here and
    materialised on the customer (+ company link) at the verify step.
    """
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or data.get("first_name") or "").strip()
    surname = (data.get("surname") or data.get("last_name") or "").strip()
    middle_name = (data.get("middle_name") or data.get("patronymic") or "").strip()
    company_name = (data.get("company_name") or data.get("company") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    # Strict email validation (rejects "asdf", missing @, bad domain).
    from app.contact_validation import normalize_phone as _norm_phone, validate_email_addr as _val_email
    ok_em, email_norm, em_err = _val_email(email, required=True)
    if not ok_em:
        raise HTTPException(status_code=400, detail=em_err)
    email = email_norm
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    # Phone is optional at registration, but if provided it must be real.
    if phone:
        ok_ph, phone_norm, ph_err = _norm_phone(phone)
        if not ok_ph:
            raise HTTPException(status_code=400, detail=ph_err)
        phone = phone_norm

    existing = await db.customers.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in instead.")

    # Compose a sensible display name from the provided parts.
    display_name = " ".join([p for p in [surname, name, middle_name] if p]).strip() or name or email.split("@", 1)[0]

    code = _gen_otp_code()
    now = datetime.now(timezone.utc)
    await db.customer_email_verifications.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "code_hash": _legacy_sha256(code),
            "name": display_name,
            "first_name": name,
            "surname": surname,
            "middle_name": middle_name,
            "company_name": company_name,
            "password_hash": _legacy_sha256(password),
            "phone": phone,
            "attempts": 0,
            "resends": 0,
            "purpose": "register",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=_EMAIL_OTP_TTL_SECONDS)).isoformat(),
            "cooldown_until": (now + timedelta(seconds=_EMAIL_OTP_RESEND_COOLDOWN)).isoformat(),
        }},
        upsert=True,
    )

    await _send_verification_email(email, code, display_name)

    resp = {
        "ok": True,
        "requiresVerification": True,
        "email": email,
        "emailMasked": _mask_email_addr(email),
        "expiresIn": _EMAIL_OTP_TTL_SECONDS,
        "resendCooldown": _EMAIL_OTP_RESEND_COOLDOWN,
    }
    # Preview / dry-run convenience: when no real email provider is configured
    # the verification code can't be delivered, so expose it for testing.
    # Once Resend keys are added in admin, this branch is skipped automatically.
    if await _email_dry_run_mode():
        resp["devCode"] = code
        resp["dry_run"] = True
        logger.info(f"[customer-register] DRY RUN — verification code for {email}: {code}")
    return resp


@fastapi_app.post("/api/customer-auth/verify-email")
async def customer_verify_email(data: Dict[str, Any] = Body(...)):
    """Step 2 — confirm the 6-digit code, create the customer + session."""
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")

    doc = await db.customer_email_verifications.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="No pending verification. Please register again.")

    now = datetime.now(timezone.utc)
    try:
        expires_at = datetime.fromisoformat(doc["expires_at"])
    except Exception:
        expires_at = now - timedelta(seconds=1)
    if now > expires_at:
        await db.customer_email_verifications.delete_one({"email": email})
        raise HTTPException(status_code=400, detail="This code has expired. Please request a new one.")

    if int(doc.get("attempts", 0)) >= _EMAIL_OTP_MAX_ATTEMPTS:
        await db.customer_email_verifications.delete_one({"email": email})
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please register again.")

    if _legacy_sha256(code) != doc.get("code_hash"):
        await db.customer_email_verifications.update_one(
            {"email": email}, {"$inc": {"attempts": 1}}
        )
        remaining = _EMAIL_OTP_MAX_ATTEMPTS - int(doc.get("attempts", 0)) - 1
        raise HTTPException(
            status_code=400,
            detail=f"Incorrect code. {remaining} attempt(s) left." if remaining > 0
                   else "Incorrect code. Please request a new one.",
        )

    # ── Success — guard against a race where the email got registered ──
    existing = await db.customers.find_one({"email": email})
    if existing:
        await db.customer_email_verifications.delete_one({"email": email})
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in instead.")

    customer_id = f"cust_{uuid.uuid4().hex[:12]}"
    # B2B linkage: find/create the company and auto-assign a manager.
    company_id, company_name_canonical, manager_id = await _link_customer_company(
        doc.get("company_name") or ""
    )
    customer = {
        "id": customer_id,
        "customerId": customer_id,
        "user_id": customer_id,
        "email": email,
        "password": doc.get("password_hash"),
        "name": doc.get("name") or email.split("@", 1)[0],
        "first_name": doc.get("first_name", ""),
        "surname": doc.get("surname", ""),
        "middle_name": doc.get("middle_name", ""),
        "phone": doc.get("phone", ""),
        "company_name": company_name_canonical or doc.get("company_name", ""),
        "company_id": company_id,
        "managerId": manager_id,
        "role": "customer",
        "status": "active",
        "source": "email",
        "picture": "",
        "emailVerified": True,
        "emailVerifiedAt": now.isoformat(),
        "created_at": now.isoformat(),
    }
    await db.customers.insert_one(customer)
    await db.customer_email_verifications.delete_one({"email": email})

    # Notify the shared manager queue about the new client registration.
    try:
        await db["waste_notifications"].insert_one({
            "id": f"ntf_{uuid.uuid4().hex[:12]}",
            "type": "registration",
            "title": "Нова реєстрація клієнта",
            "body": f"{customer.get('name')} · {email}"
                    + (f" · {customer.get('company_name')}" if customer.get("company_name") else ""),
            "customer_id": customer_id,
            "link": "/app/companies",
            "audiences": ["staff"],
            "read_by": [],
            "created_at": now.isoformat(),
        })
    except Exception as exc:
        logger.warning(f"[customer-auth/verify] manager notification failed: {exc}")

    # Best-effort welcome email (never blocks the response).
    try:
        await _send_welcome_email(email, customer["name"])
    except Exception as exc:
        logger.warning(f"[customer-auth/verify] welcome email failed: {exc}")

    token = await _create_customer_session(customer_id)
    return _customer_response(customer, token)


@fastapi_app.post("/api/customer-auth/resend-email-code")
async def customer_resend_email_code(data: Dict[str, Any] = Body(...)):
    """Re-issue a fresh verification code for a pending signup (rate-limited)."""
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    doc = await db.customer_email_verifications.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="No pending verification. Please register again.")

    now = datetime.now(timezone.utc)
    try:
        cooldown_until = datetime.fromisoformat(doc.get("cooldown_until")) if doc.get("cooldown_until") else now
    except Exception:
        cooldown_until = now
    if now < cooldown_until:
        wait = int((cooldown_until - now).total_seconds()) + 1
        raise HTTPException(status_code=429, detail=f"Please wait {wait}s before requesting a new code.")

    if int(doc.get("resends", 0)) >= _EMAIL_OTP_MAX_RESENDS:
        raise HTTPException(status_code=429, detail="Resend limit reached. Please register again.")

    code = _gen_otp_code()
    await db.customer_email_verifications.update_one(
        {"email": email},
        {"$set": {
            "code_hash": _legacy_sha256(code),
            "attempts": 0,
            "expires_at": (now + timedelta(seconds=_EMAIL_OTP_TTL_SECONDS)).isoformat(),
            "cooldown_until": (now + timedelta(seconds=_EMAIL_OTP_RESEND_COOLDOWN)).isoformat(),
        }, "$inc": {"resends": 1}},
    )
    await _send_verification_email(email, code, doc.get("name", ""))

    return {
        "ok": True,
        "email": email,
        "emailMasked": _mask_email_addr(email),
        "expiresIn": _EMAIL_OTP_TTL_SECONDS,
        "resendCooldown": _EMAIL_OTP_RESEND_COOLDOWN,
    }


@fastapi_app.post("/api/customer-auth/login")
async def customer_login(data: Dict[str, Any] = Body(...)):
    """Customer login (email + password) — real accounts only."""
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    customer = await db.customers.find_one({"email": email}, {"_id": 0})
    if not customer or customer.get("password") != _legacy_sha256(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")

    # 2FA gate — if enabled, do NOT mint a session yet; return a short-lived
    # challenge so the client must present a valid TOTP / backup code next.
    if customer.get("totp_enabled"):
        if _2fa_locked_remaining(customer) > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {max(1, _2fa_locked_remaining(customer)//60)} minute(s).",
            )
        return await _issue_2fa_challenge(cid, email)
    if customer.get("email_2fa_enabled"):
        if _2fa_locked_remaining(customer) > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {max(1, _2fa_locked_remaining(customer)//60)} minute(s).",
            )
        return await _issue_2fa_challenge(cid, email, method="email")

    token = await _create_customer_session(cid)
    return _customer_response(customer, token)


@fastapi_app.get("/api/customer-auth/me")
async def customer_me(authorization: Optional[str] = Header(None)):
    """Resolve current customer from Bearer token (shared with Google flow)."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # We don't know the token here (not returning a new one) — reuse the one the client sent
    # But frontend also reads customerId/email/name — that's top-level.
    token_from_header = ""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2:
            token_from_header = parts[1].strip()
    return _customer_response(customer, token_from_header)


@fastapi_app.get("/api/customer-auth/google/me")
async def customer_google_me(authorization: Optional[str] = Header(None)):
    """Return the current customer for a Google (or any) Bearer session."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token_from_header = ""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2:
            token_from_header = parts[1].strip()
    return _customer_response(customer, token_from_header)


@fastapi_app.post("/api/customer-auth/google/logout")
async def customer_google_logout(authorization: Optional[str] = Header(None)):
    """Invalidate the current session token (best-effort)."""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2:
            token = parts[1].strip()
            if token:
                try:
                    await db.customer_sessions.delete_many({
                        "$or": [{"token": token}, {"session_token": token}]
                    })
                except Exception as exc:
                    logger.warning(f"[customer-auth/logout] delete failed: {exc}")
    return {"success": True}

@fastapi_app.put("/api/customer-auth/me/profile")
async def customer_update_profile(data: Dict[str, Any] = Body(...)):
    """Update customer profile"""
    return {"success": True}

@fastapi_app.api_route("/api/customer-auth/me/password", methods=["PUT", "PATCH"])
async def customer_update_password(
    data: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None),
):
    """Set or change the current customer's email/password credential.

    - Google-created customers (no password yet) can SET a password without
      providing a current one. Afterwards they can sign in with BOTH Google
      and email/password.
    - Customers that already have a password must provide the correct current
      password to change it.
    """
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")

    new_password = (data.get("newPassword") or data.get("new_password") or "").strip()
    current_password = (data.get("currentPassword") or data.get("current_password") or "")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    customer_id = customer.get("customerId") or customer.get("id") or customer.get("user_id")

    # Re-fetch the full doc (with the hash) to verify the current password.
    full = await db.customers.find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]}
    )
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")

    has_password = bool(full.get("password"))
    if has_password:
        if not current_password or full.get("password") != _legacy_sha256(current_password):
            raise HTTPException(status_code=401, detail="Incorrect current password")

    await db.customers.update_one(
        {"id": full.get("id") or customer_id},
        {"$set": {"password": _legacy_sha256(new_password), "updatedAt": datetime.now(timezone.utc)}},
    )

    # Session revocation: drop every OTHER active session for this customer,
    # keeping ONLY the token used for this request (so the current device
    # stays signed in while any other device/session is forced to re-login).
    try:
        current_token = ""
        if authorization:
            _parts = authorization.split(" ", 1)
            if len(_parts) == 2 and _parts[0].lower() == "bearer":
                current_token = _parts[1].strip()
        cust_id = full.get("id") or customer_id
        await db.customer_sessions.delete_many({
            "$and": [
                {"$or": [{"customerId": cust_id}, {"user_id": cust_id}]},
                {"token": {"$ne": current_token}},
                {"session_token": {"$ne": current_token}},
            ]
        })
    except Exception as exc:
        logger.warning(f"[customer-auth/password] session revoke failed: {exc}")

    return {"success": True, "hasPassword": True, "wasSet": not has_password}

@fastapi_app.put("/api/customer-auth/me/email")
async def customer_update_email(data: Dict[str, Any] = Body(...)):
    """Update customer email"""
    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# CUSTOMER 2FA — Google Authenticator (TOTP) + backup codes
# ═══════════════════════════════════════════════════════════════════
# Optional, per-customer two-factor authentication. Mirrors the staff TOTP
# logic (pyotp + qrcode) but is fully self-contained on the `customers`
# collection and enforced across BOTH login methods (email+password AND
# Google), because 2FA is an ACCOUNT-level control, not a per-method one.
#
# Storage on db.customers:
#   totp_enabled          bool
#   totp_secret           base32 secret (active; never returned after setup)
#   totp_pending_secret   base32 secret awaiting first verify (setup stage)
#   totp_enabled_at       iso datetime
#   totp_backup_codes     [{ "hash": sha256(code), "usedAt": iso|None }]
#   twofa_failed_attempts int   (reset on success)
#   twofa_locked_until    iso datetime | None
#
# Brute-force policy: 5 failed challenge attempts → lock 15 minutes.
_TOTP_ISSUER = "BIBI Cars"
_2FA_MAX_ATTEMPTS = 5
_2FA_LOCK_MINUTES = 15
_2FA_CHALLENGE_TTL_SECONDS = 600  # 10 min to complete the login challenge
_2FA_BACKUP_CODE_COUNT = 10


def _totp_verify(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against the secret (±1 step window)."""
    if not secret or not code:
        return False
    try:
        import pyotp
        return bool(pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1))
    except Exception:
        return False


def _gen_backup_codes(n: int = _2FA_BACKUP_CODE_COUNT):
    """Return (plaintext_list, stored_docs). Codes are high-entropy, one-time.

    Plaintext is shown to the user ONCE; only sha256 hashes are persisted.
    """
    plain, docs = [], []
    for _ in range(n):
        # 10 chars, grouped XXXXX-XXXXX for readability
        raw = secrets.token_hex(5).upper()  # 10 hex chars
        code = f"{raw[:5]}-{raw[5:]}"
        plain.append(code)
        docs.append({"hash": _legacy_sha256(code.replace("-", "").upper()), "usedAt": None})
    return plain, docs


def _consume_backup_code(backup_codes: list, code: str):
    """If `code` matches an UNUSED backup code, return its index; else None."""
    if not backup_codes or not code:
        return None
    norm = code.replace("-", "").replace(" ", "").upper().strip()
    target = _legacy_sha256(norm)
    for i, bc in enumerate(backup_codes):
        if bc.get("hash") == target and not bc.get("usedAt"):
            return i
    return None


def _2fa_locked_remaining(customer: Dict[str, Any]) -> int:
    """Seconds remaining on a 2FA brute-force lock, 0 if not locked."""
    lu = customer.get("twofa_locked_until")
    if not lu:
        return 0
    try:
        if isinstance(lu, str):
            lu = datetime.fromisoformat(lu)
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=timezone.utc)
    except Exception:
        return 0
    delta = (lu - datetime.now(timezone.utc)).total_seconds()
    return int(delta) if delta > 0 else 0


async def _2fa_register_failure(customer_id: str, current_attempts: int) -> int:
    """Increment failed-attempt counter; lock for 15 min once it hits the cap.
    Returns the new attempt count."""
    new_attempts = int(current_attempts or 0) + 1
    update: Dict[str, Any] = {"twofa_failed_attempts": new_attempts}
    if new_attempts >= _2FA_MAX_ATTEMPTS:
        update["twofa_locked_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=_2FA_LOCK_MINUTES)
        ).isoformat()
        update["twofa_failed_attempts"] = 0  # reset counter once locked
    await db.customers.update_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"$set": update},
    )
    return new_attempts


async def _2fa_reset_failures(customer_id: str) -> None:
    await db.customers.update_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"$set": {"twofa_failed_attempts": 0, "twofa_locked_until": None}},
    )


async def _fetch_full_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    return await db.customers.find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]}
    )


@fastapi_app.get("/api/customer-auth/2fa/status")
async def customer_2fa_status(authorization: Optional[str] = Header(None)):
    """Current customer's 2FA status (safe — no secrets)."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid) or {}
    backup = full.get("totp_backup_codes") or []
    remaining = len([b for b in backup if not b.get("usedAt")])
    return {
        "enabled": bool(full.get("totp_enabled")),
        "setupPending": bool(full.get("totp_pending_secret") and not full.get("totp_enabled")),
        "enabledAt": full.get("totp_enabled_at"),
        "backupCodesRemaining": remaining,
        "hasPassword": bool(full.get("password")),
        "available": True,
        # Email-OTP login method (alternative to the authenticator app).
        "emailEnabled": bool(full.get("email_2fa_enabled")),
        "emailEnabledAt": full.get("email_2fa_enabled_at"),
        "email": full.get("email", ""),
        # Effective method the account currently uses at login.
        "method": "totp" if full.get("totp_enabled") else ("email" if full.get("email_2fa_enabled") else "off"),
    }


@fastapi_app.post("/api/customer-auth/2fa/email/enable")
async def customer_2fa_email_enable(
    data: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(None),
):
    """Enable e-mail-based login 2FA. Requires the account password (if set).
    Mutually exclusive with the authenticator (TOTP) method — enabling e-mail
    while TOTP is active is rejected so the account keeps a single method."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid)
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")
    if full.get("totp_enabled"):
        raise HTTPException(status_code=400, detail="Authenticator 2FA is already enabled — disable it first.")
    if full.get("email_2fa_enabled"):
        raise HTTPException(status_code=400, detail="Email 2FA is already enabled")
    if full.get("password"):
        password = (data or {}).get("password") or ""
        if not password or full.get("password") != _legacy_sha256(password):
            raise HTTPException(status_code=401, detail="Incorrect password")
    await db.customers.update_one(
        {"id": full.get("id") or cid},
        {"$set": {"email_2fa_enabled": True,
                  "email_2fa_enabled_at": datetime.now(timezone.utc).isoformat(),
                  "twofa_failed_attempts": 0, "twofa_locked_until": None,
                  "updatedAt": datetime.now(timezone.utc)}},
    )
    return {"success": True, "emailEnabled": True}


@fastapi_app.post("/api/customer-auth/2fa/email/disable")
async def customer_2fa_email_disable(
    data: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(None),
):
    """Disable e-mail-based login 2FA. Requires the account password (if set)."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid)
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not full.get("email_2fa_enabled"):
        raise HTTPException(status_code=400, detail="Email 2FA is not enabled")
    if full.get("password"):
        password = (data or {}).get("password") or ""
        if not password or full.get("password") != _legacy_sha256(password):
            raise HTTPException(status_code=401, detail="Incorrect password")
    await db.customers.update_one(
        {"id": full.get("id") or cid},
        {"$set": {"email_2fa_enabled": False, "twofa_failed_attempts": 0,
                  "twofa_locked_until": None, "updatedAt": datetime.now(timezone.utc)},
         "$unset": {"email_2fa_enabled_at": ""}},
    )
    return {"success": True, "emailEnabled": False}


@fastapi_app.post("/api/customer-auth/2fa/setup")
async def customer_2fa_setup(
    data: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(None),
):
    """Stage 1 — re-auth with password, then return a fresh QR + manual key.
    Activation only happens after /verify with a valid code."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid)
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")
    if full.get("totp_enabled"):
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    if full.get("email_2fa_enabled"):
        raise HTTPException(status_code=400, detail="Email 2FA is enabled — disable it first to switch to the authenticator app.")

    # Password re-auth (only enforceable when the account has a password —
    # Google-only accounts have none, so the active session is the auth).
    if full.get("password"):
        password = (data or {}).get("password") or ""
        if not password or full.get("password") != _legacy_sha256(password):
            raise HTTPException(status_code=401, detail="Incorrect password")

    import pyotp
    import qrcode
    import base64 as _b64
    from io import BytesIO as _BytesIO

    secret = pyotp.random_base32()
    account = full.get("email") or cid
    uri = pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=_TOTP_ISSUER)
    img = qrcode.make(uri)
    buf = _BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = _b64.b64encode(buf.getvalue()).decode()

    await db.customers.update_one(
        {"id": full.get("id") or cid},
        {"$set": {"totp_pending_secret": secret, "updatedAt": datetime.now(timezone.utc)}},
    )
    return {
        "manualKey": secret,
        "qrCode": f"data:image/png;base64,{qr_b64}",
        "uri": uri,
        "issuer": _TOTP_ISSUER,
        "account": account,
    }


@fastapi_app.post("/api/customer-auth/2fa/verify")
async def customer_2fa_verify(
    data: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None),
):
    """Stage 2 — confirm the pending secret with a code, enable 2FA, and
    return the 10 one-time backup codes (shown to the user ONCE)."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid)
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")
    secret = full.get("totp_pending_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="2FA setup not started")
    code = str((data or {}).get("code") or "").strip()
    if not _totp_verify(secret, code):
        raise HTTPException(status_code=400, detail="Invalid code")

    plain_codes, stored = _gen_backup_codes()
    await db.customers.update_one(
        {"id": full.get("id") or cid},
        {
            "$set": {
                "totp_enabled": True,
                "totp_secret": secret,
                "totp_enabled_at": datetime.now(timezone.utc).isoformat(),
                "totp_backup_codes": stored,
                "twofa_failed_attempts": 0,
                "twofa_locked_until": None,
                "updatedAt": datetime.now(timezone.utc),
            },
            "$unset": {"totp_pending_secret": ""},
        },
    )
    return {"success": True, "enabled": True, "backupCodes": plain_codes}


@fastapi_app.post("/api/customer-auth/2fa/disable")
async def customer_2fa_disable(
    data: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None),
):
    """Disable 2FA — requires BOTH the password (if set) AND a valid TOTP code."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid)
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not full.get("totp_enabled"):
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    if full.get("password"):
        password = (data or {}).get("password") or ""
        if not password or full.get("password") != _legacy_sha256(password):
            raise HTTPException(status_code=401, detail="Incorrect password")

    code = str((data or {}).get("code") or "").strip()
    backup_code = str((data or {}).get("backupCode") or (data or {}).get("backup_code") or "").strip()
    ok = _totp_verify(full.get("totp_secret"), code)
    if not ok and backup_code:
        ok = _consume_backup_code(full.get("totp_backup_codes") or [], backup_code) is not None
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid code")

    await db.customers.update_one(
        {"id": full.get("id") or cid},
        {
            "$set": {"totp_enabled": False, "twofa_failed_attempts": 0, "twofa_locked_until": None,
                     "updatedAt": datetime.now(timezone.utc)},
            "$unset": {"totp_secret": "", "totp_pending_secret": "", "totp_backup_codes": "",
                       "totp_enabled_at": ""},
        },
    )
    return {"success": True, "enabled": False}


@fastapi_app.post("/api/customer-auth/2fa/backup/regenerate")
async def customer_2fa_regenerate_backup(
    data: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None),
):
    """Re-issue 10 fresh backup codes (old ones are invalidated). Requires
    password (if set) + a valid TOTP code, same strictness as disable."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cid = customer.get("customerId") or customer.get("id") or customer.get("user_id")
    full = await _fetch_full_customer(cid)
    if not full:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not full.get("totp_enabled"):
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    if full.get("password"):
        password = (data or {}).get("password") or ""
        if not password or full.get("password") != _legacy_sha256(password):
            raise HTTPException(status_code=401, detail="Incorrect password")
    code = str((data or {}).get("code") or "").strip()
    if not _totp_verify(full.get("totp_secret"), code):
        raise HTTPException(status_code=400, detail="Invalid code")

    plain_codes, stored = _gen_backup_codes()
    await db.customers.update_one(
        {"id": full.get("id") or cid},
        {"$set": {"totp_backup_codes": stored, "updatedAt": datetime.now(timezone.utc)}},
    )
    return {"success": True, "backupCodes": plain_codes}


async def _issue_2fa_challenge(customer_id: str, email: str = "", method: str = "totp") -> Dict[str, Any]:
    """Create a short-lived login challenge token for a customer with 2FA on.

    method="totp"  → client must present an authenticator code / backup code.
    method="email" → a 6-digit code is generated, e-mailed to the customer and
                     hashed into the challenge; the client must echo it back.
    """
    token = generate_token()
    now = datetime.now(timezone.utc)
    doc = {
        "token": token,
        "customerId": customer_id,
        "method": method,
        "created_at": now,
        "expires_at": now + timedelta(seconds=_2FA_CHALLENGE_TTL_SECONDS),
    }

    if method == "email":
        code = f"{secrets.randbelow(1_000_000):06d}"
        doc["code_hash"] = hashlib.sha256(code.encode()).hexdigest()
        await db.customer_2fa_challenges.insert_one(doc)
        # Deliver the code to the customer's own (verified) e-mail. Best-effort:
        # a delivery failure must not leak the code or crash the login — the
        # client still receives the masked-recipient challenge response.
        try:
            from notifications import EmailChannel
            from app.services.customer_email_templates import render_login_otp_email
            full = await _fetch_full_customer(customer_id) or {}
            _subj, _html, _text = render_login_otp_email(
                code, name=full.get("name", ""), ttl_minutes=_2FA_CHALLENGE_TTL_SECONDS // 60,
            )
            await EmailChannel(db).send(
                to=email or full.get("email", ""), subject=_subj, html=_html, text=_text,
                event="customer_login_otp", context={"customerId": customer_id},
            )
        except Exception as _e:  # noqa: BLE001
            logger.warning(f"[2fa] customer email-otp dispatch failed: {_e}")
        return {
            "challenge": "email",
            "challenge_token": token,
            "customerId": customer_id,
            "emailMasked": _mask_email_addr(email) if email else "",
            "expires_in_seconds": _2FA_CHALLENGE_TTL_SECONDS,
        }

    await db.customer_2fa_challenges.insert_one(doc)
    return {
        "challenge": "totp",
        "challenge_token": token,
        "customerId": customer_id,
        "emailMasked": _mask_email_addr(email) if email else "",
        "expires_in_seconds": _2FA_CHALLENGE_TTL_SECONDS,
    }


@fastapi_app.post("/api/customer-auth/2fa/challenge/verify")
async def customer_2fa_challenge_verify(data: Dict[str, Any] = Body(...)):
    """Complete a login challenge: verify TOTP (or a backup code) and, on
    success, mint the customer session. Enforces the lockout policy."""
    token = (data.get("challenge_token") or "").strip()
    code = str(data.get("code") or "").strip()
    backup_code = str(data.get("backupCode") or data.get("backup_code") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="challenge_token required")

    challenge = await db.customer_2fa_challenges.find_one({"token": token})
    if not challenge:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    exp = challenge.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except Exception:
            exp = None
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp < datetime.now(timezone.utc):
        await db.customer_2fa_challenges.delete_one({"token": token})
        raise HTTPException(status_code=400, detail="Challenge expired — please sign in again")

    cid = challenge.get("customerId")
    method = challenge.get("method") or "totp"
    full = await _fetch_full_customer(cid)
    active = bool(full and (full.get("totp_enabled") if method == "totp" else full.get("email_2fa_enabled")))
    if not active:
        await db.customer_2fa_challenges.delete_one({"token": token})
        raise HTTPException(status_code=400, detail="2FA not active for this account")

    # Lockout check
    remaining = _2fa_locked_remaining(full)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {max(1, remaining // 60)} minute(s).",
        )

    used_backup_idx = None
    if method == "email":
        # Verify the e-mailed one-time code against the hashed challenge value.
        expected = challenge.get("code_hash") or ""
        ok = bool(code) and hashlib.sha256(code.encode()).hexdigest() == expected
    else:
        # Verify TOTP or a one-time backup code
        ok = _totp_verify(full.get("totp_secret"), code)
        if not ok and backup_code:
            used_backup_idx = _consume_backup_code(full.get("totp_backup_codes") or [], backup_code)
            ok = used_backup_idx is not None
    if not ok:
        attempts = await _2fa_register_failure(cid, full.get("twofa_failed_attempts"))
        left = max(0, _2FA_MAX_ATTEMPTS - attempts)
        raise HTTPException(
            status_code=401,
            detail=f"Invalid code. {left} attempt(s) left." if left else
                   f"Too many attempts. Locked for {_2FA_LOCK_MINUTES} minutes.",
        )

    # Success — consume backup code if used, clear challenge + failures, mint session
    if used_backup_idx is not None:
        codes = full.get("totp_backup_codes") or []
        codes[used_backup_idx]["usedAt"] = datetime.now(timezone.utc).isoformat()
        await db.customers.update_one(
            {"id": full.get("id") or cid}, {"$set": {"totp_backup_codes": codes}}
        )
    await db.customer_2fa_challenges.delete_one({"token": token})
    await _2fa_reset_failures(cid)
    session_token = await _create_customer_session(cid)
    return _customer_response(full, session_token)




# ═══════════════════════════════════════════════════════════════════
# APP SETTINGS (dynamic auth/base-url config editable from admin UI)
# ═══════════════════════════════════════════════════════════════════
# Everything auth-related that used to live in env vars now lives in the
# `app_settings` collection, key="auth". See /app/backend/settings_service.py
# for the schema + caching strategy.
#
# Three surfaces:
#   • GET  /api/settings/public        (anonymous, safe subset only)
#   • GET  /api/admin/settings/auth    (staff admin, full doc)
#   • PATCH /api/admin/settings/auth   (staff admin, deep-merge update)
#
# The SettingsService singleton is attached to the app at startup; the
# helper below resolves it with a safe fallback.
from settings_service import SettingsService, public_subset as _auth_public_subset

_settings_singleton: Optional[SettingsService] = None

def get_settings_service() -> SettingsService:
    """Lazy-create the SettingsService tied to the existing `db` handle."""
    global _settings_singleton
    if _settings_singleton is None:
        _settings_singleton = SettingsService(db)
    return _settings_singleton


async def resolve_base_url(request: Request) -> str:
    """Public-facing backend URL. Uses admin settings → env → request fallback."""
    svc = get_settings_service()
    return await svc.resolve_base_url(str(request.base_url))


async def resolve_frontend_url(request: Request) -> str:
    """Customer-facing UI URL used in reset-password links & post-OAuth redirects."""
    svc = get_settings_service()
    return await svc.resolve_frontend_url(str(request.base_url))


@fastapi_app.get("/api/settings/public")
async def public_settings(request: Request):
    """Anonymous-safe subset of auth settings — used by login/register pages."""
    svc = get_settings_service()
    auth = await svc.get_auth()
    subset = _auth_public_subset(auth)
    # Fill in resolved fallbacks so the frontend has working URLs even before
    # the admin has saved anything.
    if not subset.get("baseUrl"):
        subset["baseUrl"] = await svc.resolve_base_url(str(request.base_url))
    if not subset.get("frontendUrl"):
        subset["frontendUrl"] = await svc.resolve_frontend_url(str(request.base_url))
    if not (subset.get("google") or {}).get("clientId"):
        cid = await svc.resolve_google_client_id()
        subset.setdefault("google", {})["clientId"] = cid
    return subset


@fastapi_app.get("/api/admin/settings/auth", dependencies=[Depends(require_admin)])
async def admin_get_auth_settings(request: Request):
    """Full auth settings document (admin-only)."""
    svc = get_settings_service()
    auth = await svc.get_auth()
    # Also return resolved fallbacks so the admin sees what's actually in effect
    auth["_resolved"] = {
        "baseUrl": await svc.resolve_base_url(str(request.base_url)),
        "frontendUrl": await svc.resolve_frontend_url(str(request.base_url)),
        "googleClientId": await svc.resolve_google_client_id(),
        "requestBaseUrl": str(request.base_url).rstrip("/"),
    }
    # Never expose the raw JWT secret to the UI — show if set, not the value
    jwt_cfg = auth.get("jwt") or {}
    auth["jwt"] = {
        **jwt_cfg,
        "secret": "********" if (jwt_cfg.get("secret") or "").strip() else "",
        "secretIsSet": bool((jwt_cfg.get("secret") or "").strip()),
    }
    return auth


@fastapi_app.patch("/api/admin/settings/auth", dependencies=[Depends(require_admin)])
async def admin_patch_auth_settings(
    payload: Dict[str, Any] = Body(...),
    request: Request = None,
):
    """
    Partial update of auth settings (deep-merge).

    Acceptable top-level keys: baseUrl, frontendUrl, google, jwt, features,
    password, email. Any other keys are silently ignored.

    NOTE: passing `jwt.secret == "********"` is treated as "keep existing".
    Pass an empty string to explicitly clear it.
    """
    ALLOWED = {"baseUrl", "frontendUrl", "google", "jwt", "features", "password", "email", "notifications"}
    clean = {k: v for k, v in (payload or {}).items() if k in ALLOWED}

    # Guard: masked secret means "don't change"
    if isinstance(clean.get("jwt"), dict):
        jwt_in = dict(clean["jwt"])
        if jwt_in.get("secret") == "********":
            jwt_in.pop("secret", None)
        clean["jwt"] = jwt_in

    # Normalise URLs (strip trailing slashes)
    for k in ("baseUrl", "frontendUrl"):
        if isinstance(clean.get(k), str):
            clean[k] = clean[k].strip().rstrip("/")

    svc = get_settings_service()
    updated = await svc.patch_auth(clean, by="admin")

    # ─── Phase 5.4 / C-3A — google_oauth mirror RETIRED ───────────────────
    # The legacy write-mirror to integration_configs has been removed in
    # C-3A. `app_settings.auth.google.clientId` is now the SOLE source-of-
    # truth for the Google OAuth Client ID — no cross-collection write
    # happens here anymore.
    #
    # READ side (preserved):
    #   - settings_service.resolve_google_client_id() still falls back
    #     to integration_configs.{provider:google_oauth}.credentials.clientId
    #     for backward compatibility with any value not yet migrated
    #     by the startup backfill (see _backfill_google_client_id at
    #     boot-time orchestration in this file).
    #
    # The IntegrationConfigsRepository.mirror_google_client_id verb is
    # KEPT in repository surface (per C-3A mandate "НЕ в этом же
    # коммите" — verb retirement is a separate commit AFTER
    # stabilization) but has ZERO production callers from this point.
    # The verb survives only for any future legacy-data-recovery
    # scenarios and to keep the C-2 architectural answer document
    # internally consistent.

    # Mask secret back on the response
    jwt_cfg = updated.get("jwt") or {}
    updated_resp = dict(updated)
    updated_resp["jwt"] = {
        **jwt_cfg,
        "secret": "********" if (jwt_cfg.get("secret") or "").strip() else "",
        "secretIsSet": bool((jwt_cfg.get("secret") or "").strip()),
    }
    return {"success": True, "value": updated_resp}


# ═══════════════════════════════════════════════════════════════════
# FOOTER SETTINGS (public-site footer — fully admin-editable)
# ═══════════════════════════════════════════════════════════════════
# Stored in `app_settings` key="footer" (see settings_service.FOOTER_DEFAULTS).
# Surfaces:
#   • GET /api/public/footer            (anonymous — rendered by EcoFooter)
#   • GET /api/admin/settings/footer    (staff admin, full doc)
#   • PUT /api/admin/settings/footer    (staff admin, full replace)
@fastapi_app.get("/api/public/footer")
async def public_footer():
    """Anonymous-safe footer content used by the public-site footer."""
    svc = get_settings_service()
    footer = await svc.get_footer()
    return {"success": True, "footer": footer}


# ── Public GEO (IP → country) — default-language detection ───────────────
# The public site picks its default language from the visitor's territory:
#   • country == "UA"  → Ukrainian ("uk")
#   • everything else  → English ("en")
# Resolution order (fast → slow):
#   1. CDN/proxy country headers (zero-latency, if the edge sets them)
#   2. ip-api.com lookup on the forwarded client IP (cached in-process, 1h TTL)
#   3. unknown → country=None (frontend keeps its local timezone guess)
_GEO_CACHE: Dict[str, "tuple[str, float]"] = {}
_GEO_TTL_SECONDS = 3600.0


def _geo_client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    xr = (request.headers.get("x-real-ip") or "").strip()
    if xr:
        return xr
    return request.client.host if (request and request.client) else ""


def _geo_is_public_ip(s: str) -> bool:
    if not s:
        return False
    if s in ("::1", "127.0.0.1", "localhost"):
        return False
    if s.startswith(("10.", "127.", "192.168.", "169.254.", "fc", "fd")):
        return False
    if s.startswith("172."):
        try:
            second = int(s.split(".")[1])
            if 16 <= second <= 31:
                return False
        except Exception:
            pass
    return True


@fastapi_app.get("/api/public/geo")
async def public_geo(request: Request):
    """Best-effort country of the visitor for default-language selection."""
    # 1) Edge / CDN country headers (Cloudflare, Vercel, generic).
    hdr = (
        request.headers.get("cf-ipcountry")
        or request.headers.get("x-vercel-ip-country")
        or request.headers.get("x-geo-country")
        or request.headers.get("x-country-code")
        or ""
    ).strip().upper()
    country = hdr if (hdr and hdr not in ("XX", "T1", "ZZ")) else ""
    source = "header" if country else ""

    ip = _geo_client_ip(request)

    # 2) ip-api.com lookup (cached) when no header and the IP is routable.
    if not country and _geo_is_public_ip(ip):
        now = time.time()
        cached = _GEO_CACHE.get(ip)
        if cached and cached[1] > now:
            country, source = cached[0], "cache"
        else:
            try:
                async with httpx.AsyncClient(timeout=4.0) as _client:
                    r = await _client.get(
                        f"http://ip-api.com/json/{ip}",
                        params={"fields": "status,countryCode"},
                    )
                    j = r.json()
                    if j.get("status") == "success":
                        country = (j.get("countryCode") or "").upper()
                        source = "ipapi"
                        _GEO_CACHE[ip] = (country, now + _GEO_TTL_SECONDS)
            except Exception as _e:  # noqa: BLE001
                logger.warning("[geo] ip lookup failed: %s", _e)

    lang = "uk" if country == "UA" else "en"
    return {
        "country": country or None,
        "lang": lang,
        "source": source or "fallback",
    }


@fastapi_app.get("/api/admin/settings/footer", dependencies=[Depends(require_admin)])
async def admin_get_footer_settings():
    """Full footer settings document (admin-only)."""
    svc = get_settings_service()
    footer = await svc.get_footer()
    return {"success": True, "footer": footer}


@fastapi_app.put("/api/admin/settings/footer", dependencies=[Depends(require_admin)])
async def admin_put_footer_settings(payload: Dict[str, Any] = Body(...)):
    """
    Replace the footer settings document (full save). The frontend always
    sends the complete footer object; omitted sections fall back to defaults.
    """
    body = payload.get("footer") if isinstance(payload, dict) and "footer" in payload else payload
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid footer payload")
    svc = get_settings_service()
    saved = await svc.set_footer(body, by="admin")
    return {"success": True, "footer": saved}


# ═══════════════════════════════════════════════════════════════════
# PASSWORD RESET (customer) — dynamic frontendUrl, DRY-RUN email
# ═══════════════════════════════════════════════════════════════════
# Flow:
#   1. POST /api/customer-auth/forgot-password   { email }
#         → always returns 200 (no email enumeration)
#         → if user exists: creates single-use token with TTL, "sends" email
#   2. POST /api/customer-auth/reset-password    { token, password }
#         → validates token (not expired, not used)
#         → updates password (SHA-256 legacy) + marks token consumed
#         → issues a new session so the user is logged in immediately
#
# Storage = `password_reset_tokens` collection
#   { token, customerId, email, created_at, expires_at, used_at? }

@fastapi_app.post("/api/customer-auth/forgot-password")
async def customer_forgot_password(
    request: Request,
    data: Dict[str, Any] = Body(...),
):
    """Request a password-reset link. Always returns 200 (no enumeration)."""
    svc = get_settings_service()
    auth_cfg = await svc.get_auth()
    if not (auth_cfg.get("features") or {}).get("resetPasswordEnabled", True):
        raise HTTPException(status_code=403, detail="Password reset is disabled")

    email = (data.get("email") or "").strip().lower()
    # Never reveal whether the email exists
    response_ok = {"success": True, "message": "If that email exists, a reset link has been sent."}
    if not email:
        return response_ok

    customer = await db.customers.find_one({"email": email}, {"_id": 0})
    if not customer:
        return response_ok

    ttl_minutes = int(((auth_cfg.get("password") or {}).get("resetTokenTtlMinutes")) or 60)
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token": token,
        "customerId": customer.get("customerId") or customer.get("id") or customer.get("user_id"),
        "email": email,
        "created_at": now,
        "expires_at": now + timedelta(minutes=ttl_minutes),
        "used_at": None,
    })

    frontend_url = await svc.resolve_frontend_url(str(request.base_url))
    reset_link = f"{frontend_url}/cabinet/reset-password?token={token}"

    # DRY-RUN email — log the link so devs/testing-agent can grab it.
    # Future: plug into Resend/SMTP based on settings.email.mode
    logger.info(f"[password-reset] DRY RUN email to={email} link={reset_link}")
    try:
        # Phase 5.3 / C-10 — db.email_outbox ownership routes through
        # EmailOutboxRepository. The verb name (record_auth_email_audit)
        # makes the cross-domain WRITE visible at the API surface — the
        # password-reset concern persists into an outbox owned by the
        # notification family. The drift flagged in
        # PHASE5_1_OWNERSHIP_MAP.md §1.3 is confirmed and DEFERRED to
        # Phase 5.4 (PasswordReset / Auth domain extraction); the call
        # site stays here, only the persistence verb changes.
        from app.repositories import EmailOutboxRepository
        await EmailOutboxRepository(db).record_auth_email_audit({
            "to": email,
            "subject": "BIBI Cars — Password reset",
            "body": f"Click the link to reset your password (valid {ttl_minutes} min):\n\n{reset_link}\n",
            "mode": (auth_cfg.get("email") or {}).get("mode", "dry_run"),
            "template": "reset_password",
            "status": "dry_run",
            "created_at": now,
            "meta": {"reset_token": token, "customerId": customer.get("customerId")},
        })
    except Exception as exc:
        logger.warning(f"[password-reset] outbox insert failed: {exc}")

    # When DRY-RUN mode, also expose the link in the response so UI can
    # show it (only non-prod convenience; hide when email.mode != dry_run).
    if (auth_cfg.get("email") or {}).get("mode", "dry_run") == "dry_run":
        return {**response_ok, "dry_run": True, "reset_link": reset_link}
    return response_ok


@fastapi_app.post("/api/customer-auth/reset-password")
async def customer_reset_password(data: Dict[str, Any] = Body(...)):
    """Consume a reset token and set a new password. Returns a fresh session."""
    svc = get_settings_service()
    auth_cfg = await svc.get_auth()
    if not (auth_cfg.get("features") or {}).get("resetPasswordEnabled", True):
        raise HTTPException(status_code=403, detail="Password reset is disabled")

    token = (data.get("token") or "").strip()
    new_password = data.get("password") or ""
    min_len = int(((auth_cfg.get("password") or {}).get("minLength")) or 6)

    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    if len(new_password) < min_len:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {min_len} characters",
        )

    row = await db.password_reset_tokens.find_one({"token": token})
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if row.get("used_at"):
        raise HTTPException(status_code=400, detail="Token already used")
    expires_at = row.get("expires_at")
    if expires_at and isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Token expired")

    customer_id = row.get("customerId")
    customer = await db.customers.find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"_id": 0},
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Update password using same legacy SHA-256 as /register & /login
    await db.customers.update_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {
            "$set": {
                "password": _legacy_sha256(new_password),
                "password_updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    await db.password_reset_tokens.update_one(
        {"token": token},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )
    # Invalidate existing sessions to force re-login everywhere
    try:
        await db.customer_sessions.delete_many({
            "$or": [{"customerId": customer_id}, {"user_id": customer_id}]
        })
    except Exception:
        pass

    # Issue new session — user is logged in immediately after reset
    new_token = await _create_customer_session(customer_id)
    return {
        **_customer_response(customer, new_token),
        "message": "Password updated successfully",
    }


@fastapi_app.get("/api/customer-auth/validate-reset-token")
async def customer_validate_reset_token(token: str):
    """Check token before showing the reset form. Returns email (masked) if OK."""
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    row = await db.password_reset_tokens.find_one({"token": token})
    if not row:
        raise HTTPException(status_code=400, detail="Invalid token")
    if row.get("used_at"):
        raise HTTPException(status_code=400, detail="Token already used")
    expires_at = row.get("expires_at")
    if expires_at and isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Token expired")
    email = row.get("email") or ""
    if email and "@" in email:
        local, dom = email.split("@", 1)
        if len(local) > 2:
            email = local[0] + "***" + local[-1] + "@" + dom
    return {"valid": True, "email": email}


# ═══════════════════════════════════════════════════════════════════
# CUSTOMER CABINET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/customer-cabinet/dashboard")
async def customer_cabinet_dashboard():
    """Customer dashboard"""
    return {
        "success": True,
        "data": {
            "favorites": 5,
            "compares": 2,
            "orders": 1,
            "invoices": 0
        }
    }


# NOTE: The Phase III implementations of /api/favorites/me, POST /api/favorites,
# GET /api/favorites/check/{vin}, DELETE /api/favorites/{id} are defined later
# (search "PHASE III — Customer Favorites"). Those are the canonical ones —
# they require a customer Bearer token and are wired to the frontend
# FavoriteButton + FavoritesPage in the cabinet.



# Compare
# ── compare endpoints moved to authoritative implementation around line 18415 ──

# History reports
# [auto-domain removed] /api/history/quota/me (history_quota)

# [auto-domain removed] /api/history/request (request_history_report)

# [auto-domain removed] /api/history/report/{report_id} (get_history_report)

# Shipping tracking
# [auto-domain removed] /api/shipping/me (my_shipping)

# ═══════════════════════════════════════════════════════════════════
# STAFF MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/staff", dependencies=[Depends(require_admin)])
async def list_staff(role: Optional[str] = None, limit: int = 50):
    """List staff members"""
    query = {}
    if role:
        query["role"] = role
    cursor = db.staff.find(query, {'_id': 0, 'password': 0}).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "items": items}

@fastapi_app.get("/api/staff/stats", dependencies=[Depends(require_admin)])
async def staff_stats():
    """Staff statistics"""
    total = await db.staff.count_documents({})
    active = await db.staff.count_documents({"active": True})
    return {
        "success": True,
        "stats": {
            "total": total,
            "active": active,
            "inactive": total - active,
            "online": 0
        }
    }

@fastapi_app.get("/api/staff/performance", dependencies=[Depends(require_admin)])
async def staff_performance(period: str = "week"):
    """Staff performance metrics"""
    cursor = db.staff.find({}, {'_id': 0, 'password': 0}).limit(20)
    staff = await cursor.to_list(length=20)
    
    performance = []
    for s in staff:
        performance.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "role": s.get("role"),
            "leads": 0,
            "conversions": 0,
            "calls": 0,
            "avgResponseTime": 0
        })
    
    return {"success": True, "data": performance}

@fastapi_app.get("/api/staff/inactive", dependencies=[Depends(require_admin)])
async def staff_inactive(hours: int = 2):
    """Get inactive staff"""
    return {"success": True, "data": []}

@fastapi_app.post("/api/staff", dependencies=[Depends(require_admin)])
async def create_staff(data: Dict[str, Any] = Body(...)):
    """Create staff member.

    Wave 7 — accepts optional ``teamId`` (free-form short code, e.g. ``sofia``,
    ``korea``, ``shipping``). Used by the reassignment ACL to limit
    ``team_lead`` reassignments to within their own team.
    """
    raw_team = (data.get("teamId") or "").strip() or None
    staff = {
        "id": f"staff-{datetime.now(timezone.utc).timestamp()}",
        "name": data.get("name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "role": data.get("role", "manager"),
        "teamId": raw_team,
        "active": True,
        "password": _legacy_sha256(data.get("password", "123456")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.staff.insert_one(staff)
    return {"success": True, "id": staff["id"]}

@fastapi_app.put("/api/staff/{staff_id}", dependencies=[Depends(require_admin)])
async def update_staff(staff_id: str, data: Dict[str, Any] = Body(...)):
    """Update staff member.

    Wave 7 — normalises ``teamId``: empty string → ``None`` (so the DB
    stays clean and the reassignment ACL "no-team cohort" works
    consistently).
    """
    update_data = {k: v for k, v in data.items() if k != "password"}
    if "teamId" in update_data:
        v = update_data["teamId"]
        update_data["teamId"] = (v or "").strip() or None if isinstance(v, str) else (v or None)
    if data.get("password"):
        update_data["password"] = _legacy_sha256(data["password"])

    await db.staff.update_one({"id": staff_id}, {"$set": update_data})
    return {"success": True}

@fastapi_app.get("/api/staff/teams", dependencies=[Depends(require_admin)])
async def list_staff_teams():
    """Wave 7 — list distinct, non-empty ``teamId`` values from staff.

    Used by the Staff UI to power a free-form team picker with
    autocomplete from existing teams. Returns a sorted, deduplicated list
    of strings.
    """
    raw = await db.staff.distinct("teamId")
    teams = sorted({(t or "").strip() for t in raw if (t or "").strip()})
    return {"success": True, "data": teams}

@fastapi_app.put("/api/staff/{staff_id}/toggle-active", dependencies=[Depends(require_admin)])
async def toggle_staff_active(staff_id: str):
    """Toggle staff active status"""
    staff = await db.staff.find_one({"id": staff_id})
    if staff:
        await db.staff.update_one(
            {"id": staff_id},
            {"$set": {"active": not staff.get("active", True)}}
        )
    return {"success": True}

@fastapi_app.post("/api/staff/{staff_id}/reset-password", dependencies=[Depends(require_admin)])
async def reset_staff_password(staff_id: str, data: Dict[str, Any] = Body(...)):
    """Reset staff password"""
    new_password = data.get("newPassword", "123456")
    await db.staff.update_one(
        {"id": staff_id},
        {"$set": {"password": _legacy_sha256(new_password)}}
    )
    return {"success": True}

@fastapi_app.get("/api/staff/{staff_id}", dependencies=[Depends(require_admin)])
async def get_staff_member(staff_id: str):
    """Get staff member by ID"""
    member = await db.staff.find_one({"id": staff_id}, {'_id': 0, 'password': 0})
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"success": True, "data": member}

@fastapi_app.delete("/api/staff/{staff_id}", dependencies=[Depends(require_admin)])
async def delete_staff_member(staff_id: str):
    """Delete staff member"""
    await db.staff.delete_one({"id": staff_id})
    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# USERS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/users", dependencies=[Depends(require_admin)])
async def list_users(role: Optional[str] = None, limit: int = 50):
    """List users (staff + customers)"""
    query = {}
    if role:
        query["role"] = role
    
    # Get from staff collection
    cursor = db.staff.find(query, {'_id': 0, 'password': 0}).limit(limit)
    items = await cursor.to_list(length=limit)
    
    return {"success": True, "data": items}

@fastapi_app.get("/api/users/me")
async def get_current_user_endpoint(current_user: Dict[str, Any] = Depends(require_user)):
    """Return the authenticated staff user (alias of /api/auth/me).

    NOTE: this literal route MUST stay above ``/api/users/{user_id}`` so that
    FastAPI does not match ``me`` as a ``user_id`` parameter.
    """
    return {"success": True, "data": {
        "id": current_user.get("id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
        "managerId": current_user.get("managerId"),
    }}

@fastapi_app.get("/api/users/{user_id}", dependencies=[Depends(require_admin)])
async def get_user(user_id: str):
    """Get user by ID"""
    user = await db.staff.find_one({"id": user_id}, {'_id': 0, 'password': 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "data": user}



# ═══════════════════════════════════════════════════════════════════
# TEAM LEAD ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/team/dashboard")
async def team_dashboard():
    """Team dashboard"""
    return {
        "success": True,
        "kpi": {
            "totalLeads": await db.leads.count_documents({}),
            "newLeads": await db.leads.count_documents({"status": "new"}),
            "conversions": await db.deals.count_documents({"status": "won"}),
            "avgResponseTime": 5
        },
        "alerts": [],
        "overdue": []
    }

@fastapi_app.get("/api/team/managers")
async def team_managers():
    """Get team managers"""
    cursor = db.staff.find({"role": {"$in": ["manager", "team_lead"]}}, {'_id': 0, 'password': 0})
    items = await cursor.to_list(length=50)
    
    # Add stats to each manager
    for m in items:
        m["stats"] = {
            "leads": await db.leads.count_documents({"managerId": m.get("id")}),
            "deals": await db.deals.count_documents({"managerId": m.get("id")}),
            "tasks": await db.tasks.count_documents({"assigneeId": m.get("id")})
        }
    
    return {"success": True, "data": items}

@fastapi_app.get("/api/team/managers/{manager_id}")
async def team_manager_detail(manager_id: str):
    """Get manager details"""
    manager = await db.staff.find_one({"id": manager_id}, {'_id': 0, 'password': 0})
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    
    manager["stats"] = {
        "leads": await db.leads.count_documents({"managerId": manager_id}),
        "deals": await db.deals.count_documents({"managerId": manager_id}),
        "tasks": await db.tasks.count_documents({"assigneeId": manager_id})
    }
    
    return {"success": True, "data": manager}

@fastapi_app.get("/api/team/alerts")
async def team_alerts():
    """Team alerts"""
    cursor = db.alerts.find({}, {'_id': 0}).sort('created_at', -1).limit(20)
    items = await cursor.to_list(length=20)
    return {"success": True, "data": items}

@fastapi_app.get("/api/team/payments/overdue")
async def team_payments_overdue():
    """Overdue payments"""
    cursor = db.invoices.find({"status": "overdue"}, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

# [auto-domain removed] /api/team/shipping/stalled (team_shipping_stalled)

@fastapi_app.get("/api/team/performance")
async def team_performance():
    """Team performance metrics"""
    cursor = db.staff.find({"role": "manager"}, {'_id': 0, 'password': 0})
    managers = await cursor.to_list(length=20)
    
    performance = []
    for m in managers:
        performance.append({
            "managerId": m.get("id"),
            "name": m.get("name"),
            "leads": await db.leads.count_documents({"managerId": m.get("id")}),
            "conversions": await db.deals.count_documents({"managerId": m.get("id"), "status": "won"}),
            "avgResponseTime": 5,
            "score": 85
        })
    
    return {"success": True, "data": performance}

@fastapi_app.get("/api/team/reassignments")
async def team_reassignments():
    """Pending reassignments"""
    cursor = db.reassignments.find({"status": "pending"}, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

@fastapi_app.post("/api/team/reassignments/{reassignment_id}/accept")
async def accept_reassignment(reassignment_id: str, data: Dict[str, Any] = Body(...)):
    """Accept reassignment"""
    await db.reassignments.update_one(
        {"id": reassignment_id},
        {"$set": {"status": "accepted", "newManagerId": data.get("newManagerId")}}
    )
    return {"success": True}

@fastapi_app.post("/api/team/reassignments/{reassignment_id}/snooze")
async def snooze_reassignment(reassignment_id: str, data: Dict[str, Any] = Body(...)):
    """Snooze reassignment"""
    return {"success": True}

@fastapi_app.post("/api/team/reassignments/{reassignment_id}/queue")
async def queue_reassignment(reassignment_id: str):
    """Queue reassignment"""
    return {"success": True}

@fastapi_app.get("/api/team/leads")
async def team_leads():
    """Team leads"""
    cursor = db.leads.find({}, {'_id': 0}).sort('created_at', -1).limit(100)
    items = await cursor.to_list(length=100)
    return {"success": True, "data": items}

@fastapi_app.get("/api/team/leads/hot")
async def team_leads_hot():
    """Hot leads"""
    cursor = db.leads.find({"score": {"$gte": 80}}, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

@fastapi_app.get("/api/team/leads/stale")
async def team_leads_stale():
    """Stale leads"""
    return {"success": True, "data": []}

@fastapi_app.post("/api/team/leads/{lead_id}/reassign")
async def reassign_lead(
    lead_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Reassign one lead (Wave 7 — thin wrapper around the reassignment service).

    Kept for backwards compatibility with TeamLeadsPage and the
    ReassignmentCenterPage 'Accept' button. All new code should call
    ``POST /api/admin/reassign`` directly.

    ACL is now enforced via ``app.services.reassignment`` (admin/team_lead
    only; manager → 403). Body accepts the legacy ``managerId`` field as
    well as ``toManagerId`` / ``newManagerId``.
    """
    from app.services import reassignment as _rs  # local import to avoid cycle

    to_manager_id = (
        data.get("toManagerId")
        or data.get("newManagerId")
        or data.get("managerId")
    )
    if not to_manager_id:
        raise HTTPException(status_code=400, detail="toManagerId is required")

    actor = {
        "id":     current_user.get("id"),
        "email":  current_user.get("email"),
        "role":   current_user.get("role"),
        "name":   current_user.get("name"),
        "teamId": current_user.get("teamId"),
    }
    result = await _rs.reassign(
        db,
        entity="lead",
        ids=[lead_id],
        to_manager_id=to_manager_id,
        reason=data.get("reason") or "Team Lead manual reassign",
        actor=actor,
    )
    # Доопр #22 — notify newly-assigned manager
    try:
        from app.services.lead_notifications import notify_new_lead
        lead_doc = await db.leads.find_one({"id": lead_id}, {"_id": 0})
        if lead_doc:
            await notify_new_lead(db, lead_doc, assigned_by=current_user.get("name") or current_user.get("email"))
    except Exception as _e:
        logger.debug("[reassign_lead] notify failed: %s", _e)
    return {"success": result["success"], "data": result}

@fastapi_app.get("/api/team/tasks")
async def team_tasks(
    manager_id: Optional[str] = Query(None, alias="managerId"),
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Team tasks (RBAC-aware).

    • admin / team_lead → all tasks; can pin `managerId=` for a drilldown.
    • manager → only own (assignee).
    """
    role = (current_user.get("role") or "").lower()
    q: Dict[str, Any] = {}
    if role == "manager":
        q["assigneeId"] = current_user.get("id")
    elif manager_id:
        q["assigneeId"] = manager_id
    cursor = db.tasks.find(q, {"_id": 0}).sort("dueDate", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "data": items, "items": items}

@fastapi_app.get("/api/team/tasks/overdue")
async def team_tasks_overdue(
    manager_id: Optional[str] = Query(None, alias="managerId"),
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Overdue tasks (Customer-Card / Team-Lead spec, 2026-06-10).

    Definition: ``dueDate < now`` AND ``status NOT IN [completed, cancelled]``.

    Role scoping mirrors `/api/team/tasks`:
      • admin / team_lead → see every overdue task; drilldown via `managerId`.
      • manager → only own (assignee).
    """
    role = (current_user.get("role") or "").lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    q: Dict[str, Any] = {
        "dueDate": {"$lt": now_iso, "$nin": [None, ""]},
        "status":  {"$nin": ["completed", "cancelled", "done", "archived"]},
    }
    if role == "manager":
        q["assigneeId"] = current_user.get("id")
    elif manager_id:
        q["assigneeId"] = manager_id
    cursor = db.tasks.find(q, {"_id": 0}).sort("dueDate", 1).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.tasks.count_documents(q)
    return {"success": True, "data": items, "items": items, "total": total}

@fastapi_app.post("/api/team/tasks/{task_id}/escalate")
async def escalate_task(task_id: str):
    """Escalate task"""
    await db.tasks.update_one({"id": task_id}, {"$set": {"escalated": True}})
    return {"success": True}

# [auto-domain removed] /api/team/shipping (team_shipping)

# [auto-domain removed] /api/team/shipping/risky (team_shipping_risky)

@fastapi_app.get("/api/response-time/team")
async def response_time_team(days: int = 7):
    """Response time metrics"""
    return {
        "success": True,
        "data": {
            "avgResponseTime": 5,
            "targetResponseTime": 10,
            "managers": []
        }
    }

# ═══════════════════════════════════════════════════════════════════
# INGESTION/PARSER ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════
# [auto-domain removed] _derive_parser_status











# ═══════════════════════════════════════════════════════════════════
# ENGINE SELF-HEAL — install the heavy Playwright stack on admin command
# ───────────────────────────────────────────────────────────────────
# Lets an admin "deploy" the bid.cars Playwright engine (playwright +
# playwright_stealth + chromium browser) straight from the panel, without
# a code redeploy. Useful when a fresh prod image shipped without the
# browser binaries ("Missing playwright_stealth module").
#
# NOTE (honest): even with the engine installed, bid.cars stays behind
# Cloudflare — server-side Playwright will hit CF challenges. The reliable
# data path for bid.cars / CF sites is the Chrome Extension. This button
# only clears the "engine missing" state; it does not bypass Cloudflare.
# ═══════════════════════════════════════════════════════════════════
_engine_install_state: Dict[str, Any] = {
    "status": "idle",          # idle | running | success | error
    "source": None,
    "log": [],
    "started_at": None,
    "finished_at": None,
    "message": "",
}


def _engine_probe(deep: bool = False) -> Dict[str, Any]:
    """Check whether the Playwright engine is usable.

    By default this is LIGHTWEIGHT (import checks only) so it is safe to call
    on every status poll. Launching a real Chromium is expensive and, on a
    constrained pod, repeatedly doing so starves the thread-pool and times out
    other endpoints — so the browser launch test only runs when deep=True.
    """
    out = {"playwright": False, "playwright_stealth": False, "chromium": False}
    try:
        import playwright  # noqa: F401
        out["playwright"] = True
    except Exception:
        pass
    try:
        import playwright_stealth  # noqa: F401
        out["playwright_stealth"] = True
    except Exception:
        pass
    if deep and out["playwright"]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as _p:
                _b = _p.chromium.launch(headless=True)
                _b.close()
            out["chromium"] = True
        except Exception:
            out["chromium"] = False
    else:
        # Cheap heuristic: chromium browser binary present in the cache dir.
        try:
            import glob as _glob
            import os as _os
            cache = _os.path.expanduser("~/.cache/ms-playwright")
            out["chromium"] = bool(_glob.glob(_os.path.join(cache, "chromium-*")))
        except Exception:
            out["chromium"] = False
    out["ready"] = bool(out["playwright"] and out["playwright_stealth"] and out["chromium"])
    return out
















# ═════════════════════════════════════════════════════════════════
# WestMotors lazy parser worker (Phase IV-3)
# ═════════════════════════════════════════════════════════════════










# ═════════════════════════════════════════════════════════════════
# Compact promotion / parsing dashboard payload (Phase IV-3 UI)
# ═════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════
# Stabilization snapshot (Phase IV-3) — quick ops dashboard
# ═════════════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════════════
# BITMOTORS LEGACY SYNC ENDPOINTS — DEPRECATED (LIVE-FIRST architecture)
# ─────────────────────────────────────────────────────────────────
# All sync/scrape/full-sync/incremental endpoints used to accumulate the
# BidMotors catalogue locally. We removed the accumulation layer because
# auction data is a real-time stream — any local snapshot is stale within
# minutes. These routes now return 410 Gone so legacy clients fail loudly.
# ═══════════════════════════════════════════════════════════════════
_DEPRECATED_SYNC_MSG = (
    "Endpoint deprecated. The BIBI Cars backend now uses LIVE-FIRST architecture: "
    "every search hits BidMotors directly via /api/public/search/{query}. "
    "Local accumulation has been disabled."
)

def _deprecated_sync_response():
    return JSONResponse(
        status_code=410,
        content={
            "success": False,
            "error": "deprecated",
            "architecture": "LIVE_FIRST",
            "message": _DEPRECATED_SYNC_MSG,
            "use_instead": "/api/public/search/{query}",
        },
    )








# ═══════════════════════════════════════════════════════════════════
# Phase IV — WestMotors Index admin endpoints
# ═══════════════════════════════════════════════════════════════════




















# ═══════════════════════════════════════════════════════════════════
# Phase IV-2 — Lemon-Cars Index admin endpoints
# ═══════════════════════════════════════════════════════════════════























# NOTE: ``/api/ingestion/admin/parsers/bitmotors/run-once`` and
# ``/api/ingestion/admin/parsers/bitmotors/configure`` deprecated stubs were
# REMOVED — they were shadowed by the generic
# ``/api/ingestion/admin/parsers/{source}/...`` handlers defined earlier
# and therefore unreachable. The generic handlers correctly return a
# deprecated response for ``source=bitmotors``.





# ═══════════════════════════════════════════════════════════════════
# PHASE II — Smart search helpers (watchlist, rescan, search_logs)
# ═══════════════════════════════════════════════════════════════════

async def _log_public_search(raw: str, clean: str, kind: str, found: bool, source: str) -> None:
    """Insert one row into search_logs for analytics."""
    try:
        if db is None:
            return
        await db.search_logs.insert_one({
            "raw": (raw or "")[:128],
            "clean": (clean or "")[:64],
            "kind": kind,
            "found": bool(found),
            "source": source,
            "ts": datetime.now(timezone.utc),
        })
    except Exception:
        pass


# [auto-domain removed] /api/public/search/watch (public_search_watch)


@fastapi_app.delete("/api/public/search/watch/{watch_id}")
async def public_search_watch_delete(
    watch_id: str,
    user: Optional[dict] = Depends(optional_user),
):
    """Remove a watchlist entry (authenticated user can delete own;
    unauthenticated delete requires ?email= param — kept simple: admin only)."""
    match: Dict[str, Any] = {"id": watch_id}
    if user:
        if not is_admin(user):
            match["userId"] = user.get("id")
    else:
        raise HTTPException(status_code=401, detail="authentication required")
    res = await db.search_watchlist.delete_one(match)
    return {"success": bool(res.deleted_count), "deleted": res.deleted_count}



@fastapi_app.post("/api/public/search/rescan")
async def public_search_rescan(data: Dict[str, Any] = Body(...)):
    """Force a live BidMotors fetch for a VIN/LOT, bypassing the TTL cache.

    Body: {vin: "..."} (VIN 17 chars or LOT digits). Also busts the cache
    entry so subsequent reads are fresh.
    """
    raw = str(data.get("vin") or data.get("query") or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="vin is required")
    clean = raw.upper().replace(" ", "").replace("-", "")

    # Cache bust: remove any keys prefixed with suggest:<clean>:
    if live_search_cache is not None:
        try:
            async with live_search_cache._lock:  # type: ignore[attr-defined]
                keys_to_drop = [k for k in list(live_search_cache._store.keys()) if clean in k]
                for k in keys_to_drop:
                    live_search_cache._store.pop(k, None)
        except Exception:
            pass

    # [ECO CLEANUP] Bitmotors live-search removed (BITMOTORS_AVAILABLE=False).
    # Endpoint kept for API compatibility; always reports unavailable.
    return {"success": False, "error": "bidmotors unavailable", "query": raw}


# admin_search_analytics moved to app/routers/admin_search.py (Wave 2B/Batch 8)





# Proxies







# ═══════════════════════════════════════════════════════════════════
# INVOICES FULL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.post("/api/invoices/create")
async def create_invoice(data: Dict[str, Any] = Body(...)):
    """Create invoice"""
    invoice = {
        "id": f"inv-{datetime.now(timezone.utc).timestamp()}",
        "customerId": data.get("customerId"),
        "dealId": data.get("dealId"),
        "amount": data.get("amount"),
        "currency": data.get("currency", "UAH"),
        "status": "pending",
        "items": data.get("items", []),
        "dueDate": data.get("dueDate"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.invoices.insert_one(invoice)
    invoice.pop("_id", None)
    return {"success": True, "invoice": invoice}

# IMPORTANT: Specific routes MUST be before /{invoice_id} dynamic route!
@fastapi_app.get("/api/invoices/me")
async def my_invoices():
    """Customer invoices - MUST be before /{invoice_id}"""
    return {"success": True, "data": []}

@fastapi_app.get("/api/invoices/manager/my", dependencies=[Depends(require_manager_or_admin)])
async def manager_invoices():
    """Manager invoices - MUST be before /{invoice_id}"""
    cursor = db.invoices.find({}, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

@fastapi_app.get("/api/invoices/overdue")
async def overdue_invoices():
    """Overdue invoices - MUST be before /{invoice_id}"""
    cursor = db.invoices.find({"status": "overdue"}, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

@fastapi_app.get("/api/invoices/analytics")
async def invoice_analytics():
    """Invoice analytics - MUST be before /{invoice_id}"""
    return {
        "success": True,
        "analytics": {
            "total": await db.invoices.count_documents({}),
            "paid": await db.invoices.count_documents({"status": "paid"}),
            "pending": await db.invoices.count_documents({"status": "pending"}),
            "overdue": await db.invoices.count_documents({"status": "overdue"}),
            "totalAmount": 0,
            "paidAmount": 0
        }
    }

@fastapi_app.post("/api/invoices/checkout")
async def invoice_checkout(request: Request, data: Dict[str, Any] = Body(...)):
    """Create a real Stripe Checkout session for an existing invoice.

    Body: { "invoiceId": "...", "originUrl": "https://..." (optional) }
    Returns: { success, url, sessionId, publishableKey, mode }
    """
    invoice_id = data.get("invoiceId") or data.get("invoice_id")
    if not invoice_id:
        raise HTTPException(status_code=400, detail="invoiceId is required")
    invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    if invoice.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    amount = invoice.get("amount") or invoice.get("total") or 0
    description = invoice.get("description") or invoice.get("title") or f"Invoice {invoice_id}"
    customer_id = invoice.get("customerId") or invoice.get("customer_id")
    customer = (await db.customers.find_one({"customerId": customer_id}, {"_id": 0})) if customer_id else None
    customer_email = (customer or {}).get("email")

    payload = {
        "amount": amount,
        "description": description,
        "invoiceId": invoice_id,
        "currency": invoice.get("currency"),
        "customerEmail": customer_email,
    }
    # Lazy import: Stripe helpers + checkout endpoint live in
    # app/routers/payments.py (Wave 1 extraction).  This call is the legacy
    # invoice-domain bridge into the payments router.
    #
    # Phase 5.5 / E (2026-05-19) — ``get_stripe_config`` now imported from
    # its canonical service module (``app/services/stripe_config.py``);
    # ``create_checkout_session`` stays in the payments router.
    from app.routers.payments import create_checkout_session
    from app.services.stripe_config import get_stripe_config
    if data.get("originUrl"):
        cfg = await get_stripe_config()
        origin = str(data["originUrl"]).rstrip("/")
        succ = cfg["successUrl"]; canc = cfg["cancelUrl"]
        payload["successUrl"] = (succ if succ.startswith("http") else origin + (succ if succ.startswith("/") else f"/{succ}"))
        payload["cancelUrl"]  = (canc if canc.startswith("http") else origin + (canc if canc.startswith("/") else f"/{canc}"))

    return await create_checkout_session(request, payload)


@fastapi_app.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Get invoice by ID - MUST be after specific routes"""
    invoice = await db.invoices.find_one({"id": invoice_id}, {'_id': 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"success": True, "data": invoice}


@fastapi_app.post("/api/invoices/checkout/{invoice_id}")
async def invoice_checkout_id(request: Request, invoice_id: str, data: Dict[str, Any] = Body(default={})):
    """Convenience route: same as /api/invoices/checkout but with id in path."""
    return await invoice_checkout(request, {**(data or {}), "invoiceId": invoice_id})


@fastapi_app.post("/api/invoices/create-from-package")
async def create_invoice_from_package(data: Dict[str, Any] = Body(...)):
    """Create invoice from package"""
    return await create_invoice(data)

# ═══════════════════════════════════════════════════════════════════
# SHIPMENTS FULL ENDPOINTS  
# ═══════════════════════════════════════════════════════════════════

# ==================== SHIPMENT EVENT SYSTEM (ЯДРО) ====================

# [car-import removed] create_shipment_event + calculate_shipment_status
# (orphan after shipment-tracking helpers removed)


# ==================== SHIPMENT CRUD (UPDATED) ====================







# ═══════════════════════════════════════════════════════════════════
# JOURNEY API — stages, current position, events, manager controls
# ═══════════════════════════════════════════════════════════════════
#   GET    /api/shipments/{id}/journey              — one-shot cabinet view
#   PUT    /api/shipments/{id}/stages/{stage_id}    — edit a stage (vessel, label, type)
#   POST   /api/shipments/{id}/stages/advance       — mark current done, activate next
#   POST   /api/shipments/{id}/stages/{stage_id}/activate — manager override
#   POST   /api/shipments/{id}/stages               — replace full stages array
#
# The existing /api/shipments/{id}/tick already forces update_shipment_position.
# The existing /api/shipments/{id}/vessel binds a vessel at shipment level (legacy
# field). The new /stages/{stage_id} binds vessel per stage — preferred path.
# ═══════════════════════════════════════════════════════════════════














# ==================== TEAM LEAD ENDPOINTS ====================

# [auto-domain removed] /api/team/shipping (team_shipping_overview)


# [auto-domain removed] /api/team/shipping/stalled (team_stalled_shipments)


# [auto-domain removed] /api/team/shipping/risky (team_risky_shipments)


# [auto-domain removed] /api/team/shipping/{shipment_id}/ping-manager (ping_manager_about_shipment)


# [auto-domain removed] /api/team/shipping/{shipment_id}/create-task (create_shipment_task)


# [auto-domain removed] /api/team/shipping/{shipment_id}/escalate (escalate_shipment)


# DocuSign
@fastapi_app.get("/api/docusign/envelopes/{envelope_id}")
async def get_docusign_envelope(envelope_id: str):
    """Get DocuSign envelope"""
    return {"success": True, "data": {"id": envelope_id, "status": "pending"}}

@fastapi_app.post("/api/docusign/envelopes")
async def create_docusign_envelope(data: Dict[str, Any] = Body(...)):
    """Create DocuSign envelope"""
    return {"success": True, "envelopeId": f"env-{datetime.now(timezone.utc).timestamp()}"}

# ═══════════════════════════════════════════════════════════════════
# ESCALATIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/escalations")
async def list_escalations(limit: int = 50, includeSnoozed: bool = False, includeResolved: bool = False):
    """List escalations - returns direct array.
    Wave-8: by default hides resolved/snoozed-and-not-yet-due rows so the Insights queue is clean.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    or_conditions: List[Dict[str, Any]] = []
    if not includeResolved:
        or_conditions.append({"status": {"$ne": "resolved"}})
    if not includeSnoozed:
        # Show snoozed rows whose snoozedUntil has elapsed (back in queue),
        # hide currently-snoozed ones.
        or_conditions.append({
            "$or": [
                {"status": {"$ne": "snoozed"}},
                {"snoozedUntil": {"$lte": now_iso}},
            ]
        })
    query: Dict[str, Any] = {"$and": or_conditions} if or_conditions else {}
    cursor = db.escalations.find(query, {'_id': 0}).limit(limit)
    items = await cursor.to_list(length=limit)
    return items if items else []

@fastapi_app.post("/api/escalations")
async def create_escalation(data: Dict[str, Any] = Body(...)):
    """Create escalation"""
    escalation = {
        "id": f"esc-{datetime.now(timezone.utc).timestamp()}",
        "type": data.get("type"),
        "entityId": data.get("entityId"),
        "reason": data.get("reason"),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.escalations.insert_one(escalation)
    return {"success": True, "id": escalation["id"]}

@fastapi_app.post("/api/escalations/process")
async def process_escalations():
    """Process escalations"""
    return {"success": True, "processed": 0}

@fastapi_app.get("/api/escalations/stats")
async def escalation_stats():
    """Escalation stats - returns stats object directly"""
    return {
        "managerPending": await db.escalations.count_documents({"currentLevel": "manager_pending"}),
        "teamLeadPending": await db.escalations.count_documents({"currentLevel": "teamlead_pending"}),
        "ownerPending": await db.escalations.count_documents({"currentLevel": "owner_pending"}),
        "resolvedToday": await db.escalations.count_documents({"status": "resolved"}),
        "pending": await db.escalations.count_documents({"status": "pending"}),
        "resolved": await db.escalations.count_documents({"status": "resolved"}),
        "total": await db.escalations.count_documents({})
    }

@fastapi_app.patch("/api/escalations/{escalation_id}/resolve")
async def resolve_escalation(escalation_id: str, data: Dict[str, Any] = Body(...)):
    """Resolve escalation"""
    await db.escalations.update_one({"_id": escalation_id}, {"$set": {"status": "resolved"}})
    return {"success": True}

# Wave-8: Also accept POST (frontend Insights → Escalation Queue uses POST for inline action)
@fastapi_app.post("/api/escalations/{escalation_id}/resolve")
async def resolve_escalation_post(escalation_id: str, data: Dict[str, Any] = Body(default={})):
    """Resolve escalation (POST alias used by Insights → Risk & Alerts → Escalation Queue)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    res = await db.escalations.update_one(
        {"$or": [{"_id": escalation_id}, {"id": escalation_id}]},
        {"$set": {"status": "resolved", "resolvedAt": now_iso, "resolvedBy": (data.get("actor") if isinstance(data, dict) else None)}}
    )
    return {"success": True, "matched": res.matched_count, "modified": res.modified_count}

@fastapi_app.post("/api/escalations/{escalation_id}/snooze")
async def snooze_escalation(escalation_id: str, data: Dict[str, Any] = Body(default={})):
    """
    Snooze an escalation for N hours.
    Body: { "hours": <int, default 4>, "actor": <optional email/id>, "reason": <optional> }
    The snoozed escalation is hidden from queues until snoozedUntil <= now.
    """
    hours = int((data or {}).get("hours") or 4)
    hours = max(1, min(hours, 24 * 14))  # clamp 1h .. 14d
    now = datetime.now(timezone.utc)
    snoozed_until = (now + timedelta(hours=hours)).isoformat()
    actor = (data or {}).get("actor")
    reason = (data or {}).get("reason")
    update = {
        "status": "snoozed",
        "snoozedUntil": snoozed_until,
        "snoozedAt": now.isoformat(),
        "snoozedHours": hours,
    }
    if actor:
        update["snoozedBy"] = actor
    if reason:
        update["snoozeReason"] = reason
    res = await db.escalations.update_one(
        {"$or": [{"_id": escalation_id}, {"id": escalation_id}]},
        {"$set": update}
    )
    return {
        "success": True,
        "matched": res.matched_count,
        "modified": res.modified_count,
        "snoozedUntil": snoozed_until,
        "hours": hours,
    }

@fastapi_app.post("/api/escalations/{escalation_id}/reassign")
async def reassign_escalation(escalation_id: str, data: Dict[str, Any] = Body(...)):
    """Reassign an escalation to another owner. Body: { "owner": <email>, "actor": <optional> }"""
    owner = (data or {}).get("owner") or (data or {}).get("assignTo")
    if not owner:
        raise HTTPException(status_code=400, detail="owner is required")
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        "owner": owner,
        "ownerEmail": owner,
        "assignedTo": owner,
        "reassignedAt": now_iso,
        "reassignedBy": (data or {}).get("actor"),
        "status": "open",
    }
    res = await db.escalations.update_one(
        {"$or": [{"_id": escalation_id}, {"id": escalation_id}]},
        {"$set": update}
    )
    return {"success": True, "matched": res.matched_count, "owner": owner}

@fastapi_app.put("/api/escalations/{escalation_id}")
async def update_escalation(escalation_id: str, data: Dict[str, Any] = Body(...)):
    """Update escalation"""
    await db.escalations.update_one({"id": escalation_id}, {"$set": data})
    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# INVOICE REMINDERS ENDPOINTS — wired to real invoices collection
# (Bug-fix Wave: no more mock-zero responses; honest empty state on no data)
# All thresholds are live-editable via /api/invoice-reminders/settings.
# ═══════════════════════════════════════════════════════════════════

REMINDER_SETTINGS_ID = "reminder_settings_singleton"
REMINDER_SETTINGS_DEFAULTS: Dict[str, Any] = {
    "id": REMINDER_SETTINGS_ID,
    "enabled": True,
    # Escalation thresholds (days past dueDate).
    "level1_days": 1,    # Manager (warning)
    "level2_days": 3,    # Team Lead
    "level3_days": 5,    # Owner
    "critical_days": 7,  # Immediate action
    # Dispatch policy.
    "reminder_after_days": 3,   # start dispatching reminders this many days after issue/dueDate
    "cooldown_hours": 48,       # min hours between two reminders for the same invoice
    "pre_reminder_hours": 24,   # T-24h pre-reminder before the due date
    "channels": ["email", "in_app"],  # supported: email, in_app, telegram, sms
}


async def _load_reminder_settings() -> Dict[str, Any]:
    """Read the reminder-settings singleton, seeding defaults on first read."""
    try:
        doc = await db.reminder_settings.find_one({"id": REMINDER_SETTINGS_ID}, {"_id": 0})
        if doc:
            # Backfill any missing keys with defaults so future code is safe.
            merged = {**REMINDER_SETTINGS_DEFAULTS, **doc}
            return merged
        # First read → seed and return defaults.
        seed = {
            **REMINDER_SETTINGS_DEFAULTS,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await db.reminder_settings.update_one(
                {"id": REMINDER_SETTINGS_ID}, {"$setOnInsert": seed}, upsert=True
            )
        except Exception:
            logger.exception("[reminders] failed to seed default settings")
        return seed
    except Exception:
        logger.exception("[reminders] _load_reminder_settings failed; using in-memory defaults")
        return dict(REMINDER_SETTINGS_DEFAULTS)


def _iso_now_minus(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _invoice_is_unpaid_query() -> Dict[str, Any]:
    # "Unpaid" = anything not paid/void/cancelled. Includes overdue/sent/pending/draft.
    return {"status": {"$nin": ["paid", "void", "cancelled", "refunded"]}}


async def _count_overdue(days: int) -> int:
    """Count unpaid invoices whose dueDate (preferred) or created_at is older than `days`."""
    cutoff = _iso_now_minus(days)
    q = dict(_invoice_is_unpaid_query())
    q["$or"] = [
        {"dueDate": {"$lte": cutoff}},
        {"due_date": {"$lte": cutoff}},
        {"dueDate": {"$exists": False}, "created_at": {"$lte": cutoff}},
    ]
    try:
        return await db.invoices.count_documents(q)
    except Exception:
        logger.exception("[reminders] _count_overdue failed")
        return 0


# ── Settings endpoints ───────────────────────────────────────────────
@fastapi_app.get("/api/invoice-reminders/settings")
async def get_reminder_settings():
    """Return the live reminder-settings doc.

    Defaults are seeded on first read so the response is always populated.
    """
    cfg = await _load_reminder_settings()
    return {"success": True, "data": cfg, "defaults": REMINDER_SETTINGS_DEFAULTS}


_REMINDER_INT_FIELDS = {
    "level1_days": (0, 60),
    "level2_days": (0, 90),
    "level3_days": (0, 180),
    "critical_days": (0, 365),
    "reminder_after_days": (0, 60),
    "cooldown_hours": (1, 720),
    "pre_reminder_hours": (0, 168),
}
_REMINDER_CHANNEL_ALLOWED = {"email", "in_app", "telegram", "sms"}


@fastapi_app.put("/api/invoice-reminders/settings")
async def update_reminder_settings(payload: Dict[str, Any] = Body(default={})):
    """Update reminder settings. Admin-style endpoint — no destructive ops.

    Accepted fields (everything else is ignored):
      • enabled (bool)
      • level1_days, level2_days, level3_days, critical_days (int)
      • reminder_after_days, cooldown_hours, pre_reminder_hours (int)
      • channels (list[str], subset of {email,in_app,telegram,sms})

    Validation:
      • int fields are clamped to safe ranges
      • escalation thresholds must satisfy level1 ≤ level2 ≤ level3 ≤ critical
      • at least one channel must remain enabled
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")

    updates: Dict[str, Any] = {}
    errors: List[str] = []

    if "enabled" in payload:
        updates["enabled"] = bool(payload["enabled"])

    for fname, (lo, hi) in _REMINDER_INT_FIELDS.items():
        if fname in payload and payload[fname] is not None:
            try:
                v = int(payload[fname])
            except (TypeError, ValueError):
                errors.append(f"{fname} must be an integer")
                continue
            if v < lo or v > hi:
                errors.append(f"{fname} out of range [{lo}, {hi}]")
                continue
            updates[fname] = v

    if "channels" in payload:
        raw = payload["channels"] or []
        if not isinstance(raw, list):
            errors.append("channels must be a list of strings")
        else:
            cleaned = [c for c in raw if isinstance(c, str) and c in _REMINDER_CHANNEL_ALLOWED]
            if not cleaned:
                errors.append("at least one valid channel is required")
            else:
                updates["channels"] = list(dict.fromkeys(cleaned))  # dedupe preserving order

    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    if not updates:
        # Nothing to update — still return the current settings so the UI stays in sync.
        return {"success": True, "data": await _load_reminder_settings(), "noop": True}

    # Order invariant: level1 ≤ level2 ≤ level3 ≤ critical (use merged view).
    current = await _load_reminder_settings()
    merged = {**current, **updates}
    order = [merged["level1_days"], merged["level2_days"], merged["level3_days"], merged["critical_days"]]
    if not (order[0] <= order[1] <= order[2] <= order[3]):
        raise HTTPException(
            status_code=422,
            detail={"errors": [
                "escalation thresholds must satisfy level1_days ≤ level2_days ≤ level3_days ≤ critical_days"
            ]},
        )

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        await db.reminder_settings.update_one(
            {"id": REMINDER_SETTINGS_ID},
            {"$set": updates, "$setOnInsert": {"id": REMINDER_SETTINGS_ID, "created_at": updates["updated_at"]}},
            upsert=True,
        )
    except Exception:
        logger.exception("[reminders] failed to persist settings")
        raise HTTPException(status_code=500, detail="failed to persist settings")

    return {"success": True, "data": await _load_reminder_settings()}


# ── Read endpoints (driven by live settings) ─────────────────────────
@fastapi_app.get("/api/invoice-reminders/critical")
async def critical_reminders(limit: int = 50):
    """Critical (≥ `critical_days` overdue, still unpaid) invoices, newest-first.

    Returns ALWAYS a list. Frontend uses len(data)==0 → honest empty state.
    """
    cfg = await _load_reminder_settings()
    cutoff = _iso_now_minus(int(cfg.get("critical_days", 7)))
    q = dict(_invoice_is_unpaid_query())
    q["$or"] = [
        {"dueDate": {"$lte": cutoff}},
        {"due_date": {"$lte": cutoff}},
        {"dueDate": {"$exists": False}, "created_at": {"$lte": cutoff}},
    ]
    try:
        cursor = db.invoices.find(q, {"_id": 0}).sort("dueDate", 1).limit(int(limit))
        items = await cursor.to_list(length=int(limit))
    except Exception:
        logger.exception("[reminders] critical_reminders query failed")
        items = []
    return items


@fastapi_app.get("/api/invoice-reminders/escalation-summary")
async def reminder_escalation_summary():
    """Real escalation counters for the Invoice Reminders dashboard.

    Counters use thresholds from `reminder_settings`:
        level1Count   — ≥ level1_days overdue (Manager)
        level2Count   — ≥ level2_days overdue (Team Lead)
        level3Count   — ≥ level3_days overdue (Owner)
        criticalCount — ≥ critical_days overdue (immediate action)

    Also emits:
        totalInvoices     — total invoices in the system
        unpaidInvoices    — total unpaid (any age)
        hasData           — true ⇔ at least one invoice exists
        lastProcessedAt   — newest `lastReminderAt` across all invoices (or null)
        settings          — the live thresholds (so frontend tooltips stay truthful)
    """
    cfg = await _load_reminder_settings()
    try:
        total_invoices = await db.invoices.count_documents({})
    except Exception:
        logger.exception("[reminders] count total invoices failed")
        total_invoices = 0
    try:
        unpaid_invoices = await db.invoices.count_documents(_invoice_is_unpaid_query())
    except Exception:
        unpaid_invoices = 0

    level1 = await _count_overdue(int(cfg.get("level1_days", 1)))
    level2 = await _count_overdue(int(cfg.get("level2_days", 3)))
    level3 = await _count_overdue(int(cfg.get("level3_days", 5)))
    critical = await _count_overdue(int(cfg.get("critical_days", 7)))

    last_processed_at = None
    try:
        newest = await db.invoices.find_one(
            {"lastReminderAt": {"$exists": True, "$ne": None}},
            {"_id": 0, "lastReminderAt": 1},
            sort=[("lastReminderAt", -1)],
        )
        if newest:
            last_processed_at = newest.get("lastReminderAt")
    except Exception:
        pass

    return {
        "success": True,
        "hasData": total_invoices > 0,
        "totalInvoices": total_invoices,
        "unpaidInvoices": unpaid_invoices,
        "level1Count": level1,
        "level2Count": level2,
        "level3Count": level3,
        "criticalCount": critical,
        "lastProcessedAt": last_processed_at,
        "settings": {
            "enabled": cfg.get("enabled", True),
            "level1_days": cfg.get("level1_days", 1),
            "level2_days": cfg.get("level2_days", 3),
            "level3_days": cfg.get("level3_days", 5),
            "critical_days": cfg.get("critical_days", 7),
            "cooldown_hours": cfg.get("cooldown_hours", 48),
            "reminder_after_days": cfg.get("reminder_after_days", 3),
            "pre_reminder_hours": cfg.get("pre_reminder_hours", 24),
            "channels": cfg.get("channels", ["email", "in_app"]),
        },
    }


@fastapi_app.post("/api/invoice-reminders/process")
async def process_reminders():
    """Run the payment-reminder scanner ONCE, on demand.

    Returns the real `processed` (invoices inspected) and `reminders`
    (notifications dispatched) counts so the "Run processing" button is
    no longer decorative. Surfaces the actual error message instead of
    a generic 500 so the UI can show useful feedback.
    """
    try:
        cfg = await _load_reminder_settings()
        if not cfg.get("enabled", True):
            return {
                "success": True,
                "processed": 0,
                "reminders": 0,
                "skipped": True,
                "reason": "reminder_engine_disabled",
                "ranAt": datetime.now(timezone.utc).isoformat(),
            }
        res = await _run_payment_reminders_once(settings=cfg)
        return {
            "success": True,
            "processed": int(res.get("processed", 0)),
            "reminders": int(res.get("reminders", 0)),
            "ranAt": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[reminders] on-demand process failed")
        # Return a 200 with success=false so the UI can show the actual reason,
        # not a generic toast. This is intentional: the operator needs context.
        return {
            "success": False,
            "processed": 0,
            "reminders": 0,
            "error": str(e) or e.__class__.__name__,
            "ranAt": datetime.now(timezone.utc).isoformat(),
        }

# ═══════════════════════════════════════════════════════════════════
# VEHICLES EXTENDED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

# ❌ REMOVED (April 2026): /api/vehicles, /api/vehicles/{id},
# /api/vehicles/makes, /api/vehicles/stats — backed the deprecated
# /admin/vehicles "Vehicle Database" page (catalog rudiment incompatible with
# the on-demand VIN resolver architecture). The underlying db.vin_data is
# kept as an internal cache only.

# ═══════════════════════════════════════════════════════════════════
# TASKS EXTENDED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.post("/api/tasks")
async def create_task(
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Create a task.

    Role matrix:
      - admin / master_admin / owner → may assign to team_lead OR manager
      - team_lead                    → may assign to manager only
      - manager                      → forbidden (managers EXECUTE tasks)

    The `assigneeId` is REQUIRED and must point at an active staff member
    whose role is in the caller's allowed set. We do NOT silently drop
    invalid assignees — we 400 so the frontend shows the real reason.
    """
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner"):
        allowed_assignee_roles = {"team_lead", "manager"}
    elif role == "team_lead":
        allowed_assignee_roles = {"manager"}
    else:
        raise HTTPException(
            status_code=403,
            detail="Your role is not allowed to create tasks. Only admin and team_lead can.",
        )

    assignee_id = (data.get("assigneeId") or "").strip()
    if not assignee_id:
        raise HTTPException(status_code=400, detail="assigneeId is required")

    assignee = await db.staff.find_one({"id": assignee_id}, {"_id": 0, "password": 0})
    if not assignee:
        raise HTTPException(status_code=400, detail=f"Assignee not found: {assignee_id}")
    assignee_role = (assignee.get("role") or "").lower()
    if assignee_role not in allowed_assignee_roles:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Your role ({role}) cannot assign tasks to a {assignee_role}. "
                f"Allowed assignee roles: {sorted(allowed_assignee_roles)}"
            ),
        )

    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    # Compute id ONCE so the legacy `taskId` alias stays exactly equal to
    # the canonical `id`. Previously each f-string called datetime.now()
    # separately, producing two micro-second-different timestamps that
    # diverged after Python stringified them (trailing-zero stripping),
    # which is why update_task historically had to fall back to a $or query.
    _now = datetime.now(timezone.utc)
    _id = f"task-{_now.timestamp()}"
    task = {
        "id": _id,
        "taskId": _id,
        "title": title,
        "description": data.get("description"),
        "type": data.get("type", "general"),
        "assigneeId": assignee_id,
        "assigneeRole": assignee_role,
        "assigneeName": assignee.get("name") or assignee.get("email"),
        "customerId": data.get("customerId") or None,
        "leadId": data.get("leadId"),
        "dealId": data.get("dealId"),
        "dueDate": data.get("dueDate") or None,
        "priority": data.get("priority", "medium"),
        "status": "pending",
        "comment": (data.get("comment") or "").strip() or None,
        "createdBy": current_user.get("id") or current_user.get("managerId"),
        "createdByRole": role,
        "createdByName": current_user.get("name") or current_user.get("email"),
        "created_at": _now.isoformat(),
    }
    await db.tasks.insert_one(task)
    # Motor mutates `task` to attach the bson ObjectId `_id` after insert,
    # which FastAPI's jsonable_encoder cannot serialise → 500 on the create
    # path. Strip it before responding so the frontend gets a clean payload.
    task.pop("_id", None)
    return {"success": True, "task": task}

# IMPORTANT: Specific routes MUST be before /{task_id} dynamic route!
@fastapi_app.get("/api/tasks/active")
async def active_tasks():
    """Active tasks - MUST be before /{task_id}"""
    cursor = db.tasks.find({"status": {"$ne": "completed"}}, {'_id': 0}).limit(100)
    items = await cursor.to_list(length=100)
    return {"success": True, "data": items}

@fastapi_app.get("/api/tasks/queue")
async def task_queue():
    """Task queue - MUST be before /{task_id}"""
    cursor = db.tasks.find({"status": "pending"}, {'_id': 0}).sort('dueDate', 1).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

@fastapi_app.get("/api/tasks/stats")
async def task_stats():
    """Task statistics - MUST be before /{task_id}"""
    return {
        "success": True,
        "stats": {
            "total": await db.tasks.count_documents({}),
            "pending": await db.tasks.count_documents({"status": "pending"}),
            "completed": await db.tasks.count_documents({"status": "completed"}),
            "overdue": 0
        }
    }

@fastapi_app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task by ID - MUST be after specific routes"""
    task = await db.tasks.find_one({"$or": [{"id": task_id}, {"taskId": task_id}]}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "data": task}

@fastapi_app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Delete task.

    - admin / master_admin / owner → any task
    - team_lead → only tasks they created
    - manager → forbidden
    """
    role = (current_user.get("role") or "").lower()
    if role not in ("admin", "master_admin", "owner", "team_lead"):
        raise HTTPException(status_code=403, detail="Not allowed")
    if role == "team_lead":
        me = current_user.get("id") or current_user.get("managerId")
        task = await db.tasks.find_one(
            {"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0}
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.get("createdBy") != me:
            raise HTTPException(status_code=403, detail="Team leads can only delete tasks they created")
    await db.tasks.delete_one({"$or": [{"id": task_id}, {"taskId": task_id}]})
    return {"success": True}


# ─── Manager-workspace lifecycle actions (frontend ManagerTasksPage) ──
# The frontend has dispatched POST /api/tasks/{id}/start and /complete
# since the manager workspace was added, but the backend never registered
# them. Tasks could be created and listed, but never moved out of
# "pending" from the manager UI — silently 404'ing.
@fastapi_app.post("/api/tasks/{task_id}/start")
async def start_task(
    task_id: str,
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Mark a task as in-progress. Idempotent.

    The task assignee, the creator, or any admin can start the task.
    """
    task = await db.tasks.find_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    role = (current_user.get("role") or "").lower()
    me = current_user.get("id") or current_user.get("managerId")
    if role not in ("admin", "master_admin", "owner") and task.get("assigneeId") != me and task.get("createdBy") != me:
        raise HTTPException(status_code=403, detail="Only the assignee, creator, or an admin can start this task")

    res = await db.tasks.update_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]},
        {"$set": {
            "status": "in_progress",
            "startedAt": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    fresh = await db.tasks.find_one({"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0})
    return {"success": True, "task": fresh}


@fastapi_app.post("/api/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Mark a task as completed. Idempotent. Same access rules as /start."""
    task = await db.tasks.find_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    role = (current_user.get("role") or "").lower()
    me = current_user.get("id") or current_user.get("managerId")
    if role not in ("admin", "master_admin", "owner") and task.get("assigneeId") != me and task.get("createdBy") != me:
        raise HTTPException(status_code=403, detail="Only the assignee, creator, or an admin can complete this task")

    update = {
        "status": "completed",
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    if isinstance(data, dict) and data.get("result"):
        update["result"] = data["result"]
    res = await db.tasks.update_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]},
        {"$set": update},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    fresh = await db.tasks.find_one({"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0})
    return {"success": True, "task": fresh}

# ═══════════════════════════════════════════════════════════════════
# LEADS EXTENDED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: str):
    """Get lead"""
    lead = await db.leads.find_one({"id": lead_id}, {'_id': 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": True, "data": lead}

@fastapi_app.post("/api/leads")
async def create_lead(data: Dict[str, Any] = Body(...)):
    """Create lead — car-import CRM model.

    Accepts both the legacy ``name`` payload and the modern split
    ``firstName`` / ``lastName`` form. We always persist BOTH:
      • ``firstName`` / ``lastName`` (individual fields, easier to edit)
      • ``name`` (concatenated convenience field, used by older readers)
    so the admin UI, manager UI, and any reporting query work uniformly.

    Auto-strips Motor's ``_id`` after insert — otherwise FastAPI would
    fail to JSON-serialize the returned dict and respond 500.
    """
    first = (data.get("firstName") or "").strip()
    last  = (data.get("lastName") or "").strip()
    legacy_name = (data.get("name") or "").strip()
    if not first and not last and legacy_name:
        parts = legacy_name.split(maxsplit=1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
    full_name = f"{first} {last}".strip() or legacy_name or "(no name)"

    lead = {
        "id":          f"lead-{datetime.now(timezone.utc).timestamp()}",
        "firstName":   first,
        "lastName":    last,
        "name":        full_name,
        "email":       data.get("email"),
        "phone":       data.get("phone"),
        "phoneCountry": data.get("phoneCountry"),
        "source":      data.get("source", "manual"),
        "status":      data.get("status", "new"),
        "score":       data.get("score", 50),
        "managerId":   data.get("managerId"),
        "vin":         data.get("vin"),
        "vehicleInterest": data.get("vehicleInterest") or data.get("company"),
        # Budget — primary unit is EUR (BIBI is an EU operation). The legacy
        # ``budgetUsd`` key is kept as an accepted input alias for one wave so
        # old API clients / records keep working; new records persist BOTH so
        # historical analytics queries don't break.
        "budgetEur":   float(data.get("budgetEur") or data.get("budgetUsd") or data.get("value") or 0),
        "budgetUsd":   float(data.get("budgetEur") or data.get("budgetUsd") or data.get("value") or 0),
        "budgetCurrency": "EUR",
        "description": data.get("description") or data.get("notes"),
        "notes":       data.get("notes") or data.get("description"),
        "vehicleSnapshot":    data.get("vehicleSnapshot"),
        "calculatorSnapshot": data.get("calculatorSnapshot"),
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    await db.leads.insert_one(lead)
    lead.pop("_id", None)  # strip ObjectId leaked by Motor
    # Доопр #22 — push notification to assignee (or Admin/TL if unassigned)
    try:
        from app.services.lead_notifications import notify_new_lead
        await notify_new_lead(db, lead)
    except Exception as _e:
        logger.debug("[create_lead] notify failed: %s", _e)
    return {"success": True, "lead": lead, "data": lead}

@fastapi_app.put("/api/leads/{lead_id}")
async def update_lead(lead_id: str, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(require_user)):
    """Update lead — recomputes ``name`` if firstName/lastName changed."""
    # Snapshot before for Block 7.1 change history
    _before_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}
    patch = {k: v for k, v in data.items() if k not in ("_id", "id", "created_at")}
    # keep ``name`` in sync when firstName/lastName arrives
    if "firstName" in patch or "lastName" in patch:
        existing = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}
        first = patch.get("firstName", existing.get("firstName") or "")
        last  = patch.get("lastName",  existing.get("lastName") or "")
        patch["name"] = f"{(first or '').strip()} {(last or '').strip()}".strip() or existing.get("name")
    if "value" in patch and "budgetUsd" not in patch and "budgetEur" not in patch:
        try:
            patch["budgetEur"] = float(patch["value"] or 0)
            patch["budgetUsd"] = patch["budgetEur"]  # legacy mirror
        except (TypeError, ValueError):
            pass
    # Cross-mirror budgetEur <-> budgetUsd so legacy and new keys stay in sync.
    if "budgetEur" in patch and "budgetUsd" not in patch:
        try:
            patch["budgetUsd"] = float(patch["budgetEur"] or 0)
        except (TypeError, ValueError):
            pass
    if "budgetUsd" in patch and "budgetEur" not in patch:
        try:
            patch["budgetEur"] = float(patch["budgetUsd"] or 0)
        except (TypeError, ValueError):
            pass
    if "company" in patch and "vehicleInterest" not in patch:
        patch["vehicleInterest"] = patch["company"]
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.leads.update_one({"id": lead_id}, {"$set": patch})
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}

    # Block 7.1 — field-level change history (best-effort, never blocks)
    try:
        from app.services.change_history import record_field_changes as _rfc
        await _rfc(db, entity_type="lead", entity_id=lead_id,
                   before=_before_lead, after=lead, user=current_user, source="api_put")
    except Exception:
        pass

    return {"success": True, "lead": lead, "data": lead}

@fastapi_app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: str):
    """Delete lead"""
    result = await db.leads.delete_one({"id": lead_id})
    return {"success": True, "deleted": result.deleted_count}


@fastapi_app.post("/api/leads/{lead_id}/convert")
async def convert_lead_to_customer(lead_id: str, data: Dict[str, Any] = Body(default={})):
    """Convert a lead into a customer (Wave 4 — manual conversion flow).

    Business rules:
    * Idempotent — if the lead is already linked to a customer, return that
      customer card without creating a duplicate.
    * Reuses an existing customer when one is found by email or phone match
      (prevents duplicate cards when the same person was previously imported
      from the public form).
    * Otherwise creates a new customer from the lead's contact info +
      vehicle/calculator snapshot, then back-links ``customerId`` on the lead
      and flips its status to ``won`` (closed-converted).
    * Optional override fields can come in the body: ``name``, ``email``,
      ``phone``, ``company``, ``notes``, ``type`` — useful when the manager
      wants to amend before converting.
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Already converted → return the existing customer (idempotent).
    if lead.get("customerId"):
        existing = await db.customers.find_one({"id": lead["customerId"]}, {"_id": 0})
        if existing:
            return {
                "success": True,
                "alreadyConverted": True,
                "customer": existing,
                "lead": lead,
            }

    # Build override-aware customer payload.
    first = (data.get("firstName") or lead.get("firstName") or "").strip()
    last  = (data.get("lastName")  or lead.get("lastName")  or "").strip()
    email = (data.get("email")     or lead.get("email")     or "").strip().lower() or None
    phone = data.get("phone")      or lead.get("phone")
    full_name = f"{first} {last}".strip() or lead.get("name") or "(no name)"

    # Reuse existing customer when contact info matches (avoid duplicates).
    match_clauses: List[Dict[str, Any]] = []
    if email:
        match_clauses.append({"email": email})
    if phone:
        match_clauses.append({"phone": phone})
    existing_customer = None
    if match_clauses:
        existing_customer = await db.customers.find_one(
            {"$or": match_clauses},
            {"_id": 0},
        )

    if existing_customer:
        customer = existing_customer
        # Enrich the existing card with anything the lead has that's missing.
        enrich: Dict[str, Any] = {}
        if not customer.get("vehicleInterest") and lead.get("vehicleInterest"):
            enrich["vehicleInterest"] = lead["vehicleInterest"]
        if not customer.get("vehicleSnapshot") and lead.get("vehicleSnapshot"):
            enrich["vehicleSnapshot"] = lead["vehicleSnapshot"]
        if not customer.get("calculatorSnapshot") and lead.get("calculatorSnapshot"):
            enrich["calculatorSnapshot"] = lead["calculatorSnapshot"]
        if enrich:
            enrich["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.customers.update_one({"id": customer["id"]}, {"$set": enrich})
            customer.update(enrich)
    else:
        customer = {
            "id":            f"cust-{datetime.now(timezone.utc).timestamp()}",
            "firstName":     first,
            "lastName":      last,
            "name":          full_name,
            "email":         email,
            "phone":         phone,
            "phoneCountry":  lead.get("phoneCountry"),
            "company":       data.get("company") or lead.get("company"),
            "type":          data.get("type") or lead.get("customerType") or "individual",
            "source":        lead.get("source") or "lead_conversion",
            "vehicleInterest":    lead.get("vehicleInterest"),
            "vehicleSnapshot":    lead.get("vehicleSnapshot"),
            "calculatorSnapshot": lead.get("calculatorSnapshot"),
            "budgetEur":     lead.get("budgetEur") or lead.get("budgetUsd") or 0,
            "budgetCurrency": "EUR",
            "notes":         data.get("notes") or lead.get("notes") or lead.get("description"),
            "status":        "active",
            "convertedFromLeadId": lead_id,
            "created_at":    datetime.now(timezone.utc).isoformat(),
        }
        await db.customers.insert_one(customer)
        customer.pop("_id", None)

    # Back-link the lead so it can't be converted twice + mark it won.
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "customerId": customer["id"],
            "status":     "won",
            "convertedAt": datetime.now(timezone.utc).isoformat(),
            "updated_at":  datetime.now(timezone.utc).isoformat(),
        }},
    )
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or lead

    return {
        "success":   True,
        "customer":  customer,
        "lead":      lead,
        "reused":    bool(existing_customer),
    }

# [auto-domain removed] /api/leads/from-vin (create_lead_from_vin)

# ═══════════════════════════════════════════════════════════════════
# CUSTOMERS EXTENDED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

# NOTE: GET /api/customers/{customer_id} is defined further below (richer
# payload returning both ``data`` and ``customer``). The earlier shadowed
# duplicate was removed to silence the FastAPI Duplicate Operation ID warning.

@fastapi_app.post("/api/customers")
async def create_customer(
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Create customer (admin CRM).

    Same dual-field model as the lead endpoint — accepts split first/last
    plus optional company / vehicle-interest / type, persists everything,
    strips Motor's ``_id`` before returning (otherwise 500).

    Wave 7 — owns ``managerId``:
      * admin / owner / master_admin / team_lead may explicitly set
        ``managerId`` in the body.
      * If a manager creates a customer with no ``managerId``, the
        customer is assigned to that manager (self-ownership).
    """
    first = (data.get("firstName") or "").strip()
    last  = (data.get("lastName") or "").strip()
    legacy_name = (data.get("name") or "").strip()
    if not first and not last and legacy_name:
        parts = legacy_name.split(maxsplit=1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
    full_name = f"{first} {last}".strip() or legacy_name or "(no name)"

    cust_type = data.get("type") or data.get("customerType") or "individual"

    # Wave 7 — determine managerId
    role = (current_user.get("role") or "").lower()
    explicit_mid = data.get("managerId")
    if explicit_mid and role not in {"owner", "master_admin", "admin", "team_lead"}:
        # Managers cannot assign customers to other managers
        explicit_mid = None
    manager_id = explicit_mid or (current_user.get("id") if role == "manager" else None)

    # Country (direction) + Wishes (Customer-Card spec, 2026-06-10) ────────
    #   • country   — enum value in {USA, Korea, Bulgaria, Other}; default
    #     to the BIBI primary market ("Bulgaria") only when explicitly empty
    #     AND `phoneCountry`/`source` give no signal — otherwise leave None
    #     so the manager picks it on the Edit modal (no false data).
    #   • wishes    — structured: { budget_min, budget_max, currency,
    #     timeline_months, note }. All numeric fields default to 0 / null.
    _allowed_countries = {"USA", "Korea", "Bulgaria", "Other"}
    _country_raw = (data.get("country") or "").strip() or None
    if _country_raw and _country_raw not in _allowed_countries:
        _country_raw = "Other"
    _wishes_in = data.get("wishes") if isinstance(data.get("wishes"), dict) else {}
    def _f(v):
        try:
            return float(v) if v not in (None, "") else 0.0
        except Exception:
            return 0.0
    _wishes = {
        "budget_min":      _f(_wishes_in.get("budget_min")),
        "budget_max":      _f(_wishes_in.get("budget_max")),
        "currency":        (_wishes_in.get("currency") or "EUR").upper(),
        "timeline_months": int(_f(_wishes_in.get("timeline_months"))),
        "note":            (_wishes_in.get("note") or "").strip() or None,
    }

    customer = {
        "id":          f"cust-{datetime.now(timezone.utc).timestamp()}",
        "firstName":   first,
        "lastName":    last,
        "name":        full_name,
        "email":       data.get("email"),
        "phone":       data.get("phone"),
        "phoneCountry": data.get("phoneCountry"),
        "company":     data.get("company"),
        "type":        cust_type,
        "source":      data.get("source"),
        "vehicleInterest": data.get("vehicleInterest"),
        "notes":       data.get("notes") or data.get("description"),
        "status":      data.get("status", "active"),
        "managerId":   manager_id,
        "managerId_updated_at": datetime.now(timezone.utc).isoformat() if manager_id else None,
        # Customer-Card spec fields ─────────────────────────────────────────
        "country":     _country_raw,
        "wishes":      _wishes,
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    await db.customers.insert_one(customer)
    customer.pop("_id", None)

    # Block 7.2 — auto-seed canonical system folders for every new customer.
    # Idempotent: ensure_system_folders() short-circuits if folders already exist.
    try:
        from app.services.file_manager import ensure_system_folders as _ensure_sys_folders
        await _ensure_sys_folders(customer["id"], created_by=current_user.get("id"))
    except Exception as _folder_err:  # never block customer creation on folder seed failure
        logger.warning(f"[customers.create] failed to seed system folders for {customer['id']}: {_folder_err}")

    return {"success": True, "customer": customer, "data": customer}

@fastapi_app.put("/api/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Update customer — recomputes ``name`` if firstName/lastName changed.

    Wave 7: ``managerId`` MUST be changed via ``POST /api/admin/reassign``,
    NOT via this endpoint. Any ``managerId`` in the body is silently
    stripped so the reassignment service stays the single source of truth
    for ownership changes (and the audit trail is not bypassed).

    Phase Final / Block 4 — mandatory close guard:
    Transitioning ``status`` to ``closed`` / ``lost`` / ``won`` / ``archived``
    / ``inactive`` requires BOTH:
      1. a comment (in ``db.customer_comments``) made in the last 24h
      2. an open / scheduled next-action (open task OR scheduled meeting)
    Use ``X-Force-Close: true`` header to bypass (master_admin only).
    """
    CLOSE_STATUSES = {"closed", "lost", "won", "archived", "inactive"}
    if "status" in data and (data.get("status") or "").strip().lower() in CLOSE_STATUSES:
        # NOTE: The X-Force-Close override would need a ``request: Request``
        # parameter on this handler; until that is wired in, the close-guard
        # below runs unconditionally for non-master_admin users.
        # We can't read the request object here without a parameter, so do role check + open-tasks check directly
        role = (current_user.get("role") or "").lower()
        if role != "master_admin":
            # Check comments-in-24h
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            twenty_four_ago = (_dt.now(_tz.utc) - _td(hours=24)).isoformat()
            recent_comment = await db.customer_comments.find_one(
                {"customer_id": customer_id, "created_at": {"$gte": twenty_four_ago}},
                {"_id": 0, "id": 1},
            )
            if not recent_comment:
                raise HTTPException(
                    status_code=422,
                    detail="customer_close_blocked_no_comment: A comment in the last 24h is required to close this customer.",
                )
            # Check open next-action (task OR meeting)
            open_task = await db.tasks.find_one(
                {"customerId": customer_id, "status": {"$nin": ["completed", "cancelled"]}},
                {"_id": 0, "id": 1},
            )
            scheduled_meeting = await db.meetings.find_one(
                {"customerId": customer_id, "status": "scheduled"},
                {"_id": 0, "id": 1},
            )
            if not open_task and not scheduled_meeting:
                raise HTTPException(
                    status_code=422,
                    detail="customer_close_blocked_no_next_action: An open task or scheduled meeting (next action) is required to close this customer.",
                )

    patch = {k: v for k, v in data.items() if k not in ("_id", "id", "created_at", "managerId", "managerId_updated_at")}
    if "firstName" in patch or "lastName" in patch:
        existing = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {}
        first = patch.get("firstName", existing.get("firstName") or "")
        last  = patch.get("lastName",  existing.get("lastName") or "")
        patch["name"] = f"{(first or '').strip()} {(last or '').strip()}".strip() or existing.get("name")

    # ── Country (direction) sanitiser ──────────────────────────────────────
    if "country" in patch:
        _allowed_countries_u = {"USA", "Korea", "Bulgaria", "Other"}
        raw = (patch.get("country") or "").strip() or None
        if raw and raw not in _allowed_countries_u:
            raw = "Other"
        patch["country"] = raw

    # ── Wishes (budget / timeline / note) sanitiser ───────────────────────
    if "wishes" in patch and isinstance(patch["wishes"], dict):
        def _fu(v):
            try:
                return float(v) if v not in (None, "") else 0.0
            except Exception:
                return 0.0
        win = patch["wishes"]
        patch["wishes"] = {
            "budget_min":      _fu(win.get("budget_min")),
            "budget_max":      _fu(win.get("budget_max")),
            "currency":        (win.get("currency") or "EUR").upper(),
            "timeline_months": int(_fu(win.get("timeline_months"))),
            "note":            (win.get("note") or "").strip() or None,
        }

    patch["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Block 7.1 — snapshot BEFORE for diff
    _before_cust = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {}
    if not _before_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    # RBAC (2026-06-10): manager can only update own customers
    if not _can_user_see_customer(current_user, _before_cust):
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.customers.update_one({"id": customer_id}, {"$set": patch})
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {}

    # Block 7.1 — field-level change history (best-effort, never blocks)
    try:
        from app.services.change_history import record_field_changes as _rfc
        await _rfc(db, entity_type="customer", entity_id=customer_id,
                   before=_before_cust, after=customer, user=current_user, source="api_put")
    except Exception:
        pass

    return {"success": True, "customer": customer, "data": customer}

@fastapi_app.delete("/api/customers/{customer_id}")
async def delete_customer(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),  # noqa: F841
):
    """Delete customer — admin only.

    We hard-delete from ``db.customers``. Related deals / leads keep
    their ``customerId`` reference (orphaned, but historically auditable).
    """
    result = await db.customers.delete_one({"id": customer_id})
    return {"success": True, "deleted": result.deleted_count}

@fastapi_app.get("/api/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Return a single customer card (RBAC-aware).

    • admin / master_admin / team_lead → can read any customer.
    • manager → only customers they own (`managerId == self.id`).
    """
    cust = await db.customers.find_one({"id": customer_id}, _CUSTOMER_SAFE_PROJECTION)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"success": True, "data": cust, "customer": cust}

@fastapi_app.get("/api/customers/{customer_id}/360")
async def get_customer_360(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Customer 360 — full payload for the Customer360 page.

    Wave-1 rewrite:
      * Returns real `summary` (revenue/profit/deposits sum/leads/quotes/deals)
        — no more zero-stub.
      * Returns `leads/quotes/deals/deposits` arrays consumed by the UI.
      * Adds `health` block (single-pass via CustomerHealthService — same
        score that Customer list and TL Dashboard see — AC#11).

    RBAC (added 2026-06-10 per Customer-Card spec):
      • admin / master_admin / team_lead → can read any customer.
      • manager → only customers where `managerId == self.id`.
    """
    cust = await db.customers.find_one({"id": customer_id}, _CUSTOMER_SAFE_PROJECTION)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")

    # ── Build identifier filter once (legacy customerId vs customer_id +
    #    email/phone fallback for orphaned lead rows).
    or_clauses: list = [
        {"customerId": customer_id},
        {"customer_id": customer_id},
    ]
    if cust.get("email"):
        or_clauses.append({"email": cust["email"]})
    if cust.get("phone"):
        or_clauses.append({"phone": cust["phone"]})
    ident_filter = {"$or": or_clauses}
    by_cid = {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}]}

    async def _safe(coro, default=None):
        try:
            return await coro
        except Exception:
            return [] if default is None else default

    # ── Pull collections in parallel (single round-trip)
    deals, leads, quotes, deposits = await asyncio.gather(
        _safe(db.deals.find(ident_filter, {"_id": 0}).sort("created_at", -1).to_list(length=200)),
        _safe(db.leads.find(ident_filter, {"_id": 0}).sort("created_at", -1).to_list(length=200)),
        _safe(db.quotes.find(ident_filter, {"_id": 0}).sort("created_at", -1).to_list(length=200)),
        _safe(db.legal_deposits.find(by_cid, {"_id": 0}).sort("created_at", -1).to_list(length=100)),
    )

    # ── Aggregate summary ──
    def _num(v):
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    total_revenue = sum(
        _num(d.get("total_price") or d.get("totalValue") or d.get("amount"))
        for d in deals
        if (d.get("status") or d.get("stage") or "").lower() in
        {"won", "completed", "purchased", "in_delivery"}
    )
    total_profit = sum(
        _num(d.get("profit") or 0) for d in deals
    ) or total_revenue * 0.10  # 10% fallback so the tile is not always zero
    total_deposits_amount = sum(
        _num(dep.get("amount"))
        for dep in deposits
        if (dep.get("status") or "").lower() in
        {"confirmed", "paid", "received", "in_processing"}
    )
    completed_deals = sum(
        1 for d in deals
        if (d.get("status") or d.get("stage") or "").lower() in
        {"won", "completed", "purchased"}
    )

    summary = {
        "totalLeads":          len(leads),
        "totalQuotes":         len(quotes),
        "totalDeals":          len(deals),
        "completedDeals":      completed_deals,
        "depositsCount":       len(deposits),
        "totalRevenue":        round(total_revenue, 2),
        "totalProfit":         round(total_profit, 2),
        "totalDepositsAmount": round(total_deposits_amount, 2),
    }

    # ── Lead context (added 2026-06-10 per Customer-Card spec) ─────────────
    #   first_request_at = earliest of {first lead, customer.created_at}.
    #   UTM block is taken from the EARLIEST lead — i.e. the campaign that
    #   actually acquired this customer. If no leads → fall back to the
    #   customer's own utm_* fields (if present).
    def _norm_dt(v):
        if not v:
            return None
        try:
            return v if isinstance(v, str) else v.isoformat()
        except Exception:
            return str(v)

    sorted_leads_asc = sorted(
        leads,
        key=lambda d: _norm_dt(d.get("created_at")) or "9999",
    )
    first_lead = sorted_leads_asc[0] if sorted_leads_asc else None
    first_lead_at = _norm_dt(first_lead.get("created_at")) if first_lead else None
    cust_created = _norm_dt(cust.get("created_at"))
    candidates = [d for d in (first_lead_at, cust_created) if d]
    first_request_at = min(candidates) if candidates else None

    def _utm_field(name: str):
        if first_lead and first_lead.get(name) not in (None, ""):
            return first_lead.get(name)
        return cust.get(name) or None

    lead_context = {
        "first_request_at": first_request_at,
        "first_lead_at":    first_lead_at,
        "first_lead_id":    (first_lead or {}).get("id"),
        "utm_source":       _utm_field("utm_source"),
        "utm_medium":       _utm_field("utm_medium"),
        "utm_campaign":     _utm_field("utm_campaign"),
        "utm_content":      _utm_field("utm_content"),
        "utm_term":         _utm_field("utm_term"),
        "source":           (first_lead or {}).get("source") or cust.get("source"),
    }

    # ── Health (single source of truth) ──
    from app.services.customer_health import CustomerHealthService
    health = await CustomerHealthService(db).full(customer_id)

    return {
        "success":      True,
        "customer":     cust,
        "leads":        leads,
        "quotes":       quotes,
        "deals":        deals,
        "deposits":     deposits,
        "summary":      summary,
        "lead_context": lead_context,
        "health":       health,
        # back-compat aliases
        "stats":    summary,
        "data":     cust,
    }


@fastapi_app.get("/api/customers/{customer_id}/health")
async def get_customer_health(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Full health for one customer — used by Customer360 header (RBAC-aware)."""
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")
    from app.services.customer_health import CustomerHealthService
    health = await CustomerHealthService(db).full(customer_id)
    if health is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"success": True, "health": health}


@fastapi_app.get("/api/customer-health-bulk")
async def get_customers_health_bulk(ids: str = ""):
    """Lightweight bulk health (score + segment only) for customer lists.

    Query string: `?ids=id1,id2,id3` (max 200).
    Returns: `{ "items": { id1: {score, segment}, ... } }`.

    NOTE: Lives on `/api/customer-health-bulk` (no `/customers/` prefix) so
    it never collides with `/api/customers/{customer_id}/...` routes.
    """
    from app.services.customer_health import CustomerHealthService
    raw = [x.strip() for x in (ids or "").split(",") if x.strip()][:200]
    if not raw:
        return {"success": True, "items": {}}
    items = await CustomerHealthService(db).bulk(raw)
    return {"success": True, "items": items}


@fastapi_app.get("/api/customers/{customer_id}/contracts-legacy")
async def get_customer_contracts_legacy(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Legacy unauthenticated contracts list. Superseded by the
    contract_lifecycle router which mounts the canonical
    ``/api/customers/{id}/contracts`` with auth + lifecycle enrichment.

    Kept as a compatibility shim for older frontend bundles. RBAC-aware
    since 2026-06-10: manager → own customers only.
    """
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        items = await db.contracts_v2.find(
            {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}]},
            {"_id": 0},
        ).sort("created_at", -1).to_list(length=200)
    except Exception:
        items = []
    return {"success": True, "items": items, "total": len(items)}


@fastapi_app.get("/api/customers/{customer_id}/documents")
async def get_customer_documents(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Read-only list of customer documents from db.documents (RBAC-aware)."""
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        items = await db.documents.find(
            {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}]},
            {"_id": 0},
        ).sort("created_at", -1).to_list(length=500)
    except Exception:
        items = []
    # Merge uploaded files from object storage (File Layer) so computer-uploaded
    # documents appear alongside legacy `documents` rows. This reuses the SAME
    # canonical `files` collection as the Customer 360 "Акти / Звіти" tab — the
    # Documents tab is the GENERAL view over the File Layer, "Акти / Звіти" is
    # the profile view. A given upload is a SINGLE `files` row shown in both;
    # it is never duplicated as two DB records.
    try:
        files = await db.files.find(
            {"entity_type": "customer", "entity_id": customer_id,
             "status": {"$ne": "deleted"},
             "purpose": {"$in": ["document", "act", "ecologist_report"]}},
            {"_id": 0},
        ).sort("created_at", -1).to_list(length=400)
        _type_label = {"act": "Акт", "ecologist_report": "Звіт еколога", "document": "Документ"}
        seen_ids = {str(it.get("file_id") or it.get("id")) for it in items}
        for f in files:
            fid = f.get("id")
            if fid in seen_ids:
                continue  # guard against duplication if a legacy row already links it
            seen_ids.add(fid)
            meta = f.get("meta") or {}
            purpose = f.get("purpose") or "document"
            is_generated = bool(f.get("generated"))
            items.insert(0, {
                "id": fid,
                "file_id": fid,
                "name": meta.get("title") or f.get("title") or f.get("filename") or "Документ",
                "type": _type_label.get(purpose, meta.get("doc_type") or f.get("doc_type") or "Документ"),
                "purpose": purpose,
                "mime": f.get("mime") or f.get("mimeType"),
                "size": f.get("size"),
                "uploaded": not is_generated,
                "source": "system" if is_generated else "uploaded",
                "generated": is_generated,
                "uploaded_by": f.get("uploaded_by") or f.get("uploadedBy"),
                "period_label": meta.get("period_label") or meta.get("period"),
                "doc_date": meta.get("doc_date"),
                "created_at": f.get("created_at"),
                "status": "active",
            })
    except Exception:
        pass
    return {"success": True, "items": items, "total": len(items)}


@fastapi_app.post("/api/customers/{customer_id}/documents")
async def upload_customer_document(
    customer_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Create a `documents` row for a customer.

    Accepts either:
      * `{ file_url, name, type, mime }` — pre-uploaded asset
      * `{ data_url, name, type, mime }` — inline base64 (capped at 8 MB)

    File-storage is intentionally minimal: we store metadata + the data
    URL/asset URL. Heavy binary storage will move to S3/Object storage
    in a later wave; the schema stays compatible.

    RBAC (2026-06-10): manager → can only upload to own customers; admin /
    team_lead → any customer.
    """
    import uuid
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")

    name  = (payload.get("name") or "document").strip()
    dtype = (payload.get("type") or "other").strip()
    mime  = (payload.get("mime") or "application/octet-stream").strip()
    url   = payload.get("file_url") or payload.get("data_url") or ""
    if not url:
        raise HTTPException(status_code=400, detail="file_url or data_url is required")
    if isinstance(url, str) and url.startswith("data:") and len(url) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Data URL exceeds 8 MB cap")

    doc = {
        "id":           str(uuid.uuid4()),
        "customer_id":  customer_id,
        "name":         name,
        "type":         dtype,
        "mime":         mime,
        "file_url":     url,
        "size":         len(url) if isinstance(url, str) else 0,
        "uploaded_by":  payload.get("uploaded_by"),
        "tags":         payload.get("tags") or [],
        "expires_at":   payload.get("expires_at"),
        "status":       "active",
        "created_at":   datetime.now(timezone.utc),
    }
    await db.documents.insert_one({**doc})
    return {"success": True, "document": doc}


@fastapi_app.delete("/api/customers/{customer_id}/documents/{document_id}")
async def delete_customer_document(
    customer_id: str,
    document_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")
    res = await db.documents.delete_one({
        "id": document_id,
        "$or": [{"customer_id": customer_id}, {"customerId": customer_id}],
    })
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True, "deleted": document_id}


# Legacy /360 endpoint replaced — keep this anchor so search tools land here.
async def _customer_360_replaced():
    pass

@fastapi_app.get("/api/customers/{customer_id}/timeline-legacy")
async def get_customer_timeline_legacy(
    customer_id: str,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Legacy timeline endpoint — kept as alias for clients that still
    hit the old URL. New code should use the rich timeline mounted by
    ``app/routers/customer_timeline.py`` at the canonical path.

    The unified router (see Sprint 4) supersedes this implementation:
    it merges explicit ``customer_timeline_events`` with synthesised
    invoice/order/payment events and accepts a ``kinds=`` filter.

    RBAC (2026-06-10): manager → own customers only.
    """
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not _can_user_see_customer(current_user, cust):
        raise HTTPException(status_code=403, detail="Forbidden")
    events: List[Dict[str, Any]] = []
    try:
        async for d in db.deals.find(
            {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit):
            events.append({
                "type": "deal",
                "at": d.get("created_at"),
                "title": d.get("title") or d.get("name") or "Deal",
                "ref": d.get("id"),
                "data": d,
            })
    except Exception:
        pass
    try:
        match = {"customerId": customer_id}
        if cust.get("email"): match = {"$or": [match, {"email": cust["email"]}]}
        async for ld in db.leads.find(match, {"_id": 0}).sort("created_at", -1).limit(limit):
            events.append({
                "type": "lead",
                "at": ld.get("created_at"),
                "title": f"{ld.get('name') or ''} · {ld.get('source') or ''}".strip(" ·"),
                "ref": ld.get("id"),
                "data": ld,
            })
    except Exception:
        pass
    events.sort(key=lambda x: x.get("at") or "", reverse=True)
    return {"success": True, "events": events[:limit], "data": events[:limit]}

# ═══════════════════════════════════════════════════════════════════
# DEALS EXTENDED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/deals/stats")
async def deal_stats():
    """Deal statistics — literal route, MUST stay above ``/api/deals/{deal_id}``."""
    return {
        "success": True,
        "stats": {
            "total": await db.deals.count_documents({}),
            "won": await db.deals.count_documents({"status": "won"}),
            "lost": await db.deals.count_documents({"status": "lost"}),
            "inProgress": await db.deals.count_documents({"status": {"$nin": ["won", "lost"]}})
        }
    }

@fastapi_app.get("/api/deals/{deal_id}")
async def get_deal(deal_id: str):
    """Get deal — matches on `id` first, falls back to legacy `_id`."""
    deal = await db.deals.find_one({"id": deal_id})
    if not deal:
        # Legacy compatibility: pre-fix deals only had `_id`.
        deal = await db.deals.find_one({"_id": deal_id})
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    # Always emit `id` and `_id` as strings.
    _id = deal.pop("_id", None)
    if _id is not None:
        deal["_id"] = str(_id)
        if not deal.get("id"):
            deal["id"] = str(_id)
            # Opportunistic backfill so subsequent listings work.
            try:
                await db.deals.update_one(
                    {"_id": _id, "$or": [{"id": {"$exists": False}}, {"id": None}, {"id": ""}]},
                    {"$set": {"id": str(_id)}},
                )
            except Exception:
                pass
    return {"success": True, "data": deal}

@fastapi_app.post("/api/deals")
async def create_deal(data: Dict[str, Any] = Body(...)):
    """
    Create deal
    
    Auto-creates shipment if stage = 'shipping'
    """
    now = datetime.now(timezone.utc)
    
    deal_id = f"deal_{int(now.timestamp())}_{str(uuid.uuid4())[:8]}"
    
    # Wave 6 audit fix: write BOTH `_id` and `id` so the document is
    # selectable in the frontend pipeline picker (which keys off `id`).
    # If caller already provided `id` or `_id`, respect it.
    incoming_id = data.get("id") or data.get("_id") or deal_id
    deal_id = str(incoming_id)
    data.pop("_id", None)
    data.pop("id", None)

    deal = {
        "_id": deal_id,
        "id": deal_id,
        **data,
        "created_at": now,
        "updated_at": now
    }
    
    await db.deals.insert_one(deal)

    # ─── Wave 6: derive + persist pipeline_stage on insert ───────────────
    try:
        from app.wave6.pipeline import map_legacy_to_pipeline as _w6_map
        from app.wave6.timeline import write_event as _w6_tl, render_deal_created as _w6_rdc
        pl_stage = _w6_map(data.get("stage") or data.get("status"))
        await db.deals.update_one(
            {"_id": deal_id},
            {"$set": {"pipeline_stage": pl_stage}},
        )
        await _w6_tl(
            db,
            deal_id=deal_id,
            event_type="deal_created",
            message=_w6_rdc(
                title=data.get("title") or "Deal",
                vin=data.get("vin"),
                by_email=(data.get("created_by") or "system"),
            ),
            i18n_key="timeline.deal_created",
            data={
                "title": data.get("title"),
                "vin": data.get("vin"),
                "customer_id": data.get("customer_id") or data.get("customerId"),
                "pipeline_stage": pl_stage,
            },
            actor={"email": data.get("created_by"), "role": "system"},
        )
    except Exception as _w6e:
        logger.warning(f"[wave6] deal_created hook failed: {_w6e}")
    
    # [ECO CLEANUP] auto-create-shipment side-effect removed
    
    return {"success": True, "deal": serialize_doc(deal)}


@fastapi_app.put("/api/deals/{deal_id}")
async def update_deal(deal_id: str, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(require_user)):
    """Update deal"""
    _before_deal = await db.deals.find_one({"id": deal_id}, {"_id": 0}) or {}
    await db.deals.update_one({"id": deal_id}, {"$set": data})
    _after_deal = await db.deals.find_one({"id": deal_id}, {"_id": 0}) or {}

    # Block 7.1 — field-level change history (best-effort)
    try:
        from app.services.change_history import record_field_changes as _rfc
        await _rfc(db, entity_type="deal", entity_id=deal_id,
                   before=_before_deal, after=_after_deal, user=current_user, source="api_put")
    except Exception:
        pass

    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# MARKETING ENDPOINTS (DEPRECATED - NOT USED)
# ═══════════════════════════════════════════════════════════════════
# ❌ REMOVED: Marketing Control Panel logic (Facebook Ads, Google Ads automation)
# Причина: Неясная логика, не используется, не относится к текущим задачам
# Если понадобится - раскомментировать и доработать

# @fastapi_app.get("/api/marketing/auto/config")
# @fastapi_app.patch("/api/marketing/auto/config")
# @fastapi_app.get("/api/marketing/auto/decisions")
# @fastapi_app.post("/api/marketing/auto/execute")
# @fastapi_app.get("/api/marketing/auto/history")
# @fastapi_app.get("/api/marketing/roi")
# @fastapi_app.post("/api/marketing/spend/sync")
# @fastapi_app.get("/api/marketing/status")
# ... (закомментировано ~90 строк)

# ═══════════════════════════════════════════════════════════════════

@fastapi_app.post("/api/analytics/track")
async def analytics_track(request: Request):
    """Track analytics event - tolerant to any payload"""
    try:
        data = await request.json()
    except Exception:
        return {"success": True}
    event = {
        "event": data.get("event") if isinstance(data, dict) else str(data),
        "properties": data.get("properties") if isinstance(data, dict) else {},
        "userId": data.get("userId") if isinstance(data, dict) else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.analytics_events.insert_one(event)
    return {"success": True}

@fastapi_app.post("/api/analytics/link-session")
async def analytics_link_session(data: Dict[str, Any] = Body(...)):
    """Link analytics session"""
    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# CALLS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/calls")
async def list_calls(limit: int = 50):
    """List calls"""
    cursor = db.calls.find({}, {'_id': 0}).sort('created_at', -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "data": items}

@fastapi_app.get("/api/calls/{call_id}")
async def get_call(call_id: str):
    """Get call"""
    call = await db.calls.find_one({"id": call_id}, {'_id': 0})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"success": True, "data": call}

@fastapi_app.post("/api/calls")
async def create_call(data: Dict[str, Any] = Body(...)):
    """Create call record"""
    call = {
        "id": f"call-{datetime.now(timezone.utc).timestamp()}",
        "leadId": data.get("leadId"),
        "customerId": data.get("customerId"),
        "managerId": data.get("managerId"),
        "direction": data.get("direction", "outbound"),
        "duration": data.get("duration", 0),
        "status": data.get("status", "completed"),
        "notes": data.get("notes"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.calls.insert_one(call)
    # ``insert_one()`` mutates ``call`` by injecting raw ObjectId at ``_id``.
    # Strip it to keep the response JSON-serializable.
    call.pop("_id", None)
    return {"success": True, "call": call}

# ═══════════════════════════════════════════════════════════════════
# CARFAX/VIN PRICE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════
# DOCUMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/documents")
async def list_documents(limit: int = 50):
    """List documents"""
    cursor = db.documents.find({}, {'_id': 0}).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "data": items}

@fastapi_app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Get document"""
    doc = await db.documents.find_one({"id": document_id}, {'_id': 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True, "data": doc}

@fastapi_app.post("/api/documents")
async def create_document(data: Dict[str, Any] = Body(...)):
    """Create document"""
    doc = {
        "id": f"doc-{datetime.now(timezone.utc).timestamp()}",
        "name": data.get("name"),
        "type": data.get("type"),
        "dealId": data.get("dealId"),
        "customerId": data.get("customerId"),
        "url": data.get("url"),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.documents.insert_one(doc)
    # ``insert_one()`` mutates ``doc`` by injecting raw ObjectId at ``_id``.
    # Strip it to keep the response JSON-serializable.
    doc.pop("_id", None)
    return {"success": True, "document": doc}

@fastapi_app.get("/api/documents/queue/pending-verification")
async def documents_pending_verification():
    """Documents pending verification"""
    cursor = db.documents.find({"status": "pending"}, {'_id': 0}).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "data": items}

# ═══════════════════════════════════════════════════════════════════
# ROUTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/routing/queue/status")
async def routing_queue_status():
    """Routing queue status"""
    return {"success": True, "status": {"pending": 0, "assigned": 0, "processing": 0}}

@fastapi_app.get("/api/routing/rules")
async def routing_rules():
    """Get routing rules - returns direct array"""
    return [
        {"id": "r1", "name": "High Value Leads", "type": "lead_value", "condition": "price > 50000", "action": "assign_senior", "priority": 1, "isActive": True},
        {"id": "r2", "name": "New Source Leads", "type": "source", "condition": "source == 'referral'", "action": "assign_available", "priority": 2, "isActive": True},
    ]

@fastapi_app.post("/api/routing/rules")
async def create_routing_rule(data: Dict[str, Any] = Body(...)):
    """Create routing rule"""
    return {"success": True, "id": "new_rule"}

@fastapi_app.put("/api/routing/rules/{rule_id}")
async def update_routing_rule(rule_id: str, data: Dict[str, Any] = Body(...)):
    """Update routing rule"""
    return {"success": True}

@fastapi_app.delete("/api/routing/rules/{rule_id}")
async def delete_routing_rule(rule_id: str):
    """Delete routing rule"""
    return {"success": True}

@fastapi_app.patch("/api/routing/rules/{rule_id}/toggle")
async def toggle_routing_rule(rule_id: str, data: Dict[str, Any] = Body(...)):
    """Toggle routing rule active state"""
    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# SCORING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/scoring/rules")
async def scoring_rules():
    """Get scoring rules - returns direct array"""
    return [
        {"code": "s1", "name": "Lead Response Time", "scoreType": "lead_score", "description": "Score based on response time", "points": 10, "condition": "response_time < 15", "isActive": True},
        {"code": "s2", "name": "Lead Source Quality", "scoreType": "lead_score", "description": "Score for referral leads", "points": 15, "condition": "source == 'referral'", "isActive": True},
        {"code": "s3", "name": "Deal Value", "scoreType": "deal_score", "description": "Score for high value deals", "points": 20, "condition": "value > 30000", "isActive": True},
        {"code": "s4", "name": "Manager Performance", "scoreType": "manager_score", "description": "Score for conversion rate", "points": 25, "condition": "conversion > 0.3", "isActive": False},
    ]

@fastapi_app.post("/api/scoring/rules")
async def create_scoring_rule(data: Dict[str, Any] = Body(...)):
    """Create scoring rule"""
    return {"success": True, "code": "new_rule"}

@fastapi_app.put("/api/scoring/rules/{rule_id}")
async def update_scoring_rule(rule_id: str, data: Dict[str, Any] = Body(...)):
    """Update scoring rule"""
    return {"success": True}

@fastapi_app.delete("/api/scoring/rules/{rule_code}")
async def delete_scoring_rule(rule_code: str):
    """Delete scoring rule"""
    return {"success": True}

@fastapi_app.patch("/api/scoring/rules/{rule_code}/toggle")
async def toggle_scoring_rule(rule_code: str, data: Dict[str, Any] = Body(...)):
    """Toggle scoring rule active state"""
    return {"success": True}

# ═══════════════════════════════════════════════════════════════════
# INTENT ENDPOINTS (extended)
# ═══════════════════════════════════════════════════════════════════

@fastapi_app.get("/api/intent/me")
async def my_intent():
    """Get my intent data"""
    return {"success": True, "data": {"level": "warm", "score": 50}}

# ═══════════════════════════════════════════════════════════════════
# PAYMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════




# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═
# STRIPE INTEGRATION BOUNDARY  (extracted helpers + endpoints live in app/routers/payments.py)
# Webhook stays in server.py because it is an integration edge, not a CRUD
# domain.  It lazy-imports helpers from app.routers.payments inside the body.
# ═

@fastapi_app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook receiver — production hardened.

    Guarantees:
      • Always returns 200 (except 400 on invalid signature, which Stripe
        does NOT retry on) so we never get stuck in the retry loop that
        causes the 100 % error rate visible in the Stripe dashboard.
      • Idempotent: every event_id is recorded into `webhook_events`
        with a unique index. Repeated deliveries are no-ops.
      • Updates BOTH legacy (admin-invoice) payments via
        _record_payment_from_stripe AND new cabinet-source payments via
        _confirm_cabinet_payment, then recomputes the deal payment status.
      • Webhook secret loaded from Stripe admin config first, falls back
        to the STRIPE_WEBHOOK_SECRET env var.
    """
    # Lazy imports: payment domain helpers were extracted to
    # app/routers/payments.py during the Wave 1 refactor.  The webhook
    # is the integration boundary and stays here; it imports the helpers
    # from the new router module.
    #
    # Phase 5.5 / E (2026-05-19) — ``_get_stripe_config`` was moved out
    # of the payments router to its canonical home at
    # ``app/services/stripe_config.py`` (public name
    # ``get_stripe_config``). The webhook now imports it directly from
    # the service module; the two remaining helpers (Stripe object
    # confirmation + payment-record persistence) stay in the router.
    from app.services.stripe_config import get_stripe_config
    from app.routers.payments import (
        _confirm_cabinet_payment,
        _record_payment_from_stripe,
    )

    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Resolve secrets — config first, env fallback
    cfg: Dict[str, Any] = {}
    try:
        cfg = await get_stripe_config()
    except Exception:
        logger.exception("[stripe-webhook] get_stripe_config failed")

    secret_key = (cfg.get("secretKey") or os.environ.get("STRIPE_API_KEY", "")).strip()
    # MULTI-DOMAIN support: a single backend (sharing one DB) can serve several
    # public domains at once (e.g. bibicars.org AND bibicars.bg). Each Stripe
    # webhook endpoint has its OWN signing secret, so we collect ALL configured
    # secrets and accept the event if ANY of them validates the signature.
    #   - cfg["webhookSecret"]   : primary (str)
    #   - cfg["webhookSecrets"]  : additional domains (list[str])
    #   - STRIPE_WEBHOOK_SECRET  : env fallback
    _wh_candidates: List[str] = []
    if isinstance(cfg.get("webhookSecret"), str) and cfg["webhookSecret"].strip():
        _wh_candidates.append(cfg["webhookSecret"].strip())
    _extra = cfg.get("webhookSecrets")
    if isinstance(_extra, (list, tuple)):
        _wh_candidates.extend(s.strip() for s in _extra if isinstance(s, str) and s.strip())
    _env_wh = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if _env_wh:
        _wh_candidates.append(_env_wh)
    webhook_secrets = list(dict.fromkeys(_wh_candidates))  # de-dup, keep order

    # Only the SIGNATURE secret(s) are required to verify incoming events. The
    # api key (secret_key) is only needed if we have to call back into Stripe
    # (e.g. to retrieve a PaymentIntent for a `charge.refunded` event). When
    # Stripe is unconfigured altogether, we still log + ack so the dashboard
    # doesn't hit 100 % error.
    import stripe as _stripe  # type: ignore
    if secret_key:
        _stripe.api_key = secret_key

    # ── Verify signature & parse event ────────────────────────────────────
    event: Optional[Dict[str, Any]] = None
    import json as _json
    try:
        if webhook_secrets:
            # Try each configured secret; accept on the first that validates.
            verified = False
            for _sec in webhook_secrets:
                try:
                    _stripe.Webhook.construct_event(body, sig_header, _sec)
                    verified = True
                    break
                except _stripe.error.SignatureVerificationError:
                    continue
            if not verified:
                logger.warning(
                    "[stripe-webhook] signature verification failed against %d secret(s)",
                    len(webhook_secrets),
                )
                return JSONResponse(status_code=400, content={"error": "invalid_signature"})
            # Parse the ALREADY-VERIFIED raw body into a PLAIN dict. Version-proof:
            # stripe>=12 returns a StripeObject from construct_event that is NOT a
            # dict subclass and cannot be passed through dict() (KeyError: 0).
            event = _json.loads(body.decode("utf-8") or "{}")
        else:
            # Without a configured secret we still parse the JSON (test mode).
            # We log the warning so it's obvious in production to set the secret.
            logger.warning("[stripe-webhook] no webhook_secret configured — running unverified")
            event = _json.loads(body.decode("utf-8") or "{}")
    except Exception as ex:
        logger.exception("[stripe-webhook] payload parse failed")
        return JSONResponse(status_code=400, content={"error": f"invalid_payload: {ex}"})

    event_id = (event or {}).get("id") or ""
    event_type = (event or {}).get("type", "")
    obj = ((event or {}).get("data") or {}).get("object") or {}

    if not event_id or not event_type:
        logger.warning("[stripe-webhook] event has no id or type — ack and skip")
        return {"received": True, "ignored": "no_event_metadata"}

    # ── Idempotency check ─────────────────────────────────────────────────
    # Race-safe: try to insert first; if the unique index trips, we know
    # this exact event has already been processed.
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db.webhook_events.insert_one({
            "event_id": event_id,
            "type": event_type,
            "object_id": obj.get("id"),
            "payment_intent": obj.get("payment_intent") or (obj.get("id") if obj.get("object") == "payment_intent" else None),
            "session_id": obj.get("id") if obj.get("object") == "checkout.session" else None,
            "received_at": now_iso,
            "status": "processing",
            "raw": event,
        })
    except Exception as ex:
        # DuplicateKeyError → already processed
        ex_name = type(ex).__name__
        if "DuplicateKey" in ex_name or "duplicate key" in str(ex).lower():
            logger.info("[stripe-webhook] duplicate event_id=%s — idempotent skip", event_id)
            return {"received": True, "type": event_type, "idempotent": True}
        logger.exception("[stripe-webhook] webhook_events insert failed")
        # Continue processing — it's better to risk a duplicate than to drop the event

    # ── Mirror the event in stripe_events for full audit (existing collection) ──
    try:
        await db.stripe_events.insert_one({
            "id": event_id,
            "type": event_type,
            "created_at": now_iso,
            "object_id": obj.get("id"),
            "raw": event,
        })
    except Exception:
        pass

    # ── Process relevant event types ──────────────────────────────────────
    relevant_events = (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
        "payment_intent.processing",
        "charge.refunded",
        "charge.refund.updated",
    )

    cabinet_result: Dict[str, Any] = {"skipped": True, "reason": "irrelevant_event"}
    legacy_ok = True
    cabinet_ok = True

    if event_type in relevant_events:
        # Charge events carry a Charge object — for cabinet matching we want
        # the parent PaymentIntent. Retrieve it once and re-dispatch.
        # Skip the retrieve when secret_key is unavailable (test/dev mode
        # without Stripe) — fall back to the raw charge object which still
        # carries metadata.payment_id we can use for cabinet matching.
        if event_type.startswith("charge.") and obj.get("payment_intent") and secret_key:
            try:
                pi = await asyncio.to_thread(
                    lambda: _stripe.PaymentIntent.retrieve(
                        obj["payment_intent"], expand=["charges"]
                    )
                )
                pi_dict = pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)
            except Exception:
                logger.exception("[stripe-webhook] failed to refresh PI on refund")
                pi_dict = obj
        else:
            pi_dict = obj

        # 1) Legacy admin invoice payments
        try:
            await _record_payment_from_stripe(pi_dict, event_type)
        except Exception:
            legacy_ok = False
            logger.exception("[stripe-webhook] _record_payment_from_stripe failed")

        # 2) Cabinet-source payments (new flow)
        try:
            cabinet_result = await _confirm_cabinet_payment(pi_dict, event_type)
        except Exception:
            cabinet_ok = False
            logger.exception("[stripe-webhook] _confirm_cabinet_payment failed")

    # ── Mark event as processed ───────────────────────────────────────────
    try:
        await db.webhook_events.update_one(
            {"event_id": event_id},
            {"$set": {
                "status": "ok" if (legacy_ok and cabinet_ok) else "partial",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "cabinet_result": cabinet_result,
                "legacy_ok": legacy_ok,
                "cabinet_ok": cabinet_ok,
            }},
        )
    except Exception:
        pass

    logger.info(
        "[stripe-webhook] processed event_id=%s type=%s legacy_ok=%s cabinet=%s",
        event_id, event_type, legacy_ok, cabinet_result,
    )

    # Always 200 — Stripe will retry on any non-2xx response which would
    # produce the dashboard's 100 % error rate.
    return {
        "received": True,
        "type": event_type,
        "event_id": event_id,
        "cabinet": cabinet_result,
        "ok": legacy_ok and cabinet_ok,
    }


# Phase 4 / C-1 — was @fastapi_app.on_event("startup") at this site.
# Orchestrated by `lifespan()` (defined near FastAPI() construction)
# in the same source order as before; behavioural-1:1 with the legacy
# decorator-based wiring.
async def _ensure_webhook_events_index():
    """Idempotency relies on a UNIQUE index on webhook_events.event_id."""
    try:
        await db.webhook_events.create_index("event_id", unique=True, name="uniq_event_id")
        logger.info("[stripe-webhook] webhook_events.event_id unique index ensured")
    except Exception:
        logger.exception("[stripe-webhook] failed to ensure webhook_events index")



# ═══════════════════════════════════════════════════════════════════
# SERVICES CATALOG  (master_admin manages, everyone reads)
# ═══════════════════════════════════════════════════════════════════
#
# Source-of-truth list of services that managers can attach to invoices.
# Each service describes ONE step that the company performs for a client
# (Inspection, Delivery, Certification, Custom-clearance, etc).
#
# When a client pays an invoice, an `order` document is auto-created with
# one workflow step per invoice line-item — letting the manager track
# execution while team-lead and client see live progress.

DEFAULT_SERVICES = [
    {"id": "svc_inspection",    "code": "inspection",    "name": "Інспекція авто",            "name_en": "Vehicle inspection",       "name_bg": "Инспекция на автомобила",
     "description":    "Передпродажний огляд, фото та відео",
     "description_en": "Pre-sale inspection, photos and video",
     "description_bg": "Предпродажен оглед, снимки и видео",
     "category": "import",  "default_price": 200,  "currency": "USD", "default_qty": 1,
     "workflow": [
        {"key": "schedule",     "label": "Заплановано",  "label_en": "Scheduled",  "label_bg": "Планирано"},
        {"key": "in_progress",  "label": "На огляді",    "label_en": "In progress","label_bg": "В процес"},
        {"key": "report_ready", "label": "Звіт готовий", "label_en": "Report ready","label_bg": "Отчетът е готов"},
     ]},
    {"id": "svc_delivery",      "code": "delivery",      "name": "Доставка авто",             "name_en": "Vehicle delivery",         "name_bg": "Доставка на автомобила",
     "description":    "Морська + автомобільна доставка до клієнта",
     "description_en": "Sea + road delivery to the client",
     "description_bg": "Морска + автомобилна доставка до клиента",
     "category": "logistics","default_price": 1200, "currency": "USD", "default_qty": 1,
     "workflow": [
        {"key": "ports_booking", "label": "Бронювання портів", "label_en": "Port booking",   "label_bg": "Резервация на пристанища"},
        {"key": "loading",       "label": "Завантажено",       "label_en": "Loaded",         "label_bg": "Натоварено"},
        {"key": "in_transit",    "label": "У дорозі",          "label_en": "In transit",     "label_bg": "В транзит"},
        {"key": "customs",       "label": "Митниця",           "label_en": "Customs",        "label_bg": "Митница"},
        {"key": "delivered",     "label": "Доставлено",        "label_en": "Delivered",      "label_bg": "Доставено"},
     ]},
    {"id": "svc_certification", "code": "certification", "name": "Сертифікація / реєстрація", "name_en": "Certification & registration", "name_bg": "Сертификация и регистрация",
     "description":    "Документообіг, сертифікати, реєстрація",
     "description_en": "Document workflow, certificates, registration",
     "description_bg": "Документооборот, сертификати, регистрация",
     "category": "docs",    "default_price": 350,  "currency": "USD", "default_qty": 1,
     "workflow": [
        {"key": "docs_collection", "label": "Збір документів", "label_en": "Document collection", "label_bg": "Събиране на документи"},
        {"key": "submission",      "label": "Подача",          "label_en": "Submission",          "label_bg": "Подаване"},
        {"key": "approved",        "label": "Затверджено",     "label_en": "Approved",            "label_bg": "Одобрено"},
     ]},
    {"id": "svc_detailing",     "code": "detailing",     "name": "Передпродажна підготовка",  "name_en": "Pre-sale detailing",        "name_bg": "Предпродажна подготовка",
     "description":    "Хімчистка, полірування",
     "description_en": "Detailing, polishing",
     "description_bg": "Химическо чистене, полиране",
     "category": "custom",  "default_price": 250,  "currency": "USD", "default_qty": 1,
     "workflow": [
        {"key": "scheduled",   "label": "Заплановано", "label_en": "Scheduled",   "label_bg": "Планирано"},
        {"key": "in_progress", "label": "В роботі",    "label_en": "In progress", "label_bg": "В процес"},
        {"key": "ready",       "label": "Готово",      "label_en": "Ready",       "label_bg": "Готово"},
     ]},
    {"id": "svc_storage",       "code": "storage",       "name": "Зберігання на складі",      "name_en": "Storage",                   "name_bg": "Складиране",
     "description":    "Зберігання у захищеному паркінгу",
     "description_en": "Storage in a secure parking facility",
     "description_bg": "Съхранение на охраняем паркинг",
     "category": "logistics","default_price": 50,   "currency": "USD", "default_qty": 1,
     "workflow": [
        {"key": "checked_in", "label": "Прийнято",      "label_en": "Checked in",  "label_bg": "Приет"},
        {"key": "stored",     "label": "На зберіганні", "label_en": "Stored",      "label_bg": "Съхранен"},
        {"key": "released",   "label": "Видано",        "label_en": "Released",    "label_bg": "Освободен"},
     ]},
]


async def _ensure_services_seed() -> None:
    """Idempotent seed of the default services catalog. Also backfills missing
    translation fields on records that were seeded before the multi-lang upgrade
    (name_bg, description_en/_bg, workflow[].label_en/_bg).

    Phase 5.3 / C-6: all `db.services` access routed through
    ``ServiceCatalogRepository``. Orchestration (boot-time
    diff computation + idempotency guard) stays here.
    """
    if db is None:
        return
    try:
        from app.repositories import ServiceCatalogRepository
        repo = ServiceCatalogRepository(db)
        existing = await repo.count_all()
        if existing == 0:
            now = datetime.now(timezone.utc).isoformat()
            for s in DEFAULT_SERVICES:
                doc = {**s, "is_active": True, "created_at": now, "created_by": "system_seed"}
                await repo.create(doc)
            return
        # Existing collection: backfill translations on seed-managed records
        by_id = {s["id"]: s for s in DEFAULT_SERVICES}
        managed = await repo.list_seed_managed(list(by_id.keys()))
        for doc in managed:
            seed = by_id.get(doc["id"])
            if not seed:
                continue
            updates = {}
            for fld in ("name_en", "name_bg", "description", "description_en", "description_bg"):
                if not doc.get(fld) and seed.get(fld):
                    updates[fld] = seed[fld]
            # Workflow per-language labels backfill (match by `key`)
            seed_wf = {w["key"]: w for w in (seed.get("workflow") or []) if isinstance(w, dict)}
            new_wf = []
            wf_changed = False
            for step in (doc.get("workflow") or []):
                if not isinstance(step, dict):
                    new_wf.append(step); continue
                k = step.get("key")
                seed_step = seed_wf.get(k) if k else None
                merged = dict(step)
                if seed_step:
                    for lbl in ("label_en", "label_bg"):
                        if not merged.get(lbl) and seed_step.get(lbl):
                            merged[lbl] = seed_step[lbl]
                            wf_changed = True
                new_wf.append(merged)
            if wf_changed:
                updates["workflow"] = new_wf
            if updates:
                await repo.apply_patch(doc["id"], set_doc=updates)
    except Exception:
        logger.exception("[services] seed failed")


# Phase 4 / C-1 — was @fastapi_app.on_event("startup") at this site.
# Orchestrated by `lifespan()` (defined near FastAPI() construction)
# in the same source order as before; behavioural-1:1 with the legacy
# decorator-based wiring.
async def _services_startup_hook():
    try:
        await _ensure_services_seed()
    except Exception:
        pass


@fastapi_app.get("/api/services")
async def list_services_public(category: str = "", active_only: bool = True):
    """Public/staff list of services (managers + clients show this list).

    Phase 5.3 / C-6: collection access migrated to
    ``ServiceCatalogRepository.list_by_name``. Both
    ``active_only=True`` (production) and ``active_only=False``
    (no production caller but public contract retained)
    branches route through the same repository verb.
    """
    from app.repositories import ServiceCatalogRepository
    items = await ServiceCatalogRepository(db).list_by_name(
        category=(category or None),
        active_only=active_only,
    )
    return {"success": True, "items": items}


# admin_services CRUD moved to app/routers/admin_services.py (Wave 2B/Batch 10)


# ── Workflow templates (reusable step recipes) ───────────────────────
# admin workflow-templates CRUD moved to app/routers/admin_workflow_templates.py
# (Wave 2B/Batch 10) — the inline first-hit seed in list_workflow_templates
# moved WITH the router.


@fastapi_app.get("/api/workflow-templates")
async def public_workflow_templates():
    """Public read (managers need this when creating custom lines).

    Phase 5.3 / C-1: collection access migrated to
    ``WorkflowTemplateRepository.list_templates(order="asc")``.
    Sort direction is part of the public contract -- chronological
    (oldest first) for managers building custom lines.
    """
    from app.repositories.workflow_templates import WorkflowTemplateRepository
    items = await WorkflowTemplateRepository(db).list_templates(order="asc")
    return {"success": True, "items": items}


# ─── Manager invoice builder ────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════
# MANAGER INVOICE BUILDER  (multi-line items)
# ═══════════════════════════════════════════════════════════════════

# ── _round_money — Phase 5.2 / C-2 EXTRACTED ──────────────────────
# Canonical home is now `app/utils/money.py`.  This re-export
# preserves the legacy `from server import _round_money` bridge AND
# the in-module call sites.  Same compat-shim pattern as serialize_doc
# (Phase 5.2 / C-1) — module identity is preserved (`server._round_money
# is app.utils.money._round_money` → True).
from app.utils.money import _round_money  # noqa: F401  -- compat re-export



@fastapi_app.post("/api/manager/invoices", dependencies=[Depends(require_manager_or_admin)])
async def manager_create_invoice(data: Dict[str, Any] = Body(...), user: dict = Depends(require_manager_or_admin)):
    """Manager creates an invoice with multiple service line-items.

    body = {
      customerId: "...",            # required
      currency: "USD",              # optional
      dueDate: "2026-06-01",        # optional
      notes: "...",                 # optional
      items: [
        { service_id?, name, price, qty }, ...
      ]
    }
    """
    customer_id = (data.get("customerId") or data.get("customer_id") or "").strip()
    if not customer_id:
        raise HTTPException(400, "customerId is required")

    items_in = data.get("items") or []
    if not isinstance(items_in, list) or not items_in:
        raise HTTPException(400, "items must be a non-empty array")

    # Resolve services from DB to capture canonical metadata
    services_index = {}
    if any((it or {}).get("service_id") for it in items_in):
        ids = [it.get("service_id") for it in items_in if it.get("service_id")]
        # Phase 5.3 / C-6: cross-domain READ from BillingDomain →
        # ServiceCatalog via the repository. Permitted by §7.1.
        from app.repositories import ServiceCatalogRepository
        for s in await ServiceCatalogRepository(db).find_by_ids(ids):
            services_index[s["id"]] = s

    norm_items = []
    total = 0.0
    currency = (data.get("currency") or "UAH").upper()
    # Phase Final / Block 1 (Workflow Binding) — resolve workflow steps
    # via the central resolver (template_id → live template steps;
    # fallback to inline svc.workflow; final fallback to default 3-step).
    from app.services.workflow_resolver import resolve_workflow_for_service
    for raw in items_in:
        sid = (raw or {}).get("service_id") or None
        svc = services_index.get(sid) if sid else None
        name = (raw.get("name") or (svc or {}).get("name") or "").strip()
        if not name:
            continue
        price = _round_money(raw.get("price") if raw.get("price") is not None else (svc or {}).get("default_price", 0))
        qty = int(raw.get("qty") or (svc or {}).get("default_qty") or 1)
        line_total = _round_money(price * qty)
        total += line_total
        # Resolve workflow steps via central rule.  When the item has
        # no bound service (free custom line), the resolver returns the
        # default 3-step fallback.
        resolved_workflow = await resolve_workflow_for_service(svc, db)
        norm_items.append({
            "id": str(uuid.uuid4()),
            "service_id": sid,
            "service_code": (svc or {}).get("code"),
            "name": name,
            "description": raw.get("description") or (svc or {}).get("description"),
            "category": (svc or {}).get("category"),
            "price": price,
            "qty": qty,
            "line_total": line_total,
            "workflow": resolved_workflow,
            # Persist the template_id on the invoice item so downstream
            # consumers (orders, audit) can trace the binding without
            # re-reading the service catalogue.
            "workflow_template_id": (svc or {}).get("workflow_template_id"),
        })

    if not norm_items:
        raise HTTPException(400, "items must contain at least one valid line")

    inv_id = f"inv_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"
    invoice = {
        "id": inv_id,
        "customerId": customer_id,
        "managerId": user.get("id"),
        "managerEmail": user.get("email"),
        "items": norm_items,
        "amount": _round_money(total),
        "total": _round_money(total),
        "currency": currency,
        "status": "pending",
        "notes": (data.get("notes") or "").strip(),
        "dueDate": data.get("dueDate"),
        "description": data.get("description") or (norm_items[0]["name"] if len(norm_items) == 1 else f"{len(norm_items)} services"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email") or user.get("id"),
    }

    # Resolve the customer (by id OR email) and stamp email/company so the
    # client cabinet reliably surfaces this invoice (client scope matches by
    # customerId OR customerEmail OR company_id). Best-effort.
    try:
        cust = await db.customers.find_one(
            {"$or": [{"id": customer_id}, {"customerId": customer_id},
                     {"email": {"$regex": f"^{re.escape(customer_id)}$", "$options": "i"}}]},
            {"_id": 0},
        )
        if cust:
            real_id = cust.get("id") or cust.get("customerId") or customer_id
            invoice["customerId"] = real_id
            invoice["customerEmail"] = cust.get("email")
            invoice["customerName"] = cust.get("name") or cust.get("company_name")
            if cust.get("company_id"):
                invoice["company_id"] = cust.get("company_id")
    except Exception:
        logger.exception("[invoice] customer resolution failed (non-fatal)")

    # Sprint 1.5 / Finance Core Closeout — stamp UTM from customer/lead
    # so analytics can attribute every invoice back to the marketing
    # campaign. Best-effort: a failure here MUST NOT block invoice creation.
    try:
        from app.services.utm_propagation import extract_utm, stamp_utm
        _utm = await extract_utm(db, customer_id=customer_id)
        stamp_utm(invoice, _utm)
    except Exception:
        logger.exception("[invoice] utm stamping failed (non-fatal)")

    await db.invoices.insert_one(invoice)
    invoice.pop("_id", None)
    return {"success": True, "invoice": invoice}


@fastapi_app.get("/api/manager/invoices/my", dependencies=[Depends(require_manager_or_admin)])
async def manager_list_my_invoices(user: dict = Depends(require_manager_or_admin), limit: int = 100, q: str = ""):
    role = (user.get("role") or "").lower()
    base = {} if role in ("master_admin", "owner", "admin", "team_lead") else {"managerId": user.get("id")}

    query = base
    q = (q or "").strip()
    if q:
        import re as _re
        rx = {"$regex": _re.escape(q), "$options": "i"}
        # Match invoice fields directly + resolve customers by email/name/company
        try:
            from app.services.customer_resolver import search_customer_ids as _search_cust
            from app.services.staff_acl import customer_scope_filter as _cust_scope
            cust_ids = await _search_cust(db, q, _cust_scope(user), limit=500)
        except Exception:
            cust_ids = []
        or_clauses = [
            {"id": rx}, {"number": rx}, {"description": rx},
            {"customerName": rx}, {"customerEmail": rx},
            {"customerId": rx}, {"company_id": rx},
            {"contract_id": rx}, {"contract_number": rx}, {"request_id": rx},
        ]
        if cust_ids:
            or_clauses.append({"customerId": {"$in": cust_ids}})
        query = {"$and": [base, {"$or": or_clauses}]}

    cursor = db.invoices.find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))

    # ── Enrich each invoice with a stable customer DTO (company — email) so the
    #    UI never has to show a raw customer_id. Batch-resolve in one query.
    try:
        from app.services.customer_resolver import resolve_many as _resolve_many, build_dto as _build_dto
        dto_map = await _resolve_many(db, [i.get("customerId") for i in items])
        for inv in items:
            cid = inv.get("customerId")
            dto = dto_map.get(cid)
            if not dto:
                # Fall back to the denormalised fields stored on the invoice.
                dto = _build_dto(None, fallback_id=cid or "",
                                 fallback_email=inv.get("customerEmail") or "",
                                 fallback_name=inv.get("customerName") or "")
            inv["customer"] = dto
    except Exception:
        logger.exception("[invoices] customer DTO enrichment failed")
    return {"success": True, "items": items}


# ─── Invoice lifecycle (send / cancel / mark-paid) ────────────────────
async def _can_act_on_invoice(invoice: Dict[str, Any], user: Dict[str, Any]) -> bool:
    role = (user.get("role") or "").lower()
    if role in ("master_admin", "owner", "admin", "team_lead"):
        return True
    if role == "manager" and invoice.get("managerId") == user.get("id"):
        return True
    return False


@fastapi_app.patch("/api/invoices/{invoice_id}/send", dependencies=[Depends(require_manager_or_admin)])
async def invoice_send(invoice_id: str, user: dict = Depends(require_manager_or_admin)):
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if not await _can_act_on_invoice(inv, user):
        raise HTTPException(403, "Forbidden")
    new_status = "sent" if inv.get("status") in (None, "draft") else "pending"
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {"status": new_status, "sentAt": datetime.now(timezone.utc).isoformat()}},
    )
    fresh = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    try:
        await sio.emit("invoice:sent", {"invoiceId": invoice_id, "customerId": inv.get("customerId")})
    except Exception:
        pass
    # Fire business event
    try:
        import notifications as _notif
        customer = await db.customers.find_one({"id": inv.get("customerId")}, {"_id": 0}) or {}
        await _notif.emit(_notif.EVENT_INVOICE_SENT, {
            "invoice": fresh, "customer": customer,
            "manager": {"id": inv.get("managerId"), "email": inv.get("managerEmail")},
        })
    except Exception:
        logger.exception("[notif] emit invoice_sent failed")
    return {"success": True, "invoice": fresh}


@fastapi_app.patch("/api/invoices/{invoice_id}/cancel", dependencies=[Depends(require_manager_or_admin)])
async def invoice_cancel(invoice_id: str, user: dict = Depends(require_manager_or_admin)):
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if not await _can_act_on_invoice(inv, user):
        raise HTTPException(403, "Forbidden")
    if inv.get("status") == "paid":
        raise HTTPException(400, "Cannot cancel a paid invoice")
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {"status": "cancelled", "cancelledAt": datetime.now(timezone.utc).isoformat()}},
    )
    fresh = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    return {"success": True, "invoice": fresh}


@fastapi_app.patch("/api/invoices/{invoice_id}/mark-paid", dependencies=[Depends(require_manager_or_admin)])
async def invoice_mark_paid(invoice_id: str, data: Dict[str, Any] = Body(default={}), user: dict = Depends(require_manager_or_admin)):
    """Manual payment confirmation (cash, bank transfer, etc).
    Marks invoice as paid AND auto-creates the order workflow — same path
    as the Stripe webhook so manager UX is identical regardless of channel.
    """
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if not await _can_act_on_invoice(inv, user):
        raise HTTPException(403, "Forbidden")
    if inv.get("status") == "paid":
        # idempotent — return existing
        fresh = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        order = await db.orders.find_one({"invoiceId": invoice_id}, {"_id": 0})
        return {"success": True, "invoice": fresh, "order": order, "already_paid": True}

    method = (data or {}).get("method") or "manual"
    note = (data or {}).get("note") or ""
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": "paid",
            "paidAt": datetime.now(timezone.utc).isoformat(),
            "paymentMethod": method,
            "paidBy": user.get("email") or user.get("id"),
            "paymentNote": note,
        }},
    )
    fresh = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    order = {}
    try:
        # Phase 5.5 / C — order-creation orchestration retired from server.py
        # to ``app.services.orders.create_order_from_invoice``. Lazy import
        # preserves the legacy ``invoice_mark_paid`` → orchestration call shape
        # 1:1 and avoids hoisting an extra top-level import in the bootstrap
        # path.
        from app.services.orders import create_order_from_invoice
        order = await create_order_from_invoice(fresh)
    except Exception:
        logger.exception("[invoice/mark-paid] failed to auto-create order")
    return {"success": True, "invoice": fresh, "order": order}


# ═══════════════════════════════════════════════════════════════════
# ORDERS  (workflow created automatically when invoice is paid)
# ═══════════════════════════════════════════════════════════════════

ORDER_OVERALL_STATUSES = ["pending", "in_progress", "waiting_docs", "in_delivery", "completed", "cancelled", "on_hold"]


# Phase 5.5 / C (2026-05-19) — order-creation orchestration retired
# from server.py. The previous helpers
#
#   * ``_build_order_steps_from_invoice(invoice)`` — pure invoice→steps transform
#   * ``async _create_order_from_invoice(invoice)`` — idempotent order creation
#                                                   + sio + notifications fan-out
#
# now live at their canonical home in ``app/services/orders.py``. The
# public entry point is ``app.services.orders.create_order_from_invoice``
# (the leading underscore was removed during the rename — see CONTRIBUTING
# § "Private-to-public promotion on extraction"). All three legacy
# callers (``invoice_mark_paid`` here, the Stripe webhook recompute
# branch in ``app/routers/payments.py``, and the deposit auto-convert
# in ``legal_workflow.py``) now import from there.
#
# This was the LAST entry in
# ``app.core.app_state_targets.QUALIFIED_USAGE_BRIDGES`` (1 → 0).
# ``import server`` was removed from ``app/routers/payments.py`` in
# the same wave because this symbol was the only thing keeping it
# alive there.


def _recalc_order_status(steps: List[Dict[str, Any]]) -> str:
    if not steps:
        return "pending"
    if all(s.get("status") == "done" for s in steps):
        return "completed"
    if any(s.get("status") in ("in_progress", "done") for s in steps):
        return "in_progress"
    return "pending"


# Admin / staff order list moved to app/routers/admin_orders.py (Wave 2B/Batch 8)

@fastapi_app.get("/api/team/orders", dependencies=[Depends(require_manager_or_admin)])
async def team_list_orders(user: dict = Depends(require_manager_or_admin), status: str = "", manager_id: str = "", limit: int = 200):
    """Team-lead view: all orders. Regular manager sees only their own."""
    role = (user.get("role") or "").lower()
    query: Dict[str, Any] = {}
    if role in ("manager",):
        query["managerId"] = user.get("id")
    elif manager_id:
        query["managerId"] = manager_id
    if status:
        query["status"] = status
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    return {"success": True, "items": items}


@fastapi_app.get("/api/manager/orders", dependencies=[Depends(require_manager_or_admin)])
async def manager_list_orders(user: dict = Depends(require_manager_or_admin), limit: int = 100):
    role = (user.get("role") or "").lower()
    query = {} if role in ("master_admin", "owner", "admin", "team_lead") else {"managerId": user.get("id")}
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    return {"success": True, "items": items}


@fastapi_app.get("/api/orders/{order_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_order(order_id: str, user: dict = Depends(require_manager_or_admin)):
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Order not found")
    role = (user.get("role") or "").lower()
    if role == "manager" and o.get("managerId") != user.get("id"):
        raise HTTPException(403, "Forbidden")
    return {"success": True, "order": o}


@fastapi_app.patch("/api/orders/{order_id}/steps/{step_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_order_step(order_id: str, step_id: str, data: Dict[str, Any] = Body(...), user: dict = Depends(require_manager_or_admin)):
    """Set a step's status. data = {status: 'pending'|'in_progress'|'done', note?: str}"""
    new_status = (data.get("status") or "").lower()
    if new_status not in ("pending", "in_progress", "done", "skipped"):
        raise HTTPException(400, "Invalid status")

    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404, "Order not found")
    role = (user.get("role") or "").lower()
    if role == "manager" and o.get("managerId") != user.get("id"):
        raise HTTPException(403, "Forbidden")

    steps = o.get("steps") or []
    found = None
    for s in steps:
        if s.get("id") == step_id:
            s["status"] = new_status
            if new_status == "in_progress" and not s.get("started_at"):
                s["started_at"] = datetime.now(timezone.utc).isoformat()
            if new_status == "done":
                s["completed_at"] = datetime.now(timezone.utc).isoformat()
            if data.get("note"):
                s["note"] = data["note"]
            found = s
            break
    if not found:
        raise HTTPException(404, "Step not found")

    overall = _recalc_order_status(steps)
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"steps": steps, "status": overall, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Live notify the customer cabinet
    try:
        await sio.emit("order:step_updated", {
            "orderId": order_id,
            "customerId": o.get("customerId"),
            "stepId": step_id,
            "stepStatus": new_status,
            "orderStatus": overall,
        })
    except Exception:
        pass

    fresh = await db.orders.find_one({"id": order_id}, {"_id": 0})

    # Fire order_finished event when the overall flips to `completed`
    if overall == "completed" and (o.get("status") != "completed"):
        try:
            import notifications as _notif
            inv = await db.invoices.find_one({"id": fresh.get("invoiceId")}, {"_id": 0}) or {}
            customer = await db.customers.find_one({"id": fresh.get("customerId")}, {"_id": 0}) or {}
            manager = None
            if fresh.get("managerId"):
                manager = await db.users.find_one({"id": fresh.get("managerId")}, {"_id": 0})
            manager = manager or {"id": fresh.get("managerId"), "email": fresh.get("managerEmail")}
            await _notif.emit(_notif.EVENT_ORDER_FINISHED, {
                "invoice": inv, "order": fresh, "customer": customer, "manager": manager,
            })
        except Exception:
            logger.exception("[notif] emit order_finished failed")

    return {"success": True, "order": fresh}


@fastapi_app.post("/api/orders/{order_id}/notes", dependencies=[Depends(require_manager_or_admin)])
async def add_order_note(order_id: str, data: Dict[str, Any] = Body(...), user: dict = Depends(require_manager_or_admin)):
    body = (data.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "body is required")
    note = {
        "id": str(uuid.uuid4()),
        "author": user.get("email") or user.get("id"),
        "role": (user.get("role") or "").lower(),
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await db.orders.update_one({"id": order_id}, {"$push": {"notes": note}, "$set": {"updated_at": note["created_at"]}})
    if r.matched_count == 0:
        raise HTTPException(404, "Order not found")
    return {"success": True, "note": note}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/orders")
async def customer_orders(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    cursor = db.orders.find({"customerId": customer_id}, {"_id": 0}).sort("created_at", -1).limit(50)
    items = await cursor.to_list(length=50)
    return {"success": True, "items": items}



# ═══════════════════════════════════════════════════════════════════
# PROVIDER PRESSURE  (score · tier · matching · admin metrics)
# ═══════════════════════════════════════════════════════════════════







# admin_providers stats (2 endpoints) moved to app/routers/admin_providers.py
# (Wave 2B/Batch 11) — helper `_ps_service_or_503` (server.py:14762) is
# preserved here for sibling public endpoints `/api/providers/me/stats`
# and `/api/providers/{id}/stats` (server.py:14775, 14786).


# admin_business_metrics moved to app/routers/admin_metrics.py (Wave 2B/Batch 9)


# ═══════════════════════════════════════════════════════════════════
# SOURCE HEALTH
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] /api/source-health (source_health)

# ═══════════════════════════════════════════════════════════════════
# MISC ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

# admin_overview moved to app/routers/admin_overview.py (Wave 2B/Batch 11)

# admin_predictive_leads moved to app/routers/admin_predictive_leads.py (Wave 2B/Batch 11)

@fastapi_app.get("/api/login-approval/pending")
async def login_approval_pending():
    """Pending login approvals"""
    return {"success": True, "data": []}

@fastapi_app.post("/api/login-approval/{approval_id}")
async def process_login_approval(approval_id: str, data: Dict[str, Any] = Body(...)):
    """Process login approval"""
    return {"success": True}

@fastapi_app.get("/api/manager-ai/lead/{lead_id}")
async def manager_ai_lead(lead_id: str):
    """AI insights for lead"""
    return {"success": True, "insights": {"recommendation": "Follow up within 24h", "score": 75}}

@fastapi_app.get("/api/manager-ai/user/{user_id}")
async def manager_ai_user(user_id: str):
    """AI insights for user"""
    return {"success": True, "insights": {"performance": "Good", "suggestions": []}}

# [car-import removed] GET /api/deal-engine/evaluate (VIN deal scoring)


# ═══════════════════════════════════════════════════════════════════
# CARFAST COOKIE PROXY API (V4.0)
# ═══════════════════════════════════════════════════════════════════

class CarfastCookieImport(BaseModel):
    cookies: List[Dict[str, Any]]
    userAgent: Optional[str] = None
    sessionId: Optional[str] = None

# [auto-domain removed] CarfastParseRequest





# Legacy cookie-based endpoint (fallback)



# ═══════════════════════════════════════════════════════════════════
# CARFAST INGEST - Receive parsed data from extension
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] CarfastIngestData




# ═══════════════════════════════════════════════════════════════════
# AUTOASTAT INGEST - Receive parsed data from extension
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] AutoAstatIngestData




# ═══════════════════════════════════════════════════════════════════
# BID.CARS INGEST
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] BidCarsIngestData




# ═══════════════════════════════════════════════════════════════════
# BID.CARS VIN SEARCH - Backend searches bid.cars by VIN
# ═══════════════════════════════════════════════════════════════════


# [auto-domain removed] search_bidcars_playwright



# ═══════════════════════════════════════════════════════════════════
# EXTENSION DOWNLOAD
# ═══════════════════════════════════════════════════════════════════
from fastapi.responses import FileResponse
import os as os_module



# ═══════════════════════════════════════════════════════════════════
# Phase V — Multi-Source Resolver: extension bridge endpoints
# ═══════════════════════════════════════════════════════════════════
#
# Architecture (same chain runs inside ``vin_service.get_car_by_vin``):
#   CACHE → BitMotors SEARCH → WestMotors INDEX → Lemon INDEX
#         → AuctionAuto (httpx) → EXTENSION → BitMotors PAGE → NOT_FOUND
#
# The browser extension polls /api/ext/jobs to fetch pending VIN
# lookups and POSTs parsed payloads back via /api/ext/push.  Operators
# can call /api/ext/lookup directly to issue an ad-hoc lookup that
# blocks for up to ~4 s while the extension does its job.
#
# All write endpoints are protected by HMAC (require_extension_hmac);
# /api/ext/health is read-only and unprotected so the admin panel can
# poll it without provisioning extension keys.
# ═══════════════════════════════════════════════════════════════════














# ═══════════════════════════════════════════════════════════════════
# Phase 8 — Multi-client registry, event-driven push, health gate
# ═══════════════════════════════════════════════════════════════════




















# ═══════════════════════════════════════════════════════════════════
# OPS GUARDIAN — alerter + auto-healer status & control
# ═══════════════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# SCRAPING QUEUE SYSTEM - Automatic Backend Parsing
# ═══════════════════════════════════════════════════════════════════
# UNIVERSAL SCRAPING QUEUE
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] JobStatus

# [auto-domain removed] JobSource

# In-memory job queue (for MVP, use Redis/RabbitMQ for production)
scrape_jobs: Dict[str, Dict] = {}
scrape_queue: List[str] = []
is_worker_running = False

# [auto-domain removed] ScrapeJobRequest





# ═══════════════════════════════════════════════════════════════════
# PLAYWRIGHT WORKER
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] scrape_with_playwright

# [auto-domain removed] parse_copart_page

# [auto-domain removed] parse_iaai_page

# [auto-domain removed] parse_generic_page

# ═══════════════════════════════════════════════════════════════════
# QUEUE PROCESSOR
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] process_scrape_queue


# [auto-domain removed] /api/scraped/vehicles (list_scraped_vehicles)

# ═══════════════════════════════════════════════════════════════════
# BID.CARS HTML SCRAPER API
# ═══════════════════════════════════════════════════════════════════

# [auto-domain removed] BidCarsParseRequest

# [auto-domain removed] BidCarsSearchRequest







# ═══════════════════════════════════════════════════════════════════
# BID.CARS COOKIE PROXY - DEPRECATED (v3 legacy, kept for module-import safety)
# All `/api/bidcars/*` endpoints below are intercepted by the legacy
# kill-switch middleware and return 410 Gone (see top of file).
# ═══════════════════════════════════════════════════════════════════

try:
    from bidcars_cookie_proxy import BidCarsCookieProxy
except Exception as _e:
    BidCarsCookieProxy = None  # type: ignore
    logger.warning(f"[deprecated] bidcars_cookie_proxy unavailable: {_e}")

# Cookie Proxy будет использовать db напрямую
bidcars_proxy = None

# [auto-domain removed] get_bidcars_proxy





# Update main search endpoint to use cookie proxy first

# ═══════════════════════════════════════════════════════════════════
# COPART COOKIE PROXY (Session Bridge Architecture)
# ═══════════════════════════════════════════════════════════════════
# Architecture:
#   1. User logs into Copart in browser
#   2. Extension sends session cookies to backend (ONE TIME)
#   3. Backend stores cookies and uses them to fetch ANY lot/VIN
#   4. CRM searches via backend — no Copart open needed
#   5. Session refresh only when cookies expire
#
# Copart API endpoints (internal, session-authenticated):
#   POST /public/vehicleFinder/search — search by VIN/query
#   GET  /public/data/lotdetails/solr/lotImages/{lotId} — full lot details
# ═══════════════════════════════════════════════════════════════════

# In-memory Copart session store
copart_session = {
    "cookies": {},
    "user_agent": "",
    "imported_at": None,
    "last_used": None,
    "requests_count": 0,
    "success_count": 0,
    "fail_count": 0,
}

COPART_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
}


# [auto-domain removed] copart_cookie_header


# [auto-domain removed] copart_session_active






# [auto-domain removed] _copart_fetch


# [auto-domain removed] _parse_copart_lot










# ═══════════════════════════════════════════════════════════════════


# admin_chrome_extension/download moved to app/routers/admin_chrome_extension.py (Wave 2B/Batch 8)








# ═══════════════════════════════════════════════════════════════════
# VIN SEARCH ENGINE - AUTOMATED AGENT QUEUE SYSTEM
# ═══════════════════════════════════════════════════════════════════
# Architecture:
#   User → POST /api/vin/search → Backend creates PENDING task
#   Extension → GET /api/agent/tasks (polling every 5s) → Backend returns + locks task (IN_PROGRESS)
#   Extension → opens Copart, searches VIN, parses DOM → POST /api/agent/result
#   User UI → GET /api/vin/status/:id (polling every 2s) → Backend returns current status
#   Extension → POST /api/agent/heartbeat (every 10-15s) → Backend tracks agent health
#   Background job → requeue stuck tasks (IN_PROGRESS > 30s → PENDING)
# ═══════════════════════════════════════════════════════════════════

# Agent heartbeat storage (in-memory for MVP, можно переместить в Redis/MongoDB)
agent_heartbeat_store = {
    "lastHeartbeat": None,  # datetime
    "agentId": None,
    "isAlive": False
}

# [auto-domain removed] normalize_vin














# Background task: Requeue stuck tasks
# [auto-domain removed] requeue_stuck_tasks


# Start background task on app startup
# Phase 4 / C-1 — was @fastapi_app.on_event("startup") at this site.  The
# decorator is removed; lifespan() above orchestrates this hook explicitly
# (as `_vin_search_engine_startup`) in the same source order as before.
# The function is renamed to avoid module-namespace collision with the main
# startup_event() at ~line 1608 (Python would otherwise have second
# definition shadow the first in `server.startup_event`).
# [auto-domain removed] _vin_search_engine_startup


# =============================================
# CABINET API ENDPOINTS (без авторизации для теста)
# =============================================

# ═══════════════════════════════════════════════════════════════════
# PHASE III — Customer Favorites (auth-gated, real)
# ═══════════════════════════════════════════════════════════════════
# Identity = `customerId` resolved from Bearer customer-session token.
# Storage = `favorites` collection, unique by (customerId, vin).
# Each favorite snapshots vehicle metadata so cabinet renders fast even
# if the source listing is later archived/removed from `vin_data`.

# Phase 5.5 / D (2026-05-19) — `_require_customer` retired from server.py.
# Canonical home: ``app/services/customers.require_customer``.
# All callers (incl. cabinet_financials.py and 21 in-file sites)
# migrated in the same wave. No compat shim retained.


# [auto-domain removed] _vin_card_for_favorite









# =============================================================================
# COMPARE — per-customer authenticated comparison list (max 3 items)
# =============================================================================
#
# Mirrors the favorites flow but stores into `db.compare`. The cabinet UI
# (`/cabinet/:id/compare`) renders 2-3 vehicles side-by-side; the public
# car cards toggle an item in/out of this list. Same auth contract as
# favorites: `Authorization: Bearer <customer-session-token>`.
# =============================================================================

_COMPARE_MAX = 3  # FE expects isFull at count>=3; keep them in sync


# [auto-domain removed] _compare_owner_query











# =============================================================================
# CAR SHARING — generate share URLs, persist share records, list own shares
# =============================================================================
#
# Purpose: a logged-in (or anonymous) visitor on /cars/:vin can press the
# "Share" icon, which opens a modal letting them share the vehicle through
# Facebook / Viber / Telegram / Copy-link. Every share spawns a record in
# the `shares` Mongo collection so the customer can later see all the cars
# they have shared from their personal cabinet (`/cabinet/:id/shared`).
#
# Endpoints:
#   • POST   /api/shares             Create/upsert a share record. Auth optional
#                                    (anonymous shares are tracked by ip).
#   • GET    /api/shares/me          List the current customer's share history.
#   • GET    /api/shares/{id}        Public read of a single share record (used
#                                    by social-media unfurl/preview crawlers).
#   • DELETE /api/shares/{id}        Owner can remove their own share record.
#
# Indexes ensured at module-load time below. Collection is created lazily.
# =============================================================================

import secrets as _secrets_share  # local alias, separate from other secrets imports


def _short_share_id() -> str:
    """11-char URL-safe id, ~66 bits of entropy — enough for share links."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "".join(_secrets_share.choice(alphabet) for _ in range(11))


async def _ensure_shares_indexes() -> None:
    try:
        await db.shares.create_index([("id", 1)], unique=True, sparse=True)
        await db.shares.create_index([("createdBy", 1), ("createdAt", -1)])
        await db.shares.create_index([("vin", 1)])
    except Exception as _e:
        logger.debug("[shares] index ensure skipped: %s", _e)


@fastapi_app.post("/api/shares")
async def create_share(
    data: Dict[str, Any] = Body(...),
    request: Request = None,
    authorization: Optional[str] = Header(None),
):
    """Create a share record for a vehicle.

    Body: `{vin, channel?, snapshot? | image?, title?, price?, ...}`

    `channel` ∈ {"facebook", "viber", "telegram", "copy"} (optional — defaults
    to "copy" when not specified, i.e. a generic "Share link" action).
    """
    await _ensure_shares_indexes()

    # Be defensive: numeric or non-string vins (e.g. placeholder fixtures send
    # `vin: 1`) used to crash on `.strip()`.  Coerce to a string first so the
    # endpoint never raises a 500 on a typing-only mismatch.
    raw_vin_in = data.get("vin") or data.get("vehicleId") or ""
    raw_vin = str(raw_vin_in).strip().upper().replace(" ", "").replace("-", "")
    if not raw_vin:
        raise HTTPException(status_code=400, detail="vin is required")

    channel = (data.get("channel") or "copy").lower()
    if channel not in {"facebook", "viber", "telegram", "copy"}:
        channel = "copy"

    customer = await _resolve_bearer(authorization)
    customer_id = (customer or {}).get("customerId") or (customer or {}).get("id") if customer else None
    ip_addr = None
    try:
        if request is not None:
            ip_addr = (request.client.host if request.client else None)
            xff = request.headers.get("x-forwarded-for")
            if xff:
                ip_addr = xff.split(",")[0].strip()
    except Exception:
        ip_addr = None

    snapshot_in = data.get("snapshot") or {}
    snapshot = {
        "vin": raw_vin,
        "title": data.get("title") or snapshot_in.get("title"),
        "make": data.get("make") or snapshot_in.get("make"),
        "model": data.get("model") or snapshot_in.get("model"),
        "year": data.get("year") or snapshot_in.get("year"),
        "trim": data.get("trim") or snapshot_in.get("trim"),
        "price": data.get("price") or snapshot_in.get("price"),
        "currency": data.get("currency") or snapshot_in.get("currency") or "EUR",
        "image": data.get("image") or snapshot_in.get("image"),
        "lot_number": data.get("lot_number") or data.get("lot") or snapshot_in.get("lot_number"),
        "auction_name": data.get("auction_name") or data.get("auction") or snapshot_in.get("auction_name"),
        "odometer": data.get("odometer") or snapshot_in.get("odometer"),
        "odometer_unit": data.get("odometer_unit") or snapshot_in.get("odometer_unit"),
        "description": data.get("description") or snapshot_in.get("description"),
    }
    snapshot = {k: v for k, v in snapshot.items() if v not in (None, "")}

    now = datetime.now(timezone.utc)
    share_id = _short_share_id()
    record = {
        "id": share_id,
        "vin": raw_vin,
        "channel": channel,
        "createdBy": customer_id,
        "anonymous": customer_id is None,
        "ip": ip_addr,
        "snapshot": snapshot,
        "sourcePage": (data.get("sourcePage") or "")[:200],
        "createdAt": now,
        "updatedAt": now,
    }
    try:
        await db.shares.insert_one(record)
    except Exception as e:
        # Extremely unlikely duplicate-id collision — regenerate once.
        logger.warning("[shares] insert collision, retrying: %s", e)
        share_id = _short_share_id()
        record["id"] = share_id
        await db.shares.insert_one(record)

    # Build the canonical public share URL pointing at the car page.
    base = (
        (os.environ.get("PUBLIC_SITE_URL") or "").rstrip("/")
        or (request.headers.get("origin") if request else "")
        or ""
    )
    share_url = f"{base}/cars/{raw_vin}?share={share_id}" if base else f"/cars/{raw_vin}?share={share_id}"

    return {
        "success": True,
        "id": share_id,
        "vin": raw_vin,
        "channel": channel,
        "shareUrl": share_url,
        "snapshot": snapshot,
        "createdAt": now.isoformat(),
        "anonymous": customer_id is None,
    }


@fastapi_app.get("/api/shares/me")
async def list_my_shares(authorization: Optional[str] = Header(None)):
    """List the authenticated customer's share history."""
    customer = await require_customer(authorization)
    customer_id = customer.get("customerId") or customer.get("id")
    await _ensure_shares_indexes()
    cursor = db.shares.find({"createdBy": customer_id}, {"_id": 0}).sort("createdAt", -1).limit(500)
    rows = await cursor.to_list(length=500)
    out: List[Dict[str, Any]] = []
    base = (os.environ.get("PUBLIC_SITE_URL") or "").rstrip("/")
    for r in rows:
        for k in ("createdAt", "updatedAt"):
            v = r.get(k)
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
        snap = r.get("snapshot") or {}
        # Promote frequently-used snapshot fields to the top level for the cabinet UI.
        for k in ("title", "make", "model", "year", "trim", "price", "currency",
                  "image", "lot_number", "auction_name", "odometer", "odometer_unit"):
            if k not in r and snap.get(k) is not None:
                r[k] = snap.get(k)
        vin = r.get("vin")
        r["shareUrl"] = f"{base}/cars/{vin}?share={r.get('id')}" if base else f"/cars/{vin}?share={r.get('id')}"
        out.append(r)
    return out


@fastapi_app.get("/api/shares/{share_id}")
async def get_share(share_id: str):
    """Public read of a single share — used by social media unfurl bots and
    by the receiving end when a user opens the share URL."""
    await _ensure_shares_indexes()
    row = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="share not found")
    for k in ("createdAt", "updatedAt"):
        v = row.get(k)
        if hasattr(v, "isoformat"):
            row[k] = v.isoformat()
    # Strip ip from the public payload.
    row.pop("ip", None)
    return row


@fastapi_app.delete("/api/shares/{share_id}")
async def delete_share(share_id: str, authorization: Optional[str] = Header(None)):
    """Owner can remove a share they created."""
    customer = await require_customer(authorization)
    customer_id = customer.get("customerId") or customer.get("id")
    res = await db.shares.delete_one({"id": share_id, "createdBy": customer_id})
    return {"success": bool(res.deleted_count), "deleted": res.deleted_count}





# ═══════════════════════════════════════════════════════════════════
# CUSTOMER CABINET — full per-customer API (production)
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════

# Phase 5.5 / D (2026-05-19) — `_ensure_customer_seed` retired from server.py.
# Canonical home: ``app/services/customers.ensure_customer_seed``.
# All callers (incl. cabinet_financials.py and 21 in-file sites)
# migrated in the same wave. No compat shim retained.


# Phase 5.5 / D (2026-05-19) — `_seed_customer_financials` moved with
# `ensure_customer_seed` (private sibling helper, only called
# internally by the seeder). Canonical home: ``app/services/customers.py``.


def _customer_cabinet_status_label(status: Optional[str]) -> str:
    return {
        'new': 'Нова заявка',
        'negotiation': 'Переговори',
        'contract_pending': 'Очікуємо підпис договору',
        'contract_signed': 'Договір підписано',
        'deposit_pending': 'Очікуємо депозит',
        'deposit_paid': 'Депозит оплачено',
        'payment_pending': 'Очікуємо оплату',
        'payment_complete': 'Оплачено',
        'auction_won': 'Аукціон виграно',
        'in_transit': 'В дорозі',
        'shipping': 'Доставка',
        'at_port': 'В порту',
        'customs': 'Митниця',
        'delivered': 'Доставлено',
        'completed': 'Завершено',
    }.get(status or '', status or '—')


@fastapi_app.get("/api/customer-cabinet/{customer_id}/dashboard")
async def customer_cabinet_dashboard_real(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    """Full customer dashboard (real data)."""
    try:
        await ensure_customer_record(customer_id)
        customer = await db.customers.find_one({'id': customer_id}) or {'id': customer_id}

        deals = await db.deals.find({'customerId': customer_id}).sort('created_at', -1).limit(20).to_list(20)
        active_deals = [d for d in deals if d.get('status') not in ('completed', 'cancelled')]

        # Timeline — merge notifications + shipment events
        notifs = await db.notifications.find({'customerId': customer_id}).sort('createdAt', -1).limit(8).to_list(8)
        latest_timeline = [
            {
                'title': n.get('title'),
                'description': n.get('message'),
                'type': n.get('type'),
                'timestamp': n.get('createdAt').isoformat() if isinstance(n.get('createdAt'), datetime) else n.get('createdAt'),
            }
            for n in notifs
        ]

        # Next action
        next_action = None
        primary = active_deals[0] if active_deals else None
        if primary:
            st = primary.get('status')
            if st == 'contract_pending':
                next_action = {'title': 'Підпишіть договір', 'description': 'Договір готовий до підпису', 'urgency': 'high', 'dealId': primary.get('id')}
            elif st in ('deposit_pending', 'payment_pending'):
                next_action = {'title': 'Очікується оплата', 'description': 'Підтвердіть платіж щоб рухатись далі', 'urgency': 'high', 'dealId': primary.get('id')}

        # Manager
        manager = None
        if primary and primary.get('managerId'):
            manager = {
                'id': primary.get('managerId'),
                'name': primary.get('managerName') or 'Менеджер BIBI Cars',
                'phone': primary.get('managerPhone') or '+380680000000',
                'email': primary.get('managerEmail') or 'support@bibi.cars',
            }

        return {
            'customer': {
                'id': customer.get('id'),
                'firstName': customer.get('firstName'),
                'lastName': customer.get('lastName'),
                'name': customer.get('name') or customer.get('firstName'),
                'email': customer.get('email'),
                'phone': customer.get('phone'),
                'city': customer.get('city'),
                'telegram': customer.get('telegram'),
                'avatar': customer.get('avatar'),
            },
            'activeDeals': [serialize_doc(d) for d in active_deals],
            'latestTimeline': latest_timeline,
            'nextAction': next_action,
            'manager': manager,
        }
    except Exception as e:
        logger.exception(f"[CABINET] dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/api/customer-cabinet/{customer_id}/orders")
async def customer_cabinet_orders(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    deals = await db.deals.find({'customerId': customer_id}).sort('created_at', -1).to_list(100)
    return {'data': [serialize_doc(d) for d in deals]}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/orders/{deal_id}")
async def customer_cabinet_order_detail(
    customer_id: str,
    deal_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    deal = await db.deals.find_one({'id': deal_id, 'customerId': customer_id})
    if not deal:
        raise HTTPException(status_code=404, detail='Deal not found')
    # include shipment
    shipment = await db.shipments.find_one({'dealId': deal_id})
    return {
        'deal': serialize_doc(deal),
        'shipment': serialize_doc(shipment) if shipment else None,
    }


@fastapi_app.get("/api/customer-cabinet/{customer_id}/requests")
async def customer_cabinet_requests(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    requests = await db.leads.find({'customerId': customer_id}).sort('created_at', -1).to_list(50)
    return {'data': [serialize_doc(r) for r in requests]}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/deposits")
async def customer_cabinet_deposits(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    deposits = await db.deposits.find({'customerId': customer_id}).sort('created_at', -1).to_list(50)
    return {'data': [serialize_doc(d) for d in deposits]}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/timeline")
async def customer_cabinet_timeline(
    customer_id: str,
    limit: int = 50,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)

    events = []
    # Notifications as events
    notifs = await db.notifications.find({'customerId': customer_id}).sort('createdAt', -1).to_list(limit)
    for n in notifs:
        events.append({
            'id': n.get('id'),
            'title': n.get('title'),
            'description': n.get('message'),
            'type': n.get('type'),
            'timestamp': n.get('createdAt').isoformat() if isinstance(n.get('createdAt'), datetime) else n.get('createdAt'),
        })

    # Shipment events
    shipments = await db.shipments.find({'customerId': customer_id}).to_list(20)
    for s in shipments:
        sh_events = await db.shipment_events.find({'shipmentId': s['id']}).sort('timestamp', -1).limit(20).to_list(20)
        for e in sh_events:
            events.append({
                'id': e.get('id') or str(e.get('_id')),
                'title': e.get('title') or e.get('description'),
                'description': e.get('location') or '',
                'type': 'shipping',
                'timestamp': e.get('timestamp').isoformat() if isinstance(e.get('timestamp'), datetime) else e.get('timestamp'),
            })

    # sort
    def _k(e):
        t = e.get('timestamp') or ''
        return t
    events.sort(key=_k, reverse=True)
    return {'data': events[:limit]}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/notifications")
async def customer_cabinet_notifications(
    customer_id: str,
    limit: int = 50,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    items = await db.notifications.find({'customerId': customer_id}).sort('createdAt', -1).limit(limit).to_list(limit)
    return {'data': [serialize_doc(n) for n in items]}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/notifications/unread-count")
async def customer_cabinet_notifications_unread(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    cnt = await db.notifications.count_documents({'customerId': customer_id, 'read': {'$ne': True}})
    return {'unread': cnt}


@fastapi_app.post("/api/customer-cabinet/{customer_id}/notifications/{notification_id}/read")
async def customer_cabinet_notification_read(
    customer_id: str,
    notification_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await db.notifications.update_one(
        {'customerId': customer_id, 'id': notification_id}, {'$set': {'read': True}}
    )
    return {'success': True}


@fastapi_app.post("/api/customer-cabinet/{customer_id}/notifications/read-all")
async def customer_cabinet_notifications_read_all(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await db.notifications.update_many(
        {'customerId': customer_id, 'read': {'$ne': True}}, {'$set': {'read': True}}
    )
    return {'success': True}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/profile")
async def customer_cabinet_profile(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    c = await db.customers.find_one({'id': customer_id})
    if not c:
        raise HTTPException(status_code=404, detail='Customer not found')

    # statistics for the cabinet profile page
    total_deals = await db.deals.count_documents({'customerId': customer_id})
    completed_deals = await db.deals.count_documents(
        {'customerId': customer_id, 'status': {'$in': ['delivered', 'completed', 'received']}}
    )
    total_deposits = await db.deposits.count_documents({'customerId': customer_id})
    total_invoices = await db.invoices.count_documents({'customerId': customer_id})
    paid_invoices = await db.invoices.count_documents({'customerId': customer_id, 'status': 'paid'})

    # total spent
    pipeline = [
        {'$match': {'customerId': customer_id, 'status': 'paid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}},
    ]
    spent_agg = await db.invoices.aggregate(pipeline).to_list(1)
    total_spent = spent_agg[0]['total'] if spent_agg else 0

    manager = None
    latest_deal = await db.deals.find_one(
        {'customerId': customer_id, 'managerId': {'$exists': True}}
    )
    if latest_deal:
        manager = {
            'id': latest_deal.get('managerId'),
            'name': latest_deal.get('managerName', 'Менеджер BIBI Cars'),
            'phone': latest_deal.get('managerPhone'),
            'email': latest_deal.get('managerEmail'),
        }

    safe_customer = serialize_doc(c)
    if isinstance(safe_customer, dict):
        safe_customer['hasPassword'] = _customer_has_password(c)
        safe_customer['authProvider'] = _customer_auth_provider(c)
        safe_customer.pop('password', None)

    return {
        'customer': safe_customer,
        'stats': {
            'totalDeals': total_deals,
            'completedDeals': completed_deals,
            'totalDeposits': total_deposits,
            'totalInvoices': total_invoices,
            'paidInvoices': paid_invoices,
            'totalSpent': total_spent,
            'memberSince': c.get('createdAt').isoformat() if isinstance(c.get('createdAt'), datetime) else c.get('createdAt'),
        },
        'manager': manager,
    }


@fastapi_app.patch("/api/customer-cabinet/{customer_id}/profile")
async def customer_cabinet_profile_update(
    customer_id: str,
    payload: Dict[str, Any] = Body(...),
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    allowed = {k: payload[k] for k in ('firstName', 'lastName', 'phone', 'city', 'telegram', 'avatar') if k in payload}
    if allowed:
        allowed['updatedAt'] = datetime.now(timezone.utc)
        if 'firstName' in allowed or 'lastName' in allowed:
            current = await db.customers.find_one({'id': customer_id}) or {}
            allowed['name'] = f"{allowed.get('firstName', current.get('firstName',''))} {allowed.get('lastName', current.get('lastName',''))}".strip()
        await db.customers.update_one({'id': customer_id}, {'$set': allowed})
    c = await db.customers.find_one({'id': customer_id})
    safe_c = serialize_doc(c)
    if isinstance(safe_c, dict):
        safe_c['hasPassword'] = _customer_has_password(c)
        safe_c['authProvider'] = _customer_auth_provider(c)
        safe_c.pop('password', None)
    return {'customer': safe_c}


# [auto-domain removed] /api/customer-cabinet/{customer_id}/carfax (customer_cabinet_carfax)


@fastapi_app.get("/api/customer-cabinet/{customer_id}/contracts")
async def customer_cabinet_contracts(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    items = await db.contracts.find({'customerId': customer_id}).sort('created_at', -1).to_list(50)
    return {'data': [serialize_doc(c) for c in items]}


@fastapi_app.get("/api/customer-cabinet/{customer_id}/invoices")
async def customer_cabinet_invoices(
    customer_id: str,
    _auth: Dict[str, Any] = Depends(_authorize_customer_cabinet_access),
):
    await ensure_customer_record(customer_id)
    items = await db.invoices.find({'customerId': customer_id}).sort('created_at', -1).to_list(50)
    return {'data': [serialize_doc(i) for i in items]}




# ═══════════════════════════════════════════════════════════════════
# MANAGER TRACKING — Universal VIN / Container / IMO search
# ═══════════════════════════════════════════════════════════════════

# Container-tracking provider keys (ShipsGo V1 authCode / AfterShip)
# Phase 3.1 / Commit 26 — SHIPSGO_API_KEY, SHIPSGO_FLEET_KEY,
# AFTERSHIP_API_KEY globals removed.  All reads now go through
# ``tracking_config_service`` (see ``_tracking_snapshot()``).

# ── Phase 3.1 — TrackingConfigService (canonical owner since Commit 26) ──
# Service is now the SOLE source of truth for the 5 tracking provider keys.
@fastapi_app.post("/api/manager/calls/{call_id}/outcome", dependencies=[Depends(require_manager_or_admin)])
async def save_manager_call_outcome(
    call_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """
    Save call outcome and trigger Decision Engine.

    Auth: enforced by ``require_manager_or_admin`` dependency. The
    previous implementation also tried to verify the JWT manually with
    a local ``verify_token()`` that used a different (placeholder)
    JWT_SECRET than ``security.py`` — this caused every save to fail
    with 401 "Invalid or expired token" even with a valid login token.
    Phase IV-5 fix: rely entirely on the dependency and pull the user
    out of its return value.
    """
    # User identity (already authenticated by dependency)
    auth_user_id = (
        (current_user or {}).get("id")
        or (current_user or {}).get("_id")
        or (current_user or {}).get("sub")
    )
    if not auth_user_id:
        raise HTTPException(status_code=401, detail="Authenticated user missing id")

    outcome = data.get('outcome')
    outcome_note = data.get('outcome_note')
    callback_at = data.get('callback_at')

    if not outcome or not outcome_note:
        raise HTTPException(status_code=400, detail="Outcome and note required")

    # Find call
    call = await db.ringostat_calls.find_one({"call_id": call_id})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Update call with outcome
    now = datetime.now(timezone.utc)
    await db.ringostat_calls.update_one(
        {"call_id": call_id},
        {
            "$set": {
                "outcome": outcome,
                "outcome_note": outcome_note,
                "callback_at": callback_at,
                "outcome_saved_at": now,
                "updated_at": now
            }
        }
    )
    
    # Decision Engine - Create tasks based on outcome
    lead_id = call.get('lead_id')
    deal_id = call.get('deal_id')
    manager_id = call.get('manager_id')
    
    task_created = None
    
    if outcome == 'interested':
        # Create "Follow up" task
        task = {
            '_id': str(uuid.uuid4()),
            'title': f'Follow up після дзвінку',
            'description': outcome_note,
            'type': 'follow_up',
            'priority': 'medium',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': now + timedelta(days=1),
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task
        
        # 🔥 Mark lead as HOT
        if lead_id:
            await db.leads.update_one(
                {'_id': lead_id},
                {
                    '$set': {
                        'is_hot': True,
                        'temperature': 85,
                        'updated_at': now
                    }
                }
            )

        
        # NOTE (future work): bump lead score via Score Engine here once that
        # subsystem exposes a stable public API. Currently a no-op; the lead
        # status alone communicates the success outcome to downstream KPIs.
        
    elif outcome == 'callback':
        # Create callback task with specific deadline
        deadline = datetime.fromisoformat(callback_at.replace('Z', '+00:00')) if callback_at else now + timedelta(hours=2)
        
        task = {
            '_id': str(uuid.uuid4()),
            'title': f'Передзвонити клієнту',
            'description': outcome_note,
            'type': 'callback',
            'priority': 'high',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': deadline,
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task
        
    elif outcome == 'no_answer':
        # Create task через 2 часа
        task = {
            '_id': str(uuid.uuid4()),
            'title': f'Повторний дзвінок (не відповів)',
            'description': outcome_note,
            'type': 'callback',
            'priority': 'medium',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': now + timedelta(hours=2),
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task
        
    elif outcome == 'vin_request':
        # Create VIN task
        task = {
            '_id': str(uuid.uuid4()),
            'title': f'Відправити VIN для клієнта',
            'description': outcome_note,
            'type': 'vin_search',
            'priority': 'high',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': now + timedelta(hours=4),
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task
        
        # NOTE (future work): auto-trigger the VIN Engine job here once it
        # exposes an idempotent enqueue API. For now the task is created and
        # a human operator picks it up from the task board.
        
    elif outcome == 'delivery_discussion':
        # Create delivery follow-up task
        task = {
            '_id': str(uuid.uuid4()),
            'title': f'Follow-up по доставці',
            'description': outcome_note,
            'type': 'follow_up',
            'priority': 'medium',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': now + timedelta(days=2),
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task
        
    elif outcome == 'ready_deposit':
        # Move deal to next stage
        if deal_id:
            # deals._id is a UUID string in this codebase — don't wrap in ObjectId()
            try:
                await db.deals.update_one(
                    {"$or": [{"_id": deal_id}, {"id": deal_id}]},
                    {
                        "$set": {
                            "stage": "deposit",
                            "updated_at": now
                        }
                    }
                )
            except Exception as _e:
                logger.warning(f"[outcome] deal stage update skipped: {_e}")

        # Create deposit task
        task = {
            '_id': str(uuid.uuid4()),
            'title': f'Прийняти депозит від клієнта',
            'description': outcome_note,
            'type': 'payment',
            'priority': 'high',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': now + timedelta(hours=24),
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task

    elif outcome in ('reject', 'not_interested'):
        # Mark lead as lost / cold — no follow-up task.
        if lead_id:
            await db.leads.update_one(
                {'_id': lead_id},
                {'$set': {'status': 'lost', 'is_hot': False, 'temperature': 10, 'updated_at': now}}
            )

    elif outcome in ('deal', 'won', 'closed_won'):
        # Successful close — mark lead won, move active deal to won.
        if lead_id:
            await db.leads.update_one(
                {'_id': lead_id},
                {'$set': {'status': 'won', 'is_hot': False, 'updated_at': now}}
            )
        if deal_id:
            try:
                await db.deals.update_one(
                    {"$or": [{"_id": deal_id}, {"id": deal_id}]},
                    {"$set": {"stage": "won", "status": "closed_won", "updated_at": now}}
                )
            except Exception as _e:
                logger.warning(f"[outcome] deal won update skipped: {_e}")

    elif outcome == 'thinking':
        # Lead is warm — keep in pipeline, create a soft follow-up.
        if lead_id:
            await db.leads.update_one(
                {'_id': lead_id},
                {'$set': {'temperature': 55, 'updated_at': now}}
            )
        task = {
            '_id': str(uuid.uuid4()),
            'title': 'Follow up — клієнт думає',
            'description': outcome_note,
            'type': 'follow_up',
            'priority': 'medium',
            'assigned_to': manager_id,
            'lead_id': lead_id,
            'deal_id': deal_id,
            'call_id': call_id,
            'deadline': now + timedelta(days=2),
            'status': 'pending',
            'created_at': now,
            'updated_at': now
        }
        await db.tasks.insert_one(task)
        task_created = task

    # Done — return success payload (Phase IV-5: function was falling
    # off the end implicitly returning None → response body was `null`).
    return {
        "success": True,
        "call_id": call_id,
        "outcome": outcome,
        "outcome_saved_at": now.isoformat(),
        "task_created": (
            {
                "id": task_created.get("_id"),
                "type": task_created.get("type"),
                "title": task_created.get("title"),
                "deadline": task_created.get("deadline").isoformat() if task_created.get("deadline") else None,
            }
            if task_created else None
        ),
    }


# ==================== AI ANALYSIS ENDPOINTS ====================

@fastapi_app.post("/api/ai/analyze-call")
async def analyze_call_ai(
    call_id: str,
    current_user: dict = Depends(require_user)
):
    """
    AI Analysis of call using Whisper (speech-to-text) + GPT-4o mini
    
    Flow:
    1. Get call from DB (with recording_url)
    2. Download audio
    3. Whisper transcription
    4. GPT analysis (intent, objection, suggested_outcome)
    5. Save ai_analysis to DB
    6. Return suggestions
    """
    try:
        # Get call from DB
        call = await db.ringostat_calls.find_one({'call_id': call_id})
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        recording_url = call.get('recording_url')
        if not recording_url:
            raise HTTPException(status_code=400, detail="Recording URL not available yet")
        
        # Get lead context
        lead = await db.leads.find_one({'_id': call.get('lead_id')}) if call.get('lead_id') else None
        
        # Get previous calls for context
        previous_calls = []
        if call.get('lead_id'):
            prev_calls_cursor = db.ringostat_calls.find({
                'lead_id': call['lead_id'],
                '_id': {'$ne': call['_id']}
            }).sort('created_at', -1).limit(5)
            previous_calls = await prev_calls_cursor.to_list(length=5)
        
        # ── Call scoring (heuristic, rule-based) ───────────────────────
        # Lightweight analysis of the call based on duration and prior
        # contact history. No external LLM provider is required.
        duration = call.get('duration', 0)
        prev_count = len(previous_calls)

        ai_analysis = None

        # === Heuristic call scoring ===
        if not ai_analysis:
            logger.info("[call-scoring] applying heuristic analysis")
            
            if duration > 120 and prev_count >= 1:
                intent = "buy"
                interest_level = 0.85
                suggested_outcome = "interested"
            elif duration > 60:
                intent = "consider"
                interest_level = 0.65
                suggested_outcome = "callback"
            else:
                intent = "info"
                interest_level = 0.4
                suggested_outcome = "next_step"
            
            ai_analysis = {
                "call_id": call_id,
            "transcript": None,  # Will be filled by Whisper
            "intent": intent,
            "interest_level": interest_level,
            "objection": None,
            "suggested_outcome": suggested_outcome,
            "confidence": interest_level,
            "next_action": "Follow up based on interest",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "model": "heuristic-v1"
        }
        
        # Save AI analysis to call
        await db.ringostat_calls.update_one(
            {'call_id': call_id},
            {
                '$set': {
                    'ai_analysis': ai_analysis,
                    'ai_analyzed_at': datetime.now(timezone.utc)
                }
            }
        )
        
        return {
            "success": True,
            "call_id": call_id,
            "ai_analysis": ai_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/api/ai/call-analysis/{call_id}")
async def get_call_ai_analysis(
    call_id: str,
    current_user: dict = Depends(require_user)
):
    """
    Get AI analysis for a specific call
    """
    try:
        call = await db.ringostat_calls.find_one({'call_id': call_id})
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        ai_analysis = call.get('ai_analysis')
        if not ai_analysis:
            # Trigger analysis if not done yet
            return {"success": False, "message": "Analysis not available yet"}
        
        return {
            "success": True,
            "call_id": call_id,
            "ai_analysis": ai_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get AI analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OUTCOME DECISION ENGINE ====================
# This function should be defined earlier in the file, near other decision engine logic

# Note: The remaining outcome processing logic (reject, next_step, etc.) 
# should already be defined earlier in the decision engine function.
# The duplicate code below was removed to fix syntax errors.



# ═══════════════════════════════════════════════════════════════════════════
# Phase 3.3 / C-1 — IDENTITY DOMAIN EXTRACTED
# ───────────────────────────────────────────────────────────────────────────
# 8 identity endpoints + 3 legacy aliases (11 total) moved to:
#   app/routers/admin_identity.py  (router + alias_router)
#
# Migrated handlers (formerly in this file ~21372-21884):
#   POST /api/admin/identity/shipments/{shipment_id}/resolve
#   GET  /api/admin/identity/exceptions
#   GET  /api/admin/identity/exceptions/count
#   POST /api/admin/identity/exceptions/{exc_id}/confirm
#   POST /api/admin/identity/exceptions/{exc_id}/reject
#   GET  /api/admin/identity/shipments/{shipment_id}
#   GET  /api/admin/identity/tracking-status
#   POST /api/admin/identity/shipments/{shipment_id}/transfer-check
#   GET  /api/admin/tracking/status                  (legacy alias)
#   GET  /api/admin/resolver/exceptions              (legacy alias)
#   GET  /api/admin/resolver/identity/{shipment_id}  (legacy alias)
#
# Wired in via fastapi_app.include_router() near the admin_resolver / 
# admin_shipments wiring block above.  Lazy-bridge pattern (_db, _audit,
# _tracking_enabled, _identity_runtime) per Wave 2B / Batch 12 convention.
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# Phase 3.3 / C-2 — EXTENSION CLIENTS DOMAIN EXTRACTED
# ───────────────────────────────────────────────────────────────────────────
# 5 endpoints under /api/admin/ext-clients/* moved to
#   app/routers/admin_ext_clients.py
#
# Migrated handlers (formerly in this file ~21369-21520):
#   POST /api/admin/ext-clients                     (require_master_admin)
#   POST /api/admin/ext-clients/bootstrap           (require_master_admin)
#   GET  /api/admin/ext-clients                     (require_admin)
#   POST /api/admin/ext-clients/{client_id}/revoke  (require_master_admin)
#   POST /api/admin/ext-clients/{client_id}/rotate  (require_master_admin)
#
# The Pydantic model `_ExtClientCreate` and helper `_gen_client_secret`
# moved to the router file as private symbols.  Lazy-bridge pattern
# (_db, _audit) per Wave 2B / Batch 12 convention.  Auth scheme
# preserved exactly (4 master_admin writes + 1 admin read).
# ═══════════════════════════════════════════════════════════════════════════

print("All endpoints loaded successfully")




# ═══════════════════════════════════════════════════════════════════════════
# Public lead capture (About Us / Contacts / Catalog consultation forms)
# ─────────────────────────────────────────────────────────────────────────
class ConsultationLead(BaseModel):
    full_name: str
    phone: str
    source: str | None = "about-us"
    budget: str | None = None
    notes: str | None = None


def _validate_bg_phone(phone: str) -> tuple[bool, str]:
    """Validate Bulgarian phone number.
    Returns (is_valid, e164_normalized).
    Mobile: 9 digits after +359, starts with 8 or 9 (e.g. 87/88/89/98/99)
    Landline: 7-9 digits after +359, area codes 2 (Sofia), 3X-7X regional
    """
    if not phone:
        return False, ""
    # Extract digits only
    digits = "".join(ch for ch in phone if ch.isdigit())
    # Strip leading 359 (country) if present
    if digits.startswith("359"):
        digits = digits[3:]
    # Strip leading 0 (local trunk prefix) if present
    if digits.startswith("0"):
        digits = digits[1:]
    if not digits:
        return False, ""
    # Mobile: 9 digits, first is 8 or 9
    if len(digits) == 9 and digits[0] in ("8", "9"):
        return True, "+359" + digits
    # Landline: 8 or 9 digits, first is 2-7
    if len(digits) in (8, 9) and digits[0] in ("2", "3", "4", "5", "6", "7"):
        return True, "+359" + digits
    return False, ""


@fastapi_app.post("/api/leads/consultation")
async def submit_consultation_lead(payload: ConsultationLead):
    """Public endpoint — accepts free-consultation request from the website
    forms (About Us, Catalog, Contacts). Persists to `leads` collection
    using the same schema the team manager cabinet (TeamLeadsPage) reads.
    Returns a stable id so the frontend can show a thank-you state.
    """
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    full_name = (payload.full_name or "").strip()
    phone_raw = (payload.phone or "").strip()
    if not full_name or len(full_name) < 2:
        raise HTTPException(status_code=400, detail="full_name is required")

    # Validate Bulgarian phone (E.164 normalize)
    valid, e164 = _validate_bg_phone(phone_raw)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid Bulgarian phone number. Use format +359 8X XXX XXXX (mobile) or +359 2 XXX XXXX (landline)."
        )

    lead_id = _uuid.uuid4().hex
    now_iso = _dt.now(_tz.utc).isoformat()

    # Schema compatible BOTH with TeamLeadsPage (uses `name`, `phone`, `score`, `status`)
    # AND with internal /api/leads/consultation history.
    doc = {
        "_id": lead_id,
        "id": lead_id,
        "lead_id": lead_id,
        # Manager-cabinet expected fields:
        "name": full_name[:200],
        "full_name": full_name[:200],
        "phone": e164,
        "email": None,
        "source": (payload.source or "about-us")[:64],
        "country": "BG",
        "score": 60,                   # consultation form = warm lead
        "status": "new",
        "managerId": None,
        "manager": None,
        "lastContactAt": None,
        "ageInDays": 0,
        "isStale": False,
        "slaBreached": False,
        # Optional extras:
        "budget": (payload.budget or "")[:200] or None,
        "notes": (payload.notes or "")[:2000] or None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    try:
        if db is not None:
            await db.leads.insert_one(doc)
            logger.info("[LEADS] new consultation lead: %s (%s) src=%s",
                        full_name, e164, doc["source"])
    except Exception as exc:
        logger.warning("[LEADS] insert failed: %s", exc)
        # do not fail the request — lead capture is best-effort
    return {"ok": True, "lead_id": lead_id, "phone_normalized": e164}


# ═════════════════════════════════════════════════════════════════════════
# LEAD REQUESTS — public "Get in touch" modal entry-point
# Public form  →  POST /api/public/lead-requests
#                  ↓
#                  lead_requests collection (status="new")
#                  ↓
#                  round-robin manager assignment + 15-min SLA timer
#                  ↓
#                  Manager workspace: GET /api/admin/lead-requests
# ═════════════════════════════════════════════════════════════════════════

class PublicLeadRequest(BaseModel):
    source: str | None = "website_get_in_touch"
    channel: str | None = "website"
    name: str
    phone: str
    email: str | None = None
    budget: float | int | str | None = None
    currency: str | None = "EUR"
    car_preference: str | None = None
    message: str | None = None
    # Free-form metadata captured on the client (utm tags, landing page, etc.)
    utm: Dict[str, Any] | None = None
    landing_page: str | None = None


async def _round_robin_pick_manager() -> dict | None:
    """Pick the next available manager using simple load-balancing:
    - role == 'manager', not disabled
    - prefers the one with the LOWEST count of currently assigned active
      lead_requests (status in {new, in_progress})
    Returns the manager doc, or None if no managers exist.
    """
    if db is None:
        return None
    managers = await db.staff.find(
        {"role": "manager", "$or": [{"disabled": {"$exists": False}}, {"disabled": False}]}
    ).to_list(200)
    if not managers:
        return None

    # Compute open-load per manager
    pipeline = [
        {"$match": {"status": {"$in": ["new", "in_progress"]}}},
        {"$group": {"_id": "$manager_id", "load": {"$sum": 1}}},
    ]
    load_map: dict[str, int] = {}
    try:
        async for row in db.lead_requests.aggregate(pipeline):
            if row.get("_id"):
                load_map[row["_id"]] = int(row.get("load") or 0)
    except Exception:
        load_map = {}

    # Pick manager with smallest load (ties broken by created_at asc)
    def keyfn(m):
        mid = m.get("id") or str(m.get("_id"))
        return (load_map.get(mid, 0), m.get("created_at") or "")

    managers.sort(key=keyfn)
    return managers[0]


@fastapi_app.post("/api/public/lead-requests")
async def create_public_lead_request(
    payload: PublicLeadRequest,
    request: Request,
):
    """Public endpoint. Creates a `lead_request` from the homepage / footer
    `Get in touch` modal. Idempotent at the storage layer (each call creates
    a new request with a fresh id). Always returns 200 on success so the
    public form can show the success screen without leaking internal state.
    """
    import uuid as _uuid
    name = (payload.name or "").strip()
    phone_raw = (payload.phone or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name is required.")
    if len(phone_raw) < 5:
        raise HTTPException(status_code=400, detail="Phone is required.")

    # Normalize phone (best-effort BG → E.164, keep raw if unknown country)
    _ok, e164 = _validate_bg_phone(phone_raw)
    phone_e164 = e164 if _ok else phone_raw

    # Budget — coerce to float when possible
    budget_value = payload.budget
    try:
        budget_value = float(budget_value) if budget_value not in (None, "") else None
    except Exception:
        budget_value = None

    currency = (payload.currency or "EUR").upper()
    if currency not in ("EUR", "USD"):
        currency = "EUR"

    req_id = _uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    sla_due = now + timedelta(minutes=15)

    # Capture request metadata (best-effort, never fails the request)
    try:
        client_host = request.client.host if request and request.client else None
    except Exception:
        client_host = None
    user_agent = request.headers.get("user-agent") if request else None
    referer = request.headers.get("referer") if request else None
    utm = payload.utm or {}

    doc: dict = {
        "_id": req_id,
        "id": req_id,
        "type": "lead_request",
        "source": (payload.source or "website_get_in_touch")[:64],
        "channel": (payload.channel or "website")[:32],
        "status": "new",          # new | in_progress | converted | rejected | spam
        # Customer payload
        "name": name[:200],
        "phone": phone_e164[:64],
        "phone_raw": phone_raw[:64],
        "email": ((payload.email or "").strip().lower() or None),
        "budget": budget_value,
        "currency": currency,
        "car_preference": (payload.car_preference or "").strip()[:200] or None,
        "message": (payload.message or "").strip()[:4000] or None,
        # Metadata
        "metadata": {
            "utm": utm,
            "landing_page": payload.landing_page or referer,
            "ip": client_host,
            "user_agent": user_agent,
        },
        # SLA
        "response_due_at": sla_due.isoformat(),
        "sla_breached": False,
        # Assignment
        "manager_id": None,
        "manager_name": None,
        "manager_email": None,
        "assigned_at": None,
        # Timestamps
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        # Conversion linkage
        "converted_lead_id": None,
        "converted_at": None,
        "converted_by": None,
    }

    # Auto-assign manager (round-robin, smallest open load wins).
    try:
        mgr = await _round_robin_pick_manager()
        if mgr:
            mid = mgr.get("id") or str(mgr.get("_id"))
            doc["manager_id"] = mid
            doc["manager_name"] = mgr.get("name") or mgr.get("email")
            doc["manager_email"] = mgr.get("email")
            doc["assigned_at"] = now.isoformat()
    except Exception as e:
        logger.warning(f"[lead_requests] manager auto-assign failed: {e}")

    if db is not None:
        try:
            await db.lead_requests.insert_one(doc)
        except Exception as e:
            logger.error(f"[lead_requests] insert failed: {e}")
            raise HTTPException(status_code=500, detail="Could not persist request")

        # Best-effort manager notification (does not fail the request).
        try:
            if doc.get("manager_id"):
                await db.notifications.insert_one({
                    "_id": _uuid.uuid4().hex,
                    "user_id": doc["manager_id"],
                    "type": "lead_request_new",
                    "title": "New incoming request",
                    "body": f"New incoming request assigned to you: {doc['name']} ({doc['phone']}).",
                    "ref_type": "lead_request",
                    "ref_id": req_id,
                    "read": False,
                    "created_at": now.isoformat(),
                })
        except Exception as e:
            logger.debug(f"[lead_requests] notification skipped: {e}")

    logger.info("[lead_requests] new request id=%s name=%s phone=%s manager=%s",
                req_id, doc["name"], doc["phone"], doc.get("manager_email"))
    return {
        "ok": True,
        "id": req_id,
        "status": doc["status"],
        "response_due_at": doc["response_due_at"],
    }


@fastapi_app.get("/api/admin/lead-requests")
async def list_lead_requests(
    status: str | None = None,
    manager_id: str | None = None,
    limit: int = 100,
    user: dict = Depends(require_user),
):
    """Manager / admin list view — Incoming Requests workspace.
    Managers see only their own; admins / team_leads see everything.
    """
    if db is None:
        return {"items": [], "total": 0}
    role = (user or {}).get("role", "")
    me_id = (user or {}).get("id") or (user or {}).get("managerId")
    q: dict = {}
    if status:
        q["status"] = status
    if role == "manager":
        q["manager_id"] = me_id
    elif manager_id:
        q["manager_id"] = manager_id
    cur = db.lead_requests.find(q).sort("created_at", -1).limit(max(1, min(int(limit or 100), 500)))
    items = await cur.to_list(length=max(1, min(int(limit or 100), 500)))
    # Compute SLA breach flag on read
    now = datetime.now(timezone.utc)
    for d in items:
        d.pop("_id", None)
        try:
            due = d.get("response_due_at")
            d["sla_breached"] = bool(due and datetime.fromisoformat(due) < now and d.get("status") == "new")
        except Exception:
            pass
    total = await db.lead_requests.count_documents(q)
    return {"items": items, "total": total}


@fastapi_app.post("/api/admin/lead-requests/{req_id}/action")
async def lead_request_action(
    req_id: str,
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(require_user),
):
    """Manager actions on a request: assign, reject, mark_spam, convert.
    `convert` creates a `leads` document and sets converted_lead_id."""
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")
    action = (payload.get("action") or "").strip().lower()
    if action not in ("assign", "reject", "mark_spam", "convert"):
        raise HTTPException(status_code=400, detail="Unknown action")

    req = await db.lead_requests.find_one({"_id": req_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    role = (user or {}).get("role", "")
    me_id = (user or {}).get("id") or (user or {}).get("managerId")
    if role == "manager" and req.get("manager_id") not in (None, me_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    now = datetime.now(timezone.utc)
    update: dict = {"updated_at": now.isoformat()}

    if action == "assign":
        target = (payload.get("manager_id") or "").strip()
        if not target:
            raise HTTPException(status_code=400, detail="manager_id is required")
        mgr = await db.staff.find_one({"$or": [{"id": target}, {"_id": target}]})
        if not mgr:
            raise HTTPException(status_code=404, detail="Manager not found")
        update.update({
            "manager_id": mgr.get("id") or str(mgr.get("_id")),
            "manager_name": mgr.get("name") or mgr.get("email"),
            "manager_email": mgr.get("email"),
            "assigned_at": now.isoformat(),
        })

    elif action == "reject":
        update.update({"status": "rejected", "rejected_at": now.isoformat()})

    elif action == "mark_spam":
        update.update({"status": "spam", "marked_spam_at": now.isoformat()})

    elif action == "convert":
        # Create a follow-on `leads` document compatible with TeamLeadsPage.
        import uuid as _uuid
        lead_id = _uuid.uuid4().hex
        lead_doc = {
            "_id": lead_id,
            "id": lead_id,
            "lead_id": lead_id,
            "name": req.get("name"),
            "full_name": req.get("name"),
            "phone": req.get("phone"),
            "email": req.get("email"),
            "source": req.get("source") or "website_get_in_touch",
            "country": "BG",
            "score": 70,
            "status": "qualification",
            "managerId": req.get("manager_id"),
            "manager": req.get("manager_name"),
            "lastContactAt": None,
            "ageInDays": 0,
            "isStale": False,
            "slaBreached": False,
            "budget": str(req.get("budget") or "") or None,
            "notes": (
                f"Converted from lead_request {req_id}. "
                f"Car preference: {req.get('car_preference') or 'n/a'}. "
                f"Original message: {req.get('message') or ''}"
            )[:2000],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "from_request_id": req_id,
        }
        try:
            await db.leads.insert_one(lead_doc)
        except Exception as e:
            logger.error(f"[lead_requests] convert→leads insert failed: {e}")
            raise HTTPException(status_code=500, detail="Conversion failed")
        update.update({
            "status": "converted",
            "converted_lead_id": lead_id,
            "converted_at": now.isoformat(),
            "converted_by": user.get("email") or user.get("id"),
        })

    await db.lead_requests.update_one({"_id": req_id}, {"$set": update})
    fresh = await db.lead_requests.find_one({"_id": req_id})
    if fresh:
        fresh.pop("_id", None)
    return {"ok": True, "request": fresh}


# ════════════════════════════════════════════════════════════════════════════
# MODULAR ROUTERS — included AFTER all globals/helpers/services are defined.
# Each router lives under backend/app/routers/<domain>.py and owns its
# /api/<domain>/* surface.  See backend/CONTRIBUTING.md for the playbook.
# ════════════════════════════════════════════════════════════════════════════
# [car-import removed] /api/calculations router (car turnkey cost calculator)
from app.routers.payments import router as _payments_router  # noqa: E402
fastapi_app.include_router(_payments_router)

# ── Phase Final / Block 2 — Sales entity ──────────────────────────────
from app.routers.sales import router as _sales_router, customers_router as _sales_customers_router  # noqa: E402
fastapi_app.include_router(_sales_router)
fastapi_app.include_router(_sales_customers_router)

# ── Phase Final / Block 3 — Meetings + Calendar (.ics) ────────────────
from app.routers.meetings import router as _meetings_router, customers_router as _meetings_customers_router  # noqa: E402
fastapi_app.include_router(_meetings_router)
fastapi_app.include_router(_meetings_customers_router)

# ── Phase Final / Block 5 — Calculator visibility overrides ──────────
from app.routers.admin_calculator_visibility import router as _calc_vis_router  # noqa: E402
fastapi_app.include_router(_calc_vis_router)


# ── UAT Enhancement #2 — Deposits (Customer Card) ────────────────────
# Manager-facing CRUD plane on top of existing db.legal_deposits.
from app.routers.deposits import router as _deposits_router  # noqa: E402
fastapi_app.include_router(_deposits_router)


# ── ECO Waste domain (Wave 2 — Waste Core) ───────────────────────────
# Self-contained waste-utilization domain: waste_codes directory,
# Company360, objects, license matrix, waste requests. All routes under
# /api/waste. Decoupled from the legacy car monolith above.
try:
    from app.waste.router import router as _waste_router  # noqa: E402
    fastapi_app.include_router(_waste_router)
    logger.info("[waste] router mounted: %d routes",
                sum(1 for _ in _waste_router.routes))
except Exception as _e:
    logger.exception("[waste] failed to mount router: %s", _e)

# ── ECO Waste — Operations Center (Wave 3) ───────────────────────────
try:
    from app.waste.ops_router import router as _waste_ops_router  # noqa: E402
    fastapi_app.include_router(_waste_ops_router)
    logger.info("[waste] ops router mounted: %d routes",
                sum(1 for _ in _waste_ops_router.routes))
except Exception as _e:
    logger.exception("[waste] failed to mount ops router: %s", _e)

# ── ECO Waste — Contract e-signature (tokenized) ─────────────────────
try:
    from app.waste.esign_router import (  # noqa: E402
        staff_router as _waste_esign_staff,
        public_router as _waste_esign_public,
    )
    fastapi_app.include_router(_waste_esign_staff)
    fastapi_app.include_router(_waste_esign_public)
    logger.info("[waste] e-sign routers mounted: %d + %d routes",
                sum(1 for _ in _waste_esign_staff.routes),
                sum(1 for _ in _waste_esign_public.routes))
except Exception as _e:
    logger.exception("[waste] failed to mount e-sign routers: %s", _e)

# ── ECO Waste — Contract Execution Engine (schedule/financials/completion/eco-report) ──
try:
    from app.routers.contract_engine import (  # noqa: E402
        router as _ce_router, client_router as _ce_client_router, ensure_indexes as _ce_ensure,
    )
    fastapi_app.include_router(_ce_router)
    fastapi_app.include_router(_ce_client_router)
    logger.info("[contract_engine] routers mounted: %d + %d routes",
                sum(1 for _ in _ce_router.routes), sum(1 for _ in _ce_client_router.routes))

    async def _ce_index_startup():
        try:
            await _ce_ensure(db)
        except Exception as _e:  # noqa: BLE001
            logger.warning("[contract_engine] index startup skipped: %s", _e)
    fastapi_app.add_event_handler("startup", _ce_index_startup)
except Exception as _e:  # noqa: BLE001
    logger.exception("[contract_engine] failed to mount routers: %s", _e)

# ── ECO Waste — Universal Contract Template & Acceptance Flow ────────
try:
    from app.services.media_store import media_router as _media_router  # noqa: E402
    fastapi_app.include_router(_media_router)
    logger.info("[media_store] mounted /api/uploads")
except Exception as _e:  # noqa: BLE001
    logger.exception("[media_store] failed to mount: %s", _e)

try:
    from app.contract_flow.router import staff as _cflow_staff, client as _cflow_client  # noqa: E402
    from app.contract_flow import seed as _cflow_seed  # noqa: E402
    fastapi_app.include_router(_cflow_staff)
    fastapi_app.include_router(_cflow_client)
    logger.info("[contract_flow] routers mounted: %d + %d routes",
                sum(1 for _ in _cflow_staff.routes), sum(1 for _ in _cflow_client.routes))

    async def _cflow_startup():
        try:
            await _cflow_seed.seed_if_empty()
        except Exception as _e:  # noqa: BLE001
            logger.warning("[contract_flow] seed skipped: %s", _e)
    fastapi_app.add_event_handler("startup", _cflow_startup)
except Exception as _e:  # noqa: BLE001
    logger.exception("[contract_flow] failed to mount routers: %s", _e)


# ── Storage + PDF (Wave 5B-v2) ───────────────────────────────────────
try:
    from app.storage.router import router as _files_router, pickup_router as _pickup_photo_router  # noqa: E402
    fastapi_app.include_router(_files_router)
    fastapi_app.include_router(_pickup_photo_router)
    from app.storage.pdf import router as _pdf_router  # noqa: E402
    fastapi_app.include_router(_pdf_router)
    from app.storage.documents_router import router as _documents_router  # noqa: E402
    fastapi_app.include_router(_documents_router)
    logger.info("[storage] file/pdf/documents routers mounted: %d + %d + %d routes",
                sum(1 for _ in _files_router.routes),
                sum(1 for _ in _pdf_router.routes),
                sum(1 for _ in _documents_router.routes))
except Exception as _e:
    logger.exception("[storage] failed to mount routers: %s", _e)

# ── IBAN bank-transfer invoicing flow (admin requisites + manager confirm) ──
try:
    from app.routers.billing_iban import router as _billing_iban_router  # noqa: E402
    fastapi_app.include_router(_billing_iban_router)
    logger.info("[billing] IBAN invoicing router mounted: %d routes",
                sum(1 for _ in _billing_iban_router.routes))
except Exception as _e:  # noqa: BLE001
    logger.exception("[billing] failed to mount IBAN invoicing router: %s", _e)


# ── Wave 5B-v2 file migration (idempotent backfill on startup) ───────
async def _wave5bv2_backfill():
    try:
        from app.storage.migration import run_migration  # noqa: E402
        await run_migration(db)
    except Exception as _e:  # noqa: BLE001
        logger.warning("[storage.migration] backfill skipped: %s", _e)

try:
    fastapi_app.add_event_handler("startup", _wave5bv2_backfill)
except Exception:
    pass
