"""
BIBI Cars — Wave 15 — Contract aggregations
=============================================

Scope-aware read-only roll-ups used by:
  * GET /api/contracts/overview — Contract360 dashboard
  * GET /api/contracts/risk     — at-risk queue

Mirrors the scope rules used by Wave 12 / 13 / 14:
  * admin / master_admin / owner → all
  * team_lead                     → own + team members' deals
  * manager                       → own deals only
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.wave15.contract_health import compute_contract_health, CONTRACT_SEGMENTS


async def scope_filter(db, user: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    role = (user or {}).get("role")
    if role in ("master_admin", "admin", "owner"):
        return None, {"all": True, "managers": 0}
    if role == "team_lead":
        own_id = user.get("id") or user.get("managerId") or user.get("sub")
        team = await db.staff.find({"team_lead_id": own_id}, {"id": 1, "_id": 0}).to_list(length=500)
        ids = [own_id] + [t.get("id") for t in team if t.get("id")]
        ids = [i for i in ids if i]
        return ({"$or": [{"managerId": {"$in": ids}}, {"manager_id": {"$in": ids}}]},
                {"all": False, "managers": len(ids)})
    mgr = user.get("id") or user.get("managerId") or user.get("sub")
    return ({"$or": [{"managerId": mgr}, {"manager_id": mgr}]},
            {"all": False, "managers": 1})


async def compute_contracts_overview(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Contract360 headline numbers + segment distribution."""
    f, scope = await scope_filter(db, user)
    q = dict(f or {})
    rows = await db.contracts.find(q, {"_id": 0}).to_list(length=5000)

    by_status: Dict[str, int] = defaultdict(int)
    by_type:   Dict[str, int] = defaultdict(int)
    by_segment: Dict[str, int] = {s: 0 for s in CONTRACT_SEGMENTS}

    total_value         = 0.0
    active_value        = 0.0
    unsigned_value      = 0.0
    pending_approvals   = 0
    overdue_signature   = 0  # contracts in 'unsigned' segment
    expiring_soon       = 0  # within 7d of valid_to
    healthy_count       = 0

    enriched: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for c in rows:
        h = compute_contract_health(c, now=now)
        c["health"] = h
        enriched.append(c)

        status = c.get("status") or "draft"
        ctype  = c.get("type") or c.get("template") or "custom"
        seg    = h["segment"]
        amount = float(c.get("amount") or 0.0)

        by_status[status] += 1
        by_type[ctype]     += 1
        by_segment[seg] = by_segment.get(seg, 0) + 1

        total_value += amount
        if status == "active":
            active_value += amount
            healthy_count += 1
        if seg == "unsigned":
            unsigned_value += amount
            overdue_signature += 1
        if status == "pending_approval":
            pending_approvals += 1
        days = (h.get("metrics") or {}).get("days_to_expiry")
        if days is not None and 0 <= days <= 7:
            expiring_soon += 1

    # top at-risk preview (worst 5, ordered by segment severity)
    severity_order = {"critical": 0, "unsigned": 1, "wrong_version": 2,
                       "missing_annex": 3, "pending_approval": 4,
                       "draft": 5, "healthy": 6, "archived": 7}
    at_risk = sorted(
        [c for c in enriched if c["health"]["segment"] not in ("healthy", "archived")],
        key=lambda c: severity_order.get(c["health"]["segment"], 99),
    )[:5]
    top = [{
        "id":         c.get("id"),
        "title":      c.get("title"),
        "type":       c.get("type"),
        "status":     c.get("status"),
        "amount":     c.get("amount"),
        "deal_id":    c.get("deal_id"),
        "segment":    c["health"]["segment"],
        "score":      c["health"]["score"],
        "reasons":    (c["health"].get("reasons") or [])[:2],
    } for c in at_risk]

    return {
        "as_of":              datetime.now(timezone.utc).isoformat(),
        "totals": {
            "contracts":         len(rows),
            "total_value":       round(total_value, 2),
            "active_value":      round(active_value, 2),
            "unsigned_value":    round(unsigned_value, 2),
            "healthy_count":     healthy_count,
            "overdue_signature": overdue_signature,
            "pending_approvals": pending_approvals,
            "expiring_soon":     expiring_soon,
        },
        "by_status":   dict(by_status),
        "by_type":     dict(by_type),
        "by_segment":  by_segment,
        "top_at_risk": top,
        "scope":       scope,
        "currency":    "EUR",
    }


async def compute_contract_risk(db, user: Dict[str, Any], *, limit: int = 200) -> Dict[str, Any]:
    """Contracts NOT in healthy/archived segment."""
    f, scope = await scope_filter(db, user)
    q = dict(f or {})
    rows = await db.contracts.find(q, {"_id": 0}).to_list(length=2000)
    now = datetime.now(timezone.utc)

    by_segment: Dict[str, int] = {s: 0 for s in CONTRACT_SEGMENTS
                                   if s not in ("healthy", "archived")}
    items: List[Dict[str, Any]] = []
    risk_value = 0.0
    for c in rows:
        h = compute_contract_health(c, now=now)
        seg = h["segment"]
        if seg in ("healthy", "archived"):
            continue
        amount = float(c.get("amount") or 0.0)
        risk_value += amount
        by_segment[seg] = by_segment.get(seg, 0) + 1
        items.append({
            "id":         c.get("id"),
            "title":      c.get("title"),
            "deal_id":    c.get("deal_id"),
            "manager_id": c.get("managerId") or c.get("manager_id"),
            "manager_name": c.get("manager_name"),
            "type":       c.get("type"),
            "status":     c.get("status"),
            "amount":     amount,
            "segment":    seg,
            "score":      h.get("score"),
            "reasons":    h.get("reasons") or [],
            "updated_at": c.get("updated_at"),
        })
    severity_order = {"critical": 0, "unsigned": 1, "wrong_version": 2,
                       "missing_annex": 3, "pending_approval": 4, "draft": 5}
    items.sort(key=lambda r: (severity_order.get(r["segment"], 99), -r["amount"]))

    return {
        "as_of":      datetime.now(timezone.utc).isoformat(),
        "items":      items[:limit],
        "total":      len(items),
        "by_segment": by_segment,
        "risk_value": round(risk_value, 2),
        "scope":      scope,
        "currency":   "EUR",
    }


__all__ = ["scope_filter", "compute_contracts_overview", "compute_contract_risk"]
