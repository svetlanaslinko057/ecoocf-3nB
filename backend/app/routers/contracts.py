"""
Contract Lifecycle router — Mini Sprint Contracts Final
=========================================================

REST surface for sending, viewing, signing, archiving contracts.

Admin / Manager (authenticated):
  GET    /api/customers/{customer_id}/contracts        — list with lifecycle
  GET    /api/contract-lifecycle/{contract_id}                  — detail
  POST   /api/contract-lifecycle/{contract_id}/send             — generate view_token, set sent
  POST   /api/contract-lifecycle/{contract_id}/archive          — archive
  POST   /api/contract-lifecycle/{contract_id}/cancel           — cancel (admin only)

NOTE: the authenticated action endpoints live under the dedicated
``/api/contract-lifecycle`` prefix (NOT ``/api/contracts/{id}``) to avoid
colliding with the Wave15 Contract360 router which owns
``/api/contracts/{id}`` (detail/send/sign/archive) for a different
collection. The public viewer/signer keeps the 2-segment
``/api/contracts/view/{token}`` paths which never collide with Wave15.

Public (no auth, keyed by view_token):
  GET    /api/contracts/view/{view_token}              — customer-facing detail (records view)
  POST   /api/contracts/view/{view_token}/sign         — customer signs

Download (auth or public via token):
  GET    /api/contracts/{contract_id}/download         — redirect to underlying PDF
  GET    /api/contracts/view/{view_token}/download     — customer download
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.db_runtime import get_db
from app.services import contract_lifecycle as svc
from security import require_admin, require_manager_or_admin

import logging
logger = logging.getLogger("eco.contracts")

router = APIRouter(tags=["contracts"])


async def _resolve_file_url(file_id: str) -> Optional[str]:
    """Return a downloadable URL for the underlying PDF.

    File Manager stores files under ``/api/file-manager/files/{id}/download``
    which is the authenticated path. For public-viewer flow we leverage the
    short-lived view_token route handled below to stream bytes.
    """
    if not file_id:
        return None
    return f"/api/file-manager/files/{file_id}/download"


# ---------------------------------------------------------------------
# Admin / Manager endpoints (auth)
# ---------------------------------------------------------------------


@router.get("/api/customers/{customer_id}/contracts",
            dependencies=[Depends(require_manager_or_admin)])
async def list_contracts(customer_id: str, include_archived: bool = True):
    items = await svc.list_for_customer(customer_id, include_archived=include_archived)
    # enrich with download_url
    for c in items:
        c["download_url"] = await _resolve_file_url(c.get("file_id"))
    return {"success": True, "items": items, "total": len(items)}


@router.get("/api/contract-lifecycle/{contract_id}",
            dependencies=[Depends(require_manager_or_admin)])
async def get_contract(contract_id: str):
    doc = await svc.get_by_id(contract_id)
    if not doc:
        raise HTTPException(404, "Contract not found")
    doc["download_url"] = await _resolve_file_url(doc.get("file_id"))
    return {"success": True, "contract": doc}


@router.post("/api/contract-lifecycle/{contract_id}/send",
             dependencies=[Depends(require_manager_or_admin)])
async def send_contract(
    contract_id: str,
    user: dict = Depends(require_manager_or_admin),
    request: Request = None,
):
    try:
        doc = await svc.mark_sent(contract_id, by={"id": user.get("id"), "email": user.get("email")})
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not doc:
        raise HTTPException(404, "Contract not found")

    # Build the public share URL the manager can copy/paste / email.
    base = ""
    if request is not None:
        # Prefer the X-Forwarded-Host so we land on the public preview
        # URL, not the internal :8001 binding.
        fwd_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        base = f"{fwd_proto}://{fwd_host}".rstrip("/") if fwd_host else ""
    share_url = f"{base}/contract/{doc.get('view_token')}" if doc.get("view_token") else None
    return {"success": True, "contract": doc, "share_url": share_url}


@router.post("/api/contract-lifecycle/{contract_id}/archive",
             dependencies=[Depends(require_manager_or_admin)])
async def archive_contract(contract_id: str, user: dict = Depends(require_manager_or_admin)):
    doc = await svc.archive(contract_id, by={"id": user.get("id")})
    if not doc:
        raise HTTPException(404, "Contract not found")
    return {"success": True, "contract": doc}


@router.post("/api/contract-lifecycle/{contract_id}/cancel",
             dependencies=[Depends(require_admin)])
async def cancel_contract(
    contract_id: str,
    data: Dict[str, Any] = Body(default_factory=dict),
    user: dict = Depends(require_admin),
):
    try:
        doc = await svc.cancel(contract_id, by={"id": user.get("id")}, reason=data.get("reason"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not doc:
        raise HTTPException(404, "Contract not found")
    return {"success": True, "contract": doc}


# ---------------------------------------------------------------------
# Public viewer + signer (no auth, keyed by view_token)
# ---------------------------------------------------------------------


@router.get("/api/contracts/view/{view_token}")
async def public_view(view_token: str, request: Request):
    doc = await svc.get_by_view_token(view_token)
    if not doc:
        raise HTTPException(404, "Contract not found or no longer accessible")
    if doc.get("lifecycle") == "cancelled":
        raise HTTPException(410, "Contract was cancelled")
    if doc.get("lifecycle") == "archived":
        raise HTTPException(410, "Contract has been archived")

    # Idempotent view registration
    fresh = await svc.record_view(view_token) or doc

    # Pull customer name/email for the viewer
    db = get_db()
    cust = await db.customers.find_one(
        {"id": fresh.get("customerId") or fresh.get("customer_id")},
        {"_id": 0, "firstName": 1, "lastName": 1, "email": 1, "company": 1},
    )

    return {
        "success": True,
        "contract": {
            # Strip server-only fields when returning to a public client
            "id": fresh.get("id"),
            "title": fresh.get("title"),
            "number": fresh.get("number"),
            "amount": fresh.get("amount"),
            "currency": fresh.get("currency"),
            "items": fresh.get("items") or [],
            "valid_from": fresh.get("valid_from") or fresh.get("sent_at"),
            "valid_to": fresh.get("valid_to"),
            "company": fresh.get("company") or {},
            "operator": fresh.get("operator") or {},
            "version": fresh.get("version"),
            "language": fresh.get("language"),
            "lifecycle": fresh.get("lifecycle"),
            "status": fresh.get("lifecycle"),
            "esign_status": fresh.get("lifecycle"),
            "sent_at": fresh.get("sent_at"),
            "viewed_at": fresh.get("viewed_at"),
            "signed_at": fresh.get("signed_at"),
            "signed_full_name": fresh.get("signed_full_name"),
            "signed_by": fresh.get("signed_full_name"),
            "signature": fresh.get("signature"),
            "file_id": fresh.get("file_id"),
            "has_pdf": bool(fresh.get("file_id")),
            "pdf_url": (f"/api/contracts/view/{view_token}/download" if fresh.get("file_id") else None),
            "download_url": f"/api/contracts/view/{view_token}/download",
        },
        "company": fresh.get("company") or {},
        "operator": fresh.get("operator") or {},
        "customer": cust or {},
    }


@router.post("/api/contracts/view/{view_token}/sign")
async def public_sign(view_token: str, data: Dict[str, Any] = Body(...), request: Request = None):
    full_name = (data.get("full_name") or data.get("fullName") or "").strip()
    terms = bool(data.get("terms_accepted") or data.get("termsAccepted"))
    consent_text = data.get("consent_text") or data.get("consentText")
    consent_version = data.get("consent_version") or data.get("consentVersion")
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() if request else None
    if not ip and request is not None:
        ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent") if request else None
    try:
        doc = await svc.sign(
            view_token,
            full_name=full_name,
            terms_accepted=terms,
            ip=ip,
            user_agent=ua,
            consent_text=consent_text,
            consent_version=consent_version,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not doc:
        raise HTTPException(404, "Contract not found")

    # ECO invoice contracts: regenerate the signed Ukrainian PDF (best-effort)
    # so the downloadable document carries the stamped e-signature.
    try:
        if doc.get("items") and doc.get("number"):
            from app.services.eco_contract_pdf import generate_eco_contract_pdf
            from app.routers.billing_iban import get_requisites_doc
            req = await get_requisites_doc()
            file_doc = await generate_eco_contract_pdf(doc, requisites=req)
            if file_doc and file_doc.get("id"):
                db = get_db()
                await db[svc.COLLECTION].update_one(
                    {"id": doc["id"]}, {"$set": {"file_id": file_doc["id"]}}
                )
    except Exception:
        logger.exception("[contracts] signed ECO PDF regeneration failed (non-fatal)")

    return {
        "success": True,
        "contract": {
            "id": doc["id"],
            "lifecycle": doc["lifecycle"],
            "signed_at": doc["signed_at"],
            "signed_full_name": doc["signed_full_name"],
            "signature": doc.get("signature"),
        },
        "signature": doc.get("signature"),
    }


@router.get("/api/contracts/view/{view_token}/download")
async def public_download(view_token: str):
    from fastapi.responses import StreamingResponse
    from app.services import file_manager as fm
    from app.services.object_storage import get_storage

    doc = await svc.get_by_view_token(view_token)
    if not doc:
        raise HTTPException(404, "Contract not found")
    if doc.get("lifecycle") in {"cancelled", "archived"}:
        raise HTTPException(410, "Contract is no longer accessible")

    f = await fm.get_file(doc.get("file_id"))
    if not f:
        raise HTTPException(404, "File not found")
    storage = get_storage()
    try:
        stream = storage.open(f["storage_key"])
    except FileNotFoundError:
        raise HTTPException(410, "Binary missing on storage backend")

    def _iter():
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                stream.close()
            except Exception:
                pass

    return StreamingResponse(
        _iter(),
        media_type=f.get("mime_type") or "application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{f.get("original_name", "contract.pdf")}"',
            "Cache-Control": "private, max-age=300",
        },
    )
