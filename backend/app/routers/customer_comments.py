"""
Customer Comments router — Sprint 4
====================================

Free-form notes attached to a customer. Visible to all staff (manager,
team_lead, admin); customer themselves does NOT see them.

Rules
-----
* Anyone with manager+ can add a comment.
* Only the author OR an admin can edit/delete a comment.
* Anyone with team_lead+ can pin/unpin (pinned = sticks to top).
* Editing sets `edited=true` and refreshes `updated_at`.
* Soft delete: marks ``deleted=true`` and zeroes the body so audit logs
  still resolve the row. Hard deletes are admin-only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.db_runtime import get_db
from app.services import customer_timeline
from security import require_admin, require_manager_or_admin

router = APIRouter(tags=["customer-comments"])
COLLECTION = "customer_comments"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_customer(customer_id: str) -> Dict[str, Any]:
    db = get_db()
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")
    return cust


@router.get("/api/customers/{customer_id}/comments",
            dependencies=[Depends(require_manager_or_admin)])
async def list_comments(customer_id: str, include_deleted: bool = False):
    await _ensure_customer(customer_id)
    db = get_db()
    flt: Dict[str, Any] = {"customer_id": customer_id}
    if not include_deleted:
        flt["deleted"] = {"$ne": True}
    # Pinned first, then newest
    items: List[Dict[str, Any]] = await db[COLLECTION].find(flt, {"_id": 0}).to_list(length=500)
    items.sort(key=lambda c: (
        0 if c.get("pinned") else 1,
        # newest first (descending) — use string compare since ISO 8601 is sortable
        "" if c.get("pinned") else c.get("created_at") or "",
    ))
    # Then for pinned bucket also sort by created_at desc
    pinned = sorted([c for c in items if c.get("pinned")], key=lambda c: c.get("created_at") or "", reverse=True)
    rest = sorted([c for c in items if not c.get("pinned")], key=lambda c: c.get("created_at") or "", reverse=True)
    return {"success": True, "items": pinned + rest, "total": len(items)}


@router.post("/api/customers/{customer_id}/comments",
             dependencies=[Depends(require_manager_or_admin)])
async def create_comment(
    customer_id: str,
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_manager_or_admin),
):
    await _ensure_customer(customer_id)
    body = (data.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "body is required")
    if len(body) > 8000:
        raise HTTPException(400, "comment too long (max 8000 chars)")

    db = get_db()
    role = (user.get("role") or "").lower()
    doc = {
        "id": uuid.uuid4().hex,
        "customer_id": customer_id,
        "customerId": customer_id,
        "body": body,
        "author_id": user.get("id") or user.get("managerId"),
        "author_email": user.get("email"),
        "author_name": user.get("name") or user.get("firstName") or user.get("email"),
        "author_role": role,
        "pinned": bool(data.get("pinned")) if role in {"team_lead", "admin", "master_admin", "owner"} else False,
        "deleted": False,
        "edited": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db[COLLECTION].insert_one(dict(doc))
    doc.pop("_id", None)

    # Fire timeline event (best-effort)
    try:
        await customer_timeline.record_event(
            customer_id=customer_id,
            kind="comment_added",
            title=f"Комментарий от {doc['author_name'] or 'staff'}",
            body=body[:240],
            ref={"collection": COLLECTION, "id": doc["id"]},
            actor=customer_timeline.extract_actor(user),
            meta={"pinned": doc["pinned"]},
        )
    except Exception:
        pass
    return {"success": True, "comment": doc}


@router.patch("/api/customers/{customer_id}/comments/{comment_id}",
              dependencies=[Depends(require_manager_or_admin)])
async def update_comment(
    customer_id: str,
    comment_id: str,
    data: Dict[str, Any] = Body(default_factory=dict),
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    doc = await db[COLLECTION].find_one({"id": comment_id, "customer_id": customer_id})
    if not doc:
        raise HTTPException(404, "Comment not found")
    role = (user.get("role") or "").lower()
    is_owner = (doc.get("author_id") and doc.get("author_id") == (user.get("id") or user.get("managerId")))
    is_priv = role in {"team_lead", "admin", "master_admin", "owner"}

    update: Dict[str, Any] = {"updated_at": _now()}

    if "body" in data:
        if not (is_owner or is_priv):
            raise HTTPException(403, "Only the author or admins can edit a comment")
        new_body = (data.get("body") or "").strip()
        if not new_body:
            raise HTTPException(400, "body cannot be empty")
        update["body"] = new_body
        update["edited"] = True

    if "pinned" in data:
        if not is_priv:
            raise HTTPException(403, "Only team_lead and admins can pin a comment")
        update["pinned"] = bool(data.get("pinned"))

    await db[COLLECTION].update_one({"id": comment_id}, {"$set": update})

    if update.get("pinned") is True:
        try:
            await customer_timeline.record_event(
                customer_id=customer_id, kind="comment_pinned",
                title="Комментарий закреплён",
                ref={"collection": COLLECTION, "id": comment_id},
                actor=customer_timeline.extract_actor(user),
            )
        except Exception:
            pass

    fresh = await db[COLLECTION].find_one({"id": comment_id}, {"_id": 0})
    return {"success": True, "comment": fresh}


@router.delete("/api/customers/{customer_id}/comments/{comment_id}",
               dependencies=[Depends(require_manager_or_admin)])
async def delete_comment(
    customer_id: str,
    comment_id: str,
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    doc = await db[COLLECTION].find_one({"id": comment_id, "customer_id": customer_id})
    if not doc:
        raise HTTPException(404, "Comment not found")
    role = (user.get("role") or "").lower()
    is_owner = doc.get("author_id") == (user.get("id") or user.get("managerId"))
    is_priv = role in {"admin", "master_admin", "owner"}

    if not (is_owner or is_priv):
        raise HTTPException(403, "You can only delete your own comment (admins can delete any)")

    # Soft delete for plain owners; hard delete for admins
    if is_priv and not is_owner:
        await db[COLLECTION].delete_one({"id": comment_id})
    else:
        await db[COLLECTION].update_one(
            {"id": comment_id},
            {"$set": {"deleted": True, "body": "[deleted]", "updated_at": _now()}},
        )
    return {"success": True}
