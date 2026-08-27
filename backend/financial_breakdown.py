"""
BIBI Cars — Financial Breakdown (P1.2)
═══════════════════════════════════════════════════════════════════════════

Принцип: у нас НЕ инвойсы — у нас РАСЧЁТ СДЕЛКИ (payment breakdown).

  templates  =  данные (DB)     → как считать
  engine     =  логика (backend) → считает здесь
  breakdown  =  snapshot (immutable) → навсегда сохранён с копией template

Каждый breakdown «замораживается» (locked=True) в момент создания и содержит
полный snapshot template'а — изменения template'а НЕ меняют старые расчёты.

Разделение денег (главная фишка P1.2):
  • total_all       — сколько клиент платит всего
  • total_official  — что проходит по банку/документам/Stripe
  • total_cash      — наличка, мимо кассы (cash_off_books)

Payment types: bank | stripe | cash_off_books | internal | manual

Safe formula parser: используем `ast` с whitelist операций, БЕЗ eval().
"""
from __future__ import annotations

import ast
import operator
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from security import require_manager_or_admin, require_admin

from app.repositories import InvoiceTemplateRepository

# Phase 5.4 / C-4h — db_runtime accessor (module-level function reference).
# Only the `get_db` CALLABLE is imported at module-load time, not the
# database handle. Every `_db()` invocation below resolves the live Motor
# handle by calling `get_db()`, preserving the call-time semantics of the
# legacy `from server import db` bridge.
from app.core.db_runtime import get_db  # noqa: E402 (C-4h: lazy-bridge → accessor)


def _tpl_repo():
    """Lazy bridge to the server.py Mongo handle (Wave 1 pattern).

    Returns a fresh ``InvoiceTemplateRepository`` bound to the
    process-wide Motor handle. Resolves at call-time to avoid
    an import cycle with `server.py`. Will be replaced by
    ``app.state.db`` DI in Phase 5.8.
    """
    return InvoiceTemplateRepository(_db())


# ════════════════════════════════════════════════════════════════════════════
#   1.  CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

BREAKDOWN_KINDS: List[str] = ["after_win", "final"]
ITEM_TYPES: List[str] = ["input", "formula", "manual"]
PAYMENT_TYPES: List[str] = ["bank", "stripe", "cash_off_books", "internal", "manual"]

#: Стадии сделки, ИЗ которых разрешено создание final-breakdown.
#: Final — это «мы уже довезли до Болгарии, теперь считаем таможню+НДС+транспорт».
STAGES_ALLOWING_FINAL_BREAKDOWN: tuple = (
    "arrived_rotterdam",
    "customs_calculated",
    "final_payment_paid",
    "in_transit_to_bg",
    "delivered",
)

DEFAULT_FX_USD_TO_EUR: float = float(os.environ.get("BIBI_FX_USD_TO_EUR") or 0.92)


# ════════════════════════════════════════════════════════════════════════════
#   2.  SAFE FORMULA PARSER (⚠ НЕ eval!)
# ════════════════════════════════════════════════════════════════════════════

_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_MAX_FORMULA_LEN = 500


class FormulaError(ValueError):
    """Raised when a template formula is invalid or uses forbidden constructs."""


def eval_formula(formula: str, ctx: Dict[str, float]) -> float:
    """
    Safely evaluate an arithmetic formula against a numeric context dict.

    Allowed:
      • constants:  int / float
      • operators:  + - * / % ** //
      • unary:      +x, -x
      • names:      any identifier present as a key in `ctx` (resolved to
                    the numeric value — any ctx[key] is cast to float)
      • parens:     (expr)
      • tuples/lists/strings/calls/attributes/subscripts → FORBIDDEN

    Raises:
      FormulaError if the expression is malformed or uses disallowed AST nodes.

    Examples:
      eval_formula("vehicle_price * 0.10", {"vehicle_price": 15000}) → 1500.0
      eval_formula("(a + b) * 0.20", {"a": 100, "b": 50}) → 30.0
    """
    if not isinstance(formula, str) or len(formula) > _MAX_FORMULA_LEN:
        raise FormulaError(f"Formula too long or not a string (len={len(formula or '')})")

    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Invalid formula syntax: {e}") from e

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise FormulaError(f"Non-numeric constant {node.value!r}")
        # py<3.8 compat
        if isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return float(node.n)  # type: ignore[attr-defined]
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _SAFE_BINOPS:
                raise FormulaError(f"Forbidden binary operator {op_type.__name__}")
            return _SAFE_BINOPS[op_type](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _SAFE_UNARYOPS:
                raise FormulaError(f"Forbidden unary operator {op_type.__name__}")
            return _SAFE_UNARYOPS[op_type](_eval(node.operand))
        if isinstance(node, ast.Name):
            if node.id not in ctx:
                raise FormulaError(f"Unknown variable {node.id!r} in formula")
            try:
                return float(ctx[node.id])
            except (TypeError, ValueError) as e:
                raise FormulaError(f"Variable {node.id!r} is not numeric: {ctx[node.id]!r}") from e
        if isinstance(node, ast.Paren) if hasattr(ast, "Paren") else False:  # py<3.8 only
            return _eval(node.value)  # pragma: no cover
        # forbid everything else
        raise FormulaError(f"Forbidden AST node {type(node).__name__}")

    try:
        result = _eval(tree)
    except FormulaError:
        raise
    except Exception as e:
        raise FormulaError(f"Formula evaluation failed: {e}") from e

    if not isinstance(result, (int, float)):
        raise FormulaError(f"Formula did not return a number: {result!r}")
    return float(result)


# ════════════════════════════════════════════════════════════════════════════
#   3.  PYDANTIC MODELS
# ════════════════════════════════════════════════════════════════════════════

class TemplateItemIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=64,
                     description="Machine-friendly ID (e.g. 'customs_duty')")
    label: str = Field(..., min_length=1, max_length=200,
                       description="Human-facing label (EN/UA)")
    type: str = Field(..., description="input | formula | manual")
    formula: Optional[str] = Field(None, max_length=_MAX_FORMULA_LEN,
                                    description="Required if type=formula")
    default: Optional[float] = Field(None, description="Default value for type=input")
    required: bool = Field(False, description="Is this item required (type=input)?")
    payment_type: str = Field("bank", description=f"One of {PAYMENT_TYPES}")
    is_official: bool = Field(True,
                               description="Goes through books/bank? (False = cash)")
    currency: str = Field("EUR", max_length=3)
    note: Optional[str] = Field(None, max_length=500)

    @validator("type")
    def _type_valid(cls, v: str) -> str:
        if v not in ITEM_TYPES:
            raise ValueError(f"type must be one of {ITEM_TYPES}")
        return v

    @validator("payment_type")
    def _payment_type_valid(cls, v: str) -> str:
        if v not in PAYMENT_TYPES:
            raise ValueError(f"payment_type must be one of {PAYMENT_TYPES}")
        return v

    @validator("formula", always=True)
    def _formula_required(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        if values.get("type") == "formula":
            if not v or not v.strip():
                raise ValueError("formula is required when type='formula'")
            # Syntax check at validation time — fails fast on bad templates
            try:
                ast.parse(v, mode="eval")
            except SyntaxError as e:
                raise ValueError(f"Invalid formula syntax: {e}") from e
        return v


class TemplateIn(BaseModel):
    id: Optional[str] = Field(None, description="Explicit ID (e.g. 'tpl_after_win_package'); auto-generated if omitted")
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(..., description=f"One of {BREAKDOWN_KINDS}")
    items: List[TemplateItemIn] = Field(..., min_items=1)
    active: bool = Field(True)
    notes: Optional[str] = Field(None, max_length=1000)

    @validator("kind")
    def _kind_valid(cls, v: str) -> str:
        if v not in BREAKDOWN_KINDS:
            raise ValueError(f"kind must be one of {BREAKDOWN_KINDS}")
        return v

    @validator("items")
    def _unique_keys(cls, v: List[TemplateItemIn]) -> List[TemplateItemIn]:
        keys = [it.key for it in v]
        if len(keys) != len(set(keys)):
            raise ValueError("item keys must be unique within a template")
        return v


class TemplatePatch(BaseModel):
    name: Optional[str] = None
    items: Optional[List[TemplateItemIn]] = None
    active: Optional[bool] = None
    notes: Optional[str] = None


class BreakdownGenerateIn(BaseModel):
    """Payload для ручной генерации final-breakdown (клик «Generate Final Costs»)."""
    template_id: Optional[str] = Field(
        None,
        description="Если не передан — берётся активный template с kind='final'",
    )
    context: Dict[str, float] = Field(
        default_factory=dict,
        description="Значения для type=input / manual и переопределения defaults",
    )
    overrides: Dict[str, float] = Field(
        default_factory=dict,
        description="Финальные overrides (например adjustments=-150)",
    )
    note: Optional[str] = Field(None, max_length=500)


# ════════════════════════════════════════════════════════════════════════════
#   4.  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    """Lazy Mongo handle — resolves at call-time, not at module-load time.

    Phase 5.4 / C-4h — migrated from the legacy ``from server import db
    as _server_db`` lazy bridge to ``app.core.db_runtime.get_db()``. Lazy
    semantics preserved 1:1: only the ``get_db`` callable is imported at
    module-load time (see top-of-file import); the database handle is
    resolved on each ``_db()`` invocation by calling ``get_db()``. No
    module-level db capture, no constructor-time freeze. The
    ``InvoiceTemplateRepository(_db())`` factory in ``_tpl_repo()`` (line
    48) and every endpoint reading ``db.invoices`` / ``db.deals`` below
    therefore see the live Motor handle on every call.
    """
    return get_db()


async def _audit_safe(**kwargs) -> None:
    """Delegate to legal_workflow._audit; never break main request."""
    try:
        from app.core.domain_audit import _audit
        await _audit(**kwargs)
    except Exception:
        import logging as _lg
        _lg.getLogger("bibi.financial.audit").warning(
            "[financial] audit dispatch failed", exc_info=True,
        )


def _compute_items_and_totals(
    template_items: List[Dict[str, Any]],
    context: Dict[str, float],
    overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Core engine: walk the template items in order, compute each value,
    accumulate into the context so later formulas can reference earlier results.

    Args:
      template_items: ordered list (from template.items)
      context: user-provided inputs (vehicle_price_eur=15000, etc.)
      overrides: last-minute admin adjustments by key

    Returns:
      {
        "items": [ {key, label, amount, payment_type, is_official, type, currency}, ... ],
        "calc":  {key: numeric value, ...}  (full calculation trace),
        "totals": {total_all, total_official, total_cash},
      }

    Raises:
      HTTPException 422 on missing required inputs or formula errors.
    """
    overrides = overrides or {}
    items_out: List[Dict[str, Any]] = []
    calc: Dict[str, float] = dict(context)  # start from provided inputs

    for tpl_item in template_items:
        key = tpl_item["key"]
        itype = tpl_item["type"]

        # 1) compute the raw value
        if key in overrides:
            val = float(overrides[key])
        elif itype == "input":
            if key in context:
                val = float(context[key])
            elif tpl_item.get("default") is not None:
                val = float(tpl_item["default"])
            elif tpl_item.get("required"):
                raise HTTPException(422, f"Required input missing: {key}")
            else:
                val = 0.0
        elif itype == "formula":
            formula = tpl_item.get("formula")
            if not formula:
                raise HTTPException(422, f"Template item {key!r} is type=formula but has no formula")
            try:
                val = eval_formula(formula, calc)
            except FormulaError as e:
                raise HTTPException(422, f"Formula error in {key!r}: {e}") from e
        elif itype == "manual":
            val = float(context.get(key, 0.0))
        else:
            raise HTTPException(422, f"Unknown item type {itype!r} in key {key!r}")

        calc[key] = val
        items_out.append({
            "key": key,
            "label": tpl_item.get("label", key),
            "amount": round(val, 2),
            "currency": tpl_item.get("currency", "EUR"),
            "payment_type": tpl_item.get("payment_type", "bank"),
            "is_official": bool(tpl_item.get("is_official", True)),
            "type": itype,
        })

    # 2) totals (three flavours)
    total_all = round(sum(i["amount"] for i in items_out), 2)
    total_official = round(
        sum(i["amount"] for i in items_out if i["is_official"]),
        2,
    )
    total_cash = round(
        sum(i["amount"] for i in items_out if i["payment_type"] == "cash_off_books"),
        2,
    )

    return {
        "items": items_out,
        "calc": {k: round(v, 2) for k, v in calc.items()},
        "totals": {
            "total_all": total_all,
            "total_official": total_official,
            "total_cash": total_cash,
        },
    }


# ════════════════════════════════════════════════════════════════════════════
#   5.  ROUTER
# ════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api", tags=["financial-breakdown"])


# ─── 5.1  Template CRUD (admin only) ───────────────────────────────────────

@router.get("/admin/invoice-templates", dependencies=[Depends(require_admin)])
async def list_templates(kind: Optional[str] = None, active: Optional[bool] = None):
    """List all financial templates. Filter by kind and/or active."""
    if kind and kind not in BREAKDOWN_KINDS:
        raise HTTPException(400, f"kind must be one of {BREAKDOWN_KINDS}")
    items = await _tpl_repo().list_filtered(kind=kind, active=active)
    return {"success": True, "data": items, "total": len(items)}


@router.get("/admin/invoice-templates/{tpl_id}", dependencies=[Depends(require_admin)])
async def get_template(tpl_id: str):
    tpl = await _tpl_repo().get_by_id(tpl_id)
    if not tpl:
        raise HTTPException(404, f"Template {tpl_id} not found")
    return {"success": True, "template": tpl}


@router.post("/admin/invoice-templates", dependencies=[Depends(require_admin)])
async def create_template(
    payload: TemplateIn = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    repo = _tpl_repo()
    tpl_id = payload.id or f"tpl_{payload.kind}_{uuid.uuid4().hex[:8]}"
    if await repo.exists_by_id(tpl_id):
        raise HTTPException(409, f"Template {tpl_id} already exists")

    now = _now_iso()
    doc = {
        "id": tpl_id,
        "name": payload.name,
        "kind": payload.kind,
        "items": [it.dict() for it in payload.items],
        "active": payload.active,
        "notes": payload.notes,
        "version": 1,
        "created_by": user.get("email") or user.get("id"),
        "created_at": now,
        "updated_at": now,
    }
    await repo.create(doc)
    doc.pop("_id", None)

    await _audit_safe(
        event_type="invoice_template_created", entity_type="invoice_template",
        entity_id=tpl_id, user=user,
        payload={"kind": payload.kind, "items_count": len(payload.items)},
    )
    return {"success": True, "template": doc}


@router.patch("/admin/invoice-templates/{tpl_id}", dependencies=[Depends(require_admin)])
async def update_template(
    tpl_id: str,
    patch: TemplatePatch = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    repo = _tpl_repo()
    existing = await repo.get_current(tpl_id)
    if not existing:
        raise HTTPException(404, f"Template {tpl_id} not found")

    set_doc: Dict[str, Any] = {"updated_at": _now_iso()}
    if patch.name is not None:
        set_doc["name"] = patch.name
    if patch.active is not None:
        set_doc["active"] = patch.active
    if patch.notes is not None:
        set_doc["notes"] = patch.notes
    if patch.items is not None:
        set_doc["items"] = [it.dict() for it in patch.items]
        set_doc["version"] = int(existing.get("version") or 1) + 1

    await repo.apply_patch(tpl_id, set_doc=set_doc)
    tpl = await repo.get_by_id(tpl_id)

    await _audit_safe(
        event_type="invoice_template_updated", entity_type="invoice_template",
        entity_id=tpl_id, user=user,
        payload={"changed_fields": list(set_doc.keys()), "new_version": set_doc.get("version")},
    )
    return {"success": True, "template": tpl}


@router.delete("/admin/invoice-templates/{tpl_id}", dependencies=[Depends(require_admin)])
async def delete_template(
    tpl_id: str,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Soft-delete: marks active=False. Existing breakdowns keep their snapshot."""
    repo = _tpl_repo()
    if not await repo.exists_by_id(tpl_id):
        raise HTTPException(404, f"Template {tpl_id} not found")

    now = _now_iso()
    await repo.soft_delete(
        tpl_id,
        deleted_by_id=user.get("email") or user.get("id"),
        at_iso=now,
    )
    await _audit_safe(
        event_type="invoice_template_soft_deleted", entity_type="invoice_template",
        entity_id=tpl_id, user=user, payload={},
    )
    return {"success": True, "template_id": tpl_id, "active": False}


# ─── 5.2  Preview (no side effects) ────────────────────────────────────────

@router.post("/admin/invoice-templates/{tpl_id}/preview",
             dependencies=[Depends(require_manager_or_admin)])
async def preview_template(tpl_id: str, body: Dict[str, Any] = Body(default={})):
    """
    Dry-run the engine for a given template + context. No DB writes.
    Useful for admin to sanity-check formulas before saving a breakdown.
    """
    tpl = await _tpl_repo().get_by_id(tpl_id)
    if not tpl:
        raise HTTPException(404, f"Template {tpl_id} not found")

    context = (body or {}).get("context") or {}
    overrides = (body or {}).get("overrides") or {}
    result = _compute_items_and_totals(tpl["items"], context, overrides)
    return {"success": True, "template_id": tpl_id, "preview": result}


# ─── 5.3  Breakdown generation (MAIN ENGINE) ───────────────────────────────

@router.post("/legal/deals/{deal_id}/final-breakdown",
             dependencies=[Depends(require_manager_or_admin)])
async def create_final_breakdown(
    deal_id: str,
    payload: BreakdownGenerateIn = Body(default=BreakdownGenerateIn()),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """
    Generate the FINAL financial breakdown for a deal (customs + VAT + BG
    transport + service fee + adjustments). Writes an immutable snapshot.

    Gates:
      • deal.stage must be in STAGES_ALLOWING_FINAL_BREAKDOWN
      • deal must have a known vehicle_price_eur (from auction_won) OR it
        must be provided in payload.context

    Idempotency: per deal, we allow only ONE final breakdown (enforced by
    `sourceFinalBreakdownDealId` existing on an earlier doc). Re-invocation
    returns the existing breakdown (200 idempotent=True).

    Returns:
      {
        success, idempotent, deal_id, kind="final", breakdown: {...}
      }
    """
    db = _db()
    deal = await db.deals.find_one({"$or": [{"id": deal_id}, {"_id": deal_id}]})
    if not deal:
        raise HTTPException(404, f"Deal {deal_id} not found")

    # Idempotent shortcut: already have a final breakdown?
    existing = await db.invoices.find_one(
        {"dealId": deal_id, "kind": "final", "sourceFinalBreakdownDealId": deal_id},
        {"_id": 0},
    )
    if existing:
        return {
            "success": True, "idempotent": True, "deal_id": deal_id,
            "kind": "final", "breakdown": existing,
        }

    # Stage gate
    stage = deal.get("stage") or deal.get("status") or ""
    if stage not in STAGES_ALLOWING_FINAL_BREAKDOWN:
        raise HTTPException(
            400,
            f"Deal stage '{stage}' does not allow final breakdown. "
            f"Allowed: {list(STAGES_ALLOWING_FINAL_BREAKDOWN)}.",
        )

    # Resolve template
    tpl = None
    if payload.template_id:
        tpl = await _tpl_repo().get_active_by_id(payload.template_id)
        if not tpl:
            raise HTTPException(404, f"Active template {payload.template_id} not found")
    else:
        tpl = await _tpl_repo().get_active_by_kind("final")
        if not tpl:
            raise HTTPException(
                500,
                "No active template for kind='final' found. Seed one first.",
            )

    # Build context: prefer explicit payload.context, fallback to deal.auction
    auction_meta = deal.get("auction") or {}
    vehicle_price_eur = (
        payload.context.get("vehicle_price_eur")
        or auction_meta.get("price_eur")
        or 0.0
    )
    fx = float(
        payload.context.get("fx_rate_snapshot")
        or auction_meta.get("fx_rate_snapshot")
        or deal.get("fx_rate_snapshot")
        or DEFAULT_FX_USD_TO_EUR
    )
    context: Dict[str, float] = {
        "vehicle_price_eur": float(vehicle_price_eur),
        "fx_rate_snapshot": fx,
        **payload.context,
    }

    # Compute
    result = _compute_items_and_totals(tpl["items"], context, payload.overrides)

    now = _now_iso()
    breakdown_id = f"fin-final-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:6]}"
    breakdown = {
        "id": breakdown_id,
        "customerId": deal.get("customerId") or deal.get("customer_id"),
        "dealId": deal_id,
        "kind": "final",
        "template_id": tpl["id"],
        "template_snapshot": tpl,           # full copy — immutable history
        "calculation_snapshot": result["calc"],
        "items": result["items"],
        "totals": result["totals"],
        "amount": result["totals"]["total_all"],          # legacy compat
        "total": result["totals"]["total_all"],
        "currency": "EUR",
        "status": "draft",
        "locked": True,                     # immutable after create
        "fx_rate_snapshot": fx,
        "sourceFinalBreakdownDealId": deal_id,
        "linked_contract_id": deal.get("final_contract_id"),
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("email") or user.get("id"),
        "note": payload.note,
        "inputs_used": {"context": context, "overrides": payload.overrides or {}},
    }
    await db.invoices.insert_one(breakdown)
    breakdown.pop("_id", None)

    await _audit_safe(
        event_type="financial_breakdown_created", entity_type="invoice",
        entity_id=breakdown_id, user=user,
        deal_id=deal_id, customer_id=breakdown["customerId"],
        payload={
            "kind": "final",
            "template_id": tpl["id"],
            "template_version": tpl.get("version"),
            "total_all": result["totals"]["total_all"],
            "total_official": result["totals"]["total_official"],
            "total_cash": result["totals"]["total_cash"],
            "items_count": len(result["items"]),
            "fx_rate_snapshot": fx,
        },
    )

    return {
        "success": True, "idempotent": False, "deal_id": deal_id,
        "kind": "final", "breakdown": breakdown,
    }


# ─── 5.4  Deal financials list (UI timeline) ───────────────────────────────

@router.get("/legal/deals/{deal_id}/financials",
            dependencies=[Depends(require_manager_or_admin)])
async def list_deal_financials(deal_id: str):
    """All breakdowns (after_win + final) for a given deal, newest first."""
    db = _db()
    q = {"$or": [{"dealId": deal_id}, {"sourceAuctionWonDealId": deal_id},
                  {"sourceFinalBreakdownDealId": deal_id}]}
    cursor = db.invoices.find(q, {"_id": 0, "template_snapshot": 0}).sort("created_at", -1)
    items = await cursor.to_list(length=50)
    # Compute totals-by-kind summary for the UI
    summary = {
        "after_win": {"exists": False, "total_all": 0, "total_official": 0, "total_cash": 0},
        "final":     {"exists": False, "total_all": 0, "total_official": 0, "total_cash": 0},
    }
    for b in items:
        k = b.get("kind")
        if k in summary:
            summary[k]["exists"] = True
            tt = (b.get("totals") or {})
            summary[k]["total_all"] += float(tt.get("total_all") or b.get("amount") or 0)
            summary[k]["total_official"] += float(tt.get("total_official") or 0)
            summary[k]["total_cash"] += float(tt.get("total_cash") or 0)
    return {"success": True, "deal_id": deal_id, "data": items, "summary": summary}


# ════════════════════════════════════════════════════════════════════════════
#   6.  SEED DEFAULT TEMPLATES (idempotent, on startup)
# ════════════════════════════════════════════════════════════════════════════

AFTER_WIN_TEMPLATE: Dict[str, Any] = {
    "id": "tpl_after_win_package",
    "name": "After-Win Package (default)",
    "kind": "after_win",
    "active": True,
    "notes": "Auto-generated at auction_won. Migrated from hard-coded legal_workflow.after_win_package.",
    "items": [
        {
            "key": "vehicle_price", "label": "Vehicle price",
            "type": "input", "required": True,
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "auction_fee", "label": "Auction fee",
            "type": "input", "default": 500.0,
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "delivery_to_rotterdam", "label": "Delivery to Rotterdam",
            "type": "input", "default": 800.0,
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "service_fee", "label": "Service fee",
            "type": "input", "default": 1000.0,
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "deposit_applied", "label": "Deposit applied",
            "type": "input", "default": 0.0,
            "payment_type": "internal", "is_official": True, "currency": "EUR",
            "note": "Signed NEGATIVE (e.g. -1000) when applied to offset the total",
        },
    ],
}

FINAL_SETTLEMENT_TEMPLATE: Dict[str, Any] = {
    "id": "tpl_final_settlement",
    "name": "Final Settlement (customs + VAT + BG transport + service)",
    "kind": "final",
    "active": True,
    "notes": "Generated after arrival in Rotterdam/BG. Cash items marked is_official=False.",
    "items": [
        {
            "key": "vehicle_price_eur", "label": "Vehicle price (from auction_won)",
            "type": "input", "required": True,
            "payment_type": "internal", "is_official": True, "currency": "EUR",
            "note": "Informational — pulled from deal.auction.price_eur; not added to totals if formulas reference it only.",
        },
        {
            "key": "customs_duty", "label": "Customs duty (10%)",
            "type": "formula", "formula": "vehicle_price_eur * 0.10",
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "vat", "label": "VAT (20% on price+duty)",
            "type": "formula", "formula": "(vehicle_price_eur + customs_duty) * 0.20",
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "bg_transport", "label": "Transport Bulgaria (cash)",
            "type": "input", "default": 700.0,
            "payment_type": "cash_off_books", "is_official": False, "currency": "EUR",
        },
        {
            "key": "service_fee", "label": "Service fee",
            "type": "input", "default": 1000.0,
            "payment_type": "bank", "is_official": True, "currency": "EUR",
        },
        {
            "key": "adjustments", "label": "Adjustments",
            "type": "manual",
            "payment_type": "manual", "is_official": True, "currency": "EUR",
            "note": "Admin-only; can be negative (rebate) or positive (extra charge)",
        },
    ],
}


# NOTE: vehicle_price_eur is listed in the FINAL template for traceability
# inside calculation_snapshot, but the item's payment_type=internal means it
# WILL add to total_all. If you don't want it in total_all, either set is_official
# and payment_type differently, or remove the item. We keep it visible by default.
# If business wants, an admin can PATCH the template and remove/change that row.
# (We intentionally picked explicit-and-visible > hidden magic.)


async def seed_default_templates(db) -> Dict[str, int]:
    """
    Idempotent seed — inserts AFTER_WIN_TEMPLATE and FINAL_SETTLEMENT_TEMPLATE
    if they don't already exist. Safe to call on every startup.

    Returns: {"created": N, "kept": M}
    """
    repo = InvoiceTemplateRepository(db)
    created = 0
    kept = 0
    now = _now_iso()
    for tpl in (AFTER_WIN_TEMPLATE, FINAL_SETTLEMENT_TEMPLATE):
        if await repo.exists_by_id(tpl["id"]):
            kept += 1
            continue
        doc = {
            **tpl,
            "version": 1,
            "created_by": "system:seed",
            "created_at": now,
            "updated_at": now,
        }
        await repo.create(doc)
        created += 1
    return {"created": created, "kept": kept}


async def ensure_indexes(db) -> None:
    """Create indexes for invoice_templates + invoices (breakdown fields).

    NOTE (Phase 5.3 / C-5): only ``invoice_templates`` indexes are
    owned by this repository. The ``invoices`` indexes below
    belong to BillingDomain (Phase 5.7 per ownership map §1.1)
    and are kept here unchanged until that domain extracts.
    """
    repo = InvoiceTemplateRepository(db)
    await repo.ensure_indexes()
    # ── Phase 5.7 blocker: db.invoices is a separate collection
    #    owned by BillingDomain. Index management stays here
    #    until the BillingRepository extraction lands.
    try:
        await db.invoices.create_index([("dealId", 1), ("kind", 1)])
        await db.invoices.create_index([("sourceFinalBreakdownDealId", 1)], sparse=True)
    except Exception:
        import logging as _lg
        _lg.getLogger("bibi.financial").warning(
            "invoices index creation failed",
            exc_info=True,
        )
