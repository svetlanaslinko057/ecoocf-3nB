"""
SecurityAuditRepository — Phase 5.4 / C-1.
==========================================

Canonical owner of the ``db.audit_log`` Mongo collection.

**This is the FIRST extraction in Phase 5.4** — the phase that
begins **orchestration isolation** (per midpoint roadmap).
It is also the THIRD lifecycle-shaped-mandate extraction
(after C-10 ``email_outbox`` and C-11 ``audit_events``).
It completes the **dual-audit topology** identified by C-11
§1.2 / §2.5: the sibling collection that was deliberately
NOT extracted in Phase 5.3 is now extracted as its own
ownership boundary, **WITHOUT merging** the two audit
collections.

What this repository is — and what it is NOT
--------------------------------------------

**IS:** the data-access boundary for ``db.audit_log``.

**IS NOT:**
* an ``AuditService`` (forbidden by C-1 mandate);
* a unified audit abstraction;
* a wrapper that merges or normalizes any schema;
* a base class for a future hierarchy;
* a side-effect orchestration extraction.

**This is the FIRST extraction whose collection has a
WRITE-ONLY runtime usage pattern.** No admin reader endpoint
currently exists for ``audit_log``. The collection self-
cleans via a 90-day TTL index. C-1 preserves this property:
the repository exposes 5 enqueue verbs and 1 boot verb,
**zero read verbs**. If a future Phase 5.4 commit needs to
add an admin reader, that commit adds the read verb;
C-1 does NOT add speculative reads.

Lifecycle-context classification (third lifecycle-shaped
inventory; methodology stable since C-10/C-11)
---------------------------------------------------------

::

  Category                    | Sites found
  ────────────────────────────┼──────────────────────────────
  enqueue contexts            | 4 distinct shape-contexts
                              |   1) server.audit() helper
                              |      (8-field; 6 logical callers)
                              |   2) server._audit_hmac_failure
                              |      (4-field hmac variant; 1 caller)
                              |   3) server.py login flow — inline
                              |      (login_failed 4-field + login_ok
                              |      6-field; 2 inline call sites)
                              |   4) transfer_detector._audit helper
                              |      (4-field resource variant;
                              |      5 logical callers)
                              |   ⇒ 14 logical write sites collapsed
                              |     onto 5 distinct doc shapes
  dispatch contexts           | 0
  retry contexts              | 0
  failure contexts (lifecycle)| 0 — all writes try/except SWALLOW
  success/finalization        | terminal-at-insert
  cleanup/TTL contexts        | 1 — NEW vs C-10 AND C-11!
                              |   90-day TTL on ts
                              |   (server.py:2315; preserved verbatim
                              |   through ensure_indexes())
  boot/startup contexts       | 1 — INDEX (TTL only; vs C-11's 6
                              |   non-TTL indexes)
  worker contexts             | 0 — transfer_detector is a service
                              |   called by request handlers,
                              |   not a long-running worker
                              |   reading audit_log
  ────────────────────────────┴──────────────────────────────
  admin reader contexts       | 0 — write-only collection at runtime
                              |   (TTL handles cleanup)

**Of 8 lifecycle write-path categories, 3 are populated:**
enqueue (×4 context-families) + cleanup/TTL + boot-INDEX.
C-10 had 1 of 8; C-11 had 2 of 8; C-1 has 3 of 8 — the
**lifecycle-shape density rises monotonically** across the
three log-named extractions. The NEW dimension introduced
by C-1 is the cleanup/TTL category, which is structurally
distinct from the boot-INDEX category (the TTL is a
PROPERTY of the index, but the cleanup BEHAVIOUR is what
populates the category; both must be documented).

The five doc shapes (writer topology)
--------------------------------------

::

  Shape 1 — security_event (8 fields) — server.audit() helper
  ─────────────────────────────────────────────────────────────
    {
      "ts":         "<ISO string>",
      "action":     "<event verb>",      # e.g. "tracking_disabled_skipped"
      "user_id":    "<staff id or None>",
      "user_email": "<staff email or None>",
      "user_role":  "<staff role or None>",
      "resource":   "<resource path or None>",
      "meta":       {<context dict>},
      "ip":         "<client ip or None>",
    }

  Shape 2 — hmac_failure (4 fields) — _audit_hmac_failure
  ─────────────────────────────────────────────────────────────
    {
      "ts":     "<ISO string>",
      "action": "hmac_failed",
      "meta":   {"reason", "client", "method", "path"},
      "ip":     "<ip or None>",
    }
    # No user_*; no resource. Carries WHY the HMAC failed
    # (the meta dict has its own micro-schema).

  Shape 3 — login_failed (4 fields) — server.py inline @ 3837
  ─────────────────────────────────────────────────────────────
    {
      "ts":     "<ISO string>",
      "action": "login_failed",
      "email":  "<plaintext email attempt>",
      "ip":     "<ip or None>",
    }
    # FLAT email (NOT user_email); no user_id; no role.
    # The auth flow does NOT know if the email is valid
    # at the moment the audit fires.

  Shape 4 — login_ok (6 fields) — server.py inline @ 3859
  ─────────────────────────────────────────────────────────────
    {
      "ts":      "<ISO string>",
      "action":  "login_ok",
      "user_id": "<resolved staff id>",
      "email":   "<staff email>",         # FLAT (NOT user_email)
      "role":    "<staff role>",          # FLAT (NOT user_role)
      "ip":      "<ip or None>",
    }
    # FLAT email/role (NOT user_email/user_role) — divergent
    # from shape 1's nested model. Load-bearing legacy.

  Shape 5 — transfer_event (4 fields) — transfer_detector._audit
  ─────────────────────────────────────────────────────────────
    {
      "ts":       "<ISO string>",
      "action":   "<transfer verb>",        # "transfer_detected", etc
      "resource": "shipment:<shipment_id>", # FORMATTED string!
      "meta":     {<decision context>},
    }
    # No user_*; no ip; resource is a FORMATTED string
    # (not a free-form path like shape 1). Load-bearing.

These five shapes ARE NOT NORMALIZED. They are not merged into
a base type. They share NO Pydantic model. The repository
contract surface exposes **one named verb per shape** —
collapsing them would HIDE the writer topology that 9
months of organic security-audit accumulation has produced.

Inventory vs Ownership Map (post-C-11)
---------------------------------------

::

  Field                           | Value
  --------------------------------|------------------------------
  Map row                          | NOT EXPLICITLY MAPPED in
                                   | PHASE5_1_OWNERSHIP_MAP.md
                                   | (audit_log appears only in
                                   | §1.5 alongside audit_events).
                                   | C-11 documented it as Type V
                                   | sibling. C-1 (Phase 5.4)
                                   | produces the canonical map
                                   | row from inventory — SECOND
                                   | such extraction (after C-11).
  Owner candidate (C-1 verdict)    | server.py (the audit() helper
                                   | dominates write topology;
                                   | transfer_detector.py carries
                                   | a structurally-similar but
                                   | separate helper for transfer
                                   | lifecycle events; both write
                                   | through the repository)
  Static AST result                | 6 raw Motor sites
                                   |   server.py × 5
                                   |     (1 index + 4 inserts)
                                   |   transfer_detector.py × 1
  Writer contexts (lifecycle)      | 4 enqueue context-families
                                   | (14 logical callers in 2 files)
                                   | + 1 boot-INDEX + 1 cleanup/TTL.
  Reader contexts                  | 0 — NO admin endpoint reads
                                   | this collection.
  Cross-domain WRITE in own owner  | 0 inside server.audit() and
                                   | transfer_detector._audit().
                                   | Both helpers write ONLY
                                   | audit_log.
  Cross-domain WRITE from outside  | 0 — no third-party module
                                   | writes audit_log.
  Type V tension (C-11 §2.5)       | RESOLVED at the boundary
                                   | level (audit_log now has
                                   | its own repository); the
                                   | dual-schema distinction
                                   | between audit_log and
                                   | audit_events is PRESERVED
                                   | (no merging, no facade).
  Verdict                          | CONFIRMED with **dual-audit
                                   | topology now complete**.
                                   | Phase 5.4 / C-1 produces
                                   | the second half of the
                                   | audit-family ownership
                                   | boundary, without unifying
                                   | the underlying collections.

How this completes the dual-audit topology
-------------------------------------------

C-11 extracted ``audit_events`` and documented ``audit_log``
as a Type V sibling. C-1 (Phase 5.4) extracts ``audit_log``
into its own repository. The dual-audit topology is now:

::

  ┌──────────────────────────────────────────────────────────┐
  │                  Dual-audit topology                      │
  │                                                            │
  │  AuditEventsRepository (C-11, Phase 5.3)                  │
  │      ↳ db.audit_events                                    │
  │      ↳ Concern: domain-business audit (legal/payment)     │
  │      ↳ Indexes: 6 hot-lookup indexes                      │
  │      ↳ TTL: none (legal-compliance forever)               │
  │      ↳ Consumers: 2 admin endpoints                       │
  │      ↳ Shapes: 2 (domain-event, payment-webhook)          │
  │                                                            │
  │  SecurityAuditRepository (C-1, Phase 5.4) ← THIS COMMIT   │
  │      ↳ db.audit_log                                       │
  │      ↳ Concern: security audit (auth/transfer/cross-cut)  │
  │      ↳ Indexes: 1 TTL index (90 days)                     │
  │      ↳ TTL: 90 days on ts                                 │
  │      ↳ Consumers: 0 (write-only at runtime)               │
  │      ↳ Shapes: 5 (security_event / hmac_failure /         │
  │                  login_failed / login_ok / transfer_event)│
  │                                                            │
  │  NO shared base class. NO common abstraction.             │
  │  NO unified facade. NO merging at storage layer.          │
  │  The TWO repositories COEXIST as sibling ownership        │
  │  boundaries on TWO sibling collections.                   │
  └──────────────────────────────────────────────────────────┘

Phase 5.4 next steps after C-1
-------------------------------

Per the architect's mandate (the message that opened
Phase 5.4):

  5.4 / C-1  SecurityAuditRepository      ← THIS COMMIT
  5.4 / C-2  IntegrationConfigsRepository
  5.4 / C-3  app.state migration prep
  5.4 / C-4  bridge retirement wave
  5.4 / C-5  side-effect formalization

C-1 does NOT touch any of (C-2, C-3, C-4, C-5). Each is its
own ownership-decision and own commit.

Business operations vocabulary
-------------------------------

Six named verbs — one per distinct enqueue shape (5) plus one
boot-time index ensuring. **Zero read verbs** (collection is
write-only at runtime as of Phase 5.4 entry).

* ``ensure_indexes()`` —
    Creates the 90-day TTL index on ``ts``. Idempotent.
    Repeats vocabulary from C-5 + C-11 (same semantic).
* ``record_security_event(record)`` —
    8-field security-event shape from ``server.audit()``.
* ``record_hmac_failure(record)`` —
    4-field hmac variant.
* ``record_login_failed(record)`` —
    4-field login-failed variant (FLAT email).
* ``record_login_ok(record)`` —
    6-field login-ok variant (FLAT email/role).
* ``record_transfer_event(record)`` —
    4-field transfer-lifecycle variant from
    ``transfer_detector._audit``.

**6 named verbs total.** "Standard" band of the §6.3
morphology observation — verb count matches populated
lifecycle-category count (4 enqueue + 1 boot + 1 TTL
implicit in boot = 5 categories) plus one verb per distinct
enqueue shape.

Vocabulary continuity vs prior 11 repositories:

* ``ensure_indexes``           — REPEATS C-5 + C-11. Confirmed standard.
* ``record_security_event``    — NEW (lifecycle-shaped).
* ``record_hmac_failure``      — NEW (lifecycle-shaped).
* ``record_login_failed``      — NEW (lifecycle-shaped).
* ``record_login_ok``          — NEW (lifecycle-shaped).
* ``record_transfer_event``    — NEW (lifecycle-shaped).

**1 REPEATED + 5 NEW.** Strong vocabulary cohesion within
the lifecycle-shaped family: all the ``record_*`` verbs
share the lifecycle-event-naming pattern established by
C-10 (``record_email_send_*``, ``record_auth_email_audit``)
and C-11 (``record_domain_event``, ``record_payment_webhook_event``).
The vocabulary is becoming a **stable pattern language**:
``record_<source_concern>_<event_kind>``.

Legacy quirks preserved 1:1
---------------------------

1. **ts is ALWAYS an ISO string**, never datetime. Unlike
   ``audit_events`` (which mixes datetime and string), all
   5 audit_log shapes use ``datetime.now(timezone.utc).isoformat()``.
   Preserved.
2. **Each shape uses a DIFFERENT field convention** for
   user identity:
     - shape 1: nested ``user_id``/``user_email``/``user_role``
     - shapes 3, 4: flat ``email``/``role``
     - shapes 2, 5: NO user model
   Preserved 1:1 — the repository does not normalize.
3. **All writes swallow exceptions** at the call site
   (``logger.debug`` fallback). Audit must never block
   the security/auth/transfer business path. Repository
   does not raise differently.
4. **The TTL 90-day index** is the only data-lifecycle
   constraint on the collection. Old records auto-purge.
   ``audit_events`` has NO TTL (legal compliance) —
   load-bearing distinction preserved.
5. **The transfer_event shape uses a FORMATTED resource
   string** (``f"shipment:{shipment_id}"``), not a path.
   This is a different convention from shape 1's free-form
   resource. Preserved.
6. **The login flow audits BOTH success AND failure** with
   DIFFERENT shapes (login_failed has no user_id because
   auth has not yet resolved; login_ok has the resolved
   user_id but uses FLAT email/role). The two-shape
   asymmetry is a load-bearing fact about the auth state
   machine. Preserved.
7. **No admin reader.** No ``list_recent`` / ``list_filtered``
   / ``list_by_action`` on the repository. If Phase 5.4
   (or later) needs an admin tool, that commit adds the
   read verb.

What this repository does NOT do (deliberately)
------------------------------------------------

* No ``AuditService``.
* No unified audit abstraction across both audit collections.
* No shape normalization (5 distinct shapes preserved).
* No DTO / Pydantic / TypedDict.
* No ``BaseAuditRepository`` / inheritance.
* No id generation (the legacy writes have no ``id`` field;
  Mongo ``_id`` is the implicit primary key).
* No ``read`` / ``list`` / ``find`` verb of any kind.
* No HTTP exception raise (audit never blocks business).
* No event emission / Socket.IO / event bus.
* No timestamp normalization across shapes.
* No touch on ``audit_events`` (C-11's collection).
* No merging with ``audit_events`` (forbidden — Type V
  load-bearing).
* No side-effect orchestration formalization (Phase 5.4 / C-5
  territory at the earliest).
* No bridge retirement (Phase 5.4 / C-4).
* No ``app.state`` migration (Phase 5.4 / C-3).
"""
from __future__ import annotations

from typing import Any, Dict


class SecurityAuditRepository:
    """Owner of ``db.audit_log`` (security audit — auth, HMAC,
    transfer-lifecycle decisions, cross-cutting events).

    The collection is **write-only at runtime** (no admin
    reader endpoint as of Phase 5.4 / C-1). It self-cleans
    via a 90-day TTL index on ``ts``.

    Five distinct enqueue verbs preserve five load-bearing
    document shapes verbatim. One boot verb ensures the TTL
    index.

    Companion repository: ``AuditEventsRepository`` (C-11)
    owns ``db.audit_events`` (domain-business audit). The two
    repositories COEXIST as sibling ownership boundaries on
    sibling collections — they do NOT share a base class,
    a common DTO, or a unified facade.
    """

    COLLECTION = "audit_log"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Boot — TTL index ensuring (1 lifecycle context + 1 cleanup/TTL)
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Ensure the 90-day TTL index on ``ts``.

        Idempotent — Motor ``create_index`` is. Legacy
        preserved behaviour swallows any conflict (returns
        ``None`` on all error paths). Mirrors
        ``server.py:2315-2317`` verbatim:

            db.audit_log.create_index(
                "ts",
                expireAfterSeconds=90 * 24 * 3600,
                name="audit_ttl_90d",
            )
        """
        try:
            await self._db[self.COLLECTION].create_index(
                "ts",
                expireAfterSeconds=90 * 24 * 3600,
                name="audit_ttl_90d",
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Enqueue (write) — five distinct verbs reflecting five distinct
    # source concerns and five load-bearing doc shapes
    # ------------------------------------------------------------------

    async def record_security_event(self, record: Dict[str, Any]) -> None:
        """Append a generic security event.

        Mirrors ``server.audit()`` (server.py:2814-2835).
        Caller composes the 8-field shape verbatim:
        ``ts/action/user_id/user_email/user_role/resource/
        meta/ip``. Repository does NOT inject or validate.
        Terminal-at-insert. Swallow lives at the caller.
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_hmac_failure(self, record: Dict[str, Any]) -> None:
        """Append an HMAC verification failure.

        Mirrors ``_audit_hmac_failure`` (server.py:2865-2875).
        Caller composes the 4-field shape verbatim:
        ``ts/action="hmac_failed"/meta/ip``. NO user_*; NO
        resource. The ``meta`` dict carries the failure
        diagnostics (reason/client/method/path).
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_login_failed(self, record: Dict[str, Any]) -> None:
        """Append a login-failure event.

        Mirrors server.py:3837-3842 inline insert.
        Caller composes the 4-field shape verbatim:
        ``ts/action="login_failed"/email/ip``. FLAT email
        (NOT user_email); NO user_id (auth has not resolved);
        NO role.
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_login_ok(self, record: Dict[str, Any]) -> None:
        """Append a login-success event.

        Mirrors server.py:3859-3866 inline insert.
        Caller composes the 6-field shape verbatim:
        ``ts/action="login_ok"/user_id/email/role/ip``.
        FLAT email and role (NOT user_email / user_role).
        Asymmetric with ``record_login_failed`` —
        load-bearing.
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_transfer_event(self, record: Dict[str, Any]) -> None:
        """Append a transfer-lifecycle event.

        Mirrors ``transfer_detector._audit`` (transfer_detector.py:219-228).
        Caller composes the 4-field shape verbatim:
        ``ts/action/resource/meta``. The ``resource`` field
        is a FORMATTED string (``f"shipment:{shipment_id}"``),
        not a free-form path — divergent from shape 1's
        resource semantics. Load-bearing.
        """
        await self._db[self.COLLECTION].insert_one(record)


__all__ = ["SecurityAuditRepository"]
