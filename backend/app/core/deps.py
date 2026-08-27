"""Dependency-injection helpers for FastAPI routers.

During P1 (mechanical router extraction) we keep the legacy globals in
``server.py`` (``db``, ``sio`` …) and simply expose them through these
accessors so new routers do not import server.py directly (which would
re-introduce circular imports).

This module is intentionally *thin* — no business logic. Replaced by
``app.state`` lookups in P2.

Phase 5.4 / C-4b — ``bitmotors_parser_instance`` bridge retired
────────────────────────────────────────────────────────────────
The lazy ``from server import bitmotors_parser_instance`` bridge has
been replaced by an explicit setter pattern that this module owns
directly. ``server.py`` startup now calls
``set_bitmotors_parser(instance)`` at exactly one site (immediately
after the conditional ``BITMOTORS_AVAILABLE`` rebind in
``_main_startup``). Reads via ``get_bitmotors_parser()`` continue to
return the same instance with identical pre-startup/post-startup
semantics:

* Pre-startup → returns ``None`` (initial value, unchanged).
* Post-startup with ``BITMOTORS_AVAILABLE=True`` → returns the
  ``BitmotorsScraper`` singleton (same identity as the legacy
  ``server.bitmotors_parser_instance`` reference).
* Post-startup with ``BITMOTORS_AVAILABLE=False`` → returns
  ``None`` (the setter is never called; the initial ``None``
  survives — same as the legacy behaviour).

The parser's lifecycle, async-init semantics, pooling, and singleton
identity are PRESERVED 1:1. C-4b is a bridge retirement, not a
parser redesign.
"""
from __future__ import annotations

from typing import Any


# ─────────────────────────────────────────────────────────────────────
# bitmotors_parser_instance — Phase 5.4 / C-4b owned reference
# ─────────────────────────────────────────────────────────────────────
# Module-private cached reference. Single writer (the setter below,
# called exactly once from server.py:_main_startup right after the
# `bitmotors_parser_instance = BitmotorsScraper(db)` assignment).
# Multiple readers (any consumer that does
# `from app.core.deps import get_bitmotors_parser`).
_bitmotors_parser_ref: Any = None


def set_bitmotors_parser(instance: Any) -> None:
    """One-shot setter for the BitmotorsScraper singleton.

    Called exactly once during ``server.py:_main_startup`` after the
    conditional ``if BITMOTORS_AVAILABLE: bitmotors_parser_instance =
    BitmotorsScraper(db)`` rebind. Accepts ``None`` too — although
    the current startup code only invokes this setter inside the
    truthy branch, accepting ``None`` keeps the setter API
    symmetric and safe against any future startup-flow change.

    Rebinding semantics: idempotent. Calling ``set_bitmotors_parser``
    twice with the same instance keeps the same identity; calling it
    with a different instance OVERWRITES (mirrors the legacy ``global
    bitmotors_parser_instance`` rebind behaviour). This is the
    EXPECTED contract for Phase 5.4 / C-4b.
    """
    global _bitmotors_parser_ref
    _bitmotors_parser_ref = instance


def get_db() -> Any:
    """Return the live Motor database handle.

    Phase 5.4 / C-4j — db bridge retirement FINALE.
    ─────────────────────────────────────────────────
    The legacy ``from server import db`` lazy bridge has been retired
    here. This FastAPI DI source now delegates to
    ``app.core.db_runtime.get_db()`` which is the **owning accessor**
    for the live Motor ``AsyncIOMotorDatabase`` handle (set exactly
    once during ``server.py:_main_startup()`` via ``db_runtime.set_db``
    immediately after ``db = db_client[DB_NAME]``).

    Identity is preserved 1:1 with the pre-C-4j behaviour:

    * Post-startup: ``deps.get_db()`` returns the same Motor object
      that ``server.db`` holds — proven at startup time by an
      identity assertion at the setter site (server.py).
    * Pre-startup: returns ``None`` — mirroring legacy
      ``from server import db`` semantics where ``server.db`` would
      have been the module-scope initial value before
      ``_main_startup`` ran.

    Request-scope behaviour for ``Depends(get_db)`` is byte-for-byte
    identical to the pre-C-4j state. Routers continue to use the
    canonical pattern unchanged:

        from app.core.deps import get_db
        ...
        async def handler(db: Any = Depends(get_db)):
            await db.collection.find_one(...)

    The C-4j retirement removes the LAST ``from server import db``
    production site — see ``tests/test_phase5_4_c4j_db_bridge_finale.py``
    invariants 1 + 3 + 5 for the AST audit and identity proof.
    """
    # Local import to avoid any chance of circular bootstrap at deps
    # module-load time (db_runtime is import-clean but we keep the
    # local-import discipline of the legacy bridge for parity).
    from app.core.db_runtime import get_db as _runtime_get_db  # noqa: WPS433
    return _runtime_get_db()


def get_sio() -> Any:
    """Return the Socket.IO server instance.

    Phase 5.4 / C-4c — reads from ``app.core.socket_runtime`` which
    owns the live ``AsyncServer`` reference (published at module-load
    time in ``server.py`` immediately after the canonical creation +
    ASGIApp mount). The legacy ``from server import sio`` lazy bridge
    has been retired here; identity is preserved 1:1 because both
    sides reference the same object.
    """
    from app.core.socket_runtime import get_sio as _sock_get_sio  # noqa: WPS433
    return _sock_get_sio()


def get_bitmotors_parser() -> Any:
    """Return the singleton BidMotors parser instance, or ``None`` if disabled.

    Phase 5.4 / C-4b — reads from the module-local cached reference.
    The legacy ``from server import bitmotors_parser_instance`` lazy
    bridge has been retired. Object identity is preserved 1:1 with
    the legacy bridge: the setter is invoked exactly once with the
    same object that ``server.bitmotors_parser_instance`` holds.
    """
    return _bitmotors_parser_ref
