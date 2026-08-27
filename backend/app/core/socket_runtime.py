"""Socket.IO runtime accessor — Phase 5.4 / C-4c.

This module is the **owning location** for the live
``python-socketio.AsyncServer`` instance at runtime.

Pattern (mirror of ``app.core.deps.set_bitmotors_parser`` from C-4b)
─────────────────────────────────────────────────────────────────

* Single writer  ``set_sio(instance)`` — invoked exactly once at the
  module-load-time creation site in ``server.py`` (immediately after
  ``sio = socketio.AsyncServer(...)`` and the ``socketio.ASGIApp(...)``
  wrap, BEFORE any ``@sio.event`` handler decorator runs).
* Many readers  ``get_sio()`` — module-private cached reference,
  fresh on every call so any in-process rebind (forbidden but
  defensively allowed) is visible.
* Test escape hatch  ``clear_sio_for_tests()`` — restores the
  ``None`` initial state so unit tests can verify pre-startup
  semantics without touching the global accessor.

Semantics preserved 1:1 with the legacy ``from server import sio``
lazy bridge:

* Pre-load → returns ``None`` (the initial cached value).
* Post-load → returns the EXACT same ``AsyncServer`` instance that
  ``server.sio`` references and that
  ``socketio.ASGIApp(sio, ...)`` wraps and that
  ``@sio.event``-decorated handlers are bound to.
* ``@sio.event`` handler binding is unchanged because the
  decorators run AFTER the setter call and read the
  module-scope ``server.sio`` name directly (the accessor never
  proxies — only publishes the same object identity).

Why a dedicated module (not ``app.core.deps``)
────────────────────────────────────────────────

The C-4b parser accessor lives in ``app.core.deps`` because it
shares the "lazy DI for routers" shape. The Socket.IO server is a
genuinely different concern (runtime event-bus surface, not
request-scope DI), and the C-4c mandate explicitly forbids
sharing a "runtime architecture" abstraction. So this module is
deliberately tiny and standalone — it owns one thing.

Forbidden in this module (by C-4c mandate)
─────────────────────────────────────────────

* No event-bus abstraction.
* No ``SocketPublisher`` wrapper.
* No emit helpers (those stay where they are in
  ``server.py:emit_to_user`` / ``emit_to_role`` until a later wave).
* No room-name policies.
* No namespace policies.
* No JWT or auth logic.

This module's surface is exactly: ``set_sio``, ``get_sio``,
``clear_sio_for_tests`` — and the module-private cached reference
they manipulate. Nothing else.
"""
from __future__ import annotations

from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────
# Module-private cached reference. Single writer, many readers.
# Initial value is None — pre-load readers see the legacy "import a
# global that hasn't been bound yet" semantics. Once set_sio runs at
# module-load time in server.py (right after the canonical
# `sio = socketio.AsyncServer(...)` + ASGIApp wrap), this points to
# the exact AsyncServer instance used by FastAPI/ASGI mount and by
# the @sio.event decorators.
# ─────────────────────────────────────────────────────────────────────
_sio_ref: Optional[Any] = None


def set_sio(instance: Any) -> None:
    """One-shot setter for the Socket.IO ``AsyncServer`` singleton.

    Called exactly once from ``server.py`` at module-load time,
    immediately after the canonical
    ``sio = socketio.AsyncServer(...)`` creation + the
    ``socketio.ASGIApp(sio, other_asgi_app=fastapi_app)`` wrap.
    Accepts ``None`` so test harnesses can reset state via
    ``clear_sio_for_tests`` (which is a one-line wrapper).

    Rebinding semantics: idempotent — calling ``set_sio`` twice with
    the same instance keeps the same identity; calling it with a
    different instance OVERWRITES (this is the contract because
    ``server.sio`` itself is a mutable module-level global; we mirror
    that semantics exactly).

    The C-4c contract is that production code calls this EXACTLY
    ONCE. A startup-time identity assertion in ``server.py`` (and
    a regression test for the AST shape of the call) enforces this.
    """
    global _sio_ref
    _sio_ref = instance


def get_sio() -> Any:
    """Return the live ``AsyncServer`` instance, or ``None`` pre-load.

    The legacy ``from server import sio`` lazy bridge has been
    retired (C-4c). Consumers must now read from this accessor.
    Object identity is preserved 1:1 with the legacy bridge: the
    setter is invoked exactly once with the same object that
    ``server.sio`` holds, ``socketio.ASGIApp(...)`` wraps, and
    ``@sio.event`` decorators bind handlers to.

    Lazy semantics (call at point-of-use, not at import) are
    preserved by NOT caching the return value at the consumer side
    — every caller invokes ``get_sio()`` fresh.
    """
    return _sio_ref


def clear_sio_for_tests() -> None:
    """Reset the accessor to ``None``. TEST USE ONLY.

    Production code MUST NOT call this. It exists because the C-4c
    regression test suite needs to verify pre-load behaviour
    (``get_sio() is None``) without rebooting the Python process.
    Always pair with ``set_sio(original)`` in a try/finally to
    restore live state for any downstream test.
    """
    global _sio_ref
    _sio_ref = None


__all__ = ["set_sio", "get_sio", "clear_sio_for_tests"]
