"""
content — Content domain HTTP surface (site-info + blog)
=========================================================

Wave 2B / Batch 7 / Commit 13 (Content cluster).

Architectural scope:
   This is the FIRST Wave 2B batch that extracts BEYOND the admin surface.
   The blog_articles and site_info collections have both PUBLIC and ADMIN
   consumers; extracting only the admin endpoints would split collection
   ownership across two files (server.py + admin_content.py), which
   contradicts the Wave 2B invariant "no router owns more than one Mongo
   collection AND no collection is owned by more than one location".

   Cluster #2 in WAVE2_ADMIN_MAPPING.md was therefore widened from the
   admin-only scope (10 endpoints, blog 6 + site-info 4) to the FULL
   Content domain (14 endpoints + helpers + default seed):

   Two co-mounted APIRouter instances are exposed:
     * site_info_router  → /api/site-info/*    (public, 2)
                           /api/admin/site-info/* (admin, 4)
     * blog_router       → /api/admin/blog/*  (admin, 6)
                           /api/public/blog/* (public, 2)

   Auth boundaries are preserved per-endpoint (mixed public/admin within
   the same APIRouter), matching the original server.py shape byte-for-byte.

Owned data:
   * Mongo collection `site_info`     — singleton document with site-wide config
   * Mongo collection `blog_articles` — bilingual CMS articles
   * Module-level constant SITE_INFO_DOC_ID
   * Module-level seed DEFAULT_SITE_INFO (≈322 LOC of admin-editable content)
   * Module-level constant BLOG_CATEGORIES
   * 7 helpers transferred WITH the router (ownership-transfer rule):
        _get_site_info_doc, _blog_strip_html, _blog_read_minutes,
        _blog_slugify, _blog_unique_slug, _blog_serialize

Bridges accepted (Wave 1 pattern):
   * `def _db()`            → lazy `from server import db`
   * `def _static_dir()`    → lazy `from server import _STATIC_DIR`
     (shared utility, used in 9 sites across the codebase, full graduation
      deferred to Phase 5 utils-module extraction)
   * `security.require_user` → direct import (auth dep at endpoint level
     because auth boundary is mixed inside this router)

Discipline preserved:
   * mechanical 1:1 extraction (no signature / contract / payload changes)
   * no auth normalisation (still per-endpoint role check)
   * no schema change (BLOG_CATEGORIES + DEFAULT_SITE_INFO byte-equivalent)
   * frontend untouched (URLs identical)
"""
from __future__ import annotations

import html as _blog_html
import logging
import re as _blog_re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4 as _blog_uuid4

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)

from security import require_user  # auth boundary stays per-endpoint

# PHASE SECURITY S3.1 — server-authoritative upload validation (magic bytes).
from app.services.upload_security import (
    validate_image_upload as _validate_image,
    UploadRejected as _UploadRejected,
)

# Full-length legal documents (Terms / Privacy / Cookies / Conditions) —
# single source of truth shared with scripts/sync_legal_content_v2.py.
from app.constants.legal_texts import LEGAL_POLICIES

# Phase 5.4 / C-4i — db_runtime accessor (module-level function reference).
# Only the `get_db` CALLABLE is imported at module-load time. Every
# `_db()` call resolves the live Motor handle via `get_db()`, preserving
# the call-time semantics of the legacy `from server import db` bridge.
from app.core.db_runtime import get_db  # noqa: E402 (C-4i: lazy-bridge → accessor)
from app.services.media_store import save_media  # deployment-safe MongoDB media store

logger = logging.getLogger("bibi.content")


# ─────────────────────────────────────────────────────────────────────────
#  Lazy bridges  (Wave-1 pattern: avoid import cycle with server.py)
# ─────────────────────────────────────────────────────────────────────────

def _db():
    """Return the live Mongo handle — resolves at call-time.

    Phase 5.4 / C-4i — migrated to ``app.core.db_runtime.get_db()``.
    Public-cache content router: serves site-info (public + admin) and
    blog (public + admin). Lazy semantics preserved 1:1.
    """
    return get_db()


def _static_dir() -> Path:
    """Return the shared `_STATIC_DIR` path defined in server.py.

    Used in 5 image-upload endpoints inside this router (reviews / hero /
    before_after / blog / generic). This is a *shared utility* (Phase 5
    utils-module extraction will graduate it); same bridge style as
    `serialize_doc` in admin_vesselfinder.
    """
    from server import _STATIC_DIR  # noqa: E402
    return _STATIC_DIR


# ═════════════════════════════════════════════════════════════════════════
#  SITE INFO domain
# ═════════════════════════════════════════════════════════════════════════

SITE_INFO_DOC_ID = "singleton"

DEFAULT_SITE_INFO: Dict[str, Any] = {
    "_id": SITE_INFO_DOC_ID,
    "policies": LEGAL_POLICIES,
    "footer": {
        "contacts": {
            "phones": ["+380 66 788 04 45"],
            "email": "Econova2013@ukr.net",
            "addresses": [
                "Україна, Житомирська обл., Звягельський р-н, м. Баранівка, вул. Івана Франка, 104А",
            ],
            "working_hours": "Пн - Пт, 09.00 - 18.00",
            "registration_address": "Україна, Житомирська обл., Звягельський р-н, м. Баранівка, вул. Івана Франка, 104А",
        },
        "socials": {
            "instagram": {"enabled": True,  "url": "https://instagram.com/"},
            "facebook":  {"enabled": True,  "url": "https://facebook.com/"},
            "telegram":  {"enabled": True,  "url": "https://t.me/"},
            "tiktok":    {"enabled": False, "url": ""},
            "whatsapp":  {"enabled": False, "url": ""},
            "viber":     {"enabled": True,  "url": "viber://chat?number=%2B380667880445"},
        },
        "viber_community": {
            "enabled": True,
            "url": "viber://chat?number=%2B380667880445",
            "label_en": "Join our group for the latest updates",
            "label_uk": "Приєднуйтесь до нашої групи з останніми новинами",
        },
    },
    "cookie_banner": {
        "enabled": True,
        "title_uk": "Ми цінуємо вашу приватність",
        "title_en": "We value your privacy",
        "body_uk": "Ми використовуємо необхідні файли cookie для коректної роботи сайту та збереження ваших налаштувань, а також аналітичні cookie — щоб покращувати сервіс. Оберіть, які cookie дозволити.",
        "body_en": "We use essential cookies to keep the site working and your preferences saved, plus analytics cookies to improve the service. Choose which cookies to allow.",
    },
    "faq": {
        "enabled": True,
        "title_en": "FAQ",
        "title_bg": "Често задавани въпроси",
        "items": [
            {
                "id": "faq-1",
                "enabled": True,
                "question_en": "How to choose and buy a car from America?",
                "question_bg": "Как да изберете и купите автомобил от Америка?",
                "answer_en": (
                    "<p>To choose and buy a car from the USA, follow these basic steps:</p>"
                    "<ol>"
                    "<li>Set your budget – include car price, auction fees, delivery, customs, and repairs.</li>"
                    "<li>Pick a platform – popular options are Copart and IAAI.</li>"
                    "<li>Check the car history – use Carfax or AutoCheck.</li>"
                    "<li>Choose a reliable broker – they handle bidding, documents, and shipping.</li>"
                    "<li>Arrange delivery and customs clearance – shipping usually takes 4–8 weeks.</li>"
                    "<li>Repair and register the car in your country.</li>"
                    "</ol>"
                ),
                "answer_bg": (
                    "<p>За да изберете и купите автомобил от САЩ, следвайте тези основни стъпки:</p>"
                    "<ol>"
                    "<li>Определете бюджета си – включете цена, такси на търга, доставка, мита и ремонт.</li>"
                    "<li>Изберете платформа – популярни са Copart и IAAI.</li>"
                    "<li>Проверете историята на автомобила – чрез Carfax или AutoCheck.</li>"
                    "<li>Изберете надежден брокер – той се грижи за наддаването, документите и транспорта.</li>"
                    "<li>Уредете доставка и митническо оформяне – обикновено отнема 4–8 седмици.</li>"
                    "<li>Ремонтирайте и регистрирайте автомобила в България.</li>"
                    "</ol>"
                ),
            },
            {
                "id": "faq-2",
                "enabled": True,
                "question_en": "Where do you ship to?",
                "question_bg": "Къде доставяте?",
                "answer_en": (
                    "<p>We deliver vehicles worldwide. Our primary destinations include Bulgaria, "
                    "Ukraine, Romania, Moldova and other EU countries. Door-to-door and port-to-port "
                    "options are available — final delivery method is confirmed during order processing.</p>"
                ),
                "answer_bg": (
                    "<p>Доставяме автомобили по целия свят. Основните дестинации са България, "
                    "Украйна, Румъния, Молдова и други страни от ЕС. Възможни са доставки от врата до "
                    "врата и от пристанище до пристанище — методът се уточнява при обработката на поръчката.</p>"
                ),
            },
            {
                "id": "faq-3",
                "enabled": True,
                "question_en": "How long will it take for my order to arrive?",
                "question_bg": "Колко време ще отнеме доставката?",
                "answer_en": (
                    "<p>Average end-to-end timeline is <strong>4–8 weeks</strong> from the moment of "
                    "winning the auction:</p>"
                    "<ol>"
                    "<li>Auction → US warehouse: 3–7 days.</li>"
                    "<li>Inland transport to the port: 7–14 days.</li>"
                    "<li>Ocean freight: 18–30 days (Atlantic) / 35–45 days (Pacific).</li>"
                    "<li>Customs clearance + final delivery: 5–10 days.</li>"
                    "</ol>"
                ),
                "answer_bg": (
                    "<p>Средното време от край до край е <strong>4–8 седмици</strong> от момента на "
                    "спечелване на търга:</p>"
                    "<ol>"
                    "<li>Търг → склад в САЩ: 3–7 дни.</li>"
                    "<li>Сухопътен транспорт до пристанището: 7–14 дни.</li>"
                    "<li>Морски транспорт: 18–30 дни (Атлантик) / 35–45 дни (Тихи океан).</li>"
                    "<li>Митническо оформяне + крайна доставка: 5–10 дни.</li>"
                    "</ol>"
                ),
            },
            {
                "id": "faq-4",
                "enabled": True,
                "question_en": "How do I change or cancel my order?",
                "question_bg": "Как мога да променя или откажа поръчка?",
                "answer_en": (
                    "<p>You can change or cancel your order before the auction bid is placed — "
                    "contact your manager via phone or the personal cabinet. After the vehicle is "
                    "won at auction, cancellation is no longer possible per Copart/IAAI rules; "
                    "however, the title can be re-assigned to another buyer for an additional fee.</p>"
                ),
                "answer_bg": (
                    "<p>Можете да промените или откажете поръчката си преди да бъде направена офертата "
                    "на търга — свържете се с Вашия мениджър по телефон или през личния кабинет. След "
                    "като автомобилът е спечелен, отказ не е възможен съгласно правилата на Copart/IAAI; "
                    "автомобилът може да бъде преотстъпен на друг купувач срещу допълнителна такса.</p>"
                ),
            },
            {
                "id": "faq-5",
                "enabled": True,
                "question_en": "How can I track my order?",
                "question_bg": "Как мога да проследя поръчката си?",
                "answer_en": (
                    "<p>Every order has a real-time status in your <strong>personal cabinet</strong> — "
                    "auction won, picked up, in port, on water, customs, delivered. You will receive "
                    "notifications at every stage by email, Viber and Telegram.</p>"
                ),
                "answer_bg": (
                    "<p>Всяка поръчка има статус в реално време във Вашия <strong>личен кабинет</strong> — "
                    "спечелен търг, взет, в пристанище, в открито море, митница, доставен. Ще получавате "
                    "известия на всеки етап по имейл, Viber и Telegram.</p>"
                ),
            },
        ],
    },
    # Reviews — admin-managed testimonials shown in the "OUR CLIENTS SAY"
    # block on the public homepage.
    "reviews": {
        "enabled": True,
        "title_en": "What our clients say",
        "title_uk": "Що кажуть наші клієнти",
        "subtitle_en": "Businesses that trusted us with their hazardous-waste utilisation",
        "subtitle_uk": "Підприємства, що довірили нам утилізацію небезпечних відходів",
        "google_rating": 4.9,
        "google_reviews_count": 0,
        "google_reviews_url": "",
        "baseline_happy_customers": 120,
        "items": [],
    },
    # Before / After — admin-managed gallery on the public homepage.
    "before_after": {
        "enabled": True,
        "title_en": "Before and after",
        "title_bg": "Преди и след",
        "subtitle_yellow_en": "Our clients receive",
        "subtitle_yellow_bg": "Нашите клиенти получават",
        "subtitle_white_en": "the best service",
        "subtitle_white_bg": "най-добрата услуга",
        "items": [
            {
                "id": "ba-1",
                "enabled": True,
                "model": "BMV 328",
                "order_date": "12.12.2025",
                "finished_date": "12.04.2026",
                "price": "6,500 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-12@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-22@2x.webp",
            },
            {
                "id": "ba-2",
                "enabled": True,
                "model": "BMV 328",
                "order_date": "12.12.2025",
                "finished_date": "12.04.2026",
                "price": "6,500 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-11@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-32@2x.webp",
            },
            {
                "id": "ba-3",
                "enabled": True,
                "model": "BMV 328",
                "order_date": "12.12.2025",
                "finished_date": "12.04.2026",
                "price": "6,500 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-1@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-3@2x.webp",
            },
            {
                "id": "ba-4",
                "enabled": True,
                "model": "Audi Q5",
                "order_date": "03.03.2026",
                "finished_date": "11.06.2026",
                "price": "12,900 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-12@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-22@2x.webp",
            },
            {
                "id": "ba-5",
                "enabled": True,
                "model": "Mercedes-Benz GLC",
                "order_date": "18.01.2026",
                "finished_date": "22.05.2026",
                "price": "18,400 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-11@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-32@2x.webp",
            },
            {
                "id": "ba-6",
                "enabled": True,
                "model": "Toyota Camry",
                "order_date": "07.02.2026",
                "finished_date": "30.05.2026",
                "price": "9,200 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-1@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-3@2x.webp",
            },
            {
                "id": "ba-7",
                "enabled": True,
                "model": "Jeep Grand Cherokee",
                "order_date": "25.10.2025",
                "finished_date": "08.03.2026",
                "price": "15,750 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-12@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-22@2x.webp",
            },
            {
                "id": "ba-8",
                "enabled": True,
                "model": "Volkswagen Tiguan",
                "order_date": "02.11.2025",
                "finished_date": "19.02.2026",
                "price": "11,200 EURO",
                "before_image_url": "/figma/DT-Klausen-LS-135-11@2x.webp",
                "after_image_url": "/figma/DT-Klausen-LS-135-32@2x.webp",
            },
        ],
    },
    # Partners — admin-managed partner / client logos shown on the public
    # homepage as a clickable card grid. Each item: bilingual name + short
    # description, an uploaded logo, an outbound link (opens in a new tab),
    # an enabled flag (hide without deleting) and an implicit sort order
    # (array position, reorder via ↑/↓ in the admin).
    "hero": {
        # Homepage cinematic hero — configurable slide photos for block 2
        # ("Classification. Collection. Transport.") and block 3
        # ("Transparency at every step."). Block 1 (video) is not configurable.
        "scene2_image": "/api/static/hero/eco-slide-collection.jpg",
        "scene3_image": "/api/static/hero/eco-slide-transparency.jpg",
    },
    "partners": {
        "enabled": True,
        "title_uk": "Наші френди",
        "title_en": "Our friends",
        "subtitle_uk": "Компанії та організації, що працюють з ECO.NOVA",
        "subtitle_en": "Companies and organisations that work with ECO.NOVA",
        "items": [],
    },
    # ── Licenses & certificates (homepage "Ліцензії" section) ──────────────
    # Editable in Admin → Content → Certificates. Each item carries bilingual
    # title/description, the official document metadata (issuer / number /
    # dates) and links to a public thumbnail image + downloadable PDF stored
    # under static/certificates/. Real ECO.NOVA documents (ЄДРПОУ 38541812).
    "certificates": {
        "enabled": True,
        "title_uk": "Наші ліцензії",
        "title_en": "Our licenses",
        "subtitle_uk": "Кожен рух відходів — з правовою підставою. Повний пакет дозволів Мінекономіки, сертифікат ISO 14001 та ліцензія на ADR-перевезення — чинні та завжди актуальні.",
        "subtitle_en": "Every movement of waste, backed by paperwork. A complete stack of Ministry-of-Economy permits, an ISO 14001 certificate and an ADR transport licence — valid and always current.",
        "items": [
            {
                "id": "cert-license",
                "no": "01",
                "category": "license",
                "title_uk": "Ліцензія на управління небезпечними відходами",
                "title_en": "Hazardous-waste management licence",
                "desc_uk": "Наказ Міністерства економіки, довкілля та сільського господарства України. Право на поводження з небезпечними відходами 1–4 класів.",
                "desc_en": "Order of the Ministry of Economy, Environment and Agriculture of Ukraine. Right to manage class 1–4 hazardous waste.",
                "issuer_uk": "Мінекономіки України",
                "issuer_en": "Ministry of Economy of Ukraine",
                "number": "Наказ № 6700",
                "issued": "11.06.2026",
                "valid_until": "",
                "image_url": "/api/static/certificates/license-min-eco.jpg",
                "file_url": "/api/static/certificates/license-min-eco.pdf",
                "enabled": True,
            },
            {
                "id": "cert-permit",
                "no": "02",
                "category": "permit",
                "title_uk": "Дозвіл на оброблення відходів",
                "title_en": "Waste-treatment permit",
                "desc_uk": "Дозвіл № 15282/25 на здійснення операцій з оброблення відходів (R1–R13, D9, D10, D13, D15). Понад 400 дозволених кодів відходів.",
                "desc_en": "Permit № 15282/25 for waste-treatment operations (R1–R13, D9, D10, D13, D15). Over 400 authorised waste codes.",
                "issuer_uk": "Мінекономіки України",
                "issuer_en": "Ministry of Economy of Ukraine",
                "number": "№ 15282/25",
                "issued": "23.01.2026",
                "valid_until": "",
                "image_url": "/api/static/certificates/permit-waste-treatment.jpg",
                "file_url": "/api/static/certificates/permit-waste-treatment.pdf",
                "enabled": True,
            },
            {
                "id": "cert-iso",
                "no": "03",
                "category": "certificate",
                "title_uk": "Сертифікат ISO 14001:2015",
                "title_en": "ISO 14001:2015 certificate",
                "desc_uk": "Система екологічного менеджменту. Орган сертифікації — ТОВ «Центр сучасних систем менеджменту». Чинний до 16.06.2029.",
                "desc_en": "Environmental management system. Certification body — Centre of Modern Management Systems LLC. Valid until 16.06.2029.",
                "issuer_uk": "Центр сучасних систем менеджменту",
                "issuer_en": "Centre of Modern Management Systems",
                "number": "№ 80143.EMS.062.01-26",
                "issued": "17.06.2026",
                "valid_until": "16.06.2029",
                "image_url": "/api/static/certificates/iso-14001.jpg",
                "file_url": "/api/static/certificates/iso-14001.pdf",
                "enabled": True,
            },
            {
                "id": "cert-transport",
                "no": "04",
                "category": "transport",
                "title_uk": "Ліцензія на перевезення небезпечних відходів (ADR)",
                "title_en": "Dangerous-goods transport licence (ADR)",
                "desc_uk": "Витяг з наказу Укртрансбезпеки № 109 від 26.02.2021. Перевезення небезпечних вантажів та відходів автомобільним транспортом (внутрішні та міжнародні).",
                "desc_en": "Extract from Ukrtransbezpeka order № 109 of 26.02.2021. Road transport of dangerous goods and hazardous waste (domestic and international).",
                "issuer_uk": "Укртрансбезпека",
                "issuer_en": "Ukrtransbezpeka",
                "number": "Наказ № 109",
                "issued": "26.02.2021",
                "valid_until": "",
                "image_url": "/api/static/certificates/transport-ukrtransbezpeka.jpg",
                "file_url": "/api/static/certificates/transport-ukrtransbezpeka.pdf",
                "enabled": True,
            },
        ],
    },
    "updated_at": None,
    "updated_by": None,
}


async def _get_site_info_doc():
    """Fetch site_info doc; create with defaults if missing."""
    db = _db()
    if db is None:
        return DEFAULT_SITE_INFO
    doc = await db.site_info.find_one({"_id": SITE_INFO_DOC_ID})
    if not doc:
        seed = dict(DEFAULT_SITE_INFO)
        seed["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            await db.site_info.insert_one(seed)
        except Exception as e:
            logger.warning(f"[site_info] seed insert failed: {e}")
        return seed
    # Merge defaults for any missing keys (forward-compat)
    merged = {**DEFAULT_SITE_INFO, **doc}
    for k in ("policies", "footer", "cookie_banner", "header", "faq", "reviews", "before_after", "hero", "partners", "certificates"):
        if k in DEFAULT_SITE_INFO:
            merged[k] = {**DEFAULT_SITE_INFO[k], **(doc.get(k) or {})}
    # Deep-merge `footer.contacts` so newly-introduced BG-localized keys
    # (addresses_bg, working_hours_bg, registration_address_bg) are surfaced
    # for already-persisted docs that pre-date this schema extension.
    try:
        default_contacts = (DEFAULT_SITE_INFO.get("footer") or {}).get("contacts") or {}
        existing_contacts = (doc.get("footer") or {}).get("contacts") or {}
        merged_contacts = {**default_contacts, **existing_contacts}
        merged["footer"]["contacts"] = merged_contacts
    except Exception as e:
        logger.warning(f"[site_info] contacts deep-merge failed: {e}")
    # Deep-merge `reviews.items` so newly-introduced bilingual fields flow
    # through to already-persisted documents that pre-date the schema extension.
    try:
        default_items = (DEFAULT_SITE_INFO.get("reviews") or {}).get("items") or []
        existing_items = (merged.get("reviews") or {}).get("items") or []
        if existing_items:
            by_id = {it.get("id"): it for it in default_items if it.get("id")}
            patched = []
            for it in existing_items:
                d = by_id.get(it.get("id"))
                if d:
                    fill = {k: v for k, v in d.items() if k not in it}
                    patched.append({**fill, **it})
                else:
                    patched.append(it)
            merged["reviews"]["items"] = patched
    except Exception as e:
        logger.warning(f"[site_info] reviews deep-merge failed: {e}")
    # Deep-merge `before_after.items`: keep admin-edited items but APPEND
    # any default items whose `id` is missing from the persisted document.
    # This is how new default cards (ba-4 … ba-8) reach already-seeded DBs
    # without overwriting customer-tweaked entries.
    try:
        default_ba_items = (DEFAULT_SITE_INFO.get("before_after") or {}).get("items") or []
        existing_ba_items = (merged.get("before_after") or {}).get("items") or []
        existing_ids = {it.get("id") for it in existing_ba_items if it.get("id")}
        appended = list(existing_ba_items)
        for d in default_ba_items:
            if d.get("id") and d["id"] not in existing_ids:
                appended.append(d)
        merged["before_after"]["items"] = appended
    except Exception as e:
        logger.warning(f"[site_info] before_after deep-merge failed: {e}")
    # Backward-compat: socials may be stored as flat strings { ig: "url" } —
    # normalize to { ig: {enabled, url} } so the frontend has a single shape.
    try:
        socials = (merged.get("footer") or {}).get("socials") or {}
        norm = {}
        default_socials = (DEFAULT_SITE_INFO["footer"]["socials"] or {})
        for key in default_socials.keys():
            v = socials.get(key, default_socials[key])
            if isinstance(v, str):
                norm[key] = {"enabled": bool(v), "url": v}
            elif isinstance(v, dict):
                norm[key] = {
                    "enabled": bool(v.get("enabled", bool(v.get("url")))),
                    "url": v.get("url", ""),
                }
            else:
                norm[key] = {"enabled": False, "url": ""}
        merged["footer"]["socials"] = norm
    except Exception as e:
        logger.warning(f"[site_info] socials normalize failed: {e}")
    return merged


site_info_router = APIRouter(tags=["site-info"])


def _strip_bg(obj):
    """Recursively remove every Bulgarian remnant from served content.

    Bulgarian has been fully retired from the product (UK + EN only). Legacy
    documents / seed defaults may still carry ``*_bg`` fields or a ``"bg"``
    language block; this guarantees none of it ever reaches the client,
    regardless of what is stored in Mongo.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if kl == "bg" or kl.endswith("_bg"):
                continue
            out[k] = _strip_bg(v)
        return out
    if isinstance(obj, list):
        return [_strip_bg(x) for x in obj]
    return obj


@site_info_router.get("/api/site-info")
async def get_site_info_public():
    """Public endpoint — returns full site info (used by footer, cookie banner, policy pages)."""
    doc = await _get_site_info_doc()
    # Strip internal fields + any Bulgarian remnants (UK + EN only).
    return _strip_bg({k: v for k, v in doc.items() if not k.startswith("_")})


@site_info_router.get("/api/site-info/policy/{key}")
async def get_site_policy_public(key: str, lang: str = "uk"):
    """Public endpoint — returns one policy section in given language (uk|en)."""
    if key not in ("privacy", "terms", "cookies", "conditions"):
        raise HTTPException(status_code=404, detail="Unknown policy key")
    if lang == "ua":
        lang = "uk"
    if lang not in ("en", "uk"):
        lang = "uk"
    doc = await _get_site_info_doc()
    policy = (doc.get("policies") or {}).get(key) or {}
    chosen = policy.get(lang) or policy.get("uk") or policy.get("en") or {"title": key.title(), "content": ""}
    return _strip_bg(chosen)


@site_info_router.put("/api/admin/site-info")
async def update_site_info_admin(
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(require_user),
):
    """Admin endpoint — update site info. Requires master_admin / admin."""
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    db = _db()
    if db is None:
        raise HTTPException(status_code=503, detail="DB not available")

    update = {}
    for key in ("policies", "footer", "cookie_banner", "header", "faq", "reviews", "before_after", "hero", "partners", "certificates"):
        if key in payload and isinstance(payload[key], dict):
            update[key] = payload[key]
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    update["updated_by"] = user.get("email") or user.get("id")

    await db.site_info.update_one(
        {"_id": SITE_INFO_DOC_ID},
        {"$set": update},
        upsert=True,
    )
    return await _get_site_info_doc()


@site_info_router.post("/api/admin/site-info/upload-review-image")
async def upload_review_image_admin(
    image: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await image.read()
    try:
        safe = _validate_image(content, image.filename, image.content_type, max_mb=10)
    except _UploadRejected as e:
        raise HTTPException(status_code=400, detail=str(e))
    ext = safe.ext

    reviews_dir = _static_dir() / "reviews"

    fname = f"rev_{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}"
    saved = save_media("reviews", fname, content, image.content_type)
    url = saved["url"]
    return {"success": True, "url": url}


@site_info_router.post("/api/admin/site-info/upload-before-after-image")
async def upload_before_after_image_admin(
    image: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await image.read()
    try:
        safe = _validate_image(content, image.filename, image.content_type, max_mb=10)
    except _UploadRejected as e:
        raise HTTPException(status_code=400, detail=str(e))
    ext = safe.ext

    ba_dir = _static_dir() / "before_after"

    fname = f"ba_{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}"
    saved = save_media("before_after", fname, content, image.content_type)
    url = saved["url"]
    return {"success": True, "url": url}


@site_info_router.post("/api/admin/site-info/upload-hero-image")
async def upload_hero_image_admin(
    image: UploadFile = File(...),
    variant: str = "web",
    user: dict = Depends(require_user),
):
    """Upload a hero banner image.

    Query param ``variant`` selects the form-factor:
      - ``web``    — desktop 16:9 banner (default, backwards compatible).
      - ``mobile`` — mobile landing portrait variant (≈ 361:326 / 9:8).

    Files are stored under ``static/hero/`` with a variant-suffixed filename
    so the two never collide. The returned ``url`` should be saved into
    ``hero.image_url`` (web) or ``hero.image_url_mobile`` (mobile).
    """
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    variant_norm = (variant or "web").strip().lower()
    if variant_norm not in ("web", "mobile", "scene2", "scene3"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported variant. Allowed: 'web', 'mobile', 'scene2', 'scene3'.",
        )

    content = await image.read()
    try:
        safe = _validate_image(
            content, image.filename, image.content_type, max_mb=10,
            allowed_mimes={"image/jpeg", "image/png", "image/webp"},
        )
    except _UploadRejected as e:
        raise HTTPException(
            status_code=400,
            detail=f"{e}. Allowed: JPG, PNG, WebP.",
        )
    ext = safe.ext

    hero_dir = _static_dir() / "hero"

    suffix = {"web": "", "mobile": "_mobile", "scene2": "_scene2", "scene3": "_scene3"}.get(variant_norm, "")
    fname = (
        f"hero{suffix}_"
        f"{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}"
    )
    saved = save_media("hero", fname, content, image.content_type)
    url = saved["url"]
    return {
        "success": True,
        "url": url,
        "size": len(content),
        "format": ext,
        "variant": variant_norm,
    }


@site_info_router.post("/api/admin/site-info/upload-partner-logo")
async def upload_partner_logo_admin(
    image: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    """Upload a partner logo (admin / master_admin only).

    Accepts raster images (JPG / PNG / WebP / GIF). Stored under
    ``static/partners/`` with a timestamped filename. Returns the
    ``/api/static/partners/<file>`` URL to be saved into the partner item's
    ``logo_url``. (SVG is intentionally rejected by upload-security.)
    """
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await image.read()
    try:
        safe = _validate_image(
            content, image.filename, image.content_type, max_mb=5,
            allowed_mimes={"image/jpeg", "image/png", "image/webp", "image/gif"},
        )
    except _UploadRejected as e:
        raise HTTPException(
            status_code=400,
            detail=f"{e}. Allowed: JPG, PNG, WebP, GIF.",
        )
    ext = safe.ext

    partners_dir = _static_dir() / "partners"

    fname = f"partner_{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}"
    saved = save_media("partners", fname, content, image.content_type)
    url = saved["url"]
    return {"success": True, "url": url, "size": len(content), "format": ext}


@site_info_router.post("/api/admin/site-info/upload-certificate-image")
async def upload_certificate_image_admin(
    image: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    """Upload a certificate/licence preview image (admin / master_admin only).

    Accepts raster images (JPG / PNG / WebP). Stored under
    ``static/certificates/`` with a timestamped filename. Returns the
    ``/api/static/certificates/<file>`` URL to save into the item's
    ``image_url``.
    """
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await image.read()
    try:
        safe = _validate_image(
            content, image.filename, image.content_type, max_mb=8,
            allowed_mimes={"image/jpeg", "image/png", "image/webp"},
        )
    except _UploadRejected as e:
        raise HTTPException(status_code=400, detail=f"{e}. Allowed: JPG, PNG, WebP.")
    ext = safe.ext

    cert_dir = _static_dir() / "certificates"
    fname = f"cert_{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}"
    saved = save_media("certificates", fname, content, image.content_type)
    url = saved["url"]
    return {"success": True, "url": url, "size": len(content), "format": ext}


@site_info_router.post("/api/admin/site-info/upload-certificate-file")
async def upload_certificate_file_admin(
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    """Upload the certificate/licence PDF document (admin / master_admin only).

    Accepts PDF only (validated via magic bytes), max 25 MB. Stored under
    ``static/certificates/``. Returns the public ``/api/static/certificates/
    <file>.pdf`` URL to save into the item's ``file_url``.
    """
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25 MB).")
    # PDF magic bytes: "%PDF"
    if not content[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Only PDF documents are allowed.")

    cert_dir = _static_dir() / "certificates"
    fname = f"cert_{int(datetime.now(timezone.utc).timestamp() * 1000)}.pdf"
    saved = save_media("certificates", fname, content, "application/pdf")
    url = saved["url"]
    return {"success": True, "url": url, "size": len(content), "format": "pdf"}


# ═════════════════════════════════════════════════════════════════════════
#  BLOG ARTICLES domain
# ═════════════════════════════════════════════════════════════════════════

BLOG_CATEGORIES = [
    "news",         # Новини
    "regulation",   # Регулювання / законодавство
    "guides",       # Гайди / інструкції
    "cases",        # Кейси / приклади з практики
    "ecology",      # Екологія / сталий розвиток
    "industry",     # Галузь / тренди ринку
]


def _blog_strip_html(html_str: str) -> str:
    """Strip HTML tags and unescape entities — used for read-time + slug."""
    if not html_str:
        return ""
    txt = _blog_re.sub(r"<[^>]+>", " ", html_str)
    txt = _blog_html.unescape(txt)
    return _blog_re.sub(r"\s+", " ", txt).strip()


def _blog_read_minutes(*texts: str) -> int:
    """200 words / minute, minimum 1 minute, combines all language bodies."""
    total_words = 0
    for t in texts:
        if t:
            total_words += len(_blog_strip_html(t).split())
    return max(1, round(total_words / 200))


def _blog_slugify(title: str) -> str:
    """ASCII slug from EN title (fallback: random uuid)."""
    if not title:
        return _blog_uuid4().hex[:10]
    s = title.lower().strip()
    s = _blog_re.sub(r"[^a-z0-9\s-]", "", s)
    s = _blog_re.sub(r"[\s-]+", "-", s).strip("-")
    return s[:80] or _blog_uuid4().hex[:10]


async def _blog_unique_slug(base: str, current_id: str = "") -> str:
    """Append -2 / -3 / … if base slug already exists for a different article."""
    db = _db()
    slug = base
    suffix = 2
    while True:
        existing = await db.blog_articles.find_one(
            {"slug": slug, **({"id": {"$ne": current_id}} if current_id else {})},
            {"_id": 1},
        )
        if not existing:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _blog_serialize(doc: dict, public: bool = False, lang: str = "en") -> dict:
    """Convert MongoDB document → JSON.  Public mode returns lang-specific fields."""
    if not doc:
        return {}
    d = dict(doc)
    d.pop("_id", None)
    # ensure ISO-formatted timestamps
    for k in ("created_at", "updated_at", "published_at"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    if public:
        lang = lang if lang in ("en", "uk") else "uk"
        return {
            "id": d.get("id"),
            "slug": d.get("slug"),
            "category": d.get("category"),
            "cover_image_url": d.get("cover_image_url"),
            "title": (d.get("title", {}) or {}).get(lang) or (d.get("title", {}) or {}).get("uk") or (d.get("title", {}) or {}).get("en", ""),
            "excerpt": (d.get("excerpt", {}) or {}).get(lang) or (d.get("excerpt", {}) or {}).get("uk") or (d.get("excerpt", {}) or {}).get("en", ""),
            "body": (d.get("body", {}) or {}).get(lang) or (d.get("body", {}) or {}).get("uk") or (d.get("body", {}) or {}).get("en", ""),
            "read_time_minutes": d.get("read_time_minutes", 1),
            "related_ids": d.get("related_ids", []),
            "tags": d.get("tags", []) or [],
            "published": bool(d.get("published", False)),
            "published_at": d.get("published_at") or d.get("created_at"),
            "created_at": d.get("created_at"),
        }
    # ensure tags always present in admin payload too
    d["tags"] = d.get("tags", []) or []
    return d


blog_router = APIRouter(tags=["blog"])


# ── Admin: list / create ──────────────────────────────────────────────────
@blog_router.get("/api/admin/blog/articles")
async def admin_blog_list(
    user: dict = Depends(require_user),
    category: Optional[str] = None,
    q: Optional[str] = None,
):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    db = _db()
    query = {}
    if category and category != "all":
        query["category"] = category
    if q:
        query["$or"] = [
            {"title.en": {"$regex": q, "$options": "i"}},
            {"title.uk": {"$regex": q, "$options": "i"}},
            {"title.bg": {"$regex": q, "$options": "i"}},  # legacy fallback
        ]
    items = []
    cursor = db.blog_articles.find(query).sort("created_at", -1)
    async for d in cursor:
        items.append(_blog_serialize(d))
    return {"items": items, "count": len(items)}


@blog_router.post("/api/admin/blog/articles")
async def admin_blog_create(
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(require_user),
):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    db = _db()
    category = (payload.get("category") or "news").strip()
    if category not in BLOG_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    title = payload.get("title") or {}
    excerpt = payload.get("excerpt") or {}
    body = payload.get("body") or {}

    # Accept incoming `uk` (primary) — fall back to legacy `bg` payloads.
    title_uk = (title.get("uk") or title.get("bg") or "").strip()
    title_en = (title.get("en") or "").strip()
    if not title_uk and not title_en:
        raise HTTPException(status_code=400, detail="title.uk or title.en required")

    base_slug = _blog_slugify(payload.get("slug") or title_uk or title_en)
    slug = await _blog_unique_slug(base_slug)

    now = datetime.now(timezone.utc)
    published = bool(payload.get("published", False))
    raw_tags = payload.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t for t in _blog_re.split(r"[,\n]", raw_tags) if t]
    seen_tags = set()
    norm_tags: list = []
    for t in raw_tags:
        if not isinstance(t, str):
            continue
        s = t.strip()[:40]
        if not s:
            continue
        k = s.lower()
        if k in seen_tags:
            continue
        seen_tags.add(k)
        norm_tags.append(s)
        if len(norm_tags) >= 12:
            break
    doc = {
        "id": str(_blog_uuid4()),
        "slug": slug,
        "category": category,
        "cover_image_url": (payload.get("cover_image_url") or "").strip() or None,
        "title":   {"uk": title_uk, "en": title_en},
        "excerpt": {"uk": (excerpt.get("uk") or excerpt.get("bg") or "").strip(),
                    "en": (excerpt.get("en") or "").strip()},
        "body":    {"uk": body.get("uk") or body.get("bg") or "",
                    "en": body.get("en") or ""},
        "tags": norm_tags,
        "related_ids": [str(x) for x in (payload.get("related_ids") or [])][:5],
        "read_time_minutes": _blog_read_minutes(body.get("uk") or body.get("bg"), body.get("en")),
        "published": published,
        "published_at": now if published else None,
        "created_at": now,
        "updated_at": now,
    }
    await db.blog_articles.insert_one(doc)
    return _blog_serialize(doc)


# ── Admin: get / update / delete single ───────────────────────────────────
@blog_router.get("/api/admin/blog/articles/{article_id}")
async def admin_blog_get(article_id: str, user: dict = Depends(require_user)):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    db = _db()
    doc = await db.blog_articles.find_one({"id": article_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Article not found")
    return _blog_serialize(doc)


@blog_router.put("/api/admin/blog/articles/{article_id}")
async def admin_blog_update(
    article_id: str,
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(require_user),
):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    db = _db()
    existing = await db.blog_articles.find_one({"id": article_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Article not found")

    update: Dict[str, Any] = {}
    if "category" in payload:
        cat = (payload.get("category") or "").strip()
        if cat not in BLOG_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Invalid category: {cat}")
        update["category"] = cat
    if "cover_image_url" in payload:
        update["cover_image_url"] = (payload.get("cover_image_url") or "").strip() or None
    if "title" in payload:
        t = payload.get("title") or {}
        et = existing.get("title", {}) or {}
        update["title"] = {
            "uk": (t.get("uk") or t.get("bg") or et.get("uk") or et.get("bg") or "").strip(),
            "en": (t.get("en") or et.get("en") or "").strip(),
        }
    if "excerpt" in payload:
        e = payload.get("excerpt") or {}
        ee = existing.get("excerpt", {}) or {}
        update["excerpt"] = {
            "uk": (e.get("uk") or e.get("bg") or ee.get("uk") or ee.get("bg") or "").strip(),
            "en": (e.get("en") or ee.get("en") or "").strip(),
        }
    if "body" in payload:
        b = payload.get("body") or {}
        eb = existing.get("body", {}) or {}
        update["body"] = {
            "uk": b.get("uk") or b.get("bg") or eb.get("uk") or eb.get("bg") or "",
            "en": b.get("en") or eb.get("en") or "",
        }
        update["read_time_minutes"] = _blog_read_minutes(update["body"]["uk"], update["body"]["en"])
    if "related_ids" in payload:
        update["related_ids"] = [str(x) for x in (payload.get("related_ids") or [])][:5]
    if "tags" in payload:
        raw_tags = payload.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [t for t in _blog_re.split(r"[,\n]", raw_tags) if t]
        seen_tags = set()
        norm_tags: list = []
        for t in raw_tags:
            if not isinstance(t, str):
                continue
            s = t.strip()[:40]
            if not s:
                continue
            k = s.lower()
            if k in seen_tags:
                continue
            seen_tags.add(k)
            norm_tags.append(s)
            if len(norm_tags) >= 12:
                break
        update["tags"] = norm_tags
    if "published_at" in payload and payload.get("published_at"):
        try:
            pa = payload.get("published_at")
            if isinstance(pa, str):
                if len(pa) == 10:
                    pa = pa + "T00:00:00+00:00"
                update["published_at"] = datetime.fromisoformat(pa.replace("Z", "+00:00"))
        except Exception:
            pass
    if "slug" in payload and payload.get("slug"):
        base = _blog_slugify(payload.get("slug"))
        update["slug"] = await _blog_unique_slug(base, current_id=article_id)
    if "published" in payload:
        update["published"] = bool(payload.get("published"))
        if update["published"] and not existing.get("published_at"):
            update["published_at"] = datetime.now(timezone.utc)

    update["updated_at"] = datetime.now(timezone.utc)
    await db.blog_articles.update_one({"id": article_id}, {"$set": update})
    new_doc = await db.blog_articles.find_one({"id": article_id})
    return _blog_serialize(new_doc)


@blog_router.delete("/api/admin/blog/articles/{article_id}")
async def admin_blog_delete(article_id: str, user: dict = Depends(require_user)):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    db = _db()
    res = await db.blog_articles.delete_one({"id": article_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"success": True}


# ── Admin: cover-image upload ─────────────────────────────────────────────
@blog_router.post("/api/admin/blog/upload-image")
async def admin_blog_upload_image(
    image: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    role = (user or {}).get("role", "")
    if role not in ("master_admin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    content = await image.read()
    try:
        safe = _validate_image(content, image.filename, image.content_type, max_mb=10)
    except _UploadRejected as e:
        raise HTTPException(status_code=400, detail=str(e))
    ext = safe.ext

    blog_dir = _static_dir() / "blog"
    fname = f"blog_{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}"
    saved = save_media("blog", fname, content, image.content_type)
    return {"success": True, "url": saved["url"], "size": len(content)}


# ── Public: list / single ─────────────────────────────────────────────────
@blog_router.get("/api/public/blog/articles")
async def public_blog_list(
    lang: str = Query("uk"),
    category: str = Query("all"),
    tag: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    lang = lang if lang in ("en", "uk") else "uk"
    db = _db()
    query: Dict[str, Any] = {"published": True}
    if category and category != "all":
        if category not in BLOG_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        query["category"] = category
    if tag:
        # case-insensitive tag filter
        query["tags"] = {"$regex": f"^{_blog_re.escape(tag.strip())}$", "$options": "i"}

    skip = (page - 1) * limit
    total = await db.blog_articles.count_documents(query)
    items = []
    cursor = (
        db.blog_articles.find(query)
        .sort([("published_at", -1), ("created_at", -1)])
        .skip(skip)
        .limit(limit)
    )
    async for d in cursor:
        items.append(_blog_serialize(d, public=True, lang=lang))

    # collect a unique sorted list of all tags currently used by published articles
    all_tags = await db.blog_articles.distinct("tags", {"published": True})
    all_tags = sorted([t for t in (all_tags or []) if isinstance(t, str) and t.strip()])

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "categories": BLOG_CATEGORIES,
        "tags": all_tags,
    }


@blog_router.get("/api/public/blog/articles/{slug}")
async def public_blog_single(slug: str, lang: str = Query("uk")):
    lang = lang if lang in ("en", "uk") else "uk"
    db = _db()
    doc = await db.blog_articles.find_one({"slug": slug, "published": True})
    if not doc:
        raise HTTPException(status_code=404, detail="Article not found")
    main = _blog_serialize(doc, public=True, lang=lang)
    # Resolve related
    related_full = []
    for rid in (doc.get("related_ids") or [])[:5]:
        r = await db.blog_articles.find_one({"id": rid, "published": True})
        if r:
            related_full.append(_blog_serialize(r, public=True, lang=lang))
    main["related"] = related_full
    return main
