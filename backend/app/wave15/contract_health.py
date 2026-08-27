"""
BIBI Cars — Wave 15 — Contract Health Engine
================================================

Pure scorer. Single source of truth for the contractual side of a deal,
same style as ``financial_health.py`` / ``delivery_health.py``.

Returns:
    {
      "score":   int (0..100),
      "segment": one of CONTRACT_SEGMENTS,
      "reasons": [str, ...],
      "metrics": { ... }
    }

No DB calls — caller passes the contract dict (with embedded approvals /
attachments / events) and we compute everything in-memory.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Contract Health segments (ordered worst → best, sort-friendly).
CONTRACT_SEGMENTS = (
    "critical",         # expired / rejected on an active deal
    "unsigned",         # sent more than X days ago, still unsigned
    "wrong_version",    # superseded version still referenced from a deal
    "missing_annex",    # required annex missing on a signed contract
    "pending_approval", # waiting on internal sign-off
    "draft",            # being authored
    "healthy",          # active + signed + everything in place
    "archived",         # terminal — not at risk by definition
)

UNSIGNED_GRACE_DAYS = 7        # sent more than this and still unsigned = unsigned segment
EXPIRY_WARN_DAYS    = 7        # within this many days of valid_to → reason added


def _parse_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _days_between(a: Optional[datetime], b: Optional[datetime]) -> Optional[int]:
    if not a or not b: return None
    return int((b - a).total_seconds() // 86400)


def _to_iso(v: Any) -> Optional[str]:
    dt = _parse_dt(v)
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def compute_contract_health(
    contract: Optional[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Score one contract's health.

    `contract` shape (loose):
      {
        id, status, type, version, current,
        valid_from, valid_to, signed_at, sent_at, opened_at,
        required_annexes: [str],
        attachments: [{ kind: 'annex' | 'signed_pdf' | ... , filename, kind_key }],
        approvals:   [{ step, status, at, actor_id }],
        events:      [{ kind, at }],
      }
    """
    now = now or datetime.now(timezone.utc)
    c = contract or {}

    status     = (c.get("status") or "draft").lower()
    is_current = bool(c.get("current", True))
    attachments = c.get("attachments") or []
    approvals   = c.get("approvals") or []
    required_annexes = c.get("required_annexes") or []

    valid_from  = _parse_dt(c.get("valid_from"))
    valid_to    = _parse_dt(c.get("valid_to"))
    sent_at     = _parse_dt(c.get("sent_at"))
    signed_at   = _parse_dt(c.get("signed_at"))

    reasons: List[str] = []
    score = 100

    # ── terminal states ───────────────────────────────────────────────
    if status == "archived":
        return {
            "score":   100,
            "segment": "archived",
            "reasons": ["reason.archived"],
            "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
        }
    if status == "rejected":
        return {
            "score":   0,
            "segment": "critical",
            "reasons": ["reason.rejected"],
            "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
        }
    if status == "expired":
        return {
            "score":   10,
            "segment": "critical",
            "reasons": ["reason.expired"],
            "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
        }
    # ── superseded version ────────────────────────────────────────────
    if status == "amended" or not is_current:
        return {
            "score":   30,
            "segment": "wrong_version",
            "reasons": ["reason.superseded"],
            "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
        }

    # ── status-based segmentation ─────────────────────────────────────
    if status == "draft":
        return {
            "score":   60,
            "segment": "draft",
            "reasons": ["reason.draft"],
            "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
        }

    if status == "pending_approval":
        # find oldest pending step
        pending = [a for a in approvals if (a.get("status") or "pending") == "pending"]
        if pending:
            reasons.append(f"reason.waiting_step:{pending[0].get('step') or 'unknown'}")
        else:
            reasons.append("reason.pending_approval")
        score = 55
        return {"score": score, "segment": "pending_approval", "reasons": reasons,
                "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now)}

    # ── expiry check (active / signed / sent contracts) ──────────────
    if valid_to and now > valid_to:
        return {
            "score":   10,
            "segment": "critical",
            "reasons": ["reason.expired"],
            "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
        }
    if valid_to:
        days_to_expiry = _days_between(now, valid_to)
        if days_to_expiry is not None and 0 <= days_to_expiry <= EXPIRY_WARN_DAYS:
            reasons.append(f"reason.expires_in_days:{days_to_expiry}")
            score -= 10

    # ── unsigned past grace ──────────────────────────────────────────
    if status in ("approved", "sent", "opened") and not signed_at:
        ref = sent_at or _parse_dt(c.get("updated_at")) or _parse_dt(c.get("created_at"))
        if ref:
            age = _days_between(ref, now) or 0
            if age > UNSIGNED_GRACE_DAYS:
                return {
                    "score":   35,
                    "segment": "unsigned",
                    "reasons": [f"reason.sent_days_unsigned:{age}"] + reasons,
                    "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
                }
            else:
                reasons.append(f"reason.awaiting_signature_days:{age}")
                score -= 15
        else:
            reasons.append("reason.awaiting_signature")
            score -= 10

    # ── missing required annexes ─────────────────────────────────────
    annex_kinds = {(a.get("kind_key") or a.get("filename") or "").lower() for a in attachments}
    annex_filenames = {(a.get("filename") or "").lower() for a in attachments}
    missing_annexes: List[str] = []
    for required in required_annexes:
        key = required.lower()
        # match either an annex with matching kind_key OR a filename containing the key
        matched = key in annex_kinds or any(key in fn for fn in annex_filenames)
        if not matched:
            missing_annexes.append(required)
    if missing_annexes:
        # only down-grade if contract is signed/active — drafts haven't collected docs yet
        if status in ("signed", "active"):
            return {
                "score":   45,
                "segment": "missing_annex",
                "reasons": [f"reason.missing_annex:{','.join(missing_annexes[:3])}"] + reasons,
                "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
            }
        else:
            reasons.append(f"reason.will_need_annex:{','.join(missing_annexes[:3])}")
            score -= 5

    # ── happy path ──────────────────────────────────────────────────
    score = max(0, min(100, score))
    if not reasons:
        reasons = ["reason.healthy"]
    segment = "healthy" if score >= 75 else "pending_approval" if score >= 50 else "unsigned"

    return {
        "score":   score,
        "segment": segment,
        "reasons": reasons,
        "metrics": _metrics(c, valid_from, valid_to, sent_at, signed_at, attachments, approvals, required_annexes, now),
    }


def _metrics(c: Dict[str, Any], valid_from, valid_to, sent_at, signed_at,
             attachments, approvals, required_annexes, now) -> Dict[str, Any]:
    pending = [a for a in approvals if (a.get("status") or "pending") == "pending"]
    approved = [a for a in approvals if a.get("status") == "approved"]
    annex_kinds = {(a.get("kind_key") or a.get("filename") or "").lower() for a in attachments}
    annex_filenames = {(a.get("filename") or "").lower() for a in attachments}
    missing = []
    for r in (required_annexes or []):
        k = r.lower()
        if k not in annex_kinds and not any(k in fn for fn in annex_filenames):
            missing.append(r)
    return {
        "status":     c.get("status"),
        "version":    c.get("version"),
        "valid_from": _to_iso(valid_from),
        "valid_to":   _to_iso(valid_to),
        "sent_at":    _to_iso(sent_at),
        "signed_at":  _to_iso(signed_at),
        "days_to_expiry": _days_between(now, valid_to) if valid_to else None,
        "approvals_pending":  len(pending),
        "approvals_approved": len(approved),
        "approvals_total":    len(approvals),
        "attachments_count":  len(attachments),
        "missing_annexes":    missing,
    }


__all__ = ["compute_contract_health", "CONTRACT_SEGMENTS",
           "UNSIGNED_GRACE_DAYS", "EXPIRY_WARN_DAYS"]
