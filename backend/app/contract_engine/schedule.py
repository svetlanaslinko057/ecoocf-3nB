"""Universal schedule generator.

Given a contract validity window and a ``period_type`` we produce a list of
time windows. Supports quarter / month / one_time out of the box, plus
``custom`` where the caller supplies explicit windows. Designed so that adding
a new cadence (week, etc.) never requires touching the rest of the engine.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .util import parse_date, iso_date


def _quarter_windows(start: date, end: date) -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    cur = date(start.year, ((start.month - 1) // 3) * 3 + 1, 1)
    while cur <= end:
        q = (cur.month - 1) // 3  # 0..3
        m_end = q * 3 + 3
        if m_end == 12:
            q_end = date(cur.year, 12, 31)
            nxt = date(cur.year + 1, 1, 1)
        else:
            q_end = date(cur.year, m_end + 1, 1) - timedelta(days=1)
            nxt = date(cur.year, m_end + 1, 1)
        windows.append({
            "label": f"{cur.year}-Q{q + 1}",
            "date_from": iso_date(max(cur, start)),
            "date_to": iso_date(min(q_end, end)),
        })
        cur = nxt
    return windows


def _month_windows(start: date, end: date) -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        m_end = nxt - timedelta(days=1)
        windows.append({
            "label": f"{cur.year}-{cur.month:02d}",
            "date_from": iso_date(max(cur, start)),
            "date_to": iso_date(min(m_end, end)),
        })
        cur = nxt
    return windows


def build_windows(
    period_type: str,
    valid_from: Any,
    valid_to: Any,
    *,
    custom_windows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Return an ordered list of ``{label, date_from, date_to}`` windows."""
    start = parse_date(valid_from)
    end = parse_date(valid_to)

    if period_type == "custom":
        out = []
        for i, w in enumerate(custom_windows or []):
            out.append({
                "label": (w.get("label") or f"Період {i + 1}").strip(),
                "date_from": iso_date(parse_date(w.get("date_from"))),
                "date_to": iso_date(parse_date(w.get("date_to"))),
            })
        return out

    if not start or not end or end < start:
        # Not enough data -> single window spanning whatever we have.
        return [{"label": "Одноразово", "date_from": iso_date(start), "date_to": iso_date(end)}]

    if period_type == "one_time":
        return [{"label": "Одноразово", "date_from": iso_date(start), "date_to": iso_date(end)}]
    if period_type == "month":
        return _month_windows(start, end)
    # default: quarter
    return _quarter_windows(start, end)


def window_contains(window: Dict[str, Any], when: Any) -> bool:
    d = parse_date(when)
    if not d:
        return False
    f = parse_date(window.get("date_from"))
    t = parse_date(window.get("date_to"))
    if f and d < f:
        return False
    if t and d > t:
        return False
    return True
