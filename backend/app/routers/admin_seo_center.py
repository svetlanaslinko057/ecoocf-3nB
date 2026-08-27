"""
Admin SEO Center — Phase B2
============================

Granular admin API for the six SEO sub-consoles:

  1) /api/admin/seo/company      · E-E-A-T / Company profile   (GET/PUT)
  2) /api/admin/seo/analytics    · Analytics + verifications   (GET/PUT)
  3) /api/admin/seo/pages        · Per-route metadata          (CRUD)
  4) /api/admin/seo/robots       · Robots rules                (GET/PUT + preview)
  5) /api/admin/seo/sitemap      · Sitemap preview + regen     (GET + POST)

The existing /api/admin/seo/settings (admin_seo_settings.py) remains as the
"Global SEO" tab. `settings`/`company`/`analytics` all read from the same
`seo_settings` document but expose logical subsets so the UI can save one
section at a time.

Storage
-------
* `seo_settings`       — one doc, `_id="global"` (global + company + analytics)
* `seo_page_metadata`  — one doc per route path
* `seo_robots_rules`   — one doc, `_id="global"`

All writes call `app.seo.config.invalidate()` so changes take effect on the
next public request without a redeploy.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from security import require_master_admin
from app.routers.admin_seo_settings import DEFAULT_DOC as _SETTINGS_DEFAULTS, _safe_token  # reuse

logger = logging.getLogger("bibi.admin_seo_center")

router = APIRouter(prefix="/api/admin/seo", tags=["admin-seo-center"])

_SETTINGS_DOC_ID = "global"
_ROBOTS_DOC_ID = "global"


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _invalidate_cache() -> None:
    try:
        from app.seo import config as _seo_config
        _seo_config.invalidate()
    except Exception:
        pass
    # Phase C: any admin write to SEO settings / page metadata / robots must
    # bust the prerender cache so bots pick up the change on the next hit.
    try:
        from app.seo import prerender as _pr
        _pr.invalidate_prerender_cache()
    except Exception:
        pass


async def _load_settings() -> Dict[str, Any]:
    doc = await _db().seo_settings.find_one({"_id": _SETTINGS_DOC_ID})
    if not doc:
        return {k: v for k, v in _SETTINGS_DEFAULTS.items() if k != "_id"}
    out = {**{k: v for k, v in _SETTINGS_DEFAULTS.items() if k != "_id"}, **doc}
    out.pop("_id", None)
    if isinstance(out.get("updated_at"), datetime):
        out["updated_at"] = out["updated_at"].isoformat()
    return out


async def _patch_settings(update: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    if not update:
        raise HTTPException(400, "No valid fields supplied")
    update["updated_at"] = datetime.now(timezone.utc)
    update["updated_by"] = current_user.get("email") or current_user.get("id")
    await _db().seo_settings.update_one(
        {"_id": _SETTINGS_DOC_ID},
        {"$set": update, "$setOnInsert": {"_id": _SETTINGS_DOC_ID}},
        upsert=True,
    )
    _invalidate_cache()
    return await _load_settings()


# ═══════════════════════════════════════════════════════════════════════
# 1) COMPANY PROFILE (E-E-A-T)
# ═══════════════════════════════════════════════════════════════════════
COMPANY_FIELDS = {
    "legal_name": 200, "company_name": 120, "edrpou": 40,
    "license_number": 120, "license_name": 200, "license_issued_at": 20,
    "license_issued_by": 200, "founding_date": 20,
    "company_street": 200, "company_city": 120, "company_region": 120,
    "company_postal": 20, "company_country": 4,
    "company_lat": 32, "company_lng": 32,
    "company_phones": 200, "company_email": 160,
    "opening_hours": 120, "price_range": 20,
    "same_as": 1000, "company_description": 600,
}


@router.get("/company", dependencies=[Depends(require_master_admin)])
async def get_company_profile():
    s = await _load_settings()
    return {"company": {k: s.get(k, "") for k in COMPANY_FIELDS}}


@router.put("/company", dependencies=[Depends(require_master_admin)])
async def put_company_profile(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    update: Dict[str, Any] = {}
    for fld, maxlen in COMPANY_FIELDS.items():
        if fld in data:
            v = str(data[fld] or "").strip()
            if len(v) > maxlen:
                raise HTTPException(422, f"{fld} is too long (max {maxlen} chars)")
            update[fld] = v
    # Light validation for critical fields
    if update.get("company_email"):
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", update["company_email"]):
            raise HTTPException(422, "company_email: invalid email format")
    if update.get("company_lat"):
        try:
            v = float(update["company_lat"])
            if not (-90.0 <= v <= 90.0):
                raise ValueError()
        except Exception:
            raise HTTPException(422, "company_lat: expected float -90..90")
    if update.get("company_lng"):
        try:
            v = float(update["company_lng"])
            if not (-180.0 <= v <= 180.0):
                raise ValueError()
        except Exception:
            raise HTTPException(422, "company_lng: expected float -180..180")
    if update.get("founding_date"):
        if not re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", update["founding_date"]):
            raise HTTPException(422, "founding_date: YYYY, YYYY-MM or YYYY-MM-DD")
    settings = await _patch_settings(update, current_user)
    return {"success": True, "company": {k: settings.get(k, "") for k in COMPANY_FIELDS}}


# ═══════════════════════════════════════════════════════════════════════
# 2) ANALYTICS & VERIFICATIONS
# ═══════════════════════════════════════════════════════════════════════
ANALYTICS_FIELDS = (
    "ga4_measurement_id", "gtm_container_id",
    "google_ads_conversion_id", "google_ads_send_page_view", "google_ads_conversion_labels",
    "facebook_pixel_id", "linkedin_insight_id",
    "google_site_verification", "bing_site_verification", "yandex_site_verification",
    "indexnow_key",
)


@router.get("/analytics", dependencies=[Depends(require_master_admin)])
async def get_analytics_settings():
    s = await _load_settings()
    out: Dict[str, Any] = {}
    for k in ANALYTICS_FIELDS:
        out[k] = s.get(k, "" if k != "google_ads_conversion_labels" else {})
    return {"analytics": out}


@router.put("/analytics", dependencies=[Depends(require_master_admin)])
async def put_analytics_settings(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    update: Dict[str, Any] = {}
    _GA4  = re.compile(r"^G-[A-Z0-9]{6,12}$")
    _GTM  = re.compile(r"^GTM-[A-Z0-9]{4,10}$")
    _AW   = re.compile(r"^AW-\d{6,12}$")
    _FBPX = re.compile(r"^\d{8,20}$")
    _LI   = re.compile(r"^\d{4,15}$")
    _VER  = re.compile(r"^[A-Za-z0-9_\-=]{8,200}$")

    if "ga4_measurement_id" in data:
        v = (data["ga4_measurement_id"] or "").strip().upper()
        if v and not _GA4.match(v):
            raise HTTPException(422, "ga4_measurement_id: expected format G-XXXXXXXXXX")
        update["ga4_measurement_id"] = v
    if "gtm_container_id" in data:
        v = (data["gtm_container_id"] or "").strip().upper()
        if v and not _GTM.match(v):
            raise HTTPException(422, "gtm_container_id: expected format GTM-XXXXXXX")
        update["gtm_container_id"] = v
    if "google_ads_conversion_id" in data:
        v = (data["google_ads_conversion_id"] or "").strip().upper()
        if v and not _AW.match(v):
            raise HTTPException(422, "google_ads_conversion_id: expected format AW-XXXXXXXXX")
        update["google_ads_conversion_id"] = v
    if "google_ads_send_page_view" in data:
        update["google_ads_send_page_view"] = bool(data["google_ads_send_page_view"])
    if "google_ads_conversion_labels" in data:
        labels = data["google_ads_conversion_labels"] or {}
        if not isinstance(labels, dict):
            raise HTTPException(422, "google_ads_conversion_labels must be an object")
        update["google_ads_conversion_labels"] = {
            k: str(v or "").strip() for k, v in labels.items() if isinstance(k, str)
        }
    if "facebook_pixel_id" in data:
        v = (data["facebook_pixel_id"] or "").strip()
        if v and not _FBPX.match(v):
            raise HTTPException(422, "facebook_pixel_id: expected 8-20 digit ID")
        update["facebook_pixel_id"] = v
    if "linkedin_insight_id" in data:
        v = (data["linkedin_insight_id"] or "").strip()
        if v and not _LI.match(v):
            raise HTTPException(422, "linkedin_insight_id: expected 4-15 digit numeric ID")
        update["linkedin_insight_id"] = v
    for key in ("google_site_verification", "bing_site_verification", "yandex_site_verification"):
        if key in data:
            tok = _safe_token(data[key])
            if tok and not _VER.match(tok):
                raise HTTPException(422, f"{key}: invalid characters or length")
            update[key] = tok
    if "indexnow_key" in data:
        update["indexnow_key"] = (data["indexnow_key"] or "").strip()

    settings = await _patch_settings(update, current_user)
    out = {k: settings.get(k, "" if k != "google_ads_conversion_labels" else {}) for k in ANALYTICS_FIELDS}
    return {"success": True, "analytics": out}


# ═══════════════════════════════════════════════════════════════════════
# 3) PAGE METADATA MANAGER
# ═══════════════════════════════════════════════════════════════════════
_PATH_RE = re.compile(r"^/[A-Za-z0-9\-._~/:%]*$")

# Suggested starter routes so the UI can pre-populate a "known routes" list.
KNOWN_ROUTES = [
    "/", "/services", "/waste", "/calculator", "/licenses",
    "/contacts", "/about", "/blog", "/terms", "/privacy", "/cookies",
    "/waste/category/:key", "/waste-code/:slug", "/blog/:slug",
]


def _norm_page_body(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise & cap the free-text metadata fields for a single page doc."""
    def _s(v, cap=None):
        s = str(v or "").strip()
        if cap and len(s) > cap:
            raise HTTPException(422, f"field too long (max {cap})")
        return s

    out: Dict[str, Any] = {}
    path = _s(data.get("path"), 300)
    if not path or not _PATH_RE.match(path):
        raise HTTPException(422, "path: must start with / and contain URL-safe chars")
    out["path"] = path

    # Generic (lang-agnostic) metadata
    for k, cap in (
        ("title", 200), ("description", 320), ("keywords", 500),
        ("canonical_override", 400), ("robots_override", 100),
        ("og_title", 200), ("og_description", 320), ("og_image", 400),
        ("twitter_title", 200), ("twitter_description", 320),
        ("schema_type", 80), ("changefreq", 20), ("priority", 8),
        ("lastmod", 20),
    ):
        if k in data:
            out[k] = _s(data.get(k), cap)

    if "excluded" in data:
        out["excluded"] = bool(data["excluded"])

    # Per-language overrides (recommended)
    for lang_key in ("_uk", "_en"):
        blk = data.get(lang_key)
        if isinstance(blk, dict):
            nb: Dict[str, Any] = {}
            for k, cap in (("title", 200), ("description", 320), ("keywords", 500)):
                if k in blk:
                    nb[k] = _s(blk.get(k), cap)
            if nb:
                out[lang_key] = nb

    # Optional FAQ list: [{q, a}, ...]
    if "faq" in data:
        faq = data.get("faq") or []
        if not isinstance(faq, list):
            raise HTTPException(422, "faq must be a list of {q, a}")
        norm_faq = []
        for row in faq[:50]:
            if not isinstance(row, dict):
                continue
            q = _s(row.get("q"), 300)
            a = _s(row.get("a"), 2000)
            if q and a:
                norm_faq.append({"q": q, "a": a})
        out["faq"] = norm_faq

    # Optional breadcrumbs override [{name, url}, ...]
    if "breadcrumbs" in data:
        crumbs = data.get("breadcrumbs") or []
        if not isinstance(crumbs, list):
            raise HTTPException(422, "breadcrumbs must be a list of {name, url}")
        out["breadcrumbs"] = [
            {"name": _s(c.get("name"), 200), "url": _s(c.get("url"), 500)}
            for c in crumbs[:20] if isinstance(c, dict)
        ]

    return out


@router.get("/pages", dependencies=[Depends(require_master_admin)])
async def list_pages(q: Optional[str] = Query(None, description="Filter by path substring")):
    query: Dict[str, Any] = {}
    if q:
        query["path"] = {"$regex": re.escape(q), "$options": "i"}
    cursor = _db().seo_page_metadata.find(query, {"_id": 0}).sort("path", 1).limit(500)
    items = []
    async for row in cursor:
        if isinstance(row.get("updated_at"), datetime):
            row["updated_at"] = row["updated_at"].isoformat()
        items.append(row)
    # Also return the known-routes registry so the UI can pre-populate.
    return {"items": items, "known_routes": KNOWN_ROUTES}


@router.get("/pages/{path:path}", dependencies=[Depends(require_master_admin)])
async def get_page(path: str):
    key = "/" + path.lstrip("/")
    doc = await _db().seo_page_metadata.find_one({"path": key}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"No metadata for path '{key}'")
    if isinstance(doc.get("updated_at"), datetime):
        doc["updated_at"] = doc["updated_at"].isoformat()
    return {"item": doc}


@router.post("/pages", dependencies=[Depends(require_master_admin)])
async def upsert_page(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    body = _norm_page_body(data)
    body["updated_at"] = datetime.now(timezone.utc)
    body["updated_by"] = current_user.get("email") or current_user.get("id")
    await _db().seo_page_metadata.update_one(
        {"path": body["path"]},
        {"$set": body, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    _invalidate_cache()
    return {"success": True, "path": body["path"]}


@router.put("/pages/{path:path}", dependencies=[Depends(require_master_admin)])
async def update_page(
    path: str,
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    key = "/" + path.lstrip("/")
    data["path"] = key
    return await upsert_page(data, current_user)


@router.delete("/pages/{path:path}", dependencies=[Depends(require_master_admin)])
async def delete_page(path: str):
    key = "/" + path.lstrip("/")
    res = await _db().seo_page_metadata.delete_one({"path": key})
    if res.deleted_count == 0:
        raise HTTPException(404, f"No metadata for path '{key}'")
    _invalidate_cache()
    return {"success": True, "deleted": key}


# ═══════════════════════════════════════════════════════════════════════
# 4) ROBOTS MANAGER
# ═══════════════════════════════════════════════════════════════════════
_DEFAULT_ROBOTS: Dict[str, Any] = {
    "mode": "auto",                # auto | index | noindex
    "disallow": [],                # list of paths — falls back to engine defaults if empty
    "allow": [],                   # list of paths — falls back to engine defaults if empty
    "sitemap_url": "",             # override advertised Sitemap: line
    "custom_lines": "",            # free-form extra lines appended to robots.txt
}


async def _load_robots() -> Dict[str, Any]:
    doc = await _db().seo_robots_rules.find_one({"_id": _ROBOTS_DOC_ID}) or {}
    out = {**_DEFAULT_ROBOTS, **{k: v for k, v in doc.items() if k != "_id"}}
    if isinstance(out.get("updated_at"), datetime):
        out["updated_at"] = out["updated_at"].isoformat()
    return out


def _norm_paths(raw) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace("\r", "\n").replace(",", "\n").split("\n")]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip() for p in raw]
    else:
        return []
    return [p for p in parts if p and (p.startswith("/") or p.startswith("*") or p == "/$")]


@router.get("/robots", dependencies=[Depends(require_master_admin)])
async def get_robots():
    from app.seo.origin import get_environment
    from app.seo import config as _seo_config
    await _seo_config.load(_db(), force=True)
    settings = await _load_settings()
    return {
        "robots": await _load_robots(),
        "context": {
            "environment": get_environment(None),
            "indexing_enabled": bool(settings.get("allow_indexing_in_production")),
            "public_origin": settings.get("public_origin", ""),
        },
    }


@router.put("/robots", dependencies=[Depends(require_master_admin)])
async def put_robots(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    update: Dict[str, Any] = {}
    if "mode" in data:
        v = (data["mode"] or "auto").strip().lower()
        if v not in ("auto", "index", "noindex"):
            raise HTTPException(422, "mode: auto|index|noindex")
        update["mode"] = v
    if "disallow" in data:
        update["disallow"] = _norm_paths(data["disallow"])[:100]
    if "allow" in data:
        update["allow"] = _norm_paths(data["allow"])[:100]
    if "sitemap_url" in data:
        v = (data["sitemap_url"] or "").strip()
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("/")):
            raise HTTPException(422, "sitemap_url: must be a full URL or start with /")
        update["sitemap_url"] = v
    if "custom_lines" in data:
        cl = str(data["custom_lines"] or "")
        if len(cl) > 4000:
            raise HTTPException(422, "custom_lines too long (max 4000)")
        update["custom_lines"] = cl

    if not update:
        raise HTTPException(400, "No valid fields supplied")
    update["updated_at"] = datetime.now(timezone.utc)
    update["updated_by"] = current_user.get("email") or current_user.get("id")
    await _db().seo_robots_rules.update_one(
        {"_id": _ROBOTS_DOC_ID},
        {"$set": update, "$setOnInsert": {"_id": _ROBOTS_DOC_ID}},
        upsert=True,
    )
    _invalidate_cache()
    return {"success": True, "robots": await _load_robots()}


@router.get("/robots/preview", dependencies=[Depends(require_master_admin)])
async def preview_robots(request: Request):
    """Return the robots.txt that would be emitted right now."""
    from app.seo import config as _seo_config
    from app.seo.robots import build_robots
    await _seo_config.load(_db(), force=True)
    text = build_robots(request)
    return Response(content=text, media_type="text/plain")


# ═══════════════════════════════════════════════════════════════════════
# 5) SITEMAP MANAGER
# ═══════════════════════════════════════════════════════════════════════
@router.get("/sitemap", dependencies=[Depends(require_master_admin)])
async def get_sitemap_state(request: Request):
    from app.seo import config as _seo_config
    from app.seo.sitemap import PUBLIC_PAGES
    from app.seo.origin import get_origin
    await _seo_config.load(_db(), force=True)
    pages_reg = _seo_config.pages_registry() or {}
    included = []
    excluded = []
    for path, cf, pr in PUBLIC_PAGES:
        override = pages_reg.get(path) or {}
        row = {
            "path": path,
            "changefreq": override.get("changefreq") or cf,
            "priority": str(override.get("priority") or pr),
            "excluded": bool(override.get("excluded")),
            "source": "registry",
        }
        (excluded if row["excluded"] else included).append(row)
    for path, o in pages_reg.items():
        if any(p == path for p, _, _ in PUBLIC_PAGES):
            continue
        if not path.startswith("/") or ":" in path or "*" in path:
            continue
        row = {
            "path": path,
            "changefreq": o.get("changefreq") or "monthly",
            "priority": str(o.get("priority") or "0.5"),
            "excluded": bool(o.get("excluded")),
            "source": "admin",
        }
        (excluded if row["excluded"] else included).append(row)

    origin = get_origin(request)
    return {
        "sitemap": {
            "origin": origin,
            "urls_included": included,
            "urls_excluded": excluded,
            "url_count": len(included),
            "sitemap_index_url": f"{origin}/api/seo/sitemap.xml" if origin else "/api/seo/sitemap.xml",
            "typed_sitemaps": [
                {"name": "pages",   "url": f"{origin}/api/seo/sitemap-pages.xml"   if origin else "/api/seo/sitemap-pages.xml"},
                {"name": "catalog", "url": f"{origin}/api/seo/sitemap-catalog.xml" if origin else "/api/seo/sitemap-catalog.xml"},
                {"name": "blog",    "url": f"{origin}/api/seo/sitemap-blog.xml"    if origin else "/api/seo/sitemap-blog.xml"},
                {"name": "images",  "url": f"{origin}/api/seo/sitemap-images.xml"  if origin else "/api/seo/sitemap-images.xml"},
            ],
        }
    }


@router.get("/sitemap/preview", dependencies=[Depends(require_master_admin)])
async def preview_sitemap(request: Request, kind: str = Query("pages", description="pages|index|catalog|blog|images")):
    from app.seo import config as _seo_config
    from app.seo import sitemap as sm
    await _seo_config.load(_db(), force=True)
    kind = (kind or "pages").lower()
    if kind == "index":
        xml = sm.sitemap_index(request)
    elif kind == "pages":
        xml = sm.sitemap_pages(request)
    elif kind == "catalog":
        xml = await sm.sitemap_catalog(_db(), request)
    elif kind == "blog":
        xml = await sm.sitemap_blog(_db(), request)
    elif kind == "images":
        xml = await sm.sitemap_images(_db(), request)
    else:
        raise HTTPException(422, "kind: index|pages|catalog|blog|images")
    return Response(content=xml, media_type="application/xml")


@router.post("/sitemap/regenerate", dependencies=[Depends(require_master_admin)])
async def regenerate_sitemap():
    """Invalidate every SEO cache so the next request builds a fresh sitemap.

    We do not pre-generate + store the XML: the engine is fast and depends on
    live collections (blog articles, waste codes). Regeneration = force cache
    refresh + timestamp so the admin UI can display "Last regenerated at …".
    """
    _invalidate_cache()
    now = datetime.now(timezone.utc)
    await _db().seo_settings.update_one(
        {"_id": _SETTINGS_DOC_ID},
        {"$set": {"sitemap_regenerated_at": now}},
        upsert=True,
    )
    return {"success": True, "regenerated_at": now.isoformat()}


__all__ = ["router"]
