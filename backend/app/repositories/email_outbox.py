"""
EmailOutboxRepository — Phase 5.3 / C-10.
=========================================

Canonical owner of the ``db.email_outbox`` Mongo collection.

**This is the first C-10-class repository.** Eight prior
repositories (C-1..C-9) extracted CRUD/admin/boot-seed-shaped
ownership boundaries. C-10 was opened by the architect with
the explicit mandate to expose **dispatch-shaped ownership**
— a collection whose writer topology is driven by execution
flow (queue / retry / delivery lifecycle) rather than human
admin actions or boot seeding.

The inventory, however, did not find what the mandate
anticipated. It found something **different and equally
important**: the collection is NOT a transactional outbox.

What the collection actually is
-------------------------------

::

  db.email_outbox  =  append-only heterogeneous audit log
                      of outbound-message ATTEMPTS,
                      written by TWO unrelated concern-spaces
                      with TWO divergent document shapes,
                      with NO worker, NO retry, NO TTL,
                      NO state transitions after insert.

Every document is **terminal-at-insert**. The ``status`` field
is set once during the same insert that creates the document
(``"dry_run"`` for the no-provider path; ``"sent"``/
``"failed"`` after the Resend HTTP call returns, BEFORE the
document is inserted). There is no pending/queued state that
a worker later flips. There is no retry that re-flips a
status. There is no cleanup that purges by age. There is no
``find_one_and_update`` pattern; in fact there is no UPDATE
on this collection anywhere in the codebase.

Lifecycle-context classification (per architect's C-10
mandate, not the prior CRUD-shaped reader/writer dichotomy)
-----------------------------------------------------------

::

  Category                    | Sites found
  ────────────────────────────┼──────────────────────────────
  enqueue contexts            | 3
  dispatch contexts           | 0 — no worker reads the outbox
  retry contexts              | 0
  failure contexts (lifecycle)| 0 — status="failed" is set
                              |     inline at insert in the
                              |     resend branch; the document
                              |     is NEVER re-attempted
  success/finalization        | terminal-at-insert
  cleanup/TTL contexts        | 0
  boot/startup contexts       | 0
  worker contexts             | 0
  ────────────────────────────┴──────────────────────────────

Of the 8 lifecycle categories the architect's C-10 mandate
listed, **only one (enqueue) has any sites at all**. There is
no execution flow that owns this collection — only three
unrelated synchronous write sites that drop a record-of-what-
happened immediately after the corresponding side-effect (or
attempted side-effect).

The three enqueue contexts (writer topology)
---------------------------------------------

::

  ┌──────────────────────────────────────────────────────────────┐
  │ Enqueue 1 — EmailChannel.send dry-run branch                  │
  │   notifications.EmailChannel.send (legacy line 141)           │
  │     • Called from NotificationService.dispatch when           │
  │       a rule.target hits the "email" channel AND               │
  │       no RESEND_API_KEY is configured (dry_run provider).     │
  │     • Builds a 9-field record:                                │
  │         id, to, subject, html, text, provider, event,         │
  │         context, status (="dry_run"), created_at              │
  │     • Inserts atomically — status is set BEFORE the insert.   │
  │     • Returns synchronously to the dispatch caller.           │
  ├──────────────────────────────────────────────────────────────┤
  │ Enqueue 2 — EmailChannel.send resend branch                   │
  │   notifications.EmailChannel.send (legacy line 172)           │
  │     • Same caller, different branch — fires when               │
  │       RESEND_API_KEY is configured.                           │
  │     • Makes an httpx POST to Resend BEFORE inserting.         │
  │     • Builds the SAME 9-field record + 1-3 outcome fields:    │
  │         + provider_response  (on success / partial)           │
  │         + provider_status    (HTTP code)                      │
  │         + provider_error     (on httpx exception)             │
  │       status = "sent" if HTTP < 300 else "failed".            │
  │     • Insert is wrapped in try/except — outbox-insert failure │
  │       is logged but NOT propagated. The send result still     │
  │       returns based on the provider HTTP outcome, not the     │
  │       outbox write outcome.                                   │
  ├──────────────────────────────────────────────────────────────┤
  │ Enqueue 3 — server.py password-reset DRY-RUN audit            │
  │   server.py:11012 inside                                       │
  │     customer-auth/request-password-reset endpoint             │
  │     • COMPLETELY UNRELATED to NotificationService.            │
  │     • Bypasses EmailChannel entirely. Writes a DIFFERENT      │
  │       8-field doc shape:                                       │
  │         to, subject, body (NOT html/text), mode (NOT          │
  │         provider), template (NOT event), status, created_at,  │
  │         meta (NOT context)                                    │
  │     • NO ``id`` field — relies on Mongo-generated _id.        │
  │     • NO ``event`` field — uses ``template`` instead.         │
  │     • NO ``provider`` field — uses ``mode`` instead.          │
  │     • Wrapped in try/except — failure logged, not propagated. │
  │     • This is the DRIFT documented in                          │
  │       PHASE5_1_OWNERSHIP_MAP.md §1.3                          │
  │       (``server.py 1 w — drift!``). It is real, it is         │
  │       cross-domain, and it is NOT solved by C-10.             │
  └──────────────────────────────────────────────────────────────┘

The one read context
--------------------

::

  Read 1 — admin audit view
    notifications.list_email_outbox (router endpoint, legacy
    line 1141)
      • GET /api/admin/email-outbox?event=&status=&limit=100
      • require_admin guard.
      • find(q).sort("created_at", -1).limit(limit).
      • _id projected out. Returns heterogeneous shapes —
        the admin UI receives both EmailChannel records
        (with html/event/provider) AND password-reset
        records (with body/template/mode) mixed together.
      • Optional filters: event (string match on the field —
        works only for EmailChannel records, password-reset
        records have NO event field), status.

Inventory vs Ownership Map (per midpoint methodology §3.2)
-----------------------------------------------------------

| Field                           | Value                                                                                                              |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------|
| Map row (§1.3)                  | ``email_outbox``: 6 ops, owner=notifications.py (clean!), writers=notifications.py (4w), **server.py (1w — drift!)**, readers=—, phase=5.3 |
| Static AST result               | **4 raw Motor sites** (1 R + 3 W). 3 writes in 2 files (notifications.py × 2, server.py × 1).                       |
| Writer contexts (lifecycle)     | 3 enqueue contexts (1 dry-run, 1 resend, 1 password-reset). 0 dispatch / 0 retry / 0 worker / 0 cleanup / 0 boot.   |
| Reader contexts                 | 1 (admin audit list with optional event/status filter and limit).                                                  |
| Cross-domain WRITE in own owner | 0 inside ``notifications.py``.                                                                                     |
| Cross-domain WRITE from outside | **1 — ``server.py:11012`` password-reset audit write.** This is the drift flagged by the map; C-10 confirms it as a real Type I cross-domain WRITE with a DIVERGENT doc shape. |
| Cross-domain READ in own owner  | 0.                                                                                                                  |
| Adjacent infra                  | 0.                                                                                                                  |
| **Verdict**                     | **CONFIRMED with drift (Type I cross-domain WRITE — first such finding since C-4 ``provider_stats → orders``).** Map prediction of the drift was correct; reality matches; deferred to Phase 5.4 (PasswordReset / Auth domain extraction). |

The map called the drift four months ago. C-10 confirms it
exists, characterises its shape (heterogeneous doc), and
defers its resolution to Phase 5.4.

Why this collection is NOT renamed / split / unified
-----------------------------------------------------

C-10 deliberately does NOT:

* Split the collection into two (``email_outbox_dispatch`` +
  ``email_outbox_auth``) — that would be a schema migration,
  which is forbidden in 5.3.
* Normalise the doc shapes (forbidden by mandate — "no DTO /
  Pydantic normalization").
* Migrate the ``server.py`` write into ``EmailChannel.send`` —
  that would change BEHAVIOR (the password-reset write does
  NOT do a Resend HTTP call even when ``RESEND_API_KEY`` is
  set; it is a dry-run-only audit, distinct from the email
  dispatch path).
* Introduce a queue abstraction (forbidden by mandate — "no
  queue abstraction / no OutboxService / no dispatcher
  framework").
* Build a state machine over the ``status`` field (forbidden
  by mandate — "no delivery state machine abstraction").

The collection's heterogeneous shape **is the
architecturally important fact**. Hiding it behind a unified
DTO would erase the topology that C-10 just exposed.

Business operations (named verbs that EXPOSE the topology)
-----------------------------------------------------------

Three distinct enqueue verbs — one per legacy call site —
even though all three end in the same ``insert_one`` primitive.
The naming makes the multi-writer-cross-domain topology
visible at the repository contract:

* ``record_email_send_dry_run(record)`` —
    accepts the 9-field EmailChannel dry-run record verbatim.
    Caller composes the entire shape (including the
    deterministic ``id = uuid4()`` and ``status = "dry_run"``).
    Repository does NOT inject or validate. Mirrors legacy
    line 141.
* ``record_email_send_attempt(record)`` —
    accepts the 9-to-12-field EmailChannel resend record
    verbatim, including the optional provider-outcome
    fields (``provider_response``, ``provider_status``,
    ``provider_error``). Caller composes the entire shape.
    Repository does NOT inject or validate. Mirrors legacy
    line 172.
* ``record_auth_email_audit(record)`` —
    accepts the 8-field server.py password-reset record
    verbatim. Caller composes the entire shape. The verb
    NAME makes the cross-domain origin visible (this is the
    drift). Mirrors legacy line 11012. **This verb is
    explicitly NOT collapsed into ``record_email_send_*``
    because the doc shape, the upstream concern, and the
    legacy site are all distinct.** Phase 5.4 will likely
    relocate this write to a future Auth/PasswordReset
    repository — at which point this verb removes from the
    surface and the cross-domain write becomes intra-domain.

And one read verb:

* ``list_recent(*, event=None, status=None, limit=100)`` —
    admin audit list. Sort by ``created_at`` DESC. Optional
    ``event`` and ``status`` filters (truthiness-checked
    empty strings, as legacy did). ``_id`` projected out.
    Returns heterogeneous shapes — the repository does NOT
    discriminate by doc family. Mirrors legacy line 1146.

**4 named verbs.** The verb-count-proportional-to-context-count
rule from §6.3 observation 1 holds (4 verbs for 3 enqueue
contexts + 1 read context). BUT the verbs are NOT shared with
any prior repository — the lifecycle-shaped enqueue verbs are
semantically distinct from C-8/C-9's CRUD-shaped
upsert/insert/bulk_create verbs.

Legacy quirks preserved 1:1
---------------------------

* The collection has **no unique index** on any field.
  Concurrent writes can produce duplicate records; legacy
  accepts this because every write is an audit record, not
  a deduplicated entity.
* The EmailChannel records use ``id`` (uuid4) as their
  identifier; the password-reset records do NOT — they rely
  on Mongo ``_id``. Both projection-out ``_id`` on read,
  which means a password-reset record returned from
  ``list_recent`` has NO stable identifier visible to the
  admin UI. Preserved.
* EmailChannel records use ``html`` + ``text`` for the body;
  password-reset records use a single ``body`` field.
  Preserved.
* EmailChannel records use ``event`` (NotificationService
  event name); password-reset records use ``template``
  (a different field name with a different vocabulary).
  Preserved.
* EmailChannel records use ``provider`` (``"resend"`` or
  ``"dry_run"``); password-reset records use ``mode``
  (settings.auth.email.mode). Preserved.
* EmailChannel records use ``context`` (dispatch ctx dict);
  password-reset records use ``meta`` (``{reset_token,
  customerId}``). Preserved.
* The status enum is heterogeneous: ``"dry_run"``,
  ``"sent"``, ``"failed"`` are valid for EmailChannel
  records; only ``"dry_run"`` is set for password-reset
  records today (the production resend path for
  password-reset doesn't exist yet — the legacy comment
  ``# Future: plug into Resend/SMTP based on
  settings.email.mode`` confirms it is dry-run-only).
  Preserved.
* The resend insert at L172 is wrapped in try/except — an
  outbox-insert exception is logged and swallowed, the
  send result is NOT affected. Preserved. The repository
  does NOT raise differently for any error path.

What this repository does NOT do (deliberately)
-----------------------------------------------

*  No generic ``insert`` / ``save`` escape hatch.
*  No update / patch / soft-delete primitives.
*  No worker spawn / no dispatcher.
*  No retry primitive — there is no retry in legacy.
*  No TTL / cleanup primitive — there is no cleanup in legacy.
*  No state-machine abstraction over ``status``.
*  No doc-shape normalization across the three enqueue
   verbs.
*  No discrimination of doc family on read.
*  No HTTP exceptions.
*  No event emission / audit / Socket.IO.
*  No id generation (caller composes ``id`` if it uses one).
*  No timestamp injection (caller composes ``created_at``).
*  No touch on ``db.email_templates``, ``db.notification_rules``,
   ``db.notifications`` (sibling collections in the
   notification family — independently owned by C-8 / C-9 /
   future C-N).
*  No BaseRepository / BaseOutbox / OutboxService.
*  No Phase 5.4 work — the password-reset cross-domain write
   stays at ``server.py:11012`` and is documented as the
   Phase 5.4 entry point. Only the verb NAME at the
   repository surface changes (to ``record_auth_email_audit``)
   — the call site remains where legacy put it.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class EmailOutboxRepository:
    """Owner of ``db.email_outbox`` (append-only outbound-message
    audit log).

    Three caller contexts instantiate the repository ad-hoc:
    ``EmailChannel`` (notification dispatch, two enqueue
    branches), the password-reset endpoint in ``server.py``
    (auth concern, the drift), and the admin list endpoint
    (audit read). C-10 wires all three to the repository while
    preserving their distinct legacy shapes.
    """

    COLLECTION = "email_outbox"

    def __init__(self, db: Any) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Enqueue (write) — three distinct verbs reflecting three distinct
    # legacy call sites and three divergent doc shapes
    # ------------------------------------------------------------------

    async def record_email_send_dry_run(self, record: Dict[str, Any]) -> None:
        """Insert a dry-run send record.

        Mirrors legacy line 141 of ``notifications.py``
        (``EmailChannel.send`` dry-run branch). Caller composes
        the 9-field shape verbatim; repository does NOT inject
        or validate. Terminal-at-insert: ``status="dry_run"`` is
        already set by the caller.
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_email_send_attempt(self, record: Dict[str, Any]) -> None:
        """Insert a real-send-attempt audit record.

        Mirrors legacy line 172 of ``notifications.py``
        (``EmailChannel.send`` resend branch). Caller composes
        the 9-to-12-field shape verbatim, including the
        provider outcome fields populated AFTER the Resend HTTP
        call returned. Repository does NOT inject or validate.
        Terminal-at-insert: ``status`` is already
        ``"sent"`` or ``"failed"`` at the time of this call.
        """
        await self._db[self.COLLECTION].insert_one(record)

    async def record_auth_email_audit(self, record: Dict[str, Any]) -> None:
        """Insert a password-reset / auth-flow email audit record.

        Mirrors legacy line 11012 of ``server.py``. Caller
        composes the 8-field shape verbatim (different from the
        EmailChannel shape — see module docstring for details).
        Repository does NOT inject or validate. Terminal-at-
        insert.

        **This verb's existence makes the documented drift
        visible in the repository API.** ``PHASE5_1_OWNERSHIP_MAP.md
        §1.3`` flagged ``server.py 1w — drift!`` on this
        collection from day one; C-10 confirms the drift is
        real (different doc shape, different concern domain,
        different call-site file) and defers resolution to
        Phase 5.4 (PasswordReset / Auth domain extraction).
        The call site itself stays at ``server.py:11012`` —
        only the verb NAME changes from ``db.email_outbox.insert_one``
        to ``repo.record_auth_email_audit``.
        """
        await self._db[self.COLLECTION].insert_one(record)

    # ------------------------------------------------------------------
    # Read — admin audit
    # ------------------------------------------------------------------

    async def list_recent(
        self,
        *,
        event: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """Admin audit list — sort by ``created_at`` DESC.

        Mirrors legacy line 1146 of ``notifications.py``.
        Optional filters by ``event`` and ``status``
        (empty-string treated as absent, matching legacy
        truthiness check). ``_id`` projected out.

        Returns heterogeneous shapes — EmailChannel records
        and password-reset records are returned MIXED. The
        repository does NOT discriminate by doc family; the
        admin UI handles the heterogeneity (or fails to —
        either way, the legacy behaviour is preserved 1:1).
        """
        q: Dict[str, Any] = {}
        if event:
            q["event"] = event
        if status:
            q["status"] = status
        cursor = (
            self._db[self.COLLECTION]
            .find(q, {"_id": 0})
            .sort("created_at", -1)
            .limit(int(limit))
        )
        return await cursor.to_list(length=int(limit))


__all__ = ["EmailOutboxRepository"]
