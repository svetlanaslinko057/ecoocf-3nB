"""
BIBI Cars - Document Templates Repository (Sprint 3)
====================================================

Mongo-backed CRUD for HTML templates used by the PDF Engine.

A template document looks like::

    {
        "id":          "tpl_xxxxxxxx",
        "type":        "contract" | "invoice" | "acceptance_act" | ...,
        "name":        "USA Import Contract (EN)",
        "language":    "en" | "uk" | "bg",
        "is_default":  True,
        "is_active":   True,
        "html":        "<html>...{{customer.first_name}}...</html>",
        "meta":        {paper_size: "A4", margin_mm: 20, ...},
        "created_at":  iso8601,
        "updated_at":  iso8601,
        "created_by":  email,
    }

Variables available inside templates (passed by the rendering service):
  customer, manager, company, invoice, order, vehicle, calculation,
  signatures, generated_at, version.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

COLLECTION = "document_templates"

VALID_TYPES = {"contract", "invoice", "acceptance_act", "delivery_certificate"}
VALID_LANGUAGES = {"en", "uk", "bg", "ru"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tpl_id() -> str:
    return f"tpl_{uuid.uuid4().hex[:12]}"


async def ensure_indexes() -> None:
    db = get_db()
    await db[COLLECTION].create_index("id", unique=True)
    await db[COLLECTION].create_index([("type", 1), ("language", 1), ("is_default", -1)])


async def count() -> int:
    return await get_db()[COLLECTION].count_documents({})


async def list_templates(
    *,
    type: Optional[str] = None,
    language: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if type:        q["type"] = type
    if language:    q["language"] = language
    if is_active is not None: q["is_active"] = is_active
    cur = get_db()[COLLECTION].find(q, {"_id": 0}).sort("updated_at", -1)
    return await cur.to_list(length=200)


async def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    return await get_db()[COLLECTION].find_one({"id": template_id}, {"_id": 0})


async def get_default_template(
    type: str,
    *,
    language: str = "en",
    fallback_language: str = "en",
) -> Optional[Dict[str, Any]]:
    """Resolve which template to use for a given (type, language).

    Strategy:
      1. Look up an active default for (type, language).
      2. Fall back to (type, fallback_language) if not found.
      3. Otherwise, the most recently updated active template of (type).
    """
    db = get_db()
    for lang in (language, fallback_language):
        tpl = await db[COLLECTION].find_one(
            {"type": type, "language": lang, "is_active": True, "is_default": True},
            {"_id": 0},
        )
        if tpl: return tpl
    return await db[COLLECTION].find_one(
        {"type": type, "is_active": True},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )


async def create_template(data: Dict[str, Any], *, created_by: Optional[str] = None) -> Dict[str, Any]:
    if data.get("type") not in VALID_TYPES:
        raise ValueError(f"invalid template type; expected one of {sorted(VALID_TYPES)}")
    language = (data.get("language") or "en").lower()
    if language not in VALID_LANGUAGES:
        raise ValueError(f"invalid template language; expected one of {sorted(VALID_LANGUAGES)}")
    if not (data.get("html") or "").strip():
        raise ValueError("html body is required")
    if not (data.get("name") or "").strip():
        raise ValueError("name is required")

    doc = {
        "id":           _tpl_id(),
        "type":         data["type"],
        "name":         data["name"].strip(),
        "language":     language,
        "is_default":   bool(data.get("is_default")),
        "is_active":    bool(data.get("is_active", True)),
        "html":         data["html"],
        "meta":         data.get("meta") or {},
        "created_at":   _now(),
        "updated_at":   _now(),
        "created_by":   created_by,
    }
    db = get_db()
    # If marked default, demote other defaults of same (type, language)
    if doc["is_default"]:
        await db[COLLECTION].update_many(
            {"type": doc["type"], "language": doc["language"], "is_default": True},
            {"$set": {"is_default": False, "updated_at": _now()}},
        )
    await db[COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_template(template_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    cur = await get_template(template_id)
    if not cur:
        raise FileNotFoundError("template not found")
    upd = {k: v for k, v in patch.items()
           if k in {"name", "html", "language", "is_default", "is_active", "meta"}}
    if "language" in upd and upd["language"] not in VALID_LANGUAGES:
        raise ValueError("invalid language")
    upd["updated_at"] = _now()
    # If promoting to default, demote others in same (type, language)
    new_type = cur["type"]
    new_lang = upd.get("language", cur["language"])
    if upd.get("is_default"):
        await db[COLLECTION].update_many(
            {"type": new_type, "language": new_lang, "is_default": True, "id": {"$ne": template_id}},
            {"$set": {"is_default": False, "updated_at": _now()}},
        )
    await db[COLLECTION].update_one({"id": template_id}, {"$set": upd})
    return await get_template(template_id)


async def delete_template(template_id: str) -> Dict[str, Any]:
    cur = await get_template(template_id)
    if not cur:
        raise FileNotFoundError("template not found")
    await get_db()[COLLECTION].delete_one({"id": template_id})
    return {"id": template_id, "deleted": True}


async def seed_default_templates() -> List[Dict[str, Any]]:
    """Insert 3 baseline templates (contract / invoice / acceptance_act).

    Idempotent - returns the existing set if non-empty.
    """
    db = get_db()
    if await count() > 0:
        return await list_templates()

    from app.services.pdf_templates_seed import DEFAULT_TEMPLATES
    docs: List[Dict[str, Any]] = []
    for t in DEFAULT_TEMPLATES:
        docs.append({
            "id":         _tpl_id(),
            "is_default": True,
            "is_active":  True,
            "created_at": _now(),
            "updated_at": _now(),
            "created_by": "seed",
            **t,
        })
    if docs:
        await db[COLLECTION].insert_many(docs)
        for d in docs: d.pop("_id", None)
    return docs
