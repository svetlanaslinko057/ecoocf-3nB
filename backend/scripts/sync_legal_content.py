"""One-time: sync site_info.policies + cookie_banner to current ECO.NOVA defaults.

The seeded DB doc still held the old BiBi-Cars (en/bg) content which overrides
the module defaults in the deep-merge. This overwrites those two subtrees with
the fresh DEFAULT_SITE_INFO values (uk/en, ECO.NOVA branded).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from app.routers.content import DEFAULT_SITE_INFO, SITE_INFO_DOC_ID  # noqa: E402


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME") or "test_database"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    res = await db.site_info.update_one(
        {"_id": SITE_INFO_DOC_ID},
        {"$set": {
            "policies": DEFAULT_SITE_INFO["policies"],
            "cookie_banner": DEFAULT_SITE_INFO["cookie_banner"],
        }},
        upsert=True,
    )
    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    print("matched:", res.matched_count, "modified:", res.modified_count, "upserted:", res.upserted_id)
    print("policy keys:", list((doc.get("policies") or {}).keys()))
    print("privacy langs:", list((doc.get("policies", {}).get("privacy") or {}).keys()))
    print("cookie_banner:", {k: (v if isinstance(v, bool) else str(v)[:40]) for k, v in (doc.get("cookie_banner") or {}).items()})
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
