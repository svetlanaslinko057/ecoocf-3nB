"""
Staff Center — admin-only control room for managing managers.
=============================================================

Everything an admin needs to control manager work, surfaced cleanly on top
of the existing ``db.staff`` collection + the CRM collections:

  * team overview (totals, leaderboard)
  * member list with **2FA status** (admin sees who enabled Google Authenticator),
    active flag, and per-manager KPIs (leads / conversion / won value / open
    tasks / calls)
  * member CRUD — create / edit / activate-deactivate / reset password / delete
    (passwords stored as **bcrypt** in ``password_hash`` so the member can log in)
  * lead assignment & reassignment between managers

NOTE: the ``team_lead`` role has been removed from the product — only
``admin`` and ``manager`` roles are supported here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_admin, require_user, hash_password
from app.core.db_runtime import get_db
from app.repositories import AdminSecurityRepository

router = APIRouter(prefix="/api/staff-center", tags=["staff-center"], dependencies=[Depends(require_admin)])

ALLOWED_ROLES = {"admin", "manager"}
OPEN_TASK = {"$nin": ["completed", "cancelled", "done", "archived"]}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(v: Any) -> Optional[str]:
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
    return v


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in (doc or {}).items():
        if k in ("_id", "password", "password_hash"):
            continue
        out[k] = _iso(v) if isinstance(v, datetime) else v
    return out


async def _twofa_map(db, ids: List[str]) -> Dict[str, bool]:
    """Return {staff_id: enabled} reading admin_security scope user:{id}."""
    scopes = [f"user:{i}" for i in ids]
    out: Dict[str, bool] = {}
    if not scopes:
        return out
    async for d in db.admin_security.find({"_id": {"$in": scopes}}):
        sid = str(d.get("_id", "")).replace("user:", "")
        out[sid] = bool(d.get("twofa_enabled"))
    return out


async def _kpis_for(db, manager_id: str) -> Dict[str, Any]:
    lead_q = {"managerId": manager_id}
    leads_total = await db.leads.count_documents(lead_q)
    won = await db.leads.count_documents({**lead_q, "status": "won"})
    deals_won_value = 0.0
    async for d in db.deals.find({"managerId": manager_id, "stage": "won"}, {"_id": 0, "amount": 1}):
        deals_won_value += float(d.get("amount") or 0)
    open_tasks = await db.tasks.count_documents({"assigneeId": manager_id, "status": OPEN_TASK})
    overdue_tasks = await db.tasks.count_documents(
        {"assigneeId": manager_id, "status": OPEN_TASK, "due_at": {"$lt": _now().isoformat()}}
    )
    calls = await db.ringostat_calls.count_documents({"managerId": manager_id})
    return {
        "leads_total": leads_total,
        "won": won,
        "conversion": round((won / leads_total) * 100, 1) if leads_total else 0.0,
        "won_value": round(deals_won_value, 2),
        "open_tasks": open_tasks,
        "overdue_tasks": overdue_tasks,
        "calls": calls,
    }


# ══════════════════════════════════════════════════════════════════════════
#  OVERVIEW
# ══════════════════════════════════════════════════════════════════════════
@router.get("/overview")
async def overview():
    db = get_db()
    total_staff = await db.staff.count_documents({})
    managers = await db.staff.count_documents({"role": "manager"})
    active = await db.staff.count_documents({"active": {"$ne": False}})
    # Manager leaderboard
    members = await db.staff.find({"role": "manager"}, {"_id": 0, "password": 0, "password_hash": 0}).to_list(500)
    ids = [m.get("id") for m in members if m.get("id")]
    twofa = await _twofa_map(db, ids)
    # KPI «З 2FA» рахує по всьому персоналу (admin + manager), щоб бачити
    # повну картину захищеності облікових записів.
    all_staff = await db.staff.find({}, {"_id": 0, "id": 1, "role": 1}).to_list(1000)
    all_ids = [s.get("id") for s in all_staff if s.get("id")]
    twofa_all = await _twofa_map(db, all_ids)
    twofa_on = sum(1 for i in all_ids if twofa_all.get(i))
    leaderboard = []
    for m in members:
        k = await _kpis_for(db, m.get("id"))
        leaderboard.append({
            "id": m.get("id"), "name": m.get("name") or m.get("email"),
            "email": m.get("email"), "active": m.get("active", True),
            "twofa_enabled": twofa.get(m.get("id"), False), **k,
        })
    leaderboard.sort(key=lambda x: (x["won_value"], x["won"]), reverse=True)
    totals = {
        "leads": sum(x["leads_total"] for x in leaderboard),
        "won": sum(x["won"] for x in leaderboard),
        "won_value": round(sum(x["won_value"] for x in leaderboard), 2),
        "open_tasks": sum(x["open_tasks"] for x in leaderboard),
        "overdue_tasks": sum(x["overdue_tasks"] for x in leaderboard),
        "calls": sum(x["calls"] for x in leaderboard),
    }
    return {
        "success": True,
        "staff": {"total": total_staff, "managers": managers, "active": active, "twofa_enabled": twofa_on},
        "totals": totals,
        "leaderboard": leaderboard,
    }


# ══════════════════════════════════════════════════════════════════════════
#  MEMBERS
# ══════════════════════════════════════════════════════════════════════════
@router.get("/members")
async def list_members(role: Optional[str] = None, q: Optional[str] = None):
    db = get_db()
    query: Dict[str, Any] = {}
    if role and role in ALLOWED_ROLES:
        query["role"] = role
    if q:
        import re as _re
        esc = _re.escape(q.strip())
        query["$or"] = [{"name": {"$regex": esc, "$options": "i"}}, {"email": {"$regex": esc, "$options": "i"}}]
    rows = await db.staff.find(query, {"_id": 0, "password": 0, "password_hash": 0}).to_list(500)
    ids = [r.get("id") for r in rows if r.get("id")]
    twofa = await _twofa_map(db, ids)
    items = []
    for r in rows:
        k = await _kpis_for(db, r.get("id")) if r.get("role") == "manager" else {}
        c = _clean(r)
        c["active"] = c.get("active", True) is not False
        items.append({**c, "twofa_enabled": twofa.get(r.get("id"), False), "kpis": k})
    # managers first, then by name
    items.sort(key=lambda x: (x.get("role") != "manager", (x.get("name") or "").lower()))
    return {"success": True, "items": items, "total": len(items)}


@router.get("/members/{staff_id}")
async def get_member(staff_id: str):
    db = get_db()
    m = await db.staff.find_one({"id": staff_id}, {"_id": 0, "password": 0, "password_hash": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")
    twofa = await _twofa_map(db, [staff_id])
    kpis = await _kpis_for(db, staff_id)
    recent = await db.leads.find({"managerId": staff_id}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8)
    return {
        "success": True,
        "member": {**_clean(m), "twofa_enabled": twofa.get(staff_id, False)},
        "kpis": kpis,
        "recent_leads": [_clean(x) for x in recent],
    }


@router.post("/members")
async def create_member(body: Dict[str, Any] = Body(...)):
    db = get_db()
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "manager").strip().lower()
    if not email or not name:
        raise HTTPException(status_code=422, detail="Вкажіть ім'я та email")
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Роль може бути лише admin або manager")
    if len(password) < 6:
        raise HTTPException(status_code=422, detail="Пароль має містити щонайменше 6 символів")
    if await db.staff.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Співробітник з таким email вже існує")
    doc = {
        "id": f"staff_{role}_{uuid.uuid4().hex[:10]}",
        "name": name,
        "email": email,
        "phone": (body.get("phone") or "").strip(),
        "role": role,
        "active": True,
        "password_hash": hash_password(password),
        "created_at": _now(),
        "tokenVersion": 0,
    }
    await db.staff.insert_one(dict(doc))
    return {"success": True, "member": _clean(doc)}


@router.patch("/members/{staff_id}")
async def update_member(staff_id: str, body: Dict[str, Any] = Body(...)):
    db = get_db()
    patch: Dict[str, Any] = {}
    if "name" in body:
        patch["name"] = (body["name"] or "").strip()
    if "phone" in body:
        patch["phone"] = (body["phone"] or "").strip()
    if "role" in body:
        role = (body["role"] or "").strip().lower()
        if role not in ALLOWED_ROLES:
            raise HTTPException(status_code=422, detail="Невідома роль")
        patch["role"] = role
    if "active" in body:
        patch["active"] = bool(body["active"])
    if not patch:
        raise HTTPException(status_code=422, detail="Немає змін")
    res = await db.staff.update_one({"id": staff_id}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")
    m = await db.staff.find_one({"id": staff_id}, {"_id": 0, "password": 0, "password_hash": 0})
    return {"success": True, "member": _clean(m)}


@router.post("/members/{staff_id}/toggle-active")
async def toggle_active(staff_id: str):
    db = get_db()
    m = await db.staff.find_one({"id": staff_id})
    if not m:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")
    new_active = not m.get("active", True)
    await db.staff.update_one({"id": staff_id}, {"$set": {"active": new_active}})
    return {"success": True, "active": new_active}


@router.post("/members/{staff_id}/reset-password")
async def reset_password(staff_id: str, body: Dict[str, Any] = Body(...), admin: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    new_password = body.get("newPassword") or body.get("password") or ""
    if len(new_password) < 6:
        raise HTTPException(status_code=422, detail="Пароль має містити щонайменше 6 символів")
    res = await db.staff.update_one(
        {"id": staff_id},
        {"$set": {"password_hash": hash_password(new_password)}, "$inc": {"tokenVersion": 1}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")
    return {"success": True}


@router.delete("/members/{staff_id}")
async def delete_member(staff_id: str, admin: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    if staff_id == (admin.get("id")):
        raise HTTPException(status_code=400, detail="Не можна видалити власний акаунт")
    res = await db.staff.delete_one({"id": staff_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Співробітника не знайдено")
    # also wipe their 2FA state
    await db.admin_security.delete_one({"_id": f"user:{staff_id}"})
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════
#  LEAD ASSIGNMENT / REASSIGNMENT
# ══════════════════════════════════════════════════════════════════════════
@router.get("/leads")
async def assignment_leads(
    managerId: Optional[str] = Query(default=None),
    unassigned: bool = Query(default=False),
    q: Optional[str] = None,
    limit: int = 300,
):
    """All leads with their owner — for the assignment board."""
    db = get_db()
    query: Dict[str, Any] = {}
    if unassigned:
        query["$or"] = [{"managerId": None}, {"managerId": ""}, {"managerId": {"$exists": False}}]
    elif managerId:
        query["managerId"] = managerId
    if q:
        import re as _re
        esc = _re.escape(q.strip())
        query.setdefault("$and", [])
        query["$and"].append({"$or": [
            {"name": {"$regex": esc, "$options": "i"}},
            {"company": {"$regex": esc, "$options": "i"}},
        ]})
    rows = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    # owner names
    ids = list({r.get("managerId") for r in rows if r.get("managerId")})
    name_map: Dict[str, str] = {}
    if ids:
        async for s in db.staff.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
            name_map[s["id"]] = s.get("name") or s.get("email")
    items = [{**_clean(r), "ownerName": name_map.get(r.get("managerId"))} for r in rows]
    return {"success": True, "items": items, "total": len(items)}


@router.post("/assign")
async def assign_leads(body: Dict[str, Any] = Body(...)):
    """Assign/reassign one or many leads to a manager."""
    db = get_db()
    manager_id = body.get("managerId")
    lead_ids = body.get("leadIds") or ([body["leadId"]] if body.get("leadId") else [])
    if not manager_id or not lead_ids:
        raise HTTPException(status_code=422, detail="Вкажіть менеджера та ліди")
    mgr = await db.staff.find_one({"id": manager_id})
    if not mgr:
        raise HTTPException(status_code=404, detail="Менеджера не знайдено")
    res = await db.leads.update_many(
        {"id": {"$in": lead_ids}},
        {"$set": {"managerId": manager_id, "updated_at": _now(), "reassigned_at": _now().isoformat()}},
    )
    return {"success": True, "modified": res.modified_count, "managerId": manager_id}
