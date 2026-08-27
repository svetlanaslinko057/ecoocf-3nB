"""
LoginAuditRepository — владеет коллекцией ``db.login_audit``.
=========================================================

Строго выделенный овнер журнала входов в панель сотрудников
(staff). Репозиторий ничего не знает про HTTP, про auth, про крипту —
только о форме записей и о запросах.

Шаблон записи::

    {
      _id, id (uuid),
      user_id, user_email, user_name, role,
      event:     "login" | "logout" | "daily_reset_logout",
      method:    "password" | "totp" | "email_otp",
      ip, user_agent,
      device:    {browser, os, kind}        # разобрано из UA
      at:        datetime UTC,
      success:   bool,
      details:   {... free-form ...},
    }
Индексыируем по ``user_id+at`` и ``at`` для быстрых сортировок.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.repo.login_audit")


class LoginAuditRepository:
    """Repository for staff login/logout audit trail."""

    def __init__(self, db):
        self._db = db
        self._col = db.login_audit

    async def ensure_indexes(self) -> None:
        try:
            await self._col.create_index([("user_id", 1), ("at", -1)], name="la_user_at")
            await self._col.create_index([("at", -1)], name="la_at")
            await self._col.create_index([("role", 1), ("at", -1)], name="la_role_at")
        except Exception as e:
            logger.warning(f"[login_audit] ensure_indexes failed: {e}")

    async def record(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one audit entry. Returns the inserted record (stripped of _id).

        The router/service layer is responsible for filling user_id, role,
        event, method, ip, user_agent, device, etc. The repository only
        normalises timestamps and the stable ``id`` field.
        """
        now = datetime.now(timezone.utc)
        rec = {
            "id": doc.get("id") or str(uuid.uuid4()),
            "user_id":    doc.get("user_id"),
            "user_email": doc.get("user_email"),
            "user_name":  doc.get("user_name"),
            "role":       (doc.get("role") or "").lower() or None,
            "event":      doc.get("event") or "login",
            "method":     doc.get("method") or "password",
            "ip":         doc.get("ip"),
            "user_agent": doc.get("user_agent"),
            "device":     doc.get("device") or {},
            "at":         doc.get("at") or now,
            "success":    bool(doc.get("success", True)),
            "details":    doc.get("details") or {},
        }
        try:
            await self._col.insert_one(dict(rec))
        except Exception as e:
            logger.warning(f"[login_audit] insert failed: {e}")
        return rec

    async def list_events(
        self,
        *,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        event: Optional[str] = None,
        method: Optional[str] = None,
        success: Optional[bool] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 200,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        q: Dict[str, Any] = {}
        if user_id: q["user_id"] = user_id
        if role:    q["role"] = role.lower()
        if event:   q["event"] = event
        if method:  q["method"] = method
        if success is not None: q["success"] = bool(success)
        if date_from or date_to:
            r: Dict[str, Any] = {}
            if date_from: r["$gte"] = date_from
            if date_to:   r["$lte"] = date_to
            q["at"] = r
        cursor = self._col.find(q).sort("at", -1).skip(int(skip)).limit(int(limit))
        out: List[Dict[str, Any]] = []
        async for d in cursor:
            d.pop("_id", None)
            at = d.get("at")
            if isinstance(at, datetime):
                d["at"] = at.isoformat()
            out.append(d)
        return out

    async def counts_summary(self, since: Optional[datetime] = None) -> Dict[str, int]:
        """Aggregate counters for a dashboard widget.

        Returns counts of {logins_today, logins_7d, failed_today,
        unique_users_today}.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_d_ago = now - timedelta(days=7)
        try:
            logins_today = await self._col.count_documents(
                {"event": "login", "success": True, "at": {"$gte": today_start}},
            )
            logins_7d = await self._col.count_documents(
                {"event": "login", "success": True, "at": {"$gte": seven_d_ago}},
            )
            failed_today = await self._col.count_documents(
                {"event": "login", "success": False, "at": {"$gte": today_start}},
            )
            unique_today = len(
                await self._col.distinct("user_id", {"event": "login", "success": True, "at": {"$gte": today_start}}),
            )
            return {
                "loginsToday": logins_today,
                "logins7d": logins_7d,
                "failedToday": failed_today,
                "uniqueUsersToday": unique_today,
            }
        except Exception as e:
            logger.warning(f"[login_audit] counts_summary failed: {e}")
            return {"loginsToday": 0, "logins7d": 0, "failedToday": 0, "uniqueUsersToday": 0}
