"""
Contract Execution Engine — REST surface.

Mounted under /api/waste (staff) with distinct sub-paths so it never collides
with the existing ops_router (/waste/contracts, /waste/acts …). Client-facing
read-only endpoints live under /api/customer-cabinet/contracts.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response

from app.core.db_runtime import get_db
from security import require_manager_or_admin
from app.contract_engine import constants as K
from app.contract_engine import periods as PERIODS
from app.contract_engine import financials as FIN
from app.contract_engine import completion as COMP
from app.contract_engine import reports as REP
from app.contract_engine import accumulation as ACC
from app.contract_engine.util import now_iso

logger = logging.getLogger("eco.contract_engine")

router = APIRouter(prefix="/api/waste", tags=["contract-engine"])

ENGINE_FIELDS = (
    "customer_id", "object_ids", "waste_codes", "valid_from", "valid_to",
    "total_limit_kg", "region", "schedule_config", "financial_terms", "contract_value",
)


async def _contract_or_404(db, contract_id: str) -> Dict[str, Any]:
    doc = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Договір не знайдено")
    return doc


# ── Engine config on the contract ───────────────────────────────────────────
@router.patch("/contracts/{contract_id}/engine", dependencies=[Depends(require_manager_or_admin)])
async def update_engine_fields(contract_id: str, data: Dict[str, Any] = Body(...)):
    db = get_db()
    await _contract_or_404(db, contract_id)
    patch = {k: data[k] for k in ENGINE_FIELDS if k in data}
    if not patch:
        raise HTTPException(400, "No engine fields to update")
    patch["updated_at"] = now_iso()
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": patch})
    fin = await FIN.recompute(contract_id, db=db)
    return {"success": True, "contract": await _contract_or_404(db, contract_id), "financials": fin}


# ── Schedule (periods) ───────────────────────────────────────────────────────
@router.get("/contracts/{contract_id}/schedule", dependencies=[Depends(require_manager_or_admin)])
async def get_schedule(contract_id: str):
    db = get_db()
    contract = await _contract_or_404(db, contract_id)
    periods = await PERIODS.get_periods(contract_id, db=db)
    fin = contract.get("financials") or await FIN.recompute(contract_id, db=db)
    return {"success": True, "periods": periods, "financials": fin, "contract": contract}


@router.post("/contracts/{contract_id}/schedule/generate", dependencies=[Depends(require_manager_or_admin)])
async def generate_schedule(contract_id: str, data: Dict[str, Any] = Body(default={})):
    db = get_db()
    await _contract_or_404(db, contract_id)
    try:
        periods = await PERIODS.generate(
            contract_id, replace=bool(data.get("replace", True)),
            custom_windows=data.get("custom_windows"), db=db,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    fin = await FIN.recompute(contract_id, db=db)
    return {"success": True, "periods": periods, "financials": fin}


@router.patch("/periods/{period_id}/lines/{waste_code:path}", dependencies=[Depends(require_manager_or_admin)])
async def patch_line(period_id: str, waste_code: str, patch: Dict[str, Any] = Body(...)):
    try:
        res = await PERIODS.update_line(period_id, waste_code, patch)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"success": True, **res}


@router.delete("/periods/{period_id}/lines/{waste_code:path}", dependencies=[Depends(require_manager_or_admin)])
async def delete_line(period_id: str, waste_code: str):
    try:
        res = await PERIODS.remove_line(period_id, waste_code)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"success": True, **res}


@router.post("/periods/{period_id}/extra-works", dependencies=[Depends(require_manager_or_admin)])
async def add_extra(period_id: str, data: Dict[str, Any] = Body(...)):
    try:
        res = await PERIODS.add_extra_work(period_id, data)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"success": True, **res}


@router.delete("/periods/{period_id}/extra-works/{extra_id}", dependencies=[Depends(require_manager_or_admin)])
async def del_extra(period_id: str, extra_id: str):
    try:
        res = await PERIODS.remove_extra_work(period_id, extra_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"success": True, **res}


@router.post("/periods/{period_id}/status", dependencies=[Depends(require_manager_or_admin)])
async def set_period_status(period_id: str, data: Dict[str, Any] = Body(...)):
    try:
        period = await PERIODS.set_status(period_id, (data.get("status") or "").strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "period": period}


# ── Financials ───────────────────────────────────────────────────────────────
@router.get("/contracts/{contract_id}/financials", dependencies=[Depends(require_manager_or_admin)])
async def get_financials(contract_id: str):
    db = get_db()
    await _contract_or_404(db, contract_id)
    return {"success": True, "financials": await FIN.recompute(contract_id, db=db)}


@router.post("/contracts/{contract_id}/freeze-value", dependencies=[Depends(require_manager_or_admin)])
async def freeze_value(contract_id: str, data: Dict[str, Any] = Body(default={})):
    db = get_db()
    await _contract_or_404(db, contract_id)
    fin = await FIN.freeze_contract_value(contract_id, value=data.get("value"), db=db)
    return {"success": True, "financials": fin}


@router.post("/contracts/{contract_id}/recompute", dependencies=[Depends(require_manager_or_admin)])
async def recompute_all(contract_id: str):
    db = get_db()
    await _contract_or_404(db, contract_id)
    await ACC.recompute_actuals(contract_id, db=db)
    return {"success": True, "financials": await FIN.recompute(contract_id, db=db)}


# ── Completion Wizard ─────────────────────────────────────────────────────────
@router.get("/contracts/{contract_id}/completion-check", dependencies=[Depends(require_manager_or_admin)])
async def completion_check(contract_id: str):
    try:
        return {"success": True, **(await COMP.completion_check(contract_id))}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/contracts/{contract_id}/complete", dependencies=[Depends(require_manager_or_admin)])
async def complete_contract(contract_id: str, data: Dict[str, Any] = Body(default={}),
                            user: Dict[str, Any] = Depends(require_manager_or_admin)):
    try:
        return await COMP.complete_contract(
            contract_id, by={"id": user.get("id"), "email": user.get("email")},
            confirm=bool(data.get("confirm")),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Ecologist Reports ─────────────────────────────────────────────────────────
@router.get("/contracts/{contract_id}/ecologist-reports", dependencies=[Depends(require_manager_or_admin)])
async def list_eco_reports(contract_id: str):
    return {"success": True, "items": await REP.list_reports(contract_id)}


@router.post("/contracts/{contract_id}/ecologist-reports", dependencies=[Depends(require_manager_or_admin)])
async def create_eco_report(contract_id: str, data: Dict[str, Any] = Body(default={}),
                            user: Dict[str, Any] = Depends(require_manager_or_admin)):
    try:
        rep = await REP.build_report(
            contract_id,
            scope_type=data.get("scope_type") or "contract",
            period_ids=data.get("period_ids"),
            date_from=data.get("date_from"), date_to=data.get("date_to"),
            ecologist=data.get("ecologist"),
            conclusion=data.get("conclusion"), recommendations=data.get("recommendations"),
            status=data.get("status") or "draft",
            by={"id": user.get("id"), "email": user.get("email")},
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "report": rep}


@router.get("/ecologist-reports/{report_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_eco_report(report_id: str):
    rep = await REP.get_report(report_id)
    if not rep:
        raise HTTPException(404, "Звіт не знайдено")
    return {"success": True, "report": rep}


@router.patch("/ecologist-reports/{report_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_eco_report(report_id: str, patch: Dict[str, Any] = Body(...)):
    rep = await REP.update_report(report_id, patch)
    if not rep:
        raise HTTPException(404, "Звіт не знайдено")
    return {"success": True, "report": rep}


@router.get("/ecologist-reports/{report_id}/pdf")
async def eco_report_pdf(report_id: str):
    db = get_db()
    rep = await REP.get_report(report_id, db=db)
    if not rep:
        raise HTTPException(404, "Звіт не знайдено")
    contract = await db[K.C_CONTRACTS].find_one({"id": rep.get("contract_id")}, {"_id": 0}) or {}
    company = await db[K.C_COMPANIES].find_one({"id": rep.get("company_id")}, {"_id": 0}) or {}
    try:
        html_str = REP.render_report_html(rep, contract, company)
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception:
        logger.exception("[eco_report] PDF render failed for %s", report_id)
        raise HTTPException(500, "Помилка генерації PDF")
    filename = f"{(rep.get('number') or 'ecologist-report')}.pdf"
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ── Invoicing (per period / per act) ─────────────────────────────────────────
@router.post("/contracts/{contract_id}/periods/{period_id}/invoice", dependencies=[Depends(require_manager_or_admin)])
async def invoice_period(contract_id: str, period_id: str, data: Dict[str, Any] = Body(default={}),
                         user: Dict[str, Any] = Depends(require_manager_or_admin)):
    from app.contract_engine import invoicing as INV
    try:
        return {"success": True, **(await INV.generate_period_invoice(
            contract_id, period_id, basis=(data.get("basis") or "planned"),
            due_date=data.get("dueDate"), force=bool(data.get("force")),
            by={"id": user.get("id"), "email": user.get("email")}))}
    except INV.BillingError as e:
        raise HTTPException(400, str(e))


@router.post("/contracts/{contract_id}/acts/{act_id}/invoice", dependencies=[Depends(require_manager_or_admin)])
async def invoice_act(contract_id: str, act_id: str, data: Dict[str, Any] = Body(default={}),
                      user: Dict[str, Any] = Depends(require_manager_or_admin)):
    from app.contract_engine import invoicing as INV
    try:
        return {"success": True, **(await INV.generate_act_invoice(
            contract_id, act_id, force=bool(data.get("force")),
            by={"id": user.get("id"), "email": user.get("email")}))}
    except INV.BillingError as e:
        raise HTTPException(400, str(e))


@router.post("/contracts/{contract_id}/invoices/{invoice_id}/status", dependencies=[Depends(require_manager_or_admin)])
async def invoice_status(contract_id: str, invoice_id: str, data: Dict[str, Any] = Body(...)):
    from app.contract_engine import invoicing as INV
    status = (data.get("status") or "").strip().lower()
    if status not in ("pending", "partial", "paid", "cancelled", "overdue"):
        raise HTTPException(400, "Невірний статус")
    db = get_db()
    patch = {"status": status, "updated_at": now_iso()}
    if data.get("amount_paid") is not None:
        patch["amount_paid"] = float(data["amount_paid"])
    await db[K.C_INVOICES].update_one({"id": invoice_id, "contract_id": contract_id}, {"$set": patch})
    return {"success": True, "financials": await FIN.recompute(contract_id, db=db)}


@router.get("/contracts/{contract_id}/invoices", dependencies=[Depends(require_manager_or_admin)])
async def list_contract_invoices(contract_id: str):
    db = get_db()
    items = await db[K.C_INVOICES].find({"contract_id": contract_id}, {"_id": 0}).sort("created_at", -1).to_list(length=500)
    return {"success": True, "items": items}


# ── Ecologist report sign-off (internal, NOT КЕП) ────────────────────────────
@router.post("/ecologist-reports/{report_id}/sign-off", dependencies=[Depends(require_manager_or_admin)])
async def sign_off_report(report_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    try:
        rep = await REP.sign_off(report_id, by={"id": user.get("id"), "email": user.get("email"), "role": user.get("role")})
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"success": True, "report": rep}


async def ensure_indexes(db) -> None:
    try:
        await db[K.C_PERIODS].create_index("contract_id")
        await db[K.C_PERIODS].create_index([("contract_id", 1), ("index", 1)])
        await db[K.C_ECO_REPORTS].create_index("contract_id")
        await db[K.C_INVOICES].create_index("contract_id")
    except Exception:
        logger.warning("[contract_engine] index ensure skipped", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════
#  CLIENT (B2B) read-only mirror — no editing
# ════════════════════════════════════════════════════════════════════════════
client_router = APIRouter(prefix="/api/customer-cabinet", tags=["contract-engine-client"])


@client_router.get("/{customer_id}/contract-engine")
async def client_contract_engine(customer_id: str):
    """List the customer's engine-enabled contracts (by customer OR their company)."""
    db = get_db()
    ors = [{"customer_id": customer_id}, {"customerId": customer_id}]
    cust = await db["customers"].find_one({"$or": [{"id": customer_id}, {"customerId": customer_id}]}, {"_id": 0, "company_id": 1})
    company_id = (cust or {}).get("company_id")
    if company_id:
        ors.append({"company_id": company_id})
    contracts = await db[K.C_CONTRACTS].find(
        {"$or": ors}, {"_id": 0},
    ).sort("created_at", -1).to_list(length=200)
    return {"success": True, "items": contracts}


@client_router.get("/{customer_id}/contract-engine/{contract_id}")
async def client_contract_engine_detail(customer_id: str, contract_id: str):
    db = get_db()
    contract = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract:
        raise HTTPException(404, "Договір не знайдено")
    cust = await db["customers"].find_one({"$or": [{"id": customer_id}, {"customerId": customer_id}]}, {"_id": 0, "company_id": 1})
    company_id = (cust or {}).get("company_id")
    owns = (
        contract.get("customer_id") == customer_id
        or contract.get("customerId") == customer_id
        or (company_id and contract.get("company_id") == company_id)
    )
    if not owns:
        raise HTTPException(404, "Договір не знайдено")
    periods = await PERIODS.get_periods(contract_id, db=db)
    fin = await FIN.recompute(contract_id, db=db)
    acts = await db[K.C_ACTS].find({"contract_id": contract_id}, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    invoices = await db[K.C_INVOICES].find({"contract_id": contract_id}, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    reports = await REP.list_reports(contract_id, db=db)
    return {
        "success": True, "contract": contract, "periods": periods, "financials": fin,
        "acts": acts, "invoices": invoices, "ecologist_reports": reports,
    }
