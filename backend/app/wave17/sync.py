"""
BIBI Cars — Wave 17 — Sync layer (idempotent source → action upsert)
=======================================================================

The sync runs `scan_all()` and, for each suggested action:
  * If an OPEN action with the same `source_key` already exists → update
    priority/title/description/impact/owner if they drifted (so the source
    of truth remains the source scanner, not stale snapshots).
  * If a RESOLVED/CANCELLED action with the same key exists AND the
    suggestion is still surfaced → reopen it.
  * Otherwise → create a fresh one.

This is also called on every Inbox/My/Team request (cheap, 1 mongo read +
batch writes) so the Action Center is always live.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.wave17.service import create_action, _now_iso, _ev
from app.wave17.sources import scan_all


async def sync_actions(db: AsyncIOMotorDatabase, user: Dict[str, Any]) -> Dict[str, Any]:
    """Idempotent upsert of source-derived actions.

    Returns a small report:
        { created: N, updated: N, reopened: N, closed_stale: N, total_suggested: N }
    """
    suggested = await scan_all(db, user)
    now = _now_iso()
    keys = [s["key"] for s in suggested if s.get("key")]

    existing = await db.actions.find(
        {"source_key": {"$in": keys}},
        {"_id": 0}
    ).to_list(length=10000) if keys else []
    by_key = {e["source_key"]: e for e in existing if e.get("source_key")}

    created = updated = reopened = 0
    for s in suggested:
        k   = s["key"]
        cur = by_key.get(k)
        if cur is None:
            payload = {**s, "source_key": k,
                        "due_at": (datetime.now(timezone.utc) + timedelta(days=int(s.get("due_days") or 2))).isoformat()}
            await create_action(db, user, payload)
            created += 1
            continue

        # Action already exists.
        status = cur.get("status")
        if status in ("resolved", "cancelled"):
            # Reopen if the source is still raising the same issue.
            await db.actions.update_one(
                {"id": cur["id"]},
                {"$set": {"status": "open", "resolved_at": None, "updated_at": now,
                          "priority": s.get("priority") or cur.get("priority"),
                          "description": s.get("description") or cur.get("description"),
                          "impact": float(s.get("impact") or cur.get("impact") or 0)},
                 "$push": {"events": _ev("reopened", user=user, note="Source still active")}}
            )
            reopened += 1
        else:
            # Drift update — keep the existing one but refresh the volatile
            # fields. Owner is preserved if user already reassigned it.
            new_owner_id = s.get("owner_id") if not cur.get("owner_id") else cur.get("owner_id")
            new_owner_nm = s.get("owner_name") if not cur.get("owner_name") else cur.get("owner_name")
            changes: Dict[str, Any] = {}
            for field in ("priority", "title", "description"):
                if s.get(field) and s[field] != cur.get(field):
                    changes[field] = s[field]
            if float(s.get("impact") or 0) != float(cur.get("impact") or 0):
                changes["impact"] = float(s.get("impact") or 0)
            if new_owner_id != cur.get("owner_id"):
                changes["owner_id"]   = new_owner_id
                changes["owner_name"] = new_owner_nm
            if changes:
                changes["updated_at"] = now
                await db.actions.update_one({"id": cur["id"]},
                    {"$set": changes,
                     "$push": {"events": _ev("updated", user=user, note="Refreshed from source",
                                              meta={"fields": list(changes.keys())})}}
                )
                updated += 1

    # Close stale: open actions whose key is no longer surfaced.
    closed_stale = 0
    open_old = await db.actions.find(
        {"status": {"$in": ["open", "in_progress", "snoozed"]},
         "source": {"$in": ["operations", "contract", "delivery", "forecast"]},
         "source_key": {"$nin": keys}},
        {"_id": 0, "id": 1, "source_key": 1, "source": 1}
    ).to_list(length=2000)
    if open_old:
        ids = [r["id"] for r in open_old]
        res = await db.actions.update_many(
            {"id": {"$in": ids}},
            {"$set": {"status": "resolved", "resolved_at": now,
                      "updated_at": now, "meta.outcome": "auto_resolved"},
             "$push": {"events": {"kind": "auto_resolved", "at": now,
                                    "note": "Source no longer raising this issue"}}}
        )
        closed_stale = int(res.modified_count or 0)

    return {
        "created":         created,
        "updated":         updated,
        "reopened":        reopened,
        "closed_stale":    closed_stale,
        "total_suggested": len(suggested),
    }


__all__ = ["sync_actions"]
