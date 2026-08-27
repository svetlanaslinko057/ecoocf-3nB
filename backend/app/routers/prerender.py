"""
/api/prerender — public + admin endpoints for the Phase C prerender pipeline.

Public (no auth):
  GET  /api/prerender/render?path=/waste&lang=uk   → text/html
       Optional headers: X-Bot-UA, User-Agent (used only for logging /
       automatic bot classification when called via CDN worker).
  GET  /api/prerender/health                         → JSON
       Bot directory, cache stats, allowed routes.

Admin (require_master_admin):
  GET  /api/prerender/admin/metrics                  → JSON stats
  GET  /api/prerender/admin/routes                   → JSON allow-list
  POST /api/prerender/admin/warm                     → pre-render every route
  POST /api/prerender/admin/purge                    → drop Mongo cache
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from security import require_master_admin
from app.seo import prerender as _pr
from app.seo import bot_detector

logger = logging.getLogger("bibi.prerender_router")
router = APIRouter(prefix="/api/prerender", tags=["prerender"])


# ─── PUBLIC ────────────────────────────────────────────────────────────
@router.get("/render", response_class=HTMLResponse)
async def render_route(
    request: Request,
    path: str = Query("/", description="Public route to prerender, e.g. /waste"),
    lang: str = Query("uk"),
    force: int = Query(0, description="1 = bypass all caches"),
):
    """Return the fully-rendered HTML for `path`.

    Callable by CDN edge workers / nginx rules that identify a bot User-Agent
    and want to serve prerendered HTML instead of the SPA index.html.
    """
    try:
        html, info = await _pr.render(request, path=path, lang=lang, force=bool(force))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:  # pragma: no cover — safety net
        logger.exception("prerender failed for %s: %s", path, e)
        raise HTTPException(500, "Prerender engine error")

    # Cache hint for CDN + informational headers.
    headers = {
        "X-Prerender-Cache": info.get("cache") or "miss",
        "X-Prerender-Path": info.get("path") or path,
        "X-Prerender-Lang": info.get("lang") or lang,
        # 5-min shared cache; bots re-check frequently anyway.
        "Cache-Control": "public, max-age=300, s-maxage=300",
    }
    # If the caller sent a User-Agent that matches a known bot, log it (helps
    # diagnose which bots are actually consuming the prerender).
    ua = request.headers.get("user-agent", "")
    bot = bot_detector.which_bot(ua)
    if bot:
        headers["X-Prerender-Bot"] = bot.name
        _pr._METRICS.setdefault("bot_hits", {}).setdefault(bot.name, 0)
        _pr._METRICS["bot_hits"][bot.name] += 1

    return HTMLResponse(content=html, headers=headers)


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Public health / capability endpoint. No secrets, no PII."""
    return {
        "engine": "app.seo.prerender",
        "static_routes":  list(_pr.STATIC_ROUTES),
        "dynamic_routes": ["/waste-code/:slug", "/waste/category/:key", "/blog/:slug"],
        "private_prefixes_refused": ["/app", "/admin", "/client", "/api", "/oauth", "/contract", "/portal", "/manage"],
        "bots_recognised": len(bot_detector.bot_directory()),
        "cache_entries_memory": len(_pr._MEM_CACHE),
        "renders": _pr._METRICS.get("renders", 0),
    }


@router.get("/detect")
async def detect(request: Request) -> Dict[str, Any]:
    """Diagnostic: report whether the CURRENT User-Agent is recognised as a
    bot. Handy for testing curl -A '...' vs a real browser."""
    ua = request.headers.get("user-agent", "")
    bot = bot_detector.which_bot(ua)
    return {
        "user_agent": ua,
        "is_bot": bool(bot),
        "bot": {"name": bot.name, "category": bot.category} if bot else None,
    }


# ─── ADMIN ─────────────────────────────────────────────────────────────
@router.get("/admin/metrics", dependencies=[Depends(require_master_admin)])
async def admin_metrics() -> Dict[str, Any]:
    m = _pr.metrics()
    return {
        "metrics": m,
        "bots_directory": bot_detector.bot_directory(),
    }


@router.get("/admin/routes", dependencies=[Depends(require_master_admin)])
async def admin_routes() -> Dict[str, Any]:
    return {
        "static":  list(_pr.STATIC_ROUTES),
        "dynamic": [
            {"pattern": "/waste-code/:slug",     "example": "/waste-code/hg-001"},
            {"pattern": "/waste/category/:key",  "example": "/waste/category/oils"},
            {"pattern": "/blog/:slug",           "example": "/blog/hello-world"},
        ],
        "private_prefixes": ["/app", "/admin", "/client", "/api", "/oauth", "/contract", "/portal", "/manage"],
    }


@router.post("/admin/warm", dependencies=[Depends(require_master_admin)])
async def admin_warm(request: Request, langs: str = Query("uk,en")):
    """Pre-render every static route (uk+en) so the first bot hit is fast."""
    _lang_list: List[str] = [x.strip() for x in (langs or "uk").split(",") if x.strip()]
    results: List[Dict[str, Any]] = []
    for path in _pr.STATIC_ROUTES:
        for lang in _lang_list:
            try:
                _, info = await _pr.render(request, path=path, lang=lang, force=True)
                results.append({"path": path, "lang": lang, "ok": True, **info})
            except Exception as e:
                results.append({"path": path, "lang": lang, "ok": False, "error": str(e)})
    ok = sum(1 for r in results if r.get("ok"))
    return {"success": True, "warmed": ok, "total": len(results), "results": results}


@router.post("/admin/purge", dependencies=[Depends(require_master_admin)])
async def admin_purge() -> Dict[str, Any]:
    deleted = await _pr.purge_mongo_cache()
    return {"success": True, "mongo_deleted": deleted}


__all__ = ["router"]
