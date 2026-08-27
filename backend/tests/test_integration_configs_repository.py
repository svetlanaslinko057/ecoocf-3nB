"""
Phase 5.4 / C-2 — IntegrationConfigsRepository unit contract tests.
====================================================================

Thirteenth-extraction CRUD-shaped tests (second Phase 5.4 suite).
Pins the five named verbs, the five-provider provider-key topology,
the legacy quirks (``... or {}`` read fallback, ``updated_at`` vs
``updatedAt`` casing divergence, ``credentials.clientId`` dot-notation
mirror), the provider-key isolation invariant, and the conditional-
set semantics of ``upsert_provider_config`` (only kwargs the caller
provides are written; others are left untouched).

Architectural property tests:
  * test_19 — 5 distinct verbs on the surface (matches the
    architectural answer: "5 named verbs collapsing 12 production
    sites onto 1 read + 4 distinct writes")
  * test_20 — provider-key isolation (writing "stripe" never
    touches "google_oauth" — the discriminator design holds)
  * test_21 — google_oauth mirror tension is EXPOSED at the
    contract surface (mirror_google_client_id is its own verb,
    not collapsed into upsert_provider_config)

Run:
    cd /app/backend && python tests/test_integration_configs_repository.py
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

from app.repositories import IntegrationConfigsRepository  # noqa: E402


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
TEST_DB = "integration_configs_repo_test"


async def _fresh_db():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[TEST_DB]
    await db[IntegrationConfigsRepository.COLLECTION].drop()
    return client, db


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ────────────────────────────────────────────────────────────────────────
# READ — find_by_provider (single verb consolidating 9 read sites)
# ────────────────────────────────────────────────────────────────────────

async def test_1_find_by_provider_returns_empty_dict_when_missing():
    """Legacy ``... or {}`` quirk: missing document → empty dict
    (NOT None). All 9 callers depend on this — a None would crash
    .get() chains at every read site."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        doc = await repo.find_by_provider("google_oauth")
        assert doc == {}, f"missing must return {{}}, got: {doc!r}"
        # Verify it's a dict (not None) so .get() chains work
        assert isinstance(doc, dict)
        assert doc.get("credentials") is None  # .get() must not raise
        print("✓ test_1_find_by_provider_returns_empty_dict_when_missing")
    finally:
        client.close()


async def test_2_find_by_provider_returns_full_document_when_present():
    """Returns the raw Mongo doc unchanged (no projection, no shaping)."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.upsert_provider_config(
            "stripe",
            credentials={"publishableKey": "pk_test_abc", "secretKey": "sk_test_xyz"},
            settings={"currency": "USD"},
            mode="sandbox",
            is_enabled=True,
            ts_iso="2026-05-19T07:00:00+00:00",
        )
        doc = await repo.find_by_provider("stripe")
        assert doc.get("provider") == "stripe"
        assert doc.get("credentials", {}).get("secretKey") == "sk_test_xyz"
        assert doc.get("settings", {}).get("currency") == "USD"
        assert doc.get("mode") == "sandbox"
        assert doc.get("isEnabled") is True
        assert doc.get("updated_at") == "2026-05-19T07:00:00+00:00"
        print("✓ test_2_find_by_provider_returns_full_document_when_present")
    finally:
        client.close()


# ────────────────────────────────────────────────────────────────────────
# WRITE 1 — upsert_provider_config (conditional-set semantics)
# ────────────────────────────────────────────────────────────────────────

async def test_3_upsert_credentials_only_leaves_other_fields_untouched():
    """Conditional-set: passing ONLY credentials must not clobber
    settings/mode/isEnabled set by a prior call. Mirrors the legacy
    ``if isinstance(data.get('credentials'), dict): ...`` logic."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        # Initial state — set all 4 conditional fields
        await repo.upsert_provider_config(
            "openai",
            credentials={"apiKey": "sk-original"},
            settings={"model": "gpt-4o"},
            mode="sandbox",
            is_enabled=True,
        )
        # Mutate only credentials
        await repo.upsert_provider_config(
            "openai",
            credentials={"apiKey": "sk-updated"},
        )
        doc = await repo.find_by_provider("openai")
        # credentials updated
        assert doc["credentials"]["apiKey"] == "sk-updated"
        # other fields preserved
        assert doc["settings"]["model"] == "gpt-4o"
        assert doc["mode"] == "sandbox"
        assert doc["isEnabled"] is True
        print("✓ test_3_upsert_credentials_only_leaves_other_fields_untouched")
    finally:
        client.close()


async def test_4_upsert_settings_only_leaves_credentials_untouched():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.upsert_provider_config(
            "stripe",
            credentials={"secretKey": "sk_test_keep"},
            mode="sandbox",
        )
        await repo.upsert_provider_config(
            "stripe",
            settings={"currency": "EUR"},
        )
        doc = await repo.find_by_provider("stripe")
        assert doc["credentials"]["secretKey"] == "sk_test_keep"
        assert doc["settings"]["currency"] == "EUR"
        assert doc["mode"] == "sandbox"
        print("✓ test_4_upsert_settings_only_leaves_credentials_untouched")
    finally:
        client.close()


async def test_5_upsert_mode_only_no_other_fields_written():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.upsert_provider_config("stripe", mode="live")
        doc = await repo.find_by_provider("stripe")
        assert doc.get("mode") == "live"
        # credentials/settings/isEnabled NOT written
        assert "credentials" not in doc
        assert "settings" not in doc
        assert "isEnabled" not in doc
        # provider + updated_at ALWAYS written
        assert doc["provider"] == "stripe"
        assert "updated_at" in doc
        print("✓ test_5_upsert_mode_only_no_other_fields_written")
    finally:
        client.close()


async def test_6_upsert_is_enabled_only_writes_isEnabled_as_bool():
    """is_enabled is normalised through bool() — preserves the
    legacy ``bool(data['isEnabled'])`` coercion at the call site."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.upsert_provider_config("email", is_enabled=1)  # truthy non-bool
        doc = await repo.find_by_provider("email")
        # Must be normalised to True (Python bool)
        assert doc["isEnabled"] is True
        assert isinstance(doc["isEnabled"], bool)
        await repo.upsert_provider_config("email", is_enabled=False)
        doc2 = await repo.find_by_provider("email")
        assert doc2["isEnabled"] is False
        print("✓ test_6_upsert_is_enabled_only_writes_isEnabled_as_bool")
    finally:
        client.close()


async def test_7_upsert_creates_new_document_when_missing():
    """Upsert semantics: must create the document on first call."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        assert await repo.find_by_provider("shipping") == {}
        await repo.upsert_provider_config(
            "shipping",
            credentials={"vesselFinderKey": "vf-new"},
            is_enabled=True,
        )
        doc = await repo.find_by_provider("shipping")
        assert doc["provider"] == "shipping"
        assert doc["credentials"]["vesselFinderKey"] == "vf-new"
        assert doc["isEnabled"] is True
        print("✓ test_7_upsert_creates_new_document_when_missing")
    finally:
        client.close()


async def test_8_upsert_always_writes_provider_and_updated_at():
    """provider + updated_at are NEVER omitted — they're set on
    every upsert regardless of which optional kwargs were passed.
    Casing is `updated_at` (snake_case) for all admin paths."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        # Even with NO conditional kwargs, must write provider + updated_at
        await repo.upsert_provider_config("openai")
        doc = await repo.find_by_provider("openai")
        assert doc["provider"] == "openai"
        assert "updated_at" in doc
        # Snake_case (NOT camelCase — the camelCase variant is reserved
        # for mirror_google_client_id only — see test_15)
        assert "updatedAt" not in doc
        print("✓ test_8_upsert_always_writes_provider_and_updated_at")
    finally:
        client.close()


async def test_9_upsert_accepts_caller_provided_ts_iso():
    """Caller-provided ts_iso flows verbatim (no overrides)."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        fixed = "2026-01-15T12:34:56+00:00"
        await repo.upsert_provider_config(
            "google_oauth",
            credentials={"clientId": "client-abc"},
            ts_iso=fixed,
        )
        doc = await repo.find_by_provider("google_oauth")
        assert doc["updated_at"] == fixed
        print("✓ test_9_upsert_accepts_caller_provided_ts_iso")
    finally:
        client.close()


# ────────────────────────────────────────────────────────────────────────
# WRITE 2 — record_test_outcome
# ────────────────────────────────────────────────────────────────────────

async def test_10_record_test_outcome_success_writes_ok_status_empty_error():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.upsert_provider_config("stripe", credentials={"secretKey": "sk_x"})
        await repo.record_test_outcome(
            "stripe", success=True, message="all good", ts_iso="2026-05-19T08:00:00+00:00",
        )
        doc = await repo.find_by_provider("stripe")
        assert doc["lastTestStatus"] == "ok"
        assert doc["lastTestError"] == ""   # empty string on success (NOT the message)
        assert doc["lastTest"] == "2026-05-19T08:00:00+00:00"
        # Existing credentials must remain
        assert doc["credentials"]["secretKey"] == "sk_x"
        print("✓ test_10_record_test_outcome_success_writes_ok_status_empty_error")
    finally:
        client.close()


async def test_11_record_test_outcome_failure_writes_failed_status_and_message():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.record_test_outcome(
            "openai", success=False, message="API key invalid",
        )
        doc = await repo.find_by_provider("openai")
        assert doc["lastTestStatus"] == "failed"
        assert doc["lastTestError"] == "API key invalid"
        assert "lastTest" in doc
        print("✓ test_11_record_test_outcome_failure_writes_failed_status_and_message")
    finally:
        client.close()


async def test_12_record_test_outcome_upserts_without_prior_config():
    """Legacy quirk: test outcome can be recorded even when no
    config exists yet (preserved at admin_integrations.py:507-515)."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        assert await repo.find_by_provider("email") == {}
        await repo.record_test_outcome("email", success=False, message="not configured")
        doc = await repo.find_by_provider("email")
        # Document exists now with ONLY the test-outcome fields
        assert doc["lastTestStatus"] == "failed"
        # No credentials/settings/mode/isEnabled because we never set them
        assert "credentials" not in doc
        print("✓ test_12_record_test_outcome_upserts_without_prior_config")
    finally:
        client.close()


# ────────────────────────────────────────────────────────────────────────
# WRITE 3 — set_enabled (toggle)
# ────────────────────────────────────────────────────────────────────────

async def test_13_set_enabled_flips_isEnabled_true_then_false():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.set_enabled("stripe", True)
        d1 = await repo.find_by_provider("stripe")
        assert d1["isEnabled"] is True
        assert d1["provider"] == "stripe"
        assert "updated_at" in d1
        await repo.set_enabled("stripe", False)
        d2 = await repo.find_by_provider("stripe")
        assert d2["isEnabled"] is False
        print("✓ test_13_set_enabled_flips_isEnabled_true_then_false")
    finally:
        client.close()


async def test_14_set_enabled_upserts_before_any_credentials():
    """Preserved legacy behaviour at admin_integrations.py:529-534:
    a provider can be toggled before its credentials are configured."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        assert await repo.find_by_provider("shipping") == {}
        await repo.set_enabled("shipping", True)
        doc = await repo.find_by_provider("shipping")
        assert doc["isEnabled"] is True
        # No credentials field — toggle does not invent one
        assert "credentials" not in doc
        print("✓ test_14_set_enabled_upserts_before_any_credentials")
    finally:
        client.close()


# ────────────────────────────────────────────────────────────────────────
# WRITE 4 — mirror_google_client_id (cross-collection mirror tension)
# ────────────────────────────────────────────────────────────────────────

async def test_15_mirror_google_client_id_uses_updatedAt_camelCase():
    """Legacy quirk pinned VERBATIM: the mirror writes ``updatedAt``
    (camelCase), NOT ``updated_at`` (snake_case used everywhere
    else in this repo). The casing divergence is documented and
    intentional — NOT fixing in C-2."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        await repo.mirror_google_client_id("new-client.apps.googleusercontent.com")
        doc = await repo.find_by_provider("google_oauth")
        # camelCase MUST be present
        assert "updatedAt" in doc, f"updatedAt missing; keys={list(doc.keys())}"
        # snake_case must NOT be set by the mirror
        assert "updated_at" not in doc, f"mirror leaked updated_at: {doc.get('updated_at')!r}"
        assert doc["provider"] == "google_oauth"
        assert doc["credentials"]["clientId"] == "new-client.apps.googleusercontent.com"
        assert doc["isEnabled"] is True
        print("✓ test_15_mirror_google_client_id_uses_updatedAt_camelCase")
    finally:
        client.close()


async def test_16_mirror_uses_dot_notation_preserving_clientSecret():
    """Critical regression guard: the mirror must NOT clobber
    ``credentials.clientSecret`` when updating ``credentials.clientId``.
    The dot-notation ``credentials.clientId`` path achieves this;
    a full ``credentials = {...}`` replacement would destroy the
    secret. Preserved 1:1 from server.py:10943."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        # Pre-existing config with BOTH clientId and clientSecret
        await repo.upsert_provider_config(
            "google_oauth",
            credentials={
                "clientId": "old-id.apps.googleusercontent.com",
                "clientSecret": "GOCSPX-supersecret",
            },
        )
        # Mirror writes ONLY the clientId
        await repo.mirror_google_client_id("new-id.apps.googleusercontent.com")
        doc = await repo.find_by_provider("google_oauth")
        # clientId updated
        assert doc["credentials"]["clientId"] == "new-id.apps.googleusercontent.com"
        # CRITICAL: clientSecret PRESERVED (not clobbered)
        assert doc["credentials"]["clientSecret"] == "GOCSPX-supersecret"
        print("✓ test_16_mirror_uses_dot_notation_preserving_clientSecret")
    finally:
        client.close()


async def test_17_mirror_upserts_when_no_prior_google_oauth_row():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        assert await repo.find_by_provider("google_oauth") == {}
        await repo.mirror_google_client_id("first-id.apps.googleusercontent.com")
        doc = await repo.find_by_provider("google_oauth")
        assert doc["provider"] == "google_oauth"
        assert doc["credentials"]["clientId"] == "first-id.apps.googleusercontent.com"
        assert doc["isEnabled"] is True
        print("✓ test_17_mirror_upserts_when_no_prior_google_oauth_row")
    finally:
        client.close()


async def test_18_mirror_accepts_caller_provided_ts_datetime():
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        fixed = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        await repo.mirror_google_client_id("ts-test.apps.googleusercontent.com", ts=fixed)
        doc = await repo.find_by_provider("google_oauth")
        # Stored as datetime (mirror writes raw datetime, not ISO)
        stored = doc["updatedAt"]
        assert isinstance(stored, datetime)
        assert stored.replace(tzinfo=timezone.utc) == fixed or stored == fixed
        print("✓ test_18_mirror_accepts_caller_provided_ts_datetime")
    finally:
        client.close()


# ────────────────────────────────────────────────────────────────────────
# ARCHITECTURAL PROPERTY tests
# ────────────────────────────────────────────────────────────────────────

async def test_19_exactly_five_named_verbs_on_surface():
    """The C-2 mandate says 5 named verbs collapse 12 production
    sites. The repository's public surface MUST be exactly these
    five names — any drift (additions/renames) is an architectural
    regression that this test catches at the contract level."""
    expected = {
        "find_by_provider",
        "upsert_provider_config",
        "record_test_outcome",
        "set_enabled",
        "mirror_google_client_id",
    }
    public = {
        n for n in dir(IntegrationConfigsRepository)
        if not n.startswith("_") and callable(getattr(IntegrationConfigsRepository, n))
    }
    # COLLECTION class attribute is intentional (verb constant)
    public.discard("COLLECTION")
    assert public == expected, (
        f"surface drift: expected {sorted(expected)}, got {sorted(public)}; "
        f"extra={sorted(public - expected)}, missing={sorted(expected - public)}"
    )
    print("✓ test_19_exactly_five_named_verbs_on_surface")


async def test_20_provider_key_isolation_writes_dont_cross_providers():
    """Multi-provider invariant: writing to "stripe" must NEVER
    touch "google_oauth" or any other provider's row. Provider is
    the discriminator — every write filters by {"provider": ...}."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        # Seed all 5 providers
        for p in ("google_oauth", "stripe", "email", "shipping", "openai"):
            await repo.upsert_provider_config(p, credentials={"k": f"{p}-original"})
        # Mutate only stripe
        await repo.upsert_provider_config("stripe", credentials={"k": "stripe-MUTATED"})
        # Verify ALL 5 rows are still distinct, only stripe changed
        for p in ("google_oauth", "email", "shipping", "openai"):
            doc = await repo.find_by_provider(p)
            assert doc["credentials"]["k"] == f"{p}-original", (
                f"cross-provider leak: provider={p} got {doc['credentials']!r}"
            )
        stripe_doc = await repo.find_by_provider("stripe")
        assert stripe_doc["credentials"]["k"] == "stripe-MUTATED"
        # Mirror google_oauth — must not touch stripe either
        await repo.mirror_google_client_id("mirror-test.apps.googleusercontent.com")
        stripe_doc2 = await repo.find_by_provider("stripe")
        assert stripe_doc2["credentials"]["k"] == "stripe-MUTATED"
        print("✓ test_20_provider_key_isolation_writes_dont_cross_providers")
    finally:
        client.close()


async def test_21_google_mirror_tension_exposed_as_distinct_verb():
    """The architectural answer says the google_oauth mirror tension
    is EXPOSED as a distinct verb (not collapsed into upsert_provider_config).
    This is the contract-level evidence the mirror exists and must
    be reconciled in C-3 before app.state migration."""
    # Distinct verb exists
    assert hasattr(IntegrationConfigsRepository, "mirror_google_client_id")
    # And it is NOT a thin wrapper over upsert_provider_config —
    # mirror writes camelCase `updatedAt`, upsert writes snake_case
    # `updated_at`. Behavioural test 15 already pins the divergence;
    # this property test pins the surface-level evidence.
    import inspect
    src = inspect.getsource(IntegrationConfigsRepository.mirror_google_client_id)
    # The mirror MUST reference `updatedAt` (camelCase) — that's the
    # whole point of having it as a separate verb
    assert "updatedAt" in src, "mirror_google_client_id must use camelCase updatedAt"
    # And `credentials.clientId` dot-notation
    assert "credentials.clientId" in src, "mirror_google_client_id must use dot-notation"
    print("✓ test_21_google_mirror_tension_exposed_as_distinct_verb")


async def test_22_collection_name_pinned_to_integration_configs():
    """The collection constant MUST be ``integration_configs``. Renaming
    it would silently divert reads/writes away from the canonical store."""
    assert IntegrationConfigsRepository.COLLECTION == "integration_configs"
    print("✓ test_22_collection_name_pinned_to_integration_configs")


async def test_23_find_after_record_test_outcome_then_upsert_preserves_test_fields():
    """Full lifecycle interaction test: test outcome → upsert →
    test fields preserved → toggle → still preserved."""
    client, db = await _fresh_db()
    try:
        repo = IntegrationConfigsRepository(db)
        # 1) Record test outcome first (upserts the doc)
        await repo.record_test_outcome("stripe", success=True, message="ok")
        # 2) Upsert config — must NOT clobber lastTest/lastTestStatus
        await repo.upsert_provider_config(
            "stripe", credentials={"secretKey": "sk_post_test"},
        )
        doc1 = await repo.find_by_provider("stripe")
        assert doc1["lastTestStatus"] == "ok"
        assert doc1["credentials"]["secretKey"] == "sk_post_test"
        # 3) Toggle — must NOT clobber either
        await repo.set_enabled("stripe", True)
        doc2 = await repo.find_by_provider("stripe")
        assert doc2["lastTestStatus"] == "ok"
        assert doc2["credentials"]["secretKey"] == "sk_post_test"
        assert doc2["isEnabled"] is True
        print("✓ test_23_find_after_record_test_outcome_then_upsert_preserves_test_fields")
    finally:
        client.close()


async def main():
    tests = [
        test_1_find_by_provider_returns_empty_dict_when_missing,
        test_2_find_by_provider_returns_full_document_when_present,
        test_3_upsert_credentials_only_leaves_other_fields_untouched,
        test_4_upsert_settings_only_leaves_credentials_untouched,
        test_5_upsert_mode_only_no_other_fields_written,
        test_6_upsert_is_enabled_only_writes_isEnabled_as_bool,
        test_7_upsert_creates_new_document_when_missing,
        test_8_upsert_always_writes_provider_and_updated_at,
        test_9_upsert_accepts_caller_provided_ts_iso,
        test_10_record_test_outcome_success_writes_ok_status_empty_error,
        test_11_record_test_outcome_failure_writes_failed_status_and_message,
        test_12_record_test_outcome_upserts_without_prior_config,
        test_13_set_enabled_flips_isEnabled_true_then_false,
        test_14_set_enabled_upserts_before_any_credentials,
        test_15_mirror_google_client_id_uses_updatedAt_camelCase,
        test_16_mirror_uses_dot_notation_preserving_clientSecret,
        test_17_mirror_upserts_when_no_prior_google_oauth_row,
        test_18_mirror_accepts_caller_provided_ts_datetime,
        test_19_exactly_five_named_verbs_on_surface,
        test_20_provider_key_isolation_writes_dont_cross_providers,
        test_21_google_mirror_tension_exposed_as_distinct_verb,
        test_22_collection_name_pinned_to_integration_configs,
        test_23_find_after_record_test_outcome_then_upsert_preserves_test_fields,
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
    print(f"IntegrationConfigsRepository — {len(tests) - fails}/{len(tests)} PASS")
    print(f"{'=' * 60}")
    return fails


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
