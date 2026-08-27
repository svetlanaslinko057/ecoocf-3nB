"""BIBI Cars — Wave 12C — Forecasting 360 HTTP surface.

All endpoints are read-only and scope-aware (admin = all, team_lead = team,
manager = own).
"""
from __future__ import annotations
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave12.forecasting import (
    compute_forecast_overview,
    compute_revenue_forecast,
    compute_cashflow_forecast,
    compute_pipeline_forecast,
    compute_capacity_forecast,
    compute_forecast_risk,
)

logger = logging.getLogger("bibi.wave12c")
router = APIRouter(prefix="/api/forecast", tags=["Wave12C:Forecasting360"])

from security import require_user  # type: ignore


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


@router.get("/overview")
async def overview_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_forecast_overview(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/revenue")
async def revenue_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_revenue_forecast(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/cash-flow")
async def cashflow_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_cashflow_forecast(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/pipeline")
async def pipeline_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_pipeline_forecast(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/capacity")
async def capacity_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_capacity_forecast(_db(request), current_user)
    return {"success": True, "data": data}


@router.get("/risk")
async def risk_endpoint(request: Request, current_user: Dict[str, Any] = Depends(require_user)):
    data = await compute_forecast_risk(_db(request), current_user)
    return {"success": True, "data": data}


__all__ = ["router"]
