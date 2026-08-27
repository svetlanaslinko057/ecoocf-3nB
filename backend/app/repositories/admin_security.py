"""
AdminSecurityRepository — Phase 5.3 / C-3.
==========================================

Canonical owner of the ``db.admin_security`` Mongo collection.
After this commit, every mutation to that collection flows through
this class. The router ``app/routers/admin_security.py`` owns the
admin HTTP surface (TOTP secret generation, QR rendering, code
verification) and calls into THIS repository for ALL collection
access. There are NO other readers or writers of
``db.admin_security`` anywhere in the codebase.

Business operations (named verbs, NOT generic CRUD)
----------------------------------------------------

* Reads:
    - ``get_state(admin_id)``               full per-admin 2FA state
                                            (or ``None`` if no row)

* Writes:
    - ``record_setup_pending(admin_id, *, secret)``
                                            stash a fresh TOTP secret
                                            in ``twofa_secret`` and
                                            mark ``twofa_enabled=False``
                                            (upsert)
    - ``mark_enabled(admin_id)``            transition to
                                            ``twofa_enabled=True``
                                            (NO upsert — see quirks)
    - ``clear_2fa(admin_id)``               wipe secret + disable
                                            (upsert)

Legacy behaviour preserved 1:1 (Phase 5.3 / C-3 mandate)
--------------------------------------------------------

These quirks live in the legacy router site and are reproduced
here verbatim. Changing any of them is OUT OF SCOPE for this
commit.

* **``_id`` IS the ``admin_id`` string.** The collection does not
  carry a separate ``id`` field; the document primary key IS the
  admin scope identifier (``"admin"`` in single-tenant mode).
  Both reads and writes select by ``{"_id": admin_id}``.
* **``get_state`` returns ``None`` on miss** (not ``{}``). The
  legacy router applied ``... or {}`` at the call site; that
  call-site idiom is preserved in the migrated router so the
  repository surface matches Motor's natural ``find_one`` shape.
* **Timestamps are stored as ``datetime`` (not ISO strings).**
  Legacy lines 94, 128, 150 of the old router stored
  ``datetime.now(timezone.utc)`` objects directly into Mongo
  (BSON-encoded). This differs from ``history_reports`` which
  stores ISO-8601 strings. Both behaviours are preserved per
  their respective legacy contracts — do not unify.
* **``record_setup_pending`` upserts but does NOT clear
  ``twofa_enabled_at`` / ``twofa_disabled_at``.** Only the three
  setup fields are ``$set``; older audit timestamps from a prior
  enable/disable cycle linger in the document. Preserved 1:1.
* **``mark_enabled`` does NOT upsert.** Legacy line 124 of the
  old router issues a plain ``update_one`` with no ``upsert=True``.
  If no setup-pending row exists, this is a NO-OP (matched=0).
  Preserved verbatim — the router relies on the preceding
  ``twofa_secret`` check (line 117 of old) to gate this path.
* **``clear_2fa`` upserts even when the row never existed.** Legacy
  line 145 uses ``upsert=True`` so calling disable on a virgin
  install creates a row with ``twofa_enabled=False``,
  ``twofa_secret=None``, and a ``twofa_disabled_at`` stamp. This
  shape can therefore appear without ever having been enabled.
* **No projection of ``_id`` on reads.** Legacy ``find_one``
  carries ``_id`` (the admin string) through. Callers do not
  rely on its presence; preserving the lack of projection
  matches legacy byte-for-byte.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``update(filter, doc)`` escape hatch.
*  No ``save()`` / ``upsert()`` shortcut.
*  No HTTP exceptions — repository raises only on programmer error.
*  No DTO normalisation — returns dicts in the exact legacy shape.
*  No ``_id`` projection — legacy does not project it out.
*  No TOTP / QR-code logic — those are crypto/render concerns
   and stay in the router. The repository persists ONLY the
   collection state (the secret string, the booleans, the
   timestamps).
*  No BaseRepository (per architect mandate).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now() -> datetime:
    """UTC now as a ``datetime`` (matches legacy storage shape).

    Legacy writes ``datetime.now(timezone.utc)`` directly to Mongo;
    BSON encodes it as a Date. We mirror that — NOT an ISO string.
    """
    return datetime.now(timezone.utc)


class AdminSecurityRepository:
    """Owner of ``db.admin_security``.

    The repository instance is cheap to construct (just stores a
    reference to the Motor handle). The router constructs per call
    via the Wave-1 lazy-bridge pattern; that bridge is the only
    remaining ``from server import db`` site in this surface and
    will dissolve in Phase 5.8 with DI.
    """

    COLLECTION = "admin_security"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_state(self, admin_id: str) -> dict | None:
        """Fetch the per-admin 2FA state document.

        Returns the raw Mongo document (including ``_id`` which IS
        the ``admin_id``) or ``None`` if no row exists. Callers in
        the legacy router apply ``... or {}`` to coerce the miss
        path; that idiom stays at the call site.
        """
        return await self._db[self.COLLECTION].find_one({"_id": admin_id})

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def record_setup_pending(self, admin_id: str, *, secret: str) -> None:
        """Stash a freshly generated TOTP secret in setup-pending state.

        Sets exactly three fields (mirroring legacy line 91-95):
            * ``twofa_secret``           the new base32 secret
            * ``twofa_enabled``          ``False`` (verify step required)
            * ``twofa_setup_started_at`` ``datetime.now(timezone.utc)``

        Upsert. Older audit timestamps (``twofa_enabled_at`` /
        ``twofa_disabled_at``) from a prior cycle are NOT cleared —
        legacy preserves them. The secret + the booleans are
        sufficient to drive the verify path.
        """
        await self._db[self.COLLECTION].update_one(
            {"_id": admin_id},
            {"$set": {
                "twofa_secret":            secret,
                "twofa_enabled":           False,
                "twofa_setup_started_at":  _utc_now(),
            }},
            upsert=True,
        )

    async def mark_enabled(self, admin_id: str) -> None:
        """Transition from setup-pending to enabled.

        Sets ``twofa_enabled=True`` and stamps ``twofa_enabled_at``.
        Legacy line 124 of the old router does NOT use ``upsert=True``
        — this is preserved. If no setup-pending row exists, this
        operation is a NO-OP. The router's verify path gates against
        that case before reaching here (it short-circuits on a
        missing ``twofa_secret`` at line 117 of the old router).
        """
        await self._db[self.COLLECTION].update_one(
            {"_id": admin_id},
            {"$set": {
                "twofa_enabled":     True,
                "twofa_enabled_at":  _utc_now(),
            }},
        )

    async def clear_2fa(self, admin_id: str) -> None:
        """Disable 2FA — wipe secret + flip enabled flag.

        Sets ``twofa_enabled=False``, ``twofa_secret=None``, and
        stamps ``twofa_disabled_at``. Upserts (legacy line 152
        carries ``upsert=True``), which means calling disable on
        a virgin install will materialise a row in the disabled
        shape — preserved verbatim.
        """
        await self._db[self.COLLECTION].update_one(
            {"_id": admin_id},
            {"$set": {
                "twofa_enabled":      False,
                "twofa_secret":       None,
                "twofa_disabled_at":  _utc_now(),
            }},
            upsert=True,
        )


__all__ = ["AdminSecurityRepository"]
