"""
Phase 5.4 / C-1 — SecurityAuditRepository unit contract tests.
==============================================================

Twelfth-extraction lifecycle-shaped tests (first Phase 5.4
suite). Scenarios pin the five divergent enqueue shapes
(security_event 8-field / hmac_failure 4-field / login_failed
4-field / login_ok 6-field / transfer_event 4-field-with-
formatted-resource), the boot TTL index ensuring, and the
write-only runtime nature of the collection (NO read verbs
on the surface).

Run:
    cd /app/backend && python tests/test_security_audit_repository.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.repositories import SecurityAuditRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "security_audit_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[SecurityAuditRepository.COLLECTION].drop()
    return client, db


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# Boot — TTL index ensuring
# ----------------------------------------------------------------------

async def test_1_ensure_indexes_creates_ttl_90d():
    """ensure_indexes() creates the 90-day TTL index on ts."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        await repo.ensure_indexes()
        coll = db[SecurityAuditRepository.COLLECTION]
        info = await coll.index_information()
        # Find the TTL index
        ttl_idx = info.get("audit_ttl_90d")
        assert ttl_idx is not None, f"audit_ttl_90d index missing; info={list(info.keys())}"
        assert ttl_idx.get("expireAfterSeconds") == 90 * 24 * 3600, (
            f"expireAfterSeconds wrong: {ttl_idx.get('expireAfterSeconds')}"
        )
        assert ttl_idx["key"] == [("ts", 1)] or ttl_idx["key"] == {"ts": 1}, (
            f"index key wrong: {ttl_idx['key']}"
        )
        print("✓ test_1_ensure_indexes_creates_ttl_90d")
    finally:
        client.close()


async def test_2_ensure_indexes_idempotent():
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        await repo.ensure_indexes()
        await repo.ensure_indexes()  # must not raise
        info = await db[SecurityAuditRepository.COLLECTION].index_information()
        assert "audit_ttl_90d" in info
        print("✓ test_2_ensure_indexes_idempotent")
    finally:
        client.close()


async def test_3_ensure_indexes_silent_on_conflict():
    """Pre-create a conflicting non-TTL index on ts; ensure_indexes
    must NOT raise (legacy preserved behaviour)."""
    client, db = await _fresh_db()
    try:
        coll = db[SecurityAuditRepository.COLLECTION]
        # Pre-create a NON-TTL index on ts with a different name
        await coll.create_index("ts", name="ts_no_ttl")
        repo = SecurityAuditRepository(db)
        # Must not raise even though the ts index already exists
        # (Motor will reject the TTL options conflict, but the repo swallows)
        await repo.ensure_indexes()
        print("✓ test_3_ensure_indexes_silent_on_conflict")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Five distinct enqueue shapes — each preserves its 1:1 legacy form
# ----------------------------------------------------------------------

async def test_4_record_security_event_8_field_shape():
    """server.audit() shape: ts/action/user_id/user_email/user_role/
    resource/meta/ip (8 fields)."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        record = {
            "ts": _iso(),
            "action": "tracking_disabled_skipped",
            "user_id": "u1",
            "user_email": "alice@bibi.cars",
            "user_role": "admin",
            "resource": "resolver_worker",
            "meta": {"reason": "feature_flag_off"},
            "ip": "10.0.0.1",
        }
        await repo.record_security_event(record)
        doc = await db[SecurityAuditRepository.COLLECTION].find_one(
            {"action": "tracking_disabled_skipped"}
        )
        expected_keys = {
            "_id", "ts", "action", "user_id", "user_email", "user_role",
            "resource", "meta", "ip",
        }
        assert set(doc.keys()) == expected_keys, (
            f"shape mismatch: extra={set(doc.keys())-expected_keys}, "
            f"missing={expected_keys-set(doc.keys())}"
        )
        print("✓ test_4_record_security_event_8_field_shape")
    finally:
        client.close()


async def test_5_record_hmac_failure_4_field_shape():
    """_audit_hmac_failure shape: ts/action="hmac_failed"/meta/ip
    (4 fields; NO user_*, NO resource)."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        record = {
            "ts": _iso(),
            "action": "hmac_failed",
            "meta": {
                "reason": "signature_mismatch",
                "client": "ext_chrome",
                "method": "POST",
                "path": "/api/extension/event",
            },
            "ip": "10.0.0.2",
        }
        await repo.record_hmac_failure(record)
        doc = await db[SecurityAuditRepository.COLLECTION].find_one(
            {"action": "hmac_failed"}
        )
        expected_keys = {"_id", "ts", "action", "meta", "ip"}
        assert set(doc.keys()) == expected_keys
        # Must NOT carry user_*/resource (4-field shape preserved 1:1)
        for absent in ("user_id", "user_email", "user_role", "resource"):
            assert absent not in doc, (
                f"hmac_failure shape unexpectedly carries '{absent}' — "
                f"normalization is forbidden by C-1 mandate"
            )
        print("✓ test_5_record_hmac_failure_4_field_shape")
    finally:
        client.close()


async def test_6_record_login_failed_4_field_shape():
    """login_failed shape: ts/action="login_failed"/email/ip
    (FLAT email, NO user_id, NO role)."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        record = {
            "ts": _iso(),
            "action": "login_failed",
            "email": "attacker@evil.com",
            "ip": "10.0.0.3",
        }
        await repo.record_login_failed(record)
        doc = await db[SecurityAuditRepository.COLLECTION].find_one(
            {"action": "login_failed"}
        )
        expected_keys = {"_id", "ts", "action", "email", "ip"}
        assert set(doc.keys()) == expected_keys
        # FLAT email — NOT user_email
        assert doc["email"] == "attacker@evil.com"
        assert "user_email" not in doc
        assert "user_id" not in doc  # auth has not resolved
        assert "role" not in doc
        print("✓ test_6_record_login_failed_4_field_shape")
    finally:
        client.close()


async def test_7_record_login_ok_6_field_shape():
    """login_ok shape: ts/action="login_ok"/user_id/email/role/ip
    (FLAT email and role, NOT user_email/user_role)."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        record = {
            "ts": _iso(),
            "action": "login_ok",
            "user_id": "staff_1",
            "email": "admin@bibi.cars",
            "role": "admin",
            "ip": "10.0.0.4",
        }
        await repo.record_login_ok(record)
        doc = await db[SecurityAuditRepository.COLLECTION].find_one(
            {"action": "login_ok"}
        )
        expected_keys = {"_id", "ts", "action", "user_id", "email", "role", "ip"}
        assert set(doc.keys()) == expected_keys
        # FLAT email and role — NOT user_email/user_role
        assert "user_email" not in doc
        assert "user_role" not in doc
        print("✓ test_7_record_login_ok_6_field_shape")
    finally:
        client.close()


async def test_8_record_transfer_event_resource_formatted():
    """transfer_event shape: ts/action/resource(formatted)/meta
    (4 fields; NO user_*, NO ip; resource is a FORMATTED string)."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        record = {
            "ts": _iso(),
            "action": "transfer_detected",
            "resource": "shipment:shp_C1_test",
            "meta": {"old_vessel": "V1", "new_vessel": "V2", "confidence": 0.91},
        }
        await repo.record_transfer_event(record)
        doc = await db[SecurityAuditRepository.COLLECTION].find_one(
            {"action": "transfer_detected"}
        )
        expected_keys = {"_id", "ts", "action", "resource", "meta"}
        assert set(doc.keys()) == expected_keys
        # FORMATTED resource string
        assert doc["resource"] == "shipment:shp_C1_test"
        assert doc["resource"].startswith("shipment:")
        # No user_*, no ip
        for absent in ("user_id", "user_email", "user_role", "ip"):
            assert absent not in doc
        print("✓ test_8_record_transfer_event_resource_formatted")
    finally:
        client.close()


async def test_9_five_shapes_coexist_in_one_collection():
    """All 5 shapes coexist in db.audit_log — by design."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        await repo.record_security_event({
            "ts": _iso(), "action": "a1",
            "user_id": "u", "user_email": "e", "user_role": "r",
            "resource": "res", "meta": {}, "ip": "ip",
        })
        await repo.record_hmac_failure({
            "ts": _iso(), "action": "hmac_failed", "meta": {}, "ip": "ip",
        })
        await repo.record_login_failed({
            "ts": _iso(), "action": "login_failed", "email": "e", "ip": "ip",
        })
        await repo.record_login_ok({
            "ts": _iso(), "action": "login_ok",
            "user_id": "u", "email": "e", "role": "r", "ip": "ip",
        })
        await repo.record_transfer_event({
            "ts": _iso(), "action": "transfer_detected",
            "resource": "shipment:s1", "meta": {},
        })
        coll = db[SecurityAuditRepository.COLLECTION]
        assert await coll.count_documents({}) == 5
        # Shape-discriminating filters
        # security_event: has user_email AND resource AND meta
        assert await coll.count_documents({
            "user_email": {"$exists": True},
            "resource": {"$exists": True},
            "ip": {"$exists": True},
        }) == 1
        # hmac_failure: action == "hmac_failed"
        assert await coll.count_documents({"action": "hmac_failed"}) == 1
        # login_failed: action == "login_failed" AND has FLAT email AND NO user_id
        assert await coll.count_documents({
            "action": "login_failed",
            "email": {"$exists": True},
            "user_id": {"$exists": False},
        }) == 1
        # login_ok: action == "login_ok" AND has user_id AND FLAT email
        assert await coll.count_documents({
            "action": "login_ok",
            "user_id": {"$exists": True},
            "user_email": {"$exists": False},
        }) == 1
        # transfer_event: resource starts with "shipment:" AND no ip
        assert await coll.count_documents({
            "resource": {"$regex": "^shipment:"},
            "ip": {"$exists": False},
        }) == 1
        print("✓ test_9_five_shapes_coexist_in_one_collection")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Append-only / write-only at runtime
# ----------------------------------------------------------------------

async def test_10_append_only_no_update_verbs():
    """Repository surface MUST NOT expose update/patch/delete verbs."""
    repo = SecurityAuditRepository(None)
    forbidden = (
        "update", "patch", "mark_processed", "mark_reviewed",
        "set_status", "save", "upsert", "delete", "delete_one",
        "delete_many", "soft_delete",
    )
    for verb in forbidden:
        assert not hasattr(repo, verb), (
            f"repository surface MUST NOT expose '{verb}' — audit_log is "
            f"append-only with TTL-based cleanup"
        )
    print("✓ test_10_append_only_no_update_verbs")


async def test_11_write_only_no_read_verbs():
    """Repository surface MUST NOT expose read/list/find verbs (yet).
    Collection is write-only at runtime as of Phase 5.4 / C-1.
    A future commit may add a read verb when an admin reader appears."""
    repo = SecurityAuditRepository(None)
    forbidden = (
        "find_by_id", "list_recent", "list_filtered", "list_all",
        "list_for_user", "list_by_action", "find_one", "find_all",
        "count_all", "find_one_by_action",
    )
    for verb in forbidden:
        assert not hasattr(repo, verb), (
            f"repository surface MUST NOT expose '{verb}' — collection is "
            f"write-only at runtime as of Phase 5.4 / C-1; a future commit "
            f"adds the read verb when an admin reader appears"
        )
    print("✓ test_11_write_only_no_read_verbs")


# ----------------------------------------------------------------------
# Topology visibility — five distinct verbs surface five concerns
# ----------------------------------------------------------------------

async def test_12_five_distinct_verbs_surface_five_concerns():
    """Repository MUST expose exactly the 5 distinct enqueue verbs as
    DISTINCT named functions — no generic enqueue/record/audit."""
    repo = SecurityAuditRepository(None)
    expected_verbs = (
        "record_security_event",
        "record_hmac_failure",
        "record_login_failed",
        "record_login_ok",
        "record_transfer_event",
        "ensure_indexes",
    )
    for v in expected_verbs:
        assert hasattr(repo, v), f"missing verb '{v}'"

    # All 5 enqueue verbs must be distinct functions
    enqueue_methods = [
        repo.record_security_event,
        repo.record_hmac_failure,
        repo.record_login_failed,
        repo.record_login_ok,
        repo.record_transfer_event,
    ]
    assert len(set(id(m) for m in enqueue_methods)) == 5, (
        "five enqueue verbs must be five distinct functions — collapsing "
        "any of them would hide the writer topology"
    )

    forbidden_unifications = (
        "record_audit", "record_event", "record", "enqueue", "audit",
        "log_event", "append", "write_log", "log_security",
    )
    for v in forbidden_unifications:
        assert not hasattr(repo, v), (
            f"repository MUST NOT expose generic '{v}' — naming would hide "
            f"the multi-concern multi-shape topology"
        )
    print("✓ test_12_five_distinct_verbs_surface_five_concerns")


# ----------------------------------------------------------------------
# Sibling-collection isolation — must NOT bleed into audit_events
# ----------------------------------------------------------------------

async def test_13_writes_isolated_from_audit_events_sibling():
    """SecurityAuditRepository writes ONLY db.audit_log; the sibling
    db.audit_events (owned by AuditEventsRepository, C-11) MUST NOT
    be touched. Mirrors C-11's test 17 on the other side of the
    boundary."""
    client, db = await _fresh_db()
    try:
        # Pre-existing data in sibling audit_events — must remain untouched
        await db.audit_events.insert_one({
            "id": "sentinel_C1",
            "type": "deal.locked",
            "entity_type": "deal",
            "entity_id": "deal_sentinel",
        })
        before = await db.audit_events.count_documents({})

        repo = SecurityAuditRepository(db)
        await repo.ensure_indexes()
        await repo.record_security_event({
            "ts": _iso(), "action": "leak_test",
            "user_id": "u", "user_email": "e", "user_role": "r",
            "resource": "res", "meta": {}, "ip": "ip",
        })
        await repo.record_transfer_event({
            "ts": _iso(), "action": "leak_test",
            "resource": "shipment:s", "meta": {},
        })

        after = await db.audit_events.count_documents({})
        assert before == after, (
            f"audit_events count drifted ({before} → {after}) — "
            f"SecurityAuditRepository leaked into sibling collection"
        )
        # Sentinel must still be there with its original shape
        sentinel = await db.audit_events.find_one({"id": "sentinel_C1"})
        assert sentinel["type"] == "deal.locked"
        # Cleanup
        await db.audit_events.delete_many({"id": "sentinel_C1"})
        print("✓ test_13_writes_isolated_from_audit_events_sibling")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Full lifecycle through all 5 enqueue verbs + boot
# ----------------------------------------------------------------------

async def test_14_full_lifecycle_all_5_verbs():
    """All 6 verbs in one scenario, mirroring production trace."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        # Boot
        await repo.ensure_indexes()
        # Five enqueue concerns
        await repo.record_security_event({
            "ts": _iso(), "action": "tracking_disabled_skipped",
            "user_id": None, "user_email": None, "user_role": None,
            "resource": "resolver_worker", "meta": {}, "ip": None,
        })
        await repo.record_hmac_failure({
            "ts": _iso(), "action": "hmac_failed",
            "meta": {"reason": "signature_mismatch", "client": "ext", "method": "POST", "path": "/x"},
            "ip": "10.0.0.99",
        })
        await repo.record_login_failed({
            "ts": _iso(), "action": "login_failed",
            "email": "wrong@example.com", "ip": "10.0.0.10",
        })
        await repo.record_login_ok({
            "ts": _iso(), "action": "login_ok",
            "user_id": "staff_42", "email": "admin@bibi.cars",
            "role": "admin", "ip": "10.0.0.10",
        })
        await repo.record_transfer_event({
            "ts": _iso(), "action": "transfer_detected",
            "resource": "shipment:shp_C1",
            "meta": {"confidence": 0.92},
        })
        coll = db[SecurityAuditRepository.COLLECTION]
        assert await coll.count_documents({}) == 5
        # Index still present
        info = await coll.index_information()
        assert "audit_ttl_90d" in info
        print("✓ test_14_full_lifecycle_all_5_verbs")
    finally:
        client.close()


# ----------------------------------------------------------------------
# TTL property — the cleanup/TTL lifecycle category is preserved
# ----------------------------------------------------------------------

async def test_15_ttl_index_present_after_ensure_indexes():
    """ensure_indexes establishes the cleanup/TTL lifecycle category
    at the database layer. The category is implicit (TTL is a Mongo
    feature, not application code), but the index existence MUST be
    pinned at the repository contract."""
    client, db = await _fresh_db()
    try:
        repo = SecurityAuditRepository(db)
        await repo.ensure_indexes()
        info = await db[SecurityAuditRepository.COLLECTION].index_information()
        ttl_idx = info.get("audit_ttl_90d")
        assert ttl_idx is not None
        assert ttl_idx.get("expireAfterSeconds") == 90 * 24 * 3600
        # CRITICAL: the audit_events sibling has NO TTL — they must remain
        # distinct at the database-layer behaviour level
        # (we can't drop indexes on a different DB here, but we pin the
        # repository's TTL value as the load-bearing fact)
        print("✓ test_15_ttl_index_present_after_ensure_indexes")
    finally:
        client.close()


async def main():
    tests = [
        test_1_ensure_indexes_creates_ttl_90d,
        test_2_ensure_indexes_idempotent,
        test_3_ensure_indexes_silent_on_conflict,
        test_4_record_security_event_8_field_shape,
        test_5_record_hmac_failure_4_field_shape,
        test_6_record_login_failed_4_field_shape,
        test_7_record_login_ok_6_field_shape,
        test_8_record_transfer_event_resource_formatted,
        test_9_five_shapes_coexist_in_one_collection,
        test_10_append_only_no_update_verbs,
        test_11_write_only_no_read_verbs,
        test_12_five_distinct_verbs_surface_five_concerns,
        test_13_writes_isolated_from_audit_events_sibling,
        test_14_full_lifecycle_all_5_verbs,
        test_15_ttl_index_present_after_ensure_indexes,
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
    print(f"SecurityAuditRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
