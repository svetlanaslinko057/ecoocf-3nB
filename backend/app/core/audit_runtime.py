"""Audit callable runtime accessor — Phase 5.4 / C-5c.

This module is the **owning location** for the live ``audit`` async
callable at runtime — the 8-field security-event helper that writes
through ``SecurityAuditRepository`` (Phase 5.4 / C-1).

Pattern (mirror of ``app.core.socket_runtime`` from C-4c and
``app.core.aggregator_runtime`` from C-5b)
──────────────────────────────────────────────────────────────────

* Single writer  ``set_audit(callable)`` — invoked exactly once at
  module-load time in ``server.py``, immediately after the
  ``async def audit(...)`` definition closes (server.py ~line 3070).
* Many readers  ``get_audit()`` — returns the live async callable
  reference. Fresh on every call (no consumer-side caching).
* Test escape hatch  ``clear_audit_for_tests()`` — restores ``None``.

Why a dedicated module (not ``app.core.deps``)
──────────────────────────────────────────────

The C-4c sio retirement established the rule: runtime-handle
accessors that own ONE thing get their own tiny module. ``audit``
is a side-effect callable, NOT a request DI source — so it follows
the C-4c shape (own module), not the C-4b shape (shared deps.py).

Pre-C-5c micro-audit summary (mandatory per mandate correction)
────────────────────────────────────────────────────────────────

Per the C-5c mandate correction, every accessor-extraction commit
on a side-effect callable must answer five questions BEFORE the
implementation lands. The audit's results:

  Q1. Pure singleton?              ❌ NO  — async callable, not a class
       The callable is captured by reference in
       ``identity_runtime._audit_callable()`` and in two
       ``server.py``-internal worker loops (resolver_worker @
       server.py:6510, transfer_detector @ server.py:6564).
  Q2. Late-bound runtime?          ❌ YES — closes over module-global db
       The function body executes ``SecurityAuditRepository(db)``
       where ``db`` is the module-global name resolved at CALL
       time (closure-by-name). At ``async def audit(...)`` definition
       time, ``db`` is ``None``; at first call time, ``db`` has been
       set via ``app.core.db_runtime.set_db`` inside ``_main_startup``.
  Q3. Captures db internally?      ❌ YES (indirect)
       Body opens ``SecurityAuditRepository(db).record_security_event``
       on every call — the audit callable's closure depends on the
       runtime db handle. This is the **load-bearing reason** Q4
       is critical.
  Q4. Published after set_db?      ✅ YES (effectively)
       The set_audit() publication happens at MODULE-LOAD time
       (right after `async def audit(...)` closes), but every
       production call-site is invoked ONLY post-startup
       (HTTP handlers + worker loops both run after
       _main_startup completes). The lazy closure resolution
       guarantees the right db at call time. The audit callable
       also wraps its entire body in ``try / except Exception``
       (best-effort semantics, ``Never raises``) so the worst-case
       pre-set_db invocation is a silent debug log — no behaviour
       regression possible.
  Q5. Referenced by workers?       ✅ YES — but not via `from server import`
       Two worker loops in server.py call ``audit(...)`` by bare
       name (server.py-internal closure). These DO NOT use
       ``from server import audit`` and therefore are NOT in the
       C-5c migration scope. They continue to read the module
       global directly.

Verdict: PROCEED with execution. Pattern is C-4c-shape (async
callable + identity assertion at setter site) rather than C-4b-shape
(value singleton), but Q4's "publish after set_db" requirement is
satisfied implicitly by the production call-graph rather than
explicitly by ordering inside ``_main_startup``.

Critical preservation contract (load-bearing)
─────────────────────────────────────────────

The audit callable's contract is **load-bearing across the
security boundary**:

* Signature  ``async def audit(action, user=None, resource=None,
  meta=None, request=None)`` — 5 positional / keyword params.
* 8-field write schema  ``{ts, action, user_id, user_email,
  user_role, resource, meta, ip}`` — H-5 invariant from Phase
  5.4 / C-1. Forbidden to mutate.
* Best-effort semantics  ``except Exception: logger.debug(...)``
  — never raises, ever.
* Async/await behaviour  — caller pattern is always
  ``await audit(...)`` or ``await get_audit()(...)``.

C-5c MUST NOT touch any of the above. Schema, signature, and
async shape are preserved 1:1.

Forbidden in this module (by C-5c mandate)
─────────────────────────────────────────────

* No ``AuditService`` wrapper class.
* No schema normalization.
* No merge with ``audit_events`` or ``audit_log`` table.
* No ``SecurityAuditRepository`` API change.
* No event-bus abstraction.
* No DTO.
* No route changes.
* No auth-flow changes.
* No request-context changes.
* No logging/metrics changes.
* No aggregator / _STATIC_DIR / shipment-helper movement.

This module's surface is exactly: ``set_audit``, ``get_audit``,
``clear_audit_for_tests``.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional


# ─────────────────────────────────────────────────────────────────────
# Module-private cached reference. Single writer, many readers.
# Pre-load → None (the legacy "import a global that hasn't been
# bound yet" semantics — exact match for `from server import audit`
# before C-5c). Post-load → identical async callable that
# `server.audit` references and that resolver/transfer worker loops
# call by closure name.
# ─────────────────────────────────────────────────────────────────────
_audit_ref: Optional[Callable[..., Awaitable[None]]] = None


def set_audit(callable_: Optional[Callable[..., Awaitable[None]]]) -> None:
    """One-shot setter for the ``audit`` async callable.

    Called exactly once from ``server.py`` at module-load time,
    immediately after ``async def audit(...)`` closes. The
    canonical call site is documented at server.py ~line 3070
    with an identity assertion (``assert get_audit() is audit``).

    Rebinding semantics: idempotent — calling ``set_audit`` twice
    with the same callable keeps identity; calling it with a
    different callable OVERWRITES (mirrors the mutable
    module-global semantics of ``server.audit``).

    Accepts ``None`` so test harnesses can reset state via
    ``clear_audit_for_tests``.
    """
    global _audit_ref
    _audit_ref = callable_


def get_audit() -> Optional[Callable[..., Awaitable[None]]]:
    """Return the live ``audit`` async callable, or ``None`` pre-load.

    The legacy ``from server import audit`` lazy bridge has been
    retired (C-5c). Consumers must now read from this accessor:

        from app.core.audit_runtime import get_audit
        audit = get_audit()
        await audit(action="login", user=user, request=request)

    Or for one-shot fire-and-forget patterns:

        await get_audit()(action="...", ...)

    Callers MUST NOT cache the return value at module load
    (returning ``None`` would silently break). Cache only at
    call-site if at all.

    Object identity is preserved 1:1 with the legacy bridge: the
    setter is invoked exactly once with the same callable that
    ``server.audit`` references and that
    ``identity_runtime._audit_callable()`` returns.
    """
    return _audit_ref


def clear_audit_for_tests() -> None:
    """Reset the accessor to ``None``. TEST USE ONLY.

    Production code MUST NOT call this. Always pair with
    ``set_audit(original_callable)`` in a try/finally to restore
    live state for downstream tests.
    """
    global _audit_ref
    _audit_ref = None


__all__ = ["set_audit", "get_audit", "clear_audit_for_tests"]
