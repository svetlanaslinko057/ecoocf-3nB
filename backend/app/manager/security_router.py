"""
Account security — per-user 2FA (Google Authenticator / TOTP).
===============================================================

Works for ANY authenticated staff member (admin OR manager). The TOTP
secret is stored in the ``admin_security`` collection under the scope
``user:{id}`` — EXACTLY the scope read by
``AuthPolicyService.is_totp_enabled`` / ``verify_totp`` — so enabling 2FA
here automatically makes the next login require a 6-digit code.

Endpoints (prefix ``/api/account``):
    GET  /2fa/status   -> {enabled, setupPending}
    POST /2fa/setup    -> {secret, qrCode, uri, issuer, account}
    POST /2fa/verify   -> {success, enabled}   (activates after first valid code)
    POST /2fa/disable  -> {success, enabled}   (requires a valid current code)
"""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, Dict

import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_user
from app.repositories import AdminSecurityRepository

router = APIRouter(prefix="/api/account", tags=["account-security"])

ISSUER = "ECO.NOVA"


def _repo() -> AdminSecurityRepository:
    from app.core.db_runtime import get_db
    return AdminSecurityRepository(get_db())


def _scope(user: Dict[str, Any]) -> str:
    return f"user:{user.get('id') or user.get('email')}"


@router.get("/2fa/status")
async def status(user: Dict[str, Any] = Depends(require_user)):
    doc = (await _repo().get_state(_scope(user))) or {}
    return {
        "enabled": bool(doc.get("twofa_enabled")),
        "setupPending": bool(doc.get("twofa_secret") and not doc.get("twofa_enabled")),
        "email": user.get("email"),
    }


@router.post("/2fa/setup")
async def setup(user: Dict[str, Any] = Depends(require_user)):
    """Generate a fresh TOTP secret + QR PNG. Activation requires /verify."""
    scope = _scope(user)
    secret = pyotp.random_base32()
    account = user.get("email") or scope
    uri = pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER)

    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    await _repo().record_setup_pending(scope, secret=secret)
    return {
        "secret": secret,
        "qrCode": f"data:image/png;base64,{qr_b64}",
        "uri": uri,
        "issuer": ISSUER,
        "account": account,
    }


@router.post("/2fa/verify")
async def verify(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    scope = _scope(user)
    code = str(data.get("code", "")).strip()
    if not code:
        raise HTTPException(status_code=400, detail="Введіть код")
    doc = (await _repo().get_state(scope)) or {}
    secret = doc.get("twofa_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="Спочатку почніть налаштування 2FA")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Невірний код")
    await _repo().mark_enabled(scope)
    return {"success": True, "enabled": True}


@router.post("/2fa/disable")
async def disable(data: Dict[str, Any] = Body(default={}), user: Dict[str, Any] = Depends(require_user)):
    scope = _scope(user)
    code = str((data or {}).get("code", "")).strip()
    doc = (await _repo().get_state(scope)) or {}
    if doc.get("twofa_enabled"):
        secret = doc.get("twofa_secret")
        if not code or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise HTTPException(status_code=400, detail="Введіть дійсний код, щоб вимкнути 2FA")
    await _repo().clear_2fa(scope)
    return {"success": True, "enabled": False}
