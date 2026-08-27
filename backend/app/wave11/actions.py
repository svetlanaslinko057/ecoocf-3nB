"""
Wave 11.1 — Deal Operations Center

Write-side actions for Deal360:

  * Pipeline transitions      — move / complete / cancel a deal stage
  * Blockers                  — add / resolve user-defined blockers
  * Deposit shortcuts         — register from deal context (wraps legal_deposits)
  * Payment shortcuts         — register + confirm in one round trip

These are *thin* — they re-use the canonical Wave 6 pipeline catalogue, the
existing `deal_timeline` and Wave 11 `bundle.py`. Nothing here invents a
parallel data model; everything is additive on top of the deal document and
existing collections.

Why a dedicated module?
  - Keeps the Wave 11 router file readable.
  - Lets us unit-test each action in isolation later if we want.
  - Concentrates the side-effects (stage_history, deal_blockers,
    deal_timeline write) so the rules are easy to audit.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.wave6.pipeline import (
    PIPELINE_STAGES,
    PIPELINE_STAGE_LABELS,
    derive_pipeline_stage,
)
from app.wave6.timeline import write_event

logger = logging.getLogger("bibi.wave11.actions")


# ─── Pipeline transitions ───────────────────────────────────────────────────
def _is_valid_stage(stage: str) -> bool:
    return stage in PIPELINE_STAGES


def allowed_transitions(deal: Dict[str, Any]) -> List[str]:
    """Return the list of stages this deal may move to from its current stage.

    Rules (operations-friendly, not chained):
      * Any non-terminal stage → "cancelled" is always available.
      * From "delivered" or "cancelled" → no transitions (terminal).
      * Otherwise, the next stage in the linear pipeline AND the immediate
        previous stage (so the manager can step back if something went
        wrong) AND "cancelled".
    """
    current = derive_pipeline_stage(deal)
    if current in ("delivered", "cancelled"):
        return []

    linear = [s for s in PIPELINE_STAGES if s != "cancelled"]
    try:
        idx = linear.index(current)
    except ValueError:
        idx = 0

    out: List[str] = []
    if idx + 1 < len(linear):
        out.append(linear[idx + 1])
    if idx > 0:
        out.append(linear[idx - 1])
    if "cancelled" not in out:
        out.append("cancelled")
    return out


async def transition_deal_stage(
    db,
    *,
    deal: Dict[str, Any],
    target_stage: str,
    reason: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    """Move a deal to `target_stage`.

    Writes:
      * `deal.stage`
      * `deal.stage_history` (append entry)
      * `deal_timeline` event of type `stage_changed`
    """
    if not _is_valid_stage(target_stage):
        raise HTTPException(400, f"Unknown stage '{target_stage}'")
    current = derive_pipeline_stage(deal)
    if current == target_stage:
        raise HTTPException(409, f"Deal already in stage '{target_stage}'")
    if target_stage not in allowed_transitions(deal):
        raise HTTPException(
            409,
            f"Cannot transition from '{current}' to '{target_stage}'. "
            f"Allowed: {', '.join(allowed_transitions(deal)) or 'none'}",
        )

    now = datetime.now(timezone.utc)
    entry = {
        "from":   current,
        "to":     target_stage,
        "at":     now.isoformat(),
        "by":     actor.get("email") or actor.get("id"),
        "reason": (reason or "").strip()[:1000] or None,
    }

    update_doc: Dict[str, Any] = {
        "$set":  {
            "stage":          target_stage,
            "pipeline_stage": target_stage,
            "updated_at":     now.isoformat(),
        },
        "$push": {"stage_history": entry},
    }
    if target_stage == "deposit_paid" and not deal.get("deposit_paid_at"):
        update_doc["$set"]["deposit_paid_at"] = now.isoformat()
    if target_stage == "contract_signed" and not deal.get("contract_signed_at"):
        update_doc["$set"]["contract_signed_at"] = now.isoformat()
    if target_stage == "delivered" and not deal.get("delivered_at"):
        update_doc["$set"]["delivered_at"] = now.isoformat()

    await db.deals.update_one({"id": deal["id"]}, update_doc)

    # Timeline event
    cur_label = (PIPELINE_STAGE_LABELS.get(current) or {}).get("en") or current
    tgt_label = (PIPELINE_STAGE_LABELS.get(target_stage) or {}).get("en") or target_stage
    msg = f"Stage: {cur_label} → {tgt_label}" + (f" ({reason})" if reason else "")
    try:
        await write_event(
            db,
            deal_id=deal["id"],
            event_type="stage_changed",
            message=msg,
            i18n_key="timeline.stage_changed",
            data={"from": current, "to": target_stage, "reason": reason},
            actor={"email": actor.get("email"), "role": actor.get("role")},
        )
    except Exception as e:
        logger.warning("[wave11.1] stage timeline write failed: %s", e)

    return entry


# ─── Blockers ───────────────────────────────────────────────────────────────
async def add_blocker(
    db,
    *,
    deal_id: str,
    label: str,
    note: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    label = (label or "").strip()
    if not label:
        raise HTTPException(400, "Blocker label is required")
    if len(label) > 200:
        raise HTTPException(400, "Blocker label is too long (max 200 chars)")
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id":         f"blk_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}",
        "label":      label,
        "note":       (note or "").strip()[:2000] or None,
        "created_by": actor.get("email") or actor.get("id"),
        "created_at": now,
        "resolved":   False,
    }
    await db.deals.update_one(
        {"id": deal_id},
        {"$push": {"deal_blockers": entry}, "$set": {"updated_at": now}},
    )
    try:
        await write_event(
            db,
            deal_id=deal_id,
            event_type="note_added",
            message=f"Blocker added: {label}" + (f" — {note}" if note else ""),
            i18n_key="timeline.blocker_added",
            data={"blocker_id": entry["id"], "label": label},
            actor={"email": actor.get("email"), "role": actor.get("role")},
        )
    except Exception:
        pass
    return entry


async def resolve_blocker(
    db,
    *,
    deal_id: str,
    blocker_id: str,
    note: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    deal = await db.deals.find_one({"id": deal_id}, {"_id": 0, "deal_blockers": 1})
    if not deal:
        raise HTTPException(404, "Deal not found")
    blockers = deal.get("deal_blockers") or []
    match = next((b for b in blockers if b.get("id") == blocker_id), None)
    if not match:
        raise HTTPException(404, "Blocker not found")
    if match.get("resolved"):
        return match

    now = datetime.now(timezone.utc).isoformat()
    await db.deals.update_one(
        {"id": deal_id, "deal_blockers.id": blocker_id},
        {"$set": {
            "deal_blockers.$.resolved":     True,
            "deal_blockers.$.resolved_at":  now,
            "deal_blockers.$.resolved_by":  actor.get("email") or actor.get("id"),
            "deal_blockers.$.resolution":   (note or "").strip()[:2000] or None,
            "updated_at":                   now,
        }},
    )
    try:
        await write_event(
            db,
            deal_id=deal_id,
            event_type="note_added",
            message=f"Blocker resolved: {match.get('label')}" + (f" — {note}" if note else ""),
            i18n_key="timeline.blocker_resolved",
            data={"blocker_id": blocker_id, "label": match.get("label")},
            actor={"email": actor.get("email"), "role": actor.get("role")},
        )
    except Exception:
        pass
    return {**match, "resolved": True, "resolved_at": now, "resolution": note}


# ─── Deposit / payment shortcuts ────────────────────────────────────────────
async def register_deposit_quick(
    db,
    *,
    deal: Dict[str, Any],
    amount: float,
    currency: str = "EUR",
    method: Optional[str] = None,
    note: Optional[str] = None,
    actor: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Lightweight deposit registration (no separate legal_workflow logic).

    Persists in `legal_deposits` (same shape the legacy module uses) so the
    /360 bundle and the legal page both see the same record.
    """
    if amount is None or float(amount) <= 0:
        raise HTTPException(400, "Deposit amount must be positive")
    now = datetime.now(timezone.utc).isoformat()
    dep_id = f"dep_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}"
    doc = {
        "id":          dep_id,
        "deal_id":     deal.get("id"),
        "customer_id": deal.get("customer_id") or deal.get("customerId"),
        "amount":      round(float(amount), 2),
        "currency":    (currency or "EUR").upper(),
        "method":      method,
        "status":      "pending",
        "note":        note,
        "created_at":  now,
        "updated_at":  now,
        "created_by":  (actor or {}).get("email") or (actor or {}).get("id"),
        "source":      "deal360_quick",
    }
    await db.legal_deposits.insert_one(doc)
    try:
        await write_event(
            db,
            deal_id=deal.get("id"),
            event_type="deposit_requested",
            message=f"Deposit registered: {doc['amount']} {doc['currency']}",
            i18n_key="timeline.deposit_requested",
            data={"deposit_id": dep_id, "amount": doc["amount"], "currency": doc["currency"]},
            actor={"email": (actor or {}).get("email"), "role": (actor or {}).get("role")},
        )
    except Exception:
        pass
    doc.pop("_id", None)
    return doc


async def update_deposit_status(
    db,
    *,
    deposit_id: str,
    new_status: str,
    note: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    """Update a deposit's status with a strict whitelist.

    Allowed values: confirmed, rejected, refunded.
    Writes a timeline event mirroring the change.
    """
    allowed = {"confirmed", "rejected", "refunded"}
    if new_status not in allowed:
        raise HTTPException(400, f"Status must be one of {sorted(allowed)}")

    dep = await db.legal_deposits.find_one({"id": deposit_id}, {"_id": 0})
    if not dep:
        raise HTTPException(404, "Deposit not found")

    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": new_status, "updated_at": now}
    if new_status == "confirmed":
        set_fields["confirmed_at"] = now
        set_fields["confirmed_by"] = actor.get("email") or actor.get("id")
    elif new_status == "rejected":
        set_fields["rejected_at"] = now
        set_fields["rejected_by"] = actor.get("email") or actor.get("id")
        set_fields["rejection_reason"] = (note or "").strip()[:1000] or None
    elif new_status == "refunded":
        set_fields["refunded_at"] = now
        set_fields["refunded_by"] = actor.get("email") or actor.get("id")
        set_fields["refund_reason"] = (note or "").strip()[:1000] or None

    await db.legal_deposits.update_one({"id": deposit_id}, {"$set": set_fields})

    # Reflect on the deal for stage_progress.blockers heuristics
    if new_status == "confirmed":
        try:
            await db.deals.update_one(
                {"id": dep.get("deal_id")},
                {"$set": {"deposit_paid_at": now, "updated_at": now}},
            )
        except Exception:
            pass

    event_type = {
        "confirmed": "deposit_confirmed",
        "rejected":  "deposit_refunded",
        "refunded":  "deposit_refunded",
    }[new_status]
    try:
        await write_event(
            db,
            deal_id=dep.get("deal_id"),
            event_type=event_type,
            message=f"Deposit {new_status}: {dep.get('amount')} {dep.get('currency') or 'EUR'}"
                    + (f" — {note}" if note else ""),
            i18n_key=f"timeline.{event_type}",
            data={"deposit_id": deposit_id, "amount": dep.get("amount")},
            actor={"email": actor.get("email"), "role": actor.get("role")},
        )
    except Exception:
        pass

    return {**dep, **set_fields}


async def register_payment_quick(
    db,
    *,
    deal: Dict[str, Any],
    amount: float,
    currency: str = "EUR",
    kind: str = "milestone",
    status: str = "pending",
    note: Optional[str] = None,
    actor: Dict[str, Any] = None,
) -> Dict[str, Any]:
    if amount is None or float(amount) <= 0:
        raise HTTPException(400, "Payment amount must be positive")
    if status not in ("pending", "confirmed"):
        raise HTTPException(400, "Status must be 'pending' or 'confirmed'")

    now = datetime.now(timezone.utc).isoformat()
    pay_id = f"pay_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}"
    doc = {
        "id":         pay_id,
        "deal_id":    deal.get("id"),
        "customer_id": deal.get("customer_id") or deal.get("customerId"),
        "type":       kind,
        "amount":     round(float(amount), 2),
        "currency":   (currency or "EUR").upper(),
        "status":     status,
        "note":       note,
        "created_at": now,
        "updated_at": now,
        "created_by": (actor or {}).get("email") or (actor or {}).get("id"),
        "source":     "deal360_quick",
    }
    if status == "confirmed":
        doc["confirmed_at"] = now
    await db.payments.insert_one(doc)

    try:
        await write_event(
            db,
            deal_id=deal.get("id"),
            event_type="payment_received" if status == "confirmed" else "note_added",
            message=(f"Payment {status}: {doc['amount']} {doc['currency']}"
                     + (f" ({kind})" if kind and kind != 'milestone' else "")),
            i18n_key=("timeline.payment_received" if status == "confirmed"
                      else "timeline.payment_scheduled"),
            data={"payment_id": pay_id, "amount": doc["amount"], "status": status},
            actor={"email": (actor or {}).get("email"), "role": (actor or {}).get("role")},
        )
    except Exception:
        pass

    doc.pop("_id", None)
    return doc


async def update_payment_status(
    db,
    *,
    payment_id: str,
    new_status: str,
    note: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    allowed = {"confirmed", "failed", "refunded"}
    if new_status not in allowed:
        raise HTTPException(400, f"Status must be one of {sorted(allowed)}")

    pay = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not pay:
        raise HTTPException(404, "Payment not found")

    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": new_status, "updated_at": now}
    if new_status == "confirmed":
        set_fields["confirmed_at"] = now
        set_fields["confirmed_by"] = actor.get("email") or actor.get("id")
    elif new_status == "failed":
        set_fields["failed_at"] = now
        set_fields["failed_reason"] = (note or "").strip()[:1000] or None
    elif new_status == "refunded":
        set_fields["refunded_at"] = now
        set_fields["refund_reason"] = (note or "").strip()[:1000] or None

    await db.payments.update_one({"id": payment_id}, {"$set": set_fields})

    et = {
        "confirmed": "payment_received",
        "failed":    "note_added",
        "refunded":  "note_added",
    }[new_status]
    try:
        await write_event(
            db,
            deal_id=pay.get("deal_id"),
            event_type=et,
            message=f"Payment {new_status}: {pay.get('amount')} {pay.get('currency') or 'EUR'}"
                    + (f" — {note}" if note else ""),
            i18n_key=f"timeline.payment_{new_status}",
            data={"payment_id": payment_id, "amount": pay.get("amount")},
            actor={"email": actor.get("email"), "role": actor.get("role")},
        )
    except Exception:
        pass

    return {**pay, **set_fields}
