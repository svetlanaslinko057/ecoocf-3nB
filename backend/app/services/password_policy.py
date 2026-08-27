"""
password_policy — единая политика паролей для staff (admin/team_lead/manager).
==============================================================================

Правила (зафиксированы 2026-05-25 по требованию stakeholder'а):
  - длина ≥ 8 символов
  - минимум 1 строчная буква  [a-z]
  - минимум 1 заглавная буква  [A-Z]
  - минимум 1 цифра            [0-9]
  - минимум 1 спец-символ из набора  ! @ # $ % ^ & * ( ) _ + - = [ ] { } ; : , . ? / \\ | < > ~ '
    (включая дефис «-», как просил пользователь)
  - запрещены пробелы, табы, перенос строки

Сервис чистый: НЕ знает про HTTP, про MongoDB, про auth — только правила.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

# ---- constants --------------------------------------------------------------

MIN_LENGTH = 8
SPECIALS = "!@#$%^&*()_+-=[]{};:,.?/\\|<>~'\""
SPECIALS_SET = set(SPECIALS)

_RE_HAS_SPACE = re.compile(r"\s")
_RE_LOWER = re.compile(r"[a-z]")
_RE_UPPER = re.compile(r"[A-Z]")
_RE_DIGIT = re.compile(r"[0-9]")


# ---- public api -------------------------------------------------------------

@dataclass
class PolicyCheck:
    ok: bool
    failures: List[str]
    checks: Dict[str, bool]


def policy_descriptor() -> Dict[str, object]:
    """Public-facing JSON snapshot of the rules — used by the FE live meter."""
    return {
        "min_length": MIN_LENGTH,
        "must_have_lower": True,
        "must_have_upper": True,
        "must_have_digit": True,
        "must_have_special": True,
        "specials_allowed": SPECIALS,
        "forbid_whitespace": True,
        "rules": [
            f"At least {MIN_LENGTH} characters",
            "At least one lowercase letter (a-z)",
            "At least one uppercase letter (A-Z)",
            "At least one digit (0-9)",
            "At least one special character (e.g. ! @ # $ % - _ + …)",
            "No spaces or tabs",
        ],
    }


def check_password(pwd: str) -> PolicyCheck:
    """Validate a candidate password against the staff policy.

    Returns a :class:`PolicyCheck` with per-rule booleans so the API
    can return a structured response and the FE can render granular UI.
    """
    pwd = pwd or ""
    checks: Dict[str, bool] = {
        "length":      len(pwd) >= MIN_LENGTH,
        "lower":       bool(_RE_LOWER.search(pwd)),
        "upper":       bool(_RE_UPPER.search(pwd)),
        "digit":       bool(_RE_DIGIT.search(pwd)),
        "special":     any(c in SPECIALS_SET for c in pwd),
        "no_whitespace": not bool(_RE_HAS_SPACE.search(pwd)),
    }
    failures = [k for k, v in checks.items() if not v]
    return PolicyCheck(ok=not failures, failures=failures, checks=checks)


def assert_password_valid(pwd: str) -> None:
    """Raise ValueError with a human-readable message if pwd is invalid.

    The router converts ValueError → HTTP 400.
    """
    result = check_password(pwd)
    if result.ok:
        return
    pretty = {
        "length":        f"at least {MIN_LENGTH} characters",
        "lower":         "one lowercase letter",
        "upper":         "one uppercase letter",
        "digit":         "one digit",
        "special":       "one special character (e.g. - _ ! @ # $ %)",
        "no_whitespace": "no spaces",
    }
    raise ValueError(
        "Password does not meet the policy. Missing: "
        + ", ".join(pretty.get(k, k) for k in result.failures)
        + "."
    )
