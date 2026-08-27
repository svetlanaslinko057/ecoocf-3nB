"""
Environment-aware robots.txt engine — ADMIN-DRIVEN.

  * If admin has NOT toggled `allow_indexing_in_production`, we never emit an
    indexable robots.txt no matter what environment we're on.
  * production  -> allow public pages, disallow private app/api areas,
                   advertise the sitemap index. Admin can extend/override
                   the disallow and allow lists.
  * non-prod    -> Disallow: /  (so preview/stage/test never get indexed).

No hidden directives, no cloaking. Everything (env override, disallow/allow
paths, sitemap URL, AI-crawler block) is edited from the admin panel and
takes effect on the next request without a redeploy.
"""
from __future__ import annotations

from typing import List

from .origin import get_origin, get_environment

# Hard-baked defaults — kept in code as a safety net so a fresh deploy
# without admin rules still produces a sensible robots.txt.
_DEFAULT_DISALLOW = (
    "/app",          # staff CRM workspace
    "/admin",        # staff login/console
    "/client",       # B2B client cabinet
    "/api/",         # backend API
    "/contract/",    # tokenized e-sign links
    "/*?preview=",
    "/*?draft=",
)

_DEFAULT_ALLOW = (
    "/$",
    "/waste",
    "/calculator",
    "/contacts",
    "/blog",
    "/terms",
    "/privacy",
    "/cookies",
)

# AI crawlers we block when the admin flips the switch.
_AI_CRAWLERS = ("GPTBot", "ClaudeBot", "Claude-Web", "anthropic-ai", "CCBot",
                "PerplexityBot", "Google-Extended", "Bytespider", "meta-externalagent")


def _cleanup_list(raw, fallback):
    """Normalise a stored list. Accepts list, comma/newline-separated string
    or None. Trims + de-dupes + preserves ordering."""
    if raw is None:
        return list(fallback)
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace("\r", "\n").replace(",", "\n").split("\n")]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip() for p in raw]
    else:
        parts = []
    seen: List[str] = []
    for p in parts:
        if not p:
            continue
        if p not in seen:
            seen.append(p)
    return seen or list(fallback)


def build_robots(request=None) -> str:
    # Deferred import to avoid a startup-time cycle.
    from . import config as _seo_config

    origin = get_origin(request)
    env = get_environment(request)
    rules = _seo_config.robots_config() or {}
    indexing_allowed = _seo_config.allow_indexing_in_production()

    # Sitemap URL (admin can override).
    sitemap = (rules.get("sitemap_url") or "").strip()
    if not sitemap:
        sitemap = f"{origin}/sitemap.xml" if origin else "/sitemap.xml"

    lines = [
        "# ECO.NOVA — robots.txt (generated · admin-managed)",
        f"# environment: {env}",
    ]

    # Environment override — admin can force "index / noindex" here.
    forced_mode = str(rules.get("mode") or "").strip().lower()
    #   auto      → follow env + master switch
    #   index     → force allow (only meaningful in production)
    #   noindex   → force disallow everywhere
    non_prod = env != "production"
    force_noindex = (
        forced_mode == "noindex"
        or non_prod
        or not indexing_allowed
    )

    if force_noindex:
        reason = ("admin has not enabled indexing in production"
                  if (not indexing_allowed and env == "production" and forced_mode != "noindex")
                  else ("admin forced noindex" if forced_mode == "noindex"
                        else f"environment: {env}"))
        lines += [
            f"# indexing disabled — {reason}",
            "",
            "User-agent: *",
            "Disallow: /",
            "",
            f"Sitemap: {sitemap}",
            "",
        ]
        return "\n".join(lines)

    # Production + indexing allowed.
    disallow = _cleanup_list(rules.get("disallow"), _DEFAULT_DISALLOW)
    allow = _cleanup_list(rules.get("allow"), _DEFAULT_ALLOW)

    lines += ["", "User-agent: *"]
    for p in disallow:
        lines.append(f"Disallow: {p}")
    for a in allow:
        lines.append(f"Allow: {a}")

    # Reputable crawler carve-outs.
    lines += ["", "User-agent: Googlebot"]
    for p in disallow:
        # Only keep private-area disallows for these named agents.
        if p.startswith("/app") or p.startswith("/admin") or p.startswith("/client") or p.startswith("/api"):
            lines.append(f"Disallow: {p}")
    lines += ["", "User-agent: Bingbot"]
    for p in disallow:
        if p.startswith("/app") or p.startswith("/admin") or p.startswith("/client") or p.startswith("/api"):
            lines.append(f"Disallow: {p}")

    # AI-crawler block (from seo_settings, master switch).
    try:
        block_ai = bool((_seo_config._CACHE.get("data") or {}).get("block_ai_crawlers"))
    except Exception:
        block_ai = False
    if block_ai:
        lines += ["", "# AI crawler block (admin-enabled)"]
        for ua in _AI_CRAWLERS:
            lines += [f"User-agent: {ua}", "Disallow: /", ""]

    lines += ["", f"Sitemap: {sitemap}", ""]
    return "\n".join(lines)
