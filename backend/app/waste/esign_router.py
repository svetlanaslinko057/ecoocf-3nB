"""
ECO Waste — Electronic contract signing (e-sign) flow
======================================================

Adds a real e-signature lifecycle on top of the waste_contracts collection,
mirroring the proven tokenized pattern used by the legacy car-CRM
(app/services/contract_lifecycle.py) but bound to the ECO waste domain.

Staff (manager/admin, prefix /api/waste):
    POST /api/waste/contracts/{id}/send-esign     — generate unguessable
          view_token, flip status -> "sent", return a public share URL the
          operator copies / emails to the client.
    POST /api/waste/contracts/{id}/revoke-esign   — invalidate the token
          (link stops working) without deleting the contract.

Public (no auth — guarded only by the unguessable token, whitelisted via the
/api/public/* access-gate rule):
    GET  /api/public/waste-contract/{token}        — client-facing read view
          (records first open -> esign_viewed_at, idempotent).
    POST /api/public/waste-contract/{token}/sign   — client signs: typed full
          name + explicit terms acceptance. Captures IP + user-agent for audit,
          flips status -> "signed", stamps signed_at/by, logs activity.
    GET  /api/public/waste-contract/{token}/pdf     — streams the contract PDF
          (rendered on demand) so the client can read before signing.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import Response

from security import require_manager_or_admin
from app.core.db_runtime import get_db
from app.waste import service as S

logger = logging.getLogger("eco.waste.esign")

# Staff-guarded surface (lives under the existing /api/waste prefix)
staff_router = APIRouter(prefix="/api/waste", tags=["waste-esign"])
# Public surface (token-guarded; /api/public/* is whitelisted in access_gate)
public_router = APIRouter(prefix="/api/public", tags=["waste-esign-public"])


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _public_base(request: Optional[Request]) -> str:
    if request is None:
        return ""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return f"{proto}://{host}".rstrip("/") if host else ""


async def _contract_or_404(db, contract_id: str) -> Dict[str, Any]:
    doc = await db[S.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Договір не знайдено")
    return doc


# ════════════════════════════════════════════════════════════════════════════
#  STAFF — send / revoke e-sign link
# ════════════════════════════════════════════════════════════════════════════
@staff_router.post("/contracts/{contract_id}/send-esign",
                   dependencies=[Depends(require_manager_or_admin)])
async def send_esign(contract_id: str, request: Request,
                     user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await _contract_or_404(db, contract_id)
    if doc.get("status") == "signed":
        raise HTTPException(400, "Договір уже підписано")
    if doc.get("status") in ("cancelled", "closed"):
        raise HTTPException(400, f"Не можна надіслати договір у статусі «{doc.get('status')}»")

    token = doc.get("view_token") or _new_token()
    now = S.now_iso()
    by = user.get("email") or user.get("id") or "system"
    set_fields = {
        "view_token": token,
        "esign_status": "sent",
        "status": "sent",
        "esign_sent_at": doc.get("esign_sent_at") or now,
        "esign_sent_by": by,
        "esign_revoked": False,
        "updated_at": now,
    }
    hist = {"status": "sent", "at": now, "by": by, "note": "Надіслано на е-підпис"}
    await db[S.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": set_fields, "$push": {"status_history": hist}},
    )
    try:
        await S.log_activity(
            db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
            entity_type="contract", entity_id=contract_id, event="esign_sent",
            message=f"Договір {doc.get('number','')} надіслано на електронний підпис", by=by,
        )
    except Exception:
        logger.exception("[esign] activity log failed")

    base = _public_base(request)
    share_url = f"{base}/contract/{token}" if base else f"/contract/{token}"
    fresh = await db[S.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    return {"success": True, "contract": S.serialize(fresh), "view_token": token, "share_url": share_url}


@staff_router.post("/contracts/{contract_id}/revoke-esign",
                   dependencies=[Depends(require_manager_or_admin)])
async def revoke_esign(contract_id: str,
                       user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await _contract_or_404(db, contract_id)
    if doc.get("status") == "signed":
        raise HTTPException(400, "Договір уже підписано — відкликати посилання не можна")
    now = S.now_iso()
    by = user.get("email") or user.get("id") or "system"
    await db[S.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"view_token": None, "esign_status": "revoked", "esign_revoked": True, "updated_at": now}},
    )
    try:
        await S.log_activity(
            db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
            entity_type="contract", entity_id=contract_id, event="esign_revoked",
            message=f"Посилання на е-підпис договору {doc.get('number','')} відкликано", by=by,
        )
    except Exception:
        logger.exception("[esign] activity log failed")
    fresh = await db[S.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    return {"success": True, "contract": S.serialize(fresh)}


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC — view / sign / pdf (token-guarded)
# ════════════════════════════════════════════════════════════════════════════
async def _by_token_or_404(db, token: str) -> Dict[str, Any]:
    if not token:
        raise HTTPException(404, "Договір не знайдено")
    doc = await db[S.C_CONTRACTS].find_one({"view_token": token}, {"_id": 0})
    if not doc or doc.get("esign_revoked"):
        raise HTTPException(404, "Договір не знайдено або посилання більше недоступне")
    if doc.get("status") in ("cancelled",):
        raise HTTPException(410, "Договір було скасовано")
    return doc


def _public_payload(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "number": doc.get("number"),
        "title": doc.get("title"),
        "amount": doc.get("amount"),
        "currency": doc.get("currency") or "UAH",
        "valid_from": doc.get("valid_from"),
        "valid_to": doc.get("valid_to"),
        "items": doc.get("items") or [],
        "status": doc.get("status"),
        "esign_status": doc.get("esign_status"),
        "esign_sent_at": doc.get("esign_sent_at"),
        "esign_viewed_at": doc.get("esign_viewed_at"),
        "signed_at": doc.get("signed_at"),
        "signed_by": doc.get("signed_by"),
        "has_pdf": bool(doc.get("file_id")),
    }


@public_router.get("/waste-contract/{token}")
async def public_view(token: str):
    db = get_db()
    doc = await _by_token_or_404(db, token)

    # Idempotent first-open registration.
    if not doc.get("esign_viewed_at") and doc.get("status") != "signed":
        now = S.now_iso()
        await db[S.C_CONTRACTS].update_one(
            {"id": doc["id"]},
            {"$set": {"esign_viewed_at": now, "esign_status": "viewed", "updated_at": now}},
        )
        doc["esign_viewed_at"] = now
        doc["esign_status"] = "viewed"

    company = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) or {}
    return {
        "success": True,
        "contract": _public_payload(doc),
        "company": {
            "id": company.get("id"),
            "name": company.get("name"),
            "edrpou": company.get("edrpou"),
            "address": company.get("address"),
        },
        "operator": {
            "name": "ECO Utilization Operator",
            "edrpou": "44990001",
            "address": "Київ, вул. Екологічна 1",
        },
    }


@public_router.post("/waste-contract/{token}/sign")
async def public_sign(token: str, request: Request, data: Dict[str, Any] = Body(...)):
    db = get_db()
    doc = await _by_token_or_404(db, token)

    full_name = (data.get("full_name") or data.get("fullName") or "").strip()
    terms = bool(data.get("terms_accepted") or data.get("termsAccepted"))
    if not full_name:
        raise HTTPException(400, "Вкажіть прізвище та ім'я підписанта")
    if len(full_name) < 4:
        raise HTTPException(400, "Введіть повне ім'я підписанта")
    if not terms:
        raise HTTPException(400, "Необхідно прийняти умови договору перед підписанням")

    if doc.get("status") == "signed":
        # Idempotent: already signed.
        return {"success": True, "already_signed": True, "contract": _public_payload(doc)}

    now = S.now_iso()
    ip = _client_ip(request)
    ua = request.headers.get("user-agent") if request else None
    set_fields = {
        "status": "signed",
        "esign_status": "signed",
        "signed_at": now,
        "signed_by": full_name,
        "signed_ip": ip,
        "signed_user_agent": ua,
        "updated_at": now,
    }
    hist = {"status": "signed", "at": now, "by": full_name, "note": "Підписано клієнтом (е-підпис)"}
    await db[S.C_CONTRACTS].update_one(
        {"id": doc["id"]},
        {"$set": set_fields, "$push": {"status_history": hist}},
    )
    try:
        await S.log_activity(
            db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
            entity_type="contract", entity_id=doc["id"], event="signed",
            message=f"Договір {doc.get('number','')} підписано клієнтом: {full_name}",
            by=full_name,
        )
    except Exception:
        logger.exception("[esign] activity log failed")

    fresh = await db[S.C_CONTRACTS].find_one({"id": doc["id"]}, {"_id": 0})
    return {"success": True, "contract": _public_payload(fresh)}


@public_router.get("/waste-contract/{token}/pdf")
async def public_pdf(token: str):
    db = get_db()
    doc = await _by_token_or_404(db, token)
    company = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) or {}

    try:
        from app.storage.pdf.renderer import render_pdf
        from app.storage.pdf.router import BRAND, _items_total
        pdf_bytes = render_pdf(
            "contract.html",
            {"brand": BRAND, "contract": doc, "company": company,
             "items_total": _items_total(doc.get("items"))},
        )
    except Exception as e:
        logger.exception("[esign] pdf render failed")
        raise HTTPException(500, f"Не вдалося згенерувати PDF: {e}")

    fname = f"contract-{doc.get('number') or doc.get('id')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )
