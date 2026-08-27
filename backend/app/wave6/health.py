"""
Wave 6 — Deal Health badge (computed, never stored).

Simple, predictable rules. No ML, no AI scoring, no risk engines. Anything
fancier than this can be added later — after we've actually seen managers use
the operating system.

Rule order (first matching wins):
  1. cancelled→ cancelled  (terminal)
  2. delivered → healthy   (terminal, positive)
  3. risk     → explicit risk flags on the deal (manual or set by other hooks)
  4. overdue  → no `updated_at` for > OVERDUE_DAYS
  5. blocked  → stage requires deposit but deposit_paid is missing
  6. waiting_customer → awaiting_deposit > WAITING_DAYS
  7. healthy  → default

Returns a small dataclass with badge + reason + i18n key.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from .pipeline import derive_pipeline_stage

OVERDUE_DAYS = 14
WAITING_DAYS = 7
BLOCKING_STAGES_REQUIRE_DEPOSIT = {"bidding", "won", "contract_signed", "shipping"}

HEALTH_STATES = (
    "healthy",
    "waiting_customer",
    "blocked",
    "overdue",
    "risk",
    "cancelled",
)


@dataclass
class DealHealth:
    state: str           # one of HEALTH_STATES
    reason: str          # short, human-readable
    i18n_key: str        # frontend can localise without re-deriving
    pipeline_stage: str  # convenience copy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "i18n_key": self.i18n_key,
            "pipeline_stage": self.pipeline_stage,
        }


def _parse_iso(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            # tolerant of trailing Z
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _days_since(v: Any) -> Optional[float]:
    dt = _parse_iso(v)
    if not dt:
        return None
    delta = datetime.now(timezone.utc) - dt
    return delta.total_seconds() / 86400.0


def compute_health(deal: Dict[str, Any]) -> DealHealth:
    """Compute deal health badge. Always returns a DealHealth (never raises)."""
    if not deal:
        return DealHealth(
            state="risk",
            reason="Deal not found",
            i18n_key="health.missing",
            pipeline_stage="inquiry",
        )

    pipeline_stage = derive_pipeline_stage(deal)

    # 1. cancelled
    if pipeline_stage == "cancelled":
        return DealHealth("cancelled", "Deal cancelled", "health.cancelled", pipeline_stage)

    # 2. terminal positive
    if pipeline_stage == "delivered":
        return DealHealth("healthy", "Delivered successfully", "health.delivered", pipeline_stage)

    # 3. explicit risk flag (any other code path may set this)
    if deal.get("risk_flag") or deal.get("is_at_risk"):
        reason = deal.get("risk_reason") or "Risk flag set"
        return DealHealth("risk", reason, "health.risk", pipeline_stage)

    # 4. overdue (no activity)
    days_idle = _days_since(deal.get("updated_at") or deal.get("created_at"))
    if days_idle is not None and days_idle > OVERDUE_DAYS:
        return DealHealth(
            "overdue",
            f"No activity for {int(days_idle)} days",
            "health.overdue",
            pipeline_stage,
        )

    # 5. blocked (required deposit missing)
    if pipeline_stage in BLOCKING_STAGES_REQUIRE_DEPOSIT and not deal.get("deposit_paid_at"):
        # We accept either the explicit `deposit_paid_at` field OR a stage
        # >= deposit_paid; for legacy deals we infer from stage history.
        had_deposit = False
        for h in (deal.get("stage_history") or []):
            if (h or {}).get("to") == "deposit_paid":
                had_deposit = True
                break
        if not had_deposit:
            return DealHealth(
                "blocked",
                "Deposit not confirmed yet",
                "health.blocked_deposit",
                pipeline_stage,
            )

    # 6. waiting customer (stuck in awaiting_deposit)
    if pipeline_stage == "awaiting_deposit":
        days_wait = _days_since(deal.get("updated_at") or deal.get("created_at"))
        if days_wait is not None and days_wait > WAITING_DAYS:
            return DealHealth(
                "waiting_customer",
                f"Awaiting deposit for {int(days_wait)} days",
                "health.waiting_customer",
                pipeline_stage,
            )

    # 7. healthy default
    return DealHealth("healthy", "On track", "health.healthy", pipeline_stage)
