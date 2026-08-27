"""
BIBI Cars — Wave 17 — Action Center aggregations
===================================================

Scope-aware roll-ups for Inbox / My / Team / Analytics. Scope rules
match the rest of the system:

    admin / master_admin / owner → all actions
    team_lead                     → actions owned by self OR by team members
    manager                       → actions owned by self
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorDatabase


PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def scope_filter(db, user: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    role = (user or {}).get("role")
    if role in ("master_admin", "admin", "owner"):
        return None, {"all": True, "managers": 0}
    # ECO role chain: Admin → Manager → User. Managers see only their own actions.
    own = user.get("id") or user.get("managerId") or user.get("sub")
    return {"owner_id": own}, {"all": False, "managers": 1}


def _is_overdue(a: Dict[str, Any], now: datetime) -> bool:
    due = a.get("due_at")
    if not due or a.get("status") in ("resolved", "cancelled"):
        return False
    try:
        return datetime.fromisoformat(due.replace("Z", "+00:00")) < now
    except Exception:
        return False


async def list_actions(db, scope, *, status=None, priority=None, source=None,
                       owner_id=None, only_open=False, limit=500) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if scope: q.update(scope)
    if status:    q["status"]   = status
    if priority:  q["priority"] = priority
    if source:    q["source"]   = source
    if owner_id:  q["owner_id"] = owner_id
    if only_open: q["status"]   = {"$in": ["open", "in_progress", "snoozed"]}
    return await db.actions.find(q, {"_id": 0}).sort("updated_at", -1).to_list(length=limit)


async def compute_inbox(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 1 — every open action."""
    f, scope = await scope_filter(db, user)
    q = dict(f or {})
    q["status"] = {"$in": ["open", "in_progress", "snoozed"]}
    rows = await db.actions.find(q, {"_id": 0}).to_list(length=2000)
    now = datetime.now(timezone.utc)

    by_priority: Dict[str, int] = {p: 0 for p in ("critical", "high", "medium", "low")}
    by_source:   Dict[str, int] = defaultdict(int)
    by_status:   Dict[str, int] = defaultdict(int)
    overdue = 0
    impact_total    = 0.0
    impact_critical = 0.0

    for a in rows:
        a["is_overdue"] = _is_overdue(a, now)
        if a["is_overdue"]:
            overdue += 1
        p = a.get("priority") or "low"
        by_priority[p] = by_priority.get(p, 0) + 1
        by_source[a.get("source") or "manual"]   += 1
        by_status[a.get("status") or "open"]     += 1
        impact = float(a.get("impact") or 0)
        impact_total += impact
        if p == "critical":
            impact_critical += impact

    rows.sort(key=lambda a: (PRIORITY_RANK.get(a.get("priority") or "low", 3),
                              0 if a.get("is_overdue") else 1,
                              -float(a.get("impact") or 0)))
    return {
        "as_of":            datetime.now(timezone.utc).isoformat(),
        "items":            rows[:400],
        "total":            len(rows),
        "overdue":          overdue,
        "by_priority":      by_priority,
        "by_source":        dict(by_source),
        "by_status":        dict(by_status),
        "impact_total":     round(impact_total, 2),
        "impact_critical":  round(impact_critical, 2),
        "scope":            scope,
        "currency":         "UAH",
    }


async def compute_my(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 2 — actions assigned to me, bucketed by Overdue / Today / This week / Later."""
    own = user.get("id") or user.get("managerId") or user.get("sub")
    rows = await db.actions.find(
        {"owner_id": own, "status": {"$in": ["open", "in_progress", "snoozed"]}},
        {"_id": 0}).to_list(length=2000)
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    week_end  = today_end + timedelta(days=7)

    overdue: List[Dict[str, Any]] = []
    today:   List[Dict[str, Any]] = []
    week:    List[Dict[str, Any]] = []
    later:   List[Dict[str, Any]] = []
    for a in rows:
        due = a.get("due_at")
        try:
            d = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else None
        except Exception:
            d = None
        a["is_overdue"] = bool(d and d < now)
        if d and d < now:           overdue.append(a)
        elif d and d <= today_end:  today.append(a)
        elif d and d <= week_end:   week.append(a)
        else:                       later.append(a)

    for bucket in (overdue, today, week, later):
        bucket.sort(key=lambda a: (PRIORITY_RANK.get(a.get("priority") or "low", 3),
                                    -float(a.get("impact") or 0)))

    return {
        "as_of":   datetime.now(timezone.utc).isoformat(),
        "owner_id": own,
        "buckets": {
            "overdue":   {"items": overdue, "total": len(overdue)},
            "today":     {"items": today,   "total": len(today)},
            "this_week": {"items": week,    "total": len(week)},
            "later":     {"items": later,   "total": len(later)},
        },
        "total":   len(rows),
        "currency": "UAH",
    }


async def compute_team(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 3 — per-manager load + SLA. Visible to admin / team_lead."""
    f, scope = await scope_filter(db, user)
    q = dict(f or {})
    rows = await db.actions.find(q, {"_id": 0}).to_list(length=5000)
    now = datetime.now(timezone.utc)

    by_owner: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "owner_id":     None,
        "owner_name":   None,
        "open":         0,
        "in_progress":  0,
        "snoozed":      0,
        "overdue":      0,
        "resolved":     0,
        "resolved_today": 0,
        "escalated":    0,
        "avg_resolution_hours": None,
        "_resolution_hours":    [],
        "impact_open":  0.0,
    })
    for a in rows:
        oid  = a.get("owner_id") or "__unassigned__"
        b    = by_owner[oid]
        b["owner_id"]   = a.get("owner_id")
        b["owner_name"] = a.get("owner_name") or b["owner_name"] or "Unassigned"
        status = a.get("status") or "open"
        if status == "open":         b["open"]        += 1
        elif status == "in_progress":b["in_progress"] += 1
        elif status == "snoozed":    b["snoozed"]     += 1
        elif status == "resolved":   b["resolved"]    += 1
        if a.get("escalated"):       b["escalated"]   += 1
        if status in ("open", "in_progress", "snoozed"):
            b["impact_open"] += float(a.get("impact") or 0)
            if _is_overdue(a, now):
                b["overdue"] += 1
        if status == "resolved":
            created = a.get("created_at"); resolved = a.get("resolved_at")
            try:
                c = datetime.fromisoformat(created.replace("Z", "+00:00"))
                r = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
                hrs = (r - c).total_seconds() / 3600.0
                if hrs >= 0:
                    b["_resolution_hours"].append(hrs)
                if r.date() == now.date():
                    b["resolved_today"] += 1
            except Exception:
                pass

    items: List[Dict[str, Any]] = []
    for oid, b in by_owner.items():
        hrs = b.pop("_resolution_hours")
        if hrs:
            b["avg_resolution_hours"] = round(sum(hrs) / len(hrs), 1)
        total_open = b["open"] + b["in_progress"] + b["snoozed"]
        sla_score = 100
        if total_open:
            sla_score -= min(100, int((b["overdue"] / max(1, total_open)) * 100))
        b["sla_score"] = max(0, min(100, sla_score))
        b["impact_open"] = round(b["impact_open"], 2)
        items.append(b)
    items.sort(key=lambda r: (-r["overdue"], -r["open"], r["sla_score"]))
    return {
        "as_of":  datetime.now(timezone.utc).isoformat(),
        "items":  items,
        "total":  len(items),
        "scope":  scope,
        "currency": "UAH",
    }


async def compute_analytics(db, user: Dict[str, Any], *, days: int = 30) -> Dict[str, Any]:
    """Tab 4 — resolution analytics over the last `days`."""
    f, scope = await scope_filter(db, user)
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    q = dict(f or {})
    q["$or"] = [{"created_at": {"$gte": since}}, {"resolved_at": {"$gte": since}},
                  {"status": {"$in": ["open", "in_progress", "snoozed"]}}]
    rows = await db.actions.find(q, {"_id": 0}).to_list(length=5000)

    created = sum(1 for a in rows if (a.get("created_at") or "") >= since)
    resolved = [a for a in rows if a.get("status") == "resolved" and (a.get("resolved_at") or "") >= since]
    resolved_count = len(resolved)
    open_now = sum(1 for a in rows if a.get("status") in ("open", "in_progress", "snoozed"))
    overdue_now = sum(1 for a in rows if a.get("status") in ("open", "in_progress", "snoozed")
                       and _is_overdue(a, now))

    # Average resolution time over the same window.
    hrs: List[float] = []
    for a in resolved:
        try:
            c = datetime.fromisoformat(a["created_at"].replace("Z", "+00:00"))
            r = datetime.fromisoformat(a["resolved_at"].replace("Z", "+00:00"))
            hrs.append((r - c).total_seconds() / 3600.0)
        except Exception:
            pass
    avg_hrs = round(sum(hrs) / len(hrs), 1) if hrs else None

    overdue_pct = round((overdue_now / max(1, open_now)) * 100, 1) if open_now else 0.0

    # daily series for the last `days` days
    by_day_created:  Dict[str, int] = defaultdict(int)
    by_day_resolved: Dict[str, int] = defaultdict(int)
    for d in range(days):
        key = (now - timedelta(days=days - 1 - d)).strftime("%Y-%m-%d")
        by_day_created[key] = 0
        by_day_resolved[key] = 0
    for a in rows:
        c = a.get("created_at")
        if c and c >= since:
            by_day_created[c[:10]] = by_day_created.get(c[:10], 0) + 1
        r = a.get("resolved_at")
        if r and r >= since and a.get("status") == "resolved":
            by_day_resolved[r[:10]] = by_day_resolved.get(r[:10], 0) + 1
    daily = []
    for d in sorted(by_day_created.keys()):
        daily.append({"date": d, "created": by_day_created[d], "resolved": by_day_resolved.get(d, 0)})

    by_source:   Dict[str, int] = defaultdict(int)
    by_priority: Dict[str, int] = defaultdict(int)
    for a in rows:
        by_source[a.get("source") or "manual"]   += 1
        by_priority[a.get("priority") or "low"]  += 1

    return {
        "as_of":   now.isoformat(),
        "window_days":   days,
        "created":       created,
        "resolved":      resolved_count,
        "open_now":      open_now,
        "overdue_now":   overdue_now,
        "overdue_pct":   overdue_pct,
        "avg_resolution_hours": avg_hrs,
        "daily":         daily,
        "by_source":     dict(by_source),
        "by_priority":   dict(by_priority),
        "scope":         scope,
        "currency":      "UAH",
    }


__all__ = ["scope_filter", "list_actions", "compute_inbox",
           "compute_my", "compute_team", "compute_analytics"]
