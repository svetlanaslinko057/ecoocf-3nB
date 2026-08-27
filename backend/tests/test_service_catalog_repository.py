"""
Phase 5.3 / C-6 — ServiceCatalogRepository unit contract tests.
===============================================================

Mirror of C-1..C-5 unit suites: live Motor against a throw-away
database; covers every named-verb business operation; pins each
preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python tests/test_service_catalog_repository.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.repositories import ServiceCatalogRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "service_catalog_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[ServiceCatalogRepository.COLLECTION].drop()
    return client, db


def _svc(sid: str, *, name: str = None, category: str = "custom",
         is_active: bool = True, created_at: str = "2026-01-01T00:00:00+00:00") -> dict:
    return {
        "id":            sid,
        "code":          sid,
        "name":          name or sid,
        "name_en":       (name or sid).upper(),
        "description":   f"desc {sid}",
        "category":      category,
        "default_price": 50.0,
        "currency":      "USD",
        "default_qty":   1,
        "workflow":      [{"key": "pending", "label": "P"}],
        "is_active":     is_active,
        "created_at":    created_at,
        "created_by":    "test",
    }


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def test_1_count_all_empty():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        assert await repo.count_all() == 0
        print("✓ test_1_count_all_empty")
    finally:
        client.close()


async def test_2_count_all_after_inserts():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a"))
        await repo.create(_svc("svc_b"))
        assert await repo.count_all() == 2
        print("✓ test_2_count_all_after_inserts")
    finally:
        client.close()


async def test_3_list_by_name_default_active_only():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        # Active first to make sure name-sort holds regardless of insert order
        await repo.create(_svc("svc_b", name="Banana", is_active=True))
        await repo.create(_svc("svc_a", name="Apple", is_active=True))
        await repo.create(_svc("svc_z", name="Zucchini", is_active=False))
        out = await repo.list_by_name()
        names = [d["name"] for d in out]
        # Sorted by name asc, inactive filtered out
        assert names == ["Apple", "Banana"], f"got {names}"
        assert all("_id" not in d for d in out)
        print("✓ test_3_list_by_name_default_active_only")
    finally:
        client.close()


async def test_4_list_by_name_with_category_filter():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a", name="Apple", category="inspection"))
        await repo.create(_svc("svc_b", name="Banana", category="delivery"))
        out = await repo.list_by_name(category="inspection")
        assert {d["id"] for d in out} == {"svc_a"}
        print("✓ test_4_list_by_name_with_category_filter")
    finally:
        client.close()


async def test_5_list_by_name_active_only_false_returns_all():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a", name="Apple", is_active=True))
        await repo.create(_svc("svc_z", name="Zucchini", is_active=False))
        out = await repo.list_by_name(active_only=False)
        ids = [d["id"] for d in out]
        # Both returned, sorted by name asc
        assert ids == ["svc_a", "svc_z"], f"got {ids}"
        print("✓ test_5_list_by_name_active_only_false_returns_all")
    finally:
        client.close()


async def test_6_list_all_sort_by_created_at_desc():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_old", created_at="2026-01-01T00:00:00+00:00"))
        await repo.create(_svc("svc_new", created_at="2026-06-01T00:00:00+00:00"))
        await repo.create(_svc("svc_mid", created_at="2026-03-01T00:00:00+00:00"))
        out = await repo.list_all()
        assert [d["id"] for d in out] == ["svc_new", "svc_mid", "svc_old"]
        assert all("_id" not in d for d in out)
        print("✓ test_6_list_all_sort_by_created_at_desc")
    finally:
        client.close()


async def test_7_get_by_id_projects_out_id():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a"))
        doc = await repo.get_by_id("svc_a")
        assert doc is not None
        assert "_id" not in doc
        assert doc["id"] == "svc_a"
        # Miss returns None
        assert await repo.get_by_id("svc_nope") is None
        print("✓ test_7_get_by_id_projects_out_id")
    finally:
        client.close()


async def test_8_exists_by_id():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        assert await repo.exists_by_id("svc_nope") is False
        await repo.create(_svc("svc_a"))
        assert await repo.exists_by_id("svc_a") is True
        # Soft-deleted still exists
        await repo.soft_delete("svc_a", at_iso="2026-05-18T20:00:00Z")
        assert await repo.exists_by_id("svc_a") is True
        print("✓ test_8_exists_by_id")
    finally:
        client.close()


async def test_9_find_by_ids_returns_list():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a"))
        await repo.create(_svc("svc_b"))
        await repo.create(_svc("svc_c"))
        out = await repo.find_by_ids(["svc_a", "svc_c"])
        ids = sorted(d["id"] for d in out)
        assert ids == ["svc_a", "svc_c"]
        assert all("_id" not in d for d in out)
        # Missing ids silently omitted
        out = await repo.find_by_ids(["svc_a", "svc_nope"])
        assert [d["id"] for d in out] == ["svc_a"]
        # Empty input
        assert await repo.find_by_ids([]) == []
        print("✓ test_9_find_by_ids_returns_list")
    finally:
        client.close()


async def test_10_list_seed_managed_does_NOT_project_out_id():
    """Legacy quirk: line 14366 of server.py has no projection
    on the seed reconciliation cursor."""
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a"))
        await repo.create(_svc("svc_b"))
        out = await repo.list_seed_managed(["svc_a", "svc_b"])
        assert len(out) == 2
        # _id MUST be present (legacy quirk preserved)
        assert all("_id" in d for d in out), f"_id MUST be preserved (legacy); got {out!r}"
        # Empty input
        assert await repo.list_seed_managed([]) == []
        print("✓ test_10_list_seed_managed_does_NOT_project_out_id")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------

async def test_11_create_inserts_as_is():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        doc = _svc("svc_a")
        doc["custom_field"] = "preserved"
        await repo.create(doc)
        out = await repo.get_by_id("svc_a")
        assert out["custom_field"] == "preserved"
        assert out["currency"] == "USD"
        print("✓ test_11_create_inserts_as_is")
    finally:
        client.close()


async def test_12_apply_patch_silent_on_not_found():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.apply_patch("svc_nope", set_doc={"name": "X"})
        assert await repo.exists_by_id("svc_nope") is False
        print("✓ test_12_apply_patch_silent_on_not_found")
    finally:
        client.close()


async def test_13_apply_patch_replaces_set_keys():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc("svc_a", name="OldName"))
        await repo.apply_patch(
            "svc_a",
            set_doc={"name": "NewName", "updated_at": "ts2"},
        )
        out = await repo.get_by_id("svc_a")
        assert out["name"] == "NewName"
        assert out["updated_at"] == "ts2"
        # Untouched fields preserved
        assert out["category"] == "custom"
        print("✓ test_13_apply_patch_replaces_set_keys")
    finally:
        client.close()


async def test_14_apply_patch_backfill_workflow_translations():
    """Mirrors the seed-time backfill path that the server.py
    helper uses — proves repo can carry the same shape."""
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        await repo.create(_svc(
            "svc_a",
        ) | {"workflow": [{"key": "pending", "label": "Очікує"}]})
        await repo.apply_patch(
            "svc_a",
            set_doc={
                "workflow": [
                    {"key": "pending", "label": "Очікує",
                     "label_en": "Pending", "label_bg": "Чакащ"},
                ],
                "name_bg": "Услуга",
            },
        )
        out = await repo.get_by_id("svc_a")
        assert out["workflow"][0]["label_en"] == "Pending"
        assert out["workflow"][0]["label_bg"] == "Чакащ"
        assert out["name_bg"] == "Услуга"
        print("✓ test_14_apply_patch_backfill_workflow_translations")
    finally:
        client.close()


async def test_15_soft_delete_sets_two_fields_only():
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)
        doc = _svc("svc_a")
        doc["name"] = "ServiceA"
        await repo.create(doc)
        await repo.soft_delete("svc_a", at_iso="2026-05-18T20:00:00+00:00")
        cur = await repo.get_by_id("svc_a")
        assert cur["is_active"] is False
        assert cur["deleted_at"] == "2026-05-18T20:00:00+00:00"
        # Other fields untouched
        assert cur["name"] == "ServiceA"
        assert cur["currency"] == "USD"
        # Doc still exists
        assert await repo.exists_by_id("svc_a") is True
        # And filtered out of active list
        assert await repo.list_by_name(active_only=True) == []
        print("✓ test_15_soft_delete_sets_two_fields_only")
    finally:
        client.close()


async def test_16_full_seed_to_admin_lifecycle():
    """End-to-end: seed flow (count + create batch + list_seed_managed +
    apply_patch) then admin flow (list_all + get_by_id + apply_patch +
    soft_delete) — proves both writer contexts coexist."""
    client, db = await _fresh_db()
    try:
        repo = ServiceCatalogRepository(db)

        # Phase A: seed
        assert await repo.count_all() == 0
        seeded_ids = ["svc_seed_a", "svc_seed_b"]
        for sid in seeded_ids:
            await repo.create(_svc(sid))

        # Phase B: backfill
        managed = await repo.list_seed_managed(seeded_ids)
        assert len(managed) == 2
        for doc in managed:
            await repo.apply_patch(doc["id"], set_doc={"name_bg": f"BG-{doc['id']}"})
        for sid in seeded_ids:
            d = await repo.get_by_id(sid)
            assert d["name_bg"] == f"BG-{sid}"

        # Phase C: admin add custom service
        await repo.create(_svc("svc_custom", name="Custom"))
        all_admin = await repo.list_all()
        assert {d["id"] for d in all_admin} == {"svc_seed_a", "svc_seed_b", "svc_custom"}

        # Phase D: admin patch + delete
        await repo.apply_patch("svc_custom", set_doc={"default_price": 99})
        d = await repo.get_by_id("svc_custom")
        assert d["default_price"] == 99

        await repo.soft_delete("svc_custom", at_iso="ts")
        assert (await repo.get_by_id("svc_custom"))["is_active"] is False

        # Phase E: public view (active only)
        active_public = await repo.list_by_name(active_only=True)
        assert {d["id"] for d in active_public} == {"svc_seed_a", "svc_seed_b"}

        print("✓ test_16_full_seed_to_admin_lifecycle")
    finally:
        client.close()


async def main():
    tests = [
        test_1_count_all_empty,
        test_2_count_all_after_inserts,
        test_3_list_by_name_default_active_only,
        test_4_list_by_name_with_category_filter,
        test_5_list_by_name_active_only_false_returns_all,
        test_6_list_all_sort_by_created_at_desc,
        test_7_get_by_id_projects_out_id,
        test_8_exists_by_id,
        test_9_find_by_ids_returns_list,
        test_10_list_seed_managed_does_NOT_project_out_id,
        test_11_create_inserts_as_is,
        test_12_apply_patch_silent_on_not_found,
        test_13_apply_patch_replaces_set_keys,
        test_14_apply_patch_backfill_workflow_translations,
        test_15_soft_delete_sets_two_fields_only,
        test_16_full_seed_to_admin_lifecycle,
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
    print(f"ServiceCatalogRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
