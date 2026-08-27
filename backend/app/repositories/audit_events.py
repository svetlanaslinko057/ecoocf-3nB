"""
AuditEventsRepository — Phase 5.3 / C-11.
=========================================

Canonical owner of the ``db.audit_events`` Mongo collection.

**This is the SECOND lifecycle-shaped-mandate extraction** (the
first was C-10 ``email_outbox``). The architect selected
``audit_events`` for C-11 as a second data-point on collections
whose name carries pipeline/log/audit/event semantics, to test
whether the methodology divergence observed in C-10 (lifecycle-
shaped inventory > CRUD-shaped inventory for log-named
collections) repeats.

The inventory result: **it repeats, in a structurally different
way.** Where C-10 (``email_outbox``) found a transport audit log
with 3 enqueue contexts in 2 files writing 2 divergent shapes,
C-11 (``audit_events``) finds a **domain-business audit log with
1 helper-mediated enqueue context (16+ caller sites collapsed
through ``legal_workflow._audit()``) + 1 direct enqueue context
(``payments`` stripe-webhook) + 1 boot-time INDEX context (6
indexes ensured at startup) writing 2 divergent shapes**.

What the collection actually is
-------------------------------

::

  db.audit_events  =  append-only domain-business audit trail,
                      indexed by 6 keys for accountancy /
                      legal-dispute / RCA queries,
                      written by TWO unrelated concern-spaces
                      with TWO divergent document shapes,
                      with NO worker, NO retry, NO TTL,
                      NO state transitions after insert.

The collection is **indexed** (unlike ``email_outbox``):

::

  6 indexes ensured by server.py startup (line 2481-2486):
    [("ts", -1)]                                       (recency scans)
    [("deal_id", 1), ("ts", -1)]                       (deal trail)
    [("customer_id", 1), ("ts", -1)]                   (customer trail)
    [("entity_type", 1), ("entity_id", 1), ("ts", -1)] (entity trail)
    [("type", 1), ("ts", -1)]                          (event-type trail)
    [("id", 1)]   unique, sparse                       (dedup by id)

The indexes carry their own architectural fact: **the consumer
of this collection is admin / accountancy queries**, not a
dispatch worker. The indexes were designed for hot
``find_one`` / ``find`` lookups across the five canonical
filter axes (``deal_id``, ``customer_id``, ``entity_type``+
``entity_id``, ``type``, ``user_email`` — though ``user_email``
has no dedicated index, it filters in-memory after a
``ts`` scan). C-11 ensure_indexes() preserves all 6 verbatim
(no consolidation, no removal, no addition).

Lifecycle-context classification (architect's C-11 mandate
methodology — applies the rule established by C-10 §6.3
observation 7)
-----------------------------------------------------------

::

  Category                    | Sites found
  ────────────────────────────┼──────────────────────────────
  enqueue contexts            | 2
                              |   - legal_workflow._audit()
                              |     (helper called by ~16 sites)
                              |   - payments router stripe
                              |     webhook audit
                              |     (app/routers/payments.py:488)
  dispatch contexts           | 0 — no worker reads the events
  retry contexts              | 0
  failure contexts (lifecycle)| 0 — both enqueue paths are
                              |     wrapped in try/except that
                              |     SWALLOWS the exception
                              |     (audit MUST NEVER drop the
                              |     business path); the swallow
                              |     pattern is intentional, NOT
                              |     a retry surface
  success/finalization        | terminal-at-insert
  cleanup/TTL contexts        | 0 — per legal_workflow._audit
                              |     docstring: "После prod-deploy
                              |     эту коллекцию нельзя
                              |     редактировать вручную"
                              |     (post-prod-deploy this
                              |     collection cannot be edited
                              |     manually) — append-only is
                              |     a legal-compliance constraint
  boot/startup contexts       | 1 — INDEX ENSURING (6 indexes)
                              |     at server.py startup
                              |     (line 2476-2487)
  worker contexts             | 0 — transfer_detector._audit()
                              |     writes to db.audit_LOG
                              |     (the SIBLING, NOT this
                              |     collection — see §1.2)
  ────────────────────────────┴──────────────────────────────

  admin reader contexts       | 2
                              |   - GET /legal/audit (6 filters)
                              |   - GET /legal/deals/{id}/audit

**Of the 8 lifecycle write-path categories, 2 are populated
(enqueue + boot/startup-INDEX).** This is structurally different
from C-10 (where only enqueue was populated). The
``ensure_indexes`` boot context is a NEW lifecycle category
that C-10 did not exhibit — log-shaped collections do NOT have
to be index-free. The index-ensuring context is small (one call
site) but architecturally distinct from the enqueue contexts
and DESERVES its own named verb at the repository surface.

The two enqueue contexts (writer topology)
-------------------------------------------

::

  ┌──────────────────────────────────────────────────────────────┐
  │ Enqueue 1 — legal_workflow._audit() — DOMAIN AUDIT            │
  │   legal_workflow.py lines 281-319 (the helper)                │
  │     • Helper signature:                                       │
  │         _audit(event_type, entity_type, entity_id,            │
  │                user=None, payload=None,                       │
  │                deal_id=None, customer_id=None)                │
  │     • Builds a 12-field record at helper level:               │
  │         id, type, entity_type, entity_id, deal_id,            │
  │         customer_id, user_id, user_email, user_role,          │
  │         payload, at (ISO), ts (datetime)                      │
  │     • Inserts atomically. try/except SWALLOWS exception with  │
  │       a logger.warning — never blocks the business path.      │
  │     • Called by ~16 caller sites across legal_workflow.py     │
  │       for every business-relevant deal lifecycle event:       │
  │         deal.locked, deal.unlocked, deposit.created,          │
  │         deposit.refunded, auction.won, auction.lost,          │
  │         transfer.detected, transfer.applied, transfer.        │
  │         refused, refund.eligible, refund.rejected, ...        │
  ├──────────────────────────────────────────────────────────────┤
  │ Enqueue 2 — payments router stripe-webhook audit              │
  │   app/routers/payments.py line 487-503                         │
  │     • Direct insert inside the stripe-webhook handler         │
  │       AFTER persisting/recomputing the payment.               │
  │     • Builds a DIFFERENT 12-field record (NO ``entity_type``  │
  │       / ``entity_id`` / ``user_*`` / ``payload`` / ``at``):   │
  │         id, type, deal_id, payment_id, amount, currency,     │
  │         method, source, event_type, stripe_session_id,        │
  │         stripe_payment_intent, ts (ISO string, NOT datetime!) │
  │     • Inserts atomically. try/except SWALLOWS exception with  │
  │       a logger.exception — never blocks the webhook 200 OK.   │
  │     • Single caller — not wrapped in a helper.                │
  │     • Schema divergence is INTENTIONAL: the payment-webhook   │
  │       audit captures Stripe-side identifiers (session_id,     │
  │       payment_intent) that have no place in the domain-       │
  │       business 12-field shape.                                │
  └──────────────────────────────────────────────────────────────┘

The boot/startup INDEX context
-------------------------------

::

  Boot — index ensuring at startup
    server.py lines 2476-2487 (inside the lifespan startup block)
      • 6 indexes ensured idempotently (no `if not exists` —
        Motor's create_index is idempotent at the driver level).
      • Wrapped in try/except that logs but does NOT halt boot.
      • Order matters for the unique sparse id index: it must
        coexist with documents that do NOT carry an id field
        (legacy migrations may have inserted such docs in pre-
        Phase-3 state — sparse=True permits this).
      • All 6 indexes are read-optimisation, not data integrity:
        the only data-integrity index is (id, unique=True,
        sparse=True), and even that one accommodates pre-id
        legacy documents.

The two admin read contexts
----------------------------

::

  Read 1 — admin general audit list with filters
    legal_workflow.list_audit_events (GET /legal/audit)
      • require_manager_or_admin gate.
      • 6 optional filter axes: deal_id, customer_id,
        entity_type, entity_id, type, user_email.
      • limit clamped to [1, 500]; default 100.
      • Sort by ts DESC.
      • Returns docs with _id projected out; ts datetime
        objects post-processed to ISO string after the
        Motor cursor materializes (legacy serialization
        quirk: the projection happens IN the router, NOT
        at the Mongo layer).

  Read 2 — deal-scoped audit trail
    legal_workflow.get_deal_audit_trail
      (GET /legal/deals/{deal_id}/audit)
      • require_manager_or_admin gate.
      • Single filter: deal_id == path.
      • limit clamped to [1, 500]; default 200 (NOTE: different
        from list_audit_events default 100 — preserved).
      • Sort by ts DESC.
      • Same ts post-processing.
      • Returns same shape envelope with "deal_id" echoed.

Inventory vs Ownership Map (per midpoint methodology §3.2)
-----------------------------------------------------------

::

  Field                           | Value
  --------------------------------|------------------------------
  Map row                          | NOT EXPLICITLY MAPPED in
                                   | PHASE5_1_OWNERSHIP_MAP.md
                                   | §1.3 — audit_events appears
                                   | only in §1.5 ("collections
                                   | not yet scoped"). C-11 is
                                   | the first formal ownership
                                   | decision on this collection.
  Owner candidate (C-11 verdict)   | legal_workflow.py (helper
                                   | dominates write topology;
                                   | payments.py shares an
                                   | enqueue context but does NOT
                                   | own the domain semantics)
  Static AST result                | 4 raw Motor sites in 2 files
                                   | (1 R + 2 W + 1 index-bootstrap
                                   | + 1 read in legal_workflow.py)
                                   | + 6 index creates in server.py
                                   | + 1 W in payments.py
                                   | (3 sites total in 3 files).
  Writer contexts (lifecycle)      | 2 enqueue + 1 boot-INDEX.
                                   | Helper-mediated: ~16 logical
                                   | callers collapsed onto 1
                                   | helper.
  Reader contexts                  | 2 admin (filter-list +
                                   | deal-trail).
  Cross-domain WRITE in own owner  | 0 inside legal_workflow.py
                                   | (the helper only touches
                                   | audit_events).
  Cross-domain WRITE from outside  | 1 — payments router
                                   | (app/routers/payments.py
                                   | stripe-webhook audit).
                                   | This is a SECOND
                                   | cross-domain WRITE drift
                                   | (after C-10's server.py
                                   | password-reset write to
                                   | email_outbox).
  Adjacent infra (audit_LOG)       | 8+ direct writes in 3 files
                                   | to the SIBLING collection
                                   | (audit_log). Documented
                                   | in §1.2; NOT extracted in
                                   | C-11. The "dual audit
                                   | schema" tension is REAL
                                   | and architecturally
                                   | significant — see §1.2.
  Verdict                          | CONFIRMED (the FIRST
                                   | extraction with NO PRIOR
                                   | MAP ENTRY — C-11 produces
                                   | the map row from inventory,
                                   | not the other way around)
                                   | WITH a Type I cross-domain
                                   | WRITE (payments router)
                                   | AND a Type V tension (dual
                                   | audit schema with sibling
                                   | audit_log — NEW tension
                                   | type, see §1.2).

§1.2 — The sibling ``audit_log`` collection (DOCUMENTED, NOT EXTRACTED)
----------------------------------------------------------------------

C-11 mandate is **explicit**: extract ONLY ``db.audit_events``.
The sibling ``db.audit_log`` is documented here as part of the
inventory, but **deliberately not touched**.

Why this matters: ``audit_events`` and ``audit_log`` coexist
in the same Mongo database and serve overlapping but distinct
purposes:

| Collection | Concern | Writer modules | Shape | Indexes |
|------------|---------|----------------|-------|---------|
| ``audit_events`` | Domain-business audit (legal/payment lifecycle) | ``legal_workflow.py`` (helper, ~16 callers), ``app/routers/payments.py`` (stripe webhook) | 12-field structured (entity_type/entity_id/deal_id/customer_id/payload) | 6 indexes (entity/deal/customer/type/ts/id-unique) |
| ``audit_log`` | Security audit (auth + cross-cutting) | ``server.py`` (3+ direct sites + ``server.audit()`` helper), ``transfer_detector.py`` (``_audit`` helper) | 4-8-field free-form (action/resource/meta/ip) | 1 index (TTL or ts — confirmed via server.py:2315) |

The **dual audit schema** is the architecturally significant
finding of C-11. It is NOT a drift to be cleaned up; it is a
**load-bearing semantic distinction**:

- ``audit_events`` answers "what happened to *this deal* / *this
  payment* / *this entity*?" — used by accountancy, legal
  disputes, customer service.
- ``audit_log`` answers "who logged in, who tried to brute-
  force HMAC, who detected a transfer?" — used by ops /
  security incident response.

Merging them would lose the per-deal index, lose the entity
model, and force the security audit into a domain shape it
does not own. **NOT a Phase 5 concern.** A future audit
service (Phase 6+ Production Hardening territory, NOT
Phase 5.4) may unify them behind a single facade; until then,
each collection has its own ownership boundary.

C-11 freezes this state into the architecture by:
1. Naming ``AuditEventsRepository`` (NOT ``AuditRepository``) —
   the specificity prevents future confusion.
2. Writing this §1.2 explicitly into the docstring.
3. Documenting in PHASE5_3_C11_CLOSED.md as a NEW Type V
   tension (dual-schema sibling collections) added to the
   §2 taxonomy.

Business operations (named verbs that EXPOSE the topology)
-----------------------------------------------------------

Two distinct enqueue verbs — one per source concern, one per
divergent shape — even though both end in the same
``insert_one`` primitive. The naming makes the multi-concern
multi-shape topology visible at the repository contract:

* ``record_domain_event(record)`` —
    accepts the 12-field ``legal_workflow._audit()`` shape
    verbatim. Caller (the helper at ``legal_workflow.py:281``)
    composes the entire shape including the deterministic
    ``id = f"audit_{ts_ms}_{uuid8}"`` derivation, the dual
    timestamp encoding (``at`` ISO + ``ts`` datetime),
    and the user/payload optional fields. Repository does
    NOT inject or validate.
* ``record_payment_webhook_event(record)`` —
    accepts the 12-field payments-router stripe-webhook shape
    verbatim. Caller composes the entire shape including the
    Stripe-side identifiers (``stripe_session_id``,
    ``stripe_payment_intent``) and the single-string ``ts``
    (ISO, not datetime — divergent from concern 1!).
    Repository does NOT inject or validate.
* ``ensure_indexes()`` —
    Creates the 6 indexes documented above. Idempotent
    (Motor ``create_index`` is). Called from the
    ``server.py`` startup lifespan block. Returns ``None``.
    No raise on conflict (legacy preserved behaviour).

And two read verbs (one per legacy reader, both in
``legal_workflow.py``):

* ``list_filtered(*, deal_id=None, customer_id=None,
  entity_type=None, entity_id=None, type=None,
  user_email=None, limit=100)`` —
    Admin general audit list. Sort by ``ts`` DESC.
    Six optional filter axes (truthiness-checked None-or-empty,
    matching legacy). limit clamped to [1, 500].
    ``_id`` projected out. **Does NOT post-process ts** — that
    serialization quirk stays at the router caller (the
    repository returns the raw cursor result; the router
    converts datetime → ISO string before returning JSON).
* ``list_for_deal(deal_id, *, limit=200)`` —
    Deal-scoped audit trail. Single filter (deal_id == arg).
    Sort by ``ts`` DESC. limit clamped to [1, 500] (default
    differs from list_filtered — 200 vs 100; preserved).
    Same ``_id`` projection, same lack of ts post-processing.

**5 named verbs.** "Cluster" band of the §6.3 morphology
observation — verb count matches lifecycle-category count
(2 enqueue + 1 boot + 2 read).

Vocabulary continuity vs prior 10 repositories:

* ``record_domain_event``        — NEW verb name. Lifecycle-shaped (same family as C-10's ``record_email_send_*`` and ``record_auth_email_audit``).
* ``record_payment_webhook_event`` — NEW verb name. Same family.
* ``ensure_indexes``              — REPEATS C-5 (``InvoiceTemplateRepository.ensure_indexes(db)``). Same semantics: idempotent index ensuring at boot. The vocabulary repetition CONFIRMS that the verb name carries semantic load across collections (not just structural).
* ``list_filtered``               — REPEATS C-8 (``EmailTemplateRepository.list_filtered``). Different filter axes but identical semantics (multi-axis truthiness-checked filter with limit cap).
* ``list_for_deal``               — NEW verb name. Single-axis filter, similar shape to C-9's ``find_by_event`` but returns a list, not a single doc. Domain-specific name (deal_id is THE canonical scope-axis for audit_events).

**3 NEW verbs + 2 REPEATED verbs.** Mixed continuity, matching
the methodology rule from C-10 §6.3 observation 7: lifecycle-
shaped verbs do not share names with CRUD-shaped verbs, BUT
verbs whose semantics ARE truly identical (``ensure_indexes``,
``list_filtered``) can repeat across the divide.

Legacy quirks preserved 1:1
---------------------------

* The helper at ``legal_workflow._audit()`` builds the id deterministically as ``f"audit_{int(ts_ms)}_{uuid4_hex[:8]}"``. The unique sparse index on ``id`` accommodates this (it could collide only with millisecond-precision + 8-char-hex collision, which is astronomically unlikely). Preserved.
* The two enqueue shapes use INCOMPATIBLE timestamp encodings:
    - ``record_domain_event``: BOTH ``at`` (ISO string) AND ``ts`` (datetime object) — the helper writes both.
    - ``record_payment_webhook_event``: only ``ts`` (ISO string, not datetime!).
  This inconsistency is **load-bearing**: the router converts ``ts`` datetime → ISO string before returning JSON, which means if the payment webhook had used datetime, the response shape would be identical, BUT the indexes (which sort by raw BSON ``ts``) treat string and datetime differently. Sorting mixes BSON types per BSON canonical ordering; the legacy collection has lived with this for the entire pre-Phase-5 era. Preserved 1:1.
* Both write paths swallow exceptions silently. The audit MUST NEVER block the business path. Preserved 1:1. The repository does NOT raise differently for any error.
* No unique constraint on (entity_type, entity_id) — multiple events per entity is correct. The only unique constraint is on ``id``, sparse to allow legacy records without an id.
* The legacy reader endpoints do NOT use ``record_domain_event`` for self-tests — there is no synthetic-event admin endpoint. The audit is **append-only via business workflows**, never via direct admin write. C-11 preserves this: NO ``insert`` / ``save`` / ``upsert`` / ``mark_*`` escape hatch on the surface.
* ``list_audit_events`` (the router endpoint) has a quirk: it returns the filter dict (``"filters": q``) back to the client, allowing the UI to display what filter was applied. Preserved at the router layer — the repository returns only the cursor result.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``insert`` / ``save`` / ``upsert`` escape hatch.
*  No update / patch / delete / soft-delete primitives.
*  No worker spawn / no dispatcher.
*  No retry primitive.
*  No TTL / cleanup primitive (audit is forever).
*  No state-machine abstraction.
*  No doc-shape normalization across the two enqueue verbs.
*  No HTTP exceptions (audit MUST NEVER raise into the
   business path).
*  No event emission / Socket.IO / event bus.
*  No id generation (the helper composes the id; the repo
   accepts it verbatim).
*  No timestamp injection.
*  No touch on ``db.audit_log`` (the sibling — separate
   ownership, separate concern, separate schema).
*  No touch on ``db.deals`` / ``db.payments`` /
   ``db.customers`` / any other collection that audit_events
   references via foreign keys.
*  No BaseRepository / BaseAuditRepository / AuditService /
   AuditFacade.
*  No Phase 5.4 work — the cross-domain WRITE from
   ``payments.py`` stays at the router endpoint. Only the
   verb NAME at the repository surface changes.
*  No relocation of the boot index creation — ``ensure_indexes``
   lives in the repository, but the CALL still happens at the
   server.py startup site (just renamed from inline
   ``await db.audit_events.create_index(...)`` to
   ``await AuditEventsRepository(db).ensure_indexes()``).
*  No merging with ``audit_log`` (mandate forbidden).
*  No taxonomy cleanup (mandate forbidden — the legacy
   ``type`` field uses both ``"deal.locked"`` dot-notation
   and ``"payment.confirmed"`` style; preserved as-is).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List


class AuditEventsRepository:
    """Owner of ``db.audit_events`` (append-only domain-business
    audit trail for legal/payment lifecycle events).

    Three caller contexts instantiate the repository:
    ``legal_workflow._audit()`` helper (~16 logical callers
    collapsed through the helper), the stripe-webhook handler
    in ``app/routers/payments.py``, and the two admin read
    endpoints (general filter-list + deal-scoped trail). C-11
    wires all of them to the repository while preserving the
    distinct legacy shapes and the helper's mediation role.

    The companion collection ``db.audit_log`` is documented
    in the module docstring §1.2 but is NOT in scope for C-11.
    """

    COLLECTION = "audit_events"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Boot — index ensuring (1 lifecycle context)
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        """Ensure the 6 production indexes on ``audit_events``.

        Idempotent — Motor ``create_index`` is. Called from
        ``server.py`` startup lifespan; legacy preserved
        behaviour swallows any conflict (returns ``None`` on
        all error paths — the repository does NOT raise).

        Indexes (all preserved verbatim from
        ``server.py:2481-2486``):

        * ``[("ts", -1)]`` — recency scans.
        * ``[("deal_id", 1), ("ts", -1)]`` — per-deal trail.
        * ``[("customer_id", 1), ("ts", -1)]`` — per-customer trail.
        * ``[("entity_type", 1), ("entity_id", 1), ("ts", -1)]``
          — per-entity trail.
        * ``[("type", 1), ("ts", -1)]`` — per-event-type trail.
        * ``[("id", 1)]`` unique, sparse — dedup by id (sparse
          to accommodate pre-id legacy documents).
        """
        coll = self._db[self.COLLECTION]
        try:
            await coll.create_index([("ts", -1)])
            await coll.create_index([("deal_id", 1), ("ts", -1)])
            await coll.create_index([("customer_id", 1), ("ts", -1)])
            await coll.create_index([("entity_type", 1), ("entity_id", 1), ("ts", -1)])
            await coll.create_index([("type", 1), ("ts", -1)])
            await coll.create_index([("id", 1)], unique=True, sparse=True)
        except Exception:
            # Legacy behaviour: log-and-swallow at the caller layer.
            # The repository itself NEVER raises on index conflict.
            pass

    # ------------------------------------------------------------------
    # Enqueue (write) — two distinct verbs reflecting two distinct
    # source concerns and two divergent doc shapes
    # ------------------------------------------------------------------

    async def record_domain_event(self, record: Dict[str, Any]) -> None:
        """Insert a domain-business audit event.

        Mirrors the body of ``legal_workflow._audit()`` (lines
        281-319 of ``legal_workflow.py``). Caller (the helper)
        composes the 12-field shape verbatim including the
        deterministic id, the dual timestamp (``at`` ISO +
        ``ts`` datetime), the entity model (``entity_type`` +
        ``entity_id``), the optional user model
        (``user_id`` / ``user_email`` / ``user_role``),
        the optional ``deal_id`` / ``customer_id`` scopes,
        and the free-form ``payload``. Repository does NOT
        inject or validate. Terminal-at-insert.

        The caller's try/except SWALLOWS the exception
        (audit must never block business). The repository's
        ``insert_one`` may raise; the swallow is at the
        helper layer, NOT here.
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_payment_webhook_event(self, record: Dict[str, Any]) -> None:
        """Insert a payment-webhook audit event.

        Mirrors the body of the stripe-webhook audit insert
        at ``app/routers/payments.py:488``. Caller composes
        the 12-field shape verbatim including Stripe-side
        identifiers (``stripe_session_id``, ``stripe_payment_intent``)
        and the single-string ``ts`` (ISO, not datetime —
        divergent from ``record_domain_event``).
        Repository does NOT inject or validate. Terminal-at-
        insert.

        **This verb's existence makes the cross-domain WRITE
        visible in the repository API.** The payments router
        writes into a collection owned by the legal/audit
        family; collapsing this into ``record_domain_event``
        would hide the source-concern drift. Phase 5.4+ may
        relocate this write to a dedicated PaymentAudit
        boundary; until then the verb name SURFACES the
        cross-domain origin.
        """
        await self._db[self.COLLECTION].insert_one(record)

    # ------------------------------------------------------------------
    # Read — admin audit
    # ------------------------------------------------------------------

    async def list_filtered(
        self,
        *,
        deal_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        type: Optional[str] = None,
        user_email: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Admin general audit list with up to 6 optional filters.

        Mirrors ``legal_workflow.list_audit_events`` (line 1934).
        Truthiness-checked filter axes (None-or-empty treated
        as absent). Sort by ``ts`` DESC. ``_id`` projected out.
        limit clamped to [1, 500].

        **Does NOT post-process ts** — returns the raw cursor
        materialization (datetime objects intact). The router
        caller is responsible for the datetime → ISO string
        conversion before JSON encoding. This split preserves
        the legacy boundary: the repository owns Mongo round-
        trips; the router owns response serialization.
        """
        q: Dict[str, Any] = {}
        if deal_id:
            q["deal_id"] = deal_id
        if customer_id:
            q["customer_id"] = customer_id
        if entity_type:
            q["entity_type"] = entity_type
        if entity_id:
            q["entity_id"] = entity_id
        if type:
            q["type"] = type
        if user_email:
            q["user_email"] = user_email

        limit = max(1, min(int(limit), 500))
        cursor = (
            self._db[self.COLLECTION]
            .find(q, {"_id": 0})
            .sort("ts", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def list_for_deal(
        self,
        deal_id: str,
        *,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Deal-scoped audit trail.

        Mirrors ``legal_workflow.get_deal_audit_trail`` (line 1974).
        Single filter (``deal_id`` == arg). Sort by ``ts`` DESC.
        ``_id`` projected out. limit clamped to [1, 500] — note
        the default is 200 (NOT 100 like ``list_filtered``);
        preserved verbatim.

        Same lack of ts post-processing as ``list_filtered`` —
        the router converts datetime → ISO before returning.
        """
        limit = max(1, min(int(limit), 500))
        cursor = (
            self._db[self.COLLECTION]
            .find({"deal_id": deal_id}, {"_id": 0})
            .sort("ts", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)


__all__ = ["AuditEventsRepository"]
