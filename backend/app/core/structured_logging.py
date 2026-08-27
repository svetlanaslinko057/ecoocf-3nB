"""
Phase 4 / C-3 — Structured JSON logging (additive envelope).
=============================================================

PURPOSE
-------
Add a parallel structured-JSON log stream WITHOUT touching any
existing log message, logger name, formatter, or stderr/stdout
output that the team already greps / debugs against.

DESIGN INVARIANTS (per user mandate)
------------------------------------
1.  Existing stderr / stdout human-readable lines remain
    **byte-identical** to the pre-C-3 baseline.
    → grep / `tail -F /var/log/supervisor/backend.err.log` workflow
       unchanged.
2.  No existing log message text is rewritten.
3.  No existing logger name is renamed.
4.  No existing handler is replaced or removed.
5.  No existing `extra={...}` payload is renormalised.
6.  No audit-schema field is touched.
7.  No business handler is modified.
8.  No ELK / OpenTelemetry migration.

The structured layer is therefore ADDITIVE-ONLY:
  · ONE new `logging.Handler` (a `WatchedFileHandler` writing JSONL
    to `BIBI_STRUCTURED_LOG_PATH`) is attached to the root logger.
  · It uses `StructuredFormatter` which serialises each `LogRecord`
    to a single-line JSON dict, augmented with whatever ContextVar
    values are currently bound at emission time.
  · Existing handlers continue to render the same human-readable
    text to the same streams as before.

CONTEXT FIELDS
--------------
Bound via Python `contextvars.ContextVar` so they propagate
naturally through `await` boundaries without explicit threading:

  request_id          – per-HTTP-request UUID (HTTP middleware)
  correlation_id      – per-trace UUID; read from `X-Correlation-ID`
                         header if present, else mirrored from
                         request_id (HTTP middleware)
  worker_name         – name of the currently supervised worker
                         (set by worker_registry._supervise)
  restart_count       – number of restarts the current worker has
                         seen (worker_registry._supervise)
  event_id            – opt-in field for domain events that want
                         to thread their event_id through downstream
                         logs.  Default unset; populated only by
                         explicit `bind_event(...)` callers.
  lifecycle_stage     – application lifecycle phase:
                          "boot" → "starting" → "running" →
                          "draining" → "stopped"
                         Set by `lifespan()` transitions and worker
                         registry stop_all.

Any ContextVar that has not been bound at emission time is OMITTED
from the JSON envelope (no nulls, no empty strings) to keep the
record schema "presence-is-truth".

EXTRA-FIELD MERGING
-------------------
Anything passed as `logger.info("msg", extra={...})` is also merged
into the JSON envelope (under their own keys at the top level — same
behaviour as the stdlib `LogRecord` would do via `record.__dict__`).
This is how `drain_duration_ms` gets in without changing the log
text — see `worker_registry.stop_all`.

THREAD- / TASK-SAFETY
---------------------
ContextVars are coroutine-local (Python 3.7+); each request /
worker / event-handler sees its own copy, so concurrent requests
or workers never leak IDs into each other's logs.

IDEMPOTENCY
-----------
`attach_structured_handler()` is guarded against double-install
(it stores a marker attribute on the root logger).  Safe to call
from any startup site without coordination.
"""
from __future__ import annotations

import contextvars
import json
import logging
import logging.handlers
import os
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional


# ─────────────────────────────────────────────────────────────────
# ContextVars
# ─────────────────────────────────────────────────────────────────
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bibi_request_id", default=None,
)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bibi_correlation_id", default=None,
)
worker_name_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bibi_worker_name", default=None,
)
restart_count_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "bibi_restart_count", default=None,
)
event_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bibi_event_id", default=None,
)
# Per-task ContextVar OVERRIDE for lifecycle_stage.  Default `None`
# means "fall back to the module-level `_LIFECYCLE_STAGE` below".
# This is used by `bind_worker(..., lifecycle_stage=...)` when a
# worker wants to label its records with its own stage (e.g.
# "running" while the global process state has moved on to
# "draining").
lifecycle_stage_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bibi_lifecycle_stage", default=None,
)

# Module-level process state — set by `set_lifecycle_stage(...)`.
# This is NOT a ContextVar because the lifecycle phase is a property
# of the process, not of a request or task.  Using a ContextVar would
# cause request handlers (spawned as separate asyncio tasks that
# snapshot the lifespan task's context at creation time) to see a
# stale stage even after the lifespan transitioned to "running".
_LIFECYCLE_STAGE: str = "boot"


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def new_request_id() -> str:
    """Compact 32-char hex UUID, suitable for log correlation."""
    return uuid.uuid4().hex


def set_lifecycle_stage(stage: str) -> None:
    """Set the global process lifecycle stage for subsequent log records.

    Valid values (loose convention): "boot", "starting", "running",
    "draining", "stopped".  No enforcement — this is purely metadata
    for the JSON layer.

    Implementation note: writes a module-level variable (NOT a
    ContextVar) so the value is visible to all tasks immediately,
    including HTTP request tasks that were spawned before the
    transition.  A per-task `lifecycle_stage_var` ContextVar override
    is still respected when set by `bind_worker(..., lifecycle_stage=...)`.
    """
    global _LIFECYCLE_STAGE
    _LIFECYCLE_STAGE = stage


def get_lifecycle_stage() -> str:
    """Return the effective lifecycle stage for the current task.

    Resolution order:
      1. Per-task ContextVar override (if `bind_worker(...,
         lifecycle_stage=...)` set one).
      2. Module-level process state (`_LIFECYCLE_STAGE`).
    """
    override = lifecycle_stage_var.get()
    if override is not None:
        return override
    return _LIFECYCLE_STAGE


@contextmanager
def bind_request(request_id: str, correlation_id: Optional[str] = None) -> Iterator[None]:
    """Bind a request-scoped (request_id, correlation_id) pair.

    Falls back to mirroring request_id into correlation_id when no
    inbound `X-Correlation-ID` header was supplied.
    """
    t1 = request_id_var.set(request_id)
    t2 = correlation_id_var.set(correlation_id or request_id)
    try:
        yield
    finally:
        request_id_var.reset(t1)
        correlation_id_var.reset(t2)


@contextmanager
def bind_worker(name: str, *, restart_count: int = 0,
                lifecycle_stage: Optional[str] = None) -> Iterator[None]:
    """Bind worker context (name + restart count) for the duration
    of a single supervised iteration.

    Used by `worker_registry._supervise` around each loop iteration so
    every log line emitted by the worker coroutine carries its name.
    """
    t1 = worker_name_var.set(name)
    t2 = restart_count_var.set(restart_count)
    t3 = lifecycle_stage_var.set(lifecycle_stage) if lifecycle_stage else None
    try:
        yield
    finally:
        worker_name_var.reset(t1)
        restart_count_var.reset(t2)
        if t3 is not None:
            lifecycle_stage_var.reset(t3)


@contextmanager
def bind_event(event_id: str) -> Iterator[None]:
    """Opt-in helper for downstream event-emitting code that wants
    to thread an event_id through nested log lines.

    Existing emit sites do NOT need to adopt this — the field is
    omitted from the JSON envelope when unbound (no schema breakage).
    """
    t1 = event_id_var.set(event_id)
    try:
        yield
    finally:
        event_id_var.reset(t1)


# ─────────────────────────────────────────────────────────────────
# Formatter
# ─────────────────────────────────────────────────────────────────
# Standard LogRecord attributes — we DON'T re-emit these as top-level
# JSON keys (they're served by `record.getMessage()` etc).  Anything
# else in record.__dict__ is an `extra=...` payload from the caller
# and is merged at top level.
_RESERVED_LOGRECORD_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


class StructuredFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single-line JSON object.

    Output shape (keys absent when their ContextVar is unbound):

        {
          "ts": "2026-05-18T12:34:56.789Z",
          "level": "INFO",
          "logger": "bibi-v3.2",
          "msg": "[STARTUP] ✓ app.state mirror set (db, mongo_client)",
          "request_id":     "...",       # if bound
          "correlation_id": "...",       # if bound
          "worker_name":    "...",       # if bound
          "restart_count":  N,           # if bound
          "event_id":       "...",       # if bound
          "lifecycle_stage":"running",   # default "boot"
          ...                              # any keys from extra={...}
          "exc_info": "Traceback (most recent call last)..."  # on errors
        }
    """

    # ISO-8601 UTC with millisecond precision and a trailing 'Z'.
    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:  # noqa: D401, N802
        # Use time.gmtime for UTC. record.created is seconds since epoch.
        msec = int((record.created - int(record.created)) * 1000)
        gm = time.gmtime(record.created)
        base = time.strftime("%Y-%m-%dT%H:%M:%S", gm)
        return f"{base}.{msec:03d}Z"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # ── ContextVar injections (only when bound) ──
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        cid = correlation_id_var.get()
        if cid:
            payload["correlation_id"] = cid
        wn = worker_name_var.get()
        if wn:
            payload["worker_name"] = wn
        rc = restart_count_var.get()
        if rc is not None:
            payload["restart_count"] = rc
        eid = event_id_var.get()
        if eid:
            payload["event_id"] = eid
        ls = get_lifecycle_stage()
        if ls:
            payload["lifecycle_stage"] = ls

        # ── Pass-through `extra={...}` from caller ──
        for k, v in record.__dict__.items():
            if k in _RESERVED_LOGRECORD_ATTRS or k in payload:
                continue
            if k.startswith("_"):
                continue
            try:
                # only keep JSON-serialisable scalars / containers
                json.dumps(v)
            except (TypeError, ValueError):
                v = repr(v)
            payload[k] = v

        # ── Exception info if present ──
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


# ─────────────────────────────────────────────────────────────────
# Handler installation (idempotent)
# ─────────────────────────────────────────────────────────────────
_HANDLER_MARKER = "_bibi_structured_handler_installed"
DEFAULT_STRUCTURED_LOG_PATH = "/var/log/supervisor/backend.structured.jsonl"


class _BibiNamespaceFilter(logging.Filter):
    """Only let ``bibi*`` loggers (and `uvicorn.access`) into the
    JSON layer.

    Why: we set the JSON handler to DEBUG to capture fine-grained
    structured context (e.g. the per-request middleware marker), but
    we do NOT want to flood the JSONL feed with DEBUG output from
    `motor`, `asyncio`, `uvicorn.error`, `httpx`, etc.  This filter
    is the minimal scope guard.

    Note on name matching: the codebase mixes two logger-name
    conventions — `bibi-v3.2` (legacy, dash separator) and
    `bibi.worker_registry`, `bibi.security`, etc. (modern, dot
    separator).  A simple ``name.startswith("bibi")`` covers both.
    Records at WARNING+ from ANY logger always pass through so we
    never lose third-party error visibility.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        # WARNING+ always passes (so we never lose third-party errors).
        if record.levelno >= logging.WARNING:
            return True
        name = record.name or ""
        return name.startswith("bibi") or name == "uvicorn.access" or name.startswith("uvicorn.access.")


def attach_structured_handler(
    path: Optional[str] = None,
    *,
    level: int = logging.DEBUG,
) -> Optional[logging.Handler]:
    """Attach a JSON-formatted log handler to the root logger.

    Idempotent: safe to call multiple times — second + calls are
    no-ops.  Returns the handler instance on first install, ``None``
    on subsequent calls.

    Parameters
    ----------
    path : optional override for the output file.  Defaults to the
        env var ``BIBI_STRUCTURED_LOG_PATH`` if set, else
        ``/var/log/supervisor/backend.structured.jsonl``.
    level : log level threshold for the JSON layer (default DEBUG —
        scoped to `bibi*` loggers via ``_BibiNamespaceFilter``).
    """
    root = logging.getLogger()
    if getattr(root, _HANDLER_MARKER, False):
        return None

    log_path = (
        path
        or os.environ.get("BIBI_STRUCTURED_LOG_PATH")
        or DEFAULT_STRUCTURED_LOG_PATH
    )
    # Ensure parent dir exists; if we can't write there, fall back
    # to stderr so we never lose visibility on the structured layer.
    handler: logging.Handler
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        handler = logging.handlers.WatchedFileHandler(log_path, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler(sys.stderr)

    handler.setLevel(level)
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(_BibiNamespaceFilter())
    # Tag so we can identify it later if someone introspects root.handlers.
    handler.name = "bibi-structured-jsonl"
    # ── byte-identical invariant for the existing stderr stream ──
    # If we lower the root logger threshold to DEBUG (needed so
    # bibi-debug records reach our handler), any sibling root handler
    # whose level is NOTSET (0) would suddenly start emitting DEBUG
    # too — which would visibly change stderr.  Pin those siblings to
    # INFO before we touch the root level.  This is the minimal,
    # surgical guard required to keep the stderr stream byte-identical
    # to the pre-C-3 baseline.
    for h in root.handlers:
        if h is handler:
            continue
        if h.level == 0 or h.level == logging.NOTSET:
            h.setLevel(logging.INFO)
    root.addHandler(handler)
    if root.level == 0 or root.level > level:
        root.setLevel(level)
    setattr(root, _HANDLER_MARKER, True)
    return handler


__all__ = [
    # ContextVars (low-level access)
    "request_id_var",
    "correlation_id_var",
    "worker_name_var",
    "restart_count_var",
    "event_id_var",
    "lifecycle_stage_var",
    # Helpers
    "new_request_id",
    "set_lifecycle_stage",
    "get_lifecycle_stage",
    "bind_request",
    "bind_worker",
    "bind_event",
    # Formatter / handler
    "StructuredFormatter",
    "attach_structured_handler",
    "DEFAULT_STRUCTURED_LOG_PATH",
]
