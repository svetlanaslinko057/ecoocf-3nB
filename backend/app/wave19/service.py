"""
Wave 19 — Portal service layer.

These functions are PROJECTION BUILDERS. They read from existing collections
(deals / shipments / contracts / invoices / deal_documents / notifications)
and return trimmed customer-facing dicts — never raw bundles.

Server-side tenant filtering is enforced here — every query receives the
caller's `customer_id` and never trusts a client-provided one.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.delivery_health import MILESTONE_ORDER, MILESTONE_LABEL, DOC_LABEL


# ── helpers ──────────────────────────────────────────────────────────
def _iso(x: Any) -> Optional[str]:
    if not x:
        return None
    if isinstance(x, datetime):
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x.isoformat()
    return str(x)


def _vehicle_label(deal: Dict[str, Any]) -> str:
    parts = []
    if deal.get("year"):
        parts.append(str(deal["year"]))
    for k in ("make", "brand", "manufacturer"):
        if deal.get(k):
            parts.append(str(deal[k]))
            break
    for k in ("model", "modelName"):
        if deal.get(k):
            parts.append(str(deal[k]))
            break
    if not parts:
        return deal.get("vehicle") or deal.get("carName") or "Vehicle"
    return " ".join(parts)


def _deal_photo(deal: Dict[str, Any]) -> Optional[str]:
    for k in ("photo", "image", "thumbnail", "coverImage"):
        if deal.get(k):
            return str(deal[k])
    photos = deal.get("photos") or deal.get("images") or []
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            return first.get("url") or first.get("src")
        return str(first)
    return None


STATUS_LABEL = {
    "new": "New",
    "won": "Auction won",
    "auction_won": "Auction won",
    "paid": "Paid",
    "payment_confirmed": "Payment confirmed",
    "picked_up": "Picked up",
    "port_arrived": "At port",
    "loaded": "Loaded",
    "in_transit": "In transit",
    "at_sea": "At sea",
    "customs": "At customs",
    "ready_for_delivery": "Ready for delivery",
    "delivered": "Delivered",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


def _deal_summary(deal: Dict[str, Any]) -> Dict[str, Any]:
    status = (deal.get("status") or deal.get("stage") or "new").lower()
    return {
        "id": deal.get("id") or deal.get("deal_id") or str(deal.get("_id") or ""),
        "vehicle": _vehicle_label(deal),
        "vin": deal.get("vin") or deal.get("VIN"),
        "status": status,
        "statusLabel": STATUS_LABEL.get(status, status.replace("_", " ").title()),
        "photo": _deal_photo(deal),
        "eta": _iso(deal.get("eta") or deal.get("deliveryEta") or deal.get("estimatedDelivery")),
        "createdAt": _iso(deal.get("created_at") or deal.get("createdAt")),
    }


def _deal_detail(deal: Dict[str, Any]) -> Dict[str, Any]:
    summary = _deal_summary(deal)
    photos_raw = deal.get("photos") or deal.get("images") or []
    photos: List[str] = []
    if isinstance(photos_raw, list):
        for p in photos_raw[:12]:
            if isinstance(p, str):
                photos.append(p)
            elif isinstance(p, dict):
                v = p.get("url") or p.get("src")
                if v:
                    photos.append(v)
    summary.update({
        "make": deal.get("make") or deal.get("brand"),
        "model": deal.get("model"),
        "year": deal.get("year"),
        "lot": deal.get("lot") or deal.get("lotNumber"),
        "auction": deal.get("auction") or deal.get("auctionName"),
        "photos": photos,
    })
    return summary


# ── deals ───────────────────────────────────────────────────────────
async def list_deals(db: AsyncIOMotorDatabase, customer_id: str) -> List[Dict[str, Any]]:
    """All deals belonging to the caller, newest first."""
    q = {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]}
    cursor = db.deals.find(q, {"_id": 0}).sort("created_at", -1).limit(50)
    items = await cursor.to_list(length=50)
    return [_deal_summary(d) for d in items]


async def get_deal(db: AsyncIOMotorDatabase, customer_id: str, deal_id: str) -> Optional[Dict[str, Any]]:
    q = {
        "$and": [
            {"$or": [{"id": deal_id}, {"deal_id": deal_id}]},
            {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
        ]
    }
    deal = await db.deals.find_one(q, {"_id": 0})
    if not deal:
        return None
    return _deal_detail(deal)


# ── delivery timeline ──────────────────────────────────────────────────
async def get_delivery_timeline(
    db: AsyncIOMotorDatabase, customer_id: str, deal_id: str
) -> Optional[Dict[str, Any]]:
    """Read-only Wave 13 timeline trimmed for the portal.

    Looks first at deal.milestones (Deal360), then falls back to the linked
    shipment.stages array. Always returns a complete MILESTONE_ORDER list
    so the UI can render even when no milestone is yet checked off.
    """
    deal = await db.deals.find_one(
        {
            "$and": [
                {"$or": [{"id": deal_id}, {"deal_id": deal_id}]},
                {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            ]
        },
        {"_id": 0},
    )
    if not deal:
        return None

    completed: Dict[str, str] = {}
    milestones_field = deal.get("milestones") or {}
    if isinstance(milestones_field, dict):
        for k, v in milestones_field.items():
            if v:
                completed[k] = _iso(v) or ""
    elif isinstance(milestones_field, list):
        for m in milestones_field:
            if isinstance(m, dict) and m.get("key") and m.get("occurredAt"):
                completed[m["key"]] = _iso(m["occurredAt"]) or ""

    # Fallback to shipment stages
    if not completed:
        shipment = await db.shipments.find_one(
            {"$or": [{"dealId": deal_id}, {"deal_id": deal_id}, {"customerId": customer_id}]},
            {"_id": 0},
        )
        if shipment:
            stages = shipment.get("stages") or []
            current_stage_id = shipment.get("currentStageId")
            done_seen = True
            for st in stages:
                if not isinstance(st, dict):
                    continue
                key = st.get("id") or st.get("key")
                if not key:
                    continue
                if key in MILESTONE_ORDER and (st.get("completedAt") or st.get("completed")):
                    completed[key] = _iso(st.get("completedAt") or st.get("updatedAt")) or ""
                if key == current_stage_id:
                    done_seen = False

    # Build the response
    current_index = -1
    for i, key in enumerate(MILESTONE_ORDER):
        if key in completed:
            current_index = i
    current_key = MILESTONE_ORDER[current_index] if current_index >= 0 else None

    milestones: List[Dict[str, Any]] = []
    for i, key in enumerate(MILESTONE_ORDER):
        if key in completed:
            state = "done"
        elif i == current_index + 1:
            state = "current"
        else:
            state = "upcoming"
        milestones.append({
            "key": key,
            "label": MILESTONE_LABEL.get(key, key.replace("_", " ").title()),
            "state": state,
            "occurredAt": completed.get(key),
        })

    total = len(MILESTONE_ORDER)
    done = sum(1 for m in milestones if m["state"] == "done")
    progress = int(round(done * 100.0 / total)) if total else 0

    return {
        "dealId": deal_id,
        "currentMilestone": current_key,
        "eta": _iso(deal.get("eta") or deal.get("deliveryEta") or deal.get("estimatedDelivery")),
        "progressPercent": progress,
        "milestones": milestones,
    }


# ── documents ──────────────────────────────────────────────────────────
DOCUMENT_COLLECTIONS = ("deal_documents", "delivery_documents", "documents")


def _doc_kind(doc: Dict[str, Any]) -> str:
    raw = (doc.get("kind") or doc.get("type") or doc.get("category") or "other").lower()
    if "contract" in raw:
        return "contract"
    if "invoice" in raw or "bill" in raw:
        return "invoice"
    if "transport" in raw or "cmr" in raw or "bol" in raw or "loading" in raw:
        return "transport"
    if "customs" in raw or "export" in raw or "import" in raw:
        return "customs"
    return raw or "other"


def _doc_label(doc: Dict[str, Any]) -> str:
    if doc.get("label"):
        return doc["label"]
    if doc.get("name"):
        return doc["name"]
    raw_kind = (doc.get("kind") or doc.get("type") or "").lower()
    return DOC_LABEL.get(raw_kind, _doc_kind(doc).title())


async def list_documents(
    db: AsyncIOMotorDatabase, customer_id: str, deal_id: str
) -> Optional[Dict[str, Any]]:
    """Return all visible documents for the given deal owned by this customer.

    Customer-uploads are not allowed in Wave 19 — we only READ existing docs.
    URLs are always rewritten to go through the portal proxy.
    """
    deal = await db.deals.find_one(
        {
            "$and": [
                {"$or": [{"id": deal_id}, {"deal_id": deal_id}]},
                {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            ]
        },
        {"_id": 0, "id": 1, "customerId": 1, "shipmentId": 1},
    )
    if not deal:
        return None

    items: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for coll in DOCUMENT_COLLECTIONS:
        try:
            cursor = db[coll].find(
                {
                    "$or": [
                        {"dealId": deal_id},
                        {"deal_id": deal_id},
                        {"customerId": customer_id},
                    ]
                },
                {"_id": 0},
            ).limit(50)
            async for d in cursor:
                # Filter again on the server — do NOT trust client filter
                belongs = False
                if d.get("dealId") == deal_id or d.get("deal_id") == deal_id:
                    belongs = True
                elif d.get("customerId") == customer_id and d.get("shipmentId") and d.get("shipmentId") == deal.get("shipmentId"):
                    belongs = True
                if not belongs:
                    continue
                doc_id = d.get("id") or d.get("_id") or d.get("documentId")
                if not doc_id or doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)
                items.append({
                    "id": doc_id,
                    "kind": _doc_kind(d),
                    "label": _doc_label(d),
                    "filename": d.get("filename") or d.get("name"),
                    "sizeBytes": d.get("sizeBytes") or d.get("size"),
                    "uploadedAt": _iso(d.get("uploadedAt") or d.get("created_at")),
                    "downloadUrl": f"/api/portal/documents/{doc_id}/download",
                    "_storage_collection": coll,
                })
        except Exception:
            continue

    return {"dealId": deal_id, "items": items}


async def resolve_document_for_download(
    db: AsyncIOMotorDatabase, customer_id: str, doc_id: str
) -> Optional[Tuple[Dict[str, Any], str]]:
    """Locate the document record and confirm it belongs to caller.

    Returns (doc, collection_name) or None if not found / not authorized.
    """
    for coll in DOCUMENT_COLLECTIONS:
        try:
            d = await db[coll].find_one(
                {"$or": [{"id": doc_id}, {"documentId": doc_id}]},
                {"_id": 0},
            )
            if not d:
                continue
            if d.get("customerId") and d.get("customerId") != customer_id:
                return None
            # Validate via deal ownership when possible
            if d.get("dealId") or d.get("deal_id"):
                deal_id = d.get("dealId") or d.get("deal_id")
                deal = await db.deals.find_one(
                    {
                        "$and": [
                            {"$or": [{"id": deal_id}, {"deal_id": deal_id}]},
                            {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
                        ]
                    },
                    {"_id": 0, "id": 1},
                )
                if not deal:
                    return None
            return (d, coll)
        except Exception:
            continue
    return None


# ── payments ───────────────────────────────────────────────────────────
async def get_payments(
    db: AsyncIOMotorDatabase, customer_id: str, deal_id: str
) -> Optional[Dict[str, Any]]:
    deal = await db.deals.find_one(
        {
            "$and": [
                {"$or": [{"id": deal_id}, {"deal_id": deal_id}]},
                {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            ]
        },
        {"_id": 0},
    )
    if not deal:
        return None

    invoices_cursor = db.invoices.find(
        {
            "$or": [
                {"dealId": deal_id},
                {"deal_id": deal_id},
                {"customerId": customer_id},
            ]
        },
        {"_id": 0},
    ).sort("issuedAt", -1).limit(50)

    invoices_raw = await invoices_cursor.to_list(length=50)
    history: List[Dict[str, Any]] = []
    total = 0.0
    paid = 0.0
    currency = "USD"
    next_due: Optional[str] = None

    for inv in invoices_raw:
        # Tenant re-check — belt + suspenders
        if inv.get("customerId") and inv.get("customerId") != customer_id:
            continue
        # If invoice has dealId set, it must match
        inv_deal = inv.get("dealId") or inv.get("deal_id")
        if inv_deal and inv_deal != deal_id:
            continue
        try:
            amount = float(inv.get("amount") or inv.get("total") or 0)
        except Exception:
            amount = 0.0
        status = (inv.get("status") or "open").lower()
        if inv.get("currency"):
            currency = str(inv["currency"]).upper()

        is_paid = status in ("paid", "settled", "closed")
        total += amount
        if is_paid:
            paid += amount
        else:
            due = _iso(inv.get("dueDate") or inv.get("due_at"))
            if due and (next_due is None or due < next_due):
                next_due = due

        history.append({
            "id": inv.get("id") or inv.get("invoiceId") or "",
            "number": inv.get("number") or inv.get("invoiceNumber"),
            "amount": amount,
            "currency": (inv.get("currency") or currency or "USD").upper(),
            "status": "paid" if is_paid else ("overdue" if status == "overdue" else "open"),
            "dueDate": _iso(inv.get("dueDate") or inv.get("due_at")),
            "paidAt": _iso(inv.get("paidAt") or inv.get("paid_at")),
            "issuedAt": _iso(inv.get("issuedAt") or inv.get("created_at")),
        })

    outstanding = max(total - paid, 0.0)
    return {
        "dealId": deal_id,
        "currency": currency,
        "totalAmount": round(total, 2),
        "paidAmount": round(paid, 2),
        "outstandingAmount": round(outstanding, 2),
        "nextDueDate": next_due,
        "history": history,
    }


# ── notifications (Wave 18 read-only view) ───────────────────────────────
async def list_notifications(
    db: AsyncIOMotorDatabase,
    customer_id: str,
    only_unread: bool = False,
    limit: int = 30,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {
        "$or": [
            {"recipientId": customer_id},
            {"recipient_id": customer_id},
            {"customerId": customer_id},
            {"userId": customer_id},
            {"user_id": customer_id},
        ]
    }
    if only_unread:
        q["read_at"] = None

    cursor = db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    rows = await cursor.to_list(length=limit)
    items: List[Dict[str, Any]] = []
    unread = 0
    for r in rows:
        read_at = _iso(r.get("read_at"))
        if not read_at:
            unread += 1
        items.append({
            "id": r.get("id") or r.get("notificationId") or "",
            "event": r.get("event") or r.get("type") or "",
            "title": r.get("title") or r.get("event") or "Notification",
            "body": r.get("body") or r.get("message") or "",
            "createdAt": _iso(r.get("created_at") or r.get("createdAt")),
            "readAt": read_at,
            "dealId": r.get("dealId") or r.get("deal_id") or (r.get("meta") or {}).get("dealId"),
        })
    return {"items": items, "total": len(items), "unread": unread}


async def count_unread_notifications(db: AsyncIOMotorDatabase, customer_id: str) -> int:
    q = {
        "read_at": None,
        "$or": [
            {"recipientId": customer_id},
            {"recipient_id": customer_id},
            {"customerId": customer_id},
            {"userId": customer_id},
            {"user_id": customer_id},
        ],
    }
    return await db.notifications.count_documents(q)


async def mark_notification_read(
    db: AsyncIOMotorDatabase, customer_id: str, notification_id: str
) -> bool:
    q = {
        "$and": [
            {"$or": [{"id": notification_id}, {"notificationId": notification_id}]},
            {
                "$or": [
                    {"recipientId": customer_id},
                    {"recipient_id": customer_id},
                    {"customerId": customer_id},
                    {"userId": customer_id},
                    {"user_id": customer_id},
                ]
            },
        ]
    }
    now = datetime.now(timezone.utc).isoformat()
    res = await db.notifications.update_one(q, {"$set": {"read_at": now}})
    return res.matched_count > 0
