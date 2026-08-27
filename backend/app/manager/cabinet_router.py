"""
Manager Cabinet — self-contained CRM workspace for a single manager.
====================================================================

A focused, fully-working "Кабінет менеджера" built ON TOP of the existing
backend collections (``db.leads``, ``db.deals``, ``db.tasks``,
``db.ringostat_calls``) — every read & write is scoped to the *current*
authenticated user (``managerId == current_user.id`` for leads/deals/calls,
``assigneeId == current_user.id`` for tasks).

Design notes
------------
* New surface lives under ``/api/manager-cabinet/*`` so it never collides
  with the legacy ``/api/manager/*`` routes.
* Writes go into the SAME collections the legacy CRM uses, so anything the
  manager creates here also shows up in the team-wide CRM views.
* ``POST /seed`` populates realistic ECO (hazardous-waste B2B) demo data for
  the current user — idempotent (tagged with ``_src='manager_cabinet_seed'``).
* Everything returns plain JSON-serialisable dicts (``_id`` stripped, dates
  as ISO strings) so the React layer can consume it directly.
"""
from __future__ import annotations

import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.db_runtime import get_db
from security import require_user

router = APIRouter(prefix="/api/manager-cabinet", tags=["manager-cabinet"])

# ── Canonical vocabularies ──────────────────────────────────────────────
LEAD_STATUSES = ["new", "contacted", "qualified", "negotiation", "won", "lost"]
DEAL_STAGES = ["new", "negotiation", "contract", "pickup", "utilization", "won", "lost"]
TASK_STATUSES = ["pending", "in_progress", "completed"]
OPEN_TASK = {"$nin": ["completed", "cancelled", "done", "archived"]}

SEED_TAG = "manager_cabinet_seed"


# ── helpers ──────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip mongo _id and coerce datetimes to ISO strings (recursive-lite)."""
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            out[k] = _iso(v)
        else:
            out[k] = v
    return out


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _me(user: Dict[str, Any]) -> str:
    return user.get("id") or user.get("managerId") or user.get("email")


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════
#  OVERVIEW  (dashboard KPIs + funnel + recent activity)
# ══════════════════════════════════════════════════════════════════════════
@router.get("/overview")
async def overview(user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    now_iso = now.isoformat()
    today_iso = today_start.isoformat()
    tomorrow_iso = (today_start + timedelta(days=1)).isoformat()

    # ── Leads ──────────────────────────────────────────────────────────
    lead_q = {"managerId": me}
    leads_total = await db.leads.count_documents(lead_q)
    leads_by_status: Dict[str, int] = {}
    for st in LEAD_STATUSES:
        leads_by_status[st] = await db.leads.count_documents({**lead_q, "status": st})
    won_leads = leads_by_status.get("won", 0)
    open_leads = leads_total - won_leads - leads_by_status.get("lost", 0)
    conversion = round((won_leads / leads_total) * 100, 1) if leads_total else 0.0
    new_leads_today = await db.leads.count_documents(
        {**lead_q, "created_at": {"$gte": today_start}}
    )

    # ── Deals ──────────────────────────────────────────────────────────
    deal_q = {"managerId": me}
    deals_total = await db.deals.count_documents(deal_q)
    deals_open = await db.deals.count_documents({**deal_q, "stage": {"$nin": ["won", "lost"]}})
    deals_won = await db.deals.count_documents({**deal_q, "stage": "won"})
    # pipeline value (open) + won value
    pipeline_value = 0.0
    won_value = 0.0
    won_value_month = 0.0
    async for d in db.deals.find(deal_q, {"_id": 0, "stage": 1, "amount": 1, "updated_at": 1}):
        amt = float(d.get("amount") or 0)
        stage = d.get("stage")
        if stage == "won":
            won_value += amt
            up = _parse_dt(d.get("updated_at"))
            if up and up >= month_start:
                won_value_month += amt
        elif stage != "lost":
            pipeline_value += amt

    # ── Tasks ──────────────────────────────────────────────────────────
    task_q = {"assigneeId": me}
    tasks_open = await db.tasks.count_documents({**task_q, "status": OPEN_TASK})
    tasks_overdue = await db.tasks.count_documents(
        {**task_q, "status": OPEN_TASK, "due_at": {"$lt": now_iso}}
    )
    tasks_today = await db.tasks.count_documents(
        {**task_q, "status": OPEN_TASK, "due_at": {"$gte": today_iso, "$lt": tomorrow_iso}}
    )
    tasks_done = await db.tasks.count_documents({**task_q, "status": "completed"})

    # ── Calls ──────────────────────────────────────────────────────────
    call_q = {"managerId": me}
    calls_total = await db.ringostat_calls.count_documents(call_q)
    calls_today = await db.ringostat_calls.count_documents(
        {**call_q, "started_at": {"$gte": today_iso}}
    )
    calls_week = await db.ringostat_calls.count_documents(
        {**call_q, "started_at": {"$gte": week_start.isoformat()}}
    )
    calls_missed = await db.ringostat_calls.count_documents({**call_q, "status": "missed"})

    # ── Recent activity feeds ──────────────────────────────────────────
    recent_leads = [
        _clean(x)
        for x in await db.leads.find(lead_q, {"_id": 0}).sort("created_at", -1).limit(6).to_list(6)
    ]
    upcoming_tasks = [
        _clean(x)
        for x in await db.tasks.find({**task_q, "status": OPEN_TASK}).sort("due_at", 1).limit(6).to_list(6)
    ]
    recent_calls = [
        _clean(x)
        for x in await db.ringostat_calls.find(call_q).sort("started_at", -1).limit(6).to_list(6)
    ]

    return {
        "success": True,
        "manager": {
            "id": me,
            "name": user.get("name") or user.get("email"),
            "email": user.get("email"),
            "role": user.get("role"),
        },
        "kpis": {
            "leads_total": leads_total,
            "open_leads": open_leads,
            "won_leads": won_leads,
            "new_leads_today": new_leads_today,
            "conversion": conversion,
            "deals_total": deals_total,
            "deals_open": deals_open,
            "deals_won": deals_won,
            "pipeline_value": round(pipeline_value, 2),
            "won_value": round(won_value, 2),
            "won_value_month": round(won_value_month, 2),
            "tasks_open": tasks_open,
            "tasks_overdue": tasks_overdue,
            "tasks_today": tasks_today,
            "tasks_done": tasks_done,
            "calls_total": calls_total,
            "calls_today": calls_today,
            "calls_week": calls_week,
            "calls_missed": calls_missed,
        },
        "funnel": leads_by_status,
        "recent_leads": recent_leads,
        "upcoming_tasks": upcoming_tasks,
        "recent_calls": recent_calls,
    }


# ══════════════════════════════════════════════════════════════════════════
#  LEADS
# ══════════════════════════════════════════════════════════════════════════
@router.get("/leads")
async def list_leads(
    q: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    user: Dict[str, Any] = Depends(require_user),
):
    db = get_db()
    query: Dict[str, Any] = {"managerId": _me(user)}
    if status and status != "all":
        query["status"] = status
    if q:
        import re as _re
        esc = _re.escape(q.strip())
        query["$or"] = [
            {"name": {"$regex": esc, "$options": "i"}},
            {"company": {"$regex": esc, "$options": "i"}},
            {"email": {"$regex": esc, "$options": "i"}},
            {"phone": {"$regex": esc, "$options": "i"}},
        ]
    rows = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"success": True, "items": [_clean(r) for r in rows], "total": len(rows)}


@router.post("/leads")
async def create_lead(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    now = _now()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Вкажіть назву/контакт ліда")
    status = body.get("status") if body.get("status") in LEAD_STATUSES else "new"
    doc = {
        "id": _uid("lead"),
        "managerId": me,
        "name": name,
        "company": (body.get("company") or "").strip(),
        "email": (body.get("email") or "").strip(),
        "phone": (body.get("phone") or "").strip(),
        "status": status,
        "source": body.get("source") or "manual",
        "wasteType": body.get("wasteType") or "",
        "region": body.get("region") or "",
        "budgetEur": float(body.get("budgetEur") or 0),
        "notes": body.get("notes") or "",
        "score": int(body.get("score") or 0),
        "created_at": now,
        "updated_at": now,
        "last_contact_at": now,
    }
    await db.leads.insert_one(dict(doc))
    return {"success": True, "lead": _clean(doc)}


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    lead = await db.leads.find_one({"id": lead_id, "managerId": me}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Лід не знайдено")
    tasks = await db.tasks.find({"leadId": lead_id, "assigneeId": me}, {"_id": 0}).sort("due_at", 1).to_list(100)
    calls = await db.ringostat_calls.find({"leadId": lead_id, "managerId": me}, {"_id": 0}).sort("started_at", -1).to_list(100)
    return {
        "success": True,
        "lead": _clean(lead),
        "tasks": [_clean(t) for t in tasks],
        "calls": [_clean(c) for c in calls],
    }


@router.patch("/leads/{lead_id}")
async def update_lead(lead_id: str, body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    allowed = ("name", "company", "email", "phone", "status", "source",
               "wasteType", "region", "budgetEur", "notes", "score")
    patch: Dict[str, Any] = {}
    for k in allowed:
        if k in body:
            patch[k] = body[k]
    if "status" in patch and patch["status"] not in LEAD_STATUSES:
        raise HTTPException(status_code=422, detail="Невідомий статус ліда")
    if "budgetEur" in patch:
        patch["budgetEur"] = float(patch["budgetEur"] or 0)
    patch["updated_at"] = _now()
    res = await db.leads.update_one({"id": lead_id, "managerId": me}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Лід не знайдено")
    lead = await db.leads.find_one({"id": lead_id, "managerId": me}, {"_id": 0})
    return {"success": True, "lead": _clean(lead)}


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    res = await db.leads.delete_one({"id": lead_id, "managerId": me})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Лід не знайдено")
    return {"success": True}


@router.post("/leads/{lead_id}/convert")
async def convert_lead(lead_id: str, body: Dict[str, Any] = Body(default={}), user: Dict[str, Any] = Depends(require_user)):
    """Convert a lead to a deal (won pipeline). Marks lead status=won, creates a deal."""
    db = get_db()
    me = _me(user)
    lead = await db.leads.find_one({"id": lead_id, "managerId": me}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Лід не знайдено")
    now = _now()
    deal = {
        "id": _uid("deal"),
        "managerId": me,
        "title": body.get("title") or f"Угода — {lead.get('company') or lead.get('name')}",
        "customerName": lead.get("name"),
        "company": lead.get("company"),
        "amount": float(body.get("amount") or lead.get("budgetEur") or 0),
        "currency": body.get("currency") or "UAH",
        "stage": "negotiation",
        "wasteType": lead.get("wasteType") or "",
        "leadId": lead_id,
        "created_at": now,
        "updated_at": now,
    }
    await db.deals.insert_one(dict(deal))
    await db.leads.update_one({"id": lead_id, "managerId": me}, {"$set": {"status": "negotiation", "updated_at": now}})
    return {"success": True, "deal": _clean(deal)}


# ══════════════════════════════════════════════════════════════════════════
#  DEALS
# ══════════════════════════════════════════════════════════════════════════
@router.get("/deals")
async def list_deals(
    stage: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
    user: Dict[str, Any] = Depends(require_user),
):
    db = get_db()
    query: Dict[str, Any] = {"managerId": _me(user)}
    if stage and stage != "all":
        query["stage"] = stage
    if q:
        import re as _re
        esc = _re.escape(q.strip())
        query["$or"] = [
            {"title": {"$regex": esc, "$options": "i"}},
            {"company": {"$regex": esc, "$options": "i"}},
            {"customerName": {"$regex": esc, "$options": "i"}},
        ]
    rows = await db.deals.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"success": True, "items": [_clean(r) for r in rows], "total": len(rows)}


@router.post("/deals")
async def create_deal(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    now = _now()
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Вкажіть назву угоди")
    stage = body.get("stage") if body.get("stage") in DEAL_STAGES else "new"
    doc = {
        "id": _uid("deal"),
        "managerId": me,
        "title": title,
        "customerName": body.get("customerName") or "",
        "company": body.get("company") or "",
        "amount": float(body.get("amount") or 0),
        "currency": body.get("currency") or "UAH",
        "stage": stage,
        "wasteType": body.get("wasteType") or "",
        "created_at": now,
        "updated_at": now,
    }
    await db.deals.insert_one(dict(doc))
    return {"success": True, "deal": _clean(doc)}


@router.patch("/deals/{deal_id}")
async def update_deal(deal_id: str, body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    allowed = ("title", "customerName", "company", "amount", "currency", "stage", "wasteType")
    patch: Dict[str, Any] = {}
    for k in allowed:
        if k in body:
            patch[k] = body[k]
    if "stage" in patch and patch["stage"] not in DEAL_STAGES:
        raise HTTPException(status_code=422, detail="Невідомий етап угоди")
    if "amount" in patch:
        patch["amount"] = float(patch["amount"] or 0)
    patch["updated_at"] = _now()
    res = await db.deals.update_one({"id": deal_id, "managerId": me}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Угоду не знайдено")
    deal = await db.deals.find_one({"id": deal_id, "managerId": me}, {"_id": 0})
    return {"success": True, "deal": _clean(deal)}


@router.delete("/deals/{deal_id}")
async def delete_deal(deal_id: str, user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    res = await db.deals.delete_one({"id": deal_id, "managerId": me})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Угоду не знайдено")
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════
#  TASKS
# ══════════════════════════════════════════════════════════════════════════
@router.get("/tasks")
async def list_tasks(
    filter: Optional[str] = Query(default="all"),
    user: Dict[str, Any] = Depends(require_user),
):
    db = get_db()
    me = _me(user)
    now_iso = _now().isoformat()
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    query: Dict[str, Any] = {"assigneeId": me}
    if filter == "open":
        query["status"] = OPEN_TASK
    elif filter == "overdue":
        query["status"] = OPEN_TASK
        query["due_at"] = {"$lt": now_iso}
    elif filter == "today":
        query["status"] = OPEN_TASK
        query["due_at"] = {
            "$gte": today_start.isoformat(),
            "$lt": (today_start + timedelta(days=1)).isoformat(),
        }
    elif filter == "completed":
        query["status"] = "completed"
    rows = await db.tasks.find(query, {"_id": 0}).sort("due_at", 1).to_list(300)
    return {"success": True, "items": [_clean(r) for r in rows], "total": len(rows)}


@router.post("/tasks")
async def create_task(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    now = _now()
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Вкажіть назву завдання")
    doc = {
        "id": _uid("task"),
        "assigneeId": me,
        "managerId": me,
        "title": title,
        "description": body.get("description") or "",
        "status": "pending",
        "priority": body.get("priority") or "normal",
        "due_at": body.get("due_at") or (now + timedelta(days=1)).isoformat(),
        "leadId": body.get("leadId") or None,
        "created_at": now,
        "updated_at": now,
    }
    await db.tasks.insert_one(dict(doc))
    return {"success": True, "task": _clean(doc)}


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    allowed = ("title", "description", "status", "priority", "due_at", "leadId")
    patch: Dict[str, Any] = {}
    for k in allowed:
        if k in body:
            patch[k] = body[k]
    if "status" in patch and patch["status"] not in TASK_STATUSES:
        raise HTTPException(status_code=422, detail="Невідомий статус завдання")
    if patch.get("status") == "completed":
        patch["completed_at"] = _now().isoformat()
    patch["updated_at"] = _now()
    res = await db.tasks.update_one({"id": task_id, "assigneeId": me}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Завдання не знайдено")
    task = await db.tasks.find_one({"id": task_id, "assigneeId": me}, {"_id": 0})
    return {"success": True, "task": _clean(task)}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    res = await db.tasks.delete_one({"id": task_id, "assigneeId": me})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Завдання не знайдено")
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════
#  CALLS
# ══════════════════════════════════════════════════════════════════════════
@router.get("/calls")
async def list_calls(
    filter: Optional[str] = Query(default="all"),
    user: Dict[str, Any] = Depends(require_user),
):
    db = get_db()
    query: Dict[str, Any] = {"managerId": _me(user)}
    if filter == "missed":
        query["status"] = "missed"
    elif filter in ("inbound", "outbound"):
        query["direction"] = filter
    rows = await db.ringostat_calls.find(query, {"_id": 0}).sort("started_at", -1).limit(300).to_list(300)
    return {"success": True, "items": [_clean(r) for r in rows], "total": len(rows)}


@router.post("/calls")
async def log_call(body: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    me = _me(user)
    now = _now()
    doc = {
        "id": _uid("call"),
        "managerId": me,
        "direction": body.get("direction") if body.get("direction") in ("inbound", "outbound") else "outbound",
        "phone": (body.get("phone") or "").strip(),
        "contactName": body.get("contactName") or "",
        "status": body.get("status") if body.get("status") in ("answered", "missed", "no_answer") else "answered",
        "duration_sec": int(body.get("duration_sec") or 0),
        "note": body.get("note") or "",
        "leadId": body.get("leadId") or None,
        "started_at": body.get("started_at") or now.isoformat(),
        "created_at": now,
    }
    await db.ringostat_calls.insert_one(dict(doc))
    return {"success": True, "call": _clean(doc)}


# ══════════════════════════════════════════════════════════════════════════
#  SEED  — realistic ECO B2B demo data for the current manager (idempotent)
# ══════════════════════════════════════════════════════════════════════════
_COMPANIES = [
    ("ТОВ «МедіЛаб Клінікс»", "medical", "Медичні відходи 18 01 03*", "Київ"),
    ("ПрАТ «ФармаДистриб'юшн»", "pharma", "Прострочені ліки 18 01 09", "Львів"),
    ("ТОВ «АвтоПарк Захід»", "oils", "Відпрацьовані масла 13 02 05*", "Львів"),
    ("ДП «Хімреактив»", "agrochem", "Агрохімія / реагенти 16 05 06*", "Дніпро"),
    ("ТОВ «ЕнергоТех»", "accumulators", "Свинцеві акумулятори 16 06 01*", "Запоріжжя"),
    ("ПП «АгроЛан»", "pesticides", "Пестициди 02 01 08*", "Вінниця"),
    ("ТОВ «ТехноРецикл»", "electronics", "Електроніка (ВЕЕО) 16 02 13*", "Харків"),
    ("КП «Міськсвітло»", "lamps", "Люмінесцентні лампи 20 01 21*", "Одеса"),
    ("ТОВ «ЛакоФарб Сервіс»", "paints", "ЛФМ / розчинники 08 01 11*", "Київ"),
    ("ТОВ «РтутьСервіс»", "mercury", "Ртутовмісні відходи 06 04 04*", "Київ"),
    ("ТОВ «БудМаркет»", "other_hazard", "Забруднена тара 15 01 10*", "Дніпро"),
    ("ПрАТ «АвтоШина Плюс»", "tires", "Зношені шини 16 01 03", "Харків"),
]
_FIRST = ["Олександр", "Ірина", "Сергій", "Наталія", "Андрій", "Оксана", "Дмитро", "Марина", "Володимир", "Тетяна"]
_LAST = ["Коваленко", "Шевченко", "Бондаренко", "Ткаченко", "Мельник", "Кравчук", "Лисенко", "Поліщук", "Савченко", "Гриценко"]
_SOURCES = ["website", "phone", "referral", "calculator", "exhibition", "cold_call"]


@router.post("/seed")
async def seed_cabinet(
    reset: bool = Query(default=True),
    user: Dict[str, Any] = Depends(require_user),
):
    """Populate realistic demo data for the current manager. Idempotent."""
    db = get_db()
    me = _me(user)
    now = _now()
    rnd = random.Random(hash(me) & 0xFFFFFFFF)

    if reset:
        await db.leads.delete_many({"managerId": me, "_src": SEED_TAG})
        await db.deals.delete_many({"managerId": me, "_src": SEED_TAG})
        await db.tasks.delete_many({"assigneeId": me, "_src": SEED_TAG})
        await db.ringostat_calls.delete_many({"managerId": me, "_src": SEED_TAG})

    leads_docs: List[Dict[str, Any]] = []
    deals_docs: List[Dict[str, Any]] = []
    tasks_docs: List[Dict[str, Any]] = []
    calls_docs: List[Dict[str, Any]] = []

    status_weights = [
        ("new", 5), ("contacted", 5), ("qualified", 4),
        ("negotiation", 3), ("won", 4), ("lost", 2),
    ]
    weighted_statuses: List[str] = []
    for st, w in status_weights:
        weighted_statuses.extend([st] * w)

    for i in range(20):
        comp, cat, waste, region = rnd.choice(_COMPANIES)
        fn, ln = rnd.choice(_FIRST), rnd.choice(_LAST)
        status = rnd.choice(weighted_statuses)
        created = now - timedelta(days=rnd.randint(0, 45), hours=rnd.randint(0, 23))
        budget = rnd.choice([12000, 18000, 24000, 36000, 48000, 75000, 120000])
        lead_id = _uid("lead")
        leads_docs.append({
            "id": lead_id,
            "managerId": me,
            "name": f"{fn} {ln}",
            "company": comp,
            "email": f"{fn.lower()}.{ln.lower()}@{['ukr.net','gmail.com','company.ua'][i % 3]}",
            "phone": f"+38 0{rnd.randint(50,99)} {rnd.randint(100,999)} {rnd.randint(10,99)} {rnd.randint(10,99)}",
            "status": status,
            "source": rnd.choice(_SOURCES),
            "wasteType": waste,
            "region": region,
            "budgetEur": float(budget),
            "score": rnd.randint(20, 95),
            "notes": "",
            "created_at": created,
            "updated_at": created,
            "last_contact_at": created,
            "_src": SEED_TAG,
        })

        # Won/negotiation leads spawn deals
        if status in ("won", "negotiation"):
            d_created = created + timedelta(days=rnd.randint(1, 7))
            deals_docs.append({
                "id": _uid("deal"),
                "managerId": me,
                "title": f"Утилізація — {comp}",
                "customerName": f"{fn} {ln}",
                "company": comp,
                "amount": float(budget),
                "currency": "UAH",
                "stage": "won" if status == "won" else "negotiation",
                "wasteType": waste,
                "leadId": lead_id,
                "created_at": d_created,
                "updated_at": d_created + timedelta(days=rnd.randint(0, 10)),
                "_src": SEED_TAG,
            })

        # Some open leads get follow-up tasks
        if status in ("new", "contacted", "qualified", "negotiation") and rnd.random() < 0.7:
            offset = rnd.choice([-2, -1, 0, 0, 1, 2, 3])
            due = (now + timedelta(days=offset)).replace(hour=rnd.choice([10, 12, 14, 16]), minute=0, second=0, microsecond=0)
            tasks_docs.append({
                "id": _uid("task"),
                "assigneeId": me,
                "managerId": me,
                "title": rnd.choice([
                    f"Передзвонити: {comp}",
                    f"Надіслати КП — {waste}",
                    f"Узгодити графік вивозу: {comp}",
                    f"Підготувати договір для {comp}",
                    f"Уточнити обсяг відходів — {comp}",
                ]),
                "description": f"Контакт: {fn} {ln}",
                "status": rnd.choice(["pending", "pending", "in_progress"]),
                "priority": rnd.choice(["normal", "normal", "high"]),
                "due_at": due.isoformat(),
                "leadId": lead_id,
                "created_at": created,
                "updated_at": created,
                "_src": SEED_TAG,
            })

        # Calls history
        for _ in range(rnd.randint(0, 3)):
            c_when = created + timedelta(days=rnd.randint(0, 10), hours=rnd.randint(0, 8))
            if c_when > now:
                c_when = now - timedelta(hours=rnd.randint(1, 48))
            calls_docs.append({
                "id": _uid("call"),
                "managerId": me,
                "direction": rnd.choice(["inbound", "outbound", "outbound"]),
                "phone": f"+38 0{rnd.randint(50,99)} {rnd.randint(100,999)} {rnd.randint(1000,9999)}",
                "contactName": f"{fn} {ln}",
                "status": rnd.choice(["answered", "answered", "missed", "no_answer"]),
                "duration_sec": rnd.choice([0, 45, 120, 240, 380, 65]),
                "note": "",
                "leadId": lead_id,
                "started_at": c_when.isoformat(),
                "created_at": c_when,
                "_src": SEED_TAG,
            })

    # A couple of completed tasks for KPI realism
    for _ in range(4):
        comp = rnd.choice(_COMPANIES)[0]
        done_when = now - timedelta(days=rnd.randint(1, 14))
        tasks_docs.append({
            "id": _uid("task"),
            "assigneeId": me,
            "managerId": me,
            "title": f"Закрито: договір {comp}",
            "description": "",
            "status": "completed",
            "priority": "normal",
            "due_at": done_when.isoformat(),
            "completed_at": done_when.isoformat(),
            "created_at": done_when - timedelta(days=2),
            "updated_at": done_when,
            "_src": SEED_TAG,
        })

    if leads_docs:
        await db.leads.insert_many([dict(d) for d in leads_docs])
    if deals_docs:
        await db.deals.insert_many([dict(d) for d in deals_docs])
    if tasks_docs:
        await db.tasks.insert_many([dict(d) for d in tasks_docs])
    if calls_docs:
        await db.ringostat_calls.insert_many([dict(d) for d in calls_docs])

    return {
        "success": True,
        "seeded": {
            "leads": len(leads_docs),
            "deals": len(deals_docs),
            "tasks": len(tasks_docs),
            "calls": len(calls_docs),
        },
    }
