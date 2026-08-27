"""
file_manager - HTTP surface for Sprint 2 Customer File Manager.

Endpoints (all prefixed by /api):

  GET    /customers/{customer_id}/folders                  - list folders
  POST   /customers/{customer_id}/folders                  - create custom folder (or subfolder via parent_id)
  PATCH  /folders/{folder_id}                              - rename folder / set description
  DELETE /folders/{folder_id}                              - delete empty non-system folder

  GET    /customers/{customer_id}/files                    - list files (filter by ?folder_id=)
  POST   /customers/{customer_id}/folders/{folder_id}/upload - upload (multipart)
  GET    /files/{file_id}                                  - file metadata
  PATCH  /files/{file_id}                                  - update comment/name
  PATCH  /files/{file_id}/move                             - move to another folder
  DELETE /files/{file_id}                                  - soft-delete
  GET    /files/{file_id}/download                         - serve binary inline

RBAC (Launch-Candidate v1 — UAT pass):
  * All endpoints require an authenticated staff user.
  * Manager role  → can only see/upload/modify customers where
                    ``customer.managerId == manager.id`` (mirror of
                    ``_can_user_see_customer`` from server.py).
  * Manager role  → can only DELETE files they themselves uploaded
                    (``file.uploaded_by == manager.id``).
  * admin / master_admin / owner / team_lead → unrestricted.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from security import require_user, require_manager_or_admin
from app.core.db_runtime import get_db
from app.services import file_manager as fm
from app.services.object_storage import get_storage
from app.services.upload_security import safe_content_disposition as _safe_disposition

logger = logging.getLogger("bibi.file_manager")

router = APIRouter(tags=["file-manager"])


# ─────────────────────────────────────────────────────────────────────
# RBAC helpers — replicate ``_can_user_see_customer`` from server.py
# without creating a circular import.
# ─────────────────────────────────────────────────────────────────────

_ELEVATED_ROLES = ("admin", "master_admin", "owner", "team_lead")


def _user_uid(user: Dict[str, Any]) -> Optional[str]:
    return (
        user.get("id")
        or user.get("managerId")
        or user.get("staff_id")
        or user.get("email")
    )


def _user_role(user: Dict[str, Any]) -> str:
    return (user.get("role") or "").lower()


def _can_see_customer(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    if _user_role(user) in _ELEVATED_ROLES:
        return True
    uid = _user_uid(user)
    return bool(uid) and customer.get("managerId") == uid


async def _load_customer_or_403(customer_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")
    if not _can_see_customer(user, cust):
        raise HTTPException(403, "Forbidden")
    return cust


async def _load_folder_with_acl(folder_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    folder = await db.client_folders.find_one({"id": folder_id}, {"_id": 0})
    if not folder:
        raise HTTPException(404, "Folder not found")
    cust = await db.customers.find_one({"id": folder.get("customer_id")}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")
    if not _can_see_customer(user, cust):
        raise HTTPException(403, "Forbidden")
    return folder


async def _load_file_with_acl(file_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    f = await db.client_files.find_one({"id": file_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")
    cust = await db.customers.find_one({"id": f.get("customer_id")}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")
    if not _can_see_customer(user, cust):
        raise HTTPException(403, "Forbidden")
    return f


# ─────────────────────────────────────────────────────────────────────
# Folders
# ─────────────────────────────────────────────────────────────────────

@router.get("/api/customers/{customer_id}/files/unread-count")
async def files_unread_count(customer_id: str, user: dict = Depends(require_user)):
    """Return the number of files uploaded to this customer SINCE the calling
    staff user last opened the Documents tab.

    Used by the Customer 360 → Overview header to show a small badge on the
    "Documents" tab. The "last visit" is stamped via
    ``POST /api/customers/{id}/files/mark-read``.

    Tracking is staff-only (admin/team_lead/manager) — customer-cabinet callers
    get ``unread=0`` so they never see this badge.
    """
    await _load_customer_or_403(customer_id, user)  # ACL gate
    db = get_db()
    uid = _user_uid(user)
    if not uid:
        return {"success": True, "unread": 0, "last_visit_at": None}

    visit = await db.customer_doc_visits.find_one(
        {"customer_id": customer_id, "user_id": uid},
        {"_id": 0, "last_visit_at": 1},
    )
    last_visit_at = (visit or {}).get("last_visit_at")

    q: Dict[str, Any] = {
        "customer_id": customer_id,
        "deleted": {"$ne": True},
    }
    if last_visit_at:
        q["created_at"] = {"$gt": last_visit_at}
    # Exclude files uploaded BY this user — they obviously know about them.
    q["uploaded_by"] = {"$ne": uid}

    count = await db.client_files.count_documents(q)
    return {
        "success":       True,
        "unread":        int(count),
        "last_visit_at": last_visit_at,
        "customer_id":   customer_id,
    }


@router.post("/api/customers/{customer_id}/files/mark-read")
async def files_mark_read(customer_id: str, user: dict = Depends(require_user)):
    """Stamp the calling user's "last documents-tab visit" timestamp.

    Called by the frontend as soon as the Documents tab mounts so the next
    page-load shows a clean badge.
    """
    await _load_customer_or_403(customer_id, user)  # ACL gate
    db = get_db()
    uid = _user_uid(user)
    if not uid:
        return {"success": True}

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await db.customer_doc_visits.update_one(
        {"customer_id": customer_id, "user_id": uid},
        {"$set": {
            "customer_id":   customer_id,
            "user_id":       uid,
            "user_email":    user.get("email"),
            "last_visit_at": now,
        }},
        upsert=True,
    )
    return {"success": True, "last_visit_at": now}


@router.get("/api/customers/{customer_id}/files/totals")
async def files_totals(customer_id: str, user: dict = Depends(require_user)):
    """Customer-wide file totals: ``total_files``, ``total_size_bytes``,
    ``folders_count``. Used by the Documents tab header and the Overview
    short-summary block. RBAC enforced.
    """
    await _load_customer_or_403(customer_id, user)
    db = get_db()
    folders_count = await db.client_folders.count_documents({"customer_id": customer_id})
    agg = await db.client_files.aggregate([
        {"$match": {"customer_id": customer_id, "deleted": {"$ne": True}}},
        {"$group": {
            "_id":         None,
            "total_files": {"$sum": 1},
            "total_size":  {"$sum": {"$ifNull": ["$size", 0]}},
        }},
    ]).to_list(length=1)
    row = agg[0] if agg else {}
    return {
        "success":          True,
        "customer_id":      customer_id,
        "total_files":      int(row.get("total_files") or 0),
        "total_size_bytes": int(row.get("total_size") or 0),
        "folders_count":    int(folders_count),
    }


@router.get("/api/customers/{customer_id}/folders")
async def list_folders(customer_id: str, user: dict = Depends(require_user)):
    """List all folders for a customer with aggregated metadata.

    Each folder gets: ``file_count``, ``total_size_bytes``, ``last_upload_at``.
    """
    await _load_customer_or_403(customer_id, user)
    folders = await fm.list_folders(customer_id)
    return {"success": True, "items": folders, "system_folders": fm.SYSTEM_FOLDERS}


@router.post("/api/customers/{customer_id}/folders")
async def create_folder(
    customer_id: str,
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_manager_or_admin),
):
    """Create a custom (non-system) folder under a customer.

    Body: ``{ name: str, parent_id?: str, description?: str }``
    """
    await _load_customer_or_403(customer_id, user)
    try:
        folder = await fm.create_folder(
            customer_id,
            name=(data.get("name") or "").strip(),
            parent_id=data.get("parent_id"),
            description=(data.get("description") or "").strip() or None,
            created_by=user.get("email") or user.get("id"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "folder": folder}


@router.patch("/api/folders/{folder_id}")
async def rename_folder(
    folder_id: str,
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_manager_or_admin),
):
    """Rename a custom folder and/or update its description.

    Body: ``{ name?: str, description?: str }``
    System folders cannot be renamed but their description CAN be updated.
    """
    await _load_folder_with_acl(folder_id, user)
    name = (data.get("name") or "").strip() if "name" in data else None
    description = data.get("description") if "description" in data else None
    if name is None and description is None:
        raise HTTPException(400, "nothing to update")
    try:
        out = await fm.update_folder(folder_id, name=name, description=description)
    except FileNotFoundError:
        raise HTTPException(404, "Folder not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "folder": out}


@router.delete("/api/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    cascade: bool = False,
    user: dict = Depends(require_manager_or_admin),
):
    """Delete a custom folder.

    Query params:
      * ``cascade=true`` — also delete every file inside (and nested subfolders).

    RBAC:
      * admin / team_lead / master_admin / owner → can delete any custom folder
        for any visible customer.
      * manager → can only delete custom folders **they created themselves**
        (folder.created_by == manager.id or manager.email).
    """
    folder = await _load_folder_with_acl(folder_id, user)
    role = _user_role(user)

    # Manager can only delete folders they themselves created.
    if role == "manager":
        uid = _user_uid(user)
        email = (user.get("email") or "").lower()
        creator = folder.get("created_by") or ""
        if uid != creator and email != (creator or "").lower():
            raise HTTPException(
                403,
                "Managers can only delete custom folders they created themselves",
            )

    try:
        out = await fm.delete_folder(folder_id, cascade=bool(cascade))
    except FileNotFoundError:
        raise HTTPException(404, "Folder not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, **out}


# ─────────────────────────────────────────────────────────────────────
# Files
# ─────────────────────────────────────────────────────────────────────

@router.get("/api/customers/{customer_id}/files")
async def list_customer_files(
    customer_id: str,
    folder_id: Optional[str] = None,
    user: dict = Depends(require_user),
):
    await _load_customer_or_403(customer_id, user)
    files = await fm.list_files(customer_id, folder_id=folder_id)
    return {"success": True, "items": files, "total": len(files)}


@router.post("/api/customers/{customer_id}/folders/{folder_id}/upload")
async def upload_to_folder(
    customer_id: str,
    folder_id: str,
    file: UploadFile = File(...),
    comment: Optional[str] = Form(None),
    user: dict = Depends(require_manager_or_admin),
):
    """Upload a single file into a customer folder (multipart/form-data)."""
    await _load_customer_or_403(customer_id, user)
    # Make sure the folder belongs to this customer & user can access it.
    folder = await _load_folder_with_acl(folder_id, user)
    if folder.get("customer_id") != customer_id:
        raise HTTPException(400, "folder does not belong to this customer")

    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    try:
        doc = await fm.upload_file(
            customer_id=customer_id,
            folder_id=folder_id,
            original_name=file.filename or "file",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            comment=comment,
            uploaded_by=user.get("id"),
            uploaded_by_email=user.get("email"),
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Sprint 4 / Customer Timeline — surface the upload in Customer360.
    try:
        from app.services import customer_timeline
        await customer_timeline.record_event(
            customer_id=customer_id,
            kind="file_uploaded",
            title=f"File uploaded: {doc.get('name') or file.filename}",
            body=comment,
            ref={"collection": "files", "id": doc.get("id")},
            actor={"id": user.get("id"), "email": user.get("email"), "name": user.get("name") or user.get("email"), "role": (user.get("role") or "").lower()},
            meta={"size": doc.get("size"), "mime": doc.get("mime") or doc.get("content_type"), "folder_id": folder_id},
        )
    except Exception:
        pass

    return {"success": True, "file": doc}


@router.get("/api/file-manager/files/{file_id}")
async def file_metadata(file_id: str, user: dict = Depends(require_user)):
    f = await _load_file_with_acl(file_id, user)
    return {"success": True, "file": f}


@router.patch("/api/file-manager/files/{file_id}")
async def update_file_meta(
    file_id: str,
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_manager_or_admin),
):
    await _load_file_with_acl(file_id, user)
    try:
        f = await fm.update_file(
            file_id,
            comment=data.get("comment") if "comment" in data else None,
            name=data.get("name") if "name" in data else None,
        )
    except FileNotFoundError:
        raise HTTPException(404, "File not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "file": f}


@router.patch("/api/file-manager/files/{file_id}/move")
async def move_file(
    file_id: str,
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_manager_or_admin),
):
    f = await _load_file_with_acl(file_id, user)
    target = (data.get("folder_id") or "").strip()
    if not target:
        raise HTTPException(400, "folder_id is required")
    # Target folder must belong to the same customer & be ACL-visible.
    target_folder = await _load_folder_with_acl(target, user)
    if target_folder.get("customer_id") != f.get("customer_id"):
        raise HTTPException(400, "target folder belongs to a different customer")
    try:
        out = await fm.move_file(file_id, target)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"success": True, "file": out}


@router.delete("/api/file-manager/files/{file_id}")
async def delete_file(
    file_id: str,
    hard: bool = False,
    user: dict = Depends(require_manager_or_admin),
):
    f = await _load_file_with_acl(file_id, user)
    # Managers can only delete files they uploaded themselves.
    if _user_role(user) == "manager":
        uid = _user_uid(user)
        if not uid or f.get("uploaded_by") != uid:
            raise HTTPException(
                403,
                "Managers can only delete files they uploaded themselves",
            )
    try:
        out = await fm.delete_file(file_id, hard=hard)
    except FileNotFoundError:
        raise HTTPException(404, "File not found")
    return {"success": True, **out}


@router.get("/api/file-manager/files/{file_id}/download")
async def download_file(file_id: str, user: dict = Depends(require_user)):
    """Stream the binary back to the caller with Content-Disposition inline."""
    f = await _load_file_with_acl(file_id, user)
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
        media_type=f.get("mime_type") or "application/octet-stream",
        headers={
            # PHASE SECURITY S3.1.9 — never let an uploaded file execute in our
            # origin: force download for non-inline-safe types, forbid MIME
            # sniffing, and sandbox any inline render (PDF/raster images only).
            "Content-Disposition": _safe_disposition(
                f.get("original_name", "file"), bool(f.get("inline_safe"))
            ),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox",
            "Cache-Control":       "private, no-store",
        },
    )
