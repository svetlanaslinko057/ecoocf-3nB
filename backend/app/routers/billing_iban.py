"""
billing_iban.py — IBAN (bank-transfer) invoicing flow for ECO.NOVA.

No external payment gateway (Stripe is FROZEN). The flow is contract-first:

  1. Admin configures the company's legal entity + bank accounts per currency
     (UAH primary; USD/EUR optional). Single requisites document.
     GET/PUT  /api/admin/billing/requisites           (require_admin)

  2. A contract must be SIGNED first — online (e-sign, contracts_v2) or
     offline (manager uploads the signed file + marks it signed).
     GET  /api/manager/invoices/{id}/contract                 (status)
     POST /api/manager/invoices/{id}/contract/send-online     (e-sign link)
     POST /api/manager/invoices/{id}/contract/offline-sign    (upload file)

  3. Manager issues an invoice "by IBAN": the currency-matched requisites are
     snapshotted onto the invoice, a human number + payment purpose are
     generated and the invoice becomes ``sent``. Gated on a signed contract.
     POST /api/invoices/{id}/issue-iban               (manager/admin)
     GET  /api/billing/requisites                     (manager/admin preview)

  4. Client pays via bank transfer, uploads proof (mandatory) and confirms in
     the cabinet (handled in app/client/router.py) → ``awaiting_confirmation``.

  5. Manager reviews the queue and confirms (→ paid, executes the order via
     create_order_from_invoice) or rejects (→ back to ``sent``).
     GET  /api/manager/invoices/pending-confirmation  (manager/admin)
     POST /api/invoices/{id}/confirm-payment          (manager/admin)
     POST /api/invoices/{id}/reject-payment           (manager/admin)
"""
from __future__ import annotations

import logging
import pathlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile

from app.core.db_runtime import get_db
from security import require_admin, require_manager_or_admin

logger = logging.getLogger("eco.billing_iban")

router = APIRouter(tags=["billing-iban"])

REQUISITES_DOC_ID = "company_requisites"
C_BILLING = "billing_settings"
C_CONTRACTS = "contracts_v2"

# Statuses used by the IBAN flow
ST_AWAITING = "awaiting_confirmation"   # client claims paid, manager must review
ST_PAID = "paid"
ST_SENT = "sent"

SUPPORTED_CURRENCIES = ["UAH", "USD", "EUR"]

# Shared legal-entity fields (currency-independent)
LEGAL_FIELDS: Dict[str, Any] = {
    "legal_name": "",
    "edrpou": "",
    "ipn": "",
    "vat_payer": False,
    "legal_address": "",
    "director_name": "",
    "director_basis": "Статуту",
    "phone": "",
    "email": "",
    "payment_purpose_template": "Оплата за рахунком {number} від {date}",
    "notes": "",
}

# Per-currency bank account fields
ACCOUNT_FIELDS = ("currency", "iban", "bank_name", "mfo", "swift", "enabled")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc or {})
    doc.pop("_id", None)
    for k, val in list(doc.items()):
        doc[k] = _iso(val)
    return doc


def _norm_account(raw: Dict[str, Any]) -> Dict[str, Any]:
    cur = (raw.get("currency") or "UAH").upper()
    iban = (raw.get("iban") or "").replace(" ", "").upper()
    return {
        "currency": cur,
        "iban": iban,
        "bank_name": (raw.get("bank_name") or "").strip(),
        "mfo": (raw.get("mfo") or "").strip(),
        "swift": (raw.get("swift") or "").strip(),
        "enabled": bool(raw.get("enabled", True)) and bool(iban),
    }


async def get_requisites_doc() -> Dict[str, Any]:
    """Return the merged requisites document (legal entity + accounts[]).

    Backwards compatible: an old single-IBAN document (top-level iban/
    bank_name/mfo, no ``accounts``) is migrated-on-read into a single UAH
    account so historical configs keep working.
    """
    db = get_db()
    doc = await db[C_BILLING].find_one({"_id": REQUISITES_DOC_ID}) or {}

    merged: Dict[str, Any] = {**LEGAL_FIELDS}
    for k in LEGAL_FIELDS:
        if k in doc:
            merged[k] = doc[k]

    accounts = doc.get("accounts")
    if not accounts and (doc.get("iban") or "").strip():
        # migrate-on-read from the legacy single-IBAN shape
        accounts = [{
            "currency": "UAH",
            "iban": doc.get("iban"),
            "bank_name": doc.get("bank_name", ""),
            "mfo": doc.get("mfo", ""),
            "swift": doc.get("swift", ""),
            "enabled": True,
        }]
    accounts = [_norm_account(a) for a in (accounts or [])]

    merged["accounts"] = accounts
    merged["configured"] = any(a.get("enabled") and a.get("iban") for a in accounts)
    merged["currencies"] = [a["currency"] for a in accounts if a.get("enabled") and a.get("iban")]
    merged["updated_at"] = _iso(doc.get("updated_at"))
    merged["updated_by"] = doc.get("updated_by")
    return merged


def _pick_account(req: Dict[str, Any], currency: str) -> Optional[Dict[str, Any]]:
    currency = (currency or "UAH").upper()
    accounts = req.get("accounts") or []
    for a in accounts:
        if a.get("currency") == currency and a.get("enabled") and a.get("iban"):
            return a
    return None


def _can_act(invoice: Dict[str, Any], user: Dict[str, Any]) -> bool:
    role = (user.get("role") or "").lower()
    if role in ("master_admin", "owner", "admin", "team_lead"):
        return True
    if role == "manager" and invoice.get("managerId") == user.get("id"):
        return True
    return False


# ════════════════════════════════════════════════════════════════════════
#  Admin — company requisites (legal entity + accounts per currency)
# ════════════════════════════════════════════════════════════════════════
@router.get("/api/admin/billing/requisites", dependencies=[Depends(require_admin)])
async def admin_get_requisites():
    return {"success": True, "requisites": await get_requisites_doc(), "supported_currencies": SUPPORTED_CURRENCIES}


@router.put("/api/admin/billing/requisites", dependencies=[Depends(require_admin)])
async def admin_update_requisites(data: Dict[str, Any] = Body(...), user: dict = Depends(require_admin)):
    db = get_db()
    patch: Dict[str, Any] = {k: data[k] for k in data if k in LEGAL_FIELDS}

    if "accounts" in data and isinstance(data["accounts"], list):
        seen: Dict[str, Dict[str, Any]] = {}
        for raw in data["accounts"]:
            if not isinstance(raw, dict):
                continue
            acc = _norm_account(raw)
            if acc["currency"] not in SUPPORTED_CURRENCIES:
                continue
            # one account per currency — last wins
            seen[acc["currency"]] = acc
        patch["accounts"] = list(seen.values())

    patch["updated_at"] = _now()
    patch["updated_by"] = user.get("email") or user.get("id")
    await db[C_BILLING].update_one(
        {"_id": REQUISITES_DOC_ID}, {"$set": patch}, upsert=True
    )
    return {"success": True, "requisites": await get_requisites_doc()}


# ════════════════════════════════════════════════════════════════════════
#  Manager — preview requisites
# ════════════════════════════════════════════════════════════════════════
@router.get("/api/billing/requisites", dependencies=[Depends(require_manager_or_admin)])
async def manager_get_requisites():
    return {"success": True, "requisites": await get_requisites_doc()}


# ════════════════════════════════════════════════════════════════════════
#  Contract gating helpers (contract-first flow)
# ════════════════════════════════════════════════════════════════════════
async def _find_invoice_contract(db, invoice: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Most-recent contracts_v2 record linked to this invoice."""
    inv_id = invoice.get("id")
    cust_id = invoice.get("customerId")
    ors: List[Dict[str, Any]] = []
    if inv_id:
        ors.append({"invoiceId": inv_id})
        ors.append({"invoice_id": inv_id})
    if not ors:
        return None
    return await db[C_CONTRACTS].find_one({"$or": ors}, sort=[("created_at", -1)])


@router.get("/api/manager/invoices/{invoice_id}/contract", dependencies=[Depends(require_manager_or_admin)])
async def manager_invoice_contract(invoice_id: str, user: dict = Depends(require_manager_or_admin)):
    db = get_db()
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    if not _can_act(inv, user):
        raise HTTPException(403, "Forbidden")
    contract = await _find_invoice_contract(db, inv)
    return {"success": True, "contract": _clean(contract) if contract else None,
            "signed": bool(contract and contract.get("lifecycle") == "signed")}


@router.post("/api/manager/invoices/{invoice_id}/contract/offline-sign", dependencies=[Depends(require_manager_or_admin)])
async def manager_offline_sign_contract(
    invoice_id: str,
    file: UploadFile = File(...),
    signed_full_name: str = Form(""),
    note: str = Form(""),
    user: dict = Depends(require_manager_or_admin),
):
    """Manager attaches the offline-signed contract file and marks the linked
    contract as ``signed`` (contracts_v2). This unblocks IBAN issuing."""
    db = get_db()
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    if not _can_act(inv, user):
        raise HTTPException(403, "Forbidden")

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "Файл завеликий (макс. 15 МБ)")
    fname_lower = (file.filename or "").lower()
    allowed_ext = (".pdf", ".png", ".jpg", ".jpeg", ".webp")
    if not fname_lower.endswith(allowed_ext):
        raise HTTPException(400, "Дозволено: PDF, JPG, PNG, WEBP")
    ext = fname_lower.rsplit(".", 1)[-1]

    # Deployment-safe: store the signed contract in the MongoDB media store.
    from app.services.media_store import save_media
    out_name = f"signed_{invoice_id}_{int(datetime.now(timezone.utc).timestamp()*1000)}.{ext}"
    saved = save_media("signed-contracts", out_name, content, file.content_type)
    url = saved["url"]

    now = _now()
    existing = await _find_invoice_contract(db, inv)
    signer = (signed_full_name or "").strip() or inv.get("customerName") or "Підписано офлайн"
    if existing:
        await db[C_CONTRACTS].update_one(
            {"id": existing["id"]},
            {"$set": {
                "lifecycle": "signed",
                "signed_at": now,
                "signed_full_name": signer,
                "signed_offline": True,
                "signed_file_url": url,
                "signed_by": user.get("email") or user.get("id"),
                "offline_note": note or "",
                "updated_at": now,
            }},
        )
        contract = await db[C_CONTRACTS].find_one({"id": existing["id"]})
    else:
        import uuid as _uuid
        cid = f"ctr_{_uuid.uuid4().hex[:14]}"
        contract = {
            "id": cid,
            "customerId": inv.get("customerId"),
            "customer_id": inv.get("customerId"),
            "invoiceId": invoice_id,
            "dealId": inv.get("dealId"),
            "title": f"Договір за рахунком {inv.get('number') or invoice_id}",
            "lifecycle": "signed",
            "signed_at": now,
            "signed_full_name": signer,
            "signed_offline": True,
            "signed_file_url": url,
            "signed_by": user.get("email") or user.get("id"),
            "offline_note": note or "",
            "view_token": None,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("email") or user.get("id"),
        }
        await db[C_CONTRACTS].insert_one(dict(contract))

    # timeline event (best-effort)
    try:
        from app.services import customer_timeline
        await customer_timeline.record_event(
            customer_id=inv.get("customerId"),
            kind="contract_signed",
            title=f"Договір підписано офлайн ({signer})",
            ref={"collection": C_CONTRACTS, "id": (contract or {}).get("id")},
            actor={"name": user.get("email"), "role": "manager"},
            meta={"offline": True, "invoice_id": invoice_id},
        )
    except Exception:
        logger.exception("[billing] timeline emit (offline-sign) failed")

    return {"success": True, "contract": _clean(contract), "file_url": url}


@router.post("/api/manager/invoices/{invoice_id}/contract/send-online", dependencies=[Depends(require_manager_or_admin)])
async def manager_send_contract_online(invoice_id: str, user: dict = Depends(require_manager_or_admin)):
    """Ensure an ECO ``contracts_v2`` record exists for this invoice and put it
    into the ``sent`` state so the client can e-sign at ``/contract/{view_token}``.

    The contract content is built directly from the invoice (number, amount,
    items) + the customer + the company's legal requisites, in Ukrainian — we
    intentionally DO NOT call the generic PDF engine (which carries legacy
    car-import templates) so the e-sign page always shows correct ECO.NOVA data.
    """
    import uuid as _uuid

    db = get_db()
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    if not _can_act(inv, user):
        raise HTTPException(403, "Forbidden")

    from app.services import contract_lifecycle

    contract = await _find_invoice_contract(db, inv)
    if contract and contract.get("lifecycle") == "signed":
        return {"success": True, "contract": _clean(contract), "already_signed": True}

    # ── Build the ECO contract snapshot from the invoice ─────────────────────
    customer = await db.customers.find_one({"id": inv.get("customerId")}, {"_id": 0}) or {}
    req = await get_requisites_doc()
    number = inv.get("number") or await _next_invoice_number(db)
    amount = inv.get("amount") or inv.get("total") or 0
    currency = (inv.get("currency") or "UAH").upper()
    items = inv.get("items") or []
    title = f"Договір на утилізацію відходів за рахунком {number}"
    company_snap = {
        "name": customer.get("companyName") or customer.get("company_name") or customer.get("name") or "—",
        "edrpou": customer.get("edrpou") or "",
        "email": customer.get("email") or "",
    }
    operator_snap = {
        "name": req.get("legal_name") or "ECO.NOVA Utilization Operator",
        "edrpou": req.get("edrpou") or "",
    }
    now = _now()

    if not contract:
        cid = f"ctr_{_uuid.uuid4().hex[:14]}"
        contract = {
            "id": cid,
            "customerId": inv.get("customerId"),
            "customer_id": inv.get("customerId"),
            "invoiceId": invoice_id,
            "dealId": inv.get("dealId"),
            "file_id": None,
            "document_id": None,
            "template_id": None,
            "language": "uk",
            "title": title,
            "number": number,
            "amount": amount,
            "currency": currency,
            "items": items,
            "company": company_snap,
            "operator": operator_snap,
            "version": 1,
            "lifecycle": "draft",
            "view_token": None,
            "sent_at": None, "viewed_at": None, "signed_at": None,
            "signed_by": None, "signed_ip": None, "signed_user_agent": None, "signed_full_name": None,
            "archived_at": None, "cancelled_at": None,
            "created_at": now, "updated_at": now,
            "created_by": user.get("id"), "created_by_email": user.get("email"),
        }
        await db[C_CONTRACTS].insert_one(dict(contract))
    else:
        # backfill snapshot fields onto an existing draft/sent contract
        await db[C_CONTRACTS].update_one(
            {"id": contract["id"]},
            {"$set": {
                "title": contract.get("title") or title,
                "number": contract.get("number") or number,
                "amount": contract.get("amount") if contract.get("amount") is not None else amount,
                "currency": contract.get("currency") or currency,
                "items": contract.get("items") or items,
                "company": contract.get("company") or company_snap,
                "operator": contract.get("operator") or operator_snap,
                "language": "uk",
                "updated_at": now,
            }},
        )

    fresh = await contract_lifecycle.mark_sent(contract["id"], by=user)
    fresh = fresh or await db[C_CONTRACTS].find_one({"id": contract["id"]}, {"_id": 0})

    # Generate the proper ECO Ukrainian contract PDF (best-effort) and attach it.
    try:
        from app.services.eco_contract_pdf import generate_eco_contract_pdf
        file_doc = await generate_eco_contract_pdf(
            fresh, requisites=req,
            generated_by=user.get("id"), generated_by_email=user.get("email"),
        )
        if file_doc and file_doc.get("id"):
            await db[C_CONTRACTS].update_one(
                {"id": contract["id"]},
                {"$set": {"file_id": file_doc["id"], "updated_at": _now()}},
            )
            fresh = await db[C_CONTRACTS].find_one({"id": contract["id"]}, {"_id": 0})
    except Exception:
        logger.exception("[billing] ECO contract PDF generation failed (non-fatal)")

    return {"success": True, "contract": _clean(fresh), "view_token": (fresh or {}).get("view_token")}


# ════════════════════════════════════════════════════════════════════════
#  Manager — issue invoice by IBAN (gated on a signed contract)
# ════════════════════════════════════════════════════════════════════════
async def _next_invoice_number(db) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"{year}-"
    cnt = await db.invoices.count_documents({"number": {"$regex": f"^{prefix}"}})
    return f"{prefix}{cnt + 1:04d}"


@router.post("/api/invoices/{invoice_id}/issue-iban", dependencies=[Depends(require_manager_or_admin)])
async def issue_invoice_iban(invoice_id: str, user: dict = Depends(require_manager_or_admin)):
    """Snapshot the currency-matched company requisites onto the invoice,
    assign a number + payment purpose, and mark it ``sent``. Requires a
    SIGNED contract linked to the invoice (contract-first rule)."""
    db = get_db()
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    if not _can_act(inv, user):
        raise HTTPException(403, "Forbidden")

    # ── Contract-first gate ──────────────────────────────────────────────
    contract = await _find_invoice_contract(db, inv)
    if not contract or contract.get("lifecycle") != "signed":
        raise HTTPException(
            400,
            "Договір ще не підписано. Спершу підпишіть договір (онлайн e-підпис "
            "або завантажте підписаний файл), потім виставляйте рахунок."
        )

    currency = (inv.get("currency") or "UAH").upper()
    req = await get_requisites_doc()
    account = _pick_account(req, currency)
    if not account:
        raise HTTPException(
            400,
            f"Реквізити для валюти {currency} не налаштовані. "
            f"Заповніть їх у розділі «Реквізити для оплати»."
        )

    number = inv.get("number") or await _next_invoice_number(db)
    issued_at = _now()
    date_str = issued_at[:10]
    purpose_tmpl = (req.get("payment_purpose_template") or "Оплата за рахунком {number} від {date}")
    try:
        purpose = purpose_tmpl.format(number=number, date=date_str)
    except Exception:
        purpose = f"Оплата за рахунком {number} від {date_str}"

    snapshot = {k: req.get(k) for k in LEGAL_FIELDS}
    snapshot.update({
        "currency": account["currency"],
        "iban": account["iban"],
        "bank_name": account["bank_name"],
        "mfo": account["mfo"],
        "swift": account["swift"],
    })

    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "number": number,
            "status": ST_SENT,
            "paymentMethod": "iban",
            "paymentChannel": "iban",
            "requisites": snapshot,
            "payment_purpose": purpose,
            "contract_id": contract.get("id"),
            "issuedAt": issued_at,
            "sentAt": issued_at,
            "updated_at": issued_at,
        }},
    )

    # timeline event (best-effort)
    try:
        from app.services import customer_timeline
        await customer_timeline.record_event(
            customer_id=inv.get("customerId"),
            kind="iban_issued",
            title=f"Виставлено рахунок {number} (IBAN)",
            ref={"collection": "invoices", "id": invoice_id},
            meta={"amount": inv.get("amount") or inv.get("total"), "currency": currency},
        )
    except Exception:
        logger.exception("[billing] timeline emit (issue) failed")

    fresh = _clean(await db.invoices.find_one({"id": invoice_id}) or {})
    return {"success": True, "invoice": fresh}


# ════════════════════════════════════════════════════════════════════════
#  Manager — review queue + confirm / reject client payment
# ════════════════════════════════════════════════════════════════════════
@router.get("/api/manager/invoices/pending-confirmation", dependencies=[Depends(require_manager_or_admin)])
async def manager_pending_confirmation(user: dict = Depends(require_manager_or_admin), limit: int = 100):
    db = get_db()
    role = (user.get("role") or "").lower()
    q: Dict[str, Any] = {"status": ST_AWAITING}
    if role not in ("master_admin", "owner", "admin", "team_lead"):
        q["managerId"] = user.get("id")
    rows = await db.invoices.find(q, {"_id": 0}).sort("payment_claim.submitted_at", -1).limit(int(limit)).to_list(length=int(limit))
    out: List[Dict[str, Any]] = []
    for inv in rows:
        cust = await db.customers.find_one({"id": inv.get("customerId")}, {"_id": 0, "name": 1, "company_name": 1, "email": 1}) or {}
        inv["customer"] = cust
        out.append(_clean(inv))
    return {"success": True, "items": out, "count": len(out)}


@router.post("/api/invoices/{invoice_id}/confirm-payment", dependencies=[Depends(require_manager_or_admin)])
async def manager_confirm_payment(invoice_id: str, data: Dict[str, Any] = Body(default={}), user: dict = Depends(require_manager_or_admin)):
    db = get_db()
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    if not _can_act(inv, user):
        raise HTTPException(403, "Forbidden")
    if inv.get("status") == ST_PAID:
        return {"success": True, "invoice": _clean(inv), "already_paid": True}

    now = _now()
    note = (data or {}).get("note") or ""
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": ST_PAID,
            "paidAt": now,
            "paymentMethod": "iban",
            "paidBy": user.get("email") or user.get("id"),
            "paymentNote": note,
            "payment_claim.confirmed_at": now,
            "payment_claim.confirmed_by": user.get("email") or user.get("id"),
            "updated_at": now,
        }},
    )
    fresh = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})

    # ── Execute the order (idempotent): create order, notifications, roadmap ──
    order_id = None
    try:
        from app.services.orders import create_order_from_invoice
        order = await create_order_from_invoice(fresh)
        order_id = (order or {}).get("id")
        if order_id:
            await db.invoices.update_one({"id": invoice_id}, {"$set": {"order_id": order_id}})
    except Exception:
        logger.exception("[billing] order execution failed (non-fatal)")

    # notify client (best-effort)
    try:
        await db.notifications.insert_one({
            "id": f"ntf_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            "customerId": inv.get("customerId"),
            "title": "Платіж підтверджено",
            "body": f"Оплату за рахунком {fresh.get('number') or invoice_id} підтверджено. Замовлення прийнято в роботу. Дякуємо!",
            "type": "payment",
            "read": False,
            "createdAt": now,
            "created_at": now,
        })
    except Exception:
        logger.exception("[billing] client notify (confirm) failed")

    return {"success": True, "invoice": _clean(fresh), "order_id": order_id}


@router.post("/api/invoices/{invoice_id}/reject-payment", dependencies=[Depends(require_manager_or_admin)])
async def manager_reject_payment(invoice_id: str, data: Dict[str, Any] = Body(default={}), user: dict = Depends(require_manager_or_admin)):
    db = get_db()
    inv = await db.invoices.find_one({"id": invoice_id})
    if not inv:
        raise HTTPException(404, "Рахунок не знайдено")
    if not _can_act(inv, user):
        raise HTTPException(403, "Forbidden")
    now = _now()
    reason = (data or {}).get("reason") or "Платіж не знайдено"
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "status": ST_SENT,
            "payment_claim.rejected_at": now,
            "payment_claim.rejected_by": user.get("email") or user.get("id"),
            "payment_claim.rejection_reason": reason,
            "updated_at": now,
        }},
    )
    fresh = _clean(await db.invoices.find_one({"id": invoice_id}) or {})
    try:
        await db.notifications.insert_one({
            "id": f"ntf_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            "customerId": inv.get("customerId"),
            "title": "Оплату не підтверджено",
            "body": f"Оплату за рахунком {fresh.get('number') or invoice_id} не підтверджено: {reason}. Перевірте платіж.",
            "type": "payment",
            "read": False,
            "createdAt": now,
            "created_at": now,
        })
    except Exception:
        logger.exception("[billing] client notify (reject) failed")
    return {"success": True, "invoice": fresh}
