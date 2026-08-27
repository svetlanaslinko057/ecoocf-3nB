"""Small shared helpers for the contract engine (dates, ids, money)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def num(v: Any, default: float = 0.0) -> float:
    """Coerce anything to float; None/invalid -> default."""
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def round2(v: Any) -> float:
    try:
        return round(float(v) + 0.0, 2)
    except (TypeError, ValueError):
        return 0.0


def parse_date(v: Any) -> Optional[date]:
    """Parse YYYY-MM-DD / ISO datetime / date -> date. None-safe."""
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def iso_date(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=n)
