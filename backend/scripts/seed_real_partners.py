"""Replace the demo partner items with REAL Ukrainian companies + their real
logos (stored locally under /api/static/partners/). Idempotent overwrite of
the partners.items list. Admin-editable afterwards.
"""
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
SITE_INFO_DOC_ID = "singleton"

PARTNERS = [
    {"id": "pf-darnitsa", "enabled": True, "name_uk": "Дарниця", "name_en": "Darnitsa",
     "logo_url": "/api/static/partners/darnitsa.png", "link": "https://www.darnitsa.ua"},
    {"id": "pf-farmak", "enabled": True, "name_uk": "Фармак", "name_en": "Farmak",
     "logo_url": "/api/static/partners/farmak.png", "link": "https://farmak.ua"},
    {"id": "pf-mhp", "enabled": True, "name_uk": "МХП", "name_en": "MHP",
     "logo_url": "/api/static/partners/mhp.png", "link": "https://www.mhp.com.ua"},
    {"id": "pf-astarta", "enabled": True, "name_uk": "Астарта-Київ", "name_en": "Astarta",
     "logo_url": "/api/static/partners/astarta.png", "link": "https://astartaholding.com"},
    {"id": "pf-nibulon", "enabled": True, "name_uk": "НІБУЛОН", "name_en": "Nibulon",
     "logo_url": "/api/static/partners/nibulon.png", "link": "https://www.nibulon.com"},
    {"id": "pf-epicentr", "enabled": True, "name_uk": "Епіцентр", "name_en": "Epicentr",
     "logo_url": "/api/static/partners/epicentr.png", "link": "https://epicentrk.ua"},
    {"id": "pf-obolon", "enabled": True, "name_uk": "Оболонь", "name_en": "Obolon",
     "logo_url": "/api/static/partners/obolon.png", "link": "https://obolon.ua"},
    {"id": "pf-roshen", "enabled": True, "name_uk": "Рошен", "name_en": "Roshen",
     "logo_url": "/api/static/partners/roshen.png", "link": "https://www.roshen.com"},
]


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "test_database")]

    # Guard: only (re)seed when the partners list is empty or still contains
    # demo/seed placeholders. Never overwrite partners an admin has curated.
    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID}) or {}
    existing = ((doc.get("partners") or {}).get("items")) or []
    admin_curated = [
        it for it in existing
        if not str(it.get("id", "")).startswith(("demo-partner-", "pf-"))
    ]
    if existing and admin_curated:
        print(f"partners: admin-curated items present ({len(admin_curated)}) — skipping real seed")
        client.close()
        return

    await db.site_info.update_one(
        {"_id": SITE_INFO_DOC_ID},
        {"$set": {
            "partners.items": PARTNERS,
            "partners.enabled": True,
            "partners.title_uk": "Наші клієнти та партнери",
            "partners.title_en": "Our clients & partners",
            "partners.subtitle_uk": "Українські компанії, які довіряють нам поводження з небезпечними відходами",
            "partners.subtitle_en": "Ukrainian companies that trust us with hazardous-waste management",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "real_partners_seed",
        }},
        upsert=True,
    )
    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    items = (doc.get("partners") or {}).get("items") or []
    print("partners now:", len(items))
    for it in items:
        print(" -", it["name_en"], it["logo_url"])
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
