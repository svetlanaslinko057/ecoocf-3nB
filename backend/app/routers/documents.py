"""
documents - Sprint 3 PDF Engine HTTP surface.

Admin-facing template CRUD:
  GET/POST    /api/admin/document-templates
  GET/PATCH/DELETE /api/admin/document-templates/{template_id}
  POST        /api/admin/document-templates/seed-defaults

Manager-facing generation endpoints (always auto-save into File Manager):
  POST /api/invoices/{invoice_id}/contract          -> Contract PDF
  POST /api/invoices/{invoice_id}/invoice-pdf       -> Invoice PDF (export)
  POST /api/orders/{order_id}/acceptance-act        -> Acceptance Act PDF
  POST /api/customers/{customer_id}/generated-documents -> list per customer
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_manager_or_admin, require_admin
from app.core.db_runtime import get_db
from app.repositories import document_templates as tpl_repo
from app.services import pdf_engine

logger = logging.getLogger("bibi.documents")

router = APIRouter(tags=["documents"])


# ─────────────────────────────────────────────────────────────────────
# Admin: template CRUD
# ─────────────────────────────────────────────────────────────────────

@router.get("/api/admin/document-templates",
            dependencies=[Depends(require_admin)])
async def admin_list_templates(
    type: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
):
    items = await tpl_repo.list_templates(type=type, language=language)
    return {"success": True, "items": items, "total": len(items)}


@router.post("/api/admin/document-templates",
             dependencies=[Depends(require_admin)])
async def admin_create_template(data: Dict[str, Any] = Body(...), user: dict = Depends(require_admin)):
    try:
        tpl = await tpl_repo.create_template(data, created_by=user.get("email") or user.get("id"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "template": tpl}


@router.post("/api/admin/document-templates/seed-defaults",
             dependencies=[Depends(require_admin)])
async def admin_seed_defaults():
    items = await tpl_repo.seed_default_templates()
    return {"success": True, "items": items, "seeded": len(items)}


@router.get("/api/admin/document-templates/{template_id}",
            dependencies=[Depends(require_admin)])
async def admin_get_template(template_id: str):
    tpl = await tpl_repo.get_template(template_id)
    if not tpl: raise HTTPException(404, "Template not found")
    return {"success": True, "template": tpl}


@router.patch("/api/admin/document-templates/{template_id}",
              dependencies=[Depends(require_admin)])
async def admin_patch_template(template_id: str, patch: Dict[str, Any] = Body(...)):
    try:
        tpl = await tpl_repo.update_template(template_id, patch)
    except FileNotFoundError:
        raise HTTPException(404, "Template not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "template": tpl}


@router.delete("/api/admin/document-templates/{template_id}",
               dependencies=[Depends(require_admin)])
async def admin_delete_template(template_id: str):
    try:
        out = await tpl_repo.delete_template(template_id)
    except FileNotFoundError:
        raise HTTPException(404, "Template not found")
    return {"success": True, **out}


# ─────────────────────────────────────────────────────────────────────
# Manager: document generation
# ─────────────────────────────────────────────────────────────────────

@router.post("/api/invoices/{invoice_id}/contract",
             dependencies=[Depends(require_manager_or_admin)])
async def generate_contract_from_invoice(
    invoice_id: str,
    data: Optional[Dict[str, Any]] = Body(default=None),
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not invoice.get("customerId"):
        raise HTTPException(400, "Invoice has no customer linked")
    try:
        out = await pdf_engine.generate(
            doc_type="contract",
            customer_id=invoice["customerId"],
            invoice_id=invoice_id,
            language=(data or {}).get("language") or "en",
            template_id=(data or {}).get("template_id"),
            generated_by=user.get("id"),
            generated_by_email=user.get("email"),
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    return {"success": True, **out}


@router.post("/api/invoices/{invoice_id}/invoice-pdf",
             dependencies=[Depends(require_manager_or_admin)])
async def generate_invoice_pdf(
    invoice_id: str,
    data: Optional[Dict[str, Any]] = Body(default=None),
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not invoice.get("customerId"):
        raise HTTPException(400, "Invoice has no customer linked")
    try:
        out = await pdf_engine.generate(
            doc_type="invoice",
            customer_id=invoice["customerId"],
            invoice_id=invoice_id,
            language=(data or {}).get("language") or "en",
            template_id=(data or {}).get("template_id"),
            generated_by=user.get("id"),
            generated_by_email=user.get("email"),
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    return {"success": True, **out}


@router.post("/api/orders/{order_id}/acceptance-act",
             dependencies=[Depends(require_manager_or_admin)])
async def generate_acceptance_act(
    order_id: str,
    data: Optional[Dict[str, Any]] = Body(default=None),
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    if not order.get("customerId"):
        raise HTTPException(400, "Order has no customer linked")
    try:
        out = await pdf_engine.generate(
            doc_type="acceptance_act",
            customer_id=order["customerId"],
            order_id=order_id,
            language=(data or {}).get("language") or "en",
            template_id=(data or {}).get("template_id"),
            generated_by=user.get("id"),
            generated_by_email=user.get("email"),
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    return {"success": True, **out}


@router.get("/api/customers/{customer_id}/generated-documents",
            dependencies=[Depends(require_manager_or_admin)])
async def list_customer_generated(customer_id: str, type: Optional[str] = None):
    items = await pdf_engine.list_generated(customer_id, doc_type=type)
    return {"success": True, "items": items, "total": len(items)}
