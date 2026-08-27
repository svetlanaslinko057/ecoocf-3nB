"""Seed demo client reviews into site_info.reviews.items (idempotent).

The public homepage renders reviews as an auto-scrolling marquee of cards
(rating dots + X/5, quote, avatar + name). Reviews are fully admin-managed
(Admin → Info → Reviews). Demo items (id starting with 'demo-review-') are
replaced on every run; real admin-added reviews are preserved.
"""
import asyncio
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
SITE_INFO_DOC_ID = "singleton"

DEMO = [
    {
        "name": "Oksana Petrenko",
        "name_uk": "Оксана Петренко",
        "role_uk": "Директорка, МедЦентр «Здоров'я»",
        "role_en": "Director, Zdorovya Medical Center",
        "rating": 5,
        "text_uk": "Повний супровід від класифікації до акта утилізації. Усі документи — бездоганні, жодного питання від перевіряючих органів.",
        "text_en": "Full support from classification to the utilisation act. All documents were flawless — not a single question from the inspectors.",
    },
    {
        "name": "Andriy Kovalenko",
        "name_uk": "Андрій Коваленко",
        "role_uk": "Головний інженер, ПромЗавод",
        "role_en": "Chief Engineer, PromZavod",
        "rating": 5,
        "text_uk": "Вивезли 4 клас небезпеки чітко за графіком. Прозоре ціноутворення і зручний кабінет клієнта — бачу кожен етап.",
        "text_en": "Class-4 hazardous waste was collected exactly on schedule. Transparent pricing and a handy client cabinet — I see every stage.",
    },
    {
        "name": "Iryna Bondar",
        "name_uk": "Ірина Бондар",
        "role_uk": "Еколог, АгроХолдинг",
        "role_en": "Ecologist, AgroHolding",
        "rating": 4.5,
        "text_uk": "Допомогли розібратися з кодами відходів і оформити всі ліцензійні документи. Команда завжди на зв'язку.",
        "text_en": "They helped us sort out the waste codes and prepare every licensing document. The team is always in touch.",
    },
    {
        "name": "Serhiy Marchenko",
        "name_uk": "Сергій Марченко",
        "role_uk": "Власник, Автосервіс №1",
        "role_en": "Owner, Auto Service #1",
        "rating": 5,
        "text_uk": "Відпрацьовані оливи та фільтри — забирають регулярно, без затримок. Нарешті спокій із екологічною звітністю.",
        "text_en": "Used oils and filters are picked up regularly, no delays. Finally, peace of mind with environmental reporting.",
    },
    {
        "name": "Nataliia Shevchuk",
        "name_uk": "Наталія Шевчук",
        "role_uk": "Менеджерка, Фарм Дистриб'юшн",
        "role_en": "Manager, Pharma Distribution",
        "rating": 5,
        "text_uk": "Утилізація прострочених медикаментів пройшла швидко й законно. Отримали акт того ж тижня.",
        "text_en": "Disposal of expired medicines was fast and fully compliant. We received the act the same week.",
    },
    {
        "name": "Volodymyr Tkachenko",
        "name_uk": "Володимир Ткаченко",
        "role_uk": "Директор з виробництва, ХімТех",
        "role_en": "Production Director, ChemTech",
        "rating": 4.5,
        "text_uk": "Складні хімічні відходи — не проблема для ECO.NOVA. Професійний підхід і чесні строки.",
        "text_en": "Complex chemical waste is not a problem for ECO.NOVA. Professional approach and honest timelines.",
    },
]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    if not doc:
        doc = {"_id": SITE_INFO_DOC_ID}
    reviews = doc.get("reviews") or {}
    items = reviews.get("items") or []
    items = [it for it in items if not str(it.get("id", "")).startswith("demo-review-")]
    demo_items = [
        {
            "id": f"demo-review-{i+1}",
            "enabled": True,
            "name": d["name"],
            "name_uk": d["name_uk"],
            "role_uk": d["role_uk"],
            "role_en": d["role_en"],
            "image_url": "",
            "rating": d["rating"],
            "text_uk": d["text_uk"],
            "text_en": d["text_en"],
        }
        for i, d in enumerate(DEMO)
    ]
    items = demo_items + items
    reviews.update({
        "enabled": True,
        "title_uk": reviews.get("title_uk") or "Що кажуть наші клієнти",
        "title_en": reviews.get("title_en") or "What our clients say",
        "subtitle_uk": reviews.get("subtitle_uk") or "Підприємства, що довірили нам утилізацію небезпечних відходів",
        "subtitle_en": reviews.get("subtitle_en") or "Businesses that trusted us with their hazardous-waste utilisation",
        "items": items,
    })
    await db.site_info.update_one(
        {"_id": SITE_INFO_DOC_ID},
        {"$set": {"reviews": reviews, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    fresh = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    total = len(fresh["reviews"]["items"])
    demo = sum(1 for i in fresh["reviews"]["items"] if str(i.get("id", "")).startswith("demo-review-"))
    print(f"[seed_reviews] OK: {total} total reviews, {demo} demo")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
