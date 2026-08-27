"""
Phase 5.3 / C-4 — ProviderStatsRepository unit contract tests.
==============================================================

Mirror of C-1/C-2/C-3 unit suites: live Motor against a throw-away
database; covers every named-verb business operation; pins each
preserved legacy quirk by an explicit scenario.

Run:
    cd /app/backend && python tests/test_provider_stats_repository.py
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

from app.repositories import ProviderStatsRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "provider_stats_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[ProviderStatsRepository.COLLECTION].drop()
    return client, db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

async def test_1_get_for_provider_miss_returns_none():
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        out = await repo.get_for_provider("pid_missing")
        assert out is None, f"expected None on miss, got {out!r}"
        print("✓ test_1_get_for_provider_miss_returns_none")
    finally:
        client.close()


async def test_2_get_for_provider_projects_out_id():
    """Legacy quirk: every read uses {'_id': 0}."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        await repo.upsert_snapshot(
            "pid_a",
            stats={"providerId": "pid_a", "score": 70, "tier": "normal"},
            created_at_iso=_now_iso(),
        )
        doc = await repo.get_for_provider("pid_a")
        assert doc is not None
        assert "_id" not in doc, f"_id MUST be projected out, got {doc!r}"
        assert doc["providerId"] == "pid_a"
        assert doc["score"] == 70
        print("✓ test_2_get_for_provider_projects_out_id")
    finally:
        client.close()


async def test_3_list_ranked_orders_by_score_desc():
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        await repo.upsert_snapshot(
            "pid_low",
            stats={"providerId": "pid_low", "score": 25},
            created_at_iso=_now_iso(),
        )
        await repo.upsert_snapshot(
            "pid_high",
            stats={"providerId": "pid_high", "score": 95},
            created_at_iso=_now_iso(),
        )
        await repo.upsert_snapshot(
            "pid_mid",
            stats={"providerId": "pid_mid", "score": 55},
            created_at_iso=_now_iso(),
        )
        out = await repo.list_ranked()
        assert [d["providerId"] for d in out] == ["pid_high", "pid_mid", "pid_low"]
        assert all("_id" not in d for d in out)
        print("✓ test_3_list_ranked_orders_by_score_desc")
    finally:
        client.close()


async def test_4_list_unsorted_returns_all_no_order_guarantee():
    """Legacy `list_all(sort_by_score=False)` path. No ordering
    guarantee — just that all docs are returned and `_id` is
    projected out."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        for pid, score in [("pid_x", 10), ("pid_y", 90), ("pid_z", 40)]:
            await repo.upsert_snapshot(
                pid, stats={"providerId": pid, "score": score},
                created_at_iso=_now_iso(),
            )
        out = await repo.list_unsorted()
        ids = sorted(d["providerId"] for d in out)
        assert ids == ["pid_x", "pid_y", "pid_z"]
        assert all("_id" not in d for d in out)
        print("✓ test_4_list_unsorted_returns_all_no_order_guarantee")
    finally:
        client.close()


async def test_5_find_for_providers_returns_dict():
    """Returns a {providerId: snapshot} dict for the candidate list."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        for pid, score in [("pid_a", 70), ("pid_b", 30), ("pid_c", 90)]:
            await repo.upsert_snapshot(
                pid, stats={"providerId": pid, "score": score},
                created_at_iso=_now_iso(),
            )
        out = await repo.find_for_providers(["pid_a", "pid_c"])
        assert set(out.keys()) == {"pid_a", "pid_c"}
        assert out["pid_a"]["score"] == 70
        assert out["pid_c"]["score"] == 90
        assert all("_id" not in d for d in out.values())
        print("✓ test_5_find_for_providers_returns_dict")
    finally:
        client.close()


async def test_6_find_for_providers_silently_omits_missing():
    """Providers without a snapshot are silently absent from the
    result (legacy line 376-378 substitutes a neutral default at
    the service side)."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        await repo.upsert_snapshot(
            "pid_exists",
            stats={"providerId": "pid_exists", "score": 50},
            created_at_iso=_now_iso(),
        )
        out = await repo.find_for_providers(["pid_exists", "pid_missing"])
        assert "pid_exists" in out
        assert "pid_missing" not in out
        print("✓ test_6_find_for_providers_silently_omits_missing")
    finally:
        client.close()


async def test_7_find_for_providers_empty_input_returns_empty_dict():
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        out = await repo.find_for_providers([])
        assert out == {}, f"empty input must return empty dict, got {out!r}"
        print("✓ test_7_find_for_providers_empty_input_returns_empty_dict")
    finally:
        client.close()


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------

async def test_8_upsert_snapshot_inserts_with_created_at():
    """First write installs createdAt via $setOnInsert."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        ts1 = _now_iso()
        await repo.upsert_snapshot(
            "pid_a",
            stats={"providerId": "pid_a", "score": 60, "updatedAt": ts1},
            created_at_iso=ts1,
        )
        doc = await db[ProviderStatsRepository.COLLECTION].find_one(
            {"providerId": "pid_a"}
        )
        assert doc["createdAt"] == ts1
        assert doc["score"] == 60
        assert doc["updatedAt"] == ts1
        print("✓ test_8_upsert_snapshot_inserts_with_created_at")
    finally:
        client.close()


async def test_9_upsert_snapshot_preserves_created_at_on_update():
    """Re-upsert does NOT touch createdAt — only $set fields move.

    Mirrors the legacy idempotency contract: ``createdAt`` is
    installed once, all subsequent snapshots only refresh the
    payload."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        ts_create = "2026-01-01T00:00:00+00:00"
        ts_update = "2026-05-18T20:00:00+00:00"

        # First write
        await repo.upsert_snapshot(
            "pid_a",
            stats={"providerId": "pid_a", "score": 60, "updatedAt": ts_create},
            created_at_iso=ts_create,
        )

        # Second write with a different "would-be" createdAt — must be ignored
        await repo.upsert_snapshot(
            "pid_a",
            stats={"providerId": "pid_a", "score": 75, "updatedAt": ts_update},
            created_at_iso=ts_update,
        )

        doc = await db[ProviderStatsRepository.COLLECTION].find_one(
            {"providerId": "pid_a"}
        )
        assert doc["createdAt"] == ts_create, (
            f"createdAt MUST be preserved on re-upsert; got {doc['createdAt']!r}"
        )
        assert doc["score"] == 75, "payload must update"
        assert doc["updatedAt"] == ts_update
        print("✓ test_9_upsert_snapshot_preserves_created_at_on_update")
    finally:
        client.close()


async def test_10_upsert_snapshot_replaces_payload_keys():
    """`$set` REPLACES the named keys; keys that disappear from
    the new payload remain in the document (legacy `$set`
    semantics — no key deletion). This is a load-bearing quirk
    of the legacy site."""
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        # Snapshot 1 includes lastTierNotifyAt
        ts = _now_iso()
        await repo.upsert_snapshot(
            "pid_a",
            stats={
                "providerId": "pid_a",
                "score": 60,
                "lastTierNotifyAt": ts,
                "updatedAt": ts,
            },
            created_at_iso=ts,
        )
        # Snapshot 2 omits lastTierNotifyAt → field persists
        await repo.upsert_snapshot(
            "pid_a",
            stats={"providerId": "pid_a", "score": 75, "updatedAt": ts},
            created_at_iso=ts,
        )
        doc = await db[ProviderStatsRepository.COLLECTION].find_one(
            {"providerId": "pid_a"}
        )
        # Legacy quirk: lastTierNotifyAt LINGERS because $set doesn't unset
        # absent keys. The service ALWAYS includes lastTierNotifyAt in
        # the stats dict when it wants the field to remain (see
        # legacy line 284), or omits to let it linger.
        assert doc["lastTierNotifyAt"] == ts
        assert doc["score"] == 75
        print("✓ test_10_upsert_snapshot_replaces_payload_keys")
    finally:
        client.close()


async def test_11_per_provider_scoping_isolated():
    client, db = await _fresh_db()
    try:
        repo = ProviderStatsRepository(db)
        await repo.upsert_snapshot(
            "pid_a", stats={"providerId": "pid_a", "score": 10},
            created_at_iso=_now_iso(),
        )
        await repo.upsert_snapshot(
            "pid_b", stats={"providerId": "pid_b", "score": 90},
            created_at_iso=_now_iso(),
        )
        a = await repo.get_for_provider("pid_a")
        b = await repo.get_for_provider("pid_b")
        assert a["score"] == 10
        assert b["score"] == 90
        print("✓ test_11_per_provider_scoping_isolated")
    finally:
        client.close()


async def main():
    tests = [
        test_1_get_for_provider_miss_returns_none,
        test_2_get_for_provider_projects_out_id,
        test_3_list_ranked_orders_by_score_desc,
        test_4_list_unsorted_returns_all_no_order_guarantee,
        test_5_find_for_providers_returns_dict,
        test_6_find_for_providers_silently_omits_missing,
        test_7_find_for_providers_empty_input_returns_empty_dict,
        test_8_upsert_snapshot_inserts_with_created_at,
        test_9_upsert_snapshot_preserves_created_at_on_update,
        test_10_upsert_snapshot_replaces_payload_keys,
        test_11_per_provider_scoping_isolated,
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
    print(f"ProviderStatsRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
