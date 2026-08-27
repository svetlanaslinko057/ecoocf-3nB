"""
BIBI Cars — Wave 15 — Contract templates (4 defaults).

These are *seed* defaults that the create endpoint applies when a user
picks a template. They are not stored in MongoDB — they live in code so
they survive deploys and can be promoted to an editable surface later.
"""
from __future__ import annotations
from typing import Any, Dict, List

TEMPLATES: Dict[str, Dict[str, Any]] = {
    # ─────────────── PURCHASE ───────────────
    "purchase": {
        "key":   "purchase",
        "name":  "Purchase Contract",
        "type":  "purchase",
        "description": "Vehicle purchase agreement between BIBI Cars and the end customer.",
        "approval_chain": ["manager", "admin", "customer"],
        "required_annexes": ["vehicle_specification", "price_breakdown", "customs_disclosure"],
        "required_parties": ["buyer", "seller"],
        "valid_days":     30,
        "signature_required": True,
        "terms": {
            "jurisdiction": "EU",
            "language":     "en",
            "payment_schedule": "deposit_then_full",
            "warranty_days": 0,
        },
    },
    # ─────────────── AGENCY ───────────────
    "agency": {
        "key":   "agency",
        "name":  "Agency / Brokerage Contract",
        "type":  "agency",
        "description": "BIBI Cars acts as agent on behalf of customer to source / bid / win the vehicle at auction.",
        "approval_chain": ["manager", "admin", "customer"],
        "required_annexes": ["power_of_attorney", "fee_schedule"],
        "required_parties": ["agent", "buyer"],
        "valid_days":     60,
        "signature_required": True,
        "terms": {
            "jurisdiction": "EU",
            "language":     "en",
            "agency_fee_pct": 5.0,
            "refund_policy":  "non_refundable",
        },
    },
    # ─────────────── TRANSPORT ───────────────
    "transport": {
        "key":   "transport",
        "name":  "Transport / Carriage Contract",
        "type":  "transport",
        "description": "Carrier-side transport agreement covering pickup, ocean, customs, last-mile delivery.",
        "approval_chain": ["manager", "admin"],
        "required_annexes": ["cmr", "insurance_certificate", "vehicle_condition_report"],
        "required_parties": ["agent", "carrier"],
        "valid_days":     45,
        "signature_required": True,
        "terms": {
            "jurisdiction":   "EU",
            "language":       "en",
            "incoterms":      "DAP",
            "insurance_coverage_pct": 110.0,
        },
    },
    # ─────────────── CUSTOM ───────────────
    "custom": {
        "key":   "custom",
        "name":  "Custom Contract",
        "type":  "custom",
        "description": "Free-form contract for one-off agreements (NDAs, dealer side-letters, etc.).",
        "approval_chain": ["manager", "admin"],
        "required_annexes": [],
        "required_parties": ["buyer"],
        "valid_days":     90,
        "signature_required": True,
        "terms": {
            "jurisdiction": "EU",
            "language":     "en",
        },
    },
}


def get_template(key: str) -> Dict[str, Any]:
    """Return a defensive copy of the template so callers can mutate freely."""
    import copy
    tpl = TEMPLATES.get((key or "custom").lower()) or TEMPLATES["custom"]
    return copy.deepcopy(tpl)


def list_templates() -> List[Dict[str, Any]]:
    """Return every template as a list (public surface for the UI picker)."""
    import copy
    return [copy.deepcopy(t) for t in TEMPLATES.values()]


__all__ = ["TEMPLATES", "get_template", "list_templates"]
