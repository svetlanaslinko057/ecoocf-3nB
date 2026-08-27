"""
BIBI Cars — Wave 16 — Executive Center HTTP surface
=====================================================

Mounted at `/api/executive/*`. All endpoints are read-only and scope-aware.
"""
from __future__ import annotations
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave16.aggregations import (
    compute_executive_bottlenecks,
    compute_executive_dashboard,
    compute_executive_forecast,
    compute_executive_risks,
    compute_executive_team,
)

logger = logging.getLogger("bibi.wave16")
router = APIRouter(prefix="/api/executive", tags=["Wave16:ExecutiveCenter"])

from security import require_user  # type: ignore


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


@router.get("/dashboard")
async def dashboard_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    data = await compute_executive_dashboard(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/forecast")
async def forecast_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    data = await compute_executive_forecast(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/bottlenecks")
async def bottlenecks_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    data = await compute_executive_bottlenecks(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/risks")
async def risks_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    data = await compute_executive_risks(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/team")
async def team_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user),
):
    data = await compute_executive_team(_db(request), current_user)
    return {"success": True, "data": data}


__all__ = ["router"]
