"""
BIBI Cars — Wave 17 — Source scanners
========================================

Pure functions that read existing data (Operations360 / Contract360 /
Forecast360 / Delivery360) and *suggest* actions. They never write —
the sync layer (sync.py) decides whether to upsert each suggestion.

A suggestion shape:
    {
      "source":      "operations" | "contract" | ... ,
      "type":        ACTION_TYPES,
      "key":         deterministic dedup key  (source + type + entity_id),
      "title":       short human label,
      "description": longer reason,
      "priority":    one of ACTION_PRIORITIES,
      "owner_id":    suggested owner from the source entity,
      "owner_name":  suggested owner name,
      "entity_type": deal/contract/shipment/lead,
      "entity_id":   the offending entity,
      "deal_id":     deal context (for drilldowns),
      "impact":      € at stake,
      "due_days":    suggested due offset from now,
      "href":        suggested drilldown URL,
      "tags":        free-form tags,
    }
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
from collections import defaultdict

from app.wave14.aggregations import compute_bottlenecks, compute_risk_center
from app.wave15.aggregations import compute_contract_risk
from app.wave12.forecasting import compute_forecast_risk


# Mapping from operations-bucket key → (action_type, priority, due_days, title)
OPS_RULES = {
    "waiting_deposit":    ("chase_deposit",        "high",     1, "Chase deposit"),
    "waiting_payment":    ("chase_payment",        "medium",   2, "Chase payment"),
    "no_carrier":         ("assign_carrier",       "high",     1, "Assign carrier"),
    "stuck_at_customs":   ("escalate_customs",     "critical", 0, "Escalate customs"),
    "stuck_at_port":      ("escalate_port",        "high",     1, "Push port handler"),
    "missing_documents":  ("upload_documents",     "medium",   2, "Upload delivery documents"),
    "financial_at_risk":  ("collection_workflow",  "critical", 0, "Trigger collection workflow"),
    "stale_no_movement":  ("manual",               "medium",   2, "Manager call — no movement >7d"),
}

# Mapping from contract segment → (action_type, priority, due_days, title)
CONTRACT_RULES = {
    "unsigned":         ("chase_signature",          "high",     2, "Chase customer signature"),
    "pending_approval": ("approve_internally",       "medium",   1, "Approve contract internally"),
    "missing_annex":    ("upload_annex",             "medium",   3, "Upload missing annex"),
    "wrong_version":    ("replace_contract_version", "medium",   3, "Replace with current version"),
    "critical":         ("renew_or_archive",         "critical", 0, "Renew or archive contract"),
    "draft":            ("approve_internally",       "low",      5, "Submit draft for approval"),
}

# Delivery segments handled via risk_center (kind = delivery).
DELIVERY_RULES = {
    "critical":   ("operations_escalation", "critical", 0, "Delivery critical — ops escalation"),
    "delayed":    ("push_carrier",          "high",     1, "Delivery delayed — push carrier"),
    "delay_risk": ("push_carrier",          "medium",   2, "Delivery delay risk — contact carrier"),
}

# Lead cold via risk_center.
LEAD_RULES = {
    "critical": ("reactivate_lead", "high",     1, "Reactivate cold lead"),
    "at_risk":  ("reactivate_lead", "medium",   2, "Reactivate cooling lead"),
    "warning":  ("reactivate_lead", "low",      3, "Touch base with lead"),
}

# Forecast risk fallback rule.
FORECAST_RULE = ("forecast_review", "medium", 3, "Review forecast risk item")


def _dedup_key(source: str, action_type: str, entity_id: str) -> str:
    return f"{source}:{action_type}:{entity_id or '_'}"


async def scan_operations(db, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    bottle = await compute_bottlenecks(db, user)
    # We also need a deal-id → (manager_id, manager_name, impact €) map
    deals = await db.deals.find({}, {"_id": 0, "id": 1, "price": 1, "final_price": 1,
                                       "managerId": 1, "manager_id": 1,
                                       "manager_name": 1, "managerName": 1,
                                       "title": 1}).to_list(length=5000)
    deal_map = {d.get("id"): d for d in deals if d.get("id")}
    out: List[Dict[str, Any]] = []
    for bucket_key, rule in OPS_RULES.items():
        bucket = (bottle.get("buckets") or {}).get(bucket_key) or {}
        action_type, priority, due_days, title = rule
        for did in bucket.get("deal_ids") or []:
            d = deal_map.get(did) or {}
            mgr_id = d.get("managerId") or d.get("manager_id")
            mgr_nm = d.get("manager_name") or d.get("managerName")
            out.append({
                "source":      "operations",
                "type":        action_type,
                "key":         _dedup_key("operations", action_type, did),
                "title":       title,
                "description": bucket.get("label") or bucket_key,
                "priority":    priority,
                "owner_id":    mgr_id,
                "owner_name":  mgr_nm,
                "entity_type": "deal",
                "entity_id":   did,
                "deal_id":     did,
                "impact":      float(d.get("price") or d.get("final_price") or 0),
                "due_days":    due_days,
                "href":        f"/admin/deals/{did}/360" if did else None,
                "tags":        ["operations", bucket_key],
            })
    return out


async def scan_contracts(db, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    risk = await compute_contract_risk(db, user, limit=500)
    out: List[Dict[str, Any]] = []
    for c in risk.get("items") or []:
        seg = c.get("segment")
        rule = CONTRACT_RULES.get(seg)
        if not rule:
            continue
        action_type, priority, due_days, title = rule
        out.append({
            "source":      "contract",
            "type":        action_type,
            "key":         _dedup_key("contract", action_type, c.get("id")),
            "title":       title,
            "description": (c.get("reasons") or [""])[0] or seg,
            "priority":    priority,
            "owner_id":    c.get("manager_id"),
            "owner_name":  c.get("manager_name"),
            "entity_type": "contract",
            "entity_id":   c.get("id"),
            "deal_id":     c.get("deal_id"),
            "impact":      float(c.get("amount") or 0),
            "due_days":    due_days,
            "href":        f"/admin/contracts?id={c.get('id')}&tab=timeline",
            "tags":        ["contract", seg],
        })
    return out


async def scan_delivery_and_leads(db, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    risk = await compute_risk_center(db, user)
    deals = await db.deals.find({}, {"_id": 0, "id": 1, "price": 1, "final_price": 1,
                                       "managerId": 1, "manager_id": 1,
                                       "manager_name": 1, "managerName": 1}).to_list(length=5000)
    deal_map = {d.get("id"): d for d in deals if d.get("id")}
    out: List[Dict[str, Any]] = []
    for it in risk.get("items") or []:
        kind = it.get("risk_kind")
        seg  = it.get("segment")
        if kind == "delivery":
            rule = DELIVERY_RULES.get(seg)
        elif kind == "lead_cold":
            rule = LEAD_RULES.get(seg)
        else:
            continue
        if not rule:
            continue
        action_type, priority, due_days, title = rule
        # find a deal/lead owner
        eid    = it.get("entity_id")
        deal_id = None
        owner_id = None; owner_name = it.get("manager")
        impact = 0.0
        if kind == "delivery":
            # link back to the deal carrying the shipment via href
            href = it.get("href") or ""
            if "/admin/deals/" in href:
                deal_id = href.split("/admin/deals/")[1].split("/")[0]
            d = deal_map.get(deal_id) or {}
            owner_id = d.get("managerId") or d.get("manager_id") or owner_id
            impact   = float(d.get("price") or d.get("final_price") or 0)
            entity_type = "shipment"
        else:
            entity_type = "lead"
        out.append({
            "source":      "delivery" if kind == "delivery" else "manual",
            "type":        action_type,
            "key":         _dedup_key("delivery" if kind == "delivery" else "lead", action_type, eid),
            "title":       title,
            "description": (it.get("reasons") or [""])[0] or seg,
            "priority":    priority,
            "owner_id":    owner_id,
            "owner_name":  owner_name,
            "entity_type": entity_type,
            "entity_id":   eid,
            "deal_id":     deal_id,
            "impact":      impact,
            "due_days":    due_days,
            "href":        it.get("href"),
            "tags":        [kind, seg],
        })
    return out


async def scan_forecast(db, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Forecast360 surfaces top-N risky deals via /forecast/risk; we recreate
    # a smaller payload via the aggregator directly to avoid HTTP-round-trip.
    risk = await compute_forecast_risk(db, user)
    items = risk.get("items") or []
    out: List[Dict[str, Any]] = []
    action_type, priority, due_days, title = FORECAST_RULE
    for it in items[:60]:   # cap (forecast risk can be wide)
        eid = it.get("deal_id")
        out.append({
            "source":      "forecast",
            "type":        action_type,
            "key":         _dedup_key("forecast", action_type, eid),
            "title":       title,
            "description": ", ".join((it.get("reasons") or [])[:2]) or "Forecast risk item",
            "priority":    "high" if (it.get("risk_kind") == "financial" and it.get("weighted", 0) >= 10000) else priority,
            "owner_id":    it.get("manager_id") or it.get("managerId"),
            "owner_name":  it.get("manager_name") or it.get("managerName"),
            "entity_type": "deal",
            "entity_id":   eid,
            "deal_id":     eid,
            "impact":      float(it.get("weighted") or it.get("gross") or 0),
            "due_days":    due_days,
            "href":        f"/admin/deals/{eid}/360" if eid else None,
            "tags":        ["forecast", (it.get("risk_kind") or "")],
        })
    return out


async def scan_all(db, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run every scanner and return the merged list (dedup-key-unique)."""
    seen: Dict[str, Dict[str, Any]] = {}
    for scanner in (scan_operations, scan_contracts, scan_delivery_and_leads, scan_forecast):
        try:
            for s in await scanner(db, user):
                k = s["key"]
                # Keep the worst-priority duplicate.
                if k in seen:
                    if _prio_rank(s["priority"]) < _prio_rank(seen[k]["priority"]):
                        seen[k] = s
                else:
                    seen[k] = s
        except Exception:
            # Never let one source kill the rest
            continue
    return list(seen.values())


def _prio_rank(p: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(p or "low", 3)


def list_source_catalogue() -> List[Dict[str, Any]]:
    """Return a flat catalogue of suggestion rules — useful for the UI picker
    and for tests asserting we cover every bucket of every source."""
    cat: List[Dict[str, Any]] = []
    for bucket, (typ, prio, due, title) in OPS_RULES.items():
        cat.append({"source": "operations", "bucket": bucket, "type": typ, "priority": prio, "due_days": due, "title": title})
    for seg, (typ, prio, due, title) in CONTRACT_RULES.items():
        cat.append({"source": "contract",   "bucket": seg, "type": typ, "priority": prio, "due_days": due, "title": title})
    for seg, (typ, prio, due, title) in DELIVERY_RULES.items():
        cat.append({"source": "delivery",   "bucket": seg, "type": typ, "priority": prio, "due_days": due, "title": title})
    for seg, (typ, prio, due, title) in LEAD_RULES.items():
        cat.append({"source": "lead",       "bucket": seg, "type": typ, "priority": prio, "due_days": due, "title": title})
    cat.append({"source": "forecast", "bucket": "risk", "type": FORECAST_RULE[0],
                "priority": FORECAST_RULE[1], "due_days": FORECAST_RULE[2], "title": FORECAST_RULE[3]})
    return cat


__all__ = [
    "scan_operations", "scan_contracts", "scan_delivery_and_leads",
    "scan_forecast", "scan_all",
    "OPS_RULES", "CONTRACT_RULES", "DELIVERY_RULES", "LEAD_RULES", "FORECAST_RULE",
    "list_source_catalogue",
]
