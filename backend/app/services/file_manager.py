"""
File Manager service - Sprint 2 (Customer Documents with folders).

Owns 2 collections:
  * `client_folders` - hierarchical folder tree per customer
  * `client_files`   - file metadata (binary stored via object_storage)

System folders (auto-created on customer create):
  Contracts, Invoices, Registration, Adaptation, Photos, Delivery, Other

File ACL:
  * manager / team_lead / admin / master_admin can read all
  * manager can write files in folders of their assigned customers
  * customer (cabinet) sees only their own customer_id files, read-only
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db
from app.services.object_storage import get_storage

SYSTEM_FOLDERS: list[str] = [
    "Contracts",
    "Invoices",
    "Registration",
    "Adaptation",
    "Photos",
    "Delivery",
    "Other",
]

# ─── Block 7.2 — Canonical system folder taxonomy (slug-based) ───
# These are the *new* canonical folders. Names are localized in the
# frontend via i18n keys ``folders.<slug>``. The migration helper
# ``migrate_system_folders_to_canonical()`` (called from server.py
# startup) is idempotent and safely co-exists with legacy English
# folder names already in the DB.
CANONICAL_SYSTEM_FOLDERS: list[dict[str, Any]] = [
    {"slug": "customer_docs",   "name_en": "Customer documents",  "name_ru": "Документы клиента",   "order": 0},
    {"slug": "vehicle_docs",    "name_en": "Vehicle documents",   "name_ru": "Документы по авто",   "order": 1},
    {"slug": "contracts",       "name_en": "Contracts",           "name_ru": "Договоры",            "order": 2},
    {"slug": "vehicle_photos",  "name_en": "Vehicle photos",      "name_ru": "Фото авто",           "order": 3},
    {"slug": "other",           "name_en": "Other",               "name_ru": "Другое",              "order": 4},
]

# Mapping from legacy English folder name → canonical slug.
LEGACY_NAME_TO_SLUG: dict[str, str] = {
    "Contracts":    "contracts",
    "Invoices":     "customer_docs",   # invoices live with customer docs in new taxonomy
    "Registration": "customer_docs",
    "Adaptation":   "vehicle_docs",
    "Photos":       "vehicle_photos",
    "Delivery":     "vehicle_docs",
    "Other":        "other",
}

# Reverse lookup: slug → display tuple (used for ad-hoc backend renders).
SLUG_DISPLAY_NAMES: dict[str, str] = {
    f["slug"]: f["name_ru"] for f in CANONICAL_SYSTEM_FOLDERS
}

ALLOWED_MIME_PREFIXES = (
    "image/",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "text/",
)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _folder_id() -> str:
    return f"fld_{uuid.uuid4().hex[:12]}"


def _file_id() -> str:
    return f"file_{uuid.uuid4().hex[:12]}"


async def ensure_system_folders(customer_id: str, created_by: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ensure all canonical system folders exist for a customer. Idempotent.

    Block 7.2 rewrite — uses the new slug-based canonical taxonomy.
    Returns the full list of system folders (existing + newly created).
    """
    db = get_db()
    existing = await db.client_folders.find(
        {"customer_id": customer_id, "is_system": True},
        {"_id": 0},
    ).to_list(length=50)
    existing_slugs = {f.get("slug") for f in existing if f.get("slug")}
    existing_names = {f.get("name") for f in existing}

    to_create = []
    for entry in CANONICAL_SYSTEM_FOLDERS:
        slug = entry["slug"]
        if slug in existing_slugs:
            continue
        # Also skip if a legacy English-named system folder maps to this slug
        legacy_match = next((n for n, s in LEGACY_NAME_TO_SLUG.items() if s == slug and n in existing_names), None)
        if legacy_match:
            # Backfill slug onto the legacy folder rather than duplicating
            await db.client_folders.update_one(
                {"customer_id": customer_id, "name": legacy_match, "is_system": True},
                {"$set": {"slug": slug, "updated_at": _now()}},
            )
            continue
        to_create.append({
            "id":          _folder_id(),
            "customer_id": customer_id,
            "name":        entry["name_ru"],       # display fallback if frontend ignores slug
            "slug":        slug,
            "is_system":   True,
            "is_canonical": True,
            "parent_id":   None,
            "order":       entry["order"],
            "created_by":  created_by,
            "created_at":  _now(),
        })
    if to_create:
        await db.client_folders.insert_many(to_create)
        for f in to_create:
            f.pop("_id", None)
        existing.extend(to_create)
    # re-fetch slugs since we may have backfilled
    existing = await db.client_folders.find(
        {"customer_id": customer_id, "is_system": True},
        {"_id": 0},
    ).to_list(length=50)
    return sorted(existing, key=lambda f: (f.get("order", 999), f.get("name", "")))


async def migrate_system_folders_to_canonical() -> Dict[str, int]:
    """One-shot startup migration: backfill ``slug`` on every existing
    legacy system folder, and create any missing canonical folders for
    every customer that already has at least one system folder.

    Idempotent. Safe to run on every startup.

    Returns: ``{"customers": N, "slugs_backfilled": M, "canonical_added": K}``
    """
    db = get_db()
    customers_seen: set[str] = set()
    slugs_backfilled = 0
    canonical_added = 0

    # 1) Backfill slug on legacy system folders
    cur = db.client_folders.find(
        {"is_system": True, "slug": {"$in": [None, ""]}},
        {"_id": 0, "id": 1, "customer_id": 1, "name": 1},
    )
    rows = await cur.to_list(length=20000)
    for row in rows:
        slug = LEGACY_NAME_TO_SLUG.get(row.get("name") or "")
        if not slug:
            continue
        await db.client_folders.update_one(
            {"id": row["id"]},
            {"$set": {"slug": slug, "updated_at": _now()}},
        )
        slugs_backfilled += 1
        customers_seen.add(row["customer_id"])

    # 2) For every customer touched (and for every customer that already
    #    has at least one system folder), make sure all canonical folders
    #    exist.  Use a cheap distinct query for the broader set.
    customer_ids = await db.client_folders.distinct("customer_id", {"is_system": True})
    for cid in customer_ids:
        before_cnt = await db.client_folders.count_documents(
            {"customer_id": cid, "is_system": True, "is_canonical": True}
        )
        await ensure_system_folders(cid, created_by="system:migration")
        after_cnt = await db.client_folders.count_documents(
            {"customer_id": cid, "is_system": True, "is_canonical": True}
        )
        canonical_added += max(0, after_cnt - before_cnt)
        customers_seen.add(cid)

    return {
        "customers": len(customers_seen),
        "slugs_backfilled": slugs_backfilled,
        "canonical_added": canonical_added,
    }


async def list_folders(customer_id: str) -> List[Dict[str, Any]]:
    """Return all folders for a customer with aggregated metadata attached.

    Per folder we attach: ``file_count``, ``total_size_bytes``, ``last_upload_at``.
    Will auto-seed the canonical system folders if none exist yet.
    """
    db = get_db()
    folders = await db.client_folders.find(
        {"customer_id": customer_id},
        {"_id": 0},
    ).to_list(length=500)

    if not folders:
        folders = await ensure_system_folders(customer_id)

    # Single aggregation: count + size + last upload date per folder
    stats: Dict[str, Dict[str, Any]] = {}
    if folders:
        try:
            pipeline = [
                {"$match": {
                    "customer_id": customer_id,
                    "deleted": {"$ne": True},
                }},
                {"$group": {
                    "_id":             "$folder_id",
                    "count":           {"$sum": 1},
                    "total_size":      {"$sum": {"$ifNull": ["$size", 0]}},
                    "last_upload_at":  {"$max": "$created_at"},
                }},
            ]
            async for row in db.client_files.aggregate(pipeline):
                stats[row["_id"]] = row
        except Exception:
            pass

    for f in folders:
        s = stats.get(f["id"]) or {}
        f["file_count"]       = int(s.get("count") or 0)
        f["total_size_bytes"] = int(s.get("total_size") or 0)
        f["last_upload_at"]   = s.get("last_upload_at")
        # Always surface a description key (None if unset) for a stable FE shape.
        f.setdefault("description", None)

    return sorted(
        folders,
        key=lambda f: (
            0 if f.get("is_system") else 1,
            f.get("order", 999),
            (f.get("name") or "").lower(),
        ),
    )


async def create_folder(
    customer_id: str,
    name: str,
    *,
    parent_id: Optional[str] = None,
    description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    db = get_db()
    name = (name or "").strip()
    if not name:
        raise ValueError("folder name is required")
    if len(name) > 80:
        raise ValueError("folder name too long (max 80 chars)")

    # If parent_id supplied, make sure it exists and belongs to the same customer.
    if parent_id:
        parent = await db.client_folders.find_one(
            {"id": parent_id, "customer_id": customer_id},
            {"_id": 0, "id": 1},
        )
        if not parent:
            raise ValueError("parent folder not found for this customer")

    # Reject duplicates within same parent
    dup = await db.client_folders.find_one({
        "customer_id": customer_id,
        "parent_id":   parent_id,
        "name":        name,
    })
    if dup:
        raise ValueError("folder with this name already exists in this location")

    doc = {
        "id":          _folder_id(),
        "customer_id": customer_id,
        "name":        name,
        "description": (description or None),
        "is_system":   False,
        "parent_id":   parent_id,
        "order":       1000,
        "created_by":  created_by,
        "created_at":  _now(),
    }
    await db.client_folders.insert_one(doc)
    doc.pop("_id", None)
    doc["file_count"]       = 0
    doc["total_size_bytes"] = 0
    doc["last_upload_at"]   = None
    return doc


async def update_folder(
    folder_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Rename a folder and/or set its description.

    * System folders cannot be renamed, but their description CAN be updated
      (so managers can leave hints like "All notarized PDFs go here").
    * ``description`` may be passed as empty string to clear it.
    """
    db = get_db()
    folder = await db.client_folders.find_one({"id": folder_id}, {"_id": 0})
    if not folder:
        raise FileNotFoundError("folder not found")

    upd: Dict[str, Any] = {"updated_at": _now()}

    if name is not None:
        new_name = (name or "").strip()
        if not new_name:
            raise ValueError("name is required")
        if len(new_name) > 80:
            raise ValueError("folder name too long (max 80 chars)")
        if folder.get("is_system"):
            raise PermissionError("system folders cannot be renamed")
        # Reject duplicates within same parent
        dup = await db.client_folders.find_one({
            "customer_id": folder["customer_id"],
            "parent_id":   folder.get("parent_id"),
            "name":        new_name,
            "id":          {"$ne": folder_id},
        })
        if dup:
            raise ValueError("folder with this name already exists in this location")
        upd["name"] = new_name

    if description is not None:
        desc = (description or "").strip()
        upd["description"] = desc or None

    if set(upd.keys()) == {"updated_at"}:
        raise ValueError("nothing to update")

    await db.client_folders.update_one({"id": folder_id}, {"$set": upd})
    folder.update(upd)
    return folder


# Backwards-compat alias (the older router still imported `rename_folder`).
async def rename_folder(folder_id: str, new_name: str) -> Dict[str, Any]:
    return await update_folder(folder_id, name=new_name)


async def delete_folder(folder_id: str, *, cascade: bool = False) -> Dict[str, Any]:
    """Delete a non-system folder.

    * ``cascade=False`` (default): refuses if the folder still contains files.
    * ``cascade=True``: also soft-deletes (or hard-deletes) all files inside
      *and* recursively descends into every nested subfolder. This is the
      mode used by the Customer 360 → Documents UI per spec
      ("Видалити разом з вмістом").
    """
    db = get_db()
    folder = await db.client_folders.find_one({"id": folder_id}, {"_id": 0})
    if not folder:
        raise FileNotFoundError("folder not found")
    if folder.get("is_system"):
        raise PermissionError("system folders cannot be deleted")

    file_count = await db.client_files.count_documents({
        "folder_id": folder_id,
        "deleted": {"$ne": True},
    })

    if not cascade and file_count > 0:
        raise ValueError(f"folder is not empty ({file_count} files)")

    if cascade:
        # Soft-delete all files in this folder (and any nested subfolder)
        # so we never lose binaries silently.
        to_visit = [folder_id]
        visited: List[str] = []
        while to_visit:
            fid = to_visit.pop()
            visited.append(fid)
            async for child in db.client_folders.find({"parent_id": fid}, {"id": 1}):
                if child["id"] not in visited:
                    to_visit.append(child["id"])
        if visited:
            await db.client_files.update_many(
                {"folder_id": {"$in": visited}, "deleted": {"$ne": True}},
                {"$set": {"deleted": True, "deleted_at": _now()}},
            )
            # Drop the folder docs themselves (in reverse so children go first)
            await db.client_folders.delete_many({"id": {"$in": visited}})
    else:
        await db.client_folders.delete_one({"id": folder_id})

    return {
        "id":          folder_id,
        "deleted":     True,
        "cascade":     bool(cascade),
        "files_freed": int(file_count) if cascade else 0,
    }


async def upload_file(
    *,
    customer_id: str,
    folder_id: str,
    original_name: str,
    content_type: str,
    data: bytes,
    comment: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    uploaded_by_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist a file: store binary via object_storage + metadata in mongo."""
    # PHASE SECURITY S3.1 — server-authoritative validation (ignores client mime).
    from app.services.upload_security import validate_upload, UploadRejected
    try:
        safe = validate_upload(original_name, content_type, data)
    except UploadRejected as e:
        raise ValueError(str(e))

    db = get_db()
    folder = await db.client_folders.find_one({"id": folder_id, "customer_id": customer_id})
    if not folder:
        raise FileNotFoundError("folder not found for this customer")

    storage = get_storage()
    info = await storage.put(
        prefix=f"customers/{customer_id}/{folder_id}",
        filename=safe.filename,
        data=data,
        content_type=safe.mime,
    )

    doc = {
        "id":                _file_id(),
        "customer_id":       customer_id,
        "folder_id":         folder_id,
        "folder_name":       folder.get("name"),
        "original_name":     safe.filename,
        "storage_key":       info["key"],
        "url":               info["url"],
        "mime_type":         safe.mime,
        "inline_safe":       safe.inline_safe,
        "category":          safe.category,
        "size":              info["size"],
        "backend":           info["backend"],
        "comment":           (comment or "").strip() or None,
        "uploaded_by":       uploaded_by,
        "uploaded_by_email": uploaded_by_email,
        "created_at":        _now(),
        "deleted":           False,
    }
    await db.client_files.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_files(customer_id: str, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {
        "customer_id": customer_id,
        "deleted":     {"$ne": True},
    }
    if folder_id:
        q["folder_id"] = folder_id
    cursor = db.client_files.find(q, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def get_file(file_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db.client_files.find_one({"id": file_id, "deleted": {"$ne": True}}, {"_id": 0})


async def move_file(file_id: str, new_folder_id: str) -> Dict[str, Any]:
    db = get_db()
    file = await db.client_files.find_one({"id": file_id}, {"_id": 0})
    if not file:
        raise FileNotFoundError("file not found")
    folder = await db.client_folders.find_one({"id": new_folder_id, "customer_id": file["customer_id"]})
    if not folder:
        raise FileNotFoundError("target folder not found for this customer")
    await db.client_files.update_one(
        {"id": file_id},
        {"$set": {
            "folder_id":   new_folder_id,
            "folder_name": folder.get("name"),
            "updated_at":  _now(),
        }},
    )
    file["folder_id"]   = new_folder_id
    file["folder_name"] = folder.get("name")
    return file


async def update_file(file_id: str, *,
                     comment: Optional[str] = None,
                     name: Optional[str] = None) -> Dict[str, Any]:
    db = get_db()
    upd: Dict[str, Any] = {"updated_at": _now()}
    if comment is not None:
        upd["comment"] = (comment or "").strip() or None
    if name:
        upd["original_name"] = name.strip()
    if len(upd) == 1:
        raise ValueError("nothing to update")
    res = await db.client_files.update_one({"id": file_id}, {"$set": upd})
    if res.matched_count == 0:
        raise FileNotFoundError("file not found")
    return await db.client_files.find_one({"id": file_id}, {"_id": 0})


async def delete_file(file_id: str, hard: bool = False) -> Dict[str, Any]:
    db = get_db()
    file = await db.client_files.find_one({"id": file_id}, {"_id": 0})
    if not file:
        raise FileNotFoundError("file not found")
    if hard:
        try:
            get_storage().delete(file["storage_key"])
        except Exception:
            pass
        await db.client_files.delete_one({"id": file_id})
    else:
        await db.client_files.update_one(
            {"id": file_id},
            {"$set": {"deleted": True, "deleted_at": _now()}},
        )
    return {"id": file_id, "deleted": True, "hard": hard}


__all__ = [
    "SYSTEM_FOLDERS",
    "MAX_FILE_SIZE",
    "ALLOWED_MIME_PREFIXES",
    "ensure_system_folders",
    "list_folders",
    "create_folder",
    "rename_folder",
    "update_folder",
    "delete_folder",
    "upload_file",
    "list_files",
    "get_file",
    "move_file",
    "update_file",
    "delete_file",
]
