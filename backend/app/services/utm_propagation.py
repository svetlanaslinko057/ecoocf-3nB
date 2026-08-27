"""
UTM Propagation Service
=========================

Single source of truth for propagating UTM marketing attribution through
the BIBI Cars business graph:

    Lead --> Customer --> Invoice --> Order --> Deposit / Sale

The ``utm`` payload itself is a flat dict with five canonical keys plus
a ``source`` (lead-level marketing source label). Anything else is
ignored. Missing keys default to empty strings so downstream filtering
stays simple (``$eq: ""`` matches empty/missing).

Usage from any service:

    from app.services.utm_propagation import extract_utm, merge_utm

    target_doc["utm"] = await extract_utm(
        db,
        customer_id=customer.get("id"),
        lead_id=lead.get("id"),
    )

The public verbs are:

  * ``UTM_KEYS``             - the canonical key tuple.
  * ``empty_utm()``          - returns the canonical zero dict.
  * ``pick_utm(src)``        - extracts UTM-shape from an arbitrary dict.
  * ``merge_utm(a, b)``      - merges two UTM dicts (b takes priority).
  * ``extract_utm(db, ...)`` - async resolver across lead/customer.
  * ``stamp_utm(doc, utm)``  - mutate-in-place + return doc, no-op if doc
                               already has a non-empty utm_source.

All functions are pure-ish and pyright-friendly.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

UTM_KEYS: tuple[str, ...] = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
)

_SOURCE_KEYS: tuple[str, ...] = ("source", "lead_source", "leadSource")


def empty_utm() -> Dict[str, str]:
    """Return canonical empty UTM dict with all five keys + lead_source."""
    out: Dict[str, str] = {k: "" for k in UTM_KEYS}
    out["lead_source"] = ""
    return out


def pick_utm(src: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Extract UTM shape from any dict-like object.

    Accepts both flat keys (``utm_source``) and nested (``utm: {...}``).
    Always returns the canonical 6-key shape (utm_source, utm_medium,
    utm_campaign, utm_content, utm_term, lead_source).
    """
    out = empty_utm()
    if not src or not isinstance(src, Mapping):
        return out

    # Nested utm sub-object takes priority over flat keys.
    nested = src.get("utm") if isinstance(src.get("utm"), Mapping) else None

    for k in UTM_KEYS:
        if nested and nested.get(k):
            out[k] = str(nested.get(k) or "").strip()
        elif src.get(k):
            out[k] = str(src.get(k) or "").strip()

    # Lead source (free-form): first non-empty candidate wins.
    for sk in _SOURCE_KEYS:
        v = (src.get(sk) or (nested.get(sk) if nested else "")) if nested else src.get(sk)
        if v:
            out["lead_source"] = str(v).strip()
            break

    return out


def merge_utm(a: Mapping[str, Any], b: Mapping[str, Any]) -> Dict[str, str]:
    """Merge two UTM dicts: ``b`` wins on non-empty values, otherwise ``a``.

    Useful when a customer already has UTM and we want to fall back to
    the lead's UTM only for missing keys.
    """
    pa = pick_utm(a)
    pb = pick_utm(b)
    out: Dict[str, str] = {}
    for k in (*UTM_KEYS, "lead_source"):
        out[k] = pb.get(k) or pa.get(k) or ""
    return out


async def extract_utm(
    db: Any,
    *,
    customer_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    customer_doc: Optional[Mapping[str, Any]] = None,
    lead_doc: Optional[Mapping[str, Any]] = None,
) -> Dict[str, str]:
    """Resolve UTM by looking up customer first, then lead, then merging.

    Resolution order (first non-empty wins per key):
      1. ``customer_doc`` if provided, else lookup by ``customer_id``.
      2. ``lead_doc`` if provided, else lookup by ``lead_id``.
      3. If only ``customer_id`` provided, try the most recent lead
         matching the customer's email/phone (best-effort).
    """
    cust = customer_doc
    if cust is None and customer_id and db is not None:
        cust = await db.customers.find_one({"id": customer_id}, {"_id": 0}) or {}
    cust_utm = pick_utm(cust or {})

    lead = lead_doc
    if lead is None and lead_id and db is not None:
        lead = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}
    if lead is None and customer_id and db is not None and cust:
        # best-effort: most recent lead for this customer
        or_clauses: list[dict] = [
            {"customerId": customer_id},
            {"customer_id": customer_id},
        ]
        if cust.get("email"):
            or_clauses.append({"email": cust["email"]})
        if cust.get("phone"):
            or_clauses.append({"phone": cust["phone"]})
        try:
            lead = await db.leads.find_one({"$or": or_clauses}, {"_id": 0}, sort=[("created_at", -1)]) or {}
        except Exception:
            lead = {}
    lead_utm = pick_utm(lead or {})

    # Customer takes priority; lead fills missing keys.
    return merge_utm(lead_utm, cust_utm)


def stamp_utm(doc: Dict[str, Any], utm: Mapping[str, Any]) -> Dict[str, Any]:
    """Mutate ``doc`` in-place: add flat utm_* fields if missing.

    No-op if ``doc`` already has a non-empty ``utm_source`` flat field
    OR a non-empty nested ``utm.utm_source`` (the doc is considered
    UTM-stamped already).

    Always returns ``doc`` (for chaining).
    """
    if doc.get("utm_source"):
        return doc
    nested = doc.get("utm")
    if isinstance(nested, Mapping) and nested.get("utm_source"):
        return doc

    pu = pick_utm(utm)
    for k in UTM_KEYS:
        doc.setdefault(k, pu.get(k, ""))
    if pu.get("lead_source"):
        doc.setdefault("lead_source", pu["lead_source"])
    # Also nest for convenience of analytics consumers.
    doc.setdefault("utm", {k: pu.get(k, "") for k in UTM_KEYS})
    return doc
