"""
Contact-field validation helpers (phone + email).

Used by the public inquiry/callback endpoint and the client registration flow
so that garbage input ("asdf", "12", "not-an-email") is rejected with a clear,
localized message instead of silently entering the CRM queue.

Phone:  Ukraine-first but accepts any valid international number (E.164).
        A bare national UA number (e.g. "0501234567" or "067 123 45 67") is
        interpreted with the UA region; numbers starting with "+" are parsed as
        international.
Email:  RFC-ish validation via the `email-validator` package (already a dep),
        with deliverability checks disabled (no DNS in preview).
"""
from __future__ import annotations

from typing import Tuple

import phonenumbers
from phonenumbers import NumberParseException

try:  # email-validator is in requirements.txt
    from email_validator import validate_email as _ev_validate, EmailNotValidError
except Exception:  # pragma: no cover - defensive
    _ev_validate = None
    EmailNotValidError = Exception  # type: ignore


def normalize_phone(raw: str, default_region: str = "UA") -> Tuple[bool, str, str]:
    """Validate and normalize a phone number.

    Returns ``(ok, e164_or_input, error_message)``.
    - ok=True  → e164 holds the normalized "+380..." form.
    - ok=False → error_message holds a localized reason.
    """
    raw = (raw or "").strip()
    if not raw:
        return False, raw, "Вкажіть номер телефону"
    # Keep only sensible phone characters before parsing.
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch in "+()-. ")
    region = None if cleaned.startswith("+") else default_region
    try:
        num = phonenumbers.parse(cleaned, region)
    except NumberParseException:
        return False, raw, "Некоректний номер телефону"
    if not phonenumbers.is_possible_number(num):
        return False, raw, "Номер телефону закороткий або задовгий"
    if not phonenumbers.is_valid_number(num):
        return False, raw, "Номер телефону не існує. Перевірте код оператора/країни"
    e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    return True, e164, ""


def validate_email_addr(raw: str, required: bool = False) -> Tuple[bool, str, str]:
    """Validate an email address.

    Returns ``(ok, normalized_or_input, error_message)``.
    Empty input is allowed when ``required`` is False.
    """
    raw = (raw or "").strip()
    if not raw:
        if required:
            return False, raw, "Вкажіть email"
        return True, "", ""
    if _ev_validate is not None:
        try:
            res = _ev_validate(raw, check_deliverability=False)
            return True, res.normalized.lower(), ""
        except EmailNotValidError:
            return False, raw, "Некоректний email"
    # Fallback (should not happen) — minimal sanity check.
    if "@" in raw and "." in raw.split("@")[-1]:
        return True, raw.lower(), ""
    return False, raw, "Некоректний email"
