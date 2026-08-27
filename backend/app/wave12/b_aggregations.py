"""
Wave 12B — Manager P&L, Revenue at Risk, Collections Queue.

All three are scope-aware (reuse `finance_scope_for_user` from Wave 12A)
and read-only. They piggyback on the existing `_deals_in_scope` plus the
new `compute_financial_health` engine so the math has a single source of
truth.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.financial_health import compute_financial_health, SEGMENTS

from .aggregations import (
    _deals_in_scope, _deal_revenue, _deal_cost, _deal_owner, _num, _days_ago,
)

logger = logging.getLogger("bibi.wave12.b_aggregations")


# ───────────────────── per-deal pre-load helpers ───────────────────────────
async def _load_deal_money(db, deal_ids: List[str]):
    """Return two dicts keyed by deal_id: deposits[] and payments[]."""
    deposits: Dict[str, List[Dict[str, Any]]] = {}
    payments: Dict[str, List[Dict[str, Any]]] = {}
    if not deal_ids:
        return deposits, payments

    try:
        async for dep in db.legal_deposits.find(
            {"deal_id": {"$in": deal_ids}}, {"_id": 0}
        ):
            deposits.setdefault(dep["deal_id"], []).append(dep)
    except Exception as e:
        logger.warning("[wave12b] legal_deposits load failed: %s", e)
    try:
        async for pay in db.payments.find(
            {"deal_id": {"$in": deal_ids}}, {"_id": 0}
        ):
            payments.setdefault(pay["deal_id"], []).append(pay)
    except Exception as e:
        logger.warning("[wave12b] payments load failed: %s", e)
    return deposits, payments


# ───────────────────── Revenue at Risk ─────────────────────────────────────
async def compute_revenue_at_risk(db, scope: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate revenue at risk across all visible deals.

    Buckets follow the financial_health segments. "At risk total" is the
    sum of `outstanding` for deals in segments warning + at_risk + critical
    (NOT for healthy or cancelled).
    """
    deals = await _deals_in_scope(db, scope)
    deal_ids = [d["id"] for d in deals if d.get("id")]
    deposits_by, payments_by = await _load_deal_money(db, deal_ids)

    by_segment: Dict[str, Dict[str, Any]] = {
        s: {"count": 0, "outstanding": 0.0, "revenue": 0.0} for s in SEGMENTS
    }
    at_risk_total = 0.0
    at_risk_revenue = 0.0
    deals_at_risk_ids: List[str] = []

    for d in deals:
        h = compute_financial_health(
            d, deposits_by.get(d["id"], []), payments_by.get(d["id"], [])
        )
        seg = h["segment"]
        if seg not in by_segment:
            continue  # e.g. "cancelled"
        outstanding = h["metrics"]["outstanding"]
        revenue     = h["metrics"]["expected"]
        by_segment[seg]["count"]       += 1
        by_segment[seg]["outstanding"] += outstanding
        by_segment[seg]["revenue"]     += revenue
        if seg in {"warning", "at_risk", "critical"}:
            at_risk_total   += outstanding
            at_risk_revenue += revenue
            deals_at_risk_ids.append(d["id"])

    # Round
    for v in by_segment.values():
        v["outstanding"] = round(v["outstanding"], 2)
        v["revenue"]     = round(v["revenue"], 2)

    return {
        "at_risk_total":   round(at_risk_total, 2),
        "at_risk_revenue": round(at_risk_revenue, 2),
        "by_segment":      by_segment,
        "deals_at_risk":   len(deals_at_risk_ids),
        "currency":        "EUR",
    }


# ───────────────────── Manager P&L table ───────────────────────────────────
async def compute_manager_finance(db, scope: Dict[str, Any]) -> Dict[str, Any]:
    """Per-manager financial dashboard.

    For each manager-id with at least one deal in scope:
        revenue / profit / deals / outstanding / at_risk / avg_collection_days
        / health (worst segment across their deals)
    Sorted by `at_risk` DESC by default.
    """
    deals = await _deals_in_scope(db, scope)
    deal_ids = [d["id"] for d in deals if d.get("id")]
    deposits_by, payments_by = await _load_deal_money(db, deal_ids)

    # Group by owner
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in deals:
        owner = _deal_owner(d) or "_unassigned"
        groups.setdefault(owner, []).append(d)

    # Resolve owner display names from staff
    staff_lookup: Dict[str, Dict[str, Any]] = {}
    try:
        async for raw in db.staff.find(
            {"$or": [
                {"id": {"$in": list(groups.keys())}},
                {"managerId": {"$in": list(groups.keys())}},
                {"email": {"$in": list(groups.keys())}},
            ]},
            {"_id": 0, "id": 1, "managerId": 1, "email": 1, "name": 1, "full_name": 1, "role": 1},
        ):
            for k in ("id", "managerId", "email"):
                if raw.get(k):
                    staff_lookup[raw[k]] = raw
    except Exception:
        pass

    rows: List[Dict[str, Any]] = []
    severity = {"healthy": 0, "warning": 1, "at_risk": 2, "critical": 3, "cancelled": -1}

    for owner, owner_deals in groups.items():
        revenue = 0.0
        cost    = 0.0
        profit  = 0.0
        outstanding_sum = 0.0
        at_risk_sum     = 0.0
        worst_seg = "healthy"
        collection_days_samples: List[int] = []
        seg_counts = {s: 0 for s in SEGMENTS}

        for d in owner_deals:
            revenue += _deal_revenue(d)
            cost    += _deal_cost(d)
            p = _num(d.get("profit") or d.get("realProfit"))
            if not p and _deal_revenue(d) and _deal_cost(d):
                p = _deal_revenue(d) - _deal_cost(d)
            profit += p

            h = compute_financial_health(
                d, deposits_by.get(d["id"], []), payments_by.get(d["id"], [])
            )
            seg = h["segment"]
            outstanding_sum += h["metrics"]["outstanding"]
            if seg in {"warning", "at_risk", "critical"}:
                at_risk_sum += h["metrics"]["outstanding"]
            if seg in seg_counts:
                seg_counts[seg] += 1
            if severity.get(seg, 0) > severity.get(worst_seg, 0):
                worst_seg = seg

            # Avg collection days = days since deposit_paid_at for delivered
            # OR days since updated_at for open deals with non-zero outstanding
            if h["metrics"]["outstanding"] > 0:
                d_days = _days_ago(d.get("updated_at") or d.get("created_at"))
                if d_days is not None:
                    collection_days_samples.append(d_days)

        avg_coll = (
            round(sum(collection_days_samples) / len(collection_days_samples), 1)
            if collection_days_samples else None
        )

        staff = staff_lookup.get(owner) or {}
        display = staff.get("name") or staff.get("full_name") or staff.get("email") or (
            owner if owner != "_unassigned" else "Unassigned"
        )

        rows.append({
            "manager_id":  None if owner == "_unassigned" else owner,
            "manager_name": display,
            "email":       staff.get("email"),
            "role":        staff.get("role"),
            "deals":       len(owner_deals),
            "revenue":     round(revenue, 2),
            "profit":      round(profit, 2),
            "outstanding": round(outstanding_sum, 2),
            "at_risk":     round(at_risk_sum, 2),
            "avg_collection_days": avg_coll,
            "financial_health":    worst_seg,
            "segment_counts":      seg_counts,
        })

    rows.sort(key=lambda r: (r.get("at_risk") or 0, r.get("outstanding") or 0), reverse=True)
    return {
        "items":    rows,
        "currency": "EUR",
        "total":    len(rows),
    }


# ───────────────────── Collections queue ────────────────────────────────────
async def compute_collections_queue(
    db,
    scope: Dict[str, Any],
    *,
    min_days_overdue: int = 7,
    limit: int = 200,
) -> Dict[str, Any]:
    """Deals that need active follow-up by collections team.

    Inclusion rule: `outstanding > 0 AND (days_since_move >= min_days_overdue
    OR financial_health.segment != healthy)`.

    Sorted with the worst segments first (critical → at_risk → warning),
    then by `days_overdue` desc, then by `outstanding` desc.
    """
    deals = await _deals_in_scope(db, scope)
    deal_ids = [d["id"] for d in deals if d.get("id")]
    deposits_by, payments_by = await _load_deal_money(db, deal_ids)

    # Customer name resolution
    customer_cache: Dict[str, str] = {}

    async def resolve_customer(cid: Optional[str]) -> Optional[str]:
        if not cid:
            return None
        if cid in customer_cache:
            return customer_cache[cid]
        try:
            doc = await db.customers.find_one(
                {"$or": [{"id": cid}, {"_id": cid}]},
                {"_id": 0, "name": 1, "first_name": 1, "last_name": 1, "email": 1},
            )
        except Exception:
            doc = None
        if not doc:
            customer_cache[cid] = ""
            return None
        name = (doc.get("name") or " ".join(
            x for x in (doc.get("first_name"), doc.get("last_name")) if x
        ) or doc.get("email") or "")
        customer_cache[cid] = name
        return name

    seg_priority = {"critical": 0, "at_risk": 1, "warning": 2, "healthy": 3, "cancelled": 9}
    rows: List[Dict[str, Any]] = []
    total_outstanding = 0.0
    by_segment_count = {"critical": 0, "at_risk": 0, "warning": 0}

    for d in deals:
        h = compute_financial_health(
            d, deposits_by.get(d["id"], []), payments_by.get(d["id"], [])
        )
        seg = h["segment"]
        outstanding = h["metrics"]["outstanding"]
        if outstanding <= 0:
            continue
        if seg in {"healthy", "cancelled"} and h["metrics"]["days_since_move"] < min_days_overdue:
            continue

        last_move = d.get("updated_at") or d.get("created_at")
        rows.append({
            "deal_id":          d["id"],
            "deal_title":       d.get("title") or "",
            "vin":              d.get("vin"),
            "stage":            d.get("pipeline_stage") or d.get("stage") or d.get("status"),
            "customer_id":      d.get("customer_id") or d.get("customerId"),
            "manager_id":       _deal_owner(d),
            "currency":         d.get("currency") or "EUR",
            "expected":         h["metrics"]["expected"],
            "received":         h["metrics"]["received"],
            "outstanding":      h["metrics"]["outstanding"],
            "outstanding_ratio": h["metrics"]["outstanding_ratio"],
            "days_overdue":     h["metrics"]["days_since_move"],
            "financial_health": seg,
            "health_score":     h["score"],
            "reasons":          h["reasons"],
            "last_move":        last_move,
        })
        total_outstanding += outstanding
        if seg in by_segment_count:
            by_segment_count[seg] += 1

    rows.sort(key=lambda r: (
        seg_priority.get(r.get("financial_health"), 9),
        -(r.get("days_overdue") or 0),
        -(r.get("outstanding") or 0),
    ))
    rows = rows[:limit]
    for r in rows:
        r["customer_name"] = await resolve_customer(r.get("customer_id"))

    return {
        "items":   rows,
        "total":   len(rows),
        "summary": {
            "outstanding": round(total_outstanding, 2),
            "deals":       len(rows),
            "by_segment":  by_segment_count,
        },
    }
