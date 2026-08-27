"""Database runtime accessor — Phase 5.4 / C-4e.

This module is the **owning location** for the live Motor
``AsyncIOMotorDatabase`` (and its parent ``AsyncIOMotorClient``)
at runtime.

Pattern (mirror of ``app.core.socket_runtime`` from C-4c)
─────────────────────────────────────────────────────────────────

* Single writer  ``set_db(db, mongo_client=None)`` — invoked
  exactly once during ``_main_startup()`` in ``server.py``,
  immediately after the canonical
  ``db = db_client[DB_NAME]`` line and the existing
  ``fastapi_app.state.db = db`` mirror (Phase 4 / C-2).
* Many readers
    - ``get_db()`` — returns the live Motor database handle, or
      ``None`` pre-startup;
    - ``get_mongo_client()`` — returns the live
      ``AsyncIOMotorClient``, or ``None`` pre-startup.
* Test escape hatch  ``clear_db_for_tests()`` — resets the cached
  references to ``None`` so unit tests can verify pre-startup
  semantics without rebooting the process.

Semantics preserved 1:1 with the legacy ``from server import db``
lazy bridge:

* **Pre-startup**: ``get_db()`` returns ``None``. The legacy
  bridge would have returned the module-scope ``db = None``
  initial value (server.py:705) — identical observable
  behaviour for callers that fire too early.
* **Post-startup**: ``get_db() is server.db`` (identity invariant
  asserted at the setter site, plus a regression test).
* **Pre-startup writes are accepted** (the setter accepts ``None``
  to mirror legacy ``global db; db = None`` reset semantics, and
  to support test harnesses that explicitly reset state).

Why a dedicated module (not ``app.core.deps``)
────────────────────────────────────────────────

The C-4c parser / sio accessors live in ``app.core.deps`` and
``app.core.socket_runtime`` respectively because each owns one
runtime concern. ``app.core.deps`` is the FastAPI DI surface
(``Depends(get_db)``); putting the runtime-singleton accessor for
``db`` into the same module would conflate the request/DI surface
with the module-load-time runtime root. C-4d planning made this
distinction explicit: this module is for **module-service
consumers** (Class B per the DB_CONSUMER_INVENTORY taxonomy) and
for the future ``app.core.deps.get_db`` delegate (Class E, C-4j).

Forbidden in this module (by C-4e mandate)
─────────────────────────────────────────────

* No FastAPI integration (no ``Depends`` wrappers, no
  request-scoped lifetimes).
* No connection pooling logic.
* No collection helpers / repository factories.
* No session / transaction management.
* No retry policies.

This module's surface is exactly: ``set_db``, ``get_db``,
``get_mongo_client``, ``clear_db_for_tests`` — and the two
module-private cached references they manipulate. Nothing else.
"""
from __future__ import annotations

from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────
# Module-private cached references. Single writer, many readers.
# Initial values are None — pre-startup readers see the legacy
# "lazy-imported global that hasn't been bound yet" semantics. Once
# set_db runs in _main_startup (right after `db = db_client[DB_NAME]`
# and the `fastapi_app.state.db = db` mirror), both refs point at the
# exact Motor objects used by every owner-side reader in server.py.
# ─────────────────────────────────────────────────────────────────────
_db_ref: Optional[Any] = None
_mongo_client_ref: Optional[Any] = None


def set_db(db: Any, mongo_client: Optional[Any] = None) -> None:
    """One-shot setter for the Motor ``AsyncIOMotorDatabase`` and
    optional ``AsyncIOMotorClient`` singletons.

    Called exactly once from ``server.py:_main_startup()`` immediately
    after the canonical ``db = db_client[DB_NAME]`` assignment and the
    existing ``fastapi_app.state.db = db`` mirror (Phase 4 / C-2).
    Accepting ``None`` mirrors the legacy ``global db; db = None``
    reset semantics and supports test harnesses.

    Rebinding semantics: idempotent — calling ``set_db`` twice with the
    same handle keeps the same identity; calling with a different
    handle OVERWRITES (this is the contract because ``server.db`` is a
    mutable module-level global; we mirror that semantics exactly).
    The ``mongo_client`` parameter is optional so that callers who
    only need to rebind the database (e.g. tests that swap to an
    in-memory test DB) can leave the cached client intact.

    The C-4e contract is that production code calls this EXACTLY
    ONCE during ``_main_startup``. A startup-time identity assertion
    in ``server.py`` and a regression test for the AST shape of the
    call enforce this.
    """
    global _db_ref, _mongo_client_ref
    _db_ref = db
    if mongo_client is not None:
        _mongo_client_ref = mongo_client


def get_db() -> Any:
    """Return the live Motor ``AsyncIOMotorDatabase``, or ``None``
    pre-startup.

    The legacy ``from server import db`` lazy bridge is being phased
    out (C-4e..C-4j). C-4e migrates the first 12 Class-A router
    consumers to read via this accessor; identity is preserved 1:1
    because the setter is invoked exactly once with the same handle
    that ``server.db`` holds. Lazy semantics (call at point-of-use,
    not at import) are preserved: callers invoke ``get_db()`` fresh
    on every read.
    """
    return _db_ref


def get_mongo_client() -> Any:
    """Return the live ``AsyncIOMotorClient``, or ``None``
    pre-startup.

    Used by startup hooks and admin tools that need raw client
    access (database-level operations, admin commands, replica-set
    introspection) rather than the bound database handle.
    """
    return _mongo_client_ref


def clear_db_for_tests() -> None:
    """Reset both cached references to ``None``. TEST USE ONLY.

    Production code MUST NOT call this. It exists because the C-4e
    regression test suite needs to verify pre-startup behaviour
    (``get_db() is None``) without rebooting the Python process.
    Always pair with a ``set_db(original_db, original_client)`` in a
    try/finally to restore live state for any downstream test.
    """
    global _db_ref, _mongo_client_ref
    _db_ref = None
    _mongo_client_ref = None


__all__ = ["set_db", "get_db", "get_mongo_client", "clear_db_for_tests"]
