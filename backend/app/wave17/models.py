"""
BIBI Cars — Wave 17 — Action Center — Pydantic models
========================================================
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Sources — which 360 raised this action.
ACTION_SOURCES = (
    "operations", "finance", "contract", "delivery", "forecast", "manual",
)
# Action types — short, machine-friendly verbs.
ACTION_TYPES = (
    "chase_deposit", "chase_payment", "assign_carrier",
    "escalate_customs", "escalate_port", "upload_documents",
    "chase_signature", "approve_internally", "upload_annex",
    "replace_contract_version", "renew_or_archive",
    "push_carrier", "operations_escalation",
    "forecast_review", "capacity_rebalance",
    "reactivate_lead", "collection_workflow",
    "manual",
)
ACTION_PRIORITIES = ("critical", "high", "medium", "low")
ACTION_STATUSES = ("open", "in_progress", "snoozed", "resolved", "cancelled")
ESCALATION_STEPS = ("none", "admin")


class ActionEvent(BaseModel):
    kind:       str                  # created / assigned / started / resolved / snoozed / escalated / reopened / commented
    at:         str
    actor_id:   Optional[str] = None
    actor_name: Optional[str] = None
    note:       Optional[str] = None
    meta:       Optional[Dict[str, Any]] = None


class ActionCreate(BaseModel):
    source:        str = "manual"        # one of ACTION_SOURCES
    type:          str = "manual"        # one of ACTION_TYPES
    title:         str
    description:   Optional[str] = None
    priority:      str = "medium"        # one of ACTION_PRIORITIES
    owner_id:      Optional[str] = None
    owner_name:    Optional[str] = None
    entity_type:   Optional[str] = None  # deal / contract / shipment / lead / customer
    entity_id:     Optional[str] = None
    impact:        Optional[float] = None
    currency:      str = "UAH"
    due_at:        Optional[str] = None  # ISO; +X days if missing
    deal_id:       Optional[str] = None
    href:          Optional[str] = None
    tags:          List[str] = Field(default_factory=list)
    meta:          Optional[Dict[str, Any]] = None


class ActionPatch(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    priority:     Optional[str] = None
    due_at:       Optional[str] = None
    impact:       Optional[float] = None
    tags:         Optional[List[str]] = None
    meta:         Optional[Dict[str, Any]] = None


class AssignAction(BaseModel):
    owner_id:    str
    owner_name:  Optional[str] = None
    comment:     Optional[str] = None


class ResolveAction(BaseModel):
    comment:     Optional[str] = None
    outcome:     str = "resolved"   # resolved / wont_do / duplicate / superseded


class SnoozeAction(BaseModel):
    snooze_until: str                 # ISO
    comment:      Optional[str] = None


class EscalateAction(BaseModel):
    to_step:     str = "admin"    # admin
    new_owner_id:   Optional[str] = None
    new_owner_name: Optional[str] = None
    comment:     Optional[str] = None


class CommentAction(BaseModel):
    comment: str


__all__ = [
    "ACTION_SOURCES", "ACTION_TYPES", "ACTION_PRIORITIES",
    "ACTION_STATUSES", "ESCALATION_STEPS",
    "ActionEvent", "ActionCreate", "ActionPatch",
    "AssignAction", "ResolveAction", "SnoozeAction",
    "EscalateAction", "CommentAction",
]
