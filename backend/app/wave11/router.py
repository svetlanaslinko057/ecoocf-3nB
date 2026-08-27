"""
Wave 11 — Deal360 FastAPI router.

Mounted with prefix `/api` from server.py, so the public surface is:

    GET    /api/deals/{deal_id}/360
    GET    /api/deals/{deal_id}/documents
    POST   /api/deals/{deal_id}/documents          (metadata only — body: {name, url, kind?})
    DELETE /api/deals/{deal_id}/documents/{doc_id}
    GET    /api/deals/{deal_id}/stage-progress
    POST   /api/deals/{deal_id}/notes              (alias to Wave 6 note hook)

Access control re-uses Wave 6 helpers so a manager only sees their own deals.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from security import require_manager_or_admin

from app.wave6.timeline import write_event
from app.wave6.router import _check_deal_access  # reuse access matrix
from .bundle import build_deal360_bundle, list_deal_documents
from .stage_progress import compute_stage_progress
from .actions import (
    allowed_transitions,
    transition_deal_stage,
    add_blocker,
    resolve_blocker,
    register_deposit_quick,
    update_deposit_status,
    register_payment_quick,
    update_payment_status,
)

logger = logging.getLogger("bibi.wave11.router")
router = APIRouter()


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _fetch_deal_or_404(db, deal_id: str) -> Dict[str, Any]:
    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]}, {"_id": 0}
    )
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")
    return deal


# ─── /360 ───────────────────────────────────────────────────────────────────
@router.get("/deals/{deal_id}/360")
async def deal_360(
    deal_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Single round-trip Deal360 bundle. See app.wave11.bundle for the shape."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    bundle = await build_deal360_bundle(db, deal_id)
    if not bundle:
        raise HTTPException(404, f"Deal {deal_id} not found")
    return bundle


@router.get("/deals/{deal_id}/stage-progress")
async def deal_stage_progress(
    deal_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Cheap endpoint used by widgets that only need the bar (no documents/timeline)."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)
    return {"success": True, "data": compute_stage_progress(deal)}


# ─── Documents ──────────────────────────────────────────────────────────────
@router.get("/deals/{deal_id}/documents")
async def deal_documents_list(
    deal_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    docs = await list_deal_documents(db, deal_id)
    return {"success": True, "items": docs, "data": docs, "total": len(docs)}


@router.post("/deals/{deal_id}/documents")
async def deal_documents_add(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Register a document metadata entry. The actual file upload is handled by
    the existing media endpoints; here we only persist the link + metadata so
    the Documents tab can render it.
    """
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    name = (body or {}).get("name") or "Document"
    url  = (body or {}).get("url")
    if not url:
        raise HTTPException(400, "url is required")

    doc = {
        "id":          f"dd_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}",
        "deal_id":     deal_id,
        "name":        str(name)[:255],
        "url":         url,
        "kind":        (body or {}).get("kind") or "other",
        "size":        (body or {}).get("size"),
        "uploaded_by": user.get("email") or user.get("id"),
        "uploaded_at": _now_iso(),
        "created_at":  _now_iso(),
    }
    try:
        await db.deal_documents.insert_one(doc)
    except Exception as e:
        logger.exception("[wave11] failed to insert deal_document: %s", e)
        raise HTTPException(500, "Failed to register document")

    # Best-effort timeline event so the document is visible there too.
    try:
        await write_event(
            db,
            deal_id=deal_id,
            event_type="note_added",
            message=f"Document attached: {doc['name']}",
            i18n_key="timeline.document_added",
            data={"document_id": doc["id"], "url": url, "kind": doc["kind"]},
            actor={"email": user.get("email"), "role": user.get("role")},
        )
    except Exception:
        pass

    return {"success": True, "data": {**doc, "_id": None}}


@router.delete("/deals/{deal_id}/documents/{doc_id}")
async def deal_documents_remove(
    deal_id: str,
    doc_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    res = await db.deal_documents.delete_one({"deal_id": deal_id, "id": doc_id})
    if not res.deleted_count:
        raise HTTPException(404, "Document not found")
    return {"success": True}


# ─── Notes (alias / convenience over Wave 6 timeline) ──────────────────────
@router.post("/deals/{deal_id}/notes")
async def deal_note_add(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Append a free-form note to the deal timeline (mirrors /api/admin/deals/{id}/notes)."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    text = ((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Note text is required")
    if len(text) > 4000:
        raise HTTPException(400, "Note is too long (max 4000 chars)")

    ev = await write_event(
        db,
        deal_id=deal_id,
        event_type="note_added",
        message=text,
        i18n_key="timeline.note",
        data={"text": text},
        actor={"email": user.get("email"), "role": user.get("role")},
    )
    return {"success": True, "data": ev.to_dict() if ev else None}


# ─── Wave 11.1 — Pipeline transitions ─────────────────────────────────────
@router.get("/deals/{deal_id}/transitions")
async def deal_available_transitions(
    deal_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """List the stages the current deal may move to."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)
    return {"success": True, "items": allowed_transitions(deal)}


@router.post("/deals/{deal_id}/transition")
async def deal_transition(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Move the deal to a new stage.

    Body: `{ "to": "<stage>", "reason": "<optional>" }`
    """
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    target = (body or {}).get("to") or (body or {}).get("stage")
    reason = (body or {}).get("reason")
    if not target:
        raise HTTPException(400, "Field 'to' is required")

    entry = await transition_deal_stage(
        db, deal=deal, target_stage=target, reason=reason, actor=user
    )
    return {"success": True, "data": entry}


# ─── Wave 11.1 — Blockers ─────────────────────────────────────────────────
@router.post("/deals/{deal_id}/blockers")
async def deal_blocker_add(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Add a manual blocker to the deal."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    entry = await add_blocker(
        db,
        deal_id=deal_id,
        label=(body or {}).get("label") or "",
        note=(body or {}).get("note"),
        actor=user,
    )
    return {"success": True, "data": entry}


@router.delete("/deals/{deal_id}/blockers/{blocker_id}")
async def deal_blocker_resolve(
    deal_id: str,
    blocker_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Mark a blocker as resolved. Optional resolution note via ?note=..."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    note = request.query_params.get("note")
    entry = await resolve_blocker(
        db, deal_id=deal_id, blocker_id=blocker_id, note=note, actor=user
    )
    return {"success": True, "data": entry}


# ─── Wave 11.1 — Deposit quick actions ────────────────────────────────────
@router.post("/deals/{deal_id}/deposits")
async def deal_deposit_register(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Register a deposit for the deal in one click. Status starts as 'pending'."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    doc = await register_deposit_quick(
        db,
        deal=deal,
        amount=(body or {}).get("amount"),
        currency=(body or {}).get("currency") or deal.get("currency") or "EUR",
        method=(body or {}).get("method"),
        note=(body or {}).get("note"),
        actor=user,
    )
    return {"success": True, "data": doc}


@router.post("/deals/{deal_id}/deposits/{deposit_id}/{action}")
async def deal_deposit_action(
    deal_id: str,
    deposit_id: str,
    action: str,
    request: Request,
    body: Dict[str, Any] = Body(default={}),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Confirm / reject / refund a deposit (action in {confirm,reject,refund})."""
    if action not in ("confirm", "reject", "refund"):
        raise HTTPException(400, "Action must be confirm / reject / refund")
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    new_status = {"confirm": "confirmed", "reject": "rejected", "refund": "refunded"}[action]
    doc = await update_deposit_status(
        db,
        deposit_id=deposit_id,
        new_status=new_status,
        note=(body or {}).get("note"),
        actor=user,
    )
    return {"success": True, "data": doc}


# ─── Wave 11.1 — Payment quick actions ────────────────────────────────────
@router.post("/deals/{deal_id}/payments")
async def deal_payment_register(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Register a payment row for the deal (status pending or confirmed)."""
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    doc = await register_payment_quick(
        db,
        deal=deal,
        amount=(body or {}).get("amount"),
        currency=(body or {}).get("currency") or deal.get("currency") or "EUR",
        kind=(body or {}).get("type") or (body or {}).get("kind") or "milestone",
        status=(body or {}).get("status") or "pending",
        note=(body or {}).get("note"),
        actor=user,
    )
    return {"success": True, "data": doc}


@router.post("/deals/{deal_id}/payments/{payment_id}/{action}")
async def deal_payment_action(
    deal_id: str,
    payment_id: str,
    action: str,
    request: Request,
    body: Dict[str, Any] = Body(default={}),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """confirm / fail / refund a payment."""
    if action not in ("confirm", "fail", "refund"):
        raise HTTPException(400, "Action must be confirm / fail / refund")
    db = _db(request)
    deal = await _fetch_deal_or_404(db, deal_id)
    await _check_deal_access(db, deal, user)

    new_status = {"confirm": "confirmed", "fail": "failed", "refund": "refunded"}[action]
    doc = await update_payment_status(
        db,
        payment_id=payment_id,
        new_status=new_status,
        note=(body or {}).get("note"),
        actor=user,
    )
    return {"success": True, "data": doc}


# ─── Startup ────────────────────────────────────────────────────────────────
async def on_startup(db) -> None:
    """Ensure indexes on the new `deal_documents` collection."""
    try:
        await db.deal_documents.create_index("id", unique=True, name="uniq_deal_document_id")
        await db.deal_documents.create_index([("deal_id", 1), ("created_at", -1)])
        logger.info("[wave11] deal_documents indexes ensured")
    except Exception as e:
        logger.warning("[wave11] deal_documents index ensure failed: %s", e)
