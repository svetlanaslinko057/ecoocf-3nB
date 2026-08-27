"""
admin_seo_settings.py — /api/admin/seo/settings  (master-admin only)
====================================================================

One-stop SEO control panel, sibling of /api/admin/system/settings.
Lets ПМ АВТО ГРУП ops set runtime-injectable SEO knobs without code
edits or redeploys:

  • verification           — Google Search Console, Bing Webmasters,
                             Yandex Webmaster verification tokens
  • analytics              — Google Analytics 4 measurement ID (G-XXXX)
  • ads                    — Google Ads conversion linker ID (AW-XXXX)
                             + per-event conversion labels
  • social                 — Facebook Pixel ID, optional
  • site_identity          — default OG image override, fallback title
                             pattern, description, default keywords
  • crawler_directives     — toggle whether to block AI crawlers
                             (GPTBot/Claude-Web/CCBot/anthropic-ai)

Storage: a single ``seo_settings`` Mongo document with ``_id="global"``.
A companion public endpoint ``GET /api/seo/runtime-config`` returns the
*safe* subset (no internal flags) so the frontend can inject GA/AW
trackers at runtime without editing index.html.

Why a separate router (and not extending system_settings)?
  • Cleaner blast-radius: SEO mis-config can't lock the team out of the UI
  • Easier read-only surface for the public ``runtime-config`` endpoint
  • Naturally maps to a sidebar entry under "Settings" (master-admin only)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_master_admin

logger = logging.getLogger("bibi.admin_seo_settings")

router = APIRouter(prefix="/api/admin/seo", tags=["admin-seo"])

DOC_ID = "global"

DEFAULT_DOC: Dict[str, Any] = {
    "_id": DOC_ID,
    # ─── Domain & environment (admin-managed, no redeploy) ───────────────
    "public_origin":   "",     # e.g. https://eco-nova.ua  (empty → env/host)
    "seo_environment": "auto", # auto | production | preview | stage | test | dev
    "allow_indexing_in_production": False,  # master safety switch — must be
                                            # explicitly enabled before Google
                                            # can index the production domain.
    "canonical_strategy": "origin",  # origin | request | admin_override
    "default_language":   "uk",
    "enabled_languages":  "uk,en",
    "site_name":          "ECO.NOVA",
    # ─── Search-engine verification tokens (paste from console screens) ──
    "google_site_verification": "",
    "bing_site_verification":   "",
    "yandex_site_verification": "",
    "indexnow_key":             "",
    # ─── Analytics & advertising IDs ─────────────────────────────────────
    "ga4_measurement_id":       "",   # e.g. "G-XXXXXXXXXX"
    "gtm_container_id":         "",   # e.g. "GTM-XXXXXXX"
    "google_ads_conversion_id": "",   # e.g. "AW-XXXXXXXXX"
    "google_ads_send_page_view": True,
    "google_ads_conversion_labels": {
        "lead_submit":     "",
        "calc_used":       "",
        "contract_signed": "",
    },
    "facebook_pixel_id":        "",
    # ─── Company identity & E-E-A-T (feeds JSON-LD Organization/LocalBusiness) ─
    "company_name":        "ECO.NOVA",
    "legal_name":          "ЕКО-НОВА",
    "edrpou":              "",     # ЄДРПОУ / VAT
    "license_number":      "",     # № ліцензії на поводження з небезпечними відходами
    "license_name":        "",
    "company_email":       "Econova2013@ukr.net",
    "company_phones":      "+380 66 788 04 45",     # comma-separated
    "company_street":      "вул. Івана Франка, 104А",
    "company_city":        "Баранівка",
    "company_region":      "Житомирська область",
    "company_postal":      "",
    "company_country":     "UA",
    "company_lat":         "",
    "company_lng":         "",
    "founding_date":       "",     # YYYY-MM-DD
    "opening_hours":       "Mo-Fr 09:00-18:00",     # e.g. "Mo-Fr 09:00-18:00"
    "price_range":         "",
    "same_as":             "",     # newline/comma-separated social URLs
    "company_description": "",
    # ─── Site identity overrides ─────────────────────────────────────────
    "default_title":         "ECO.NOVA — Утилізація небезпечних відходів для бізнесу | B2B Україна",
    "default_description":   "ECO.NOVA — ліцензований оператор поводження з небезпечними відходами. Класифікація, збір, вивіз, утилізація та повний документальний супровід для бізнесу в одній прозорій B2B-системі.",
    "default_keywords":      "утилізація небезпечних відходів, поводження з відходами, вивіз відходів, класифікація відходів, нацперелік відходів, B2B утилізація, ECO.NOVA",
    "default_og_image":      "/og-image.png",
    # ─── Crawler directives ──────────────────────────────────────────────
    "block_ai_crawlers":     False,   # GPTBot, anthropic-ai, Claude-Web, CCBot
    # ─── Metadata ────────────────────────────────────────────────────────
    "updated_at": None,
    "updated_by": None,
}

# ─── Validators ─────────────────────────────────────────────────────────
_GA4_RE  = re.compile(r"^G-[A-Z0-9]{6,12}$")
_AW_RE   = re.compile(r"^AW-\d{6,12}$")
_FBPX_RE = re.compile(r"^\d{8,20}$")
_VERIF_RE = re.compile(r"^[A-Za-z0-9_\-=]{8,200}$")


def _db():
    from app.core.db_runtime import get_db
    return get_db()


async def _load() -> Dict[str, Any]:
    doc = await _db().seo_settings.find_one({"_id": DOC_ID})
    if not doc:
        return {k: v for k, v in DEFAULT_DOC.items() if k != "_id"}
    out = {**{k: v for k, v in DEFAULT_DOC.items() if k != "_id"}, **doc}
    out.pop("_id", None)
    if isinstance(out.get("updated_at"), datetime):
        out["updated_at"] = out["updated_at"].isoformat()
    return out


def _safe_token(value: Any) -> str:
    """Normalize a verification token: trim + drop leading 'content=' / quotes."""
    s = str(value or "").strip()
    s = s.strip('"').strip("'")
    # If user pasted the whole meta tag, extract the content attribute.
    m = re.search(r'content\s*=\s*"([^"]+)"', s) or re.search(r"content\s*=\s*'([^']+)'", s)
    if m:
        s = m.group(1)
    return s


# ═════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS (master_admin only)
# ═════════════════════════════════════════════════════════════════════════
@router.get("/settings", dependencies=[Depends(require_master_admin)])
async def get_seo_settings():
    """Return current SEO settings + helper hints for the UI."""
    return {
        "settings": await _load(),
        "hints": {
            "ga4_format":  "G-XXXXXXXXXX  (10-char alphanumeric, find it in Analytics → Admin → Data Streams)",
            "ads_format":  "AW-XXXXXXXXX  (9-10 digit ID, find it in Google Ads → Tools → Conversions)",
            "verification_help": "Paste either the raw token or the full <meta…> tag — we will extract the value automatically.",
        },
    }


@router.patch("/settings", dependencies=[Depends(require_master_admin)])
async def update_seo_settings(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    """Upsert one or more SEO fields.

    Strict-but-friendly validation: invalid formats are rejected with a 422
    that names the field, so the UI can highlight it inline.
    """
    update: Dict[str, Any] = {}

    # Verification tokens
    for key in ("google_site_verification", "bing_site_verification", "yandex_site_verification"):
        if key in data:
            tok = _safe_token(data[key])
            if tok and not _VERIF_RE.match(tok):
                raise HTTPException(422, f"{key}: token contains invalid characters or is too short/long")
            update[key] = tok

    # Analytics / advertising
    if "ga4_measurement_id" in data:
        v = (data["ga4_measurement_id"] or "").strip().upper()
        if v and not _GA4_RE.match(v):
            raise HTTPException(422, "ga4_measurement_id: expected format G-XXXXXXXXXX")
        update["ga4_measurement_id"] = v

    if "google_ads_conversion_id" in data:
        v = (data["google_ads_conversion_id"] or "").strip().upper()
        if v and not _AW_RE.match(v):
            raise HTTPException(422, "google_ads_conversion_id: expected format AW-XXXXXXXXX")
        update["google_ads_conversion_id"] = v

    if "google_ads_send_page_view" in data:
        update["google_ads_send_page_view"] = bool(data["google_ads_send_page_view"])

    if "google_ads_conversion_labels" in data:
        labels = data["google_ads_conversion_labels"] or {}
        if not isinstance(labels, dict):
            raise HTTPException(422, "google_ads_conversion_labels must be an object")
        # Just trim — labels are arbitrary opaque strings from Google
        update["google_ads_conversion_labels"] = {
            k: str(v or "").strip() for k, v in labels.items() if isinstance(k, str)
        }

    if "facebook_pixel_id" in data:
        v = (data["facebook_pixel_id"] or "").strip()
        if v and not _FBPX_RE.match(v):
            raise HTTPException(422, "facebook_pixel_id: expected 8-20 digit ID")
        update["facebook_pixel_id"] = v

    # Site identity (length sanity)
    if "default_title" in data:
        v = (data["default_title"] or "").strip()
        if v and len(v) > 200:
            raise HTTPException(422, "default_title is too long (max 200 chars)")
        update["default_title"] = v

    if "default_description" in data:
        v = (data["default_description"] or "").strip()
        if v and len(v) > 320:
            raise HTTPException(422, "default_description is too long (max 320 chars)")
        update["default_description"] = v

    if "default_keywords" in data:
        v = (data["default_keywords"] or "").strip()
        if v and len(v) > 500:
            raise HTTPException(422, "default_keywords is too long (max 500 chars)")
        update["default_keywords"] = v

    if "default_og_image" in data:
        v = (data["default_og_image"] or "").strip()
        if v and not (v.startswith("/") or v.startswith("http://") or v.startswith("https://")):
            raise HTTPException(422, "default_og_image must be an absolute URL or start with /")
        update["default_og_image"] = v

    # Crawler directives
    if "block_ai_crawlers" in data:
        update["block_ai_crawlers"] = bool(data["block_ai_crawlers"])
    if "allow_indexing_in_production" in data:
        update["allow_indexing_in_production"] = bool(data["allow_indexing_in_production"])
    if "canonical_strategy" in data:
        v = (data["canonical_strategy"] or "origin").strip().lower()
        if v not in ("origin", "request", "admin_override"):
            raise HTTPException(422, "canonical_strategy: origin|request|admin_override")
        update["canonical_strategy"] = v
    if "default_language" in data:
        v = (data["default_language"] or "uk").strip().lower()
        if v not in ("uk", "en"):
            raise HTTPException(422, "default_language: uk|en")
        update["default_language"] = v
    if "enabled_languages" in data:
        raw = data["enabled_languages"] or "uk,en"
        if isinstance(raw, list):
            raw = ",".join(str(x) for x in raw)
        parts = [p.strip().lower() for p in str(raw).split(",") if p.strip()]
        allowed = {"uk", "en"}
        parts = [p for p in parts if p in allowed]
        if not parts:
            raise HTTPException(422, "enabled_languages: at least one of uk,en")
        update["enabled_languages"] = ",".join(parts)
    if "site_name" in data:
        v = (data["site_name"] or "").strip()
        if len(v) > 120:
            raise HTTPException(422, "site_name too long (max 120)")
        update["site_name"] = v

    # ─── Domain & environment ────────────────────────────────────────────
    if "public_origin" in data:
        v = (data["public_origin"] or "").strip().rstrip("/")
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise HTTPException(422, "public_origin must start with http:// or https://")
        update["public_origin"] = v
    if "seo_environment" in data:
        v = (data["seo_environment"] or "auto").strip().lower()
        if v not in ("auto", "production", "preview", "stage", "staging", "test", "dev"):
            raise HTTPException(422, "seo_environment: auto|production|preview|stage|test|dev")
        update["seo_environment"] = v
    if "indexnow_key" in data:
        update["indexnow_key"] = (data["indexnow_key"] or "").strip()
    if "gtm_container_id" in data:
        v = (data["gtm_container_id"] or "").strip().upper()
        if v and not re.match(r"^GTM-[A-Z0-9]{4,10}$", v):
            raise HTTPException(422, "gtm_container_id: expected format GTM-XXXXXXX")
        update["gtm_container_id"] = v

    # ─── Company identity & E-E-A-T (free-text, length-capped) ───────────
    _STR_FIELDS = {
        "company_name": 120, "legal_name": 200, "edrpou": 40,
        "license_number": 120, "license_name": 200, "company_email": 160,
        "company_phones": 200, "company_street": 200, "company_city": 120,
        "company_region": 120, "company_postal": 20, "company_country": 4,
        "company_lat": 32, "company_lng": 32, "founding_date": 20,
        "opening_hours": 120, "price_range": 20, "same_as": 1000,
        "company_description": 600,
    }
    for fld, maxlen in _STR_FIELDS.items():
        if fld in data:
            v = (str(data[fld] or "")).strip()
            if len(v) > maxlen:
                raise HTTPException(422, f"{fld} is too long (max {maxlen} chars)")
            update[fld] = v

    if not update:
        raise HTTPException(400, "No valid fields supplied")

    # Audit trail
    update["updated_at"] = datetime.now(timezone.utc)
    update["updated_by"] = current_user.get("email") or current_user.get("id")

    await _db().seo_settings.update_one(
        {"_id": DOC_ID},
        {"$set": update, "$setOnInsert": {"_id": DOC_ID}},
        upsert=True,
    )

    logger.info("[seo] settings updated by %s: keys=%s",
                update["updated_by"], list(update.keys()))

    # Invalidate the SEO engine cache so domain/EEAT/env changes apply
    # on the very next request (no redeploy).
    try:
        from app.seo import config as _seo_config
        _seo_config.invalidate()
    except Exception:
        pass
    # Phase C: also bust the prerender cache so bots see the change.
    try:
        from app.seo import prerender as _pr
        _pr.invalidate_prerender_cache()
    except Exception:
        pass

    return {
        "success":  True,
        "settings": await _load(),
        "message":  "SEO settings saved — taking effect on next page load.",
    }


__all__ = ["router"]
