"""ECO Analytics — pure aggregation helpers (read-only) over the ECO domain."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

UTC = timezone.utc

DEAL_STAGES = ["new", "negotiation", "contract", "pickup", "utilization", "won", "lost"]
OPEN_STAGES = {"new", "negotiation", "contract", "pickup", "utilization"}
TERMINAL_STAGES = {"won", "lost"}
STAGE_PROB = {
    "new": 0.10, "negotiation": 0.30, "contract": 0.55,
    "pickup": 0.75, "utilization": 0.90, "won": 1.0, "lost": 0.0,
}
STAGE_LABELS_UK = {
    "new": "Нова", "negotiation": "Переговори", "contract": "Договір",
    "pickup": "Вивіз", "utilization": "Утилізація", "won": "Виграно", "lost": "Втрачено",
}

# Contract statuses
CTR_OPEN_UNPAID = {"draft", "pending_approval", "sent", "signed", "active"}
CTR_REVENUE = {"signed", "active", "archived"}
CTR_STATUS_LABELS_UK = {
    "draft": "Чернетка", "pending_approval": "На узгодженні", "sent": "Надіслано",
    "signed": "Підписано", "active": "Активний", "archived": "Архів", "cancelled": "Скасовано",
}

CURRENCY = "UAH"


# ─────────────────────────────────────────────────────────────────────────────
#  utils
# ─────────────────────────────────────────────────────────────────────────────
def now() -> datetime:
    return datetime.now(UTC)


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except Exception:
        return None


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def month_start(ref: Optional[datetime] = None) -> datetime:
    ref = ref or now()
    return ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def scope_ctx(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Return scoping context: admin → all; manager → own deals/companies."""
    role = (user or {}).get("role") or "manager"
    uid = (user or {}).get("id") or (user or {}).get("managerId") or (user or {}).get("email")
    is_admin = role in ("admin", "owner", "director")
    ctx: Dict[str, Any] = {"all": is_admin, "uid": uid, "managers": 0 if is_admin else 1}
    if is_admin:
        ctx["deal_filter"] = {}
        ctx["company_ids"] = None
        ctx["deal_ids"] = None
        return ctx
    ctx["deal_filter"] = {"managerId": uid}
    deals = await db.deals.find({"managerId": uid}, {"_id": 0, "id": 1, "company_id": 1}).to_list(5000)
    ctx["deal_ids"] = {d.get("id") for d in deals}
    ctx["company_ids"] = {d.get("company_id") for d in deals if d.get("company_id")}
    return ctx


async def _fetch_deals(db, ctx) -> List[Dict[str, Any]]:
    return await db.deals.find(ctx["deal_filter"], {"_id": 0}).to_list(20000)


async def _fetch_contracts(db, ctx) -> List[Dict[str, Any]]:
    rows = await db.contracts.find({}, {"_id": 0}).to_list(20000)
    if ctx["all"]:
        return rows
    ids = ctx.get("deal_ids") or set()
    cids = ctx.get("company_ids") or set()
    return [r for r in rows if r.get("deal_id") in ids or r.get("company_id") in cids]


async def _fetch_payments(db, ctx) -> List[Dict[str, Any]]:
    rows = await db.payments.find({}, {"_id": 0}).to_list(50000)
    if ctx["all"]:
        return rows
    ids = ctx.get("deal_ids") or set()
    return [r for r in rows if r.get("deal_id") in ids]


def _contract_outstanding(c: Dict[str, Any]) -> float:
    if c.get("status") in ("cancelled", "draft"):
        return 0.0
    return max(0.0, _num(c.get("amount") or c.get("value")) - _num(c.get("paid_amount")))


def _contract_overdue_sign(c: Dict[str, Any], ref: datetime) -> bool:
    if c.get("status") != "sent":
        return False
    due = parse_dt(c.get("due_signature_at"))
    return bool(due and due < ref)


# ─────────────────────────────────────────────────────────────────────────────
#  FINANCE (Wave 12)
# ─────────────────────────────────────────────────────────────────────────────
async def finance_overview(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    deals = await _fetch_deals(db, ctx)
    contracts = await _fetch_contracts(db, ctx)
    ref = now()

    revenue = sum(_num(c.get("amount") or c.get("value")) for c in contracts if c.get("status") in CTR_REVENUE)
    profit = sum(_num(c.get("amount") or c.get("value")) - _num(c.get("cost"))
                 for c in contracts if c.get("status") in CTR_REVENUE)
    outstanding = sum(_contract_outstanding(c) for c in contracts)

    segments = {k: {"count": 0, "outstanding": 0.0, "revenue": 0.0}
                for k in ("healthy", "warning", "at_risk", "critical")}
    at_risk_total = 0.0
    for c in contracts:
        out = _contract_outstanding(c)
        if out <= 0:
            continue
        created = parse_dt(c.get("created_at")) or ref
        age = (ref - created).days
        overdue = _contract_overdue_sign(c, ref)
        if overdue or age > 60:
            seg = "critical"
        elif age > 30:
            seg = "at_risk"
        elif age > 14:
            seg = "warning"
        else:
            seg = "healthy"
        segments[seg]["count"] += 1
        segments[seg]["outstanding"] += out
        segments[seg]["revenue"] += _num(c.get("amount") or c.get("value"))
        if seg in ("at_risk", "critical"):
            at_risk_total += out

    counts = {
        "deals_total": len(deals),
        "deals_open": sum(1 for d in deals if d.get("stage") in OPEN_STAGES),
        "deals_delivered": sum(1 for d in deals if d.get("stage") == "won"),
        "refunds_pending": 0, "refunds_paid": 0,
    }
    return {
        "scope": {"all": ctx["all"], "managers": ctx["managers"]},
        "currency": CURRENCY,
        "counts": counts,
        "totals": {
            "revenue": round(revenue, 2), "profit": round(profit, 2),
            "outstanding": round(outstanding, 2), "at_risk": round(at_risk_total, 2),
            "contracts": len(contracts),
        },
        "risk": {"by_segment": {k: {"count": v["count"],
                                    "outstanding": round(v["outstanding"], 2),
                                    "revenue": round(v["revenue"], 2)}
                                for k, v in segments.items()}},
    }


async def finance_forecast(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    deals = await _fetch_deals(db, ctx)
    ref = now()
    open_deals = [d for d in deals if d.get("stage") in OPEN_STAGES]

    horizons: Dict[str, Any] = {}
    for h in (30, 60, 90):
        limit = ref + timedelta(days=h)
        sel = [d for d in open_deals if (parse_dt(d.get("expected_close")) or limit) <= limit]
        weighted = sum(_num(d.get("amount")) * _num(d.get("probability", STAGE_PROB.get(d.get("stage"), 0.3))) for d in sel)
        gross = sum(_num(d.get("amount")) for d in sel)
        profit = sum((_num(d.get("amount")) - _num(d.get("cost"))) * _num(d.get("probability", STAGE_PROB.get(d.get("stage"), 0.3))) for d in sel)
        horizons[str(h)] = {"deals": len(sel), "weighted": round(weighted, 2),
                            "gross": round(gross, 2), "profit": round(profit, 2)}

    # 13-week cash-flow projection
    weeks: List[Dict[str, Any]] = []
    running = 0.0
    week0 = ref - timedelta(days=ref.weekday())
    for w in range(13):
        w_start = week0 + timedelta(weeks=w)
        w_end = w_start + timedelta(days=7)
        cash_in = 0.0
        cash_out = 0.0
        for d in open_deals:
            ec = parse_dt(d.get("expected_close"))
            if ec and w_start <= ec < w_end:
                prob = _num(d.get("probability", STAGE_PROB.get(d.get("stage"), 0.3)))
                cash_in += _num(d.get("amount")) * prob
                cash_out += _num(d.get("cost")) * prob
        net = cash_in - cash_out
        running += net
        weeks.append({"start": w_start.date().isoformat(), "cash_in": round(cash_in, 2),
                      "cash_out": round(cash_out, 2), "net": round(net, 2),
                      "running_balance": round(running, 2)})

    return {
        "as_of": ref.isoformat(),
        "currency": CURRENCY,
        "how_much": {"horizons": horizons},
        "when": {"weeks": weeks},
        "scope": {"all": ctx["all"], "managers": ctx["managers"]},
    }


async def finance_risk(db, user) -> Dict[str, Any]:
    ov = await finance_overview(db, user)
    seg = ov["risk"]["by_segment"]
    at_risk_total = sum(seg[k]["outstanding"] for k in ("at_risk", "critical"))
    at_risk_revenue = sum(seg[k]["revenue"] for k in ("at_risk", "critical"))
    return {"at_risk_total": round(at_risk_total, 2), "at_risk_revenue": round(at_risk_revenue, 2),
            "by_segment": seg, "currency": CURRENCY}


async def finance_collections(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    contracts = await _fetch_contracts(db, ctx)
    ref = now()
    items = []
    by_segment = {"critical": 0, "at_risk": 0, "warning": 0}
    outstanding = 0.0
    for c in contracts:
        out = _contract_outstanding(c)
        if out <= 0:
            continue
        created = parse_dt(c.get("created_at")) or ref
        age = (ref - created).days
        seg = "critical" if (age > 60 or _contract_overdue_sign(c, ref)) else "at_risk" if age > 30 else "warning"
        by_segment[seg] = by_segment.get(seg, 0) + 1
        outstanding += out
        items.append({"id": c.get("id"), "number": c.get("number"), "customer_name": c.get("customer_name"),
                      "company": c.get("company"), "outstanding": round(out, 2), "age_days": age,
                      "segment": seg, "status": c.get("status")})
    items.sort(key=lambda x: x["outstanding"], reverse=True)
    return {"items": items, "total": len(items),
            "summary": {"outstanding": round(outstanding, 2), "deals": len(items), "by_segment": by_segment}}


async def finance_managers_pnl(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    deals = await _fetch_deals(db, ctx)
    staff = {s["id"]: s for s in await db.staff.find({}, {"_id": 0}).to_list(500)}
    agg: Dict[str, Dict[str, Any]] = {}
    for d in deals:
        mid = d.get("managerId") or "—"
        a = agg.setdefault(mid, {"manager_id": mid, "name": (staff.get(mid) or {}).get("name", mid),
                                 "deals": 0, "won": 0, "revenue": 0.0, "profit": 0.0, "pipeline": 0.0})
        a["deals"] += 1
        if d.get("stage") == "won":
            a["won"] += 1
            a["revenue"] += _num(d.get("amount"))
            a["profit"] += _num(d.get("amount")) - _num(d.get("cost"))
        elif d.get("stage") in OPEN_STAGES:
            a["pipeline"] += _num(d.get("amount"))
    items = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
    for it in items:
        it["revenue"] = round(it["revenue"], 2); it["profit"] = round(it["profit"], 2); it["pipeline"] = round(it["pipeline"], 2)
    return {"items": items, "currency": CURRENCY, "total": len(items)}


async def finance_transactions(db, user, limit: int = 100) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    payments = await _fetch_payments(db, ctx)
    payments.sort(key=lambda p: parse_dt(p.get("date") or p.get("created_at")) or now(), reverse=True)
    items = [{"id": p.get("id"), "company": p.get("company"), "customer_name": p.get("customer_name"),
              "kind": p.get("kind"), "amount": round(_num(p.get("amount")), 2), "status": p.get("status"),
              "date": p.get("date") or (p.get("created_at").isoformat() if isinstance(p.get("created_at"), datetime) else p.get("created_at")),
              "currency": CURRENCY} for p in payments[:limit]]
    income = sum(_num(p.get("amount")) for p in payments if p.get("kind") == "income")
    expense = sum(_num(p.get("amount")) for p in payments if p.get("kind") == "expense")
    return {"items": items, "total": len(payments), "currency": CURRENCY,
            "summary": {"income": round(income, 2), "expense": round(expense, 2), "net": round(income - expense, 2)}}


async def finance_outstanding(db, user) -> Dict[str, Any]:
    col = await finance_collections(db, user)
    return {"items": col["items"], "total": col["total"], "summary": col["summary"], "currency": CURRENCY}


# ─────────────────────────────────────────────────────────────────────────────
#  OPERATIONS (Wave 14)
# ─────────────────────────────────────────────────────────────────────────────
async def _pickups(db, ctx) -> List[Dict[str, Any]]:
    rows = await db.waste_pickups.find({}, {"_id": 0}).to_list(20000)
    if ctx["all"]:
        return rows
    cids = ctx.get("company_ids") or set()
    return [r for r in rows if r.get("company_id") in cids]


async def operations_dashboard(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    deals = await _fetch_deals(db, ctx)
    contracts = await _fetch_contracts(db, ctx)
    payments = await _fetch_payments(db, ctx)
    pickups = await _pickups(db, ctx)
    ref = now()
    ms = month_start(ref)

    lead_q = {} if ctx["all"] else {"managerId": ctx["uid"]}
    active_leads = await db.leads.count_documents({**lead_q, "stage": {"$nin": ["won", "lost", "converted"]}})
    new_leads_mtd = await db.leads.count_documents({**lead_q, "created_at": {"$gte": ms}})

    active_deals = sum(1 for d in deals if d.get("stage") in OPEN_STAGES)
    income_mtd = sum(_num(p.get("amount")) for p in payments
                     if p.get("kind") == "income" and (parse_dt(p.get("date") or p.get("created_at")) or ms) >= ms)
    expense_mtd = sum(_num(p.get("amount")) for p in payments
                      if p.get("kind") == "expense" and (parse_dt(p.get("date") or p.get("created_at")) or ms) >= ms)
    outstanding = sum(_contract_outstanding(c) for c in contracts)

    in_transit = sum(1 for p in pickups if p.get("status") in ("planning", "route", "driver_assigned"))
    critical = sum(1 for p in pickups
                   if p.get("status") not in ("delivered", "cancelled")
                   and (parse_dt(p.get("scheduled_at")) or ref) < ref)
    at_risk_deals = sum(1 for d in deals if d.get("stage") in OPEN_STAGES
                        and (parse_dt(d.get("expected_close")) or ref) < ref)

    return {
        "as_of": ref.isoformat(),
        "scope": {"all": ctx["all"], "managers": ctx["managers"]},
        "tiles": {
            "active_leads": active_leads, "new_leads_mtd": new_leads_mtd,
            "active_deals": active_deals, "revenue_mtd": round(income_mtd, 2),
            "profit_mtd": round(income_mtd - expense_mtd, 2), "outstanding": round(outstanding, 2),
            "cars_in_transit": in_transit, "critical_deliveries": critical, "at_risk_deals": at_risk_deals,
        },
        "currency": CURRENCY,
    }


async def operations_sla(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    contracts = await _fetch_contracts(db, ctx)
    pickups = await _pickups(db, ctx)
    ref = now()
    lead_q = {} if ctx["all"] else {"managerId": ctx["uid"]}
    stale_lead_cut = ref - timedelta(days=2)
    stale_leads = await db.leads.find({**lead_q, "stage": {"$in": ["lead", "new", "qualifying"]},
                                       "created_at": {"$lt": stale_lead_cut}}, {"_id": 0, "id": 1, "company": 1}).to_list(500)

    overdue_sign = [c for c in contracts if _contract_overdue_sign(c, ref)]
    overdue_pickup = [p for p in pickups if p.get("status") not in ("delivered", "cancelled")
                      and (parse_dt(p.get("scheduled_at")) or ref) < ref]
    overdue_pay = [c for c in contracts if _contract_outstanding(c) > 0
                   and (ref - (parse_dt(c.get("created_at")) or ref)).days > 30]

    rules = [
        {"id": "lead_response_48h", "label": "Реакція на лід > 48 год", "limit_label": "48 год",
         "count": len(stale_leads), "items": [{"id": x.get("id"), "label": x.get("company")} for x in stale_leads[:20]]},
        {"id": "contract_signing", "label": "Прострочений підпис договору", "limit_label": "10 днів",
         "count": len(overdue_sign), "items": [{"id": c.get("id"), "label": c.get("number")} for c in overdue_sign[:20]]},
        {"id": "pickup_overdue", "label": "Прострочений вивіз", "limit_label": "за планом",
         "count": len(overdue_pickup), "items": [{"id": p.get("id"), "label": p.get("number")} for p in overdue_pickup[:20]]},
        {"id": "payment_overdue_30d", "label": "Оплата прострочена > 30 днів", "limit_label": "30 днів",
         "count": len(overdue_pay), "items": [{"id": c.get("id"), "label": c.get("number")} for c in overdue_pay[:20]]},
    ]
    return {"as_of": ref.isoformat(), "rules": rules,
            "scope": {"all": ctx["all"], "managers": ctx["managers"]}}


async def operations_bottlenecks(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    deals = await _fetch_deals(db, ctx)
    buckets = {}
    for st in DEAL_STAGES:
        if st in TERMINAL_STAGES:
            continue
        ids = [d.get("id") for d in deals if d.get("stage") == st]
        buckets[st] = {"key": st, "label": STAGE_LABELS_UK[st], "count": len(ids), "deal_ids": ids[:50]}
    total_active = sum(b["count"] for b in buckets.values())
    return {"total_active_deals": total_active, "buckets": buckets}


async def operations_risk(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    deals = await _fetch_deals(db, ctx)
    contracts = await _fetch_contracts(db, ctx)
    ref = now()
    items = []
    by_kind = {"lead_cold": 0, "financial": 0, "delivery": 0}
    for d in deals:
        if d.get("stage") in OPEN_STAGES and (parse_dt(d.get("expected_close")) or ref) < ref:
            by_kind["lead_cold"] += 1
            items.append({"kind": "lead_cold", "id": d.get("id"), "label": d.get("title"),
                          "company": d.get("company"), "segment": "warning"})
    for c in contracts:
        out = _contract_outstanding(c)
        if out > 0 and (_contract_overdue_sign(c, ref) or (ref - (parse_dt(c.get("created_at")) or ref)).days > 30):
            by_kind["financial"] += 1
            items.append({"kind": "financial", "id": c.get("id"), "label": c.get("number"),
                          "company": c.get("company"), "outstanding": round(out, 2), "segment": "critical"})
    return {"items": items, "total": len(items), "by_kind": by_kind, "by_segment": {},
            "scope": {"all": ctx["all"], "managers": ctx["managers"]}}


async def operations_team(db, user) -> Dict[str, Any]:
    pnl = await finance_managers_pnl(db, user)
    return {"items": pnl["items"], "total": pnl["total"]}


# ─────────────────────────────────────────────────────────────────────────────
#  EXECUTIVE (Wave 16)
# ─────────────────────────────────────────────────────────────────────────────
async def executive_dashboard(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    ops = await operations_dashboard(db, user)
    contracts = await _fetch_contracts(db, ctx)
    fc = await finance_forecast(db, user)
    ref = now()
    customers = await db.customers.count_documents({})

    unsigned = sum(1 for c in contracts if c.get("status") in ("sent", "pending_approval", "draft"))
    pending_appr = sum(1 for c in contracts if c.get("status") == "pending_approval")
    active_ctr = sum(1 for c in contracts if c.get("status") in ("active", "signed"))
    expiring = sum(1 for c in contracts if c.get("status") == "active"
                   and (parse_dt(c.get("due_signature_at")) or ref) < ref + timedelta(days=14))

    tiles = dict(ops["tiles"])
    tiles.update({
        "active_customers": customers, "unsigned_contracts": unsigned,
        "pending_approvals": pending_appr, "active_contracts": active_ctr,
        "expiring_contracts": expiring,
    })
    return {"as_of": ref.isoformat(), "tiles": tiles,
            "horizons": fc["how_much"]["horizons"], "currency": CURRENCY}


async def executive_forecast(db, user) -> Dict[str, Any]:
    fc = await finance_forecast(db, user)
    h = fc["how_much"]["horizons"]
    out = {}
    for k, v in h.items():
        out[k] = {"expected_revenue": v["gross"], "expected_profit": v["profit"],
                  "weighted_revenue": v["weighted"], "pipeline_value": v["gross"], "deals": v["deals"]}
    return {"as_of": fc["as_of"], "horizons": out, "currency": CURRENCY}


async def executive_risks(db, user) -> Dict[str, Any]:
    r = await operations_risk(db, user)
    summary = {"critical": sum(1 for i in r["items"] if i.get("segment") == "critical"),
               "at_risk": sum(1 for i in r["items"] if i.get("segment") == "at_risk"),
               "warning": sum(1 for i in r["items"] if i.get("segment") == "warning")}
    return {"as_of": now().isoformat(), "items": r["items"], "total": r["total"],
            "by_kind": r["by_kind"], "by_segment": {}, "summary": summary,
            "scope": r["scope"]}


# ─────────────────────────────────────────────────────────────────────────────
#  CONTRACTS (Wave 15)
# ─────────────────────────────────────────────────────────────────────────────
async def contracts_overview(db, user) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    contracts = await _fetch_contracts(db, ctx)
    ref = now()
    total_value = sum(_num(c.get("value") or c.get("amount")) for c in contracts)
    active_value = sum(_num(c.get("value") or c.get("amount")) for c in contracts if c.get("status") in ("signed", "active"))
    unsigned_value = sum(_num(c.get("value") or c.get("amount")) for c in contracts if c.get("status") in ("sent", "pending_approval", "draft"))
    overdue_sig = sum(1 for c in contracts if _contract_overdue_sign(c, ref))

    seg = {"healthy": 0, "unsigned": 0, "pending_approval": 0, "critical": 0, "draft": 0, "archived": 0}
    for c in contracts:
        st = c.get("status")
        if _contract_overdue_sign(c, ref):
            seg["critical"] += 1
        elif st in ("active", "signed"):
            seg["healthy"] += 1
        elif st == "sent":
            seg["unsigned"] += 1
        elif st == "pending_approval":
            seg["pending_approval"] += 1
        elif st == "draft":
            seg["draft"] += 1
        elif st == "archived":
            seg["archived"] += 1
    return {"as_of": ref.isoformat(),
            "totals": {"contracts": len(contracts), "total_value": round(total_value, 2),
                       "active_value": round(active_value, 2), "unsigned_value": round(unsigned_value, 2),
                       "overdue_signature": overdue_sig, "healthy_count": seg["healthy"]},
            "by_segment": seg, "currency": CURRENCY,
            "scope": {"all": ctx["all"], "managers": ctx["managers"]}}


async def contracts_list(db, user, status: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    ctx = await scope_ctx(db, user)
    contracts = await _fetch_contracts(db, ctx)
    if status and status != "all":
        contracts = [c for c in contracts if c.get("status") == status]
    contracts.sort(key=lambda c: parse_dt(c.get("updated_at") or c.get("created_at")) or now(), reverse=True)
    items = []
    for c in contracts[:limit]:
        items.append({"id": c.get("id"), "number": c.get("number"), "customerId": c.get("customerId"),
                      "customer_name": c.get("customer_name"), "company": c.get("company"),
                      "status": c.get("status"), "status_label": CTR_STATUS_LABELS_UK.get(c.get("status"), c.get("status")),
                      "value": round(_num(c.get("value") or c.get("amount")), 2), "amount": round(_num(c.get("amount")), 2),
                      "paid_amount": round(_num(c.get("paid_amount")), 2), "wasteType": c.get("wasteType"),
                      "created_at": c.get("created_at").isoformat() if isinstance(c.get("created_at"), datetime) else c.get("created_at"),
                      "updated_at": c.get("updated_at").isoformat() if isinstance(c.get("updated_at"), datetime) else c.get("updated_at")})
    return {"items": items, "total": len(contracts), "scope": {"all": ctx["all"], "managers": ctx["managers"]}}


async def contract_get(db, user, contract_id: str) -> Optional[Dict[str, Any]]:
    c = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    if not c:
        return None
    if isinstance(c.get("created_at"), datetime):
        c["created_at"] = c["created_at"].isoformat()
    if isinstance(c.get("updated_at"), datetime):
        c["updated_at"] = c["updated_at"].isoformat()
    c["status_label"] = CTR_STATUS_LABELS_UK.get(c.get("status"), c.get("status"))
    return c


CONTRACT_TEMPLATES = [
    {"key": "utilization", "name": "Договір на утилізацію відходів", "type": "utilization",
     "description": "Стандартний договір на утилізацію небезпечних відходів (ДСТУ).", "approval": True},
    {"key": "pickup", "name": "Договір на вивіз та транспортування", "type": "pickup",
     "description": "Вивіз і транспортування відходів спецтранспортом.", "approval": True},
    {"key": "recycling", "name": "Договір на переробку вторсировини", "type": "recycling",
     "description": "Приймання та переробка вторинної сировини.", "approval": False},
    {"key": "annual", "name": "Річний рамковий договір", "type": "framework",
     "description": "Рамкова угода на регулярне обслуговування підприємства.", "approval": True},
]

LIFECYCLE_MAP = {
    "send": "sent", "approve": "active", "reject": "draft", "sign": "signed",
    "amend": "draft", "archive": "archived", "open": "active", "cancel": "cancelled",
}


async def contract_lifecycle(db, user, contract_id: str, action: str, note: str = "") -> Dict[str, Any]:
    c = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    if not c:
        return {"ok": False, "error": "not_found"}
    new_status = LIFECYCLE_MAP.get(action)
    if not new_status:
        return {"ok": False, "error": "bad_action"}
    patch: Dict[str, Any] = {"status": new_status, "updated_at": now()}
    if new_status == "signed":
        patch["signed_at"] = now().isoformat()
    await db.contracts.update_one({"id": contract_id}, {"$set": patch, "$push": {
        "status_history": {"status": new_status, "at": now().isoformat(),
                           "by": (user or {}).get("email") or (user or {}).get("id"), "note": note}}})
    return {"ok": True, "status": new_status}


# ─────────────────────────────────────────────────────────────────────────────
#  DEAL360 (Wave 6 + 11)
# ─────────────────────────────────────────────────────────────────────────────
def _deal_health(deal: Dict[str, Any], contracts: List[Dict[str, Any]], ref: datetime) -> Dict[str, Any]:
    score = 70
    reasons = []
    stage = deal.get("stage")
    if stage == "won":
        score = 100
    elif stage == "lost":
        score = 0; reasons.append("Угоду втрачено")
    else:
        ec = parse_dt(deal.get("expected_close"))
        if ec and ec < ref:
            score -= 25; reasons.append("Прострочена очікувана дата закриття")
        idx = DEAL_STAGES.index(stage) if stage in DEAL_STAGES else 0
        score += idx * 4
        out = sum(_contract_outstanding(c) for c in contracts)
        if out > 0:
            score -= 10; reasons.append("Є несплачений залишок за договором")
    score = max(0, min(100, score))
    label = "healthy" if score >= 70 else "warning" if score >= 40 else "critical"
    return {"score": score, "label": label, "reasons": reasons}


async def deal_360(db, user, deal_id: str) -> Optional[Dict[str, Any]]:
    deal = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        return None
    ref = now()
    contracts = await db.contracts.find({"deal_id": deal_id}, {"_id": 0}).to_list(100)
    payments = await db.payments.find({"deal_id": deal_id}, {"_id": 0}).to_list(500)
    company = None
    if deal.get("company_id"):
        company = await db.waste_companies.find_one({"id": deal["company_id"]}, {"_id": 0})

    def _s(d):
        for k in ("created_at", "updated_at", "signed_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat()
        return d

    contracts = [_s(c) for c in contracts]
    payments = [_s(p) for p in payments]
    deal = _s(dict(deal))

    income = sum(_num(p.get("amount")) for p in payments if p.get("kind") == "income")
    expense = sum(_num(p.get("amount")) for p in payments if p.get("kind") == "expense")
    stage = deal.get("stage")
    stage_idx = DEAL_STAGES.index(stage) if stage in DEAL_STAGES else 0

    return {
        "deal": deal,
        "company": company,
        "contracts": contracts,
        "payments": payments,
        "health": _deal_health(deal, contracts, ref),
        "stage_progress": {
            "stage": stage, "label": STAGE_LABELS_UK.get(stage, stage),
            "index": stage_idx, "total": len(DEAL_STAGES),
            "percent": 100 if stage == "won" else (round((stage_idx / (len(DEAL_STAGES) - 2)) * 100) if stage != "lost" else 0),
            "stages": [{"key": s, "label": STAGE_LABELS_UK[s], "done": i <= stage_idx and stage != "lost"}
                       for i, s in enumerate(DEAL_STAGES) if s != "lost"],
        },
        "financials": {"amount": _num(deal.get("amount")), "cost": _num(deal.get("cost")),
                       "income": round(income, 2), "expense": round(expense, 2),
                       "outstanding": round(sum(_contract_outstanding(c) for c in contracts), 2),
                       "currency": CURRENCY},
    }


async def deal_stage_progress(db, user, deal_id: str) -> Optional[Dict[str, Any]]:
    full = await deal_360(db, user, deal_id)
    return full["stage_progress"] if full else None


async def deal_transition(db, user, deal_id: str, to_stage: str, note: str = "") -> Dict[str, Any]:
    if to_stage not in DEAL_STAGES:
        return {"ok": False, "error": "bad_stage"}
    deal = await db.deals.find_one({"id": deal_id}, {"_id": 0})
    if not deal:
        return {"ok": False, "error": "not_found"}
    await db.deals.update_one({"id": deal_id}, {"$set": {"stage": to_stage, "updated_at": now(),
                              "probability": STAGE_PROB.get(to_stage, 0.3)},
                              "$push": {"stage_history": {"stage": to_stage, "at": now().isoformat(),
                                        "by": (user or {}).get("email") or (user or {}).get("id"), "note": note}}})
    return {"ok": True, "stage": to_stage}
