"""
Canonical URL builder.

Produces a clean, self-referencing canonical:
  * forces the configured origin (scheme + host)
  * drops tracking / session / preview query params
  * keeps only meaningful params (e.g. ?lang=en, pagination) sorted
  * removes URL fragments and duplicate slashes
  * never emits a trailing slash except for the root
"""
from __future__ import annotations

from urllib.parse import urlencode, urlsplit, parse_qsl

from .origin import get_origin

# Query params that must never appear in a canonical URL.
_STRIP_PREFIXES = ("utm_", "pk_", "mtm_", "_hs")
_STRIP_EXACT = {
    "fbclid", "gclid", "gclsrc", "dclid", "wbraid", "gbraid", "msclkid",
    "yclid", "twclid", "igshid", "mc_cid", "mc_eid", "vero_id", "oly_anon_id",
    "ref", "referrer", "source", "session", "sessionid", "sid", "sessid",
    "preview", "preview_token", "draft", "nocache", "_", "cache", "v",
    "fbadid", "ad_id", "campaign", "spm",
}
# Params that ARE allowed to stay (they change the indexable content).
_KEEP = {"lang", "page", "category", "q"}


def clean_query(query: str) -> str:
    """Return a normalized, tracker-free query string (may be empty)."""
    pairs = parse_qsl(query or "", keep_blank_values=False)
    kept = []
    for k, val in pairs:
        key = (k or "").strip().lower()
        if not key:
            continue
        if key in _KEEP:
            kept.append((key, val))
            continue
        if key in _STRIP_EXACT:
            continue
        if any(key.startswith(p) for p in _STRIP_PREFIXES):
            continue
        # Unknown params: drop by default (safer for canonical hygiene).
    kept.sort(key=lambda kv: kv[0])
    return urlencode(kept)


def _clean_path(path: str) -> str:
    if not path:
        return "/"
    # collapse duplicate slashes
    while "//" in path:
        path = path.replace("//", "/")
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def canonical_url(path_or_url: str, request=None, keep_query: bool = True) -> str:
    """Build a clean canonical URL from a path or full URL."""
    origin = get_origin(request)
    parts = urlsplit(path_or_url or "/")
    path = _clean_path(parts.path)
    q = clean_query(parts.query) if keep_query else ""
    url = f"{origin}{path}"
    if q:
        url = f"{url}?{q}"
    return url
