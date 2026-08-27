"""
BIBI Cars — Wave 12C — Forecasting 360 aggregations
=====================================================

Pure read-only deterministic forecaster on top of:
  * `deals`              — stage / price / cost / managerId / created_at / delivered_at
  * `deposits`/`payments`— received / expected money flows
  * `shipments`          — ETA, carrier, current milestone
  * Existing health scorers (financial / delivery)

No writes. No new collections. No AI. Scope-aware like everything else
in Wave 12+ (admin = all, team_lead = team, manager = own).

Public surface:
    compute_forecast_overview(db, user)
    compute_revenue_forecast(db, user)
    compute_cashflow_forecast(db, user)
    compute_pipeline_forecast(db, user)
    compute_capacity_forecast(db, user)
    compute_forecast_risk(db, user)
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.services.financial_health import compute_financial_health
from app.services.delivery_health import compute_delivery_health
from app.wave12.forecast_config import (
    stage_probability,
    HORIZONS,
    MAX_HORIZON,
    DEFAULT_PAYMENT_LAG_DAYS,
    MANAGER_TARGET_OPEN_DEALS,
    CARRIER_TARGET_OPEN_LOADS,
    RISK_WEIGHT_BY_SEGMENT,
)

TERMINAL_DEAL_STAGES = {"delivered", "cancelled", "refunded", "closed_won", "closed_lost", "lost"}


# ============================================================================
# Scope + helpers
# ============================================================================
async def _scope_filter(db, user: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    role = (user or {}).get("role")
    if role in ("master_admin", "admin", "owner"):
        return None, {"all": True, "managers": 0}
    if role == "team_lead":
        own_id = user.get("id") or user.get("managerId") or user.get("sub")
        team_ids = await db.staff.find({"team_lead_id": own_id}, {"id": 1, "_id": 0}).to_list(length=500)
        ids = [own_id] + [t.get("id") for t in team_ids if t.get("id")]
        ids = [i for i in ids if i]
        return ({"$or": [{"managerId": {"$in": ids}}, {"manager_id": {"$in": ids}}]},
                {"all": False, "managers": len(ids)})
    mgr = user.get("id") or user.get("managerId") or user.get("sub")
    return ({"$or": [{"managerId": mgr}, {"manager_id": mgr}]},
            {"all": False, "managers": 1})


def _to_dt(v: Any) -> Optional[datetime]:
    if not v: return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _expected_close(d: Dict[str, Any], shipment: Optional[Dict[str, Any]], now: datetime) -> datetime:
    """When do we expect this deal to either pay or deliver?
    Priority: shipment ETA → deal expected_close_at → created_at + lag → now + lag.
    """
    if shipment:
        delivery = shipment.get("delivery") or {}
        eta = _to_dt(delivery.get("eta_expected")) or _to_dt(delivery.get("eta_actual"))
        if eta:
            return eta
    expected = _to_dt(d.get("expected_close_at")) or _to_dt(d.get("expected_delivery_at"))
    if expected:
        return expected
    created = _to_dt(d.get("created_at"))
    if created:
        return created + timedelta(days=DEFAULT_PAYMENT_LAG_DAYS)
    return now + timedelta(days=DEFAULT_PAYMENT_LAG_DAYS)


def _amount(d: Dict[str, Any]) -> float:
    return float(d.get("price") or d.get("final_price") or d.get("sale_price") or 0.0)


def _profit(d: Dict[str, Any]) -> float:
    return float(d.get("profit") or (_amount(d) - float(d.get("cost") or 0.0)))


async def _load_scope(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """One pass loader — returns everything needed across all 6 endpoints.
    Kept here so each endpoint stays a thin call site."""
    scope_filter, scope_meta = await _scope_filter(db, user)
    f = dict(scope_filter or {})
    deals = await db.deals.find(f, {"_id": 0}).to_list(length=5000)
    deal_ids = [d.get("id") for d in deals if d.get("id")]
    deposits = await db.deposits.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    payments = await db.payments.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    shipments = await db.shipments.find({"$or": [{"deal_id": {"$in": deal_ids}}, {"dealId": {"$in": deal_ids}}]} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    docs = await db.delivery_documents.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=10000) if deal_ids else []
    deps_by_deal = defaultdict(list); [deps_by_deal[x.get("deal_id")].append(x) for x in deposits]
    pays_by_deal = defaultdict(list); [pays_by_deal[x.get("deal_id")].append(x) for x in payments]
    ship_by_deal: Dict[str, Dict[str, Any]] = {}
    for s in shipments:
        ship_by_deal[s.get("deal_id") or s.get("dealId")] = s
    docs_by_ship = defaultdict(list); [docs_by_ship[x.get("shipment_id")].append(x) for x in docs]
    return {
        "deals": deals, "deposits": deposits, "payments": payments,
        "shipments": shipments, "deps_by_deal": deps_by_deal,
        "pays_by_deal": pays_by_deal, "ship_by_deal": ship_by_deal,
        "docs_by_ship": docs_by_ship, "scope": scope_meta,
    }


# ============================================================================
# 1. REVENUE FORECAST
# ============================================================================
async def compute_revenue_forecast(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    ctx = await _load_scope(db, user)

    horizons_buckets = {h: {"deals": 0, "weighted": 0.0, "gross": 0.0, "profit": 0.0} for h in HORIZONS}
    rows: List[Dict[str, Any]] = []
    for d in ctx["deals"]:
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES and stage != "closed_won" and stage != "delivered":
            continue
        if (d.get("status") or "").lower() == "cancelled":
            continue
        prob = stage_probability(stage)
        if prob <= 0:
            continue
        ship = ctx["ship_by_deal"].get(d.get("id"))
        close = _expected_close(d, ship, now)
        days_out = max(0, int((close - now).total_seconds() // 86400))
        gross  = _amount(d)
        profit = _profit(d)
        weighted = gross * prob
        rows.append({
            "deal_id":     d.get("id"),
            "deal_title":  d.get("title") or d.get("vehicle_label") or d.get("id"),
            "stage":       stage or "unknown",
            "manager_id":  d.get("managerId") or d.get("manager_id"),
            "manager_name":d.get("manager_name") or d.get("managerName"),
            "gross":       round(gross, 2),
            "profit":      round(profit, 2),
            "probability": round(prob, 3),
            "weighted":    round(weighted, 2),
            "weighted_profit": round(profit * prob, 2),
            "days_out":    days_out,
            "expected_close": close.isoformat(),
        })
        for h in HORIZONS:
            if days_out <= h:
                horizons_buckets[h]["deals"]    += 1
                horizons_buckets[h]["weighted"] += weighted
                horizons_buckets[h]["gross"]    += gross
                horizons_buckets[h]["profit"]   += profit * prob

    # Sort rows by largest weighted contribution first
    rows.sort(key=lambda r: -r["weighted"])

    # Aggregate by stage (for the funnel sub-chart)
    by_stage: Dict[str, Dict[str, float]] = {}
    for r in rows:
        b = by_stage.setdefault(r["stage"], {"deals": 0, "gross": 0.0, "weighted": 0.0, "probability": r["probability"]})
        b["deals"]   += 1
        b["gross"]   += r["gross"]
        b["weighted"]+= r["weighted"]

    # Round + finalise the horizon buckets
    for h, b in horizons_buckets.items():
        b["weighted"] = round(b["weighted"], 2)
        b["gross"]    = round(b["gross"], 2)
        b["profit"]   = round(b["profit"], 2)

    return {
        "as_of":     now.isoformat(),
        "horizons":  {str(h): horizons_buckets[h] for h in HORIZONS},
        "by_stage":  {k: {**v, "weighted": round(v["weighted"], 2), "gross": round(v["gross"], 2)}
                      for k, v in sorted(by_stage.items(), key=lambda kv: -kv[1]["weighted"])},
        "items":     rows[:200],
        "total_deals": len(rows),
        "scope":     ctx["scope"],
        "currency":  "EUR",
    }


# ============================================================================
# 2. CASH FLOW FORECAST
# ============================================================================
async def compute_cashflow_forecast(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    ctx = await _load_scope(db, user)

    # 13 weekly buckets covering the next ~90 days
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    weeks: List[Dict[str, Any]] = []
    for i in range(13):
        week_start = start + timedelta(weeks=i)
        week_end   = week_start + timedelta(days=7)
        weeks.append({
            "week":     i,
            "start":    week_start.isoformat(),
            "end":      week_end.isoformat(),
            "cash_in":  0.0,
            "cash_out": 0.0,
            "net":      0.0,
            "deals_in": 0,
        })

    def _bucket(when: datetime) -> Optional[int]:
        if when < start:
            return 0     # treat overdue as “this week” so it shows up
        idx = int((when - start).days // 7)
        return idx if 0 <= idx < len(weeks) else None

    # ---- Cash-in: expected revenue from open deals weighted by probability
    for d in ctx["deals"]:
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES:
            continue
        if (d.get("status") or "").lower() == "cancelled":
            continue
        prob = stage_probability(stage)
        if prob <= 0:
            continue
        ship = ctx["ship_by_deal"].get(d.get("id"))
        close = _expected_close(d, ship, now)
        idx = _bucket(close)
        if idx is None:
            continue
        deps = ctx["deps_by_deal"].get(d.get("id"), [])
        pays = ctx["pays_by_deal"].get(d.get("id"), [])
        fh = compute_financial_health(d, deps, pays)
        outstanding = float((fh.get("metrics") or {}).get("outstanding") or 0.0)
        amount = outstanding or _amount(d)
        weighted = amount * prob
        weeks[idx]["cash_in"] += weighted
        weeks[idx]["deals_in"] += 1

    # ---- Cash-out: carrier / customs cost. We don't track those explicitly,
    # so we use deal.cost as a *gross outflow proxy*, weighted by stage probability
    # and bucketed by ETA.
    for d in ctx["deals"]:
        cost = float(d.get("cost") or 0.0)
        if cost <= 0:
            continue
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES and stage != "delivered":
            continue
        prob = stage_probability(stage)
        if prob <= 0:
            continue
        ship = ctx["ship_by_deal"].get(d.get("id"))
        close = _expected_close(d, ship, now)
        idx = _bucket(close)
        if idx is None:
            continue
        weeks[idx]["cash_out"] += cost * prob

    cash_in_total  = 0.0
    cash_out_total = 0.0
    for w in weeks:
        w["cash_in"]  = round(w["cash_in"], 2)
        w["cash_out"] = round(w["cash_out"], 2)
        w["net"]      = round(w["cash_in"] - w["cash_out"], 2)
        cash_in_total  += w["cash_in"]
        cash_out_total += w["cash_out"]

    # Running balance projection (cumulative net), useful for the area chart
    running = 0.0
    for w in weeks:
        running += w["net"]
        w["running_balance"] = round(running, 2)

    return {
        "as_of":   now.isoformat(),
        "weeks":   weeks,
        "totals":  {
            "cash_in":  round(cash_in_total, 2),
            "cash_out": round(cash_out_total, 2),
            "net":      round(cash_in_total - cash_out_total, 2),
        },
        "scope":   ctx["scope"],
        "currency":"EUR",
    }


# ============================================================================
# 3. PIPELINE FORECAST
# ============================================================================
async def compute_pipeline_forecast(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    ctx = await _load_scope(db, user)

    # Stage buckets x time horizon buckets
    stage_rows: Dict[str, Dict[str, Any]] = {}
    month_buckets: Dict[str, Dict[str, Any]] = {}
    quarter_buckets: Dict[str, Dict[str, Any]] = {}

    def _q_label(d: datetime) -> str:
        return f"{d.year}-Q{((d.month - 1) // 3) + 1}"

    def _m_label(d: datetime) -> str:
        return d.strftime("%Y-%m")

    for d in ctx["deals"]:
        stage = (d.get("stage") or "").lower() or "unknown"
        if stage in TERMINAL_DEAL_STAGES:
            continue
        if (d.get("status") or "").lower() == "cancelled":
            continue
        prob = stage_probability(stage)
        if prob <= 0:
            continue
        gross = _amount(d)
        weighted = gross * prob
        ship = ctx["ship_by_deal"].get(d.get("id"))
        close = _expected_close(d, ship, now)

        sb = stage_rows.setdefault(stage, {
            "stage":       stage,
            "probability": round(prob, 3),
            "deals":       0,
            "gross":       0.0,
            "weighted":    0.0,
        })
        sb["deals"]    += 1
        sb["gross"]    += gross
        sb["weighted"] += weighted

        m = month_buckets.setdefault(_m_label(close),
                                     {"period": _m_label(close), "deals": 0,
                                      "gross": 0.0, "weighted": 0.0})
        m["deals"]    += 1
        m["gross"]    += gross
        m["weighted"] += weighted

        q = quarter_buckets.setdefault(_q_label(close),
                                       {"period": _q_label(close), "deals": 0,
                                        "gross": 0.0, "weighted": 0.0})
        q["deals"]    += 1
        q["gross"]    += gross
        q["weighted"] += weighted

    def _round(rows):
        for r in rows:
            r["gross"]    = round(r["gross"], 2)
            r["weighted"] = round(r["weighted"], 2)
        return rows

    return {
        "as_of":      now.isoformat(),
        "by_stage":   _round(sorted(stage_rows.values(), key=lambda r: -r["weighted"])),
        "by_month":   _round(sorted(month_buckets.values(),   key=lambda r: r["period"])),
        "by_quarter": _round(sorted(quarter_buckets.values(), key=lambda r: r["period"])),
        "scope":      ctx["scope"],
        "currency":   "EUR",
    }


# ============================================================================
# 4. CAPACITY FORECAST
# ============================================================================
async def compute_capacity_forecast(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    ctx = await _load_scope(db, user)

    # ---- Manager load ----------------------------------------------------
    mgr_rows: Dict[str, Dict[str, Any]] = {}
    staff = await db.staff.find({}, {"_id": 0}).to_list(length=1000)
    by_id = {s.get("id"): s for s in staff}

    for d in ctx["deals"]:
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES:
            continue
        if (d.get("status") or "").lower() == "cancelled":
            continue
        mgr = d.get("managerId") or d.get("manager_id")
        key = mgr or "__unassigned__"
        m = mgr_rows.setdefault(key, {
            "manager_id":  mgr,
            "manager_name": (by_id.get(mgr) or {}).get("name")
                            or (by_id.get(mgr) or {}).get("email")
                            or ("Unassigned" if not mgr else mgr),
            "open_deals":  0,
            "target":      MANAGER_TARGET_OPEN_DEALS,
            "weighted_pipeline": 0.0,
        })
        m["open_deals"]         += 1
        m["weighted_pipeline"]  += _amount(d) * stage_probability(stage)

    for m in mgr_rows.values():
        m["weighted_pipeline"] = round(m["weighted_pipeline"], 2)
        m["utilization"] = round(min(100, (m["open_deals"] / max(m["target"], 1)) * 100), 1)
        if m["utilization"] >= 100:
            m["status"] = "overloaded"
        elif m["utilization"] >= 80:
            m["status"] = "high"
        elif m["utilization"] >= 40:
            m["status"] = "healthy"
        else:
            m["status"] = "low"

    # ---- Carrier load ---------------------------------------------------
    car_rows: Dict[str, Dict[str, Any]] = {}
    for s in ctx["shipments"]:
        delivery = s.get("delivery") or {}
        if delivery.get("cancelled"): continue
        cm = delivery.get("current_milestone")
        if cm == "delivered": continue
        cid = delivery.get("carrier_id") or "__unassigned__"
        cname = delivery.get("carrier_name") or "Unassigned"
        c = car_rows.setdefault(cid, {
            "carrier_id":   delivery.get("carrier_id"),
            "carrier_name": cname,
            "open_loads":   0,
            "target":       CARRIER_TARGET_OPEN_LOADS,
        })
        c["open_loads"] += 1

    for c in car_rows.values():
        c["utilization"] = round(min(100, (c["open_loads"] / max(c["target"], 1)) * 100), 1)
        c["status"] = "overloaded" if c["utilization"] >= 100 else "high" if c["utilization"] >= 80 else "healthy" if c["utilization"] >= 40 else "low"

    return {
        "as_of":       now.isoformat(),
        "managers":    sorted(mgr_rows.values(),  key=lambda r: -r["utilization"]),
        "carriers":    sorted(car_rows.values(),  key=lambda r: -r["utilization"]),
        "manager_target": MANAGER_TARGET_OPEN_DEALS,
        "carrier_target": CARRIER_TARGET_OPEN_LOADS,
        "scope":       ctx["scope"],
    }


# ============================================================================
# 5. FORECAST RISK
# ============================================================================
async def compute_forecast_risk(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """How much of the forecast is parked on deals that already show health
    flags (financial warning/at_risk/critical OR delivery delay_risk/delayed/critical)."""
    now = datetime.now(timezone.utc)
    ctx = await _load_scope(db, user)

    forecast_total = 0.0
    risk_total     = 0.0
    by_kind = {"financial": 0.0, "delivery": 0.0}
    items: List[Dict[str, Any]] = []

    for d in ctx["deals"]:
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES: continue
        if (d.get("status") or "").lower() == "cancelled": continue
        prob = stage_probability(stage)
        if prob <= 0: continue
        gross    = _amount(d)
        weighted = gross * prob
        forecast_total += weighted

        deps = ctx["deps_by_deal"].get(d.get("id"), [])
        pays = ctx["pays_by_deal"].get(d.get("id"), [])
        fh = compute_financial_health(d, deps, pays)
        fh_seg = fh.get("segment")

        ship = ctx["ship_by_deal"].get(d.get("id"))
        dh = compute_delivery_health(
            ship,
            documents=ctx["docs_by_ship"].get((ship or {}).get("id"), []),
            deal=d,
        ) if ship else None
        dh_seg = (dh or {}).get("segment") if dh else None

        # Pick the WORST risk weight between the two healths
        w_f = RISK_WEIGHT_BY_SEGMENT.get(fh_seg or "", 0.0)
        w_d = RISK_WEIGHT_BY_SEGMENT.get(dh_seg or "", 0.0)
        weight = max(w_f, w_d)
        if weight <= 0:
            continue

        at_risk_amount = weighted * weight
        risk_total    += at_risk_amount
        if w_f >= w_d:
            by_kind["financial"] += at_risk_amount
            risk_kind = "financial"
            reasons = (fh.get("reasons") or [])[:2]
            segment = fh_seg
        else:
            by_kind["delivery"] += at_risk_amount
            risk_kind = "delivery"
            reasons = ((dh or {}).get("reasons") or [])[:2]
            segment = dh_seg

        items.append({
            "deal_id":       d.get("id"),
            "deal_title":    d.get("title") or d.get("vehicle_label") or d.get("id"),
            "manager_name":  d.get("manager_name") or d.get("managerName"),
            "weighted":      round(weighted, 2),
            "at_risk":       round(at_risk_amount, 2),
            "risk_kind":     risk_kind,
            "segment":       segment,
            "reasons":       reasons,
            "financial_health": fh_seg,
            "delivery_health":  dh_seg,
        })

    items.sort(key=lambda r: -r["at_risk"])
    return {
        "as_of":          now.isoformat(),
        "forecast_total": round(forecast_total, 2),
        "risk_total":     round(risk_total, 2),
        "risk_share_pct": round((risk_total / forecast_total * 100) if forecast_total else 0, 1),
        "by_kind":        {k: round(v, 2) for k, v in by_kind.items()},
        "items":          items[:200],
        "total":          len(items),
        "scope":          ctx["scope"],
        "currency":       "EUR",
    }


# ============================================================================
# 6. OVERVIEW — “How much? When? What can derail it?”
# ============================================================================
async def compute_forecast_overview(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Cheap roll-up that calls revenue + cashflow + risk and packages the
    three headline numbers (how_much, when, derail_risk) for the Overview tab.
    """
    rev    = await compute_revenue_forecast(db, user)
    cf     = await compute_cashflow_forecast(db, user)
    risk   = await compute_forecast_risk(db, user)

    return {
        "as_of":     rev["as_of"],
        "how_much":  {
            "horizons":      rev["horizons"],          # 30/60/90 → weighted
            "forecast_total": risk["forecast_total"],
        },
        "when":      {
            "weeks":   cf["weeks"],                    # 13-week cash-in/out
            "totals":  cf["totals"],
        },
        "derail": {
            "risk_total":    risk["risk_total"],
            "risk_share_pct":risk["risk_share_pct"],
            "by_kind":       risk["by_kind"],
            "top_items":     risk["items"][:5],
        },
        "scope":     rev["scope"],
        "currency":  rev["currency"],
    }


__all__ = [
    "compute_forecast_overview",
    "compute_revenue_forecast",
    "compute_cashflow_forecast",
    "compute_pipeline_forecast",
    "compute_capacity_forecast",
    "compute_forecast_risk",
]
