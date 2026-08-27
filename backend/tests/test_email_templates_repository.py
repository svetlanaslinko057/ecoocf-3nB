"""
Phase 5.3 / C-8 — EmailTemplateRepository unit contract tests.
==============================================================

Mirror of C-1..C-7 unit suites: live Motor against a throw-away
database; covers every named-verb business operation; pins each
preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python tests/test_email_templates_repository.py
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

from app.repositories import EmailTemplateRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "email_templates_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[EmailTemplateRepository.COLLECTION].drop()
    return client, db


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tpl(event: str, audience: str = "customer", lang: str = "en",
         *, subject: str = "", html: str = "", active: bool = True,
         text_template: str = "") -> dict:
    """Build a legacy-shape template doc — caller composes id and timestamp."""
    return {
        "id":            f"tpl_{event}_{audience}_{lang}",
        "event":         event,
        "audience":      audience,
        "lang":          lang,
        "subject":       subject or f"Subject for {event}",
        "html":          html or f"<p>{event}</p>",
        "text_template": text_template,
        "active":        active,
        "created_at":    _iso(),
    }


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def test_1_count_all_empty():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        assert await repo.count_all() == 0
        print("✓ test_1_count_all_empty")
    finally:
        client.close()


async def test_2_count_all_after_bulk_create():
    """count_all is the boot existence sentinel; must reflect inserts."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([_tpl("e1"), _tpl("e2"), _tpl("e3")])
        assert await repo.count_all() == 3
        print("✓ test_2_count_all_after_bulk_create")
    finally:
        client.close()


async def test_3_find_for_dispatch_exact_match():
    """Exact 3-key tuple lookup with _id projected out."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([
            _tpl("invoice_issued", audience="customer", lang="en", subject="EN-CUST"),
            _tpl("invoice_issued", audience="customer", lang="bg", subject="BG-CUST"),
            _tpl("invoice_issued", audience="manager",  lang="en", subject="EN-MGR"),
        ])
        hit = await repo.find_for_dispatch(
            "invoice_issued", audience="customer", lang="bg"
        )
        assert hit is not None
        assert hit["subject"] == "BG-CUST"
        # _id projection
        assert "_id" not in hit
        print("✓ test_3_find_for_dispatch_exact_match")
    finally:
        client.close()


async def test_4_find_for_dispatch_returns_none_on_miss():
    """No match → None. (Fallback chain lives at the caller, not here.)"""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([_tpl("e1", audience="customer", lang="en")])
        miss = await repo.find_for_dispatch("e1", audience="manager", lang="en")
        assert miss is None
        miss = await repo.find_for_dispatch("e1", audience="customer", lang="ua")
        assert miss is None
        print("✓ test_4_find_for_dispatch_returns_none_on_miss")
    finally:
        client.close()


async def test_5_list_filtered_no_filters_returns_all():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([
            _tpl("a", lang="en"), _tpl("a", lang="bg"),
            _tpl("b", lang="en"), _tpl("c", lang="en"),
        ])
        items = await repo.list_filtered()
        assert len(items) == 4
        # _id projection
        assert all("_id" not in t for t in items)
        print("✓ test_5_list_filtered_no_filters_returns_all")
    finally:
        client.close()


async def test_6_list_filtered_sort_order():
    """Sort by [(event, 1), (audience, 1), (lang, 1)]."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([
            _tpl("z", audience="manager", lang="en"),
            _tpl("a", audience="customer", lang="bg"),
            _tpl("a", audience="customer", lang="en"),
            _tpl("a", audience="manager",  lang="en"),
            _tpl("m", audience="customer", lang="en"),
        ])
        items = await repo.list_filtered()
        keys = [(t["event"], t["audience"], t["lang"]) for t in items]
        assert keys == sorted(keys), f"sort broken: {keys}"
        print("✓ test_6_list_filtered_sort_order")
    finally:
        client.close()


async def test_7_list_filtered_event_filter():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([
            _tpl("e1"), _tpl("e1", lang="bg"), _tpl("e2"),
        ])
        items = await repo.list_filtered(event="e1")
        assert {t["lang"] for t in items} == {"en", "bg"}
        assert all(t["event"] == "e1" for t in items)
        print("✓ test_7_list_filtered_event_filter")
    finally:
        client.close()


async def test_8_list_filtered_three_filters_combined():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([
            _tpl("e1", "customer", "en"),
            _tpl("e1", "customer", "bg"),
            _tpl("e1", "manager",  "en"),
        ])
        items = await repo.list_filtered(
            event="e1", audience="customer", lang="bg"
        )
        assert len(items) == 1
        assert items[0]["lang"] == "bg"
        assert items[0]["audience"] == "customer"
        print("✓ test_8_list_filtered_three_filters_combined")
    finally:
        client.close()


async def test_9_list_filtered_empty_string_treated_as_absent():
    """Legacy truthiness quirk: empty string filters are ignored."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([_tpl("e1"), _tpl("e2")])
        items = await repo.list_filtered(event="", audience="", lang="")
        assert len(items) == 2
        print("✓ test_9_list_filtered_empty_string_treated_as_absent")
    finally:
        client.close()


async def test_10_get_by_id_projects_out_id():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([_tpl("e1")])
        t = await repo.get_by_id("tpl_e1_customer_en")
        assert t is not None
        assert "_id" not in t
        assert t["id"] == "tpl_e1_customer_en"
        assert (await repo.get_by_id("tpl_missing")) is None
        print("✓ test_10_get_by_id_projects_out_id")
    finally:
        client.close()


async def test_11_exists_by_id():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        assert await repo.exists_by_id("tpl_anything") is False
        await repo.bulk_create([_tpl("e1")])
        assert await repo.exists_by_id("tpl_e1_customer_en") is True
        assert await repo.exists_by_id("tpl_e1_customer_bg") is False
        print("✓ test_11_exists_by_id")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------

async def test_12_bulk_create_empty_is_noop():
    """Legacy quirk: empty list MUST NOT raise (insert_many with [] would)."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        # MUST NOT raise
        await repo.bulk_create([])
        assert await repo.count_all() == 0
        print("✓ test_12_bulk_create_empty_is_noop")
    finally:
        client.close()


async def test_13_bulk_create_writes_docs_as_is():
    """Repository does NOT inject id/timestamp/anything."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        custom = {
            "id":            "tpl_custom_id",
            "event":         "x",
            "audience":      "customer",
            "lang":          "en",
            "subject":       "S",
            "html":          "H",
            "text_template": "T",
            "active":        True,
            "created_at":    "2026-01-01T00:00:00+00:00",
            "extra_field":   "preserved",
        }
        await repo.bulk_create([custom])
        t = await repo.get_by_id("tpl_custom_id")
        assert t["id"] == "tpl_custom_id"
        assert t["extra_field"] == "preserved", "repo MUST not strip fields"
        assert t["created_at"] == "2026-01-01T00:00:00+00:00"
        print("✓ test_13_bulk_create_writes_docs_as_is")
    finally:
        client.close()


async def test_14_apply_patch_silent_on_not_found():
    """update_one semantics: silent on not-found. Caller GATES via exists_by_id."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        # MUST NOT raise
        await repo.apply_patch("tpl_missing", set_doc={"active": False})
        assert await repo.count_all() == 0
        print("✓ test_14_apply_patch_silent_on_not_found")
    finally:
        client.close()


async def test_15_apply_patch_replaces_set_keys():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        await repo.bulk_create([_tpl("e1", subject="OLD", html="OLD")])
        await repo.apply_patch(
            "tpl_e1_customer_en",
            set_doc={"subject": "NEW", "active": False, "updated_at": "2026-02-02"},
        )
        t = await repo.get_by_id("tpl_e1_customer_en")
        assert t["subject"] == "NEW"
        assert t["active"] is False
        assert t["updated_at"] == "2026-02-02"
        # untouched fields preserved
        assert t["html"] == "OLD"
        assert t["lang"] == "en"
        print("✓ test_15_apply_patch_replaces_set_keys")
    finally:
        client.close()


async def test_16_upsert_by_id_creates_when_absent():
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        assert await repo.exists_by_id("tpl_new_customer_en") is False
        doc = _tpl("new", subject="CREATED")
        await repo.upsert_by_id("tpl_new_customer_en", doc=doc)
        t = await repo.get_by_id("tpl_new_customer_en")
        assert t is not None
        assert t["subject"] == "CREATED"
        print("✓ test_16_upsert_by_id_creates_when_absent")
    finally:
        client.close()


async def test_17_upsert_by_id_idempotent_replace():
    """Re-POST same id → replaces (idempotent admin POST workflow)."""
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)
        doc1 = _tpl("e1", subject="V1")
        doc2 = _tpl("e1", subject="V2", text_template="extra")
        await repo.upsert_by_id("tpl_e1_customer_en", doc=doc1)
        await repo.upsert_by_id("tpl_e1_customer_en", doc=doc2)
        coll = db[EmailTemplateRepository.COLLECTION]
        assert await coll.count_documents({"id": "tpl_e1_customer_en"}) == 1
        t = await repo.get_by_id("tpl_e1_customer_en")
        assert t["subject"] == "V2"
        assert t["text_template"] == "extra"
        print("✓ test_17_upsert_by_id_idempotent_replace")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Full lifecycle — all 3 writer + 4 reader contexts in one scenario
# ----------------------------------------------------------------------

async def test_18_full_seed_dispatch_admin_lifecycle():
    """Mirrors the legacy NotificationService + admin endpoint flow:

        Phase A — boot existence gate         count_all() == 0
        Phase B — boot bulk seed              bulk_create([3 seeds])
        Phase C — boot re-gate (idempotent)   count_all() > 0 → skip
        Phase D — runtime dispatch lookup     find_for_dispatch(e, a, l)
        Phase E — admin list (no filters)     list_filtered() → 3 items
        Phase F — admin list (filtered)       list_filtered(event=...)
        Phase G — admin PATCH (with guard)    exists + apply_patch + get_by_id
        Phase H — admin POST (upsert new)     upsert_by_id(...)
        Phase I — admin POST (upsert replace) upsert_by_id(same id, new doc)
    """
    client, db = await _fresh_db()
    try:
        repo = EmailTemplateRepository(db)

        # Phase A — boot existence gate (legacy line 638 truthiness check)
        assert await repo.count_all() == 0

        # Phase B — boot bulk seed (legacy line 647)
        seeds = [
            _tpl("invoice_issued", "customer", "en"),
            _tpl("invoice_issued", "customer", "bg"),
            _tpl("payment_received", "customer", "en"),
        ]
        await repo.bulk_create(seeds)
        assert await repo.count_all() == 3

        # Phase C — boot re-gate (idempotent — caller skips on non-zero)
        assert await repo.count_all() == 3  # still 3, no re-seed at caller

        # Phase D — runtime dispatch lookup (legacy line 673)
        hit_en = await repo.find_for_dispatch(
            "invoice_issued", audience="customer", lang="en"
        )
        assert hit_en is not None and hit_en["lang"] == "en"
        hit_bg = await repo.find_for_dispatch(
            "invoice_issued", audience="customer", lang="bg"
        )
        assert hit_bg is not None and hit_bg["lang"] == "bg"
        miss = await repo.find_for_dispatch(
            "invoice_issued", audience="customer", lang="ua"
        )
        assert miss is None  # caller does language fallback chain

        # Phase E — admin list (legacy line 1035)
        all_items = await repo.list_filtered()
        assert len(all_items) == 3

        # Phase F — admin list filtered
        invoice_items = await repo.list_filtered(event="invoice_issued")
        assert len(invoice_items) == 2
        assert all(t["event"] == "invoice_issued" for t in invoice_items)

        # Phase G — admin PATCH (with exists_by_id guard, replaces legacy
        # matched_count idiom — legacy lines 1048-1050)
        target = "tpl_invoice_issued_customer_en"
        assert await repo.exists_by_id(target) is True
        await repo.apply_patch(target, set_doc={
            "subject": "PATCHED",
            "updated_at": _iso(),
        })
        patched = await repo.get_by_id(target)
        assert patched["subject"] == "PATCHED"
        assert "updated_at" in patched

        # Phase H — admin POST (upsert new — legacy line 1079)
        new_id = "tpl_invoice_issued_customer_ua"
        new_doc = _tpl("invoice_issued", "customer", "ua", subject="UA-NEW")
        await repo.upsert_by_id(new_id, doc=new_doc)
        assert await repo.exists_by_id(new_id) is True
        assert await repo.count_all() == 4

        # Phase I — admin POST (upsert replace — same id, new content)
        replaced_doc = _tpl("invoice_issued", "customer", "ua", subject="UA-V2")
        await repo.upsert_by_id(new_id, doc=replaced_doc)
        # Still 4 total — no duplicate
        assert await repo.count_all() == 4
        t = await repo.get_by_id(new_id)
        assert t["subject"] == "UA-V2"

        print("✓ test_18_full_seed_dispatch_admin_lifecycle")
    finally:
        client.close()


async def main():
    tests = [
        test_1_count_all_empty,
        test_2_count_all_after_bulk_create,
        test_3_find_for_dispatch_exact_match,
        test_4_find_for_dispatch_returns_none_on_miss,
        test_5_list_filtered_no_filters_returns_all,
        test_6_list_filtered_sort_order,
        test_7_list_filtered_event_filter,
        test_8_list_filtered_three_filters_combined,
        test_9_list_filtered_empty_string_treated_as_absent,
        test_10_get_by_id_projects_out_id,
        test_11_exists_by_id,
        test_12_bulk_create_empty_is_noop,
        test_13_bulk_create_writes_docs_as_is,
        test_14_apply_patch_silent_on_not_found,
        test_15_apply_patch_replaces_set_keys,
        test_16_upsert_by_id_creates_when_absent,
        test_17_upsert_by_id_idempotent_replace,
        test_18_full_seed_dispatch_admin_lifecycle,
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
    print(f"EmailTemplateRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
