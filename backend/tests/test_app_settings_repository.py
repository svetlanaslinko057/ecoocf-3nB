"""
Phase 5.3 / C-7 — AppSettingsRepository unit contract tests.
============================================================

Mirror of C-1..C-6 unit suites: live Motor against a throw-away
database; covers every named-verb business operation; pins each
preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python tests/test_app_settings_repository.py
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

from app.repositories import AppSettingsRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "app_settings_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[AppSettingsRepository.COLLECTION].drop()
    return client, db


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def test_1_get_by_key_returns_none_when_absent():
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        assert await repo.get_by_key("auth") is None
        assert await repo.get_by_key("anything") is None
        print("✓ test_1_get_by_key_returns_none_when_absent")
    finally:
        client.close()


async def test_2_get_by_key_returns_full_doc_including_id():
    """Legacy quirk: ``_id`` is NOT projected out."""
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        await repo.insert(
            "auth",
            value={"baseUrl": "https://x"},
            updated_at=_now(),
            updated_by="system",
        )
        doc = await repo.get_by_key("auth")
        assert doc is not None
        # ``_id`` IS present — legacy site never projects it out,
        # caller ignores it but the Mongo round-trip shape is identical.
        assert "_id" in doc, "legacy quirk: _id MUST be present in returned doc"
        assert doc["key"] == "auth"
        assert doc["value"] == {"baseUrl": "https://x"}
        assert doc["updatedBy"] == "system"
        assert isinstance(doc["updatedAt"], datetime)
        print("✓ test_2_get_by_key_returns_full_doc_including_id")
    finally:
        client.close()


async def test_3_get_by_key_filters_by_key_only():
    """``get_by_key`` matches on ``key`` field, not on ``_id`` or anything else."""
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        await repo.insert(
            "auth",
            value={"a": 1},
            updated_at=_now(),
            updated_by="system",
        )
        await repo.insert(
            "branding",
            value={"a": 2},
            updated_at=_now(),
            updated_by="system",
        )
        a = await repo.get_by_key("auth")
        b = await repo.get_by_key("branding")
        assert a is not None and a["value"] == {"a": 1}
        assert b is not None and b["value"] == {"a": 2}
        assert (await repo.get_by_key("missing")) is None
        print("✓ test_3_get_by_key_filters_by_key_only")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------

async def test_4_insert_writes_exactly_four_fields():
    """Legacy quirk: insert writes EXACTLY {key, value, updatedAt, updatedBy}."""
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        at = _now()
        await repo.insert(
            "auth",
            value={"baseUrl": "https://x"},
            updated_at=at,
            updated_by="system",
        )
        doc = await repo.get_by_key("auth")
        # Exactly 5 fields: _id (Mongo auto) + 4 written.
        assert set(doc.keys()) == {"_id", "key", "value", "updatedAt", "updatedBy"}, (
            f"insert should write exactly 4 fields + _id, got {set(doc.keys())}"
        )
        assert doc["key"] == "auth"
        assert doc["value"] == {"baseUrl": "https://x"}
        # Mongo strips tzinfo on roundtrip — compare naive-naive
        ret = doc["updatedAt"]
        at_naive = at.replace(tzinfo=None) if at.tzinfo else at
        ret_naive = ret.replace(tzinfo=None) if ret.tzinfo else ret
        assert abs((ret_naive - at_naive).total_seconds()) < 1
        assert doc["updatedBy"] == "system"
        print("✓ test_4_insert_writes_exactly_four_fields")
    finally:
        client.close()


async def test_5_insert_is_not_upsert():
    """Legacy quirk: ``insert`` is NOT upsert. A second call MUST NOT silently update.

    The collection has no unique index in production, so duplicates are
    physically possible. The legacy path is GUARDED at the caller side
    (ensure_defaults checks ``get_by_key`` is None first). The repository
    primitive is a plain ``insert_one``.
    """
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        at1 = _now()
        await repo.insert("auth", value={"v": 1}, updated_at=at1, updated_by="sys")
        # Second insert without guard → produces a second doc, NOT an update.
        at2 = _now()
        await repo.insert("auth", value={"v": 2}, updated_at=at2, updated_by="sys")
        coll = db[AppSettingsRepository.COLLECTION]
        count = await coll.count_documents({"key": "auth"})
        assert count == 2, (
            f"insert is not upsert — expected 2 docs after 2 inserts, got {count}"
        )
        print("✓ test_5_insert_is_not_upsert")
    finally:
        client.close()


async def test_6_upsert_value_creates_when_absent():
    """``upsert_value`` creates the doc if absent — runtime ``set`` semantics."""
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        assert await repo.get_by_key("auth") is None
        await repo.upsert_value(
            "auth",
            value={"baseUrl": "https://y"},
            updated_at=_now(),
            updated_by="admin",
        )
        doc = await repo.get_by_key("auth")
        assert doc is not None
        assert doc["value"] == {"baseUrl": "https://y"}
        assert doc["updatedBy"] == "admin"
        print("✓ test_6_upsert_value_creates_when_absent")
    finally:
        client.close()


async def test_7_upsert_value_updates_when_present():
    """``upsert_value`` updates the existing doc — second write wins on $set fields."""
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        await repo.insert(
            "auth",
            value={"v": 1, "baseUrl": "https://a"},
            updated_at=_now(),
            updated_by="system",
        )
        # Second write
        await repo.upsert_value(
            "auth",
            value={"v": 2, "baseUrl": "https://b"},
            updated_at=_now(),
            updated_by="admin",
        )
        doc = await repo.get_by_key("auth")
        assert doc["value"] == {"v": 2, "baseUrl": "https://b"}
        assert doc["updatedBy"] == "admin"
        # Still exactly one doc — upsert_value matched and updated.
        coll = db[AppSettingsRepository.COLLECTION]
        count = await coll.count_documents({"key": "auth"})
        assert count == 1
        print("✓ test_7_upsert_value_updates_when_present")
    finally:
        client.close()


async def test_8_upsert_value_replaces_value_dict_entirely():
    """Legacy semantics: ``$set value=<new>`` replaces the inner value
    object as a whole (NOT a deep merge — deep merge lives in
    SettingsService.patch_auth at the caller layer).
    """
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        await repo.insert(
            "auth",
            value={"baseUrl": "https://a", "feature": {"x": True}},
            updated_at=_now(),
            updated_by="sys",
        )
        # Re-upsert with a smaller value dict
        await repo.upsert_value(
            "auth",
            value={"baseUrl": "https://b"},
            updated_at=_now(),
            updated_by="admin",
        )
        doc = await repo.get_by_key("auth")
        # No "feature" key — value dict was replaced wholesale.
        assert doc["value"] == {"baseUrl": "https://b"}
        print("✓ test_8_upsert_value_replaces_value_dict_entirely")
    finally:
        client.close()


async def test_9_upsert_value_touches_only_three_fields():
    """Legacy quirk: $set on EXACTLY {value, updatedAt, updatedBy}.

    If the existing doc has extra fields (e.g. legacy migration artifacts,
    extensions), they MUST be preserved.
    """
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        # Inject a doc with an extra field directly (simulating a legacy
        # migration artifact)
        coll = db[AppSettingsRepository.COLLECTION]
        await coll.insert_one(
            {
                "key": "auth",
                "value": {"v": 1},
                "updatedAt": _now(),
                "updatedBy": "sys",
                "legacyField": "from-migration",
                "createdAt": _now(),
            }
        )
        # Upsert
        await repo.upsert_value(
            "auth",
            value={"v": 2},
            updated_at=_now(),
            updated_by="admin",
        )
        doc = await repo.get_by_key("auth")
        # Extra fields preserved.
        assert doc["legacyField"] == "from-migration"
        assert "createdAt" in doc
        # Touched fields updated.
        assert doc["value"] == {"v": 2}
        assert doc["updatedBy"] == "admin"
        print("✓ test_9_upsert_value_touches_only_three_fields")
    finally:
        client.close()


async def test_10_timestamp_stored_as_datetime():
    """Legacy quirk: ``updatedAt`` is a BSON datetime, NOT an ISO string.

    Other Phase 5.3 repos (C-5 / C-6) use ISO strings because their
    legacy sites did. ``app_settings`` differs by legacy; C-7
    preserves the inconsistency rather than normalising it.
    """
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await repo.insert("auth", value={}, updated_at=at, updated_by="sys")
        # Read the raw Mongo doc — bypass repo to confirm type
        coll = db[AppSettingsRepository.COLLECTION]
        raw = await coll.find_one({"key": "auth"})
        assert isinstance(raw["updatedAt"], datetime), (
            f"updatedAt should be datetime, got {type(raw['updatedAt'])}"
        )
        # Same for upsert path
        await repo.upsert_value("other", value={}, updated_at=at, updated_by="sys")
        raw2 = await coll.find_one({"key": "other"})
        assert isinstance(raw2["updatedAt"], datetime)
        print("✓ test_10_timestamp_stored_as_datetime")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Full lifecycle (mirrors the 3 SettingsService call paths)
# ----------------------------------------------------------------------

async def test_11_full_seed_then_runtime_set_lifecycle():
    """The full SettingsService journey through the repository:

        Phase A — boot existence gate     get_by_key(absent) → None
        Phase B — boot seed insert        insert(auth, defaults, system)
        Phase C — boot existence gate     get_by_key(present) → truthy
                                          (idempotent: no second insert)
        Phase D — runtime cached read     get_by_key(present) → doc
        Phase E — runtime admin upsert    upsert_value(auth, patched, admin)
        Phase F — runtime cached read     get_by_key reflects patch
        Phase G — runtime second admin    upsert_value(auth, again, admin)
                  upsert                  (still exactly 1 doc)
    """
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)

        # Phase A
        assert await repo.get_by_key("auth") is None

        # Phase B
        defaults = {
            "baseUrl": "",
            "google": {"clientId": ""},
            "features": {"googleEnabled": True},
        }
        await repo.insert(
            "auth",
            value=defaults,
            updated_at=_now(),
            updated_by="system",
        )

        # Phase C — idempotent gate
        doc1 = await repo.get_by_key("auth")
        assert doc1 is not None
        # In the legacy ensure_defaults flow, this is the moment the seed
        # path RETURNS without writing. The repository does nothing extra
        # — the orchestration gate is at the caller.

        # Phase D
        doc2 = await repo.get_by_key("auth")
        assert doc2["value"] == defaults

        # Phase E — admin patch
        await repo.upsert_value(
            "auth",
            value={**defaults, "baseUrl": "https://prod.example"},
            updated_at=_now(),
            updated_by="admin",
        )

        # Phase F
        doc3 = await repo.get_by_key("auth")
        assert doc3["value"]["baseUrl"] == "https://prod.example"
        assert doc3["updatedBy"] == "admin"

        # Phase G
        await repo.upsert_value(
            "auth",
            value={**defaults, "baseUrl": "https://prod.example", "patched": True},
            updated_at=_now(),
            updated_by="admin",
        )
        coll = db[AppSettingsRepository.COLLECTION]
        count = await coll.count_documents({"key": "auth"})
        assert count == 1, (
            f"upsert_value must NOT create duplicate docs — got {count}"
        )
        doc4 = await repo.get_by_key("auth")
        assert doc4["value"]["patched"] is True

        print("✓ test_11_full_seed_then_runtime_set_lifecycle")
    finally:
        client.close()


async def test_12_get_by_key_handles_extra_keys_independently():
    """Multiple keys coexist in the same collection — the repository
    primitive is key-scoped."""
    client, db = await _fresh_db()
    try:
        repo = AppSettingsRepository(db)
        await repo.insert("auth", value={"a": 1}, updated_at=_now(), updated_by="s")
        await repo.insert("branding", value={"b": 2}, updated_at=_now(), updated_by="s")
        await repo.insert("flags", value={"c": 3}, updated_at=_now(), updated_by="s")

        # Upsert "branding" should not touch "auth" or "flags"
        await repo.upsert_value(
            "branding", value={"b": 99}, updated_at=_now(), updated_by="admin"
        )
        assert (await repo.get_by_key("auth"))["value"] == {"a": 1}
        assert (await repo.get_by_key("branding"))["value"] == {"b": 99}
        assert (await repo.get_by_key("flags"))["value"] == {"c": 3}
        print("✓ test_12_get_by_key_handles_extra_keys_independently")
    finally:
        client.close()


async def main():
    tests = [
        test_1_get_by_key_returns_none_when_absent,
        test_2_get_by_key_returns_full_doc_including_id,
        test_3_get_by_key_filters_by_key_only,
        test_4_insert_writes_exactly_four_fields,
        test_5_insert_is_not_upsert,
        test_6_upsert_value_creates_when_absent,
        test_7_upsert_value_updates_when_present,
        test_8_upsert_value_replaces_value_dict_entirely,
        test_9_upsert_value_touches_only_three_fields,
        test_10_timestamp_stored_as_datetime,
        test_11_full_seed_then_runtime_set_lifecycle,
        test_12_get_by_key_handles_extra_keys_independently,
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
    print(f"AppSettingsRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
