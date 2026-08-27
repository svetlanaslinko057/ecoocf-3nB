"""
BIBI Cars — Wave 10A — Lead Priority Score
==========================================

Deterministic priority engine that surfaces "who do I call first" for the
manager. Built on top of the existing health signals — no LLM, no training.

Inputs:
  * lead doc            — status, source, budget, vin, created_at, last_contact_at
  * health              — output of compute_lead_health() (score, status, days_since)
  * open_tasks (count)  — operational discipline signal
  * recent calls count  — engagement signal (best-effort)

Output:
  {
    "score":  0..100,
    "bucket": "A" | "B" | "C" | "D",
    "reasons": ["high budget", "in negotiation", ...],
    "label":   "Hot" | "Active" | "Watch" | "Cold",
  }

Bucket cutoffs are intentionally simple so they're explainable:
  A (>= 80) — hot, push for close
  B (60-79) — active, follow up
  C (40-59) — watch
  D (<  40) — cold / backburner
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


# Reused signals: status weight on priority
_STATUS_BONUS = {
    "new":           -5,
    "contacted":      0,
    "qualified":     10,
    "negotiation":   15,
    "decision":      20,
    "not_qualified": -40,
    "lost":          -50,
    "converted":     -30,   # already a customer, deprioritise in lead view
}

# Source quality (Wave 10A heuristic — can be re-tuned per market data)
_SOURCE_BONUS = {
    "website":        5,
    "referral":      10,
    "partner":       10,
    "social_media":   3,
    "advertisement":  0,
    "cold_call":     -5,
    "other":          0,
}


def _budget_bonus(value: Optional[float]) -> int:
    try:
        v = float(value or 0)
    except Exception:
        v = 0.0
    if v >= 60_000:  return 15
    if v >= 30_000:  return 10
    if v >= 15_000:  return 5
    if v == 0:       return -5
    return 0


def compute_lead_priority(
    lead: Dict[str, Any],
    *,
    health: Optional[Dict[str, Any]] = None,
    open_tasks_count: int = 0,
    recent_calls_count: int = 0,
) -> Dict[str, Any]:
    """Compute the priority bundle. Conservative — never raises."""
    health = health or {}
    reasons: List[str] = []
    score = float(health.get("score") or 50)  # anchor to health if known

    # Status bias
    st = (lead.get("status") or "new").lower()
    sb = _STATUS_BONUS.get(st, 0)
    score += sb
    if sb > 0:
        reasons.append(f"In {st}")
    elif sb < -10:
        reasons.append(f"Status: {st}")

    # Budget bias
    bb = _budget_bonus(lead.get("budgetEur") or lead.get("budgetUsd"))
    if bb:
        score += bb
        if bb > 0:
            reasons.append("High budget" if bb >= 10 else "Has budget")
        elif bb < 0:
            reasons.append("No budget set")

    # Source bias
    src = (lead.get("source") or "").lower()
    sb2 = _SOURCE_BONUS.get(src, 0)
    if sb2:
        score += sb2
        if sb2 > 0:
            reasons.append(f"Strong source ({src})")

    # VIN already linked → shopping
    if lead.get("vin"):
        score += 8
        reasons.append("VIN linked")

    # Engagement
    if recent_calls_count >= 3:
        score += 8
        reasons.append(f"{recent_calls_count} recent calls")
    elif recent_calls_count >= 1:
        score += 3

    # Discipline: open tasks but no overdue is good
    overdue = int(health.get("overdue_tasks") or 0)
    if overdue:
        score -= 10
        reasons.append(f"{overdue} overdue task(s)")
    elif open_tasks_count:
        score += 3

    # Clamp + bucket
    score = max(0.0, min(100.0, score))
    score_int = int(round(score))

    # ─── Wave 10A.1 — qualification floor ───────────────────────────────
    # Business rule: a brand-new lead with no budget on file has not been
    # qualified by anyone yet — even if it came from a strong source the
    # priority must not be higher than C ("watch"). This avoids
    # over-promoting noisy referrals before a manager has even talked to
    # them.
    budget_value = float(lead.get("budgetEur") or lead.get("budgetUsd") or 0)
    st_lower = (lead.get("status") or "new").lower()
    if st_lower == "new" and budget_value == 0:
        if score_int >= 60:
            score_int = 59
            reasons.append("Unqualified (no budget)")

    if score_int >= 80:
        bucket, label = "A", "Hot"
    elif score_int >= 60:
        bucket, label = "B", "Active"
    elif score_int >= 40:
        bucket, label = "C", "Watch"
    else:
        bucket, label = "D", "Cold"

    return {
        "score":   score_int,
        "bucket":  bucket,
        "label":   label,
        "reasons": reasons[:4],   # keep tooltip short
    }


def quick_priority_bucket(lead: Dict[str, Any], health_bucket: Optional[str] = None) -> str:
    """Lightweight bucket using only lead-doc fields. Mirrors compute_lead_priority
    but cheap — used for filtering hundreds of leads in /kanban without joins.
    """
    score = 50
    st = (lead.get("status") or "new").lower()
    score += _STATUS_BONUS.get(st, 0)
    score += _budget_bonus(lead.get("budgetEur") or lead.get("budgetUsd"))
    score += _SOURCE_BONUS.get((lead.get("source") or "").lower(), 0)
    if lead.get("vin"):
        score += 8

    # Coarse health adjust
    hb = (health_bucket or "").lower()
    if hb == "healthy":
        score += 10
    elif hb == "warning":
        score += 0
    elif hb == "stale":
        score -= 10
    elif hb == "dead":
        score -= 25

    score = max(0, min(100, score))

    # ─── Wave 10A.1 — qualification floor ───────────────────────────────
    # New lead with no budget cannot exceed C — see compute_lead_priority.
    budget_value = float(lead.get("budgetEur") or lead.get("budgetUsd") or 0)
    if (lead.get("status") or "new").lower() == "new" and budget_value == 0 and score >= 60:
        score = 59

    if score >= 80:  return "A"
    if score >= 60:  return "B"
    if score >= 40:  return "C"
    return "D"


# ──────────────────────────────────────────────────────────────────────────
# Wave 10A — Smart Filter Presets
#
# Each preset is a named query that LeadFiltersSidebar can apply with one
# click. The query is a dict of params understood by /api/leads and
# /api/leads/kanban. Backend exposes this list via /api/leads/smart-filters
# so the frontend never hard-codes business logic.
# ──────────────────────────────────────────────────────────────────────────

SMART_FILTERS: List[Dict[str, Any]] = [
    {
        "id":   "needs_contact_today",
        "name": "Needs contact today",
        "name_i18n": {
            "uk": "Потрібен контакт сьогодні",
            "en": "Needs contact today",
            "bg": "Нужен контакт днес",
        },
        "description": "No touch in the last 24h, still active in pipeline",
        "description_i18n": {
            "uk": "Без зв’язку понад 24 години, але лід ще активний",
            "en": "No touch in the last 24h, still active in pipeline",
            "bg": "Без контакт повече от 24 часа, но лийдът е активен",
        },
        "icon": "Phone",
        "color": "#DC2626",
        "query": {"healthStatus": "warning"},   # mapped server-side too
    },
    {
        "id":   "no_contact_7d",
        "name": "No contact > 7d",
        "name_i18n": {
            "uk": "Немає контакту > 7 днів",
            "en": "No contact > 7d",
            "bg": "Без контакт > 7 дни",
        },
        "description": "Stale leads — re-engage or kill",
        "description_i18n": {
            "uk": "Зависли ліди — реактивувати або закрити",
            "en": "Stale leads — re-engage or kill",
            "bg": "Замразени лийдове — реактивирай или затвори",
        },
        "icon": "Clock",
        "color": "#F59E0B",
        "query": {"healthStatus": "stale"},
    },
    {
        "id":   "hot_no_task",
        "name": "Hot + no open task",
        "name_i18n": {
            "uk": "Гарячий + без відкритих задач",
            "en": "Hot + no open task",
            "bg": "Горещ + без отворени задачи",
        },
        "description": "Priority A leads without a planned follow-up",
        "description_i18n": {
            "uk": "Ліди пріоритету A без запланованих дій",
            "en": "Priority A leads without a planned follow-up",
            "bg": "Лийдове с приоритет A без планирана задача",
        },
        "icon": "Fire",
        "color": "#DC2626",
        "query": {"priority": "A", "noOpenTasks": True},
    },
    {
        "id":   "ready_to_convert",
        "name": "Ready to convert",
        "name_i18n": {
            "uk": "Готові до конвертації",
            "en": "Ready to convert",
            "bg": "Готови за конверсия",
        },
        "description": "In decision stage and healthy",
        "description_i18n": {
            "uk": "На етапі рішення і без просадки активності",
            "en": "In decision stage and healthy",
            "bg": "В етап на решение и здрави",
        },
        "icon": "CheckCircle",
        "color": "#16A34A",
        "query": {"status": "decision", "healthStatus": "healthy"},
    },
    {
        "id":   "stuck_negotiation",
        "name": "Stuck in negotiation",
        "name_i18n": {
            "uk": "Зависли на перемовинах",
            "en": "Stuck in negotiation",
            "bg": "Заседнали в преговори",
        },
        "description": "Negotiation > 7d without contact",
        "description_i18n": {
            "uk": "Перемовини більше 7 днів без контакту",
            "en": "Negotiation > 7d without contact",
            "bg": "Преговори > 7 дни без контакт",
        },
        "icon": "Warning",
        "color": "#F59E0B",
        "query": {"status": "negotiation", "healthStatus": "stale"},
    },
    {
        "id":   "no_manager",
        "name": "Unassigned",
        "name_i18n": {
            "uk": "Без менеджера",
            "en": "Unassigned",
            "bg": "Без мениджър",
        },
        "description": "Lead without a manager",
        "description_i18n": {
            "uk": "Лід без призначеного менеджера",
            "en": "Lead without a manager",
            "bg": "Лийд без назначен мениджър",
        },
        "icon": "UserCircle",
        "color": "#71717A",
        "query": {"managerId": "unassigned"},
    },
    {
        "id":   "high_budget_active",
        "name": "Big budget, active",
        "name_i18n": {
            "uk": "Великий бюджет, активний",
            "en": "Big budget, active",
            "bg": "Голям бюджет, активен",
        },
        "description": "Priority A or B with a real budget",
        "description_i18n": {
            "uk": "Пріоритет A або B з реальним бюджетом",
            "en": "Priority A or B with a real budget",
            "bg": "Приоритет A или B с реален бюджет",
        },
        "icon": "CurrencyEur",
        "color": "#16A34A",
        "query": {"priority": "A", "budgetFrom": 30000},
    },
]
