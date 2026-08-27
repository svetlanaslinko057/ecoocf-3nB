"""
admin_calculator_visibility — /api/admin/calculator/visibility surface.
Phase Final / Block 5.
"""
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Body, Depends, HTTPException

from security import require_admin, require_master_admin
from app.services.calculator_visibility import (
    load_overrides, save_overrides, ALLOWED_VISIBILITIES,
)

router = APIRouter(prefix="/api/admin/calculator/visibility", tags=["admin-calculator"])


@router.get("", dependencies=[Depends(require_admin)])
async def get_visibility_overrides():
    overrides = await load_overrides()
    return {"success": True, "overrides": overrides, "allowed": sorted(ALLOWED_VISIBILITIES)}


@router.put("", dependencies=[Depends(require_master_admin)])
async def put_visibility_overrides(
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_master_admin),
):
    overrides = data.get("overrides") or {}
    if not isinstance(overrides, dict):
        raise HTTPException(400, "overrides must be an object")
    try:
        doc = await save_overrides(overrides, updated_by=user.get("email") or user.get("id"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "overrides": doc["overrides"]}
