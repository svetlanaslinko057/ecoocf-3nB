"""
BIBI Cars - PDF Engine (Sprint 3)
=================================

Mid-layer service that turns:
    (document_type, customer_id, invoice_id?, order_id?)
to:
    a versioned, persisted PDF stored in the customer's File Manager.

Flow:
    1. Load the right template (DB or default).
    2. Build a render context: customer + manager + company + invoice + order +
       vehicle + calculation + version + generated_at.
    3. Jinja2-render the HTML.
    4. WeasyPrint-render the PDF bytes.
    5. Save bytes to the customer's appropriate folder (Contracts / Delivery /
       Invoices) via app.services.file_manager.upload_file.
    6. Append a row to ``generated_documents`` for traceability.
    7. Return both the file_doc (File Manager metadata) and the gen-doc.

Versioning rule: Each call to ``generate()`` for the same (entity_id, type)
increments ``version``. v1, v2, v3... live as separate files in File Manager.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from jinja2 import Environment, BaseLoader, StrictUndefined, Undefined

from app.core.db_runtime import get_db
from app.repositories.document_templates import (
    get_default_template,
    get_template,
)
from app.services import file_manager as fm

logger = logging.getLogger("bibi.pdf_engine")

GEN_COLLECTION = "generated_documents"

# Map a document type to the file-manager folder name where it lives.
TYPE_TO_FOLDER: Dict[str, str] = {
    "contract":             "Contracts",
    "acceptance_act":       "Contracts",
    "delivery_certificate": "Delivery",
    "invoice":              "Invoices",
}

# Forgiving Undefined - missing variables render as empty strings
class _SilentUndefined(Undefined):
    def __str__(self): return ""
    def __getattr__(self, name): return _SilentUndefined()
    def __getitem__(self, key): return _SilentUndefined()
    def __bool__(self): return False

_jinja_env = Environment(
    loader=BaseLoader(),
    undefined=_SilentUndefined,
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    return f"doc_{uuid.uuid4().hex[:12]}"


async def _resolve_customer(db, customer_id: str) -> Dict[str, Any]:
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    return cust or {"id": customer_id}


async def _resolve_manager(db, manager_id: Optional[str], manager_email: Optional[str]) -> Dict[str, Any]:
    if not manager_id and not manager_email:
        return {}
    q = {"$or": [{"id": manager_id or "__none__"}, {"email": manager_email or "__none__"}]}
    mgr = await db.staff.find_one(q, {"_id": 0, "password": 0, "passwordHash": 0})
    return mgr or {"id": manager_id, "email": manager_email, "name": manager_email}


def _default_company() -> Dict[str, Any]:
    return {
        "name":    "BIBI CARS LTD",
        "address": "Sofia, Bulgaria",
        "email":   "info@bibi.cars",
        "vat":     "",
    }


async def _resolve_company(db) -> Dict[str, Any]:
    try:
        cfg = await db.integration_configs.find_one({"provider": "company_branding"}, {"_id": 0})
        if cfg and isinstance(cfg.get("data"), dict):
            return {**_default_company(), **cfg["data"]}
    except Exception:
        pass
    return _default_company()


async def _next_version(customer_id: str, doc_type: str, entity_id: Optional[str]) -> int:
    db = get_db()
    q: Dict[str, Any] = {
        "customer_id": customer_id,
        "type":        doc_type,
    }
    if entity_id:
        q["entity_id"] = entity_id
    latest = await db[GEN_COLLECTION].find_one(q, {"_id": 0, "version": 1}, sort=[("version", -1)])
    return (latest.get("version") if latest else 0) + 1


async def generate(
    *,
    doc_type: str,
    customer_id: str,
    template_id: Optional[str] = None,
    language: str = "en",
    invoice_id: Optional[str] = None,
    order_id: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    generated_by: Optional[str] = None,
    generated_by_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Render + persist a PDF document. See module docstring for the flow."""
    db = get_db()

    # ---- 1. Pick template ------------------------------------------------
    tpl: Optional[Dict[str, Any]] = None
    if template_id:
        tpl = await get_template(template_id)
    if not tpl:
        tpl = await get_default_template(doc_type, language=language)
    if not tpl:
        raise ValueError(f"No template available for type={doc_type}, language={language}")

    # ---- 2. Build render context -----------------------------------------
    customer = await _resolve_customer(db, customer_id)
    invoice  = await db.invoices.find_one({"id": invoice_id}, {"_id": 0}) if invoice_id else None
    order    = await db.orders.find_one({"id": order_id},   {"_id": 0}) if order_id   else None
    if not order and invoice:
        order = await db.orders.find_one({"invoiceId": invoice.get("id")}, {"_id": 0})
    if not invoice and order and order.get("invoiceId"):
        invoice = await db.invoices.find_one({"id": order["invoiceId"]}, {"_id": 0})
    manager_id    = (invoice or {}).get("managerId") or (order or {}).get("managerId")
    manager_email = (invoice or {}).get("managerEmail") or (order or {}).get("managerEmail")
    manager = await _resolve_manager(db, manager_id, manager_email)
    company = await _resolve_company(db)

    entity_id = invoice_id or order_id
    version   = await _next_version(customer_id, doc_type, entity_id)

    # Normalise line-item collections so templates can safely iterate them.
    # NOTE: Jinja resolves ``invoice['items']`` on a dict that lacks the key
    # by falling back to ``dict.items`` (the *method*), which then blows up a
    # ``{% for %}`` loop with "'builtin_function_or_method' object is not
    # iterable". Guaranteeing a real list under ``items`` keeps every template
    # robust regardless of how the source invoice/order was created.
    invoice_ctx = {**(invoice or {})}
    invoice_ctx["items"] = invoice_ctx.get("items") or []
    order_ctx = {**(order or {})}
    order_ctx["items"] = order_ctx.get("items") or []

    ctx: Dict[str, Any] = {
        "customer":     customer,
        "manager":      manager,
        "company":      company,
        "invoice":      invoice_ctx,
        "order":        order_ctx,
        "generated_at": _now_iso(),
        "version":      version,
    }
    if extra_context:
        # Allow callers to override resolved customer fields (e.g. inject
        # national_id / address_full from a contract's buyer party).
        co = extra_context.pop("customer_override", None)
        if co:
            ctx["customer"] = {**(ctx.get("customer") or {}), **co}
        ctx.update(extra_context)

    # ---- 3. Render HTML --------------------------------------------------
    try:
        html_str = _jinja_env.from_string(tpl["html"]).render(**ctx)
    except Exception as exc:
        logger.exception("[pdf_engine] template render failed: %s", exc)
        raise ValueError(f"template render failed: {exc}")

    # ---- 4. Render PDF via WeasyPrint ------------------------------------
    try:
        from weasyprint import HTML  # local import keeps boot fast
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as exc:
        logger.exception("[pdf_engine] weasyprint failed: %s", exc)
        raise RuntimeError(f"PDF rendering failed: {exc}")

    # ---- 5. Ensure folder + upload --------------------------------------
    folder_name = TYPE_TO_FOLDER.get(doc_type, "Other")
    # Map English folder names → slug for the canonical client_folders lookup
    name_to_slug = {
        "Contracts": "contracts",
        "Delivery":  "delivery",
        "Invoices":  "invoices",
        "Acts":      "acts",
    }
    target_slug = name_to_slug.get(folder_name)
    await fm.ensure_system_folders(customer_id)
    # Lookup by slug first (canonical), then by name (legacy).
    folder = None
    if target_slug:
        folder = await db.client_folders.find_one(
            {"customer_id": customer_id, "slug": target_slug, "is_system": True},
            {"_id": 0},
        )
    if not folder:
        folder = await db.client_folders.find_one(
            {"customer_id": customer_id, "name": folder_name, "is_system": True},
            {"_id": 0},
        )
    if not folder:
        raise RuntimeError(f"System folder '{folder_name}' missing for customer")

    base = doc_type.replace("_", " ").title().replace(" ", "_")
    safe_entity = (entity_id or "")[-8:]
    filename = f"{base}_{safe_entity}_v{version}.pdf" if entity_id else f"{base}_v{version}.pdf"

    file_doc = await fm.upload_file(
        customer_id=customer_id,
        folder_id=folder["id"],
        original_name=filename,
        content_type="application/pdf",
        data=pdf_bytes,
        comment=f"Auto-generated {doc_type} v{version}",
        uploaded_by=generated_by,
        uploaded_by_email=generated_by_email,
    )

    # ---- 6. Append audit row --------------------------------------------
    gen_doc = {
        "id":             _gen_id(),
        "type":           doc_type,
        "customer_id":    customer_id,
        "entity_id":      entity_id,
        "invoice_id":     invoice_id,
        "order_id":       order_id,
        "template_id":    tpl["id"],
        "template_name":  tpl["name"],
        "language":       tpl.get("language", "en"),
        "version":        version,
        "file_id":        file_doc["id"],
        "storage_key":    file_doc["storage_key"],
        "folder_id":      folder["id"],
        "folder_name":    folder_name,
        "size":           file_doc["size"],
        "signature_status": "unsigned",  # placeholder for future e-sign
        "generated_at":   _now_iso(),
        "generated_by":   generated_by,
        "generated_by_email": generated_by_email,
    }
    await db[GEN_COLLECTION].insert_one(gen_doc)
    gen_doc.pop("_id", None)

    # Sprint 4 / Customer Timeline — surface generated documents in Customer360.
    try:
        from app.services import customer_timeline
        await customer_timeline.record_event(
            customer_id=customer_id,
            kind="document_generated",
            title=f"Document generated: {doc_type.replace('_', ' ')} v{version}",
            ref={"collection": GEN_COLLECTION, "id": gen_doc["id"]},
            actor={"id": generated_by, "email": generated_by_email},
            meta={
                "doc_type": doc_type,
                "language": tpl.get("language", "en"),
                "version": version,
                "file_id": file_doc["id"],
                "entity_id": entity_id,
            },
        )
    except Exception:
        logger.exception("[pdf_engine] timeline emit failed (non-fatal)")

    # Mini Sprint / Contracts Final — every generated contract gets a
    # lifecycle row in contracts_v2 so the manager can later move it
    # through Draft → Sent → Signed → Archived. Idempotent: subsequent
    # regenerations re-use the same row keyed by document_id.
    if doc_type == "contract":
        try:
            from app.services import contract_lifecycle
            await contract_lifecycle.create_from_generation(
                customer_id=customer_id,
                invoice_id=invoice_id,
                deal_id=(await db.invoices.find_one({"id": invoice_id}, {"_id": 0, "dealId": 1}) or {}).get("dealId") if invoice_id else None,
                file_id=file_doc["id"],
                document_id=gen_doc["id"],
                template_id=tpl["id"],
                language=tpl.get("language", "en"),
                title=f"{tpl.get('name') or 'Contract'} v{version}",
                version=version,
                generated_by=generated_by,
                generated_by_email=generated_by_email,
            )
        except Exception:
            logger.exception("[contract_lifecycle] auto-row creation failed (non-fatal)")

    return {"file": file_doc, "document": gen_doc}


async def list_generated(customer_id: str, *, doc_type: Optional[str] = None) -> list:
    db = get_db()
    q: Dict[str, Any] = {"customer_id": customer_id}
    if doc_type: q["type"] = doc_type
    cur = db[GEN_COLLECTION].find(q, {"_id": 0}).sort([("generated_at", -1)])
    return await cur.to_list(length=200)
