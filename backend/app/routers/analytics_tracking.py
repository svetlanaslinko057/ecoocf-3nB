"""
analytics_tracking.py — реальная аналитика без mock-данных.
=============================================================

Заменяет старые mock-эндпоинты `/api/analytics/dashboard` и
`/api/marketing/campaigns` в server.py.

Архитектура:

  Frontend tracker (lib/tracker.js)
       │ POST /api/track/event  {type, path, session_id, host, referrer, utm_*}
       ▼
  analytics_events (Mongo) — TTL 90 дней
       │
       └─▶ GET /api/analytics/dashboard   — агрегаты (group by host)
       └─▶ GET /api/marketing/campaigns   — группировки по utm_campaign
       └─▶ POST /api/admin/marketing/campaigns — админ вводит spend для расчёта ROI

Все агрегации фильтруются по `host` (домен, с которого пришло событие). Это значит:
  • In preview deployments (`*.preview.<host>`) — analytics is collected
    с превью домена.
  • После переезда на боевой домен (`bibi.cars`) — фронт начнёт писать
    `host: bibi.cars`, dashboard покажет данные именно по нему.
  • Параметр query `?host=<value>` позволяет admin'у явно посмотреть
    статистику по конкретному домену.

Нет fallback на mock — если данных нет, dashboard вернёт нули
(`visits: 0`, `funnel.steps[*].value: 0`). Это правильно: «честный 0»
лучше выдуманных «15000».
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from security import require_admin

logger = logging.getLogger("bibi.analytics_tracking")


def _db():
    from app.core.db_runtime import get_db
    return get_db()


# ─────────────────────────────────────────────────────────────────────
# Public tracking endpoint
# ─────────────────────────────────────────────────────────────────────
public_router = APIRouter(prefix="/api/track", tags=["analytics-track"])


_EVENT_TYPES = {
    "page_view",       # обычная загрузка страницы
    "vehicle_view",    # открыта карточка авто (path вида /single-car/<vin> или /vehicle/<id>)
    "vin_search",      # поиск по VIN (на главной или через парсер)
    "calculator_use",  # пользователь нажал расчёт
    "lead_submit",     # отправлена форма лида (form, calculator quote и т.п.)
    "deal_won",        # выигран лот (фиксируем при POST /legal/deals/{id}/auction/won — см. ниже)
    "session_start",   # первый ping в сессии (опционально)
}


def _normalise_host(raw: Optional[str]) -> str:
    if not raw:
        return ""
    raw = raw.strip().lower()
    # Strip protocol if пришло целиком
    if "://" in raw:
        try:
            raw = urlparse(raw).hostname or ""
        except Exception:
            pass
    # Strip port (`localhost:3000` → `localhost`)
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    # Strip www.
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


@public_router.post("/event")
async def track_event(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    """Принимает событие от фронта. Анонимно, без auth (PII не пишем).

    Body (обязательно): `type` (одно из _EVENT_TYPES).
    Body (опц.): `path`, `session_id`, `referrer`, `host`, `user_agent`,
                 `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`,
                 `vin` (для type=vin_search), `vehicle_id` (для vehicle_view).

    Хост определяется в порядке: payload.host → Origin → Referer →
    X-Forwarded-Host → request.client (last-resort). Это нужно чтобы
    бэкенд знал, для какого домена считать статистику.
    """
    db = _db()
    event_type = (payload.get("type") or "").strip().lower()
    if event_type not in _EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown event type: {event_type!r}. Allowed: {sorted(_EVENT_TYPES)}")

    # Определяем host
    host_raw = (
        payload.get("host")
        or request.headers.get("origin")
        or request.headers.get("referer")
        or request.headers.get("x-forwarded-host")
        or ""
    )
    host = _normalise_host(host_raw)

    # IP (rough — только для гео-агрегации в будущем, не привязываем к user)
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
    )

    doc = {
        "type": event_type,
        "host": host,
        "path": (payload.get("path") or "")[:512],
        "session_id": (payload.get("session_id") or "")[:64],
        "referrer": (payload.get("referrer") or "")[:512],
        "user_agent": (payload.get("user_agent") or request.headers.get("user-agent") or "")[:512],
        "utm_source":   (payload.get("utm_source") or "")[:64].lower(),
        "utm_medium":   (payload.get("utm_medium") or "")[:64].lower(),
        "utm_campaign": (payload.get("utm_campaign") or "")[:128],
        "utm_term":     (payload.get("utm_term") or "")[:128],
        "utm_content":  (payload.get("utm_content") or "")[:128],
        "vin":          (payload.get("vin") or "")[:32].upper() or None,
        "vehicle_id":   payload.get("vehicle_id") or None,
        "ip_prefix":    ".".join(ip.split(".")[:3]) + ".x" if ip and "." in ip else None,
        "ts":           datetime.now(timezone.utc),
    }
    await db.analytics_events.insert_one(doc)
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────
# Dashboard — реальные агрегации
# ─────────────────────────────────────────────────────────────────────
public_dash_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _classify_source(utm_source: str, utm_medium: str, referrer: str) -> str:
    """Канонизация источника трафика. Возвращает одно из:
      Google / Facebook / Instagram / Email / Direct / Referral / Other.
    """
    s = (utm_source or "").lower()
    if "google" in s:
        return "Google"
    if "facebook" in s or "fb" == s:
        return "Facebook"
    if "instagram" in s or "ig" == s:
        return "Instagram"
    if (utm_medium or "").lower() == "email" or "email" in s:
        return "Email"
    if not referrer:
        return "Direct"
    ref_host = _normalise_host(referrer)
    if not ref_host:
        return "Direct"
    if "google" in ref_host:
        return "Google"
    if "facebook" in ref_host or "fb.com" in ref_host:
        return "Facebook"
    if "instagram" in ref_host:
        return "Instagram"
    if ref_host.endswith("youtube.com"):
        return "YouTube"
    return "Referral"


@public_dash_router.get("/dashboard", dependencies=[Depends(require_admin)])
async def analytics_dashboard(
    days: int = Query(30, ge=1, le=365),
    host: Optional[str] = Query(None, description="Если передан — фильтр по конкретному домену; иначе агрегация по всем"),
):
    """Реальные агрегации из коллекции analytics_events + leads + deals.
    Никаких mock-fallback: пустой результат = нули.
    """
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_match: Dict[str, Any] = {"ts": {"$gte": since}}
    if host:
        base_match["host"] = _normalise_host(host)

    # ── KPI counts ────────────────────────────────────────────────────
    pipeline = [
        {"$match": base_match},
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1},
            "unique_sessions": {"$addToSet": "$session_id"},
        }},
    ]
    by_type: Dict[str, Dict[str, Any]] = {}
    async for row in db.analytics_events.aggregate(pipeline):
        by_type[row["_id"]] = {
            "count": row["count"],
            "unique_sessions": len([s for s in row["unique_sessions"] if s]),
        }

    visits          = by_type.get("page_view", {}).get("count", 0)
    unique_sessions = sum(v.get("unique_sessions", 0) for v in by_type.values())
    # Better: distinct session_ids across all events for this period
    distinct_sessions = await db.analytics_events.distinct(
        "session_id", {**base_match, "session_id": {"$ne": ""}},
    )
    unique_sessions = len([s for s in distinct_sessions if s])

    vin_searches    = by_type.get("vin_search", {}).get("count", 0)
    vehicle_views   = by_type.get("vehicle_view", {}).get("count", 0)
    calculator_uses = by_type.get("calculator_use", {}).get("count", 0)

    # Leads/Deals — из бизнес-коллекций (не из событий, иначе lead_submit нужно явно слать)
    lead_match: Dict[str, Any] = {"created_at": {"$gte": since}}
    deal_match: Dict[str, Any] = {"created_at": {"$gte": since}}
    leads_count = await db.leads.count_documents(lead_match) if "leads" in await db.list_collection_names() else 0
    deals_count = await db.deals.count_documents(deal_match) if "deals" in await db.list_collection_names() else 0

    conversion = round((deals_count / visits) * 100, 2) if visits else 0.0

    # ── Timeline (daily) ──────────────────────────────────────────────
    timeline_pipe = [
        {"$match": base_match},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}},
            "pageViews": {"$sum": {"$cond": [{"$eq": ["$type", "page_view"]}, 1, 0]}},
            "sessions":  {"$addToSet": "$session_id"},
        }},
        {"$project": {
            "pageViews": 1,
            "visitors": {"$size": {"$filter": {"input": "$sessions", "as": "s", "cond": {"$ne": ["$$s", ""]}}}},
            "total": "$pageViews",
            "conversions": {"$literal": 0},
        }},
        {"$sort": {"_id": 1}},
    ]
    timeline: List[Dict[str, Any]] = []
    async for row in db.analytics_events.aggregate(timeline_pipe):
        timeline.append(row)

    # ── Funnel ────────────────────────────────────────────────────────
    base = visits or 1  # избегаем деления на 0
    funnel_steps = [
        {"name_key": "funnel_step_visits",        "name": "Visits",        "value": visits,          "rate": 100.0 if visits else 0.0},
        {"name_key": "funnel_step_vehicle_views", "name": "Vehicle Views", "value": vehicle_views,   "rate": round(vehicle_views   / base * 100, 1)},
        {"name_key": "funnel_step_calculator",    "name": "Calculator",   "value": calculator_uses, "rate": round(calculator_uses / base * 100, 1)},
        {"name_key": "funnel_step_lead",          "name": "Lead",         "value": leads_count,     "rate": round(leads_count     / base * 100, 1)},
        {"name_key": "funnel_step_deal",          "name": "Deal",         "value": deals_count,     "rate": round(deals_count     / base * 100, 1)},
    ]

    # ── Traffic sources ───────────────────────────────────────────────
    src_match = {**base_match, "type": "page_view"}
    sources_agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"visits": 0, "leads": 0, "deals": 0, "profit": 0})

    src_pipe = [
        {"$match": src_match},
        {"$project": {
            "utm_source": 1, "utm_medium": 1, "referrer": 1,
        }},
    ]
    async for row in db.analytics_events.aggregate(src_pipe):
        s = _classify_source(row.get("utm_source", ""), row.get("utm_medium", ""), row.get("referrer", ""))
        sources_agg[s]["visits"] += 1

    # Подсчитаем leads/deals по источнику (если у lead есть utm_source — будущее улучшение).
    # Сейчас leads/deals по источнику не делим — ставим 0; если в lead есть utm_source, легко добавить.
    sources = sorted(
        [{"source": k, **v, "conversion": round((v["deals"] / v["visits"]) * 100, 2) if v["visits"] else 0.0} for k, v in sources_agg.items()],
        key=lambda x: -x["visits"],
    )

    # ── Top pages ─────────────────────────────────────────────────────
    top_pipe = [
        {"$match": {**base_match, "type": "page_view"}},
        {"$group": {"_id": "$path", "views": {"$sum": 1}}},
        {"$sort": {"views": -1}},
        {"$limit": 10},
    ]
    top_pages: List[Dict[str, Any]] = []
    async for row in db.analytics_events.aggregate(top_pipe):
        top_pages.append({"path": row["_id"] or "/", "views": row["views"], "avgTime": 0})

    return {
        "success": True,
        "data": {
            "host_filter": host or "(all)",
            "kpi": {
                "visits": visits,
                "uniqueSessions": unique_sessions,
                "vinSearches": vin_searches,
                "leads": leads_count,
                "deals": deals_count,
                "conversion": conversion,
                "conversionRate": conversion,
            },
            "summary": {
                "pageViews": visits,
                "uniqueVisitors": unique_sessions,
                "avgSessionDuration": 0,  # требует session-end событий — позже
                "bounceRate": 0,
                "newUsers": unique_sessions,  # без cookie-fingerprint считаем сессии
                "conversionRate": conversion,
            },
            "trend": {  # период-к-периоду; считаем позже, когда накопится достаточно данных
                "pageViews": 0, "visitors": 0, "sessions": 0,
            },
            "timeline": timeline,
            "funnel": {"steps": funnel_steps},
            "sources": sources,
            "fakeTraffic": None,
            "topPages": top_pages,
        }
    }


# ─────────────────────────────────────────────────────────────────────
# Marketing campaigns
# ─────────────────────────────────────────────────────────────────────
@public_dash_router.get("/marketing-campaigns", dependencies=[Depends(require_admin)])
async def marketing_campaigns_real(
    days: int = Query(30, ge=1, le=365),
    host: Optional[str] = Query(None),
):
    """Группировка по utm_campaign из реальных событий + ввод admin'а
    про spend через POST /api/admin/marketing/campaigns.
    """
    db = _db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    match: Dict[str, Any] = {"ts": {"$gte": since}, "type": "page_view", "utm_campaign": {"$ne": ""}}
    if host:
        match["host"] = _normalise_host(host)

    # Группа по (utm_campaign, utm_source)
    pipe = [
        {"$match": match},
        {"$group": {
            "_id": {"campaign": "$utm_campaign", "source": "$utm_source"},
            "visits": {"$sum": 1},
            "sessions": {"$addToSet": "$session_id"},
        }},
        {"$sort": {"visits": -1}},
        {"$limit": 50},
    ]
    rows: List[Dict[str, Any]] = []
    async for r in db.analytics_events.aggregate(pipe):
        rows.append({
            "campaign": r["_id"].get("campaign") or "(no name)",
            "source":   r["_id"].get("source") or "direct",
            "visits":   r["visits"],
            "sessions": len([s for s in r["sessions"] if s]),
        })

    # Подтягиваем spend, заданный admin'ом
    admin_inputs: Dict[str, Dict[str, Any]] = {}
    async for c in db.marketing_campaigns.find({}):
        key = (c.get("campaign") or "", c.get("source") or "")
        admin_inputs[key] = c

    # Считаем leads и deals для каждой кампании
    decisions: List[Dict[str, Any]] = []
    for row in rows:
        key = (row["campaign"], row["source"])
        admin_row = admin_inputs.get(key, {})
        spend = float(admin_row.get("spend") or 0)
        avg_deal_profit = float(admin_row.get("avg_deal_profit") or 0)

        # Leads / Deals atribution: count leads/deals where utm_campaign matches
        leads_n = await db.leads.count_documents({
            "utm_campaign": row["campaign"],
            "created_at": {"$gte": since},
        }) if row["campaign"] != "(no name)" else 0
        deals_n = await db.deals.count_documents({
            "utm_campaign": row["campaign"],
            "created_at": {"$gte": since},
        }) if row["campaign"] != "(no name)" else 0

        profit = deals_n * avg_deal_profit
        roi = round(((profit - spend) / spend) * 100, 1) if spend > 0 else None

        # Status calc
        if roi is None:
            status = "watch"
            actions = ["No spend recorded — fill in via admin panel to enable ROI calculation."]
        elif roi >= 150:
            status, actions = "scale", ["Increase budget by 20-30%"]
        elif roi >= 75:
            status, actions = "keep", ["Maintain current budget"]
        elif roi >= 0:
            status, actions = "watch", ["Refresh creatives, review targeting"]
        else:
            status, actions = "kill", ["Pause campaign — negative ROI"]

        decisions.append({
            "campaign": row["campaign"],
            "source":   row["source"],
            "spend":    spend,
            "visits":   row["visits"],
            "leads":    leads_n,
            "deals":    deals_n,
            "profit":   profit,
            "roi":      roi if roi is not None else 0.0,
            "status":   status,
            "actions":  actions,
        })

    summary = {
        "scaleCount":  sum(1 for d in decisions if d["status"] == "scale"),
        "keepCount":   sum(1 for d in decisions if d["status"] == "keep"),
        "watchCount":  sum(1 for d in decisions if d["status"] == "watch"),
        "killCount":   sum(1 for d in decisions if d["status"] == "kill"),
        "recommendations": [],
    }
    if decisions:
        # Recs: топ-3 по ROI и предложение перебросить бюджет с худших.
        sorted_by_roi = sorted([d for d in decisions if d["spend"] > 0], key=lambda x: -x["roi"])
        if sorted_by_roi and sorted_by_roi[0]["roi"] > 100:
            summary["recommendations"].append(
                f"Top performer: '{sorted_by_roi[0]['campaign']}' ROI {sorted_by_roi[0]['roi']}% — consider scaling."
            )
        negatives = [d for d in decisions if d["spend"] > 0 and d["roi"] < 0]
        if negatives:
            summary["recommendations"].append(
                f"Pause negative-ROI campaigns: {', '.join(n['campaign'] for n in negatives[:3])}"
            )

    return {
        "success": True,
        "data": {
            "decisions": decisions,
            "summary": summary,
            "campaigns": [
                {"id": d["campaign"], "name": d["campaign"], "status": d["status"],
                 "spend": d["spend"], "leads": d["leads"], "conversions": d["deals"], "roi": d["roi"]}
                for d in decisions
            ],
            "totalSpend":       sum(d["spend"]  for d in decisions),
            "totalLeads":       sum(d["leads"]  for d in decisions),
            "totalConversions": sum(d["deals"]  for d in decisions),
            "avgCPA": round(sum(d["spend"] for d in decisions) / sum(d["leads"] for d in decisions), 2)
                      if sum(d["leads"] for d in decisions) else 0,
            "avgROI": round(sum(d["roi"] or 0 for d in decisions) / len(decisions), 1) if decisions else 0,
        }
    }


# ─────────────────────────────────────────────────────────────────────
# Admin: ввод spend для кампаний
# ─────────────────────────────────────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin/marketing", tags=["admin-marketing"], dependencies=[Depends(require_admin)])


@admin_router.get("/campaigns")
async def list_admin_campaigns():
    """Список введённых вручную параметров кампаний (spend, avg_deal_profit)."""
    db = _db()
    out: List[Dict[str, Any]] = []
    async for c in db.marketing_campaigns.find({}).sort("updated_at", -1):
        c["_id"] = str(c["_id"])
        out.append(c)
    return {"data": out}


@admin_router.post("/campaigns")
async def upsert_admin_campaign(data: Dict[str, Any] = Body(...)):
    """Записать spend для кампании. Body:
      {campaign: "Spring Promo", source: "google", spend: 5000, avg_deal_profit: 800}
    """
    db = _db()
    campaign = (data.get("campaign") or "").strip()
    if not campaign:
        raise HTTPException(status_code=400, detail="`campaign` is required")
    source = (data.get("source") or "").strip().lower()
    spend = float(data.get("spend") or 0)
    avg_deal_profit = float(data.get("avg_deal_profit") or 0)

    await db.marketing_campaigns.update_one(
        {"campaign": campaign, "source": source},
        {
            "$set": {
                "campaign": campaign,
                "source": source,
                "spend": spend,
                "avg_deal_profit": avg_deal_profit,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    return {"success": True}


@admin_router.delete("/campaigns/{campaign}")
async def delete_admin_campaign(campaign: str, source: Optional[str] = None):
    db = _db()
    q: Dict[str, Any] = {"campaign": campaign}
    if source is not None:
        q["source"] = source.lower()
    res = await db.marketing_campaigns.delete_many(q)
    return {"success": True, "deleted": res.deleted_count}


# ─────────────────────────────────────────────────────────────────────
# Index init (вызывается при старте)
# ─────────────────────────────────────────────────────────────────────
async def ensure_analytics_indexes(db) -> None:
    """Идемпотентно: индексы и TTL (90 дней) для analytics_events."""
    try:
        await db.analytics_events.create_index([("ts", -1)])
        await db.analytics_events.create_index([("host", 1), ("ts", -1)])
        await db.analytics_events.create_index([("type", 1), ("ts", -1)])
        await db.analytics_events.create_index([("utm_campaign", 1), ("ts", -1)])
        await db.analytics_events.create_index("ts", expireAfterSeconds=90 * 24 * 3600)
        await db.marketing_campaigns.create_index([("campaign", 1), ("source", 1)], unique=True)
        logger.info("[analytics] indexes ensured (analytics_events + marketing_campaigns)")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[analytics] index ensure failed: {e}")
