"""Legal profile validation adapter (backend authoritative).

Merges the customer document with an optionally linked company
(``waste_companies``) into a single legal profile and validates the required
requisites for full contract acceptance. Validation NEVER blocks creation or
preview — it only powers the soft-blocking gate at acceptance time.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from . import constants as K

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def build_profile(customer: Dict[str, Any], company: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge customer + company into one legal profile dict.

    Precedence: an explicit ``legal_profile`` sub-doc on the customer wins,
    then top-level customer fields, then company fields. This keeps the adapter
    universal — it works whether requisites live on the customer or the company.
    """
    company = company or {}
    lp = (customer or {}).get("legal_profile") or {}

    def pick(*keys: str) -> str:
        for src in (lp, customer or {}, company):
            for k in keys:
                val = _clean(src.get(k))
                if val:
                    return val
        return ""

    profile = {
        "legal_name": pick("legal_name", "company_name", "name"),
        "edrpou": pick("edrpou", "code", "registration_code"),
        "legal_address": pick("legal_address", "address"),
        "phone": pick("phone", "phone_number"),
        "email": pick("email"),
        "signer_full_name": pick("signer_full_name", "director", "director_name", "contact_name"),
        "signer_position": pick("signer_position", "director_position", "position"),
        # optional
        "iban": pick("iban"),
        "bank_name": pick("bank_name", "bank"),
        "mfo": pick("mfo"),
        "tax_status": pick("tax_status"),
        "vat_number": pick("vat_number", "ipn"),
        "postal_address": pick("postal_address"),
        "authorized_basis": pick("authorized_basis"),
        "power_of_attorney": pick("power_of_attorney"),
        "website": pick("website"),
        "contact_person": pick("contact_person", "contact_name"),
    }
    return profile


def _field_invalid(field: str, value: str) -> bool:
    if not value:
        return False  # emptiness is "missing", not "invalid"
    if field == "email":
        return not bool(_EMAIL_RE.match(value))
    if field == "edrpou":
        digits = re.sub(r"\D", "", value)
        return len(digits) not in (8, 10)
    if field == "phone":
        digits = re.sub(r"\D", "", value)
        return len(digits) < 9
    return False


def validate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return {complete, missing_fields, invalid_fields, completion_percent}."""
    missing: List[str] = []
    invalid: List[str] = []
    filled = 0
    for f in K.REQUIRED_PROFILE_FIELDS:
        val = _clean(profile.get(f))
        if not val:
            missing.append(f)
            continue
        if _field_invalid(f, val):
            invalid.append(f)
            continue
        filled += 1
    total = len(K.REQUIRED_PROFILE_FIELDS)
    percent = int(round((filled / total) * 100)) if total else 100
    complete = (len(missing) == 0 and len(invalid) == 0)
    return {
        "complete": complete,
        "missing_fields": missing,
        "invalid_fields": invalid,
        "completion_percent": percent,
        "labels": {f: K.PROFILE_FIELD_LABELS_UK.get(f, f) for f in K.REQUIRED_PROFILE_FIELDS},
    }


def profile_and_validation(customer: Dict[str, Any], company: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    profile = build_profile(customer, company)
    validation = validate_profile(profile)
    return {"profile": profile, "validation": validation}
