"""
auth_extra — расширенные endpoints входа (TOTP / email-OTP / logout)
=================================================================

Mонтируется РЯДОМ с базовым /api/auth/login (который в server.py).
Ничего в server.py не ломаем — логин продолжает выдавать JWT,
политика «челлендж вместо токена» реализована хуком (патч в server.py
вызывает наш сервис и может вернуть challenge).

Endpoints:
  POST /api/auth/2fa/verify          — админ TOTP challenge
  POST /api/auth/email-otp/request   — (вызывается автоматически при login тимлида,
                                       но доступен для resend по challenge_token)
  POST /api/auth/email-otp/verify    — тимлид вводит OTP
  POST /api/auth/logout              — запись logout-события в audit
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request, Depends

from security import create_jwt, get_current_user_optional

logger = logging.getLogger("bibi.auth_extra")

router = APIRouter(prefix="/api/auth", tags=["auth-extra"])


def _svc():
    from app.core.db_runtime import get_db
    from app.services.auth_policy import AuthPolicyService
    return AuthPolicyService(get_db())


def _db():
    from app.core.db_runtime import get_db
    return get_db()


async def _resolve_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    db = _db()
    d = await db.staff.find_one({"$or": [{"id": user_id}, {"_id": user_id}]})
    if not d:
        return None
    return {
        "id":       d.get("id") or d.get("_id"),
        "email":    d.get("email"),
        "name":     d.get("name") or d.get("email"),
        "role":     (d.get("role") or "manager").lower(),
        "managerId": d.get("id") or d.get("_id"),
        "tokenVersion": int(d.get("tokenVersion") or 0),
    }


async def _resolve_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    if not email:
        return None
    db = _db()
    d = await db.staff.find_one({"email": email.strip().lower()})
    if not d:
        return None
    return {
        "id":       d.get("id") or d.get("_id"),
        "email":    d.get("email"),
        "name":     d.get("name") or d.get("email"),
        "role":     (d.get("role") or "manager").lower(),
        "managerId": d.get("id") or d.get("_id"),
        "tokenVersion": int(d.get("tokenVersion") or 0),
    }


def _client_ip(req: Request) -> Optional[str]:
    return (req.client.host if req.client else None) or req.headers.get("x-forwarded-for")


# ----------------------------------------------------------------------- TOTP

@router.post("/2fa/verify")
async def auth_2fa_verify(
    payload: Dict[str, Any] = Body(...),
    request: Request = None,
):
    """Second step for ADMIN role: verify Google Authenticator TOTP.

    Body: {challenge_token, code}
      - challenge_token: a short-lived state token returned by /api/auth/login
        when the role requires TOTP. We use the user's email here because
        TOTP doesn't need a server-side state; the password step already
        proved who the user is. To keep state out of the database we
        accept ``user_id`` directly (the login response includes it).
    """
    code = str(payload.get("code") or "").strip()
    user_id = payload.get("user_id") or payload.get("userId")
    if not code or not user_id:
        raise HTTPException(status_code=400, detail="code and user_id required")
    user = await _resolve_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    svc = _svc()
    if not await svc.verify_totp(user, code):
        await svc.write_event(
            user=user, event="login", method="totp", success=False,
            ip=_client_ip(request) if request else None,
            user_agent=(request.headers.get("user-agent") if request else None),
            details={"reason": "invalid_totp"},
        )
        raise HTTPException(status_code=401, detail="Invalid TOTP code")
    token = create_jwt(user)
    await svc.write_event(
        user=user, event="login", method="totp", success=True,
        ip=_client_ip(request) if request else None,
        user_agent=(request.headers.get("user-agent") if request else None),
    )
    return {"access_token": token, "token_type": "Bearer", "user": user}


# ------------------------------------------------------------------- EMAIL-OTP (retired)
# The ``team_lead`` role has been removed from the product, so the email-OTP
# login path is no longer reachable. The endpoints are kept under the same
# URLs to keep existing clients from blowing up, but they now respond with
# HTTP 410 Gone so any caller can see the path was retired on purpose.


@router.post("/email-otp/request")
async def auth_email_otp_request(payload: Dict[str, Any] = Body(default={})):
    raise HTTPException(status_code=410, detail="email-otp login was retired together with team_lead role")


@router.post("/email-otp/verify")
async def auth_email_otp_verify(payload: Dict[str, Any] = Body(default={})):
    raise HTTPException(status_code=410, detail="email-otp login was retired together with team_lead role")


# ------------------------------------------------------------------- LOGOUT

@router.post("/logout")
async def auth_logout(
    request: Request,
    user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """Record a logout event. JWT itself is stateless, so this is
    audit-only — the client throws the token away."""
    if user:
        svc = _svc()
        await svc.write_event(
            user=user, event="logout", method="manual", success=True,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    return {"success": True}


def _mask_email(email: Optional[str]) -> str:
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"
