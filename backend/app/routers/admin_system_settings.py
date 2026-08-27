"""
admin_system_settings.py — /api/admin/system/settings (Phase IV-5).

One-stop admin control panel for runtime settings that previously required
editing ``.env`` and restarting the backend:

  • production_domain   — the canonical site URL ('https://bibi.cars'). Used
                          to render webhook URLs in the UI and OG-tags.
  • cors_origins        — exact-match allowlist for browser-side CORS.
  • cors_origin_regex   — optional wildcard regex (e.g. preview subdomains).
  • allow_subdomains    — when true, auto-derives a wildcard regex from the
                          production_domain (so *.bibi.cars also works).

Storage: a single ``system_settings`` Mongo document with ``_id="global"``.
Changes invalidate the ``DynamicCORSMiddleware`` cache so they take effect
on the very next preflight (no restart needed).

Endpoints:
  GET  /api/admin/system/settings          → current settings + env baseline
  PATCH /api/admin/system/settings         → upsert one or more fields
  POST  /api/admin/system/settings/jwt/rotate → generate fresh JWT_SECRET
                                              (admin must accept loss-of-sessions)

All endpoints require ``require_master_admin`` because misconfiguring CORS
can lock the admin team out of their own UI; we want a single, audited
chokepoint for these changes.
"""
from __future__ import annotations

import logging
import secrets
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException

from security import (
    parse_cors_origins,
    parse_cors_origin_regex,
    require_master_admin,
)

logger = logging.getLogger("bibi.admin_system_settings")

router = APIRouter(prefix="/api/admin/system", tags=["admin-system"])

DOC_ID = "global"
DEFAULT_DOC: Dict[str, Any] = {
    "_id": DOC_ID,
    "production_domain": "",
    "cors_origins": [],
    "cors_origin_regex": None,
    "allow_subdomains": False,
    "updated_at": None,
    "updated_by": None,
}


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _normalize_origin(o: str) -> str:
    """Strip trailing slash + lowercase scheme."""
    o = (o or "").strip().rstrip("/")
    if "://" in o:
        scheme, rest = o.split("://", 1)
        o = f"{scheme.lower()}://{rest}"
    return o


def _derive_subdomain_regex(production_domain: str) -> Optional[str]:
    """Given ``https://bibi.cars``, return ``^https?://[^.]+\\.bibi\\.cars$``.

    Used when ``allow_subdomains=true`` so admins don't need to type a regex.
    """
    if not production_domain:
        return None
    try:
        parsed = urlparse(production_domain)
        host = parsed.hostname or ""
        if not host:
            return None
        # Strip leading 'www.' so the regex covers it too
        if host.startswith("www."):
            host = host[4:]
        escaped = re.escape(host)
        # Allow https/http both, with arbitrary 1-level subdomain prefix
        return rf"^https?://([^.]+\.)?{escaped}$"
    except Exception:
        return None


@router.get("/settings", dependencies=[Depends(require_master_admin)])
async def get_system_settings():
    """Return current settings + env baseline so the UI can show what's
    coming from .env (read-only) vs. DB (editable)."""
    db = _db()
    doc = await db.system_settings.find_one({"_id": DOC_ID}) or {}
    env_origins = parse_cors_origins()
    env_regex = parse_cors_origin_regex()

    return {
        "settings": {
            "production_domain": doc.get("production_domain", ""),
            "cors_origins": doc.get("cors_origins", []),
            "cors_origin_regex": doc.get("cors_origin_regex"),
            "allow_subdomains": bool(doc.get("allow_subdomains", False)),
            "updated_at": (
                doc["updated_at"].isoformat()
                if doc.get("updated_at") and hasattr(doc["updated_at"], "isoformat")
                else doc.get("updated_at")
            ),
            "updated_by": doc.get("updated_by"),
        },
        "env_baseline": {
            "cors_origins": env_origins,
            "cors_origin_regex": env_regex,
            "note": "These come from the .env file and act as a baseline; admin entries are merged on top.",
        },
        # Helpful pre-computed URLs the UI can copy/paste.
        # These are the *integration links* admins paste into 3rd-party
        # dashboards (Ringostat, Stripe, Resend) or hand to web devs.
        "computed": {
            "site_origin": doc.get("production_domain") or None,
            "ringostat_webhook_url": (
                f"{doc.get('production_domain', '').rstrip('/')}/api/integrations/ringostat/webhook"
                if doc.get("production_domain") else None
            ),
            "stripe_webhook_url": (
                f"{doc.get('production_domain', '').rstrip('/')}/api/payments/stripe/webhook"
                if doc.get("production_domain") else None
            ),
            "resend_webhook_url": (
                f"{doc.get('production_domain', '').rstrip('/')}/api/integrations/resend/webhook"
                if doc.get("production_domain") else None
            ),
            "site_tracker_url": (
                f"{doc.get('production_domain', '').rstrip('/')}/api/v1/site-activity/tracker.js"
                if doc.get("production_domain") else None
            ),
        },
    }


@router.patch("/settings", dependencies=[Depends(require_master_admin)])
async def update_system_settings(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    """Upsert one or more system settings.

    Body fields (all optional):
      - ``production_domain`` (str)   — e.g. ``https://bibi.cars``
      - ``cors_origins`` (list[str] | csv)
      - ``cors_origin_regex`` (str | null)
      - ``allow_subdomains`` (bool)   — derive a wildcard regex from production_domain

    Returns the updated settings (same shape as GET).
    """
    db = _db()
    patch: Dict[str, Any] = {}

    if "production_domain" in data:
        pd = _normalize_origin(str(data["production_domain"] or ""))
        if pd and not pd.startswith(("http://", "https://")):
            pd = f"https://{pd}"
        patch["production_domain"] = pd

    if "cors_origins" in data:
        origins_in = data["cors_origins"]
        if isinstance(origins_in, str):
            origins_in = [o.strip() for o in origins_in.replace(";", ",").split(",") if o.strip()]
        elif isinstance(origins_in, list):
            origins_in = [str(o).strip() for o in origins_in if str(o).strip()]
        else:
            origins_in = []
        patch["cors_origins"] = [_normalize_origin(o) for o in origins_in if _normalize_origin(o)]

    if "cors_origin_regex" in data:
        rx = (data["cors_origin_regex"] or "").strip() or None
        if rx:
            # Validate the regex compiles before saving
            try:
                re.compile(rx)
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"Invalid regex: {e}")
        patch["cors_origin_regex"] = rx

    if "allow_subdomains" in data:
        patch["allow_subdomains"] = bool(data["allow_subdomains"])

    # If allow_subdomains is enabled and we have a production_domain (either
    # in the patch or already saved), auto-derive the regex.
    if patch.get("allow_subdomains") or (
        "allow_subdomains" not in data
        and (await db.system_settings.find_one({"_id": DOC_ID}) or {}).get("allow_subdomains")
    ):
        existing = await db.system_settings.find_one({"_id": DOC_ID}) or {}
        prod = patch.get("production_domain") or existing.get("production_domain") or ""
        derived = _derive_subdomain_regex(prod)
        if derived and not patch.get("cors_origin_regex"):
            patch["cors_origin_regex"] = derived

    # ── Auto-add production_domain into cors_origins ──────────────────
    # Admin should not have to type the same URL twice. If they save a
    # production_domain we make sure it appears in cors_origins (both the
    # bare host and the `www.` variant), so the browser can reach the
    # backend from that origin without any extra configuration step.
    existing_doc = await db.system_settings.find_one({"_id": DOC_ID}) or {}
    desired_prod = patch.get("production_domain", existing_doc.get("production_domain") or "")
    if desired_prod:
        merged = list(patch.get("cors_origins", existing_doc.get("cors_origins") or []))
        candidates = [desired_prod]
        try:
            parsed = urlparse(desired_prod)
            host = parsed.hostname or ""
            scheme = parsed.scheme or "https"
            if host:
                if host.startswith("www."):
                    candidates.append(f"{scheme}://{host[4:]}")
                else:
                    candidates.append(f"{scheme}://www.{host}")
        except Exception:
            pass
        for c in candidates:
            c_norm = _normalize_origin(c)
            if c_norm and c_norm not in merged:
                merged.append(c_norm)
        patch["cors_origins"] = merged

    patch["updated_at"] = datetime.now(timezone.utc)
    patch["updated_by"] = (current_user or {}).get("id") or (current_user or {}).get("_id")

    await db.system_settings.update_one(
        {"_id": DOC_ID},
        {"$set": patch, "$setOnInsert": {"_id": DOC_ID}},
        upsert=True,
    )

    # Invalidate the live CORS cache so changes take effect on next request
    try:
        from app.middleware.dynamic_cors import DynamicCORSMiddleware
        DynamicCORSMiddleware.invalidate_cache()
        await DynamicCORSMiddleware._refresh_from_db()
    except Exception as e:
        logger.warning(f"[admin/system/settings] cache invalidate failed: {e}")

    return await get_system_settings()


@router.post("/settings/jwt/rotate", dependencies=[Depends(require_master_admin)])
async def rotate_jwt_secret(
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_master_admin),
):
    """Generate a fresh JWT_SECRET and persist it to ``system_settings``.

    ⚠️  This invalidates every existing token immediately — all logged-in
    users (including you) will need to log back in.

    Body:
      - ``confirm`` (bool) — must be ``true`` to proceed (safety guard).

    The new secret is written to the SHARED Mongo ``settings`` document
    (``_id="jwt_secret"``) which ``security.bootstrap_jwt_secret()`` reads on
    startup, so every replica converges on it after a restart/redeploy. It is
    also applied to the serving pod's in-memory secret immediately. If
    ``JWT_SECRET`` is pinned via a deployment ENV var, that takes precedence and
    the response explains how to apply the rotation.
    """
    if not data.get("confirm"):
        raise HTTPException(
            status_code=400,
            detail="Confirm=true required: rotating JWT will log out everyone (including you).",
        )

    new_secret = secrets.token_urlsafe(48)  # 64 chars, URL-safe
    db = _db()

    # 1) Persist the new secret to the SHARED Mongo source-of-truth that
    #    security.bootstrap_jwt_secret() reads on startup (settings._id=
    #    "jwt_secret"). This is what makes rotation MULTI-REPLICA SAFE: every
    #    pod re-reads the same value on its next boot instead of diverging.
    await db.settings.update_one(
        {"_id": "jwt_secret"},
        {"$set": {
            "value": new_secret,
            "rotated_at": datetime.now(timezone.utc).isoformat(),
            "rotated_by": (current_user or {}).get("id"),
            "note": "rotated via admin endpoint (set JWT_SECRET env to override)",
        }},
        upsert=True,
    )

    # 2) Audit trail in system_settings.
    await db.system_settings.update_one(
        {"_id": DOC_ID},
        {
            "$set": {
                "jwt_secret_rotated_at": datetime.now(timezone.utc),
                "jwt_secret_rotated_by": (current_user or {}).get("id"),
            },
            "$push": {
                "jwt_rotation_history": {
                    "ts": datetime.now(timezone.utc),
                    "by": (current_user or {}).get("id"),
                }
            },
            "$setOnInsert": {"_id": DOC_ID},
        },
        upsert=True,
    )

    # 3) Apply to THIS pod's live in-memory secret immediately so the rotation
    #    takes effect without waiting for a restart on the serving pod. Other
    #    replicas pick up the new shared secret from Mongo on their next boot.
    env_override = False
    try:
        import security as _security_mod
        if _security_mod.JWT_SECRET_SOURCE == "env":
            # ENV wins over Mongo by design — rotating here will NOT take effect
            # until the operator updates the JWT_SECRET deployment env var.
            env_override = True
        else:
            _security_mod.JWT_SECRET = new_secret
            _security_mod.JWT_SECRET_SOURCE = "mongo"
    except Exception as e:
        logger.warning(f"[admin/system/settings] live secret swap failed: {e}")

    if env_override:
        return {
            "success": True,
            "message": (
                "A new JWT secret was stored in MongoDB, but JWT_SECRET is currently "
                "pinned via a deployment ENV variable which takes precedence. To apply "
                "the rotation, update the JWT_SECRET env var in your deployment settings "
                "to the new value and redeploy."
            ),
            "new_secret": new_secret,
            "rotated_at": datetime.now(timezone.utc).isoformat(),
            "warning": "Rotation is staged in DB but ENV JWT_SECRET overrides it until updated.",
            "source": "env_pinned",
        }

    return {
        "success": True,
        "message": (
            "JWT_SECRET rotated and stored in the shared Mongo source. It is live on "
            "this pod now; restart/redeploy the backend so all replicas re-read it: "
            "`sudo supervisorctl restart backend`"
        ),
        "rotated_at": datetime.now(timezone.utc).isoformat(),
        "warning": "All existing JWT tokens are now invalid — everyone must log in again.",
        "source": "mongo",
    }
