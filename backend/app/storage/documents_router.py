"""/api/documents/* — document lifecycle + version history surface.

Kept separate from the legacy /api/storage/files/* router so we don't risk
breaking existing callers. Two endpoints:

  GET  /api/documents/{entity_type}/{entity_id}
       -> {lifecycle:{status,history,available,labels}, versions:[...], latest:{...}}

  POST /api/documents/{entity_type}/{entity_id}/transition
       Body: {to_status, note?}
       -> validates the move against the per-type state machine and stamps it.

Additionally guards pickup completion: any attempt to transition a
``pickup`` document to ``signed`` (which we treat as 'closed') is blocked
unless the photo-checklist required stages are present.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.db_runtime import get_db
from app.storage.files_repo import FileRepository
from app.storage.lifecycle import LifecycleRepository, LIFECYCLES, labels_for
from app.storage.photo_workflow import checklist as photo_checklist

try:
    from security import require_user, require_manager_or_admin  # type: ignore
except Exception:  # pragma: no cover
    require_user = require_manager_or_admin = lambda: None  # type: ignore

router = APIRouter(prefix="/api/document-lifecycle", tags=["documents"])

VALID_TYPES = set(LIFECYCLES.keys())


def _ensure_type(entity_type: str) -> str:
    et = (entity_type or "").strip().lower()
    if et not in VALID_TYPES:
        raise HTTPException(400, f"Невідомий тип документа. Допустимі: {', '.join(sorted(VALID_TYPES))}")
    return et


def _decorate(rec: Dict[str, Any]) -> Dict[str, Any]:
    if not rec:
        return rec
    r = {k: v for k, v in rec.items() if k != "_id"}
    fid = r.get("id")
    r["url"] = f"/api/storage/files/{fid}/view"
    r["download_url"] = f"/api/storage/files/{fid}/download"
    return r


@router.get("/lifecycles", dependencies=[Depends(require_user)])
async def lifecycles():
    """Return all lifecycle definitions (for UI dropdowns)."""
    return {
        "success": True,
        "items": [{"entity_type": et, "states": LIFECYCLES[et], "labels": labels_for(et)} for et in sorted(LIFECYCLES)],
    }


@router.get("/{entity_type}/{entity_id}", dependencies=[Depends(require_user)])
async def get_document(entity_type: str, entity_id: str):
    et = _ensure_type(entity_type)
    db = get_db()
    lc = await LifecycleRepository(db).get(et, entity_id)
    repo = FileRepository(db)
    versions = [_decorate(v) for v in await repo.versions(et, entity_id, purpose="pdf")]
    versions.sort(key=lambda r: int(r.get("version") or 0), reverse=True)
    latest = next((v for v in versions if v.get("status") == "active"), versions[0] if versions else None)
    return {
        "success": True,
        "entity_type": et,
        "entity_id": entity_id,
        "lifecycle": lc,
        "versions": versions,
        "latest": latest,
    }


@router.post("/{entity_type}/{entity_id}/transition", dependencies=[Depends(require_manager_or_admin)])
async def transition(
    entity_type: str,
    entity_id: str,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    et = _ensure_type(entity_type)
    to_state = (body.get("to_status") or body.get("toStatus") or "").strip().lower()
    if not to_state:
        raise HTTPException(400, "Потрібен параметр to_status")
    note = body.get("note")
    db = get_db()
    # Pickup closure guard: cannot move to signed ("closed") without the
    # required photo stages (before_loading / after_loading / signed_act).
    if et == "pickup" and to_state in ("signed", "archived"):
        ck = await photo_checklist(db, entity_id)
        if not ck.get("can_close"):
            raise HTTPException(
                409,
                {
                    "detail": "Не можна закрити вивіз — відсутні обов'язкові фото",
                    "missing": ck.get("missing"),
                    "required": ck.get("required"),
                },
            )
    ok, new = await LifecycleRepository(db).transition(
        et, entity_id, to_state=to_state,
        by=(user or {}).get("email") or (user or {}).get("id"), note=note,
    )
    if not ok:
        raise HTTPException(409, {
            "detail": "Неприпустимий перехід статусу",
            "current": new.get("status"),
            "requested": to_state,
            "available": list(LIFECYCLES.get(et, ())),
        })
    return {"success": True, "lifecycle": new}


__all__ = ["router"]
