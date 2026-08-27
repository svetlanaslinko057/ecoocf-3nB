"""
BIBI Cars — Wave 14 — Operations 360 aggregations
===================================================

All functions are scope-aware (admin → all, team_lead → own + team,
manager → own). Read-only; no writes anywhere in this module.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.services.financial_health import compute_financial_health
from app.services.delivery_health import compute_delivery_health

# ---- shared helpers -------------------------------------------------------

TERMINAL_DEAL_STAGES = {"delivered", "cancelled", "refunded", "closed_won", "closed_lost"}
TERMINAL_LEAD_STATUSES = {"converted", "customer", "dead", "lost", "unqualified"}


async def _scope_filter(db, user: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Return (mongo_filter_for_deals_or_leads, scope_meta).
    None filter == company-wide."""
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
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _days_since(v: Any, now: datetime) -> Optional[int]:
    d = _to_dt(v)
    if not d:
        return None
    return int((now - d).total_seconds() // 86400)


def _hours_since(v: Any, now: datetime) -> Optional[float]:
    d = _to_dt(v)
    if not d:
        return None
    return (now - d).total_seconds() / 3600.0


def _month_window(now: datetime) -> Tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


# ============================================================================
# 1. COMPANY HEALTH DASHBOARD
# ============================================================================
async def compute_company_dashboard(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    scope_filter, scope_meta = await _scope_filter(db, user)

    # --- leads (active = not terminal) ----------------------------------
    lead_filter = dict(scope_filter or {})
    leads = await db.leads.find(lead_filter, {"_id": 0}).to_list(length=5000)
    active_leads = [l for l in leads if (l.get("status") or "new").lower() not in TERMINAL_LEAD_STATUSES]
    new_leads_mtd = [l for l in leads
                     if _to_dt(l.get("created_at")) and _to_dt(l.get("created_at")) >= _month_window(now)[0]]

    # --- deals -----------------------------------------------------------
    deal_filter = dict(scope_filter or {})
    deals = await db.deals.find(deal_filter, {"_id": 0}).to_list(length=5000)
    active_deals = [d for d in deals if (d.get("stage") or "").lower() not in TERMINAL_DEAL_STAGES
                    and (d.get("status") or "").lower() != "cancelled"]

    # --- finance -- piggy-back on the same shape Finance360 uses ---------
    deal_ids = [d.get("id") for d in deals if d.get("id")]
    deposits = await db.deposits.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    payments = await db.payments.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []

    deps_by_deal = defaultdict(list)
    for d in deposits:
        deps_by_deal[d.get("deal_id")].append(d)
    pays_by_deal = defaultdict(list)
    for p in payments:
        pays_by_deal[p.get("deal_id")].append(p)

    month_start = _month_window(now)[0]

    revenue_mtd = 0.0
    profit_mtd  = 0.0
    outstanding_total = 0.0
    at_risk_deals = 0
    collections_count = 0

    for d in deals:
        deal_id = d.get("id")
        deps = deps_by_deal.get(deal_id, [])
        pays = pays_by_deal.get(deal_id, [])
        fh = compute_financial_health(d, deps, pays)
        seg = fh.get("segment")
        metrics = fh.get("metrics") or {}
        outstanding_total += float(metrics.get("outstanding") or 0.0)
        if seg in ("warning", "at_risk", "critical"):
            at_risk_deals += 1
        if seg in ("at_risk", "critical") or (metrics.get("days_since_move") or 0) >= 7:
            collections_count += 1

        # Revenue / profit MTD — count delivered or paid deals in this month
        delivered_at = _to_dt(d.get("delivered_at") or d.get("closed_at"))
        if delivered_at and delivered_at >= month_start:
            revenue_mtd += float(d.get("price") or d.get("final_price") or 0)
            profit_mtd  += float(d.get("profit") or (float(d.get("price") or 0) - float(d.get("cost") or 0)))
        else:
            # Fall back to confirmed payments in this month
            for p in pays:
                p_at = _to_dt(p.get("received_at") or p.get("created_at"))
                if p_at and p_at >= month_start and (p.get("status") or "").lower() in ("confirmed", "paid", "received"):
                    revenue_mtd += float(p.get("amount") or 0)

    # --- shipments -------------------------------------------------------
    sh_filter = dict(scope_filter or {})
    shipments = await db.shipments.find(sh_filter, {"_id": 0}).to_list(length=5000)
    delivery_docs_by_ship: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if shipments:
        sids = [s.get("id") for s in shipments if s.get("id")]
        for doc in await db.delivery_documents.find({"shipment_id": {"$in": sids}}, {"_id": 0}).to_list(length=5000):
            delivery_docs_by_ship[doc.get("shipment_id")].append(doc)

    cars_in_transit = 0
    critical_deliveries = 0
    for s in shipments:
        deal_ref = None
        for d in deals:
            if d.get("id") == (s.get("deal_id") or s.get("dealId")):
                deal_ref = d; break
        dh = compute_delivery_health(s, documents=delivery_docs_by_ship.get(s.get("id"), []), deal=deal_ref)
        seg = dh.get("segment")
        cm  = (dh.get("metrics") or {}).get("current_milestone")
        if seg not in ("delivered", "cancelled") and cm:
            cars_in_transit += 1
        if seg == "critical":
            critical_deliveries += 1

    return {
        "as_of": now.isoformat(),
        "scope": scope_meta,
        "tiles": {
            "active_leads":        len(active_leads),
            "new_leads_mtd":       len(new_leads_mtd),
            "active_deals":        len(active_deals),
            "revenue_mtd":         round(revenue_mtd, 2),
            "profit_mtd":          round(profit_mtd, 2),
            "outstanding":         round(outstanding_total, 2),
            "collections":         collections_count,
            "cars_in_transit":     cars_in_transit,
            "critical_deliveries": critical_deliveries,
            "at_risk_deals":       at_risk_deals,
        },
        "currency": "EUR",
    }


# ============================================================================
# 2. BOTTLENECK ENGINE
# ============================================================================
async def compute_bottlenecks(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Where is the company stuck right now?

    Buckets every active deal into the most-specific bottleneck reason. The
    rule with the most deals → `top_bottleneck`.
    """
    now = datetime.now(timezone.utc)
    scope_filter, scope_meta = await _scope_filter(db, user)
    deal_filter = dict(scope_filter or {})
    deals = await db.deals.find(deal_filter, {"_id": 0}).to_list(length=5000)
    active = [d for d in deals if (d.get("stage") or "").lower() not in TERMINAL_DEAL_STAGES
              and (d.get("status") or "").lower() != "cancelled"]

    deal_ids = [d.get("id") for d in active if d.get("id")]
    deposits = await db.deposits.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    payments = await db.payments.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    shipments = await db.shipments.find({"$or": [{"deal_id": {"$in": deal_ids}}, {"dealId": {"$in": deal_ids}}]} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    docs = await db.delivery_documents.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=10000) if deal_ids else []

    deps_by_deal = defaultdict(list); [deps_by_deal[d.get("deal_id")].append(d) for d in deposits]
    pays_by_deal = defaultdict(list); [pays_by_deal[p.get("deal_id")].append(p) for p in payments]
    ship_by_deal = {}
    for s in shipments:
        ship_by_deal[s.get("deal_id") or s.get("dealId")] = s
    docs_by_ship = defaultdict(list); [docs_by_ship[d.get("shipment_id")].append(d) for d in docs]

    buckets = {
        "waiting_deposit":       {"label": "Waiting for deposit",         "count": 0, "deal_ids": []},
        "waiting_payment":       {"label": "Waiting for payment",         "count": 0, "deal_ids": []},
        "no_carrier":            {"label": "No carrier assigned",         "count": 0, "deal_ids": []},
        "stuck_at_customs":      {"label": "Stuck at customs",            "count": 0, "deal_ids": []},
        "stuck_at_port":         {"label": "Stuck at port",               "count": 0, "deal_ids": []},
        "missing_documents":     {"label": "Missing delivery documents",  "count": 0, "deal_ids": []},
        "stale_no_movement":     {"label": "No movement >7 days",         "count": 0, "deal_ids": []},
        "financial_at_risk":     {"label": "Financial health at risk",    "count": 0, "deal_ids": []},
    }

    # by-stage funnel (count active deals per stage, useful breakdown)
    by_stage: Dict[str, int] = defaultdict(int)

    for d in active:
        deal_id = d.get("id")
        stage = (d.get("stage") or "").lower()
        by_stage[stage or "unknown"] += 1

        deps = deps_by_deal.get(deal_id, [])
        pays = pays_by_deal.get(deal_id, [])
        sh   = ship_by_deal.get(deal_id)
        docs_for_ship = docs_by_ship.get(sh.get("id") if sh else None, [])
        delivery = (sh or {}).get("delivery") or {}
        current_milestone = delivery.get("current_milestone") or ""
        days_since_move   = None
        for m in reversed(delivery.get("milestones") or []):
            dt = _to_dt(m.get("at"))
            if dt:
                days_since_move = int((now - dt).total_seconds() // 86400)
                break

        # Categorise into the FIRST applicable bucket (priority order)
        fh = compute_financial_health(d, deps, pays)
        dh = compute_delivery_health(sh, documents=docs_for_ship, deal=d) if sh else None

        if not deps or all((dep.get("status") or "").lower() in ("pending", "rejected") for dep in deps):
            buckets["waiting_deposit"]["count"] += 1
            buckets["waiting_deposit"]["deal_ids"].append(deal_id)
            continue
        if fh.get("segment") in ("warning", "at_risk", "critical") and (fh.get("metrics") or {}).get("outstanding", 0) > 0:
            # only count as “financial” if there's no more specific delivery problem
            pass
        if sh and not delivery.get("carrier_id") and not delivery.get("carrier_name"):
            buckets["no_carrier"]["count"] += 1
            buckets["no_carrier"]["deal_ids"].append(deal_id)
            continue
        if current_milestone == "customs" and (days_since_move or 0) >= 7:
            buckets["stuck_at_customs"]["count"] += 1
            buckets["stuck_at_customs"]["deal_ids"].append(deal_id)
            continue
        if current_milestone == "port_arrived" and (days_since_move or 0) >= 5:
            buckets["stuck_at_port"]["count"] += 1
            buckets["stuck_at_port"]["deal_ids"].append(deal_id)
            continue
        if dh and (dh.get("metrics") or {}).get("missing_documents"):
            buckets["missing_documents"]["count"] += 1
            buckets["missing_documents"]["deal_ids"].append(deal_id)
            continue
        if pays and any((p.get("status") or "").lower() == "pending" for p in pays):
            buckets["waiting_payment"]["count"] += 1
            buckets["waiting_payment"]["deal_ids"].append(deal_id)
            continue
        if fh.get("segment") in ("at_risk", "critical"):
            buckets["financial_at_risk"]["count"] += 1
            buckets["financial_at_risk"]["deal_ids"].append(deal_id)
            continue
        if (days_since_move or 0) >= 7:
            buckets["stale_no_movement"]["count"] += 1
            buckets["stale_no_movement"]["deal_ids"].append(deal_id)
            continue

    ranked = sorted(buckets.items(), key=lambda kv: kv[1]["count"], reverse=True)
    top_key = ranked[0][0] if ranked and ranked[0][1]["count"] > 0 else None

    return {
        "total_active_deals": len(active),
        "buckets":            {k: {**v, "key": k} for k, v in buckets.items()},
        "ranked":             [{"key": k, "label": v["label"], "count": v["count"]} for k, v in ranked],
        "top_bottleneck":     buckets[top_key] | {"key": top_key} if top_key else None,
        "by_stage":           dict(by_stage),
        "scope":              scope_meta,
    }


# ============================================================================
# 3. TEAM PERFORMANCE 360
# ============================================================================
async def compute_team_performance(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    scope_filter, scope_meta = await _scope_filter(db, user)

    # All staff in scope
    if scope_meta["all"]:
        staff = await db.staff.find({}, {"_id": 0}).to_list(length=1000)
    else:
        own_id = user.get("id") or user.get("managerId") or user.get("sub")
        if user.get("role") == "team_lead":
            staff = await db.staff.find({"$or": [{"id": own_id}, {"team_lead_id": own_id}]}, {"_id": 0}).to_list(length=500)
        else:
            staff = await db.staff.find({"id": own_id}, {"_id": 0}).to_list(length=10)

    leads = await db.leads.find(dict(scope_filter or {}), {"_id": 0}).to_list(length=5000)
    deals = await db.deals.find(dict(scope_filter or {}), {"_id": 0}).to_list(length=5000)
    deal_ids = [d.get("id") for d in deals if d.get("id")]
    deposits = await db.deposits.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    payments = await db.payments.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    shipments = await db.shipments.find({"$or": [{"deal_id": {"$in": deal_ids}}, {"dealId": {"$in": deal_ids}}]} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []

    deps_by_deal = defaultdict(list); [deps_by_deal[d.get("deal_id")].append(d) for d in deposits]
    pays_by_deal = defaultdict(list); [pays_by_deal[p.get("deal_id")].append(p) for p in payments]
    ship_by_deal = {}
    for s in shipments:
        ship_by_deal[s.get("deal_id") or s.get("dealId")] = s

    rows: List[Dict[str, Any]] = []
    # Build a quick (staff_id) → row scaffold
    by_mgr: Dict[str, Dict[str, Any]] = {}
    for s in staff:
        sid = s.get("id")
        if not sid:
            continue
        by_mgr[sid] = {
            "manager_id":   sid,
            "manager_name": s.get("name") or s.get("email") or sid,
            "email":        s.get("email"),
            "role":         s.get("role"),
            "leads":         0,
            "leads_converted": 0,
            "deals":          0,
            "deals_delivered": 0,
            "revenue":        0.0,
            "profit":         0.0,
            "outstanding":    0.0,
            "collections":    0,
            "avg_deal_time_days": None,
            "_deal_durations":    [],
            "delivery_delays":    0,
        }
    # Unassigned bucket
    by_mgr["__unassigned__"] = {
        "manager_id":   None,
        "manager_name": "Unassigned",
        "email":        None,
        "role":         None,
        "leads":         0,
        "leads_converted": 0,
        "deals":          0,
        "deals_delivered": 0,
        "revenue":        0.0,
        "profit":         0.0,
        "outstanding":    0.0,
        "collections":    0,
        "avg_deal_time_days": None,
        "_deal_durations":    [],
        "delivery_delays":    0,
    }

    def _row_for(mgr_id: Optional[str]) -> Dict[str, Any]:
        return by_mgr.get(mgr_id or "") or by_mgr["__unassigned__"]

    # Leads
    for l in leads:
        mgr_id = l.get("managerId") or l.get("manager_id")
        row = _row_for(mgr_id)
        row["leads"] += 1
        if (l.get("status") or "").lower() in ("converted", "customer"):
            row["leads_converted"] += 1

    # Deals + finance + delivery
    for d in deals:
        mgr_id = d.get("managerId") or d.get("manager_id")
        row = _row_for(mgr_id)
        row["deals"] += 1
        stage = (d.get("stage") or "").lower()
        if stage == "delivered":
            row["deals_delivered"] += 1

        deps = deps_by_deal.get(d.get("id"), [])
        pays = pays_by_deal.get(d.get("id"), [])
        fh = compute_financial_health(d, deps, pays)
        m = fh.get("metrics") or {}
        row["revenue"]     += float(d.get("price") or d.get("final_price") or 0)
        row["profit"]      += float(d.get("profit") or (float(d.get("price") or 0) - float(d.get("cost") or 0)))
        row["outstanding"] += float(m.get("outstanding") or 0)
        if fh.get("segment") in ("at_risk", "critical"):
            row["collections"] += 1

        # deal duration: created_at → delivered_at or now if open
        created = _to_dt(d.get("created_at"))
        end = _to_dt(d.get("delivered_at")) or now
        if created:
            row["_deal_durations"].append(int((end - created).total_seconds() // 86400))

        # delivery delay flag
        sh = ship_by_deal.get(d.get("id"))
        if sh:
            dh = compute_delivery_health(sh, deal=d)
            v = (dh.get("metrics") or {}).get("eta_variance_days")
            if isinstance(v, int) and v > 0:
                row["delivery_delays"] += 1

    # finalise
    for row in by_mgr.values():
        durs = row.pop("_deal_durations", []) or []
        if durs:
            row["avg_deal_time_days"] = round(sum(durs) / len(durs), 1)
        conv = row["leads_converted"]
        leads_n = row["leads"]
        row["conversion_rate"] = round(conv / leads_n * 100, 1) if leads_n else None
        row["revenue"]     = round(row["revenue"], 2)
        row["profit"]      = round(row["profit"], 2)
        row["outstanding"] = round(row["outstanding"], 2)

        # composite ops score 0..100
        score = 100
        if row["collections"]:    score -= min(row["collections"] * 10, 30)
        if row["delivery_delays"]: score -= min(row["delivery_delays"] * 8, 20)
        if row["conversion_rate"] is not None and row["conversion_rate"] < 20:
            score -= 10
        if row["outstanding"] and row["revenue"]:
            ratio = row["outstanding"] / max(row["revenue"], 1)
            if ratio > 0.5:   score -= 15
            elif ratio > 0.25: score -= 5
        row["ops_score"] = max(0, min(100, score))

    rows = list(by_mgr.values())
    # Drop empty unassigned row if nothing landed there
    rows = [r for r in rows if (r["leads"] + r["deals"]) > 0]
    # Sort by ops_score asc (worst first — those are who need attention)
    rows.sort(key=lambda r: (r["ops_score"], -(r["collections"] + r["delivery_delays"])))
    return {"items": rows, "total": len(rows), "scope": scope_meta}


# ============================================================================
# 4. SLA MONITOR
# ============================================================================
SLA_RULES = [
    {"id": "lead_response_15min",  "label": "Lead response > 15 min",   "limit_label": "15 min"},
    {"id": "deal_stuck_7d",        "label": "Deal stuck > 7 days",      "limit_label": "7 days"},
    {"id": "deposit_pending_3d",   "label": "Deposit pending > 3 days", "limit_label": "3 days"},
    {"id": "carrier_not_assigned_2d", "label": "Carrier not assigned > 2 days", "limit_label": "2 days"},
    {"id": "customs_14d",          "label": "Customs > 14 days",        "limit_label": "14 days"},
]


async def compute_sla(db, user: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    scope_filter, scope_meta = await _scope_filter(db, user)

    violations = defaultdict(list)

    # --- 1. lead_response_15min ----------------------------------------
    leads = await db.leads.find(dict(scope_filter or {}), {"_id": 0}).to_list(length=5000)
    for l in leads:
        if (l.get("status") or "").lower() in TERMINAL_LEAD_STATUSES:
            continue
        # "responded" if we have last_contact_at or first_contact_at
        responded_at = _to_dt(l.get("first_contact_at")) or _to_dt(l.get("last_contact_at"))
        created_at   = _to_dt(l.get("created_at"))
        if responded_at:
            continue
        if created_at and (now - created_at).total_seconds() / 60.0 > 15:
            violations["lead_response_15min"].append({
                "id":        l.get("id"),
                "label":     l.get("full_name") or l.get("name") or l.get("phone") or l.get("email") or l.get("id"),
                "href":      f"/admin/leads/{l.get('id')}" if l.get("id") else None,
                "age_hours": round((now - created_at).total_seconds() / 3600.0, 1),
                "manager":   l.get("managerName") or l.get("manager_name") or l.get("managerId"),
            })

    # --- 2. deal_stuck_7d ----------------------------------------------
    deals = await db.deals.find(dict(scope_filter or {}), {"_id": 0}).to_list(length=5000)
    for d in deals:
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES:
            continue
        last = _to_dt(d.get("stage_updated_at")) or _to_dt(d.get("updated_at")) or _to_dt(d.get("created_at"))
        if last and (now - last).days > 7:
            violations["deal_stuck_7d"].append({
                "id":      d.get("id"),
                "label":   d.get("title") or d.get("vehicle_label") or d.get("id"),
                "href":    f"/admin/deals/{d.get('id')}/360" if d.get("id") else None,
                "age_days": (now - last).days,
                "stage":   stage,
                "manager": d.get("manager_name") or d.get("managerName") or d.get("managerId"),
            })

    # --- 3. deposit_pending_3d -----------------------------------------
    deal_ids_in_scope = {d.get("id") for d in deals if d.get("id")}
    deps = await db.deposits.find({"deal_id": {"$in": list(deal_ids_in_scope)}} if deal_ids_in_scope else {}, {"_id": 0}).to_list(length=5000) if deal_ids_in_scope else []
    for dep in deps:
        if (dep.get("status") or "").lower() != "pending":
            continue
        created = _to_dt(dep.get("created_at"))
        if created and (now - created).days > 3:
            violations["deposit_pending_3d"].append({
                "id":      dep.get("id"),
                "label":   f"Deposit — deal {dep.get('deal_id', '')[-8:]}",
                "href":    f"/admin/deals/{dep.get('deal_id')}/360" if dep.get("deal_id") else None,
                "age_days": (now - created).days,
                "amount":  dep.get("amount"),
            })

    # --- 4. carrier_not_assigned_2d ------------------------------------
    shipments = await db.shipments.find({"$or": [{"deal_id": {"$in": list(deal_ids_in_scope)}}, {"dealId": {"$in": list(deal_ids_in_scope)}}]} if deal_ids_in_scope else {}, {"_id": 0}).to_list(length=5000) if deal_ids_in_scope else []
    for sh in shipments:
        delivery = sh.get("delivery") or {}
        if delivery.get("carrier_id") or delivery.get("carrier_name"):
            continue
        if delivery.get("cancelled") or delivery.get("current_milestone") == "delivered":
            continue
        created = _to_dt(sh.get("created_at"))
        if created and (now - created).days > 2:
            violations["carrier_not_assigned_2d"].append({
                "id":      sh.get("id"),
                "label":   sh.get("vehicleLabel") or f"Shipment {sh.get('id', '')[-8:]}",
                "href":    f"/admin/deals/{sh.get('deal_id') or sh.get('dealId')}/360?tab=delivery" if (sh.get("deal_id") or sh.get("dealId")) else None,
                "age_days": (now - created).days,
            })

    # --- 5. customs_14d -------------------------------------------------
    for sh in shipments:
        delivery = sh.get("delivery") or {}
        if delivery.get("current_milestone") != "customs":
            continue
        last_at = None
        for m in reversed(delivery.get("milestones") or []):
            if m.get("key") == "customs":
                last_at = _to_dt(m.get("at"))
                break
        if last_at and (now - last_at).days > 14:
            violations["customs_14d"].append({
                "id":      sh.get("id"),
                "label":   sh.get("vehicleLabel") or f"Shipment {sh.get('id', '')[-8:]}",
                "href":    f"/admin/deals/{sh.get('deal_id') or sh.get('dealId')}/360?tab=delivery" if (sh.get("deal_id") or sh.get("dealId")) else None,
                "age_days": (now - last_at).days,
            })

    # Build rules with their items
    out_rules = []
    for rule in SLA_RULES:
        items = violations.get(rule["id"], [])
        out_rules.append({**rule, "count": len(items), "items": items[:50]})

    return {
        "as_of":   now.isoformat(),
        "rules":   out_rules,
        "total":   sum(r["count"] for r in out_rules),
        "scope":   scope_meta,
    }


# ============================================================================
# 5. RISK CENTER
# ============================================================================
async def compute_risk_center(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Cross-entity risk view — unified Lead / Customer / Financial / Delivery risk."""
    now = datetime.now(timezone.utc)
    scope_filter, scope_meta = await _scope_filter(db, user)

    deals = await db.deals.find(dict(scope_filter or {}), {"_id": 0}).to_list(length=5000)
    leads = await db.leads.find(dict(scope_filter or {}), {"_id": 0}).to_list(length=5000)
    deal_ids = [d.get("id") for d in deals if d.get("id")]
    deps = await db.deposits.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    pays = await db.payments.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    ships = await db.shipments.find({"$or": [{"deal_id": {"$in": deal_ids}}, {"dealId": {"$in": deal_ids}}]} if deal_ids else {}, {"_id": 0}).to_list(length=5000) if deal_ids else []
    docs  = await db.delivery_documents.find({"deal_id": {"$in": deal_ids}} if deal_ids else {}, {"_id": 0}).to_list(length=10000) if deal_ids else []

    deps_by_deal = defaultdict(list); [deps_by_deal[d.get("deal_id")].append(d) for d in deps]
    pays_by_deal = defaultdict(list); [pays_by_deal[p.get("deal_id")].append(p) for p in pays]
    docs_by_ship = defaultdict(list); [docs_by_ship[d.get("shipment_id")].append(d) for d in docs]
    ship_by_deal = {}
    for s in ships:
        ship_by_deal[s.get("deal_id") or s.get("dealId")] = s

    SEG_RANK = {"critical": 0, "at_risk": 1, "delay_risk": 1, "delayed": 2, "warning": 2,
                "on_track": 4, "healthy": 4, "delivered": 5, "cancelled": 6}

    items: List[Dict[str, Any]] = []

    # ---- Lead risk (stuck/cold leads) ---------------------------------
    for l in leads:
        status = (l.get("status") or "").lower()
        if status in TERMINAL_LEAD_STATUSES:
            continue
        last = _to_dt(l.get("last_contact_at")) or _to_dt(l.get("updated_at")) or _to_dt(l.get("created_at"))
        if not last: continue
        days = (now - last).days
        if days < 3:
            continue
        seg = "critical" if days >= 14 else "at_risk" if days >= 7 else "warning"
        items.append({
            "entity_type": "lead",
            "entity_id":   l.get("id"),
            "label":       l.get("full_name") or l.get("name") or l.get("phone") or l.get("email") or l.get("id"),
            "href":        f"/admin/leads/{l.get('id')}" if l.get("id") else None,
            "manager":     l.get("managerName") or l.get("manager_name"),
            "segment":     seg,
            "score":       max(0, 100 - days * 4),
            "risk_kind":   "lead_cold",
            "reasons":     [f"No contact in {days}d"],
        })

    # ---- Financial risk (deals) ---------------------------------------
    for d in deals:
        stage = (d.get("stage") or "").lower()
        if stage in TERMINAL_DEAL_STAGES:
            continue
        fh = compute_financial_health(d, deps_by_deal.get(d.get("id"), []), pays_by_deal.get(d.get("id"), []))
        if fh.get("segment") in ("warning", "at_risk", "critical"):
            items.append({
                "entity_type": "deal",
                "entity_id":   d.get("id"),
                "label":       d.get("title") or d.get("vehicle_label") or d.get("id"),
                "href":        f"/admin/deals/{d.get('id')}/360" if d.get("id") else None,
                "manager":     d.get("manager_name") or d.get("managerName"),
                "segment":     fh["segment"],
                "score":       fh["score"],
                "risk_kind":   "financial",
                "reasons":     fh["reasons"][:3],
            })

    # ---- Delivery risk (shipments) ------------------------------------
    for d in deals:
        sh = ship_by_deal.get(d.get("id"))
        if not sh:
            continue
        dh = compute_delivery_health(sh, documents=docs_by_ship.get(sh.get("id"), []), deal=d)
        if dh.get("segment") in ("delay_risk", "delayed", "critical"):
            items.append({
                "entity_type": "shipment",
                "entity_id":   sh.get("id"),
                "label":       (sh.get("vehicleLabel") or d.get("title") or d.get("id")),
                "href":        f"/admin/deals/{d.get('id')}/360?tab=delivery" if d.get("id") else None,
                "manager":     d.get("manager_name") or d.get("managerName"),
                "segment":     dh["segment"],
                "score":       dh["score"],
                "risk_kind":   "delivery",
                "reasons":     dh["reasons"][:3],
            })

    # Order: critical first, then at_risk/delay_risk, then warning/delayed.
    items.sort(key=lambda x: (SEG_RANK.get(x["segment"], 9), -x["score"]))

    by_kind = {"lead_cold": 0, "financial": 0, "delivery": 0}
    by_segment: Dict[str, int] = defaultdict(int)
    for it in items:
        by_kind[it["risk_kind"]] = by_kind.get(it["risk_kind"], 0) + 1
        by_segment[it["segment"]] += 1

    return {
        "items":      items[:300],
        "total":      len(items),
        "by_kind":    by_kind,
        "by_segment": dict(by_segment),
        "scope":      scope_meta,
    }


__all__ = [
    "compute_company_dashboard",
    "compute_bottlenecks",
    "compute_team_performance",
    "compute_sla",
    "compute_risk_center",
    "SLA_RULES",
]
