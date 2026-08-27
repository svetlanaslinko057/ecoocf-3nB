"""Universal Contract Flow — REST surface (staff/admin + client)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import Response, HTMLResponse

from security import require_manager_or_admin, require_admin
from app.client.router import get_current_customer
from . import service as S
from . import constants as K

logger = logging.getLogger("eco.contract_flow")

# Staff/admin surface
staff = APIRouter(prefix="/api/waste/cflow", tags=["contract-flow"])
# Client surface
client = APIRouter(prefix="/api/client/cflow", tags=["contract-flow-client"])


def _actor(user: Dict[str, Any]) -> str:
    return user.get("email") or user.get("id") or "staff"


# ═══════════════════════ META ═══════════════════════
@staff.get("/meta")
async def meta():
    return {
        "statuses": K.STATUSES, "status_labels": K.STATUS_LABELS_UK,
        "payment_statuses": K.PAYMENT_STATUSES, "payment_status_labels": K.PAYMENT_STATUS_LABELS_UK,
        "required_profile_fields": list(K.REQUIRED_PROFILE_FIELDS),
        "optional_profile_fields": list(K.OPTIONAL_PROFILE_FIELDS),
        "profile_field_labels": K.PROFILE_FIELD_LABELS_UK,
        "variable_catalog": K.DEFAULT_VARIABLE_CATALOG,
    }


@staff.get("/settings")
async def get_settings(user=Depends(require_manager_or_admin)):
    return await S.get_settings()


@staff.put("/settings", dependencies=[Depends(require_admin)])
async def save_settings(body: Dict[str, Any] = Body(...)):
    return await S.save_settings(body)


@staff.post("/seed", dependencies=[Depends(require_admin)])
async def seed_defaults():
    from . import seed as _seed
    return await _seed.seed_if_empty()


# ═══════════════════════ CONTRACT TYPES ═══════════════════════
@staff.get("/types")
async def list_types(active: Optional[bool] = None, user=Depends(require_manager_or_admin)):
    return {"items": await S.list_types(active)}


@staff.post("/types", dependencies=[Depends(require_admin)])
async def create_type(body: Dict[str, Any] = Body(...), user=Depends(require_admin)):
    return await S.create_type(body, actor=_actor(user))


@staff.put("/types/{type_id}", dependencies=[Depends(require_admin)])
async def update_type(type_id: str, body: Dict[str, Any] = Body(...), user=Depends(require_admin)):
    return await S.update_type(type_id, body, actor=_actor(user))


@staff.delete("/types/{type_id}", dependencies=[Depends(require_admin)])
async def delete_type(type_id: str):
    await S.delete_type(type_id)
    return {"success": True}


# ═══════════════════════ TEMPLATE LIBRARY ═══════════════════════
@staff.get("/templates")
async def list_templates(type_id: Optional[str] = None, status: Optional[str] = None,
                         user=Depends(require_manager_or_admin)):
    return {"items": await S.list_templates(type_id, status)}


@staff.get("/templates/{template_id}")
async def get_template(template_id: str, user=Depends(require_manager_or_admin)):
    tpl = await S.get_template(template_id)
    if not tpl:
        raise HTTPException(404, "Шаблон не знайдено")
    return tpl


@staff.post("/templates", dependencies=[Depends(require_admin)])
async def create_template(body: Dict[str, Any] = Body(...), user=Depends(require_admin)):
    return await S.create_template(body, actor=_actor(user))


@staff.post("/templates/upload", dependencies=[Depends(require_admin)])
async def upload_template_source(
    file: UploadFile = File(...),
    name: str = Query(""),
    contract_type_id: str = Query(""),
    user=Depends(require_admin),
):
    """Upload a DOCX/PDF/HTML source. HTML content is stored inline; DOCX/PDF
    are stored as source files and can be bound to a type (rendered as static
    PDF or converted later)."""
    content = await file.read()
    ct = (file.content_type or "").lower()
    fname = file.filename or "template"
    fmt = "html"
    html = ""
    source_id = None
    if fname.lower().endswith((".html", ".htm")) or "html" in ct:
        fmt = "html"
        html = content.decode("utf-8", errors="ignore")
    elif fname.lower().endswith(".docx") or "word" in ct:
        fmt = "docx"
        saved = await S.save_file(content, fname, ct, purpose="template_source", owner=_actor(user))
        source_id = saved["id"]
        # best-effort text extraction so variables still work
        try:
            import io, zipfile, re as _re
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            text = _re.sub(r"<[^>]+>", "", xml)
            html = "<html><body style='font-family:DejaVu Sans,Arial;white-space:pre-wrap'>" + text + "</body></html>"
        except Exception:
            html = "<html><body>{{contract.number}}</body></html>"
    else:  # pdf / other → static
        fmt = "pdf"
        saved = await S.save_file(content, fname, ct, purpose="template_source", owner=_actor(user))
        source_id = saved["id"]
        html = "<html><body>Статичний шаблон (PDF). Змінні не підставляються.</body></html>"
    tpl = await S.create_template({
        "name": name or fname, "contract_type_id": contract_type_id or None,
        "format": fmt, "html": html, "source_file_id": source_id, "status": "draft",
    }, actor=_actor(user))
    return tpl


@staff.put("/templates/{template_id}", dependencies=[Depends(require_admin)])
async def update_template(template_id: str, body: Dict[str, Any] = Body(...), user=Depends(require_admin)):
    return await S.update_template(template_id, body, actor=_actor(user))


@staff.delete("/templates/{template_id}", dependencies=[Depends(require_admin)])
async def delete_template(template_id: str):
    await S.delete_template(template_id)
    return {"success": True}


# ═══════════════════════ LEGAL PROFILE ═══════════════════════
@staff.get("/legal-profile/{customer_id}")
async def staff_legal_profile(customer_id: str, user=Depends(require_manager_or_admin)):
    out = await S.legal_profile_for(customer_id)
    if out.get("error"):
        raise HTTPException(404, "Клієнта не знайдено")
    return out


@staff.put("/legal-profile/{customer_id}")
async def staff_update_legal_profile(customer_id: str, body: Dict[str, Any] = Body(...),
                                     user=Depends(require_manager_or_admin)):
    try:
        return await S.update_legal_profile(customer_id, body, actor=_actor(user))
    except ValueError:
        raise HTTPException(404, "Клієнта не знайдено")


# ═══════════════════════ CONTRACTS (staff) ═══════════════════════
@staff.get("/contracts")
async def staff_list_contracts(customer_id: Optional[str] = None, status: Optional[str] = None,
                               user=Depends(require_manager_or_admin)):
    return {"items": await S.list_contracts(customer_id=customer_id, status=status)}


@staff.post("/contracts")
async def staff_create_contract(body: Dict[str, Any] = Body(...), user=Depends(require_manager_or_admin)):
    try:
        return await S.create_contract(body, actor=_actor(user))
    except ValueError as e:
        raise HTTPException(400, str(e))


@staff.get("/contracts/{contract_id}")
async def staff_get_contract(contract_id: str, user=Depends(require_manager_or_admin)):
    try:
        return await S.get_contract(contract_id)
    except ValueError:
        raise HTTPException(404, "Договір не знайдено")


@staff.patch("/contracts/{contract_id}")
async def staff_patch_contract(contract_id: str, body: Dict[str, Any] = Body(...),
                               user=Depends(require_manager_or_admin)):
    return await S.patch_contract(contract_id, body, actor=_actor(user))


@staff.post("/contracts/{contract_id}/regenerate")
async def staff_regenerate(contract_id: str, user=Depends(require_manager_or_admin)):
    return await S.regenerate(contract_id, actor=_actor(user), reason="Ручна регенерація")


@staff.post("/contracts/{contract_id}/send")
async def staff_send(contract_id: str, user=Depends(require_manager_or_admin)):
    return await S.send_for_review(contract_id, actor=_actor(user))


@staff.post("/contracts/{contract_id}/invoice")
async def staff_invoice(contract_id: str, user=Depends(require_manager_or_admin)):
    return await S.issue_invoice(contract_id, actor=_actor(user))


@staff.post("/contracts/{contract_id}/confirm-payment")
async def staff_confirm_payment(contract_id: str, body: Dict[str, Any] = Body(default={}),
                                user=Depends(require_manager_or_admin)):
    return await S.confirm_payment(contract_id, actor=_actor(user),
                                   reference=(body or {}).get("reference", ""),
                                   notes=(body or {}).get("notes", ""))


@staff.post("/contracts/{contract_id}/reject-payment")
async def staff_reject_payment(contract_id: str, body: Dict[str, Any] = Body(default={}),
                               user=Depends(require_manager_or_admin)):
    return await S.reject_payment(contract_id, actor=_actor(user), notes=(body or {}).get("notes", ""))


@staff.post("/contracts/{contract_id}/approve")
async def staff_approve(contract_id: str, user=Depends(require_manager_or_admin)):
    try:
        return await S.approve_contract(contract_id, actor=_actor(user))
    except ValueError as e:
        raise HTTPException(400, str(e))


@staff.get("/contracts/{contract_id}/pdf")
async def staff_pdf(contract_id: str, user=Depends(require_manager_or_admin)):
    return await _render_pdf(contract_id)


@staff.get("/contracts/{contract_id}/preview", response_class=HTMLResponse)
async def staff_preview(contract_id: str, user=Depends(require_manager_or_admin)):
    doc = await S.get_contract(contract_id)
    cur = (doc.get("versions") or [])[-1] if doc.get("versions") else doc.get("current")
    return HTMLResponse((cur or {}).get("html", ""))


@staff.get("/files/{file_id}")
async def staff_file(file_id: str, user=Depends(require_manager_or_admin)):
    f = await S.get_file(file_id)
    if not f:
        raise HTTPException(404, "Файл не знайдено")
    return Response(content=f["bytes"], media_type=f.get("content_type", "application/octet-stream"),
                    headers={"Content-Disposition": f"inline; filename=\"{f.get('filename','file')}\""})


# ═══════════════════════ CLIENT SURFACE ═══════════════════════
@client.get("/legal-profile")
async def client_legal_profile(customer=Depends(get_current_customer)):
    return await S.legal_profile_for(customer.get("id"))


@client.put("/legal-profile")
async def client_update_legal_profile(body: Dict[str, Any] = Body(...), customer=Depends(get_current_customer)):
    return await S.update_legal_profile(customer.get("id"), body, actor=f"client:{customer.get('id')}")


@client.get("/contracts")
async def client_list_contracts(customer=Depends(get_current_customer)):
    return {"items": await S.list_contracts(customer_id=customer.get("id"))}


@client.get("/contracts/{contract_id}")
async def client_get_contract(contract_id: str, customer=Depends(get_current_customer)):
    try:
        return await S.get_contract(contract_id, customer_id=customer.get("id"))
    except PermissionError:
        raise HTTPException(403, "Немає доступу")
    except ValueError:
        raise HTTPException(404, "Договір не знайдено")


@client.post("/contracts/{contract_id}/open")
async def client_open(contract_id: str, customer=Depends(get_current_customer)):
    try:
        return await S.mark_opened(contract_id, customer.get("id"))
    except PermissionError:
        raise HTTPException(403, "Немає доступу")
    except ValueError:
        raise HTTPException(404, "Договір не знайдено")


@client.post("/contracts/{contract_id}/accept")
async def client_accept(contract_id: str, request: Request, body: Dict[str, Any] = Body(default={}),
                        customer=Depends(get_current_customer)):
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    try:
        res = await S.accept_contract(contract_id, customer.get("id"), ip=ip, user_agent=ua,
                                      read_confirmed=bool((body or {}).get("read_confirmed")))
    except PermissionError:
        raise HTTPException(403, "Немає доступу")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if isinstance(res, dict) and res.get("error"):
        raise HTTPException(status_code=409, detail=res)
    return res


@client.post("/contracts/{contract_id}/proof")
async def client_upload_proof(contract_id: str, file: UploadFile = File(...),
                              customer=Depends(get_current_customer)):
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "Файл завеликий (максимум 15МБ)")
    saved = await S.save_file(content, file.filename or "proof", file.content_type or "",
                              purpose="payment_proof", owner=f"client:{customer.get('id')}")
    try:
        return await S.upload_proof(contract_id, customer.get("id"), saved["id"], saved["filename"],
                                    actor=f"client:{customer.get('id')}")
    except PermissionError:
        raise HTTPException(403, "Немає доступу")


@client.get("/contracts/{contract_id}/pdf")
async def client_pdf(contract_id: str, customer=Depends(get_current_customer)):
    doc = await S.get_contract(contract_id, customer_id=customer.get("id"))  # ownership check
    return await _render_pdf(contract_id)


@client.get("/files/{file_id}")
async def client_file(file_id: str, customer=Depends(get_current_customer)):
    f = await S.get_file(file_id)
    if not f:
        raise HTTPException(404, "Файл не знайдено")
    return Response(content=f["bytes"], media_type=f.get("content_type", "application/octet-stream"),
                    headers={"Content-Disposition": f"inline; filename=\"{f.get('filename','file')}\""})


# ═══════════════════════ helpers ═══════════════════════
async def _render_pdf(contract_id: str) -> Response:
    doc = await S.get_contract(contract_id)
    versions = doc.get("versions") or []
    cur = versions[-1] if versions else doc.get("current") or {}
    html = cur.get("html", "")
    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename=\"contract-{doc.get('number','')}.pdf\""})
    except Exception as e:
        logger.warning("[cflow] pdf render failed: %s", e)
        return HTMLResponse(html)
