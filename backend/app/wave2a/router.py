"""Wave 2A — Calls Foundation router (read-only, ACL-aware).

Mounted at ``/api`` via ``include_router(..., prefix='/api')``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse, Response

from security import require_user

from app.wave2a import calls_aggregator as ca

logger = logging.getLogger("bibi.wave2a.router")
router = APIRouter()


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


def _actor(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":     user.get("id") or user.get("_id"),
        "email":  user.get("email"),
        "role":   (user.get("role") or "").lower(),
        "name":   user.get("name"),
        "teamId": user.get("teamId"),
    }


# ─────────── GET /api/customers/{customer_id}/calls ────────────────────────
@router.get("/customers/{customer_id}/calls")
async def get_customer_calls(
    request: Request,
    customer_id: str = Path(...),
    dateFrom:      Optional[str] = Query(None, description="ISO-8601 start datetime"),
    dateTo:        Optional[str] = Query(None, description="ISO-8601 end datetime"),
    managerId:     Optional[str] = Query(None),
    direction:     Optional[str] = Query(None, description="inbound | outbound"),
    withRecording: bool = Query(False),
    limit:         int = Query(200, ge=1, le=500),
    skip:          int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    actor = _actor(user)
    filters = {
        "dateFrom":      dateFrom,
        "dateTo":        dateTo,
        "managerId":     managerId,
        "direction":     direction,
        "withRecording": withRecording,
        "limit":         limit,
        "skip":          skip,
    }
    result = await ca.aggregate_customer_calls(db, customer_id, filters, actor)
    if not result.get("success"):
        raise HTTPException(
            status_code=result.get("status", 400),
            detail=result.get("error") or "failed",
        )
    return result


# ─────────── GET /api/calls/{call_id}/recording ────────────────────────────
# Proxy streams the audio file. Range header is forwarded so the
# HTML5 <audio> element can seek and the client doesn't have to know the
# upstream Ringostat URL.
_CHUNK_SIZE = 64 * 1024


@router.get("/calls/{call_id}/recording", operation_id="proxy_call_recording_get")
@router.head("/calls/{call_id}/recording", operation_id="proxy_call_recording_head")
async def proxy_call_recording(
    request: Request,
    call_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    actor = _actor(user)
    call = await ca.get_call_for_recording(db, call_id, actor)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found or forbidden")
    recording_url = (call.get("recording_url") or "").strip()
    if not recording_url:
        raise HTTPException(status_code=404, detail="Recording not available")

    forward_headers: Dict[str, str] = {}
    rng = request.headers.get("range")
    if rng:
        forward_headers["Range"] = rng

    # HEAD support — quick metadata probe (used by some players).
    method = request.method.upper()
    try:
        if method == "HEAD":
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                upstream = await client.head(recording_url, headers=forward_headers)
            out_headers = _pick_proxy_headers(upstream.headers)
            return Response(status_code=upstream.status_code, headers=out_headers)

        # GET path — stream chunks back to the client.
        client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        upstream_req = client.build_request("GET", recording_url, headers=forward_headers)
        upstream = await client.send(upstream_req, stream=True)
        if upstream.status_code >= 400:
            try:
                await upstream.aread()
            except Exception:
                pass
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=502,
                detail=f"Upstream recording fetch failed: {upstream.status_code}",
            )

        async def _iterator():
            try:
                async for chunk in upstream.aiter_bytes(_CHUNK_SIZE):
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        out_headers = _pick_proxy_headers(upstream.headers)
        return StreamingResponse(
            _iterator(),
            status_code=upstream.status_code,
            headers=out_headers,
            media_type=out_headers.get("Content-Type", "audio/mpeg"),
        )
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.warning("[w2a] recording proxy upstream error call=%s: %s", call_id, e)
        raise HTTPException(status_code=502, detail="Recording proxy upstream error")
    except Exception as e:
        logger.exception("[w2a] recording proxy unexpected error call=%s: %s", call_id, e)
        raise HTTPException(status_code=500, detail="Recording proxy failed")


def _pick_proxy_headers(src) -> Dict[str, str]:
    """Pick only safe headers from upstream and add no-cache controls."""
    allowed = {"content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified"}
    out: Dict[str, str] = {}
    for k, v in src.items():
        if k.lower() in allowed:
            out[k] = v
    out.setdefault("Accept-Ranges", "bytes")
    out.setdefault("Content-Type", "audio/mpeg")
    out["Cache-Control"] = "private, max-age=600"
    return out


# ─────────── Startup hook (indexes) ────────────────────────────────────────
async def on_startup(db) -> None:
    await ca.ensure_indexes(db)


# ─────────── Admin diagnostics: WHY did calls match this customer? ────────
_ADMIN_ROLES = {"owner", "master_admin", "admin"}


# ─────────── Доопр #18 — Manual call notes & manager score (no AI) ─────
from fastapi import Body  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


@router.patch("/calls/{call_id}/notes")
async def patch_call_notes(
    request: Request,
    call_id: str = Path(...),
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_user),
):
    """Save the manager's per-call comment and score (1–10).

    Stored in `call_notes` collection — keyed by call_id — and joined into
    the calls feed by `calls_aggregator`. AI fields are intentionally
    omitted (client said: drop AI conversation analysis from scope).
    """
    db = _db(request)
    score = payload.get("score")
    if score is not None:
        try:
            score = int(score)
            if not (1 <= score <= 10):
                raise ValueError()
        except Exception:
            raise HTTPException(400, "score must be an integer 1–10")
    doc = {
        "call_id":  call_id,
        "comment":  (payload.get("comment") or "").strip()[:5000],
        "score":    score,
        "updated_by": user.get("id") or user.get("email"),
        "updated_by_name": user.get("name") or user.get("email"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.call_notes.update_one(
        {"call_id": call_id},
        {"$set": doc},
        upsert=True,
    )
    return {"success": True, "data": doc}


@router.get("/calls/{call_id}/notes")
async def get_call_notes(
    request: Request,
    call_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    doc = await db.call_notes.find_one({"call_id": call_id}, {"_id": 0})
    return {"success": True, "data": doc or {"call_id": call_id, "comment": "", "score": None}}


@router.get("/admin/customers/{customer_id}/calls/diagnostics")
async def admin_call_matching_diagnostics(
    request: Request,
    customer_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_user),
):
    """Admin-only troubleshooting endpoint.

    Returns the full set of identifiers the system uses to match calls to
    a customer (customer ids, lead ids, deal ids, phones split by primary /
    secondary / lead-origin), per-key match counters and a 50-call sample
    with the *reason* each call was attributed.
    """
    actor = _actor(user)
    if actor["role"] not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    db = _db(request)
    result = await ca.build_diagnostics(db, customer_id, actor)
    if not result.get("success"):
        raise HTTPException(
            status_code=result.get("status", 400),
            detail=result.get("error") or "failed",
        )
    return result
