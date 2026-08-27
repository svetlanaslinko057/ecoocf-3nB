"""
Wave 7 — Manual Workload Rebalancing Service
=============================================

Centralized reassignment logic for **lead / customer / deal** entities.

This module is the SINGLE source of truth for changing the ``managerId`` /
ownership of any of the three CRM core entities. All endpoints (the new
``POST /api/admin/reassign`` and the legacy ``POST /api/team/leads/{id}/reassign``
wrapper) MUST route through this service so that:

  1. Audit is consistently written into ``db.reassignments``.
  2. Deal reassignment ALWAYS appends a ``owner_changed`` event in
     ``deal_timeline`` (best-effort; never blocks the update).
  3. ACL (admin / team_lead / manager / team boundary) is enforced once,
     not duplicated per call-site.
  4. Bulk operations have predictable partial-failure semantics.

Design rules
------------
  * Pure async. Pass ``db`` explicitly (no ``from server import db``).
  * Bulk-first API: ``reassign(entity, ids, ...)`` always takes a list.
  * Idempotent: reassigning to the same manager returns ``ok`` with a
    ``"no_change"`` note (does NOT write an audit row).
  * Never raises on per-id failures — collects them in ``results[]``.
    Raises only on contract violations (bad entity, missing toManagerId,
    auth error).

ACL matrix (Wave 7 final):

    admin / owner / master_admin   →  any → any
    team_lead                       →  only within own team (staff.teamId)
    manager                          →  403 (manager cannot reassign)

A team_lead with ``teamId == None`` is restricted to managers also having
``teamId == None`` (treated as "no-team" cohort) — explicit rather than
implicit "allow all".
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

logger = logging.getLogger("bibi.wave7.reassignment")

# ---------------------------------------------------------------------------
# Entity registry: maps entity-name → mongo collection + per-entity options.
# ---------------------------------------------------------------------------
ENTITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "lead":     {"collection": "leads",     "label_field": "name"},
    "customer": {"collection": "customers", "label_field": "name"},
    "deal":     {"collection": "deals",     "label_field": "title"},
}

ADMIN_ROLES = {"owner", "master_admin", "admin"}
ALLOWED_ROLES = ADMIN_ROLES | {"team_lead"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_reassignment_id() -> str:
    return f"rea_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}"


def _normalize_role(role: Optional[str]) -> str:
    return (role or "").strip().lower()


# ---------------------------------------------------------------------------
# ACL helpers
# ---------------------------------------------------------------------------
def assert_role_can_reassign(actor: Dict[str, Any]) -> None:
    """Raise 403 unless actor role is admin/team_lead."""
    role = _normalize_role(actor.get("role"))
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or team_lead may reassign workload",
        )


async def assert_team_boundary(
    db,
    *,
    actor: Dict[str, Any],
    to_manager_id: str,
    from_manager_id: Optional[str] = None,
) -> None:
    """For team_lead: ensure both source and target are within own team.

    Admin roles bypass this check entirely.
    """
    role = _normalize_role(actor.get("role"))
    if role in ADMIN_ROLES:
        return  # admins are unrestricted

    if role != "team_lead":
        # Should never reach here because assert_role_can_reassign blocks others.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not allowed to reassign",
        )

    actor_team = actor.get("teamId")

    # Fetch target manager's team
    target = await db.staff.find_one(
        {"id": to_manager_id}, {"_id": 0, "teamId": 1, "role": 1, "id": 1}
    )
    if not target:
        raise HTTPException(status_code=404, detail="Target manager not found")
    target_team = target.get("teamId")

    if (actor_team or None) != (target_team or None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="team_lead can only reassign within own team",
        )

    # Also check the source manager (if known) is within team
    if from_manager_id:
        src = await db.staff.find_one(
            {"id": from_manager_id}, {"_id": 0, "teamId": 1}
        )
        if src and (src.get("teamId") or None) != (actor_team or None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="team_lead cannot reassign entities owned outside own team",
            )


# ---------------------------------------------------------------------------
# Helpers — manager resolution + workload
# ---------------------------------------------------------------------------
async def _resolve_manager(db, manager_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not manager_id:
        return None
    return await db.staff.find_one(
        {"id": manager_id}, {"_id": 0, "password": 0}
    )


def _format_manager_label(m: Optional[Dict[str, Any]]) -> str:
    if not m:
        return "—"
    return m.get("name") or m.get("email") or m.get("id") or "—"


async def _validate_target_manager(db, to_manager_id: str) -> Dict[str, Any]:
    target = await _resolve_manager(db, to_manager_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Manager {to_manager_id} not found")
    role = _normalize_role(target.get("role"))
    if role not in {"manager", "team_lead", "admin", "owner", "master_admin"}:
        raise HTTPException(
            status_code=400,
            detail=f"Target user {to_manager_id} is not a staff member",
        )
    if target.get("is_active") is False:
        raise HTTPException(
            status_code=400,
            detail=f"Target manager {_format_manager_label(target)} is inactive",
        )
    return target


# ---------------------------------------------------------------------------
# Audit + timeline helpers
# ---------------------------------------------------------------------------
async def _write_audit(
    db,
    *,
    entity: str,
    entity_id: str,
    from_manager_id: Optional[str],
    to_manager_id: str,
    reason: Optional[str],
    performed_by: Dict[str, Any],
    status_value: str = "completed",
) -> Dict[str, Any]:
    """Insert a row into ``db.reassignments`` (audit trail)."""
    doc = {
        "id": _new_reassignment_id(),
        "entity": entity,
        "entityId": entity_id,
        "fromManagerId": from_manager_id,
        "toManagerId": to_manager_id,
        "reason": (reason or "").strip() or None,
        "performedBy": performed_by.get("id"),
        "performedByEmail": performed_by.get("email"),
        "performedByRole": performed_by.get("role"),
        "status": status_value,
        "createdAt": _now_iso(),
    }
    try:
        await db.reassignments.insert_one(doc)
    except Exception as e:  # pragma: no cover — defensive
        logger.warning("[reassignment.audit] insert failed entity=%s id=%s err=%s",
                       entity, entity_id, e)
    doc.pop("_id", None)
    return doc


async def _maybe_write_deal_timeline(
    db,
    *,
    deal_id: str,
    from_manager: Optional[Dict[str, Any]],
    to_manager: Dict[str, Any],
    actor: Dict[str, Any],
    reason: Optional[str],
) -> None:
    """Best-effort deal_timeline event for owner_changed. Never raises."""
    try:
        # Lazy import to avoid circulars at module-load.
        from app.wave6.timeline import write_event  # type: ignore

        from_label = _format_manager_label(from_manager) if from_manager else "(none)"
        to_label = _format_manager_label(to_manager)
        actor_label = actor.get("email") or actor.get("name") or actor.get("id") or "system"
        message = f"Owner changed from {from_label} to {to_label} by {actor_label}"
        if reason:
            message += f" — {reason.strip()}"

        await write_event(
            db,
            deal_id=deal_id,
            event_type="owner_changed",
            message=message,
            i18n_key="timeline.owner_changed",
            data={
                "from": {"id": (from_manager or {}).get("id"), "name": from_label},
                "to":   {"id": to_manager.get("id"),           "name": to_label},
                "reason": (reason or "").strip() or None,
            },
            actor={
                "email": actor.get("email"),
                "role":  actor.get("role"),
            },
        )
    except Exception as e:  # pragma: no cover — timeline must never block
        logger.warning("[reassignment.timeline] failed deal=%s err=%s", deal_id, e)


# ---------------------------------------------------------------------------
# Core operation: reassign(entity, ids, ...)
# ---------------------------------------------------------------------------
async def reassign(
    db,
    *,
    entity: str,
    ids: List[str],
    to_manager_id: str,
    reason: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    """Bulk reassign one or more entities to a target manager.

    Args:
      db:              Motor DB handle.
      entity:          "lead" | "customer" | "deal".
      ids:             List of entity ids (non-empty).
      to_manager_id:   Target staff/manager id.
      reason:          Free-form reason (audit only).
      actor:           Auth user dict (role / id / email / teamId).

    Returns:
      {
        "success": bool,
        "processed": int,         # rows actually modified
        "no_change": int,         # already owned by target
        "failed":   int,
        "results": [              # per-id results
          {"id": "...", "ok": True,  "fromManagerId": "...", "toManagerId": "...", "noChange": False},
          {"id": "...", "ok": False, "error": "..."},
        ],
      }
    """
    # ---- contract checks ----
    if entity not in ENTITY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported entity '{entity}'. Allowed: {list(ENTITY_REGISTRY)}",
        )
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="ids must be a non-empty list")
    if not to_manager_id:
        raise HTTPException(status_code=400, detail="toManagerId is required")

    # Dedup ids to avoid duplicate audit rows
    seen, unique_ids = set(), []
    for _id in ids:
        if not _id or _id in seen:
            continue
        seen.add(_id)
        unique_ids.append(_id)

    # ---- ACL ----
    assert_role_can_reassign(actor)
    target_manager = await _validate_target_manager(db, to_manager_id)

    coll_name = ENTITY_REGISTRY[entity]["collection"]
    coll = db[coll_name]

    results: List[Dict[str, Any]] = []
    processed = 0
    no_change = 0
    failed = 0

    for entity_id in unique_ids:
        try:
            doc = await coll.find_one({"id": entity_id}, {"_id": 0})
            if not doc:
                results.append({"id": entity_id, "ok": False, "error": "not_found"})
                failed += 1
                continue

            from_manager_id = doc.get("managerId")
            from_manager = await _resolve_manager(db, from_manager_id) if from_manager_id else None

            # team boundary check (per-id because source manager varies)
            await assert_team_boundary(
                db,
                actor=actor,
                to_manager_id=to_manager_id,
                from_manager_id=from_manager_id,
            )

            # Idempotent shortcut: already owned by target.
            if from_manager_id == to_manager_id:
                results.append({
                    "id": entity_id,
                    "ok": True,
                    "noChange": True,
                    "fromManagerId": from_manager_id,
                    "toManagerId": to_manager_id,
                })
                no_change += 1
                continue

            # Apply update
            await coll.update_one(
                {"id": entity_id},
                {"$set": {
                    "managerId": to_manager_id,
                    "managerId_updated_at": _now_iso(),
                }},
            )

            # Доопр #24 — cascade open/overdue/no-deadline tasks to the new
            # manager. Completed/cancelled tasks stay assigned to the old
            # one (history). Only relevant for lead/customer entities.
            tasks_moved = 0
            if entity in ("lead", "customer"):
                link_field = "leadId" if entity == "lead" else "customerId"
                task_q = {
                    link_field: entity_id,
                    "status": {"$nin": ["completed", "cancelled", "done"]},
                }
                upd = await db.tasks.update_many(
                    task_q,
                    {"$set": {
                        "assigneeId":   to_manager_id,
                        "assigneeName": target_manager.get("name") or target_manager.get("email"),
                        "assigneeRole": target_manager.get("role", "manager"),
                        "reassigned_at":      _now_iso(),
                        "reassigned_from":    from_manager_id,
                        "reassigned_by":      actor.get("id"),
                    }},
                )
                tasks_moved = getattr(upd, "modified_count", 0)

            # Audit (one row per id)
            await _write_audit(
                db,
                entity=entity,
                entity_id=entity_id,
                from_manager_id=from_manager_id,
                to_manager_id=to_manager_id,
                reason=reason,
                performed_by=actor,
            )

            # Deal timeline event (deals only)
            if entity == "deal":
                await _maybe_write_deal_timeline(
                    db,
                    deal_id=entity_id,
                    from_manager=from_manager,
                    to_manager=target_manager,
                    actor=actor,
                    reason=reason,
                )

            results.append({
                "id": entity_id,
                "ok": True,
                "noChange": False,
                "fromManagerId": from_manager_id,
                "toManagerId": to_manager_id,
                "tasksMoved": tasks_moved,
            })
            processed += 1

        except HTTPException as he:
            # ACL/per-id boundary errors → record but keep processing the rest
            results.append({"id": entity_id, "ok": False, "error": he.detail, "status": he.status_code})
            failed += 1
        except Exception as e:  # pragma: no cover
            logger.exception("[reassignment] unexpected error entity=%s id=%s", entity, entity_id)
            results.append({"id": entity_id, "ok": False, "error": str(e)})
            failed += 1

    # Доопр #24 — notify the new manager about the batch + the old managers
    # (one consolidated notification per source manager).
    try:
        if processed > 0 and entity in ("lead", "customer"):
            total_tasks = sum(int(r.get("tasksMoved") or 0) for r in results if r.get("ok") and not r.get("noChange"))
            actor_name = actor.get("name") or actor.get("email") or "Admin"
            tgt_name   = target_manager.get("name") or target_manager.get("email")
            notif_doc = {
                "id":         f"notif-mass-{_now_iso()}-{to_manager_id}",
                "userId":     to_manager_id,
                "read":       False, "isRead": False,
                "type":       "lead_bulk_reassigned",
                "event":      "lead_bulk_reassigned",
                "title":      f"You have been assigned {processed} {entity}(s) by {actor_name}",
                "message":    f"{processed} transferred · {total_tasks} open tasks",
                "i18n_key":   "notif_bulk_in",
                "i18n_params": {"count": processed, "tasksMoved": total_tasks, "actor": actor_name, "entity": entity},
                "severity":   "info",
                "meta":       {"count": processed, "tasksMoved": total_tasks,
                               "fromActor": actor_name, "entity": entity,
                               "url": f"/admin/{entity}s"},
                "soundKey":   "lead_assigned",
                "created_at": _now_iso(), "createdAt": _now_iso(),
            }
            await db.notifications.insert_one(notif_doc)
            prev_managers: set = {r.get("fromManagerId") for r in results if r.get("ok") and r.get("fromManagerId") and r.get("fromManagerId") != to_manager_id}
            confirm_rows = []
            for pmid in prev_managers:
                confirm_rows.append({
                    "id": f"notif-mass-confirm-{_now_iso()}-{pmid}",
                    "userId": pmid,
                    "read": False, "isRead": False,
                    "type": "lead_bulk_reassigned_out",
                    "event":"lead_bulk_reassigned_out",
                    "title":   f"Transferred to manager {tgt_name}",
                    "message": f"{processed} {entity}(s) · {total_tasks} tasks",
                    "i18n_key": "notif_bulk_out",
                    "i18n_params": {"count": processed, "tasksMoved": total_tasks, "target": tgt_name, "entity": entity},
                    "severity": "info",
                    "meta": {"count": processed, "toManagerId": to_manager_id, "entity": entity},
                    "created_at": _now_iso(), "createdAt": _now_iso(),
                })
            if confirm_rows:
                await db.notifications.insert_many(confirm_rows)
    except Exception as _e:
        logger.warning("[reassignment] mass notification failed: %s", _e)

    return {
        "success": failed == 0,
        "processed": processed,
        "no_change": no_change,
        "failed": failed,
        "total": len(unique_ids),
        "entity": entity,
        "toManagerId": to_manager_id,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Workload payload (for the UI to show real load when picking a manager)
# ---------------------------------------------------------------------------
LOAD_WEIGHTS = {
    "leads":     1.0,
    "customers": 1.0,
    "deals":     2.0,
    "tasks":     0.5,
}

LEAD_ACTIVE_FILTER     = {"status": {"$nin": ["archived", "lost"]}}
CUSTOMER_ACTIVE_FILTER = {}  # customer doesn't have a "lost" concept
DEAL_ACTIVE_FILTER     = {"status": {"$nin": ["won", "lost", "cancelled"]}}
TASK_ACTIVE_FILTER     = {"status": {"$nin": ["done", "cancelled"]}}


async def get_managers_with_workload(
    db,
    *,
    actor: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return staff with role manager/team_lead, enriched with active workload.

    ACL:
      * admin / owner / master_admin → see everyone.
      * team_lead                     → see only own team.
      * manager                       → see only themselves.
    """
    role = _normalize_role(actor.get("role"))
    query: Dict[str, Any] = {"role": {"$in": ["manager", "team_lead"]}}

    if role in ADMIN_ROLES:
        pass  # see all
    elif role == "team_lead":
        query["teamId"] = actor.get("teamId")  # exact match incl. None
    elif role == "manager":
        query["id"] = actor.get("id")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")

    cursor = db.staff.find(query, {"_id": 0, "password": 0})
    staff = await cursor.to_list(length=200)

    out: List[Dict[str, Any]] = []
    for m in staff:
        mid = m.get("id")
        if not mid:
            continue
        active_leads     = await db.leads.count_documents({**LEAD_ACTIVE_FILTER,     "managerId": mid})
        active_customers = await db.customers.count_documents({**CUSTOMER_ACTIVE_FILTER, "managerId": mid})
        active_deals     = await db.deals.count_documents({**DEAL_ACTIVE_FILTER,     "managerId": mid})
        active_tasks     = await db.tasks.count_documents({**TASK_ACTIVE_FILTER,     "assigneeId": mid})

        load_score = round(
            active_leads     * LOAD_WEIGHTS["leads"]
            + active_customers * LOAD_WEIGHTS["customers"]
            + active_deals   * LOAD_WEIGHTS["deals"]
            + active_tasks   * LOAD_WEIGHTS["tasks"],
            1,
        )

        out.append({
            "id":              mid,
            "name":            m.get("name"),
            "email":           m.get("email"),
            "role":            m.get("role"),
            "teamId":          m.get("teamId"),
            "avatarUrl":       m.get("avatarUrl") or m.get("avatar"),
            "isAvailable":     m.get("is_active", True) is not False,
            "activeLeads":     active_leads,
            "activeCustomers": active_customers,
            "activeDeals":     active_deals,
            "activeTasks":     active_tasks,
            "loadScore":       load_score,
        })

    # Sort by lowest load first — UI hint for fair distribution.
    out.sort(key=lambda x: (not x["isAvailable"], x["loadScore"]))
    return out


# ---------------------------------------------------------------------------
# Audit query helper (used by UI history)
# ---------------------------------------------------------------------------
async def get_audit_history(
    db,
    *,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Return newest-first audit history."""
    q: Dict[str, Any] = {}
    if entity:
        q["entity"] = entity
    if entity_id:
        q["entityId"] = entity_id
    cursor = db.reassignments.find(q, {"_id": 0}).sort("createdAt", -1).limit(int(limit))
    return await cursor.to_list(length=int(limit))


# ---------------------------------------------------------------------------
# Customers backfill — best-effort match by email/phone to leads.
# Called once at startup; safe to re-run.
# ---------------------------------------------------------------------------
async def backfill_customer_manager_id(db) -> Dict[str, int]:
    """For customers missing managerId, try to inherit from a matching lead.

    Match rules (in order):
      1. By email (case-insensitive).
      2. By phone (digits-only).

    Returns counts: {scanned, matched, updated}.
    """
    scanned = 0
    matched = 0
    updated = 0

    cursor = db.customers.find(
        {"$or": [{"managerId": {"$exists": False}}, {"managerId": None}]},
        {"_id": 0, "id": 1, "email": 1, "phone": 1},
    )

    async for c in cursor:
        scanned += 1
        email = (c.get("email") or "").strip().lower()
        phone = "".join(ch for ch in (c.get("phone") or "") if ch.isdigit())

        lead_match = None
        if email:
            lead_match = await db.leads.find_one(
                {"email": {"$regex": f"^{email}$", "$options": "i"}, "managerId": {"$exists": True, "$ne": None}},
                {"_id": 0, "managerId": 1},
            )
        if not lead_match and phone:
            lead_match = await db.leads.find_one(
                {"phone": {"$regex": phone, "$options": "i"}, "managerId": {"$exists": True, "$ne": None}},
                {"_id": 0, "managerId": 1},
            )

        if lead_match and lead_match.get("managerId"):
            matched += 1
            try:
                res = await db.customers.update_one(
                    {"id": c.get("id")},
                    {"$set": {
                        "managerId": lead_match["managerId"],
                        "managerId_source": "backfill_from_lead",
                        "managerId_updated_at": _now_iso(),
                    }},
                )
                if res.modified_count > 0:
                    updated += 1
            except Exception as e:  # pragma: no cover
                logger.warning("[reassignment.backfill] update failed customer=%s err=%s",
                               c.get("id"), e)

    logger.info("[reassignment.backfill] scanned=%d matched=%d updated=%d",
                scanned, matched, updated)
    return {"scanned": scanned, "matched": matched, "updated": updated}
