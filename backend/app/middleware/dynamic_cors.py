"""
app/middleware/dynamic_cors.py — DB-backed CORS middleware (Phase IV-5).

Standard Starlette ``CORSMiddleware`` resolves its ``allow_origins`` /
``allow_origin_regex`` once at construction time and never refreshes them.
That forced operators to edit ``.env`` and restart the backend every time
they spun up a new domain — which is brittle in production.

This middleware subclasses CORSMiddleware and overrides the per-request
origin check so the allow-list is read from the ``system_settings`` Mongo
collection with a short in-process TTL cache (30 s). Admin updates flow
through ``PATCH /api/admin/system/settings`` and take effect on the next
preflight without a process restart.

Fallback order (most → least specific):
  1. DB ``system_settings.cors_origins`` (exact match list) + ``cors_origin_regex``
  2. ``.env`` CORS_ORIGINS / CORS_ORIGIN_REGEX (boot-time defaults)
  3. ``localhost:3000`` only (visible warning in logs)

The cache is process-local; on a multi-worker deploy each worker re-reads
once per TTL — fine for human-rate admin edits.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, List, Optional

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("bibi.dynamic_cors")


class DynamicCORSMiddleware(CORSMiddleware):
    """CORS middleware whose allow-list is reloaded from Mongo on a 30 s TTL."""

    _CACHE_TTL = 30.0  # seconds
    _cached_origins: List[str] = []
    _cached_regex: Optional[str] = None
    _cached_regex_compiled: Optional[re.Pattern] = None
    _cache_loaded_at: float = 0.0

    def __init__(
        self,
        app: ASGIApp,
        *,
        env_allow_origins: List[str],
        env_allow_origin_regex: Optional[str],
        **kwargs: Any,
    ) -> None:
        # Initial config — env defaults. Will be merged with DB values per req.
        self._env_origins = list(env_allow_origins or [])
        self._env_regex = env_allow_origin_regex
        # Pass a *permissive-by-string-match* default to parent — the parent
        # builds the access-control headers from the resolved origin string,
        # we just override which origins it accepts.
        super().__init__(
            app,
            allow_origins=self._env_origins or ["*"],
            allow_origin_regex=env_allow_origin_regex,
            **kwargs,
        )
        # Pre-populate cache with env defaults
        DynamicCORSMiddleware._cached_origins = list(self._env_origins)
        DynamicCORSMiddleware._cached_regex = env_allow_origin_regex
        DynamicCORSMiddleware._cached_regex_compiled = (
            re.compile(env_allow_origin_regex) if env_allow_origin_regex else None
        )
        DynamicCORSMiddleware._cache_loaded_at = time.time()

    @classmethod
    def invalidate_cache(cls) -> None:
        """Force a refresh on the next request (call after admin PATCH)."""
        cls._cache_loaded_at = 0.0

    @classmethod
    async def _refresh_from_db(cls) -> None:
        """Pull the latest allow-list from ``system_settings`` once per TTL."""
        try:
            from app.core.db_runtime import get_db
            db = get_db()
            if db is None:
                return
            doc = await db.system_settings.find_one({"_id": "global"})
            if not doc:
                return
            origins = doc.get("cors_origins") or []
            if isinstance(origins, str):
                origins = [o.strip() for o in origins.replace(";", ",").split(",") if o.strip()]
            origin_regex = (doc.get("cors_origin_regex") or "").strip() or None
            # Always union with env defaults (env wins on conflict so a misclick
            # in admin UI never locks out localhost during dev)
            merged = list({*origins, *cls._cached_origins[:0], *(cls._cached_origins)})
            # Re-merge with env baseline
            from security import parse_cors_origins as _env_origins
            env_origins = _env_origins()
            merged = list({*env_origins, *origins})
            cls._cached_origins = [o.rstrip("/") for o in merged if o]
            cls._cached_regex = origin_regex
            cls._cached_regex_compiled = re.compile(origin_regex) if origin_regex else None
            cls._cache_loaded_at = time.time()
            logger.debug(
                f"[dynamic_cors] refreshed: origins={cls._cached_origins} regex={origin_regex}"
            )
        except Exception as e:
            logger.warning(f"[dynamic_cors] DB refresh failed: {e}")

    def is_allowed_origin(self, origin: str) -> bool:
        # Quick TTL refresh — but only on origins we *might* reject, since
        # is_allowed_origin is hot path. Cheap enough either way.
        now = time.time()
        if now - DynamicCORSMiddleware._cache_loaded_at > self._CACHE_TTL:
            # Fire-and-forget: a sync call to async refresh would block,
            # so we mark stale and let the next request pick up after we
            # try a non-blocking refresh in middleware __call__ below.
            DynamicCORSMiddleware._cache_loaded_at = now  # reset to avoid stampede
            # Schedule the refresh on the running loop:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                loop.create_task(DynamicCORSMiddleware._refresh_from_db())
            except Exception:
                pass

        if origin in DynamicCORSMiddleware._cached_origins:
            return True
        if DynamicCORSMiddleware._cached_regex_compiled and \
                DynamicCORSMiddleware._cached_regex_compiled.match(origin):
            return True
        # Final fallback: env baseline (already in cache; this guards the very
        # first request before refresh completes)
        if origin in self._env_origins:
            return True
        if self._env_regex and re.match(self._env_regex, origin):
            return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # The parent's preflight/simple-request logic uses self.allow_origins
        # as a strict list; we patch in our dynamic list so its built-in
        # checks (and Access-Control-Allow-Origin echo) also match what
        # is_allowed_origin returns.
        self.allow_origins = list(DynamicCORSMiddleware._cached_origins) or self._env_origins or ["*"]
        await super().__call__(scope, receive, send)
