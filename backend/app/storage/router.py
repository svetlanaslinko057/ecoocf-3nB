"""Wave 5B-v2: File upload / download / management router.

Keeps the public URLs (``/api/storage/files/*``) byte-for-byte
compatible with the legacy Wave 5B implementation so the existing UI
(Files Manager, AttachmentsPanel, PhotoPreview, etc.) keeps working
without changes.

New capabilities surfaced here:
  * ``photo_stage`` form field on upload (Pickup workflow enum)
  * ``versions`` endpoint per (entity_type, entity_id)
  * uploads always create new immutable file versions — the previous
    active version, if any, is auto-marked ``replaced`` by the
    FileRepository.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

from app.storage import ALLOWED_MIMES, FILE_COLLECTION, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, StoredFile, storage
from app.storage.providers import get_storage_provider
from app.storage.providers.base import guess_mime
from app.storage.files_repo import FileRepository
from app.storage.photo_workflow import normalize_stage, checklist, PHOTO_STAGES
from app.storage.lifecycle import LifecycleRepository
from app.core.db_runtime import get_db
from app.waste import service as S  # type: ignore

try:
    from security import require_user, require_admin  # type: ignore
except Exception:  # pragma: no cover
    require_user = require_admin = lambda: None  # type: ignore

try:
    from app.services.staff_acl import staff_can_see_customer  # type: ignore
except Exception:  # pragma: no cover
    staff_can_see_customer = None  # type: ignore

router = APIRouter(prefix="/api/storage/files", tags=["files"])


async def _assert_customer_upload_access(entity_type: Optional[str], entity_id: Optional[str],
                                         user: Dict[str, Any]) -> None:
    """Enforce customer-ownership on customer-scoped uploads.

    A manager may only attach files to their OWN clients; admin / team_lead may
    attach to any. Mirrors the RBAC used by the Customer 360 GET / delete
    endpoints so uploads cannot bypass ownership. No-op for non-customer
    entities (contracts / pickups / invoices keep their own guards)."""
    if entity_type != "customer" or not entity_id:
        return
    if staff_can_see_customer is None:
        return
    db = get_db()
    customer = await db.customers.find_one({"id": entity_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Клієнта не знайдено")
    if not staff_can_see_customer(user, customer):
        raise HTTPException(403, "Немає доступу до цього клієнта")



def _gen_id(prefix: str = "f") -> str:
    return S.gen_id(prefix)


async def _autolink(db, rec: Dict[str, Any]) -> None:
    """Mirror the file URL onto the linked entity (legacy contract).

    Contract/Act get ``file_id`` set to the inline-view URL of the new
    version; Pickup gets the photo pushed to ``photos[]`` (only for image
    mimes) and ``photo_url`` updated.
    """
    fid = rec["id"]
    file_url = rec.get("url")
    if not file_url:
        return
    if rec.get("contract_id"):
        await db[S.C_CONTRACTS].update_one({"id": rec["contract_id"]}, {"$set": {"file_id": file_url, "updated_at": S.now_iso()}})
    if rec.get("act_id"):
        await db[S.C_ACTS].update_one({"id": rec["act_id"]}, {"$set": {"file_id": file_url, "updated_at": S.now_iso()}})
    if rec.get("pickup_id"):
        is_photo = (rec.get("mime") or "").startswith("image/")
        if is_photo:
            entry = {
                "id": fid, "url": file_url, "filename": rec.get("filename"),
                "at": rec.get("created_at"), "stage": rec.get("photo_stage"),
                "kind": rec.get("purpose") or "photo",
            }
            await db[S.C_PICKUPS].update_one({"id": rec["pickup_id"]}, {"$push": {"photos": entry}, "$set": {"updated_at": S.now_iso(), "photo_url": file_url}})


def _decorate(rec: Dict[str, Any]) -> Dict[str, Any]:
    rec = {k: v for k, v in rec.items() if k != "_id"}
    fid = rec.get("id")
    rec["url"] = f"/api/storage/files/{fid}/view"
    rec["download_url"] = f"/api/storage/files/{fid}/download"
    return rec


# ── Customer document hardening (Customer 360 acts / reports) ───────────────
_CUSTOMER_DOC_PURPOSES = {"act", "ecologist_report", "document"}
_CUSTOMER_DOC_MAX_BYTES = 25 * 1024 * 1024  # 25 MB cap for manual customer docs
# Executable / script extensions that must never appear anywhere in the name
# (defends against double-extension tricks like ``report.pdf.exe``).
_DANGEROUS_EXTS = {
    "exe", "bat", "cmd", "com", "cpl", "js", "jse", "jar", "msi", "scr",
    "sh", "bash", "ps1", "vbs", "vbe", "wsf", "wsh", "dll", "app", "apk",
    "php", "phtml", "py", "pyc", "html", "htm", "svg",
}


def _reject_double_extension(filename: str) -> None:
    """Raise 400 if the filename contains a dangerous (non-final) extension
    segment — a classic double-extension bypass, e.g. ``invoice.pdf.exe`` or
    ``act.exe.pdf``."""
    parts = [p for p in (filename or "").split(".") if p != ""]
    if len(parts) < 3:
        return  # at most name + single extension → nothing to check
    for seg in parts[1:]:  # every extension-like segment after the base name
        if seg.strip().lower() in _DANGEROUS_EXTS:
            raise HTTPException(400, "Недопустиме подвійне розширення у назві файлу")


def _parse_iso_date(v: Any) -> Optional[str]:
    """Return the ISO date string if valid, else raise 400."""
    if v in (None, ""):
        return None
    from datetime import datetime as _dt
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            _dt.strptime(s[: len(fmt) + 2] if "T" in fmt else s[:10], fmt)
            return s
        except Exception:
            continue
    # last resort: fromisoformat
    try:
        _dt.fromisoformat(s.replace("Z", "+00:00"))
        return s
    except Exception:
        raise HTTPException(400, f"Некоректна дата: {v}")


def _validate_customer_doc_meta(meta_obj: Dict[str, Any]) -> None:
    """Validate metadata dates for a customer act/report upload."""
    if not isinstance(meta_obj, dict):
        return
    df = _parse_iso_date(meta_obj.get("doc_date"))
    pf = _parse_iso_date(meta_obj.get("period_from"))
    pt = _parse_iso_date(meta_obj.get("period_to"))
    if pf and pt and pf[:10] > pt[:10]:
        raise HTTPException(400, "Період: дата початку не може бути пізніше за дату завершення")
    _ = df  # doc_date validity already enforced by _parse_iso_date


@router.post("", dependencies=[Depends(require_user)])
async def upload_file(
    file: UploadFile = File(...),
    purpose: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    company_id: Optional[str] = Form(None),
    object_id: Optional[str] = Form(None),
    contract_id: Optional[str] = Form(None),
    pickup_id: Optional[str] = Form(None),
    act_id: Optional[str] = Form(None),
    invoice_id: Optional[str] = Form(None),
    entity_type: Optional[str] = Form(None),
    entity_id: Optional[str] = Form(None),
    meta: Optional[str] = Form(None),
    photo_stage: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(require_user),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Файл порожній")
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, f"Файл перевищує максимум {MAX_FILE_SIZE_MB} МБ")

    # ── Customer document hardening: parse meta up-front + extra validation ──
    is_customer_doc = (entity_type == "customer") and ((purpose or "") in _CUSTOMER_DOC_PURPOSES)
    meta_obj: Dict[str, Any] = {}
    if meta:
        try:
            import json as _json
            parsed = _json.loads(meta) if isinstance(meta, str) else dict(meta)
            if isinstance(parsed, dict):
                meta_obj = parsed
        except Exception:
            raise HTTPException(400, "Некоректні метадані (очікується JSON)")
    if is_customer_doc:
        if len(data) > _CUSTOMER_DOC_MAX_BYTES:
            raise HTTPException(413, "Файл перевищує максимум 25 МБ")
        _reject_double_extension(file.filename or "")
        _validate_customer_doc_meta(meta_obj)

    # RBAC: customer-scoped uploads must respect ownership (manager → own only).
    await _assert_customer_upload_access(entity_type, entity_id, user)

    stage = normalize_stage(photo_stage) if photo_stage else None
    if photo_stage and not stage:
        raise HTTPException(400, f"Невідома стадія фото. Допустимі: {', '.join(PHOTO_STAGES)}")
    try:
        # Persist upload to the configured durable object store (Emergent
        # object storage by default) — never the app pod's local disk.
        eff_mime = guess_mime(file.filename or "file", file.content_type)
        if eff_mime not in ALLOWED_MIMES:
            raise ValueError(f"Тип «{eff_mime}» не підтримується")
        if not data:
            raise ValueError("Файл порожній")
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл перевищує максимум {MAX_FILE_SIZE_MB} МБ")
        _obj = get_storage_provider().put_bytes(
            data, filename=file.filename or "file", mime=eff_mime, prefix="uploads",
        )
        stored = StoredFile.from_stored(id=uuid.uuid4().hex, obj=_obj)
    except ValueError as e:
        raise HTTPException(400, str(e))
    repo = FileRepository(get_db())
    rec = await repo.add_file(
        id=stored.id, stored=stored, owner=user.get("email") or user.get("id"),
        purpose=purpose, title=title,
        company_id=company_id, object_id=object_id,
        contract_id=contract_id, pickup_id=pickup_id, act_id=act_id, invoice_id=invoice_id,
        entity_type=entity_type, entity_id=entity_id,
        photo_stage=stage, generated=False,
    )
    rec = _decorate(rec)
    # Optional metadata (e.g. ecologist-report period/type) — stored on the
    # file record and echoed back so tables can display it.
    if meta_obj:
        try:
            set_fields: Dict[str, Any] = {"meta": meta_obj}
            for k in ("period", "period_label", "report_type", "doc_type",
                      "doc_date", "period_from", "period_to", "contract_id",
                      "object_id", "act_number"):
                if meta_obj.get(k) not in (None, ""):
                    set_fields[k] = meta_obj[k]
            await get_db()[FILE_COLLECTION].update_one({"id": rec["id"]}, {"$set": set_fields})
            rec.update(set_fields)
        except Exception:
            pass
    await _autolink(get_db(), rec)
    return {"success": True, "file": rec}


@router.get("", dependencies=[Depends(require_user)])
async def list_files(
    company_id: Optional[str] = None,
    contract_id: Optional[str] = None,
    pickup_id: Optional[str] = None,
    act_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    purpose: Optional[str] = None,
    latest_only: bool = Query(default=False),
    include_replaced: bool = Query(default=False),
    limit: int = Query(200, ge=1, le=1000),
):
    db = get_db()
    query: Dict[str, Any] = {}
    if not include_replaced:
        query["status"] = {"$ne": "deleted"}
        if latest_only:
            query["status"] = "active"
    for k, v in {
        "company_id": company_id, "contract_id": contract_id,
        "pickup_id": pickup_id, "act_id": act_id, "invoice_id": invoice_id,
        "entity_type": entity_type, "entity_id": entity_id, "purpose": purpose,
    }.items():
        if v: query[k] = v
    rows = await db[FILE_COLLECTION].find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    rows = [_decorate(r) for r in rows]
    return {"success": True, "items": rows, "count": len(rows)}


@router.get("/versions", dependencies=[Depends(require_user)])
async def list_versions(entity_type: str, entity_id: str, purpose: Optional[str] = None):
    repo = FileRepository(get_db())
    versions = await repo.versions(entity_type, entity_id, purpose=purpose)
    items = [_decorate(v) for v in versions]
    items.sort(key=lambda r: int(r.get("version") or 0), reverse=True)
    latest = next((it for it in items if it.get("status") == "active"), items[0] if items else None)
    return {"success": True, "entity_type": entity_type, "entity_id": entity_id, "items": items, "latest": latest, "count": len(items)}


@router.get("/{file_id}", dependencies=[Depends(require_user)])
async def file_meta(file_id: str):
    db = get_db()
    rec = await db[FILE_COLLECTION].find_one({"id": file_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Файл не знайдено")
    return {"success": True, "file": _decorate(rec)}


async def _stream_response(file_id: str, *, attachment: bool):
    db = get_db()
    rec = await db[FILE_COLLECTION].find_one({"id": file_id})
    if not rec:
        raise HTTPException(404, "Файл не знайдено")
    if rec.get("status") == "deleted":
        raise HTTPException(410, "Файл видалено")
    storage_key = rec.get("storage_key") or rec.get("storageKey") or rec.get("path")
    try:
        data, _ = storage.read(storage_key)
    except FileNotFoundError:
        raise HTTPException(410, "Файл був видалений зі сховища")
    fname = rec.get("filename") or f"{file_id}"
    disp = "attachment" if attachment else "inline"
    headers = {
        "Content-Disposition": f'{disp}; filename="{fname}"',
        "Content-Length": str(len(data)),
    }
    return Response(content=data, media_type=rec.get("mime") or rec.get("mimeType") or "application/octet-stream", headers=headers)


@router.get("/{file_id}/download", dependencies=[Depends(require_user)])
async def file_download(file_id: str):
    return await _stream_response(file_id, attachment=True)


@router.get("/{file_id}/view", dependencies=[Depends(require_user)])
async def file_view(file_id: str):
    return await _stream_response(file_id, attachment=False)


@router.delete("/{file_id}", dependencies=[Depends(require_admin)])
async def file_delete(file_id: str, user: Dict[str, Any] = Depends(require_admin)):
    db = get_db()
    rec = await db[FILE_COLLECTION].find_one({"id": file_id})
    if not rec:
        raise HTTPException(404, "Файл не знайдено")
    # Hard-delete binary; keep audit row in files collection as soft-delete
    # for traceability (status='deleted'). This preserves version history
    # while freeing storage.
    try:
        storage_key = rec.get("storage_key") or rec.get("storageKey") or rec.get("path")
        if storage_key:
            storage.delete(storage_key)
    except Exception:
        pass
    repo = FileRepository(db)
    await repo.soft_delete(file_id, by=(user or {}).get("email") or (user or {}).get("id"))
    return {"success": True}


# ---- Pickup photo checklist ---------------------------------------------
pickup_router = APIRouter(prefix="/api/waste/pickups", tags=["pickups"])


@pickup_router.get("/{pickup_id}/photo-checklist", dependencies=[Depends(require_user)])
async def pickup_photo_checklist(pickup_id: str):
    return {"success": True, "pickup_id": pickup_id, **await checklist(get_db(), pickup_id)}


__all__ = ["router", "pickup_router"]
