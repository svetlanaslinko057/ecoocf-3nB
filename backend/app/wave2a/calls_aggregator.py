"""Wave 2A — Calls Aggregator
=================================

Pure data-layer helpers used by ``app/wave2a/router.py``.

Main job:
    Given a customer id + filters + actor (caller), return the *normalized*
    list of telephony calls that belong to this customer, regardless of which
    foreign key Ringostat used to attach them (customer_id / lead_id /
    deal_id / phone / secondaryPhone).

Design notes
------------
*   We **don't** mutate or re-analyze anything here. Existing
    ``ringostat_calls.ai_analysis`` is passed through as-is.
*   ACL is enforced at *output filter* level (post-query) on top of a Mongo
    `$or` that may match calls owned by *any* manager. This is intentional:
    the same aggregation can be used by admin/team_lead/manager with one
    code path and predictable per-record filtering.
*   All timestamps are normalized to ISO-8601 strings in the response.
*   Each call carries ``matchedBy[]`` — the set of customer keys that
    produced the match (``customer_id``, ``lead_id``, ``deal_id``,
    ``phone:primary``, ``phone:secondary``, ``phone:lead``). This powers the
    admin "why did this call match" troubleshooting screen.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("bibi.wave2a.calls")

_ADMIN_ROLES = {"owner", "master_admin", "admin"}
_TEAM_LEAD_ROLES = {"team_lead", "lead", "teamlead"}
_MANAGER_ROLES = {"manager", "sales", "sales_manager"}


# ── Time + value helpers ────────────────────────────────────────────────────

def _to_iso(value: Any) -> Optional[str]:
    """Convert datetime / iso-string / None to ISO-8601 string (or None)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _started_at(call: Dict[str, Any]) -> Optional[datetime]:
    for key in ("started_at", "created_at", "answered_at", "ended_at", "updated_at"):
        v = call.get(key)
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        iso = _parse_iso(v if isinstance(v, str) else None)
        if iso:
            return iso
    return None


def _normalize_phone(p: Any) -> str:
    if not p:
        return ""
    return "".join(ch for ch in str(p) if ch.isdigit() or ch == "+")


# ── Identifier resolution ───────────────────────────────────────────────────

@dataclass
class CustomerIdentifiers:
    """Everything we need to (a) build the Mongo query, (b) attribute matches.

    Each ``phones_*`` set keeps both the raw literal AND the normalised digits
    form so a Mongo equality match works regardless of formatting.
    """
    customer:        Dict[str, Any]
    customer_ids:    Set[str] = field(default_factory=set)   # legacy + canonical
    lead_ids:        Set[str] = field(default_factory=set)
    deal_ids:        Set[str] = field(default_factory=set)
    phones_primary:  Set[str] = field(default_factory=set)
    phones_secondary: Set[str] = field(default_factory=set)
    phones_lead:     Set[str] = field(default_factory=set)
    lead_phone_map:  Dict[str, str] = field(default_factory=dict)   # phone -> lead_id

    @property
    def all_phones(self) -> Set[str]:
        return self.phones_primary | self.phones_secondary | self.phones_lead

    def to_sources(self) -> Dict[str, Any]:
        return {
            "leadIds":          sorted(self.lead_ids),
            "dealIds":          sorted(self.deal_ids),
            "phonesPrimary":    sorted(self.phones_primary),
            "phonesSecondary":  sorted(self.phones_secondary),
            "phonesLead":       sorted(self.phones_lead),
            # back-compat alias used by the v1 UI
            "phones":           sorted(self.all_phones),
        }


async def _resolve_customer_identifiers(db, customer_id: str) -> Optional[CustomerIdentifiers]:
    cust = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not cust:
        cust = await db.customers.find_one({"_id": customer_id})
    if not cust:
        return None

    ids = CustomerIdentifiers(customer=cust)
    canonical = cust.get("id") or cust.get("_id")
    if canonical:
        ids.customer_ids.add(str(canonical))
    ids.customer_ids.add(str(customer_id))

    # ── primary phone ────────────────────────────────────────────────────
    primary = cust.get("phone")
    if isinstance(primary, str) and primary.strip():
        ids.phones_primary.add(primary.strip())
        n = _normalize_phone(primary)
        if n:
            ids.phones_primary.add(n)

    # ── secondary phones (single field + alternates + array) ─────────────
    for key in ("secondaryPhone", "phone_secondary", "phone2", "altPhone"):
        val = cust.get(key)
        if isinstance(val, str) and val.strip():
            ids.phones_secondary.add(val.strip())
            n = _normalize_phone(val)
            if n:
                ids.phones_secondary.add(n)
    phones_field = cust.get("phones")
    if isinstance(phones_field, (list, tuple)):
        for p in phones_field:
            if isinstance(p, str) and p.strip():
                if p.strip() in ids.phones_primary:
                    continue
                ids.phones_secondary.add(p.strip())
                n = _normalize_phone(p)
                if n:
                    ids.phones_secondary.add(n)

    # ── leads of this customer ───────────────────────────────────────────
    lead_filter = {
        "$or": [
            {"customerId": str(canonical or customer_id)},
            {"customer_id": str(canonical or customer_id)},
        ]
    }
    try:
        async for lead in db.leads.find(lead_filter, {"_id": 1, "id": 1, "phone": 1}):
            lid = str(lead.get("id") or lead.get("_id") or "")
            if lid:
                ids.lead_ids.add(lid)
            lp = lead.get("phone")
            if isinstance(lp, str) and lp.strip():
                raw = lp.strip()
                norm = _normalize_phone(raw)
                # only add as lead-phone if not already a customer phone (avoid double-attribution)
                if raw not in ids.phones_primary and raw not in ids.phones_secondary:
                    ids.phones_lead.add(raw)
                    if lid:
                        ids.lead_phone_map[raw] = lid
                if norm and norm not in ids.phones_primary and norm not in ids.phones_secondary:
                    ids.phones_lead.add(norm)
                    if lid:
                        ids.lead_phone_map[norm] = lid
    except Exception as e:
        logger.warning("[w2a] lead lookup failed for cust=%s: %s", customer_id, e)

    # ── deals of this customer ───────────────────────────────────────────
    deal_filter = {
        "$or": [
            {"customerId": str(canonical or customer_id)},
            {"customer_id": str(canonical or customer_id)},
        ]
    }
    if ids.lead_ids:
        deal_filter["$or"].extend([
            {"lead_id": {"$in": list(ids.lead_ids)}},
            {"leadId": {"$in": list(ids.lead_ids)}},
        ])
    try:
        async for deal in db.deals.find(deal_filter, {"_id": 1, "id": 1}):
            did = str(deal.get("id") or deal.get("_id") or "")
            if did:
                ids.deal_ids.add(did)
    except Exception as e:
        logger.warning("[w2a] deal lookup failed for cust=%s: %s", customer_id, e)

    return ids


# ── Mongo query builder ─────────────────────────────────────────────────────

def _build_calls_filter(ids: CustomerIdentifiers) -> Dict[str, Any]:
    or_clauses: List[Dict[str, Any]] = []
    cids = [c for c in ids.customer_ids if c]
    if cids:
        or_clauses.append({"customer_id": {"$in": cids}})
        or_clauses.append({"customerId":  {"$in": cids}})
    li = list(ids.lead_ids)
    if li:
        or_clauses.append({"lead_id": {"$in": li}})
        or_clauses.append({"leadId":  {"$in": li}})
    di = list(ids.deal_ids)
    if di:
        or_clauses.append({"deal_id": {"$in": di}})
        or_clauses.append({"dealId":  {"$in": di}})
    ph = list(ids.all_phones)
    if ph:
        or_clauses.append({"from": {"$in": ph}})
        or_clauses.append({"to":   {"$in": ph}})
        or_clauses.append({"from_number": {"$in": ph}})
        or_clauses.append({"to_number":   {"$in": ph}})
    if not or_clauses:
        # No identifiers at all — guarantee empty result rather than $or:[].
        return {"_id": {"$exists": False, "$eq": "__never__"}}
    return {"$or": or_clauses}


# ── Per-call match attribution ──────────────────────────────────────────────

def _compute_match_reasons(call: Dict[str, Any], ids: CustomerIdentifiers) -> List[Dict[str, Any]]:
    """Return a list of structured reasons explaining why this call matched.

    Each entry: {key, label, value, side?}
      * key       — machine tag (customer_id / lead_id / deal_id / phone_primary / phone_secondary / phone_lead)
      * label     — short user-readable label
      * value     — the actual matched value (e.g. the phone number, lead id, etc.)
      * side      — for phone matches, "from" or "to" (which side of the call matched)
    """
    reasons: List[Dict[str, Any]] = []

    # ── id-based matches ────────────────────────────────────────────────
    call_cid = str(call.get("customer_id") or call.get("customerId") or "")
    if call_cid and call_cid in ids.customer_ids:
        reasons.append({"key": "customer_id", "label": "customer_id", "value": call_cid})

    call_lid = str(call.get("lead_id") or call.get("leadId") or "")
    if call_lid and call_lid in ids.lead_ids:
        reasons.append({"key": "lead_id", "label": "lead_id", "value": call_lid})

    call_did = str(call.get("deal_id") or call.get("dealId") or "")
    if call_did and call_did in ids.deal_ids:
        reasons.append({"key": "deal_id", "label": "deal_id", "value": call_did})

    # ── phone-based matches ─────────────────────────────────────────────
    for side_key, side_label in (("from", "from"), ("to", "to"),
                                 ("from_number", "from"), ("to_number", "to")):
        v = call.get(side_key)
        if not v or not isinstance(v, str):
            continue
        raw = v.strip()
        norm = _normalize_phone(raw)
        candidates = {raw, norm} - {""}
        if candidates & ids.phones_primary:
            reasons.append({"key": "phone_primary", "label": "phone (primary)",
                            "value": raw, "side": side_label})
        elif candidates & ids.phones_secondary:
            reasons.append({"key": "phone_secondary", "label": "phone (secondary)",
                            "value": raw, "side": side_label})
        elif candidates & ids.phones_lead:
            lead_id = ids.lead_phone_map.get(raw) or ids.lead_phone_map.get(norm)
            entry = {"key": "phone_lead", "label": "phone (lead)",
                     "value": raw, "side": side_label}
            if lead_id:
                entry["leadId"] = lead_id
            reasons.append(entry)

    # Deduplicate identical entries (e.g. both raw + norm matched same bucket
    # for both sides — keep first occurrence per (key, value, side)).
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in reasons:
        sig = (r.get("key"), r.get("value"), r.get("side"))
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(r)
    return deduped


# ── ACL ────────────────────────────────────────────────────────────────────

async def _team_manager_ids(db, team_id: Optional[str]) -> Set[str]:
    if not team_id:
        return set()
    cursor = db.staff.find({"teamId": team_id}, {"_id": 1, "id": 1})
    ids: Set[str] = set()
    async for s in cursor:
        sid = s.get("id") or s.get("_id")
        if sid:
            ids.add(str(sid))
    return ids


async def _filter_by_acl(
    db, calls: List[Dict[str, Any]], actor: Dict[str, Any]
) -> List[Dict[str, Any]]:
    role = (actor.get("role") or "").lower()
    if role in _ADMIN_ROLES:
        return calls
    if role in _TEAM_LEAD_ROLES:
        team_id = actor.get("teamId")
        team_ids = await _team_manager_ids(db, team_id)
        own_id = str(actor.get("id") or "")
        if own_id:
            team_ids.add(own_id)
        return [
            c for c in calls
            if not c.get("manager_id") or str(c.get("manager_id")) in team_ids
        ]
    if role in _MANAGER_ROLES:
        own_id = str(actor.get("id") or "")
        if not own_id:
            return []
        return [c for c in calls if str(c.get("manager_id") or "") == own_id]
    return []


# ── Manager name resolution (batch) ─────────────────────────────────────────

async def _resolve_manager_names(db, ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    cursor = db.staff.find(
        {"$or": [
            {"id": {"$in": list(ids)}},
            {"_id": {"$in": list(ids)}},
        ]},
        {"_id": 1, "id": 1, "name": 1, "email": 1, "role": 1},
    )
    result: Dict[str, Dict[str, Any]] = {}
    async for s in cursor:
        sid = str(s.get("id") or s.get("_id") or "")
        if not sid:
            continue
        result[sid] = {
            "id": sid,
            "name": s.get("name") or s.get("email") or sid,
            "email": s.get("email"),
            "role": s.get("role"),
        }
    return result


# ── Normalization ──────────────────────────────────────────────────────────

def _normalize_call(c: Dict[str, Any], managers: Dict[str, Dict[str, Any]],
                    ids: CustomerIdentifiers) -> Dict[str, Any]:
    mid = str(c.get("manager_id") or "")
    manager = managers.get(mid)
    if not manager and mid:
        manager = {"id": mid, "name": mid}
    if not manager:
        manager = None

    started = _started_at(c)
    rec_url = (c.get("recording_url") or "").strip()
    ai = c.get("ai_analysis") or {}
    if not isinstance(ai, dict):
        ai = {}

    cid = c.get("call_id") or str(c.get("_id") or "")
    reasons = _compute_match_reasons(c, ids)

    return {
        "id":          cid,
        "_id":         str(c.get("_id")) if c.get("_id") else None,
        "callId":      c.get("call_id"),
        "startedAt":   _to_iso(started),
        "createdAt":   _to_iso(c.get("created_at")),
        "endedAt":     _to_iso(c.get("ended_at")),
        "direction":   (c.get("direction") or "").lower() or "unknown",
        "status":      (c.get("status") or "").upper() or "UNKNOWN",
        "duration":    int(c.get("duration") or 0),
        "fromNumber":  c.get("from") or c.get("from_number") or "",
        "toNumber":    c.get("to") or c.get("to_number") or "",
        "manager":     manager,
        "outcome":     c.get("outcome"),
        "outcomeNote": c.get("outcome_note"),
        "recordingAvailable": bool(rec_url),
        "aiAnalysis":  {
            "intent":           ai.get("intent"),
            "objection":        ai.get("objection"),
            "suggestedOutcome": ai.get("suggested_outcome"),
            "interestLevel":    ai.get("interest_level"),
            "nextAction":       ai.get("next_action"),
            "hasAnalysis":      bool(ai),
        },
        "meta": {
            "leadId":     c.get("lead_id") or c.get("leadId"),
            "dealId":     c.get("deal_id") or c.get("dealId"),
            "customerId": c.get("customer_id") or c.get("customerId"),
            "utmSource":   c.get("utm_source"),
            "utmCampaign": c.get("utm_campaign"),
            "utmMedium":   c.get("utm_medium"),
        },
        # Wave 2A troubleshooting: WHY did this call match this customer?
        "matchedBy":      [r["key"] for r in reasons],
        "matchedReasons": reasons,
    }


# ── Public API ─────────────────────────────────────────────────────────────

async def aggregate_customer_calls(
    db,
    customer_id: str,
    filters: Dict[str, Any],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    """Return ``{ success, customer, total, calls, sources }``.

    ``filters``: dateFrom, dateTo (ISO), managerId, direction, withRecording,
                 limit (1..500), skip (>=0).
    """
    ids = await _resolve_customer_identifiers(db, customer_id)
    if ids is None:
        return {"success": False, "error": "Customer not found", "status": 404}

    base = _build_calls_filter(ids)

    extra: Dict[str, Any] = {}
    direction = (filters.get("direction") or "").lower()
    if direction in ("inbound", "outbound"):
        extra["direction"] = {"$regex": f"^{direction}$", "$options": "i"}
    mgr = filters.get("managerId")
    if mgr:
        extra["manager_id"] = mgr
    if filters.get("withRecording") is True:
        extra["recording_url"] = {"$exists": True, "$nin": [None, ""]}

    query = {"$and": [base, extra]} if extra else base

    limit = min(int(filters.get("limit") or 200), 500)
    skip = max(int(filters.get("skip") or 0), 0)

    cursor = (db.ringostat_calls
              .find(query)
              .sort([("started_at", -1), ("created_at", -1)])
              .skip(skip).limit(limit))
    raw = await cursor.to_list(length=limit)

    # Date-range filter (applied in Python to handle missing started_at)
    df = _parse_iso(filters.get("dateFrom"))
    dt = _parse_iso(filters.get("dateTo"))
    if df or dt:
        kept: List[Dict[str, Any]] = []
        for c in raw:
            s = _started_at(c)
            if s is None:
                continue
            if df and s < df:
                continue
            if dt and s > dt:
                continue
            kept.append(c)
        raw = kept

    permitted = await _filter_by_acl(db, raw, actor)

    mgr_ids = {str(c.get("manager_id") or "") for c in permitted if c.get("manager_id")}
    managers = await _resolve_manager_names(db, mgr_ids)

    normalized = [_normalize_call(c, managers, ids) for c in permitted]

    return {
        "success": True,
        "customer": {
            "id":           ids.customer.get("id") or str(ids.customer.get("_id") or ""),
            "name":         ids.customer.get("name"),
            "phone":        ids.customer.get("phone"),
            "secondaryPhone": ids.customer.get("secondaryPhone")
                              or ids.customer.get("phone_secondary"),
        },
        "total":   len(normalized),
        "calls":   normalized,
        "sources": ids.to_sources(),
    }


async def get_call_for_recording(
    db, call_id: str, actor: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    call = await db.ringostat_calls.find_one({
        "$or": [{"call_id": call_id}, {"_id": call_id}]
    })
    if not call:
        return None
    permitted = await _filter_by_acl(db, [call], actor)
    return permitted[0] if permitted else None


async def build_diagnostics(
    db, customer_id: str, actor: Dict[str, Any]
) -> Dict[str, Any]:
    """Admin diagnostic dump for one customer.

    Returns:
        identifiers   — all keys the system uses to find this customer's calls
        callCount     — totals (all + per matched key)
        sample        — up to 50 most recent calls with full reason breakdown
        unmatchedHint — calls in ringostat_calls that share *some* identifier
                        but were skipped by ACL or by some mismatch
    """
    ids = await _resolve_customer_identifiers(db, customer_id)
    if ids is None:
        return {"success": False, "error": "Customer not found", "status": 404}

    base = _build_calls_filter(ids)
    raw_all = await db.ringostat_calls.find(base).sort(
        [("started_at", -1), ("created_at", -1)]
    ).limit(500).to_list(length=500)

    permitted = await _filter_by_acl(db, raw_all, actor)

    # Per-key counters
    counter_keys = (
        "customer_id", "lead_id", "deal_id",
        "phone_primary", "phone_secondary", "phone_lead",
    )
    counts: Dict[str, int] = {k: 0 for k in counter_keys}
    counts_total = 0
    sample: List[Dict[str, Any]] = []

    for c in raw_all:
        reasons = _compute_match_reasons(c, ids)
        for r in reasons:
            counts[r["key"]] = counts.get(r["key"], 0) + 1
        counts_total += 1
        if len(sample) < 50:
            sample.append({
                "callId":     c.get("call_id") or str(c.get("_id") or ""),
                "direction":  (c.get("direction") or "").lower(),
                "status":     (c.get("status") or "").upper(),
                "duration":   int(c.get("duration") or 0),
                "from":       c.get("from") or c.get("from_number") or "",
                "to":         c.get("to") or c.get("to_number") or "",
                "managerId":  c.get("manager_id"),
                "startedAt":  _to_iso(_started_at(c)),
                "matchedBy":  [r["key"] for r in reasons],
                "reasons":    reasons,
                "permitted":  c in permitted,
            })

    return {
        "success": True,
        "customer": {
            "id":             ids.customer.get("id") or str(ids.customer.get("_id") or ""),
            "name":           ids.customer.get("name"),
            "phone":          ids.customer.get("phone"),
            "secondaryPhone": ids.customer.get("secondaryPhone")
                              or ids.customer.get("phone_secondary"),
        },
        "identifiers": {
            "customerIds":    sorted(ids.customer_ids),
            "leadIds":        sorted(ids.lead_ids),
            "dealIds":        sorted(ids.deal_ids),
            "phonesPrimary":  sorted(ids.phones_primary),
            "phonesSecondary": sorted(ids.phones_secondary),
            "phonesLead":     sorted(ids.phones_lead),
            "leadPhoneMap":   dict(ids.lead_phone_map),
        },
        "counts": {
            "matched":   counts_total,
            "permitted": len(permitted),
            "perKey":    counts,
            "withRecording": sum(1 for c in raw_all if (c.get("recording_url") or "").strip()),
            "missing": {
                # rough breakdown of common gaps
                "withoutManager":  sum(1 for c in raw_all if not c.get("manager_id")),
                "withoutOutcome":  sum(1 for c in raw_all if not c.get("outcome")),
                "withoutAI":       sum(1 for c in raw_all if not c.get("ai_analysis")),
            },
        },
        "sample": sample,
    }


async def ensure_indexes(db) -> None:
    """Idempotent index ensure for ringostat_calls (read paths)."""
    try:
        await db.ringostat_calls.create_index("call_id")
        await db.ringostat_calls.create_index("lead_id")
        await db.ringostat_calls.create_index("deal_id")
        await db.ringostat_calls.create_index("customer_id")
        await db.ringostat_calls.create_index("manager_id")
        await db.ringostat_calls.create_index([("started_at", -1)])
        await db.ringostat_calls.create_index([("created_at", -1)])
        await db.ringostat_calls.create_index("from")
        await db.ringostat_calls.create_index("to")
        logger.info("[wave2a] ringostat_calls indexes ensured")
    except Exception as e:
        logger.warning("[wave2a] index ensure failed: %s", e)
