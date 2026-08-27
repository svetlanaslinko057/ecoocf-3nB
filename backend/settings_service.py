"""
settings_service.py — dynamic admin-editable config stored in MongoDB
=====================================================================

The BIBI CRM historically reads a lot of config from env vars (JWT_SECRET,
GOOGLE_CLIENT_ID, base URL, …). That's fine for single-tenant prod, but it
breaks the moment you move between preview domains, change the frontend
URL, or want the admin to flip a feature flag without SSH.

This module centralises **auth-related** settings into a single document in
`app_settings` keyed by `"auth"`. Everything is read-through cached for
sub-millisecond lookups and writes invalidate the cache atomically.

Shape (collection `app_settings`):

    {
      key: "auth",
      value: {
        baseUrl: "https://bibicars.bg",        # backend public URL (callbacks/emails)
        frontendUrl: "https://bibicars.bg",    # customer-facing UI (reset links)
        google: {
            clientId: "",                       # GIS popup Client ID
            redirectPath: "/api/auth/google/callback"  # legacy, unused by GIS
        },
        jwt: {
            secret: "",                         # optional override; falls back to env
            accessExpires: "15m",
            refreshExpires: "7d"
        },
        features: {
            googleEnabled: true,
            passwordEnabled: true,
            registerEnabled: true,
            resetPasswordEnabled: true
        },
        password: {
            minLength: 6,
            resetTokenTtlMinutes: 60
        },
        email: {
            mode: "dry_run",                    # dry_run | smtp | resend (future)
            from: "no-reply@bibicars.bg",
            replyTo: ""
        }
      },
      updatedAt: <datetime>,
      updatedBy: <staff email or "system">
    }

Public-facing consumers (login page, cabinet, reset-password page) should
hit the **`/api/settings/public`** endpoint which returns only the safe
subset — never `jwt.secret`, never internal email transport creds.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.repositories import AppSettingsRepository

logger = logging.getLogger("bibi.settings")


# ──────────────────────────────────────────────────────────────────────
# Default "auth" document used when the collection is empty or missing
# fields. Every write deep-merges on top of this, so adding a new field
# later never breaks old deployments.
# ──────────────────────────────────────────────────────────────────────
AUTH_DEFAULTS: Dict[str, Any] = {
    "baseUrl": "",
    "frontendUrl": "",
    "google": {
        "clientId": "",
        "redirectPath": "/api/auth/google/callback",
    },
    "jwt": {
        "secret": "",
        "accessExpires": "15m",
        "refreshExpires": "7d",
    },
    "features": {
        "googleEnabled": True,
        "passwordEnabled": True,
        "registerEnabled": True,
        "resetPasswordEnabled": True,
    },
    "password": {
        "minLength": 6,
        "resetTokenTtlMinutes": 60,
    },
    "email": {
        "mode": "dry_run",
        "from": "no-reply@bibicars.bg",
        "replyTo": "",
    },
    "notifications": {
        "notifyEmail": "",   # mailbox that receives new-request/inquiry alerts
    },
}


# ──────────────────────────────────────────────────────────────────────
# FOOTER — fully admin-editable public-site footer content. Stored in
# `app_settings` under key="footer". Everything here is PUBLIC (no secrets),
# served to anonymous browsers via GET /api/public/footer and edited by the
# admin via GET/PUT /api/admin/settings/footer.
# ──────────────────────────────────────────────────────────────────────
FOOTER_DEFAULTS: Dict[str, Any] = {
    "brand": {
        "name": "ECO",
        "accentChar": ".",
        "tagline": (
            "Ліцензований оператор поводження з небезпечними відходами. "
            "Прозора B2B-система утилізації по всій Україні."
        ),
        "wordmark": "ECO",
        "showWordmark": True,
    },
    "cta": {
        "enabled": True,
        "primaryLabel": "Розрахувати вартість",
        "primaryHref": "/calculator",
        "secondaryLabel": "Створити заявку",
        "secondaryHref": "/contacts",
    },
    "columns": [
        {
            "title": "Сайт",
            "links": [
                {"label": "Головна", "href": "/"},
                {"label": "Каталог відходів", "href": "/waste"},
                {"label": "Калькулятор", "href": "/calculator"},
                {"label": "Контакти", "href": "/contacts"},
            ],
        },
        {
            "title": "Довідник",
            "links": [
                {"label": "Медичні відходи", "href": "/waste"},
                {"label": "Акумулятори", "href": "/waste"},
                {"label": "Ртутні лампи", "href": "/waste"},
                {"label": "Відпрацьовані оливи", "href": "/waste"},
            ],
        },
    ],
    "contacts": {
        "title": "Контакти",
        "phone": "+380 (44) 223-00-00",
        "phoneHref": "tel:+380442230000",
        "phone2": "",
        "phone2Href": "",
        "email": "info@eco.ua",
        "email2": "",
        "address": "м. Київ, вул. Екологічна, 1",
        "hours": "Пн–Пт, 9:00–18:00",
        "clientLoginLabel": "Вхід для клієнтів",
        "clientLoginHref": "/client/login",
    },
    "company": {
        "legalName": "ТОВ «ЕКО Утилізація»",
        "edrpou": "",
        "registration": "",
    },
    "newsletter": {
        "enabled": True,
        "title": "Розсилка",
        "description": "Новини законодавства та поради з поводження з відходами — раз на місяць.",
        "placeholder": "Ваш email",
        "buttonLabel": "Підписатися",
        "successText": "Дякуємо! Ви підписані на розсилку.",
    },
    "socials": [
        {"network": "linkedin", "label": "LinkedIn", "href": ""},
        {"network": "facebook", "label": "Facebook", "href": ""},
        {"network": "instagram", "label": "Instagram", "href": ""},
        {"network": "telegram", "label": "Telegram", "href": ""},
    ],
    "badges": ["Ліцензія Мінекології", "Акти 1–4 клас", "ADR-транспорт"],
    "bottomLinks": [
        {"label": "Умови використання", "href": "/terms"},
        {"label": "Політика конфіденційності", "href": "/privacy"},
        {"label": "Політика Cookies", "href": "/cookies"},
    ],
    "copyright": "ECO Utilization Platform",
}


# ──────────────────────────────────────────────────────────────────────
# Safe subset exposed to the unauthenticated frontend via
# /api/settings/public — never include secrets or internal transport.
# ──────────────────────────────────────────────────────────────────────
def public_subset(auth: Dict[str, Any]) -> Dict[str, Any]:
    """Return fields safe to ship to anonymous browsers."""
    if not isinstance(auth, dict):
        return {}
    return {
        "baseUrl": auth.get("baseUrl", "") or "",
        "frontendUrl": auth.get("frontendUrl", "") or "",
        "google": {
            "clientId": (auth.get("google") or {}).get("clientId", "") or "",
        },
        "features": dict(auth.get("features") or {}),
        "password": {
            "minLength": (auth.get("password") or {}).get("minLength", 6),
        },
    }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge (override wins, nested dicts are merged)."""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class SettingsService:
    """
    Thin async wrapper over Mongo collection `app_settings`.

    • `get(key)`  → cached dict (deep copy). Returns `None` if absent.
    • `get_auth()`→ convenience for key="auth", always returns a dict merged
                    on top of AUTH_DEFAULTS (never None).
    • `set(key, value, by)` → upsert + cache invalidation.
    • `patch_auth(partial, by)` → deep-merge on top of current "auth" doc.
    • `ensure_defaults()` → idempotent seed on startup.

    A single process-wide cache is used. In multi-worker setups the cache
    goes stale until TTL (default 30s) elapses. For this CRM (one uvicorn
    worker behind Kubernetes) a 30s TTL is fine — admin changes still
    appear nearly instantly because writes invalidate locally.
    """

    _CACHE_TTL_SEC = 30.0

    def __init__(self, db):
        self.db = db
        # Phase 5.3 / C-7 — collection access routes through the
        # canonical app_settings owner. SettingsService keeps its
        # own process-local cache, deep-merge logic, env-fallback
        # chain, and public-subset helpers. The repository owns
        # ONLY the Mongo round-trip.
        self._repo = AppSettingsRepository(db)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_exp: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ── lifecycle ─────────────────────────────────────────────────────
    async def ensure_defaults(self, request_base_url: str = "") -> None:
        """Seed the `auth` doc if it doesn't exist. Idempotent."""
        doc = await self._repo.get_by_key("auth")
        if doc:
            return
        seed = copy.deepcopy(AUTH_DEFAULTS)
        # First-time boot: try to pick sensible defaults from env so the
        # app is immediately functional without the admin touching the UI.
        seed["baseUrl"] = (
            os.environ.get("PUBLIC_APP_URL", "") or request_base_url or ""
        ).rstrip("/")
        seed["frontendUrl"] = seed["baseUrl"]
        seed["google"]["clientId"] = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
        seed["jwt"]["secret"] = (os.environ.get("JWT_SECRET") or "").strip()
        await self._repo.insert(
            "auth",
            value=seed,
            updated_at=datetime.now(timezone.utc),
            updated_by="system",
        )
        logger.info("[settings] seeded default auth config")

    # ── read ──────────────────────────────────────────────────────────
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = asyncio.get_event_loop().time()
        if key in self._cache and self._cache_exp.get(key, 0) > now:
            return copy.deepcopy(self._cache[key])
        async with self._lock:
            # Double-check inside lock
            if key in self._cache and self._cache_exp.get(key, 0) > now:
                return copy.deepcopy(self._cache[key])
            doc = await self._repo.get_by_key(key)
            if not doc:
                return None
            value = doc.get("value") or {}
            self._cache[key] = copy.deepcopy(value)
            self._cache_exp[key] = now + self._CACHE_TTL_SEC
            return copy.deepcopy(value)

    async def get_auth(self) -> Dict[str, Any]:
        """Always returns a merged-with-defaults dict. Never None."""
        current = await self.get("auth") or {}
        return _deep_merge(AUTH_DEFAULTS, current)

    # ── write ─────────────────────────────────────────────────────────
    async def set(self, key: str, value: Dict[str, Any], by: str = "admin") -> Dict[str, Any]:
        clean = dict(value or {})
        await self._repo.upsert_value(
            key,
            value=clean,
            updated_at=datetime.now(timezone.utc),
            updated_by=by,
        )
        self._invalidate(key)
        return clean

    async def patch_auth(self, partial: Dict[str, Any], by: str = "admin") -> Dict[str, Any]:
        """Deep-merge a partial update on top of the current auth doc."""
        current = await self.get_auth()
        merged = _deep_merge(current, partial or {})
        # Never accept obviously bogus structures
        if not isinstance(merged.get("features"), dict):
            merged["features"] = dict(AUTH_DEFAULTS["features"])
        await self.set("auth", merged, by)
        return merged

    def _invalidate(self, key: str) -> None:
        self._cache.pop(key, None)
        self._cache_exp.pop(key, None)

    # ── footer (public-site, admin-editable) ──────────────────────────
    async def get_footer(self) -> Dict[str, Any]:
        """Always returns a merged-with-defaults footer dict. Never None.

        Lists (columns/socials/badges/bottomLinks) are REPLACED by the stored
        value when present (deep-merge keeps stored lists as-is), so the admin
        can freely add/remove items. Missing top-level keys fall back to
        FOOTER_DEFAULTS so older saved docs never lose new sections.
        """
        current = await self.get("footer") or {}
        return _deep_merge(FOOTER_DEFAULTS, current)

    async def set_footer(self, value: Dict[str, Any], by: str = "admin") -> Dict[str, Any]:
        """Persist the full footer document (replace semantics for lists)."""
        # Merge on top of defaults so any omitted section is still valid.
        merged = _deep_merge(FOOTER_DEFAULTS, value or {})
        await self.set("footer", merged, by)
        return merged

    # ── helpers consumed by business logic ────────────────────────────
    async def resolve_base_url(self, request_base_url: str = "") -> str:
        """
        Pick backend base URL in priority order:
          1. app_settings.auth.baseUrl
          2. PUBLIC_APP_URL env
          3. caller-provided request.base_url (FastAPI)
        Always returned without trailing slash.
        """
        auth = await self.get_auth()
        chosen = (
            (auth.get("baseUrl") or "").strip()
            or (os.environ.get("PUBLIC_APP_URL") or "").strip()
            or (request_base_url or "").strip()
        )
        return chosen.rstrip("/")

    async def resolve_frontend_url(self, request_base_url: str = "") -> str:
        """
        Frontend URL for reset-password links, redirects after OAuth, etc.
        Falls back to baseUrl if frontendUrl is empty (single-domain setups).
        """
        auth = await self.get_auth()
        chosen = (auth.get("frontendUrl") or "").strip()
        if not chosen:
            chosen = await self.resolve_base_url(request_base_url)
        return chosen.rstrip("/")

    async def resolve_google_client_id(self) -> str:
        """
        Google Client ID lookup chain (for GIS popup):
          1. app_settings.auth.google.clientId
          2. integration_configs.{provider:"google_oauth"}.credentials.clientId
          3. GOOGLE_CLIENT_ID env
        Returns "" if not configured.

        Phase 5.4 / C-2: step 2 reads through IntegrationConfigsRepository
        (find_by_provider preserves the legacy ``... or {}`` quirk).
        The fallback orchestration (priority chain) stays at the caller —
        the repository ONLY answers "what is persisted for this provider?".
        """
        auth = await self.get_auth()
        cid = ((auth.get("google") or {}).get("clientId") or "").strip()
        if cid:
            return cid
        from app.repositories import IntegrationConfigsRepository
        doc = await IntegrationConfigsRepository(self.db).find_by_provider("google_oauth")
        cid = ((doc.get("credentials") or {}).get("clientId") or "").strip()
        if cid:
            return cid
        return (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()

    async def resolve_jwt_secret(self) -> str:
        auth = await self.get_auth()
        secret = ((auth.get("jwt") or {}).get("secret") or "").strip()
        return secret or (os.environ.get("JWT_SECRET") or "").strip()
