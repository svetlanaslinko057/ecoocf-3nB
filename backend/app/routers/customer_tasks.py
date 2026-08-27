"""
Customer Tasks router — Sprint 4
=================================

Thin wrapper on top of the existing global ``db.tasks`` collection that
adds the missing **customer dimension**. Re-uses the same documents so
the SLA Engine, eligible-assignees, and notification dispatch keep
working unchanged.

Key points
----------
* Adds ``customerId`` (and snake_case alias ``customer_id``) to every
  task created via this surface.
* ``GET`` returns tasks linked to the customer by EITHER customerId or
  by an associated leadId / dealId.
* Tasks have rich statuses: pending / in_progress / completed /
  cancelled. Completion sets ``completed_at`` and fires the timeline.
* ``overdue`` is computed live, not stored, so we never lie if the
  clock moves.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.db_runtime import get_db
from app.services import customer_timeline
from security import require_manager_or_admin

router = APIRouter(tags=["customer-tasks"])
COLLECTION = "tasks"

VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _is_overdue(task: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    if (task.get("status") or "").lower() in {"completed", "cancelled"}:
        return False
    due = task.get("dueDate") or task.get("due_date")
    if not due:
        return False
    try:
        due_dt = datetime.fromisoformat(str(due).replace("Z", "+00:00"))
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    n = now or _now()
    return n > due_dt


async def _resolve_lead_and_deal_ids(customer_id: str) -> Dict[str, List[str]]:
    db = get_db()
    leads = [ld["id"] async for ld in db.leads.find({"customerId": customer_id}, {"id": 1, "_id": 0}) if ld.get("id")]
    deals = [d["id"] async for d in db.deals.find({"customerId": customer_id}, {"id": 1, "_id": 0}) if d.get("id")]
    return {"leadIds": leads, "dealIds": deals}


@router.get("/api/customers/{customer_id}/tasks",
            dependencies=[Depends(require_manager_or_admin)])
async def list_customer_tasks(
    customer_id: str,
    status: Optional[str] = None,
    include_completed: bool = True,
):
    db = get_db()
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")

    related = await _resolve_lead_and_deal_ids(customer_id)
    or_clauses: List[Dict[str, Any]] = [
        {"customerId": customer_id},
        {"customer_id": customer_id},
    ]
    if related["leadIds"]:
        or_clauses.append({"leadId": {"$in": related["leadIds"]}})
    if related["dealIds"]:
        or_clauses.append({"dealId": {"$in": related["dealIds"]}})
    flt: Dict[str, Any] = {"$or": or_clauses}
    if status:
        flt["status"] = status.lower()
    if not include_completed:
        flt["status"] = {"$nin": ["completed", "cancelled"]}

    items = await db[COLLECTION].find(flt, {"_id": 0}).sort("created_at", -1).to_list(length=300)
    now = _now()
    open_count, done_count, overdue_count = 0, 0, 0
    for it in items:
        it["overdue"] = _is_overdue(it, now=now)
        st = (it.get("status") or "").lower()
        if st == "completed":
            done_count += 1
        elif st == "cancelled":
            pass
        else:
            open_count += 1
            if it["overdue"]:
                overdue_count += 1

    return {
        "success": True,
        "items": items,
        "total": len(items),
        "summary": {
            "open": open_count,
            "completed": done_count,
            "overdue": overdue_count,
        },
    }


@router.post("/api/customers/{customer_id}/tasks",
             dependencies=[Depends(require_manager_or_admin)])
async def create_customer_task(
    customer_id: str,
    data: Dict[str, Any] = Body(...),
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(404, "Customer not found")

    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")

    role = (user.get("role") or "").lower()

    # Resolve assignee: explicit assigneeId wins. Otherwise default to
    # the customer's owning manager. If neither, assign to the caller.
    assignee_id = (data.get("assigneeId") or "").strip() or cust.get("managerId") or user.get("id")
    assignee_doc = await db.staff.find_one({"id": assignee_id}, {"_id": 0, "password": 0, "passwordHash": 0})
    if not assignee_doc:
        # Fall back to current user; we don't fail just because the legacy
        # managerId pointer on the customer is stale.
        assignee_doc = {
            "id": user.get("id"),
            "role": role,
            "name": user.get("name") or user.get("email"),
            "email": user.get("email"),
        }

    priority = (data.get("priority") or "medium").lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    now = _now()
    _id = f"task-{now.timestamp()}-{uuid.uuid4().hex[:6]}"
    task = {
        "id": _id,
        "taskId": _id,
        "title": title,
        "description": data.get("description"),
        "type": data.get("type", "customer"),
        "customerId": customer_id,
        "customer_id": customer_id,
        "leadId": data.get("leadId"),
        "dealId": data.get("dealId"),
        "assigneeId": assignee_doc.get("id"),
        "assigneeRole": (assignee_doc.get("role") or "").lower(),
        "assigneeName": assignee_doc.get("name") or assignee_doc.get("email"),
        "assigneeEmail": assignee_doc.get("email"),
        "dueDate": data.get("dueDate") or data.get("due_date"),
        "priority": priority,
        "status": "pending",
        "createdBy": user.get("id"),
        "createdByRole": role,
        "createdByName": user.get("name") or user.get("email"),
        "created_at": _iso(now),
    }
    await db[COLLECTION].insert_one(dict(task))
    task.pop("_id", None)

    try:
        await customer_timeline.record_event(
            customer_id=customer_id,
            kind="task_created",
            title=f"Задача: {title}",
            body=(task.get("description") or "")[:240] or None,
            ref={"collection": COLLECTION, "id": _id},
            actor=customer_timeline.extract_actor(user),
            meta={"assigneeName": task["assigneeName"], "dueDate": task["dueDate"], "priority": priority},
        )
    except Exception:
        pass

    return {"success": True, "task": task}


@router.patch("/api/customers/{customer_id}/tasks/{task_id}",
              dependencies=[Depends(require_manager_or_admin)])
async def update_customer_task(
    customer_id: str,
    task_id: str,
    data: Dict[str, Any] = Body(default_factory=dict),
    user: dict = Depends(require_manager_or_admin),
):
    db = get_db()
    task = await db[COLLECTION].find_one({"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Task not found")

    update: Dict[str, Any] = {"updated_at": _iso(_now())}
    fire_completed = False
    if "status" in data:
        st = (data.get("status") or "").lower()
        if st not in VALID_STATUSES:
            raise HTTPException(400, f"invalid status; expected one of {sorted(VALID_STATUSES)}")
        update["status"] = st
        if st == "completed":
            update["completed_at"] = _iso(_now())
            fire_completed = True
        elif st in {"pending", "in_progress"} and task.get("status") == "completed":
            update["completed_at"] = None
    if "title" in data:
        new_title = (data.get("title") or "").strip()
        if new_title:
            update["title"] = new_title
    if "description" in data:
        update["description"] = data.get("description")
    if "dueDate" in data or "due_date" in data:
        update["dueDate"] = data.get("dueDate") or data.get("due_date")
    if "priority" in data:
        p = (data.get("priority") or "").lower()
        if p in VALID_PRIORITIES:
            update["priority"] = p
    if "assigneeId" in data and data.get("assigneeId"):
        new_assignee = await db.staff.find_one({"id": data["assigneeId"]}, {"_id": 0})
        if new_assignee:
            update["assigneeId"] = new_assignee["id"]
            update["assigneeRole"] = (new_assignee.get("role") or "").lower()
            update["assigneeName"] = new_assignee.get("name") or new_assignee.get("email")
            update["assigneeEmail"] = new_assignee.get("email")

    await db[COLLECTION].update_one(
        {"$or": [{"id": task_id}, {"taskId": task_id}]},
        {"$set": update},
    )
    fresh = await db[COLLECTION].find_one({"$or": [{"id": task_id}, {"taskId": task_id}]}, {"_id": 0})
    if fresh:
        fresh["overdue"] = _is_overdue(fresh)

    if fire_completed:
        try:
            await customer_timeline.record_event(
                customer_id=customer_id,
                kind="task_completed",
                title=f"Задача выполнена: {fresh.get('title') if fresh else ''}",
                ref={"collection": COLLECTION, "id": task_id},
                actor=customer_timeline.extract_actor(user),
            )
        except Exception:
            pass
    return {"success": True, "task": fresh}


@router.delete("/api/customers/{customer_id}/tasks/{task_id}",
               dependencies=[Depends(require_manager_or_admin)])
async def delete_customer_task(customer_id: str, task_id: str):
    db = get_db()
    r = await db[COLLECTION].delete_one({"$or": [{"id": task_id}, {"taskId": task_id}]})
    if not r.deleted_count:
        raise HTTPException(404, "Task not found")
    return {"success": True}
