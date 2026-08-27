"""
BIBI Cars — Wave 15 — Contract Lifecycle Management — Pydantic models
========================================================================

Loose-typed by design — every collection is a single ``contracts`` doc
with embedded sub-arrays (``versions``, ``approvals``, ``attachments``,
``events``) for fast bundle reads without extra collections.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ───────────────────────────────────────────────────────────────────────
# Enums (kept as plain string constants so they survive arbitrary input
# from old data without raising 422).
# ───────────────────────────────────────────────────────────────────────
CONTRACT_TYPES = ("purchase", "agency", "transport", "custom")
CONTRACT_STATUSES = (
    "draft",
    "pending_approval",   # awaiting internal sign-off
    "approved",           # all internal approvals collected
    "sent",               # delivered to customer
    "opened",             # customer viewed it
    "signed",             # customer signed → contract is binding
    "active",             # signed AND inside valid_from..valid_to
    "amended",            # superseded by a newer version
    "expired",            # past valid_to without renewal
    "archived",           # terminal
    "rejected",           # rejected during approval
)
APPROVAL_STEPS = ("manager", "admin", "customer")
APPROVAL_STATUS = ("pending", "approved", "rejected", "skipped")
EVENT_KINDS = (
    "created", "updated", "sent", "opened", "approved", "rejected",
    "signed", "amended", "archived", "attachment_added", "attachment_removed",
    "reminder_sent",
)


class ContractParty(BaseModel):
    role:  str = "buyer"            # buyer / seller / agent / carrier
    name:  Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    vat:     Optional[str] = None
    address: Optional[str] = None
    # BG legal contract additions (ЕГН/ЛНЧ for Bulgarian commission contracts)
    national_id: Optional[str] = None      # ЕГН (Bulgarian citizens) or ЛНЧ (foreigners)
    address_full: Optional[str] = None     # Full postal address with street/city/postcode


class VehicleSpec(BaseModel):
    """Параметри на МПС (Приложение №1 to Bulgarian commission contract)."""
    make:          Optional[str]   = None
    model:         Optional[str]   = None
    year:          Optional[int]   = None
    vin:           Optional[str]   = None
    country:       Optional[str]   = None   # САЩ / Южна Корея / друго
    auction:       Optional[str]   = None   # MANHEIM / ENCAR / COPART / IAAI / ...
    max_bid:       Optional[float] = None   # Максимална оферта
    total_budget:  Optional[float] = None   # Общ ориентировъчен бюджет
    currency:      str             = "EUR"


class ContractFinancialTerms(BaseModel):
    """Financial conditions of a Bulgarian commission contract."""
    deposit_pct:           Optional[float] = 15.0           # %
    deposit_min_eur:       Optional[float] = 1000.0         # not-less-than
    executor_fee_eur:      Optional[float] = 800.0          # Възнаграждение на ИЗПЪЛНИТЕЛЯ
    full_prepay_platforms: Optional[List[str]] = None       # ["MANHEIM", "ENCAR"]
    duration_days:         Optional[int]   = 180            # срок на договора
    confidentiality_years: Optional[int]   = 3
    force_majeure_days:    Optional[int]   = 90
    overage_tolerance_pct: Optional[float] = 2.0
    payment_deadline_h:    Optional[int]   = 72


class ContractAttachment(BaseModel):
    id:          str
    filename:    str
    kind:        str = "annex"      # annex / signed_pdf / supporting / photos
    size:        Optional[int] = None
    content_type: Optional[str] = None
    storage_key: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[str] = None


class ContractApproval(BaseModel):
    step:       str                 # manager / team_lead / admin / customer
    status:     str = "pending"     # pending / approved / rejected / skipped
    actor_id:   Optional[str] = None
    actor_name: Optional[str] = None
    comment:    Optional[str] = None
    at:         Optional[str] = None


class ContractEvent(BaseModel):
    kind:       str                 # see EVENT_KINDS
    at:         str
    actor_id:   Optional[str] = None
    actor_name: Optional[str] = None
    note:       Optional[str] = None
    meta:       Optional[Dict[str, Any]] = None


class ContractVersion(BaseModel):
    version:    int
    status:     str
    snapshot:   Dict[str, Any] = Field(default_factory=dict)
    at:         str
    by:         Optional[str] = None
    reason:     Optional[str] = None


class ContractCreate(BaseModel):
    deal_id:      Optional[str] = None
    customer_id:  Optional[str] = None
    template:     str = "purchase"  # one of CONTRACT_TYPES
    type:         Optional[str] = None
    title:        Optional[str] = None
    amount:       Optional[float] = None
    currency:     str = "EUR"
    valid_from:   Optional[str] = None
    valid_to:     Optional[str] = None
    parties:      List[ContractParty] = Field(default_factory=list)
    required_annexes: List[str] = Field(default_factory=list)
    terms:        Optional[Dict[str, Any]] = None
    notes:        Optional[str] = None
    # ─── Bulgarian commission-contract fields (Договор за поръчка) ────
    contract_number: Optional[str] = None              # auto-generated if missing
    place:           Optional[str] = "София"           # place of signing
    language:        Optional[str] = "bg"              # bg / en / uk / ru
    vehicle_spec:    Optional[VehicleSpec] = None
    financial_terms: Optional[ContractFinancialTerms] = None
    client_national_id: Optional[str] = None           # convenience shortcut for ВЪЗЛОЖИТЕЛ ЕГН/ЛНЧ
    client_address:     Optional[str] = None           # convenience shortcut for ВЪЗЛОЖИТЕЛ адрес


class ContractPatch(BaseModel):
    title:        Optional[str] = None
    amount:       Optional[float] = None
    currency:     Optional[str] = None
    valid_from:   Optional[str] = None
    valid_to:     Optional[str] = None
    parties:      Optional[List[ContractParty]] = None
    required_annexes: Optional[List[str]] = None
    terms:        Optional[Dict[str, Any]] = None
    notes:        Optional[str] = None


class ApprovalAction(BaseModel):
    step:    Optional[str] = None   # auto-detected if not provided
    comment: Optional[str] = None


class SignAction(BaseModel):
    signer_name:  Optional[str] = None
    signer_email: Optional[str] = None
    signed_at:    Optional[str] = None  # ISO; defaults to now
    method:       str = "electronic"    # electronic / wet_ink / docusign
    ip:           Optional[str] = None


class AmendAction(BaseModel):
    reason: Optional[str] = None
    terms:  Optional[Dict[str, Any]] = None


__all__ = [
    "CONTRACT_TYPES", "CONTRACT_STATUSES", "APPROVAL_STEPS", "APPROVAL_STATUS", "EVENT_KINDS",
    "ContractParty", "ContractAttachment", "ContractApproval", "ContractEvent", "ContractVersion",
    "ContractCreate", "ContractPatch", "ApprovalAction", "SignAction", "AmendAction",
    "VehicleSpec", "ContractFinancialTerms",
]
