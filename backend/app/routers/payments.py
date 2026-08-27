"""payments: Stripe checkout flow + admin payments dashboard.

OWNER:  payments-domain
SOURCE: extracted from legacy server.py on 2026-05-17
WAVE:   1

================================================================================
                          !!! TEMP BRIDGE !!!
This router previously used `import server` globals during Wave 1
extraction.  Phase 5.5 / C (2026-05-19) retired the last bridge — see
"Retired bridges" below — and the ``import server`` line has been fully
removed from this module.

Retired bridges (kept here for changelog clarity):
  * server._create_order_from_invoice - Phase 5.5 / C (migrated to
                         ``from app.services.orders import
                         create_order_from_invoice``; lazy import inside
                         the Stripe webhook recompute branch mirrors the
                         existing ``_get_stripe_config`` /
                         ``_record_payment_from_stripe`` consumption
                         shape).
  * server.db          - Phase 5.4 / C-4i (migrated to `Depends(get_db)`
                         / `app.core.db_runtime.get_db()`)
  * server.logger      - Phase 5.5 / A   (migrated to module-local
                         `logger = logging.getLogger("bibi.payments")`)

DO NOT replicate this `import server` pattern in NEW routers without an
explicit migration plan.

================================================================================
                       !!! INTEGRATION BOUNDARY !!!
The Stripe webhook (POST /api/stripe/webhook) and its startup index
(`_ensure_webhook_events_index`) intentionally REMAIN in server.py.
Webhooks are integration boundaries, not domain CRUD.  They live with the
ASGI app surface.  Webhook calls these helpers via lazy `from
app.routers.payments import ...` inside its handler.
================================================================================

This module owns:
  HELPERS:
    _confirm_cabinet_payment     update cabinet payment status from Stripe object
    _record_payment_from_stripe  persist/refresh normalized payment record

  (NOTE: Phase 5.5/E — `_get_stripe_config` moved to its canonical home
  at ``app/services/stripe_config.py``; consumed via module-level import
  ``from app.services.stripe_config import get_stripe_config``.)

  PUBLIC ENDPOINTS:
    GET    /api/payments/packages
    GET    /api/stripe/public-config
    POST   /api/stripe/create-checkout-session
    GET    /api/stripe/session/{session_id}

  ADMIN ENDPOINTS:
    GET    /api/admin/payments
    GET    /api/admin/payments/stats
    GET    /api/admin/payments/recent-events
    GET    /api/admin/payments/{payment_id}
    POST   /api/admin/payments/{payment_id}/refund
    POST   /api/admin/payments/sync
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from security import require_admin, require_master_admin

# Phase 5.4 / C-4i — db_runtime accessor (module-level function reference).
# Only the `get_db` CALLABLE is imported at module-load time. Every
# `get_db()` call resolves the live Motor handle, preserving the
# call-time semantics of the retired `get_db().X` qualified pattern.
from app.core.db_runtime import get_db  # noqa: E402 (C-4i: qualified-import → accessor)

# Phase 5.5 / E — Stripe config helper moved to its canonical home at
# ``app/services/stripe_config.py`` (public entry ``get_stripe_config``).
# The Wave-1 router-internal placement was a misclassification fixed in
# 5.5/E; this is now the standard cross-domain import shape used by all
# 4 caller clusters (this router × 7 sites; ``server.py`` × 2 lazy sites;
# ``cabinet_financials.py`` × 1 site formerly broken).
from app.services.stripe_config import get_stripe_config

# Phase 5.5 / A — module-local logger. Replaces the 8
# ``server.logger.exception(...)`` qualified-access sites that were the
# residue of the pre-C-4a logger retirement (C-4a removed the
# ``from server import logger`` shape; the ``server.logger`` qualified
# shape survived because ``import server`` was an acceptable temporary
# bridge — see C-5f QUALIFIED_USAGE_BRIDGES). Namespace mirrors the
# canonical ``bibi.*`` logger hierarchy used by Phase 4 observability.
#
# Phase 5.5 / C — ``import server`` line REMOVED. The last consumer was
# the qualified ``server._create_order_from_invoice(...)`` call in the
# Stripe webhook recompute branch; it now goes through the canonical
# home ``app.services.orders.create_order_from_invoice`` via a lazy
# inline import (mirroring the ``_get_stripe_config`` /
# ``_record_payment_from_stripe`` consumption shape used by the webhook
# integration boundary at server.py:13907-13911).
logger = logging.getLogger("bibi.payments")

router = APIRouter(tags=["payments"])


@router.get("/api/payments/packages")
async def payment_packages():
    """Get payment packages"""
    return {
        "success": True,
        "packages": [
            {"id": "basic", "name": "Basic", "price": 99, "features": ["5 VIN checks", "Basic support"]},
            {"id": "pro", "name": "Pro", "price": 299, "features": ["Unlimited VIN checks", "Priority support"]},
            {"id": "enterprise", "name": "Enterprise", "price": 999, "features": ["All features", "Dedicated support"]},
        ]
    }
# Phase 5.5 / E (2026-05-19) — `_get_stripe_config` retired from this
# router and moved to its canonical home at
# ``app/services/stripe_config.py`` (public entry point
# ``get_stripe_config``). The helper was a Wave-1 router-internal
# placement; its proper architectural slot is ``app/services/``
# (cross-domain config helper, consumed by 4 distinct caller clusters).
# 7 in-file callers below were bulk-migrated to the bare public name.
@router.get("/api/stripe/public-config")
async def stripe_public_config():
    """Public endpoint — returns Publishable Key, currency, payment methods,
    checkout mode. No secrets. Used by the cabinet to render the Pay button
    and (for embedded mode) initialize Stripe.js."""
    cfg = await get_stripe_config()
    enabled = cfg["enabledMethods"] or {}
    # Methods we display on the customer-facing picker
    display_methods = []
    method_meta = [
        ("card",              "Card",                "Visa, Mastercard, Amex, Discover"),
        ("apple_pay",         "Apple Pay",           "One-tap on Safari / iOS"),
        ("google_pay",        "Google Pay",          "One-tap on Chrome / Android"),
        ("link",              "Link",                "Stripe one-click checkout"),
        ("klarna",            "Klarna",              "Buy now, pay later"),
        ("afterpay_clearpay", "Afterpay / Clearpay", "Pay in 4 instalments"),
        ("cashapp",           "Cash App Pay",        "USD only"),
        ("crypto",            "Crypto",              "USDC stablecoin (Stripe Crypto)"),
        ("us_bank_account",   "US Bank Account",     "ACH Debit (USA)"),
        ("sepa_debit",        "SEPA Direct Debit",   "EUR (EU)"),
        ("ideal",             "iDEAL",               "Netherlands"),
        ("bancontact",        "Bancontact",          "Belgium"),
        ("p24",               "Przelewy24",          "Poland"),
        ("blik",              "BLIK",                "Poland"),
        ("alipay",            "Alipay",              "China"),
        ("wechat_pay",        "WeChat Pay",          "China"),
    ]
    for k, label, hint in method_meta:
        if enabled.get(k):
            display_methods.append({"key": k, "label": label, "hint": hint})

    return {
        "enabled": bool(cfg["isEnabled"] and cfg["publishableKey"]),
        "publishableKey": cfg["publishableKey"],
        "currency": cfg["currency"],
        "paymentMethods": cfg["paymentMethods"],
        "enabledMethods": cfg["enabledMethods"],
        "displayMethods": display_methods,
        "checkoutMode": cfg["checkoutMode"],
        "automaticPaymentMethods": cfg["automaticPaymentMethods"],
        "mode": cfg["mode"],
    }


@router.post("/api/stripe/create-checkout-session")
async def create_checkout_session(request: Request, data: Dict[str, Any] = Body(...)):
    """Create a real Stripe Checkout Session using admin-saved credentials.

    Request body:
      {
        "amount": 1000,             # required, in MAJOR units (e.g. 10.00)
        "description": "Invoice #…", # optional
        "invoiceId": "inv_...",     # optional — used to attach metadata
        "customerEmail": "...",     # optional
        "successUrl": "https://...",# optional override
        "cancelUrl": "https://...", # optional override
        "currency": "EUR"           # optional override
      }
    """
    cfg = await get_stripe_config()
    if not cfg["isEnabled"]:
        raise HTTPException(status_code=424, detail="Stripe is disabled in admin Integrations.")
    if not cfg["secretKey"]:
        raise HTTPException(status_code=424, detail="Stripe Secret Key is not configured.")

    amount = data.get("amount")
    try:
        amount_minor = int(round(float(amount) * 100))
    except Exception:
        raise HTTPException(status_code=400, detail="amount is required and must be a number")
    if amount_minor <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    currency = (data.get("currency") or cfg["currency"] or "usd").lower()
    description = data.get("description") or "Invoice payment"
    invoice_id = data.get("invoiceId") or ""
    customer_email = data.get("customerEmail")
    success_url = data.get("successUrl") or cfg["successUrl"]
    cancel_url = data.get("cancelUrl") or cfg["cancelUrl"]

    # Resolve base URL: explicit env > X-Forwarded-Host header > request host
    def _resolve_base() -> str:
        env_url = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
        if env_url:
            return env_url
        # Try X-Forwarded-Host (Kubernetes ingress)
        xf_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        xf_proto = request.headers.get("x-forwarded-proto", "https")
        if xf_host:
            return f"{xf_proto}://{xf_host}".rstrip("/")
        return str(request.base_url).rstrip("/")

    base = _resolve_base()
    if not success_url.startswith("http"): success_url = base + (success_url if success_url.startswith("/") else f"/{success_url}")
    if not cancel_url.startswith("http"):  cancel_url  = base + (cancel_url  if cancel_url.startswith("/")  else f"/{cancel_url}")
    # Append session_id placeholder for tracking
    if "{CHECKOUT_SESSION_ID}" not in success_url:
        success_url = success_url + ("&" if "?" in success_url else "?") + "session_id={CHECKOUT_SESSION_ID}"

    try:
        import stripe as _stripe  # type: ignore
        _stripe.api_key = cfg["secretKey"]

        params = {
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": description, "metadata": {"invoiceId": invoice_id}},
                    "unit_amount": amount_minor,
                },
                "quantity": 1,
            }],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "invoiceId": invoice_id,
                "customerId": str(data.get("customerId") or ""),
                "source": "bibi-crm",
            },
        }

        # Payment-methods strategy:
        #   When `automaticPaymentMethods=True` (recommended), we omit
        #   `payment_method_types` so Stripe Checkout auto-renders methods
        #   enabled in the Dashboard + the right wallets (Apple Pay /
        #   Google Pay / Link) based on browser/device.
        #   Otherwise we pass `payment_method_types` explicitly.
        if not cfg["automaticPaymentMethods"]:
            pm_list = [m for m in (cfg["paymentMethods"] or []) if m and m not in ("auto", "automatic")]
            if not pm_list:
                pm_list = ["card"]
            params["payment_method_types"] = pm_list

        # Capture method (immediate vs manual)
        capture = (cfg.get("captureMethod") or "automatic").lower()
        if capture in ("automatic", "manual", "automatic_async"):
            params["payment_intent_data"] = {
                "capture_method": capture,
                "metadata": {"invoiceId": invoice_id, "source": "bibi-crm"},
            }
            if cfg.get("statementDescriptor"):
                params["payment_intent_data"]["statement_descriptor_suffix"] = cfg["statementDescriptor"]

        if cfg.get("allowPromotionCodes"):
            params["allow_promotion_codes"] = True
        if cfg.get("billingAddressCollection") in ("auto", "required"):
            params["billing_address_collection"] = cfg["billingAddressCollection"]
        if cfg.get("phoneNumberCollection"):
            params["phone_number_collection"] = {"enabled": True}

        if customer_email:
            params["customer_email"] = customer_email
        if cfg["checkoutMode"] == "embedded":
            params["ui_mode"] = "embedded"
            params["return_url"] = success_url
            # `embedded` mode does NOT take success_url/cancel_url
            params.pop("success_url", None)
            params.pop("cancel_url", None)

        session = await asyncio.to_thread(lambda: _stripe.checkout.Session.create(**params))

        # Persist the session for later reconciliation
        try:
            await get_db().payment_sessions.insert_one({
                "id": session.id,
                "invoiceId": invoice_id,
                "customerId": str(data.get("customerId") or ""),
                "customerEmail": customer_email,
                "amount": amount_minor / 100,
                "amountMinor": amount_minor,
                "currency": currency,
                "description": description,
                "status": session.status,
                "paymentStatus": getattr(session, "payment_status", "unpaid"),
                "url": session.url,
                "client_secret": getattr(session, "client_secret", None),
                "mode": cfg["mode"],
                "checkoutMode": cfg["checkoutMode"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass

        return {
            "success": True,
            "sessionId": session.id,
            "url": session.url,                                    # for hosted
            "clientSecret": getattr(session, "client_secret", None),  # for embedded
            "publishableKey": cfg["publishableKey"],
            "mode": cfg["checkoutMode"],
        }
    except Exception as ex:
        logger.exception("[stripe] create_checkout_session failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {type(ex).__name__}: {str(ex)[:200]}")


@router.get("/api/stripe/session/{session_id}")
async def get_checkout_session(session_id: str):
    """Look up a checkout session (used by success page to confirm payment)."""
    cfg = await get_stripe_config()
    if not cfg["secretKey"]:
        raise HTTPException(status_code=503, detail="Stripe is not configured.")
    try:
        import stripe as _stripe  # type: ignore
        _stripe.api_key = cfg["secretKey"]
        s = await asyncio.to_thread(lambda: _stripe.checkout.Session.retrieve(session_id))
        return {
            "success": True,
            "sessionId": s.id,
            "status": s.status,
            "paymentStatus": s.payment_status,
            "amount": (s.amount_total or 0) / 100,
            "currency": s.currency,
            "customerEmail": s.customer_details.email if s.customer_details else None,
            "metadata": dict(s.metadata or {}),
        }
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Stripe error: {type(ex).__name__}: {str(ex)[:200]}")
async def _confirm_cabinet_payment(obj: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """
    Confirm a cabinet-source Stripe payment based on a Checkout Session or
    PaymentIntent payload.

    Returns dict with diagnostic info: {found, payment_id, deal_id, status, action}
    so the webhook can include it in its log + audit trail.

    Matching priority (most reliable first):
      1. metadata.payment_id  (we set this on every cabinet checkout session)
      2. stripe_session_id    (only for Checkout Session events)
      3. stripe_payment_intent (for PI events; also session events once PI exists)
      4. client_reference_id  (we set this to payment_id at session creation)
    """
    if not obj:
        return {"found": False, "reason": "empty_object"}

    is_session = (
        obj.get("object") == "checkout.session"
        or "amount_total" in obj
        or ("payment_intent" in obj and obj.get("mode") in (None, "payment", "subscription"))
    )

    metadata = dict(obj.get("metadata") or {})
    metadata_payment_id = metadata.get("payment_id") or metadata.get("paymentId")
    client_ref = obj.get("client_reference_id")
    session_id = obj.get("id") if is_session else None
    pi_id = (obj.get("payment_intent") if is_session else obj.get("id")) or None

    # Build OR-query in priority order
    or_clauses = []
    if metadata_payment_id:
        or_clauses.append({"id": metadata_payment_id})
    if session_id:
        or_clauses.append({"stripe_session_id": session_id})
    if pi_id:
        or_clauses.append({"stripe_payment_intent": pi_id})
    if client_ref and client_ref != metadata_payment_id:
        or_clauses.append({"id": client_ref})

    if not or_clauses:
        return {"found": False, "reason": "no_identifiers"}

    payment = await get_db().payments.find_one({"$or": or_clauses})
    if not payment:
        return {
            "found": False,
            "reason": "not_in_db",
            "session_id": session_id,
            "payment_intent": pi_id,
            "metadata_payment_id": metadata_payment_id,
        }

    # Only operate on cabinet-sourced payments to avoid colliding with
    # _record_payment_from_stripe, which manages legacy admin invoice flow.
    if payment.get("source") != "cabinet":
        return {"found": True, "skipped": True, "reason": "non_cabinet_source"}

    deal_id = payment.get("deal_id")
    payment_id = payment.get("id")
    prev_status = payment.get("status")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Determine new status from event type
    confirm_events = (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "payment_intent.succeeded",
    )
    fail_events = (
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    )
    refund_events = ("charge.refunded", "charge.refund.updated")

    new_status: Optional[str] = None
    set_fields: Dict[str, Any] = {"updated_at": now_iso}

    if event_type in confirm_events:
        # For Checkout Session, also require payment_status == 'paid'
        if is_session and obj.get("payment_status") and obj.get("payment_status") != "paid":
            new_status = None  # session completed but not yet paid (async/processing)
        else:
            new_status = "confirmed"
            set_fields["confirmed_at"] = now_iso
            set_fields["confirmed_via"] = "stripe_webhook"
    elif event_type in fail_events:
        new_status = "failed"
        set_fields["failed_at"] = now_iso
        set_fields["failure_reason"] = (
            (obj.get("last_payment_error") or {}).get("message")
            or obj.get("cancellation_reason")
            or event_type
        )
    elif event_type in refund_events:
        new_status = "refunded"
        set_fields["refunded_at"] = now_iso

    # Always backfill payment_intent if we just learned it
    if pi_id and not payment.get("stripe_payment_intent"):
        set_fields["stripe_payment_intent"] = pi_id
    # Capture receipt URL if available (for emails / customer page)
    charges = (obj.get("charges") or {}).get("data") if isinstance(obj.get("charges"), dict) else None
    if charges:
        receipt_url = (charges[0] or {}).get("receipt_url")
        if receipt_url:
            set_fields["receipt_url"] = receipt_url

    if new_status:
        # Idempotent: don't overwrite an already-confirmed payment with another confirm
        if prev_status == new_status:
            return {
                "found": True,
                "payment_id": payment_id,
                "deal_id": deal_id,
                "status": prev_status,
                "action": "no_change",
            }
        set_fields["status"] = new_status

    await get_db().payments.update_one({"id": payment_id}, {"$set": set_fields})

    # Recompute deal payment status (single source of truth used by cabinet UI)
    if deal_id and new_status in ("confirmed", "refunded"):
        try:
            from payments_tracking import recompute_deal_payment_status
            await recompute_deal_payment_status(deal_id)
        except Exception:
            logger.exception("[stripe-webhook] recompute_deal_payment_status failed for %s", deal_id)

    # Audit
    try:
        # Phase 5.3 / C-11 — db.audit_events ownership routes through
        # AuditEventsRepository. The verb name (record_payment_webhook_event)
        # makes the cross-domain WRITE visible — the payments router
        # persists into a collection owned by the legal/audit family.
        # Phase 5.4+ may relocate this write to a dedicated PaymentAudit
        # boundary; the call site stays here, only the verb changes.
        from app.repositories import AuditEventsRepository
        await AuditEventsRepository(get_db()).record_payment_webhook_event({
            "id": f"aud-{uuid.uuid4().hex[:12]}",
            "type": f"payment.{new_status or event_type}",
            "deal_id": deal_id,
            "payment_id": payment_id,
            "amount": payment.get("amount"),
            "currency": payment.get("currency"),
            "method": "stripe",
            "source": "stripe_webhook",
            "event_type": event_type,
            "stripe_session_id": session_id,
            "stripe_payment_intent": pi_id,
            "ts": now_iso,
        })
    except Exception:
        logger.exception("[stripe-webhook] audit insert failed")

    return {
        "found": True,
        "payment_id": payment_id,
        "deal_id": deal_id,
        "status": new_status or prev_status,
        "action": "updated" if new_status else "no_status_change",
    }
async def _record_payment_from_stripe(obj: Dict[str, Any], event_type: str = "") -> None:
    """Persist/refresh a normalized payment record from a Stripe object
    (PaymentIntent or Checkout Session)."""
    if not obj:
        return
    try:
        # Detect whether obj is a Checkout Session or a PaymentIntent
        is_session = obj.get("object") == "checkout.session" or "payment_intent" in obj or "amount_total" in obj
        pi_id = (obj.get("payment_intent") if is_session else obj.get("id")) or ""
        session_id = obj.get("id") if is_session else None

        amount = obj.get("amount_total") if is_session else (obj.get("amount_received") or obj.get("amount") or 0)
        currency = (obj.get("currency") or "usd").lower()
        status = obj.get("status") or ""
        payment_status = obj.get("payment_status") or status
        metadata = dict(obj.get("metadata") or {})
        invoice_id = metadata.get("invoiceId") or metadata.get("invoice_id") or ""
        customer_id = metadata.get("customerId") or metadata.get("customer_id") or ""
        customer_email = None
        cust_details = obj.get("customer_details") or {}
        customer_email = cust_details.get("email") if isinstance(cust_details, dict) else None
        if not customer_email:
            customer_email = obj.get("receipt_email") or obj.get("customer_email")

        # Try to derive payment method type
        pm_types = obj.get("payment_method_types") or []
        pm_type = pm_types[0] if pm_types else None
        # For PaymentIntents the actually used method lives on charge or payment_method
        charges = (obj.get("charges") or {}).get("data") if isinstance(obj.get("charges"), dict) else None
        pm_brand = None
        last4 = None
        wallet = None
        if charges:
            ch = charges[0] or {}
            pmd = (ch.get("payment_method_details") or {})
            pm_type = pmd.get("type") or pm_type
            card = pmd.get("card") or {}
            pm_brand = card.get("brand")
            last4 = card.get("last4")
            wallet = (card.get("wallet") or {}).get("type")

        # Receipt URL
        receipt_url = None
        if charges:
            receipt_url = (charges[0] or {}).get("receipt_url")

        amount_major = (amount or 0) / 100 if isinstance(amount, (int, float)) else 0

        record = {
            "paymentIntentId": pi_id,
            "sessionId": session_id,
            "amount": amount_major,
            "amountMinor": int(amount or 0),
            "currency": currency,
            "status": status,
            "paymentStatus": payment_status,
            "method": pm_type,
            "wallet": wallet,
            "cardBrand": pm_brand,
            "cardLast4": last4,
            "invoiceId": invoice_id,
            "customerId": customer_id,
            "customerEmail": customer_email,
            "metadata": metadata,
            "receiptUrl": receipt_url,
            "lastEvent": event_type or status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Use paymentIntentId if available else sessionId as the upsert key
        key = {"paymentIntentId": pi_id} if pi_id else {"sessionId": session_id}
        existing = await get_db().payments.find_one(key) if any(key.values()) else None
        if existing:
            await get_db().payments.update_one(key, {"$set": record})
        else:
            record["id"] = pi_id or session_id or str(uuid.uuid4())
            record["created_at"] = datetime.now(timezone.utc).isoformat()
            await get_db().payments.insert_one(record)

        # Also keep payment_sessions in sync with status
        if session_id:
            await get_db().payment_sessions.update_one(
                {"id": session_id},
                {"$set": {
                    "status": status,
                    "paymentStatus": payment_status,
                    "paymentIntentId": pi_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

        # If paid, mark the linked invoice as paid
        if invoice_id and (payment_status == "paid" or status in ("succeeded", "complete")):
            try:
                await get_db().invoices.update_one(
                    {"id": invoice_id},
                    {"$set": {
                        "status": "paid",
                        "paidAt": datetime.now(timezone.utc).isoformat(),
                        "paymentMethod": pm_type or "stripe",
                        "paymentIntentId": pi_id,
                    }},
                )
                # Auto-create the workflow / order so manager can start working.
                # Phase 5.5 / C — qualified `server._create_order_from_invoice`
                # retired in favour of the canonical home in
                # `app.services.orders.create_order_from_invoice`. Lazy import
                # mirrors the established `_get_stripe_config` / `_record_payment_from_stripe`
                # consumption shape used by the Stripe webhook integration boundary
                # at server.py:13907-13911.
                try:
                    invoice_doc = await get_db().invoices.find_one({"id": invoice_id}, {"_id": 0})
                    if invoice_doc:
                        from app.services.orders import create_order_from_invoice
                        await create_order_from_invoice(invoice_doc)
                except Exception:
                    logger.exception("[stripe] failed to auto-create order from paid invoice")
            except Exception:
                logger.exception("[stripe] failed to update invoice status")
    except Exception:
        logger.exception("[stripe] _record_payment_from_stripe failed")
@router.get("/api/admin/payments", dependencies=[Depends(require_admin)])
async def admin_list_payments(
    status: str = "",
    method: str = "",
    q: str = "",
    days: int = 90,
    limit: int = 100,
    skip: int = 0,
):
    """Master-admin: list payments with optional filters."""
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if method:
        query["method"] = method
    if q:
        query["$or"] = [
            {"customerEmail": {"$regex": q, "$options": "i"}},
            {"customerId": {"$regex": q, "$options": "i"}},
            {"invoiceId": {"$regex": q, "$options": "i"}},
            {"paymentIntentId": {"$regex": q, "$options": "i"}},
            {"sessionId": {"$regex": q, "$options": "i"}},
        ]
    if days and days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        query["created_at"] = {"$gte": cutoff}

    total = await get_db().payments.count_documents(query)
    cursor = get_db().payments.find(query, {"_id": 0}).sort("created_at", -1).skip(int(skip)).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    return {"success": True, "total": total, "items": items}


@router.get("/api/admin/payments/stats", dependencies=[Depends(require_admin)])
async def admin_payments_stats(days: int = 30):
    """Master-admin: aggregated stats."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
    base = {"created_at": {"$gte": cutoff}}
    succeeded = {**base, "status": {"$in": ["succeeded", "complete", "paid"]}}
    failed = {**base, "status": {"$in": ["failed", "canceled", "expired"]}}

    pipeline_total = [
        {"$match": succeeded},
        {"$group": {"_id": None, "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    by_method = [
        {"$match": succeeded},
        {"$group": {"_id": "$method", "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"amount": -1}},
    ]
    by_currency = [
        {"$match": succeeded},
        {"$group": {"_id": "$currency", "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    by_day = [
        {"$match": succeeded},
        {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    total_doc = await get_db().payments.aggregate(pipeline_total).to_list(length=1)
    methods = await get_db().payments.aggregate(by_method).to_list(length=50)
    currencies = await get_db().payments.aggregate(by_currency).to_list(length=50)
    daily = await get_db().payments.aggregate(by_day).to_list(length=400)

    succ_count = await get_db().payments.count_documents(succeeded)
    fail_count = await get_db().payments.count_documents(failed)
    pending_count = await get_db().payments.count_documents({**base, "status": {"$in": ["processing", "requires_payment_method", "requires_action", "open"]}})
    refund_count = await get_db().payments.count_documents({**base, "lastEvent": {"$regex": "refund"}})

    return {
        "success": True,
        "windowDays": days,
        "totalAmount": (total_doc[0]["amount"] if total_doc else 0),
        "totalCount": (total_doc[0]["count"] if total_doc else 0),
        "succeeded": succ_count,
        "failed": fail_count,
        "pending": pending_count,
        "refunded": refund_count,
        "byMethod": [{"method": (m["_id"] or "unknown"), "amount": m["amount"], "count": m["count"]} for m in methods],
        "byCurrency": [{"currency": (c["_id"] or "usd"), "amount": c["amount"], "count": c["count"]} for c in currencies],
        "daily": [{"date": d["_id"], "amount": d["amount"], "count": d["count"]} for d in daily],
    }


@router.get("/api/admin/payments/recent-events", dependencies=[Depends(require_admin)])
async def admin_recent_stripe_events(limit: int = 50):
    """Master-admin: latest webhook events received."""
    cursor = get_db().stripe_events.find({}, {"_id": 0, "raw": 0}).sort("created_at", -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    return {"success": True, "items": items}


@router.get("/api/admin/payments/{payment_id}", dependencies=[Depends(require_admin)])
async def admin_payment_detail(payment_id: str):
    """Master-admin: get one payment with fresh Stripe data."""
    p = await get_db().payments.find_one(
        {"$or": [{"id": payment_id}, {"paymentIntentId": payment_id}, {"sessionId": payment_id}]},
        {"_id": 0},
    )
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    cfg = await get_stripe_config()
    fresh: Dict[str, Any] = {}
    if cfg.get("secretKey") and p.get("paymentIntentId"):
        try:
            import stripe as _stripe  # type: ignore
            _stripe.api_key = cfg["secretKey"]
            pi = await asyncio.to_thread(
                lambda: _stripe.PaymentIntent.retrieve(p["paymentIntentId"], expand=["charges", "latest_charge"])
            )
            fresh = pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)
        except Exception as ex:
            fresh = {"error": str(ex)[:200]}

    return {"success": True, "payment": p, "stripe": fresh}


@router.post("/api/admin/payments/{payment_id}/refund", dependencies=[Depends(require_master_admin)])
async def admin_refund_payment(payment_id: str, data: Dict[str, Any] = Body(default={})):
    """Master-admin: refund a payment (full or partial). data: { amount?, reason? }"""
    p = await get_db().payments.find_one(
        {"$or": [{"id": payment_id}, {"paymentIntentId": payment_id}, {"sessionId": payment_id}]},
        {"_id": 0},
    )
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    pi = p.get("paymentIntentId")
    if not pi:
        raise HTTPException(status_code=400, detail="Payment has no PaymentIntent — cannot refund")

    cfg = await get_stripe_config()
    if not cfg.get("secretKey"):
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        import stripe as _stripe  # type: ignore
        _stripe.api_key = cfg["secretKey"]
        params = {"payment_intent": pi}
        amount = data.get("amount")
        if amount is not None:
            try:
                amt_minor = int(round(float(amount) * 100))
                if amt_minor > 0:
                    params["amount"] = amt_minor
            except Exception:
                pass
        reason = data.get("reason")
        if reason in ("duplicate", "fraudulent", "requested_by_customer"):
            params["reason"] = reason
        params["metadata"] = {"refunded_by": "master_admin", "source": "bibi-crm"}

        refund = await asyncio.to_thread(lambda: _stripe.Refund.create(**params))

        # Refresh payment record from PI
        try:
            pi_obj = await asyncio.to_thread(lambda: _stripe.PaymentIntent.retrieve(pi, expand=["charges"]))
            await _record_payment_from_stripe(pi_obj.to_dict() if hasattr(pi_obj, "to_dict") else dict(pi_obj), "refund.created")
        except Exception:
            pass

        return {"success": True, "refundId": refund.id, "status": refund.status, "amount": (refund.amount or 0) / 100}
    except Exception as ex:
        logger.exception("[stripe] refund failed")
        raise HTTPException(status_code=502, detail=f"Refund failed: {type(ex).__name__}: {str(ex)[:200]}")


@router.post("/api/admin/payments/sync", dependencies=[Depends(require_admin)])
async def admin_payments_sync(limit: int = 100):
    """Master-admin: pull recent PaymentIntents from Stripe and refresh local cache."""
    cfg = await get_stripe_config()
    if not cfg.get("secretKey"):
        raise HTTPException(status_code=503, detail="Stripe not configured")
    try:
        import stripe as _stripe  # type: ignore
        _stripe.api_key = cfg["secretKey"]
        pis = await asyncio.to_thread(lambda: _stripe.PaymentIntent.list(limit=min(int(limit), 100), expand=["data.charges"]))
        synced = 0
        for pi in pis.data:
            try:
                d = pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)
                await _record_payment_from_stripe(d, "sync")
                synced += 1
            except Exception:
                logger.exception("[stripe-sync] one PI failed")
        return {"success": True, "synced": synced, "total": len(pis.data)}
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Sync failed: {type(ex).__name__}: {str(ex)[:200]}")
