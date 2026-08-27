"""
SEO Prerender engine — Phase C.

Produces a fully-rendered HTML document for any known public route so bots
(Googlebot, Bingbot, DuckDuckBot, FacebookExternalHit, Twitterbot,
LinkedInBot, Slackbot, TelegramBot, …) receive complete HTML on the first
byte — no JavaScript execution required.

What's inside every prerendered page
------------------------------------
* `<title>` + `<meta name="description">`  (from Admin SEO Center)
* `<link rel="canonical">`
* `<link rel="alternate" hreflang="uk|en|x-default">`
* Full OpenGraph + Twitter Card meta tags
* JSON-LD `@graph`: Organization + LocalBusiness + WebPage + BreadcrumbList
  + FAQPage + Article + SoftwareApplication as applicable
* Human-readable page body:
    – `<h1>` with the page title
    – Lead paragraph = description
    – Optional H2 sections with route-specific content
    – Optional FAQ section rendered as `<details>` (also mirrored in
      JSON-LD FAQPage)
    – Breadcrumb `<nav>`
    – Language switcher links
* NO cloaking: exactly the same title/description/JSON-LD the SPA renders.

What we NEVER prerender
-----------------------
* /app/*, /admin/*, /client/*, /api/*  — private surfaces
* Any path with wildcard/query characters that could DoS us
* Any path when the master indexing switch is OFF *AND* the admin has not
  explicitly enabled a `preview_prerender` toggle → we emit `<meta
  name="robots" content="noindex,nofollow">` instead so preview/stage
  domains never accidentally get indexed.

Cache
-----
* Layer 1: in-process dict, TTL = 5 minutes (survives request bursts).
* Layer 2: Mongo `seo_prerender_cache` collection, TTL = 24 hours.
* Invalidation: any admin write to seo_settings / seo_page_metadata /
  seo_robots_rules calls `invalidate_prerender_cache()`.
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request

logger = logging.getLogger("bibi.prerender")

# ─── Route allow-list ──────────────────────────────────────────────────
# Static routes we can prerender safely.
STATIC_ROUTES = (
    "/", "/services", "/waste", "/calculator", "/licenses",
    "/contacts", "/about", "/blog",
    "/terms", "/privacy", "/cookies",
)

# Dynamic route matchers — each returns (matched, resolver_key, param).
_DYNAMIC_ROUTES = (
    (re.compile(r"^/waste-code/(?P<slug>[A-Za-z0-9\-._]+)$"),          "waste_code"),
    (re.compile(r"^/waste/category/(?P<key>[A-Za-z0-9\-._]+)$"),        "waste_category"),
    (re.compile(r"^/blog/(?P<slug>[A-Za-z0-9\-._]+)$"),                 "blog_post"),
)

# Private/private-adjacent paths that MUST be refused for prerender.
_PRIVATE_PREFIXES = ("/app", "/admin", "/client", "/api", "/oauth", "/contract",
                     "/portal", "/manage")

# In-process cache — key: (path, lang, indexing_allowed_flag)
_MEM_TTL = 5 * 60  # 5 minutes
_MEM_CACHE: Dict[Tuple[str, str, bool], Tuple[float, str]] = {}
_MEM_LOCK_STAMP = 0.0

# Metrics — updated in-process; also persisted best-effort to Mongo.
_METRICS: Dict[str, Any] = {
    "renders": 0,
    "cache_hits_mem": 0,
    "cache_hits_db": 0,
    "cache_misses": 0,
    "last_render_at": None,
    "per_route": {},   # path → {"hits": n, "last": iso}
}


def classify_route(path: str) -> Tuple[str, Dict[str, str]]:
    """Return ("static"|"dynamic:<key>"|"unknown"|"private", params)."""
    if not path or not path.startswith("/"):
        return "unknown", {}
    for prefix in _PRIVATE_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return "private", {}
    p = path if path == "/" else path.rstrip("/")
    if p in STATIC_ROUTES:
        return "static", {}
    for rx, key in _DYNAMIC_ROUTES:
        m = rx.match(p)
        if m:
            return f"dynamic:{key}", dict(m.groupdict())
    return "unknown", {}


def is_prerenderable(path: str) -> bool:
    kind, _ = classify_route(path)
    return kind == "static" or kind.startswith("dynamic:")


# ─── HTML helpers ─────────────────────────────────────────────────────
def _h(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _meta(name: str, content: str) -> str:
    return f'<meta name="{_h(name)}" content="{_h(content)}">'


def _og(prop: str, content: str) -> str:
    return f'<meta property="{_h(prop)}" content="{_h(content)}">'


def _link(rel: str, href: str, **extra) -> str:
    attrs = " ".join(f'{k}="{_h(v)}"' for k, v in extra.items() if v)
    return f'<link rel="{_h(rel)}" href="{_h(href)}"{" " + attrs if attrs else ""}>'


def _link_hreflang(alternates: List[Dict[str, str]]) -> str:
    # `alternates` is produced by app.seo.hreflang.hreflang_alternates(), which
    # returns dicts keyed by "hreflang" (Google's canonical attribute name). We
    # ALSO accept "lang" as a legacy fallback for any historic callers.
    return "".join(
        _link(
            "alternate",
            a.get("href") or "",
            hreflang=(a.get("hreflang") or a.get("lang") or ""),
        )
        for a in alternates
        if a.get("href")
    )


# ─── Content resolvers ────────────────────────────────────────────────
async def _fetch_dynamic_content(request: Request, path: str, lang: str) -> Dict[str, Any]:
    """Return route-specific body content. Never fabricates: unknown fields
    stay empty and the HTML template just omits the section.

    Phase D1 hook: if the admin has published a CMS page for this path+lang,
    the block-rendered HTML replaces the default sections and its SEO
    metadata (title/description/keywords/og_image) overrides the defaults
    resolved from `seo_page_metadata`.
    """
    from app.core.db_runtime import get_db
    db = get_db()
    out: Dict[str, Any] = {"sections": [], "faq": [], "meta_extra": {}, "cms_html": "", "cms_meta": {}}

    # ─── CMS override (Phase D1) ────────────────────────────────────
    try:
        from app.content.service import ContentPageService, FAQService
        cms_svc = ContentPageService(db)
        cms_page = await cms_svc.get_public(path, lang)
        if cms_page:
            from app.content.blocks import render_blocks_html
            faq_svc = FAQService(db)

            # Sync resolver isn't possible from render_blocks_html; instead
            # pre-resolve any faq_group references before render:
            blocks = cms_page.get("blocks") or []
            for b in blocks:
                if b.get("type") == "faq" and b.get("faq_group") and not b.get("items"):
                    try:
                        b["items"] = await faq_svc.resolve_group(b["faq_group"], lang)
                    except Exception:
                        b["items"] = []
            out["cms_html"] = render_blocks_html(blocks)
            out["cms_meta"] = {
                "title": (cms_page.get("seo") or {}).get("title") or cms_page.get("title"),
                "description": (cms_page.get("seo") or {}).get("description") or cms_page.get("summary"),
                "keywords": (cms_page.get("seo") or {}).get("keywords"),
                "og_image": (cms_page.get("seo") or {}).get("og_image"),
                "canonical_override": (cms_page.get("seo") or {}).get("canonical_override"),
                "robots": (cms_page.get("seo") or {}).get("robots"),
                "breadcrumbs": (cms_page.get("cms") or {}).get("breadcrumbs") or [],
                "cover_image_url": (cms_page.get("cms") or {}).get("cover_image_url"),
            }
            # Also pull per-page published FAQ (rendered as an extra <section> below)
            try:
                items = await faq_svc.list(page_path=path, lang=lang, published_only=True, limit=50)
                if items:
                    out["faq"] = [{"question": f.get("question"), "answer": f.get("answer")} for f in items]
            except Exception:
                pass
    except Exception as e:
        logger.debug("cms override skipped for %s (%s): %s", path, lang, e)

    if path.startswith("/waste-code/"):
        slug = path.rsplit("/", 1)[-1]
        try:
            doc = await db.waste_codes.find_one({"slug": slug}, {"_id": 0}) or {}
            if doc:
                code = doc.get("code") or slug
                hazard = doc.get("hazard_class") or doc.get("hazard")
                desc = doc.get("description_uk") if lang == "uk" else doc.get("description_en")
                desc = desc or doc.get("description") or ""
                if desc:
                    out["sections"].append({
                        "h2": ("Опис коду" if lang == "uk" else "Code description"),
                        "text": desc,
                    })
                if hazard:
                    out["sections"].append({
                        "h2": ("Клас небезпеки" if lang == "uk" else "Hazard class"),
                        "text": hazard,
                    })
                methods = doc.get("methods") or doc.get("utilization_methods") or []
                if isinstance(methods, list) and methods:
                    out["sections"].append({
                        "h2": ("Методи утилізації" if lang == "uk" else "Utilization methods"),
                        "list": [str(m) for m in methods if m],
                    })
                out["meta_extra"]["code"] = code
        except Exception as e:
            logger.debug("waste_code fetch failed: %s", e)

    elif path.startswith("/waste/category/"):
        key = path.rsplit("/", 1)[-1]
        try:
            # Aggregate codes in this category so the page has real content.
            cursor = db.waste_codes.find({"category": key}, {"_id": 0, "code": 1, "name_uk": 1, "name_en": 1, "slug": 1}).limit(50)
            items = []
            async for row in cursor:
                items.append(row)
            if items:
                label_field = "name_uk" if lang == "uk" else "name_en"
                out["sections"].append({
                    "h2": ("Коди у категорії" if lang == "uk" else "Codes in category"),
                    "list": [
                        f"{row.get('code','')} — {row.get(label_field) or row.get('name_uk') or row.get('name_en') or ''}"
                        for row in items
                    ],
                })
        except Exception as e:
            logger.debug("waste_category fetch failed: %s", e)

    elif path.startswith("/blog/"):
        slug = path.rsplit("/", 1)[-1]
        try:
            doc = await db.blog_articles.find_one({"slug": slug}, {"_id": 0}) or {}
            if doc:
                lead = doc.get("excerpt") or doc.get("summary") or ""
                body_md = doc.get("body_uk") if lang == "uk" else doc.get("body_en")
                body_md = body_md or doc.get("body") or doc.get("content") or ""
                if lead:
                    out["sections"].append({"h2": "", "text": lead})
                if body_md:
                    # Very light markdown-to-text: strip HTML tags, collapse whitespace.
                    plain = re.sub(r"<[^>]+>", " ", str(body_md))
                    plain = re.sub(r"\s+", " ", plain).strip()
                    # Split into ~600-char sections separated by \n\n if present.
                    for chunk in re.split(r"\n{2,}", plain):
                        chunk = chunk.strip()
                        if chunk:
                            out["sections"].append({"text": chunk})
                if doc.get("cover_image") or doc.get("image"):
                    out["meta_extra"]["cover"] = doc.get("cover_image") or doc.get("image")
        except Exception as e:
            logger.debug("blog fetch failed: %s", e)

    elif path == "/" or path == "/services":
        # Homepage / services: minimal, static, translation-safe copy.
        if lang == "uk":
            out["sections"] = [
                {"h2": "Утилізація небезпечних відходів для бізнесу",
                 "text": "ECO.NOVA — ліцензований оператор поводження з небезпечними відходами. Ми супроводжуємо клієнтів на всіх етапах: від класифікації і паспортизації до транспортування і документального закриття."},
                {"h2": "Що ми утилізуємо",
                 "list": [
                     "Відпрацьовані нафтопродукти та мастила",
                     "Медичні та біологічні відходи",
                     "Промислова хімія, кислоти й луги",
                     "Ртутьмісткі лампи та прилади",
                     "Батарейки та акумулятори",
                     "Тверді промислові відходи (Клас I–IV)",
                 ]},
                {"h2": "Чому обирають ECO.NOVA",
                 "list": [
                     "Актуальна ліцензія на поводження з небезпечними відходами",
                     "Повний документообіг: договір, акти, декларації, звіти",
                     "Власний спецтранспорт (ADR)",
                     "Прозорий калькулятор і фіксовані ціни",
                 ]},
            ]
        else:
            out["sections"] = [
                {"h2": "Hazardous waste utilization for B2B",
                 "text": "ECO.NOVA is a licensed operator for hazardous waste management. We support clients end-to-end: classification, passportization, transport (ADR) and full documentation."},
                {"h2": "What we handle",
                 "list": ["Used oils and lubricants", "Medical and bio waste", "Industrial chemicals, acids, alkalis",
                          "Mercury-containing lamps", "Batteries and accumulators", "Solid industrial waste (Class I–IV)"]},
                {"h2": "Why ECO.NOVA",
                 "list": ["Active hazardous-waste license", "Full paperwork: contract, acts, declarations, reports",
                          "Own ADR transport", "Transparent calculator and fixed pricing"]},
            ]

    elif path == "/waste":
        if lang == "uk":
            out["sections"] = [
                {"h2": "Каталог кодів відходів",
                 "text": "Повний класифікатор небезпечних відходів згідно з національним каталогом. Оберіть категорію або скористайтесь пошуком за кодом."},
            ]
        else:
            out["sections"] = [
                {"h2": "Waste catalog",
                 "text": "Full classifier of hazardous waste per Ukraine's national catalog. Pick a category or search by code."},
            ]

    elif path == "/calculator":
        if lang == "uk":
            out["sections"] = [
                {"h2": "Онлайн-калькулятор утилізації",
                 "text": "Швидка попередня оцінка вартості поводження з відходами. Вкажіть категорію, обсяг і клас — отримайте орієнтовну ціну і чек-лист документів."},
            ]
        else:
            out["sections"] = [
                {"h2": "Online utilization calculator",
                 "text": "Get an instant preliminary quote. Choose category, volume and class — receive an indicative price and a document checklist."},
            ]

    elif path == "/licenses":
        if lang == "uk":
            out["sections"] = [
                {"h2": "Ліцензії та дозволи",
                 "text": "ECO.NOVA працює на підставі ліцензії на поводження з небезпечними відходами. Номер ліцензії, дата видачі та ліцензійний орган публікуються на цій сторінці і в структурованих даних."},
            ]
        else:
            out["sections"] = [
                {"h2": "Licenses and permits",
                 "text": "ECO.NOVA operates under a hazardous-waste license issued by the competent authority. The license number, issue date and issuer are published on this page and in structured data."},
            ]

    elif path == "/contacts":
        if lang == "uk":
            out["sections"] = [
                {"h2": "Контакти",
                 "text": "Зателефонуйте, напишіть на пошту або залиште заявку — менеджер зв'яжеться протягом однієї робочої години."},
            ]
        else:
            out["sections"] = [
                {"h2": "Contacts",
                 "text": "Call, email us or leave a request — a manager will get back to you within one business hour."},
            ]

    elif path == "/about":
        if lang == "uk":
            out["sections"] = [
                {"h2": "Про ECO.NOVA",
                 "text": "Команда інженерів і екологів із багаторічним досвідом у поводженні з небезпечними відходами. Ми ліцензовані, прозорі й документально підзвітні на всіх етапах виконання договору."},
            ]
        else:
            out["sections"] = [
                {"h2": "About ECO.NOVA",
                 "text": "Engineers and ecologists with years of experience in hazardous-waste operations. Licensed, transparent and fully documented at every step."},
            ]

    elif path == "/blog":
        try:
            cursor = db.blog_articles.find(
                {"published": True},
                {"_id": 0, "title": 1, "slug": 1, "excerpt": 1, "published_at": 1}
            ).sort("published_at", -1).limit(20)
            items = []
            async for row in cursor:
                items.append(row)
            if items:
                out["sections"].append({
                    "h2": ("Останні статті" if lang == "uk" else "Latest articles"),
                    "articles": [
                        {"title": r.get("title") or r.get("slug"),
                         "url":   f"/blog/{r.get('slug')}",
                         "excerpt": r.get("excerpt") or ""}
                        for r in items if r.get("slug")
                    ],
                })
        except Exception as e:
            logger.debug("blog list fetch failed: %s", e)

    elif path in ("/terms", "/privacy", "/cookies"):
        # These are already served by the app's public content collections;
        # falling back to a placeholder H2 so the page is not empty for bots.
        titles = {
            "/terms":    ("Умови користування", "Terms of use"),
            "/privacy":  ("Політика приватності", "Privacy policy"),
            "/cookies":  ("Політика cookies", "Cookies policy"),
        }
        title = titles[path][0 if lang == "uk" else 1]
        try:
            slug_map = {"/terms": "terms", "/privacy": "privacy", "/cookies": "cookies"}
            doc = await db.legal_pages.find_one({"slug": slug_map[path]}, {"_id": 0}) or {}
            body = (doc.get("body_uk") if lang == "uk" else doc.get("body_en")) or doc.get("body") or ""
            plain = re.sub(r"<[^>]+>", " ", str(body))
            plain = re.sub(r"\s+", " ", plain).strip()
            if plain:
                out["sections"].append({"h2": title, "text": plain[:2500]})
            else:
                out["sections"].append({"h2": title, "text": ""})
        except Exception:
            out["sections"].append({"h2": title, "text": ""})

    return out


# ─── HTML template ────────────────────────────────────────────────────
def _render_html(meta: Dict[str, Any], content: Dict[str, Any], *, origin: str,
                 indexing_allowed: bool, company: Dict[str, Any]) -> str:
    lang = meta.get("lang") or "uk"
    title = meta.get("title") or company.get("name") or "ECO.NOVA"
    descr = meta.get("description") or ""
    kw    = meta.get("keywords") or ""
    canon = meta.get("canonical") or ""
    og    = meta.get("og") or {}
    tw    = meta.get("twitter") or {}
    crumbs = meta.get("breadcrumbs") or []
    faq   = meta.get("_faq") or []
    jsonld = meta.get("jsonld") or ""
    if isinstance(jsonld, (dict, list)):
        jsonld_str = json.dumps(jsonld, ensure_ascii=False, separators=(",", ":"))
    else:
        jsonld_str = str(jsonld)

    robots_val = meta.get("robots") or "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"
    if not indexing_allowed:
        robots_val = "noindex,nofollow"

    head_parts: List[str] = [
        '<!DOCTYPE html>',
        f'<html lang="{_h(lang)}">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{_h(title)}</title>',
        _meta("description", descr),
    ]
    if kw:
        head_parts.append(_meta("keywords", kw))
    head_parts.append(_meta("robots", robots_val))
    if canon:
        head_parts.append(_link("canonical", canon))
    head_parts.append(_link_hreflang(meta.get("hreflang") or []))

    # OpenGraph
    head_parts.extend([
        _og("og:type",        og.get("type") or "website"),
        _og("og:site_name",   og.get("site_name") or company.get("name") or "ECO.NOVA"),
        _og("og:title",       og.get("title") or title),
        _og("og:description", og.get("description") or descr),
        _og("og:url",         og.get("url") or canon),
        _og("og:locale",      og.get("locale") or ("uk_UA" if lang == "uk" else "en_US")),
    ])
    if og.get("locale_alternate"):
        head_parts.append(_og("og:locale:alternate", og["locale_alternate"]))
    if og.get("image"):
        head_parts.append(_og("og:image", og["image"]))
        head_parts.append(_og("og:image:alt", og.get("title") or title))
    # Twitter
    head_parts.extend([
        _meta("twitter:card",        tw.get("card") or "summary_large_image"),
        _meta("twitter:title",       tw.get("title") or title),
        _meta("twitter:description", tw.get("description") or descr),
    ])
    if tw.get("image"):
        head_parts.append(_meta("twitter:image", tw["image"]))

    # JSON-LD @graph
    if jsonld_str:
        head_parts.append(f'<script type="application/ld+json">{jsonld_str}</script>')

    head_parts.append('<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.55;max-width:960px;margin:2rem auto;padding:0 1.25rem;color:#18181B}h1{font-size:1.9rem;margin:.25rem 0 .75rem}h2{font-size:1.35rem;margin:1.5rem 0 .5rem;color:#3F3F46}nav.breadcrumbs{font-size:.85rem;color:#71717A;margin-bottom:1rem}nav.breadcrumbs a{color:#71717A;text-decoration:none}nav.breadcrumbs a:hover{text-decoration:underline}ul{padding-left:1.5rem}details{border-top:1px solid #E4E4E7;padding:.75rem 0}details summary{cursor:pointer;font-weight:600}footer{margin-top:3rem;border-top:1px solid #E4E4E7;padding-top:1rem;color:#71717A;font-size:.85rem}.lang a{margin-right:.75rem}</style>')
    head_parts.append('</head>')

    # Body
    body_parts: List[str] = ['<body>']

    # Breadcrumbs
    if crumbs:
        body_parts.append('<nav class="breadcrumbs" aria-label="Breadcrumbs">')
        parts = []
        for c in crumbs:
            name = c.get("name") or ""
            url = c.get("url") or ""
            if url:
                parts.append(f'<a href="{_h(url)}">{_h(name)}</a>')
            else:
                parts.append(_h(name))
        body_parts.append(" › ".join(parts))
        body_parts.append('</nav>')

    body_parts.append(f'<h1>{_h(meta.get("shortTitle") or title)}</h1>')
    if descr:
        body_parts.append(f'<p>{_h(descr)}</p>')

    # CMS-rendered body (Phase D1) — if the admin has published a block-based
    # page for this route, its HTML replaces the static route-specific
    # sections below. The default sections still render if there is no CMS
    # override (backwards-compatible with Phase C behaviour).
    cms_html = (content.get("cms_html") or "").strip()
    if cms_html:
        body_parts.append('<main class="cms-body">')
        body_parts.append(cms_html)
        body_parts.append('</main>')
    else:
        # Content sections (fallback)
        for sec in (content.get("sections") or []):
            h2 = sec.get("h2")
            if h2:
                body_parts.append(f'<h2>{_h(h2)}</h2>')
            text = sec.get("text")
            if text:
                body_parts.append(f'<p>{_h(text)}</p>')
            lst = sec.get("list")
            if isinstance(lst, list) and lst:
                body_parts.append('<ul>')
                for li in lst:
                    body_parts.append(f'<li>{_h(li)}</li>')
                body_parts.append('</ul>')
            arts = sec.get("articles")
            if isinstance(arts, list) and arts:
                body_parts.append('<ul>')
                for a in arts:
                    body_parts.append(f'<li><a href="{_h(a.get("url"))}">{_h(a.get("title"))}</a>{": " + _h(a.get("excerpt")) if a.get("excerpt") else ""}</li>')
                body_parts.append('</ul>')

    # FAQ (admin-provided per-page + legacy)
    cms_faq = content.get("faq") or []
    if cms_faq:
        body_parts.append('<section aria-label="FAQ" class="cms-page-faq">')
        body_parts.append(f'<h2>{"Поширені запитання" if lang == "uk" else "Frequently asked questions"}</h2>')
        for row in cms_faq:
            q = _h(row.get("question") or row.get("q") or "")
            a_raw = row.get("answer") or row.get("a") or ""
            if q and a_raw:
                # Answers from CMS are already sanitised HTML; render as-is.
                body_parts.append(f'<details><summary>{q}</summary><div>{a_raw}</div></details>')
        body_parts.append('</section>')

    if faq and not cms_faq:
        body_parts.append('<section aria-label="FAQ">')
        body_parts.append(f'<h2>{"Поширені запитання" if lang == "uk" else "Frequently asked questions"}</h2>')
        for row in faq:
            q = _h(row.get("q") or "")
            a = _h(row.get("a") or "")
            if q and a:
                body_parts.append(f'<details><summary>{q}</summary><p>{a}</p></details>')
        body_parts.append('</section>')

    # Language switcher (from hreflang) — read both "hreflang" (canonical key
    # produced by hreflang_alternates) and "lang" (legacy fallback).
    def _alt_lang(a):
        return a.get("hreflang") or a.get("lang") or ""

    alts = [a for a in (meta.get("hreflang") or []) if _alt_lang(a) not in ("x-default", "")]
    if alts:
        body_parts.append(f'<p class="lang" aria-label="{"Мова" if lang == "uk" else "Language"}">')
        for a in alts:
            lg = _alt_lang(a)
            body_parts.append(f'<a href="{_h(a.get("href"))}" hreflang="{_h(lg)}">{_h(lg)}</a>')
        body_parts.append('</p>')

    # Footer with company E-E-A-T facts
    fields = []
    if company.get("legal_name"):    fields.append(company["legal_name"])
    if company.get("edrpou"):        fields.append(f"ЄДРПОУ {company['edrpou']}")
    if company.get("license_number"): fields.append(f"Ліцензія {company['license_number']}")
    if company.get("phone"):         fields.append(company["phone"])
    if company.get("email"):         fields.append(company["email"])
    if company.get("street"):        fields.append(", ".join(x for x in [company.get("street"), company.get("city")] if x))
    if fields:
        body_parts.append(f'<footer>{" · ".join(_h(f) for f in fields)}</footer>')

    body_parts.append('</body></html>')

    return "".join(head_parts) + "\n" + "".join(body_parts)


# ─── Public entry points ──────────────────────────────────────────────
async def render(request: Request, path: str, lang: str = "uk", *, force: bool = False) -> Tuple[str, Dict[str, Any]]:
    """Return (html, info). Uses caches unless `force`."""
    from app.routers.seo import resolve_page_meta, _company  # local imports to avoid cycle
    from app.seo import config as _seo_config
    from app.seo.origin import get_origin

    lang = "en" if (lang or "uk").lower().startswith("en") else "uk"
    path = path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    kind, params = classify_route(path)
    if kind == "private":
        raise PermissionError(f"Private path not eligible for prerender: {path}")
    if kind == "unknown":
        # Phase D1: any path that has a PUBLISHED content_pages doc is
        # a valid prerender target — services / industries / landings /
        # custom pages the admin created via the Content Center.
        try:
            from app.core.db_runtime import get_db as _get_db_check
            _db = _get_db_check()
            if _db is not None:
                cms_hit = await _db.content_pages.find_one(
                    {"path": path, "status": "published"},
                    {"_id": 0, "path": 1},
                )
                if cms_hit:
                    kind = "dynamic:cms_page"
                    params = {}
                else:
                    raise ValueError(f"Route not on the prerender allow-list: {path}")
            else:
                raise ValueError(f"Route not on the prerender allow-list: {path}")
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"Route not on the prerender allow-list: {path}")

    # Force a fresh SEO settings load so admin edits show up.
    from app.core.db_runtime import get_db
    db = get_db()
    await _seo_config.load(db)
    indexing_allowed = _seo_config.allow_indexing_in_production()

    cache_key = (path, lang, indexing_allowed)
    now = time.time()

    # ── Layer 1: in-memory ─────
    if not force and cache_key in _MEM_CACHE:
        ts, cached = _MEM_CACHE[cache_key]
        if now - ts < _MEM_TTL:
            _METRICS["cache_hits_mem"] += 1
            return cached, {"cache": "memory", "path": path, "lang": lang}

    # ── Layer 2: Mongo ─────────
    if not force:
        try:
            doc = await db.seo_prerender_cache.find_one({"_id": f"{path}|{lang}|{int(indexing_allowed)}"})
            if doc and (now - float(doc.get("ts", 0.0))) < 24 * 3600:
                cached = doc["html"]
                _MEM_CACHE[cache_key] = (now, cached)
                _METRICS["cache_hits_db"] += 1
                return cached, {"cache": "mongo", "path": path, "lang": lang}
        except Exception as e:
            logger.debug("mongo cache read failed: %s", e)

    # ── Miss → render ─────────
    _METRICS["cache_misses"] += 1
    meta = await resolve_page_meta(request, path=path, lang=lang)
    content = await _fetch_dynamic_content(request, path, lang)
    # CMS override: if a published content_pages doc exists for this path,
    # its SEO metadata takes precedence over seo_page_metadata defaults.
    cms_meta = content.get("cms_meta") or {}
    if cms_meta:
        if cms_meta.get("title"):
            meta["title"] = cms_meta["title"]
        if cms_meta.get("description"):
            meta["description"] = cms_meta["description"]
        if cms_meta.get("keywords"):
            meta["keywords"] = cms_meta["keywords"]
        if cms_meta.get("canonical_override"):
            meta["canonical"] = cms_meta["canonical_override"]
        if cms_meta.get("robots"):
            meta["robots"] = cms_meta["robots"]
        if cms_meta.get("og_image"):
            og = dict(meta.get("og") or {})
            og["image"] = cms_meta["og_image"]
            meta["og"] = og
            tw = dict(meta.get("twitter") or {})
            tw["image"] = cms_meta["og_image"]
            meta["twitter"] = tw
        if cms_meta.get("breadcrumbs"):
            # CMS breadcrumbs replace default breadcrumbs entirely.
            meta["breadcrumbs"] = [
                {"name": b.get("label"), "url": b.get("href")}
                for b in cms_meta["breadcrumbs"] if isinstance(b, dict)
            ]
    company = await _company(request)
    origin = get_origin(request)
    html_out = _render_html(meta, content, origin=origin, indexing_allowed=indexing_allowed, company=company)

    # Save caches
    _MEM_CACHE[cache_key] = (now, html_out)
    try:
        await db.seo_prerender_cache.update_one(
            {"_id": f"{path}|{lang}|{int(indexing_allowed)}"},
            {"$set": {
                "path": path, "lang": lang, "indexing_allowed": indexing_allowed,
                "html": html_out, "ts": now,
                "generated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug("mongo cache write failed: %s", e)

    # Metrics
    _METRICS["renders"] += 1
    _METRICS["last_render_at"] = datetime.now(timezone.utc).isoformat()
    r = _METRICS["per_route"].setdefault(path, {"hits": 0, "last": None})
    r["hits"] += 1
    r["last"] = _METRICS["last_render_at"]

    return html_out, {"cache": "miss", "path": path, "lang": lang}


def _clear_memory_cache() -> None:
    """Internal helper: wipe ONLY the in-memory layer. Used by both the
    public `invalidate_prerender_cache()` (which additionally schedules a
    Mongo purge) and `purge_mongo_cache()` (which does the Mongo delete
    first and then clears memory to avoid stale reads). Split out so the
    two entry points don't recurse into each other."""
    global _MEM_LOCK_STAMP
    _MEM_CACHE.clear()
    _MEM_LOCK_STAMP = time.time()


def invalidate_prerender_cache() -> None:
    """Wipe in-memory cache AND schedule Mongo cache clean-up.

    Admin writes to SEO settings / page metadata / company profile / robots
    must busy-clear BOTH layers so bots pick up the change on the next hit.
    Previously this only cleared the memory layer, leaving Mongo returning
    stale HTML for up to 24h — that broke the "changes propagate within
    minutes" user story from plan.md Phase 3.

    The Mongo purge is fire-and-forget (best-effort) so admin write paths
    stay synchronous and cheap; failure never blocks the write.
    """
    _clear_memory_cache()
    # Best-effort Mongo purge — schedule as a background task so we don't
    # block the admin write. If no running loop is present (rare: sync
    # test path), we simply skip the Mongo layer — the memory layer clear
    # above still ensures freshness for the next in-process request.
    try:
        import asyncio as _asyncio
        loop = _asyncio.get_running_loop()
        loop.create_task(_purge_mongo_cache_no_recurse())
    except RuntimeError:
        # No running event loop — best-effort skip.
        pass


async def _purge_mongo_cache_no_recurse() -> int:
    """Internal: delete every Mongo cache entry WITHOUT re-clearing memory
    (that would recurse into the async scheduler). Returns count deleted."""
    try:
        from app.core.db_runtime import get_db
        db = get_db()
        r = await db.seo_prerender_cache.delete_many({})
        return int(getattr(r, "deleted_count", 0) or 0)
    except Exception as e:
        logger.exception("_purge_mongo_cache_no_recurse failed: %s", e)
        return 0


async def purge_mongo_cache() -> int:
    """Delete every Mongo cache entry AND wipe the memory layer. Returns
    count deleted. Called by the /admin/purge admin endpoint. For the
    admin-write invalidation path use `invalidate_prerender_cache()`
    instead (that entry point schedules Mongo purge without recursion)."""
    deleted = await _purge_mongo_cache_no_recurse()
    _clear_memory_cache()
    return deleted


def metrics() -> Dict[str, Any]:
    return {**_METRICS, "cache_entries_memory": len(_MEM_CACHE)}


__all__ = [
    "render", "classify_route", "is_prerenderable",
    "invalidate_prerender_cache", "purge_mongo_cache", "metrics",
    "STATIC_ROUTES",
]
