#!/usr/bin/env python3
"""
cleanup_demo_customer_data.py
=============================

One-off, SAFE cleanup of the legacy DEMO/seed artefacts that the old
``ensure_customer_seed`` subsystem used to create before the cabinet was
converted to production data mode. It removes, by STRICT WHITELIST:

  1. Demo BUSINESS documents with deterministic, demo-only id prefixes
     (deals / shipments / shipment_events / invoices / payments / contracts /
     carfax / notifications / leads / deposits).
  2. Seeded / test CUSTOMER accounts (``seeded == True`` or ``source`` in
     {seed, test} or known historical test ids/emails).

SAFETY
------
* DRY-RUN BY DEFAULT — prints what *would* be deleted; writes NOTHING.
* Add ``--apply`` to actually delete.
* STRICT WHITELIST — only documents matching the demo id prefixes / seed
  markers are ever touched. Real customer data is never matched.
* NEVER auto-runs — must be invoked manually.

USAGE
-----
    # Dry-run (scan everything, write nothing):
    python scripts/cleanup_demo_customer_data.py

    # Dry-run for a single customer id:
    python scripts/cleanup_demo_customer_data.py --customer <customer_id>

    # Actually delete everything matched:
    python scripts/cleanup_demo_customer_data.py --apply

    # Actually delete for one customer only:
    python scripts/cleanup_demo_customer_data.py --customer <customer_id> --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

from motor.motor_asyncio import AsyncIOMotorClient

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

# Historical seed/test accounts (whitelist) — removed in production data mode.
LEGACY_TEST_CUSTOMER_IDS = {"test_customer_001", "test_user_bibi"}
LEGACY_TEST_CUSTOMER_EMAILS = {"test@customer.com", "user@bibi.cars"}

# (collection, id-field, list-of-prefixes) — each prefix is followed by the
# customer_id. These mirror the deterministic ids the demo seeder produced.
DEMO_SPECS = [
    ("deals",            "id",         ["deal_{cid}_"]),
    ("shipments",        "id",         ["ship_{cid}_"]),
    ("shipment_events",  "shipmentId", ["ship_{cid}_"]),
    ("invoices",         "id",         ["inv_{cid}_", "fin-final-{cid}-"]),
    ("payments",         "id",         ["pay-{cid}-"]),
    ("contracts",        "id",         ["ctr_{cid}_"]),
    ("carfax_reports",   "id",         ["carfax_{cid}_"]),
    ("notifications",    "id",         ["notif_{cid}_"]),
    ("leads",            "id",         ["lead_{cid}_"]),
    ("deposits",         "id",         ["dep_{cid}_"]),
]


def _regex_for(prefixes, cid):
    parts = [re.escape(p.format(cid=cid)) for p in prefixes]
    return {"$regex": f"^(?:{'|'.join(parts)})"}


async def _discover_customers(db):
    """Return customer_ids that still carry demo deals (the reliable anchor)."""
    cids = set()
    cursor = db.deals.find({"id": {"$regex": r"^deal_.+_[0-9]+$"}}, {"id": 1, "customerId": 1})
    async for d in cursor:
        cid = d.get("customerId")
        if not cid:
            m = re.match(r"^deal_(.+)_[0-9]+$", d.get("id", ""))
            cid = m.group(1) if m else None
        if cid:
            cids.add(cid)
    return sorted(cids)


async def _process_customer_business(db, cid, apply):
    total = 0
    per_coll = {}
    for coll, field, prefixes in DEMO_SPECS:
        query = {field: _regex_for(prefixes, cid)}
        count = await db[coll].count_documents(query)
        if count:
            per_coll[coll] = count
            total += count
            if apply:
                await db[coll].delete_many(query)
    return total, per_coll


async def _cleanup_seed_accounts(db, apply):
    """Remove seeded/test customer accounts by strict whitelist."""
    query = {"$or": [
        {"seeded": True},
        {"source": {"$in": ["seed", "test"]}},
        {"id": {"$in": list(LEGACY_TEST_CUSTOMER_IDS)}},
        {"email": {"$in": list(LEGACY_TEST_CUSTOMER_EMAILS)}},
    ]}
    docs = await db.customers.find(query, {"id": 1, "email": 1}).to_list(1000)
    if docs and apply:
        await db.customers.delete_many(query)
        # also drop their auth sessions
        ids = [d.get("id") for d in docs if d.get("id")]
        if ids:
            await db.customer_sessions.delete_many({"customerId": {"$in": ids}})
    return docs


async def main():
    ap = argparse.ArgumentParser(description="Remove legacy demo cabinet data + seed accounts (dry-run by default).")
    ap.add_argument("--customer", help="Target a single customer_id (business data only)")
    ap.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    ap.add_argument("--skip-accounts", action="store_true", help="Do not touch seed/test customer accounts")
    args = ap.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL not set in environment/.env", file=sys.stderr)
        sys.exit(2)
    db_name = os.environ.get("DB_NAME", "bibi_crm")
    db = AsyncIOMotorClient(mongo_url)[db_name]

    mode = "APPLY (DELETING)" if args.apply else "DRY-RUN (no writes)"
    print(f"=== cleanup_demo_customer_data — {mode} | db={db_name} ===\n")

    targets = [args.customer] if args.customer else await _discover_customers(db)

    grand_total = 0
    cleaned_customers = 0
    for cid in targets:
        total, per_coll = await _process_customer_business(db, cid, args.apply)
        if total:
            cleaned_customers += 1
            grand_total += total
            breakdown = ", ".join(f"{k}={v}" for k, v in per_coll.items())
            verb = "deleted" if args.apply else "would delete"
            print(f"- {cid}: {verb} {total} demo business docs  [{breakdown}]")

    if not args.skip_accounts and not args.customer:
        accounts = await _cleanup_seed_accounts(db, args.apply)
        if accounts:
            verb = "deleted" if args.apply else "would delete"
            listing = ", ".join(f"{d.get('email') or d.get('id')}" for d in accounts)
            print(f"\n- seed/test ACCOUNTS: {verb} {len(accounts)}  [{listing}]")

    print(f"\n=== Summary: {grand_total} demo business docs across {cleaned_customers} customer(s) "
          f"{'DELETED' if args.apply else 'matched (dry-run)'} ===")
    if not args.apply and (grand_total or not args.skip_accounts):
        print("Re-run with --apply to perform the deletion.")


if __name__ == "__main__":
    asyncio.run(main())
