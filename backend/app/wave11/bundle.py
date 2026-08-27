"""
Wave 11 — Deal360 bundle assembler.

Single function `build_deal360_bundle(db, deal_id)` produces everything the
Deal360 page needs in one round trip. Each sub-section is wrapped in a
best-effort try/except so a missing collection (e.g. legacy DB without
`deal_timeline`) never breaks the page.

Output shape (loosely contracted with the frontend):

    {
        "success": True,
        "deal":            <deal doc, _id stripped>,
        "customer":        <{ id, name, email, phone, company } | None>,
        "lead":            <{ id, name, status, source } | None>,
        "pipeline_stage":  "deposit_paid",
        "stage_legacy":    "...",
        "health":          { state, reason, i18n_key, pipeline_stage },
        "stage_progress":  { ...see stage_progress.compute_stage_progress... },
        "financials":      { revenue, cost, profit, margin_pct, deposit_eur, ... },
        "deposits":        [ ... ],
        "contracts":       [ ... ],
        "payments":        [ ... ],
        "shipments":       [ ... ],
        "documents":       [ ... ],
        "timeline":        [ ... last 30 events newest-first ... ],
        "manager":         <{ id, name, email, role, avatar } | None>,
        "counts":          { deposits, contracts, payments, shipments,
                             documents, timeline },
    }
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.wave6.pipeline import derive_pipeline_stage
from app.wave6.health import compute_health
from app.wave11.stage_progress import compute_stage_progress
from app.wave11.actions import allowed_transitions
from app.services.financial_health import compute_financial_health
from app.services.delivery_health import compute_delivery_health

logger = logging.getLogger("bibi.wave11.bundle")


# ─── Helpers ────────────────────────────────────────────────────────────────
async def _safe_list(coro, default=None) -> List[Dict[str, Any]]:
    """Run an async DB coroutine returning a list; swallow exceptions."""
    try:
        return await coro
    except Exception as e:
        logger.warning("[wave11] safe_list failed: %s", e)
        return default if default is not None else []


async def _safe_one(coro) -> Optional[Dict[str, Any]]:
    try:
        return await coro
    except Exception as e:
        logger.warning("[wave11] safe_one failed: %s", e)
        return None


async def _safe_count(db, coll: str, q: Dict[str, Any]) -> int:
    try:
        return await db[coll].count_documents(q)
    except Exception:
        return 0


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


# ─── Sub-builders ───────────────────────────────────────────────────────────
async def _load_deal(db, deal_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a deal by `id` first then by `_id`. Drops `_id` from the output."""
    deal = await _safe_one(db.deals.find_one({"id": deal_id}, {"_id": 0}))
    if deal:
        return deal
    # Legacy fallback — some pre-Wave-6 deals only had `_id`.
    legacy = await _safe_one(db.deals.find_one({"_id": deal_id}))
    if not legacy:
        return None
    legacy.pop("_id", None)
    if not legacy.get("id"):
        legacy["id"] = deal_id
    return legacy


async def _load_customer_light(db, deal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cid = deal.get("customer_id") or deal.get("customerId")
    if not cid:
        return None
    proj = {
        "_id": 0, "id": 1, "name": 1, "first_name": 1, "last_name": 1,
        "email": 1, "phone": 1, "company": 1, "vip": 1, "created_at": 1,
    }
    return await _safe_one(
        db.customers.find_one({"$or": [{"id": cid}, {"_id": cid}]}, proj)
    )


async def _load_lead_light(db, deal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """If the deal was converted from a lead, attach a light card for the lead."""
    lid = (
        deal.get("converted_from_lead_id")
        or deal.get("lead_id")
        or deal.get("leadId")
    )
    if not lid:
        return None
    proj = {
        "_id": 0, "id": 1, "name": 1, "first_name": 1, "last_name": 1,
        "status": 1, "source": 1, "phone": 1, "email": 1, "created_at": 1,
    }
    return await _safe_one(
        db.leads.find_one({"$or": [{"id": lid}, {"_id": lid}]}, proj)
    )


async def _load_manager(db, deal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mid = (
        deal.get("managerId")
        or deal.get("manager_id")
        or deal.get("assigned_to")
        or deal.get("assigneeId")
    )
    if not mid:
        return None
    raw = await _safe_one(
        db.staff.find_one(
            {"$or": [{"id": mid}, {"_id": mid}, {"email": mid}, {"managerId": mid}]},
            {"_id": 0, "password_hash": 0, "password": 0},
        )
    )
    if not raw:
        # Fallback to the legacy `users` collection
        raw = await _safe_one(
            db.users.find_one(
                {"$or": [{"id": mid}, {"_id": mid}, {"email": mid}]},
                {"_id": 0, "password_hash": 0, "password": 0},
            )
        )
    if not raw:
        return None
    return {
        "id":     raw.get("id") or raw.get("email"),
        "name":   raw.get("name") or raw.get("full_name") or raw.get("email"),
        "email":  raw.get("email"),
        "role":   raw.get("role"),
        "avatar": raw.get("avatar_url") or raw.get("avatar"),
    }


async def _load_deposits(db, deal_id: str) -> List[Dict[str, Any]]:
    """Pull legal_deposits + legacy `deposits` collections, newest-first."""
    a = await _safe_list(
        db.legal_deposits.find({"deal_id": deal_id}, {"_id": 0})
        .sort("created_at", -1).to_list(length=50)
    )
    b = await _safe_list(
        db.deposits.find({"deal_id": deal_id}, {"_id": 0})
        .sort("created_at", -1).to_list(length=50)
    )
    return [*a, *b]


async def _load_contracts(db, deal_id: str) -> List[Dict[str, Any]]:
    """Pull contracts2 (Wave-level legal_workflow) + legacy `contracts`."""
    a = await _safe_list(
        db.contracts2.find({"deal_id": deal_id}, {"_id": 0})
        .sort("created_at", -1).to_list(length=50)
    )
    b = await _safe_list(
        db.contracts.find(
            {"$or": [{"deal_id": deal_id}, {"dealId": deal_id}]}, {"_id": 0}
        ).sort("created_at", -1).to_list(length=50)
    )
    c = await _safe_list(
        db.legal_contracts.find({"deal_id": deal_id}, {"_id": 0})
        .sort("created_at", -1).to_list(length=50)
    )
    return [*a, *b, *c]


async def _load_payments(db, deal_id: str) -> List[Dict[str, Any]]:
    return await _safe_list(
        db.payments.find({"deal_id": deal_id}, {"_id": 0})
        .sort("created_at", -1).to_list(length=100)
    )


async def _load_shipments(db, deal_id: str) -> List[Dict[str, Any]]:
    return await _safe_list(
        db.shipments.find(
            {"$or": [{"dealId": deal_id}, {"deal_id": deal_id}]}, {"_id": 0}
        ).sort("created_at", -1).to_list(length=20)
    )


async def list_deal_documents(db, deal_id: str) -> List[Dict[str, Any]]:
    """Best-effort union of three potential sources for deal documents:
        1. `deal_documents` collection  (preferred new schema)
        2. `deal.documents` sub-array   (legacy attached array)
        3. contracts → uploaded_file fields (treated as documents too)
    """
    docs: List[Dict[str, Any]] = []

    coll_docs = await _safe_list(
        db.deal_documents.find({"deal_id": deal_id}, {"_id": 0})
        .sort("created_at", -1).to_list(length=200)
    )
    for d in coll_docs:
        docs.append({
            "id":         d.get("id") or d.get("doc_id"),
            "name":       d.get("name") or d.get("file_name") or d.get("title") or "Document",
            "url":        d.get("url") or d.get("file_url"),
            "kind":       d.get("kind") or d.get("type") or "other",
            "size":       d.get("size"),
            "uploaded_by": d.get("uploaded_by") or d.get("created_by"),
            "uploaded_at": d.get("uploaded_at") or d.get("created_at"),
            "source":     "deal_documents",
        })

    # Inline list on the deal doc itself.
    deal = await _safe_one(
        db.deals.find_one({"id": deal_id}, {"_id": 0, "documents": 1, "files": 1, "attachments": 1})
    )
    for key in ("documents", "files", "attachments"):
        for d in (deal or {}).get(key) or []:
            if not isinstance(d, dict):
                continue
            docs.append({
                "id":         d.get("id") or d.get("doc_id") or d.get("name"),
                "name":       d.get("name") or d.get("title") or "Document",
                "url":        d.get("url") or d.get("file_url"),
                "kind":       d.get("kind") or d.get("type") or key.rstrip("s"),
                "size":       d.get("size"),
                "uploaded_by": d.get("uploaded_by"),
                "uploaded_at": d.get("uploaded_at") or d.get("created_at"),
                "source":     f"deal.{key}",
            })

    # Signed contract uploads also count as documents.
    for contract_coll in ("contracts2", "legal_contracts"):
        try:
            cursor = db[contract_coll].find(
                {"deal_id": deal_id},
                {"_id": 0, "id": 1, "signed_file_url": 1, "uploaded_file_url": 1,
                 "title": 1, "uploaded_at": 1, "signed_at": 1}
            )
            async for c in cursor:
                url = c.get("signed_file_url") or c.get("uploaded_file_url")
                if not url:
                    continue
                docs.append({
                    "id":         f"contract:{c.get('id')}",
                    "name":       c.get("title") or "Signed contract",
                    "url":        url,
                    "kind":       "contract",
                    "size":       None,
                    "uploaded_by": None,
                    "uploaded_at": c.get("uploaded_at") or c.get("signed_at"),
                    "source":     contract_coll,
                })
        except Exception:
            continue

    return docs


async def _load_timeline(db, deal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    return await _safe_list(
        db.deal_timeline.find({"deal_id": deal_id}, {"_id": 0})
        .sort("at", -1).limit(limit).to_list(length=limit)
    )


def _financials_snapshot(
    deal: Dict[str, Any],
    deposits: List[Dict[str, Any]],
    payments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Pure aggregation — no DB calls. Mirrors the surface the UI needs."""
    revenue = _num(
        deal.get("total_price")
        or deal.get("totalValue")
        or deal.get("clientPrice")
        or deal.get("amount")
    )
    cost = _num(
        deal.get("internal_cost")
        or deal.get("internalCost")
        or deal.get("purchase_price")
        or deal.get("purchasePrice")
    )
    profit = _num(deal.get("profit"))
    if not profit and revenue and cost:
        profit = round(revenue - cost, 2)
    margin_pct = round((profit / revenue) * 100, 1) if revenue else 0.0

    deposit_eur = sum(
        _num(dep.get("amount"))
        for dep in deposits
        if (dep.get("status") or "").lower() in
        {"confirmed", "paid", "received", "in_processing"}
    )
    deposit_pending = sum(
        _num(dep.get("amount"))
        for dep in deposits
        if (dep.get("status") or "").lower() in {"pending", "draft", "requested"}
    )

    payments_received = sum(
        _num(p.get("amount"))
        for p in payments
        if (p.get("status") or "").lower() in {"confirmed", "paid", "received"}
    )
    payments_pending = sum(
        _num(p.get("amount"))
        for p in payments
        if (p.get("status") or "").lower() in {"pending", "scheduled"}
    )

    balance_due = max(0.0, revenue - payments_received - deposit_eur)

    return {
        "currency":         deal.get("currency") or "EUR",
        "revenue":          round(revenue, 2),
        "cost":             round(cost, 2),
        "profit":           round(profit, 2),
        "margin_pct":       margin_pct,
        "deposit_received": round(deposit_eur, 2),
        "deposit_pending":  round(deposit_pending, 2),
        "payments_received": round(payments_received, 2),
        "payments_pending":  round(payments_pending, 2),
        "balance_due":      round(balance_due, 2),
    }


# ─── Public entry point ────────────────────────────────────────────────────
async def build_deal360_bundle(db, deal_id: str) -> Optional[Dict[str, Any]]:
    """Build the full Deal360 payload. Returns None when the deal does not exist."""
    deal = await _load_deal(db, deal_id)
    if not deal:
        return None

    # All fan-out queries in parallel.
    (
        customer, lead, manager,
        deposits, contracts, payments, shipments,
        documents, timeline,
    ) = await asyncio.gather(
        _load_customer_light(db, deal),
        _load_lead_light(db, deal),
        _load_manager(db, deal),
        _load_deposits(db, deal_id),
        _load_contracts(db, deal_id),
        _load_payments(db, deal_id),
        _load_shipments(db, deal_id),
        list_deal_documents(db, deal_id),
        _load_timeline(db, deal_id, limit=30),
    )

    pipeline_stage = derive_pipeline_stage(deal)
    health         = compute_health(deal).to_dict()
    stage_progress = compute_stage_progress(deal)
    financials     = _financials_snapshot(deal, deposits, payments)
    financial_health = compute_financial_health(deal, deposits, payments)

    # Wave 13 — pick the most recent shipment (one deal can have multiple
    # historical shipment rows but the current one is what Deal360 cares about).
    primary_shipment = shipments[0] if shipments else None
    delivery_documents: List[Dict[str, Any]] = []
    if primary_shipment and primary_shipment.get("id"):
        delivery_documents = await _safe_list(
            db.delivery_documents.find(
                {"shipment_id": primary_shipment["id"]}, {"_id": 0}
            ).sort("uploaded_at", -1).to_list(length=100)
        )
    delivery_health = compute_delivery_health(
        primary_shipment, documents=delivery_documents, deal=deal,
    )

    # Merge user-added blockers (Wave 11.1) into the progress payload so the
    # header bar shows them alongside heuristic ones.
    user_blockers_raw = deal.get("deal_blockers") or []
    open_user_blockers = [b for b in user_blockers_raw if not b.get("resolved")]
    if open_user_blockers:
        heuristic = list(stage_progress.get("blockers") or [])
        manual    = [b.get("label") for b in open_user_blockers if b.get("label")]
        merged    = heuristic + [m for m in manual if m not in heuristic]
        stage_progress = {**stage_progress, "blockers": merged}

    available_transitions = allowed_transitions(deal)

    counts = {
        "deposits":  len(deposits),
        "contracts": len(contracts),
        "payments":  len(payments),
        "shipments": len(shipments),
        "documents": len(documents),
        "timeline":  len(timeline),
        "blockers":  len(open_user_blockers),
    }

    return {
        "success":               True,
        "deal":                  deal,
        "customer":              customer,
        "lead":                  lead,
        "manager":               manager,
        "pipeline_stage":        pipeline_stage,
        "stage_legacy":          deal.get("stage") or deal.get("status"),
        "health":                health,
        "stage_progress":        stage_progress,
        "available_transitions": available_transitions,
        "blockers":              user_blockers_raw,
        "financials":            financials,
        "financial_health":      financial_health,
        "delivery_health":       delivery_health,
        "delivery_documents":    delivery_documents,
        "deposits":              deposits,
        "contracts":             contracts,
        "payments":              payments,
        "shipments":             shipments,
        "documents":             documents,
        "timeline":              timeline,
        "counts":                counts,
    }
