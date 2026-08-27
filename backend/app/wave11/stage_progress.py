"""
Wave 11 — Deal Stage Progress.

Maps the canonical 10-stage Wave 6 pipeline to a linear 0..100 progress bar
and exposes a small "what's next" hint so the operations sidebar always has
something actionable for the manager.

Returned shape:
    {
        "current_stage":   "deposit_paid",
        "current_index":   3,
        "total_stages":    9,            # we drop `cancelled` from the bar
        "percent":         33,           # 0..100
        "next_stage":      "bidding",
        "next_label":      "Bidding",
        "is_terminal":     False,        # True for delivered / cancelled
        "is_cancelled":    False,
        "blockers":        ["Deposit not confirmed"],
        "advice":          "Confirm deposit to unlock auction bidding",
    }

Pure function. No DB calls. Safe to call from anywhere.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.wave6.pipeline import (
    PIPELINE_STAGES,
    PIPELINE_STAGE_LABELS,
    derive_pipeline_stage,
)
from app.wave6.health import compute_health


# Order used by the progress bar. `cancelled` is its own terminal track and
# does not appear on the linear bar.
_LINEAR_STAGES: List[str] = [s for s in PIPELINE_STAGES if s != "cancelled"]


def _label(stage: str, lang: str = "en") -> str:
    info = PIPELINE_STAGE_LABELS.get(stage) or {}
    return info.get(lang) or info.get("en") or stage


def _blockers_for_stage(stage: str, deal: Dict[str, Any]) -> List[str]:
    """Heuristic blockers list — purely advisory for the sidebar hint."""
    blockers: List[str] = []
    if stage in ("awaiting_deposit", "bidding", "won", "contract_signed", "shipping") \
            and not deal.get("deposit_paid_at"):
        # Confirm via stage history too (wave6.health does this same trick)
        had_deposit = any(
            (h or {}).get("to") == "deposit_paid"
            for h in (deal.get("stage_history") or [])
        )
        if not had_deposit:
            blockers.append("Deposit not confirmed")
    if stage in ("contract_signed", "shipping") and not (
        deal.get("contract_signed_at") or deal.get("final_contract_signed_at")
    ):
        blockers.append("Final contract not signed")
    if stage == "shipping" and not deal.get("vin"):
        blockers.append("VIN not assigned")
    return blockers


def _advice_for(stage: str) -> str:
    return {
        "inquiry":          "Qualify need and budget, then move to negotiating",
        "negotiating":      "Send VIN options and request deposit",
        "awaiting_deposit": "Chase deposit payment from the customer",
        "deposit_paid":     "Pick the auction lot and prepare a bid",
        "bidding":          "Win the auction or rebid",
        "won":              "Send the final contract for signing",
        "contract_signed":  "Trigger shipping and confirm logistics",
        "shipping":         "Track the shipment to delivery",
        "delivered":        "Close the deal and request a review",
        "cancelled":        "Deal cancelled — archive or reopen",
    }.get(stage, "")


def compute_stage_progress(deal: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the linear progress bundle for one deal. Never raises."""
    if not deal:
        return {
            "current_stage":  "inquiry",
            "current_index":  0,
            "total_stages":   len(_LINEAR_STAGES),
            "percent":        0,
            "next_stage":     _LINEAR_STAGES[1] if len(_LINEAR_STAGES) > 1 else None,
            "next_label":     _label(_LINEAR_STAGES[1]) if len(_LINEAR_STAGES) > 1 else None,
            "is_terminal":    False,
            "is_cancelled":   False,
            "blockers":       [],
            "advice":         _advice_for("inquiry"),
            "stages":         [
                {"id": s, "label": _label(s), "passed": False, "current": s == "inquiry"}
                for s in _LINEAR_STAGES
            ],
        }

    stage = derive_pipeline_stage(deal)
    is_cancelled = stage == "cancelled"

    if is_cancelled:
        return {
            "current_stage":  "cancelled",
            "current_index":  -1,
            "total_stages":   len(_LINEAR_STAGES),
            "percent":        0,
            "next_stage":     None,
            "next_label":     None,
            "is_terminal":    True,
            "is_cancelled":   True,
            "blockers":       [],
            "advice":         _advice_for("cancelled"),
            "stages":         [
                {"id": s, "label": _label(s), "passed": False, "current": False}
                for s in _LINEAR_STAGES
            ],
        }

    try:
        idx = _LINEAR_STAGES.index(stage)
    except ValueError:
        idx = 0

    is_terminal = stage == "delivered"
    total = len(_LINEAR_STAGES)
    # Progress reaches 100 only on delivered (terminal positive). Each stage
    # earns roughly 1/(total-1) of the bar — gives a calm linear advance.
    if is_terminal:
        percent = 100
    else:
        percent = int(round((idx / max(1, total - 1)) * 100))

    next_stage = _LINEAR_STAGES[idx + 1] if (idx + 1) < total else None
    next_label = _label(next_stage) if next_stage else None

    return {
        "current_stage":  stage,
        "current_index":  idx,
        "total_stages":   total,
        "percent":        percent,
        "next_stage":     next_stage,
        "next_label":     next_label,
        "is_terminal":    is_terminal,
        "is_cancelled":   False,
        "blockers":       _blockers_for_stage(stage, deal),
        "advice":         _advice_for(stage),
        "stages":         [
            {
                "id":      s,
                "label":   _label(s),
                "passed":  i < idx,
                "current": i == idx,
            }
            for i, s in enumerate(_LINEAR_STAGES)
        ],
    }


def deal_health_bundle(deal: Dict[str, Any]) -> Dict[str, Any]:
    """Return the deal-health dict in the same shape Wave 6 router returns it."""
    return compute_health(deal).to_dict()
