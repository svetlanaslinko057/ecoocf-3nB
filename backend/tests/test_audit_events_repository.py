"""
Phase 5.3 / C-11 — AuditEventsRepository unit contract tests.
=============================================================

The SECOND C-N-class test suite organised by LIFECYCLE-CONTEXT
(after C-10's email_outbox suite). Scenarios pin the two
divergent enqueue shapes (domain-event vs payment-webhook),
the boot index ensuring, and the two admin read endpoints
with their distinct filter contracts.

Run:
    cd /app/backend && python tests/test_audit_events_repository.py
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

from app.repositories import AuditEventsRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "audit_events_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[AuditEventsRepository.COLLECTION].drop()
    return client, db


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _domain_event_record(**overrides) -> dict:
    """Reproduce the legal_workflow._audit() 12-field shape."""
    rec = {
        "id":          f"audit_{int(datetime.now(timezone.utc).timestamp()*1000)}_{uuid.uuid4().hex[:8]}",
        "type":        "deal.locked",
        "entity_type": "deal",
        "entity_id":   "deal_abc",
        "deal_id":     "deal_abc",
        "customer_id": "cust_1",
        "user_id":     "staff_1",
        "user_email":  "admin@bibi.cars",
        "user_role":   "admin",
        "payload":     {"reason": "auction_won"},
        "at":          _iso(),
        "ts":          datetime.now(timezone.utc),
    }
    rec.update(overrides)
    return rec


def _payment_webhook_record(**overrides) -> dict:
    """Reproduce the payments router stripe-webhook 12-field shape.

    NOTE: NO entity_type / entity_id / user_* / payload / at fields;
    uses payment_id / amount / currency / method / source / event_type /
    stripe_session_id / stripe_payment_intent INSTEAD. ts is ISO string,
    NOT datetime!"""
    rec = {
        "id":                     f"aud-{uuid.uuid4().hex[:12]}",
        "type":                   "payment.confirmed",
        "deal_id":                "deal_pay_1",
        "payment_id":             "pay_xyz",
        "amount":                 1234.56,
        "currency":               "USD",
        "method":                 "stripe",
        "source":                 "stripe_webhook",
        "event_type":             "checkout.session.completed",
        "stripe_session_id":      "cs_test_xyz",
        "stripe_payment_intent":  "pi_test_xyz",
        "ts":                     _iso(),  # ISO string!
    }
    rec.update(overrides)
    return rec


# ----------------------------------------------------------------------
# Boot — index ensuring (1 lifecycle context — NEW vs C-10)
# ----------------------------------------------------------------------

async def test_1_ensure_indexes_creates_6_indexes():
    """ensure_indexes() creates exactly 6 indexes (plus _id auto)."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.ensure_indexes()
        coll = db[AuditEventsRepository.COLLECTION]
        # Wait briefly for index creation to settle
        info = await coll.index_information()
        # _id is always present; we add 6 more
        key_sets = set()
        for name, idx in info.items():
            if name == "_id_":
                continue
            keys = tuple((k, v) for k, v in idx["key"])
            key_sets.add(keys)
        expected = {
            (("ts", -1),),
            (("deal_id", 1), ("ts", -1)),
            (("customer_id", 1), ("ts", -1)),
            (("entity_type", 1), ("entity_id", 1), ("ts", -1)),
            (("type", 1), ("ts", -1)),
            (("id", 1),),
        }
        assert key_sets == expected, f"index mismatch: {key_sets} vs {expected}"
        print("✓ test_1_ensure_indexes_creates_6_indexes")
    finally:
        client.close()


async def test_2_ensure_indexes_idempotent():
    """ensure_indexes() is idempotent (Motor create_index is)."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.ensure_indexes()
        # Re-run — must not raise
        await repo.ensure_indexes()
        info = await db[AuditEventsRepository.COLLECTION].index_information()
        non_id = [n for n in info if n != "_id_"]
        assert len(non_id) == 6
        print("✓ test_2_ensure_indexes_idempotent")
    finally:
        client.close()


async def test_3_ensure_indexes_silent_on_conflict():
    """Repository NEVER raises on index conflict — legacy behaviour."""
    client, db = await _fresh_db()
    try:
        # Pre-create an INCOMPATIBLE index (same fields, different opts)
        coll = db[AuditEventsRepository.COLLECTION]
        await coll.create_index([("id", 1)], unique=False)
        repo = AuditEventsRepository(db)
        # Must NOT raise even though the create_index would conflict
        await repo.ensure_indexes()
        print("✓ test_3_ensure_indexes_silent_on_conflict")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Enqueue verbs — each preserves its legacy doc shape verbatim
# ----------------------------------------------------------------------

async def test_4_record_domain_event_persists_12_field_shape():
    """record_domain_event writes the 12-field domain shape verbatim."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        record = _domain_event_record()
        await repo.record_domain_event(record)
        doc = await db[AuditEventsRepository.COLLECTION].find_one({"id": record["id"]})
        expected_keys = {
            "_id", "id", "type", "entity_type", "entity_id",
            "deal_id", "customer_id", "user_id", "user_email", "user_role",
            "payload", "at", "ts",
        }
        assert set(doc.keys()) == expected_keys
        assert doc["type"] == "deal.locked"
        assert doc["entity_type"] == "deal"
        # ts must remain a datetime (not converted)
        assert isinstance(doc["ts"], datetime)
        print("✓ test_4_record_domain_event_persists_12_field_shape")
    finally:
        client.close()


async def test_5_record_payment_webhook_event_distinct_shape():
    """payment-webhook shape is DIFFERENT from domain-event shape."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        record = _payment_webhook_record()
        await repo.record_payment_webhook_event(record)
        doc = await db[AuditEventsRepository.COLLECTION].find_one({"id": record["id"]})
        assert doc is not None
        # Fields that domain-event has but payment-webhook does NOT
        for absent_field in ("entity_type", "entity_id", "user_id",
                             "user_email", "user_role", "payload", "at"):
            assert absent_field not in doc, (
                f"payment-webhook shape unexpectedly carries '{absent_field}' — "
                f"shape normalization is forbidden by C-11 mandate"
            )
        # Fields that ONLY payment-webhook has
        for present_field in ("payment_id", "amount", "currency", "method",
                              "source", "event_type", "stripe_session_id",
                              "stripe_payment_intent"):
            assert present_field in doc
        # ts is ISO string here, NOT datetime
        assert isinstance(doc["ts"], str)
        assert doc["method"] == "stripe"
        print("✓ test_5_record_payment_webhook_event_distinct_shape")
    finally:
        client.close()


async def test_6_two_enqueue_shapes_coexist_in_one_collection():
    """Heterogeneous shapes share the same collection — by design."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.record_domain_event(_domain_event_record(type="deal.locked"))
        await repo.record_domain_event(_domain_event_record(type="deposit.created"))
        await repo.record_payment_webhook_event(_payment_webhook_record())
        coll = db[AuditEventsRepository.COLLECTION]
        assert await coll.count_documents({}) == 3
        # Count by source shape — entity_type only on domain records
        assert await coll.count_documents({"entity_type": {"$exists": True}}) == 2
        assert await coll.count_documents({"stripe_session_id": {"$exists": True}}) == 1
        # Count by type prefix
        assert await coll.count_documents({"type": {"$regex": "^deal\\."}}) == 1
        assert await coll.count_documents({"type": {"$regex": "^deposit\\."}}) == 1
        assert await coll.count_documents({"type": {"$regex": "^payment\\."}}) == 1
        print("✓ test_6_two_enqueue_shapes_coexist_in_one_collection")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Append-only / terminal-at-insert verification
# ----------------------------------------------------------------------

async def test_7_enqueue_is_append_only_no_update_verbs():
    """Repository surface MUST NOT expose update/patch/mark verbs.

    audit_events is append-only by legal/compliance constraint;
    surface MUST be append-only at the contract layer too."""
    repo = AuditEventsRepository(None)
    forbidden = (
        "update", "patch", "mark_processed", "mark_reviewed", "mark_voided",
        "set_status", "save", "upsert", "delete", "delete_one", "delete_many",
        "soft_delete",
    )
    for verb in forbidden:
        assert not hasattr(repo, verb), (
            f"repository surface MUST NOT expose '{verb}' — audit_events is "
            f"append-only by legal/compliance constraint"
        )
    print("✓ test_7_enqueue_is_append_only_no_update_verbs")


# ----------------------------------------------------------------------
# Read — list_filtered
# ----------------------------------------------------------------------

async def test_8_list_filtered_empty():
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        items = await repo.list_filtered()
        assert items == []
        print("✓ test_8_list_filtered_empty")
    finally:
        client.close()


async def test_9_list_filtered_sorted_desc_by_ts():
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        # Insert in deliberate non-time order
        await repo.record_domain_event(_domain_event_record(
            id="r1", ts=datetime(2026, 1, 1, tzinfo=timezone.utc)
        ))
        await repo.record_domain_event(_domain_event_record(
            id="r3", ts=datetime(2026, 3, 1, tzinfo=timezone.utc)
        ))
        await repo.record_domain_event(_domain_event_record(
            id="r2", ts=datetime(2026, 2, 1, tzinfo=timezone.utc)
        ))
        items = await repo.list_filtered()
        ids = [r["id"] for r in items]
        assert ids == ["r3", "r2", "r1"]
        assert all("_id" not in r for r in items)
        print("✓ test_9_list_filtered_sorted_desc_by_ts")
    finally:
        client.close()


async def test_10_list_filtered_limit_clamp_high_and_low():
    """limit is clamped to [1, 500] (legacy quirk)."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        for i in range(10):
            await repo.record_domain_event(_domain_event_record(
                id=f"r{i:02d}",
                ts=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            ))
        # limit > 500 → 500 cap
        items = await repo.list_filtered(limit=99999)
        assert len(items) == 10  # only 10 docs, but cap honoured
        # limit = 0 → minimum 1
        items = await repo.list_filtered(limit=0)
        assert len(items) == 1
        # limit = -5 → minimum 1
        items = await repo.list_filtered(limit=-5)
        assert len(items) == 1
        print("✓ test_10_list_filtered_limit_clamp_high_and_low")
    finally:
        client.close()


async def test_11_list_filtered_six_axes_independent():
    """All 6 filter axes (deal_id, customer_id, entity_type, entity_id,
    type, user_email) work independently and combine via AND."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.record_domain_event(_domain_event_record(
            id="r1", deal_id="d1", customer_id="c1",
            entity_type="deal", entity_id="d1", type="deal.locked",
            user_email="alice@bibi.cars",
        ))
        await repo.record_domain_event(_domain_event_record(
            id="r2", deal_id="d2", customer_id="c1",
            entity_type="deal", entity_id="d2", type="deposit.created",
            user_email="bob@bibi.cars",
        ))
        await repo.record_domain_event(_domain_event_record(
            id="r3", deal_id="d1", customer_id="c2",
            entity_type="invoice", entity_id="i1", type="invoice.issued",
            user_email="alice@bibi.cars",
        ))
        # Single-axis filters
        assert {r["id"] for r in await repo.list_filtered(deal_id="d1")} == {"r1", "r3"}
        assert {r["id"] for r in await repo.list_filtered(customer_id="c1")} == {"r1", "r2"}
        assert {r["id"] for r in await repo.list_filtered(entity_type="deal")} == {"r1", "r2"}
        assert {r["id"] for r in await repo.list_filtered(type="deal.locked")} == {"r1"}
        assert {r["id"] for r in await repo.list_filtered(user_email="alice@bibi.cars")} == {"r1", "r3"}
        # Multi-axis AND
        items = await repo.list_filtered(deal_id="d1", user_email="alice@bibi.cars")
        assert {r["id"] for r in items} == {"r1", "r3"}
        items = await repo.list_filtered(deal_id="d1", type="invoice.issued")
        assert {r["id"] for r in items} == {"r3"}
        print("✓ test_11_list_filtered_six_axes_independent")
    finally:
        client.close()


async def test_12_list_filtered_empty_string_treated_as_absent():
    """Legacy truthiness: deal_id='' = no filter."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.record_domain_event(_domain_event_record(id="r1"))
        await repo.record_payment_webhook_event(_payment_webhook_record())
        items = await repo.list_filtered(
            deal_id="", customer_id="", entity_type="", entity_id="",
            type="", user_email="",
        )
        assert len(items) == 2  # both shapes returned (no filter applied)
        print("✓ test_12_list_filtered_empty_string_treated_as_absent")
    finally:
        client.close()


async def test_13_list_filtered_returns_raw_datetime_ts():
    """Repository does NOT post-process ts datetime → ISO; that's the
    router's job. The repo returns the cursor materialization raw."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.record_domain_event(_domain_event_record(id="r1"))  # ts = datetime
        items = await repo.list_filtered()
        # Domain-event records have ts as datetime
        assert isinstance(items[0]["ts"], datetime), (
            f"repository must NOT convert ts datetime → ISO; got {type(items[0]['ts'])}"
        )
        print("✓ test_13_list_filtered_returns_raw_datetime_ts")
    finally:
        client.close()


async def test_14_list_filtered_crosses_doc_families():
    """Filter by type='deal.locked' must work on domain records;
    filter by source='stripe_webhook' must work on payment records."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.record_domain_event(_domain_event_record(
            id="r1", type="deal.locked"
        ))
        await repo.record_payment_webhook_event(_payment_webhook_record(
            id="r2", type="payment.confirmed"
        ))
        # type filter sees both via the shared `type` field
        items = await repo.list_filtered(type="deal.locked")
        assert len(items) == 1
        assert items[0]["id"] == "r1"
        items = await repo.list_filtered(type="payment.confirmed")
        assert len(items) == 1
        assert items[0]["id"] == "r2"
        print("✓ test_14_list_filtered_crosses_doc_families")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Read — list_for_deal
# ----------------------------------------------------------------------

async def test_15_list_for_deal_default_limit_is_200():
    """list_for_deal default limit is 200 (NOT 100 like list_filtered)."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        # Insert 250 events for one deal
        for i in range(250):
            await repo.record_domain_event(_domain_event_record(
                id=f"r{i:03d}", deal_id="deal_X",
                ts=datetime(2026, 1, 1, 0, 0, i % 60, tzinfo=timezone.utc),
            ))
        items = await repo.list_for_deal("deal_X")
        assert len(items) == 200, f"default limit 200 (legacy); got {len(items)}"
        print("✓ test_15_list_for_deal_default_limit_is_200")
    finally:
        client.close()


async def test_16_list_for_deal_filter_isolates_one_deal():
    """list_for_deal filters strictly by deal_id."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        await repo.record_domain_event(_domain_event_record(id="d1_r1", deal_id="d1"))
        await repo.record_domain_event(_domain_event_record(id="d2_r1", deal_id="d2"))
        await repo.record_domain_event(_domain_event_record(id="d1_r2", deal_id="d1"))
        items = await repo.list_for_deal("d1")
        assert {r["id"] for r in items} == {"d1_r1", "d1_r2"}
        print("✓ test_16_list_for_deal_filter_isolates_one_deal")
    finally:
        client.close()


async def test_17_list_for_deal_excludes_audit_log_collection():
    """list_for_deal scopes to db.audit_events ONLY — never touches
    db.audit_log (the sibling, NOT in C-11 scope)."""
    client, db = await _fresh_db()
    try:
        # Insert into sibling audit_log directly
        await db.audit_log.insert_one({
            "ts": _iso(),
            "action": "login_ok",
            "user_id": "u1",
            "deal_id": "deal_x",  # accidentally contains deal_id, must be invisible
        })
        repo = AuditEventsRepository(db)
        items = await repo.list_for_deal("deal_x")
        assert items == [], (
            "list_for_deal must NOT bleed into audit_log — sibling collection "
            "ownership is preserved at the repository scope"
        )
        # Cleanup
        await db.audit_log.delete_many({"deal_id": "deal_x"})
        print("✓ test_17_list_for_deal_excludes_audit_log_collection")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Full lifecycle through both writer concerns + both reads
# ----------------------------------------------------------------------

async def test_18_full_two_concern_lifecycle():
    """Both enqueue verbs + both read endpoints in one scenario."""
    client, db = await _fresh_db()
    try:
        repo = AuditEventsRepository(db)
        # Ensure indexes (boot context)
        await repo.ensure_indexes()
        # Concern A — domain audit
        await repo.record_domain_event(_domain_event_record(
            id="d_r1", deal_id="d_X", type="deal.locked"
        ))
        await repo.record_domain_event(_domain_event_record(
            id="d_r2", deal_id="d_X", type="deposit.created"
        ))
        # Concern B — payment webhook audit
        await repo.record_payment_webhook_event(_payment_webhook_record(
            id="p_r1", deal_id="d_X", type="payment.confirmed"
        ))
        # Admin read — general list
        items = await repo.list_filtered(limit=10)
        assert len(items) == 3
        # Admin read — deal trail
        deal_items = await repo.list_for_deal("d_X", limit=10)
        assert len(deal_items) == 3
        # Filter by entity_type (only domain records have entity_type)
        deal_only = await repo.list_filtered(entity_type="deal")
        assert len(deal_only) == 2  # both d_r1 and d_r2
        # Filter by type — sees both families
        pay_only = await repo.list_filtered(type="payment.confirmed")
        assert len(pay_only) == 1
        print("✓ test_18_full_two_concern_lifecycle")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Topology visibility — naming surfaces the cross-domain WRITE
# ----------------------------------------------------------------------

async def test_19_cross_domain_write_visible_via_named_verb():
    """The repository surface MUST expose record_payment_webhook_event
    as a distinct named verb — collapsing it into record_domain_event
    would hide the cross-concern source."""
    repo = AuditEventsRepository(None)
    # The two enqueue verbs exist and are distinct
    assert hasattr(repo, "record_domain_event")
    assert hasattr(repo, "record_payment_webhook_event")
    # They are NOT the same function
    assert repo.record_domain_event is not repo.record_payment_webhook_event
    # No generic enqueue/audit/record verb
    forbidden_unifications = (
        "record_audit", "record_event", "record", "enqueue", "audit",
        "log_event", "append",
    )
    for v in forbidden_unifications:
        assert not hasattr(repo, v), (
            f"repository MUST NOT expose generic '{v}' — naming would hide "
            f"the multi-concern multi-shape topology"
        )
    print("✓ test_19_cross_domain_write_visible_via_named_verb")


async def main():
    tests = [
        test_1_ensure_indexes_creates_6_indexes,
        test_2_ensure_indexes_idempotent,
        test_3_ensure_indexes_silent_on_conflict,
        test_4_record_domain_event_persists_12_field_shape,
        test_5_record_payment_webhook_event_distinct_shape,
        test_6_two_enqueue_shapes_coexist_in_one_collection,
        test_7_enqueue_is_append_only_no_update_verbs,
        test_8_list_filtered_empty,
        test_9_list_filtered_sorted_desc_by_ts,
        test_10_list_filtered_limit_clamp_high_and_low,
        test_11_list_filtered_six_axes_independent,
        test_12_list_filtered_empty_string_treated_as_absent,
        test_13_list_filtered_returns_raw_datetime_ts,
        test_14_list_filtered_crosses_doc_families,
        test_15_list_for_deal_default_limit_is_200,
        test_16_list_for_deal_filter_isolates_one_deal,
        test_17_list_for_deal_excludes_audit_log_collection,
        test_18_full_two_concern_lifecycle,
        test_19_cross_domain_write_visible_via_named_verb,
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
    print(f"AuditEventsRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
