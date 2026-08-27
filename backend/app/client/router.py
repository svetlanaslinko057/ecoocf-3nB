"""Client (B2B customer) self-serve area.

All routes under ``/api/client`` (Bearer customer-session protected) plus a
small public inquiry endpoint under ``/api/public``.

This is ADDITIVE — it reuses the existing customer auth primitives
(``db.customers`` + ``db.customer_sessions``, minted by the Google GIS verify
endpoint in server.py) and the Waste domain collections. It never touches the
staff/CRM surface.

A client is typically a COMPANY (e.g. a hospital) that orders waste-utilisation
services repeatedly, so the area is built for B2B: request/order history,
repeat orders, documents (contracts/acts/certificates), amounts & status
timelines. No deliveries / TTN / e-commerce checkout.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, UploadFile

from app.core.db_runtime import get_db
from app.waste import service as S
from app.waste.router import _build_request_doc, _validate_items  # reuse builders

logger = logging.getLogger("eco.client")

router = APIRouter(prefix="/api/client", tags=["client-area"])
pub_router = APIRouter(prefix="/api/public", tags=["public-inquiry"])

C_CUSTOMERS = "customers"
C_SESSIONS = "customer_sessions"
C_INQUIRIES = "public_inquiries"
C_STAFF = "staff"


async def _resolve_manager_card(db, customer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve the customer's responsible manager (via managerId or the
    company's assigned_manager_id) into a contact card the client can see."""
    manager_id = customer.get("managerId")
    if not manager_id and customer.get("company_id"):
        co = await db[S.C_COMPANIES].find_one(
            {"id": customer.get("company_id")}, {"_id": 0, "assigned_manager_id": 1}
        )
        if co:
            manager_id = co.get("assigned_manager_id")
    if not manager_id:
        return None
    s = await db[C_STAFF].find_one({"id": manager_id}, {"_id": 0})
    if not s:
        return None
    return {
        "id": s.get("id"),
        "name": s.get("name") or (s.get("email") or "").split("@")[0],
        "email": s.get("email", ""),
        "phone": s.get("phone", ""),
        "role": s.get("role", "manager"),
    }


async def _notify_new_request(db, doc: Dict[str, Any], customer: Dict[str, Any]) -> None:
    """Best-effort alert when a client submits a request: in-app feed for the
    assigned manager + admin, plus an email to the configured notify mailbox.
    Never blocks or fails the request."""
    try:
        now = datetime.now(timezone.utc)
        manager_id = doc.get("assigned_manager_id")
        company_name = customer.get("company_name") or (doc.get("contact") or {}).get("company_name") or "—"
        title = "Нова заявка від клієнта"
        body = f"{customer.get('name') or customer.get('email')} ({company_name}) створив(ла) заявку {doc.get('id')}."
        audiences = ["admin"]
        if manager_id:
            audiences.append(manager_id)
        await db["waste_notifications"].insert_one({
            "id": S.gen_id("ntf"),
            "type": "client_request",
            "title": title,
            "body": body,
            "request_id": doc.get("id"),
            "company_id": doc.get("company_id"),
            "audiences": audiences,
            "read_by": [],
            "created_at": now.isoformat(),
        })
    except Exception as exc:
        logger.warning(f"[client] notification insert failed: {exc}")
    # Email to the notify mailbox (dry-run safe — never raises)
    try:
        from notifications import EmailChannel  # type: ignore
        from server import get_settings_service  # type: ignore
        svc = get_settings_service()
        auth_cfg = await svc.get_auth()
        notify_to = ((auth_cfg.get("notifications") or {}).get("notifyEmail") or "").strip()
        if notify_to:
            company_name = customer.get("company_name") or "—"
            html = (
                f"<div style='font-family:system-ui,sans-serif;padding:20px'>"
                f"<h2 style='margin:0 0 10px'>Нова заявка від клієнта</h2>"
                f"<p>Клієнт: <b>{customer.get('name') or customer.get('email')}</b> ({company_name})</p>"
                f"<p>Заявка: <b>{doc.get('id')}</b></p></div>"
            )
            await EmailChannel(db).send(
                to=notify_to, subject="ECO · Нова заявка від клієнта",
                html=html, text=f"Нова заявка {doc.get('id')} від {customer.get('email')}",
                event="client_request", context={"request_id": doc.get("id")},
            )
    except Exception as exc:
        logger.warning(f"[client] notify email failed: {exc}")


# ════════════════════════════════════════════════════════════════════════════
#  Auth — resolve the customer Bearer session token
# ════════════════════════════════════════════════════════════════════════════
async def _resolve_customer(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolve a customer Bearer session token → customer doc (or None).

    Mirrors server._resolve_bearer (kept local to avoid importing the monolith
    and creating an import cycle).
    """
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    db = get_db()
    session = await db[C_SESSIONS].find_one(
        {"$or": [{"token": token}, {"session_token": token}]}, {"_id": 0}
    )
    if not session:
        return None
    expires_at = session.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None
        if expires_at and getattr(expires_at, "tzinfo", None) is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            return None
    customer_id = session.get("customerId") or session.get("user_id")
    if not customer_id:
        return None
    customer = await db[C_CUSTOMERS].find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"_id": 0},
    )
    if not customer:
        return None
    customer["hasPassword"] = bool(customer.get("password"))
    for secret in ("password", "totp_secret", "totp_pending_secret", "backup_codes"):
        customer.pop(secret, None)
    return customer


async def get_current_customer(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    customer = await _resolve_customer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Не авторизовано")
    return customer


def _public_customer(c: Dict[str, Any]) -> Dict[str, Any]:
    cid = c.get("customerId") or c.get("id") or c.get("user_id")
    return {
        "id": cid,
        "customerId": cid,
        "email": c.get("email", ""),
        "name": c.get("name", ""),
        "picture": c.get("picture", ""),
        "phone": c.get("phone", ""),
        "company_name": c.get("company_name", ""),
        "position": c.get("position", ""),
        "company_id": c.get("company_id"),
        "role": c.get("role", "customer"),
        "created_at": c.get("created_at"),
    }


# ════════════════════════════════════════════════════════════════════════════
#  Client scope helpers
# ════════════════════════════════════════════════════════════════════════════
def _scope_query(customer: Dict[str, Any]) -> Dict[str, Any]:
    """Mongo filter that selects rows belonging to this customer.

    Always by verified email (contact.email). When the customer is linked to a
    waste_company, also include the whole company's history (B2B).
    """
    email = (customer.get("email") or "").strip().lower()
    ors: List[Dict[str, Any]] = []
    if email:
        ors.append({"contact.email": email})
        ors.append({"contact.email": {"$regex": f"^{_escape(email)}$", "$options": "i"}})
    company_id = customer.get("company_id")
    if company_id:
        ors.append({"company_id": company_id})
    if not ors:
        # No identity → match nothing
        return {"id": "__none__"}
    return {"$or": ors}


def _escape(text: str) -> str:
    import re
    return re.escape(text)


async def _enrich_request(db, req: Dict[str, Any]) -> Dict[str, Any]:
    """Attach derived B2B fields: stage label, linked contract/act, amount."""
    rid = req.get("id")
    company_id = req.get("company_id")
    contract = None
    act = None
    if rid:
        contract = await db[S.C_CONTRACTS].find_one({"request_id": rid}, {"_id": 0})
        act = await db[S.C_ACTS].find_one({"request_id": rid}, {"_id": 0})
    amount = None
    currency = "UAH"
    payment_status = None
    if contract:
        amount = contract.get("amount")
        currency = contract.get("currency") or "UAH"
        payment_status = contract.get("payment_status") or contract.get("paid")
    total_weight = act.get("total_weight_kg") if act else None
    return {
        **S.serialize(req),
        "stage_label": S.STAGE_LABELS_UK.get(req.get("stage"), req.get("stage")),
        "amount": amount,
        "currency": currency,
        "payment_status": payment_status,
        "total_weight_kg": total_weight,
        "has_contract": bool(contract),
        "has_act": bool(act),
        "contract_number": contract.get("number") if contract else None,
        "act_number": act.get("number") if act else None,
    }


# ════════════════════════════════════════════════════════════════════════════
#  Profile
# ════════════════════════════════════════════════════════════════════════════
@router.get("/me")
async def client_me(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    manager = await _resolve_manager_card(db, customer)
    return {"success": True, "customer": _public_customer(customer), "manager": manager}


@router.put("/me")
async def client_update_me(
    data: Dict[str, Any] = Body(...),
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    db = get_db()
    allowed = {"name", "phone", "company_name", "position"}
    patch = {k: v for k, v in (data or {}).items() if k in allowed}
    if patch:
        patch["updated_at"] = S.now_iso()
        await db[C_CUSTOMERS].update_one(
            {"email": customer.get("email")}, {"$set": patch}
        )
    fresh = await db[C_CUSTOMERS].find_one({"email": customer.get("email")}, {"_id": 0}) or customer
    return {"success": True, "customer": _public_customer(fresh)}


# ════════════════════════════════════════════════════════════════════════════
#  Notifications / Messages (received from staff: admin / manager)
# ════════════════════════════════════════════════════════════════════════════
def _client_notif_view(n: Dict[str, Any]) -> Dict[str, Any]:
    created = n.get("created_at")
    if not isinstance(created, str):
        try:
            created = created.isoformat()
        except Exception:
            created = str(created) if created else None
    return {
        "id": n.get("id"),
        "title": n.get("title"),
        "body": n.get("body") or n.get("message"),
        "type": n.get("type") or "message",
        "priority": n.get("priority") or "normal",
        "from_name": n.get("from_name"),
        "from_role": n.get("from_role"),
        "read": bool(n.get("read")),
        "created_at": created,
    }


@router.get("/notifications")
async def client_notifications(
    limit: int = 50,
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    db = get_db()
    cid = customer.get("id")
    rows = await db.notifications.find(
        {"customerId": cid}
    ).sort("createdAt", -1).limit(int(limit)).to_list(length=int(limit))
    unread = await db.notifications.count_documents({"customerId": cid, "read": {"$ne": True}})
    return {"success": True, "items": [_client_notif_view(n) for n in rows], "unread": unread}


@router.get("/notifications/unread-count")
async def client_notifications_unread(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    unread = await db.notifications.count_documents({"customerId": customer.get("id"), "read": {"$ne": True}})
    return {"success": True, "unread": unread}


@router.post("/notifications/{notification_id}/read")
async def client_notification_read(
    notification_id: str,
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    db = get_db()
    await db.notifications.update_one(
        {"customerId": customer.get("id"), "id": notification_id}, {"$set": {"read": True}}
    )
    return {"success": True}


@router.post("/notifications/read-all")
async def client_notifications_read_all(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    await db.notifications.update_many(
        {"customerId": customer.get("id"), "read": {"$ne": True}}, {"$set": {"read": True}}
    )
    return {"success": True}



# ════════════════════════════════════════════════════════════════════════════
#  Summary / KPIs
# ════════════════════════════════════════════════════════════════════════════
@router.get("/summary")
async def client_summary(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    q = _scope_query(customer)
    reqs = await db[S.C_REQUESTS].find(q, {"_id": 0}).sort("created_at", -1).to_list(length=500)
    open_stages = {"new", "quote", "contract", "pickup", "utilization"}
    total = len(reqs)
    open_count = sum(1 for r in reqs if r.get("stage") in open_stages)
    done_count = sum(1 for r in reqs if r.get("stage") in {"act", "archived"})
    last_at = reqs[0].get("created_at") if reqs else None

    # company-scoped contracts / acts
    company_id = customer.get("company_id")
    req_ids = [r.get("id") for r in reqs if r.get("id")]
    doc_q: Dict[str, Any] = {"request_id": {"$in": req_ids}} if req_ids else {"id": "__none__"}
    if company_id:
        doc_q = {"$or": [doc_q, {"company_id": company_id}]}
    contracts = await db[S.C_CONTRACTS].find(doc_q, {"_id": 0}).to_list(length=500)
    acts = await db[S.C_ACTS].find(doc_q, {"_id": 0}).to_list(length=500)
    total_amount = sum((c.get("amount") or 0) for c in contracts)
    total_weight = sum((a.get("total_weight_kg") or 0) for a in acts)

    return {
        "success": True,
        "summary": {
            "total_requests": total,
            "open_requests": open_count,
            "completed_requests": done_count,
            "contracts": len(contracts),
            "acts": len(acts),
            "total_amount": total_amount,
            "currency": "UAH",
            "total_weight_kg": total_weight,
            "last_request_at": last_at,
        },
        "manager": await _resolve_manager_card(db, customer),
    }


# ════════════════════════════════════════════════════════════════════════════
#  Requests / Orders
# ════════════════════════════════════════════════════════════════════════════
@router.get("/requests")
async def client_requests(
    stage: Optional[str] = None,
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    db = get_db()
    q = _scope_query(customer)
    if stage:
        q = {"$and": [q, {"stage": stage}]}
    rows = await db[S.C_REQUESTS].find(q, {"_id": 0}).sort("created_at", -1).limit(300).to_list(length=300)
    items = [await _enrich_request(db, r) for r in rows]
    return {"success": True, "items": items, "count": len(items)}


@router.get("/requests/{request_id}")
async def client_request_detail(
    request_id: str,
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    db = get_db()
    req = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "Заявку не знайдено")
    # ownership: email match OR company match
    email = (customer.get("email") or "").strip().lower()
    owns = (req.get("contact") or {}).get("email", "").strip().lower() == email
    if not owns and customer.get("company_id") and req.get("company_id") == customer.get("company_id"):
        owns = True
    if not owns:
        raise HTTPException(403, "Немає доступу до цієї заявки")
    enriched = await _enrich_request(db, req)
    # linked documents
    contracts = await db[S.C_CONTRACTS].find({"request_id": request_id}, {"_id": 0}).to_list(length=50)
    pickups = await db[S.C_PICKUPS].find({"request_id": request_id}, {"_id": 0}).to_list(length=50)
    acts = await db[S.C_ACTS].find({"request_id": request_id}, {"_id": 0}).to_list(length=50)
    return {
        "success": True,
        "request": enriched,
        "timeline": req.get("stage_history") or [],
        "documents": {
            "contracts": [S.serialize(c) for c in contracts],
            "pickups": [S.serialize(p) for p in pickups],
            "acts": [S.serialize(a) for a in acts],
        },
    }


@router.post("/requests")
async def client_create_request(
    data: Dict[str, Any] = Body(...),
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    """Authenticated self-serve request. Contact is injected from the profile;
    only licensed (accepted) codes are allowed — same guardrail as public."""
    db = get_db()
    items = _validate_items(data.get("items"))
    not_accepted: List[str] = []
    for it in items:
        chk = await S.license_check(db, it["waste_code"])
        if not chk.get("accepted"):
            not_accepted.append(it["waste_code"])
    if not_accepted:
        raise HTTPException(422, f"Ці коди поза нашою ліцензією (не приймаємо): {', '.join(not_accepted)}")
    payload = {
        "items": data.get("items"),
        "comment": data.get("comment"),
        "company_id": customer.get("company_id") or data.get("company_id"),
        "contact_name": customer.get("name"),
        "contact_phone": customer.get("phone") or data.get("contact_phone"),
        "contact_email": customer.get("email"),
        "company_name": customer.get("company_name") or data.get("company_name"),
    }
    doc = await _build_request_doc(db, payload, source="client", created_by=customer.get("email"))
    await db[S.C_REQUESTS].insert_one(doc)
    await S.log_activity(
        db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
        entity_type="request", entity_id=doc["id"], event="created",
        message="Заявка створена клієнтом з кабінету", by=customer.get("email"),
    )
    await _notify_new_request(db, doc, customer)
    return {"success": True, "request_id": doc["id"], "stage": doc["stage"]}


@router.post("/requests/{request_id}/reorder")
async def client_reorder(
    request_id: str,
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    """Repeat a previous order — clone its items into a fresh 'new' request."""
    db = get_db()
    src = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    if not src:
        raise HTTPException(404, "Заявку не знайдено")
    email = (customer.get("email") or "").strip().lower()
    owns = (src.get("contact") or {}).get("email", "").strip().lower() == email
    if not owns and customer.get("company_id") and src.get("company_id") == customer.get("company_id"):
        owns = True
    if not owns:
        raise HTTPException(403, "Немає доступу до цієї заявки")
    items = [{"waste_code": it.get("waste_code"), "qty": it.get("qty"),
              "unit": it.get("unit"), "name": it.get("name")} for it in (src.get("items") or [])]
    if not items:
        raise HTTPException(422, "У заявці немає позицій для повтору")
    payload = {
        "items": items,
        "comment": f"Повторне замовлення на основі {request_id}",
        "company_id": customer.get("company_id") or src.get("company_id"),
        "contact_name": customer.get("name"),
        "contact_phone": customer.get("phone"),
        "contact_email": customer.get("email"),
        "company_name": customer.get("company_name"),
    }
    doc = await _build_request_doc(db, payload, source="client", created_by=customer.get("email"))
    await db[S.C_REQUESTS].insert_one(doc)
    await S.log_activity(
        db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
        entity_type="request", entity_id=doc["id"], event="created",
        message=f"Повторне замовлення (на основі {request_id})", by=customer.get("email"),
    )
    await _notify_new_request(db, doc, customer)
    return {"success": True, "request_id": doc["id"], "stage": doc["stage"]}


# ════════════════════════════════════════════════════════════════════════════
#  Documents (read-only)
# ════════════════════════════════════════════════════════════════════════════
@router.get("/documents")
async def client_documents(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    q = _scope_query(customer)
    reqs = await db[S.C_REQUESTS].find(q, {"_id": 0, "id": 1}).to_list(length=500)
    req_ids = [r.get("id") for r in reqs if r.get("id")]
    company_id = customer.get("company_id")
    doc_q: Dict[str, Any] = {"request_id": {"$in": req_ids}} if req_ids else {"id": "__none__"}
    if company_id:
        doc_q = {"$or": [{"request_id": {"$in": req_ids}}, {"company_id": company_id}]}
    contracts = await db[S.C_CONTRACTS].find(doc_q, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    acts = await db[S.C_ACTS].find(doc_q, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    return {
        "success": True,
        "contracts": [S.serialize(c) for c in contracts],
        "acts": [S.serialize(a) for a in acts],
    }


# ════════════════════════════════════════════════════════════════════════════
#  DEV-ONLY login bypass (env-gated) — for automated/local testing without the
#  real Google popup. MUST be disabled in production (ALLOW_DEV_LOGIN unset).
# ════════════════════════════════════════════════════════════════════════════
@router.post("/dev-login")
async def client_dev_login(data: Dict[str, Any] = Body(...)):
    if (os.environ.get("ALLOW_DEV_LOGIN") or "").strip().lower() != "true":
        raise HTTPException(404, "Not found")
    import uuid
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "email is required")
    db = get_db()
    now = datetime.now(timezone.utc)
    existing = await db[C_CUSTOMERS].find_one({"email": email}, {"_id": 0})
    if existing:
        customer_id = existing.get("customerId") or existing.get("id") or f"cust_{uuid.uuid4().hex[:12]}"
        await db[C_CUSTOMERS].update_one({"email": email}, {"$set": {
            "id": customer_id, "customerId": customer_id, "user_id": customer_id,
            "last_login_at": now.isoformat(),
            "name": data.get("name") or existing.get("name") or email.split("@")[0],
            "company_name": data.get("company_name", existing.get("company_name", "")),
            "phone": data.get("phone", existing.get("phone", "")),
        }})
        customer = await db[C_CUSTOMERS].find_one({"email": email}, {"_id": 0})
    else:
        customer_id = f"cust_{uuid.uuid4().hex[:12]}"
        customer = {
            "id": customer_id, "customerId": customer_id, "user_id": customer_id,
            "email": email, "name": data.get("name") or email.split("@")[0],
            "company_name": data.get("company_name", ""), "phone": data.get("phone", ""),
            "role": "customer", "status": "active", "source": "dev",
            "created_at": now.isoformat(), "last_login_at": now.isoformat(),
        }
        await db[C_CUSTOMERS].insert_one(customer)
    from datetime import timedelta
    token = uuid.uuid4().hex + uuid.uuid4().hex
    await db[C_SESSIONS].insert_one({
        "token": token, "session_token": token, "customerId": customer_id,
        "user_id": customer_id, "provider": "dev",
        "created_at": now, "expires_at": now + timedelta(days=7),
    })
    return {"success": True, "sessionToken": token, "token": token,
            "customer": _public_customer(customer)}


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC inquiry / callback (site-wide CTA)
# ════════════════════════════════════════════════════════════════════════════
@pub_router.post("/inquiry")
async def public_inquiry(data: Dict[str, Any] = Body(...)):
    from app.contact_validation import normalize_phone, validate_email_addr

    name = (data.get("name") or "").strip()
    phone_raw = (data.get("phone") or "").strip()
    if not name:
        raise HTTPException(400, "Вкажіть ім'я")
    ok_phone, phone_e164, perr = normalize_phone(phone_raw)
    if not ok_phone:
        raise HTTPException(400, perr)
    ok_email, email_norm, eerr = validate_email_addr(data.get("email"), required=False)
    if not ok_email:
        raise HTTPException(400, eerr)
    db = get_db()
    doc = {
        "id": S.gen_id("inq"),
        "name": name,
        "phone": phone_e164,
        "phone_raw": phone_raw,
        "email": email_norm,
        "company_name": (data.get("company_name") or "").strip(),
        "company_edrpou": (data.get("company_edrpou") or "").strip(),
        "message": (data.get("message") or "").strip()[:2000],
        "type": data.get("type") if data.get("type") in {"callback", "inquiry", "request"} else "inquiry",
        "waste_code": (data.get("waste_code") or "").strip(),
        "status": "new",
        "source": "public_site",
        "created_at": S.now_iso(),
    }
    await db[C_INQUIRIES].insert_one(doc)
    await _notify_new_inquiry(db, doc)
    try:
        await S.log_activity(
            db, company_id=None, object_id=None,
            entity_type="inquiry", entity_id=doc["id"], event="created",
            message=f"Звернення з сайту: {name} ({phone_e164})", by="public",
        )
    except Exception:
        pass
    return {"success": True, "id": doc["id"]}


async def _notify_new_inquiry(db, doc: Dict[str, Any]) -> None:
    """Broadcast a new public inquiry/callback to the SHARED staff queue:
    every manager + admin sees it (audience token ``staff``). Never blocks."""
    type_labels = {"callback": "Замовлення дзвінка", "inquiry": "Нове звернення", "request": "Заявка з сайту"}
    title = type_labels.get(doc.get("type"), "Нове звернення")
    company = doc.get("company_name") or "—"
    body = f"{doc.get('name')} · {doc.get('phone')} · {company}"
    try:
        await db["waste_notifications"].insert_one({
            "id": S.gen_id("ntf"),
            "type": "inquiry",
            "title": title,
            "body": body,
            "inquiry_id": doc.get("id"),
            "link": "/app/inquiries",
            "audiences": ["staff"],   # shared: all managers + admin
            "read_by": [],
            "created_at": S.now_iso(),
        })
    except Exception as exc:
        logger.warning(f"[public] inquiry notification insert failed: {exc}")
    # Best-effort email to the configured notify mailbox (dry-run safe).
    try:
        from notifications import EmailChannel  # type: ignore
        from server import get_settings_service  # type: ignore
        svc = get_settings_service()
        auth_cfg = await svc.get_auth()
        notify_to = ((auth_cfg.get("notifications") or {}).get("notifyEmail") or "").strip()
        if notify_to:
            html = (
                f"<div style='font-family:system-ui,sans-serif;padding:20px'>"
                f"<h2 style='margin:0 0 10px'>{title}</h2>"
                f"<p>Імʼя: <b>{doc.get('name')}</b></p>"
                f"<p>Телефон: <b>{doc.get('phone')}</b></p>"
                f"<p>Компанія: {company}</p>"
                f"<p>Повідомлення: {doc.get('message') or '—'}</p></div>"
            )
            await EmailChannel(db).send(
                to=notify_to, subject=f"ECO · {title}",
                html=html, text=f"{title}: {doc.get('name')} {doc.get('phone')}",
                event="public_inquiry", context={"inquiry_id": doc.get("id")},
            )
    except Exception as exc:
        logger.warning(f"[public] inquiry notify email failed: {exc}")


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC company autocomplete (registry) + editable site contacts
# ════════════════════════════════════════════════════════════════════════════
C_COMPANY_REGISTRY = "company_registry"
C_SITE_CONTACTS = "site_settings"


async def _ensure_company_registry(db) -> None:
    """Idempotently seed the starter company registry (runs once)."""
    try:
        if await db[C_COMPANY_REGISTRY].count_documents({}) > 0:
            return
        from app.site_directory import company_seed_docs
        docs = company_seed_docs(S.gen_id, S.now_iso)
        if docs:
            await db[C_COMPANY_REGISTRY].insert_many(docs)
            await db[C_COMPANY_REGISTRY].create_index("name_lower")
            logger.info(f"[public] seeded company_registry: {len(docs)} rows")
    except Exception as exc:
        logger.warning(f"[public] company registry seed failed: {exc}")


@pub_router.get("/company-suggest")
async def company_suggest(q: str = "", limit: int = 8):
    """Autocomplete for company / establishment names.

    Merges the operator's own ``waste_companies`` (full data) with the seeded
    ``company_registry`` (public UA company names). Substring, case-insensitive.
    """
    term = (q or "").strip()
    if len(term) < 2:
        return {"success": True, "items": []}
    db = get_db()
    await _ensure_company_registry(db)
    limit = max(1, min(int(limit or 8), 20))
    rx = {"$regex": _re_escape(term), "$options": "i"}
    out: List[Dict[str, Any]] = []
    seen = set()

    # 1) operator's own companies first (they may already be clients)
    try:
        own = await db[S.C_COMPANIES].find(
            {"name": rx}, {"_id": 0, "name": 1, "edrpou": 1, "region": 1}
        ).limit(limit).to_list(length=limit)
        for c in own:
            key = (c.get("name") or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append({"name": c.get("name"), "edrpou": c.get("edrpou") or "",
                            "region": c.get("region") or "", "known_client": True})
    except Exception:
        pass

    # 2) public registry
    try:
        reg = await db[C_COMPANY_REGISTRY].find(
            {"name_lower": {"$regex": _re_escape(term.lower())}},
            {"_id": 0, "name": 1, "edrpou": 1, "region": 1},
        ).limit(limit * 2).to_list(length=limit * 2)
        for c in reg:
            key = (c.get("name") or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append({"name": c.get("name"), "edrpou": c.get("edrpou") or "",
                            "region": c.get("region") or "", "known_client": False})
            if len(out) >= limit:
                break
    except Exception:
        pass

    return {"success": True, "items": out[:limit]}


def _re_escape(s: str) -> str:
    import re
    return re.escape(s)


# ════════════════════════════════════════════════════════════════════════════
#  Invoices — IBAN bank-transfer flow (client side)
# ════════════════════════════════════════════════════════════════════════════
C_INVOICES = "invoices"
_CLIENT_VISIBLE_STATUSES = {"sent", "pending", "overdue", "awaiting_confirmation", "paid", "cancelled"}


def _invoice_scope(customer: Dict[str, Any]) -> Dict[str, Any]:
    """Invoices belonging to this client: by customerId, e-mail or company."""
    ors: List[Dict[str, Any]] = []
    cid = customer.get("id")
    if cid:
        ors.append({"customerId": cid})
    email = (customer.get("email") or "").strip().lower()
    if email:
        ors.append({"customerEmail": {"$regex": f"^{_escape(email)}$", "$options": "i"}})
    company_id = customer.get("company_id")
    if company_id:
        ors.append({"company_id": company_id})
    return {"$or": ors} if ors else {"id": "__none__"}


def _invoice_view(inv: Dict[str, Any]) -> Dict[str, Any]:
    inv = dict(inv or {})
    inv.pop("_id", None)
    for k in ("createdAt", "created_at", "issuedAt", "sentAt", "paidAt", "dueDate", "updated_at"):
        v = inv.get(k)
        if v is not None and not isinstance(v, str):
            try:
                inv[k] = v.isoformat()
            except Exception:
                inv[k] = str(v)
    return inv


@router.get("/invoices")
async def client_invoices(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    q = {"$and": [_invoice_scope(customer), {"status": {"$in": list(_CLIENT_VISIBLE_STATUSES)}}]}
    rows = await db[C_INVOICES].find(q, {"_id": 0}).sort("createdAt", -1).limit(300).to_list(length=300)
    items = [_invoice_view(r) for r in rows]
    summary = {
        "total": len(items),
        "awaiting": sum(1 for i in items if i.get("status") == "awaiting_confirmation"),
        "to_pay": sum(1 for i in items if i.get("status") in ("sent", "pending", "overdue")),
        "paid": sum(1 for i in items if i.get("status") == "paid"),
        "outstanding_amount": sum((i.get("amount") or i.get("total") or 0)
                                  for i in items if i.get("status") in ("sent", "pending", "overdue", "awaiting_confirmation")),
        "currency": "UAH",
    }
    return {"success": True, "items": items, "summary": summary}


@router.get("/invoices/{invoice_id}")
async def client_invoice_detail(invoice_id: str, customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    inv = await db[C_INVOICES].find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    # ownership
    scope = _invoice_scope(customer)
    owns = await db[C_INVOICES].find_one({"$and": [{"id": invoice_id}, scope]}, {"_id": 1})
    if not owns:
        raise HTTPException(403, "Немає доступу до цього рахунку")
    if inv.get("status") not in _CLIENT_VISIBLE_STATUSES:
        raise HTTPException(404, "Рахунок ще не виставлено")
    return {"success": True, "invoice": _invoice_view(inv)}


@router.post("/invoices/{invoice_id}/upload-proof")
async def client_invoice_upload_proof(
    invoice_id: str,
    file: UploadFile = File(...),
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    db = get_db()
    scope = _invoice_scope(customer)
    owns = await db[C_INVOICES].find_one({"$and": [{"id": invoice_id}, scope]}, {"_id": 1})
    if not owns:
        raise HTTPException(403, "Немає доступу до цього рахунку")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Файл завеликий (макс. 10 МБ)")
    fname_lower = (file.filename or "").lower()
    allowed_ext = (".pdf", ".png", ".jpg", ".jpeg", ".webp")
    if not fname_lower.endswith(allowed_ext):
        raise HTTPException(400, "Дозволено: PDF, JPG, PNG, WEBP")
    ext = fname_lower.rsplit(".", 1)[-1]

    # Deployment-safe: store the proof in the MongoDB-backed media store.
    from app.services.media_store import save_media
    out_name = f"proof_{invoice_id}_{int(datetime.now(timezone.utc).timestamp()*1000)}.{ext}"
    saved = save_media("payment-proofs", out_name, content, file.content_type)
    url = saved["url"]
    return {"success": True, "url": url, "filename": file.filename}


@router.post("/invoices/{invoice_id}/confirm-payment")
async def client_invoice_confirm_payment(
    invoice_id: str,
    data: Dict[str, Any] = Body(default={}),
    customer: Dict[str, Any] = Depends(get_current_customer),
):
    """Client states they have paid by bank transfer. Moves the invoice into
    the manager's review queue (status ``awaiting_confirmation``)."""
    db = get_db()
    inv = await db[C_INVOICES].find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    scope = _invoice_scope(customer)
    owns = await db[C_INVOICES].find_one({"$and": [{"id": invoice_id}, scope]}, {"_id": 1})
    if not owns:
        raise HTTPException(403, "Немає доступу до цього рахунку")
    if inv.get("status") not in ("sent", "pending", "overdue"):
        raise HTTPException(400, "Цей рахунок не очікує на оплату")

    proof_url = ((data or {}).get("proof_url") or "").strip()
    if not proof_url:
        raise HTTPException(400, "Спершу завантажте файл-підтвердження оплати (квитанцію/платіжне доручення).")

    now = datetime.now(timezone.utc).isoformat()
    claim = {
        "submitted_at": now,
        "submitted_by": customer.get("email"),
        "note": (data or {}).get("note") or "",
        "proof_url": proof_url,
        "amount": (data or {}).get("amount") or inv.get("amount") or inv.get("total"),
        "payer": (data or {}).get("payer") or customer.get("company_name") or customer.get("name"),
    }
    await db[C_INVOICES].update_one(
        {"id": invoice_id},
        {"$set": {"status": "awaiting_confirmation", "payment_claim": claim, "updated_at": now}},
    )

    # notify the assigned manager / staff (best-effort)
    try:
        await db.notifications.insert_one({
            "id": f"ntf_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            "managerId": inv.get("managerId"),
            "title": "Клієнт підтвердив оплату",
            "body": f"{claim['payer'] or 'Клієнт'} повідомив про оплату рахунку {inv.get('number') or invoice_id}. Перевірте платіж.",
            "type": "payment_review",
            "read": False,
            "createdAt": now,
            "created_at": now,
        })
    except Exception:
        logger.exception("[client] manager notify (payment claim) failed")

    fresh = await db[C_INVOICES].find_one({"id": invoice_id}, {"_id": 0})
    return {"success": True, "invoice": _invoice_view(fresh)}




async def _get_public_contacts(db) -> Dict[str, Any]:
    from app.site_directory import DEFAULT_CONTACTS
    doc = await db[C_SITE_CONTACTS].find_one({"id": "public_contacts"}, {"_id": 0})
    if not doc:
        seed = dict(DEFAULT_CONTACTS)
        try:
            await db[C_SITE_CONTACTS].insert_one(dict(seed))
        except Exception:
            pass
        return seed
    merged = {**DEFAULT_CONTACTS, **doc}
    return merged


@pub_router.get("/contacts")
async def public_contacts():
    """Public-facing contact block (header / footer / Contacts page)."""
    db = get_db()
    data = await _get_public_contacts(db)
    data.pop("_id", None)
    return {"success": True, "contacts": data}


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC newsletter subscribe (footer form) → `newsletter_subscribers`
# ════════════════════════════════════════════════════════════════════════════
C_NEWSLETTER = "newsletter_subscribers"


@pub_router.post("/newsletter/subscribe")
async def public_newsletter_subscribe(data: Dict[str, Any] = Body(...)):
    """Subscribe an email to the newsletter (idempotent by email)."""
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Вкажіть коректний email")
    db = get_db()
    now = S.now_iso()
    existing = await db[C_NEWSLETTER].find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        await db[C_NEWSLETTER].update_one(
            {"email": email},
            {"$set": {"status": "active", "updated_at": now}},
        )
        return {"success": True, "id": existing.get("id"), "already": True}
    doc = {
        "id": S.gen_id("nl"),
        "email": email,
        "source": (data.get("source") or "footer").strip()[:50],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    await db[C_NEWSLETTER].insert_one(doc)
    return {"success": True, "id": doc["id"]}


# ════════════════════════════════════════════════════════════════════════════
#  Contract Execution Engine — CLIENT read-only mirror
# ════════════════════════════════════════════════════════════════════════════
def _owns_contract(customer: Dict[str, Any], contract: Dict[str, Any]) -> bool:
    cid = customer.get("customerId") or customer.get("id")
    if contract.get("customer_id") and contract["customer_id"] == cid:
        return True
    if contract.get("customerId") and contract["customerId"] == cid:
        return True
    if customer.get("company_id") and contract.get("company_id") == customer.get("company_id"):
        return True
    return False


@router.get("/contract-engine")
async def client_ce_list(customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    cid = customer.get("customerId") or customer.get("id")
    ors: List[Dict[str, Any]] = [{"customer_id": cid}, {"customerId": cid}]
    if customer.get("company_id"):
        ors.append({"company_id": customer["company_id"]})
    contracts = await db[S.C_CONTRACTS].find(
        {"$or": ors, "schedule_config": {"$exists": True}}, {"_id": 0},
    ).sort("created_at", -1).to_list(length=200)
    return {"success": True, "items": contracts}


@router.get("/contract-engine/{contract_id}")
async def client_ce_detail(contract_id: str, customer: Dict[str, Any] = Depends(get_current_customer)):
    db = get_db()
    from app.contract_engine import constants as K
    from app.contract_engine import periods as PERIODS
    from app.contract_engine import financials as FIN
    from app.contract_engine import reports as REP

    contract = await db[S.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract or not _owns_contract(customer, contract):
        raise HTTPException(404, "Договір не знайдено")
    periods = await PERIODS.get_periods(contract_id, db=db)
    fin = await FIN.recompute(contract_id, db=db)
    acts = await db[K.C_ACTS].find({"contract_id": contract_id}, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    invoices = await db[K.C_INVOICES].find({"contract_id": contract_id}, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    reports = await REP.list_reports(contract_id, db=db)
    return {
        "success": True, "contract": contract, "periods": periods, "financials": fin,
        "acts": acts, "invoices": invoices, "ecologist_reports": reports,
    }


@router.get("/contract-engine/{contract_id}/reports/{report_id}/pdf")
async def client_ce_report_pdf(contract_id: str, report_id: str,
                               customer: Dict[str, Any] = Depends(get_current_customer)):
    from fastapi.responses import Response
    from app.contract_engine import constants as K
    from app.contract_engine import reports as REP
    db = get_db()
    contract = await db[S.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract or not _owns_contract(customer, contract):
        raise HTTPException(404, "Договір не знайдено")
    rep = await REP.get_report(report_id, db=db)
    if not rep or rep.get("contract_id") != contract_id:
        raise HTTPException(404, "Звіт не знайдено")
    company = await db[K.C_COMPANIES].find_one({"id": rep.get("company_id")}, {"_id": 0}) or {}
    try:
        html_str = REP.render_report_html(rep, contract, company)
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception:
        logger.exception("[client] eco report pdf failed")
        raise HTTPException(500, "Помилка генерації PDF")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{rep.get("number","report")}.pdf"'})
