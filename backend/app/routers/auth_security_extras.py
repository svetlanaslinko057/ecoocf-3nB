"""
auth_security_extras — per-user TOTP + admin OTP config + pending OTPs view
===========================================================================

Дополняет существующий admin_security.py новыми ROUTES, не ломая старых:

  GET  /api/me/2fa/status               — свой статус TOTP
  POST /api/me/2fa/setup                — выдаёт QR + secret (пендинг до verify)
  POST /api/me/2fa/verify               — подтверждает включение
  POST /api/me/2fa/disable              — выключает (требует текущий код)

  GET  /api/admin/security/team-lead-otp-config   — текущий реципиент
  PUT  /api/admin/security/team-lead-otp-config   — изменить
  GET  /api/admin/security/pending-otps           — живые OTP-коды для тимлидов
  GET  /api/admin/security/daily-reset-config     — статус (включено/выкл/время)
  PUT  /api/admin/security/daily-reset-config     — вкл/выкл
"""
from __future__ import annotations

import base64
import logging
from io import BytesIO
from typing import Any, Dict

import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_admin, get_current_user

logger = logging.getLogger("bibi.auth_security_extras")


def _svc():
    from app.core.db_runtime import get_db
    from app.services.auth_policy import AuthPolicyService
    return AuthPolicyService(get_db())


# ============================================================ PER-USER TOTP

me_router = APIRouter(prefix="/api/me/2fa", tags=["me-2fa"])


def _scope(user: Dict[str, Any]) -> str:
    return f"user:{user.get('id') or user.get('email')}"


@me_router.get("/status")
async def me_2fa_status(user: Dict[str, Any] = Depends(get_current_user)):
    svc = _svc()
    doc = (await svc.admin_sec.get_state(_scope(user))) or {}
    return {
        "enabled": bool(doc.get("twofa_enabled")),
        "setupPending": bool(doc.get("twofa_secret") and not doc.get("twofa_enabled")),
        "available": True,
    }


@me_router.post("/setup")
async def me_2fa_setup(user: Dict[str, Any] = Depends(get_current_user)):
    """Generate fresh TOTP secret + QR. Activation happens after /verify.
    Only admin-role accounts may turn on TOTP — managers/team_leads use
    their own flows (daily-reset / email-OTP) and don't need it.
    """
    from app.services.auth_policy import is_admin_role
    if not is_admin_role(user.get("role")):
        raise HTTPException(status_code=403, detail="TOTP available only for admin role")
    svc = _svc()
    secret = pyotp.random_base32()
    issuer = "BIBI Cars CRM"
    account = user.get("email") or _scope(user)
    uri = pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    await svc.admin_sec.record_setup_pending(_scope(user), secret=secret)
    return {
        "secret": secret,
        "qrCode": f"data:image/png;base64,{qr_b64}",
        "uri": uri,
        "issuer": issuer,
        "account": account,
    }


@me_router.post("/verify")
async def me_2fa_verify(
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    code = str(payload.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="code required")
    svc = _svc()
    doc = (await svc.admin_sec.get_state(_scope(user))) or {}
    secret = doc.get("twofa_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="2FA setup not started")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    await svc.admin_sec.mark_enabled(_scope(user))
    return {"success": True, "enabled": True}


@me_router.post("/disable")
async def me_2fa_disable(
    payload: Dict[str, Any] = Body(default={}),
    user: Dict[str, Any] = Depends(get_current_user),
):
    svc = _svc()
    doc = (await svc.admin_sec.get_state(_scope(user))) or {}
    code = str((payload or {}).get("code") or "").strip()
    if doc.get("twofa_enabled"):
        secret = doc.get("twofa_secret")
        if not code or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise HTTPException(status_code=400, detail="Invalid code")
    await svc.admin_sec.clear_2fa(_scope(user))
    return {"success": True, "enabled": False}


# =========================================== ADMIN-ONLY: team_lead OTP config

admin_extra_router = APIRouter(
    prefix="/api/admin/security",
    tags=["admin-security-extras"],
    dependencies=[Depends(require_admin)],
)


@admin_extra_router.get("/team-lead-otp-config")
async def get_otp_config():
    svc = _svc()
    email = await svc.get_team_lead_otp_recipient()
    return {"recipient_email": email}


@admin_extra_router.put("/team-lead-otp-config")
async def put_otp_config(payload: Dict[str, Any] = Body(...)):
    email = (payload.get("recipient_email") or "").strip().lower()
    if email and "@" not in email:
        raise HTTPException(status_code=400, detail="recipient_email must be a valid email")
    svc = _svc()
    await svc.set_team_lead_otp_recipient(email or None)
    return {"success": True, "recipient_email": email or None}


@admin_extra_router.get("/pending-otps")
async def list_pending_otps(limit: int = 25):
    """Admin reads the active team-lead OTP codes. THIS IS THE FALLBACK
    that lets the system work without an SMTP integration: the admin
    sees the code in the UI and forwards it to the team-lead by phone
    or messenger."""
    svc = _svc()
    return {"data": await svc.otp.list_pending_for_admin(limit=limit)}


@admin_extra_router.get("/daily-reset-config")
async def get_daily_reset_config():
    svc = _svc()
    enabled = await svc.get_manager_daily_reset_enabled()
    return {
        "enabled": enabled,
        "hour_local": 12,
        "timezone": "Europe/Sofia",
        "applies_to": ["manager"],
    }


@admin_extra_router.put("/daily-reset-config")
async def put_daily_reset_config(payload: Dict[str, Any] = Body(...)):
    enabled = bool(payload.get("enabled", True))
    svc = _svc()
    await svc._settings_set("manager_daily_reset_enabled", enabled)
    return {"success": True, "enabled": enabled}


@admin_extra_router.get("/manager-relogins")
async def manager_relogins_since_daily_reset():
    """Управленческая панель: кто из менеджеров уже перезашёл после
    последнего 12:00 Europe/Sofia, кто ещё нет.

    Возвращает:
      since_utc:   ISO timestamp последнего 12:00 Europe/Sofia
      managers: [
        {
          id, email, name,
          relogged_in:   bool,                # был ли первый успешный login после since_utc
          first_login_at: ISO | null,
          ip, device { os, browser, kind }, user_agent,
          login_count_since:  int,            # сколько раз заходил после reset'а
          minutes_since_reset: int | null,    # как давно после reset'а — для маркера
          last_login_at: ISO | null,
          missing: bool                        # not relogged & manager seen ever
        }
      ]
      summary: { total_managers, relogged_in, pending }
    """
    from app.services.auth_policy import last_daily_reset_utc
    from datetime import datetime, timezone
    from app.core.db_runtime import get_db

    db = get_db()
    since = last_daily_reset_utc()
    now = datetime.now(timezone.utc)

    def _aware(d):
        """Mongo может вернуть naive datetime. Делаем tz-aware (UTC),
        чтобы операции `-` с tz-aware ``since`` не падали."""
        if d is None:
            return None
        if isinstance(d, datetime) and d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d

    # 1) All managers from db.staff
    staff_rows = await db.staff.find(
        {"role": {"$in": ["manager", "sales"]}}
    ).to_list(length=200)

    if not staff_rows:
        return {
            "since_utc": since.isoformat(),
            "since_label": since.astimezone().strftime("%d %b %H:%M"),
            "managers": [],
            "summary": {"total_managers": 0, "relogged_in": 0, "pending": 0},
        }

    # 2) For each manager, fetch their first successful login (event=login,
    # success=true) since `since`, plus their count and last entry.
    out = []
    relogged = 0
    for st in staff_rows:
        mgr_email = (st.get("email") or "").strip().lower()
        mgr_id = st.get("id") or st.get("_id")
        if not mgr_email:
            continue
        query = {
            "user_email": mgr_email,
            "event": "login",
            "success": True,
            "at": {"$gte": since},
        }
        cur = db.login_audit.find(query).sort("at", 1)
        rows = await cur.to_list(length=50)
        first = rows[0] if rows else None
        last = rows[-1] if rows else None
        if first:
            relogged += 1
        # last_ever login (for managers who didn't login yet today — show their previous session)
        last_ever = None
        if not first:
            le_cur = db.login_audit.find(
                {"user_email": mgr_email, "event": "login", "success": True}
            ).sort("at", -1).limit(1)
            le_rows = await le_cur.to_list(length=1)
            last_ever = le_rows[0] if le_rows else None

        item = {
            "id": str(mgr_id),
            "email": mgr_email,
            "name": st.get("name") or st.get("display_name") or mgr_email.split("@")[0].title(),
            "relogged_in": bool(first),
            "first_login_at": (_aware(first.get("at")).isoformat() if first and first.get("at") else None),
            "last_login_at":  (_aware(last.get("at")).isoformat()  if last  and last.get("at")  else None),
            "ip":           (first.get("ip")          if first else (last_ever.get("ip") if last_ever else None)),
            "device":       (first.get("device")      if first else (last_ever.get("device") if last_ever else {})),
            "user_agent":   (first.get("user_agent")  if first else (last_ever.get("user_agent") if last_ever else None)),
            "login_count_since": len(rows),
            "minutes_since_first": (
                int((_aware(last.get("at")) - _aware(first.get("at"))).total_seconds() // 60)
                if first and last and last.get("at") and first.get("at")
                else None
            ) if first else None,
            "minutes_since_reset_to_login": (
                int((_aware(first.get("at")) - since).total_seconds() // 60)
                if first and first.get("at") else None
            ),
            "pending_minutes": (
                int((now - since).total_seconds() // 60) if not first else None
            ),
            "last_login_before_reset_at": (
                _aware(last_ever.get("at")).isoformat() if last_ever and last_ever.get("at") else None
            ),
        }
        out.append(item)

    # Sort: pending first (so admin sees who hasn't logged in yet), then by first_login asc
    out.sort(key=lambda x: (x["relogged_in"], x.get("first_login_at") or ""))

    return {
        "since_utc": since.isoformat(),
        "since_label": since.astimezone().strftime("%d %b %H:%M UTC"),
        "now_utc": now.isoformat(),
        "managers": out,
        "summary": {
            "total_managers": len(out),
            "relogged_in": relogged,
            "pending": len(out) - relogged,
        },
    }
