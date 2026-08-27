"""
WorkerRegistry — supervised lifecycle for long-running async workers
=====================================================================

Phase 3.4 / C-1 — Skeleton + first worker migration.

Goal
----
Replace the scattered ``asyncio.create_task(some_loop())`` calls in
``server.py`` with a centralised registry that knows about every
background worker, can start / stop them in a controlled order,
captures their crashes, and surfaces their state to /admin/health.

What this module does NOT do (out of scope for C-1):
  * No lifespan rewrite (still called from ``@on_event("startup")``).
  * No ``app.state`` migration (registry is a module-level singleton).
  * No Prometheus / structured logging (Phase 4 scope).
  * No worker queue / job dispatch (this is for *long-running* loops,
    not one-shot fire-and-forget tasks like ``_log_public_search``).

Migration discipline (Wave-2B / Phase-3.2 style)
------------------------------------------------
For each worker we migrate:
  1. Locate the existing ``asyncio.create_task(worker_loop())`` call.
  2. REMOVE that call.
  3. REGISTER the same coro_factory through ``worker_registry.register(...)``.
  4. Call ``await worker_registry.start_all()`` at the end of startup
     orchestration (the registry only starts workers that have not yet
     been started — so multiple ``start_all()`` calls are idempotent).
  5. Invariant: total worker count = number_registered + number_legacy.
     If any number diverges, the duplicate-worker invariant is broken.

For C-1 only ``ringostat_cron_loop`` is migrated.  The other 6
long-running loops (`_payment_reminder_loop`, `_watchlist_live_poll_loop`,
`tracking_worker_loop`, `resolver_worker_loop`, `transfer_detector_loop`,
`ops_guardian_loop`) stay on the legacy path until subsequent C-N
checkpoints.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Literal, Optional


logger = logging.getLogger("bibi.worker_registry")


# ─────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────
RestartPolicy = Literal["on_failure", "always", "never"]
WorkerState = Literal["registered", "starting", "running", "crashed", "stopped"]

CoroFactory = Callable[[], Awaitable[None]]


@dataclass
class WorkerSpec:
    """Static description of a long-running worker."""

    name: str
    coro_factory: CoroFactory
    restart_policy: RestartPolicy = "on_failure"
    critical: bool = False  # if True, failure is logged at ERROR; else WARNING
    restart_backoff_sec: float = 5.0
    max_restarts: Optional[int] = None  # None = unlimited
    # ── Mutable runtime state (kept here for status() simplicity) ──
    state: WorkerState = "registered"
    restarts: int = 0
    last_error: Optional[str] = None
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    def to_status_dict(self) -> Dict[str, Any]:
        now = time.time()
        running_duration_sec: Optional[float] = None
        if self.state == "running" and self.started_at is not None:
            running_duration_sec = round(now - self.started_at, 3)
        return {
            "name": self.name,
            "state": self.state,
            "restart_policy": self.restart_policy,
            "critical": self.critical,
            "restarts": self.restarts,
            "max_restarts": self.max_restarts,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "running_duration_sec": running_duration_sec,
            "running": self.state == "running"
                      and self._task is not None
                      and not self._task.done(),
        }


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────
class WorkerRegistry:
    """Module-level singleton; one per backend process."""

    def __init__(self) -> None:
        self._workers: Dict[str, WorkerSpec] = {}
        self._lock = asyncio.Lock()

    # ── Registration ──────────────────────────────────────────
    def register(
        self,
        name: str,
        coro_factory: CoroFactory,
        *,
        restart_policy: RestartPolicy = "on_failure",
        critical: bool = False,
        restart_backoff_sec: float = 5.0,
        max_restarts: Optional[int] = None,
    ) -> WorkerSpec:
        """Register a worker (does NOT start it).

        Idempotent on name — re-registering replaces the spec **only if
        the worker is not currently running**.  Trying to re-register a
        running worker raises ``ValueError`` — this protects against the
        ``duplicate workers`` invariant (Phase 3.4 mandate).
        """
        existing = self._workers.get(name)
        if existing is not None and existing.state in ("starting", "running"):
            raise ValueError(
                f"Worker {name!r} is already registered and "
                f"{existing.state}. Stop it before re-registering."
            )

        # ── [AUTO-DOMAIN REMOVED — Wave 1 cleanup] ───────────────────────
        # The car-import domain (catalogue scraping, VIN enrichment, ocean
        # shipment tracking, multi-source resolving, transfer detection) is
        # being removed in favour of the waste-utilization domain. We
        # neutralise those workers at the single registration choke-point so
        # we don't have to surgically edit every scattered registration site
        # in the 28k-line monolith. They are still *registered* (so any
        # start()/status() callers keep working) but run a no-op coroutine
        # that exits immediately and never restarts.
        _AUTO_DOMAIN_WORKERS = {
            "watchlist_live_poll",
            "tracking_worker",
            "resolver_worker",
            "transfer_detector",
            "enrichment_worker",
            "catalog_promotion",
            "catalog_promotion_worker",
            "westmotors_sync",
            "lemon_sync",
        }
        if name in _AUTO_DOMAIN_WORKERS:
            async def _noop_disabled_worker() -> None:
                return None
            coro_factory = _noop_disabled_worker
            restart_policy = "never"
            logger.info(
                "[worker_registry] worker %s DISABLED (auto-domain removed) — "
                "registered as no-op", name,
            )

        spec = WorkerSpec(
            name=name,
            coro_factory=coro_factory,
            restart_policy=restart_policy,
            critical=critical,
            restart_backoff_sec=restart_backoff_sec,
            max_restarts=max_restarts,
        )
        self._workers[name] = spec
        logger.info(
            "[worker_registry] registered name=%s policy=%s critical=%s",
            name, restart_policy, critical,
        )
        return spec

    def names(self) -> List[str]:
        return sorted(self._workers.keys())

    def get(self, name: str) -> Optional[WorkerSpec]:
        return self._workers.get(name)

    # ── Lifecycle ─────────────────────────────────────────────
    async def start(self, name: str) -> None:
        """Start a single worker by name.  Idempotent — if already
        running, this is a no-op (logs at DEBUG)."""
        async with self._lock:
            spec = self._workers.get(name)
            if spec is None:
                raise KeyError(f"Worker {name!r} is not registered")
            if spec._task is not None and not spec._task.done():
                logger.debug("[worker_registry] start(%s): already running", name)
                return
            self._launch_supervised(spec)

    async def start_all(self) -> None:
        """Start every registered worker that is not already running.

        Idempotent: calling twice does not create duplicate tasks.

        Emits a per-worker ``active_instances=N`` invariant assertion
        log after launch — this is the canonical line operators / CI
        smoke checks should grep for to detect duplicate workers.
        Emitted to BOTH logger.info AND stdout (via print) so it
        survives any log-handler reconfiguration.
        """
        async with self._lock:
            for spec in self._workers.values():
                if spec._task is not None and not spec._task.done():
                    continue
                self._launch_supervised(spec)
        # Per-worker invariant assertion lines (operator-grep target).
        # We emit on BOTH channels because the `bibi.worker_registry`
        # logger namespace can be silenced by uvicorn's handler config.
        for spec in self._workers.values():
            count = self.count_active(spec.name)
            line = (
                f"[worker_registry] {spec.name} active_instances={count} "
                f"state={spec.state} policy={spec.restart_policy}"
            )
            logger.info(line)
            print(line, flush=True)
        names = ", ".join(self.names())
        summary = f"[worker_registry] start_all complete — workers: [{names}]"
        logger.info(summary)
        print(summary, flush=True)
        # Phase 4 / C-4 — mirror per-worker state into Prometheus gauges
        # at start_all completion.  Read-only effect on metrics; the
        # `/metrics` endpoint refreshes these again at scrape time.
        try:
            from app.core import metrics as _m4
            for spec in self._workers.values():
                _m4.record_worker_state(
                    spec.name,
                    running=(spec._task is not None and not spec._task.done()),
                    restarts=int(spec.restarts),
                    started_at=spec.started_at,
                )
        except Exception:
            pass

    def count_active(self, name: str) -> int:
        """Return the count of live tasks for a registered worker name.

        Used by the ``active_instances=N`` invariant assertion. Anything
        other than ``0`` (not yet started) or ``1`` (registry-owned)
        indicates the duplicate-worker invariant has been violated.
        """
        spec = self._workers.get(name)
        if spec is None or spec._task is None:
            return 0
        return 0 if spec._task.done() else 1

    async def stop(self, name: str, *, grace_period_sec: float = 5.0) -> None:
        """Cancel + await a single worker."""
        async with self._lock:
            spec = self._workers.get(name)
            if spec is None or spec._task is None:
                return
            await self._cancel_and_await(spec, grace_period_sec)

    async def stop_all(self, *, grace_period_sec: float = 5.0) -> None:
        """Cancel all running workers, awaiting their graceful shutdown.

        Emits a per-worker drain confirmation to stdout — this is the
        canonical line operators / CI smoke checks should grep for to
        verify clean shutdown semantics (no pending task warnings).
        """
        # Phase 4 / C-3 — additive timing capture for the JSON envelope.
        # The summary log line below stays byte-identical in stderr;
        # `drain_duration_ms` rides along only inside `extra={...}` so
        # the structured-JSON formatter picks it up at top level.
        _stop_all_t0 = time.time()
        drained: list[str] = []
        timed_out: list[str] = []
        async with self._lock:
            tasks: List[asyncio.Task] = []
            tracked: List[WorkerSpec] = []
            for spec in self._workers.values():
                if spec._task is not None and not spec._task.done():
                    spec._task.cancel()
                    tasks.append(spec._task)
                    tracked.append(spec)
                    spec.state = "stopped"
                    spec.stopped_at = time.time()
            if tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=grace_period_sec,
                    )
                    drained = [s.name for s in tracked]
                except asyncio.TimeoutError:
                    for s, t in zip(tracked, tasks):
                        if t.done():
                            drained.append(s.name)
                        else:
                            timed_out.append(s.name)
                    logger.warning(
                        "[worker_registry] stop_all: timeout after %.1fs — "
                        "%d workers did not finish in time: %s",
                        grace_period_sec, len(timed_out), timed_out,
                    )
        # Per-worker drain confirmation (operator-grep target)
        for name in drained:
            line = f"[worker_registry] {name} drained_cleanly=true"
            logger.info(line, extra={"worker_name": name, "drained_cleanly": True})
            print(line, flush=True)
        for name in timed_out:
            line = f"[worker_registry] {name} drained_cleanly=false reason=timeout"
            logger.warning(line, extra={"worker_name": name, "drained_cleanly": False,
                                        "drain_failure_reason": "timeout"})
            print(line, flush=True)
        drain_duration_ms = int((time.time() - _stop_all_t0) * 1000)
        # Phase 4 / C-4 — record drain duration in Prometheus histogram.
        # Read-only effect on metrics layer; never mutates registry state.
        try:
            from app.core import metrics as _m4
            _m4.observe_drain_duration_ms(drain_duration_ms)
            # Mirror per-worker state to gauges: all drained workers are
            # now stopped (active_instances=0); per-worker restart count
            # is monotonic and refreshed at /metrics scrape time too.
            for _spec in self._workers.values():
                _m4.record_worker_state(
                    _spec.name,
                    running=False,
                    restarts=int(_spec.restarts),
                    started_at=_spec.started_at,
                )
        except Exception:
            pass
        summary = f"[worker_registry] stop_all complete — drained={len(drained)} timed_out={len(timed_out)}"
        # `extra={...}` is read by the C-3 StructuredFormatter and
        # merged at top level of the JSON record.  It is NOT printed
        # to stderr by the default StreamHandler — the summary text
        # remains byte-identical to pre-C-3.
        logger.info(
            summary,
            extra={
                "drained_count": len(drained),
                "timed_out_count": len(timed_out),
                "drain_duration_ms": drain_duration_ms,
                "lifecycle_stage": "drained",
            },
        )
        print(summary, flush=True)

    # ── Status / introspection ───────────────────────────────
    def status(self) -> List[Dict[str, Any]]:
        """Snapshot of all registered workers and their runtime state."""
        return [s.to_status_dict() for s in self._workers.values()]

    def status_summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for s in self._workers.values():
            counts[s.state] = counts.get(s.state, 0) + 1
        counts["total"] = len(self._workers)
        return counts

    # ── Internal: supervised task wrapper ────────────────────
    def _launch_supervised(self, spec: WorkerSpec) -> None:
        spec.state = "starting"
        spec.started_at = time.time()
        spec._task = asyncio.create_task(
            self._supervise(spec),
            name=f"worker:{spec.name}",
        )

    async def _supervise(self, spec: WorkerSpec) -> None:
        """Run ``coro_factory()`` with crash capture + restart policy."""
        # Phase 4 / C-3 — bind worker context for the structured-JSON
        # layer.  This is additive: all existing logger.info(...) lines
        # below stay byte-identical in stderr; the structured layer
        # additionally enriches each emitted record with `worker_name`
        # and `restart_count`.  If the structured_logging module is
        # unavailable (e.g. during unit tests that import this file
        # in isolation), we degrade silently to a no-op context.
        try:
            from app.core.structured_logging import bind_worker as _bind_worker
        except Exception:
            from contextlib import contextmanager as _cm

            @_cm
            def _bind_worker(*_a, **_kw):  # type: ignore[no-redef]
                yield

        while True:
            with _bind_worker(spec.name, restart_count=spec.restarts,
                              lifecycle_stage="running"):
                try:
                    spec.state = "running"
                    logger.info("[worker_registry] running name=%s (restarts=%d)",
                                spec.name, spec.restarts)
                    await spec.coro_factory()
                    # Coroutine returned cleanly — treat as graceful exit.
                    spec.state = "stopped"
                    spec.stopped_at = time.time()
                    logger.info("[worker_registry] worker %s exited cleanly", spec.name)
                    return
                except asyncio.CancelledError:
                    spec.state = "stopped"
                    spec.stopped_at = time.time()
                    logger.info("[worker_registry] worker %s cancelled", spec.name)
                    raise  # propagate cancellation to the task
                except Exception as exc:
                    spec.state = "crashed"
                    spec.last_error = f"{type(exc).__name__}: {exc}"
                    log_fn = logger.error if spec.critical else logger.warning
                    log_fn(
                        "[worker_registry] worker %s crashed (policy=%s, restarts=%d): %s",
                        spec.name, spec.restart_policy, spec.restarts, exc,
                        exc_info=True,
                    )
                    if spec.restart_policy == "never":
                        return
                    if spec.max_restarts is not None and spec.restarts >= spec.max_restarts:
                        logger.error(
                            "[worker_registry] worker %s exceeded max_restarts=%d — giving up",
                            spec.name, spec.max_restarts,
                        )
                        return
                    spec.restarts += 1
                    # Back-off before restart
                    try:
                        await asyncio.sleep(spec.restart_backoff_sec)
                    except asyncio.CancelledError:
                        spec.state = "stopped"
                        spec.stopped_at = time.time()
                        raise
                    # Loop continues -> restart

    async def _cancel_and_await(self, spec: WorkerSpec, grace_period_sec: float) -> None:
        if spec._task is None or spec._task.done():
            return
        spec._task.cancel()
        try:
            await asyncio.wait_for(spec._task, timeout=grace_period_sec)
        except asyncio.TimeoutError:
            logger.warning(
                "[worker_registry] stop(%s): timeout after %.1fs",
                spec.name, grace_period_sec,
            )
        except asyncio.CancelledError:
            pass
        spec.state = "stopped"
        spec.stopped_at = time.time()


# ─────────────────────────────────────────────────────────────
# Module-level singleton — import this from server.py
# ─────────────────────────────────────────────────────────────
worker_registry = WorkerRegistry()


__all__ = [
    "WorkerRegistry",
    "WorkerSpec",
    "RestartPolicy",
    "WorkerState",
    "CoroFactory",
    "worker_registry",
]
