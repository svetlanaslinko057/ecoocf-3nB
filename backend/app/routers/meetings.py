"""
meetings — /api/meetings HTTP surface  (Phase Final / Block 3)
================================================================

Lightweight meetings entity for BIBI Cars — internal calendar without
Google Calendar / OAuth. Supports .ics export for any external client
(Outlook, Apple Calendar, Google Calendar import).

Resource model
--------------
::

    db.meetings
    {
      id:           "mtg_<10hex>",
      customerId:   str | None,           # at least one of customer/lead/deal
      leadId:       str | None,
      dealId:       str | None,
      managerId:    str,                  # owner (defaults to current user)
      title:        str,                  # short label
      startAt:      ISO8601 (UTC),
      endAt:        ISO8601 (UTC),        # computed from startAt + durationMin if missing
      durationMin:  int = 30,
      meetingType:  "call" | "in_person" | "online" | "other",
      location:     str | None,           # address / Zoom URL / phone
      notes:        str | None,
      # Outcome (filled on completion)
      result:       str | None,
      nextStep:     str | None,
      # Status
      status:       "scheduled" | "completed" | "cancelled" | "no_show",
      completedAt:  ISO8601 | None,
      cancelledAt:  ISO8601 | None,
      # Audit
      created_at:   ISO8601,
      created_by:   str (email),
      updated_at:   ISO8601,
      updated_by:   str (email),
    }
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

from security import require_manager_or_admin, require_user
from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.meetings")

router = APIRouter(prefix="/api/meetings", tags=["meetings"])
customers_router = APIRouter(prefix="/api/customers", tags=["meetings"])

ALLOWED_STATUSES = {"scheduled", "completed", "cancelled", "no_show"}
ALLOWED_TYPES = {"call", "in_person", "online", "other"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    return f"mtg_{uuid.uuid4().hex[:10]}"


def _parse_dt(value: Any) -> Optional[datetime]:
    """Robust ISO8601 parser — accepts trailing 'Z' (UTC)."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, f"Invalid datetime: {value!r}")


def _normalize(data: Dict[str, Any], *, partial: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if "customerId" in data:
        out["customerId"] = (str(data.get("customerId") or "").strip() or None)
    if "leadId" in data:
        out["leadId"] = (str(data.get("leadId") or "").strip() or None)
    if "dealId" in data:
        out["dealId"] = (str(data.get("dealId") or "").strip() or None)
    if "managerId" in data:
        out["managerId"] = (str(data.get("managerId") or "").strip() or None)
    if "title" in data:
        out["title"] = (str(data.get("title") or "").strip() or None)
    if "startAt" in data:
        dt = _parse_dt(data["startAt"])
        out["startAt"] = dt.isoformat() if dt else None
    if "endAt" in data:
        dt = _parse_dt(data["endAt"])
        out["endAt"] = dt.isoformat() if dt else None
    if "durationMin" in data:
        try:
            out["durationMin"] = int(data["durationMin"] or 30)
        except (TypeError, ValueError):
            raise HTTPException(400, "durationMin must be an integer")
    if "meetingType" in data:
        mt = (data.get("meetingType") or "call").strip().lower()
        if mt not in ALLOWED_TYPES:
            raise HTTPException(400, f"meetingType must be one of {sorted(ALLOWED_TYPES)}")
        out["meetingType"] = mt
    if "location" in data:
        out["location"] = (str(data.get("location") or "").strip() or None)
    if "notes" in data:
        out["notes"] = (str(data.get("notes") or "").strip() or None)
    if "result" in data:
        out["result"] = (str(data.get("result") or "").strip() or None)
    if "nextStep" in data:
        out["nextStep"] = (str(data.get("nextStep") or "").strip() or None)
    if "status" in data:
        st = (data.get("status") or "scheduled").strip().lower()
        if st not in ALLOWED_STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(ALLOWED_STATUSES)}")
        out["status"] = st
    if "completedAt" in data:
        out["completedAt"] = data["completedAt"]
    if "cancelledAt" in data:
        out["cancelledAt"] = data["cancelledAt"]
    return out


def _ics_escape(text: str) -> str:
    """Escape per RFC 5545: backslash, comma, semicolon, newline."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _format_ics_dt(dt_iso: str) -> str:
    """ISO → ICS UTC compact format YYYYMMDDTHHMMSSZ."""
    dt = _parse_dt(dt_iso)
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_ics(meeting: Dict[str, Any]) -> str:
    """Render a single VEVENT inside a VCALENDAR."""
    start = _format_ics_dt(meeting.get("startAt") or _now_iso())
    end_iso = meeting.get("endAt")
    if not end_iso:
        # compute from durationMin
        start_dt = _parse_dt(meeting.get("startAt")) or datetime.now(timezone.utc)
        dur = int(meeting.get("durationMin") or 30)
        end_iso = (start_dt + timedelta(minutes=dur)).isoformat()
    end = _format_ics_dt(end_iso)
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = f"{meeting['id']}@bibicars"
    summary = _ics_escape(meeting.get("title") or "BIBI Meeting")
    description_parts: List[str] = []
    if meeting.get("notes"):     description_parts.append(meeting["notes"])
    if meeting.get("nextStep"):  description_parts.append(f"Next step: {meeting['nextStep']}")
    if meeting.get("result"):    description_parts.append(f"Result: {meeting['result']}")
    description = _ics_escape("\n".join(description_parts))
    location = _ics_escape(meeting.get("location") or "")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BIBI Cars//Meetings//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{summary}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if location:
        lines.append(f"LOCATION:{location}")
    status_map = {
        "scheduled": "CONFIRMED",
        "completed": "CONFIRMED",
        "cancelled": "CANCELLED",
        "no_show":   "CANCELLED",
    }
    lines.append(f"STATUS:{status_map.get(meeting.get('status') or 'scheduled', 'CONFIRMED')}")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


# ── HTTP routes ──────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(require_manager_or_admin)])
async def list_meetings(
    customer_id: Optional[str] = Query(None, alias="customerId"),
    manager_id: Optional[str] = Query(None, alias="managerId"),
    status: Optional[str] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    limit: int = 500,
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """List meetings with optional filters. Managers see only their own."""
    db = get_db()
    q: Dict[str, Any] = {}
    role = (current_user.get("role") or "").lower()
    if role == "manager":
        q["managerId"] = current_user.get("id")
    if customer_id:
        q["customerId"] = customer_id
    if manager_id and role != "manager":
        q["managerId"] = manager_id
    if status:
        q["status"] = status.strip().lower()
    if date_from or date_to:
        rng: Dict[str, Any] = {}
        if date_from:
            dt = _parse_dt(date_from)
            if dt:
                rng["$gte"] = dt.isoformat()
        if date_to:
            dt = _parse_dt(date_to)
            if dt:
                rng["$lte"] = dt.isoformat()
        if rng:
            q["startAt"] = rng
    cursor = db.meetings.find(q, {"_id": 0}).sort("startAt", 1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    return {"success": True, "items": items, "count": len(items)}


@router.get("/calendar", dependencies=[Depends(require_manager_or_admin)])
async def calendar_view(
    date_from: str = Query(..., alias="from"),
    date_to: str = Query(..., alias="to"),
    manager_id: Optional[str] = Query(None, alias="managerId"),
    current_user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Calendar-friendly listing in a date range."""
    return await list_meetings(
        customer_id=None,
        manager_id=manager_id,
        status=None,
        date_from=date_from,
        date_to=date_to,
        limit=2000,
        current_user=current_user,
    )


@router.get("/{meeting_id}", dependencies=[Depends(require_user)])
async def get_meeting(meeting_id: str):
    db = get_db()
    doc = await db.meetings.find_one({"id": meeting_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Meeting not found")
    return {"success": True, "meeting": doc}


@router.get("/{meeting_id}/ics")
async def download_ics(meeting_id: str):
    """Public .ics download for one meeting (no auth — link can be sent
    via email and opened in any calendar app)."""
    db = get_db()
    doc = await db.meetings.find_one({"id": meeting_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Meeting not found")
    ics = _build_ics(doc)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=meeting-{meeting_id}.ics"},
    )


@router.post("", dependencies=[Depends(require_manager_or_admin)])
async def create_meeting(
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = get_db()
    payload = _normalize(data, partial=False)

    if not payload.get("title"):
        raise HTTPException(400, "title is required")
    if not payload.get("startAt"):
        raise HTTPException(400, "startAt is required")
    if not any([payload.get("customerId"), payload.get("leadId"), payload.get("dealId")]):
        raise HTTPException(400, "At least one of customerId / leadId / dealId is required")

    # Compute endAt from durationMin if not provided
    if not payload.get("endAt"):
        dur = int(payload.get("durationMin") or 30)
        start = _parse_dt(payload["startAt"])
        payload["endAt"] = (start + timedelta(minutes=dur)).isoformat() if start else None

    doc = {
        "id": _gen_id(),
        "customerId": payload.get("customerId"),
        "leadId": payload.get("leadId"),
        "dealId": payload.get("dealId"),
        "managerId": payload.get("managerId") or user.get("id"),
        "title": payload["title"],
        "startAt": payload["startAt"],
        "endAt": payload.get("endAt"),
        "durationMin": payload.get("durationMin") or 30,
        "meetingType": payload.get("meetingType") or "call",
        "location": payload.get("location"),
        "notes": payload.get("notes"),
        "result": None,
        "nextStep": None,
        "status": payload.get("status") or "scheduled",
        "completedAt": None,
        "cancelledAt": None,
        "created_at": _now_iso(),
        "created_by": user.get("email") or user.get("id"),
        "updated_at": _now_iso(),
        "updated_by": user.get("email") or user.get("id"),
    }
    await db.meetings.insert_one(doc)
    doc.pop("_id", None)

    # Timeline event
    if doc.get("customerId"):
        try:
            from app.services.customer_timeline import record_event
            await record_event(
                customer_id=doc["customerId"],
                kind="meeting_scheduled",
                title=f"Meeting scheduled — {doc['title']}",
                body=f"At {doc['startAt']}",
                ref={"meeting_id": doc["id"]},
                actor={"id": user.get("id"), "email": user.get("email")},
                meta={"meetingType": doc["meetingType"], "startAt": doc["startAt"]},
            )
        except Exception:
            logger.debug("[meetings] timeline write skipped", exc_info=True)

    return {"success": True, "meeting": doc}


@router.patch("/{meeting_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_meeting(
    meeting_id: str,
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = get_db()
    upd = _normalize(data, partial=True)
    if not upd:
        raise HTTPException(400, "Nothing to update")
    upd["updated_at"] = _now_iso()
    upd["updated_by"] = user.get("email") or user.get("id")

    # Status side effects
    if upd.get("status") == "completed" and not upd.get("completedAt"):
        upd["completedAt"] = _now_iso()
    if upd.get("status") == "cancelled" and not upd.get("cancelledAt"):
        upd["cancelledAt"] = _now_iso()

    res = await db.meetings.update_one({"id": meeting_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(404, "Meeting not found")

    doc = await db.meetings.find_one({"id": meeting_id}, {"_id": 0})

    # Timeline event for completion / cancellation
    if doc.get("customerId") and upd.get("status") in ("completed", "cancelled"):
        try:
            from app.services.customer_timeline import record_event
            kind = "meeting_completed" if upd["status"] == "completed" else "meeting_cancelled"
            await record_event(
                customer_id=doc["customerId"],
                kind=kind,
                title=f"Meeting {upd['status']} — {doc.get('title')}",
                body=doc.get("result") or doc.get("notes"),
                ref={"meeting_id": doc["id"]},
                actor={"id": user.get("id"), "email": user.get("email")},
                meta={"nextStep": doc.get("nextStep")},
            )
        except Exception:
            logger.debug("[meetings] timeline write skipped", exc_info=True)

    return {"success": True, "meeting": doc}


@router.delete("/{meeting_id}", dependencies=[Depends(require_manager_or_admin)])
async def delete_meeting(
    meeting_id: str,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Soft-cancel a meeting."""
    db = get_db()
    res = await db.meetings.update_one(
        {"id": meeting_id},
        {"$set": {
            "status": "cancelled",
            "cancelledAt": _now_iso(),
            "updated_at": _now_iso(),
            "updated_by": user.get("email") or user.get("id"),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Meeting not found")
    return {"success": True}


# ── Customer-scoped read ─────────────────────────────────────────────


@customers_router.get("/{customer_id}/meetings", dependencies=[Depends(require_user)])
async def list_customer_meetings(customer_id: str):
    db = get_db()
    cursor = db.meetings.find({"customerId": customer_id}, {"_id": 0}).sort("startAt", -1)
    items = await cursor.to_list(length=500)
    return {"success": True, "items": items, "count": len(items)}


__all__ = ["router", "customers_router"]
