"""
Contract Lifecycle service — Mini Sprint Contracts Final
=========================================================

Manages the state-machine of every contract from the moment a manager
generates the PDF up to the moment the customer signs it.

Lifecycle
---------
      ╔═══════╗      ╔══════╗      ╔═══════╗      ╔════════╗      ╔══════════╗
   ---║ draft ╟──────╬ sent ╟──────╬ viewed ╟──────╬ signed ╟──────╬ archived ║
      ╚═══╦═══╝      ╚══════╝      ╚═══════╝      ╚═══╦════╝      ╚══════════╝
          │                                  │
          ╚═ cancel  (admin only)             ╚═ archive (admin)

Key points
----------
* Every contract carries a stable, opaque ``view_token`` that grants
  read+sign access to the customer **without** authentication. The
  token is generated when the contract transitions from draft → sent.
* Visiting the public viewer flips ``viewed_at`` exactly once (we
  don't churn the state-machine on subsequent re-views).
* Signing requires explicit terms acceptance + a typed full name.
  We record the requester's IP and user-agent for audit.
* Idempotent ``record_view`` / ``ensure_view_token`` helpers so
  webhook retries don't multiply events.
* Emits ``contract_signed`` event to the Customer Timeline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.contract_lifecycle")

# --- Electronic signature (Simple Electronic Signature / ПЕП) -------------
# Legal basis (Ukraine): ст. 207 ЦКУ (правочин в електронній формі) +
# Закон «Про електронні довірчі послуги» (простий електронний підпис).
# A SES is legally binding between B2B parties when they agree to use it and
# the act of signing is reliably attributable to the signer. We make it
# *attributable & tamper-evident* by binding the signature to an immutable
# SHA-256 hash of the exact agreement terms and a full audit trail
# (signer identity, explicit consent, timestamp, IP, user-agent, serial №).
SIGNATURE_METHOD = "simple_electronic_signature"
SIGNATURE_STANDARD = "UA SES (ЦКУ ст.207; ЗУ «Про електронні довірчі послуги»)"
HASH_ALGORITHM = "SHA-256"
CONSENT_VERSION = "1.0"
DEFAULT_CONSENT_TEXT = (
    "Я ознайомлений(-а) з умовами договору, погоджуюся з ними та підписую його "
    "простим електронним підписом. Підтверджую, що дані, наведені при підписанні, "
    "є достовірними, а цей електронний підпис прирівнюється до власноручного "
    "відповідно до ст. 207 Цивільного кодексу України та Закону України "
    "«Про електронні довірчі послуги»."
)
SIGNATURES_COLLECTION = "contract_signatures"


def _canonical_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Stable subset of fields that legally constitute the agreement.

    Hashing this canonical form makes the signature tamper-evident: any change
    to the terms after signing yields a different hash than the one stored on
    the signature certificate.
    """
    return {
        "id": doc.get("id"),
        "number": doc.get("number"),
        "title": doc.get("title"),
        "version": doc.get("version"),
        "amount": doc.get("amount"),
        "currency": doc.get("currency"),
        "items": doc.get("items") or [],
        "company": doc.get("company") or {},
        "operator": doc.get("operator") or {},
        "customer_id": doc.get("customerId") or doc.get("customer_id"),
        "valid_from": doc.get("valid_from") or doc.get("sent_at"),
        "valid_to": doc.get("valid_to"),
        "language": doc.get("language"),
    }


def compute_document_hash(doc: Dict[str, Any]) -> str:
    canonical = json.dumps(
        _canonical_document(doc), sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _make_signature_serial() -> str:
    return f"ECO-SIG-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

COLLECTION = "contracts_v2"

LIFECYCLE_STATES = ("draft", "sent", "viewed", "signed", "archived", "cancelled")
# Allowed forward transitions. Backward moves are admin-only and bypass this map.
ALLOWED_TRANSITIONS = {
    "draft":     {"sent", "cancelled", "archived"},
    "sent":      {"viewed", "signed", "cancelled", "archived"},
    "viewed":    {"signed", "cancelled", "archived"},
    "signed":    {"archived"},
    "archived":  set(),
    "cancelled": {"archived"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"ctr_{uuid.uuid4().hex[:14]}"


def _new_view_token() -> str:
    # 32 url-safe chars — hard to brute-force, easy to embed in mailer
    return secrets.token_urlsafe(24)


async def create_from_generation(
    *,
    customer_id: str,
    invoice_id: Optional[str],
    deal_id: Optional[str],
    file_id: str,
    document_id: str,
    template_id: Optional[str],
    language: str = "en",
    title: Optional[str] = None,
    version: int = 1,
    generated_by: Optional[str] = None,
    generated_by_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Spawn a contracts_v2 row right after the PDF is generated.

    Idempotency: if a contract for the same ``document_id`` already
    exists we return it unchanged (so re-generating the same PDF
    twice doesn't duplicate the lifecycle record).
    """
    db = get_db()
    existing = await db[COLLECTION].find_one({"document_id": document_id}, {"_id": 0})
    if existing:
        return existing

    doc = {
        "id": _new_id(),
        "customerId": customer_id,
        "customer_id": customer_id,
        "invoiceId": invoice_id,
        "dealId": deal_id,
        "file_id": file_id,
        "document_id": document_id,
        "template_id": template_id,
        "language": language,
        "title": title or f"Contract {version}",
        "version": version,
        "lifecycle": "draft",
        "view_token": None,
        "sent_at": None,
        "viewed_at": None,
        "signed_at": None,
        "signed_by": None,
        "signed_ip": None,
        "signed_user_agent": None,
        "signed_full_name": None,
        "archived_at": None,
        "cancelled_at": None,
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": generated_by,
        "created_by_email": generated_by_email,
    }
    await db[COLLECTION].insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def list_for_customer(customer_id: str, *, include_archived: bool = True) -> List[Dict[str, Any]]:
    db = get_db()
    flt: Dict[str, Any] = {
        "$or": [{"customerId": customer_id}, {"customer_id": customer_id}],
    }
    if not include_archived:
        flt["lifecycle"] = {"$ne": "archived"}
    cursor = db[COLLECTION].find(flt, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=300)


async def get_by_id(contract_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db[COLLECTION].find_one({"id": contract_id}, {"_id": 0})


async def get_by_view_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    db = get_db()
    return await db[COLLECTION].find_one({"view_token": token}, {"_id": 0})


def _transition_ok(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current or "draft", set())


async def mark_sent(contract_id: str, *, by: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await get_by_id(contract_id)
    if not doc:
        return None
    if doc.get("lifecycle") not in {"draft", "sent"}:
        # Sending again from a later state is meaningless
        raise ValueError(f"Cannot send from lifecycle '{doc.get('lifecycle')}'")
    token = doc.get("view_token") or _new_view_token()
    await db[COLLECTION].update_one(
        {"id": contract_id},
        {"$set": {
            "lifecycle": "sent",
            "view_token": token,
            "sent_at": doc.get("sent_at") or _now(),
            "sent_by": (by or {}).get("id"),
            "sent_by_email": (by or {}).get("email"),
            "updated_at": _now(),
        }},
    )
    return await get_by_id(contract_id)


async def record_view(view_token: str) -> Optional[Dict[str, Any]]:
    """Idempotently bump viewed_at on first public open."""
    db = get_db()
    doc = await get_by_view_token(view_token)
    if not doc:
        return None
    if doc.get("lifecycle") in {"sent"}:
        await db[COLLECTION].update_one(
            {"id": doc["id"]},
            {"$set": {"lifecycle": "viewed", "viewed_at": _now(), "updated_at": _now()}},
        )
        return await get_by_id(doc["id"])
    # Already viewed/signed/archived — leave alone
    return doc


async def sign(
    view_token: str,
    *,
    full_name: str,
    terms_accepted: bool,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    consent_text: Optional[str] = None,
    consent_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not terms_accepted:
        raise ValueError("Перед підписанням необхідно прийняти умови договору")
    if not (full_name and full_name.strip()):
        raise ValueError("Вкажіть повне ім'я підписанта")
    db = get_db()
    doc = await get_by_view_token(view_token)
    if not doc:
        return None
    cur = doc.get("lifecycle")
    if cur not in {"sent", "viewed"}:
        raise ValueError(f"Неможливо підписати з поточного стану '{cur}'")

    signer_name = full_name.strip()
    signed_at = _now()
    document_hash = compute_document_hash(doc)
    signature_id = _make_signature_serial()
    consent = (consent_text or DEFAULT_CONSENT_TEXT).strip()
    cversion = consent_version or CONSENT_VERSION

    # Tamper-evident signature certificate bound to the exact agreement terms.
    signature = {
        "signature_id": signature_id,
        "method": SIGNATURE_METHOD,
        "standard": SIGNATURE_STANDARD,
        "signer_name": signer_name,
        "signer_customer_id": doc.get("customerId") or doc.get("customer_id"),
        "signed_at": signed_at,
        "ip": ip,
        "user_agent": user_agent,
        "hash_algorithm": HASH_ALGORITHM,
        "document_hash": document_hash,
        "document_version": doc.get("version"),
        "consent_text": consent,
        "consent_version": cversion,
    }

    await db[COLLECTION].update_one(
        {"id": doc["id"]},
        {"$set": {
            "lifecycle": "signed",
            "signed_at": signed_at,
            "signed_full_name": signer_name,
            "signed_by": doc.get("customerId") or doc.get("customer_id"),
            "signed_ip": ip,
            "signed_user_agent": user_agent,
            "signature": signature,
            "updated_at": _now(),
        }},
    )

    # Immutable, append-only audit log of every signing act.
    try:
        await db[SIGNATURES_COLLECTION].insert_one({
            "id": f"sigrec_{uuid.uuid4().hex[:12]}",
            "contract_id": doc["id"],
            "contract_number": doc.get("number"),
            **signature,
            "created_at": signed_at,
        })
    except Exception:
        logger.exception("[contract_lifecycle] signature audit insert failed (non-fatal)")

    fresh = await get_by_id(doc["id"])

    # Emit timeline event
    try:
        from app.services import customer_timeline
        await customer_timeline.record_event(
            customer_id=doc.get("customerId") or doc.get("customer_id"),
            kind="contract_signed",
            title=f"Договір підписано: {signer_name}",
            ref={"collection": COLLECTION, "id": doc["id"]},
            actor={"name": signer_name, "email": None, "role": "customer"},
            meta={
                "ip": ip,
                "user_agent": user_agent,
                "version": doc.get("version"),
                "signature_id": signature_id,
                "document_hash": document_hash,
            },
        )
    except Exception:
        logger.exception("[contract_lifecycle] timeline emit failed")
    return fresh


async def archive(contract_id: str, *, by: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await get_by_id(contract_id)
    if not doc:
        return None
    await db[COLLECTION].update_one(
        {"id": contract_id},
        {"$set": {
            "lifecycle": "archived",
            "archived_at": _now(),
            "archived_by": (by or {}).get("id"),
            "updated_at": _now(),
        }},
    )
    return await get_by_id(contract_id)


async def cancel(contract_id: str, *, by: Optional[Dict[str, Any]] = None, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await get_by_id(contract_id)
    if not doc:
        return None
    if doc.get("lifecycle") in {"archived", "signed"}:
        raise ValueError(f"Cannot cancel from lifecycle '{doc.get('lifecycle')}'")
    await db[COLLECTION].update_one(
        {"id": contract_id},
        {"$set": {
            "lifecycle": "cancelled",
            "cancelled_at": _now(),
            "cancelled_by": (by or {}).get("id"),
            "cancellation_reason": reason,
            "updated_at": _now(),
        }},
    )
    return await get_by_id(contract_id)


__all__ = [
    "LIFECYCLE_STATES",
    "create_from_generation",
    "list_for_customer",
    "get_by_id",
    "get_by_view_token",
    "mark_sent",
    "record_view",
    "sign",
    "archive",
    "cancel",
]
