"""
BIBI Cars — Block 7.3 — Manager Instructions
==============================================

Single rich-text document editable by admins, readable by all staff.

Schema (singleton, ``id="default"`` in db.manager_instructions):

::

    {
      "id":              "default",
      "content_html":    "<p>…</p>",
      "content_text":    "plain text fallback",
      "updated_at":      "<iso>",
      "updated_by":      "<user-id-or-email>",
      "updated_by_name": "<display>",
      "version":         <int>
    }

Endpoints
---------

  GET  /api/manager-instructions          — all authenticated staff
  PUT  /api/manager-instructions          — admin / master_admin only
  GET  /api/manager-instructions/history  — list previous versions (admin)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from security import require_user

logger = logging.getLogger("bibi.manager_instructions")
router = APIRouter()

COL = "manager_instructions"
HISTORY_COL = "manager_instructions_history"
DOC_ID = "default"


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


def _role(user: Dict[str, Any]) -> str:
    return (user.get("role") or "").lower()


def _is_admin(user: Dict[str, Any]) -> bool:
    return _role(user) in {"owner", "master_admin", "admin"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────
# GET /api/manager-instructions
# ──────────────────────────────────────────────────────────────────────
@router.get("/manager-instructions")
async def get_instructions(
    request: Request,
    user: Dict[str, Any] = Depends(require_user),
):
    role = _role(user)
    if role not in {"owner", "master_admin", "admin", "team_lead", "manager", "support"}:
        raise HTTPException(403, "Staff only")
    db = _db(request)
    doc = await db[COL].find_one({"id": DOC_ID}, {"_id": 0})
    if not doc:
        # Initial empty document, do not insert yet.
        doc = {
            "id":              DOC_ID,
            "content_html":    "",
            "content_text":    "",
            "updated_at":      None,
            "updated_by":      None,
            "updated_by_name": None,
            "version":         0,
        }
    return {"success": True, "data": doc}


# ──────────────────────────────────────────────────────────────────────
# PUT /api/manager-instructions
# ──────────────────────────────────────────────────────────────────────
class InstructionsIn(BaseModel):
    # Accept both `content_html` and `content` aliases. At least one of them
    # must be supplied (the validator below enforces this so the API does not
    # surface a cryptic 422 when a client passes `content`).
    content_html: Optional[str] = Field(None, min_length=0, max_length=200_000)
    content: Optional[str] = Field(None, min_length=0, max_length=200_000)
    content_text: Optional[str] = Field(None, max_length=200_000)

    def resolved_html(self) -> str:
        return self.content_html if self.content_html is not None else (self.content or "")


@router.put("/manager-instructions")
async def put_instructions(
    request: Request,
    payload: InstructionsIn = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Admin only")
    # Require at least one of content/content_html to be provided
    if payload.content_html is None and payload.content is None:
        raise HTTPException(
            status_code=400,
            detail="content_html (or its alias `content`) is required",
        )
    db = _db(request)

    prev = await db[COL].find_one({"id": DOC_ID}, {"_id": 0})
    version = int((prev or {}).get("version") or 0) + 1
    now_iso = _now_iso()
    actor_id   = user.get("id") or user.get("email")
    actor_name = user.get("name") or actor_id

    new_doc = {
        "id":              DOC_ID,
        "content_html":    payload.resolved_html() or "",
        "content_text":    (payload.content_text or "").strip()[:200_000],
        "updated_at":      now_iso,
        "updated_by":      actor_id,
        "updated_by_name": actor_name,
        "version":         version,
    }
    await db[COL].update_one({"id": DOC_ID}, {"$set": new_doc}, upsert=True)

    # snapshot to history collection (best-effort)
    try:
        if prev:
            prev["_history_id"] = f"mih_{uuid.uuid4().hex[:14]}"
            prev["_archived_at"] = now_iso
            prev.pop("_id", None)
            await db[HISTORY_COL].insert_one(prev)
    except Exception as e:
        logger.warning("[manager_instructions] history archive failed: %s", e)

    return {"success": True, "data": new_doc}


# ──────────────────────────────────────────────────────────────────────
# GET /api/manager-instructions/history
# ──────────────────────────────────────────────────────────────────────
@router.get("/manager-instructions/history")
async def get_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    user: Dict[str, Any] = Depends(require_user),
):
    if not _is_admin(user):
        raise HTTPException(403, "Admin only")
    db = _db(request)
    rows = await (
        db[HISTORY_COL]
        .find({"id": DOC_ID}, {"_id": 0})
        .sort("_archived_at", -1)
        .limit(int(limit))
        .to_list(length=int(limit))
    )
    return {"success": True, "data": rows, "count": len(rows)}


async def on_startup(db) -> None:
    try:
        await db[COL].create_index("id", unique=True)
        await db[HISTORY_COL].create_index([("id", 1), ("_archived_at", -1)])
        logger.info("[manager_instructions] indexes ensured")
    except Exception as e:
        logger.warning("[manager_instructions] index ensure failed: %s", e)
