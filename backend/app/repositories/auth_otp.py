"""
AuthOtpRepository — владеет коллекцией ``db.auth_email_otp``.
========================================================

Одноразовые коды для email-OTP логина (тимлиды).
Шифруем только SHA-256 от кода, равный код в базе не храним.
Но для UX «мастер-админ видит код в админке» попытки и plaintext-код
храним тоже (срок TTL 10 минут), видимые только админу через
защищённый endpoint. Это и есть фоллбэк под сценарий «без ключей».

Схема::

    {
      _id, id (uuid),
      challenge_token: str,
      user_id, user_email, role,
      recipient_email: str (куда "отправили" — как правило админ),
      code:            str (6-значный plaintext, TTL 10 мин),
      code_hash:       str (SHA-256 для verify-пути),
      attempts:        int (макс 5),
      created_at, expires_at, used_at,
      status: "pending" | "used" | "expired" | "failed"
    }
Индексы: challenge_token unique, expires_at TTL.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.repo.auth_otp")

OTP_TTL_MIN = 10
MAX_ATTEMPTS = 5


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class AuthOtpRepository:
    def __init__(self, db):
        self._db = db
        self._col = db.auth_email_otp

    async def ensure_indexes(self) -> None:
        try:
            await self._col.create_index([("challenge_token", 1)], unique=True, name="otp_ct_unique")
            await self._col.create_index([("user_id", 1), ("created_at", -1)], name="otp_user_at")
            # Mongo TTL — auto-clean expired entries (24h after expires_at to keep history briefly)
            await self._col.create_index("expires_at", expireAfterSeconds=86400, name="otp_ttl")
            await self._col.create_index([("status", 1), ("created_at", -1)], name="otp_status_at")
        except Exception as e:
            logger.warning(f"[auth_otp] ensure_indexes failed: {e}")

    async def issue(
        self,
        *,
        user_id: str,
        user_email: str,
        role: str,
        recipient_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a fresh 6-digit OTP code + challenge_token. Returns full doc."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        challenge_token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        doc = {
            "id": str(uuid.uuid4()),
            "challenge_token": challenge_token,
            "user_id": user_id,
            "user_email": user_email,
            "role": (role or "").lower() or None,
            "recipient_email": recipient_email or user_email,
            "code": code,
            "code_hash": _hash(code),
            "attempts": 0,
            "created_at": now,
            "expires_at": now + timedelta(minutes=OTP_TTL_MIN),
            "used_at": None,
            "status": "pending",
        }
        try:
            await self._col.insert_one(dict(doc))
        except Exception as e:
            logger.error(f"[auth_otp] issue failed: {e}")
            raise
        return doc

    async def get_by_token(self, challenge_token: str) -> Optional[Dict[str, Any]]:
        if not challenge_token:
            return None
        d = await self._col.find_one({"challenge_token": challenge_token})
        if d:
            d.pop("_id", None)
        return d

    async def verify(self, challenge_token: str, code: str) -> Dict[str, Any]:
        """Verify code. Returns {ok, status, doc?}. Increments attempts on fail.

        Outcome codes:
          - ok=True, status='used'
          - ok=False, status='not_found' | 'expired' | 'already_used' |
                            'too_many_attempts' | 'invalid'
        """
        d = await self.get_by_token(challenge_token)
        if not d:
            return {"ok": False, "status": "not_found"}
        if d.get("status") == "used":
            return {"ok": False, "status": "already_used"}
        exp = d.get("expires_at")
        if isinstance(exp, datetime) and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and datetime.now(timezone.utc) > exp:
            await self._col.update_one({"challenge_token": challenge_token}, {"$set": {"status": "expired"}})
            return {"ok": False, "status": "expired"}
        attempts = int(d.get("attempts") or 0)
        if attempts >= MAX_ATTEMPTS:
            await self._col.update_one({"challenge_token": challenge_token}, {"$set": {"status": "failed"}})
            return {"ok": False, "status": "too_many_attempts"}
        if _hash((code or "").strip()) != d.get("code_hash"):
            await self._col.update_one({"challenge_token": challenge_token}, {"$inc": {"attempts": 1}})
            return {"ok": False, "status": "invalid"}
        await self._col.update_one(
            {"challenge_token": challenge_token},
            {"$set": {"status": "used", "used_at": datetime.now(timezone.utc)}},
        )
        d["status"] = "used"
        return {"ok": True, "status": "used", "doc": d}

    async def list_pending_for_admin(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Return active (non-expired, non-used) OTP requests so master-admin
        can read the codes from the UI and pass them to the team-lead by
        phone/messenger. Sensitive: ONLY mounted under require_admin."""
        now = datetime.now(timezone.utc)
        cursor = self._col.find({
            "status": "pending",
            "expires_at": {"$gt": now},
        }).sort("created_at", -1).limit(int(limit))
        out: List[Dict[str, Any]] = []
        async for d in cursor:
            d.pop("_id", None)
            for k in ("created_at", "expires_at", "used_at"):
                v = d.get(k)
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            # Оставляем plaintext code — именно он нужен админу. Скрываем хэш.
            d.pop("code_hash", None)
            out.append(d)
        return out
