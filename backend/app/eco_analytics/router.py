"""ECO Analytics — HTTP routers (read-only, scope-aware: admin=all, manager=own).

Mounted in server.py with prefix "/api". Replaces the legacy wave12/12c/14/15/16
routers at the SAME public paths so the existing ECO portal frontend keeps
working — only the data source changed (car-import → ECO waste domain).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.eco_analytics import aggregations as A
from security import require_user  # type: ignore

logger = logging.getLogger("eco.analytics")


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(500, "Database not initialised on app.state")
    return db


# ═══════════════════════════════════════════════════════════════════════════
#  FINANCE  /api/finance/*   (Wave 12) + /api/forecast/*  (Wave 12C)
# ═══════════════════════════════════════════════════════════════════════════
finance_router = APIRouter(prefix="/api/finance", tags=["ECO:Finance360"])


@finance_router.get("/overview")
async def finance_overview(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.finance_overview(_db(request), u)}


@finance_router.get("/transactions")
async def finance_transactions(request: Request, limit: int = Query(100, ge=1, le=1000),
                               u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.finance_transactions(_db(request), u, limit)}


@finance_router.get("/outstanding")
async def finance_outstanding(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.finance_outstanding(_db(request), u)}


@finance_router.get("/risk")
async def finance_risk(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.finance_risk(_db(request), u)}


@finance_router.get("/collections")
async def finance_collections(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.finance_collections(_db(request), u)}


@finance_router.get("/managers/pnl")
async def finance_managers_pnl(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.finance_managers_pnl(_db(request), u)}


@finance_router.get("/managers")
async def finance_managers(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.finance_managers_pnl(_db(request), u)}


@finance_router.get("/refunds")
async def finance_refunds(u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "items": [], "total": 0, "summary": {"pending": 0, "paid": 0}}


# Forecast lives under /api/forecast/* — separate router, no /api prefix needed here.
forecast_router = APIRouter(prefix="/api/forecast", tags=["ECO:Forecasting360"])


@forecast_router.get("/overview")
async def forecast_overview(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.finance_forecast(_db(request), u)}


@forecast_router.get("/cash-flow")
async def forecast_cash_flow(request: Request, u: Dict[str, Any] = Depends(require_user)):
    fc = await A.finance_forecast(_db(request), u)
    return {"success": True, "data": {"weeks": fc["when"]["weeks"]}}


@forecast_router.get("/revenue")
async def forecast_revenue(request: Request, u: Dict[str, Any] = Depends(require_user)):
    fc = await A.finance_forecast(_db(request), u)
    return {"success": True, "data": {"horizons": fc["how_much"]["horizons"]}}


# ═══════════════════════════════════════════════════════════════════════════
#  OPERATIONS  /api/operations/*  (Wave 14)
# ═══════════════════════════════════════════════════════════════════════════
operations_router = APIRouter(prefix="/api/operations", tags=["ECO:Operations360"])


@operations_router.get("/dashboard")
async def ops_dashboard(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.operations_dashboard(_db(request), u)}


@operations_router.get("/bottlenecks")
async def ops_bottlenecks(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.operations_bottlenecks(_db(request), u)}


@operations_router.get("/sla")
async def ops_sla(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.operations_sla(_db(request), u)}


@operations_router.get("/risk")
async def ops_risk(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.operations_risk(_db(request), u)}


@operations_router.get("/team")
async def ops_team(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.operations_team(_db(request), u)}


# ═══════════════════════════════════════════════════════════════════════════
#  EXECUTIVE  /api/executive/*  (Wave 16) — admin/director lens
# ═══════════════════════════════════════════════════════════════════════════
executive_router = APIRouter(prefix="/api/executive", tags=["ECO:ExecutiveCenter"])


@executive_router.get("/dashboard")
async def exec_dashboard(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.executive_dashboard(_db(request), u)}


@executive_router.get("/forecast")
async def exec_forecast(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.executive_forecast(_db(request), u)}


@executive_router.get("/risks")
async def exec_risks(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.executive_risks(_db(request), u)}


@executive_router.get("/bottlenecks")
async def exec_bottlenecks(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.operations_bottlenecks(_db(request), u)}


# ═══════════════════════════════════════════════════════════════════════════
#  CONTRACTS  /api/contracts/*  (Wave 15)
# ═══════════════════════════════════════════════════════════════════════════
contracts_router = APIRouter(prefix="/api/contracts", tags=["ECO:Contract360"])


@contracts_router.get("/overview")
async def ctr_overview(request: Request, u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "data": await A.contracts_overview(_db(request), u)}


@contracts_router.get("/templates")
async def ctr_templates(u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, "items": A.CONTRACT_TEMPLATES, "total": len(A.CONTRACT_TEMPLATES)}


@contracts_router.get("/risk")
async def ctr_risk(request: Request, u: Dict[str, Any] = Depends(require_user)):
    ov = await A.contracts_overview(_db(request), u)
    return {"success": True, "data": {"by_segment": ov["by_segment"], "totals": ov["totals"]}}


@contracts_router.get("")
async def ctr_list(request: Request, status: Optional[str] = None, limit: int = Query(200, ge=1, le=1000),
                   u: Dict[str, Any] = Depends(require_user)):
    return {"success": True, **await A.contracts_list(_db(request), u, status, limit)}


@contracts_router.get("/{contract_id}")
async def ctr_get(request: Request, contract_id: str, u: Dict[str, Any] = Depends(require_user)):
    c = await A.contract_get(_db(request), u, contract_id)
    if not c:
        raise HTTPException(404, "Contract not found")
    return {"success": True, "data": c}


@contracts_router.post("/{contract_id}/{action}")
async def ctr_lifecycle(request: Request, contract_id: str, action: str,
                        body: Dict[str, Any] = Body(default={}), u: Dict[str, Any] = Depends(require_user)):
    res = await A.contract_lifecycle(_db(request), u, contract_id, action, body.get("note", ""))
    if not res.get("ok"):
        raise HTTPException(400 if res.get("error") == "bad_action" else 404, res.get("error", "error"))
    return {"success": True, **res}


# ═══════════════════════════════════════════════════════════════════════════
#  DEALS / DEAL360  (Wave 6 + 11) — ECO namespace to avoid legacy collisions
# ═══════════════════════════════════════════════════════════════════════════
deals_router = APIRouter(prefix="/api/eco", tags=["ECO:Deal360"])


@deals_router.get("/deals/{deal_id}/360")
async def deal_360(request: Request, deal_id: str, u: Dict[str, Any] = Depends(require_user)):
    data = await A.deal_360(_db(request), u, deal_id)
    if not data:
        raise HTTPException(404, "Deal not found")
    return {"success": True, "data": data}


@deals_router.get("/deals/{deal_id}/stage-progress")
async def deal_stage_progress(request: Request, deal_id: str, u: Dict[str, Any] = Depends(require_user)):
    data = await A.deal_stage_progress(_db(request), u, deal_id)
    if not data:
        raise HTTPException(404, "Deal not found")
    return {"success": True, "data": data}


@deals_router.post("/deals/{deal_id}/transition")
async def deal_transition(request: Request, deal_id: str, body: Dict[str, Any] = Body(...),
                          u: Dict[str, Any] = Depends(require_user)):
    res = await A.deal_transition(_db(request), u, deal_id, body.get("stage") or body.get("to_stage"), body.get("note", ""))
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "error"))
    return {"success": True, **res}


@deals_router.get("/deals/{deal_id}")
async def eco_deal(request: Request, deal_id: str, u: Dict[str, Any] = Depends(require_user)):
    data = await A.deal_360(_db(request), u, deal_id)
    if not data:
        raise HTTPException(404, "Deal not found")
    return {"success": True, "deal": data["deal"], "health": data["health"],
            "stage_progress": data["stage_progress"], "financials": data["financials"],
            "contracts": data["contracts"], "payments": data["payments"], "company": data["company"]}


ALL_ROUTERS = [finance_router, forecast_router, operations_router,
               executive_router, contracts_router, deals_router]
