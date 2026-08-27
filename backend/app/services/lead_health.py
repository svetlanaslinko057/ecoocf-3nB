"""
BIBI Cars — Wave 9 — Lead Health & Activity Score
==================================================

Single source of truth for lead "operational discipline" indicators:
  * status   — healthy / warning / overdue / stale / dead
  * score    — 0..100 (used for sort & smart filters in future Wave 10)
  * reasons  — list of human-readable explanations
  * next_action — what the manager should do RIGHT NOW

The model is intentionally simple and deterministic — no ML.
Inputs:
  * last_contact_at  — when did we last touch this lead?
  * tasks            — open tasks (count, overdue, soonest due)
  * status           — pipeline stage (some stages are terminal)
  * created_at       — age of the lead
  * calls            — last call date / outcome (optional, best-effort)

This matches the Activity Layer Wave 8 sketched out: the user said the
left filter rail on Zoho is not about pipeline status, it's about
operational discipline. Lead360 surfaces it as a HealthBadge + Next
Action card, the Workspace filter rail filters by it.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


# Cut-off windows (days) — picked from CRM-best-practice + can be tuned
WINDOWS = {
    "fresh":   1,   # 0-1d since last contact: healthy
    "warm":    3,   # 2-3d since last contact: warning if no open tasks
    "stale":   7,   # 4-7d: stale
    "dead":   21,   # >21d: dead unless converted
}

TERMINAL_GOOD = {"converted"}
TERMINAL_BAD  = {"lost", "not_qualified"}


def _safe_parse(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        if isinstance(iso, datetime):
            return iso if iso.tzinfo else iso.replace(tzinfo=timezone.utc)
        s = str(iso).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _days_since(iso: Optional[str], now: datetime) -> Optional[float]:
    d = _safe_parse(iso)
    if not d:
        return None
    return max(0.0, (now - d).total_seconds() / 86400.0)


def compute_lead_health(
    lead: Dict[str, Any],
    *,
    open_tasks: Optional[List[Dict[str, Any]]] = None,
    last_call_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Compute health snapshot for a single lead.

    Returns dict with: status, score, reasons[], next_action{title, kind, urgency}.
    Always safe — never raises; on missing data returns conservative warning.
    """
    now = now or datetime.now(timezone.utc)
    open_tasks = open_tasks or []

    status = (lead.get("status") or "new").lower()

    # ── Terminal states bypass the health math ──
    if status in TERMINAL_GOOD:
        return {
            "status":  "converted",
            "score":   100,
            "reasons": ["Lead converted to customer"],
            "next_action": {
                "kind": "view_customer",
                "title": "Open customer profile",
                "urgency": "none",
                "customer_id": lead.get("customerId"),
            },
        }
    if status in TERMINAL_BAD:
        return {
            "status":  "dead",
            "score":   0,
            "reasons": [f"Lead marked as {status.replace('_',' ')}"],
            "next_action": {
                "kind": "archive",
                "title": "Archive or reopen",
                "urgency": "none",
            },
        }

    reasons: List[str] = []

    # Compute key time deltas
    last_contact_iso = (
        lead.get("last_contact_at")
        or lead.get("last_status_change_at")
        or last_call_at
        or lead.get("updated_at")
        or lead.get("created_at")
    )
    days_since_contact = _days_since(last_contact_iso, now)
    days_since_created = _days_since(lead.get("created_at"), now) or 0.0

    # Open tasks audit
    overdue_tasks = []
    soonest_due: Optional[datetime] = None
    for t in open_tasks:
        due_iso = t.get("due_at") or t.get("dueDate")
        due_dt = _safe_parse(due_iso)
        if due_dt and due_dt < now:
            overdue_tasks.append(t)
        if due_dt and (soonest_due is None or due_dt < soonest_due):
            soonest_due = due_dt
    has_overdue = len(overdue_tasks) > 0
    has_open    = len(open_tasks) > 0

    # ── Score model (0..100) ──
    score = 100

    # Contact freshness
    if days_since_contact is None:
        score -= 25
        reasons.append("No contact recorded")
    elif days_since_contact <= WINDOWS["fresh"]:
        pass  # full credit
    elif days_since_contact <= WINDOWS["warm"]:
        score -= 10
    elif days_since_contact <= WINDOWS["stale"]:
        score -= 25
        reasons.append(f"No contact for {int(days_since_contact)}d")
    elif days_since_contact <= WINDOWS["dead"]:
        score -= 45
        reasons.append(f"Stale for {int(days_since_contact)}d")
    else:
        score -= 65
        reasons.append(f"Dead air for {int(days_since_contact)}d")

    # Tasks discipline
    if has_overdue:
        score -= 25
        reasons.append(f"{len(overdue_tasks)} overdue task(s)")
    elif not has_open and (days_since_contact or 0) > WINDOWS["fresh"]:
        score -= 10
        reasons.append("No follow-up planned")

    # Age penalty for ancient leads still stuck pre-qualified
    if days_since_created > 30 and status in {"new", "contacted"}:
        score -= 10
        reasons.append(f"{int(days_since_created)}d in early pipeline")

    score = max(0, min(100, score))

    # ── Bucket -> categorical status ──
    if score >= 80:
        cat = "healthy"
    elif score >= 55:
        cat = "warning"
    elif score >= 30:
        cat = "overdue" if has_overdue else "stale"
    else:
        cat = "dead"

    # ── Next action recommendation ──
    next_action = _suggest_next_action(
        lead=lead,
        status=status,
        cat=cat,
        days_since_contact=days_since_contact,
        has_overdue=has_overdue,
        overdue_tasks=overdue_tasks,
        soonest_due=soonest_due,
        open_tasks_count=len(open_tasks),
    )

    return {
        "status":       cat,
        "score":        score,
        "reasons":      reasons,
        "last_contact": last_contact_iso,
        "days_since_contact": (
            round(days_since_contact, 1) if days_since_contact is not None else None
        ),
        "open_tasks":   len(open_tasks),
        "overdue_tasks": len(overdue_tasks),
        "next_action":  next_action,
    }


def _suggest_next_action(
    *, lead, status, cat, days_since_contact, has_overdue, overdue_tasks,
    soonest_due, open_tasks_count,
) -> Dict[str, Any]:
    """Heuristic next-action picker. Returns
       {kind, title, urgency: 'low'|'normal'|'high'|'critical', payload?}
    """
    phone = lead.get("phone")

    if has_overdue:
        return {
            "kind":    "complete_task",
            "title":   f"Complete {len(overdue_tasks)} overdue task(s)",
            "urgency": "critical",
            "task_id": (overdue_tasks[0] or {}).get("id"),
        }

    if status == "new":
        return {
            "kind":    "first_call",
            "title":   "Make the first call",
            "urgency": "high" if (days_since_contact or 0) > 0.25 else "normal",
            "phone":   phone,
        }

    if status == "contacted" and (days_since_contact or 0) > WINDOWS["fresh"]:
        return {
            "kind":    "qualify",
            "title":   "Qualify need + budget",
            "urgency": "high",
            "phone":   phone,
        }

    if status == "qualified" and not soonest_due:
        return {
            "kind":    "send_quote",
            "title":   "Send VIN/quote proposal",
            "urgency": "high",
        }

    if status == "negotiation":
        return {
            "kind":    "close_deal",
            "title":   "Push to decision / close",
            "urgency": "high" if cat in ("warning", "overdue", "stale") else "normal",
            "phone":   phone,
        }

    if status == "decision":
        return {
            "kind":    "follow_up",
            "title":   "Awaiting decision — follow up",
            "urgency": "high" if (days_since_contact or 0) > WINDOWS["warm"] else "normal",
            "phone":   phone,
        }

    if cat in ("stale", "dead") and (days_since_contact or 0) > WINDOWS["stale"]:
        return {
            "kind":    "reanimate",
            "title":   "Re-engage or disqualify",
            "urgency": "high",
            "phone":   phone,
        }

    # default
    return {
        "kind":    "call",
        "title":   "Call the lead",
        "urgency": "normal",
        "phone":   phone,
    }
