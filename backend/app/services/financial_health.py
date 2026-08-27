"""
BIBI Cars — Wave 12B — Financial Health Engine
==============================================

Single source of truth for the **financial** health of one deal. This is
intentionally separate from Wave 6 `compute_health` which scores the
*operational* health (stage age, blockers, owner). The two can disagree:

    Deal Health        🟢 Healthy
    Financial Health   🔴 Critical

…means the operation is moving but the money is not following. That's
exactly the case TL and owner need to spot fast.

Input:
    * deal       — the deal document
    * deposits   — list of `legal_deposits` rows for this deal
    * payments   — list of `payments` rows for this deal

Output:
    {
        "score":   0..100,
        "segment": "healthy" | "warning" | "at_risk" | "critical",
        "reasons": ["Outstanding balance > 25%", "Deposit confirmed", ...],
        "metrics": {
            "expected":          50000,
            "received":          12000,
            "outstanding":       38000,
            "outstanding_ratio": 0.76,
            "days_since_move":   12,
            "open_refunds":      0,
            "rejected_deposits": 0,
        }
    }

Segment cutoffs (cumulative score):
    score >= 80  → healthy
    score >= 60  → warning
    score >= 40  → at_risk
    score <  40  → critical

Cancelled deals get segment="cancelled" and never count as critical.
Delivered deals with balance≤0 are always healthy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


_TERMINAL_NEG = {"cancelled", "lost", "closed_lost"}
_TERMINAL_POS = {"delivered", "completed", "closed"}


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _deal_revenue(deal: Dict[str, Any]) -> float:
    return _num(deal.get("total_price")
                or deal.get("totalValue")
                or deal.get("clientPrice"))


def _stage(deal: Dict[str, Any]) -> str:
    return (deal.get("pipeline_stage") or deal.get("stage") or deal.get("status") or "").lower()


def _days_since(iso: Any) -> int:
    if not iso:
        return 0
    try:
        s = iso.rstrip("Z") if isinstance(iso, str) else None
        dt = datetime.fromisoformat(s) if s else None
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if not dt:
            return 0
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        return 0


def _sum_by_status(rows: List[Dict[str, Any]], statuses: set) -> float:
    total = 0.0
    for r in rows or []:
        s = (r.get("status") or "").lower()
        if s in statuses:
            total += _num(r.get("amount"))
    return total


def _count_by_status(rows: List[Dict[str, Any]], statuses: set) -> int:
    return sum(1 for r in (rows or []) if (r.get("status") or "").lower() in statuses)


def compute_financial_health(
    deal: Dict[str, Any],
    deposits: List[Dict[str, Any]],
    payments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Pure scorer — no DB calls. Always returns a dict, never raises."""
    stage = _stage(deal)
    expected = _deal_revenue(deal)

    deposit_received = _sum_by_status(deposits, {"confirmed", "paid", "received"})
    payment_received = _sum_by_status(payments, {"confirmed", "paid", "received"})
    received = deposit_received + payment_received

    outstanding = max(0.0, expected - received)
    outstanding_ratio = (outstanding / expected) if expected else 0.0

    rejected_deposits = _count_by_status(deposits, {"rejected", "failed"})
    refund_paid       = _count_by_status(deposits, {"refunded"}) + _count_by_status(payments, {"refunded"})
    failed_payments   = _count_by_status(payments, {"failed"})
    open_refunds      = _count_by_status(payments, {"refund_pending"})

    last_move = deal.get("updated_at") or deal.get("created_at")
    days_since_move = _days_since(last_move)

    # ── Terminal short-circuits ───────────────────────────────────────
    if stage in _TERMINAL_NEG:
        return {
            "score": 0,
            "segment": "cancelled",
            "reasons": ["Deal cancelled"],
            "metrics": {
                "expected": round(expected, 2),
                "received": round(received, 2),
                "outstanding": round(outstanding, 2),
                "outstanding_ratio": round(outstanding_ratio, 4),
                "days_since_move": days_since_move,
                "open_refunds": open_refunds,
                "rejected_deposits": rejected_deposits,
            },
        }
    if stage in _TERMINAL_POS and outstanding <= 0:
        return {
            "score": 100,
            "segment": "healthy",
            "reasons": ["Deal delivered, fully paid"],
            "metrics": {
                "expected": round(expected, 2),
                "received": round(received, 2),
                "outstanding": 0.0,
                "outstanding_ratio": 0.0,
                "days_since_move": days_since_move,
                "open_refunds": open_refunds,
                "rejected_deposits": rejected_deposits,
            },
        }

    score = 100.0
    reasons: List[str] = []

    # ── Outstanding balance penalty (the strongest signal) ────────────
    if expected > 0:
        if outstanding_ratio >= 0.9:
            score -= 35
            reasons.append("Almost nothing collected yet")
        elif outstanding_ratio >= 0.5:
            score -= 20
            reasons.append("Outstanding balance > 50%")
        elif outstanding_ratio >= 0.25:
            score -= 10
            reasons.append("Outstanding balance > 25%")

    # ── Stage-age penalty (cash sitting still) ────────────────────────
    if stage not in _TERMINAL_POS:
        if days_since_move >= 30:
            score -= 25
            reasons.append(f"No movement in {days_since_move}d")
        elif days_since_move >= 14:
            score -= 15
            reasons.append(f"No movement in {days_since_move}d")
        elif days_since_move >= 7:
            score -= 5
            reasons.append(f"Quiet for {days_since_move}d")

    # ── Refund / failure penalties ────────────────────────────────────
    if open_refunds:
        score -= 15
        reasons.append(f"{open_refunds} refund request(s) pending")
    if rejected_deposits:
        score -= 15
        reasons.append(f"{rejected_deposits} deposit(s) rejected")
    if failed_payments:
        score -= 10
        reasons.append(f"{failed_payments} payment(s) failed")
    # Already-paid refunds are not penalised heavily (water under the bridge)
    if refund_paid:
        score -= 5
        reasons.append(f"{refund_paid} refund(s) paid")

    # ── Positive signals ──────────────────────────────────────────────
    if deposit_received > 0:
        reasons.append("Deposit confirmed")
        # Deposit being in the door is good — small bonus to keep the
        # score above zero even with high outstanding ratio.
        score += 5

    # Clamp
    score = max(0.0, min(100.0, score))
    score_int = int(round(score))

    if score_int >= 80:
        segment = "healthy"
    elif score_int >= 60:
        segment = "warning"
    elif score_int >= 40:
        segment = "at_risk"
    else:
        segment = "critical"

    return {
        "score":   score_int,
        "segment": segment,
        "reasons": reasons[:5],
        "metrics": {
            "expected":          round(expected, 2),
            "received":          round(received, 2),
            "outstanding":       round(outstanding, 2),
            "outstanding_ratio": round(outstanding_ratio, 4),
            "days_since_move":   days_since_move,
            "open_refunds":      open_refunds,
            "rejected_deposits": rejected_deposits,
        },
    }


def segment_for_score(score: int) -> str:
    if score >= 80: return "healthy"
    if score >= 60: return "warning"
    if score >= 40: return "at_risk"
    return "critical"


SEGMENTS = ("healthy", "warning", "at_risk", "critical")
