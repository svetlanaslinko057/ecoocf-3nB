"""
app/services/stripe_config.py — Stripe config service module.

This module is the **canonical home** for the Stripe configuration
resolver helper, extracted as part of Phase 5.5 / E (2026-05-19).

Migration history
─────────────────

  * Pre-Wave-1:  ``server._get_stripe_config`` (private name, lived
                 alongside Stripe webhook + checkout handlers inside
                 the monolith ``server.py``).
  * Wave 1:      moved to ``app.routers.payments._get_stripe_config``
                 when the payments router was carved out. Intent was
                 mechanical co-location with the payment endpoints,
                 NOT a final architectural home.
  * Phase 5.5/E: moved HERE (``app.services.stripe_config``) and
                 renamed to the public ``get_stripe_config`` (no
                 leading underscore — same precedent as Phase 5.5/C
                 ``create_order_from_invoice`` and Phase 5.5/D
                 ``require_customer`` / ``ensure_customer_seed``).

Why this lives in ``services`` and not ``routers``
──────────────────────────────────────────────────

The function is a **domain/configuration helper** — it reads from the
``integration_configs`` collection and returns a shaped Stripe
configuration dict consumed by:

  * payment-flow endpoints (checkout session, refund, sync) — 7
    callers inside ``app/routers/payments.py``
  * legal-deposit checkout bridge — 1 caller in ``server.py``
  * Stripe webhook handler — 1 caller in ``server.py``
  * cabinet-flow checkout — 1 caller in ``cabinet_financials.py``

This is a cross-domain config resolver, not a router-internal helper.
Living in a router module was an accidental Wave-1 placement; living
in ``app/services/`` matches the established extraction taxonomy
(``app/services/orders.py``, ``app/services/customers.py``,
``app/services/calculator.py``).

NOT an ``app/core/`` runtime accessor
─────────────────────────────────────

``app/core/`` is reserved for **runtime-owned mutable singletons** —
``db_runtime``, ``socket_runtime``, ``aggregator_runtime``,
``audit_runtime``, ``tracking_config_service``. Those publish a
``set_X`` / ``get_X`` accessor pair invoked from startup. Stripe
config has no such lifecycle: it's a pure-read helper that hits the
``integration_configs`` collection on every call (cache-free by
design — admin config changes propagate without restart).

Latent bug repaired in 5.5/E
────────────────────────────

Step-1 audit surfaced that ``cabinet_financials.py:366`` carried a
``from server import _get_stripe_config`` lazy WPS433 bridge — but
``server`` never exported the symbol module-level. The line ALWAYS
raised ``ImportError`` at runtime, and the surrounding
``except Exception`` masked the failure: the cabinet checkout flow
silently degraded to its "Онлайн-оплата картою тимчасово недоступна"
stub mode. After 5.5/E the cabinet flow imports
``get_stripe_config`` from THIS module and the Stripe path is
actually exercised. See ``PHASE5_5_E_STRIPE_CONFIG_CLOSED.md``
section 4 ("Intentional behaviour repair scope").

Public surface
──────────────

  * ``get_stripe_config()`` — single async callable, returns
    ``Dict[str, Any]`` with 18 stable keys (see docstring).

No additional public symbols exported. ``IntegrationConfigsRepository``
is the canonical owner of the underlying collection; this module
only reshapes its output.
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.db_runtime import get_db

__all__ = ["get_stripe_config"]


async def get_stripe_config() -> Dict[str, Any]:
    """Load Stripe credentials + settings from the
    ``integration_configs`` collection and return a shaped 18-key
    config dict.

    Returns
    -------
    Dict[str, Any]
        Stable 18-key shape (legacy contract preserved 1:1 from
        ``app/routers/payments._get_stripe_config`` pre-5.5/E):

        Credentials (4 strings — empty if not configured):
          * ``secretKey``         — Stripe Secret Key (``sk_*``)
          * ``restrictedKey``     — Stripe Restricted Key (``rk_*``)
          * ``publishableKey``    — Stripe Publishable Key (``pk_*``)
          * ``webhookSecret``     — Stripe webhook signing secret
                                    (``whsec_*``)

        Behavioural settings (10):
          * ``currency``          — lowercased ISO-4217 code
                                    (default ``"usd"``)
          * ``paymentMethods``    — list[str], derived from
                                    ``enabledMethods`` minus wallet
                                    entries (``apple_pay``,
                                    ``google_pay``); ``card`` always
                                    present when any wallet enabled;
                                    default ``["card"]``
          * ``enabledMethods``    — dict[str, bool] — source of truth
                                    for payment-method enablement
                                    (back-compat: legacy
                                    ``settings.paymentMethods`` list
                                    is converted to this dict shape
                                    when ``enabledMethods`` absent);
                                    default ``{"card": True}``
          * ``checkoutMode``      — ``"hosted" | "embedded"``
                                    (default ``"hosted"``)
          * ``automaticPaymentMethods`` — bool (default ``True``)
          * ``captureMethod``     — ``"automatic" | "manual"``
                                    (default ``"automatic"``)
          * ``statementDescriptor`` — str, truncated to 22 chars
                                      (Stripe limit; default ``""``)
          * ``successUrl``        — str, default
                                    ``"/cabinet/payment/success"``
          * ``cancelUrl``         — str, default
                                    ``"/cabinet/payment/cancel"``
          * ``allowPromotionCodes`` — bool (default ``True``)
          * ``billingAddressCollection`` — ``"auto" | "required"``
                                           (default ``"auto"``)
          * ``phoneNumberCollection`` — bool (default ``False``)

        Lifecycle flags (2):
          * ``isEnabled``         — bool — whether the admin has
                                    enabled Stripe integration
                                    (default ``False``)
          * ``mode``              — ``"sandbox" | "live"``
                                    (default ``"sandbox"``)

    Notes
    -----
    * When ``find_by_provider("stripe")`` returns ``{}`` (no doc),
      the helper returns the default shape (creds empty, defaults
      applied, ``isEnabled=False``, ``mode="sandbox"``).
    * Apple Pay / Google Pay are wallets riding on the ``card``
      method type — they're excluded from ``paymentMethods`` but
      ``card`` is force-included whenever any wallet is enabled.
    * No env-variable fallback by design — the collection is the
      single source of truth (admin manages it via
      ``PATCH /api/admin/integrations/stripe``).
    """
    # Phase 5.4 / C-2 — Stripe config lookup routes through
    # IntegrationConfigsRepository (single read consolidates all callers).
    from app.repositories import IntegrationConfigsRepository
    doc = await IntegrationConfigsRepository(get_db()).find_by_provider("stripe")
    creds = doc.get("credentials") or {}
    settings = doc.get("settings") or {}

    # New richer enabledMethods dict (preferred source-of-truth)
    enabled_methods = settings.get("enabledMethods") or {}
    if not isinstance(enabled_methods, dict):
        enabled_methods = {}

    # Back-compat: legacy paymentMethods list
    legacy_pm = settings.get("paymentMethods")
    if isinstance(legacy_pm, list) and legacy_pm and not enabled_methods:
        enabled_methods = {m: True for m in legacy_pm}

    if not enabled_methods:
        enabled_methods = {"card": True}

    # Apple Pay / Google Pay are wallets that ride on the `card` method type.
    # When `automaticPaymentMethods=True` Stripe auto-shows them based on
    # device/browser support; we still keep flags so admin sees clear state.
    pm_list = [k for k, v in enabled_methods.items() if v and k not in ("apple_pay", "google_pay")]
    if "card" not in pm_list and (enabled_methods.get("apple_pay") or enabled_methods.get("google_pay")):
        pm_list.append("card")
    if not pm_list:
        pm_list = ["card"]

    return {
        "secretKey": (creds.get("secretKey") or "").strip(),
        "restrictedKey": (creds.get("restrictedKey") or "").strip(),
        "publishableKey": (creds.get("publishableKey") or "").strip(),
        "webhookSecret": (creds.get("webhookSecret") or "").strip(),
        "webhookSecrets": [
            s.strip()
            for s in (creds.get("webhookSecrets") or [])
            if isinstance(s, str) and s.strip()
        ],
        "currency": (settings.get("currency") or "USD").lower(),
        "paymentMethods": pm_list,
        "enabledMethods": enabled_methods,
        "checkoutMode": (settings.get("checkoutMode") or "hosted"),
        "automaticPaymentMethods": bool(settings.get("automaticPaymentMethods", True)),
        "captureMethod": (settings.get("captureMethod") or "automatic"),
        "statementDescriptor": (settings.get("statementDescriptor") or "")[:22],
        "successUrl": settings.get("successUrl") or "/cabinet/payment/success",
        "cancelUrl": settings.get("cancelUrl") or "/cabinet/payment/cancel",
        "allowPromotionCodes": bool(settings.get("allowPromotionCodes", True)),
        "billingAddressCollection": (settings.get("billingAddressCollection") or "auto"),
        "phoneNumberCollection": bool(settings.get("phoneNumberCollection", False)),
        "isEnabled": bool(doc.get("isEnabled", False)),
        "mode": doc.get("mode") or "sandbox",
    }
