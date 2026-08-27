"""
BIBI Cars — Wave 13 — Delivery Health Engine
================================================

Pure scorer. Single source of truth for “where is the car?” health
the same way `financial_health.py` is the source of truth for money
health.

Returns:
    {
      "score":   int (0..100),
      "segment": "on_track" | "delay_risk" | "delayed" | "critical"
                 | "delivered" | "cancelled",
      "reasons": [str, ...],   # human-readable, top to bottom
      "metrics": {
          "eta_expected":  iso8601 | None,
          "eta_actual":    iso8601 | None,
          "eta_variance_days": int | None,
          "days_since_milestone": int | None,
          "milestones_done":     int,
          "milestones_total":    int,
          "current_milestone":   str,
          "missing_documents":   [str, ...],
      },
    }

This module is intentionally **pure** — no DB calls, no I/O. Callers
pre-fetch the shipment dict (plus the deal's documents/stage) and pass
it in.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Standard CRM-side delivery lifecycle (vessel-tracking detail lives
# in the existing `shipment.stages` array — we deliberately keep the
# two layers separate).
MILESTONE_ORDER: List[str] = [
    "auction_won",
    "payment_confirmed",
    "picked_up",
    "port_arrived",
    "loaded",
    "in_transit",
    "customs",
    "ready_for_delivery",
    "delivered",
]

MILESTONE_LABEL: Dict[str, str] = {
    "auction_won":         "Auction won",
    "payment_confirmed":   "Payment confirmed",
    "picked_up":           "Picked up",
    "port_arrived":        "Port arrived",
    "loaded":              "Loaded",
    "in_transit":          "In transit",
    "customs":             "Customs",
    "ready_for_delivery":  "Ready for delivery",
    "delivered":           "Delivered",
    "cancelled":           "Cancelled",
}

# Document types we expect for a fully papered delivery. The scorer
# treats anything in REQUIRED_DOCS as "missing" if we don't see at
# least one delivery_document with that kind.
REQUIRED_DOCS: List[str] = ["bill_of_sale", "cmr", "invoice"]

DOC_LABEL: Dict[str, str] = {
    "bill_of_sale":      "Bill of Sale",
    "cmr":               "CMR",
    "invoice":           "Invoice",
    "export":            "Export",
    "customs":           "Customs",
    "transport_contract":"Transport Contract",
    "photos":            "Photos",
    "other":             "Other",
}

SEGMENTS = ("on_track", "delay_risk", "delayed", "critical",
            "delivered", "cancelled")


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
    if not a or not b:
        return None
    return int((b - a).total_seconds() // 86400)


def _to_iso(v: Any) -> Optional[str]:
    dt = _parse_dt(v)
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def _milestone_done_index(milestones_done: List[str]) -> int:
    """Return the index of the latest milestone in MILESTONE_ORDER
    that's marked done. -1 if none."""
    idx = -1
    done = set(milestones_done or [])
    for i, key in enumerate(MILESTONE_ORDER):
        if key in done:
            idx = i
    return idx


def compute_delivery_health(
    shipment: Optional[Dict[str, Any]],
    *,
    documents: Optional[List[Dict[str, Any]]] = None,
    deal: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Compute a (score, segment, reasons, metrics) tuple for one shipment.

    `shipment` shape (loose — we tolerate missing fields):
      {
        "id": str,
        "deal_id": str,
        "delivery": {
            "carrier_id":         str | None,
            "carrier_name":       str | None,
            "current_milestone":  str | None,
            "milestones":         [{"key":..., "at":..., "by":..., "note":...}],
            "eta_expected":       iso | None,
            "eta_actual":         iso | None,
            "pickup_at":          iso | None,
            "delivered_at":       iso | None,
            "cancelled":          bool,
        },
        ...
      }
    """
    now = now or datetime.now(timezone.utc)
    sh = shipment or {}
    delivery = sh.get("delivery") or {}
    documents = documents or []
    deal = deal or {}

    reasons: List[str] = []
    score = 100

    # ---- terminal states --------------------------------------------------
    if delivery.get("cancelled") or (deal.get("status") == "cancelled"):
        return {
            "score": 0,
            "segment": "cancelled",
            "reasons": ["Delivery cancelled"],
            "metrics": {
                "eta_expected":  _to_iso(delivery.get("eta_expected")),
                "eta_actual":    _to_iso(delivery.get("eta_actual")),
                "eta_variance_days": None,
                "days_since_milestone": None,
                "milestones_done":  0,
                "milestones_total": len(MILESTONE_ORDER),
                "current_milestone": delivery.get("current_milestone") or "",
                "missing_documents": [],
            },
        }

    milestones_log = delivery.get("milestones") or []
    done_keys = [m.get("key") for m in milestones_log if m.get("key")]
    current = delivery.get("current_milestone") or (done_keys[-1] if done_keys else "")

    if current == "delivered" or "delivered" in done_keys:
        return {
            "score": 100,
            "segment": "delivered",
            "reasons": ["Delivered"],
            "metrics": {
                "eta_expected":  _to_iso(delivery.get("eta_expected")),
                "eta_actual":    _to_iso(delivery.get("eta_actual") or delivery.get("delivered_at")),
                "eta_variance_days": _days_between(
                    _parse_dt(delivery.get("eta_expected")),
                    _parse_dt(delivery.get("eta_actual") or delivery.get("delivered_at")),
                ),
                "days_since_milestone": 0,
                "milestones_done":  len(MILESTONE_ORDER),
                "milestones_total": len(MILESTONE_ORDER),
                "current_milestone": "delivered",
                "missing_documents": [],
            },
        }

    # ---- carrier ----------------------------------------------------------
    if not delivery.get("carrier_id") and not delivery.get("carrier_name"):
        reasons.append("No carrier assigned")
        score -= 15

    # ---- pickup confirmation ---------------------------------------------
    pickup_at = _parse_dt(delivery.get("pickup_at"))
    if not pickup_at and "picked_up" not in done_keys:
        # If we're already past payment_confirmed but no pickup, that hurts
        if "payment_confirmed" in done_keys:
            reasons.append("No pickup confirmation")
            score -= 10

    # ---- ETA variance -----------------------------------------------------
    eta_expected = _parse_dt(delivery.get("eta_expected"))
    eta_actual   = _parse_dt(delivery.get("eta_actual"))
    variance: Optional[int] = None
    if eta_expected:
        ref = eta_actual or now
        variance = _days_between(eta_expected, ref)
        if variance is not None:
            if variance > 14:
                reasons.append(f"ETA exceeded by {variance}d")
                score -= 40
            elif variance > 7:
                reasons.append(f"ETA exceeded by {variance}d")
                score -= 25
            elif variance > 3:
                reasons.append(f"ETA exceeded by {variance}d")
                score -= 12
            elif variance > 0 and not eta_actual:
                # Still in transit but past expected ETA
                reasons.append(f"Past expected ETA by {variance}d")
                score -= 7

    # ---- milestone stagnation --------------------------------------------
    last_move = None
    for m in reversed(milestones_log):
        last_move = _parse_dt(m.get("at"))
        if last_move:
            break
    days_since_milestone = _days_between(last_move, now) if last_move else None

    # Port stagnation (>5d at port_arrived without loaded)
    if current == "port_arrived" and days_since_milestone is not None and days_since_milestone > 5:
        reasons.append(f"Port delay — {days_since_milestone}d at port")
        score -= 12

    # Customs stagnation (>7d at customs without ready_for_delivery)
    if current == "customs" and days_since_milestone is not None and days_since_milestone > 7:
        reasons.append(f"Customs delay — {days_since_milestone}d at customs")
        score -= 15

    # Generic stagnation (no movement in >10d on any non-terminal stage)
    if days_since_milestone is not None and days_since_milestone > 10 and current not in ("", "delivered"):
        if not any("delay" in r.lower() for r in reasons):
            reasons.append(f"No movement in {days_since_milestone}d")
            score -= 8

    # ---- documents --------------------------------------------------------
    doc_kinds = {(d.get("kind") or d.get("type") or "").lower() for d in documents}
    missing_docs: List[str] = []
    # Only require docs once we're past payment_confirmed (paperwork phase begins).
    if "payment_confirmed" in done_keys:
        for k in REQUIRED_DOCS:
            if k not in doc_kinds:
                missing_docs.append(k)
        if missing_docs:
            pretty = ", ".join(DOC_LABEL.get(k, k) for k in missing_docs)
            reasons.append(f"Missing document(s): {pretty}")
            score -= 5 * min(len(missing_docs), 3)

    # ---- clamp + segment --------------------------------------------------
    score = max(0, min(100, score))
    if score >= 80:
        segment = "on_track"
    elif score >= 60:
        segment = "delay_risk"
    elif score >= 40:
        segment = "delayed"
    else:
        segment = "critical"

    milestones_done_count = _milestone_done_index(done_keys) + 1
    if milestones_done_count < 0:
        milestones_done_count = 0

    if not reasons:
        reasons = ["On track"]

    return {
        "score":   score,
        "segment": segment,
        "reasons": reasons,
        "metrics": {
            "eta_expected":      _to_iso(delivery.get("eta_expected")),
            "eta_actual":        _to_iso(delivery.get("eta_actual")),
            "eta_variance_days": variance,
            "days_since_milestone": days_since_milestone,
            "milestones_done":   milestones_done_count,
            "milestones_total":  len(MILESTONE_ORDER),
            "current_milestone": current or (MILESTONE_ORDER[0] if not done_keys else current),
            "missing_documents": missing_docs,
        },
    }


__all__ = [
    "compute_delivery_health",
    "MILESTONE_ORDER",
    "MILESTONE_LABEL",
    "REQUIRED_DOCS",
    "DOC_LABEL",
    "SEGMENTS",
]
