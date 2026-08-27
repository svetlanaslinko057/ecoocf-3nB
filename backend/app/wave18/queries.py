"""
BIBI Cars — Wave 18 — Notification queries & aggregations
==============================================================
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorDatabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def inbox(
    db: AsyncIOMotorDatabase,
    user_id: str,
    *,
    only_unread: bool = False,
    include_dismissed: bool = False,
    limit: int = 100,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {"recipient_id": user_id, "channel": "in_app"}
    if only_unread:
        q["read_at"] = None
    if not include_dismissed:
        q["dismissed_at"] = None
    rows = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
    unread = sum(1 for r in rows if r.get("read_at") is None)
    by_event:    Dict[str, int] = defaultdict(int)
    by_priority: Dict[str, int] = defaultdict(int)
    for r in rows:
        by_event[r.get("event") or ""] += 1
        by_priority[r.get("priority") or "low"] += 1
    return {
        "as_of":       _now_iso(),
        "items":       rows,
        "total":       len(rows),
        "unread":      unread,
        "by_event":    dict(by_event),
        "by_priority": dict(by_priority),
    }


async def unread_count(db, user_id: str) -> int:
    if not user_id: return 0
    return await db.notifications.count_documents({
        "recipient_id": user_id, "channel": "in_app",
        "read_at": None, "dismissed_at": None,
    })


async def mark_read(db, user_id: str, notif_id: str) -> Optional[Dict[str, Any]]:
    await db.notifications.update_one(
        {"id": notif_id, "recipient_id": user_id},
        {"$set": {"status": "read", "read_at": _now_iso()}}
    )
    return await db.notifications.find_one({"id": notif_id, "recipient_id": user_id}, {"_id": 0})


async def mark_all_read(db, user_id: str) -> int:
    res = await db.notifications.update_many(
        {"recipient_id": user_id, "channel": "in_app", "read_at": None},
        {"$set": {"status": "read", "read_at": _now_iso()}}
    )
    return int(res.modified_count or 0)


async def dismiss(db, user_id: str, notif_id: str) -> Optional[Dict[str, Any]]:
    await db.notifications.update_one(
        {"id": notif_id, "recipient_id": user_id},
        {"$set": {"status": "dismissed", "dismissed_at": _now_iso()}}
    )
    return await db.notifications.find_one({"id": notif_id, "recipient_id": user_id}, {"_id": 0})


async def analytics(db, *, days: int = 30) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    rows = await db.notifications.find(
        {"created_at": {"$gte": since}},
        {"_id": 0}
    ).to_list(length=10000)
    by_channel: Dict[str, int] = defaultdict(int)
    by_event:   Dict[str, int] = defaultdict(int)
    by_status:  Dict[str, int] = defaultdict(int)
    delivered = 0; failed = 0; read_count = 0
    for r in rows:
        by_channel[r.get("channel") or ""] += 1
        by_event  [r.get("event")   or ""] += 1
        st = r.get("status") or ""
        by_status[st] += 1
        if st in ("sent", "read"):  delivered += 1
        if st == "failed":          failed    += 1
        if r.get("read_at"):        read_count += 1
    total = len(rows)
    return {
        "as_of":       _now_iso(),
        "window_days": days,
        "total":       total,
        "delivered":   delivered,
        "failed":      failed,
        "read":        read_count,
        "delivery_rate": round((delivered / total * 100), 1) if total else 0.0,
        "read_rate":     round((read_count / total * 100), 1) if total else 0.0,
        "by_channel":  dict(by_channel),
        "by_event":    dict(by_event),
        "by_status":   dict(by_status),
    }


__all__ = ["inbox", "unread_count", "mark_read", "mark_all_read",
           "dismiss", "analytics"]
