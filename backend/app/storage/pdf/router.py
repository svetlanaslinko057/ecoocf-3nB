"""Wave 5B-v2 PDF router.

Keeps the legacy URL surface (``POST /api/pdf/contract|act|pickup|invoice/{id}``)
intact, but now:

  * renders HTML from Jinja2 templates under ``templates/`` (not from
    hardcoded Python strings),
  * goes through the ``PdfRenderer`` abstraction (currently WeasyPrint),
  * persists each generation as a **new immutable version** via
    FileRepository (previous active version is auto-marked ``replaced``),
  * stamps the document lifecycle: any successful generation moves the
    document state to ``generated``.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.storage import storage
from app.storage.files_repo import FileRepository
from app.storage.lifecycle import LifecycleRepository
from app.storage.pdf.renderer import render_pdf
from app.core.db_runtime import get_db
from app.waste import service as S

try:
    from security import require_manager_or_admin  # type: ignore
except Exception:  # pragma: no cover
    require_manager_or_admin = lambda: None  # type: ignore

router = APIRouter(prefix="/api/pdf", tags=["pdf"])

BRAND = {
    "name": "ECO Utilization Operator",
    "edrpou": "44990001",
    "address": "Київ, вул. Екологічна 1",
    "email": "office@bibi.cars",
}

METHOD_LABELS = {
    "incineration": "Спалювання",
    "neutralization": "Хімічна нейтралізація",
    "recycling": "Переробка",
    "sorting": "Сортування / розбір",
    "burial": "Захоронення",
    "sterilization": "Стерилізація автоклавом",
    "composting": "Компостування",
}

STATUS_LABELS = {
    "pending": "Очікує оплати",
    "paid": "Оплачено",
    "overdue": "Прострочено",
    "cancelled": "Скасовано",
}


def _items_total(items):
    total = 0.0
    for it in items or []:
        try:
            total += float(it.get("qty") or it.get("quantity") or 0)
        except Exception:
            pass
    return total


async def _save_and_link(
    *,
    pdf_bytes: bytes,
    name: str,
    owner: str,
    entity_type: str,
    entity_id: str,
    **links: Any,
) -> Dict[str, Any]:
    """Persist a generated PDF as a new file version + lifecycle bump."""
    stored = storage.write_bytes(pdf_bytes, name, "application/pdf", generated=True)
    db = get_db()
    repo = FileRepository(db)
    file_id = uuid.uuid4().hex
    # Use repository-issued id (file_id) instead of the one from the storage layer.
    stored.id = file_id
    rec = await repo.add_file(
        id=file_id, stored=stored, owner=owner, purpose="pdf", title=name,
        entity_type=entity_type, entity_id=entity_id, generated=True,
        **links,
    )
    rec["url"] = f"/api/storage/files/{file_id}/view"
    rec["download_url"] = f"/api/storage/files/{file_id}/download"
    # Bump lifecycle: any successful PDF generation lands the document on
    # ``generated`` (idempotent if it's already past that state).
    try:
        lc = LifecycleRepository(db)
        cur = await lc.get(entity_type, entity_id)
        if (cur.get("status") or "draft") in ("draft",):
            await lc.mark(entity_type, entity_id, status="generated", by=owner, file_id=file_id, note="PDF generated")
        else:
            # Keep history of regenerations even if state already further along.
            await lc.mark(entity_type, entity_id, status=cur.get("status"), by=owner, file_id=file_id, note="PDF regenerated")
    except Exception:
        pass
    return rec


# --- Contract -------------------------------------------------------------
@router.post("/contract/{contract_id}", dependencies=[Depends(require_manager_or_admin)])
async def generate_contract_pdf(contract_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await db[S.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Договір не знайдено")
    co = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) or {}
    pdf_bytes = render_pdf("contract.html", {"brand": BRAND, "contract": doc, "company": co, "items_total": _items_total(doc.get("items"))})
    name = f"contract-{doc.get('number') or contract_id}.pdf"
    rec = await _save_and_link(
        pdf_bytes=pdf_bytes, name=name, owner=user.get("email") or user.get("id"),
        entity_type="contract", entity_id=contract_id,
        contract_id=contract_id, company_id=doc.get("company_id"),
    )
    await db[S.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"file_id": rec["url"], "updated_at": S.now_iso()}})
    return {"success": True, "file": rec}


# --- Act -------------------------------------------------------------------
@router.post("/act/{act_id}", dependencies=[Depends(require_manager_or_admin)])
async def generate_act_pdf(act_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await db[S.C_ACTS].find_one({"id": act_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Акт не знайдено")
    co = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) or {}
    method_label = METHOD_LABELS.get(doc.get("utilization_method"), doc.get("utilization_method") or "—")
    pdf_bytes = render_pdf("act.html", {"brand": BRAND, "act": doc, "company": co, "method_label": method_label, "items_total": _items_total(doc.get("items"))})
    name = f"act-{doc.get('number') or act_id}.pdf"
    rec = await _save_and_link(
        pdf_bytes=pdf_bytes, name=name, owner=user.get("email") or user.get("id"),
        entity_type="act", entity_id=act_id,
        act_id=act_id, company_id=doc.get("company_id"),
    )
    await db[S.C_ACTS].update_one({"id": act_id}, {"$set": {"file_id": rec["url"], "updated_at": S.now_iso()}})
    return {"success": True, "file": rec}


# --- Pickup ---------------------------------------------------------------
@router.post("/pickup/{pickup_id}", dependencies=[Depends(require_manager_or_admin)])
async def generate_pickup_pdf(pickup_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await db[S.C_PICKUPS].find_one({"id": pickup_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Вивіз не знайдено")
    co = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) or {}
    obj = await db[S.C_OBJECTS].find_one({"id": doc.get("object_id")}, {"_id": 0}) if doc.get("object_id") else None
    pdf_bytes = render_pdf("pickup_sheet.html", {"brand": BRAND, "pickup": doc, "company": co, "object": obj or {}, "driver": doc.get("driver") or {}, "items_total": _items_total(doc.get("items"))})
    name = f"pickup-{doc.get('number') or pickup_id}.pdf"
    rec = await _save_and_link(
        pdf_bytes=pdf_bytes, name=name, owner=user.get("email") or user.get("id"),
        entity_type="pickup", entity_id=pickup_id,
        pickup_id=pickup_id, company_id=doc.get("company_id"),
    )
    await db[S.C_PICKUPS].update_one({"id": pickup_id}, {"$set": {"sheet_file_id": rec["url"], "updated_at": S.now_iso()}})
    return {"success": True, "file": rec}


# --- Invoice --------------------------------------------------------------
@router.post("/invoice/{invoice_id}", dependencies=[Depends(require_manager_or_admin)])
async def generate_invoice_pdf(invoice_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Рахунок не знайдено")
    cid = doc.get("customerId") or doc.get("customer_id")
    cust = None
    if cid:
        cust = await db.customers.find_one({"$or": [{"customerId": cid}, {"id": cid}]}, {"_id": 0})
    co = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) if doc.get("company_id") else None
    party = {
        "name":    (co or {}).get("name") or (cust or {}).get("name") or (cust or {}).get("email") or cid or "—",
        "edrpou":  (co or {}).get("edrpou") or "—",
        "address": (co or {}).get("address") or (cust or {}).get("address") or "—",
        "email":   (co or {}).get("email") or (cust or {}).get("email") or "—",
        "phone":   (co or {}).get("phone") or (cust or {}).get("phone") or "—",
    }
    items = doc.get("items") or []
    cur = doc.get("currency") or "UAH"
    rows = []
    grand = 0.0
    for it in items:
        qty = float(it.get("qty") or it.get("quantity") or 1)
        price = float(it.get("price") or it.get("unit_price") or 0)
        total = float(it.get("total") if it.get("total") is not None else qty * price)
        grand += total
        rows.append({"name": it.get("name") or it.get("title") or it.get("description") or "—", "qty": qty, "unit": it.get("unit") or "", "price": price, "total": total})
    if not rows:
        amt = float(doc.get("amount") or doc.get("total") or 0)
        grand = amt
        rows.append({"name": doc.get("description") or doc.get("title") or "Послуги з утилізації відходів", "qty": 1, "unit": "шт", "price": amt, "total": amt})
    status_label = STATUS_LABELS.get((doc.get("status") or "pending"), doc.get("status") or "—")
    pdf_bytes = render_pdf("invoice.html", {"brand": BRAND, "invoice": doc, "party": party, "rows": rows, "grand_total": grand, "currency": cur, "status_label": status_label})
    name = f"invoice-{doc.get('number') or invoice_id}.pdf"
    rec = await _save_and_link(
        pdf_bytes=pdf_bytes, name=name, owner=user.get("email") or user.get("id"),
        entity_type="invoice", entity_id=invoice_id,
        invoice_id=invoice_id, company_id=doc.get("company_id"),
    )
    await db.invoices.update_one({"id": invoice_id}, {"$set": {"file_id": rec["url"], "updated_at": S.now_iso()}})
    return {"success": True, "file": rec}


__all__ = ["router"]
