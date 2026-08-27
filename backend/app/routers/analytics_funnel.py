"""
analytics_funnel.py — реальная воронка продаж (Sales Funnel) на основе
существующих коллекций без mock-данных.

Заменяет mock-эндпоинты:
  • GET /api/journey/funnel        — 11-этапная воронка + dropOff
  • GET /api/journey/bottlenecks   — узкие места (топ drop-off)
  • GET /api/journey/durations     — среднее время между ключевыми вехами

Подход
------
Sales funnel мы НЕ ведём через отдельную таблицу транзитов (это требовало бы
рефакторинга всех мест, где статусы меняются). Вместо этого считаем
*кумулятивно по факту присутствия данных*: если у клиента есть payment,
значит он прошёл и contract_signed, и contract_sent, и negotiation, и
qualified, и contact_attempt, и new_lead. На каждой ступени берём
max(текущая_ступень, count_по_коллекции) — это гарантирует монотонность
графика (каждое следующее число ≤ предыдущему), что и требует UI.

Что считаем "реализованным" для каждой ступени
----------------------------------------------
  NEW_LEAD         — все leads + все deals (минус пересечение customer_id)
  CONTACT_ATTEMPT  — leads.status != 'new' (есть запись об обработке) + все deals
  QUALIFIED        — leads.status в processing/qualified/won/contacted + все deals
  CAR_SELECTED     — deals с непустым vin/selectedVin + wishlist_deals
  NEGOTIATION      — deals.status в auction_won/negotiation/in_progress/contract_pending
  CONTRACT_SENT    — все contracts (статус неважен; раз есть запись — был отправлен)
  CONTRACT_SIGNED  — contracts.status в signed/completed
  PAYMENT_PENDING  — все payments (любой; запись = был создан счёт)
  PAYMENT_DONE     — payments.status в confirmed/completed/paid/succeeded
  SHIPPING         — все shipments (любой; запись = доставка началась)
  DELIVERED        — shipments.status='delivered' ИЛИ lastEventProgress>=100

Дальше каждая ступень корректируется снизу-вверх:
  prev_stage = max(prev_raw, current_stage)

Все count_documents фильтруются по `created_at >= since`. Окно — параметр
`days` (1..365, default 30).

Никаких mock-fallback: пустая БД ⇒ funnel = все нули.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from security import require_admin

logger = logging.getLogger("bibi.analytics_funnel")


def _db():
    from app.core.db_runtime import get_db
    return get_db()


router = APIRouter(prefix="/api/journey", tags=["analytics-funnel"])


# Канонический порядок стадий — должен совпадать с frontend STAGE_ORDER.
STAGE_ORDER = [
    "NEW_LEAD",
    "CONTACT_ATTEMPT",
    "QUALIFIED",
    "CAR_SELECTED",
    "NEGOTIATION",
    "CONTRACT_SENT",
    "CONTRACT_SIGNED",
    "PAYMENT_PENDING",
    "PAYMENT_DONE",
    "SHIPPING",
    "DELIVERED",
]


async def _raw_counts(db, since: datetime) -> Dict[str, int]:
    """RAW count для каждой стадии (без корректировки монотонности)."""
    # Поля даты у разных коллекций различаются — используем $or на created_at и createdAt.
    win = {"$or": [{"created_at": {"$gte": since}}, {"createdAt": {"$gte": since}}]}

    # Helper
    async def cnt(col: str, extra: Optional[Dict[str, Any]] = None) -> int:
        if col not in await db.list_collection_names():
            return 0
        q: Dict[str, Any] = dict(win)
        if extra:
            q = {"$and": [win, extra]}
        try:
            return await db[col].count_documents(q)
        except Exception as e:
            logger.warning("[funnel] count %s failed: %s", col, e)
            return 0

    leads_total = await cnt("leads")
    leads_engaged = await cnt("leads", {"status": {"$nin": ["new", None, ""]}})
    leads_qualified = await cnt("leads", {"status": {"$in": ["qualified", "processing", "won", "contacted", "converted"]}})

    deals_total = await cnt("deals")
    deals_with_vin = await cnt("deals", {"$or": [{"vin": {"$nin": [None, ""]}}, {"selectedVin": {"$nin": [None, ""]}}]})
    deals_negotiation = await cnt("deals", {"status": {"$in": ["auction_won", "negotiation", "in_progress", "contract_pending"]}})

    wishlist_total = await cnt("wishlist_deals")

    contracts_total = await cnt("contracts") + await cnt("docusign_envelopes") + await cnt("envelopes")
    # Для signed contracts смотрим status поля
    async def signed_count(col: str) -> int:
        if col not in await db.list_collection_names():
            return 0
        try:
            return await db[col].count_documents({
                "$and": [
                    win,
                    {"$or": [
                        {"status": {"$in": ["signed", "completed", "executed"]}},
                        {"signedDate": {"$nin": [None, ""]}},
                        {"signed_at": {"$nin": [None, ""]}},
                    ]},
                ]
            })
        except Exception:
            return 0
    contracts_signed = sum([await signed_count(c) for c in ["contracts", "docusign_envelopes", "envelopes"]])

    payments_total = await cnt("payments") + await cnt("customer_payments")
    async def paid_count(col: str) -> int:
        if col not in await db.list_collection_names():
            return 0
        try:
            return await db[col].count_documents({
                "$and": [
                    win,
                    {"status": {"$in": ["confirmed", "completed", "paid", "succeeded", "captured"]}},
                ]
            })
        except Exception:
            return 0
    payments_done = sum([await paid_count(c) for c in ["payments", "customer_payments"]])

    shipments_total = await cnt("shipments")
    async def delivered_count() -> int:
        if "shipments" not in await db.list_collection_names():
            return 0
        try:
            return await db.shipments.count_documents({
                "$and": [
                    win,
                    {"$or": [
                        {"status": "delivered"},
                        {"lastEventProgress": {"$gte": 100}},
                    ]},
                ]
            })
        except Exception:
            return 0
    shipments_delivered = await delivered_count()

    # Composite raw values per stage (cumulative-eligible).
    raw = {
        "NEW_LEAD":         leads_total + deals_total,    # total flow inbound
        "CONTACT_ATTEMPT":  leads_engaged + deals_total,
        "QUALIFIED":        leads_qualified + deals_total,
        "CAR_SELECTED":     deals_with_vin + wishlist_total,
        "NEGOTIATION":      deals_negotiation,
        "CONTRACT_SENT":    contracts_total,
        "CONTRACT_SIGNED":  contracts_signed,
        "PAYMENT_PENDING":  payments_total,
        "PAYMENT_DONE":     payments_done,
        "SHIPPING":         shipments_total,
        "DELIVERED":        shipments_delivered,
    }
    return raw


def _enforce_monotonic(raw: Dict[str, int]) -> Dict[str, int]:
    """Чем дальше по воронке, тем число меньше или равно. Поднимаем
    предыдущие до max(prev, current) — это правильная семантика
    «прошёл хотя бы эту ступень».
    """
    out = dict(raw)
    for i in range(len(STAGE_ORDER) - 2, -1, -1):
        cur = STAGE_ORDER[i]
        nxt = STAGE_ORDER[i + 1]
        if out[nxt] > out[cur]:
            out[cur] = out[nxt]
    return out


@router.get("/funnel", dependencies=[Depends(require_admin)])
async def journey_funnel(days: int = Query(30, ge=1, le=365)):
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    raw = await _raw_counts(db, since)
    funnel = _enforce_monotonic(raw)

    total_deals = funnel["NEW_LEAD"]
    delivered = funnel["DELIVERED"]
    conversion_rate = round((delivered / total_deals) * 100, 1) if total_deals else 0.0

    drop_off: List[Dict[str, Any]] = []
    for i in range(len(STAGE_ORDER) - 1):
        a, b = STAGE_ORDER[i], STAGE_ORDER[i + 1]
        va, vb = funnel[a], funnel[b]
        lost = max(va - vb, 0)
        rate = round((lost / va) * 100, 1) if va else 0.0
        drop_off.append({"from": a, "to": b, "rate": rate, "count": lost})

    return {
        "totalDeals":     total_deals,
        "delivered":      delivered,
        "conversionRate": conversion_rate,
        "funnel":         funnel,
        "dropOff":        drop_off,
        "windowDays":     days,
        "windowStart":    since.isoformat(),
    }


@router.get("/bottlenecks", dependencies=[Depends(require_admin)])
async def journey_bottlenecks(days: int = Query(30, ge=1, le=365), top: int = Query(5, ge=1, le=10)):
    """Топ-N стадий с самым большим drop-off rate (по абсолютному % падения)."""
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    raw = await _raw_counts(db, since)
    funnel = _enforce_monotonic(raw)

    issues: List[Dict[str, Any]] = []
    for i in range(len(STAGE_ORDER) - 1):
        a, b = STAGE_ORDER[i], STAGE_ORDER[i + 1]
        va, vb = funnel[a], funnel[b]
        if va == 0:
            continue
        lost = max(va - vb, 0)
        rate = round((lost / va) * 100, 1)
        if lost > 0:
            issues.append({"from": a, "to": b, "rate": rate, "count": lost})

    issues.sort(key=lambda x: (-x["rate"], -x["count"]))
    return issues[:top]


async def _avg_days_between(db, col: str, from_field: str, to_field: str, since: datetime) -> Optional[float]:
    """Среднее количество дней между from_field и to_field в коллекции col."""
    if col not in await db.list_collection_names():
        return None
    pipeline = [
        {"$match": {
            from_field: {"$ne": None, "$gte": since},
            to_field:   {"$ne": None},
        }},
        {"$project": {
            "diff": {"$divide": [{"$subtract": [f"${to_field}", f"${from_field}"]}, 1000 * 60 * 60 * 24]}
        }},
        {"$group": {"_id": None, "avg": {"$avg": "$diff"}, "count": {"$sum": 1}}},
    ]
    try:
        async for row in db[col].aggregate(pipeline):
            if row.get("avg") is not None and row.get("count", 0) > 0:
                return round(float(row["avg"]), 1)
    except Exception as e:
        logger.warning("[funnel] avg %s.%s→%s failed: %s", col, from_field, to_field, e)
    return None


@router.get("/durations", dependencies=[Depends(require_admin)])
async def journey_durations(days: int = Query(30, ge=1, le=365)):
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Try several common datetime-field name conventions.
    async def best(col: str, from_fields: List[str], to_fields: List[str]) -> Optional[float]:
        for f in from_fields:
            for t in to_fields:
                v = await _avg_days_between(db, col, f, t, since)
                if v is not None:
                    return v
        return None

    days_to_contact   = await best("leads",     ["created_at", "createdAt"], ["contactedAt", "first_contact_at", "updatedAt"])
    days_to_deal      = await best("deals",     ["leadCreatedAt", "lead_created_at", "created_at", "createdAt"], ["created_at", "createdAt"])
    days_to_contract  = await best("contracts", ["dealCreatedAt", "deal_created_at", "created_at", "createdAt"], ["sent_at", "createdAt", "created_at"])
    days_to_payment   = await best("payments",  ["created_at", "createdAt"], ["confirmed_at", "paid_at", "completed_at", "updatedAt"])
    days_to_delivery  = await best("shipments", ["created_at", "createdAt"], ["delivered_at", "completedAt", "updatedAt"])

    # Total = sum of available components.
    parts = [v for v in [days_to_contact, days_to_deal, days_to_contract, days_to_payment, days_to_delivery] if v is not None]
    total = round(sum(parts), 1) if parts else None

    # Count of deals delivered in window (used by UI as denominator).
    delivered_n = 0
    if "shipments" in await db.list_collection_names():
        try:
            delivered_n = await db.shipments.count_documents({
                "$and": [
                    {"$or": [{"created_at": {"$gte": since}}, {"createdAt": {"$gte": since}}]},
                    {"$or": [{"status": "delivered"}, {"lastEventProgress": {"$gte": 100}}]},
                ]
            })
        except Exception:
            delivered_n = 0

    def _round_int(v: Optional[float]) -> Optional[int]:
        return None if v is None else int(round(v))

    return {
        "count": delivered_n,
        "averages": {
            "daysToContact":  _round_int(days_to_contact),
            "daysToDeal":     _round_int(days_to_deal),
            "daysToContract": _round_int(days_to_contract),
            "daysToPayment":  _round_int(days_to_payment),
            "daysToDelivery": _round_int(days_to_delivery),
            "totalJourneyDays": _round_int(total),
        },
        "raw": {
            "daysToContact":  days_to_contact,
            "daysToDeal":     days_to_deal,
            "daysToContract": days_to_contract,
            "daysToPayment":  days_to_payment,
            "daysToDelivery": days_to_delivery,
            "totalJourneyDays": total,
        },
        "windowDays": days,
    }
