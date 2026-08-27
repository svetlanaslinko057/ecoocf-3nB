"""
Wave 12 — Finance aggregations (read-only).

Every public function takes a `scope` dict (returned by
`finance_scope_for_user`) so the caller never has to think about RBAC again.

`scope` shape:

    {
        "all":          True/False,
        "manager_ids":  list[str] | None,  # None when "all"
    }

When `all` is True we don't add any owner filter to the mongo queries.
When `all` is False we restrict by `managerId in [...]` (matching all the
common owner fields the legacy data uses).

All functions are conservative — they never raise on a missing collection
or malformed document; instead they degrade to zero / empty list.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.wave12.aggregations")


# ───────────────────────── Scope ────────────────────────────────────────────
def _me_id(user: Dict[str, Any]) -> str:
    return user.get("managerId") or user.get("id") or user.get("email") or ""


def _is_admin(role: str) -> bool:
    return role in ("admin", "owner", "master_admin")


async def finance_scope_for_user(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the manager-id whitelist for the current user.

    - admin/owner/master_admin → all managers
    - team_lead                → own + everyone whose staff.team_lead_id == me
    - manager                  → own only
    """
    role = (user.get("role") or "").lower()
    if _is_admin(role):
        return {"all": True, "manager_ids": None}

    me = _me_id(user)
    if role != "team_lead":
        return {"all": False, "manager_ids": [me] if me else []}

    # Team lead — pull team members
    ids = {me} if me else set()
    try:
        cursor = db.staff.find(
            {"$or": [{"team_lead_id": me}, {"teamLeadId": me}]},
            {"_id": 0, "id": 1, "managerId": 1, "email": 1},
        )
        async for row in cursor:
            for key in ("id", "managerId", "email"):
                v = row.get(key)
                if v:
                    ids.add(v)
    except Exception as e:
        logger.warning("[wave12] team_lead scope load failed: %s", e)
    return {"all": False, "manager_ids": list(ids)}


def _scope_query(scope: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """Build a $or filter against the given list of owner fields."""
    if scope.get("all"):
        return {}
    mids = scope.get("manager_ids") or []
    if not mids:
        # No managers in scope → match nothing (sentinel that never matches)
        return {"_id": "__no_match__"}
    return {"$or": [{f: {"$in": mids}} for f in fields]}


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _iso(ts: Any) -> str:
    if not ts:
        return ""
    if hasattr(ts, "isoformat"):
        try:
            return ts.isoformat()
        except Exception:
            return str(ts)
    return str(ts)


def _days_ago(iso: str) -> Optional[int]:
    if not iso:
        return None
    try:
        # Strip trailing Z if present
        s = iso.rstrip("Z")
        # fromisoformat handles tz-aware ISO strings in py3.11+
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, delta.days)
    except Exception:
        return None


# ───────────────────────── Deals helpers ────────────────────────────────────
DEAL_OWNER_FIELDS = ["managerId", "manager_id", "assigned_to", "assigneeId"]
DEPOSIT_OWNER_FIELDS = ["managerId", "manager_id", "owner_id", "created_by"]
PAYMENT_OWNER_FIELDS = ["managerId", "manager_id", "owner_id", "created_by"]


async def _deals_in_scope(db, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = _scope_query(scope, DEAL_OWNER_FIELDS)
    # Project only the fields we use for aggregation
    proj = {
        "_id": 0, "id": 1, "title": 1, "vin": 1,
        "managerId": 1, "manager_id": 1, "assigned_to": 1, "assigneeId": 1,
        "customer_id": 1, "customerId": 1,
        "currency": 1, "total_price": 1, "totalValue": 1, "clientPrice": 1,
        "internal_cost": 1, "internalCost": 1,
        "purchase_price": 1, "purchasePrice": 1,
        "profit": 1, "estimatedMargin": 1, "realProfit": 1,
        "status": 1, "stage": 1, "pipeline_stage": 1,
        "created_at": 1, "updated_at": 1, "deposit_paid_at": 1,
        "delivered_at": 1,
    }
    cursor = db.deals.find(query, proj)
    return await cursor.to_list(length=5000)


def _deal_revenue(deal: Dict[str, Any]) -> float:
    return _num(deal.get("total_price")
                or deal.get("totalValue")
                or deal.get("clientPrice"))


def _deal_cost(deal: Dict[str, Any]) -> float:
    return _num(deal.get("internal_cost")
                or deal.get("internalCost")
                or deal.get("purchase_price")
                or deal.get("purchasePrice"))


def _deal_owner(deal: Dict[str, Any]) -> Optional[str]:
    for k in DEAL_OWNER_FIELDS:
        v = deal.get(k)
        if v:
            return v
    return None


# ───────────────────────── Overview ─────────────────────────────────────────
async def build_finance_overview(db, scope: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the KPI bundle used by the Finance360 Overview tab."""
    deals = await _deals_in_scope(db, scope)
    deal_ids = [d["id"] for d in deals if d.get("id")]
    deal_by_id = {d["id"]: d for d in deals if d.get("id")}

    revenue_total       = 0.0
    cost_total          = 0.0
    profit_total        = 0.0
    delivered_revenue   = 0.0
    delivered_count     = 0
    open_count          = 0
    pipeline_revenue    = 0.0  # non-terminal deals
    by_stage_counts: Dict[str, int] = {}

    for d in deals:
        r = _deal_revenue(d)
        c = _deal_cost(d)
        p = _num(d.get("profit") or d.get("realProfit"))
        if not p and r and c:
            p = r - c
        revenue_total += r
        cost_total    += c
        profit_total  += p

        stage = (d.get("pipeline_stage") or d.get("stage") or d.get("status") or "").lower()
        by_stage_counts[stage] = by_stage_counts.get(stage, 0) + 1

        terminal_neg = stage in {"cancelled", "lost", "closed_lost"}
        terminal_pos = stage in {"delivered", "completed", "closed"}
        if terminal_pos:
            delivered_revenue += r
            delivered_count   += 1
        elif terminal_neg:
            pass
        else:
            open_count       += 1
            pipeline_revenue += r

    # ── deposits + payments aggregations (one pass each) ────────────────
    deposit_received   = 0.0
    deposit_pending    = 0.0
    payment_received   = 0.0
    payment_pending    = 0.0
    refund_pending     = 0.0
    refund_paid        = 0.0
    refund_count_pend  = 0
    refund_count_paid  = 0

    cash_30d  = 0.0
    horizon   = datetime.now(timezone.utc) - timedelta(days=30)

    deals_filter = {"deal_id": {"$in": deal_ids}} if deal_ids else None

    if deals_filter is not None:
        try:
            async for dep in db.legal_deposits.find(deals_filter, {"_id": 0}):
                s = (dep.get("status") or "").lower()
                amt = _num(dep.get("amount"))
                if s in {"confirmed", "paid", "received"}:
                    deposit_received += amt
                elif s in {"pending", "draft", "requested", "in_processing"}:
                    deposit_pending += amt
                elif s == "refunded":
                    refund_paid       += amt
                    refund_count_paid += 1
                # Cash flow: count confirmed deposits in the last 30d
                conf_at = dep.get("confirmed_at") or dep.get("paid_at") or dep.get("created_at")
                try:
                    s_ts = conf_at.rstrip("Z") if isinstance(conf_at, str) else None
                    dt = datetime.fromisoformat(s_ts) if s_ts else None
                    if dt and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt and dt >= horizon and s in {"confirmed", "paid", "received"}:
                        cash_30d += amt
                except Exception:
                    pass
        except Exception as e:
            logger.warning("[wave12] legal_deposits scan failed: %s", e)

        try:
            async for pay in db.payments.find(deals_filter, {"_id": 0}):
                s = (pay.get("status") or "").lower()
                amt = _num(pay.get("amount"))
                if s in {"confirmed", "paid", "received"}:
                    payment_received += amt
                elif s in {"pending", "scheduled"}:
                    payment_pending += amt
                elif s == "refunded":
                    refund_paid       += amt
                    refund_count_paid += 1
                elif s == "refund_pending":
                    refund_pending      += amt
                    refund_count_pend   += 1
                conf_at = pay.get("confirmed_at") or pay.get("paid_at") or pay.get("created_at")
                try:
                    s_ts = conf_at.rstrip("Z") if isinstance(conf_at, str) else None
                    dt = datetime.fromisoformat(s_ts) if s_ts else None
                    if dt and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt and dt >= horizon and s in {"confirmed", "paid", "received"}:
                        cash_30d += amt
                except Exception:
                    pass
        except Exception as e:
            logger.warning("[wave12] payments scan failed: %s", e)

    # Money already in the door
    cash_in_door = round(deposit_received + payment_received, 2)

    # Outstanding = sum of (revenue - cash_in_door) for non-terminal deals
    # NB: this requires per-deal numbers; we already have them deal-by-deal
    # but recomputing here keeps the function self-contained.
    outstanding_total = 0.0
    at_risk_total     = 0.0
    expected_revenue  = 0.0
    for d in deals:
        stage = (d.get("pipeline_stage") or d.get("stage") or d.get("status") or "").lower()
        if stage in {"cancelled", "lost", "closed_lost"}:
            continue
        r = _deal_revenue(d)
        if stage in {"delivered", "completed", "closed"}:
            continue
        expected_revenue += r

    outstanding_total = max(0.0, revenue_total - cash_in_door - delivered_revenue + 0)
    # Better: outstanding from non-terminal pipeline revenue minus cash already collected
    outstanding_total = max(0.0, pipeline_revenue - cash_in_door)

    # At-risk: revenue from deals that are stuck (open but updated_at >14d ago)
    risk_horizon = datetime.now(timezone.utc) - timedelta(days=14)
    for d in deals:
        stage = (d.get("pipeline_stage") or d.get("stage") or d.get("status") or "").lower()
        if stage in {"cancelled", "lost", "closed_lost", "delivered", "completed", "closed"}:
            continue
        u = d.get("updated_at") or d.get("created_at")
        try:
            s_ts = u.rstrip("Z") if isinstance(u, str) else None
            dt = datetime.fromisoformat(s_ts) if s_ts else None
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt and dt < risk_horizon:
                at_risk_total += _deal_revenue(d)
        except Exception:
            pass

    return {
        "scope":             {"all": scope.get("all"), "managers": len(scope.get("manager_ids") or [])},
        "currency":          "EUR",  # canonical
        "counts": {
            "deals_total":   len(deals),
            "deals_open":    open_count,
            "deals_delivered": delivered_count,
            "refunds_pending": refund_count_pend,
            "refunds_paid":    refund_count_paid,
        },
        "totals": {
            "revenue":           round(revenue_total, 2),
            "cost":              round(cost_total, 2),
            "profit":            round(profit_total, 2),
            "delivered_revenue": round(delivered_revenue, 2),
            "expected_revenue":  round(expected_revenue, 2),
            "deposit_received":  round(deposit_received, 2),
            "deposit_pending":   round(deposit_pending, 2),
            "payment_received":  round(payment_received, 2),
            "payment_pending":   round(payment_pending, 2),
            "cash_in_door":      cash_in_door,
            "outstanding":       round(outstanding_total, 2),
            "at_risk":           round(at_risk_total, 2),
            "refund_paid":       round(refund_paid, 2),
            "refund_pending":    round(refund_pending, 2),
            "cash_flow_30d":     round(cash_30d, 2),
        },
        "by_stage":          by_stage_counts,
        "_deal_ids":         deal_ids,
        "_deals_by_id":      deal_by_id,
    }


# ───────────────────────── Transactions journal ─────────────────────────────
async def list_finance_transactions(
    db,
    scope: Dict[str, Any],
    *,
    txn_type: Optional[str] = None,
    status:   Optional[str] = None,
    manager_id: Optional[str] = None,
    deal_id:    Optional[str] = None,
    customer_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    q:         Optional[str] = None,
    limit:     int = 200,
    offset:    int = 0,
) -> Dict[str, Any]:
    """Return a unified, paginated, filterable journal across:
        * `legal_deposits`  → type=deposit / refund (if refunded)
        * `payments`        → type=payment / refund (if refunded)

    Each item is normalised to:
        { id, type, deal_id, deal_title, customer_id, customer_name,
          manager_id, manager_name, amount, currency, status, method,
          note, at }
    Items are returned newest-first.
    """
    # Pre-resolve deals-in-scope so we know which deal_ids are visible AND we
    # can attach deal_title / customer_id without per-row lookups.
    deals = await _deals_in_scope(db, scope)
    deals_by_id = {d["id"]: d for d in deals if d.get("id")}
    visible_deal_ids = set(deals_by_id.keys())

    # Customer name cache (resolved lazily)
    customer_name_cache: Dict[str, str] = {}

    async def resolve_customer_name(cid: Optional[str]) -> Optional[str]:
        if not cid:
            return None
        if cid in customer_name_cache:
            return customer_name_cache[cid]
        try:
            doc = await db.customers.find_one(
                {"$or": [{"id": cid}, {"_id": cid}]},
                {"_id": 0, "name": 1, "first_name": 1, "last_name": 1, "email": 1},
            )
        except Exception:
            doc = None
        if not doc:
            customer_name_cache[cid] = ""
            return None
        name = doc.get("name") or " ".join(
            x for x in (doc.get("first_name"), doc.get("last_name")) if x
        ) or doc.get("email")
        customer_name_cache[cid] = name or ""
        return name

    items: List[Dict[str, Any]] = []

    def in_window(at: Optional[str]) -> bool:
        if not at:
            return True
        try:
            s = at.rstrip("Z") if isinstance(at, str) else None
            dt = datetime.fromisoformat(s) if s else None
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if date_from:
                df = datetime.fromisoformat(date_from.rstrip("Z"))
                if df.tzinfo is None:
                    df = df.replace(tzinfo=timezone.utc)
                if dt and dt < df:
                    return False
            if date_to:
                dtt = datetime.fromisoformat(date_to.rstrip("Z"))
                if dtt.tzinfo is None:
                    dtt = dtt.replace(tzinfo=timezone.utc)
                if dt and dt > dtt:
                    return False
        except Exception:
            return True
        return True

    # ── Deposits → may produce 1 or 2 transactions (one for the deposit,
    #    one for the refund if applicable)
    if not deal_id or deal_id in visible_deal_ids:
        dep_q: Dict[str, Any] = {}
        if deal_id:
            dep_q["deal_id"] = deal_id
        else:
            dep_q["deal_id"] = {"$in": list(visible_deal_ids)} if visible_deal_ids else "__no__"

        try:
            async for dep in db.legal_deposits.find(dep_q, {"_id": 0}):
                deal = deals_by_id.get(dep.get("deal_id")) or {}
                if manager_id and _deal_owner(deal) != manager_id:
                    continue
                if customer_id and (
                    deal.get("customer_id") or deal.get("customerId")
                ) != customer_id:
                    continue
                base_at = (
                    dep.get("confirmed_at") or dep.get("paid_at")
                    or dep.get("rejected_at") or dep.get("created_at")
                )
                if not in_window(base_at):
                    continue

                base = {
                    "id":            f"dep:{dep.get('id')}",
                    "ref_id":        dep.get("id"),
                    "type":          "deposit",
                    "deal_id":       dep.get("deal_id"),
                    "deal_title":    deal.get("title") or "",
                    "customer_id":   deal.get("customer_id") or deal.get("customerId"),
                    "manager_id":    _deal_owner(deal),
                    "amount":        round(_num(dep.get("amount")), 2),
                    "currency":      (dep.get("currency") or deal.get("currency") or "EUR").upper(),
                    "status":        (dep.get("status") or "pending").lower(),
                    "method":        dep.get("method"),
                    "note":          dep.get("note") or dep.get("rejection_reason"),
                    "at":            base_at,
                }
                items.append(base)

                # Separate row for the refund (so it shows up on the Refunds
                # filter naturally).
                if (dep.get("status") or "").lower() == "refunded" and dep.get("refunded_at"):
                    refund_row = {
                        **base,
                        "id":     f"dep_ref:{dep.get('id')}",
                        "type":   "refund",
                        "amount": round(_num(dep.get("amount")), 2),
                        "status": "paid",
                        "note":   dep.get("refund_reason") or "Deposit refunded",
                        "at":     dep.get("refunded_at"),
                    }
                    if in_window(refund_row["at"]):
                        items.append(refund_row)
        except Exception as e:
            logger.warning("[wave12] deposits journal scan failed: %s", e)

        # ── Payments
        pay_q: Dict[str, Any] = {}
        if deal_id:
            pay_q["deal_id"] = deal_id
        else:
            pay_q["deal_id"] = {"$in": list(visible_deal_ids)} if visible_deal_ids else "__no__"

        try:
            async for pay in db.payments.find(pay_q, {"_id": 0}):
                deal = deals_by_id.get(pay.get("deal_id")) or {}
                if manager_id and _deal_owner(deal) != manager_id:
                    continue
                if customer_id and (
                    deal.get("customer_id") or deal.get("customerId")
                ) != customer_id:
                    continue
                base_at = (
                    pay.get("confirmed_at") or pay.get("paid_at")
                    or pay.get("failed_at") or pay.get("created_at")
                )
                if not in_window(base_at):
                    continue
                base = {
                    "id":          f"pay:{pay.get('id')}",
                    "ref_id":      pay.get("id"),
                    "type":        "payment",
                    "deal_id":     pay.get("deal_id"),
                    "deal_title":  deal.get("title") or "",
                    "customer_id": deal.get("customer_id") or deal.get("customerId"),
                    "manager_id":  _deal_owner(deal),
                    "amount":      round(_num(pay.get("amount")), 2),
                    "currency":    (pay.get("currency") or deal.get("currency") or "EUR").upper(),
                    "status":      (pay.get("status") or "pending").lower(),
                    "method":      pay.get("method") or pay.get("type"),
                    "note":        pay.get("note") or pay.get("failed_reason"),
                    "at":          base_at,
                }
                items.append(base)
                if (pay.get("status") or "").lower() == "refunded" and pay.get("refunded_at"):
                    refund_row = {
                        **base,
                        "id":     f"pay_ref:{pay.get('id')}",
                        "type":   "refund",
                        "status": "paid",
                        "note":   pay.get("refund_reason") or "Payment refunded",
                        "at":     pay.get("refunded_at"),
                    }
                    if in_window(refund_row["at"]):
                        items.append(refund_row)
        except Exception as e:
            logger.warning("[wave12] payments journal scan failed: %s", e)

    # ── Filters that need post-processing
    if txn_type:
        items = [it for it in items if it["type"] == txn_type]
    if status:
        items = [it for it in items if it["status"] == status]
    if q:
        ql = q.lower()
        items = [
            it for it in items
            if (it.get("deal_title") or "").lower().find(ql) >= 0
            or (it.get("deal_id") or "").lower().find(ql) >= 0
            or (it.get("note") or "").lower().find(ql) >= 0
            or (it.get("ref_id") or "").lower().find(ql) >= 0
        ]

    # Resolve customer names lazily (only for the page we'll return)
    items.sort(key=lambda it: _iso(it.get("at")), reverse=True)
    total = len(items)
    page = items[offset: offset + max(1, limit)]
    for it in page:
        it["customer_name"] = await resolve_customer_name(it.get("customer_id"))

    return {
        "items":  page,
        "total":  total,
        "offset": offset,
        "limit":  limit,
    }


# ───────────────────────── Outstanding ──────────────────────────────────────
async def list_outstanding_deals(
    db,
    scope: Dict[str, Any],
    *,
    min_outstanding: float = 1.0,
    limit: int = 200,
) -> Dict[str, Any]:
    """Return the deals that still owe money, sorted by `days_overdue` desc.

    `expected` is the deal's revenue. `received` is the sum of confirmed
    deposits + confirmed payments for that deal. `outstanding = expected -
    received`. `days_overdue` is days since the deal's `updated_at` so the TL
    sees what's been sitting unmoved the longest.
    """
    deals = await _deals_in_scope(db, scope)
    deal_ids = [d["id"] for d in deals if d.get("id")]
    if not deal_ids:
        return {"items": [], "total": 0, "summary": {"outstanding": 0.0, "deals": 0}}

    received_by_deal: Dict[str, float] = {did: 0.0 for did in deal_ids}

    try:
        async for dep in db.legal_deposits.find(
            {"deal_id": {"$in": deal_ids}}, {"_id": 0, "deal_id": 1, "status": 1, "amount": 1}
        ):
            if (dep.get("status") or "").lower() in {"confirmed", "paid", "received"}:
                received_by_deal[dep["deal_id"]] = received_by_deal.get(dep["deal_id"], 0.0) + _num(dep.get("amount"))
    except Exception as e:
        logger.warning("[wave12] outstanding/deposits scan: %s", e)

    try:
        async for pay in db.payments.find(
            {"deal_id": {"$in": deal_ids}}, {"_id": 0, "deal_id": 1, "status": 1, "amount": 1}
        ):
            if (pay.get("status") or "").lower() in {"confirmed", "paid", "received"}:
                received_by_deal[pay["deal_id"]] = received_by_deal.get(pay["deal_id"], 0.0) + _num(pay.get("amount"))
    except Exception as e:
        logger.warning("[wave12] outstanding/payments scan: %s", e)

    # Customer cache for the page
    customer_cache: Dict[str, Dict[str, Any]] = {}

    async def cust(cid: Optional[str]) -> Optional[Dict[str, Any]]:
        if not cid:
            return None
        if cid in customer_cache:
            return customer_cache[cid]
        try:
            doc = await db.customers.find_one(
                {"$or": [{"id": cid}, {"_id": cid}]},
                {"_id": 0, "id": 1, "name": 1, "first_name": 1, "last_name": 1, "email": 1},
            )
        except Exception:
            doc = None
        if doc:
            doc["display_name"] = doc.get("name") or " ".join(
                x for x in (doc.get("first_name"), doc.get("last_name")) if x
            ) or doc.get("email")
        customer_cache[cid] = doc or {}
        return doc

    rows: List[Dict[str, Any]] = []
    total_outstanding = 0.0
    for d in deals:
        stage = (d.get("pipeline_stage") or d.get("stage") or d.get("status") or "").lower()
        # Skip terminal deals
        if stage in {"cancelled", "lost", "closed_lost", "delivered", "completed", "closed"}:
            continue
        expected   = _deal_revenue(d)
        received   = received_by_deal.get(d["id"], 0.0)
        outstanding = round(max(0.0, expected - received), 2)
        if outstanding < float(min_outstanding):
            continue
        last_move = d.get("updated_at") or d.get("created_at")
        rows.append({
            "deal_id":      d["id"],
            "deal_title":   d.get("title") or "",
            "vin":          d.get("vin"),
            "stage":        d.get("pipeline_stage") or d.get("stage") or d.get("status"),
            "customer_id":  d.get("customer_id") or d.get("customerId"),
            "manager_id":   _deal_owner(d),
            "currency":     d.get("currency") or "EUR",
            "expected":     round(expected, 2),
            "received":     round(received, 2),
            "outstanding":  outstanding,
            "days_overdue": _days_ago(last_move),
            "last_move":    last_move,
        })
        total_outstanding += outstanding

    # Sort by days_overdue desc, then outstanding desc
    rows.sort(key=lambda r: (r.get("days_overdue") or 0, r.get("outstanding") or 0), reverse=True)
    rows = rows[:limit]
    for r in rows:
        c = await cust(r.get("customer_id"))
        if c:
            r["customer_name"] = c.get("display_name")

    return {
        "items":   rows,
        "total":   len(rows),
        "summary": {
            "outstanding": round(total_outstanding, 2),
            "deals":       len(rows),
        },
    }
