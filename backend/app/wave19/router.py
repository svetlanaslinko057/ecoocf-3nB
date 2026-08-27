"""
BIBI Cars — Wave 19 — Customer Portal View HTTP surface
========================================================

Mounted at `/api/customer-portal/*` — staff-only (manager / team_lead /
admin / master_admin). The customer is identified ALWAYS via the `customer_id`
path segment. Returns trimmed read-only projections — the same data the
customer would see "if they were looking at their own portal".

Cross-cutting for the three admin cabinets — same shape, same payload, role
is checked by the canonical `require_user` dependency from `security.py`.
"""
from __future__ import annotations
import logging
import mimetypes
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .security import _db, resolve_customer, require_user
from .service import (count_unread_notifications, get_deal,
                      get_delivery_timeline, get_payments, list_deals,
                      list_documents, list_notifications,
                      mark_notification_read,
                      resolve_document_for_download)

logger = logging.getLogger("bibi.wave19.customer_portal")
router = APIRouter(prefix="/api/customer-portal", tags=["Wave19:CustomerPortalView"])


# ── customer summary ────────────────────────────────────────────────────────
@router.get("/customers")
async def cp_list_customers(
    request: Request,
    q: Optional[str] = Query(None, description="search by name / email / phone"),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Picker for the customer-portal view. Returns customers with deal count
    and last activity so the staff member can find who to look at quickly."""
    db = _db(request)
    query: Dict[str, Any] = {}
    if q:
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"name": rx}, {"email": rx}, {"phone": rx}]
    cursor = db.customers.find(query, {"_id": 0, "password": 0}).limit(limit)
    items = []
    async for c in cursor:
        cid = c.get("customerId") or c.get("id") or c.get("user_id")
        if not cid:
            continue
        deals_count = await db.deals.count_documents({"$or": [{"customerId": cid}, {"customer_id": cid}]})
        items.append({
            "customerId": cid,
            "name": c.get("name") or "",
            "email": c.get("email") or "",
            "phone": c.get("phone") or "",
            "picture": c.get("picture") or "",
            "dealsCount": deals_count,
            "createdAt": c.get("created_at") or "",
        })
    items.sort(key=lambda x: (-(x["dealsCount"] or 0), x["name"] or ""))
    return {"items": items, "total": len(items)}


@router.get("/{customer_id}")
async def cp_customer_summary(
    request: Request,
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    cust = await resolve_customer(db, customer_id)
    return {
        "customerId": cust["customerId"],
        "name": cust.get("name") or "",
        "email": cust.get("email") or "",
        "phone": cust.get("phone") or "",
        "picture": cust.get("picture") or "",
        "createdAt": cust.get("created_at") or "",
    }


# ── deals ───────────────────────────────────────────────────────────────────
@router.get("/{customer_id}/deals")
async def cp_deals_list(
    request: Request,
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    await resolve_customer(db, customer_id)
    items = await list_deals(db, customer_id)
    return {"items": items, "total": len(items)}


@router.get("/{customer_id}/deals/{deal_id}")
async def cp_deal_detail(
    request: Request,
    customer_id: str,
    deal_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    deal = await get_deal(db, customer_id, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found for this customer")
    return deal


# ── delivery timeline ───────────────────────────────────────────────────────
@router.get("/{customer_id}/deals/{deal_id}/delivery")
async def cp_deal_delivery(
    request: Request,
    customer_id: str,
    deal_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    tl = await get_delivery_timeline(db, customer_id, deal_id)
    if not tl:
        raise HTTPException(status_code=404, detail="Deal not found for this customer")
    return tl


# ── documents ───────────────────────────────────────────────────────────────
@router.get("/{customer_id}/deals/{deal_id}/documents")
async def cp_deal_documents(
    request: Request,
    customer_id: str,
    deal_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    docs = await list_documents(db, customer_id, deal_id)
    if docs is None:
        raise HTTPException(status_code=404, detail="Deal not found for this customer")
    items = []
    for d in docs["items"]:
        clean = {k: v for k, v in d.items() if not k.startswith("_")}
        # Override the customer-side proxy URL with the staff-side equivalent so the
        # link in the admin UI hits the staff surface (it is still tenant-checked).
        clean["downloadUrl"] = f"/api/customer-portal/{customer_id}/documents/{d['id']}/download"
        items.append(clean)
    return {"dealId": docs["dealId"], "items": items}


@router.get("/{customer_id}/documents/{doc_id}/download")
async def cp_document_download(
    request: Request,
    customer_id: str,
    doc_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    found = await resolve_document_for_download(db, customer_id, doc_id)
    if not found:
        raise HTTPException(status_code=404, detail="Document not found for this customer")
    doc, _coll = found
    path = doc.get("path") or doc.get("filepath") or doc.get("filePath")
    if path and os.path.exists(path):
        filename = doc.get("filename") or os.path.basename(path)
        media = doc.get("mime") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return FileResponse(path, filename=filename, media_type=media)
    url = doc.get("url") or doc.get("publicUrl") or doc.get("publicURL")
    if url:
        return {"redirect": url, "filename": doc.get("filename") or "document"}
    raise HTTPException(status_code=410, detail="Document file not available")


# ── payments ────────────────────────────────────────────────────────────────
@router.get("/{customer_id}/deals/{deal_id}/payments")
async def cp_deal_payments(
    request: Request,
    customer_id: str,
    deal_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    payments = await get_payments(db, customer_id, deal_id)
    if payments is None:
        raise HTTPException(status_code=404, detail="Deal not found for this customer")
    return payments


# ── notifications ───────────────────────────────────────────────────────────
@router.get("/{customer_id}/notifications")
async def cp_notifications_inbox(
    request: Request,
    customer_id: str,
    only_unread: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    await resolve_customer(db, customer_id)
    return await list_notifications(db, customer_id, only_unread=only_unread, limit=limit)


@router.get("/{customer_id}/notifications/unread-count")
async def cp_notifications_unread(
    request: Request,
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    await resolve_customer(db, customer_id)
    count = await count_unread_notifications(db, customer_id)
    return {"unread": count}


@router.post("/{customer_id}/notifications/{notification_id}/read")
async def cp_notification_mark_read(
    request: Request,
    customer_id: str,
    notification_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    ok = await mark_notification_read(db, customer_id, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found for this customer")
    return {"success": True}


# ── one-shot home aggregator ────────────────────────────────────────────────
@router.get("/{customer_id}/home")
async def cp_home(
    request: Request,
    customer_id: str,
    deal_id: Optional[str] = Query(None, description="Optional deal id; defaults to active or newest"),
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    cust = await resolve_customer(db, customer_id)
    deals = await list_deals(db, customer_id)

    active = None
    if deal_id:
        active = next((d for d in deals if d["id"] == deal_id), None)
    if active is None:
        active = next(
            (d for d in deals if d["status"] not in ("delivered", "completed", "cancelled")),
            (deals[0] if deals else None),
        )
    other = [d for d in deals if not active or d["id"] != active["id"]][:10]

    delivery = documents = payments = None
    deal_detail = None
    if active:
        deal_detail = await get_deal(db, customer_id, active["id"])
        delivery = await get_delivery_timeline(db, customer_id, active["id"])
        docs = await list_documents(db, customer_id, active["id"])
        if docs:
            docs_items = []
            for d in docs["items"]:
                clean = {k: v for k, v in d.items() if not k.startswith("_")}
                clean["downloadUrl"] = f"/api/customer-portal/{customer_id}/documents/{d['id']}/download"
                docs_items.append(clean)
            docs["items"] = docs_items
        documents = docs
        payments = await get_payments(db, customer_id, active["id"])

    notifications = await list_notifications(db, customer_id, limit=10)

    return {
        "customer": {
            "customerId": cust["customerId"],
            "email": cust.get("email", ""),
            "name": cust.get("name", ""),
            "phone": cust.get("phone", ""),
            "picture": cust.get("picture", ""),
        },
        "activeDeal": deal_detail,
        "delivery": delivery,
        "documents": documents,
        "payments": payments,
        "notifications": notifications,
        "otherDeals": other,
        "allDeals": deals,
    }
