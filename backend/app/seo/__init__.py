"""
ECO.NOVA — centralized, production-grade SEO engine.

Single source of truth for every SEO surface so the site stays consistent
and free of the legacy BiBi Cars artifacts:

  origin.py      → resolve the canonical public origin + environment
  canonical.py   → build clean canonical URLs (strip trackers/session/preview)
  hreflang.py    → uk / en / x-default alternates (no loops)
  robots.py      → environment-aware robots.txt (prod indexable, others not)
  sitemap.py     → sitemap index + typed sitemaps (pages/catalog/blog/images)
  schema.py      → JSON-LD builders (Organization, WebSite, Breadcrumb, ...)
  metadata.py    → per-route metadata registry (title/description/OG/...)

Nothing here contains hardcoded domains: everything derives from
SEO_PUBLIC_ORIGIN (env) or the request Host, so switching to the real
production domain is a one-line env change.
"""
from .origin import get_origin, get_environment, is_production  # noqa: F401
from .canonical import canonical_url, clean_query  # noqa: F401
from .hreflang import hreflang_alternates, LANGS  # noqa: F401

__all__ = [
    "get_origin",
    "get_environment",
    "is_production",
    "canonical_url",
    "clean_query",
    "hreflang_alternates",
    "LANGS",
]
