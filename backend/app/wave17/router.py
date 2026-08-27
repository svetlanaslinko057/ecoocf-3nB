"""
BIBI Cars — Wave 17 — Action Center HTTP surface
====================================================

Mounted at `/api/actions/*`.

Auth:
  * Reads (inbox / my / team / analytics / detail / list / sources) → require_user
  * Mutations (create / patch / lifecycle / sync)                  → require_user
    (managers can resolve their own; team_lead can resolve team's; admin
     can resolve anyone's — enforced in service layer / patch endpoint)
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave17.aggregations import (
    compute_analytics, compute_inbox, compute_my, compute_team,
    list_actions, scope_filter,
)
from app.wave17.models import (
    ActionCreate, ActionPatch, AssignAction, CommentAction,
    EscalateAction, ResolveAction, SnoozeAction,
)
from app.wave17.service import (
    assign_action, comment_action, create_action, escalate_action,
    get_action, patch_action, reopen_action, resolve_action,
    snooze_action, start_action, auto_resume_snoozed,
)
from app.wave17.sources import list_source_catalogue
from app.wave17.sync import sync_actions

logger = logging.getLogger("bibi.wave17")
router = APIRouter(prefix="/api/actions", tags=["Wave17:ActionCenter"])

from security import require_user  # type: ignore


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


# ────────────────────────────────────────────────────────────────────
# STATIC
# ────────────────────────────────────────────────────────────────────
@router.get("/sources")
async def sources_endpoint(_: Dict[str, Any] = Depends(require_user)):
    cat = list_source_catalogue()
    return {"success": True, "items": cat, "total": len(cat)}


# ────────────────────────────────────────────────────────────────────
# DASHBOARD TABS (auto-sync + auto-resume on every read)
# ────────────────────────────────────────────────────────────────────
async def _refresh(db, user):
    """Cheap background refresh: bounce snoozed back to open + sync sources."""
    try:
        await auto_resume_snoozed(db)
        await sync_actions(db, user)
    except Exception as _e:
        logger.warning("[wave17] refresh failed: %s", _e)


@router.get("/inbox")
async def inbox_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    db = _db(request)
    await _refresh(db, current_user)
    data = await compute_inbox(db, current_user)
    return {"success": True, "data": data}


@router.get("/my")
async def my_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    db = _db(request)
    await _refresh(db, current_user)
    data = await compute_my(db, current_user)
    return {"success": True, "data": data}


@router.get("/team")
async def team_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    db = _db(request)
    await _refresh(db, current_user)
    data = await compute_team(db, current_user)
    return {"success": True, "data": data}


@router.get("/analytics")
async def analytics_endpoint(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    data = await compute_analytics(db, current_user, days=days)
    return {"success": True, "data": data}


# ────────────────────────────────────────────────────────────────────
# LIST + DETAIL
# ────────────────────────────────────────────────────────────────────
@router.get("")
async def list_endpoint(
    request: Request,
    status:   Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    source:   Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    only_open: bool         = Query(False),
    limit:    int           = Query(500, ge=1, le=2000),
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    f, scope = await scope_filter(db, current_user)
    items = await list_actions(db, f, status=status, priority=priority,
                                source=source, owner_id=owner_id,
                                only_open=only_open, limit=limit)
    return {"success": True, "items": items, "total": len(items), "scope": scope}


@router.get("/{action_id}")
async def detail_endpoint(
    action_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await get_action(_db(request), action_id)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


# ────────────────────────────────────────────────────────────────────
# MUTATIONS
# ────────────────────────────────────────────────────────────────────
@router.post("")
async def create_endpoint(
    payload: ActionCreate, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await create_action(_db(request), current_user, payload.model_dump(exclude_none=True))
    return {"success": True, "data": a}


@router.patch("/{action_id}")
async def patch_endpoint(
    action_id: str, payload: ActionPatch, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await patch_action(_db(request), action_id, current_user,
                           payload.model_dump(exclude_none=True))
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/assign")
async def assign_endpoint(
    action_id: str, payload: AssignAction, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await assign_action(_db(request), action_id, current_user,
                             owner_id=payload.owner_id, owner_name=payload.owner_name,
                             comment=payload.comment)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/start")
async def start_endpoint(
    action_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await start_action(_db(request), action_id, current_user)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/resolve")
async def resolve_endpoint(
    action_id: str, payload: ResolveAction = Body(default=ResolveAction()),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await resolve_action(_db(request), action_id, current_user,
                              comment=payload.comment, outcome=payload.outcome)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/snooze")
async def snooze_endpoint(
    action_id: str, payload: SnoozeAction, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await snooze_action(_db(request), action_id, current_user,
                              snooze_until=payload.snooze_until, comment=payload.comment)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/escalate")
async def escalate_endpoint(
    action_id: str, payload: EscalateAction = Body(default=EscalateAction()),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await escalate_action(_db(request), action_id, current_user,
                                to_step=payload.to_step,
                                new_owner_id=payload.new_owner_id,
                                new_owner_name=payload.new_owner_name,
                                comment=payload.comment)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/reopen")
async def reopen_endpoint(
    action_id: str, payload: CommentAction = Body(default=CommentAction(comment="Reopened")),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await reopen_action(_db(request), action_id, current_user, comment=payload.comment)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/{action_id}/comment")
async def comment_endpoint(
    action_id: str, payload: CommentAction, request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    a = await comment_action(_db(request), action_id, current_user, comment=payload.comment)
    if not a:
        raise HTTPException(404, "Action not found")
    return {"success": True, "data": a}


@router.post("/sync")
async def sync_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    report = await sync_actions(_db(request), current_user)
    return {"success": True, "data": report}


__all__ = ["router"]
