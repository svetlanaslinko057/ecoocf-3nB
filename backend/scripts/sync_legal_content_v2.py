#!/usr/bin/env python3
"""Push the full-length legal texts (app/constants/legal_texts.py) into the
live `site_info` document. Idempotent — safe to run multiple times.

Usage:  cd /app/backend && python scripts/sync_legal_content_v2.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from app.constants.legal_texts import LEGAL_POLICIES  # noqa: E402


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    doc = await db.site_info.find_one({})
    if not doc:
        print("no site_info doc found — backend startup will seed defaults (already using new texts)")
        return

    res = await db.site_info.update_one(
        {"_id": doc["_id"]},
        {"$set": {"policies": LEGAL_POLICIES}},
    )
    print(f"site_info policies updated (matched={res.matched_count}, modified={res.modified_count})")
    for key, langs in LEGAL_POLICIES.items():
        print(f"  • {key}: uk={len(langs['uk']['content'])} chars, en={len(langs['en']['content'])} chars")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
