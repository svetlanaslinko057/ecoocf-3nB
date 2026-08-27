"""
BIBI Cars — Block 7.1 — Change History HTTP router
====================================================

Endpoints
---------

  GET /api/customers/{id}/change-history
  GET /api/leads/{id}/change-history
  GET /api/deals/{id}/change-history

All three are role-gated: staff (any) can read history for entities they
can already see. The history collection is internal-only; customers
never see it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from security import require_user
from app.services import change_history as svc

logger = logging.getLogger("bibi.change_history.router")
router = APIRouter()


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


def _role(user: Dict[str, Any]) -> str:
    return (user.get("role") or "").lower()


def _allowed_staff(user: Dict[str, Any]) -> bool:
    return _role(user) in {"owner", "master_admin", "admin", "team_lead", "manager"}


async def _can_view_lead(db, lead_id: str, user: Dict[str, Any]) -> None:
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0, "managerId": 1})
    if not lead:
        raise HTTPException(404, "Lead not found")
    role = _role(user)
    if role in {"owner", "master_admin", "admin", "team_lead"}:
        return
    if role == "manager" and lead.get("managerId") == (user.get("id") or user.get("email")):
        return
    raise HTTPException(403, "Forbidden")


async def _can_view_customer(db, customer_id: str, user: Dict[str, Any]) -> None:
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0, "managerId": 1})
    if not cust:
        raise HTTPException(404, "Customer not found")
    role = _role(user)
    if role in {"owner", "master_admin", "admin", "team_lead"}:
        return
    if role == "manager" and cust.get("managerId") == (user.get("id") or user.get("email")):
        return
    raise HTTPException(403, "Forbidden")


async def _can_view_deal(db, deal_id: str, user: Dict[str, Any]) -> None:
    deal = await db.deals.find_one({"id": deal_id}, {"_id": 0, "managerId": 1})
    if not deal:
        raise HTTPException(404, "Deal not found")
    role = _role(user)
    if role in {"owner", "master_admin", "admin", "team_lead"}:
        return
    if role == "manager" and deal.get("managerId") == (user.get("id") or user.get("email")):
        return
    raise HTTPException(403, "Forbidden")


# ────────────────── Customer ──────────────────
@router.get("/customers/{customer_id}/change-history")
async def customer_history(
    customer_id: str,
    request: Request,
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    if not _allowed_staff(user):
        raise HTTPException(403, "Forbidden")
    await _can_view_customer(db, customer_id, user)
    rows = await svc.list_field_changes(db, entity_type="customer", entity_id=customer_id, limit=limit)
    return {"success": True, "data": rows, "count": len(rows)}


# ────────────────── Lead ──────────────────
@router.get("/leads/{lead_id}/change-history")
async def lead_history(
    lead_id: str,
    request: Request,
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    if not _allowed_staff(user):
        raise HTTPException(403, "Forbidden")
    await _can_view_lead(db, lead_id, user)
    rows = await svc.list_field_changes(db, entity_type="lead", entity_id=lead_id, limit=limit)
    return {"success": True, "data": rows, "count": len(rows)}


# ────────────────── Deal ──────────────────
@router.get("/deals/{deal_id}/change-history")
async def deal_history(
    deal_id: str,
    request: Request,
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_user),
):
    db = _db(request)
    if not _allowed_staff(user):
        raise HTTPException(403, "Forbidden")
    await _can_view_deal(db, deal_id, user)
    rows = await svc.list_field_changes(db, entity_type="deal", entity_id=deal_id, limit=limit)
    return {"success": True, "data": rows, "count": len(rows)}


async def on_startup(db) -> None:
    await svc.ensure_indexes(db)
