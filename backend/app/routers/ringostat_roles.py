"""
Ringostat role-based UX endpoints
=================================

Phase IV-6: deliver different Ringostat experiences per role.

    manager     → keep current "must fill outcome" intrusive flow
    team_lead   → team supervision summary (no forced banners)
    admin       → silent oversight: high-level dashboard + opt-in alerts

This file adds:

    GET    /api/teamlead/calls/overview      → team supervision summary
    GET    /api/teamlead/calls/managers      → per-manager breakdown for team
    GET    /api/admin/ringostat/oversight    → admin-only company-wide summary
    GET    /api/me/preferences/ringostat-ui  → personal UI prefs (banners on/off)
    PATCH  /api/me/preferences/ringostat-ui  → save personal UI prefs

User preferences are stored in ``user_preferences`` collection with
``_id == user_id`` (lazy-create, no migration needed).

We deliberately reuse the SAME data model (``ringostat_calls``) — the
difference between roles is purely in WHICH cuts/filters are exposed
and how the frontend presents them. No data duplication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
import os

from security import require_admin, require_manager_or_admin, require_user

logger = logging.getLogger("bibi.ringostat.roles")

# ── DB handle (lazy, same pattern as admin_ringostat.py) ──────────────
_client: Optional[AsyncIOMotorClient] = None


def _db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return _client[os.environ.get("DB_NAME", "test_database")]


# ── UI preferences (per-user) ────────────────────────────────────────
PREFS_DEFAULT = {
    "show_live_bar": True,
    "show_incoming_popup": True,
    "show_missed_alerts": True,
    "show_outcome_banner": True,
    "force_outcome_blocking": True,  # manager-mode default; team_lead/admin override
    "show_aggregate_summary": False,
}

# Per-role overrides — the *default* shape for a role.  Saved per-user
# prefs still override these.
ROLE_PREFS_DEFAULTS = {
    "manager": {
        "show_live_bar": True,
        "show_incoming_popup": True,
        "show_missed_alerts": True,
        "show_outcome_banner": True,
        "force_outcome_blocking": True,
        "show_aggregate_summary": False,
    },
    "team_lead": {
        # Team leads see supervision summary, not personal call popups
        "show_live_bar": True,
        "show_incoming_popup": False,
        "show_missed_alerts": False,
        "show_outcome_banner": False,
        "force_outcome_blocking": False,
        "show_aggregate_summary": True,
    },
    "admin": {
        # Admins are passive observers by default
        "show_live_bar": False,
        "show_incoming_popup": False,
        "show_missed_alerts": False,
        "show_outcome_banner": False,
        "force_outcome_blocking": False,
        "show_aggregate_summary": True,
    },
    "owner": {
        "show_live_bar": False,
        "show_incoming_popup": False,
        "show_missed_alerts": False,
        "show_outcome_banner": False,
        "force_outcome_blocking": False,
        "show_aggregate_summary": True,
    },
    "master_admin": {
        "show_live_bar": False,
        "show_incoming_popup": False,
        "show_missed_alerts": False,
        "show_outcome_banner": False,
        "force_outcome_blocking": False,
        "show_aggregate_summary": True,
    },
}


def _defaults_for(role: str) -> Dict[str, Any]:
    out = dict(PREFS_DEFAULT)
    out.update(ROLE_PREFS_DEFAULTS.get((role or "").lower(), {}))
    return out


router = APIRouter()


# ─── Personal UI preferences ──────────────────────────────────────────
@router.get("/api/me/preferences/ringostat-ui")
async def get_my_ringostat_ui_prefs(user: dict = Depends(require_user)):
    """Return effective Ringostat UI preferences for the current user.

    Order of precedence:
      1) explicit per-user override (``user_preferences.{user_id}.ringostat_ui``)
      2) role default (manager / team_lead / admin / owner / master_admin)
      3) global default (``PREFS_DEFAULT``)

    The frontend should hide / show widgets based on this, NEVER hardcode
    role checks on its own.
    """
    db = _db()
    role = (user.get("role") or "").lower()
    uid = user.get("id") or user.get("_id") or user.get("sub")
    defaults = _defaults_for(role)
    stored = await db.user_preferences.find_one({"_id": uid}) if uid else None
    saved = (stored or {}).get("ringostat_ui") or {}
    # saved keys override role defaults
    effective = dict(defaults)
    effective.update({k: v for k, v in saved.items() if k in PREFS_DEFAULT})
    return {
        "role": role,
        "effective": effective,
        "saved": saved,
        "role_defaults": defaults,
    }


@router.patch("/api/me/preferences/ringostat-ui")
async def patch_my_ringostat_ui_prefs(
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(require_user),
):
    """Update the current user's Ringostat UI preferences.

    Only keys in ``PREFS_DEFAULT`` are accepted; everything else is ignored.
    Managers may NOT disable ``force_outcome_blocking`` — that's an
    invariant of their role (admin can still flip it from admin UI on
    their behalf via ringostat_config.automation_rules).
    """
    db = _db()
    role = (user.get("role") or "").lower()
    uid = user.get("id") or user.get("_id") or user.get("sub")
    if not uid:
        raise HTTPException(status_code=400, detail="User has no id")

    clean: Dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if k in PREFS_DEFAULT:
            clean[k] = bool(v) if isinstance(PREFS_DEFAULT[k], bool) else v

    # Check if payload had ANY valid keys before hard guard
    had_valid_keys = len(clean) > 0

    # Hard guard: managers can't silence themselves out of outcome flow
    if role == "manager":
        clean.pop("force_outcome_blocking", None)
        clean.pop("show_outcome_banner", None)

    # If no valid keys at all (before guard), return 400
    if not had_valid_keys:
        raise HTTPException(status_code=400, detail="No valid preference keys in payload")

    # If clean is empty AFTER guards (but had valid keys), return success (silent drop)
    if not clean:
        new_saved = await _get_saved(db, uid)
        defaults = _defaults_for(role)
        effective = {**defaults, **new_saved}
        return {"success": True, "saved": new_saved, "effective": effective}

    now = datetime.now(timezone.utc)
    await db.user_preferences.update_one(
        {"_id": uid},
        {"$set": {"ringostat_ui": {**(await _get_saved(db, uid)), **clean}, "updated_at": now}},
        upsert=True,
    )
    # Recompute effective for return
    new_saved = await _get_saved(db, uid)
    defaults = _defaults_for(role)
    effective = {**defaults, **new_saved}
    return {"success": True, "saved": new_saved, "effective": effective}


async def _get_saved(db, uid: str) -> Dict[str, Any]:
    doc = await db.user_preferences.find_one({"_id": uid}) or {}
    return doc.get("ringostat_ui") or {}


# ─── Team-lead supervision endpoints ──────────────────────────────────
def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def _team_member_ids(db, team_lead_id: str) -> List[str]:
    """Return the list of staff ids that report to this team lead.

    Resolution order:
      1) ``staff.team_lead_id`` field
      2) ``staff.manager_id`` field (legacy)
      3) ``teams`` collection: documents where ``leader_id == team_lead_id``
         list members in ``member_ids``
    Always includes the team_lead itself so they see their own activity.
    """
    ids: set = {team_lead_id}
    if not team_lead_id:
        return list(ids)
    async for s in db.staff.find(
        {"$or": [{"team_lead_id": team_lead_id}, {"manager_id": team_lead_id}]},
        {"_id": 1, "id": 1},
    ):
        ids.add(s.get("id") or s.get("_id"))
    async for team in db.teams.find({"leader_id": team_lead_id}, {"member_ids": 1}):
        for m in team.get("member_ids") or []:
            ids.add(m)
    return [x for x in ids if x]


@router.get("/api/teamlead/calls/overview")
async def teamlead_calls_overview(
    days: int = 1,
    user: dict = Depends(require_manager_or_admin),
):
    """Aggregate calls for the team supervised by the current user.

    ``days`` is the look-back window (1 = today, 7 = last week, …).
    Admins / owners see the WHOLE company (no team filter); team_leads
    see only their team; ordinary managers can also call this but they
    will just see *themselves* (defensive — single-member team).
    """
    db = _db()
    role = (user.get("role") or "").lower()
    uid = user.get("id") or user.get("_id") or user.get("sub")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(days, 1))

    base_filter: Dict[str, Any] = {"started_at": {"$gte": cutoff}}

    if role in ("admin", "owner", "master_admin"):
        scope = "company"
        member_ids = []
    elif role == "team_lead":
        scope = "team"
        member_ids = await _team_member_ids(db, uid)
        base_filter["manager_id"] = {"$in": member_ids}
    else:
        scope = "self"
        member_ids = [uid] if uid else []
        base_filter["manager_id"] = {"$in": member_ids}

    total = await db.ringostat_calls.count_documents(base_filter)
    answered = await db.ringostat_calls.count_documents({**base_filter, "status": "ANSWERED"})
    missed = await db.ringostat_calls.count_documents(
        {**base_filter, "status": {"$in": ["MISSED", "NO ANSWER", "NOANSWER", "NO_ANSWER"]}}
    )
    inbound = await db.ringostat_calls.count_documents({**base_filter, "direction": "inbound"})
    outbound = await db.ringostat_calls.count_documents({**base_filter, "direction": "outbound"})
    pending_outcome = await db.ringostat_calls.count_documents(
        {
            **base_filter,
            "duration": {"$gt": 30},
            "status": "ANSWERED",
            "$or": [{"outcome": None}, {"outcome": ""}, {"outcome": {"$exists": False}}],
        }
    )
    unassigned = await db.ringostat_calls.count_documents(
        {
            **base_filter,
            "$or": [{"manager_id": None}, {"manager_id": ""}, {"manager_id": {"$exists": False}}],
        }
    )

    # Avg duration & calls today
    today_start = _today_utc_start()
    today_filter = {**base_filter, "started_at": {"$gte": today_start}}
    today_total = await db.ringostat_calls.count_documents(today_filter)
    pipeline = [
        {"$match": {**base_filter, "billsec": {"$gt": 0}}},
        {"$group": {"_id": None, "avg": {"$avg": "$billsec"}, "max": {"$max": "$billsec"}}},
    ]
    duration_stats: Dict[str, Any] = {}
    async for r in db.ringostat_calls.aggregate(pipeline):
        duration_stats = {"avg_sec": round(r.get("avg") or 0, 1), "max_sec": int(r.get("max") or 0)}

    return {
        "scope": scope,
        "window_days": days,
        "team_size": len(member_ids) if member_ids else None,
        "totals": {
            "all": total,
            "today": today_total,
            "answered": answered,
            "missed": missed,
            "inbound": inbound,
            "outbound": outbound,
            "answer_rate": round(answered / (answered + missed) * 100, 1) if (answered + missed) else 0.0,
            "pending_outcome": pending_outcome,
            "unassigned": unassigned,
            **duration_stats,
        },
        "alerts": {
            "many_missed": missed > 5,
            "many_pending_outcome": pending_outcome > 10,
            "many_unassigned": unassigned > 5,
        },
    }


@router.get("/api/teamlead/calls/managers")
async def teamlead_calls_by_manager(
    days: int = 1,
    user: dict = Depends(require_manager_or_admin),
):
    """Per-manager breakdown within the scope of the current user."""
    db = _db()
    role = (user.get("role") or "").lower()
    uid = user.get("id") or user.get("_id") or user.get("sub")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(days, 1))

    if role in ("admin", "owner", "master_admin"):
        member_filter: Dict[str, Any] = {}
    elif role == "team_lead":
        members = await _team_member_ids(db, uid)
        member_filter = {"manager_id": {"$in": members}}
    else:
        member_filter = {"manager_id": uid}

    pipeline = [
        {"$match": {"started_at": {"$gte": cutoff}, **member_filter}},
        {
            "$group": {
                "_id": "$manager_id",
                "total": {"$sum": 1},
                "answered": {
                    "$sum": {"$cond": [{"$eq": ["$status", "ANSWERED"]}, 1, 0]}
                },
                "missed": {
                    "$sum": {"$cond": [{"$in": ["$status", ["MISSED", "NO ANSWER", "NOANSWER", "NO_ANSWER"]]}, 1, 0]}
                },
                "pending_outcome": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$gt": ["$duration", 30]},
                                    {"$eq": ["$status", "ANSWERED"]},
                                    {"$or": [{"$eq": ["$outcome", None]}, {"$eq": ["$outcome", ""]}]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
                "avg_duration": {"$avg": "$billsec"},
                "last_call_at": {"$max": "$started_at"},
            }
        },
        {"$sort": {"total": -1}},
    ]

    rows: List[Dict[str, Any]] = []
    async for r in db.ringostat_calls.aggregate(pipeline):
        mid = r["_id"]
        if not mid:
            # rolled up as "unassigned" below
            rows.append(
                {
                    "manager_id": None,
                    "manager_name": "(unassigned)",
                    "total": r["total"],
                    "answered": r["answered"],
                    "missed": r["missed"],
                    "pending_outcome": r["pending_outcome"],
                    "answer_rate": round(r["answered"] / (r["answered"] + r["missed"]) * 100, 1)
                    if (r["answered"] + r["missed"])
                    else 0.0,
                    "avg_duration_sec": round(r.get("avg_duration") or 0, 1),
                    "last_call_at": r["last_call_at"].isoformat() if r.get("last_call_at") else None,
                }
            )
            continue
        person = await db.staff.find_one({"$or": [{"id": mid}, {"_id": mid}]})
        rows.append(
            {
                "manager_id": mid,
                "manager_name": (person or {}).get("name") or (person or {}).get("email") or "unknown",
                "extension": (person or {}).get("extension"),
                "role": (person or {}).get("role"),
                "total": r["total"],
                "answered": r["answered"],
                "missed": r["missed"],
                "pending_outcome": r["pending_outcome"],
                "answer_rate": round(r["answered"] / (r["answered"] + r["missed"]) * 100, 1)
                if (r["answered"] + r["missed"])
                else 0.0,
                "avg_duration_sec": round(r.get("avg_duration") or 0, 1),
                "last_call_at": r["last_call_at"].isoformat() if r.get("last_call_at") else None,
            }
        )
    return {"window_days": days, "rows": rows}


# ─── Admin company-wide oversight ─────────────────────────────────────
@router.get("/api/admin/ringostat/oversight")
async def admin_ringostat_oversight(
    days: int = 1,
    user: dict = Depends(require_admin),
):
    """High-level passive dashboard for admins.

    Designed for "the admin should be able to glance and know if the
    sales operation is healthy without being interrupted by every call".

    Returns:
      - company-level totals (same shape as team_lead overview but always company scope)
      - per-team-lead rollup
      - top managers by call volume + top managers by pending_outcome
      - cron worker last_run_at / status (so admin sees if sync is alive)
    """
    db = _db()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(days, 1))

    base = {"started_at": {"$gte": cutoff}}
    total = await db.ringostat_calls.count_documents(base)
    answered = await db.ringostat_calls.count_documents({**base, "status": "ANSWERED"})
    missed = await db.ringostat_calls.count_documents(
        {**base, "status": {"$in": ["MISSED", "NO ANSWER", "NOANSWER", "NO_ANSWER"]}}
    )
    pending_outcome = await db.ringostat_calls.count_documents(
        {
            **base,
            "duration": {"$gt": 30},
            "status": "ANSWERED",
            "$or": [{"outcome": None}, {"outcome": ""}, {"outcome": {"$exists": False}}],
        }
    )
    unassigned = await db.ringostat_calls.count_documents(
        {**base, "$or": [{"manager_id": None}, {"manager_id": ""}, {"manager_id": {"$exists": False}}]}
    )

    # Top 5 by volume + top 5 by pending_outcome
    pipeline_vol = [
        {"$match": base},
        {"$group": {"_id": "$manager_id", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 5},
    ]
    pipeline_pending = [
        {
            "$match": {
                **base,
                "duration": {"$gt": 30},
                "status": "ANSWERED",
                "$or": [{"outcome": None}, {"outcome": ""}, {"outcome": {"$exists": False}}],
            }
        },
        {"$group": {"_id": "$manager_id", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 5},
    ]

    async def _resolve(rows):
        out = []
        async for r in rows:
            mid = r["_id"]
            person = await db.staff.find_one({"$or": [{"id": mid}, {"_id": mid}]}) if mid else None
            out.append(
                {
                    "manager_id": mid,
                    "manager_name": (person or {}).get("name")
                    or (person or {}).get("email")
                    or ("(unassigned)" if not mid else "unknown"),
                    "count": r["n"],
                }
            )
        return out

    top_volume = await _resolve(db.ringostat_calls.aggregate(pipeline_vol))
    top_pending = await _resolve(db.ringostat_calls.aggregate(pipeline_pending))

    # Cron health (last successful sync)
    last_sync = await db.ringostat_calls.find_one(
        {"source": {"$in": ["cron_export", "webhook"]}},
        sort=[("synced_at", -1)],
    )
    last_sync_at = (last_sync or {}).get("synced_at") or (last_sync or {}).get("updated_at")
    # Mongo stores naive datetimes; normalize before arithmetic with `now` (UTC-aware)
    if last_sync_at and last_sync_at.tzinfo is None:
        last_sync_at = last_sync_at.replace(tzinfo=timezone.utc)

    # Team-lead breakdown
    team_lead_rows = []
    async for tl in db.staff.find({"role": "team_lead"}):
        tl_id = tl.get("id") or tl.get("_id")
        members = await _team_member_ids(db, tl_id)
        tl_total = await db.ringostat_calls.count_documents(
            {**base, "manager_id": {"$in": members}}
        )
        tl_pending = await db.ringostat_calls.count_documents(
            {
                **base,
                "manager_id": {"$in": members},
                "duration": {"$gt": 30},
                "status": "ANSWERED",
                "$or": [{"outcome": None}, {"outcome": ""}, {"outcome": {"$exists": False}}],
            }
        )
        team_lead_rows.append(
            {
                "team_lead_id": tl_id,
                "team_lead_name": tl.get("name") or tl.get("email"),
                "members": len(members),
                "calls": tl_total,
                "pending_outcome": tl_pending,
            }
        )

    return {
        "window_days": days,
        "company_totals": {
            "all": total,
            "answered": answered,
            "missed": missed,
            "answer_rate": round(answered / (answered + missed) * 100, 1) if (answered + missed) else 0.0,
            "pending_outcome": pending_outcome,
            "unassigned": unassigned,
        },
        "top_volume": top_volume,
        "top_pending_outcome": top_pending,
        "team_leads": team_lead_rows,
        "sync_health": {
            "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
            "last_sync_source": (last_sync or {}).get("source"),
            "stale_minutes": (
                round((now - last_sync_at).total_seconds() / 60, 1) if last_sync_at else None
            ),
        },
    }
