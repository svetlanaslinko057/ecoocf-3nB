"""
BIBI Cars — Wave 16 — Executive Center aggregations
=====================================================

This module is a *thin orchestrator*. Every primitive (financial / delivery
/ contract / lead health, forecast, team performance) is already implemented
in Wave 12C / 13 / 14 / 15. The functions below just compose them into the
5 tabs of the Executive Center.

0 new collections · 0 writes · 0 AI.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from collections import defaultdict

# Wave 14 (Operations 360 / SLA / Risk Center / Team Performance).
from app.wave14.aggregations import (
    compute_company_dashboard, compute_bottlenecks, compute_risk_center,
    compute_team_performance,
)

# Wave 12C (Forecasting 360).
from app.wave12.forecasting import (
    compute_forecast_overview, compute_revenue_forecast,
)

# Wave 15 (Contract 360).
from app.wave15.aggregations import (
    compute_contracts_overview, compute_contract_risk,
)
from app.wave15.contract_health import compute_contract_health


SEVERITY_RANK = {
    "critical": 0, "at_risk": 1, "unsigned": 1, "wrong_version": 2,
    "missing_annex": 2, "delay_risk": 2, "warning": 3, "delayed": 3,
    "pending_approval": 3, "draft": 4, "on_track": 5, "healthy": 5,
    "delivered": 6, "cancelled": 7, "archived": 7,
}


# ═════════════════════════════════════════════════════════════════
# 1. EXECUTIVE DASHBOARD
# ═════════════════════════════════════════════════════════════════
async def compute_executive_dashboard(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 1 — "What is happening in the company today?"

    Base tiles come from Wave 14 (`compute_company_dashboard`); we augment
    them with Contract360 and Forecast360 tiles.
    """
    base = await compute_company_dashboard(db, user)
    base_tiles = base.get("tiles", {})

    # ----- Contract360 tiles --------------------------------------------
    contracts_ov = await compute_contracts_overview(db, user)
    c_totals = contracts_ov.get("totals", {}) or {}
    unsigned_contracts  = int(c_totals.get("overdue_signature", 0))
    pending_approvals   = int(c_totals.get("pending_approvals", 0))
    expiring_contracts  = int(c_totals.get("expiring_soon", 0))
    active_contracts    = int(c_totals.get("healthy_count", 0))
    unsigned_value      = float(c_totals.get("unsigned_value", 0))

    # ----- Forecast tiles -----------------------------------------------
    forecast_ov = await compute_forecast_overview(db, user)
    horizons = (forecast_ov.get("how_much", {}) or {}).get("horizons", {})
    rev_at_risk = float((forecast_ov.get("derail") or {}).get("risk_total", 0))

    # ----- Customers ----------------------------------------------------
    # Active customers = distinct customer_id appearing on active deals.
    # Cheap to compute on top of what Wave14 already loaded.
    scope_filter = None
    if not (user.get("role") in ("master_admin", "admin", "owner")):
        # cheap-enough lookup to avoid double-loading staff: rely on deals
        mgr = user.get("id") or user.get("managerId") or user.get("sub")
        scope_filter = {"$or": [{"managerId": mgr}, {"manager_id": mgr}]}

    active_customer_ids = set()
    async for d in db.deals.find(scope_filter or {}, {"_id": 0, "customer_id": 1, "stage": 1, "status": 1}):
        stage = (d.get("stage") or "").lower()
        st    = (d.get("status") or "").lower()
        if stage in ("delivered", "won", "closed_won") or st == "cancelled":
            continue
        cid = d.get("customer_id")
        if cid:
            active_customer_ids.add(cid)

    tiles = {
        # Pipeline volume
        "active_leads":       base_tiles.get("active_leads", 0),
        "active_customers":   len(active_customer_ids),
        "active_deals":       base_tiles.get("active_deals", 0),
        # Money MTD
        "revenue_mtd":        base_tiles.get("revenue_mtd", 0),
        "profit_mtd":         base_tiles.get("profit_mtd", 0),
        "outstanding":        base_tiles.get("outstanding", 0),
        "collections":        base_tiles.get("collections", 0),
        # Delivery
        "cars_in_transit":      base_tiles.get("cars_in_transit", 0),
        "critical_deliveries":  base_tiles.get("critical_deliveries", 0),
        # Contract360
        "unsigned_contracts":   unsigned_contracts,
        "pending_approvals":    pending_approvals,
        "expiring_contracts":   expiring_contracts,
        "active_contracts":     active_contracts,
        "unsigned_value":       round(unsigned_value, 2),
        # Forecast
        "revenue_at_risk":      round(rev_at_risk, 2),
    }

    return {
        "as_of":    datetime.now(timezone.utc).isoformat(),
        "tiles":    tiles,
        "horizons": {h: horizons.get(h, {}) for h in ("30", "60", "90")},
        "scope":    base.get("scope", {}),
        "currency": base.get("currency", "EUR"),
    }


# ═════════════════════════════════════════════════════════════════
# 2. FORECAST PANEL (proxies Wave 12C)
# ═════════════════════════════════════════════════════════════════
async def compute_executive_forecast(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 2 — 30 / 60 / 90 outlook.

    Composes Forecast360.overview (which already returns the three horizons)
    with the revenue forecast roll-up so the Executive Center can render
    Expected Revenue / Profit / Cash / Pipeline / Risk side-by-side.
    """
    ov = await compute_forecast_overview(db, user)
    revenue = await compute_revenue_forecast(db, user)
    horizons = (ov.get("how_much") or {}).get("horizons", {}) or {}
    derail   = ov.get("derail") or {}

    # Per-horizon: weighted, gross (= expected revenue), profit (= expected profit)
    out: Dict[str, Dict[str, Any]] = {}
    for h in ("30", "60", "90"):
        b = horizons.get(h) or {}
        out[h] = {
            "expected_revenue": round(float(b.get("gross")    or 0), 2),
            "expected_profit":  round(float(b.get("profit")   or 0), 2),
            "weighted_revenue": round(float(b.get("weighted") or 0), 2),
            "pipeline_value":   round(float(b.get("gross")    or 0), 2),
            "deals":            int(b.get("deals") or 0),
        }

    cashflow_weeks = (ov.get("when") or {}).get("weeks") or []
    cashflow_total_in  = round(sum(float(w.get("cash_in")  or 0) for w in cashflow_weeks), 2)
    cashflow_total_out = round(sum(float(w.get("cash_out") or 0) for w in cashflow_weeks), 2)

    return {
        "as_of":           datetime.now(timezone.utc).isoformat(),
        "horizons":        out,
        "weeks":           cashflow_weeks,
        "cash_in_total":   cashflow_total_in,
        "cash_out_total":  cashflow_total_out,
        "forecast_risk":   {
            "value":      round(float(derail.get("risk_total")     or 0), 2),
            "share_pct":  round(float(derail.get("risk_share_pct") or 0), 2),
            "by_kind":    derail.get("by_kind")  or {},
            "top_items":  derail.get("top_items") or [],
        },
        "by_stage":        revenue.get("by_stage") or {},
        "scope":           ov.get("scope") or {},
        "currency":        ov.get("currency") or "EUR",
    }


# ═════════════════════════════════════════════════════════════════
# 3. BOTTLENECKS (unified)
# ═════════════════════════════════════════════════════════════════
async def compute_executive_bottlenecks(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 3 — unified Type / Severity / Owner / Impact € / Reason / Action table.

    Sources: Wave14.compute_bottlenecks  (operations buckets)
           + Wave15.compute_contract_risk (contract buckets)
           + Finance / Delivery risk from Wave14.compute_risk_center.
    """
    # 1) Ops buckets (waiting_deposit / no_carrier / customs / port / etc.)
    ops = await compute_bottlenecks(db, user)

    # 2) Risk feed (already segmented; we extract «impact» by joining with deals)
    risk = await compute_risk_center(db, user)

    # 3) Contract risk
    contract = await compute_contract_risk(db, user, limit=300)

    # Build a quick deal map for impact (€) on financial / delivery items
    deals = await db.deals.find({}, {"_id": 0, "id": 1, "price": 1, "final_price": 1,
                                       "profit": 1, "cost": 1,
                                       "manager_name": 1, "managerName": 1,
                                       "title": 1}).to_list(length=5000)
    deal_by_id = {d.get("id"): d for d in deals if d.get("id")}

    rows: List[Dict[str, Any]] = []

    # ── Ops bucket rows ──────────────────────────────────────────
    OPS_LABEL_ACTION = {
        "waiting_deposit":   "Chase deposit",
        "waiting_payment":   "Chase payment",
        "no_carrier":        "Assign carrier",
        "stuck_at_customs":  "Escalate customs",
        "stuck_at_port":     "Push port handler",
        "missing_documents": "Upload documents",
        "stale_no_movement": "Manager call",
        "financial_at_risk": "Trigger collection",
    }
    OPS_SEVERITY = {
        "waiting_deposit":   "at_risk",
        "waiting_payment":   "warning",
        "no_carrier":        "at_risk",
        "stuck_at_customs":  "critical",
        "stuck_at_port":     "at_risk",
        "missing_documents": "warning",
        "stale_no_movement": "warning",
        "financial_at_risk": "critical",
    }
    for k, bucket in (ops.get("buckets") or {}).items():
        for did in (bucket.get("deal_ids") or [])[:60]:
            d = deal_by_id.get(did) or {}
            impact = float(d.get("price") or d.get("final_price") or 0)
            rows.append({
                "type":      "operations",
                "sub_type":  k,
                "severity":  OPS_SEVERITY.get(k, "warning"),
                "owner":     d.get("manager_name") or d.get("managerName") or "Unassigned",
                "entity_id": did,
                "label":     d.get("title") or did,
                "impact":    round(impact, 2),
                "reason":    bucket.get("label") or k,
                "action":    OPS_LABEL_ACTION.get(k, "Investigate"),
                "href":      f"/admin/deals/{did}/360" if did else None,
            })

    # ── Finance / Delivery from risk_center ───────────────────────────
    for it in risk.get("items") or []:
        kind = it.get("risk_kind") or ""
        if kind in ("financial", "delivery", "lead_cold"):
            d = deal_by_id.get(it.get("entity_id"))
            impact = 0.0
            if d:
                impact = float(d.get("price") or d.get("final_price") or 0)
            rows.append({
                "type":     kind if kind in ("financial", "delivery") else "lead",
                "sub_type": kind,
                "severity": it.get("segment") or "warning",
                "owner":    it.get("manager") or "Unassigned",
                "entity_id": it.get("entity_id"),
                "label":    it.get("label"),
                "impact":   round(impact, 2),
                "reason":   (it.get("reasons") or [""])[0],
                "action":   {"financial":  "Collection workflow",
                              "delivery":   "Operations escalation",
                              "lead_cold":  "Reactivate lead"}.get(kind, "Investigate"),
                "href":     it.get("href"),
            })

    # ── Contract bottlenecks ─────────────────────────────────────────
    CONTRACT_ACTION = {
        "unsigned":         "Chase signature",
        "pending_approval": "Approve internally",
        "missing_annex":    "Upload annex",
        "wrong_version":    "Replace with current",
        "critical":         "Renew or archive",
        "draft":            "Submit for approval",
    }
    for c in contract.get("items") or []:
        rows.append({
            "type":     "contract",
            "sub_type": c.get("segment"),
            "severity": c.get("segment"),
            "owner":    c.get("manager_name") or "Unassigned",
            "entity_id": c.get("id"),
            "label":    c.get("title") or c.get("id"),
            "impact":   round(float(c.get("amount") or 0), 2),
            "reason":   (c.get("reasons") or [""])[0],
            "action":   CONTRACT_ACTION.get(c.get("segment"), "Review"),
            "href":     f"/admin/contracts?id={c.get('id')}&tab=timeline",
        })

    # severity sort, then impact desc
    rows.sort(key=lambda r: (SEVERITY_RANK.get(r["severity"], 9), -float(r["impact"] or 0)))

    # roll-ups
    by_type:     Dict[str, int]   = defaultdict(int)
    by_severity: Dict[str, int]   = defaultdict(int)
    impact_total = 0.0
    impact_critical = 0.0
    for r in rows:
        by_type[r["type"]] += 1
        by_severity[r["severity"]] += 1
        imp = float(r["impact"] or 0)
        impact_total += imp
        if r["severity"] == "critical":
            impact_critical += imp

    return {
        "as_of":            datetime.now(timezone.utc).isoformat(),
        "items":            rows[:400],
        "total":            len(rows),
        "by_type":          dict(by_type),
        "by_severity":      dict(by_severity),
        "impact_total":     round(impact_total, 2),
        "impact_critical":  round(impact_critical, 2),
        "scope":            ops.get("scope") or {},
        "currency":         "EUR",
    }


# ═════════════════════════════════════════════════════════════════
# 4. EXECUTIVE RISKS (merged)
# ═════════════════════════════════════════════════════════════════
async def compute_executive_risks(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 4 — unified Lead + Financial + Delivery + Contract risk feed."""
    risk_ops = await compute_risk_center(db, user)   # lead_cold / financial / delivery
    risk_con = await compute_contract_risk(db, user, limit=300)

    items: List[Dict[str, Any]] = []
    for it in risk_ops.get("items") or []:
        items.append({
            "entity_type":   it.get("entity_type"),
            "entity_id":     it.get("entity_id"),
            "label":         it.get("label"),
            "href":          it.get("href"),
            "manager":       it.get("manager"),
            "segment":       it.get("segment"),
            "score":         it.get("score"),
            "risk_kind":     it.get("risk_kind"),
            "reasons":       it.get("reasons") or [],
        })
    for c in risk_con.get("items") or []:
        items.append({
            "entity_type":   "contract",
            "entity_id":     c.get("id"),
            "label":         c.get("title") or c.get("id"),
            "href":          f"/admin/contracts?id={c.get('id')}&tab=timeline",
            "manager":       c.get("manager_name"),
            "segment":       c.get("segment"),
            "score":         c.get("score"),
            "risk_kind":     "contract",
            "reasons":       c.get("reasons") or [],
        })

    items.sort(key=lambda x: (SEVERITY_RANK.get(x["segment"], 9), -(x.get("score") or 0)))

    by_kind:    Dict[str, int] = defaultdict(int)
    by_segment: Dict[str, int] = defaultdict(int)
    for it in items:
        by_kind[it["risk_kind"]] += 1
        by_segment[it["segment"]] += 1

    # tri-state grouping (Critical / At Risk / Warning) for headline KPIs
    critical_n = sum(1 for it in items if it["segment"] in ("critical",))
    at_risk_n  = sum(1 for it in items if it["segment"] in ("at_risk", "unsigned", "wrong_version", "missing_annex", "delay_risk"))
    warning_n  = sum(1 for it in items if it["segment"] in ("warning", "delayed", "pending_approval"))

    return {
        "as_of":      datetime.now(timezone.utc).isoformat(),
        "items":      items[:400],
        "total":      len(items),
        "by_kind":    dict(by_kind),
        "by_segment": dict(by_segment),
        "summary":    {"critical": critical_n, "at_risk": at_risk_n, "warning": warning_n},
        "scope":      risk_ops.get("scope") or {},
    }


# ═════════════════════════════════════════════════════════════════
# 5. TEAM PERFORMANCE (extended)
# ═════════════════════════════════════════════════════════════════
async def compute_executive_team(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Tab 5 — Wave14 team rows + Forecast Accuracy & Ops Score extras.

    Forecast accuracy (deterministic, not ML):
        accuracy_pct = 100 * (1 - abs(actual_revenue_mtd - weighted_revenue_30d) / max(weighted_revenue_30d, 1))
        clamped to [0, 100].
    """
    team = await compute_team_performance(db, user)
    rows = list(team.get("items") or [])

    # Per-manager weighted 30d revenue (from Wave 12C).
    revenue = await compute_revenue_forecast(db, user)
    weighted_30_by_mgr: Dict[str, float] = defaultdict(float)
    for it in revenue.get("items") or []:
        if (it.get("days_out") or 0) > 30:
            continue
        mgr = it.get("manager_id") or ""
        weighted_30_by_mgr[mgr] += float(it.get("weighted") or 0)

    # Per-manager contract risk count for an extra column.
    contract_risk = await compute_contract_risk(db, user, limit=400)
    contract_risk_by_mgr: Dict[str, int] = defaultdict(int)
    for c in contract_risk.get("items") or []:
        contract_risk_by_mgr[c.get("manager_id") or ""] += 1

    for r in rows:
        mgr = r.get("manager_id") or ""
        expected = float(weighted_30_by_mgr.get(mgr, 0.0))
        actual   = float(r.get("revenue") or 0.0)
        if expected <= 0:
            r["forecast_accuracy"] = None
            r["forecast_expected_30d"] = 0.0
        else:
            err = abs(actual - expected) / max(expected, 1.0)
            r["forecast_accuracy"] = round(max(0.0, min(100.0, 100.0 * (1.0 - err))), 1)
            r["forecast_expected_30d"] = round(expected, 2)
        r["contracts_at_risk"] = int(contract_risk_by_mgr.get(mgr, 0))

    return {
        "as_of":  datetime.now(timezone.utc).isoformat(),
        "items":  rows,
        "total":  len(rows),
        "scope":  team.get("scope") or {},
        "currency": "EUR",
    }


__all__ = [
    "compute_executive_dashboard",
    "compute_executive_forecast",
    "compute_executive_bottlenecks",
    "compute_executive_risks",
    "compute_executive_team",
]
