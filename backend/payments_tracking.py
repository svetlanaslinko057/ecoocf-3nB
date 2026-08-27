"""
BIBI Cars — Payments Tracking (P1.2-payments)
═══════════════════════════════════════════════════════════════════════════

Реальный учёт денег: сколько ПРИШЛО, не «сколько надо».

Архитектура:
  payments        =  факт прихода денег (immutable; void вместо delete)
  deal_financials =  сколько надо (templates → breakdown)
  deal.status     =  состояние сделки (unpaid/partial/paid → auto-close)

Принцип:
  • payment связан с deal (НЕ с invoice/breakdown — клиент платит за сделку)
  • payment.method отражает реальный путь денег (bank|stripe|cash_off_books)
  • after confirm — нельзя редактировать; только void (с reason)
  • переплата разрешена (фиксируем как есть)
  • naличка без proof — OK; банковский без proof — warning, но не блок

Auto-status:
  paid_total = sum(amounts) для status=confirmed (без voided)
  remaining = breakdown.totals.total_all - paid_total
  status:  unpaid (0) | partial (>0 < total) | paid (>= total) | overpaid (> total)

При переходе в `paid` (>= 100%): сделка авто-двигается в
`ready_for_delivery` (если ещё не дальше), эмитится событие
`deal_paid_in_full` и пишется audit_event.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from security import require_manager_or_admin, require_admin

# Phase 5.4 / C-4h — db_runtime accessor (module-level function reference).
# Only the `get_db` CALLABLE is imported at module-load time. Every
# `_db()` call resolves the live Motor handle via `get_db()`, preserving
# the call-time semantics of the legacy `from server import db` bridge.
# This module hosts payment-tracking refund + reminder code paths that
# are orchestration-adjacent — capture timing matters.
from app.core.db_runtime import get_db  # noqa: E402 (C-4h: lazy-bridge → accessor)


# ════════════════════════════════════════════════════════════════════════════
#   1.  CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

PAYMENT_METHODS: List[str] = ["bank", "stripe", "cash_off_books", "internal", "other"]
PAYMENT_STATUSES: List[str] = ["pending", "confirmed", "voided"]
DEAL_PAYMENT_STATUSES: List[str] = ["unpaid", "partial", "paid", "overpaid"]

#: Стадии сделки, ИЗ которых разрешён auto-advance в ready_for_delivery.
#: Не двигаем назад и не из заведомо терминальных стадий.
STAGES_ALLOWING_AUTO_PAID: tuple = (
    "auction_won",
    "final_contract_sent",
    "final_contract_signed",
    "after_win_payment_paid",
    "in_transit_to_rotterdam",
    "arrived_rotterdam",
    "customs_calculated",
    "final_payment_paid",
    "in_transit_to_bg",
)

#: Целевая стадия после полной оплаты.
TARGET_STAGE_AFTER_FULL_PAYMENT = "in_transit_to_bg"

# Внимание: реальный список стадий в legal_workflow.DEAL_STAGES не содержит
# буквальной "ready_for_delivery", но содержит сопоставимый прогресс (delivered,
# closed). Мы используем "in_transit_to_bg" как "готов к доставке клиенту"
# флаг, а отдельно ставим deal.payment_status="paid" — это и есть
# «готов к доставке» в бизнес-смысле. Сделано так чтобы не ломать существующий
# pipeline валидаторами `_can_advance_deal`.


# ════════════════════════════════════════════════════════════════════════════
#   2.  PYDANTIC MODELS
# ════════════════════════════════════════════════════════════════════════════

class PaymentCreateIn(BaseModel):
    amount: float = Field(..., gt=0, description="EUR; positive only")
    method: str = Field(..., description=f"One of {PAYMENT_METHODS}")
    currency: str = Field("EUR", max_length=3)
    proof_url: Optional[str] = Field(None, max_length=1024,
                                      description="URL of proof attachment (bank statement, photo)")
    bank_received_at: Optional[str] = Field(None, description="ISO datetime; default = now")
    note: Optional[str] = Field(None, max_length=500)
    auto_confirm: bool = Field(False,
                                description="If True — create as confirmed in one step (admin only)")

    @validator("method")
    def _method_valid(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError(f"method must be one of {PAYMENT_METHODS}")
        return v


class PaymentConfirmIn(BaseModel):
    bank_received_at: Optional[str] = None
    proof_url: Optional[str] = Field(None, max_length=1024)
    note: Optional[str] = Field(None, max_length=500)


class PaymentVoidIn(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


# ════════════════════════════════════════════════════════════════════════════
#   3.  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    """Lazy Mongo handle — resolves at call-time, not at module-load time.

    Phase 5.4 / C-4h — migrated to ``app.core.db_runtime.get_db()``.
    Critical for this module because the refund cron + payment-reminder
    code paths (`recompute_deal_payment_status`, `_audit_safe`, etc.)
    are orchestration-adjacent: a module-load-time db capture here would
    silently freeze the handle for every subsequent payment write.
    Only the ``get_db`` callable is imported at top-of-file; the handle
    is read fresh on every ``_db()`` call.
    """
    return get_db()


async def _audit_safe(**kwargs) -> None:
    try:
        from app.core.domain_audit import _audit
        await _audit(**kwargs)
    except Exception:
        import logging as _lg
        _lg.getLogger("bibi.payments.audit").warning("audit dispatch failed", exc_info=True)


async def _emit_safe(event: str, payload: Dict[str, Any]) -> None:
    try:
        from notifications import bus as _bus  # type: ignore
        await _bus.emit(event, payload)
    except Exception:
        pass


async def _resolve_deal_breakdown_total(db, deal_id: str) -> Dict[str, Any]:
    """
    Returns {'total_all', 'total_official', 'total_cash', 'has_breakdown'}.
    Берём САМЫЙ ПОСЛЕДНИЙ breakdown сделки (final > after_win, по created_at desc).
    Если ни одного — has_breakdown=False, totals=0.
    """
    # Prefer 'final' kind first (it's the comprehensive one), fallback to 'after_win'
    final = await db.invoices.find_one(
        {"dealId": deal_id, "kind": "final"},
        {"_id": 0, "totals": 1, "amount": 1},
        sort=[("created_at", -1)],
    )
    if final:
        tt = final.get("totals") or {}
        return {
            "has_breakdown": True,
            "kind": "final",
            "total_all": float(tt.get("total_all") or final.get("amount") or 0),
            "total_official": float(tt.get("total_official") or 0),
            "total_cash": float(tt.get("total_cash") or 0),
        }

    aw = await db.invoices.find_one(
        {"sourceAuctionWonDealId": deal_id},
        {"_id": 0, "totals": 1, "amount": 1, "kind": 1},
        sort=[("created_at", -1)],
    )
    if aw:
        tt = aw.get("totals") or {}
        return {
            "has_breakdown": True,
            "kind": aw.get("kind") or "after_win",
            "total_all": float(tt.get("total_all") or aw.get("amount") or 0),
            "total_official": float(tt.get("total_official") or 0),
            "total_cash": float(tt.get("total_cash") or 0),
        }

    return {"has_breakdown": False, "kind": None,
            "total_all": 0.0, "total_official": 0.0, "total_cash": 0.0}


def _classify_status(paid: float, total: float) -> str:
    if total <= 0:
        return "unpaid" if paid <= 0 else "overpaid"
    if paid <= 0:
        return "unpaid"
    if paid + 0.01 < total:
        return "partial"
    if paid > total + 0.01:
        return "overpaid"
    return "paid"


async def recompute_deal_payment_status(deal_id: str) -> Dict[str, Any]:
    """
    Single source of truth: пересчитать paid_total/remaining/status для сделки
    и записать в `deal.payment_status` + `deal.payment_summary`. Идемпотентно.

    Возвращает dict со статистикой. Также эмитит `deal_paid_in_full` событие
    при первом переходе в `paid`.
    """
    db = _db()
    # Sum confirmed payments (voided excluded)
    pipe = [
        {"$match": {"deal_id": deal_id, "status": "confirmed"}},
        {"$group": {
            "_id": None,
            "paid_total": {"$sum": "$amount"},
            "paid_official": {"$sum": {"$cond": [
                {"$in": ["$method", ["bank", "stripe", "internal"]]}, "$amount", 0,
            ]}},
            "paid_cash": {"$sum": {"$cond": [
                {"$eq": ["$method", "cash_off_books"]}, "$amount", 0,
            ]}},
            "count": {"$sum": 1},
        }},
    ]
    agg = await db.payments.aggregate(pipe).to_list(length=1)
    paid_total = float(agg[0]["paid_total"]) if agg else 0.0
    paid_official = float(agg[0]["paid_official"]) if agg else 0.0
    paid_cash = float(agg[0]["paid_cash"]) if agg else 0.0
    count = int(agg[0]["count"]) if agg else 0

    bd = await _resolve_deal_breakdown_total(db, deal_id)
    total_all = bd["total_all"]
    remaining = round(total_all - paid_total, 2)
    new_status = _classify_status(paid_total, total_all)

    summary = {
        "paid_total": round(paid_total, 2),
        "paid_official": round(paid_official, 2),
        "paid_cash": round(paid_cash, 2),
        "total_all": round(total_all, 2),
        "total_official": round(bd["total_official"], 2),
        "total_cash": round(bd["total_cash"], 2),
        "remaining": remaining,
        "payment_count": count,
        "breakdown_kind": bd["kind"],
        "has_breakdown": bd["has_breakdown"],
        "ts": _now_iso(),
    }

    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"payment_status": 1, "stage": 1, "status": 1},
    )
    prev_status = (deal or {}).get("payment_status") or "unpaid"
    cur_stage = (deal or {}).get("stage") or (deal or {}).get("status")

    set_doc: Dict[str, Any] = {
        "payment_status": new_status,
        "payment_summary": summary,
        "updated_at": _now_iso(),
    }

    # Auto-advance once on paid transition
    auto_advanced = False
    if (
        new_status in ("paid", "overpaid")
        and prev_status not in ("paid", "overpaid")
        and cur_stage in STAGES_ALLOWING_AUTO_PAID
    ):
        # We don't override later stages
        from app.core.domain_audit import DEAL_STAGES  # type: ignore
        try:
            cur_idx = DEAL_STAGES.index(cur_stage) if cur_stage in DEAL_STAGES else -1
            tgt_idx = DEAL_STAGES.index(TARGET_STAGE_AFTER_FULL_PAYMENT)
            if tgt_idx > cur_idx:
                set_doc["stage"] = TARGET_STAGE_AFTER_FULL_PAYMENT
                set_doc["status"] = TARGET_STAGE_AFTER_FULL_PAYMENT
                auto_advanced = True
        except Exception:
            pass

    push_doc: Dict[str, Any] = {}
    if auto_advanced:
        push_doc["stage_history"] = {
            "from": cur_stage,
            "to": TARGET_STAGE_AFTER_FULL_PAYMENT,
            "by": "system:payments",
            "by_role": "system",
            "at": _now_iso(),
            "note": (f"auto: payment_status={new_status} "
                     f"(paid {paid_total:.2f} / {total_all:.2f} EUR)"),
            "source": "payments_auto_close",
        }

    update_ops: Dict[str, Any] = {"$set": set_doc}
    if push_doc:
        update_ops["$push"] = push_doc

    await db.deals.update_one({"$or": [{"id": deal_id}, {"_id": deal_id}]}, update_ops)

    # Emit event on first paid transition
    if new_status in ("paid", "overpaid") and prev_status not in ("paid", "overpaid"):
        await _emit_safe("deal_paid_in_full", {
            "dealId": deal_id, "paid_total": paid_total, "total_all": total_all,
            "auto_advanced": auto_advanced,
        })
        await _audit_safe(
            event_type="deal_paid_in_full", entity_type="deal",
            entity_id=deal_id, deal_id=deal_id,
            payload={**summary, "auto_advanced": auto_advanced,
                     "from_status": prev_status},
        )

    return {
        "deal_id": deal_id,
        "payment_status": new_status,
        "summary": summary,
        "auto_advanced": auto_advanced,
        "prev_status": prev_status,
    }


# ════════════════════════════════════════════════════════════════════════════
#   4.  ROUTER
# ════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api", tags=["payments-tracking"])


@router.post("/legal/deals/{deal_id}/payments",
             dependencies=[Depends(require_manager_or_admin)])
async def create_payment(
    deal_id: str,
    payload: PaymentCreateIn = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """
    Зарегистрировать платёж по сделке. Статус = pending пока менеджер не
    подтвердит через /confirm. Если admin делает auto_confirm=True — сразу
    confirmed (для cash платежей которые уже на руках).

    Edge cases:
      • Bank без proof_url — warning в response (не блок)
      • Cash без proof — OK
      • Сделка не найдена → 404
      • Сделка в cancelled — отказ 409
    """
    db = _db()
    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"id": 1, "stage": 1, "status": 1, "customerId": 1, "customer_id": 1},
    )
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")

    stage = deal.get("stage") or deal.get("status") or ""
    if stage == "cancelled":
        raise HTTPException(409, f"Cannot register payment on cancelled deal {deal_id}")

    role = (user.get("role") or "").lower()
    is_admin = role in ("admin", "master_admin", "owner")

    warnings: List[str] = []
    if payload.method == "bank" and not payload.proof_url:
        warnings.append(
            "Bank payment without proof_url — recommended to attach a statement/screenshot."
        )

    payment_id = f"pay_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}"
    now = _now_iso()
    customer_id = deal.get("customerId") or deal.get("customer_id")

    initial_status = "confirmed" if (payload.auto_confirm and is_admin) else "pending"

    doc = {
        "id": payment_id,
        "deal_id": deal_id,
        "customer_id": customer_id,
        "amount": round(float(payload.amount), 2),
        "currency": payload.currency,
        "method": payload.method,
        "is_official": payload.method in ("bank", "stripe", "internal"),
        "status": initial_status,
        "proof_url": payload.proof_url,
        "bank_received_at": payload.bank_received_at or (now if initial_status == "confirmed" else None),
        "note": payload.note,
        "created_by": user.get("email") or user.get("id"),
        "created_at": now,
        "updated_at": now,
        "confirmed_by": (user.get("email") or user.get("id")) if initial_status == "confirmed" else None,
        "confirmed_at": now if initial_status == "confirmed" else None,
        "voided": False,
        "history": [{
            "event": "created", "status": initial_status, "at": now,
            "by": user.get("email") or user.get("id"),
            "data": {"amount": payload.amount, "method": payload.method,
                     "auto_confirm": payload.auto_confirm and is_admin,
                     "warnings": warnings},
        }],
    }
    await db.payments.insert_one(doc)
    doc.pop("_id", None)

    await _audit_safe(
        event_type=("payment_confirmed" if initial_status == "confirmed" else "payment_created"),
        entity_type="payment", entity_id=payment_id, user=user,
        deal_id=deal_id, customer_id=customer_id,
        payload={"amount": payload.amount, "method": payload.method,
                 "is_official": doc["is_official"],
                 "auto_confirmed": initial_status == "confirmed",
                 "warnings": warnings},
    )

    summary_update = None
    if initial_status == "confirmed":
        summary_update = await recompute_deal_payment_status(deal_id)

    return {
        "success": True, "payment": doc,
        "warnings": warnings,
        "summary": (summary_update or {}).get("summary"),
        "auto_advanced": (summary_update or {}).get("auto_advanced", False),
    }


@router.post("/legal/payments/{payment_id}/confirm",
             dependencies=[Depends(require_manager_or_admin)])
async def confirm_payment(
    payment_id: str,
    payload: PaymentConfirmIn = Body(default=PaymentConfirmIn()),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """
    Подтвердить платёж (деньги пришли).

    Идемпотентно: повтор на уже-confirmed возвращает 200 + idempotent=True.
    Voided платёж confirm нельзя → 409.
    """
    db = _db()
    p = await db.payments.find_one({"id": payment_id})
    if not p:
        raise HTTPException(404, f"Payment {payment_id} not found")

    if p.get("status") == "confirmed":
        return {
            "success": True, "idempotent": True,
            "payment_id": payment_id, "status": "confirmed",
            "payment": {k: v for k, v in p.items() if k != "_id"},
        }
    if p.get("status") == "voided":
        raise HTTPException(409, f"Payment {payment_id} is voided — cannot confirm")
    if p.get("status") != "pending":
        raise HTTPException(409, f"Cannot confirm from status {p.get('status')!r}")

    now = _now_iso()
    set_doc: Dict[str, Any] = {
        "status": "confirmed",
        "confirmed_by": user.get("email") or user.get("id"),
        "confirmed_at": now,
        "updated_at": now,
    }
    if payload.bank_received_at:
        set_doc["bank_received_at"] = payload.bank_received_at
    elif not p.get("bank_received_at"):
        set_doc["bank_received_at"] = now
    if payload.proof_url:
        set_doc["proof_url"] = payload.proof_url

    await db.payments.update_one(
        {"id": payment_id, "status": "pending"},
        {
            "$set": set_doc,
            "$push": {"history": {"event": "confirmed", "at": now,
                                  "by": user.get("email") or user.get("id"),
                                  "data": {"note": payload.note}}},
        },
    )

    await _audit_safe(
        event_type="payment_confirmed", entity_type="payment",
        entity_id=payment_id, user=user,
        deal_id=p.get("deal_id"), customer_id=p.get("customer_id"),
        payload={"amount": p.get("amount"), "method": p.get("method"),
                 "note": payload.note},
    )

    summary_update = await recompute_deal_payment_status(p["deal_id"])

    fresh = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    return {
        "success": True, "idempotent": False,
        "payment_id": payment_id, "status": "confirmed",
        "payment": fresh,
        "summary": summary_update.get("summary"),
        "auto_advanced": summary_update.get("auto_advanced", False),
    }


@router.post("/legal/payments/{payment_id}/void",
             dependencies=[Depends(require_admin)])
async def void_payment(
    payment_id: str,
    payload: PaymentVoidIn = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """
    Отменить платёж (admin only). Не удаляет запись — ставит status=voided.
    Это сохраняет audit trail и помогает разруливать ошибки ввода.
    """
    db = _db()
    p = await db.payments.find_one({"id": payment_id})
    if not p:
        raise HTTPException(404, f"Payment {payment_id} not found")

    if p.get("status") == "voided":
        return {
            "success": True, "idempotent": True,
            "payment_id": payment_id, "status": "voided",
        }

    now = _now_iso()
    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {
            "status": "voided",
            "voided": True,
            "voided_at": now,
            "voided_by": user.get("email") or user.get("id"),
            "void_reason": payload.reason,
            "updated_at": now,
        },
         "$push": {"history": {"event": "voided", "at": now,
                                "by": user.get("email") or user.get("id"),
                                "data": {"reason": payload.reason,
                                         "prev_status": p.get("status")}}}},
    )

    await _audit_safe(
        event_type="payment_voided", entity_type="payment",
        entity_id=payment_id, user=user,
        deal_id=p.get("deal_id"), customer_id=p.get("customer_id"),
        payload={"amount": p.get("amount"), "method": p.get("method"),
                 "prev_status": p.get("status"), "reason": payload.reason},
    )

    summary_update = await recompute_deal_payment_status(p["deal_id"])

    return {
        "success": True, "idempotent": False,
        "payment_id": payment_id, "status": "voided",
        "summary": summary_update.get("summary"),
    }


@router.get("/legal/deals/{deal_id}/payments",
            dependencies=[Depends(require_manager_or_admin)])
async def list_deal_payments(deal_id: str):
    """
    Все платежи + summary с paid/remaining/status.
    Voided платежи возвращаются, но НЕ участвуют в paid_total.
    """
    db = _db()
    cursor = db.payments.find({"deal_id": deal_id}, {"_id": 0}).sort("created_at", -1)
    payments = await cursor.to_list(length=200)
    summary_update = await recompute_deal_payment_status(deal_id)
    return {
        "success": True, "deal_id": deal_id,
        "payments": payments, "total": len(payments),
        "summary": summary_update["summary"],
        "payment_status": summary_update["payment_status"],
    }


@router.get("/legal/payments/{payment_id}",
            dependencies=[Depends(require_manager_or_admin)])
async def get_payment(payment_id: str):
    db = _db()
    p = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, f"Payment {payment_id} not found")
    return {"success": True, "payment": p}


@router.post("/legal/deals/{deal_id}/payments/recompute",
             dependencies=[Depends(require_manager_or_admin)])
async def recompute_payment_status(deal_id: str):
    """Manual recompute — для dev/debug. Идемпотентно."""
    res = await recompute_deal_payment_status(deal_id)
    return {"success": True, **res}


# ════════════════════════════════════════════════════════════════════════════
#   5.  STARTUP HELPERS
# ════════════════════════════════════════════════════════════════════════════

async def ensure_indexes(db) -> None:
    try:
        await db.payments.create_index([("id", 1)], unique=True)
        await db.payments.create_index([("deal_id", 1), ("status", 1)])
        await db.payments.create_index([("deal_id", 1), ("created_at", -1)])
        await db.payments.create_index([("customer_id", 1), ("created_at", -1)])
        await db.payments.create_index([("status", 1), ("created_at", -1)])
    except Exception:
        import logging as _lg
        _lg.getLogger("bibi.payments").warning("index creation failed", exc_info=True)
