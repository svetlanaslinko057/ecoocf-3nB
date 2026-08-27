"""
CustomerHealthService — единственный источник истины для Health Score
и Customer Risks в системе.

Архитектурные принципы (зафиксированы в W1):

1. **N+1 free** — за один проход собирает все коллекции через
   `asyncio.gather`. Никаких циклов вида «для каждого клиента сходить
   в Mongo».

2. **Stateless / on-the-fly** — никакой коллекции `customer_health` и
   никакого фонового воркера. Считаем при каждом запросе. Если станет
   медленно — переедем на materialized view, но сначала докажем нужду.

3. **Single source of truth** — Customer360, Customers list и Team Lead
   Dashboard вызывают одну и ту же функцию. AC#11.

4. **Lazy в bulk** — для списка возвращаем только `{score, segment}`,
   полный breakdown и risks — только для одного клиента.

Использование:
    >>> svc = CustomerHealthService(db)
    >>> await svc.full(customer_id)
    {'score': 84, 'segment': 'hot', 'breakdown': {...}, 'risks': [...]}

    >>> await svc.bulk([id1, id2, id3])
    {id1: {'score': 84, 'segment': 'hot'}, ...}
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ─────────────────────── Формула (lock-in v2) ───────────────────────
# Ребалансирована, чтобы Score отражал ОТНОШЕНИЯ, а не только деньги:
WEIGHTS = {
    "activity":      0.25,
    "engagement":    0.20,
    "financial":     0.20,
    "deal_progress": 0.20,
    "documents":     0.15,
}
# Risk-штраф — каждый активный риск -10, но не больше -40 суммарно.
RISK_PENALTY_PER_ITEM = 10
RISK_PENALTY_CAP = 40

# Сегменты:
SEGMENT_THRESHOLDS: List[Tuple[int, str]] = [
    (80, "hot"),
    (60, "warm"),
    (30, "cold"),
    (0,  "lost"),
]


def _segment_for(score: int) -> str:
    for threshold, segment in SEGMENT_THRESHOLDS:
        if score >= threshold:
            return segment
    return "lost"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


def _coerce_dt(v: Any) -> Optional[datetime]:
    """Best-effort conversion of stored timestamp → aware datetime."""
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(v, str):
        try:
            s = v.replace("Z", "+00:00")
            d = datetime.fromisoformat(s)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _ident_filter(customer: Dict[str, Any]) -> Dict[str, Any]:
    """
    Match any record that belongs to this customer regardless of how the
    foreign key is spelled — `customerId`, `customer_id`, or matched by
    email/phone for legacy leads.
    """
    cid = customer.get("id") or customer.get("_id")
    or_clauses: List[Dict[str, Any]] = [
        {"customerId": cid},
        {"customer_id": cid},
    ]
    if customer.get("email"):
        or_clauses.append({"email": customer["email"]})
    if customer.get("phone"):
        or_clauses.append({"phone": customer["phone"]})
    return {"$or": or_clauses}


# ────────────────────── Risk Rules (lock-in v1) ──────────────────────
# Чистые функции над уже выгруженным контекстом — никаких новых запросов.
# Каждое правило: (code, predicate) → human text on hit.

def _risks_from_context(ctx: Dict[str, Any]) -> List[str]:
    risks: List[str] = []
    customer = ctx["customer"]
    calls = ctx["calls"]
    deals = ctx["deals"]
    deposits = ctx["deposits"]
    docs = ctx["documents"]
    contracts = ctx["contracts"]

    last_contact = ctx.get("last_contact_at")
    now = _now()

    if not customer.get("managerId") and not customer.get("manager_id"):
        risks.append("No manager assigned")

    if last_contact is None or (now - last_contact).days >= 30:
        risks.append("No contact for 30 days")
    elif (now - last_contact).days >= 14:
        risks.append("No contact for 14 days")

    # Active deal без подтверждённого депозита > 7 дней.
    for d in deals:
        status = (d.get("status") or "").lower()
        if status in {"waiting_deposit", "negotiation"}:
            created = _coerce_dt(d.get("created_at") or d.get("createdAt"))
            if created and (now - created).days >= 7:
                if not any(_belongs_to_deal(dep, d) for dep in deposits):
                    risks.append("Deposit overdue")
                    break

    # Won deal без подписанного контракта.
    won_deals = [d for d in deals if (d.get("status") or "").lower() in {"won", "purchased", "completed", "in_delivery"}]
    if won_deals:
        signed_contracts = [c for c in contracts if (c.get("lifecycle") or "").lower() in {"signed", "active"}]
        if not signed_contracts:
            risks.append("Missing signed contract")
        # Транспортный контракт для in_delivery.
        if any(_status(d) == "in_delivery" for d in won_deals):
            if not any((c.get("type") or "").lower() in {"transport", "delivery"} for c in contracts):
                risks.append("Missing transport contract")

    # Юр. поля BG — нужны при наличии хотя бы одной сделки.
    if deals and not (customer.get("legal") or {}).get("egn"):
        risks.append("Missing customer legal data")

    # Истёкшие документы.
    expired = [d for d in docs if (_coerce_dt(d.get("expires_at")) or now) < now]
    for d in expired[:3]:
        risks.append(f"Document expired: {d.get('name') or d.get('type') or 'document'}")

    # Зависшая сделка — нет движения stage > 14 дней.
    for d in deals:
        upd = _coerce_dt(d.get("updated_at") or d.get("updatedAt") or d.get("created_at"))
        if upd and (now - upd).days >= 14 and _status(d) not in {"won", "completed", "cancelled", "purchased"}:
            risks.append(f"Deal stuck: {d.get('title') or d.get('name') or d.get('id') or 'deal'}")
            break

    return risks


def _status(d: Dict[str, Any]) -> str:
    return (d.get("status") or d.get("stage") or "").lower()


def _belongs_to_deal(deposit: Dict[str, Any], deal: Dict[str, Any]) -> bool:
    did = deal.get("id") or deal.get("_id")
    return deposit.get("deal_id") == did or deposit.get("dealId") == did


# ────────────────────── Sub-scores (0..100) ──────────────────────────

def _score_activity(ctx: Dict[str, Any]) -> int:
    """calls + emails за последние 30 дней. 5+ контактов = 100."""
    cutoff = _days_ago(30)
    n = 0
    for c in ctx["calls"]:
        at = _coerce_dt(c.get("started_at") or c.get("created_at"))
        if at and at >= cutoff:
            n += 1
    n += ctx.get("emails_last_30d", 0)
    return min(100, n * 20)


def _score_engagement(ctx: Dict[str, Any]) -> int:
    """Открытия/клики писем за 30д. Заглушка: считаем reply'и в leads."""
    # Пока нет email-tracking → используем количество ответных leads
    # (новые записи lead'ов = клиент отзывается).
    cutoff = _days_ago(30)
    n = 0
    for l in ctx["leads"]:
        at = _coerce_dt(l.get("created_at") or l.get("createdAt"))
        if at and at >= cutoff:
            n += 1
    # Bonus за наличие непустых notes от клиента.
    if ctx["customer"].get("notes"):
        n += 1
    return min(100, n * 25)


def _score_financial(ctx: Dict[str, Any]) -> int:
    """Сумма подтверждённых депозитов / целевая планка."""
    target = 5000  # EUR — настраиваемая планка «крупного клиента»
    total = 0.0
    for dep in ctx["deposits"]:
        st = (dep.get("status") or "").lower()
        if st in {"confirmed", "paid", "received", "in_processing"}:
            try:
                total += float(dep.get("amount") or 0)
            except Exception:
                pass
    # Дополнительно — закрытые сделки.
    for d in ctx["deals"]:
        if _status(d) in {"won", "completed", "purchased"}:
            try:
                total += float(d.get("total_price") or d.get("totalValue") or 0) * 0.5
            except Exception:
                pass
    return int(min(100, total / target * 100))


def _score_deal_progress(ctx: Dict[str, Any]) -> int:
    """% сделок, продвинувшихся хотя бы до negotiation+."""
    deals = ctx["deals"]
    if not deals:
        return 0
    advanced = sum(
        1 for d in deals
        if _status(d) in {"negotiation", "waiting_deposit", "deposit_paid",
                           "purchased", "in_delivery", "won", "completed"}
    )
    return int(round(advanced / len(deals) * 100))


def _score_documents(ctx: Dict[str, Any]) -> int:
    """Полнота документов: законченность legal + наличие основных файлов."""
    customer = ctx["customer"]
    legal = customer.get("legal") or {}
    points = 0
    if legal.get("egn"):                points += 25
    if legal.get("national_id_no"):     points += 25
    if legal.get("id_card_address"):    points += 15
    if ctx["documents"]:                points += 20
    if ctx["contracts"]:                points += 15
    return min(100, points)


SUB_SCORES = {
    "activity":      _score_activity,
    "engagement":    _score_engagement,
    "financial":     _score_financial,
    "deal_progress": _score_deal_progress,
    "documents":     _score_documents,
}


# ────────────────────── Service ───────────────────────────────────────

class CustomerHealthService:
    """Single-pass aggregator for Customer Health Score + Risks."""

    def __init__(self, db):
        self.db = db

    # ───── Public API ─────

    async def full(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Полный health для одной карточки клиента.

        Возвращает None, если клиент не найден.
        """
        customer = await self.db.customers.find_one({"id": customer_id}, {"_id": 0})
        if not customer:
            return None
        ctx = await self._build_context(customer)
        return self._compute(ctx)

    async def bulk(self, customer_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        """Lazy health для списка — только {score, segment}.

        Использует параллельный gather + минимальные проекции
        для сокращения объёма данных. Если customers id'ы пустые —
        возвращает пустой словарь.
        """
        ids = [cid for cid in customer_ids if cid]
        if not ids:
            return {}

        customers = await self.db.customers.find(
            {"id": {"$in": ids}}, {"_id": 0}
        ).to_list(length=len(ids))
        if not customers:
            return {}

        # Параллельный сбор контекста для всех клиентов.
        contexts = await asyncio.gather(
            *(self._build_context(c) for c in customers)
        )

        out: Dict[str, Dict[str, Any]] = {}
        for ctx in contexts:
            cid = ctx["customer"].get("id")
            full = self._compute(ctx)
            out[cid] = {"score": full["score"], "segment": full["segment"]}
        return out

    # ───── Internals ─────

    async def _build_context(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Параллельно вытащить все нужные данные для одного клиента.

        Возвращает плоский словарь, который потом скоринг-функции
        читают синхронно без новых походов в Mongo.
        """
        flt = _ident_filter(customer)
        cid = customer.get("id") or customer.get("_id")
        by_cid = {"$or": [{"customer_id": cid}, {"customerId": cid}]}
        # Telephony match: by customer_id OR by phone (legacy webhook rows
        # carry only `from`/`to` until the resolver attaches the customer).
        call_or = [{"customer_id": cid}, {"customerId": cid}]
        if customer.get("phone"):
            call_or.append({"from": customer["phone"]})
            call_or.append({"to": customer["phone"]})
        call_flt = {"$or": call_or}

        async def _safe(coro, *, default=None):
            try:
                return await coro
            except Exception:
                return default if default is not None else []

        # Все запросы — параллельно через gather (1 round-trip)
        deals, leads, deposits, docs, contracts, calls = await asyncio.gather(
            _safe(self.db.deals.find(flt, {"_id": 0}).to_list(length=200)),
            _safe(self.db.leads.find(flt, {"_id": 0}).to_list(length=200)),
            _safe(self.db.legal_deposits.find(by_cid, {"_id": 0}).to_list(length=100)),
            _safe(self.db.documents.find(by_cid, {"_id": 0}).to_list(length=100)),
            _safe(self.db.contracts_v2.find(by_cid, {"_id": 0}).to_list(length=100)),
            _safe(self.db.ringostat_calls.find(call_flt, {"_id": 0}).to_list(length=200)),
        )

        # Последний контакт = max(call.started_at, deal.updated_at, ...)
        candidates: List[Optional[datetime]] = []
        for c in calls:
            candidates.append(_coerce_dt(c.get("started_at") or c.get("created_at")))
        for d in deals:
            candidates.append(_coerce_dt(d.get("updated_at") or d.get("created_at")))
        for l in leads:
            candidates.append(_coerce_dt(l.get("created_at")))
        last_contact = max([c for c in candidates if c is not None], default=None)

        return {
            "customer":         customer,
            "deals":            deals or [],
            "leads":            leads or [],
            "deposits":         deposits or [],
            "documents":        docs or [],
            "contracts":        contracts or [],
            "calls":            calls or [],
            "last_contact_at":  last_contact,
            "emails_last_30d":  0,  # placeholder until email tracking ships
        }

        # Последний контакт = max(call.started_at, deal.updated_at, ...)
        candidates: List[Optional[datetime]] = []
        for c in calls:
            candidates.append(_coerce_dt(c.get("started_at") or c.get("created_at")))
        for d in deals:
            candidates.append(_coerce_dt(d.get("updated_at") or d.get("created_at")))
        for l in leads:
            candidates.append(_coerce_dt(l.get("created_at")))
        last_contact = max([c for c in candidates if c is not None], default=None)

        return {
            "customer":         customer,
            "deals":            deals or [],
            "leads":            leads or [],
            "deposits":         deposits or [],
            "documents":        docs or [],
            "contracts":        contracts or [],
            "calls":            calls or [],
            "last_contact_at":  last_contact,
            "emails_last_30d":  0,  # placeholder until email tracking ships
        }

    def _compute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Чистая функция от контекста → health dict."""
        breakdown = {name: fn(ctx) for name, fn in SUB_SCORES.items()}
        risks = _risks_from_context(ctx)
        penalty = min(len(risks) * RISK_PENALTY_PER_ITEM, RISK_PENALTY_CAP)

        weighted = sum(breakdown[k] * w for k, w in WEIGHTS.items())
        raw = weighted * (1 - penalty / 100.0)
        score = max(0, min(100, int(round(raw))))

        return {
            "customer_id":  ctx["customer"].get("id"),
            "score":        score,
            "segment":      _segment_for(score),
            "breakdown":    {**breakdown, "risk_penalty": -penalty},
            "risks":        risks,
            "weights":      WEIGHTS,
            "last_contact": (ctx.get("last_contact_at").isoformat()
                              if ctx.get("last_contact_at") else None),
        }
