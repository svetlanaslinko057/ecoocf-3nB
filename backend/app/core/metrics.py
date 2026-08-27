"""
Phase 4 / C-4 — Prometheus metrics (additive observability layer).
==================================================================

PURPOSE
-------
Expose runtime state as Prometheus metrics on a single, isolated,
non-invasive endpoint (``/metrics``) without changing any existing
log message, business handler, middleware ordering, worker
semantic, or OpenAPI surface.

DESIGN INVARIANTS (per user mandate)
------------------------------------
1.  Metrics READ from runtime state — they NEVER mutate it.
2.  Metrics layer lives parallel to (not mixed with) the C-3 JSON
    structured-logging layer.
3.  ``/metrics`` is fully isolated: it does not touch any of the
    618 business routes; it is excluded from the OpenAPI schema
    (``include_in_schema=False``) so the 618/679 freeze invariant
    stays intact.
4.  No tracing / OpenTelemetry integration in this batch.
5.  No change to existing logger, middleware, or handler.

WHAT THIS MODULE DECLARES (matches user mandate exactly)
--------------------------------------------------------
Required:
    worker_restart_total            (Counter, label=name)
    worker_active_instances         (Gauge,   label=name)
    worker_drain_duration_ms        (Histogram)
    worker_uptime_seconds           (Gauge,   label=name)
    http_requests_total             (Counter, labels=method, route, status_code)
    http_request_duration_seconds   (Histogram, labels=method, route)
    openapi_paths_total             (Gauge)
    openapi_operations_total        (Gauge)
    startup_total                   (Counter)
    graceful_shutdown_total         (Counter)
    process_lifecycle_stage         (Gauge,   label=stage)   ← bonus: C-3 stage as gauge for completeness

Optional (declared but populated only when underlying integration
hooks exist; absent samples are silently 0 — Prometheus considers
that a healthy null):
    mongo_operation_duration_seconds  (Histogram, labels=op)
    socketio_emit_total               (Counter,   label=event)

REGISTRY
--------
We use a DEDICATED ``CollectorRegistry()`` rather than the default
process-global one.  Reasons:

  * keeps our metrics namespace cleanly partitioned from any
    library that may already use the default registry (e.g.
    third-party SDKs in this codebase);
  * import-time idempotency: re-importing this module under
    uvicorn's WatchFiles reloader would raise
    ``ValueError: Duplicated timeseries`` on the default registry;
    our dedicated registry is freshly constructed each import.

  Trade-off: the standard ``ProcessCollector`` /
  ``PlatformCollector`` (which expose ``process_cpu_seconds_total``
  etc.) are NOT auto-installed in a custom registry.  We re-attach
  them explicitly — they are essential for any operator dashboard
  and adding them is non-invasive.

RUNTIME-LATE FACTS
------------------
Some sources of truth (OpenAPI surface size; current
``worker_active_instances`` per name) are not stable at module
import time — they are populated as the application boots.  We
provide explicit ``set_openapi_surface(...)`` and
``record_worker_state(...)`` mutators that the boot orchestrator
calls when the corresponding fact becomes known.
"""
from __future__ import annotations

import time
from typing import Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_client import ProcessCollector, PlatformCollector


# ─────────────────────────────────────────────────────────────────
# Dedicated registry (clean namespace)
# ─────────────────────────────────────────────────────────────────
registry: CollectorRegistry = CollectorRegistry(auto_describe=True)

# Re-attach process + platform collectors to our dedicated registry
# so /metrics still includes the standard process_cpu_seconds_total,
# process_resident_memory_bytes, python_info, etc.
try:
    ProcessCollector(registry=registry)
except Exception:
    pass
try:
    PlatformCollector(registry=registry)
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────
# Worker metrics  (canonical sources of truth: worker_registry)
# ─────────────────────────────────────────────────────────────────
worker_restart_total = Counter(
    "worker_restart_total",
    "Number of times each supervised worker has been restarted by the worker_registry "
    "(monotonic; resets only on process restart).",
    labelnames=("name",),
    registry=registry,
)

worker_active_instances = Gauge(
    "worker_active_instances",
    "Current number of running instances of each worker name (1 = healthy, 0 = stopped/crashed). "
    "Phase 3.4 invariant: every registered worker MUST be == 1 while the process is alive.",
    labelnames=("name",),
    registry=registry,
)

worker_uptime_seconds = Gauge(
    "worker_uptime_seconds",
    "Wall-clock seconds since the current worker instance started running. "
    "Recomputed on scrape; 0 if the worker is not currently running.",
    labelnames=("name",),
    registry=registry,
)

worker_drain_duration_ms = Histogram(
    "worker_drain_duration_ms",
    "Histogram of worker_registry.stop_all() drain durations in milliseconds.",
    buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000),
    registry=registry,
)


# ─────────────────────────────────────────────────────────────────
# HTTP metrics  (populated by Phase 4 / C-4 metrics middleware)
# ─────────────────────────────────────────────────────────────────
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests handled by the FastAPI app, by method/route/status.",
    labelnames=("method", "route", "status_code"),
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Wall-clock request handling latency in seconds, observed inside the C-4 metrics middleware.",
    labelnames=("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)


# ─────────────────────────────────────────────────────────────────
# OpenAPI freeze gauges  (Phase 2 → Phase 3.4 invariant 618/679)
# ─────────────────────────────────────────────────────────────────
openapi_paths_total = Gauge(
    "openapi_paths_total",
    "Number of unique paths exposed by the FastAPI OpenAPI schema. Phase 3.4 freeze: 618.",
    registry=registry,
)

openapi_operations_total = Gauge(
    "openapi_operations_total",
    "Number of operations (method+path tuples) exposed by the FastAPI OpenAPI schema. Phase 3.4 freeze: 679.",
    registry=registry,
)


# ─────────────────────────────────────────────────────────────────
# Lifecycle counters
# ─────────────────────────────────────────────────────────────────
startup_total = Counter(
    "startup_total",
    "Number of times the lifespan startup hook has completed cleanly since process start.",
    registry=registry,
)

graceful_shutdown_total = Counter(
    "graceful_shutdown_total",
    "Number of times the lifespan shutdown hook has completed cleanly (drained=N timed_out=0).",
    registry=registry,
)

process_lifecycle_stage = Gauge(
    "process_lifecycle_stage",
    "Current process lifecycle stage (boot/starting/running/draining/stopped) as a one-hot gauge.",
    labelnames=("stage",),
    registry=registry,
)
# Initialise all known stages at 0 so they appear in /metrics from
# scrape #1 (one-hot pattern: exactly one stage at 1.0 at any time).
for _stage in ("boot", "starting", "running", "draining", "stopped"):
    process_lifecycle_stage.labels(stage=_stage).set(0)


# ─────────────────────────────────────────────────────────────────
# Optional metrics  (declared, populated only when integrations adopt)
# ─────────────────────────────────────────────────────────────────
mongo_operation_duration_seconds = Histogram(
    "mongo_operation_duration_seconds",
    "Latency of Mongo operations in seconds (opt-in; populated only "
    "when call-sites wrap their motor calls with `record_mongo_op(...)`).",
    labelnames=("op",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

socketio_emit_total = Counter(
    "socketio_emit_total",
    "Number of Socket.IO events emitted by the server (opt-in; populated "
    "only when call-sites adopt `record_socketio_emit(...)`).",
    labelnames=("event",),
    registry=registry,
)


# ─────────────────────────────────────────────────────────────────
# Mutators (called by the boot orchestrator + worker_registry)
# ─────────────────────────────────────────────────────────────────
def set_openapi_surface(paths_count: int, operations_count: int) -> None:
    """Snapshot the OpenAPI surface size into gauges.

    Called once at lifespan startup (after all routers are wired)
    by the boot orchestrator.  The freeze invariant is 618/679 —
    Phase 4 / C-5 will pin this as a CI assertion.
    """
    openapi_paths_total.set(paths_count)
    openapi_operations_total.set(operations_count)


def record_worker_state(name: str, *, running: bool,
                        restarts: int, started_at: Optional[float]) -> None:
    """Refresh worker-related gauges and counters for a single name.

    Idempotent: safe to call from any code path that observes a
    state change in ``worker_registry``.  ``worker_restart_total``
    is monotonic — we set it to ``restarts`` (not increment) so
    re-scrapes of an idle worker remain correct.
    """
    worker_active_instances.labels(name=name).set(1 if running else 0)
    # Counter exposes _value as MutableValue we can re-seed.  Using
    # `inc(restarts - cur)` would race with concurrent increments,
    # but in our usage workers only have a single supervisor task —
    # this is single-writer.
    cur = 0
    try:
        cur = worker_restart_total.labels(name=name)._value.get()  # type: ignore[attr-defined]
    except Exception:
        cur = 0
    delta = max(0, int(restarts) - int(cur))
    if delta:
        worker_restart_total.labels(name=name).inc(delta)
    if running and started_at:
        worker_uptime_seconds.labels(name=name).set(max(0.0, time.time() - started_at))
    else:
        worker_uptime_seconds.labels(name=name).set(0.0)


def observe_drain_duration_ms(duration_ms: float) -> None:
    """Record one drain-duration sample (called by stop_all)."""
    worker_drain_duration_ms.observe(max(0.0, float(duration_ms)))


# ─────────────────────────────────────────────────────────────────
# Lifecycle helpers
# ─────────────────────────────────────────────────────────────────
def set_lifecycle_stage(stage: str) -> None:
    """One-hot update of process_lifecycle_stage gauge.

    Mirrors `structured_logging.set_lifecycle_stage(...)` for the
    metrics layer.  Safe to call from anywhere — invalid stages are
    silently registered as a new label (Prometheus accepts that).
    """
    known = ("boot", "starting", "running", "draining", "stopped")
    for s in known:
        process_lifecycle_stage.labels(stage=s).set(1 if s == stage else 0)
    if stage not in known:
        process_lifecycle_stage.labels(stage=stage).set(1)


def inc_startup() -> None:
    startup_total.inc()


def inc_graceful_shutdown() -> None:
    graceful_shutdown_total.inc()


# ─────────────────────────────────────────────────────────────────
# Opt-in mongo / socketio helpers (provided for future adoption)
# ─────────────────────────────────────────────────────────────────
class _MongoOpTimer:
    """Context manager: ``with record_mongo_op('find_one'): ...``"""
    __slots__ = ("op", "_t0")

    def __init__(self, op: str) -> None:
        self.op = op
        self._t0 = 0.0

    def __enter__(self) -> "_MongoOpTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_exc) -> None:
        try:
            mongo_operation_duration_seconds.labels(op=self.op).observe(
                max(0.0, time.perf_counter() - self._t0)
            )
        except Exception:
            pass


def record_mongo_op(op: str) -> _MongoOpTimer:
    """Opt-in latency timer for a Mongo operation."""
    return _MongoOpTimer(op)


def record_socketio_emit(event: str) -> None:
    """Opt-in counter bump for a Socket.IO emit (call sites adopt incrementally)."""
    try:
        socketio_emit_total.labels(event=event).inc()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
# Exposition
# ─────────────────────────────────────────────────────────────────
def render_metrics() -> bytes:
    """Serialise the dedicated registry into Prometheus text format."""
    return generate_latest(registry)


METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST


__all__ = [
    "registry",
    # required metrics
    "worker_restart_total",
    "worker_active_instances",
    "worker_uptime_seconds",
    "worker_drain_duration_ms",
    "http_requests_total",
    "http_request_duration_seconds",
    "openapi_paths_total",
    "openapi_operations_total",
    "startup_total",
    "graceful_shutdown_total",
    "process_lifecycle_stage",
    # optional metrics
    "mongo_operation_duration_seconds",
    "socketio_emit_total",
    # mutators
    "set_openapi_surface",
    "record_worker_state",
    "observe_drain_duration_ms",
    "set_lifecycle_stage",
    "inc_startup",
    "inc_graceful_shutdown",
    "record_mongo_op",
    "record_socketio_emit",
    # exposition
    "render_metrics",
    "METRICS_CONTENT_TYPE",
]
