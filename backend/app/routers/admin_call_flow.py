"""
admin_call_flow — /api/admin/call-flow/* HTTP surface
======================================================

Wave 2B / Batch 5 / Commit 11 (SOLO).

Mechanical 1:1 extraction from server.py — 4 service-only stub
endpoints with **zero bridge edges**: no `db`, no `serialize_doc`,
no module-level state, no scraper/worker dependency.

Originally located at:
    server.py:6798 — GET  /api/admin/call-flow/board
    server.py:6802 — GET  /api/admin/call-flow/due
    server.py:6806 — GET  /api/admin/call-flow/stats
    server.py:15031 — GET /api/admin/call-flow/session/{session_id}

Implementations preserved byte-for-byte (response shapes verified
against pre-extraction OpenAPI schema).

Why this router graduates Phase 2 by construction:
  * zero `import server` whatsoever
  * zero own helpers (all four endpoints are inline literals)
  * zero Mongo collection ownership (service-only stubs)
  * zero coupling to Cluster #1 operational core

Auth: hoisted onto router-level via
    APIRouter(prefix=..., dependencies=[Depends(require_admin)])
matching the Wave 2B Batch 1/3 zero-bridge pattern.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from security import require_admin

router = APIRouter(
    prefix="/api/admin/call-flow",
    tags=["admin-call-flow"],
    dependencies=[Depends(require_admin)],
)


@router.get("/board")
async def call_flow_board():
    return {"calls": []}


@router.get("/due")
async def call_flow_due():
    return {"dueCalls": []}


@router.get("/stats")
async def call_flow_stats():
    return {"totalCalls": 0, "completedCalls": 0}


@router.get("/session/{session_id}")
async def call_flow_session(session_id: str):
    """Get call flow session"""
    return {"success": True, "data": {"sessionId": session_id, "events": []}}
