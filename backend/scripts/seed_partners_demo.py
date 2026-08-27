"""Seed demo "friends" (partners) into site_info.partners.items (idempotent).

The public homepage renders partners as a clean, auto-scrolling logo / wordmark
marquee (the "Наші френди" block). Each item carries a bilingual name, an
optional uploaded logo (grayscale in the strip) and an outbound link. Demo
items (id starting with 'demo-partner-') are replaced on every run; real
admin-added partners are preserved.
"""
import asyncio
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
SITE_INFO_DOC_ID = "singleton"

DEMO = [
    {"name_uk": "ЕкоГрін Логістик", "name_en": "EcoGreen Logistics", "link": "https://example.com/ecogreen"},
    {"name_uk": "ТехноРециклінг", "name_en": "TechnoRecycling", "link": "https://example.com/technorecycling"},
    {"name_uk": "ЕкоЛаб", "name_en": "EcoLab", "link": "https://example.com/ecolab"},
    {"name_uk": "УкрХімПром", "name_en": "UkrChemProm", "link": "https://example.com/ukrchemprom"},
    {"name_uk": "БіоСфера", "name_en": "BioSphere", "link": "https://example.com/biosphere"},
    {"name_uk": "МедУтиль", "name_en": "MedUtil", "link": "https://example.com/medutil"},
    {"name_uk": "ГрінВей", "name_en": "GreenWay", "link": "https://example.com/greenway"},
    {"name_uk": "ЕнергоВторма", "name_en": "EnergoVtorma", "link": "https://example.com/energovtorma"},
]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    if not doc:
        doc = {"_id": SITE_INFO_DOC_ID}
    partners = doc.get("partners") or {}
    items = partners.get("items") or []
    # drop any previously seeded demo items, keep real ones
    items = [it for it in items if not str(it.get("id", "")).startswith("demo-partner-")]
    demo_items = [
        {
            "id": f"demo-partner-{i+1}",
            "enabled": True,
            "name_uk": d["name_uk"],
            "name_en": d["name_en"],
            "desc_uk": "",
            "desc_en": "",
            "logo_url": "",
            "image_url": "",
            "link": d["link"],
        }
        for i, d in enumerate(DEMO)
    ]
    items = demo_items + items
    partners.update({
        "enabled": True,
        "title_uk": partners.get("title_uk") or "Наші френди",
        "title_en": partners.get("title_en") or "Our friends",
        "subtitle_uk": partners.get("subtitle_uk") or "Компанії та організації, що працюють з ECO.NOVA",
        "subtitle_en": partners.get("subtitle_en") or "Companies and organisations that work with ECO.NOVA",
        "items": items,
    })
    await db.site_info.update_one(
        {"_id": SITE_INFO_DOC_ID},
        {"$set": {"partners": partners, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    fresh = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    total = len(fresh["partners"]["items"])
    demo = sum(1 for i in fresh["partners"]["items"] if str(i.get("id", "")).startswith("demo-partner-"))
    print(f"[seed_partners] OK: {total} total friends, {demo} demo")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
