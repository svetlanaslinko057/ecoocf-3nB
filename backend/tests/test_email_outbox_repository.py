"""
Phase 5.3 / C-10 — EmailOutboxRepository unit contract tests.
=============================================================

The FIRST C-10-class test suite: scenarios are organised by
LIFECYCLE-CONTEXT rather than by CRUD method. Each enqueue
verb is tested with the EXACT doc shape its legacy caller
composes, including the divergent shape between
NotificationService.EmailChannel records and the
server.py password-reset records.

Run:
    cd /app/backend && python tests/test_email_outbox_repository.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.repositories import EmailOutboxRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "email_outbox_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[EmailOutboxRepository.COLLECTION].drop()
    return client, db


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _email_dry_run_record(**overrides) -> dict:
    """Reproduce the EmailChannel.send dry-run shape (legacy line 141, 9
    fields)."""
    rec = {
        "id":         str(uuid.uuid4()),
        "to":         "customer@example.com",
        "subject":    "Welcome",
        "html":       "<p>Welcome</p>",
        "text":       "Welcome",
        "provider":   "dry_run",
        "event":      "lead.created",
        "context":    {"lead_id": "lead_123"},
        "status":     "dry_run",
        "created_at": _iso(),
    }
    rec.update(overrides)
    return rec


def _email_attempt_record(*, sent: bool = True, **overrides) -> dict:
    """Reproduce the EmailChannel.send resend shape (legacy line 172,
    9-12 fields)."""
    rec = {
        "id":               str(uuid.uuid4()),
        "to":               "customer@example.com",
        "subject":          "Welcome",
        "html":             "<p>Welcome</p>",
        "text":             "Welcome",
        "provider":         "resend",
        "event":            "lead.created",
        "context":          {"lead_id": "lead_123"},
        "status":           "sent" if sent else "failed",
        "created_at":       _iso(),
        "provider_response": {"id": "msg_xyz"} if sent else {},
        "provider_status":  200 if sent else 503,
    }
    rec.update(overrides)
    return rec


def _auth_audit_record(**overrides) -> dict:
    """Reproduce the server.py password-reset shape (legacy line 11012,
    8 fields — NO id, NO event, NO context, NO provider, NO html/text,
    different field names: body/mode/template/meta)."""
    rec = {
        "to":         "user@example.com",
        "subject":    "BIBI Cars — Password reset",
        "body":       "Click the link...",
        "mode":       "dry_run",
        "template":   "reset_password",
        "status":     "dry_run",
        "created_at": datetime.now(timezone.utc),  # legacy uses datetime here, not iso!
        "meta":       {"reset_token": "tok_abc", "customerId": "cust_42"},
    }
    rec.update(overrides)
    return rec


# ----------------------------------------------------------------------
# Enqueue verbs — each preserves its legacy doc shape verbatim
# ----------------------------------------------------------------------

async def test_1_record_email_send_dry_run_persists_shape():
    """Verb writes the 9-field EmailChannel dry-run shape verbatim."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        record = _email_dry_run_record()
        await repo.record_email_send_dry_run(record)
        coll = db[EmailOutboxRepository.COLLECTION]
        doc = await coll.find_one({"id": record["id"]})
        # 9 user fields + _id auto = 10 keys
        assert set(doc.keys()) == {
            "_id", "id", "to", "subject", "html", "text",
            "provider", "event", "context", "status", "created_at",
        }
        assert doc["status"] == "dry_run"
        assert doc["provider"] == "dry_run"
        print("✓ test_1_record_email_send_dry_run_persists_shape")
    finally:
        client.close()


async def test_2_record_email_send_attempt_with_outcome():
    """Verb writes the resend shape including provider outcome fields."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        record = _email_attempt_record(sent=True)
        await repo.record_email_send_attempt(record)
        doc = await db[EmailOutboxRepository.COLLECTION].find_one({"id": record["id"]})
        assert doc["status"] == "sent"
        assert doc["provider"] == "resend"
        assert doc["provider_response"] == {"id": "msg_xyz"}
        assert doc["provider_status"] == 200
        print("✓ test_2_record_email_send_attempt_with_outcome")
    finally:
        client.close()


async def test_3_record_email_send_attempt_failed_branch():
    """Failed-send branch writes status='failed' with optional fields."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        record = _email_attempt_record(
            sent=False, provider_error="connection timeout"
        )
        record["provider_response"] = {}  # legacy sets empty on failure
        await repo.record_email_send_attempt(record)
        doc = await db[EmailOutboxRepository.COLLECTION].find_one({"id": record["id"]})
        assert doc["status"] == "failed"
        assert doc["provider_error"] == "connection timeout"
        print("✓ test_3_record_email_send_attempt_failed_branch")
    finally:
        client.close()


async def test_4_record_auth_email_audit_distinct_shape():
    """server.py password-reset shape is DIFFERENT from EmailChannel shape.

    No id, no event, no context, no provider, no html/text. Uses
    body / mode / template / meta instead. This test PINS the
    legacy-quirk shape divergence — if a future commit normalises the
    shape, this test will fail and the topology exposure is
    preserved.
    """
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        record = _auth_audit_record()
        await repo.record_auth_email_audit(record)
        coll = db[EmailOutboxRepository.COLLECTION]
        # Find by template — no id field to filter by!
        doc = await coll.find_one({"template": "reset_password"})
        assert doc is not None
        # Fields that EmailChannel records have but auth records do NOT
        for absent_field in ("id", "event", "context", "provider", "html", "text"):
            assert absent_field not in doc, (
                f"auth audit shape unexpectedly carries '{absent_field}' — "
                f"shape normalization is forbidden by C-10 mandate"
            )
        # Fields that ONLY auth records have
        for present_field in ("body", "mode", "template", "meta"):
            assert present_field in doc
        # Legacy quirk: auth uses datetime (BSON), EmailChannel uses ISO
        assert isinstance(doc["created_at"], datetime)
        assert doc["mode"] == "dry_run"
        print("✓ test_4_record_auth_email_audit_distinct_shape")
    finally:
        client.close()


async def test_5_three_enqueue_verbs_coexist_in_one_collection():
    """Heterogeneous shapes share the same collection — by design."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        await repo.record_email_send_dry_run(_email_dry_run_record())
        await repo.record_email_send_attempt(_email_attempt_record(sent=True))
        await repo.record_email_send_attempt(_email_attempt_record(sent=False))
        await repo.record_auth_email_audit(_auth_audit_record())
        coll = db[EmailOutboxRepository.COLLECTION]
        assert await coll.count_documents({}) == 4
        # Count by status — three statuses coexist
        assert await coll.count_documents({"status": "dry_run"}) == 2  # 1 email + 1 auth
        assert await coll.count_documents({"status": "sent"}) == 1
        assert await coll.count_documents({"status": "failed"}) == 1
        print("✓ test_5_three_enqueue_verbs_coexist_in_one_collection")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Append-only / terminal-at-insert verification
# ----------------------------------------------------------------------

async def test_6_enqueue_is_append_only_no_update():
    """Every write is a new document. The repository exposes no
    update/patch primitive — second 'enqueue' with same id creates
    a SECOND doc, not an update."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        fixed_id = "fixed_id_1"
        await repo.record_email_send_dry_run(_email_dry_run_record(id=fixed_id))
        await repo.record_email_send_dry_run(
            _email_dry_run_record(id=fixed_id, subject="V2")
        )
        coll = db[EmailOutboxRepository.COLLECTION]
        count = await coll.count_documents({"id": fixed_id})
        assert count == 2, (
            f"insert_one is append-only — expected 2 docs with the same id, "
            f"got {count}. Legacy outbox has NO unique index, dedup, or "
            f"upsert — preserved."
        )
        print("✓ test_6_enqueue_is_append_only_no_update")
    finally:
        client.close()


async def test_7_status_is_terminal_at_insert():
    """The repository has no verb to mutate `status` after insert.
    A 'failed' record stays failed; a 'sent' record stays sent."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        rid = "rec_42"
        await repo.record_email_send_attempt(
            _email_attempt_record(id=rid, sent=False)
        )
        # Read direct — confirm shape
        doc = await db[EmailOutboxRepository.COLLECTION].find_one({"id": rid})
        assert doc["status"] == "failed"
        # The repository surface offers NO 'mark_retried' / 'mark_sent_later'
        # / 'apply_outcome' verb. Confirm:
        forbidden = (
            "update", "patch", "mark_sent", "mark_failed", "retry",
            "apply_outcome", "set_status", "save", "upsert",
        )
        for verb in forbidden:
            assert not hasattr(repo, verb), (
                f"repository surface MUST NOT expose '{verb}' — "
                f"legacy has NO state transitions on email_outbox"
            )
        print("✓ test_7_status_is_terminal_at_insert")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Read — admin audit
# ----------------------------------------------------------------------

async def test_8_list_recent_empty():
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        items = await repo.list_recent()
        assert items == []
        print("✓ test_8_list_recent_empty")
    finally:
        client.close()


async def test_9_list_recent_sorted_desc_by_created_at():
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        # Insert in deliberate non-time order
        await repo.record_email_send_dry_run(_email_dry_run_record(
            id="r1", created_at="2026-01-01T00:00:00+00:00"
        ))
        await repo.record_email_send_dry_run(_email_dry_run_record(
            id="r3", created_at="2026-03-01T00:00:00+00:00"
        ))
        await repo.record_email_send_dry_run(_email_dry_run_record(
            id="r2", created_at="2026-02-01T00:00:00+00:00"
        ))
        items = await repo.list_recent()
        ids = [r["id"] for r in items]
        assert ids == ["r3", "r2", "r1"], f"sort desc broken: {ids}"
        # _id projection
        assert all("_id" not in r for r in items)
        print("✓ test_9_list_recent_sorted_desc_by_created_at")
    finally:
        client.close()


async def test_10_list_recent_limit_caps_results():
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        for i in range(20):
            await repo.record_email_send_dry_run(_email_dry_run_record(
                id=f"r{i:02d}", created_at=f"2026-01-{i+1:02d}T00:00:00+00:00"
            ))
        items = await repo.list_recent(limit=5)
        assert len(items) == 5
        assert items[0]["id"] == "r19"  # newest
        print("✓ test_10_list_recent_limit_caps_results")
    finally:
        client.close()


async def test_11_list_recent_event_filter():
    """event filter works ONLY for EmailChannel records — auth-audit
    records have no event field, so they're invisible when filtering."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        await repo.record_email_send_dry_run(_email_dry_run_record(
            event="lead.created"
        ))
        await repo.record_email_send_dry_run(_email_dry_run_record(
            event="payment.received"
        ))
        await repo.record_auth_email_audit(_auth_audit_record())  # no event
        items = await repo.list_recent(event="lead.created")
        assert len(items) == 1
        assert items[0]["event"] == "lead.created"
        # No auth-audit record leaked through (it has no event field
        # but the filter is positive-match — must not return docs
        # missing the field).
        assert all("event" in r for r in items)
        print("✓ test_11_list_recent_event_filter")
    finally:
        client.close()


async def test_12_list_recent_status_filter_crosses_doc_families():
    """status filter sees BOTH EmailChannel and auth-audit records —
    'dry_run' status exists in both families."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        await repo.record_email_send_dry_run(_email_dry_run_record(id="email_1"))
        await repo.record_email_send_attempt(_email_attempt_record(id="email_2", sent=True))
        await repo.record_auth_email_audit(_auth_audit_record())
        items = await repo.list_recent(status="dry_run")
        # Should return BOTH the email_1 dry_run record AND the
        # auth-audit record (which also has status="dry_run").
        statuses = [r["status"] for r in items]
        assert statuses == ["dry_run", "dry_run"]
        # Mixed shapes: one has 'id'+'event'+'provider', one has
        # 'template'+'mode'+'body'.
        has_event = sum(1 for r in items if "event" in r)
        has_template = sum(1 for r in items if "template" in r)
        assert has_event == 1
        assert has_template == 1
        print("✓ test_12_list_recent_status_filter_crosses_doc_families")
    finally:
        client.close()


async def test_13_list_recent_empty_string_filters_treated_as_absent():
    """Legacy truthiness: event='' or status='' = no filter."""
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)
        await repo.record_email_send_dry_run(_email_dry_run_record(id="r1"))
        await repo.record_auth_email_audit(_auth_audit_record())
        items = await repo.list_recent(event="", status="")
        assert len(items) == 2
        print("✓ test_13_list_recent_empty_string_filters_treated_as_absent")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Full lifecycle through the three enqueue contexts
# ----------------------------------------------------------------------

async def test_14_full_three_concern_lifecycle():
    """All three enqueue verbs + admin list in one scenario.

    Mirrors the real production trace:
      a) NotificationService dispatches → EmailChannel dry-run insert
      b) NotificationService dispatches → EmailChannel resend insert
         (with provider outcome)
      c) server.py password-reset → auth-audit insert (different shape)
      d) Admin opens the audit page → list_recent returns mixed shapes
    """
    client, db = await _fresh_db()
    try:
        repo = EmailOutboxRepository(db)

        # a) NotificationService dry-run path
        dry = _email_dry_run_record(event="invoice.issued")
        await repo.record_email_send_dry_run(dry)

        # b) NotificationService resend path (succeeded)
        attempt = _email_attempt_record(sent=True, event="invoice.issued")
        await repo.record_email_send_attempt(attempt)

        # c) server.py password-reset audit
        auth = _auth_audit_record()
        await repo.record_auth_email_audit(auth)

        # d) Admin list — heterogeneous, sorted by created_at desc
        items = await repo.list_recent(limit=10)
        assert len(items) == 3
        # All three families coexist; admin UI receives them as-is
        statuses = sorted(r["status"] for r in items)
        assert statuses == ["dry_run", "dry_run", "sent"]

        # Filter by event "invoice.issued" → only the 2 EmailChannel
        # records, auth audit has no event field
        invoice_items = await repo.list_recent(event="invoice.issued")
        assert len(invoice_items) == 2
        assert all(r.get("event") == "invoice.issued" for r in invoice_items)

        print("✓ test_14_full_three_concern_lifecycle")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Drift visibility — verifying the verb name SURFACES the cross-domain
# write (this is a topology test, not a behaviour test)
# ----------------------------------------------------------------------

async def test_15_drift_is_visible_via_named_verb():
    """The repository surface MUST expose `record_auth_email_audit`
    as a distinct named verb so the cross-domain origin is visible
    at code-review time. Collapsing it into `record_email_send_*`
    would hide the drift.
    """
    repo = EmailOutboxRepository(None)
    # The three enqueue verbs exist and are distinct
    assert hasattr(repo, "record_email_send_dry_run")
    assert hasattr(repo, "record_email_send_attempt")
    assert hasattr(repo, "record_auth_email_audit")
    # They are NOT the same function (no unification)
    assert repo.record_email_send_dry_run is not repo.record_email_send_attempt
    assert repo.record_email_send_attempt is not repo.record_auth_email_audit
    # No "record_outbound" / "record_message" / "enqueue" generic verb
    forbidden_unifications = (
        "record_outbound", "record_message", "record_email", "enqueue",
        "send", "audit", "log_send",
    )
    for v in forbidden_unifications:
        assert not hasattr(repo, v), (
            f"repository MUST NOT expose generic '{v}' — naming would "
            f"hide the multi-concern multi-shape topology"
        )
    print("✓ test_15_drift_is_visible_via_named_verb")


async def main():
    tests = [
        test_1_record_email_send_dry_run_persists_shape,
        test_2_record_email_send_attempt_with_outcome,
        test_3_record_email_send_attempt_failed_branch,
        test_4_record_auth_email_audit_distinct_shape,
        test_5_three_enqueue_verbs_coexist_in_one_collection,
        test_6_enqueue_is_append_only_no_update,
        test_7_status_is_terminal_at_insert,
        test_8_list_recent_empty,
        test_9_list_recent_sorted_desc_by_created_at,
        test_10_list_recent_limit_caps_results,
        test_11_list_recent_event_filter,
        test_12_list_recent_status_filter_crosses_doc_families,
        test_13_list_recent_empty_string_filters_treated_as_absent,
        test_14_full_three_concern_lifecycle,
        test_15_drift_is_visible_via_named_verb,
    ]
    fails = 0
    for t in tests:
        try:
            await t()
        except Exception as e:
            fails += 1
            print(f"✗ {t.__name__}: {type(e).__name__}: {e}")

    client = AsyncIOMotorClient(MONGO_URL)
    await client.drop_database(TEST_DB)
    client.close()

    print(f"\n{'=' * 60}")
    print(f"EmailOutboxRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
