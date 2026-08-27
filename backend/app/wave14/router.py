"""BIBI Cars — Wave 14 — Operations 360 HTTP surface.

All endpoints are read-only and scope-aware (admin = all, team_lead = team,
manager = own).
"""
from __future__ import annotations
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave14.aggregations import (
    compute_company_dashboard,
    compute_bottlenecks,
    compute_team_performance,
    compute_sla,
    compute_risk_center,
)

logger = logging.getLogger("bibi.wave14")
router = APIRouter(prefix="/api/operations", tags=["Wave14:Operations360"])

from security import require_user  # type: ignore


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


@router.get("/dashboard")
async def dashboard_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_company_dashboard(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/bottlenecks")
async def bottlenecks_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_bottlenecks(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/team")
async def team_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_team_performance(_db(request), current_user)
    return {"success": True, **data}


@router.get("/sla")
async def sla_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_sla(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/risk")
async def risk_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_risk_center(_db(request), current_user)
    return {"success": True, **data}


__all__ = ["router"]
