"""
Lead SLA — Block 6.2 thresholds and event names.
==================================================

Default thresholds:
  * 30 min after lead creation without first response → reminder to manager
  * 2  h  after lead creation without first response → escalation to team lead
                                                       (+ optional auto-reassign)

These defaults can be overridden via the existing ``settings`` collection
with the keys:

    sla_first_response_minutes      (default 30)
    sla_escalate_minutes            (default 120)
    sla_auto_reassign_to_tl         (default False — only notify, no auto-reassign)

The thresholds are intentionally **minutes**, not hours, because the first
response window in this business is short (the entire CRM revolves around
fast call-backs).
"""
from __future__ import annotations

# Default thresholds (minutes)
DEFAULT_REMIND_MINUTES: int = 30
DEFAULT_ESCALATE_MINUTES: int = 120

# Hard ceilings to avoid pathological config (e.g. 0 → infinite spam)
MIN_THRESHOLD_MINUTES: int = 1
MAX_THRESHOLD_MINUTES: int = 60 * 24 * 7   # 7 days

# Settings keys
SETTING_REMIND_KEY: str = "sla_first_response_minutes"
SETTING_ESCALATE_KEY: str = "sla_escalate_minutes"
SETTING_AUTO_REASSIGN_KEY: str = "sla_auto_reassign_to_tl"

# Notification event names
EVENT_LEAD_SLA_WARNING: str = "lead_sla_warning"
EVENT_LEAD_SLA_ESCALATED: str = "lead_sla_escalated"

# State enum
SLA_STATE_GREEN: str = "green"        # well within threshold
SLA_STATE_AMBER: str = "amber"        # >50% of remind threshold consumed
SLA_STATE_OVERDUE: str = "overdue"    # past remind threshold, < escalate
SLA_STATE_ESCALATED: str = "escalated"  # past escalate threshold
SLA_STATE_OK: str = "responded"       # manager has responded — SLA closed
SLA_STATE_NA: str = "na"              # no managerId yet, or lead is in terminal status

__all__ = [
    "DEFAULT_REMIND_MINUTES", "DEFAULT_ESCALATE_MINUTES",
    "MIN_THRESHOLD_MINUTES", "MAX_THRESHOLD_MINUTES",
    "SETTING_REMIND_KEY", "SETTING_ESCALATE_KEY", "SETTING_AUTO_REASSIGN_KEY",
    "EVENT_LEAD_SLA_WARNING", "EVENT_LEAD_SLA_ESCALATED",
    "SLA_STATE_GREEN", "SLA_STATE_AMBER", "SLA_STATE_OVERDUE",
    "SLA_STATE_ESCALATED", "SLA_STATE_OK", "SLA_STATE_NA",
]
