"""
login_audit — журнал входов (HTTP-слой)
========================================

Два роутера в одном модуле: «админ видит всё» и «тимлид видит своих
менеджеров и себя». Роутер только о форме HTTP — вся логика в
``LoginAuditRepository``.
Данные по умолчанию — за последние 30 дней, с поддержкой фильтров.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from security import require_admin, require_manager_or_admin
from app.repositories.login_audit import LoginAuditRepository

logger = logging.getLogger("bibi.login_audit_http")


def _repo():
    from app.core.db_runtime import get_db
    return LoginAuditRepository(get_db())


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Accept ISO date or full datetime
        if "T" not in s and len(s) == 10:
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------- ADMIN (full view)

admin_router = APIRouter(
    prefix="/api/admin/login-audit",
    tags=["admin-login-audit"],
    dependencies=[Depends(require_admin)],
)


@admin_router.get("")
async def admin_list(
    user_id: Optional[str] = None,
    role: Optional[str] = None,
    event: Optional[str] = None,
    method: Optional[str] = None,
    success: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    skip: int = Query(0, ge=0),
):
    df = _parse_dt(date_from) or (datetime.now(timezone.utc) - timedelta(days=30))
    dt = _parse_dt(date_to)
    repo = _repo()
    items = await repo.list_events(
        user_id=user_id, role=role, event=event, method=method,
        success=success, date_from=df, date_to=dt,
        limit=limit, skip=skip,
    )
    summary = await repo.counts_summary()
    return {"data": items, "summary": summary, "count": len(items)}


# -------------------------------------------------- TEAM-LEAD (скоуп scope)

team_router = APIRouter(
    prefix="/api/team-lead/login-audit",
    tags=["team-lead-login-audit"],
    dependencies=[Depends(require_manager_or_admin)],
)


@team_router.get("")
async def team_list(
    user_id: Optional[str] = None,
    event: Optional[str] = None,
    method: Optional[str] = None,
    success: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Team-lead view of the staff login log.

    Manager: sees only their own logins.
    Team-lead/admin: sees everyone (same scope as admin endpoint, but
    routed under /team-lead for the team-lead UI).
    """
    from app.services.auth_policy import is_manager_role
    df = _parse_dt(date_from) or (datetime.now(timezone.utc) - timedelta(days=30))
    dt = _parse_dt(date_to)
    role = (user.get("role") or "").lower()
    if is_manager_role(role):
        # Менеджер видит только свои входы — endpoint пригодится в «My security» вкладке.
        user_id = user.get("id") or user.get("_id")
    repo = _repo()
    items = await repo.list_events(
        user_id=user_id, event=event, method=method, success=success,
        date_from=df, date_to=dt, limit=limit, skip=skip,
    )
    summary = await repo.counts_summary()
    return {"data": items, "summary": summary, "count": len(items)}
