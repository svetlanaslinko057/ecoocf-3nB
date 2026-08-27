"""Universal variable engine — renders any template against a dynamic context.

Templates use ``{{ path.to.value }}`` tokens. Missing values render a visible
marker (never a silent empty string) and are reported so required variables can
block acceptance.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from . import constants as K

_TOKEN_RE = re.compile(r"{{\s*([a-zA-Z0-9_.]+)\s*}}")


def _resolve(context: Dict[str, Any], path: str) -> Any:
    cur: Any = context
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def build_context(
    *,
    profile: Dict[str, Any],
    customer: Dict[str, Any],
    contract: Dict[str, Any],
    ctype: Dict[str, Any] | None,
    payment: Dict[str, Any] | None,
    custom_vars: Dict[str, Any] | None,
) -> Dict[str, Any]:
    ctype = ctype or {}
    payment = payment or {}
    custom_vars = custom_vars or {}

    ctx: Dict[str, Any] = {
        "company": {
            "legal_name": profile.get("legal_name", ""),
            "edrpou": profile.get("edrpou", ""),
            "legal_address": profile.get("legal_address", ""),
            "iban": profile.get("iban", ""),
            "bank_name": profile.get("bank_name", ""),
            "mfo": profile.get("mfo", ""),
            "vat_number": profile.get("vat_number", ""),
        },
        "customer": {
            "full_name": customer.get("name") or profile.get("contact_person", ""),
            "email": profile.get("email") or customer.get("email", ""),
            "phone": profile.get("phone") or customer.get("phone", ""),
        },
        "signer": {
            "full_name": profile.get("signer_full_name", ""),
            "position": profile.get("signer_position", ""),
        },
        "contract": {
            "number": contract.get("number", ""),
            "date": contract.get("date", ""),
            "valid_from": contract.get("valid_from", ""),
            "valid_to": contract.get("valid_to", ""),
            "value": contract.get("value", ""),
            "title": contract.get("title", ""),
        },
        "service": {
            "name": contract.get("service_name", "") or ctype.get("name", ""),
        },
        "payment": {
            "iban": payment.get("iban", ""),
            "terms": payment.get("terms", ""),
            "recipient_name": payment.get("recipient_name", ""),
            "recipient_edrpou": payment.get("recipient_edrpou", ""),
            "bank_name": payment.get("bank_name", ""),
            "amount_due": payment.get("amount_due", ""),
            "payment_purpose": payment.get("payment_purpose", ""),
        },
        "waste": {"items": contract.get("waste_items", "")},
        "schedule": {"periods": contract.get("schedule_periods", "")},
    }
    # custom variables live under `custom.*` and also flat top-level keys.
    # Dotted keys (e.g. "service.custom_field") are expanded into nested dicts
    # and merged into the context so `{{service.custom_field}}` resolves.
    ctx["custom"] = dict(custom_vars)
    for k, v in custom_vars.items():
        if "." in k:
            parts = k.split(".")
            node = ctx
            for p in parts[:-1]:
                nxt = node.get(p)
                if not isinstance(nxt, dict):
                    nxt = {}
                    node[p] = nxt
                node = nxt
            node[parts[-1]] = v
        elif k not in ctx:
            ctx[k] = v
    return ctx


def render_template(
    html: str,
    context: Dict[str, Any],
    variable_catalog: List[Dict[str, Any]] | None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Render ``html`` against ``context``.

    Returns (rendered_html, missing_variables) where each missing variable is
    ``{key, label, required}``. A required token that is missing is replaced by
    a visible marker; an optional one becomes an empty string.
    """
    catalog = {c["key"]: c for c in (variable_catalog or K.DEFAULT_VARIABLE_CATALOG)}
    missing: List[Dict[str, Any]] = []
    seen_missing = set()

    def repl(m: re.Match) -> str:
        key = m.group(1)
        val = _resolve(context, key)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            meta = catalog.get(key, {"key": key, "label": key, "required": False})
            required = bool(meta.get("required", False))
            if key not in seen_missing:
                seen_missing.add(key)
                missing.append({"key": key, "label": meta.get("label", key), "required": required})
            if required:
                return f"{K.MISSING_MARKER_PREFIX}{meta.get('label', key)}{K.MISSING_MARKER_SUFFIX}"
            return ""
        return str(val)

    rendered = _TOKEN_RE.sub(repl, html or "")
    return rendered, missing


def checksum(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
