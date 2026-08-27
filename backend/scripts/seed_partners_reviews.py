"""One-off: seed demo partner + review items into the site_info doc.

These are admin-editable afterwards (Admin → Content). Idempotent: only fills
items when the corresponding list is currently empty, so it never clobbers
data an operator has already entered.
"""
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

SITE_INFO_DOC_ID = "singleton"

PARTNERS = [
    {"id": "pf-1", "enabled": True, "name_uk": "ЕкоТранс", "name_en": "EcoTrans", "logo_url": "", "link": "https://example.com/ecotrans"},
    {"id": "pf-2", "enabled": True, "name_uk": "ГрінСайкл", "name_en": "GreenCycle", "logo_url": "", "link": "https://example.com/greencycle"},
    {"id": "pf-3", "enabled": True, "name_uk": "УкрХім", "name_en": "UkrChem", "logo_url": "", "link": "https://example.com/ukrchem"},
    {"id": "pf-4", "enabled": True, "name_uk": "СейфВейст", "name_en": "SafeWaste", "logo_url": "", "link": "https://example.com/safewaste"},
    {"id": "pf-5", "enabled": True, "name_uk": "БіоНова", "name_en": "BioNova", "logo_url": "", "link": "https://example.com/bionova"},
    {"id": "pf-6", "enabled": True, "name_uk": "МеталЮА", "name_en": "MetalUA", "logo_url": "", "link": ""},
]

REVIEWS = [
    {
        "id": "rv-1", "enabled": True,
        "name": "Andriy Kovalenko", "name_uk": "Андрій Коваленко",
        "role_en": "Operations Director, ТОВ «ХімПром»", "role_uk": "Директор з операцій, ТОВ «ХімПром»",
        "text_en": "ECO.NOVA took full documentary responsibility for our hazardous waste. Clear pricing, on-time pickups and every act signed digitally.",
        "text_uk": "ECO.NOVA взяла на себе весь документообіг щодо наших небезпечних відходів. Прозорі ціни, вчасні вивози та всі акти підписані онлайн.",
        "rating": 5, "image_url": "",
    },
    {
        "id": "rv-2", "enabled": True,
        "name": "Olena Bondar", "name_uk": "Олена Бондар",
        "role_en": "Head of ESG, Manufacturing Group", "role_uk": "Керівник ESG, виробнича група",
        "text_en": "The transparent B2B cabinet is exactly what we needed — requests, contracts and invoices in one place. Support is fast and competent.",
        "text_uk": "Прозорий B2B-кабінет — саме те, що нам було потрібно: заявки, договори та рахунки в одному місці. Підтримка швидка й компетентна.",
        "rating": 5, "image_url": "",
    },
    {
        "id": "rv-3", "enabled": True,
        "name": "Ihor Melnyk", "name_uk": "Ігор Мельник",
        "role_en": "Plant Manager", "role_uk": "Керівник заводу",
        "text_en": "Licensed operator with a real utilization complex. Waste codes, volumes and compliance reports were handled professionally.",
        "text_uk": "Ліцензований оператор із реальним комплексом утилізації. Коди відходів, обсяги та звіти про відповідність опрацьовані професійно.",
        "rating": 4.5, "image_url": "",
    },
    {
        "id": "rv-4", "enabled": True,
        "name": "Kateryna Shevchenko", "name_uk": "Катерина Шевченко",
        "role_en": "Procurement Lead, Retail Chain", "role_uk": "Керівник закупівель, торгова мережа",
        "text_en": "From the first request to the signed act — a smooth, predictable process. The cost calculator gave us an accurate estimate up front.",
        "text_uk": "Від першої заявки до підписаного акта — плавний, передбачуваний процес. Калькулятор вартості одразу дав точну оцінку.",
        "rating": 5, "image_url": "",
    },
]


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    if not doc:
        # Trigger default seeding shape
        doc = {"_id": SITE_INFO_DOC_ID}

    partners = doc.get("partners") or {}
    reviews = doc.get("reviews") or {}

    updates = {}
    if not (partners.get("items") or []):
        updates["partners.items"] = PARTNERS
        updates["partners.enabled"] = True
    if not (reviews.get("items") or []):
        updates["reviews.items"] = REVIEWS
        updates["reviews.enabled"] = True

    if not updates:
        print("Nothing to seed — items already present.")
        return

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = "seed_script"
    await db.site_info.update_one({"_id": SITE_INFO_DOC_ID}, {"$set": updates}, upsert=True)
    print(f"Seeded: {list(updates.keys())}")

    check = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    print("partners items:", len((check.get('partners') or {}).get('items') or []))
    print("reviews items:", len((check.get('reviews') or {}).get('items') or []))


if __name__ == "__main__":
    asyncio.run(main())
