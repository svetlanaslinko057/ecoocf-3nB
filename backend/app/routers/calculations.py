"""calculations: immutable financial-engine snapshots + role-aware projection.

OWNER:  calculations-domain
SOURCE: extracted from legacy server.py on 2026-05-17
WAVE:   1

================================================================================
                          !!! ALL BRIDGES RETIRED !!!
Phase 5.5/B — 2026-05-19 — completes the qualified-access retirement
for this router. The previous `import server` line has been REMOVED.
All non-db symbols that used to be reached via ``server.X`` qualified
access are now sourced from their canonical homes:

  * ``logger``                — module-local ``logger = logging.getLogger("bibi.calculations")``
                                (retires the single ``server.logger.warning(...)``
                                site at line ~733; companion to 5.5/A
                                which retired the same shape in payments.py)
  * ``calculator_calculate``  — ``from app.services.calculator import calculator_calculate``
  * ``_calculate_korea``      — ``from app.services.calculator import _calculate_korea``

Phase 5.4 / C-4i — the qualified ``server.db.X`` access pattern was
retired earlier; all Mongo collection access flows through ``get_db().X``
via the canonical ``app.core.db_runtime`` accessor (this remains the
correct pattern; ``get_db()`` is the only allowed entry point to the
live Motor handle).

Historical bridge trail (for changelog clarity):
  - Pre-C-4i:  ``import server`` + ``server.db.X``  (~23 sites) — RETIRED C-4i
  - Pre-5.5/B: ``import server`` + ``server.logger`` (1 site)    — RETIRED 5.5/B
  - Pre-5.5/B: ``import server`` + ``server.calculator_calculate``
                                                    (1 site)     — RETIRED 5.5/B
  - Pre-5.5/B: ``import server`` + ``server._calculate_korea``
                                                    (1 site)     — RETIRED 5.5/B
  - Post-5.5/B: NO ``import server`` line in this router. Zero
                ``server.X`` qualified-access sites.

DO NOT replicate the ``import server`` pattern in NEW routers — doing
so creates a "distributed god-file". The canonical pattern is:
  * direct imports from the symbol's canonical home (service / utility
    module) for behaviour
  * ``from app.core.db_runtime import get_db`` for Mongo access
  * module-local ``logger = logging.getLogger("bibi.<domain>")``
================================================================================

This module owns:
  * POST   /api/calculations                                     create snapshot
  * GET    /api/calculations/{calc_id}                           get one
  * GET    /api/calculations                                     list (filtered)
  * POST   /api/calculations/{calc_id}/clone                     new version
  * PATCH  /api/calculations/{calc_id}/status                    state-machine transition
  * PATCH  /api/calculations/{calc_id}/overrides                 set manager overrides
  * DELETE /api/calculations/{calc_id}                           soft archive
  * GET    /api/calculations/{calc_id}/comments                  list comments
  * POST   /api/calculations/{calc_id}/comments                  post comment
  * GET    /api/calculations/{calc_id}/timeline                  aggregated timeline
  * GET    /api/calculations-compare                             side-by-side delta
  * GET    /api/public/calculations/share/{share_token}          public share read
  * POST   /api/public/calculations/share/{share_token}/approve  client approval

P1 EXTRACTION DISCIPLINE: this is a mechanical move-only refactor.
No business logic, response shapes, status codes or DB fields were changed.

Lifecycle / status transitions:
    draft -> sent_to_client -> approved_by_client -> auction_mode -> final -> archived
                          \\-> archived (skip if rejected)

Versioning: POST .../clone bumps `version` per deal_id, parent_id links back.

Visibility taxonomy (set on each breakdown row):
    "client"     - shown to anonymous & customer
    "manager"    - shown to manager / teamlead / admin
    "admin_only" - shown to teamlead / admin (margins, hidden fees, damage coeffs)
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from security import (
    is_admin,
    is_master_admin,
    is_staff,
    optional_user,
    require_user,
)

# Phase 5.4 / C-4i — db_runtime accessor (module-level function reference).
# Only the `get_db` CALLABLE is imported at module-load time. Every
# `get_db()` call resolves the live Motor handle, preserving the
# call-time semantics of the legacy ``server.db.X`` qualified access.
from app.core.db_runtime import get_db  # noqa: E402 (C-4i: qualified-import → accessor)

# Phase 5.5/B — Calculator engines now have a canonical home in
# ``app/services/calculator.py``. Consumers import them directly instead
# of going through the (now-retired) ``server.X`` qualified-access shape.
from app.services.calculator import (  # noqa: E402
    _calculate_korea,
    calculator_calculate,
)

# Phase 5.5/B — module-local logger. Replaces the single
# ``server.logger.warning(...)`` qualified-access site (line ~733,
# calc-approve notification fail-soft branch). Message strings, levels,
# and arguments are byte-identical to the pre-retirement source.
logger = logging.getLogger("bibi.calculations")

router = APIRouter(tags=["calculations"])


# ════════════════════════════════════════════════════════════════════════════
# Constants + pure helpers (cohesive with calculations domain)
# ════════════════════════════════════════════════════════════════════════════

CALC_STATUS_FLOW = {
    "draft":              {"sent_to_client", "auction_mode", "archived"},
    "sent_to_client":     {"approved_by_client", "draft", "archived"},
    "approved_by_client": {"auction_mode", "final", "archived"},
    "auction_mode":       {"final", "archived"},
    "final":              {"archived"},
    "archived":           set(),
}

CALC_VISIBILITY_LEVELS = ("client", "manager", "admin_only")

# Breakdown keys that are informational/derivation rows only -- they do NOT
# contribute to the grand total (which is computed from explicit sub-totals
# inside the engine: calc1+calc2+calc3 for Korea, price+auctionTotal+deliveryTotal
# for USA). Including them in a sum-based total would double-count.
CALC_INFO_ONLY_KEYS = frozenset({
    "customsBase",
    "declaredValue",
})


def _calc_visibility_for(user: Optional[dict]) -> set:
    """Return the set of visibility levels a given user is allowed to see.

    Per P2.7 spec (Teamlead control): team_lead must see hidden margins,
    manager discounts, overrides AND profitability -- same view as admin.
    Only `manager` / `moderator` get the mid-tier (client + manager rows,
    no admin_only payload and no profitability widget).
    """
    if is_admin(user) or is_master_admin(user):
        return {"client", "manager", "admin_only"}
    role = ((user or {}).get("role") or "").lower()
    if role in {"team_lead", "teamlead", "team-lead"}:
        return {"client", "manager", "admin_only"}
    if is_staff(user):
        return {"client", "manager"}
    return {"client"}


def _apply_overrides_to_breakdown(breakdown: List[Dict[str, Any]], overrides: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply per-row overrides to a copy of the breakdown.

    Override schema:
      {
        "rows": { "<row_key>": <new_value> },              # numeric override
        "hidden_rows": [ "<row_key>", ... ],               # hide row from output
        "discount": <number>,                              # global discount line
        "added_rows": [ { "key", "label", "value", "visibility"? } ]
      }
    """
    if not overrides:
        return [dict(r) for r in breakdown]
    row_overrides = (overrides.get("rows") or {})
    hidden = set(overrides.get("hidden_rows") or [])
    added = overrides.get("added_rows") or []
    out: List[Dict[str, Any]] = []
    for row in breakdown:
        k = row.get("key")
        if k in hidden:
            continue
        new_row = dict(row)
        if k in row_overrides:
            try:
                new_row["value"] = round(float(row_overrides[k]), 2)
                new_row["overridden"] = True
            except (TypeError, ValueError):
                pass
        out.append(new_row)
    for ar in added:
        out.append({
            "key":        ar.get("key") or f"custom_{len(out)}",
            "label":      ar.get("label") or "Custom Line",
            "value":      round(float(ar.get("value") or 0), 2),
            "currency":   ar.get("currency") or "USD",
            "visibility": ar.get("visibility") or "manager",
            "custom":     True,
        })
    disc = overrides.get("discount")
    if disc:
        try:
            out.append({
                "key": "managerDiscount",
                "label": "Manager Discount",
                "value": -round(float(disc), 2),
                "currency": "USD",
                "visibility": "client",
                "category": "discount",
                "custom": True,
            })
        except (TypeError, ValueError):
            pass
    return out


def _filter_breakdown_by_role(breakdown: List[Dict[str, Any]], allowed: set) -> List[Dict[str, Any]]:
    return [r for r in breakdown if (r.get("visibility") or "client") in allowed]


def _apply_overrides_to_total(engine_total: float, original_breakdown: List[Dict[str, Any]], overrides: Dict[str, Any]) -> float:
    """Compute the post-override total without re-summing the entire breakdown.

    Strategy: start from the engine-computed `engine_total` (immutable, trustworthy),
    then add/subtract only the deltas introduced by the override map.
    """
    if not overrides:
        return engine_total
    total = float(engine_total or 0)
    by_key = {r.get("key"): r for r in original_breakdown}
    # 1) Row value overrides -> add (new - original) per row that contributes
    for k, new_v in (overrides.get("rows") or {}).items():
        if k in CALC_INFO_ONLY_KEYS:
            continue
        orig = float((by_key.get(k) or {}).get("value") or 0)
        try:
            total += float(new_v) - orig
        except (TypeError, ValueError):
            pass
    # 2) Hidden rows -> subtract their original value (informational rows are no-op)
    for k in (overrides.get("hidden_rows") or []):
        if k in CALC_INFO_ONLY_KEYS:
            continue
        orig = float((by_key.get(k) or {}).get("value") or 0)
        total -= orig
    # 3) Added rows -> add their value
    for ar in (overrides.get("added_rows") or []):
        try:
            total += float(ar.get("value") or 0)
        except (TypeError, ValueError):
            pass
    # 4) Discount -> subtract
    try:
        total -= float(overrides.get("discount") or 0)
    except (TypeError, ValueError):
        pass
    return round(total, 2)


def _recompute_total_from_breakdown(breakdown: List[Dict[str, Any]], origin: str, vehicle_price: float, auction_total: float) -> float:
    """Legacy helper retained for callers -- sums breakdown skipping info-only
    keys; only used as a sanity fallback when engine total is missing."""
    total = 0.0
    has_vehicle_row = any(r.get("key") == "vehiclePrice" for r in breakdown)
    has_auction_rows = any((r.get("key") or "").startswith("auction") for r in breakdown)
    for r in breakdown:
        if r.get("key") in CALC_INFO_ONLY_KEYS:
            continue
        try:
            total += float(r.get("value") or 0)
        except (TypeError, ValueError):
            pass
    if not has_vehicle_row:
        total += float(vehicle_price or 0)
    if not has_auction_rows:
        total += float(auction_total or 0)
    return round(total, 2)


async def _fetch_calc_doc(calc_id: str) -> Dict[str, Any]:
    doc = await get_db().calculations.find_one({"id": calc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return doc


def _project_calc_for_user(doc: Dict[str, Any], user: Optional[dict]) -> Dict[str, Any]:
    """Apply overrides + filter breakdown to the user's visibility level."""
    allowed = _calc_visibility_for(user)
    breakdown = doc.get("breakdown") or []
    overrides = doc.get("overrides") or {}
    outputs = dict(doc.get("outputs") or {})

    # Apply overrides on a copy of the full breakdown first, then role-filter
    # the result. The total is computed from the engine total + override deltas
    # (NOT by re-summing the breakdown -- that would double-count info-only rows).
    breakdown_after = _apply_overrides_to_breakdown(breakdown, overrides)
    breakdown_filtered = _filter_breakdown_by_role(breakdown_after, allowed)
    engine_total = float(outputs.get("total") or 0)
    new_total = _apply_overrides_to_total(engine_total, breakdown, overrides)
    outputs["total"] = new_total
    if outputs.get("fxUsdToEur"):
        outputs["totalEur"] = round(new_total * float(outputs["fxUsdToEur"]), 2)

    projected = dict(doc)
    projected["breakdown"] = breakdown_filtered
    projected["outputs"] = outputs
    projected["viewer_role"] = "admin" if "admin_only" in allowed else ("manager" if "manager" in allowed else "client")

    # -- Profitability block (admin / teamlead only) --
    # Computed from the FULL post-override breakdown (no visibility filter)
    # so admins see the true picture even with hidden rows.
    if "admin_only" in allowed:
        revenue = 0.0
        true_cost = 0.0
        tax = 0.0
        discount_amount = 0.0
        for row in breakdown_after:
            cat = (row.get("category") or "").lower()
            try:
                v = float(row.get("value") or 0)
            except (TypeError, ValueError):
                v = 0.0
            if cat == "info":
                continue
            elif cat == "revenue":
                revenue += v
            elif cat == "tax":
                tax += v
            elif cat == "discount":
                discount_amount += v   # already negative
            elif cat == "cost":
                true_cost += v
            else:
                true_cost += v
        # Manager discount goes against revenue (BIBI gives up its own margin)
        net_revenue = revenue + discount_amount   # discount_amount is negative
        margin_pct = (net_revenue / new_total * 100.0) if new_total > 0 else 0.0
        projected["profitability"] = {
            "revenue":            round(revenue, 2),
            "passThroughCost":    round(true_cost, 2),
            "tax":                round(tax, 2),
            "discount":           round(discount_amount, 2),     # negative
            "netRevenue":         round(net_revenue, 2),
            "customerTotal":      round(new_total, 2),
            "marginPercent":      round(margin_pct, 2),
        }

    # Hide internal payload pieces based on role
    if "manager" not in allowed:
        # Public / customer view -> strip all internal fields
        projected.pop("profile_snapshot", None)
        projected.pop("overrides", None)
        projected.pop("status_history", None)
        projected.pop("profitability", None)
    elif "admin_only" not in allowed:
        # Manager view -> keep status_history + overrides (workflow needs them),
        # strip admin-only payload (profile snapshot + profitability)
        projected.pop("profile_snapshot", None)
        projected.pop("profitability", None)
    return projected


# ════════════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════════════

@router.post("/api/calculations")
async def create_calculation_snapshot(
    data: Dict[str, Any] = Body(...),
    current_user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    """Create an immutable calculation snapshot.

    Body:
      origin, price, port, auction, vehicleType, damaged, vin, invoicePrice,
      useLogisticsPackage, additionalFees
      + linkage: deal_id, customer_id, lead_id (optional)
      + meta: source ("public_calculator" / "cabinet" / "crm_deal"),
              status (default "draft")

    Returns the persisted snapshot (full document, all visibility levels).
    """
    origin = (data.get("origin") or "usa").lower()
    # Run the live engine to produce outputs.
    if origin in ("korea", "kr", "korea_bg"):
        engine_out = await _calculate_korea(data)
    else:
        engine_out = await calculator_calculate(data)  # type: ignore[arg-type]
    calc_payload = engine_out.get("calculation") or {}
    breakdown = calc_payload.get("breakdown") or []
    profile_code = calc_payload.get("profileCode")

    # Snapshot the profile that was used (immutable copy).
    profile_snapshot = None
    if profile_code:
        prof = await get_db().calculator_profile.find_one({"code": profile_code}, {"_id": 0})
        profile_snapshot = prof

    # Versioning: bump version per deal_id.
    deal_id = data.get("deal_id")
    if deal_id:
        last = await get_db().calculations.find_one(
            {"deal_id": deal_id},
            sort=[("version", -1)],
            projection={"version": 1},
        )
        version = (last.get("version", 0) if last else 0) + 1
    else:
        version = 1

    now_iso = datetime.now(timezone.utc).isoformat()
    created_by = (current_user or {}).get("id") if current_user else None
    created_role = (current_user or {}).get("role") if current_user else "public"
    status = (data.get("status") or "draft").lower()
    if status not in CALC_STATUS_FLOW:
        status = "draft"

    snapshot_id = f"calc-{uuid.uuid4().hex[:12]}"
    share_token = secrets.token_urlsafe(18)  # ~24 chars -- used in /quote/:shareToken public URL
    doc = {
        "id": snapshot_id,
        "share_token": share_token,
        "version": version,
        "parent_id": data.get("parent_id"),
        "deal_id": deal_id,
        "lead_id": data.get("lead_id"),
        "customer_id": data.get("customer_id"),
        "status": status,
        "origin": origin,
        # Raw inputs (immutable record of what user typed)
        "inputs": {
            "price":                data.get("price"),
            "invoicePrice":         data.get("invoicePrice"),
            "vehicleType":          data.get("vehicleType"),
            "damaged":              bool(data.get("damaged") or False),
            "port":                 data.get("port"),
            "auction":              data.get("auction"),
            "useLogisticsPackage":  data.get("useLogisticsPackage"),
            "additionalFees":       data.get("additionalFees"),
            "vin":                  data.get("vin"),
        },
        # Outputs (immutable computed result)
        "outputs": calc_payload,
        "breakdown": breakdown,
        "fx_snapshot": calc_payload.get("fxUsdToEur"),
        "profile_code": profile_code,
        "profile_snapshot": profile_snapshot,
        # Manager overrides (mutable -- but stored separately so original outputs are preserved)
        "overrides": data.get("overrides") or {},
        # Provenance
        "source":     data.get("source") or ("crm_deal" if deal_id else "public_calculator"),
        "created_by": created_by,
        "created_role": created_role,
        "created_at": now_iso,
        "updated_at": now_iso,
        "status_history": [{
            "status": status,
            "at": now_iso,
            "by": created_by,
        }],
    }
    await get_db().calculations.insert_one(doc)
    doc.pop("_id", None)
    return {"success": True, "calculation": _project_calc_for_user(doc, current_user)}


@router.get("/api/calculations/{calc_id}")
async def get_calculation_snapshot(
    calc_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    doc = await _fetch_calc_doc(calc_id)
    return {"success": True, "calculation": _project_calc_for_user(doc, current_user)}


@router.get("/api/calculations")
async def list_calculations(
    dealId: Optional[str] = None,
    customerId: Optional[str] = None,
    leadId: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    """List calculations filtered by deal/customer/lead and optionally status.
    Returns role-projected snapshots (newest first)."""
    q: Dict[str, Any] = {}
    if dealId:
        q["deal_id"] = dealId
    if customerId:
        q["customer_id"] = customerId
    if leadId:
        q["lead_id"] = leadId
    if status:
        q["status"] = status
    # Non-staff cannot list arbitrary calculations -- must scope via a known id
    if not is_staff(current_user) and not (dealId or customerId or leadId):
        raise HTTPException(status_code=403, detail="Scope required (dealId / customerId / leadId)")
    cur = get_db().calculations.find(q, {"_id": 0}).sort("created_at", -1).limit(min(max(limit, 1), 200))
    docs = await cur.to_list(length=limit)
    return {
        "success": True,
        "items": [_project_calc_for_user(d, current_user) for d in docs],
        "count": len(docs),
    }


@router.post("/api/calculations/{calc_id}/clone")
async def clone_calculation(
    calc_id: str,
    data: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Create a new version of an existing calculation.

    Optional body fields override the original inputs (e.g. new auction won price)
    or set overrides / status for the clone. Version auto-increments under the
    same deal_id; parent_id always points at the source snapshot.
    """
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Manager role required")
    parent = await _fetch_calc_doc(calc_id)
    inputs = dict(parent.get("inputs") or {})
    inputs.update({k: v for k, v in (data.get("inputs") or {}).items() if v is not None})

    body = {
        **inputs,
        "deal_id": data.get("deal_id") or parent.get("deal_id"),
        "lead_id": data.get("lead_id") or parent.get("lead_id"),
        "customer_id": data.get("customer_id") or parent.get("customer_id"),
        "origin": data.get("origin") or parent.get("origin"),
        "overrides": data.get("overrides") if "overrides" in data else parent.get("overrides", {}),
        "parent_id": parent["id"],
        "source": data.get("source") or "crm_deal_version",
        "status": data.get("status") or "draft",
    }
    return await create_calculation_snapshot(body, current_user)


@router.patch("/api/calculations/{calc_id}/status")
async def update_calculation_status(
    calc_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Transition a calculation through the lifecycle. Validates state machine."""
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Manager role required")
    new_status = (data.get("status") or "").lower()
    if new_status not in CALC_STATUS_FLOW:
        raise HTTPException(status_code=400, detail=f"Unknown status: {new_status}")
    doc = await _fetch_calc_doc(calc_id)
    current = (doc.get("status") or "draft").lower()
    allowed_next = CALC_STATUS_FLOW.get(current, set())
    if new_status != current and new_status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current} -> {new_status}. Allowed: {sorted(allowed_next)}",
        )
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        "$set": {"status": new_status, "updated_at": now_iso},
        "$push": {"status_history": {"status": new_status, "at": now_iso, "by": current_user.get("id"), "note": data.get("note")}},
    }
    await get_db().calculations.update_one({"id": calc_id}, update)
    fresh = await _fetch_calc_doc(calc_id)
    return {"success": True, "calculation": _project_calc_for_user(fresh, current_user)}


@router.patch("/api/calculations/{calc_id}/overrides")
async def update_calculation_overrides(
    calc_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Set manager overrides (rows / hidden_rows / discount / added_rows).
    Posting an empty `{}` clears all overrides."""
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Manager role required")
    doc = await _fetch_calc_doc(calc_id)
    if (doc.get("status") or "") in ("final", "archived"):
        raise HTTPException(status_code=400, detail="Cannot edit overrides on final / archived calculation")
    overrides = data.get("overrides") if "overrides" in data else data
    now_iso = datetime.now(timezone.utc).isoformat()
    await get_db().calculations.update_one(
        {"id": calc_id},
        {"$set": {"overrides": overrides or {}, "updated_at": now_iso}},
    )
    fresh = await _fetch_calc_doc(calc_id)
    return {"success": True, "calculation": _project_calc_for_user(fresh, current_user)}


@router.delete("/api/calculations/{calc_id}")
async def archive_calculation(
    calc_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Soft-archive a calculation (sets status='archived'). Hard delete is not allowed --
    snapshots are immutable for audit / legal reasons."""
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Manager role required")
    return await update_calculation_status(calc_id, {"status": "archived", "note": "archived via DELETE"}, current_user)


# ------------------------- COMMENTS on calculations -------------------------
# Each comment has visibility: "internal" (manager+ only) or "shared" (also
# visible to the client via the public share link). Comments are append-only.

@router.get("/api/calculations/{calc_id}/comments")
async def list_calculation_comments(
    calc_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    doc = await _fetch_calc_doc(calc_id)  # 404 if missing  # noqa: F841
    is_staff_user = is_staff(current_user)
    q = {"calc_id": calc_id}
    if not is_staff_user:
        q["visibility"] = "shared"
    cur = get_db().calculation_comments.find(q, {"_id": 0}).sort("created_at", 1).limit(500)
    items = await cur.to_list(length=500)
    return {"success": True, "items": items}


@router.post("/api/calculations/{calc_id}/comments")
async def post_calculation_comment(
    calc_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(require_user),
):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Manager role required")
    doc = await _fetch_calc_doc(calc_id)  # noqa: F841 -- 404 guard
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty comment")
    visibility = (data.get("visibility") or "internal").lower()
    if visibility not in ("internal", "shared"):
        visibility = "internal"
    now_iso = datetime.now(timezone.utc).isoformat()
    comment = {
        "id": f"cmt-{uuid.uuid4().hex[:12]}",
        "calc_id": calc_id,
        "text": text,
        "visibility": visibility,
        "author_id": current_user.get("id"),
        "author_name": current_user.get("name") or current_user.get("email") or "Manager",
        "author_role": current_user.get("role"),
        "created_at": now_iso,
    }
    await get_db().calculation_comments.insert_one(comment)
    comment.pop("_id", None)
    return {"success": True, "comment": comment}


# ------------------------- PUBLIC SHARE (no auth) --------------------------
# Customer-facing read-only view of a calculation, addressed by share_token.
# Only "client"-visibility rows + totals are returned. Approve endpoint
# transitions the calc into status=approved_by_client (idempotent).

@router.get("/api/public/calculations/share/{share_token}")
async def public_get_calculation_by_share(share_token: str):
    doc = await get_db().calculations.find_one({"share_token": share_token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Shared calculation not found")
    if (doc.get("status") or "") == "archived":
        raise HTTPException(status_code=410, detail="This calculation has been archived")
    projected = _project_calc_for_user(doc, None)  # force client visibility
    # Strip internal back-link IDs from public payload
    for k in ("deal_id", "customer_id", "lead_id", "created_by", "created_role", "parent_id", "profile_code"):
        projected.pop(k, None)
    # Include shared comments
    shared_cmts = await get_db().calculation_comments.find(
        {"calc_id": doc["id"], "visibility": "shared"}, {"_id": 0}
    ).sort("created_at", 1).to_list(length=200)
    projected["comments"] = shared_cmts
    return {"success": True, "calculation": projected}


@router.post("/api/public/calculations/share/{share_token}/approve")
async def public_approve_calculation_by_share(share_token: str, data: Dict[str, Any] = Body(default={})):
    doc = await get_db().calculations.find_one({"share_token": share_token})
    if not doc:
        raise HTTPException(status_code=404, detail="Shared calculation not found")
    current = (doc.get("status") or "draft").lower()
    if current == "approved_by_client":
        return {"success": True, "already_approved": True}
    if current not in ("sent_to_client", "draft"):
        raise HTTPException(status_code=400, detail=f"Cannot approve from status '{current}'")
    now_iso = datetime.now(timezone.utc).isoformat()
    await get_db().calculations.update_one(
        {"share_token": share_token},
        {
            "$set": {"status": "approved_by_client", "updated_at": now_iso, "approved_at": now_iso},
            "$push": {"status_history": {
                "status": "approved_by_client",
                "at": now_iso,
                "by": "client",
                "note": (data.get("note") or "Client approved via public share link"),
            }},
        },
    )

    # -- P2.7: notify the manager who owns this calc / deal --
    try:
        manager_id = doc.get("created_by")
        deal_id    = doc.get("deal_id")
        # Fall back: if calc has deal_id, find the manager_id on the deal
        if not manager_id and deal_id:
            deal = await get_db().deals.find_one({"id": deal_id}, {"manager_id": 1, "owner_id": 1})
            if deal:
                manager_id = deal.get("manager_id") or deal.get("owner_id")
        total = (doc.get("outputs") or {}).get("total") or 0
        version = doc.get("version") or 1
        note_text = (data.get("note") or "").strip()

        # Persist notification (works for the customer-facing bell + manager bell)
        if manager_id:
            await get_db().notifications.insert_one({
                "id": f"notif-{uuid.uuid4().hex[:12]}",
                "type": "calculation_approved",
                "title": "Calculation approved by client",
                "message": (
                    f"Client approved calc v{version} "
                    f"(total ~ EUR {int(total):,})." + (f" Note: {note_text}" if note_text else "")
                ),
                "userId":  manager_id,
                "user_id": manager_id,  # alias for older consumers
                "deal_id": deal_id,
                "calc_id": doc.get("id"),
                "share_token": share_token,
                "read":   False,
                "isRead": False,
                "created_at": now_iso,
            })

        # Also log a deal-timeline event (used by the new /calculations/{id}/timeline endpoint
        # AND by the deal-level timeline). Non-blocking.
        await get_db().deal_events.insert_one({
            "id":         f"de-{uuid.uuid4().hex[:12]}",
            "deal_id":    deal_id,
            "calc_id":    doc.get("id"),
            "event_type": "calculation_approved_by_client",
            "summary":    f"Client approved calc v{version}",
            "metadata":   {"total": float(total or 0), "note": note_text},
            "actor":      "client",
            "actor_role": "client",
            "created_at": now_iso,
        })
    except Exception as _e:  # fail-soft -- never block approval
        logger.warning(f"[calc-approve] notification/event side-effect failed: {_e}")

    return {"success": True, "status": "approved_by_client", "approved_at": now_iso}


# ------------------------- P2.7: TIMELINE PER CALCULATION ------------------
# Aggregates: snapshot creation, status transitions, override changes, comments,
# child versions (clones) -- in a single chronological feed for the UI.

@router.get("/api/calculations/{calc_id}/timeline")
async def calculation_timeline(
    calc_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    doc = await _fetch_calc_doc(calc_id)
    is_staff_user = is_staff(current_user)
    events: List[Dict[str, Any]] = []

    # 1) Snapshot creation
    events.append({
        "kind":   "created",
        "at":     doc.get("created_at"),
        "by":     doc.get("created_role") or "system",
        "label":  f"Calculation v{doc.get('version', 1)} created",
        "detail": f"origin={doc.get('origin')} source={doc.get('source')}",
    })

    # 2) Status transitions from status_history
    for h in (doc.get("status_history") or []):
        events.append({
            "kind":   "status",
            "at":     h.get("at"),
            "by":     h.get("by") or "system",
            "label":  f"Status -> {h.get('status')}",
            "detail": h.get("note") or "",
        })

    # 3) Comments (role-filtered)
    cq = {"calc_id": calc_id}
    if not is_staff_user:
        cq["visibility"] = "shared"
    async for c in get_db().calculation_comments.find(cq, {"_id": 0}).sort("created_at", 1):
        events.append({
            "kind":   "comment",
            "at":     c.get("created_at"),
            "by":     c.get("author_name") or c.get("author_role") or "Manager",
            "label":  f"{c.get('author_name') or 'Manager'} commented",
            "detail": c.get("text"),
            "visibility": c.get("visibility"),
        })

    # 4) Deal events linked to this calc (e.g. client approved)
    async for e in get_db().deal_events.find({"calc_id": calc_id}, {"_id": 0}).sort("created_at", 1):
        events.append({
            "kind":   "deal_event",
            "at":     e.get("created_at"),
            "by":     e.get("actor") or "system",
            "label":  e.get("summary") or e.get("event_type"),
            "detail": (e.get("metadata") or {}),
        })

    # 5) Child versions (other calcs whose parent_id == calc_id)
    async for child in get_db().calculations.find(
        {"parent_id": calc_id}, {"_id": 0, "id": 1, "version": 1, "created_at": 1, "created_role": 1}
    ).sort("created_at", 1):
        events.append({
            "kind":   "version",
            "at":     child.get("created_at"),
            "by":     child.get("created_role") or "system",
            "label":  f"New version v{child.get('version')} created",
            "detail": f"calc_id={child.get('id')}",
        })

    # Stable chronological order
    events.sort(key=lambda e: e.get("at") or "")
    return {"success": True, "items": events}


# ------------------------- P2.7: COMPARE TWO CALCS ------------------------
# Returns side-by-side rows of two calculations + computed delta per row +
# delta totals. Role-aware (re-uses _project_calc_for_user).

@router.get("/api/calculations-compare")
async def compare_two_calculations(
    a: str,
    b: str,
    current_user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    if not a or not b or a == b:
        raise HTTPException(status_code=400, detail="Provide two different calc ids (?a=&b=)")
    doc_a = await _fetch_calc_doc(a)
    doc_b = await _fetch_calc_doc(b)
    proj_a = _project_calc_for_user(doc_a, current_user)
    proj_b = _project_calc_for_user(doc_b, current_user)

    def _by_key(rows):
        return {r.get("key"): r for r in (rows or []) if r.get("key")}

    ra = _by_key(proj_a.get("breakdown"))
    rb = _by_key(proj_b.get("breakdown"))
    keys = list({*ra.keys(), *rb.keys()})
    # Stable order: preserve A's order first, then any extras from B
    order_a = [r.get("key") for r in proj_a.get("breakdown", []) if r.get("key")]
    order_b = [k for k in (r.get("key") for r in proj_b.get("breakdown", [])) if k and k not in order_a]
    keys = order_a + order_b

    rows = []
    for k in keys:
        a_row = ra.get(k) or {}
        b_row = rb.get(k) or {}
        a_val = float(a_row.get("value") or 0)
        b_val = float(b_row.get("value") or 0)
        rows.append({
            "key":      k,
            "label":    a_row.get("label") or b_row.get("label") or k,
            "category": a_row.get("category") or b_row.get("category"),
            "currency": a_row.get("currency") or b_row.get("currency") or "EUR",
            "a":        a_val,
            "b":        b_val,
            "delta":    round(b_val - a_val, 2),
            "visibility": a_row.get("visibility") or b_row.get("visibility"),
            "in_a":     bool(a_row),
            "in_b":     bool(b_row),
        })

    total_a = float((proj_a.get("outputs") or {}).get("total") or 0)
    total_b = float((proj_b.get("outputs") or {}).get("total") or 0)

    return {
        "success": True,
        "a": {
            "id":      proj_a.get("id"),
            "version": proj_a.get("version"),
            "status":  proj_a.get("status"),
            "total":   total_a,
            "created_at": proj_a.get("created_at"),
        },
        "b": {
            "id":      proj_b.get("id"),
            "version": proj_b.get("version"),
            "status":  proj_b.get("status"),
            "total":   total_b,
            "created_at": proj_b.get("created_at"),
        },
        "rows":  rows,
        "delta_total": round(total_b - total_a, 2),
    }
