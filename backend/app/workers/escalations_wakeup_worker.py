"""
escalations_wakeup_worker.py
============================

Wave-8 — Insights / Risk & Alerts vertical.

Purpose
-------
A small, focused background worker that periodically scans
`db.escalations` for snoozed rows whose `snoozedUntil` has elapsed,
returns them to the active queue (status=open), and emits a real-time
notification so the Insights → Risk & Alerts feed updates without the
user having to refresh.

Why a dedicated worker (and not a per-request filter only)
----------------------------------------------------------
The GET /api/escalations endpoint already hides currently-snoozed rows
(safe & cheap).  However that means a manager who snoozed an item for
4h would never receive a *push* when the snooze elapses — they would
only see it on the next refresh.  This worker closes that gap by:

  * flipping `status: snoozed → open` once `snoozedUntil <= now`
  * recording `wakeAt` for audit
  * inserting a `db.notifications` row addressed to the previous owner
  * emitting `notification` via Socket.IO (best-effort)

Architecture
------------
* Module is **standalone** — does NOT import from server.py.
* Receives its `db` (motor) and `sio` (Socket.IO server) via `init()`.
* Loop is async / cooperative and is registered through
  `worker_registry` (see app/core/worker_registry.py) so it is
  lifecycle-managed alongside other supervised workers.
* Tuning knobs (interval / batch size) are module constants; can be
  overridden via env without code change.

Idempotency
-----------
Wake-ups are guarded by a unique `wakeAt` timestamp written atomically
together with the `status=open` flip.  A row already woken in this
iteration will not match the filter on the next pass.

Failure mode
------------
The loop catches & logs any exception per-iteration and continues.
Critical=False at the registry level (revenue is not affected if the
worker pauses temporarily — manual refresh still works).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("bibi.escalations_wakeup")

# ── Tuning knobs ────────────────────────────────────────────────
# All are env-overridable so ops can tune without a redeploy.
SCAN_INTERVAL_SEC: int = int(os.getenv("ESC_WAKEUP_INTERVAL_SEC", "60"))    # default 1 min
BATCH_SIZE: int = int(os.getenv("ESC_WAKEUP_BATCH_SIZE", "100"))            # rows per pass
WARMUP_DELAY_SEC: int = int(os.getenv("ESC_WAKEUP_WARMUP_SEC", "20"))       # pre-loop pause

# ── Module-level dependencies wired by init() ──────────────────
_db: Any = None         # motor AsyncIOMotorDatabase
_sio: Any = None        # socketio.AsyncServer
_enabled: bool = False


def init(db: Any, sio: Optional[Any] = None) -> None:
    """Wire dependencies.  Idempotent — safe to call twice."""
    global _db, _sio, _enabled
    _db = db
    _sio = sio
    # Motor / pymongo Database objects intentionally disable bool() — compare
    # with `is not None` (per Mongo client guidance).
    _enabled = db is not None
    logger.info(
        "[esc_wakeup] initialised (db=%s, sio=%s, interval=%ss)",
        db is not None, sio is not None, SCAN_INTERVAL_SEC,
    )


async def _wake_one_pass() -> Dict[str, int]:
    """One scan + flip pass.  Returns counters for logging."""
    if not _enabled or _db is None:
        return {"woken": 0, "notified": 0, "scanned": 0}

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Find candidates first so we can craft per-row notifications
    # (single update_many would be faster but we'd lose the data we
    # need to write notifications).  Batch caps the pass.
    cursor = _db.escalations.find(
        {
            "status": "snoozed",
            "snoozedUntil": {"$lte": now_iso},
        },
        # project only the fields we need to keep IO small
        {
            "_id": 1, "id": 1, "title": 1, "subject": 1, "type": 1,
            "owner": 1, "ownerEmail": 1, "assignedTo": 1,
            "snoozedBy": 1, "snoozedUntil": 1, "severity": 1,
        },
    ).limit(BATCH_SIZE)
    rows = await cursor.to_list(length=BATCH_SIZE)
    if not rows:
        return {"woken": 0, "notified": 0, "scanned": 0}

    woken = 0
    notified = 0
    for row in rows:
        row_id = row.get("_id") or row.get("id")
        if not row_id:
            continue
        # Flip atomically — guard with both id-shape variants and the
        # "still snoozed" precondition to avoid races with manual /resolve.
        res = await _db.escalations.update_one(
            {
                "$or": [{"_id": row_id}, {"id": row_id}],
                "status": "snoozed",
            },
            {
                "$set": {
                    "status": "open",
                    "wakeAt": now_iso,
                    "wakeReason": "snooze_elapsed",
                },
                # keep snoozedUntil for audit trail; unset only volatile bits
                "$unset": {"snoozeReason": ""},
            },
        )
        if res.modified_count == 0:
            continue  # someone else handled it (resolve/reassign race)
        woken += 1

        # Push-notify the owner (best-effort).
        owner = (
            row.get("snoozedBy")
            or row.get("ownerEmail")
            or row.get("owner")
            or row.get("assignedTo")
        )
        if not owner:
            continue
        try:
            notif = {
                "type": "escalation_wakeup",
                "title": "Escalation back in queue",
                "message": row.get("title") or row.get("subject") or row.get("type") or "Snoozed escalation is due again",
                "entityId": row_id,
                "entityType": "escalation",
                "ownerEmail": owner,
                "severity": row.get("severity") or "medium",
                "read": False,
                "createdAt": now_iso,
                "created_at": now,
            }
            await _db.notifications.insert_one(notif)
            notified += 1
            # Socket.IO emit is best-effort — silently skip if not wired.
            if _sio is not None:
                try:
                    await _sio.emit("notification", {
                        **notif,
                        # ObjectId is not JSON-serialisable — drop it
                        "_id": str(notif.get("_id")) if notif.get("_id") else None,
                        "created_at": now_iso,
                    }, room=f"user_{owner}")
                except Exception:
                    logger.debug("[esc_wakeup] sio.emit failed for %s", owner, exc_info=True)
        except Exception:
            logger.exception("[esc_wakeup] failed to insert notification for %s", row_id)

    return {"woken": woken, "notified": notified, "scanned": len(rows)}


async def loop() -> None:
    """Main worker loop.  Registered with worker_registry on startup."""
    if not _enabled:
        logger.warning("[esc_wakeup] loop started but worker is disabled (no db).  Exiting.")
        return

    if WARMUP_DELAY_SEC > 0:
        await asyncio.sleep(WARMUP_DELAY_SEC)

    logger.info("[esc_wakeup] loop running (every %ss)", SCAN_INTERVAL_SEC)
    while True:
        try:
            res = await _wake_one_pass()
            if res["woken"]:
                logger.info(
                    "[esc_wakeup] woke=%d notified=%d scanned=%d",
                    res["woken"], res["notified"], res["scanned"],
                )
        except asyncio.CancelledError:
            logger.info("[esc_wakeup] cancelled — exiting cleanly")
            raise
        except Exception:
            logger.exception("[esc_wakeup] loop iteration failed")
        await asyncio.sleep(SCAN_INTERVAL_SEC)


__all__ = ["init", "loop", "SCAN_INTERVAL_SEC", "BATCH_SIZE"]
