"""
BIBI Cars — Customer Cabinet Financials (P1.2-cabinet)
═══════════════════════════════════════════════════════════════════════════

Customer-facing read API: клиент видит ПОЛНУЮ картину денег по своей сделке.

  • Что должен заплатить (breakdown items + 3 totals)
  • Что уже оплатил (payments list)
  • Сколько осталось (remaining)
  • Какие части идут «официально» (bank/stripe) — для оплаты картой
  • Какие — наличными (cash_off_books) — отображены, но не оплачиваются онлайн

Безопасность:
  • Bearer token customer-session → resolve customerId
  • Customer видит ТОЛЬКО свои сделки (deal.customerId == customer.customerId)
  • Чужая сделка → 404 (не 403, чтобы не enumerate-ить чужие IDs)
  • Не возвращаем audit_events, template_snapshot, calculation_snapshot,
    inputs_used (чтобы не светить внутренние поля)

NOTE: write-эндпоинты (создание платежа, void) НЕДОСТУПНЫ для customer.
В этом модуле только READ + кнопка `Pay via Stripe`, которая создаёт
Stripe Checkout Session (если Stripe настроен в админке) и регистрирует
pending-платёж в БД. Stripe webhook (отдельный endpoint в server.py)
переводит платёж в `confirmed` после успешной оплаты.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request

from security import require_user

# Phase 5.4 / C-4h — db_runtime accessor (module-level function reference).
# Only the `get_db` CALLABLE is imported at module-load time. Every
# `_db()` call resolves the live Motor handle via `get_db()`, preserving
# the call-time semantics of the legacy `from server import db` bridge.
from app.core.db_runtime import get_db  # noqa: E402 (C-4h: lazy-bridge → accessor)

logger = logging.getLogger("bibi.cabinet_financials")

router = APIRouter(prefix="/api/cabinet", tags=["cabinet-financials"])


# ─── Helpers ──────────────────────────────────────────────────────────────

def _db():
    """Lazy Mongo handle — resolves at call-time, not at module-load time.

    Phase 5.4 / C-4h — migrated to ``app.core.db_runtime.get_db()``.
    Cabinet-financials hosts customer-facing reads of deal/invoice/payment
    state. Lazy semantics preserved 1:1 — only the ``get_db`` callable is
    imported at top-of-file, the database handle is resolved on every
    ``_db()`` invocation.

    Phase 5.5 / D — the ``_require_customer`` and ``_ensure_customer_seed``
    cross-domain bridges (previously lazy ``from server import …``)
    were retired in favour of ``app.services.customers``. See the
    wrapper functions below for the redirect shape. The remaining
    cross-domain lazy imports (``_get_stripe_config``, ``serialize_doc``)
    are still outside C-4h scope and remain in the wave queue.
    """
    return get_db()


async def _require_customer(authorization: Optional[str]) -> Dict[str, Any]:
    """Resolve customer session; 401 on miss.

    Phase 5.5 / D — body moved to
    ``app.services.customers.require_customer``. This wrapper now
    redirects lazily; it is kept (vs. inlining the import everywhere)
    to preserve the existing call shape used throughout this file's
    endpoints. The ``from server import _require_customer`` lazy
    bridge has been retired in the same wave.
    """
    from app.services.customers import require_customer
    return await require_customer(authorization)


async def _ensure_seed(customer_id: str) -> None:
    """Idempotent customer-record bootstrap (production data mode).

    Guarantees a minimal real customer document exists — never seeds demo
    business data. The legacy demo-seed subsystem was removed; this delegates
    to ``app.services.customers.ensure_customer_record``.
    """
    try:
        from app.services.customers import ensure_customer_record
        await ensure_customer_record(customer_id)
    except Exception:
        logger.exception("[cabinet] ensure_customer_record failed for %s", customer_id)


def _strip_internal(bd: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fields клиенту не нужные/опасные."""
    blacklist = {
        "_id", "template_snapshot", "calculation_snapshot",
        "inputs_used", "linked_contract_id", "auto_created_from",
        "auction",  # contains supplier price + lot info
        "created_by", "fx_rate_snapshot",
    }
    return {k: v for k, v in (bd or {}).items() if k not in blacklist}


def _strip_payment(p: Dict[str, Any]) -> Dict[str, Any]:
    """Public-safe payment view — drop creator/internal history."""
    if not p:
        return p
    return {
        "id": p.get("id"),
        "amount": p.get("amount"),
        "currency": p.get("currency"),
        "method": p.get("method"),
        "is_official": p.get("is_official") or (p.get("method") in ("bank", "stripe", "internal")),
        "status": p.get("status"),
        "proof_url": p.get("proof_url"),
        "bank_received_at": p.get("bank_received_at"),
        "confirmed_at": p.get("confirmed_at"),
        "created_at": p.get("created_at"),
        "void_reason": p.get("void_reason") if p.get("status") == "voided" else None,
    }


async def _customer_owns_deal(db, customer_id: str, deal_id: str) -> bool:
    deal = await db.deals.find_one(
        {
            "$and": [
                {"$or": [{"id": deal_id}, {"_id": deal_id}]},
                {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            ],
        },
        {"id": 1},
    )
    return bool(deal)


def _serialize_dt(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _normalize_deal(d: Dict[str, Any]) -> Dict[str, Any]:
    """Public-safe deal projection."""
    if not d:
        return d
    return {
        "id": d.get("id"),
        "title": d.get("title") or d.get("vehicleTitle"),
        "vin": d.get("vin"),
        "lot": d.get("lot"),
        "stage": d.get("stage") or d.get("status"),
        "status": d.get("status"),
        "mainImage": d.get("mainImage"),
        "managerName": d.get("managerName"),
        "managerEmail": d.get("managerEmail"),
        "managerPhone": d.get("managerPhone"),
        "payment_status": d.get("payment_status") or "unpaid",
        "payment_summary": d.get("payment_summary") or {},
        "created_at": _serialize_dt(d.get("created_at")),
        "updated_at": _serialize_dt(d.get("updated_at")),
    }


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.get("/deals")
async def list_my_deals(authorization: Optional[str] = Header(None)):
    """List of all deals for the authenticated customer.

    Used by the cabinet's Financials list page (`/cabinet/financials`).
    Recomputes payment_status + payment_summary on the fly so the cards
    reflect the latest paid-in-full / partial / unpaid state.
    """
    customer = await _require_customer(authorization)
    customer_id = customer.get("customerId") or customer.get("id")
    if not customer_id:
        raise HTTPException(401, "Customer ID missing")

    # Idempotent seed so the cabinet has demo data for fresh customers.
    await _ensure_seed(customer_id)

    db = _db()
    cursor = db.deals.find(
        {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
        {"_id": 0},
    ).sort("created_at", -1).limit(100)
    deals = await cursor.to_list(length=100)

    # Recompute every deal's payment_status (uses indexed payments collection)
    try:
        from payments_tracking import recompute_deal_payment_status
    except Exception:
        recompute_deal_payment_status = None  # type: ignore
        logger.exception("[cabinet] payments_tracking unavailable")

    out: List[Dict[str, Any]] = []
    for d in deals:
        deal_id = d.get("id") or d.get("_id")
        if recompute_deal_payment_status and deal_id:
            try:
                rec = await recompute_deal_payment_status(deal_id)
                d["payment_status"] = rec["payment_status"]
                d["payment_summary"] = rec["summary"]
            except Exception:
                pass
        out.append(_normalize_deal(d))

    return {"success": True, "data": out, "total": len(out)}


@router.get("/deals/{deal_id}/financials")
async def get_my_deal_financials(
    deal_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Полная финансовая картина по СВОЕЙ сделке.

    Returns:
      {
        deal: {id, stage, payment_status, payment_summary, created_at, ...},
        breakdowns: [{id, kind, items, totals, locked, ...}],
        payments: [{id, amount, method, status, proof_url, ...}],
        summary: {paid_total, paid_official, paid_cash, total_all,
                  total_official, total_cash, remaining, payment_count,
                  payment_status},
      }

    404 если сделка не принадлежит этому клиенту (чтобы не enumerate-ить).
    """
    customer = await _require_customer(authorization)
    customer_id = customer.get("customerId") or customer.get("id")
    db = _db()

    if not await _customer_owns_deal(db, customer_id, deal_id):
        raise HTTPException(404, f"Deal {deal_id} not found")

    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"_id": 0},
    )

    # Breakdowns: prefer final, also show after_win
    bds_cursor = db.invoices.find(
        {
            "$and": [
                {"$or": [
                    {"dealId": deal_id},
                    {"sourceAuctionWonDealId": deal_id},
                    {"sourceFinalBreakdownDealId": deal_id},
                ]},
                {"kind": {"$in": ["after_win", "final"]}},
            ],
        },
        {"_id": 0},
    ).sort("created_at", -1)
    bds_raw = await bds_cursor.to_list(length=20)
    breakdowns = [_strip_internal(b) for b in bds_raw]

    # Payments: include everything (status badge in UI distinguishes pending/voided)
    pays_cursor = db.payments.find(
        {"deal_id": deal_id}, {"_id": 0},
    ).sort("created_at", -1)
    pays_raw = await pays_cursor.to_list(length=200)
    payments = [_strip_payment(p) for p in pays_raw]

    # Recompute summary (single source of truth — same engine the manager UI uses)
    try:
        from payments_tracking import recompute_deal_payment_status
        recomputed = await recompute_deal_payment_status(deal_id)
        summary = recomputed["summary"]
        payment_status = recomputed["payment_status"]
    except Exception:
        logger.exception("[cabinet] recompute failed for %s", deal_id)
        summary = (deal or {}).get("payment_summary") or {}
        payment_status = (deal or {}).get("payment_status") or "unpaid"

    return {
        "success": True,
        "deal": _normalize_deal(deal),
        "breakdowns": breakdowns,
        "payments": payments,
        "summary": summary,
        "payment_status": payment_status,
    }


@router.post("/deals/{deal_id}/pay-intent")
async def create_pay_intent(
    deal_id: str,
    request: Request,
    body: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(None),
):
    """
    Create a Stripe Checkout Session for the OFFICIAL (bank/stripe/internal)
    portion of the customer's outstanding balance.

    Cash items are intentionally NOT included — those are handed in person.

    Returns:
      • {success: True, checkout_url, session_id, payment_id, amount, currency}
        when Stripe is configured;
      • {success: True, stub: True, amount, currency, message}
        when Stripe is not yet configured (graceful degrade);
      • {success: True, reason: "no_official_due", amount: 0, summary, message}
        when the official portion is already fully paid.
    """
    customer = await _require_customer(authorization)
    customer_id = customer.get("customerId") or customer.get("id")
    customer_email = customer.get("email")
    if not customer_id:
        raise HTTPException(401, "Customer ID missing")

    db = _db()
    if not await _customer_owns_deal(db, customer_id, deal_id):
        raise HTTPException(404, f"Deal {deal_id} not found")

    deal = await db.deals.find_one(
        {"$or": [{"id": deal_id}, {"_id": deal_id}]},
        {"_id": 0, "title": 1, "vehicleTitle": 1, "vin": 1, "id": 1},
    ) or {}

    # Compute remaining OFFICIAL due (bank+stripe+internal)
    try:
        from payments_tracking import recompute_deal_payment_status
        rec = await recompute_deal_payment_status(deal_id)
        summary = rec["summary"]
    except Exception as e:
        logger.exception("[cabinet] recompute failed")
        raise HTTPException(500, f"Calculation error: {e}")

    total_official = float(summary.get("total_official") or 0)
    paid_official  = float(summary.get("paid_official") or 0)
    remaining_official = round(max(0.0, total_official - paid_official), 2)

    if remaining_official <= 0.0:
        return {
            "success": True,
            "reason": "no_official_due",
            "amount": 0,
            "summary": summary,
            "message": "Все офіційне вже сплачено",
        }

    # Optional partial-pay override (capped at remaining)
    requested = body.get("amount") if isinstance(body, dict) else None
    if requested is not None:
        try:
            requested = float(requested)
            if requested > 0:
                remaining_official = round(min(remaining_official, requested), 2)
        except Exception:
            pass

    # Try Stripe; gracefully degrade to a stub if not configured
    cfg = None
    try:
        # Phase 5.5 / E (2026-05-19) — repaired latent ImportError bridge.
        # The previous line tried to lazy-import the legacy underscore-
        # prefixed name from ``server``, but ``server`` never exported
        # the symbol module-level; the import always raised, the
        # surrounding ``except Exception`` masked the failure, and the
        # cabinet checkout flow silently degraded to stub-mode below.
        # The helper has been moved to its canonical home at
        # ``app/services/stripe_config.py``; this import now actually
        # resolves and the cabinet flow can exercise the real Stripe
        # checkout path.
        from app.services.stripe_config import get_stripe_config
        cfg = await get_stripe_config()
    except Exception:
        logger.exception("[cabinet] get_stripe_config failed")

    if not cfg or not cfg.get("isEnabled") or not cfg.get("secretKey"):
        return {
            "success": True,
            "stub": True,
            "amount": remaining_official,
            "currency": "EUR",
            "message": (
                "Онлайн-оплата карткою тимчасово недоступна. "
                "Зв'яжіться з менеджером для отримання банківських реквізитів."
            ),
        }

    # Build success/cancel URLs against the public host
    def _resolve_base() -> str:
        env_url = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
        if env_url:
            return env_url
        xf_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        xf_proto = request.headers.get("x-forwarded-proto", "https")
        if xf_host:
            return f"{xf_proto}://{xf_host}".rstrip("/")
        return str(request.base_url).rstrip("/")

    base = _resolve_base()
    success_url = f"{base}/cabinet/deals/{deal_id}/financials?paid=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{base}/cabinet/deals/{deal_id}/financials?paid=cancel"

    payment_id = f"pay-stripe-{uuid.uuid4().hex[:12]}"
    amount_minor = int(round(remaining_official * 100))
    deal_title = deal.get("title") or deal.get("vehicleTitle") or f"Deal {deal_id}"
    currency = (cfg.get("currency") or "eur").lower()

    try:
        import stripe as _stripe  # type: ignore
        _stripe.api_key = cfg["secretKey"]

        params: Dict[str, Any] = {
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": currency,
                    "product_data": {
                        "name": f"BIBI Cars · {deal_title}",
                        "description": f"Officially-payable balance for deal {deal_id}",
                        "metadata": {"deal_id": deal_id, "customer_id": customer_id},
                    },
                    "unit_amount": amount_minor,
                },
                "quantity": 1,
            }],
            "success_url": success_url,
            "cancel_url":  cancel_url,
            "client_reference_id": payment_id,
            "metadata": {
                "deal_id": deal_id,
                "customer_id": customer_id,
                "payment_id": payment_id,
                "source": "bibi-cabinet",
            },
            "payment_intent_data": {
                "metadata": {
                    "deal_id": deal_id,
                    "customer_id": customer_id,
                    "payment_id": payment_id,
                    "source": "bibi-cabinet",
                },
            },
        }
        if customer_email:
            params["customer_email"] = customer_email
        if not cfg.get("automaticPaymentMethods"):
            pm_list = [m for m in (cfg.get("paymentMethods") or [])
                       if m and m not in ("auto", "automatic")] or ["card"]
            params["payment_method_types"] = pm_list

        session = await asyncio.to_thread(lambda: _stripe.checkout.Session.create(**params))
    except Exception as e:
        logger.exception("[cabinet] Stripe Checkout Session create failed")
        # Graceful fallback to stub on Stripe API errors
        return {
            "success": True,
            "stub": True,
            "amount": remaining_official,
            "currency": "EUR",
            "message": (
                f"Тимчасова помилка платіжного шлюзу: {e}. "
                "Спробуйте пізніше або зверніться до менеджера."
            ),
        }

    # Record a PENDING payment so the cabinet shows the in-flight intent.
    # The Stripe webhook flips this to 'confirmed' on successful payment.
    payment_doc = {
        "id": payment_id,
        "deal_id": deal_id,
        "customer_id": customer_id,
        "amount": remaining_official,
        "currency": "EUR",
        "method": "stripe",
        "status": "pending",
        "stripe_session_id": session.id,
        "stripe_payment_intent": getattr(session, "payment_intent", None),
        "checkout_url": session.url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": customer_email or customer_id,
        "source": "cabinet",
    }
    try:
        await db.payments.insert_one(payment_doc)
    except Exception:
        logger.exception("[cabinet] failed to record pending payment")

    return {
        "success": True,
        "checkout_url": session.url,
        "session_id":   session.id,
        "payment_id":   payment_id,
        "amount":       remaining_official,
        "currency":     "EUR",
    }


# ════════════════════════════════════════════════════════════════════════════
#   ABSORBED v1 CABINET ENDPOINTS  — moved from server.py on 2026-05-17
# ════════════════════════════════════════════════════════════════════════════
#
# Wave 1 / Commit 5 of the Controlled Modular Monolith refactoring.
# These 9 GET endpoints lived in three separate locations inside server.py
# (7043, 12492, 19234-19277) and were absorbed here verbatim to keep the
# cabinet domain in a single bounded island (the "absorb-not-relocate"
# strategy -- see backend/CONTRIBUTING.md).
#
# Behaviour preserved 1-to-1:
#   * stubs remain stubs (kept for frontend backward-compat)
#   * `serialize_doc` is the legacy server.py utility (will move to
#     app/utils/serialization.py during Phase 6).
#   * `require_user` is the standard JWT customer/staff resolver.
#
# !!! TEMP BRIDGE !!!  Same controlled anti-pattern: lazy `_db()` resolver
# and lazy `from server import serialize_doc` inside each endpoint that
# needs it.  Documented in REFACTOR_DEPENDENCIES.md.
# ════════════════════════════════════════════════════════════════════════════


@router.get("/history-reports")
async def cabinet_history_reports():
    return {"reports": []}


@router.get("/watchlist")
async def cabinet_watchlist(user: dict = Depends(require_user)):
    """Return the authenticated user's watchlist (pending + notified)."""
    db = _db()
    uid = user.get("id")
    cursor = db.search_watchlist.find(
        {"$or": [{"userId": uid}, {"email": (user.get("email") or "").lower()}]},
        {"_id": 0},
    ).sort("createdAt", -1).limit(200)
    items = await cursor.to_list(length=200)
    # Serialize datetimes
    for it in items:
        for k in ("createdAt", "notifiedAt", "notified_at"):
            if hasattr(it.get(k), "isoformat"):
                it[k] = it[k].isoformat()
    return {"success": True, "items": items, "count": len(items)}


@router.get("/orders")
async def get_cabinet_orders(authorization: Optional[str] = Header(None)):
    """Real, customer-scoped orders (deals) for the authenticated customer."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    deals = await db.deals.find({"$or": [{"customerId": cid}, {"customer_id": cid}]}).sort("created_at", -1).limit(50).to_list(50)
    return {"orders": [serialize_doc(d) for d in deals]}


@router.get("/deposits")
async def get_cabinet_deposits(authorization: Optional[str] = Header(None)):
    """Real, customer-scoped deposits for the authenticated customer."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    deposits = await db.deposits.find({"$or": [{"customerId": cid}, {"customer_id": cid}]}).sort("created_at", -1).limit(50).to_list(50)
    return {"deposits": [serialize_doc(d) for d in deposits]}


@router.get("/invoices")
async def get_cabinet_invoices(authorization: Optional[str] = Header(None)):
    """Real, customer-scoped invoices for the authenticated customer."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    invoices = await db.invoices.find({"$or": [{"customerId": cid}, {"customer_id": cid}]}).sort("created_at", -1).limit(50).to_list(50)
    return {"invoices": [serialize_doc(i) for i in invoices]}


@router.get("/contracts")
async def get_cabinet_contracts(authorization: Optional[str] = Header(None)):
    """Real, customer-scoped contracts for the authenticated customer."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    contracts = await db.contracts.find({"$or": [{"customerId": cid}, {"customer_id": cid}]}).sort("created_at", -1).limit(50).to_list(50)
    return {"contracts": [serialize_doc(c) for c in contracts]}


@router.get("/shipping")
async def get_cabinet_shipping(authorization: Optional[str] = Header(None)):
    """Real, customer-scoped shipments for the authenticated customer."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    shipments = await db.shipments.find({"$or": [{"customerId": cid}, {"customer_id": cid}]}).sort("created_at", -1).limit(50).to_list(50)
    return {"shipments": [serialize_doc(s) for s in shipments]}


@router.get("/notifications")
async def get_cabinet_notifications(authorization: Optional[str] = Header(None)):
    """Real, customer-scoped notifications for the authenticated customer."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    notes = await db.notifications.find({"$or": [{"customerId": cid}, {"customer_id": cid}]}).sort("created_at", -1).limit(50).to_list(50)
    return {"notifications": [serialize_doc(n) for n in notes]}


@router.get("/profile")
async def get_cabinet_profile(authorization: Optional[str] = Header(None)):
    """Return the authenticated customer's REAL profile (no hardcoded data)."""
    from app.utils.serialization import serialize_doc
    customer = await _require_customer(authorization)
    cid = customer.get("customerId") or customer.get("id")
    db = _db()
    c = await db.customers.find_one({"id": cid}, {"_id": 0, "password": 0}) or {}
    return serialize_doc(c)

