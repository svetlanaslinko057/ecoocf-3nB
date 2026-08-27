"""
Dynamic sitemap engine.

Emits a sitemap INDEX plus typed child sitemaps:
  * sitemap-pages.xml     — static public pages (+ hreflang alternates)
  * sitemap-catalog.xml   — waste categories + national-classifier codes
  * sitemap-blog.xml      — published blog articles
  * sitemap-images.xml    — image entries for image search

Every <url> carries <lastmod>, <changefreq>, <priority> and, where the
content is bilingual, xhtml:link alternates (uk / en / x-default).

Resilient: a missing collection yields a smaller (still valid) sitemap.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from .origin import get_origin
from .hreflang import hreflang_alternates

_XHTML_NS = 'xmlns:xhtml="http://www.w3.org/1999/xhtml"'


def w3c_date(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    if isinstance(value, str) and value:
        return value[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _url_block(loc: str, lastmod: str, changefreq: str, priority: str,
               alternates: Optional[List[Dict[str, str]]] = None,
               images: Optional[List[Dict[str, str]]] = None) -> str:
    parts = ["  <url>", f"    <loc>{escape(loc)}</loc>"]
    for alt in alternates or []:
        parts.append(
            f'    <xhtml:link rel="alternate" hreflang="{escape(alt["hreflang"])}" '
            f'href="{escape(alt["href"])}"/>'
        )
    for img in images or []:
        parts.append("    <image:image>")
        parts.append(f"      <image:loc>{escape(img.get('loc',''))}</image:loc>")
        if img.get("title"):
            parts.append(f"      <image:title>{escape(img['title'])}</image:title>")
        parts.append("    </image:image>")
    parts.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


def _wrap(urls: List[str], with_images: bool = False) -> bytes:
    ns = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          + _XHTML_NS)
    if with_images:
        ns += ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
    ns += ">"
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n' + ns + "\n"
           + "\n".join(urls) + "\n</urlset>\n")
    return xml.encode("utf-8")


# ──────────────── static public pages ─────────────────────────────
PUBLIC_PAGES = [
    ("/",          "daily",   "1.0"),
    ("/waste",     "weekly",  "0.9"),
    ("/calculator","monthly", "0.8"),
    ("/blog",      "weekly",  "0.7"),
    ("/contacts",  "monthly", "0.7"),
    ("/terms",     "yearly",  "0.3"),
    ("/privacy",   "yearly",  "0.3"),
    ("/cookies",   "yearly",  "0.3"),
]


def sitemap_pages(request=None) -> bytes:
    # Deferred import to avoid a startup-time cycle.
    from . import config as _seo_config

    origin = get_origin(request)
    today = w3c_date(None)
    urls = []
    pages_reg = _seo_config.pages_registry() or {}
    # Excluded paths (admin-managed via seo_page_metadata.excluded=true).
    excluded = {p for p, o in pages_reg.items() if o.get("excluded")}

    for path, cf, pr in PUBLIC_PAGES:
        if path in excluded:
            continue
        override = pages_reg.get(path) or {}
        urls.append(_url_block(
            loc=f"{origin}{path}" if path != "/" else f"{origin}/",
            lastmod=w3c_date(override.get("lastmod")) if override.get("lastmod") else today,
            changefreq=(override.get("changefreq") or cf),
            priority=str(override.get("priority") or pr),
            alternates=hreflang_alternates(path, request),
        ))
    # Extra pages added purely from admin panel (paths not in PUBLIC_PAGES).
    known = {p for p, _, _ in PUBLIC_PAGES}
    for path, o in pages_reg.items():
        if path in known:
            continue
        if o.get("excluded"):
            continue
        # Only include paths that look like public routes.
        if not path.startswith("/") or path.startswith(("/app", "/admin", "/client", "/api")):
            continue
        # Skip dynamic patterns / templates (contain :param or *).
        if ":" in path or "*" in path:
            continue
        urls.append(_url_block(
            loc=f"{origin}{path}",
            lastmod=w3c_date(o.get("lastmod")) if o.get("lastmod") else today,
            changefreq=(o.get("changefreq") or "monthly"),
            priority=str(o.get("priority") or "0.5"),
            alternates=hreflang_alternates(path, request),
        ))
    return _wrap(urls)


async def sitemap_catalog(db, request=None) -> bytes:
    origin = get_origin(request)
    today = w3c_date(None)
    urls: List[str] = []
    # categories
    try:
        if db is not None:
            cats = await db.waste_codes.distinct("category")
            for key in sorted(c for c in cats if c):
                path = f"/waste/category/{key}"
                urls.append(_url_block(
                    loc=f"{origin}{path}", lastmod=today,
                    changefreq="weekly", priority="0.7",
                    alternates=hreflang_alternates(path, request),
                ))
    except Exception:
        pass
    # codes
    try:
        if db is not None:
            cursor = db.waste_codes.find(
                {"slug": {"$exists": True, "$nin": [None, ""]}},
                {"_id": 0, "slug": 1, "updated_at": 1},
            ).limit(20000)
            async for c in cursor:
                slug = c.get("slug")
                if not slug:
                    continue
                path = f"/waste-code/{slug}"
                urls.append(_url_block(
                    loc=f"{origin}{path}",
                    lastmod=w3c_date(c.get("updated_at")),
                    changefreq="monthly", priority="0.6",
                    alternates=hreflang_alternates(path, request),
                ))
    except Exception:
        pass
    return _wrap(urls)


async def sitemap_blog(db, request=None) -> bytes:
    origin = get_origin(request)
    urls: List[str] = []
    try:
        if db is not None:
            cursor = db.blog_articles.find(
                {"$or": [{"published": True},
                          {"status": {"$in": ["published", "live"]}}]},
                {"_id": 0, "slug": 1, "updated_at": 1, "published_at": 1},
            ).limit(5000)
            async for a in cursor:
                slug = a.get("slug")
                if not slug:
                    continue
                path = f"/blog/{slug}"
                urls.append(_url_block(
                    loc=f"{origin}{path}",
                    lastmod=w3c_date(a.get("updated_at") or a.get("published_at")),
                    changefreq="weekly", priority="0.65",
                    alternates=hreflang_alternates(path, request),
                ))
    except Exception:
        pass
    return _wrap(urls)


async def sitemap_images(db, request=None) -> bytes:
    origin = get_origin(request)
    urls: List[str] = []
    try:
        if db is not None:
            cursor = db.blog_articles.find(
                {"$or": [{"published": True},
                          {"status": {"$in": ["published", "live"]}}]},
                {"_id": 0, "slug": 1, "cover_image": 1, "image": 1, "title": 1},
            ).limit(5000)
            async for a in cursor:
                slug = a.get("slug")
                img = a.get("cover_image") or a.get("image")
                if not slug or not img:
                    continue
                urls.append(_url_block(
                    loc=f"{origin}/blog/{slug}", lastmod=w3c_date(None),
                    changefreq="monthly", priority="0.4",
                    images=[{"loc": img, "title": a.get("title") or ""}],
                ))
    except Exception:
        pass
    return _wrap(urls, with_images=True)


async def sitemap_content(db, request=None) -> bytes:
    """Emit URLs for every PUBLISHED page in the CMS `content_pages`
    collection (Phase D1). Drafts / review / archived are excluded.
    Deduplicates against static PUBLIC_PAGES and blog/catalog sitemaps.
    """
    origin = get_origin(request)
    urls: List[str] = []
    try:
        if db is not None:
            static_paths = {p for p, _, _ in PUBLIC_PAGES}
            cursor = db.content_pages.find(
                {"status": "published"},
                {"_id": 0, "path": 1, "lang": 1, "kind": 1,
                 "updated_at": 1, "published_at": 1},
            ).limit(20000)
            # Group by path so we hreflang once per URL.
            paths_seen: Dict[str, Dict[str, Any]] = {}
            async for p in cursor:
                path = p.get("path")
                if not path:
                    continue
                # Skip anything that already ships from PUBLIC_PAGES /
                # blog / catalog sitemaps to avoid duplicates.
                if path in static_paths:
                    continue
                if path.startswith(("/blog/", "/waste-code/", "/waste/category/")):
                    continue
                # Also skip admin / api / client prefixes as defence-in-depth.
                if path.startswith(("/app", "/admin", "/client", "/api", "/oauth")):
                    continue
                existing = paths_seen.get(path)
                lastmod = p.get("updated_at") or p.get("published_at")
                if not existing or (lastmod and (existing.get("lastmod") or "") < lastmod):
                    kind = (p.get("kind") or "page").lower()
                    prio = "0.75" if kind in ("service", "industry") else \
                           "0.85" if kind == "landing" else "0.6"
                    paths_seen[path] = {"lastmod": lastmod, "priority": prio}
            for path, o in paths_seen.items():
                urls.append(_url_block(
                    loc=f"{origin}{path}",
                    lastmod=w3c_date(o.get("lastmod")),
                    changefreq="weekly",
                    priority=o["priority"],
                    alternates=hreflang_alternates(path, request),
                ))
    except Exception:
        pass
    return _wrap(urls)


def sitemap_index(request=None, children: Optional[List[str]] = None) -> bytes:
    origin = get_origin(request)
    today = w3c_date(None)
    children = children or [
        "/api/seo/sitemap-pages.xml",
        "/api/seo/sitemap-catalog.xml",
        "/api/seo/sitemap-blog.xml",
        "/api/seo/sitemap-content.xml",
        "/api/seo/sitemap-images.xml",
    ]
    rows = "".join(
        f"  <sitemap><loc>{escape(origin + c)}</loc>"
        f"<lastmod>{today}</lastmod></sitemap>\n"
        for c in children
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + rows + "</sitemapindex>\n")
    return xml.encode("utf-8")
