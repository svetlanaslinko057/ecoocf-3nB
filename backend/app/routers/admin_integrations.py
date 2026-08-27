"""
admin_integrations — /api/admin/integrations HTTP surface
============================================================

Wave 2B / Batch 14 / Commit 20 — full integrations cluster
(reads + writes, including the Tier-A reads originally planned
for Batch 11 that were not yet extracted).

Mechanical 1:1 extraction of 9 admin endpoints over the
`integration_configs` collection:

  Reads (4):
    * GET  /api/admin/integrations                       — list all providers
    * GET  /api/admin/integrations/health                — per-provider health summary
    * GET  /api/admin/integrations/{integration_id}      — stub (always succeeds)
    * GET  /api/admin/integrations/ringostat/config      — public-shape ringostat read

  Writes (5):
    * PUT   /api/admin/integrations/{integration_id}     — stub
    * PATCH /api/admin/integrations/{provider}           — persist creds/settings/mode
    * POST  /api/admin/integrations/ringostat/configure  — upsert ringostat_config
    * POST  /api/admin/integrations/{provider}/test      — test creds, persist outcome
    * POST  /api/admin/integrations/{provider}/toggle    — flip isEnabled

────────────────────────────────────────────────────────────────────────
Mutation ownership — PARTIAL transfer of integration_configs
────────────────────────────────────────────────────────────────────────

This router becomes runtime mutation owner of `integration_configs`
(PATCH, POST .../test, POST .../toggle all write).  Residual writers
in server.py: NONE (admin path is the only mutation site).

Cross-domain writes:
  * POST .../ringostat/configure also upserts `ringostat_config`
    (cross into the ringostat domain).  This is the higher-level
    orchestration endpoint; the more granular `PATCH /api/admin/
    ringostat/settings` (admin_ringostat router) and `POST /api/admin/
    ringostat/mappings` (admin_ringostat router) are alternative
    interfaces to the same storage.  Documented as cross-domain edge.

────────────────────────────────────────────────────────────────────────
Phase 3 coupling — RETIRED in Phase 5.5/F
────────────────────────────────────────────────────────────────────────

`integrations_health` (GET /health) AND `test_integration` (POST /test
for shipping provider) READ five tracking provider keys that originally
lived as module globals in server.py:

  VESSELFINDER_API_KEY, VESSELFINDER_FLEET_KEY,
  SHIPSGO_API_KEY, SHIPSGO_FLEET_KEY, AFTERSHIP_API_KEY

(Phase 3.1 / Commit 26 retired those globals — they now live inside a
single ``TrackingConfigService`` instance.)

Pre-5.5/F: this router used ``getattr(server, "tracking_config_service",
None)`` to reach the live service instance (lazy lookup, cold-start
safe via the default ``None``). That qualified-access shape was the
last remaining bridge for tracking-config readers.

Post-5.5/F: the live service instance is published via a canonical
module-level accessor in its OWN module
(``app/services/tracking_config.py::get_service``). The lazy semantic
is identical (called fresh on every read) and the cold-start behaviour
is identical (returns ``None`` pre-bind → caller falls back to the
all-empty-string dict). See ``_tracking_env_keys`` below.

Auth: uniform `require_admin` hoisted at router level.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_admin, require_master_admin

logger = logging.getLogger("bibi.admin_integrations")


def _db():
    """Lazy bridge to the live Mongo handle in server.py."""
    from app.core.db_runtime import get_db  # noqa: E402 (C-4e: lazy-bridge → accessor)
    return get_db()


def _tracking_env_keys() -> Dict[str, str]:
    """Read the 5 tracking provider keys via TrackingConfigService.

    Phase 3.1 / Commit 24+26 — sole consumer.  Returns the legacy dict
    shape (UPPER_SNAKE keys) so every existing call site is unchanged.
    Returns all-empty strings if the service is not yet bound (cold
    start, before startup() runs) — every call site treats empty as
    "not configured".

    Phase 5.5/F (2026-05-19) — retired the legacy qualified-access
    bridge ``getattr(server, "tracking_config_service", None)``. The
    accessor is now sourced from the canonical home
    ``app/services/tracking_config.py::get_service``. Cold-start
    semantics (``None`` → all-empty fallback) preserved 1:1.
    """
    # [ECO CLEANUP] auto-domain tracking providers (VesselFinder/ShipsGo/
    # AfterShip) removed — always report "not configured".
    return {
        "VESSELFINDER_API_KEY":   "",
        "VESSELFINDER_FLEET_KEY": "",
        "SHIPSGO_API_KEY":        "",
        "SHIPSGO_FLEET_KEY":      "",
        "AFTERSHIP_API_KEY":      "",
    }


router = APIRouter(
    prefix="/api/admin/integrations",
    tags=["admin-integrations"],
    dependencies=[Depends(require_admin)],
)


# ── READS ─────────────────────────────────────────────────────────────

@router.get("")
async def admin_integrations():
    """Return integrations configs as array for frontend.

    Reads each provider's persisted credentials/settings from
    ``db.integration_configs``. Secret-typed fields are masked on output
    (the full value is preserved server-side and used at runtime).
    """
    db = _db()
    # Check if Ringostat is configured (separate legacy collection)
    ringostat_config = await db.ringostat_config.find_one({})
    ringostat_enabled = ringostat_config.get('enabled', False) if ringostat_config else False

    def _mask(s: str) -> str:
        if not s: return ""
        return "…" + s[-8:] if len(s) > 10 else "…"

    # Per-provider field schema → which keys must be masked (passwords / secrets)
    SECRET_FIELDS = {
        "google_oauth": {"clientSecret"},
        "stripe":       {"secretKey", "restrictedKey", "webhookSecret", "webhookSecrets"},
        "email":        {"smtpPassword"},
        "resend":       {"apiKey", "resendKey"},
        "openai":       {"apiKey"},
        "shipping":     {"apiKey", "vesselFinderKey", "shipsGoKey"},
        "sms":          {"apiKey", "textbeltKey"},
    }
    # Public-typed keys whose default we want exposed even when DB has no record
    PUBLIC_DEFAULTS = {
        "stripe":   {"settings": {"currency": "USD"}, "mode": "sandbox"},
        "openai":   {"settings": {"model": "gpt-4o"}, "mode": "sandbox"},
        "email":    {"settings": {}, "mode": "disabled"},
        "resend":   {"settings": {}, "mode": "disabled"},
        "shipping": {"settings": {}, "mode": "disabled"},
        "google_oauth": {"settings": {}, "mode": "disabled"},
        "sms":      {"settings": {"provider": "textbelt", "sender": "BIBI Cars"}, "mode": "free"},
    }

    async def _load(provider: str) -> Dict[str, Any]:
        # Phase 5.4 / C-2 — db.integration_configs ownership routes through
        # IntegrationConfigsRepository.find_by_provider (preserves legacy
        # `... or {}` quirk at every call site).
        from app.repositories import IntegrationConfigsRepository
        doc = await IntegrationConfigsRepository(db).find_by_provider(provider)
        creds_raw = doc.get("credentials") or {}
        secret_keys = SECRET_FIELDS.get(provider, set())
        creds = {}
        for k, v in creds_raw.items():
            if k in secret_keys:
                # secrets may be a single string OR a list of strings (e.g.
                # stripe.webhookSecrets) — never emit either in the clear.
                if isinstance(v, (list, tuple)):
                    creds[k] = [_mask(x if isinstance(x, str) else "") for x in v]
                else:
                    creds[k] = _mask(v if isinstance(v, str) else "")
            else:
                creds[k] = v if v is not None else ""
        defaults = PUBLIC_DEFAULTS.get(provider, {"settings": {}, "mode": "disabled"})
        settings = doc.get("settings") or defaults.get("settings", {})
        mode = doc.get("mode") or defaults.get("mode", "disabled")
        # Default `isEnabled` heuristic: explicit flag > inferred from creds presence
        if "isEnabled" in doc:
            is_enabled = bool(doc.get("isEnabled"))
        else:
            is_enabled = bool([v for v in creds_raw.values() if v])
        return {
            "provider": provider,
            "credentials": creds,
            "settings": settings,
            "mode": mode,
            "isEnabled": is_enabled,
        }

    google = await _load("google_oauth")
    stripe_cfg = await _load("stripe")
    email_cfg = await _load("email")
    resend_cfg = await _load("resend")
    shipping_cfg = await _load("shipping")
    openai_cfg = await _load("openai")
    sms_cfg = await _load("sms")

    ringostat_block = {
        "provider": "ringostat",
        "credentials": {},
        "settings": {},
        "mode": "production" if ringostat_enabled else "disabled",
        "isEnabled": ringostat_enabled,
    }

    return [google, stripe_cfg, ringostat_block, email_cfg, resend_cfg, shipping_cfg, openai_cfg, sms_cfg]


@router.get("/health")
async def integrations_health():
    """Return health status by provider, computed from persisted creds."""
    db = _db()
    tracking_env = _tracking_env_keys()
    # Phase 5.4 / C-2 — find_by_provider consolidates all admin reads.
    from app.repositories import IntegrationConfigsRepository
    repo = IntegrationConfigsRepository(db)
    async def _doc(p): return await repo.find_by_provider(p)

    google_doc = await _doc("google_oauth")
    google_ok = bool((google_doc.get("credentials") or {}).get("clientId")) and bool(google_doc.get("isEnabled", True))

    stripe_doc = await _doc("stripe")
    stripe_creds = stripe_doc.get("credentials") or {}
    stripe_has_keys = bool(stripe_creds.get("publishableKey")) and bool(
        stripe_creds.get("secretKey") or stripe_creds.get("restrictedKey")
    )
    stripe_enabled = bool(stripe_doc.get("isEnabled", stripe_has_keys))
    if stripe_has_keys and stripe_enabled:
        stripe_status = "ok"
    elif stripe_has_keys and not stripe_enabled:
        stripe_status = "degraded"
    else:
        stripe_status = "not_configured"

    email_doc = await _doc("email")
    email_creds = email_doc.get("credentials") or {}
    email_has = bool(email_creds.get("smtpHost") and email_creds.get("smtpLogin"))
    email_enabled = bool(email_doc.get("isEnabled", email_has))

    resend_doc = await _doc("resend")
    resend_creds = resend_doc.get("credentials") or {}
    resend_key = (resend_creds.get("apiKey") or "").strip()
    resend_has = bool(resend_key)
    resend_enabled = bool(resend_doc.get("isEnabled", resend_has))
    if resend_has and resend_enabled:
        resend_status = "ok"
    elif resend_has and not resend_enabled:
        resend_status = "degraded"
    else:
        # env fallback — если в .env стоит RESEND_API_KEY, всё равно «ok»
        import os as _os
        resend_status = "ok" if _os.environ.get("RESEND_API_KEY") else "not_configured"

    openai_doc = await _doc("openai")
    openai_creds = openai_doc.get("credentials") or {}
    openai_has = bool(openai_creds.get("apiKey"))
    openai_enabled = bool(openai_doc.get("isEnabled", openai_has))

    shipping_doc = await _doc("shipping")
    shipping_creds = shipping_doc.get("credentials") or {}
    shipping_db_has = bool(shipping_creds.get("apiKey") or shipping_creds.get("vesselFinderKey") or shipping_creds.get("shipsGoKey"))
    shipping_env_has = bool(
        tracking_env["VESSELFINDER_API_KEY"] or tracking_env["VESSELFINDER_FLEET_KEY"]
        or tracking_env["SHIPSGO_API_KEY"] or tracking_env["SHIPSGO_FLEET_KEY"]
    )

    now = datetime.now(timezone.utc).isoformat()
    return {
        "google_oauth": {
            "status": "ok" if google_ok else "not_configured",
            "isEnabled": bool(google_doc.get("isEnabled", google_ok)),
            "lastCheck": now if google_ok else None,
        },
        "stripe": {
            "status": stripe_status,
            "isEnabled": stripe_enabled,
            "lastCheck": now if stripe_has_keys else None,
            "lastTest": stripe_doc.get("lastTest"),
            "lastTestStatus": stripe_doc.get("lastTestStatus"),
            "lastTestError": stripe_doc.get("lastTestError"),
        },
        "ringostat": {"status": "not_configured", "isEnabled": False, "lastCheck": None},
        "email": {
            "status": "ok" if (email_has and email_enabled) else ("degraded" if email_has else "not_configured"),
            "isEnabled": email_enabled,
            "lastCheck": now if email_has else None,
        },
        "resend": {
            "status": resend_status,
            "isEnabled": resend_enabled,
            "lastCheck": now if resend_has else None,
            "lastTest": resend_doc.get("lastTest"),
            "lastTestStatus": resend_doc.get("lastTestStatus"),
            "lastTestError": resend_doc.get("lastTestError"),
        },
        "shipping": {
            "status": "ok" if (shipping_db_has or shipping_env_has) else "not_configured",
            "isEnabled": bool(shipping_db_has or shipping_env_has),
            "lastCheck": now,
        },
        "openai": {
            "status": "ok" if (openai_has and openai_enabled) else ("degraded" if openai_has else "not_configured"),
            "isEnabled": openai_enabled,
            "lastCheck": now if openai_has else None,
        },
        "sms": await _sms_health_block(db, now),
    }


@router.get("/email/status", dependencies=[Depends(require_admin)])
async def email_provider_status():
    """Consolidated email-provider readiness for Admin → Integrations.

    Reports the ACTIVE provider (mock/resend/smtp/dry_run), from email/name,
    masked key hint, the last delivery error and recent outbox counts. Never
    returns raw secrets.
    """
    import os as _os
    db = _db()

    def _mask(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        return "…" + s[-4:] if len(s) > 6 else "…"

    from notifications import EmailChannel
    ch = EmailChannel(db)
    resend_cfg = await ch._resolve_resend_cfg()
    smtp_cfg = None
    try:
        smtp_cfg = await ch._resolve_smtp_cfg()
    except Exception:
        smtp_cfg = None

    mock = (_os.environ.get("EMAIL_MOCK_TRANSPORT") or "").strip().lower()
    if mock in ("1", "true", "success", "sent", "fail", "failed"):
        active, from_email, from_name, key_hint = "mock", "mock@local", "ECO.NOVA (mock)", ""
    elif resend_cfg:
        active = "resend"
        from_email = resend_cfg.get("from") or ""
        from_name = ""
        key_hint = _mask(resend_cfg.get("api_key"))
    elif smtp_cfg:
        active = "smtp"
        from_email = smtp_cfg.get("from") or smtp_cfg.get("login") or ""
        from_name = ""
        key_hint = _mask(smtp_cfg.get("login"))
    else:
        active, from_email, from_name, key_hint = "dry_run", "", "", ""

    status = "ready" if active in ("resend", "smtp", "mock") else "dry_run"

    # recent outbox stats + last error (best-effort)
    counts = {"sent": 0, "failed": 0, "dry_run": 0, "queued": 0}
    last_error = None
    try:
        async for d in db.email_outbox.find({}, {"_id": 0, "status": 1, "provider_error": 1, "created_at": 1}).sort("created_at", -1).limit(200):
            st = (d.get("status") or "").lower()
            if st in counts:
                counts[st] += 1
            if last_error is None and st == "failed" and d.get("provider_error"):
                last_error = {"error": d.get("provider_error"), "at": d.get("created_at")}
    except Exception:
        pass

    return {
        "status": status,               # ready | dry_run
        "active_provider": active,       # resend | smtp | mock | dry_run
        "from_email": from_email,
        "from_name": from_name,
        "key_hint": key_hint,            # masked, last 4 chars only
        "can_test": True,
        "last_error": last_error,
        "recent_counts": counts,
        "note": ("Провайдер налаштований — листи доставляються." if status == "ready"
                 else "Провайдер не налаштований — листи формуються у dry-run (записуються в чергу, але не відправляються)."),
    }


@router.post("/email/test")
async def email_provider_test(data: Dict[str, Any] = Body(default={}), current_user: Dict[str, Any] = Depends(require_admin)):
    """Send a TEST email through the real EmailChannel and report the honest
    outcome (sent / failed / dry_run). No secrets are returned."""
    db = _db()
    to = (data.get("to") or data.get("email") or (current_user or {}).get("email") or "").strip()
    if not to:
        raise HTTPException(400, "Вкажіть email отримувача (to)")
    from notifications import EmailChannel
    result = await EmailChannel(db).send(
        to=to,
        subject="ECO.NOVA — тестовий лист інтеграції",
        html="<p>Це тестовий лист від ECO.NOVA. Якщо ви його бачите — email-провайдер працює.</p>",
        text="Тестовий лист ECO.NOVA. Email-провайдер працює.",
        event="integration_test",
        context={"by": (current_user or {}).get("email")},
    )
    mode = (result or {}).get("mode") or "unknown"
    status = (result or {}).get("status") or ("sent" if (result or {}).get("ok") else "failed")
    delivered = bool((result or {}).get("ok")) and mode in ("resend", "smtp", "mock")
    return {
        "success": True, "delivered": delivered, "mode": mode, "status": status,
        "sent_to": to, "provider_id": (result or {}).get("provider_id"),
        "error": (result or {}).get("error"),
        "message": ("Тестовий лист надіслано" if delivered
                    else ("Помилка: провайдер відхилив лист" if status == "failed"
                          else "Провайдер не налаштований — лист записано у dry-run чергу")),
    }



async def _sms_health_block(db, now: str) -> Dict[str, Any]:
    """SMS health: textbelt free is *always* available without keys, paid mode
    needs admin-provided key."""
    sms_doc = await db.integration_configs.find_one({"provider": "sms"}) or {}
    creds = sms_doc.get("credentials") or {}
    has_key = bool((creds.get("apiKey") or "").strip() and (creds.get("apiKey") or "").strip().lower() != "textbelt")
    enabled = sms_doc.get("isEnabled")
    # By default SMS is enabled (free quota available), unless admin explicitly disabled.
    if enabled is False:
        return {"status": "disabled", "isEnabled": False, "mode": "dry_run", "lastCheck": now}
    if has_key:
        return {"status": "ok", "isEnabled": True, "mode": "textbelt_paid", "lastCheck": now}
    return {"status": "ok", "isEnabled": True, "mode": "textbelt_free",
            "hint": "Free quota: 1 SMS/day/IP. Add textbelt key in Admin → Notification Rules → Channel Integrations to remove limit.",
            "lastCheck": now}


@router.get("/{integration_id}")
async def get_integration(integration_id: str):
    return {"id": integration_id, "status": "active", "config": {}}


@router.get("/ringostat/config")
async def get_ringostat_config():
    """Get current Ringostat configuration"""
    db = _db()
    config = await db.ringostat_config.find_one({})
    if not config:
        return {"enabled": False}
    return {
        "enabled": config.get('enabled', False),
        "project_id": config.get('project_id', ''),
        "extension_mapping": config.get('extension_mapping', {})
    }


# ── WRITES ────────────────────────────────────────────────────────────

@router.put("/{integration_id}", dependencies=[Depends(require_master_admin)])
async def update_integration(integration_id: str, data: Dict[str, Any] = Body(...)):
    return {"success": True}


@router.patch("/{provider}", dependencies=[Depends(require_master_admin)])
async def patch_integration(provider: str, data: Dict[str, Any] = Body(...)):
    """Persist integration config (credentials, settings, mode)."""
    db = _db()
    allowed = {"google_oauth", "stripe", "email", "resend", "shipping", "openai", "sms"}
    if provider not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Phase 5.4 / C-2 — masked-secret-preservation logic stays at the
    # router layer (per repository design); the repo only persists.
    from app.repositories import IntegrationConfigsRepository
    repo = IntegrationConfigsRepository(db)

    creds_arg: Dict[str, Any] | None = None
    settings_arg: Dict[str, Any] | None = None
    mode_arg: str | None = None
    enabled_arg: bool | None = None

    if isinstance(data.get("credentials"), dict):
        incoming = dict(data["credentials"])
        existing = await repo.find_by_provider(provider)
        existing_creds = dict(existing.get("credentials") or {})
        for k, v in list(incoming.items()):
            # A masked placeholder ("…suffix") means "keep the stored secret".
            if isinstance(v, str) and v.startswith("…"):
                incoming[k] = existing_creds.get(k, "")
            # Same rule for list-typed secrets (e.g. stripe.webhookSecrets):
            # if every element is a masked placeholder, keep the stored list.
            elif isinstance(v, (list, tuple)) and v and all(
                isinstance(x, str) and x.startswith("…") for x in v
            ):
                incoming[k] = existing_creds.get(k, list(v))
        # MERGE: start from the stored credentials and overlay the incoming
        # keys. This preserves any credential the caller did NOT include in
        # the payload, so a partial update (e.g. only webhookSecret) no longer
        # wipes sibling keys (secretKey / publishableKey / restrictedKey).
        creds_arg = {**existing_creds, **incoming}
    if isinstance(data.get("settings"), dict):
        settings_arg = data["settings"]
    if "mode" in data:
        mode_arg = data["mode"]
    if "isEnabled" in data:
        enabled_arg = bool(data["isEnabled"])

    await repo.upsert_provider_config(
        provider,
        credentials=creds_arg,
        settings=settings_arg,
        mode=mode_arg,
        is_enabled=enabled_arg,
    )
    logger.info(f"[integrations] patched {provider}")
    return {"success": True, "provider": provider}


@router.post("/ringostat/configure", dependencies=[Depends(require_master_admin)])
async def ringostat_configure(data: Dict[str, Any] = Body(...)):
    """Configure Ringostat integration"""
    db = _db()
    try:
        api_key = data.get('api_key', '')
        project_id = data.get('project_id', '')
        extension_mapping = data.get('extension_mapping', {})
        await db.ringostat_config.update_one(
            {},
            {
                '$set': {
                    'api_key': api_key,
                    'project_id': project_id,
                    'enabled': True if api_key else False,
                    'extension_mapping': extension_mapping,
                    'updated_at': datetime.now(timezone.utc)
                },
                '$setOnInsert': {
                    'created_at': datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
        return {"success": True, "message": "Ringostat configured"}
    except Exception as e:
        logger.error(f"Ringostat config error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/{provider}/test")
async def test_integration(provider: str, data: Optional[Dict[str, Any]] = Body(default=None)):
    if data is None:
        data = {}
    """Test integration connection using saved credentials."""
    db = _db()
    tracking_env = _tracking_env_keys()
    # Phase 5.4 / C-2 — pre-read for test routes through repository.
    from app.repositories import IntegrationConfigsRepository
    repo = IntegrationConfigsRepository(db)
    doc = await repo.find_by_provider(provider)
    creds = doc.get("credentials") or {}
    settings = doc.get("settings") or {}

    success = False
    message = f"{provider}: not implemented"

    try:
        if provider == "stripe":
            secret_key = (creds.get("secretKey") or "").strip()
            restricted_key = (creds.get("restrictedKey") or "").strip()
            publishable = (creds.get("publishableKey") or "").strip()

            if not secret_key and not restricted_key:
                success, message = False, "Secret Key (or Restricted Key) is empty — fill it in and Save first."
            else:
                try:
                    import stripe as _stripe  # type: ignore
                    parts: list[str] = []
                    overall_ok = True

                    def _retrieve_account(api_key: str):
                        _stripe.api_key = api_key
                        return _stripe.Account.retrieve()

                    if secret_key:
                        try:
                            acc = await asyncio.to_thread(_retrieve_account, secret_key)
                            acc_id = getattr(acc, "id", None) or "?"
                            charges_enabled = bool(getattr(acc, "charges_enabled", False))
                            livemode = bool(getattr(acc, "livemode", False))
                            mode_label = "live" if livemode else "test"
                            biz = getattr(acc, "business_profile", None)
                            biz_name = getattr(biz, "name", None) if biz else None
                            biz_suffix = f" — {biz_name}" if biz_name else ""
                            parts.append(f"✓ Secret Key: account {acc_id} ({mode_label}, charges_enabled={charges_enabled}){biz_suffix}")
                        except Exception as ex:
                            overall_ok = False
                            parts.append(f"✗ Secret Key FAILED: {type(ex).__name__}: {str(ex)[:160]}")

                    if restricted_key:
                        try:
                            acc = await asyncio.to_thread(_retrieve_account, restricted_key)
                            acc_id = getattr(acc, "id", None) or "?"
                            parts.append(f"✓ Restricted Key: account {acc_id} (scoped access OK)")
                        except Exception as ex:
                            try:
                                _stripe.api_key = restricted_key
                                await asyncio.to_thread(lambda: _stripe.Customer.list(limit=1))
                                parts.append(f"✓ Restricted Key: auth OK (limited scope; Account read not granted)")
                            except Exception as ex2:
                                overall_ok = False
                                parts.append(f"✗ Restricted Key FAILED: {type(ex2).__name__}: {str(ex2)[:160]}")

                    if publishable:
                        if publishable.startswith("pk_test_") or publishable.startswith("pk_live_"):
                            parts.append(f"✓ Publishable Key format OK ({'live' if publishable.startswith('pk_live_') else 'test'} mode)")
                        else:
                            parts.append("⚠ Publishable Key format unexpected — expected pk_test_… or pk_live_…")

                    success = overall_ok
                    message = " · ".join(parts) if parts else "No keys to test"

                except Exception as ex:
                    success = False
                    message = f"Stripe error: {type(ex).__name__}: {str(ex)[:200]}"

        elif provider == "google_oauth":
            client_id = (creds.get("clientId") or "").strip()
            if not client_id:
                success, message = False, "Client ID is empty — fill it in and Save first."
            elif not client_id.endswith(".apps.googleusercontent.com"):
                success, message = False, "Client ID format looks wrong — it should end with '.apps.googleusercontent.com'."
            else:
                success, message = True, f"Client ID format OK ({client_id[:18]}…). Final verification happens at sign-in time."

        elif provider == "openai":
            api_key = (creds.get("apiKey") or "").strip()
            if not api_key:
                success, message = False, "API Key is empty — fill it in and Save first."
            else:
                try:
                    from openai import OpenAI as _OpenAI
                    client = _OpenAI(api_key=api_key)
                    res = await asyncio.to_thread(lambda: client.models.list())
                    n = len(getattr(res, "data", []) or [])
                    success = True
                    message = f"OpenAI key valid — {n} models accessible."
                except Exception as ex:
                    success = False
                    message = f"OpenAI error: {type(ex).__name__}: {str(ex)[:200]}"

        elif provider == "email":
            host = (creds.get("smtpHost") or "").strip()
            port = int((creds.get("smtpPort") or 587) or 587)
            login = (creds.get("smtpLogin") or "").strip()
            pwd = creds.get("smtpPassword") or ""
            if not (host and login and pwd):
                success, message = False, "SMTP host/login/password are required."
            else:
                try:
                    import smtplib, ssl
                    def _smtp_check():
                        ctx = ssl.create_default_context()
                        with smtplib.SMTP(host, port, timeout=8) as s:
                            s.ehlo(); s.starttls(context=ctx); s.ehlo()
                            s.login(login, pwd)
                        return True
                    await asyncio.to_thread(_smtp_check)
                    success, message = True, f"SMTP login successful at {host}:{port}."
                except Exception as ex:
                    success = False
                    message = f"SMTP error: {type(ex).__name__}: {str(ex)[:200]}"

        elif provider == "resend":
            # Resend test: либо валидируем ключ через GET /domains, либо шлём
            # реальное письмо (если в body есть test_email). Без верификации
            # домена шлёт только onboarding@resend.dev → email владельца аккаунта.
            api_key = (creds.get("apiKey") or "").strip()
            from_addr = (creds.get("from") or settings.get("from") or "").strip()
            reply_to = (creds.get("replyTo") or settings.get("replyTo") or "").strip() or None
            test_email = (data.get("test_email") or data.get("email") or "").strip()
            if not api_key:
                success, message = False, "Resend API Key is empty — fill it in and Save first."
            elif not api_key.startswith("re_"):
                success, message = False, "Resend API Key format looks wrong — expected re_xxx."
            else:
                try:
                    import httpx as _httpx
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    if test_email and "@" in test_email:
                        # Реальная отправка
                        payload = {
                            "from": from_addr or "onboarding@resend.dev",
                            "to":   [test_email],
                            "subject": "BIBI Cars · Resend integration test",
                            "html": (
                                "<div style='font-family:system-ui,sans-serif;padding:24px;background:#fafafa'>"
                                "<h2 style='margin:0 0 12px 0;color:#18181B'>BIBI Cars · Resend OK</h2>"
                                "<p style='color:#3F3F46;line-height:1.5'>If you see this — Resend "
                                "integration is working. Sender, DKIM and API key are all valid.</p>"
                                f"<p style='color:#A1A1AA;font-size:12px;margin-top:24px'>{datetime.now(timezone.utc).isoformat()}</p>"
                                "</div>"
                            ),
                            **({"reply_to": reply_to} if reply_to else {}),
                        }
                        async with _httpx.AsyncClient(timeout=15.0) as _client:
                            _r = await _client.post("https://api.resend.com/emails", headers=headers, json=payload)
                        try:
                            _body = _r.json() if _r.content else {}
                        except Exception:
                            _body = {"raw": _r.text[:200]}
                        if _r.status_code < 300:
                            email_id = _body.get("id") or "?"
                            success, message = True, f"Resend OK: email sent (id={email_id}) → {test_email}"
                        else:
                            err = _body.get("message") or _body.get("error") or f"HTTP {_r.status_code}"
                            success, message = False, f"Resend rejected: {err}"
                    else:
                        # Только валидация ключа — пингуем /domains (требует api_key, ничего не шлёт)
                        async with _httpx.AsyncClient(timeout=10.0) as _client:
                            _r = await _client.get("https://api.resend.com/domains", headers=headers)
                        if _r.status_code == 200:
                            try:
                                _data = _r.json()
                                domains = _data.get("data") or []
                                verified = [d for d in domains if (d.get("status") or "").lower() == "verified"]
                                parts = [f"✓ API key valid · {len(domains)} domain(s), {len(verified)} verified"]
                                if from_addr:
                                    parts.append(f"From: {from_addr}")
                                if not verified and from_addr and "resend.dev" not in from_addr:
                                    parts.append("⚠ No verified domains — Resend will reject sends from custom From. Verify in resend.com → Domains, or use onboarding@resend.dev for tests.")
                                success, message = True, " · ".join(parts) + ". Pass `test_email` in body to send a real test."
                            except Exception:
                                success, message = True, "Resend API key valid (parse error on /domains response)."
                        elif _r.status_code in (401, 403):
                            success, message = False, f"Resend rejected the API key (HTTP {_r.status_code}). Get a new one at resend.com → API Keys."
                        else:
                            success, message = False, f"Resend /domains returned HTTP {_r.status_code}: {_r.text[:160]}"
                except Exception as ex:
                    success = False
                    message = f"Resend error: {type(ex).__name__}: {str(ex)[:200]}"

        elif provider == "shipping":
            has_any = any([
                creds.get("apiKey"), creds.get("vesselFinderKey"), creds.get("shipsGoKey"),
                tracking_env["VESSELFINDER_API_KEY"], tracking_env["VESSELFINDER_FLEET_KEY"],
                tracking_env["SHIPSGO_API_KEY"], tracking_env["SHIPSGO_FLEET_KEY"],
            ])
            success = has_any
            message = "Shipping providers reachable." if has_any else "No shipping API keys configured."

        elif provider == "sms":
            # SMS test: send a real SMS via TextBelt if test_phone provided,
            # otherwise just validate that we have something to send through.
            test_phone = (data.get("test_phone") or data.get("phone") or "").strip()
            api_key = (creds.get("apiKey") or "").strip() or "textbelt"
            sender = ((doc.get("settings") or {}).get("sender") or "BIBI Cars")[:11]
            if not test_phone:
                success = True
                message = (
                    "SMS provider ready (TextBelt). "
                    f"Mode: {'paid' if api_key.lower() != 'textbelt' else 'free quota (1/day/IP)'}. "
                    "Pass `test_phone` in request body to send a real test SMS."
                )
            else:
                try:
                    import httpx as _httpx
                    body = f"[BIBI Cars] Test SMS — admin verification, ignore. {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
                    async with _httpx.AsyncClient(timeout=15.0) as _client:
                        _r = await _client.post(
                            "https://textbelt.com/text",
                            data={"phone": test_phone, "message": body, "key": api_key, "sender": sender},
                        )
                    _p = _r.json() if _r.content else {}
                    if _p.get("success"):
                        success = True
                        quota = _p.get("quotaRemaining")
                        message = f"SMS sent to {test_phone} via TextBelt. Quota remaining: {quota}"
                    else:
                        success = False
                        message = f"TextBelt rejected: {_p.get('error') or 'unknown error'}. Response: {_p}"
                except Exception as _ex:
                    success = False
                    message = f"SMS test error: {type(_ex).__name__}: {str(_ex)[:200]}"

        elif provider == "ringostat":
            rd = await db.ringostat_config.find_one({}) or {}
            api_key = (rd.get("api_key") or "").strip()
            project_id = (rd.get("project_id") or "").strip()
            if not (rd.get("enabled") and api_key and project_id):
                success, message = False, "Ringostat is not configured (api_key/project_id/enabled missing)."
            else:
                # Live ping — same endpoint as the dedicated test-connection route.
                try:
                    import httpx as _httpx
                    from datetime import timedelta as _td
                    _now = datetime.now(timezone.utc)
                    _headers = {
                        "Auth-key": api_key,
                        "x-project-id": project_id,
                        "Accept": "application/json",
                    }
                    _params = {
                        "date_from": (_now - _td(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
                        "date_to": _now.strftime("%Y-%m-%d %H:%M:%S"),
                        "limit": 1,
                    }
                    async with _httpx.AsyncClient(timeout=10.0) as _client:
                        _r = await _client.get(
                            "https://api.ringostat.net/calls/list",
                            headers=_headers, params=_params,
                        )
                    if _r.status_code == 200:
                        success, message = True, f"Ringostat live ping OK (project {project_id})."
                    elif _r.status_code in (401, 403):
                        success, message = False, f"Ringostat auth rejected (HTTP {_r.status_code})."
                    else:
                        success, message = False, f"Ringostat returned HTTP {_r.status_code}: {_r.text[:160]}"
                except Exception as _ex:
                    success, message = False, f"Ringostat error: {type(_ex).__name__}: {str(_ex)[:200]}"

        else:
            success, message = False, f"Unknown provider: {provider}"

    except Exception as ex:
        success = False
        message = f"{provider}: {type(ex).__name__}: {str(ex)[:200]}"

    # Persist the test outcome (only for known providers)
    try:
        # Phase 5.4 / C-2 — outcome write routes through repo
        await repo.record_test_outcome(
            provider, success=success, message=message,
        )
    except Exception:
        pass

    logger.info(f"[integrations] test {provider} → success={success} msg={message[:120]}")
    return {"success": success, "message": message}


@router.post("/{provider}/toggle", dependencies=[Depends(require_master_admin)])
async def toggle_integration(provider: str, data: Dict[str, Any] = Body(...)):
    """Toggle integration enabled state (persisted for supported providers)."""
    db = _db()
    is_enabled = bool(data.get("isEnabled", False))
    if provider in ("google_oauth", "stripe", "email", "resend", "shipping", "openai", "sms"):
        # Phase 5.4 / C-2 — toggle write routes through repo.set_enabled
        from app.repositories import IntegrationConfigsRepository
        await IntegrationConfigsRepository(db).set_enabled(provider, is_enabled)
    return {"success": True, "isEnabled": is_enabled}


# ─────────────────────────────────────────────────────────────────────────
# Resend Domains — UI-level domain management (proxy to api.resend.com/domains).
#
# Зачем: чтобы admin не открывал dashboard.resend.com отдельно. Прямо в нашем
# UI он:
#   1) Видит список своих доменов в Resend + их status (verified / pending /
#      failed / not_started).
#   2) Добавляет новый домен (POST /domains) → получает SPF + DKIM + DMARC
#      DNS-записи которые нужно прописать у своего DNS-провайдера.
#   3) После того как DNS прокинулся, жмёт «Verify now» → мы триггерим
#      POST /domains/{id}/verify в Resend, дёргаем GET /domains/{id} и
#      возвращаем свежий статус.
#   4) Может удалить домен (DELETE /domains/{id}).
#
# Все ручки используют API-ключ из integration_configs.resend (или env
# fallback). Если ключа нет — 400 с понятным сообщением.
# ─────────────────────────────────────────────────────────────────────────

async def _resolve_resend_key() -> str:
    """Достаёт live API-ключ Resend из integration_configs.resend, иначе из env."""
    db = _db()
    doc = (
        await db.integration_configs.find_one({"provider": "resend"})
        or await db.integration_configs.find_one({"_id": "resend"})
        or await db.integration_configs.find_one({"id": "resend"})
    ) or {}
    creds = doc.get("credentials") or {}
    api_key = (creds.get("apiKey") or creds.get("resendKey") or "").strip()
    if not api_key:
        import os as _os
        api_key = (_os.environ.get("RESEND_API_KEY") or "").strip()
    return api_key


@router.get("/resend/domains", dependencies=[Depends(require_admin)])
async def resend_list_domains():
    """Список всех доменов на стороне Resend (только метаданные, без DNS-записей)."""
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured. Save it in /admin/integrations → Resend first.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True, "items": body.get("data", []) or []}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend list failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.get("/resend/domains/{domain_id}", dependencies=[Depends(require_admin)])
async def resend_get_domain(domain_id: str):
    """Полный объект домена с массивом records[] (DKIM / SPF / DMARC)."""
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"https://api.resend.com/domains/{domain_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True, "domain": body}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend get failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.post("/resend/domains", dependencies=[Depends(require_master_admin)])
async def resend_create_domain(data: Dict[str, Any] = Body(...)):
    """Добавить новый домен в Resend. Body: {name, region?}.

    region: us-east-1 (default) | eu-west-1 | sa-east-1 | ap-northeast-1.
    Возвращает свежесозданный объект уже с массивом records[] — фронт сразу
    рисует DNS-инструкцию.
    """
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured. Save it first.")
    name = (data.get("name") or data.get("domain") or "").strip().lower()
    if not name or "." not in name:
        raise HTTPException(400, "Field 'name' must be a valid domain (e.g. bibi.cars).")
    region = (data.get("region") or "us-east-1").strip()
    payload: Dict[str, Any] = {"name": name, "region": region}
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True, "domain": body}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend create failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.post("/resend/domains/{domain_id}/verify", dependencies=[Depends(require_master_admin)])
async def resend_verify_domain(domain_id: str):
    """Триггерим повторную проверку DNS на стороне Resend и сразу возвращаем
    обновлённый объект домена (со свежим status и records[*].status).
    """
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"https://api.resend.com/domains/{domain_id}/verify",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            verify_body = r.json() if r.content else {}
            if r.status_code >= 300:
                raise HTTPException(r.status_code, verify_body.get("message") or f"Resend HTTP {r.status_code}")
            # Подтягиваем свежий объект с обновлёнными records
            r2 = await client.get(
                f"https://api.resend.com/domains/{domain_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            fresh = r2.json() if r2.content else {}
        return {"success": True, "domain": fresh, "verify_response": verify_body}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend verify failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.delete("/resend/domains/{domain_id}", dependencies=[Depends(require_master_admin)])
async def resend_delete_domain(domain_id: str):
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.delete(
                f"https://api.resend.com/domains/{domain_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True, "deleted": body}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend delete failed: {type(ex).__name__}: {str(ex)[:200]}")



# ─────────────────────────────────────────────────────────────────────────
# Resend API Keys — UI-level key management (proxy to api.resend.com/api-keys).
#
# Resend позволяет создавать дополнительные ключи:
#   • permission="full_access" — полный доступ (отправка + управление доменами/ключами)
#   • permission="sending_access" — только отправка emails (для production-сервисов)
#   • domain_id (optional) — ограничить ключ конкретным доменом
#
# Важно: при создании ключа Resend возвращает токен ОДИН раз. После этого его
# не показывают нигде. Поэтому UI должен показать токен в модалке с copy-кнопкой
# и предупредить «save now — won't show again».
# ─────────────────────────────────────────────────────────────────────────

@router.get("/resend/api-keys", dependencies=[Depends(require_admin)])
async def resend_list_api_keys():
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.resend.com/api-keys",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True, "items": body.get("data", []) or []}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend API keys list failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.post("/resend/api-keys", dependencies=[Depends(require_master_admin)])
async def resend_create_api_key(data: Dict[str, Any] = Body(...)):
    """Создаёт новый ключ. Body: {name, permission?, domain_id?}.

    permission: full_access (default) | sending_access
    domain_id: ограничить ключ конкретным доменом (опционально, только для sending_access)

    Возвращает токен в ответе ОДИН раз — фронт обязан показать его в модалке
    с copy-кнопкой и предупредить пользователя сохранить его сейчас.
    """
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Field 'name' is required (any human-readable label).")
    permission = (data.get("permission") or "full_access").strip()
    if permission not in ("full_access", "sending_access"):
        raise HTTPException(400, "permission must be 'full_access' or 'sending_access'")
    payload: Dict[str, Any] = {"name": name, "permission": permission}
    domain_id = (data.get("domain_id") or "").strip()
    if domain_id:
        payload["domain_id"] = domain_id
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.resend.com/api-keys",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True, "key": body}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend API key create failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.delete("/resend/api-keys/{key_id}", dependencies=[Depends(require_master_admin)])
async def resend_delete_api_key(key_id: str):
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.delete(
                f"https://api.resend.com/api-keys/{key_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if r.status_code >= 300:
            try:
                body = r.json()
            except Exception:
                body = {}
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend API key delete failed: {type(ex).__name__}: {str(ex)[:200]}")


# ─────────────────────────────────────────────────────────────────────────
# Resend Webhooks — UI-level management + receiver endpoint.
#
# Resend шлёт события (email.sent / email.delivered / email.bounced /
# email.complained / email.opened / email.clicked / email.delivery_delayed)
# на заданный URL. Мы:
#   1) Через UI создаём webhook у Resend, указывая URL нашего receiver-эндпоинта.
#   2) Receiver принимает события и обновляет email_outbox (поля delivered_at,
#      bounced_at, etc.) — это даёт admin живую картину доставляемости.
#
# Подпись событий: Resend использует Svix-headers (svix-id / svix-timestamp /
# svix-signature). Для production secret валидации нужен webhook_secret из
# Resend dashboard. Мы храним секрет в integration_configs.resend.settings.
# ─────────────────────────────────────────────────────────────────────────

RESEND_EVENT_TYPES = [
    "email.sent",
    "email.delivered",
    "email.delivery_delayed",
    "email.bounced",
    "email.complained",
    "email.opened",
    "email.clicked",
    "email.failed",
]


@router.get("/resend/webhooks", dependencies=[Depends(require_admin)])
async def resend_list_webhooks():
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.resend.com/webhooks",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {
            "success": True,
            "items": body.get("data", []) or [],
            "available_events": RESEND_EVENT_TYPES,
            # Готовый URL receiver-эндпоинта — фронт может прямо предложить его
            # как default при создании.
            "suggested_receiver_url": (
                (os.environ.get("PUBLIC_APP_URL") or os.environ.get("PUBLIC_SITE_URL") or "").rstrip("/")
                + "/api/webhooks/resend/events"
            ),
        }
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend webhooks list failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.post("/resend/webhooks", dependencies=[Depends(require_master_admin)])
async def resend_create_webhook(data: Dict[str, Any] = Body(...)):
    """Создаёт webhook у Resend. Body: {endpoint_url, events[]}.

    После создания Resend возвращает ВЕБХУК-СЕКРЕТ (whsec_xxx) — нужен для
    Svix-валидации входящих событий. Сохраняем его в integration_configs.resend.settings.webhook_secret.
    """
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    endpoint_url = (data.get("endpoint_url") or data.get("url") or "").strip()
    if not endpoint_url.startswith("http"):
        raise HTTPException(400, "endpoint_url must be a public HTTPS URL")
    events = data.get("events") or RESEND_EVENT_TYPES
    if not isinstance(events, list) or not events:
        raise HTTPException(400, "events must be a non-empty list of event types")
    payload = {"endpoint_url": endpoint_url, "events": events}
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.resend.com/webhooks",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        body = r.json() if r.content else {}
        if r.status_code >= 300:
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        # Сохраняем секрет в settings.resend.webhook_secret (одноразово показывается)
        secret = (body.get("secret") or body.get("signing_secret") or "").strip()
        if secret:
            try:
                from app.repositories import IntegrationConfigsRepository
                repo = IntegrationConfigsRepository(_db())
                existing = await repo.get("resend") or {}
                merged_settings = dict(existing.get("settings") or {})
                merged_settings["webhook_secret"] = secret
                merged_settings["webhook_id"] = body.get("id")
                await repo.upsert(
                    "resend",
                    credentials=existing.get("credentials") or {},
                    settings=merged_settings,
                    mode=existing.get("mode") or "production",
                    is_enabled=bool(existing.get("isEnabled", True)),
                )
            except Exception:
                logger.exception("[resend/webhook] failed to persist secret")
        return {"success": True, "webhook": body}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend webhook create failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.delete("/resend/webhooks/{webhook_id}", dependencies=[Depends(require_master_admin)])
async def resend_delete_webhook(webhook_id: str):
    api_key = await _resolve_resend_key()
    if not api_key:
        raise HTTPException(400, "Resend API Key not configured.")
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as client:
            r = await client.delete(
                f"https://api.resend.com/webhooks/{webhook_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if r.status_code >= 300:
            try:
                body = r.json()
            except Exception:
                body = {}
            raise HTTPException(r.status_code, body.get("message") or f"Resend HTTP {r.status_code}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(502, f"Resend webhook delete failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.get("/resend/webhook-stats", dependencies=[Depends(require_admin)])
async def resend_webhook_stats():
    """Агрегаты по эвентам из email_outbox за последние 30 дней.

    Используется UI чтобы показать sparkline delivered/bounced/complained.
    """
    from datetime import timedelta
    db = _db()
    now = datetime.now(timezone.utc)
    since_30d = (now - timedelta(days=30)).isoformat()
    stats = {"delivered": 0, "bounced": 0, "complained": 0, "opened": 0, "clicked": 0, "delivery_delayed": 0}
    try:
        for ev in stats.keys():
            field = f"events.{ev}"
            stats[ev] = await db.email_outbox.count_documents({field: {"$exists": True}, "created_at": {"$gte": since_30d}})
    except Exception:
        logger.exception("[resend/webhook-stats] aggregate failed")
    return {"success": True, "stats_30d": stats}
