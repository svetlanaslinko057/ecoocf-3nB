"""
Per-route metadata registry + resolver.

Each public route gets a UNIQUE title/description/keywords (uk + en) plus
type, image and change hints — no shared template. The resolver combines
this with canonical + hreflang + breadcrumbs so a single call returns
everything the frontend <SeoHead> (and the crawler prerender) needs.

Dynamic routes (waste category, waste code, blog article) receive their
values from the caller (DB lookups happen in the router, not here).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

SITE_NAME = "ECO.NOVA"
TITLE_SUFFIX = {
    "uk": "ECO.NOVA — утилізація небезпечних відходів",
    "en": "ECO.NOVA — hazardous-waste utilization",
}

# Static route registry. Keyed by exact path.
REGISTRY: Dict[str, Dict[str, Dict[str, str]]] = {
    "/": {
        "uk": {
            "title": "Утилізація небезпечних відходів для бізнесу",
            "description": "Ліцензований оператор поводження з небезпечними відходами: класифікація, збір, вивіз, утилізація та повний документальний супровід для бізнесу в одній прозорій B2B-системі.",
            "keywords": "утилізація небезпечних відходів, поводження з відходами, вивіз відходів, класифікація відходів",
        },
        "en": {
            "title": "Hazardous-waste utilization for business",
            "description": "Licensed hazardous-waste operator: classification, collection, transport, utilization and full documentary support for business in one transparent B2B system.",
            "keywords": "hazardous waste utilization, waste management Ukraine, waste disposal, waste classification",
        },
        "_meta": {"type": "website", "changefreq": "daily", "priority": "1.0"},
    },
    "/waste": {
        "uk": {
            "title": "Каталог кодів відходів за нацкласифікатором",
            "description": "Повний каталог кодів небезпечних відходів (класи 1–4) за національним класифікатором: матриця приймання, вимоги до пакування та утилізації.",
            "keywords": "коди відходів, нацперелік відходів, класифікація відходів",
        },
        "en": {
            "title": "Waste code catalog (national classifier)",
            "description": "Full catalog of hazardous-waste codes (classes 1–4) under the national classifier: acceptance matrix, packaging and utilization requirements.",
            "keywords": "waste codes, national waste list, waste classification Ukraine",
        },
        "_meta": {"type": "website", "changefreq": "weekly", "priority": "0.9"},
    },
    "/calculator": {
        "uk": {
            "title": "Калькулятор вартості утилізації відходів",
            "description": "Орієнтовний розрахунок вартості поводження з відходами за кодом, вагою, типом тари та логістикою — прозоро й швидко.",
            "keywords": "калькулятор відходів, вартість утилізації",
        },
        "en": {
            "title": "Waste utilization cost calculator",
            "description": "Estimate waste-handling cost by code, weight, container type and logistics — transparent and instant.",
            "keywords": "waste cost calculator, utilization price",
        },
        "_meta": {"type": "website", "changefreq": "monthly", "priority": "0.8", "app": True},
    },
    "/contacts": {
        "uk": {
            "title": "Контакти та заявка на послугу",
            "description": "Зв’яжіться з ECO.NOVA: телефон, email, адреса та форма заявки на поводження з небезпечними відходами для бізнесу.",
            "keywords": "контакти, заявка на вивіз відходів",
        },
        "en": {
            "title": "Contacts & service request",
            "description": "Reach ECO.NOVA: phone, email, address and a request form for hazardous-waste handling for business.",
            "keywords": "contacts, waste pickup request",
        },
        "_meta": {"type": "website", "changefreq": "monthly", "priority": "0.7"},
    },
    "/blog": {
        "uk": {
            "title": "Блог: поводження з відходами",
            "description": "Статті, гайди та новини галузі про поводження з небезпечними відходами, регулювання та екологічні практики.",
            "keywords": "блог, новини, гайди про відходи",
        },
        "en": {
            "title": "Blog: waste management",
            "description": "Articles, guides and industry news on hazardous-waste handling, regulation and environmental practice.",
            "keywords": "blog, waste news, guides",
        },
        "_meta": {"type": "website", "changefreq": "weekly", "priority": "0.7"},
    },
    "/terms": {
        "uk": {"title": "Умови використання", "description": "Умови використання платформи ECO.NOVA.", "keywords": ""},
        "en": {"title": "Terms of Use", "description": "Terms of use for the ECO.NOVA platform.", "keywords": ""},
        "_meta": {"type": "website", "changefreq": "yearly", "priority": "0.3"},
    },
    "/privacy": {
        "uk": {"title": "Політика конфіденційності", "description": "Як ECO.NOVA збирає та захищає персональні дані.", "keywords": ""},
        "en": {"title": "Privacy Policy", "description": "How ECO.NOVA collects and protects personal data.", "keywords": ""},
        "_meta": {"type": "website", "changefreq": "yearly", "priority": "0.3"},
    },
    "/cookies": {
        "uk": {"title": "Політика Cookies", "description": "Як ECO.NOVA використовує файли cookie.", "keywords": ""},
        "en": {"title": "Cookies Policy", "description": "How ECO.NOVA uses cookies.", "keywords": ""},
        "_meta": {"type": "website", "changefreq": "yearly", "priority": "0.3"},
    },
}


def _crumbs(path: str, lang: str, title: str, origin: str) -> List[Dict[str, str]]:
    home = "Головна" if lang == "uk" else "Home"
    items = [{"name": home, "url": f"{origin}/"}]
    if path != "/":
        items.append({"name": title, "url": f"{origin}{path}"})
    return items


def base_for(path: str) -> Optional[Dict[str, Any]]:
    return REGISTRY.get(path)


def resolve_static(path: str, lang: str, origin: str) -> Optional[Dict[str, Any]]:
    # Admin per-route override takes precedence over the static registry.
    # Falls through if the admin document is missing or has no fields set for this lang.
    override = None
    try:
        from . import config as _seo_config
        override = _seo_config.page_override(path)
    except Exception:
        override = None

    entry = REGISTRY.get(path)
    if not entry and not override:
        return None

    # Base values from static registry (defaults).
    if entry:
        loc = entry.get(lang) or entry.get("uk") or {}
        meta = entry.get("_meta", {})
        base_title = loc.get("title", "")
        base_desc = loc.get("description", "")
        base_kw = loc.get("keywords", "")
        base_type = meta.get("type", "website")
        base_app = bool(meta.get("app"))
    else:
        base_title = base_desc = base_kw = ""
        base_type = "website"
        base_app = False

    # Apply override (per-lang first, then generic fallbacks).
    if override:
        lang_key = f"_{lang}" if lang in ("uk", "en") else "_uk"
        by_lang = override.get(lang_key) or {}
        # Prefer per-lang, then generic keys, then base.
        title = (by_lang.get("title") or override.get("title") or base_title).strip()
        description = (by_lang.get("description") or override.get("description") or base_desc).strip()
        keywords = (by_lang.get("keywords") or override.get("keywords") or base_kw).strip()
        base_type = override.get("schema_type") or override.get("type") or base_type
    else:
        title = base_title
        description = base_desc
        keywords = base_kw

    if not title:
        return None

    return {
        "title": title,
        "full_title": f"{title} · {TITLE_SUFFIX.get(lang, TITLE_SUFFIX['uk'])}",
        "description": description,
        "keywords": keywords,
        "type": base_type,
        "is_app": base_app,
        "breadcrumbs": _crumbs(path, lang, title, origin),
        "lang": lang,
        "override": override or {},
    }
