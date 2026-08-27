"""
sales — /api/sales HTTP surface  (Phase Final / Block 2)
==========================================================

Sales entity for BIBI Cars — represents a SOLD vehicle and its
attached commercial / legal context. Independent of ``deals`` (catalog
items) and ``invoices`` (services billing).

Resource model
--------------
::

    db.sales
    {
      id:               "sale_<10hex>",
      customerId:       str,                # required
      managerId:        str,                # required (assignment)
      source:           "manual" | "deal" | "vin",
      # vehicle identity
      vin:              str | None,
      lot:              str | None,
      auction:          "copart" | "iaai" | "manheim" | "korea_auction" | "other" | None,
      country:          "USA" | "KOREA" | "OTHER",   # origin country
      brand:            str | None,
      model:            str | None,
      year:             int | None,
      # Commercial
      saleAmount:       float,              # in saleCurrency
      saleCurrency:     "USD" | "EUR" | "BGN" | "UAH" | "GBP",
      # Links
      dealId:           str | None,         # link to db.deals (when source=deal)
      contractId:       str | None,         # link to db.contracts (Phase 1)
      invoiceIds:       list[str],          # related invoices
      acceptanceActId:  str | None,         # link to generated act PDF
      # Status
      status:           "draft" | "active" | "sold" | "cancelled",
      soldAt:           ISO8601 | None,
      cancelledAt:      ISO8601 | None,
      cancelReason:     str | None,
      notes:            str | None,
      # Attribution
      utm:              {utm_source, utm_medium, utm_campaign, utm_content, utm_term, source},
      # Audit
      created_at:       ISO8601,
      created_by:       str (email),
      updated_at:       ISO8601,
      updated_by:       str (email),
    }

Auth model
----------
* Public list/get inside cabinet → mounted separately in
  ``/api/customer-cabinet/{cid}/sales``; that view is a thin wrapper
  on ``list_sales(customer_id=cid)`` and lives in server.py to keep
  the cabinet bouquet co-located.

* Manager / team_lead / admin → full CRUD here via
  ``require_manager_or_admin``.

Inputs are validated at the HTTP layer with pydantic-style dicts
(matching the rest of the codebase). The router owns NO domain
logic — it composes data and delegates writes to
``app.repositories.sales.SalesRepository``.

Customer cabinet visibility
---------------------------
Sales with ``status in {"active","sold"}`` are visible in
``/customer-cabinet/{cid}/sales`` (the customer-facing view).
``draft`` and ``cancelled`` are hidden.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_manager_or_admin, require_user
from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.sales")

router = APIRouter(prefix="/api/sales", tags=["sales"])

ALLOWED_STATUSES = {"draft", "active", "sold", "cancelled"}  # "sold" == completed/utilized
ALLOWED_SOURCES = {"manual", "deal", "vin"}
ALLOWED_CURRENCIES = {"UAH", "USD", "EUR", "BGN", "GBP"}
ALLOWED_HAZARD = {"I", "II", "III", "IV"}
ALLOWED_UNITS = {"kg", "t", "l", "pcs", "m3"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    return f"sale_{uuid.uuid4().hex[:10]}"


def _normalize(data: Dict[str, Any], *, partial: bool = False) -> Dict[str, Any]:
    """Whitelist + validate Sales fields. Drops unknown keys.

    Args:
        data: caller-supplied payload.
        partial: True for PATCH; permits missing required fields.
    """
    out: Dict[str, Any] = {}

    # Required (on create)
    if "customerId" in data:
        out["customerId"] = str(data["customerId"]).strip()
    if "managerId" in data:
        out["managerId"] = str(data["managerId"]).strip()

    # Waste identity (ECO.NOVA — utilization order)
    if "wasteType" in data:
        out["wasteType"] = (str(data.get("wasteType") or "").strip() or None)
    if "wasteCode" in data:
        out["wasteCode"] = (str(data.get("wasteCode") or "").strip() or None)
    if "batchNo" in data:
        out["batchNo"] = (str(data.get("batchNo") or "").strip() or None)
    if "hazardClass" in data:
        hz = (str(data.get("hazardClass") or "").strip().upper() or None)
        if hz and hz not in ALLOWED_HAZARD:
            raise HTTPException(400, f"hazardClass must be one of {sorted(ALLOWED_HAZARD)}")
        out["hazardClass"] = hz
    if "quantity" in data:
        q = data.get("quantity")
        try:
            out["quantity"] = float(q) if q is not None and str(q).strip() != "" else None
        except (ValueError, TypeError):
            raise HTTPException(400, "quantity must be numeric")
    if "unit" in data:
        u = (str(data.get("unit") or "").strip().lower() or None)
        if u and u not in ALLOWED_UNITS:
            raise HTTPException(400, f"unit must be one of {sorted(ALLOWED_UNITS)}")
        out["unit"] = u

    # Commercial
    if "saleAmount" in data:
        try:
            out["saleAmount"] = float(data.get("saleAmount") or 0)
        except (ValueError, TypeError):
            raise HTTPException(400, "saleAmount must be numeric")
    if "saleCurrency" in data:
        cur = (data.get("saleCurrency") or "USD").strip().upper()
        if cur not in ALLOWED_CURRENCIES:
            raise HTTPException(400, f"saleCurrency must be one of {sorted(ALLOWED_CURRENCIES)}")
        out["saleCurrency"] = cur

    # Links
    if "dealId" in data:
        out["dealId"] = (str(data.get("dealId") or "").strip() or None)
    if "contractId" in data:
        out["contractId"] = (str(data.get("contractId") or "").strip() or None)
    if "invoiceIds" in data:
        ids = data.get("invoiceIds") or []
        if not isinstance(ids, list):
            raise HTTPException(400, "invoiceIds must be a list")
        out["invoiceIds"] = [str(x).strip() for x in ids if x]
    if "acceptanceActId" in data:
        out["acceptanceActId"] = (str(data.get("acceptanceActId") or "").strip() or None)

    # Source
    if "source" in data:
        src = (data.get("source") or "manual").strip().lower()
        if src not in ALLOWED_SOURCES:
            raise HTTPException(400, f"source must be one of {sorted(ALLOWED_SOURCES)}")
        out["source"] = src

    # Status (driven by transitions, but allow direct write for admin)
    if "status" in data:
        st = (data.get("status") or "draft").strip().lower()
        if st not in ALLOWED_STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(ALLOWED_STATUSES)}")
        out["status"] = st

    if "notes" in data:
        out["notes"] = (str(data.get("notes") or "").strip() or None)

    # UAT Enhancement #2 — alias `comment` for spec parity ──────────────
    if "comment" in data:
        out["comment"] = (str(data.get("comment") or "").strip() or None)

    # Explicit sale event date (defaults to created_at if not provided)
    if "saleDate" in data:
        out["saleDate"] = data.get("saleDate") or None

    # Attached documents (file IDs from File Manager) ───────────────────
    if "fileIds" in data:
        ids = data.get("fileIds") or []
        if not isinstance(ids, list):
            raise HTTPException(400, "fileIds must be a list")
        out["fileIds"] = [str(x).strip() for x in ids if x]

    # Optional informational phone override (display-only)
    if "phone" in data:
        out["phone"] = (str(data.get("phone") or "").strip() or None)

    if "soldAt" in data:
        out["soldAt"] = data.get("soldAt")
    if "cancelledAt" in data:
        out["cancelledAt"] = data.get("cancelledAt")
    if "cancelReason" in data:
        out["cancelReason"] = (str(data.get("cancelReason") or "").strip() or None)

    return out


@router.get("", dependencies=[Depends(require_manager_or_admin)])
async def list_sales(
    customer_id: Optional[str] = Query(None, alias="customerId"),
    country: Optional[str] = None,
    status: Optional[str] = None,
    manager_id: Optional[str] = Query(None, alias="managerId"),
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """List Sales with optional filters.

    Visibility:
      * admin / master_admin / owner / team_lead → see everything
      * manager → only their own sales (managerId == self)
    """
    db = get_db()
    q: Dict[str, Any] = {}
    role = (current_user.get("role") or "").lower()
    if role == "manager":
        q["managerId"] = current_user.get("id")
    if customer_id:
        q["customerId"] = customer_id
    if country:
        q["country"] = country.strip().upper()
    if status:
        q["status"] = status.strip().lower()
    if manager_id and role != "manager":
        q["managerId"] = manager_id
    if dateFrom or dateTo:
        cr: Dict[str, Any] = {}
        if dateFrom: cr["$gte"] = dateFrom
        if dateTo:   cr["$lte"] = dateTo
        q["created_at"] = cr
    cursor = db.sales.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    raw = await cursor.to_list(length=int(limit))
    # Enhancement #3 — enrich each row with customerName/Phone, managerName,
    # contractNumber, files so listing pages (e.g. /admin/sales) can show
    # phone without N+1 lookups on the frontend.
    items = [await _enrich_sale(s, db) for s in raw]
    return {"success": True, "items": items, "count": len(items)}


@router.get("/{sale_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_sale(sale_id: str):
    db = get_db()
    doc = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Sale not found")
    return {"success": True, "sale": doc}


@router.post("", dependencies=[Depends(require_manager_or_admin)])
async def create_sale(
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Create a Sale (manual / from deal / from VIN — same endpoint).

    Required: ``customerId`` + at least one of ``vin``, ``lot``, ``dealId``.

    If ``dealId`` is set, the helper enriches vin/lot/auction/brand/model/year
    from the linked deal doc (best-effort; missing fields stay None).
    """
    db = get_db()
    payload = _normalize(data, partial=False)

    # Required
    if not payload.get("customerId"):
        raise HTTPException(400, "customerId is required")
    # At least one waste identity
    if not payload.get("wasteType") and not payload.get("wasteCode"):
        raise HTTPException(400, "At least one of wasteType or wasteCode is required")

    payload.setdefault("source", "manual")
    # Default manager to current user
    payload.setdefault("managerId", user.get("id"))

    # Build doc
    doc = {
        "id": _gen_id(),
        "status": payload.get("status") or "draft",
        "wasteType": payload.get("wasteType"),
        "wasteCode": payload.get("wasteCode"),
        "batchNo": payload.get("batchNo"),
        "hazardClass": payload.get("hazardClass"),
        "quantity": payload.get("quantity"),
        "unit": payload.get("unit"),
        "saleAmount": float(payload.get("saleAmount") or 0),
        "saleCurrency": payload.get("saleCurrency") or "UAH",
        "saleDate": payload.get("saleDate"),
        "customerId": payload["customerId"],
        "managerId": payload.get("managerId"),
        "dealId": payload.get("dealId"),
        "contractId": payload.get("contractId"),
        "invoiceIds": payload.get("invoiceIds") or [],
        "fileIds": payload.get("fileIds") or [],
        "phone": payload.get("phone"),
        "acceptanceActId": payload.get("acceptanceActId"),
        "source": payload["source"],
        "notes": payload.get("notes"),
        "comment": payload.get("comment") or payload.get("notes"),
        "soldAt": payload.get("soldAt"),
        "created_at": _now_iso(),
        "created_by": user.get("email") or user.get("id"),
        "updated_at": _now_iso(),
        "updated_by": user.get("email") or user.get("id"),
    }

    # UTM stamping (best-effort)
    try:
        from app.services.utm_propagation import extract_utm, stamp_utm
        utm = await extract_utm(db, customer_id=doc["customerId"])
        stamp_utm(doc, utm)
    except Exception:
        logger.exception("[sales] utm stamping failed (non-fatal)")

    await db.sales.insert_one(doc)
    doc.pop("_id", None)

    # Customer timeline event (best-effort)
    try:
        from app.services.customer_timeline import record_event
        await record_event(
            customer_id=doc["customerId"],
            kind="sale_created",
            title=f"Utilization order created — {doc.get('wasteType') or doc.get('wasteCode') or doc['id']}",
            body=f"Amount: {doc.get('saleAmount')} {doc.get('saleCurrency')}",
            ref={"sale_id": doc["id"], "wasteCode": doc.get("wasteCode")},
            actor={"id": user.get("id"), "email": user.get("email")},
            meta={"amount": doc.get("saleAmount"), "currency": doc.get("saleCurrency"), "hazardClass": doc.get("hazardClass")},
        )
    except Exception:
        logger.debug("[sales] timeline event write skipped", exc_info=True)

    return {"success": True, "sale": doc}


@router.patch("/{sale_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_sale(
    sale_id: str,
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = get_db()
    upd = _normalize(data, partial=True)
    if not upd:
        raise HTTPException(400, "Nothing to update")
    upd["updated_at"] = _now_iso()
    upd["updated_by"] = user.get("email") or user.get("id")

    # Status transition side effects
    if upd.get("status") == "sold" and not upd.get("soldAt"):
        upd["soldAt"] = _now_iso()
    if upd.get("status") == "cancelled" and not upd.get("cancelledAt"):
        upd["cancelledAt"] = _now_iso()

    res = await db.sales.update_one({"id": sale_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(404, "Sale not found")

    doc = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    return {"success": True, "sale": doc}


@router.delete("/{sale_id}", dependencies=[Depends(require_manager_or_admin)])
async def delete_sale(
    sale_id: str,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Soft-cancel a Sale (status=cancelled). Historical records preserved."""
    db = get_db()
    res = await db.sales.update_one(
        {"id": sale_id},
        {"$set": {
            "status": "cancelled",
            "cancelledAt": _now_iso(),
            "updated_at": _now_iso(),
            "updated_by": user.get("email") or user.get("id"),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Sale not found")
    return {"success": True}


# ── Customer-scoped helpers (mounted under /api/customers) ─────────
customers_router = APIRouter(prefix="/api/customers", tags=["sales"])


async def _enrich_sale(s: Dict[str, Any], db) -> Dict[str, Any]:
    """Attach customerName/Phone, managerName, contractNumber, files[], utm{}, leadSource for UI."""
    d = dict(s)
    cid = d.get("customerId")
    cust = await db.customers.find_one(
        {"id": cid},
        {"_id": 0, "firstName": 1, "lastName": 1, "name": 1, "phone": 1, "email": 1, "managerId": 1, "leadId": 1},
    ) if cid else None
    if cust:
        full_name = " ".join(filter(None, [cust.get("firstName"), cust.get("lastName")])).strip()
        d["customerName"] = full_name or cust.get("name") or cust.get("email") or ""
        d["customerPhone"] = d.get("phone") or cust.get("phone") or ""

    mid = d.get("managerId") or (cust or {}).get("managerId")
    if mid:
        mgr = await db.staff.find_one({"id": mid}, {"_id": 0, "name": 1, "email": 1, "firstName": 1, "lastName": 1})
        if mgr:
            mname = " ".join(filter(None, [mgr.get("firstName"), mgr.get("lastName")])).strip()
            d["managerName"] = mname or mgr.get("name") or mgr.get("email") or ""

    contract_id = d.get("contractId")
    if contract_id:
        contract = (
            await db.contracts.find_one({"id": contract_id}, {"_id": 0, "title": 1, "version": 1, "contract_number": 1})
            or await db.contracts_lifecycle.find_one({"id": contract_id}, {"_id": 0, "title": 1, "version": 1, "contract_number": 1})
        )
        if contract:
            d["contractNumber"] = contract.get("contract_number") or contract.get("title") or contract_id

    file_ids = d.get("fileIds") or []
    files_out: List[Dict[str, Any]] = []
    if file_ids:
        cursor = db.client_files.find(
            {"id": {"$in": file_ids}, "deleted": {"$ne": True}},
            {"_id": 0, "id": 1, "name": 1, "original_name": 1, "size_bytes": 1, "mime_type": 1},
        )
        async for f in cursor:
            files_out.append({
                "id": f.get("id"),
                "name": f.get("original_name") or f.get("name") or "file",
                "size_bytes": int(f.get("size_bytes") or 0),
                "mime_type": f.get("mime_type") or "application/octet-stream",
            })
    d["files"] = files_out

    # Convenience: spec uses "Date" — surface saleDate or created_at
    d.setdefault("saleDate", d.get("saleDate") or d.get("created_at"))
    # Convenience: spec uses "Comment" — surface comment or notes
    d.setdefault("comment", d.get("comment") or d.get("notes"))

    # UTM + Lead Source (Doopr #7) — already stamped on create via
    # stamp_utm(); also fall back to customer/lead resolution for older rows.
    try:
        from app.services.utm_propagation import pick_utm, extract_utm

        own_utm = pick_utm(d)
        if not own_utm.get("utm_source") and cid:
            resolved = await extract_utm(db, customer_id=cid, customer_doc=cust)
            for k in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"):
                if not own_utm.get(k):
                    own_utm[k] = resolved.get(k, "")
            if not own_utm.get("lead_source"):
                own_utm["lead_source"] = resolved.get("lead_source", "")
        d["utm"] = {k: own_utm.get(k, "") for k in (
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        )}
        d["leadSource"] = own_utm.get("lead_source", "") or d.get("source") or ""
        if not d.get("leadId"):
            d["leadId"] = (cust or {}).get("leadId") or ""
    except Exception:
        d.setdefault("utm", {})
        d.setdefault("leadSource", "")

    return d


@customers_router.get("/{customer_id}/sales", dependencies=[Depends(require_user)])
async def list_customer_sales(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Sales for a single customer — used by Customer360 tab.

    Returns enriched docs with customerName/Phone, managerName,
    contractNumber, and files[] resolved from File Manager.
    """
    db = get_db()
    cursor = db.sales.find({"customerId": customer_id}, {"_id": 0}).sort("created_at", -1)
    raw = await cursor.to_list(length=500)
    items = [await _enrich_sale(s, db) for s in raw]

    def _amt(x):
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0

    summary = {
        "total":     len(items),
        "draft":     sum(1 for i in items if (i.get("status") or "").lower() == "draft"),
        "active":    sum(1 for i in items if (i.get("status") or "").lower() == "active"),
        "sold":      sum(1 for i in items if (i.get("status") or "").lower() == "sold"),
        "cancelled": sum(1 for i in items if (i.get("status") or "").lower() == "cancelled"),
        "totalAmount":  round(sum(_amt(i.get("saleAmount")) for i in items), 2),
        "soldAmount":   round(sum(_amt(i.get("saleAmount")) for i in items if (i.get("status") or "").lower() == "sold"), 2),
    }
    return {"success": True, "items": items, "count": len(items), "summary": summary}


# ─────────────────── Доопр #23 — Handover Act ───────────────────────
@router.post("/{sale_id}/handover-act")
async def generate_handover_act(
    sale_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Generate an Acceptance / Handover Act PDF for a given sale.

    Pulls customer, vehicle, contract, manager, sale-amount data from the
    Sale record and renders the `acceptance_act` template. The PDF is
    stored in the customer's "Contracts" system folder (versioned) — so
    re-runs create v2/v3 without deleting v1.

    Body (optional):
      handover_date  — ISO date of actual handover (defaults to today)
      comments       — extra free-text comment to print on the act
    """
    db = get_db()
    sale = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(404, "Sale not found")

    # Resolve customer to feed PDF engine
    cust_id = sale.get("customerId")
    if not cust_id:
        raise HTTPException(400, "Sale has no customer attached")
    customer = await db.customers.find_one({"id": cust_id}, {"_id": 0}) or {}

    # Resolve related contract (latest), if any
    contract = await db.contracts.find_one(
        {"customerId": cust_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not contract:
        contract = await db.contracts_v2.find_one(
            {"customer_id": cust_id},
            {"_id": 0},
            sort=[("created_at", -1)],
        ) or {}

    from app.services.pdf_engine import generate as pdf_generate
    extra = {
        "vehicle": {
            "make":     sale.get("brand") or sale.get("make"),
            "model":    sale.get("model"),
            "year":     sale.get("year"),
            "vin":      sale.get("vin"),
            "country":  sale.get("country"),
        },
        "sale": {
            "id":         sale.get("id"),
            "amount":     sale.get("saleAmount"),
            "currency":   sale.get("currency", "EUR"),
            "soldAt":     sale.get("soldAt") or sale.get("created_at"),
            "managerId":  sale.get("managerId"),
        },
        "contract": {
            "id":     contract.get("id"),
            "number": contract.get("number") or contract.get("contractNumber"),
            "date":   contract.get("signed_at") or contract.get("sentAt") or contract.get("created_at"),
        },
        "handover_date": payload.get("handover_date") or datetime.now(timezone.utc).date().isoformat(),
        "comments":      (payload.get("comments") or "").strip(),
        "act_kind":      "acceptance_handover",
        # BG acceptance_act template (Приложение №2) expects a `handover`
        # object with date/place/documents/condition/keys/remarks fields.
        "handover": {
            "date":                  payload.get("handover_date") or datetime.now(timezone.utc).date().isoformat(),
            "time":                  payload.get("handover_time") or "",
            "place":                 payload.get("handover_place") or "гр. София",
            "documents":             payload.get("documents") or "Договор за покупка, талон, ключове, COC сертификат, митническа декларация",
            "condition":             payload.get("condition") or "Без видими повреди при предаване",
            "keys_and_accessories":  payload.get("keys_and_accessories") or "2 ключа, ръководство на потребителя",
            "remarks":               (payload.get("comments") or "").strip() or "—",
        },
    }
    result = await pdf_generate(
        doc_type="acceptance_act",
        customer_id=cust_id,
        language=(payload.get("language") or "bg"),
        order_id=None,
        extra_context=extra,
        generated_by=current_user.get("id"),
        generated_by_email=current_user.get("email"),
    )
    doc = result.get("document") or {}
    fil = result.get("file") or {}

    # Link the generated act to this Sale so the Sales card lists it.
    try:
        await db.sales.update_one(
            {"id": sale_id},
            {"$push": {"handoverActs": {
                "id":         doc.get("id"),
                "version":    doc.get("version"),
                "file_id":    doc.get("file_id"),
                "generated_at": doc.get("generated_at"),
                "by":         current_user.get("name") or current_user.get("email"),
            }}}
        )
    except Exception:
        pass

    return {"success": True, "data": {
        "id":           doc.get("id"),
        "version":      doc.get("version"),
        "file_id":      doc.get("file_id"),
        "folder_name":  doc.get("folder_name"),
        "generated_at": doc.get("generated_at"),
        "download_url": f"/api/file-manager/files/{doc.get('file_id')}/download" if doc.get("file_id") else None,
    }}


@router.get("/{sale_id}/handover-acts")
async def list_handover_acts(
    sale_id: str,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Returns ALL versions of the handover act generated for this sale."""
    db = get_db()
    sale = await db.sales.find_one({"id": sale_id}, {"_id": 0, "handoverActs": 1, "customerId": 1})
    if not sale:
        raise HTTPException(404, "Sale not found")
    # Also pull canonical "generated_documents" rows of type=acceptance_act for this customer/sale
    docs = await db.generated_documents.find(
        {"type": "acceptance_act", "customer_id": sale.get("customerId")},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=100)
    return {"success": True, "items": docs, "linked": sale.get("handoverActs") or []}


__all__ = ["router", "customers_router"]
