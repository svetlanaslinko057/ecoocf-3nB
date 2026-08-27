"""
Wave 12 — Finance360 FastAPI router.

Mounted with prefix `/api` from server.py → public surface:

    GET /api/finance/overview
    GET /api/finance/transactions     (?type, status, manager_id, deal_id,
                                       customer_id, date_from, date_to, q,
                                       limit, offset)
    GET /api/finance/outstanding
    GET /api/finance/refunds          (alias of /transactions?type=refund)
    GET /api/finance/managers         (light list of managers in scope, for filters)

Access:
    require_manager_or_admin — scope is then computed by
    `finance_scope_for_user` so each role sees only what they may.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from security import require_manager_or_admin

from .aggregations import (
    build_finance_overview,
    list_finance_transactions,
    list_outstanding_deals,
    finance_scope_for_user,
)
from .b_aggregations import (
    compute_revenue_at_risk,
    compute_manager_finance,
    compute_collections_queue,
)

logger = logging.getLogger("bibi.wave12.router")
router = APIRouter()


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(500, "Database not initialised on app.state")
    return db


@router.get("/finance/overview")
async def finance_overview(
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    data = await build_finance_overview(db, scope)
    # Strip the internal `_*` keys before returning to the client
    public = {k: v for k, v in data.items() if not k.startswith("_")}
    # Wave 12B — attach Revenue At Risk breakdown so the Overview KPI tile
    # has a single payload to render.
    try:
        public["risk"] = await compute_revenue_at_risk(db, scope)
    except Exception as e:
        logger.warning("[wave12b] risk attach failed: %s", e)
        public["risk"] = None
    return {"success": True, "data": public}


@router.get("/finance/transactions")
async def finance_transactions(
    request: Request,
    type: Optional[str] = Query(None, description="deposit | payment | refund"),
    status: Optional[str] = Query(None),
    manager_id: Optional[str] = Query(None),
    deal_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO 8601"),
    date_to: Optional[str] = Query(None, description="ISO 8601"),
    q: Optional[str] = Query(None, description="free-text search on deal_title / id / note"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    page = await list_finance_transactions(
        db, scope,
        txn_type=type, status=status, manager_id=manager_id,
        deal_id=deal_id, customer_id=customer_id,
        date_from=date_from, date_to=date_to, q=q,
        limit=limit, offset=offset,
    )
    return {"success": True, **page}


@router.get("/finance/refunds")
async def finance_refunds(
    request: Request,
    status: Optional[str] = Query(None),
    manager_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Convenience alias: transactions filtered by type='refund'."""
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    page = await list_finance_transactions(
        db, scope, txn_type="refund", status=status, manager_id=manager_id,
        limit=limit, offset=offset,
    )
    return {"success": True, **page}


@router.get("/finance/outstanding")
async def finance_outstanding(
    request: Request,
    min_outstanding: float = Query(1.0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    data = await list_outstanding_deals(
        db, scope, min_outstanding=min_outstanding, limit=limit
    )
    return {"success": True, **data}


@router.get("/finance/managers")
async def finance_managers(
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """List the manager-ids visible to the current user (used by the
    Transactions / Outstanding filter dropdowns).

    `team_lead` sees own + team. `admin` sees everyone with a managerId.
    """
    db = _db(request)
    scope = await finance_scope_for_user(db, user)

    if scope.get("all"):
        query = {"role": {"$in": ["manager"]}}
    else:
        ids = scope.get("manager_ids") or []
        if not ids:
            return {"success": True, "items": []}
        query = {"$or": [{"id": {"$in": ids}},
                         {"managerId": {"$in": ids}},
                         {"email": {"$in": ids}}]}

    items = []
    try:
        async for raw in db.staff.find(
            query,
            {"_id": 0, "id": 1, "managerId": 1, "name": 1, "full_name": 1,
             "email": 1, "role": 1, "team_lead_id": 1, "avatar_url": 1},
        ):
            items.append({
                "id":     raw.get("id") or raw.get("managerId") or raw.get("email"),
                "name":   raw.get("name") or raw.get("full_name") or raw.get("email"),
                "email":  raw.get("email"),
                "role":   raw.get("role"),
                "avatar": raw.get("avatar_url"),
            })
    except Exception as e:
        logger.warning("[wave12] managers list failed: %s", e)
    return {"success": True, "items": items}


# ─── Wave 12B endpoints ────────────────────────────────────────────────────
@router.get("/finance/risk")
async def finance_risk(
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Revenue at risk breakdown (healthy / warning / at_risk / critical)."""
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    data = await compute_revenue_at_risk(db, scope)
    return {"success": True, "data": data}


@router.get("/finance/managers/pnl")
async def finance_managers_pnl(
    request: Request,
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Per-manager P&L: revenue, profit, outstanding, at_risk, avg_collection_days, health."""
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    data = await compute_manager_finance(db, scope)
    return {"success": True, **data}


@router.get("/finance/collections")
async def finance_collections(
    request: Request,
    min_days_overdue: int = Query(7, ge=0),
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Collections queue — outstanding deals needing follow-up, worst first."""
    db = _db(request)
    scope = await finance_scope_for_user(db, user)
    data = await compute_collections_queue(
        db, scope, min_days_overdue=min_days_overdue, limit=limit
    )
    return {"success": True, **data}
