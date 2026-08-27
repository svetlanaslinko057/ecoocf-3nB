#!/usr/bin/env python3
"""
setup_stripe_webhook.py — multi-domain Stripe webhook provisioning for BIBI.

A single backend (sharing one MongoDB) can serve SEVERAL public domains at the
same time — e.g. while migrating from ``bibicars.org`` to ``bibicars.bg``. Each
Stripe webhook endpoint has its OWN signing secret, so we keep a LIST of secrets
in the integration config (``credentials.webhookSecrets``). The webhook handler
accepts an event if ANY of those secrets validates the signature.

WHAT IT DOES (per run, for ONE --domain)
────────────────────────────────────────
  1. Recreates ONLY the webhook endpoint for THAT domain (other domains'
     endpoints are left intact).
  2. Subscribes it to the 10 events the handler processes.
  3. Merges the new signing secret into ``credentials.webhookSecrets`` (dedup)
     and also sets it as the primary ``credentials.webhookSecret``.

USAGE
─────
    # First domain (current):
    python scripts/setup_stripe_webhook.py --domain https://bibicars.org

    # Later, ADD a second domain without breaking the first:
    python scripts/setup_stripe_webhook.py --domain https://bibicars.bg

    # Remove a domain that is no longer used:
    python scripts/setup_stripe_webhook.py --domain https://old-domain.com --remove

The Stripe secret key is read from the integration config in Mongo (saved via
/admin/payments). Pass --secret-key only for first-time bootstrap.
"""
import argparse
import asyncio
import os
import sys

import stripe
from motor.motor_asyncio import AsyncIOMotorClient

ENABLED_EVENTS = [
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "payment_intent.canceled",
    "payment_intent.processing",
    "charge.refunded",
    "charge.refund.updated",
]


async def _load_secret_key(db) -> str:
    doc = await db.integration_configs.find_one({"provider": "stripe"}) or {}
    creds = doc.get("credentials") or {}
    return (creds.get("secretKey") or creds.get("restrictedKey") or "").strip()


async def _current_secrets(db) -> list:
    doc = await db.integration_configs.find_one({"provider": "stripe"}) or {}
    creds = doc.get("credentials") or {}
    out = []
    if isinstance(creds.get("webhookSecret"), str) and creds["webhookSecret"].strip():
        out.append(creds["webhookSecret"].strip())
    for s in creds.get("webhookSecrets") or []:
        if isinstance(s, str) and s.strip():
            out.append(s.strip())
    return list(dict.fromkeys(out))


def _delete_endpoint_for(url: str):
    for ep in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        if ep.url == url:
            stripe.WebhookEndpoint.delete(ep.id)


def _create_endpoint(url: str) -> stripe.WebhookEndpoint:
    _delete_endpoint_for(url)
    return stripe.WebhookEndpoint.create(
        url=url,
        enabled_events=ENABLED_EVENTS,
        description="BIBI Cars — multi-domain",
    )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, help="Public base URL, e.g. https://bibicars.bg")
    ap.add_argument("--secret-key", default="", help="Stripe secret key (optional; else read from Mongo)")
    ap.add_argument("--remove", action="store_true", help="Remove this domain's endpoint + secret")
    ap.add_argument("--mongo-url", default=os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    ap.add_argument("--db-name", default=os.environ.get("DB_NAME", "bibi_cars"))
    args = ap.parse_args()

    webhook_url = args.domain.rstrip("/") + "/api/stripe/webhook"
    client = AsyncIOMotorClient(args.mongo_url)
    db = client[args.db_name]

    secret_key = args.secret_key.strip() or await _load_secret_key(db)
    if not secret_key:
        print("ERROR: no Stripe secret key (pass --secret-key or save it in /admin/payments first).")
        return 1
    stripe.api_key = secret_key

    if args.remove:
        await asyncio.to_thread(_delete_endpoint_for, webhook_url)
        print(f"Removed endpoint for {webhook_url} (secrets list left untouched; rotate if needed).")
        return 0

    print(f"Provisioning webhook at: {webhook_url}")
    ep = await asyncio.to_thread(_create_endpoint, webhook_url)
    whsec = ep.secret

    existing = await _current_secrets(db)
    merged = list(dict.fromkeys([whsec] + existing))  # new secret first
    await db.integration_configs.update_one(
        {"provider": "stripe"},
        {"$set": {"credentials.webhookSecret": whsec, "credentials.webhookSecrets": merged}},
        upsert=True,
    )

    print("✓ Done")
    print(f"  endpoint id    : {ep.id}")
    print(f"  status         : {ep.status}")
    print(f"  events         : {len(ep.enabled_events)}")
    print(f"  whsec          : {whsec[:12]}…{whsec[-4:]}")
    print(f"  total secrets  : {len(merged)} (this backend now accepts {len(merged)} domain(s))")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
