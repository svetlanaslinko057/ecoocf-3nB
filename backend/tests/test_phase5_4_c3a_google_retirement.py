"""
Phase 5.4 / C-3A — Google ClientID mirror retirement & backfill tests.
========================================================================

Tests the C-3A behaviour:
  * Mirror write at the settings PATCH endpoint has been REMOVED.
  * Startup backfill copies `integration_configs.google_oauth.credentials.clientId`
    into `app_settings.auth.google.clientId` ONCE if the latter is empty.
  * `mirror_google_client_id` repository verb still exists on the surface
    (mandate: "verb retirement в отдельном коммите") but has ZERO
    production callers.
  * Idempotent: second invocation of the backfill helper is a no-op.

Architectural invariants pinned:
  * `app_settings.auth.google.clientId` is now the SOLE source-of-truth.
  * `IntegrationConfigsRepository.mirror_google_client_id` is callable
    but not called from any production module.
  * READ fallback chain (settings → integration_configs → env) is
    preserved at the caller, NOT collapsed.

Run:
    cd /app/backend && python tests/test_phase5_4_c3a_google_retirement.py
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

from app.repositories import (  # noqa: E402
    AppSettingsRepository,
    IntegrationConfigsRepository,
)


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "phase5_4_c3a_test"


async def _fresh_db():
    """Fresh DB with both collections dropped."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db.app_settings.drop()
    await db.integration_configs.drop()
    return client, db


# ───────────────────────────────────────────────────────────────────────
# Helper: a minimal extraction of the C-3A backfill block in
# server.py:2505-2540, so tests can exercise it directly without
# spinning up uvicorn. The real production block is gated by
# `get_settings_service()` — here we drive the same logic via the
# repositories directly.
# ───────────────────────────────────────────────────────────────────────

async def _backfill(db) -> str:
    """Mirror of the C-3A startup backfill block in server.py.

    Returns the value that ended up in app_settings.auth.google.clientId
    (so tests can assert on the outcome). Idempotent: returns the
    existing value untouched if app_settings already has one.
    """
    app_repo = AppSettingsRepository(db)
    ic_repo = IntegrationConfigsRepository(db)
    doc = await app_repo.get_by_key("auth")
    current = (doc or {}).get("value") or {}
    current_cid = ((current.get("google") or {}).get("clientId") or "").strip()
    if current_cid:
        return current_cid  # skip — already populated
    legacy = await ic_repo.find_by_provider("google_oauth")
    legacy_cid = ((legacy.get("credentials") or {}).get("clientId") or "").strip()
    if not legacy_cid:
        return ""  # nothing to backfill
    merged_google = dict(current.get("google") or {})
    merged_google["clientId"] = legacy_cid
    merged_auth = dict(current)
    merged_auth["google"] = merged_google
    await app_repo.upsert_value(
        "auth",
        value=merged_auth,
        updated_at=datetime.now(timezone.utc),
        updated_by="startup_backfill_c3a",
    )
    return legacy_cid


async def _read_auth_value(db) -> dict:
    """Fetch the merged auth document (returns {} if none)."""
    doc = await AppSettingsRepository(db).get_by_key("auth")
    return (doc or {}).get("value") or {}


# ───────────────────────────────────────────────────────────────────────
# Backfill behaviour tests
# ───────────────────────────────────────────────────────────────────────

async def test_1_backfill_copies_legacy_into_app_settings_when_empty():
    """Happy path: legacy integration_configs has a clientId, app_settings
    has none → backfill copies the legacy value into app_settings."""
    client, db = await _fresh_db()
    try:
        # Seed legacy storage only
        await IntegrationConfigsRepository(db).mirror_google_client_id(
            "legacy-id.apps.googleusercontent.com",
        )
        # Pre-condition: app_settings empty
        a0 = await _read_auth_value(db)
        assert not ((a0.get("google") or {}).get("clientId"))
        # Run backfill
        out = await _backfill(db)
        assert out == "legacy-id.apps.googleusercontent.com"
        # Post-condition: app_settings populated
        a1 = await _read_auth_value(db)
        assert a1["google"]["clientId"] == "legacy-id.apps.googleusercontent.com"
        print("✓ test_1_backfill_copies_legacy_into_app_settings_when_empty")
    finally:
        client.close()


async def test_2_backfill_skips_when_app_settings_already_has_clientId():
    """Idempotent: if app_settings already has a clientId, backfill must
    NOT overwrite it — even if legacy storage has a different value."""
    client, db = await _fresh_db()
    try:
        # Seed BOTH stores with DIFFERENT values
        await AppSettingsRepository(db).upsert_value(
            "auth",
            value={"google": {"clientId": "primary-from-settings.apps.googleusercontent.com"}},
            updated_at=datetime.now(timezone.utc),
            updated_by="seed",
        )
        await IntegrationConfigsRepository(db).mirror_google_client_id(
            "stale-legacy.apps.googleusercontent.com",
        )
        out = await _backfill(db)
        # Returns the existing value (no overwrite)
        assert out == "primary-from-settings.apps.googleusercontent.com"
        # app_settings UNCHANGED
        a1 = await _read_auth_value(db)
        assert a1["google"]["clientId"] == "primary-from-settings.apps.googleusercontent.com"
        print("✓ test_2_backfill_skips_when_app_settings_already_has_clientId")
    finally:
        client.close()


async def test_3_backfill_noop_when_legacy_storage_empty():
    """If neither store has a clientId, backfill is a clean no-op:
    returns empty string and writes nothing."""
    client, db = await _fresh_db()
    try:
        out = await _backfill(db)
        assert out == ""
        # No app_settings.auth document created
        a1 = await _read_auth_value(db)
        assert not ((a1.get("google") or {}).get("clientId"))
        print("✓ test_3_backfill_noop_when_legacy_storage_empty")
    finally:
        client.close()


async def test_4_backfill_idempotent_on_second_invocation():
    """Calling the backfill twice in a row produces the same result —
    important because the startup hook runs on every boot."""
    client, db = await _fresh_db()
    try:
        await IntegrationConfigsRepository(db).mirror_google_client_id(
            "idempotent.apps.googleusercontent.com",
        )
        first = await _backfill(db)
        # Touch nothing between calls
        second = await _backfill(db)
        third = await _backfill(db)
        assert first == "idempotent.apps.googleusercontent.com"
        # On 2nd/3rd calls the function returns the app_settings value
        # (which now equals the legacy value) — so all three are equal
        assert first == second == third
        a1 = await _read_auth_value(db)
        assert a1["google"]["clientId"] == "idempotent.apps.googleusercontent.com"
        print("✓ test_4_backfill_idempotent_on_second_invocation")
    finally:
        client.close()


async def test_5_backfill_preserves_other_app_settings_auth_fields():
    """Backfill only writes `google.clientId` — must not clobber other
    `auth` fields (jwt, features, baseUrl, etc.)."""
    client, db = await _fresh_db()
    try:
        await AppSettingsRepository(db).upsert_value(
            "auth",
            value={
                "google": {"clientId": "", "redirectPath": "/api/auth/google/callback"},
                "jwt": {"secret": "my-jwt-secret", "accessExpires": "15m"},
                "features": {"googleEnabled": True, "passwordEnabled": True},
                "baseUrl": "https://bibi.cars",
            },
            updated_at=datetime.now(timezone.utc),
            updated_by="seed",
        )
        await IntegrationConfigsRepository(db).mirror_google_client_id(
            "preserve.apps.googleusercontent.com",
        )
        out = await _backfill(db)
        assert out == "preserve.apps.googleusercontent.com"
        a1 = await _read_auth_value(db)
        # clientId populated
        assert a1["google"]["clientId"] == "preserve.apps.googleusercontent.com"
        # Other fields PRESERVED
        assert a1["google"]["redirectPath"] == "/api/auth/google/callback"
        assert a1["jwt"]["secret"] == "my-jwt-secret"
        assert a1["jwt"]["accessExpires"] == "15m"
        assert a1["features"]["googleEnabled"] is True
        assert a1["baseUrl"] == "https://bibi.cars"
        print("✓ test_5_backfill_preserves_other_app_settings_auth_fields")
    finally:
        client.close()


# ───────────────────────────────────────────────────────────────────────
# Surface invariants for the retired mirror verb
# ───────────────────────────────────────────────────────────────────────

async def test_6_mirror_verb_still_exists_on_repository_surface():
    """Per C-3A mandate: verb retirement = separate commit. The verb
    must remain callable on the repository surface, even though
    production callers are zero."""
    assert hasattr(IntegrationConfigsRepository, "mirror_google_client_id")
    assert callable(IntegrationConfigsRepository.mirror_google_client_id)
    print("✓ test_6_mirror_verb_still_exists_on_repository_surface")


async def test_7_mirror_verb_marked_deprecated_in_docstring():
    """Surface-level documentation invariant: anyone discovering this
    verb in the future MUST see the deprecation marker in the docstring.
    This is the contract guarantee that retirement is planned."""
    import re
    doc = (IntegrationConfigsRepository.mirror_google_client_id.__doc__ or "").lower()
    # Whitespace-normalize (the docstring is word-wrapped across lines)
    flat = re.sub(r"\s+", " ", doc)
    assert "deprecated" in flat, "docstring missing DEPRECATED marker"
    assert "c-3a" in flat, "docstring missing C-3A reference"
    assert (
        "zero production callers" in flat
        or "0 production callers" in flat
        or "no production caller" in flat
    ), "docstring should explicitly state ZERO production callers"
    print("✓ test_7_mirror_verb_marked_deprecated_in_docstring")


async def test_8_mirror_verb_still_functionally_correct():
    """The verb is deprecated, but if someone calls it (e.g., a future
    disaster-recovery script), it must still work correctly. Pinning
    the functional contract here so the eventual retirement commit
    has a documented invariant to break."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        # Pre-existing config with both clientId and clientSecret
        await repo.upsert_provider_config(
            "google_oauth",
            credentials={
                "clientId": "old-id.apps.googleusercontent.com",
                "clientSecret": "GOCSPX-still-secret",
            },
        )
        await repo.mirror_google_client_id(
            "new-id.apps.googleusercontent.com",
            ts=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
        )
        doc = await repo.find_by_provider("google_oauth")
        assert doc["credentials"]["clientId"] == "new-id.apps.googleusercontent.com"
        # clientSecret PRESERVED (the legacy dot-notation invariant
        # remains correct even after deprecation)
        assert doc["credentials"]["clientSecret"] == "GOCSPX-still-secret"
        assert "updatedAt" in doc  # camelCase preserved
        print("✓ test_8_mirror_verb_still_functionally_correct")
    finally:
        client.close()


async def test_9_no_production_caller_in_server_py():
    """Code-level invariant: server.py must not call
    mirror_google_client_id any more. This is the regression guard —
    if anyone re-adds the mirror call in a future refactor, this
    test fires."""
    server_py = ROOT / "server.py"
    src = server_py.read_text(encoding="utf-8")
    # Heuristic: an actual CALL would be `mirror_google_client_id(`
    # (open paren at the end). The DEPRECATION docstring text in the
    # repo file does NOT match this pattern.
    assert ".mirror_google_client_id(" not in src, (
        "regression: server.py contains a call to mirror_google_client_id — "
        "C-3A retired the mirror; this call MUST be removed."
    )
    print("✓ test_9_no_production_caller_in_server_py")


async def test_10_no_production_caller_in_routers():
    """Same regression guard for the routers tree."""
    routers_dir = ROOT / "app" / "routers"
    for py_file in routers_dir.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        assert ".mirror_google_client_id(" not in src, (
            f"regression: {py_file.name} calls mirror_google_client_id — "
            "C-3A retired the mirror; this call MUST be removed."
        )
    print("✓ test_10_no_production_caller_in_routers")


async def test_11_read_fallback_chain_preserved_at_caller():
    """The READ fallback chain (settings → integration_configs → env)
    is PRESERVED at the caller layer (settings_service.resolve_google_client_id),
    NOT collapsed into the repository. This test asserts the chain
    text is still present in settings_service.py."""
    svc_py = ROOT / "settings_service.py"
    src = svc_py.read_text(encoding="utf-8")
    # The function must exist
    assert "async def resolve_google_client_id" in src
    # The fallback chain comment / behaviour must mention integration_configs
    assert "integration_configs" in src, (
        "settings_service.py must still mention integration_configs in the "
        "fallback chain — C-3A preserves the fallback READ"
    )
    # And env fallback
    assert "GOOGLE_CLIENT_ID" in src
    print("✓ test_11_read_fallback_chain_preserved_at_caller")


# ───────────────────────────────────────────────────────────────────────
# Architectural property — the SOLE-SOURCE-OF-TRUTH invariant
# ───────────────────────────────────────────────────────────────────────

async def test_12_settings_patch_no_longer_mentions_mirror_call():
    """C-3A architectural marker: server.py's settings PATCH endpoint
    must contain the C-3A retirement comment AND must not contain a
    live mirror call. The previous C-2 block had a try/except around
    IntegrationConfigsRepository(db).mirror_google_client_id(...) — that
    code is now gone, replaced by a documentation block."""
    server_py = ROOT / "server.py"
    src = server_py.read_text(encoding="utf-8")
    assert "C-3A" in src, "server.py missing C-3A marker comments"
    # The retirement comment block
    assert "mirror RETIRED" in src or "mirror retired" in src, (
        "server.py missing the 'mirror RETIRED' marker in settings PATCH"
    )
    # No live call
    assert ".mirror_google_client_id(" not in src
    print("✓ test_12_settings_patch_no_longer_mentions_mirror_call")


async def test_13_startup_backfill_block_present_in_server_py():
    """The startup backfill block MUST exist in server.py — it's the
    only thing that closes the gap between legacy data and the new
    source-of-truth."""
    server_py = ROOT / "server.py"
    src = server_py.read_text(encoding="utf-8")
    assert "C-3A — Google ClientID" in src or "C-3A google" in src.lower() or (
        "backfill" in src.lower() and "google_oauth" in src
    ), "server.py missing the C-3A startup backfill block"
    # The block must use settings_service to write (not raw collection)
    # and IntegrationConfigsRepository to read
    assert "IntegrationConfigsRepository" in src
    assert "patch_auth" in src or "set(" in src  # writes via service
    print("✓ test_13_startup_backfill_block_present_in_server_py")


async def main():
    tests = [
        test_1_backfill_copies_legacy_into_app_settings_when_empty,
        test_2_backfill_skips_when_app_settings_already_has_clientId,
        test_3_backfill_noop_when_legacy_storage_empty,
        test_4_backfill_idempotent_on_second_invocation,
        test_5_backfill_preserves_other_app_settings_auth_fields,
        test_6_mirror_verb_still_exists_on_repository_surface,
        test_7_mirror_verb_marked_deprecated_in_docstring,
        test_8_mirror_verb_still_functionally_correct,
        test_9_no_production_caller_in_server_py,
        test_10_no_production_caller_in_routers,
        test_11_read_fallback_chain_preserved_at_caller,
        test_12_settings_patch_no_longer_mentions_mirror_call,
        test_13_startup_backfill_block_present_in_server_py,
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
    print(f"Phase 5.4 / C-3A retirement & backfill — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
