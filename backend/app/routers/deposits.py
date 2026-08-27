"""
deposits.py — Customer 360 → Deposits tab REST surface
======================================================

UAT Enhancement #2 — "Depositi v kartci klienta".

Single-source: writes/reads against the existing ``db.legal_deposits``
collection so we DO NOT fork the data model. The auction-driven
lifecycle endpoints under ``/api/legal/deposits/*`` (max-bid /
forfeit / refund) keep operating on the SAME docs — this router only
adds a thin manager-facing CRUD plane sufficient for the customer
card spec:

    Поля: Дата, Дата платежу, Сума, Валюта, Статус, Менеджер,
          Контракт, Файли, Коментар, Created At, Updated At.

Endpoints
---------
* ``GET    /api/customers/{cid}/deposits``   list (require_user + RBAC)
* ``POST   /api/customers/{cid}/deposits``   create (manager/admin)
* ``PATCH  /api/deposits/{id}``              update (manager/admin)
* ``DELETE /api/deposits/{id}``              soft-cancel (manager/admin)

Backward-compat
---------------
* Reads BOTH ``customer_id`` (snake) and ``customerId`` (camel) on
  the doc to merge legacy + new rows.
* New docs are written with BOTH keys for safe reads everywhere.
* ``date`` is the deposit event date (defaults to created_at);
  ``paymentDate`` is when payment was/should be received.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_manager_or_admin, require_user
from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.deposits")

router = APIRouter(tags=["deposits"])

ALLOWED_STATUSES = {"pending", "paid", "cancelled", "refunded"}
ALLOWED_CURRENCIES = {"USD", "EUR", "BGN", "UAH", "GBP"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    return f"dep_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}"


def _can_user_see_customer(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    """Mirror of server.py::_can_user_see_customer (kept local to avoid circular import).

    * admin / master_admin / owner / team_lead → full visibility
    * manager → only their own customers (managerId == self)
    """
    role = (user.get("role") or "").lower()
    if role in ("admin", "master_admin", "owner", "team_lead"):
        return True
    uid = user.get("id") or user.get("managerId") or user.get("staff_id") or user.get("email")
    return bool(uid) and customer.get("managerId") == uid


async def _load_customer_or_403(customer_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")
    if not _can_user_see_customer(user, cust):
        raise HTTPException(403, "Forbidden")
    return cust


async def _load_deposit_or_403(deposit_id: str, user: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    """Look up a deposit in legal_deposits first, then legacy deposits.

    Returns (doc, collection_name) so callers know which collection to write back to.
    """
    db = get_db()
    coll = "legal_deposits"
    dep = await db.legal_deposits.find_one({"id": deposit_id}, {"_id": 0})
    if not dep:
        dep = await db.deposits.find_one({"id": deposit_id}, {"_id": 0})
        coll = "deposits"
    if not dep:
        raise HTTPException(404, "Deposit not found")
    cid = dep.get("customerId") or dep.get("customer_id")
    cust = await db.customers.find_one({"id": cid}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")
    if not _can_user_see_customer(user, cust):
        raise HTTPException(403, "Forbidden")
    return dep, coll


def _amount_from_legacy(dep: Dict[str, Any]) -> float:
    """Pick the most relevant amount across legacy/new schemas."""
    for key in ("amount", "paid_amount_eur", "required_amount_eur"):
        v = dep.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return 0.0


def _normalize_payload(data: Dict[str, Any], *, partial: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if "date" in data:
        out["date"] = data.get("date") or None
    if "paymentDate" in data:
        out["paymentDate"] = data.get("paymentDate") or None

    if "amount" in data:
        try:
            out["amount"] = float(data.get("amount") or 0)
        except (TypeError, ValueError):
            raise HTTPException(400, "amount must be numeric")

    if "currency" in data:
        cur = (data.get("currency") or "EUR").strip().upper()
        if cur not in ALLOWED_CURRENCIES:
            raise HTTPException(400, f"currency must be one of {sorted(ALLOWED_CURRENCIES)}")
        out["currency"] = cur

    if "status" in data:
        st = (data.get("status") or "").strip().lower()
        if st and st not in ALLOWED_STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(ALLOWED_STATUSES)}")
        out["status"] = st or "pending"

    if "managerId" in data:
        out["managerId"] = (str(data.get("managerId") or "").strip() or None)
    if "contractId" in data:
        out["contractId"] = (str(data.get("contractId") or "").strip() or None)
    if "dealId" in data:
        out["dealId"] = (str(data.get("dealId") or "").strip() or None)

    if "fileIds" in data:
        ids = data.get("fileIds") or []
        if not isinstance(ids, list):
            raise HTTPException(400, "fileIds must be a list")
        out["fileIds"] = [str(x).strip() for x in ids if x]

    if "comment" in data:
        out["comment"] = (str(data.get("comment") or "").strip() or None)

    return out


async def _enrich_deposit(dep: Dict[str, Any], db) -> Dict[str, Any]:
    """Attach managerName/customerName/customerPhone/contract/files/utm/leadSource for UI."""
    d = dict(dep)

    # Unify customer_id key
    cid = d.get("customerId") or d.get("customer_id")
    d["customerId"] = cid

    # Pick a sensible amount/currency for legacy docs
    d.setdefault("amount", _amount_from_legacy(d))
    d.setdefault("currency", d.get("currency") or "EUR")
    d.setdefault("status", d.get("status") or "pending")
    d.setdefault("comment", d.get("comment") or d.get("note"))

    # Date default: explicit date else created_at
    d.setdefault("date", d.get("date") or d.get("created_at"))
    d.setdefault("paymentDate", d.get("paymentDate") or d.get("paid_at") or None)

    # Customer (name/phone)
    cust = await db.customers.find_one(
        {"id": cid},
        {"_id": 0, "firstName": 1, "lastName": 1, "name": 1, "phone": 1, "email": 1, "managerId": 1, "leadId": 1},
    ) if cid else None
    if cust:
        full_name = " ".join(filter(None, [cust.get("firstName"), cust.get("lastName")])).strip()
        d["customerName"] = full_name or cust.get("name") or cust.get("email") or ""
        d["customerPhone"] = cust.get("phone") or ""

    # Manager (name)
    mid = d.get("managerId") or (cust or {}).get("managerId")
    if mid:
        mgr = await db.staff.find_one({"id": mid}, {"_id": 0, "name": 1, "email": 1, "firstName": 1, "lastName": 1})
        if mgr:
            full_name = " ".join(filter(None, [mgr.get("firstName"), mgr.get("lastName")])).strip()
            d["managerName"] = full_name or mgr.get("name") or mgr.get("email") or ""
        d["managerId"] = mid

    # Contract (number / title) — best effort across the two contract collections
    cid2 = d.get("contractId")
    if cid2:
        contract = (
            await db.contracts.find_one({"id": cid2}, {"_id": 0, "title": 1, "version": 1, "contract_number": 1})
            or await db.contracts_lifecycle.find_one({"id": cid2}, {"_id": 0, "title": 1, "version": 1, "contract_number": 1})
        )
        if contract:
            d["contractNumber"] = contract.get("contract_number") or contract.get("title") or cid2

    # Files
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

    # UTM + Lead Source (Doopr #7) — surface from doc itself OR resolve from
    # customer / customer's most recent lead. Customer takes priority.
    try:
        from app.services.utm_propagation import pick_utm, extract_utm

        # 1) Already stamped on the deposit doc?
        own_utm = pick_utm(d)
        # 2) Fall back to customer/lead lookup.
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
        # leadId pass-through for "open original lead" deep link
        if not d.get("leadId"):
            d["leadId"] = (cust or {}).get("leadId") or ""
    except Exception:
        # UTM enrichment is best-effort: never fail the response.
        d.setdefault("utm", {})
        d.setdefault("leadSource", "")

    return d


def _summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _amt(x):
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0
    paid = [i for i in items if (i.get("status") or "").lower() == "paid"]
    pending = [i for i in items if (i.get("status") or "").lower() in {"pending", ""}]
    return {
        "total": len(items),
        "paid": len(paid),
        "pending": len(pending),
        "cancelled": sum(1 for i in items if (i.get("status") or "").lower() == "cancelled"),
        "refunded": sum(1 for i in items if (i.get("status") or "").lower() == "refunded"),
        "totalAmount": round(sum(_amt(i.get("amount")) for i in items), 2),
        "paidAmount": round(sum(_amt(i.get("amount")) for i in paid), 2),
        "pendingAmount": round(sum(_amt(i.get("amount")) for i in pending), 2),
    }


# ─── Global list (Doopr #7) ─────────────────────────────────────────


@router.get("/api/deposits", dependencies=[Depends(require_manager_or_admin)])
async def list_all_deposits(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    managerId: Optional[str] = None,
    country: Optional[str] = None,
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    limit: int = 500,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Global Deposits list with RBAC + enrichment.

    Visibility (mirrors Sales / Customer360 rules):
      * admin / master_admin / owner / team_lead → see everything.
      * manager → only deposits owned by their customers.

    Filters: ``status``, ``customer_id``, ``manager_id``, ``country``
    (resolved through the customer doc).

    Each row is enriched with customerName/Phone, managerName,
    contractNumber, files[], utm{} and leadSource so the global page
    (/admin/deposits) and Customer360 share one shape.
    """
    db = get_db()
    q: Dict[str, Any] = {}

    if status:
        st = status.strip().lower()
        if st and st not in ALLOWED_STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(ALLOWED_STATUSES)}")
        q["status"] = st

    if customer_id:
        q["$or"] = [{"customerId": customer_id}, {"customer_id": customer_id}]

    role = (user.get("role") or "").lower()
    uid = user.get("id") or user.get("managerId") or user.get("staff_id") or user.get("email")
    if role == "manager":
        # Restrict to customers managed by this manager.
        customer_ids: List[str] = []
        async for c in db.customers.find({"managerId": uid}, {"_id": 0, "id": 1}):
            if c.get("id"):
                customer_ids.append(c["id"])
        if not customer_ids:
            return {"success": True, "items": [], "count": 0, "summary": _summary([])}
        q["$or"] = [
            {"customerId": {"$in": customer_ids}},
            {"customer_id": {"$in": customer_ids}},
            *( [{"managerId": uid}] ),
        ]
    elif manager_id or managerId:
        q["managerId"] = manager_id or managerId

    # Доопр #15 — date range filter (created_at)
    if dateFrom or dateTo:
        cr: Dict[str, Any] = {}
        if dateFrom: cr["$gte"] = dateFrom
        if dateTo:   cr["$lte"] = dateTo
        q["created_at"] = cr

    cursor1 = db.legal_deposits.find(q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    raw_new = await cursor1.to_list(length=int(limit))

    # Also read from legacy db.deposits (calculator-driven flow). Records
    # there use slightly different shape; _enrich_deposit normalises them.
    # We exclude soft-cancelled rows already present in legal_deposits by id.
    seen_ids = {r.get("id") for r in raw_new if r.get("id")}
    legacy_q = dict(q)
    cursor2 = db.deposits.find(legacy_q, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    raw_legacy_all = await cursor2.to_list(length=int(limit))
    raw_legacy = [r for r in raw_legacy_all if r.get("id") not in seen_ids]

    raw = raw_new + raw_legacy
    # Final sort by created_at desc (handle both str and datetime)
    def _sort_key(r):
        ca = r.get("created_at")
        if ca is None:
            return "1970-01-01T00:00:00"
        return ca.isoformat() if hasattr(ca, 'isoformat') else str(ca)
    raw.sort(key=_sort_key, reverse=True)
    raw = raw[: int(limit)]

    items = [await _enrich_deposit(d, db) for d in raw]

    # Optional country filter — applied post-enrichment (customer country).
    if country:
        c = country.strip().upper()
        items = [i for i in items if str(i.get("country") or "").upper() == c]

    return {"success": True, "items": items, "count": len(items), "summary": _summary(items)}


# ─── List / Create ──────────────────────────────────────────────────


@router.get("/api/customers/{customer_id}/deposits")
async def list_customer_deposits(
    customer_id: str,
    user: Dict[str, Any] = Depends(require_user),
):
    """Return all deposits for a customer, enriched for the UI.

    Includes legacy auction-driven deposits and new manager-created ones.
    """
    await _load_customer_or_403(customer_id, user)
    db = get_db()
    q = {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}]}

    cur_new = db.legal_deposits.find(q, {"_id": 0}).sort("created_at", -1)
    new_rows = await cur_new.to_list(length=500)
    seen = {r.get("id") for r in new_rows if r.get("id")}

    cur_legacy = db.deposits.find(q, {"_id": 0}).sort("created_at", -1)
    legacy_rows = [r for r in await cur_legacy.to_list(length=500) if r.get("id") not in seen]

    raw = new_rows + legacy_rows
    # Sort by created_at desc (handle both str and datetime)
    def _sort_key(r):
        ca = r.get("created_at")
        if ca is None:
            return "1970-01-01T00:00:00"
        return ca.isoformat() if hasattr(ca, 'isoformat') else str(ca)
    raw.sort(key=_sort_key, reverse=True)

    items = [await _enrich_deposit(d, db) for d in raw]
    return {"success": True, "items": items, "count": len(items), "summary": _summary(items)}


@router.post("/api/customers/{customer_id}/deposits", dependencies=[Depends(require_manager_or_admin)])
async def create_customer_deposit(
    customer_id: str,
    data: Dict[str, Any] = Body(default_factory=dict),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Create a manager-driven deposit row for a customer.

    Minimal fields: amount, currency, status. The rest are optional.
    """
    cust = await _load_customer_or_403(customer_id, user)
    payload = _normalize_payload(data, partial=False)

    if "amount" not in payload:
        raise HTTPException(400, "amount is required")

    now = _now_iso()
    doc: Dict[str, Any] = {
        "id": _gen_id(),
        # write BOTH key styles for back-compat
        "customerId": customer_id,
        "customer_id": customer_id,
        "date": payload.get("date") or now,
        "paymentDate": payload.get("paymentDate"),
        "amount": float(payload.get("amount") or 0),
        "currency": payload.get("currency") or "EUR",
        "status": payload.get("status") or "pending",
        "managerId": payload.get("managerId") or cust.get("managerId"),
        "contractId": payload.get("contractId"),
        "dealId": payload.get("dealId"),
        "fileIds": payload.get("fileIds") or [],
        "comment": payload.get("comment"),
        "source": "manual",
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("email") or user.get("id"),
        "updated_by": user.get("email") or user.get("id"),
        "history": [
            {"event": "created", "at": now,
             "by": user.get("email") or user.get("id"),
             "data": {"amount": payload.get("amount"), "currency": payload.get("currency")}},
        ],
    }

    db = get_db()

    # UTM stamping (Doopr #7) — best-effort, never blocks create.
    try:
        from app.services.utm_propagation import extract_utm, stamp_utm
        utm = await extract_utm(db, customer_id=customer_id, customer_doc=cust)
        stamp_utm(doc, utm)
    except Exception:
        logger.exception("[deposits] utm stamping failed (non-fatal)")

    await db.legal_deposits.insert_one(doc)
    doc.pop("_id", None)

    enriched = await _enrich_deposit(doc, db)
    return {"success": True, "deposit": enriched}


# ─── Update / Delete ────────────────────────────────────────────────


@router.patch("/api/deposits/{deposit_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_deposit(
    deposit_id: str,
    data: Dict[str, Any] = Body(default_factory=dict),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    existing, coll = await _load_deposit_or_403(deposit_id, user)
    upd = _normalize_payload(data, partial=True)
    if not upd:
        raise HTTPException(400, "Nothing to update")

    upd["updated_at"] = _now_iso()
    upd["updated_by"] = user.get("email") or user.get("id")

    # Auto-stamp paymentDate when transitioning to "paid" without explicit date
    if upd.get("status") == "paid" and not upd.get("paymentDate") and not existing.get("paymentDate"):
        upd["paymentDate"] = _now_iso()

    db = get_db()
    push_hist = {
        "$push": {"history": {
            "event": "updated", "at": _now_iso(),
            "by": user.get("email") or user.get("id"),
            "data": {k: v for k, v in upd.items() if k != "updated_at"},
        }}
    }
    await db[coll].update_one({"id": deposit_id}, {"$set": upd, **push_hist})

    fresh = await db[coll].find_one({"id": deposit_id}, {"_id": 0})
    enriched = await _enrich_deposit(fresh, db)
    return {"success": True, "deposit": enriched}


@router.delete("/api/deposits/{deposit_id}", dependencies=[Depends(require_manager_or_admin)])
async def delete_deposit(
    deposit_id: str,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Soft-cancel a deposit (status → cancelled). Historical records preserved."""
    _, coll = await _load_deposit_or_403(deposit_id, user)
    db = get_db()
    now = _now_iso()
    await db[coll].update_one(
        {"id": deposit_id},
        {
            "$set": {
                "status": "cancelled",
                "cancelledAt": now,
                "updated_at": now,
                "updated_by": user.get("email") or user.get("id"),
            },
            "$push": {"history": {"event": "cancelled", "at": now, "by": user.get("email") or user.get("id")}},
        },
    )
    return {"success": True}


__all__ = ["router"]
