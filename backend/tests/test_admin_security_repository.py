"""
Phase 5.3 / C-3 — AdminSecurityRepository unit contract tests.
==============================================================

Mirror of the C-1/C-2 unit suites: live Motor against a throw-away
database; covers every named-verb business operation; pins each
preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python -m pytest tests/test_admin_security_repository.py -v

Or directly:
    cd /app/backend && python tests/test_admin_security_repository.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing app.repositories without installing the package
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.repositories import AdminSecurityRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "admin_security_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[AdminSecurityRepository.COLLECTION].drop()
    return client, db


async def _doc(db, admin_id: str):
    return await db[AdminSecurityRepository.COLLECTION].find_one({"_id": admin_id})


async def test_1_get_state_miss_returns_none():
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        out = await repo.get_state("admin")
        assert out is None, f"expected None on miss, got {out!r}"
        print("✓ test_1_get_state_miss_returns_none")
    finally:
        client.close()


async def test_2_record_setup_pending_creates_row_with_three_fields():
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.record_setup_pending("admin", secret="JBSWY3DPEHPK3PXP")

        doc = await _doc(db, "admin")
        assert doc is not None, "row must exist after upsert"
        assert doc["_id"] == "admin"
        assert doc["twofa_secret"] == "JBSWY3DPEHPK3PXP"
        assert doc["twofa_enabled"] is False
        assert isinstance(doc["twofa_setup_started_at"], datetime)
        # Motor decodes BSON Date as naive datetime — legacy quirk
        # preserved (BSON does not carry tzinfo). Originating write
        # was UTC-aware; storage shape is naive UTC.
        print("✓ test_2_record_setup_pending_creates_row_with_three_fields")
    finally:
        client.close()


async def test_3_record_setup_pending_overwrites_secret_on_re_setup():
    """Re-running setup overwrites the secret but does NOT clear
    older audit timestamps (legacy quirk — only $set three fields)."""
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.record_setup_pending("admin", secret="OLD_SECRET_XXXXX")
        # Seed a stale audit field as if a prior cycle had enabled+disabled.
        # NOTE: stored as naive UTC datetime to match the legacy
        # storage shape (BSON Date doesn't carry tzinfo).
        stale_dt = datetime(2020, 1, 1)
        await db[AdminSecurityRepository.COLLECTION].update_one(
            {"_id": "admin"},
            {"$set": {"twofa_enabled_at": stale_dt, "twofa_disabled_at": stale_dt}},
        )
        await repo.record_setup_pending("admin", secret="NEW_SECRET_YYYYY")
        doc = await _doc(db, "admin")
        assert doc["twofa_secret"] == "NEW_SECRET_YYYYY"
        assert doc["twofa_enabled"] is False
        # Legacy quirk: old audit timestamps linger
        assert doc.get("twofa_enabled_at") == stale_dt
        assert doc.get("twofa_disabled_at") == stale_dt
        print("✓ test_3_record_setup_pending_overwrites_secret_on_re_setup")
    finally:
        client.close()


async def test_4_mark_enabled_transitions_existing_row():
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.record_setup_pending("admin", secret="JBSWY3DPEHPK3PXP")
        await repo.mark_enabled("admin")
        doc = await _doc(db, "admin")
        assert doc["twofa_enabled"] is True
        assert isinstance(doc["twofa_enabled_at"], datetime)
        # Secret is preserved through the transition
        assert doc["twofa_secret"] == "JBSWY3DPEHPK3PXP"
        print("✓ test_4_mark_enabled_transitions_existing_row")
    finally:
        client.close()


async def test_5_mark_enabled_is_noop_when_no_row():
    """Legacy quirk: mark_enabled does NOT upsert. If no row exists,
    nothing happens (silent — matched_count=0)."""
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.mark_enabled("admin")  # no preceding setup
        doc = await _doc(db, "admin")
        assert doc is None, f"mark_enabled MUST NOT upsert; got {doc!r}"
        print("✓ test_5_mark_enabled_is_noop_when_no_row")
    finally:
        client.close()


async def test_6_clear_2fa_wipes_secret_and_disables():
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.record_setup_pending("admin", secret="JBSWY3DPEHPK3PXP")
        await repo.mark_enabled("admin")
        await repo.clear_2fa("admin")
        doc = await _doc(db, "admin")
        assert doc["twofa_enabled"] is False
        assert doc["twofa_secret"] is None
        assert isinstance(doc["twofa_disabled_at"], datetime)
        print("✓ test_6_clear_2fa_wipes_secret_and_disables")
    finally:
        client.close()


async def test_7_clear_2fa_upserts_on_virgin_install():
    """Legacy quirk: clear_2fa upserts. Disabling on a virgin install
    materialises a row in the disabled shape."""
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.clear_2fa("admin")  # no preceding setup
        doc = await _doc(db, "admin")
        assert doc is not None, "clear_2fa MUST upsert"
        assert doc["twofa_enabled"] is False
        assert doc["twofa_secret"] is None
        assert isinstance(doc["twofa_disabled_at"], datetime)
        print("✓ test_7_clear_2fa_upserts_on_virgin_install")
    finally:
        client.close()


async def test_8_get_state_returns_full_doc_with_id():
    """Legacy quirk: NO ``_id`` projection — caller sees the admin
    scope id."""
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.record_setup_pending("admin", secret="JBSWY3DPEHPK3PXP")
        doc = await repo.get_state("admin")
        assert doc is not None
        assert doc["_id"] == "admin"
        assert doc["twofa_secret"] == "JBSWY3DPEHPK3PXP"
        assert doc["twofa_enabled"] is False
        print("✓ test_8_get_state_returns_full_doc_with_id")
    finally:
        client.close()


async def test_9_per_admin_scoping_isolated():
    """Different admin_id values produce isolated rows."""
    client, db = await _fresh_db()
    try:
        repo = AdminSecurityRepository(db)
        await repo.record_setup_pending("admin", secret="AAA")
        await repo.record_setup_pending("manager-7", secret="BBB")
        a = await repo.get_state("admin")
        m = await repo.get_state("manager-7")
        assert a["twofa_secret"] == "AAA"
        assert m["twofa_secret"] == "BBB"
        assert a["_id"] == "admin"
        assert m["_id"] == "manager-7"
        print("✓ test_9_per_admin_scoping_isolated")
    finally:
        client.close()


async def main():
    tests = [
        test_1_get_state_miss_returns_none,
        test_2_record_setup_pending_creates_row_with_three_fields,
        test_3_record_setup_pending_overwrites_secret_on_re_setup,
        test_4_mark_enabled_transitions_existing_row,
        test_5_mark_enabled_is_noop_when_no_row,
        test_6_clear_2fa_wipes_secret_and_disables,
        test_7_clear_2fa_upserts_on_virgin_install,
        test_8_get_state_returns_full_doc_with_id,
        test_9_per_admin_scoping_isolated,
    ]
    fails = 0
    for t in tests:
        try:
            await t()
        except Exception as e:
            fails += 1
            print(f"✗ {t.__name__}: {e}")

    # Cleanup test DB
    client = AsyncIOMotorClient(MONGO_URL)
    await client.drop_database(TEST_DB)
    client.close()

    print(f"\n{'=' * 60}")
    print(f"AdminSecurityRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
