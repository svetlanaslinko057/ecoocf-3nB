"""
hreflang alternates for the bilingual public site (Ukrainian primary + English).

Language is selected via the ?lang= query param so each language has a
distinct, crawlable URL:
  * uk         -> {origin}{path}            (default, no param)
  * en         -> {origin}{path}?lang=en
  * x-default  -> {origin}{path}            (points at the Ukrainian default)

Returns a list of {"hreflang": ..., "href": ...} with no self-referential
loops and reciprocal entries, ready for <link rel=alternate> or sitemap
xhtml:link tags.
"""
from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlencode, urlsplit

from .canonical import clean_query
from .origin import get_origin

LANGS = ("uk", "en")


def _base(path_or_url: str, request=None) -> tuple[str, str, dict]:
    origin = get_origin(request)
    parts = urlsplit(path_or_url or "/")
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # preserve meaningful non-lang params
    from urllib.parse import parse_qsl
    params = {k: v for k, v in parse_qsl(clean_query(parts.query)) if k != "lang"}
    return origin, path, params


def _url(origin: str, path: str, params: dict, lang: str | None) -> str:
    q = dict(params)
    if lang and lang != "uk":
        q["lang"] = lang
    qs = urlencode(sorted(q.items()))
    return f"{origin}{path}?{qs}" if qs else f"{origin}{path}"


def hreflang_alternates(path_or_url: str, request=None) -> List[Dict[str, str]]:
    origin, path, params = _base(path_or_url, request)
    out = [
        {"hreflang": "uk", "href": _url(origin, path, params, "uk")},
        {"hreflang": "en", "href": _url(origin, path, params, "en")},
        {"hreflang": "x-default", "href": _url(origin, path, params, "uk")},
    ]
    return out
