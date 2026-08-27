"""
auth_password — staff password lifecycle (change + policy descriptor)
======================================================================

Endpoints:
  GET  /api/auth/password-policy       — public rules snapshot for live UI meter
  POST /api/auth/change-password       — authenticated user changes own password

Notes:
  * `/api/auth/change-password` used to be a stub returning `{success:True}` in
    server.py — replaced here by a proper implementation.
  * Applies the new password policy from app.services.password_policy.
  * Verifies the current password before updating.
  * Hashes the new password using security.hash_password (bcrypt).
  * Writes a login_audit record (event=password_change, method=manual).
  * On manager role the daily-reset boundary still applies — but the JWT the
    user is using stays valid until the next 12:00 Europe/Sofia.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from security import (
    get_current_user,
    hash_password,
    verify_password,
)
from app.services.password_policy import (
    assert_password_valid,
    check_password,
    policy_descriptor,
)

logger = logging.getLogger("bibi.auth_password")

router = APIRouter(prefix="/api/auth", tags=["auth-password"])


def _db():
    from app.core.db_runtime import get_db
    return get_db()


def _client_ip(req: Request):
    return (req.client.host if req.client else None) or req.headers.get("x-forwarded-for")


@router.get("/password-policy")
async def get_password_policy() -> Dict[str, Any]:
    """Public — frontend uses this to render the live policy meter on
    sign-up / change-password screens. No auth required."""
    return policy_descriptor()


@router.post("/password/validate")
async def validate_password(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Public — return per-rule booleans without changing anything.
    Useful for live UI even outside of a logged-in flow."""
    pwd = (payload or {}).get("password") or ""
    res = check_password(pwd)
    return {"ok": res.ok, "failures": res.failures, "checks": res.checks}


@router.post("/change-password")
async def change_password(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Authenticated staff member changes their own password.

    Body: { current_password: str, new_password: str }

    Behaviour:
      1. Validate that the user exists in `db.staff`.
      2. Verify ``current_password`` against the stored bcrypt hash.
      3. Enforce the staff password policy on ``new_password``.
      4. Hash + persist. Bump ``password_changed_at``.
      5. Write an audit event so admins see the change in /admin/login-audit.
    """
    current_pwd = (payload or {}).get("current_password") or ""
    new_pwd = (payload or {}).get("new_password") or ""

    if not current_pwd or not new_pwd:
        raise HTTPException(status_code=400, detail="current_password and new_password are required")
    if current_pwd == new_pwd:
        raise HTTPException(status_code=400, detail="New password must differ from the current one")

    db = _db()
    user_id = user.get("id") or user.get("_id")
    email = (user.get("email") or "").strip().lower()
    if not email and not user_id:
        raise HTTPException(status_code=401, detail="cannot resolve current user")

    # 1) Find the staff row by id-or-email.
    staff = None
    if user_id:
        staff = await db.staff.find_one({"$or": [{"id": user_id}, {"_id": user_id}]})
    if not staff and email:
        staff = await db.staff.find_one({"email": email})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff account not found")

    # 2) Verify current password.
    hashed = staff.get("password_hash") or staff.get("hashed_password") or staff.get("password")
    if not hashed or not verify_password(current_pwd, hashed):
        # Audit the failed attempt (do NOT leak which step failed).
        try:
            from app.services.auth_policy import AuthPolicyService
            await AuthPolicyService(db).write_event(
                user=user, event="password_change", method="manual", success=False,
                ip=_client_ip(request), user_agent=request.headers.get("user-agent"),
                details={"reason": "invalid_current_password"},
            )
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # 3) Enforce policy on the new password.
    try:
        assert_password_valid(new_pwd)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 4) Hash + persist.
    from datetime import datetime, timezone
    try:
        new_hash = hash_password(new_pwd)
    except Exception as e:
        logger.error(f"[change-password] hash failed: {e}")
        raise HTTPException(status_code=500, detail="hashing failed")

    await db.staff.update_one(
        {"_id": staff.get("_id")},
        {
            "$set": {
                "password_hash": new_hash,
                # Some legacy rows used different field names — null them so
                # verify_password() picks up the new canonical field.
                "hashed_password": new_hash,
                "password": new_hash,
                "password_changed_at": datetime.now(timezone.utc),
            },
            # Session revocation: bump the token epoch so every JWT issued
            # before this change (carrying the old tokenVersion claim) is
            # rejected by require_user / the access gate → other devices/
            # sessions are forced to re-login.
            "$inc": {"tokenVersion": 1},
        },
    )

    # Keep the CURRENT session alive: mint a fresh JWT that carries the new
    # tokenVersion so the device that just changed the password is not logged
    # out. The frontend stores this returned access_token.
    new_token = None
    try:
        from security import create_jwt
        new_version = int(staff.get("tokenVersion") or 0) + 1
        refreshed_user = {
            "id": staff.get("id") or staff.get("_id"),
            "email": staff.get("email"),
            "name": staff.get("name") or staff.get("email"),
            "role": (staff.get("role") or "manager").lower(),
            "managerId": staff.get("id") or staff.get("_id"),
            "tokenVersion": new_version,
        }
        new_token = create_jwt(refreshed_user)
    except Exception as _e:
        logger.warning(f"[change-password] could not mint refreshed token: {_e}")

    # 5) Audit success.
    try:
        from app.services.auth_policy import AuthPolicyService
        await AuthPolicyService(db).write_event(
            user=user, event="password_change", method="manual", success=True,
            ip=_client_ip(request), user_agent=request.headers.get("user-agent"),
        )
    except Exception as _e:
        logger.warning(f"[change-password] audit failed: {_e}")

    return {"success": True, "message": "Password updated", "access_token": new_token}
