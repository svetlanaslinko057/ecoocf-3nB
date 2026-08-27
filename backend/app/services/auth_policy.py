"""
auth_policy — политика входа и сессий BIBI Cars
=================================================

Этот сервис знает правила и ничего не знает про HTTP и про Mongo.
Он вызывает репозитории (login_audit, auth_otp, admin_security)
и возвращает решения наверх в router.

Политика:
  • manager:   password only, ежедневный hard-reset в 12:00 Europe/Sofia
  • team_lead: password → email-OTP (код виден админу в админке)
  • admin:     password → TOTP (Google Authenticator), если включён в личном профиле.
                Если админ ещё не настроил TOTP — пускаем по password (опциональность).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import pyotp
from zoneinfo import ZoneInfo

from app.repositories.login_audit import LoginAuditRepository
from app.repositories.auth_otp import AuthOtpRepository
from app.repositories import AdminSecurityRepository

logger = logging.getLogger("bibi.svc.auth_policy")

SOFIA_TZ = ZoneInfo("Europe/Sofia")
ADMIN_ROLES = {"admin", "master_admin", "owner", "moderator"}
MANAGER_ROLES = {"manager", "sales"}
TEAM_LEAD_ROLES = {"team_lead", "team-lead", "teamlead"}

# Configuration key in db.settings for the email recipient that receives
# team-lead login OTP codes. Admin can change this from the UI.
SETTINGS_KEY_OTP_RECIPIENT = "team_lead_otp_recipient_email"
SETTINGS_KEY_DAILY_RESET = "manager_daily_reset_enabled"   # bool, default True


# ---------------------------------------------------------------------------
#  Role helpers
# ---------------------------------------------------------------------------

def normalize_role(role: Optional[str]) -> str:
    r = (role or "").strip().lower().replace("-", "_")
    if r in {"teamlead", "team_lead"}:
        return "team_lead"
    return r


def is_admin_role(role: Optional[str]) -> bool:
    return normalize_role(role) in ADMIN_ROLES


def is_team_lead_role(role: Optional[str]) -> bool:
    return normalize_role(role) in TEAM_LEAD_ROLES


def is_manager_role(role: Optional[str]) -> bool:
    return normalize_role(role) in MANAGER_ROLES


# ---------------------------------------------------------------------------
#  Daily reset (Europe/Sofia 12:00)
# ---------------------------------------------------------------------------

DAILY_RESET_HOUR_LOCAL = 12  # 12:00 Europe/Sofia


def last_daily_reset_utc(now: Optional[datetime] = None) -> datetime:
    """Return the timestamp (UTC) of the *most recent* 12:00 Europe/Sofia
    boundary at or before ``now``. Any session whose ``iat`` is strictly
    before this timestamp is considered expired for managers.
    """
    now_utc = now or datetime.now(timezone.utc)
    now_sofia = now_utc.astimezone(SOFIA_TZ)
    boundary_local = now_sofia.replace(hour=DAILY_RESET_HOUR_LOCAL, minute=0, second=0, microsecond=0)
    if now_sofia < boundary_local:
        boundary_local = boundary_local - timedelta(days=1)
    return boundary_local.astimezone(timezone.utc)


def is_token_expired_by_daily_reset(role: Optional[str], iat_timestamp: Optional[int]) -> bool:
    """True if ``role`` is a manager AND the token's ``iat`` is strictly
    before the last daily-reset boundary. Other roles are not affected.
    """
    if not is_manager_role(role):
        return False
    if not iat_timestamp:
        return False
    iat_dt = datetime.fromtimestamp(int(iat_timestamp), tz=timezone.utc)
    return iat_dt < last_daily_reset_utc()


# ---------------------------------------------------------------------------
#  Device fingerprinting (best-effort from UA)
# ---------------------------------------------------------------------------

_UA_PATTERNS = [
    (r"iPhone", "iOS", "phone"),
    (r"iPad", "iOS", "tablet"),
    (r"Android", "Android", "phone"),
    (r"Macintosh|Mac OS X", "macOS", "desktop"),
    (r"Windows NT", "Windows", "desktop"),
    (r"X11.*Linux", "Linux", "desktop"),
]
_BROWSER_PATTERNS = [
    (r"Edg/",      "Edge"),
    (r"OPR/|Opera", "Opera"),
    (r"Firefox/",  "Firefox"),
    (r"Chrome/",   "Chrome"),
    (r"Safari/",   "Safari"),
]


def parse_device(user_agent: Optional[str]) -> Dict[str, str]:
    ua = user_agent or ""
    os_name = "Unknown"
    kind = "desktop"
    for pat, os_, k in _UA_PATTERNS:
        if re.search(pat, ua):
            os_name = os_
            kind = k
            break
    browser = "Unknown"
    for pat, b in _BROWSER_PATTERNS:
        if re.search(pat, ua):
            browser = b
            break
    return {"os": os_name, "browser": browser, "kind": kind}


# ---------------------------------------------------------------------------
#  Service
# ---------------------------------------------------------------------------

class AuthPolicyService:
    """Stateful only via injected ``db`` handle. Stateless per-request."""

    def __init__(self, db):
        self._db = db
        self.audit = LoginAuditRepository(db)
        self.otp = AuthOtpRepository(db)
        self.admin_sec = AdminSecurityRepository(db)

    # ---- settings (db.settings) -------------------------------------------

    async def _settings_get(self, key: str, default: Any = None) -> Any:
        try:
            d = await self._db.settings.find_one({"_id": key})
            return (d or {}).get("value", default)
        except Exception:
            return default

    async def _settings_set(self, key: str, value: Any) -> None:
        try:
            await self._db.settings.update_one(
                {"_id": key},
                {"$set": {"value": value, "updated_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[auth_policy] settings_set({key}) failed: {e}")

    async def get_team_lead_otp_recipient(self) -> Optional[str]:
        return await self._settings_get(SETTINGS_KEY_OTP_RECIPIENT, None)

    async def set_team_lead_otp_recipient(self, email: Optional[str]) -> None:
        await self._settings_set(SETTINGS_KEY_OTP_RECIPIENT, (email or "").strip().lower() or None)

    async def get_manager_daily_reset_enabled(self) -> bool:
        v = await self._settings_get(SETTINGS_KEY_DAILY_RESET, True)
        return bool(v)

    # ---- per-user TOTP scope ---------------------------------------------

    def _totp_scope_for(self, user: Dict[str, Any]) -> str:
        return f"user:{user.get('id') or user.get('email')}"

    async def is_totp_enabled(self, user: Dict[str, Any]) -> bool:
        doc = (await self.admin_sec.get_state(self._totp_scope_for(user))) or {}
        return bool(doc.get("twofa_enabled"))

    async def verify_totp(self, user: Dict[str, Any], code: str) -> bool:
        doc = (await self.admin_sec.get_state(self._totp_scope_for(user))) or {}
        secret = doc.get("twofa_secret")
        if not secret:
            return False
        try:
            return pyotp.TOTP(secret).verify((code or "").strip(), valid_window=1)
        except Exception:
            return False

    # ---- main policy decision --------------------------------------------

    async def required_challenge(self, user: Dict[str, Any]) -> Optional[str]:
        """After password is verified, returns the next challenge step or
        None if the session is ready to be issued.

        Outcomes:
          - None         -> no further step, issue JWT now (manager/admin
                            without TOTP enabled in their profile)
          - 'totp'       -> require TOTP from Google Authenticator
                            (admin OR manager who enabled 2FA)

        NOTE: the ``team_lead`` role has been removed from the product —
        there is no email-OTP login path anymore.
        """
        role = normalize_role(user.get("role"))
        # admin + manager: optional Google Authenticator (TOTP).
        # Challenge only if the user enabled 2FA in their own profile.
        if role in ADMIN_ROLES or role in MANAGER_ROLES:
            return "totp" if await self.is_totp_enabled(user) else None
        return None  # all others: password only

    # ---- audit ------------------------------------------------------------

    async def write_event(
        self,
        *,
        user: Dict[str, Any],
        event: str,
        method: str,
        success: bool,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            await self.audit.record({
                "user_id":    user.get("id"),
                "user_email": user.get("email"),
                "user_name":  user.get("name"),
                "role":       normalize_role(user.get("role")),
                "event":      event,
                "method":     method,
                "ip":         ip,
                "user_agent": user_agent,
                "device":     parse_device(user_agent),
                "success":    success,
                "details":    details or {},
            })
        except Exception as e:
            logger.warning(f"[auth_policy] write_event failed: {e}")


async def ensure_indexes(db) -> None:
    """Aggregate index ensure invoked from server startup."""
    await LoginAuditRepository(db).ensure_indexes()
    await AuthOtpRepository(db).ensure_indexes()
