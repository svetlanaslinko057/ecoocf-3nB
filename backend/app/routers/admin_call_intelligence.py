"""
admin_call_intelligence — /api/admin/calls/*/intelligence surface
==================================================================

Wave 2A-CI (Jul 12, 2026) — Call Intelligence endpoints backing the
CRM's Lead360 / Customer360 → Calls drawer.

Endpoints
---------
  POST  /api/admin/calls/{call_id}/intelligence/process   — trigger pipeline
  GET   /api/admin/calls/{call_id}/intelligence           — read cached data
  POST  /api/admin/calls/{call_id}/intelligence/apply     — apply suggestions
  GET   /api/admin/calls/intelligence/stats               — manager rollup

All endpoints require an authenticated admin (require_admin) — the same
security posture as the rest of the /api/admin/* surface.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from security import require_admin, require_manager_or_admin

from app.services import call_intelligence as ci_service

logger = logging.getLogger("bibi.admin_call_intelligence")


router = APIRouter(prefix="/api/admin/calls", tags=["admin-call-intelligence"])


def _db():
    """Lazy Mongo handle bridge — same pattern as sibling admin_* routers."""
    from app.core.db_runtime import get_db
    return get_db()


def _serialize(obj: Any) -> Any:
    """Recursively coerce Mongo/datetime objects into JSON-safe primitives."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items() if not k.startswith("_id_bin")}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


# ─────────────────────────── PROCESS ─────────────────────────────────

class ProcessBody(BaseModel):
    force: bool = Field(False, description="Re-run even if intelligence is cached")


@router.post("/{call_id}/intelligence/process")
async def process_call_endpoint(
    call_id: str,
    body: ProcessBody = Body(default_factory=ProcessBody),
    _user=Depends(require_manager_or_admin),
):
    """Kick off (or replay) the transcription + analysis pipeline."""
    db = _db()
    try:
        result = await ci_service.process_call(db, call_id, force=body.force)
    except Exception as e:  # noqa: BLE001
        logger.exception("[call-intel] process failed for call_id=%s", call_id)
        raise HTTPException(status_code=500, detail=str(e))
    return _serialize(result)


class BulkProcessBody(BaseModel):
    call_ids: List[str] = Field(default_factory=list, description="Calls to transcribe + analyse")
    force: bool = Field(False, description="Re-run even if intelligence is cached")


@router.post("/intelligence/bulk-process")
async def bulk_process_endpoint(
    body: BulkProcessBody,
    _user=Depends(require_manager_or_admin),
):
    """Transcribe + analyse several calls in one request (on-demand).

    Runs sequentially to stay gentle on the LLM gateway. Returns a per-call
    outcome list so the UI can mark each row.
    """
    db = _db()
    ids = [c for c in (body.call_ids or []) if c][:50]  # hard cap per batch
    if not ids:
        raise HTTPException(status_code=400, detail="call_ids is required")
    results: List[Dict[str, Any]] = []
    ok = 0
    for cid in ids:
        try:
            r = await ci_service.process_call(db, cid, force=body.force)
            if r.get("success"):
                ok += 1
            results.append({"call_id": cid, "success": bool(r.get("success")),
                            "error": r.get("error"), "cached": r.get("cached", False)})
        except Exception as e:  # noqa: BLE001
            logger.exception("[call-intel] bulk process failed for %s", cid)
            results.append({"call_id": cid, "success": False, "error": str(e)})
    return {"success": True, "processed": len(ids), "succeeded": ok,
            "failed": len(ids) - ok, "results": results}


# ─────────────────────────── READ ────────────────────────────────────

@router.get("/{call_id}/intelligence")
async def get_call_intelligence(
    call_id: str,
    _user=Depends(require_manager_or_admin),
):
    """Return the cached intelligence + transcript for a call.

    Response shape::

        {
          "call_id":          str,
          "status":           "ready" | "pending" | "failed" | "no_recording" | "not_started",
          "intelligence":     { summary, next_actions, ... } | null,
          "transcript":       { full_text, language, ... }   | null,
          "recording_available": bool,
          "auto_task_id":     str | null,   // populated when auto-follow-up task exists
        }
    """
    db = _db()
    call = await db.ringostat_calls.find_one({"call_id": call_id}) or \
           await db.ringostat_calls.find_one({"_id": call_id})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    tr = await db.call_transcripts.find_one({"call_id": call_id})
    ci = await db.call_intelligence.find_one({"call_id": call_id})

    task = await db.tasks.find_one({
        "call_id": call_id,
        "source":  "ai_call_ci",
    })
    return _serialize({
        "call_id": call_id,
        "status": call.get("intelligence_status") or ("not_started" if not ci else "ready"),
        "error":  call.get("intelligence_error"),
        "transcription_status": call.get("transcription_status"),
        "recording_available": bool(call.get("recording_url")),
        "recording_url": call.get("recording_url"),
        "intelligence": ci,
        "transcript":   tr,
        "auto_task_id": (task or {}).get("_id") or (task or {}).get("id"),
    })


# ─────────────────────────── APPLY ───────────────────────────────────

class ApplyBody(BaseModel):
    """Manager-confirmed application of AI suggestions to CRM entities."""
    create_task: bool = Field(False, description="Create a follow-up task")
    task_title:  Optional[str] = None
    task_due_at: Optional[str] = None  # ISO-8601 or YYYY-MM-DD
    update_lead: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Partial update payload for the linked lead (e.g. {\"stage\": \"qualified\"})",
    )
    add_note:    Optional[str] = None


@router.post("/{call_id}/intelligence/apply")
async def apply_suggestions(
    call_id: str,
    body: ApplyBody,
    user=Depends(require_manager_or_admin),
):
    """Materialise AI suggestions the manager accepted.

    Only performs the actions the manager ticked — never mutates blindly.
    Returns a small summary of what was applied.
    """
    db = _db()
    call = await db.ringostat_calls.find_one({"call_id": call_id}) or \
           await db.ringostat_calls.find_one({"_id": call_id})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    ci = await db.call_intelligence.find_one({"call_id": call_id}) or {}
    now = datetime.now(timezone.utc)
    applied: Dict[str, Any] = {}

    # 1) Create a follow-up task
    if body.create_task:
        title = body.task_title or (
            ((ci.get("next_actions") or [{}])[0].get("action") if ci.get("next_actions") else None)
            or f"Follow up on call {call_id}"
        )
        due_at = now + timedelta(days=2)
        if body.task_due_at:
            try:
                due_at = datetime.fromisoformat(body.task_due_at.replace("Z", "+00:00"))
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        task_doc = {
            "_id":         str(uuid.uuid4()),
            "id":          str(uuid.uuid4()),
            "type":        "follow_up",
            "source":      "ai_call_ci_manual",
            "title":       title[:200],
            "description": ci.get("summary") or "",
            "call_id":     call_id,
            "lead_id":     call.get("lead_id"),
            "leadId":      call.get("lead_id"),
            "deal_id":     call.get("deal_id"),
            "customer_id": call.get("customer_id"),
            "customerId":  call.get("customer_id"),
            "assignee_id": call.get("manager_id") or user.get("id"),
            "assigneeId":  call.get("manager_id") or user.get("id"),
            "status":      "pending",
            "priority":    "high" if ci.get("purchase_intent") in ("high", "very_high") else "medium",
            "due_at":      due_at,
            "dueDate":     due_at,
            "deadline":    due_at,
            "created_at":  now,
            "updated_at":  now,
            "created_by":  user.get("id"),
        }
        await db.tasks.insert_one(task_doc)
        applied["task_id"] = task_doc["_id"]

    # 2) Partial lead update — restricted to a safe allow-list
    if body.update_lead and call.get("lead_id"):
        SAFE = {"stage", "status", "carOfInterest", "budget", "priority", "notes"}
        patch = {k: v for k, v in body.update_lead.items() if k in SAFE}
        if patch:
            patch["updatedAt"] = now
            await db.leads.update_one({"_id": call["lead_id"]}, {"$set": patch})
            applied["lead_patch"] = patch

    # 3) Free-form note appended to the call & (if any) linked lead
    if body.add_note:
        note_doc = {
            "_id":       str(uuid.uuid4()),
            "call_id":   call_id,
            "lead_id":   call.get("lead_id"),
            "author_id": user.get("id"),
            "text":      body.add_note[:2000],
            "created_at": now,
            "source":    "ai_call_ci_apply",
        }
        await db.call_notes.insert_one(note_doc)
        applied["note_id"] = note_doc["_id"]

    return {"success": True, "applied": applied, "applied_at": now.isoformat()}


# ─────────────────────────── STATS ───────────────────────────────────

@router.get("/intelligence/stats")
async def intelligence_stats(
    manager_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=180),
    _user=Depends(require_manager_or_admin),
):
    """Coaching / deal-risk rollup for a manager (or the entire team)."""
    db = _db()
    stats = await ci_service.manager_stats(db, manager_id=manager_id, days=days)
    return {"success": True, "stats": stats}


@router.get("/intelligence/config")
async def intelligence_config(user=Depends(require_manager_or_admin)):
    """Return whether OpenAI is configured (without revealing the key).

    All staff roles (admin/team_lead/manager) can read this — only admins
    can WRITE the key (via /api/admin/integrations/openai, which is guarded
    by ``require_admin`` in ``admin_integrations.py``).

    The frontend uses this to decide whether to show a "Configure OpenAI"
    call-to-action inside the CallDrawer instead of the Process button.
    """
    key = await ci_service.resolve_api_key()
    role = (user.get("role") or "").lower()
    is_admin_role = role in {"admin", "owner", "master_admin"}
    # Prefer DB-persisted admin settings; fall back to environment defaults.
    transcribe_model = await ci_service.resolve_transcribe_model()
    analyze_model    = await ci_service.resolve_analyze_model()
    transcribe_lang  = await ci_service.resolve_transcribe_language()
    key_source = "none"
    if key:
        key_source = "emergent" if ci_service._is_emergent_key(key) else "openai"
    return {
        "success": True,
        "openai_configured": bool(key),
        "key_source": key_source,  # "openai" (production) | "emergent" (MR Gate) | "none"
        "transcribe_model":     transcribe_model,
        "analyze_model":        analyze_model,
        "transcribe_language":  transcribe_lang or "auto",
        "supported_languages":  sorted(list(ci_service._SUPPORTED_LANGUAGES)),
        "auto_process":     (os.environ.get("CALL_INTELLIGENCE_AUTO_PROCESS", "true").lower()
                             in ("1", "true", "yes", "on")),
        "auto_create_task": ci_service._auto_create_task_enabled(),
        "role": role,
        "can_configure_key": is_admin_role,
    }


@router.get("/intelligence/recent")
async def intelligence_recent(
    manager_id: Optional[str] = Query(None, description="Filter by manager (team_lead/admin only for other managers)"),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_manager_or_admin),
):
    """Return the last N analyzed calls (feed for CI dashboards).

    Access rules:
      * admin / master_admin / team_lead → see everyone (any ``manager_id``)
      * manager                          → forcibly scoped to their own id

    Each item includes compact metadata + transcript preview + AI verdict
    so the Ringostat CI tab (and future Customer 360 rollups) can render
    a row without extra requests.
    """
    role = (user.get("role") or "").lower()
    scoped_manager_id: Optional[str] = manager_id
    if role in {"manager", "moderator"}:
        # Non-supervisors only see their own calls.
        scoped_manager_id = user.get("id") or user.get("managerId")
    items = await ci_service.recent_analyzed_calls(
        _db(),
        manager_id=scoped_manager_id,
        limit=limit,
    )
    return {"success": True, "items": items, "count": len(items)}


@router.get("/intelligence/at-risk")
async def calls_at_risk(
    days: int = Query(14, ge=1, le=180),
    limit: int = Query(20, ge=1, le=100),
    manager_id: Optional[str] = Query(None, description="Filter to one manager"),
    user=Depends(require_manager_or_admin),
):
    """Manager coaching feed: negative-sentiment OR high-intent calls that
    have no next_action yet — i.e. deals at risk that need a follow-up.

    Each item is enriched with call metadata + a suggested next step so the
    supervisor can act (create a task) without opening the drawer.
    """
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    role = (user.get("role") or "").lower()
    scoped_manager = manager_id
    if role in {"manager", "moderator"}:
        scoped_manager = user.get("id") or user.get("managerId")

    match: Dict[str, Any] = {
        "created_at": {"$gte": since},
        "$or": [
            # High intent but nobody planned a next step ⇒ at risk of stalling
            {"purchase_intent": {"$in": ["high", "very_high"]},
             "$or": [{"next_actions": {"$exists": False}}, {"next_actions": {"$size": 0}}]},
            # Explicit negative sentiment ⇒ needs coaching / recovery
            {"sentiment": "negative"},
        ],
    }
    if scoped_manager:
        match["manager_id"] = scoped_manager

    cursor = db.call_intelligence.find(match).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)

    # Enrich with call metadata (direction / started_at / manager_name) + a
    # human "suggested next step".
    call_ids = [it.get("call_id") for it in items if it.get("call_id")]
    calls_by_id: Dict[str, Dict[str, Any]] = {}
    if call_ids:
        async for c in db.ringostat_calls.find(
            {"call_id": {"$in": call_ids}},
            {"_id": 0, "call_id": 1, "direction": 1, "duration": 1, "started_at": 1,
             "startedAt": 1, "manager_id": 1, "manager_name": 1, "number": 1,
             "from_number": 1, "recording_url": 1}):
            calls_by_id[c["call_id"]] = c

    out: List[Dict[str, Any]] = []
    for it in items:
        c = calls_by_id.get(it.get("call_id") or "") or {}
        na = it.get("next_actions") or []
        if na and isinstance(na[0], dict) and na[0].get("action"):
            suggested = na[0]["action"]
        elif it.get("sentiment") == "negative":
            suggested = "Передзвонити клієнту та відпрацювати заперечення"
        else:
            suggested = "Створити завдання-follow-up та надіслати пропозицію"
        out.append({
            "call_id": it.get("call_id"),
            "manager_id": it.get("manager_id") or c.get("manager_id"),
            "manager_name": c.get("manager_name"),
            "summary": it.get("summary") or "",
            "sentiment": it.get("sentiment"),
            "purchase_intent": it.get("purchase_intent"),
            "deal_probability": it.get("deal_probability"),
            "objections": it.get("objections") or [],
            "risks": it.get("risks") or [],
            "suggested_next_step": suggested,
            "direction": c.get("direction"),
            "number": c.get("number") or c.get("from_number"),
            "started_at": c.get("startedAt") or c.get("started_at"),
            "created_at": it.get("created_at"),
            "recording_available": bool(c.get("recording_url")),
        })
    return {"success": True, "items": _serialize(out), "count": len(out)}
