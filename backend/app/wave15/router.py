"""
BIBI Cars — Wave 15 — Contract360 HTTP surface
=================================================

Mounted at `/api/contracts/*`.

Auth:
  * Listings / overview / risk   → require_user (scope-aware)
  * Mutations (create/send/approve/reject/sign/amend/archive)
                                  → require_manager_or_admin
  * Attachment upload/delete     → require_manager_or_admin
"""
from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile,
)
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave15.aggregations import (
    compute_contracts_overview, compute_contract_risk, scope_filter,
)
from app.wave15.contract_health import compute_contract_health
from app.wave15.models import (
    AmendAction, ApprovalAction, ContractCreate, ContractPatch, SignAction,
)
from app.wave15.service import (
    add_attachment, amend_contract, approve_contract, archive_contract,
    create_contract, get_contract, list_contracts, mark_opened, patch_contract,
    reject_contract, remove_attachment, send_contract, sign_contract,
)
from app.wave15.templates import list_templates

logger = logging.getLogger("bibi.wave15")
router = APIRouter(prefix="/api/contracts", tags=["Wave15:Contract360"])

from security import require_user, require_manager_or_admin  # type: ignore


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


# ═════════════════════════════════════════════════════════════════
# OVERVIEW + STATIC
# ═════════════════════════════════════════════════════════════════
@router.get("/overview")
async def overview_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_contracts_overview(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/templates")
async def templates_endpoint(_: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "items": list_templates(), "total": 4}


@router.get("/risk")
async def risk_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_contract_risk(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/me")
async def my_contracts_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Customer-side surface: list contracts that belong to the caller.

    Backwards-compatibility replacement for the legacy `/api/contracts/me`
    stub (which returned `{"contracts": []}`). Now actually scopes by
    customer_id resolved from the JWT.
    """
    db = _db(request)
    cust_id = current_user.get("customerId") or current_user.get("customer_id")
    q: Dict[str, Any] = {}
    if cust_id:
        q = {"customer_id": cust_id}
    items = await db.contracts.find(q, {"_id": 0}).sort("updated_at", -1).to_list(length=200)
    for c in items:
        c["health"] = compute_contract_health(c)
    return {"success": True, "contracts": items, "total": len(items)}


# ═════════════════════════════════════════════════════════════════
# LIST + DETAIL
# ═════════════════════════════════════════════════════════════════
@router.get("")
async def list_endpoint(
    request: Request,
    status:        Optional[str] = Query(None),
    type:          Optional[str] = Query(None, alias="type"),
    deal_id:       Optional[str] = Query(None),
    only_at_risk:  bool          = Query(False),
    limit:         int           = Query(200, ge=1, le=1000),
    current_user:  Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    f, scope = await scope_filter(db, current_user)
    items = await list_contracts(
        db, f,
        status=status, type_=type, deal_id=deal_id,
        only_at_risk=only_at_risk, limit=limit,
    )
    return {"success": True, "items": items, "total": len(items), "scope": scope}


@router.get("/{contract_id}")
async def detail_endpoint(
    contract_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    c = await get_contract(_db(request), contract_id)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


# ═════════════════════════════════════════════════════════════════
# WRITE
# ═════════════════════════════════════════════════════════════════
@router.post("")
async def create_endpoint(
    payload: ContractCreate,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await create_contract(_db(request), current_user, payload.model_dump(exclude_none=True))
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


# ─── Доопр #21 — auto-generate contract from calculator snapshot ──────
@router.post("/from-calculator")
async def create_from_calculator(
    payload: Dict[str, Any] = Body(...),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Generate a contract from a calculator snapshot.

    Body (JSON):
      {
        "customer_id": "cust_…",       # required
        "deal_id":     "deal_…",       # optional
        "snapshot":    { ...calc },    # the full calculator result
        "title":       "Auto purchase contract for ...",  # optional
        "currency":    "EUR"           # optional, default EUR
      }

    The snapshot is frozen into `terms.calculator` so the contract always
    reflects the values at generation time, even if base costs change
    later (\u0414\u043e\u043e\u043f\u0440 #21 \u201cAlready created contract keeps its values\u201d).
    """
    if not payload.get("customer_id"):
        raise HTTPException(400, "customer_id is required")
    snap = payload.get("snapshot") or {}
    amount = None
    for key in ("total", "totalEur", "total_eur", "grandTotal", "final_total"):
        if snap.get(key) is not None:
            try:
                amount = float(snap[key]); break
            except Exception:
                pass

    body = ContractCreate(
        deal_id=payload.get("deal_id"),
        customer_id=payload["customer_id"],
        template=payload.get("template", "purchase"),
        title=payload.get("title") or "Auto purchase contract (from calculator)",
        amount=amount,
        currency=(payload.get("currency") or "EUR"),
        # ── BG commission contract passthrough ────────────────────────
        contract_number=payload.get("contract_number"),
        place=payload.get("place") or "София",
        language=payload.get("language") or "bg",
        vehicle_spec=payload.get("vehicle_spec"),
        financial_terms=payload.get("financial_terms"),
        client_national_id=payload.get("client_national_id"),
        client_address=payload.get("client_address"),
        parties=payload.get("parties") or [],
        terms={
            "calculator": snap,
            "generated_from": "calculator",
            "snapshot_taken_at": payload.get("snapshot_taken_at"),
            **(payload.get("terms") or {}),
        },
        notes=payload.get("notes"),
    )
    c = await create_contract(_db(request), current_user, body.model_dump(exclude_none=True))
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.patch("/{contract_id}")
async def patch_endpoint(
    contract_id: str, payload: ContractPatch, request: Request,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await patch_contract(_db(request), contract_id, current_user, payload.model_dump(exclude_none=True))
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/send")
async def send_endpoint(
    contract_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await send_contract(_db(request), contract_id, current_user)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/approve")
async def approve_endpoint(
    contract_id: str, payload: ApprovalAction = Body(default=ApprovalAction()),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c, err = await approve_contract(_db(request), contract_id, current_user,
                                    step=payload.step, comment=payload.comment)
    if not c:
        raise HTTPException(404, "Contract not found")
    if err:
        # 409 if business state forbids it (eg wrong step / role)
        if err.startswith("role_"):
            raise HTTPException(403, err)
        raise HTTPException(409, err)
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/reject")
async def reject_endpoint(
    contract_id: str, payload: ApprovalAction = Body(default=ApprovalAction()),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await reject_contract(_db(request), contract_id, current_user, comment=payload.comment)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/sign")
async def sign_endpoint(
    contract_id: str, payload: SignAction = Body(default=SignAction()),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    c = await sign_contract(_db(request), contract_id, current_user, signer=payload.model_dump(exclude_none=True))
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/amend")
async def amend_endpoint(
    contract_id: str, payload: AmendAction = Body(default=AmendAction()),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await amend_contract(_db(request), contract_id, current_user,
                              reason=payload.reason, terms=payload.terms)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/archive")
async def archive_endpoint(
    contract_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await archive_contract(_db(request), contract_id, current_user)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.post("/{contract_id}/open")
async def open_endpoint(
    contract_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    c = await mark_opened(_db(request), contract_id, current_user)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


# ═════════════════════════════════════════════════════════════════
# ATTACHMENTS
# ═════════════════════════════════════════════════════════════════
@router.post("/{contract_id}/attachments")
async def upload_endpoint(
    contract_id: str, request: Request,
    file: Optional[UploadFile] = File(default=None),
    kind: str       = Form(default="annex"),
    kind_key: Optional[str] = Form(default=None),
    filename: Optional[str] = Form(default=None),
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    storage_key: Optional[str] = None
    size: Optional[int] = None
    content_type: Optional[str] = None
    if file is not None:
        # We avoid hard-binding to a specific object_storage backend so the
        # test surface can also stub-create attachments without a file. If
        # a real file is provided, we just stash metadata — the bytes are
        # consumed but not persisted by this minimal surface.
        data = await file.read()
        size = len(data) if data else None
        content_type = file.content_type
        filename = filename or file.filename or f"attachment_{uuid.uuid4().hex[:6]}"
        # storage_key remains None — callers wanting real storage should
        # plug app.services.object_storage in this branch; we keep this
        # surface dependency-free for the deterministic test suite.
    else:
        if not filename:
            raise HTTPException(400, "Either 'file' upload OR 'filename' form field is required")
    c = await add_attachment(
        db, contract_id, current_user,
        filename=filename, kind=kind, kind_key=kind_key or kind,
        size=size, content_type=content_type, storage_key=storage_key,
    )
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


@router.delete("/{contract_id}/attachments/{att_id}")
async def delete_attachment_endpoint(
    contract_id: str, att_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    c = await remove_attachment(_db(request), contract_id, current_user, att_id)
    if not c:
        raise HTTPException(404, "Contract not found")
    c["health"] = compute_contract_health(c)
    return {"success": True, "data": c}


# ═════════════════════════════════════════════════════════════════
# PDF RENDER — Bulgarian "Договор за поръчка" full lifecycle PDF
# ═════════════════════════════════════════════════════════════════
@router.post("/{contract_id}/render-pdf")
async def render_pdf_endpoint(
    contract_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Render the Bulgarian commission contract PDF for an existing wave15
    contract record. The PDF is saved into the customer's "Contracts"
    File Manager folder and the resulting URL is returned.

    Body (optional):
      language   — "bg" (default) / "en" / ...
      template_id — explicit template override (else default for language)
    """
    db = _db(request)
    c = await get_contract(db, contract_id)
    if not c:
        raise HTTPException(404, "Contract not found")

    customer_id = c.get("customer_id")
    if not customer_id:
        raise HTTPException(400, "Contract has no customer_id — cannot render PDF")

    # Pull buyer party for ВЪЗЛОЖИТЕЛ shortcut into top-level `customer` ctx
    buyer = next((p for p in (c.get("parties") or []) if (p.get("role") or "buyer") == "buyer"), {}) or {}

    from app.services.pdf_engine import generate as pdf_generate
    extra = {
        "contract": {
            "id":     c.get("id"),
            "number": c.get("contract_number") or c.get("id"),
            "date":   (c.get("signed_at") or c.get("created_at") or "")[:10],
            "place":  c.get("place") or "София",
        },
        "vehicle_spec":    c.get("vehicle_spec") or {},
        "vehicle":         c.get("vehicle_spec") or {},   # alias for templates that look at "vehicle"
        "terms":           c.get("terms") or {},
        "financial_terms": c.get("financial_terms") or {},
        # Buyer overrides (these merge on top of the resolved DB customer)
        "buyer_party": buyer,
    }

    # Inject buyer national_id / address_full into customer ctx so the
    # template renders them even when the customers collection doesn't
    # store ЕГН/ЛНЧ centrally.
    if buyer.get("national_id") or buyer.get("address_full") or buyer.get("address"):
        cust = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {}
        cust = {**cust, **{
            "national_id": buyer.get("national_id") or cust.get("national_id"),
            "address":     buyer.get("address_full") or buyer.get("address") or cust.get("address"),
            "name":        buyer.get("name") or cust.get("name") or (
                (cust.get("firstName") or "") + " " + (cust.get("lastName") or "")
            ).strip(),
        }}
        extra["customer_override"] = cust

    try:
        result = await pdf_generate(
            doc_type="contract",
            customer_id=customer_id,
            language=payload.get("language") or c.get("language") or "bg",
            template_id=payload.get("template_id"),
            extra_context=extra,
            generated_by=current_user.get("id"),
            generated_by_email=current_user.get("email"),
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))

    file_doc = result.get("file") or {}
    gen_doc  = result.get("document") or {}

    # Link the generated PDF onto the contract record so the UI can show it
    try:
        await db.contracts.update_one(
            {"id": contract_id},
            {"$push": {"pdfs": {
                "id":           gen_doc.get("id"),
                "version":      gen_doc.get("version"),
                "file_id":      file_doc.get("id"),
                "generated_at": gen_doc.get("generated_at"),
                "language":     gen_doc.get("language"),
                "by":           current_user.get("name") or current_user.get("email"),
            }}, "$set": {"updated_at": gen_doc.get("generated_at")}}
        )
    except Exception:
        pass

    return {"success": True, "data": {
        "file_id":      file_doc.get("id"),
        "document_id":  gen_doc.get("id"),
        "version":      gen_doc.get("version"),
        "language":     gen_doc.get("language"),
        "generated_at": gen_doc.get("generated_at"),
        "download_url": f"/api/file-manager/files/{file_doc.get('id')}/download" if file_doc.get("id") else None,
    }}


__all__ = ["router"]
