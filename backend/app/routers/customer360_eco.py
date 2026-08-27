"""
customer360_eco.py — ECO-domain Customer 360 aggregation (staff-facing).

Reuses the existing waste_* collections and RBAC. Customer ↔ ECO history is
linked through the customer's `company_id` (waste_requests / waste_contracts /
utilization_acts / waste_tasks / waste_activity are company-scoped), plus the
customer id for invoices / payments.

Endpoints (all read-only, RBAC-aware — a manager only sees their own clients):
  GET /api/customers/{id}/eco/overview    — KPI header + last activity + open tasks
  GET /api/customers/{id}/eco/requests    — заявки / замовлення (waste_requests)
  GET /api/customers/{id}/eco/contracts    — договори (waste_contracts + lifecycle numbers)
  GET /api/customers/{id}/eco/acts         — акти утилізації + звіти еколога
  GET /api/customers/{id}/eco/activity     — universal timeline (waste_activity + comments)

We DO NOT create a new invoice/contract engine — the Invoices / Documents /
Payments tabs consume the already-existing customer360_finance + documents
endpoints. This router only fills the ECO waste gaps.
"""
from __future__ import annotations

from typing import Any, Dict, List
import asyncio

from fastapi import APIRouter, HTTPException, Depends, Response, Body

from app.core.db_runtime import get_db
from security import require_user
from app.services.staff_acl import staff_can_see_customer
from app.services.customer_resolver import build_dto

router = APIRouter(tags=["customer-360-eco"])

_OPEN_INV = {"sent", "pending", "awaiting_confirmation", "draft"}
_OVERDUE = {"overdue"}


async def _load_customer_or_403(customer_id: str, current_user: Dict[str, Any]):
    db = get_db()
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    if not staff_can_see_customer(current_user, customer):
        raise HTTPException(403, "Access denied: customer not in your book")
    return customer


async def _safe(coro, default=None):
    try:
        return await coro
    except Exception:
        return default if default is not None else []


def _company_filter(customer: Dict[str, Any]) -> Dict[str, Any]:
    """Match ECO docs belonging to this customer's company (and, defensively,
    directly to the customer id where a collection stores it)."""
    cid = customer.get("id")
    company_id = customer.get("company_id")
    ors: List[dict] = []
    if company_id:
        ors.append({"company_id": company_id})
    if cid:
        ors.append({"customer_id": cid})
        ors.append({"customerId": cid})
    return {"$or": ors} if ors else {"id": "__none__"}


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


@router.get("/api/customers/{customer_id}/eco/requests")
async def eco_requests(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    flt = _company_filter(customer)
    items = await _safe(
        db.waste_requests.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    )
    return {"success": True, "items": items, "total": len(items)}


@router.get("/api/customers/{customer_id}/eco/contracts")
async def eco_contracts(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    flt = _company_filter(customer)
    items = await _safe(
        db.waste_contracts.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    )
    # Lightweight execution numbers so the tab can show value/executed/remaining
    for c in items:
        fin = c.get("financials") or {}
        c["_value"] = _num(c.get("total_amount") or fin.get("grand_total") or fin.get("planned_total"))
        c["_invoiced"] = _num(fin.get("invoiced_total"))
        c["_paid"] = _num(fin.get("paid_total"))
        c["_remaining"] = round(c["_value"] - c["_paid"], 2)
    return {"success": True, "items": items, "total": len(items)}


# Roles allowed to delete manual uploads. Managers are additionally scoped to
# their own clients via ``staff_can_see_customer`` in ``_load_customer_or_403``.
# Clients / plain users can never reach here (staff ACL returns 403 first).
_DELETE_ROLES = {"admin", "master_admin", "owner", "team_lead", "manager"}
# File purposes that represent MANUAL uploads which the profile view may delete.
_MANUAL_PURPOSES = {"act", "ecologist_report", "document"}


def _can_delete_uploads(current_user: Dict[str, Any]) -> bool:
    return (current_user.get("role") or "").lower() in _DELETE_ROLES


def _upload_period_label(meta: dict, f: dict) -> str:
    """Human-readable period for an uploaded act/report from its metadata."""
    lbl = meta.get("period_label") or f.get("period_label") or meta.get("period") or f.get("period")
    if lbl:
        return str(lbl)
    q, y = meta.get("quarter"), meta.get("year")
    if q and y:
        return f"Q{q} {y}"
    pf, pt = meta.get("period_from"), meta.get("period_to")
    if pf or pt:
        return f"{pf or '…'} — {pt or '…'}"
    return ""


@router.get("/api/customers/{customer_id}/eco/acts")
async def eco_acts(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    flt = _company_filter(customer)
    acts, reports, uploaded = await asyncio.gather(
        _safe(db.utilization_acts.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=300)),
        _safe(db.ecologist_reports.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=200)),
        _safe(db.files.find(
            {"entity_type": "customer", "entity_id": customer_id,
             "status": {"$ne": "deleted"}, "purpose": {"$in": ["act", "ecologist_report"]}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(length=200)),
    )

    can_delete = _can_delete_uploads(current_user)

    def _norm_upload(f: dict) -> dict:
        meta = f.get("meta") or {}
        return {
            "id": f.get("id"),
            "file_id": f.get("id"),
            "title": meta.get("title") or f.get("title") or f.get("filename") or f.get("original_name") or "Завантажений файл",
            "filename": f.get("filename"),
            "mime": f.get("mime") or f.get("mimeType"),
            "created_at": f.get("created_at"),          # when uploaded
            "doc_date": meta.get("doc_date") or f.get("doc_date"),
            "uploaded": True,
            "source": "uploaded",
            "generated": False,
            "can_delete": can_delete,
            "uploaded_by": f.get("uploaded_by") or f.get("uploadedBy") or f.get("owner"),
            "size": f.get("size"),
            "status": f.get("status") or "active",
            "period_from": meta.get("period_from"),
            "period_to": meta.get("period_to"),
            "period_label": _upload_period_label(meta, f),
            "contract_id": meta.get("contract_id") or f.get("contract_id"),
            "object_id": meta.get("object_id") or f.get("object_id"),
            "notes": meta.get("notes"),
            # report-specific
            "report_type": meta.get("report_type") or f.get("report_type"),
            "report_scope": meta.get("report_scope"),
            "quarter": meta.get("quarter"),
            "year": meta.get("year"),
            # act-specific
            "act_number": meta.get("act_number"),
            "utilization_method": meta.get("utilization_method"),
            "total_weight_kg": meta.get("total_weight_kg"),
        }

    def _mark_system(d: dict) -> dict:
        d.setdefault("uploaded", False)
        d["source"] = "system"
        d["generated"] = True
        d["can_delete"] = False
        return d

    up_acts = [_norm_upload(f) for f in (uploaded or []) if f.get("purpose") == "act"]
    up_reports = [_norm_upload(f) for f in (uploaded or []) if f.get("purpose") == "ecologist_report"]
    sys_acts = [_mark_system(a) for a in (acts or [])]
    sys_reports = [_mark_system(r) for r in (reports or [])]
    acts = up_acts + sys_acts
    reports = up_reports + sys_reports
    return {"success": True, "acts": acts, "reports": reports,
            "total_acts": len(acts), "total_reports": len(reports),
            "can_delete_uploads": can_delete}


@router.delete("/api/customers/{customer_id}/files/{file_id}")
async def delete_customer_file(customer_id: str, file_id: str,
                               payload: Dict[str, Any] = Body(default={}),
                               current_user: Dict[str, Any] = Depends(require_user)):
    """Delete a MANUALLY UPLOADED customer-scoped file (act / ecologist report /
    document) — profile view (Customer 360 → Акти / Звіти).

    Guardrails:
      • RBAC — admin: any accessible file; manager: only files of own clients;
        client / plain user: no delete (staff ACL returns 403 before we reach
        the mutation).
      • System-generated documents (``generated=True``) or non-manual purposes
        are NEVER deletable through this endpoint (returns 403).
      • Soft-delete only (``status=deleted``) — the File Layer keeps the binary
        + version history, so the deletion is fully auditable/recoverable.
      • Records an audit row (file_audit via FileRepository) AND a customer
        timeline event (waste_activity) with actor / timestamp / entity /
        filename / optional reason.
      • After deletion the file disappears from the profile table AND the
        client read-only view (both filter ``status != deleted``).
    """
    from datetime import datetime, timezone
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    if not _can_delete_uploads(current_user):
        raise HTTPException(status_code=403, detail="Недостатньо прав для видалення файлів")

    rec = await db.files.find_one(
        {"id": file_id, "entity_type": "customer", "entity_id": customer_id},
        {"_id": 0},
    )
    if not rec or rec.get("status") == "deleted":
        raise HTTPException(status_code=404, detail="Файл не знайдено")

    # Protect system-generated documents and any non-manual purpose.
    if rec.get("generated") is True or (rec.get("purpose") or "") not in _MANUAL_PURPOSES:
        raise HTTPException(
            status_code=403,
            detail="Системні (згенеровані) документи не можна видаляти через цей інтерфейс",
        )

    reason = (payload or {}).get("reason")
    actor = current_user.get("email") or current_user.get("id")
    filename = rec.get("filename") or rec.get("title") or file_id

    # Soft-delete via the canonical File Layer (keeps binary + versioning +
    # writes a file_audit 'deleted' event).
    try:
        from app.storage.files_repo import FileRepository
        await FileRepository(db).soft_delete(file_id, by=actor)
    except Exception:
        # Fallback: direct soft-delete if the repo import ever fails.
        await db.files.update_one(
            {"id": file_id},
            {"$set": {"status": "deleted", "deleted_at": datetime.now(timezone.utc).isoformat(),
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    # Persist the delete reason / actor on the file record for traceability.
    await db.files.update_one(
        {"id": file_id},
        {"$set": {"deleted_by": actor,
                  "deleted_reason": reason,
                  "deleted_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Customer timeline event (shows up in the Activity tab via _company_filter).
    try:
        purpose = rec.get("purpose") or "document"
        kind_label = {"act": "акт", "ecologist_report": "звіт еколога"}.get(purpose, "документ")
        await db.waste_activity.insert_one({
            "id": f"file_del_{file_id}",
            "event": "file_deleted",
            "entity_type": "customer",
            "entity_id": customer_id,
            "company_id": customer.get("company_id"),
            "customer_id": customer_id,
            "message": f"Видалено {kind_label} «{filename}»" + (f" · причина: {reason}" if reason else ""),
            "file_id": file_id,
            "filename": filename,
            "reason": reason,
            "by": actor,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {"success": True, "deleted": file_id}



def _iso(v) -> str:
    try:
        return v if isinstance(v, str) else (v.isoformat() if v else "")
    except Exception:
        return ""


def _money_str(v, cur="UAH") -> str:
    try:
        return f"{float(v or 0):,.2f} {cur}".replace(",", " ")
    except Exception:
        return f"{v} {cur}"


@router.get("/api/customers/{customer_id}/eco/activity")
async def eco_activity(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Unified customer timeline — merges, into a single chronological stream:
      • waste_activity (company/object/request/contract events, status changes)
      • invoice lifecycle events synthesised from each invoice (created / sent /
        paid / cancelled) WITH amounts
      • payment-confirmation events (from the invoice payment_claim)
      • change_history entries for the customer's invoices
      • internal comments (u_comments) — also returned separately for the composer
    Everything is normalised to {id, type, kind, title, created_at, by, amount}.
    """
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    flt = _company_filter(customer)
    inv_flt = {"$or": [
        {"customerId": customer_id}, {"customer_id": customer_id},
        *([{"company_id": customer.get("company_id")}] if customer.get("company_id") else []),
    ]}

    waste_ev, comments, invoices = await asyncio.gather(
        _safe(db.waste_activity.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=300)),
        _safe(db.u_comments.find({"entity_id": customer_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)),
        _safe(db.invoices.find(inv_flt, {"_id": 0}).to_list(length=300)),
    )

    events: List[dict] = []

    # 1) Raw waste_activity events (requests/contracts/company status changes)
    for e in (waste_ev or []):
        events.append({
            "id": e.get("id") or f"wa_{len(events)}",
            "kind": "event",
            "type": e.get("event") or e.get("entity_type") or "event",
            "title": e.get("message") or e.get("event") or "Подія",
            "created_at": _iso(e.get("created_at") or e.get("at")),
            "by": e.get("by") or e.get("author"),
        })

    # 2) Invoice lifecycle events synthesised from invoice fields
    inv_ids = []
    for iv in (invoices or []):
        inv_ids.append(iv.get("id"))
        num = iv.get("number") or (iv.get("id") or "")[-8:]
        cur = iv.get("currency") or "UAH"
        amt = iv.get("amount") or iv.get("total")
        status = (iv.get("status") or "").lower()
        if iv.get("created_at"):
            events.append({"id": f"inv_c_{iv.get('id')}", "kind": "invoice", "type": "invoice_created",
                           "title": f"Рахунок {num} створено · {_money_str(amt, cur)}",
                           "created_at": _iso(iv.get("created_at")), "by": iv.get("created_by"),
                           "amount": amt})
        if iv.get("sentAt"):
            events.append({"id": f"inv_s_{iv.get('id')}", "kind": "invoice", "type": "invoice_sent",
                           "title": f"Рахунок {num} надіслано клієнту",
                           "created_at": _iso(iv.get("sentAt")), "by": iv.get("managerEmail")})
        claim = iv.get("payment_claim") or {}
        if claim.get("submitted_at"):
            events.append({"id": f"inv_pc_{iv.get('id')}", "kind": "payment", "type": "payment_claimed",
                           "title": f"Клієнт заявив оплату рахунку {num}" + (f" · платник: {claim.get('payer')}" if claim.get("payer") else ""),
                           "created_at": _iso(claim.get("submitted_at")), "by": claim.get("payer")})
        if status == "paid":
            events.append({"id": f"inv_p_{iv.get('id')}", "kind": "payment", "type": "payment_confirmed",
                           "title": f"Оплату рахунку {num} підтверджено · {_money_str(amt, cur)}",
                           "created_at": _iso(iv.get("paidAt") or iv.get("paid_at") or iv.get("updated_at")),
                           "by": iv.get("confirmed_by"), "amount": amt})
        elif status == "cancelled":
            events.append({"id": f"inv_x_{iv.get('id')}", "kind": "invoice", "type": "invoice_cancelled",
                           "title": f"Рахунок {num} скасовано",
                           "created_at": _iso(iv.get("updated_at")), "by": iv.get("cancelled_by")})

    # 3) change_history entries for the customer's invoices (best-effort)
    if inv_ids:
        hist = await _safe(db.change_history.find(
            {"entity_id": {"$in": [i for i in inv_ids if i]}}, {"_id": 0}
        ).sort("created_at", -1).to_list(length=200))
        for h in (hist or []):
            events.append({
                "id": h.get("id") or f"ch_{len(events)}",
                "kind": "event",
                "type": h.get("action") or h.get("field") or "change",
                "title": h.get("summary") or h.get("message") or (
                    f"{h.get('field')}: {h.get('old_value')} → {h.get('new_value')}" if h.get("field") else "Зміну зафіксовано"),
                "created_at": _iso(h.get("created_at") or h.get("at")),
                "by": h.get("actor") or h.get("by") or h.get("author"),
            })

    # sort newest-first, drop empty timestamps to the bottom deterministically
    events.sort(key=lambda e: e.get("created_at") or "", reverse=True)

    return {"success": True, "events": events, "comments": comments, "total": len(events)}


@router.get("/api/companies/{company_id}/customers")
async def company_customers(company_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """Contact persons (customers) linked to a company — Company↔Customer link."""
    db = get_db()
    role = (current_user.get("role") or "").lower()
    flt: Dict[str, Any] = {"company_id": company_id}
    # Manager scope — only own clients
    if role == "manager":
        uid = current_user.get("id")
        flt = {"$and": [flt, {"managerId": uid}]}
    docs = await _safe(db.customers.find(flt, {"_id": 0, "password": 0}).to_list(length=200))
    items = [build_dto(d) for d in docs]
    return {"success": True, "items": items, "total": len(items)}


@router.get("/api/customers/{customer_id}/eco/overview")
async def eco_overview(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    flt = _company_filter(customer)
    inv_flt = {"$or": [
        {"customerId": customer_id}, {"customer_id": customer_id},
        *([{"company_id": customer.get("company_id")}] if customer.get("company_id") else []),
    ]}

    requests, contracts, acts, invoices, tasks, activity = await asyncio.gather(
        _safe(db.waste_requests.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.waste_contracts.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.utilization_acts.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.invoices.find(inv_flt, {"_id": 0}).to_list(length=500)),
        _safe(db.waste_tasks.find(flt, {"_id": 0}).to_list(length=500)),
        _safe(db.waste_activity.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=1)),
    )

    def _amt(i):
        return _num(i.get("total") or i.get("amount"))

    invoiced = sum(_amt(i) for i in invoices if (i.get("status") or "").lower() != "cancelled")
    paid = sum(_amt(i) for i in invoices if (i.get("status") or "").lower() == "paid")
    debt = sum(_amt(i) for i in invoices if (i.get("status") or "").lower() in _OPEN_INV)
    overdue = sum(_amt(i) for i in invoices if (i.get("status") or "").lower() in _OVERDUE)

    active_contracts = sum(
        1 for c in contracts
        if (c.get("status") or "").lower() in {"active", "signed", "in_progress", "executing"}
    )
    open_tasks = sum(
        1 for t in tasks
        if (t.get("status") or "").lower() in {"open", "new", "in_progress", "todo", "pending"}
    )

    # last activity across all streams
    def _dt(v):
        try:
            return v if isinstance(v, str) else (v.isoformat() if v else "")
        except Exception:
            return ""
    stamps = []
    for coll in (requests, contracts, acts, invoices):
        for d in coll:
            stamps.append(_dt(d.get("created_at")))
    if activity:
        stamps.append(_dt(activity[0].get("created_at")))
    last_activity = max([s for s in stamps if s], default=None)

    return {
        "success": True,
        "customer": build_dto(customer),
        "summary": {
            "requests_total": len(requests),
            "active_contracts": active_contracts,
            "contracts_total": len(contracts),
            "acts_total": len(acts),
            "invoices_total": len(invoices),
            "invoiced_amount": round(invoiced, 2),
            "paid_amount": round(paid, 2),
            "debt_amount": round(debt, 2),
            "overdue_amount": round(overdue, 2),
            "open_tasks": open_tasks,
            "last_activity": last_activity,
            "currency": next((i.get("currency") for i in invoices if i.get("currency")), "UAH"),
        },
    }



def _esc(v) -> str:
    import html as _html
    return _html.escape(str(v if v is not None else "—"))


def _fmt_money(v, cur="UAH") -> str:
    try:
        return f"{float(v or 0):,.2f} {cur}".replace(",", " ")
    except Exception:
        return f"{v} {cur}"


async def _gather_customer_finance(db, customer: Dict[str, Any]) -> Dict[str, Any]:
    """Shared aggregation used by the PDF card, bulk export and debt reminder."""
    customer_id = customer.get("id")
    flt = _company_filter(customer)
    inv_flt = {"$or": [
        {"customerId": customer_id}, {"customer_id": customer_id},
        *([{"company_id": customer.get("company_id")}] if customer.get("company_id") else []),
    ]}
    invoices, contracts = await asyncio.gather(
        _safe(db.invoices.find(inv_flt, {"_id": 0}).sort("created_at", -1).to_list(length=500)),
        _safe(db.waste_contracts.find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=200)),
    )

    def _amt(i):
        return _num(i.get("total") or i.get("amount"))
    cur = next((i.get("currency") for i in invoices if i.get("currency")), "UAH")
    open_invoices = [i for i in invoices if (i.get("status") or "").lower() in _OPEN_INV]
    return {
        "invoices": invoices, "contracts": contracts, "currency": cur,
        "invoiced": sum(_amt(i) for i in invoices if (i.get("status") or "").lower() != "cancelled"),
        "paid": sum(_amt(i) for i in invoices if (i.get("status") or "").lower() == "paid"),
        "debt": sum(_amt(i) for i in open_invoices),
        "overdue": sum(_amt(i) for i in invoices if (i.get("status") or "").lower() in _OVERDUE),
        "open_invoices": open_invoices,
    }


def _customer_card_html(customer: Dict[str, Any], dto: Dict[str, Any], fin: Dict[str, Any]) -> str:
    from datetime import datetime, timezone
    cur = fin["currency"]
    invoices, contracts = fin["invoices"], fin["contracts"]
    _m = lambda v: _fmt_money(v, cur)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    inv_rows = "".join(
        f"<tr><td>{_esc(i.get('number') or (i.get('id') or '')[-8:])}</td>"
        f"<td>{_esc((i.get('status') or '—'))}</td>"
        f"<td class='r'>{_m(i.get('amount') or i.get('total'))}</td>"
        f"<td>{_esc((i.get('created_at') or '')[:10])}</td></tr>"
        for i in invoices
    ) or "<tr><td colspan='4' class='muted'>Рахунків немає</td></tr>"
    con_rows = "".join(
        f"<tr><td>{_esc(c.get('number') or c.get('contract_number') or (c.get('id') or '')[-8:])}</td>"
        f"<td>{_esc(c.get('status') or '—')}</td>"
        f"<td>{_esc((c.get('valid_from') or '')[:10])} — {_esc((c.get('valid_to') or '')[:10])}</td>"
        f"<td>{_esc((c.get('created_at') or '')[:10])}</td></tr>"
        for c in contracts
    ) or "<tr><td colspan='4' class='muted'>Договорів немає</td></tr>"
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"/>
<style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  * {{ font-family: 'DejaVu Sans', Arial, sans-serif; color: #0f172a; }}
  h1 {{ font-size: 20px; margin: 0 0 2px; }}
  .sub {{ color: #64748b; font-size: 12px; }}
  .hdr {{ border-bottom: 3px solid #10b981; padding-bottom: 10px; margin-bottom: 16px; }}
  .brand {{ color: #10b981; font-weight: 700; letter-spacing: .5px; font-size: 12px; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }}
  .kpi {{ flex: 1 1 22%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px; }}
  .kpi .l {{ font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: .4px; }}
  .kpi .v {{ font-size: 15px; font-weight: 700; margin-top: 3px; }}
  .kpi.debt .v {{ color: #b91c1c; }}
  .kpi.paid .v {{ color: #047857; }}
  h2 {{ font-size: 13px; margin: 18px 0 6px; color: #0f172a; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #eef2f7; }}
  th {{ background: #f8fafc; color: #475569; text-transform: uppercase; font-size: 9px; letter-spacing: .3px; }}
  td.r, th.r {{ text-align: right; }}
  .muted {{ color: #94a3b8; text-align: center; padding: 12px; }}
  .foot {{ margin-top: 22px; color: #94a3b8; font-size: 10px; border-top: 1px solid #eef2f7; padding-top: 8px; }}
  .idrow {{ font-size: 11px; color: #475569; margin-top: 4px; }}
</style></head><body>
  <div class="hdr">
    <div class="brand">ECO.NOVA · UTILIZATION PLATFORM</div>
    <h1>Картка клієнта</h1>
    <div class="sub">{_esc(dto.get('company_name') or dto.get('full_name'))}{(' — ' + _esc(dto.get('email'))) if dto.get('email') else ''}</div>
    <div class="idrow">
      {('Компанія: ' + _esc(dto.get('company_name')) + ' &nbsp;·&nbsp; ') if dto.get('company_name') else ''}
      {('Контакт: ' + _esc(dto.get('full_name')) + ' &nbsp;·&nbsp; ') if dto.get('full_name') else ''}
      {('Тел: ' + _esc(dto.get('phone')) + ' &nbsp;·&nbsp; ') if dto.get('phone') else ''}
      Статус: {_esc(customer.get('status') or 'active')}
    </div>
  </div>
  <div class="grid">
    <div class="kpi"><div class="l">Виставлено</div><div class="v">{_m(fin['invoiced'])}</div></div>
    <div class="kpi paid"><div class="l">Оплачено</div><div class="v">{_m(fin['paid'])}</div></div>
    <div class="kpi debt"><div class="l">Борг</div><div class="v">{_m(fin['debt'])}</div></div>
    <div class="kpi debt"><div class="l">Прострочено</div><div class="v">{_m(fin['overdue'])}</div></div>
  </div>
  <h2>Рахунки ({len(invoices)})</h2>
  <table><thead><tr><th>№</th><th>Статус</th><th class="r">Сума</th><th>Створено</th></tr></thead>
  <tbody>{inv_rows}</tbody></table>
  <h2>Договори ({len(contracts)})</h2>
  <table><thead><tr><th>№</th><th>Статус</th><th>Період</th><th>Створено</th></tr></thead>
  <tbody>{con_rows}</tbody></table>
  <div class="foot">Згенеровано {generated} · ECO.NOVA CRM · Customer 360</div>
</body></html>"""


def _render_pdf(html_str: str) -> bytes:
    try:
        from weasyprint import HTML
        return HTML(string=html_str).write_pdf()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(500, f"PDF generation failed: {exc}")


@router.get("/api/customers/{customer_id}/card.pdf")
async def customer_card_pdf(customer_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    """One-click Customer Card export → PDF (реквізити, зведення, рахунки, договори)."""
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    dto = build_dto(customer)
    fin = await _gather_customer_finance(db, customer)
    pdf_bytes = _render_pdf(_customer_card_html(customer, dto, fin))
    fname = f"customer-card-{customer_id}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/api/customers/cards.zip")
async def customer_cards_zip(payload: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(require_user)):
    """Bulk export — build a Customer Card PDF for each selected customer and
    return them zipped into a single archive. RBAC-scoped: customers the caller
    may not see are silently skipped. Filenames are de-duplicated."""
    import io, zipfile, re as _re
    ids = payload.get("customer_ids") or payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "customer_ids (non-empty list) required")
    ids = [str(x) for x in ids][:100]
    db = get_db()

    buf = io.BytesIO()
    exported, skipped = 0, 0
    used_names: set = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cid in ids:
            cust = await db.customers.find_one({"id": cid}, {"_id": 0, "password": 0, "password_hash": 0})
            if not cust or not staff_can_see_customer(current_user, cust):
                skipped += 1
                continue
            try:
                dto = build_dto(cust)
                fin = await _gather_customer_finance(db, cust)
                pdf_bytes = _render_pdf(_customer_card_html(cust, dto, fin))
                base = _re.sub(r"[^\w\-.]+", "_", (dto.get("company_name") or dto.get("full_name") or cid))[:40] or cid
                fname = f"{base}.pdf"
                n = 2
                while fname in used_names:
                    fname = f"{base}-{n}.pdf"; n += 1
                used_names.add(fname)
                zf.writestr(fname, pdf_bytes)
                exported += 1
            except Exception:
                skipped += 1
    if exported == 0:
        raise HTTPException(404, "No accessible customers to export")
    buf.seek(0)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={
                        "Content-Disposition": f'attachment; filename="customer-cards-{stamp}.zip"',
                        "X-Exported-Count": str(exported), "X-Skipped-Count": str(skipped),
                    })


@router.post("/api/customers/{customer_id}/debt-reminder")
async def customer_debt_reminder(customer_id: str, payload: Dict[str, Any] = Body(default={}),
                                 current_user: Dict[str, Any] = Depends(require_user)):
    """Send a debt-reminder email to the customer in one click.

    Reuses the platform email pipeline (Resend/SMTP if an admin configured a
    provider, otherwise a dry-run record is written to the outbox — we report
    the real mode honestly, never a fake 'sent'). Also drops a timeline event.
    """
    db = get_db()
    customer = await _load_customer_or_403(customer_id, current_user)
    dto = build_dto(customer)
    to = (dto.get("email") or "").strip()
    if not to:
        raise HTTPException(400, "У клієнта не вказано email")

    fin = await _gather_customer_finance(db, customer)
    debt = fin["debt"]
    if debt <= 0:
        raise HTTPException(400, "У клієнта немає непогашеного боргу")

    cur = fin["currency"]
    _m = lambda v: _fmt_money(v, cur)
    name = dto.get("company_name") or dto.get("full_name") or "Шановний клієнте"
    rows = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>{_esc(i.get('number') or (i.get('id') or '')[-8:])}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{_esc((i.get('created_at') or '')[:10])}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:right'>{_m(i.get('amount') or i.get('total'))}</td></tr>"
        for i in fin["open_invoices"]
    )
    custom_note = _esc(payload.get("note") or "")
    subject = f"Нагадування про заборгованість — {_m(debt)}"
    html = f"""<div style="font-family:Arial,sans-serif;color:#0f172a;max-width:560px">
      <div style="border-bottom:3px solid #10b981;padding-bottom:8px;margin-bottom:16px">
        <span style="color:#10b981;font-weight:700;letter-spacing:.5px">ECO.NOVA</span>
      </div>
      <p>Шановні {_esc(name)},</p>
      <p>Нагадуємо про наявну заборгованість за послуги з утилізації відходів на суму
         <strong style="color:#b91c1c">{_m(debt)}</strong>.</p>
      {f'<p>{custom_note}</p>' if custom_note else ''}
      <table style="border-collapse:collapse;width:100%;font-size:13px;margin:12px 0">
        <thead><tr style="background:#f8fafc">
          <th style="text-align:left;padding:6px 10px">Рахунок №</th>
          <th style="text-align:left;padding:6px 10px">Дата</th>
          <th style="text-align:right;padding:6px 10px">Сума</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p>Просимо здійснити оплату найближчим часом. Якщо оплату вже здійснено — просто проігноруйте цей лист.</p>
      <p style="color:#64748b;font-size:12px;margin-top:20px">З повагою, команда ECO.NOVA</p>
    </div>"""
    text = f"Шановні {name}, нагадуємо про заборгованість на суму {_m(debt)} за послуги з утилізації відходів. Просимо здійснити оплату."

    try:
        from notifications import EmailChannel
        result = await EmailChannel(db).send(
            to=to, subject=subject, html=html, text=text,
            event="debt_reminder",
            context={"customer_id": customer_id, "debt": debt, "currency": cur,
                     "invoice_count": len(fin["open_invoices"]), "by": current_user.get("email")},
        )
    except Exception as exc:
        raise HTTPException(500, f"Email dispatch failed: {exc}")

    mode = (result or {}).get("mode") or "unknown"
    status = (result or {}).get("status") or ("sent" if (result or {}).get("ok") else "failed")
    provider_error = (result or {}).get("error")
    delivered = bool((result or {}).get("ok")) and mode in ("resend", "smtp", "mock")

    # Honest timeline state: delivered / failed / dry_run
    if delivered:
        tl_msg = f"Нагадування про борг {_m(debt)} — надіслано клієнту ({mode})"
        ui_msg = "Лист-нагадування надіслано клієнту"
    elif status == "failed":
        tl_msg = f"Нагадування про борг {_m(debt)} — помилка надсилання (провайдер відхилив)"
        ui_msg = "Помилка надсилання: провайдер email відхилив лист. Перевірте налаштування в Адмін → Інтеграції."
    else:  # dry_run / queued
        tl_msg = f"Нагадування про борг {_m(debt)} — сформовано (dry-run, email-провайдер не налаштований)"
        ui_msg = "Нагадування сформовано та поставлено в чергу (email-провайдер не налаштований в Адмін → Інтеграції)"

    # Timeline event (best-effort) so the reminder shows in the activity stream
    try:
        from datetime import datetime, timezone
        await db.waste_activity.insert_one({
            "id": f"dr_{(result or {}).get('id') or customer_id}",
            "company_id": customer.get("company_id"),
            "customer_id": customer_id,
            "event": "debt_reminder",
            "email_status": status,
            "message": tl_msg,
            "by": current_user.get("email"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {
        "success": True, "delivered": delivered, "mode": mode, "status": status,
        "sent_to": to, "debt": debt, "currency": cur,
        "invoice_count": len(fin["open_invoices"]),
        "provider_id": (result or {}).get("provider_id"),
        "error": provider_error,
        "message": ui_msg,
    }
