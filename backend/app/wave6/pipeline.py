"""
Wave 6 — Simplified 10-stage operational pipeline.

We never destroy the legacy 20-stage truth. Instead we maintain a parallel,
UI-facing `pipeline_stage` field that maps any legacy stage into one of ten
canonical operational states managers, team-leads and admins understand the
same way.

Mapping decisions (locked-in for Wave 6):

    Legacy stage(s)                                            → pipeline_stage
    ─────────────────────────────────────────────────────────────────────────
    lead                                                       → inquiry
    qualified, variants_sent                                   → negotiating
    deposit_contract_drafted, deposit_contract_signed          → awaiting_deposit
    deposit_paid                                               → deposit_paid
    searching_at_auction, auction_lost                         → bidding
    auction_won                                                → won
    final_contract_sent, final_contract_signed,
      after_win_payment_paid                                   → contract_signed
    in_transit_to_rotterdam, arrived_rotterdam,
      customs_calculated, final_payment_paid, in_transit_to_bg → shipping
    delivered, closed                                          → delivered
    cancelled                                                  → cancelled

Also supports the legacy short-form statuses found on older `deals` documents
(`new`, `negotiation`, `waiting_deposit`, `purchased`, `in_delivery`,
`completed`) so the workspace never crashes on historical data.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# ─── 10-stage canonical pipeline ───────────────────────────────────────────
PIPELINE_STAGES: List[str] = [
    "inquiry",
    "negotiating",
    "awaiting_deposit",
    "deposit_paid",
    "bidding",
    "won",
    "contract_signed",
    "shipping",
    "delivered",
    "cancelled",
]

PIPELINE_STAGE_LABELS: Dict[str, Dict[str, str]] = {
    "inquiry":          {"en": "Inquiry",          "bg": "Запитване",        "uk": "Запит"},
    "negotiating":      {"en": "Negotiating",      "bg": "Преговори",         "uk": "Переговори"},
    "awaiting_deposit": {"en": "Awaiting Deposit", "bg": "В очакване",         "uk": "Очікує депозит"},
    "deposit_paid":     {"en": "Deposit Paid",     "bg": "Депозит платен",    "uk": "Депозит сплачено"},
    "bidding":          {"en": "Bidding",          "bg": "Наддаване",         "uk": "Торги"},
    "won":              {"en": "Won",              "bg": "Спечелено",         "uk": "Виграно"},
    "contract_signed":  {"en": "Contract Signed",  "bg": "Договор подписан",  "uk": "Контракт підписано"},
    "shipping":         {"en": "Shipping",         "bg": "Доставка",         "uk": "Доставка"},
    "delivered":        {"en": "Delivered",        "bg": "Доставено",         "uk": "Доставлено"},
    "cancelled":        {"en": "Cancelled",        "bg": "Отказано",          "uk": "Скасовано"},
}

# Legacy 20-stage map (from legal_workflow.py)
LEGACY_TO_PIPELINE: Dict[str, str] = {
    "lead":                       "inquiry",
    "qualified":                  "negotiating",
    "variants_sent":              "negotiating",
    "deposit_contract_drafted":   "awaiting_deposit",
    "deposit_contract_signed":    "awaiting_deposit",
    "deposit_paid":               "deposit_paid",
    "searching_at_auction":       "bidding",
    "auction_lost":               "bidding",
    "auction_won":                "won",
    "final_contract_sent":        "contract_signed",
    "final_contract_signed":      "contract_signed",
    "after_win_payment_paid":     "contract_signed",
    "in_transit_to_rotterdam":    "shipping",
    "arrived_rotterdam":          "shipping",
    "customs_calculated":         "shipping",
    "final_payment_paid":         "shipping",
    "in_transit_to_bg":           "shipping",
    "delivered":                  "delivered",
    "closed":                     "delivered",
    "cancelled":                  "cancelled",
}

# Old short-form statuses also seen on legacy `deals` documents (see Deals.js).
_SHORT_FORM_TO_PIPELINE: Dict[str, str] = {
    "new":               "inquiry",
    "negotiation":       "negotiating",
    "waiting_deposit":   "awaiting_deposit",
    "deposit_paid":      "deposit_paid",
    "purchased":         "won",
    "in_delivery":       "shipping",
    "completed":         "delivered",
    "cancelled":         "cancelled",
}


def map_legacy_to_pipeline(stage: Optional[str]) -> str:
    """Map any legacy stage / status to a canonical pipeline_stage.

    Unknown values default to ``inquiry`` (safest operational fallback).
    Never raises.
    """
    if not stage:
        return "inquiry"
    s = str(stage).strip().lower()
    if s in LEGACY_TO_PIPELINE:
        return LEGACY_TO_PIPELINE[s]
    if s in _SHORT_FORM_TO_PIPELINE:
        return _SHORT_FORM_TO_PIPELINE[s]
    if s in PIPELINE_STAGES:
        return s
    return "inquiry"


def derive_pipeline_stage(deal: Dict) -> str:
    """Pick the best canonical pipeline_stage for a given deal document.

    Priority: explicit `pipeline_stage` field → `stage` → `status` → default.
    """
    if not deal:
        return "inquiry"
    explicit = deal.get("pipeline_stage")
    if explicit and explicit in PIPELINE_STAGES:
        return explicit
    return map_legacy_to_pipeline(
        deal.get("stage") or deal.get("status")
    )


def pipeline_stage_label(stage: str, lang: str = "en") -> str:
    info = PIPELINE_STAGE_LABELS.get(stage)
    if not info:
        return stage
    return info.get(lang) or info.get("en") or stage
