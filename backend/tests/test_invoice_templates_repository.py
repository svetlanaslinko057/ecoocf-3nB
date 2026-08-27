"""
Phase 5.3 / C-5 — InvoiceTemplateRepository unit contract tests.
================================================================

Mirror of C-1/C-2/C-3/C-4 unit suites: live Motor against a
throw-away database; covers every named-verb business operation;
pins each preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python tests/test_invoice_templates_repository.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.repositories import InvoiceTemplateRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "invoice_templates_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[InvoiceTemplateRepository.COLLECTION].drop()
    return client, db


def _tpl(tid: str, *, kind: str = "after_win", active: bool = True, version: int = 1) -> dict:
    return {
        "id":         tid,
        "name":       f"Template {tid}",
        "kind":       kind,
        "items":      [{"key": "x", "label": "X", "amount": 0,
                        "currency": "EUR", "payment_type": "bank",
                        "is_official": True, "type": "fee"}],
        "active":     active,
        "notes":      "test",
        "version":    version,
        "created_by": "test",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def test_1_get_by_id_miss_returns_none():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        out = await repo.get_by_id("tpl_missing")
        assert out is None
        print("✓ test_1_get_by_id_miss_returns_none")
    finally:
        client.close()


async def test_2_get_by_id_projects_out_mongo_id():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a"))
        doc = await repo.get_by_id("tpl_a")
        assert doc is not None
        assert "_id" not in doc, f"_id MUST be projected out, got {doc!r}"
        assert doc["id"] == "tpl_a"
        print("✓ test_2_get_by_id_projects_out_mongo_id")
    finally:
        client.close()


async def test_3_get_current_does_NOT_project_out_mongo_id():
    """Legacy quirk: line 440 of financial_breakdown.py has no
    projection — preserved by `get_current`."""
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a"))
        doc = await repo.get_current("tpl_a")
        assert doc is not None
        assert "_id" in doc, f"get_current MUST preserve _id (legacy quirk); got {doc!r}"
        assert doc["id"] == "tpl_a"
        assert doc["version"] == 1
        print("✓ test_3_get_current_does_NOT_project_out_mongo_id")
    finally:
        client.close()


async def test_4_exists_by_id_returns_bool():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        assert await repo.exists_by_id("tpl_nope") is False
        await repo.create(_tpl("tpl_a"))
        assert await repo.exists_by_id("tpl_a") is True
        # Even soft-deleted (active=False) ones still exist
        await repo.soft_delete("tpl_a", deleted_by_id="admin@x", at_iso="2026-01-02T00:00:00Z")
        assert await repo.exists_by_id("tpl_a") is True
        print("✓ test_4_exists_by_id_returns_bool")
    finally:
        client.close()


async def test_5_list_filtered_no_filter():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a", kind="after_win"))
        await repo.create(_tpl("tpl_b", kind="final"))
        out = await repo.list_filtered()
        assert len(out) == 2
        # sorted by kind asc: 'after_win' < 'final'
        assert out[0]["kind"] == "after_win"
        assert out[1]["kind"] == "final"
        assert all("_id" not in d for d in out)
        print("✓ test_5_list_filtered_no_filter")
    finally:
        client.close()


async def test_6_list_filtered_by_kind():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a", kind="after_win"))
        await repo.create(_tpl("tpl_b", kind="final"))
        out = await repo.list_filtered(kind="final")
        assert len(out) == 1
        assert out[0]["id"] == "tpl_b"
        print("✓ test_6_list_filtered_by_kind")
    finally:
        client.close()


async def test_7_list_filtered_by_active():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a", active=True))
        await repo.create(_tpl("tpl_b", active=False))
        active = await repo.list_filtered(active=True)
        inactive = await repo.list_filtered(active=False)
        assert {d["id"] for d in active} == {"tpl_a"}
        assert {d["id"] for d in inactive} == {"tpl_b"}
        print("✓ test_7_list_filtered_by_active")
    finally:
        client.close()


async def test_8_get_active_by_id_filters_inactive_out():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_inactive", active=False))
        out = await repo.get_active_by_id("tpl_inactive")
        assert out is None, f"inactive templates MUST return None, got {out!r}"
        # Active one returns
        await repo.create(_tpl("tpl_active", active=True))
        out = await repo.get_active_by_id("tpl_active")
        assert out is not None
        assert "_id" not in out
        print("✓ test_8_get_active_by_id_filters_inactive_out")
    finally:
        client.close()


async def test_9_get_active_by_kind_returns_first_active():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        # Two active templates of the same kind — Mongo natural order
        await repo.create(_tpl("tpl_x", kind="final", active=True))
        await repo.create(_tpl("tpl_y", kind="final", active=True))
        out = await repo.get_active_by_kind("final")
        assert out is not None
        assert out["id"] in {"tpl_x", "tpl_y"}
        assert "_id" not in out
        # Inactive ones not returned
        out = await repo.get_active_by_kind("missing_kind")
        assert out is None
        print("✓ test_9_get_active_by_kind_returns_first_active")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------

async def test_10_create_inserts_as_is():
    """The repository does NOT inject anything — caller's dict is persisted verbatim."""
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        doc = _tpl("tpl_a")
        doc["custom_field"] = "lingers"
        await repo.create(doc)
        out = await repo.get_by_id("tpl_a")
        assert out["custom_field"] == "lingers"
        assert out["version"] == 1
        print("✓ test_10_create_inserts_as_is")
    finally:
        client.close()


async def test_11_apply_patch_replaces_set_keys():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a", version=1))
        await repo.apply_patch(
            "tpl_a",
            set_doc={"name": "New Name", "version": 2, "updated_at": "ts2"},
        )
        out = await repo.get_by_id("tpl_a")
        assert out["name"] == "New Name"
        assert out["version"] == 2
        assert out["updated_at"] == "ts2"
        # Untouched keys preserved
        assert out["kind"] == "after_win"
        print("✓ test_11_apply_patch_replaces_set_keys")
    finally:
        client.close()


async def test_12_apply_patch_silent_on_not_found():
    """`update_one` semantics — no exception on missing id."""
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.apply_patch("tpl_nope", set_doc={"name": "X"})
        # No row created (update_one without upsert)
        assert await repo.exists_by_id("tpl_nope") is False
        print("✓ test_12_apply_patch_silent_on_not_found")
    finally:
        client.close()


async def test_13_soft_delete_sets_four_fields_only():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a", version=3))
        await repo.soft_delete(
            "tpl_a",
            deleted_by_id="admin@bibi.cars",
            at_iso="2026-05-18T20:00:00+00:00",
        )
        out = await repo.get_current("tpl_a")
        assert out["active"] is False
        assert out["deleted_by"] == "admin@bibi.cars"
        assert out["deleted_at"] == "2026-05-18T20:00:00+00:00"
        assert out["updated_at"] == "2026-05-18T20:00:00+00:00"
        # Legacy quirk: version NOT touched
        assert out["version"] == 3
        # Doc NOT removed
        assert await repo.exists_by_id("tpl_a") is True
        print("✓ test_13_soft_delete_sets_four_fields_only")
    finally:
        client.close()


async def test_14_soft_delete_then_get_active_returns_none():
    """End-to-end: soft-deleted template no longer surfaces via
    `get_active_by_id` / `get_active_by_kind`."""
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.create(_tpl("tpl_a", kind="after_win", active=True))
        await repo.soft_delete("tpl_a", deleted_by_id="admin", at_iso="ts")
        assert await repo.get_active_by_id("tpl_a") is None
        assert await repo.get_active_by_kind("after_win") is None
        # But the doc still exists for audit
        assert await repo.exists_by_id("tpl_a") is True
        print("✓ test_14_soft_delete_then_get_active_returns_none")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Infrastructure
# ----------------------------------------------------------------------

async def test_15_ensure_indexes_creates_two_idx_silent_on_repeat():
    client, db = await _fresh_db()
    try:
        repo = InvoiceTemplateRepository(db)
        await repo.ensure_indexes()
        idx = await db[InvoiceTemplateRepository.COLLECTION].index_information()
        # Mongo default '_id_' + the two we created
        names = set(idx.keys())
        assert "_id_" in names
        assert any("id_1" in n for n in names), f"id index missing: {names}"
        assert any("kind_1_active_1" in n for n in names), f"kind+active index missing: {names}"
        # Idempotent — re-running must not raise
        await repo.ensure_indexes()
        print("✓ test_15_ensure_indexes_creates_two_idx_silent_on_repeat")
    finally:
        client.close()


async def test_16_ensure_indexes_silent_on_conflict():
    """If an index already exists with conflicting options, the
    legacy quirk is to swallow the error and log a warning. The
    repository preserves this contract."""
    client, db = await _fresh_db()
    try:
        coll = db[InvoiceTemplateRepository.COLLECTION]
        # Pre-create a non-unique index on `id` to conflict with the unique one
        await coll.create_index([("id", 1)], unique=False, name="id_1")
        repo = InvoiceTemplateRepository(db)
        # Must NOT raise — legacy try/except contract
        await repo.ensure_indexes()
        print("✓ test_16_ensure_indexes_silent_on_conflict")
    finally:
        client.close()


async def main():
    tests = [
        test_1_get_by_id_miss_returns_none,
        test_2_get_by_id_projects_out_mongo_id,
        test_3_get_current_does_NOT_project_out_mongo_id,
        test_4_exists_by_id_returns_bool,
        test_5_list_filtered_no_filter,
        test_6_list_filtered_by_kind,
        test_7_list_filtered_by_active,
        test_8_get_active_by_id_filters_inactive_out,
        test_9_get_active_by_kind_returns_first_active,
        test_10_create_inserts_as_is,
        test_11_apply_patch_replaces_set_keys,
        test_12_apply_patch_silent_on_not_found,
        test_13_soft_delete_sets_four_fields_only,
        test_14_soft_delete_then_get_active_returns_none,
        test_15_ensure_indexes_creates_two_idx_silent_on_repeat,
        test_16_ensure_indexes_silent_on_conflict,
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
    print(f"InvoiceTemplateRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
