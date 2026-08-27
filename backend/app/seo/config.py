"""
Admin-managed SEO configuration cache.
=======================================

Everything that used to be hardcoded (domain, environment, company E-E-A-T
facts, default meta) now lives in the `seo_settings` Mongo document and is
edited from the admin panel (/api/admin/seo/settings).

The SEO engines (origin/canonical/hreflang/sitemap/schema) run in both sync
and async contexts, so we keep a tiny in-process cache here that async
request handlers refresh (short TTL). Admin saves call `invalidate()` so the
next request reloads immediately — changes take effect on the next page load
without a redeploy.

Resolution philosophy: ADMIN VALUE → ENV → sensible default. Nothing is ever
fabricated; empty admin fields simply fall through.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

_DOC_ID = "global"
_ROBOTS_DOC_ID = "global"
_TTL_SECONDS = 15.0
_CACHE: Dict[str, Any] = {"data": {}, "ts": 0.0}
_ROBOTS_CACHE: Dict[str, Any] = {"data": {}, "ts": 0.0}
_PAGES_CACHE: Dict[str, Any] = {"data": {}, "ts": 0.0}


def invalidate() -> None:
    _CACHE["ts"] = 0.0
    _ROBOTS_CACHE["ts"] = 0.0
    _PAGES_CACHE["ts"] = 0.0


async def load(db, force: bool = False) -> Dict[str, Any]:
    """Refresh the cache from Mongo if stale. Safe to call every request."""
    now = time.time()
    if not force and (now - _CACHE["ts"]) < _TTL_SECONDS and _CACHE["data"]:
        return _CACHE["data"]
    data: Dict[str, Any] = {}
    try:
        if db is not None:
            doc = await db.seo_settings.find_one({"_id": _DOC_ID}) or {}
            doc.pop("_id", None)
            data = doc
    except Exception:
        data = _CACHE.get("data") or {}
    _CACHE["data"] = data
    _CACHE["ts"] = now
    # Load robots + pages caches too (same TTL). Non-fatal on error.
    try:
        if db is not None:
            rdoc = await db.seo_robots_rules.find_one({"_id": _ROBOTS_DOC_ID}) or {}
            rdoc.pop("_id", None)
            _ROBOTS_CACHE["data"] = rdoc
            _ROBOTS_CACHE["ts"] = now
    except Exception:
        pass
    try:
        if db is not None:
            pages: Dict[str, Any] = {}
            cursor = db.seo_page_metadata.find({}, {"_id": 0})
            async for row in cursor:
                path = (row.get("path") or "").strip()
                if not path:
                    continue
                pages[path] = row
            _PAGES_CACHE["data"] = pages
            _PAGES_CACHE["ts"] = now
    except Exception:
        pass
    return data


def get(key: str, default: Any = None) -> Any:
    val = (_CACHE.get("data") or {}).get(key)
    return val if val not in (None, "") else default


def public_origin() -> str:
    """Admin domain → env → empty. Always without trailing slash."""
    admin = str(get("public_origin", "") or "").strip().rstrip("/")
    if admin:
        return admin
    env = (
        os.environ.get("SEO_PUBLIC_ORIGIN")
        or os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("PUBLIC_APP_URL")
        or ""
    ).strip().rstrip("/")
    return env


def environment_override() -> Optional[str]:
    """Explicit environment chosen in admin (or env), else None → auto-detect."""
    admin = str(get("seo_environment", "") or "").strip().lower()
    if admin and admin != "auto":
        return "production" if admin in ("prod", "production", "live") else admin
    env = (os.environ.get("SEO_ENV") or "").strip().lower()
    if env:
        return "production" if env in ("prod", "production", "live") else env
    return None


def company() -> Dict[str, Any]:
    """Assemble the company/E-E-A-T dict for schema.py from admin settings.

    Never fabricates: unknown fields stay empty and schema.py omits them.
    """
    g = _CACHE.get("data") or {}
    phones = g.get("company_phones")
    if isinstance(phones, str):
        phones = [p.strip() for p in phones.split(",") if p.strip()]
    if not phones and g.get("company_phone"):
        phones = [g.get("company_phone")]
    same_as = g.get("same_as")
    if isinstance(same_as, str):
        same_as = [s.strip() for s in same_as.replace("\n", ",").split(",") if s.strip()]
    return {
        "name": g.get("company_name") or "ECO.NOVA",
        "legal_name": g.get("legal_name"),
        "edrpou": g.get("edrpou"),
        "phones": phones or [],
        "phone": (phones or [None])[0],
        "email": g.get("company_email"),
        "street": g.get("company_street"),
        "city": g.get("company_city"),
        "region": g.get("company_region"),
        "postal_code": g.get("company_postal"),
        "country": g.get("company_country") or "UA",
        "lat": g.get("company_lat"),
        "lng": g.get("company_lng"),
        "founding_date": g.get("founding_date"),
        "opening_hours": g.get("opening_hours"),
        "price_range": g.get("price_range"),
        "license_number": g.get("license_number"),
        "license_name": g.get("license_name"),
        "same_as": same_as or [],
        "description": g.get("default_description") or g.get("company_description"),
        "logo": g.get("default_og_image"),
    }


# ─── B2 ADMIN SEO CENTER — new helpers ──────────────────────────────────
def allow_indexing_in_production() -> bool:
    """Master switch: even on a production domain the admin can keep the site
    noindex. Default TRUE for backwards compatibility."""
    val = (_CACHE.get("data") or {}).get("allow_indexing_in_production")
    # A missing/None value means "not explicitly set" → default to True so
    # historical deployments keep behaving the way they did.
    if val is None:
        return True
    return bool(val)


def robots_config() -> Dict[str, Any]:
    """Admin-managed robots rules (from seo_robots_rules collection)."""
    return _ROBOTS_CACHE.get("data") or {}


def pages_registry() -> Dict[str, Any]:
    """Admin-managed per-route metadata overrides (from seo_page_metadata)."""
    return _PAGES_CACHE.get("data") or {}


def page_override(path: str) -> Optional[Dict[str, Any]]:
    """Return the admin override document for a given exact path, if any."""
    if not path:
        return None
    return (_PAGES_CACHE.get("data") or {}).get(path)
