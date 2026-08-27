"""
Phase 5.3 / C-9 — NotificationRuleRepository unit contract tests.
=================================================================

Mirror of C-1..C-8 unit suites: live Motor against a throw-away
database; covers every named-verb business operation; pins each
preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python tests/test_notification_rules_repository.py
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

from app.repositories import NotificationRuleRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "notification_rules_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[NotificationRuleRepository.COLLECTION].drop()
    return client, db


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rule(event: str, *, enabled: bool = True,
          targets: list | None = None,
          created_at: str | None = None) -> dict:
    """Build a legacy-shape rule doc — caller composes id, event, targets."""
    return {
        "id":         f"rule_{event}",
        "event":      event,
        "enabled":    enabled,
        "targets":    targets if targets is not None else [
            {"audience": "customer", "channels": ["email", "in_app"]}
        ],
        "created_at": created_at or _iso(),
    }


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def test_1_count_all_empty():
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        assert await repo.count_all() == 0
        print("✓ test_1_count_all_empty")
    finally:
        client.close()


async def test_2_count_all_after_bulk_create():
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        await repo.bulk_create([
            _rule("invoice.issued"),
            _rule("payment.received"),
            _rule("lead.created"),
        ])
        assert await repo.count_all() == 3
        print("✓ test_2_count_all_after_bulk_create")
    finally:
        client.close()


async def test_3_find_by_event_hit():
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        await repo.bulk_create([_rule("invoice.issued", enabled=False)])
        r = await repo.find_by_event("invoice.issued")
        assert r is not None
        assert r["event"] == "invoice.issued"
        assert r["enabled"] is False
        assert r["id"] == "rule_invoice.issued"
        # _id projection
        assert "_id" not in r
        print("✓ test_3_find_by_event_hit")
    finally:
        client.close()


async def test_4_find_by_event_miss_returns_none():
    """No match → None. Default-rules fallback chain lives at caller."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        await repo.bulk_create([_rule("a")])
        assert await repo.find_by_event("nonexistent.event") is None
        print("✓ test_4_find_by_event_miss_returns_none")
    finally:
        client.close()


async def test_5_list_all_sorted_empty():
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        items = await repo.list_all_sorted()
        assert items == []
        print("✓ test_5_list_all_sorted_empty")
    finally:
        client.close()


async def test_6_list_all_sorted_returns_all_no_cap():
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        # Insert in non-sorted order
        await repo.bulk_create([
            _rule("z.event"), _rule("a.event"), _rule("m.event"), _rule("b.event")
        ])
        items = await repo.list_all_sorted()
        assert len(items) == 4
        events = [r["event"] for r in items]
        assert events == sorted(events), f"sort broken: {events}"
        # _id projection
        assert all("_id" not in r for r in items)
        print("✓ test_6_list_all_sorted_returns_all_no_cap")
    finally:
        client.close()


async def test_7_list_all_sorted_no_filter_returns_everything():
    """list_all_sorted has NO filter — returns the full collection."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        await repo.bulk_create([
            _rule("e1", enabled=True),
            _rule("e2", enabled=False),
            _rule("e3", enabled=True),
        ])
        items = await repo.list_all_sorted()
        assert len(items) == 3
        # Even disabled rules are returned (admin needs to see them)
        assert any(r["enabled"] is False for r in items)
        print("✓ test_7_list_all_sorted_no_filter_returns_everything")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------

async def test_8_bulk_create_empty_is_noop():
    """Empty list MUST NOT raise (legacy `if docs:` guard)."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        await repo.bulk_create([])
        assert await repo.count_all() == 0
        print("✓ test_8_bulk_create_empty_is_noop")
    finally:
        client.close()


async def test_9_bulk_create_writes_docs_as_is():
    """Repo does NOT inject id/event/timestamp — caller composes."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        custom = {
            "id":          "rule_custom",
            "event":       "x.y",
            "enabled":     True,
            "targets":     [],
            "created_at":  "2026-01-01T00:00:00+00:00",
            "extra_field": "preserved",
        }
        await repo.bulk_create([custom])
        r = await repo.find_by_event("x.y")
        assert r["id"] == "rule_custom"
        assert r["extra_field"] == "preserved"
        assert r["created_at"] == "2026-01-01T00:00:00+00:00"
        print("✓ test_9_bulk_create_writes_docs_as_is")
    finally:
        client.close()


async def test_10_upsert_by_event_creates_when_absent():
    """Upsert-insert path — caller composes full $set incl. id + event."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        assert await repo.find_by_event("new.event") is None
        set_doc = {
            "enabled":    True,
            "targets":    [{"audience": "manager", "channels": ["email"]}],
            "updated_at": _iso(),
            "event":      "new.event",         # legacy duplication
            "id":         "rule_new.event",    # legacy deterministic id
        }
        await repo.upsert_by_event("new.event", set_doc=set_doc)
        r = await repo.find_by_event("new.event")
        assert r is not None
        assert r["event"] == "new.event"
        assert r["id"] == "rule_new.event"
        assert r["enabled"] is True
        print("✓ test_10_upsert_by_event_creates_when_absent")
    finally:
        client.close()


async def test_11_upsert_by_event_updates_existing():
    """Upsert-update path — second upsert with same event keeps one doc."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        await repo.bulk_create([_rule("e1", enabled=True)])
        await repo.upsert_by_event("e1", set_doc={
            "enabled":    False,
            "targets":    [],
            "updated_at": _iso(),
            "event":      "e1",
            "id":         "rule_e1",
        })
        coll = db[NotificationRuleRepository.COLLECTION]
        assert await coll.count_documents({"event": "e1"}) == 1
        r = await repo.find_by_event("e1")
        assert r["enabled"] is False
        assert r["targets"] == []
        print("✓ test_11_upsert_by_event_updates_existing")
    finally:
        client.close()


async def test_12_upsert_by_event_only_touches_set_keys():
    """$set replaces the specified keys; other doc fields preserved."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        # Insert with extra fields
        coll = db[NotificationRuleRepository.COLLECTION]
        await coll.insert_one({
            "id":         "rule_e1",
            "event":      "e1",
            "enabled":    True,
            "targets":    [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "extra_meta": "preserved",
        })
        await repo.upsert_by_event("e1", set_doc={
            "enabled":    False,
            "updated_at": "2026-02-02T00:00:00+00:00",
            "event":      "e1",
            "id":         "rule_e1",
        })
        r = await repo.find_by_event("e1")
        assert r["enabled"] is False
        assert r["updated_at"] == "2026-02-02T00:00:00+00:00"
        # Untouched fields preserved
        assert r["created_at"] == "2026-01-01T00:00:00+00:00"
        assert r["extra_meta"] == "preserved"
        print("✓ test_12_upsert_by_event_only_touches_set_keys")
    finally:
        client.close()


async def test_13_upsert_by_event_caller_composes_full_set_shape():
    """Legacy quirk: caller DUPLICATES event and id inside $set so an
    upsert-INSERT produces a doc with those fields populated even
    though they're also the filter values."""
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        # $set WITH event+id duplication
        await repo.upsert_by_event("e_with_dup", set_doc={
            "enabled":    True,
            "targets":    [],
            "updated_at": _iso(),
            "event":      "e_with_dup",
            "id":         "rule_e_with_dup",
        })
        r = await repo.find_by_event("e_with_dup")
        assert r["event"] == "e_with_dup"
        assert r["id"] == "rule_e_with_dup"
        # The repository wrote the $set verbatim — both filter
        # duplication fields are present.
        print("✓ test_13_upsert_by_event_caller_composes_full_set_shape")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Full lifecycle — 2 writer + 4 reader contexts in one scenario
# ----------------------------------------------------------------------

async def test_14_full_lifecycle():
    """Mirrors the legacy notifications.py + admin endpoint flow:

      Phase A — boot existence gate          count_all() == 0
      Phase B — boot bulk seed               bulk_create([3 default rules])
      Phase C — boot re-gate (idempotent)    count_all() > 0 → skip
      Phase D — runtime dispatch lookup hit  find_by_event(event)
      Phase E — runtime dispatch miss        find_by_event(unknown) → None
                                              (caller does DEFAULT_RULES
                                               fallback)
      Phase F — admin list                   list_all_sorted() → sorted
      Phase G — admin upsert new event       upsert_by_event(new, ...)
      Phase H — admin upsert existing event  upsert_by_event(existing,
                                              { enabled:false })
      Phase I — admin re-read after upsert   find_by_event(existing) →
                                              fresh shape
    """
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)

        # Phase A
        assert await repo.count_all() == 0

        # Phase B
        seeds = [
            _rule("invoice.issued"),
            _rule("lead.created"),
            _rule("payment.received"),
        ]
        await repo.bulk_create(seeds)
        assert await repo.count_all() == 3

        # Phase C — idempotent re-gate at caller
        assert await repo.count_all() == 3  # still 3, no re-seed

        # Phase D
        hit = await repo.find_by_event("invoice.issued")
        assert hit is not None and hit["enabled"] is True

        # Phase E
        miss = await repo.find_by_event("nonexistent.event")
        assert miss is None  # caller does default fallback

        # Phase F
        items = await repo.list_all_sorted()
        events = [r["event"] for r in items]
        assert events == sorted(events)
        assert "invoice.issued" in events

        # Phase G — upsert new
        await repo.upsert_by_event("custom.event", set_doc={
            "enabled":    True,
            "targets":    [{"audience": "admin", "channels": ["in_app"]}],
            "updated_at": _iso(),
            "event":      "custom.event",
            "id":         "rule_custom.event",
        })
        assert await repo.count_all() == 4

        # Phase H — upsert existing
        await repo.upsert_by_event("invoice.issued", set_doc={
            "enabled":    False,
            "targets":    [],
            "updated_at": _iso(),
            "event":      "invoice.issued",
            "id":         "rule_invoice.issued",
        })
        # Still 4 — upsert matched
        assert await repo.count_all() == 4

        # Phase I
        fresh = await repo.find_by_event("invoice.issued")
        assert fresh["enabled"] is False
        assert fresh["targets"] == []

        print("✓ test_14_full_lifecycle")
    finally:
        client.close()


async def test_15_id_field_does_not_drive_lookup():
    """Legacy quirk: lookups are by `event` NOT by `id`.

    A doc inserted with id="rule_xxx" but event="yyy" is found by event
    via find_by_event("yyy"), NOT by find_by_event("xxx").
    """
    client, db = await _fresh_db()
    try:
        repo = NotificationRuleRepository(db)
        coll = db[NotificationRuleRepository.COLLECTION]
        await coll.insert_one({
            "id":         "rule_xxx_mismatched",
            "event":      "yyy.actual",
            "enabled":    True,
            "targets":    [],
            "created_at": _iso(),
        })
        # Find by event works
        r = await repo.find_by_event("yyy.actual")
        assert r is not None
        # Find by the id-as-event does NOT match
        miss = await repo.find_by_event("rule_xxx_mismatched")
        assert miss is None
        print("✓ test_15_id_field_does_not_drive_lookup")
    finally:
        client.close()


async def main():
    tests = [
        test_1_count_all_empty,
        test_2_count_all_after_bulk_create,
        test_3_find_by_event_hit,
        test_4_find_by_event_miss_returns_none,
        test_5_list_all_sorted_empty,
        test_6_list_all_sorted_returns_all_no_cap,
        test_7_list_all_sorted_no_filter_returns_everything,
        test_8_bulk_create_empty_is_noop,
        test_9_bulk_create_writes_docs_as_is,
        test_10_upsert_by_event_creates_when_absent,
        test_11_upsert_by_event_updates_existing,
        test_12_upsert_by_event_only_touches_set_keys,
        test_13_upsert_by_event_caller_composes_full_set_shape,
        test_14_full_lifecycle,
        test_15_id_field_does_not_drive_lookup,
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
    print(f"NotificationRuleRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
