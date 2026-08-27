#!/usr/bin/env python3
"""One-shot FORCE reseed of the waste catalogue from the official national list.

Wipes waste_codes / chapters / groups / license matrix and reseeds everything
from /app/data/national_waste_list.json (via app.waste.national_data).
"""
import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(override=False)


async def main():
    from app.waste import service as S

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "eco_platform")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"DB = {db_name}")
    await S.ensure_indexes(db)

    print(">> force reseed waste codes (drop & seed)...")
    res_codes = await S.seed_waste_codes(db, force=True)
    print("   ", res_codes)

    print(">> force reseed license matrix (all official codes)...")
    res_lic = await S.seed_license_matrix(db, force=True)
    print("   ", res_lic)

    print(">> reseed price rules for accepted codes...")
    try:
        res_price = await S.seed_price_rules(db)
        print("   ", res_price)
    except Exception as e:
        print("   price rules skipped:", e)

    print(">> reseed categories...")
    try:
        res_cat = await S.seed_waste_categories(db, force=True)
        print("   ", res_cat)
    except Exception as e:
        print("   categories skipped:", e)

    # Final tallies
    total = await db[S.C_CODES].count_documents({})
    haz = await db[S.C_CODES].count_documents({"hazardous": True})
    accepted = await db[S.C_CODES].count_documents({"accepted": True})
    chapters = await db[S.C_CHAPTERS].count_documents({})
    groups = await db[S.C_GROUPS].count_documents({})
    print("\n=== FINAL ===")
    print(f"codes={total} hazardous={haz} accepted={accepted} chapters={chapters} groups={groups}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
