"""
Waste Core service layer (Wave 2)
=================================

Pure-ish helpers for the waste domain: index creation, idempotent seeding,
document construction from the seed dataset, smart search (phrase -> codes),
license-matrix acceptance check and a v0 price estimate.

DB access uses the existing ``app.core.db_runtime.get_db`` singleton so the
waste module shares one Motor client with the rest of the backend.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.waste.seed_data import CATEGORIES, WASTE_CODES
from app.waste import national_data as ND

logger = logging.getLogger("eco.waste")

# Collection names (single source of truth)
C_CODES = "waste_codes"
C_CHAPTERS = "waste_chapters"          # 20 глав з постанови КМУ
C_GROUPS = "waste_groups"              # 115 підгруп
C_COMPANIES = "waste_companies"
C_OBJECTS = "waste_objects"
C_LICENSES = "waste_license_matrix"
C_REQUESTS = "waste_requests"
# Wave 3 — Operations Center
C_CONTRACTS = "waste_contracts"
C_PICKUPS = "waste_pickups"
C_ACTS = "utilization_acts"
C_ACTIVITY = "waste_activity"      # Company/Object timeline
C_TASKS = "waste_tasks"
C_COMMENTS = "waste_comments"
C_COUNTERS = "waste_counters"      # sequential document numbering
C_PRICE_RULES = "waste_price_rules"  # Wave 4A — Pricing Engine v2
C_CATEGORIES = "waste_categories"    # Admin-managed catalog categories (icons + UA/EN names)

# Request lifecycle stages (ordered)
REQUEST_STAGES: List[str] = [
    "new",            # Нова заявка
    "quote",          # Комерційна пропозиція / прорахунок
    "contract",       # Договір
    "pickup",         # Вивіз / забір
    "utilization",    # Утилізація
    "act",            # Акт готовий
    "archived",       # Архів
]
STAGE_LABELS_UK = {
    "new": "Нова", "quote": "Прорахунок", "contract": "Договір", "pickup": "Вивіз",
    "utilization": "Утилізація", "act": "Акт готовий", "archived": "Архів",
}

# ── Wave 3 lifecycles ────────────────────────────────────────────────────────
CONTRACT_STAGES: List[str] = ["draft", "sent", "agreed", "signed", "active", "closed", "cancelled"]
CONTRACT_LABELS_UK = {
    "draft": "Чернетка", "sent": "Надіслано", "agreed": "Погоджено", "signed": "Підписано",
    "active": "Активний", "closed": "Закритий", "cancelled": "Скасовано",
}
PICKUP_STAGES: List[str] = ["planning", "route", "driver_assigned", "picked_up", "delivered", "cancelled"]
PICKUP_LABELS_UK = {
    "planning": "Планування", "route": "Маршрут", "driver_assigned": "Водій призначений",
    "picked_up": "Забір виконано", "delivered": "Доставлено", "cancelled": "Скасовано",
}
ACT_STAGES: List[str] = ["expected", "created", "signed", "archived", "cancelled"]
ACT_LABELS_UK = {
    "expected": "Очікується", "created": "Створено", "signed": "Підписано",
    "archived": "Архів", "cancelled": "Скасовано",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Small utils
# ─────────────────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_id(prefix: str) -> str:
    return f"{prefix}_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:8]}"


def slugify_code(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")


def serialize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strip Mongo _id and make values JSON-safe (datetimes -> isoformat)."""
    if not doc:
        return doc
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Wave 3 — document numbering + activity timeline
# ─────────────────────────────────────────────────────────────────────────────
async def next_number(db, kind: str, prefix: str) -> str:
    """Atomic sequential document number, e.g. WC-2026-000123."""
    year = datetime.now(timezone.utc).year
    key = f"{kind}:{year}"
    doc = await db[C_COUNTERS].find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,  # ReturnDocument.AFTER
    )
    seq = (doc or {}).get("seq", 1)
    return f"{prefix}-{year}-{seq:06d}"


async def log_activity(
    db, *, company_id: Optional[str], entity_type: str, entity_id: str,
    event: str, message: str, by: Optional[str] = None, object_id: Optional[str] = None,
) -> None:
    """Append an event to the Company/Object timeline (best-effort)."""
    try:
        await db[C_ACTIVITY].insert_one({
            "id": gen_id("act"),
            "company_id": company_id,
            "object_id": object_id,
            "entity_type": entity_type,   # request | contract | pickup | act | company | object | task | comment
            "entity_id": entity_id,
            "event": event,               # created | stage_changed | signed | ...
            "message": message,
            "by": by,
            "at": now_iso(),
        })
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] log_activity (non-fatal): %s", e)


# ─────────────────────────────────────────────────────────────────────────────
#  Document construction
# ─────────────────────────────────────────────────────────────────────────────
def build_full_doc(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a compact seed entry with its category defaults into a full doc."""
    cat = entry.get("category") or "other_hazard"
    cdef = CATEGORIES.get(cat, CATEGORIES["other_hazard"])
    code = entry.get("code_override") or entry["code"]
    hazardous = bool(entry.get("hazardous"))
    doc: Dict[str, Any] = {
        "id": gen_id("wc"),
        "code": code,
        "slug": slugify_code(code),
        "name": entry["name"],
        "human_names": entry.get("human_names") or [],
        "category": cat,
        "category_name": cdef["name"],
        "hazard_class": entry.get("hazard_class"),
        "hazardous": hazardous,
        "mirror_code": entry.get("mirror_code"),
        # Реальна ієрархія з національного переліку
        "level": entry.get("level", 3),
        "chapter": entry.get("chapter"),
        "group": entry.get("group"),
        "parent_code": entry.get("parent_code"),
        "mirror_hazardous": bool(entry.get("mirror_hazardous")),
        "source": entry.get("source"),               # 'national_list_2023' | None
        "official": bool(entry.get("official")),     # офіційний код з постанови
        "description": entry.get("description") or entry["name"],
        "storage": entry.get("storage") or cdef["storage"],
        "transport": entry.get("transport") or cdef["transport"],
        "utilization_process": entry.get("process") or cdef["process"],
        "required_docs": entry.get("required_docs") or list(cdef["docs"]),
        "price_from": entry.get("price_from"),
        "price_unit": entry.get("price_unit") or cdef["price_unit"],
        "min_order_kg": entry.get("min_order_kg", cdef["min_order_kg"]),
        "requires_container": entry.get("requires_container", cdef["requires_container"]),
        "requires_transport": entry.get("requires_transport", cdef["requires_transport"]),
        "packaging": entry.get("packaging"),
        "license_allowed": entry.get("license_allowed", True),
        "service_available": entry.get("service_available", True),
        # «Ми приймаємо» — похідне поле, синхронізується з License Matrix.
        # За замовчуванням False: лише ліцензований піднабір стає публічним.
        "accepted": bool(entry.get("accepted", False)),
        "notes": entry.get("notes"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return doc


# ─────────────────────────────────────────────────────────────────────────────
#  Indexes + seeding
# ─────────────────────────────────────────────────────────────────────────────
async def ensure_indexes(db) -> None:
    try:
        await db[C_CODES].create_index("code", unique=True)
        await db[C_CODES].create_index("slug")
        await db[C_CODES].create_index("category")
        await db[C_CODES].create_index("hazardous")
        await db[C_CODES].create_index("human_names")
        await db[C_CODES].create_index("chapter")
        await db[C_CODES].create_index("group")
        await db[C_CODES].create_index("parent_code")
        await db[C_CODES].create_index("level")
        await db[C_CODES].create_index("official")
        await db[C_CODES].create_index("accepted")
        # National list — chapters & groups
        await db[C_CHAPTERS].create_index("code", unique=True)
        await db[C_GROUPS].create_index("code", unique=True)
        await db[C_GROUPS].create_index("chapter")
        await db[C_COMPANIES].create_index("id", unique=True)
        await db[C_COMPANIES].create_index("edrpou")
        await db[C_COMPANIES].create_index("assigned_manager_id")
        await db[C_OBJECTS].create_index("id", unique=True)
        await db[C_OBJECTS].create_index("company_id")
        await db[C_LICENSES].create_index("id", unique=True)
        await db[C_LICENSES].create_index("waste_code")
        await db[C_REQUESTS].create_index("id", unique=True)
        await db[C_REQUESTS].create_index("company_id")
        await db[C_REQUESTS].create_index("stage")
        await db[C_REQUESTS].create_index([("created_at", -1)])
        # ── Wave 3 — Operations Center ──
        for coll in (C_CONTRACTS, C_PICKUPS, C_ACTS, C_TASKS):
            await db[coll].create_index("id", unique=True)
            await db[coll].create_index("company_id")
            await db[coll].create_index("status")
            await db[coll].create_index([("created_at", -1)])
        await db[C_PICKUPS].create_index("object_id")
        await db[C_ACTS].create_index("object_id")
        await db[C_ACTIVITY].create_index("company_id")
        await db[C_ACTIVITY].create_index("object_id")
        await db[C_ACTIVITY].create_index([("at", -1)])
        await db[C_COMMENTS].create_index("company_id")
        await db[C_COMMENTS].create_index([("created_at", -1)])
        # ── Wave 4A — Pricing Engine v2 ──
        await db[C_PRICE_RULES].create_index("id", unique=True)
        await db[C_PRICE_RULES].create_index("wasteCode")
        await db[C_PRICE_RULES].create_index([("wasteCode", 1), ("region", 1), ("minWeight", 1)])
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] ensure_indexes (non-fatal): %s", e)


async def seed_waste_codes(db, *, force: bool = False) -> Dict[str, Any]:
    """Idempotently seed the OFFICIAL National Waste List (Постанова КМУ № 1102).

    Якщо колекція не порожня і ``force=False`` — пропустити.
    Якщо ``force=True`` — повністю замінити dummy коди реальними (drop&seed),
    плюс глави та підгрупи у власних колекціях.
    """
    if force:
        await db[C_CODES].delete_many({})
        await db[C_CHAPTERS].delete_many({})
        await db[C_GROUPS].delete_many({})

    existing = await db[C_CODES].estimated_document_count()
    if existing and not force:
        return {"seeded": False, "reason": "already_populated", "count": existing}

    # 1) Глави (level=1)
    now = now_iso()
    chapters_payload = [
        {**c, "id": gen_id("chap"), "created_at": now, "updated_at": now}
        for c in ND.all_chapters()
    ]
    if chapters_payload:
        await db[C_CHAPTERS].insert_many(chapters_payload)

    # 2) Підгрупи (level=2)
    groups_payload = [
        {**g, "id": gen_id("grp"), "created_at": now, "updated_at": now}
        for g in ND.all_groups()
    ]
    if groups_payload:
        await db[C_GROUPS].insert_many(groups_payload)

    # 3) Коди-листи (level=3)
    created, updated = 0, 0
    entries = ND.all_seed_entries() or WASTE_CODES  # fallback на dummy, якщо JSON не знайдено
    for entry in entries:
        doc = build_full_doc(entry)
        code = doc["code"]
        prev = await db[C_CODES].find_one({"code": code}, {"_id": 1, "id": 1, "created_at": 1})
        if prev:
            doc["id"] = prev.get("id") or doc["id"]
            doc["created_at"] = prev.get("created_at") or doc["created_at"]
            doc["updated_at"] = now_iso()
            await db[C_CODES].update_one({"code": code}, {"$set": doc})
            updated += 1
        else:
            await db[C_CODES].insert_one(doc)
            created += 1
    total = await db[C_CODES].count_documents({})
    logger.info(
        "[waste] seed complete: chapters=%d groups=%d created=%d updated=%d total_codes=%d",
        len(chapters_payload), len(groups_payload), created, updated, total,
    )
    return {
        "seeded": True,
        "source": "national_list_2023",
        "chapters": len(chapters_payload),
        "groups": len(groups_payload),
        "created": created,
        "updated": updated,
        "total": total,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Smart search (Waste Intelligence v0 — phrase -> codes)
# ─────────────────────────────────────────────────────────────────────────────
_CODE_HINT = re.compile(r"\d")


def _category_for_phrase(q: str) -> List[str]:
    """Return category keys whose name/synonyms match the phrase."""
    ql = q.lower()
    hits: List[str] = []
    for key, meta in CATEGORIES.items():
        hay = [meta["name"].lower(), key] + [s.lower() for s in meta.get("synonyms", [])]
        if any(tok and (tok in ql or ql in tok) for tok in hay):
            hits.append(key)
    return hits


async def search_codes(
    db, *, q: Optional[str] = None, category: Optional[str] = None,
    hazardous: Optional[bool] = None, accepted: Optional[bool] = None, limit: int = 50,
) -> List[Dict[str, Any]]:
    """Resolve a human phrase OR a code fragment to matching waste codes."""
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    if hazardous is not None:
        query["hazardous"] = hazardous
    if accepted is not None:
        query["accepted"] = accepted

    if q:
        q = q.strip()
        ors: List[Dict[str, Any]] = []
        # Code-like query → match code prefix/substring (normalise spaces).
        if _CODE_HINT.search(q):
            norm = q.replace(" ", "")
            ors.append({"code": {"$regex": re.escape(q), "$options": "i"}})
            ors.append({"slug": {"$regex": re.escape(slugify_code(q)), "$options": "i"}})
            # also match by stripped spaces against code
            ors.append({"code": {"$regex": re.escape(norm[:2]) + r".*" + re.escape(norm[2:]) if len(norm) >= 3 else re.escape(norm), "$options": "i"}})
        # Free-text → name + human_names.
        rx = {"$regex": re.escape(q), "$options": "i"}
        ors.append({"name": rx})
        ors.append({"human_names": rx})
        ors.append({"category_name": rx})
        # Category synonym expansion (e.g. "лампи денного світла" -> lamps).
        cat_hits = _category_for_phrase(q)
        if cat_hits:
            ors.append({"category": {"$in": cat_hits}})
        query["$or"] = ors

    cursor = db[C_CODES].find(query, {"_id": 0}).limit(int(limit))
    rows = await cursor.to_list(length=int(limit))
    # Rank: hazardous + name/human exact-ish first (simple heuristic).
    if q:
        ql = q.lower()
        def _score(r: Dict[str, Any]) -> int:
            s = 0
            if ql in (r.get("name", "").lower()):
                s += 2
            if any(ql in (h or "").lower() or (h or "").lower() in ql for h in r.get("human_names", [])):
                s += 3
            if r.get("code", "").lower().replace(" ", "").startswith(ql.replace(" ", "")):
                s += 4
            return -s
        rows.sort(key=_score)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
#  License Matrix — acceptance decision
# ─────────────────────────────────────────────────────────────────────────────
async def license_check(db, code: str) -> Dict[str, Any]:
    """Decide whether we can accept a waste code, and under which license.

    Decision order:
      1. Explicit license_matrix entry for the code (most specific).
      2. Fallback to waste_code.license_allowed + service_available.
    """
    wc = await db[C_CODES].find_one({"code": code}, {"_id": 0})
    base = {
        "code": code,
        "exists": bool(wc),
        "hazardous": (wc or {}).get("hazardous"),
        "name": (wc or {}).get("name"),
        "category": (wc or {}).get("category"),
    }
    if not wc:
        return {**base, "accepted": False, "reason": "Код відсутній у довіднику", "license": None}

    lic = await db[C_LICENSES].find_one({"waste_code": code}, {"_id": 0})
    if lic is not None:
        allowed = bool(lic.get("allowed"))
        valid_until = lic.get("valid_until")
        expired = False
        if valid_until:
            try:
                expired = datetime.fromisoformat(str(valid_until).replace("Z", "+00:00")) < datetime.now(timezone.utc)
            except Exception:
                expired = False
        accepted = allowed and not expired
        reason = (
            "Ліцензія діє" if accepted else
            ("Термін дії ліцензії сплив" if expired else "Код не входить у дозволені ліцензією")
        )
        return {**base, "accepted": accepted, "reason": reason, "license": serialize(lic)}

    # Немає запису в License Matrix → код НЕ входить до ліцензованого переліку.
    # «Не більше і не менше»: публічно приймаються лише ліцензовані коди.
    return {
        **base,
        "accepted": False,
        "reason": "Код не входить до ліцензованого переліку (не приймаємо)",
        "license": None,
        "default_policy": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  «Ми приймаємо» — похідний прапор `accepted` на waste_codes.
#  Єдине правило: код приймається ⇔ існує активний (allowed, не прострочений)
#  запис у License Matrix. Лише цей піднабір стає публічним (каталог/калькулятор/
#  заявка). Майстер-довідник лишається повним для адмінки.
# ─────────────────────────────────────────────────────────────────────────────
def _license_active(lic: Optional[Dict[str, Any]]) -> bool:
    if not lic or not bool(lic.get("allowed")):
        return False
    valid_until = lic.get("valid_until")
    if valid_until:
        try:
            if datetime.fromisoformat(str(valid_until).replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return False
        except Exception:
            pass
    return True


async def sync_code_accepted(db, code: str) -> bool:
    """Перерахувати `accepted` для одного коду на основі License Matrix."""
    lic = await db[C_LICENSES].find_one({"waste_code": code}, {"_id": 0})
    accepted = _license_active(lic)
    await db[C_CODES].update_one(
        {"code": code}, {"$set": {"accepted": accepted, "updated_at": now_iso()}}
    )
    return accepted


async def recompute_accepted_all(db) -> Dict[str, int]:
    """Перерахувати `accepted` для усіх кодів (bulk). Викликається після seed
    ліцензій / reseed / на старті."""
    # 1) Зібрати множину активних ліцензованих кодів.
    licensed: set[str] = set()
    async for lic in db[C_LICENSES].find({}, {"_id": 0, "waste_code": 1, "allowed": 1, "valid_until": 1}):
        if _license_active(lic):
            licensed.add(lic.get("waste_code"))
    # 2) Виставити accepted=True для ліцензованих, False для решти.
    now = now_iso()
    if licensed:
        await db[C_CODES].update_many(
            {"code": {"$in": list(licensed)}},
            {"$set": {"accepted": True, "updated_at": now}},
        )
    await db[C_CODES].update_many(
        {"code": {"$nin": list(licensed)}} if licensed else {},
        {"$set": {"accepted": False, "updated_at": now}},
    )
    accepted_count = await db[C_CODES].count_documents({"accepted": True})
    return {"licensed": len(licensed), "accepted_codes": accepted_count}


async def seed_license_matrix(db, *, force: bool = False) -> Dict[str, Any]:
    """Ідемпотентно засіяти реальний ліцензований перелік (License Matrix).

    Це визначає, які коди оператор реально приймає («ми приймаємо»). Після seed
    автоматично перераховується `accepted` на кодах.
    """
    if force:
        await db[C_LICENSES].delete_many({"source": "license_seed"})

    existing = await db[C_LICENSES].estimated_document_count()
    if existing and not force:
        # Все одно синхронізуємо accepted (на випадок, якщо колекція кодів пересіяна).
        rec = await recompute_accepted_all(db)
        return {"seeded": False, "reason": "already_populated", "count": existing, **rec}

    now = now_iso()
    created = 0
    for entry in ND.licensed_seed_entries():
        code = entry["waste_code"]
        # Сіємо лише коди, які реально існують у довіднику.
        if not await db[C_CODES].find_one({"code": code}, {"_id": 1}):
            logger.warning("[waste] licensed code missing in catalog, skipped: %s", code)
            continue
        prev = await db[C_LICENSES].find_one({"waste_code": code}, {"_id": 0, "id": 1, "created_at": 1})
        doc = {
            **entry,
            "updated_at": now,
            "updated_by": "system_seed",
        }
        if prev:
            doc["id"] = prev.get("id")
            doc["created_at"] = prev.get("created_at") or now
            await db[C_LICENSES].update_one({"waste_code": code}, {"$set": doc})
        else:
            doc["id"] = gen_id("lic")
            doc["created_at"] = now
            await db[C_LICENSES].insert_one(doc)
        created += 1

    rec = await recompute_accepted_all(db)
    logger.info("[waste] seed_license_matrix: seeded=%d %s", created, rec)
    return {"seeded": True, "created": created, **rec}


# ─────────────────────────────────────────────────────────────────────────────
#  Pricing Engine v2 (Wave 4A)
#  Контракт (зворотно сумісний з v0):
#    IN : {code|wasteCode, weight|qty_kg, region, container('provided'|'needed'),
#          transport(bool), urgent(bool)}
#    OUT: {ok, code, price, currency, breakdown:[{key,label,amount}], source,
#          price_per_kg, minimum_charge, applied_rule, ...meta}
#
#  Модель ціни = max(pricePerKg × billable_kg, minimumCharge)
#                + тара + спецтранспорт + регіональний коеф. + терміновість.
#  Тариф (pricePerKg/minimumCharge + опц. overrides логістики) береться з найбільш
#  специфічного активного price_rule, що збігається за кодом/регіоном/ваговою
#  смугою/типом тари; інакше — fallback на code.price_from + глобальні дефолти.
# ─────────────────────────────────────────────────────────────────────────────
REGION_FACTORS: Dict[str, float] = {
    "kyiv": 1.0, "київ": 1.0,
    "kyiv_oblast": 1.05, "center": 1.05,
    "west": 1.12, "east": 1.12, "south": 1.12, "north": 1.08,
}
URGENT_SURCHARGE = 0.25          # +25%
CONTAINER_FEE_PER_KG = 1.5       # UAH/kg when we must provide containers
TRANSPORT_BASE = 1500.0          # UAH flat dispatch
TRANSPORT_PER_KG = 2.0           # UAH/kg

# ── Admin-editable Pricing Defaults (DB-backed, in-memory cached) ────────────
# Persisted in the `waste_pricing_defaults` collection as a singleton
# ({"key": "singleton"}) so admins can rotate the global surcharges without a
# redeploy. Falls back to the module constants above when the collection is
# empty or unavailable.
C_PRICING_DEFAULTS = "waste_pricing_defaults"

_DEFAULTS_CACHE: Dict[str, Any] = {
    "loaded_at": 0.0,
    "data": None,
}
_DEFAULTS_TTL_SEC = 30  # short TTL — pricing surface reads often, edits should propagate quickly


def _fallback_defaults() -> Dict[str, float]:
    return {
        "urgent_surcharge_pct": URGENT_SURCHARGE,
        "container_fee_per_kg": CONTAINER_FEE_PER_KG,
        "transport_base": TRANSPORT_BASE,
        "transport_per_kg": TRANSPORT_PER_KG,
    }


def _sanitize_defaults(patch: Dict[str, Any]) -> Dict[str, float]:
    """Coerce & clamp incoming defaults to safe non-negative floats."""
    out: Dict[str, float] = {}
    fields = ("urgent_surcharge_pct", "container_fee_per_kg", "transport_base", "transport_per_kg")
    for k in fields:
        if k in patch and patch[k] is not None:
            v = _num(patch[k], None)
            if v is None:
                continue
            v = max(0.0, float(v))
            # Cap percentage-style fields to 5.0 (=500%) as a sanity guard.
            if k == "urgent_surcharge_pct" and v > 5.0:
                v = 5.0
            out[k] = v
    return out


async def load_pricing_defaults(db, *, force: bool = False) -> Dict[str, float]:
    """Return the current admin-editable pricing defaults (cached 30s).

    Reads the singleton doc from `waste_pricing_defaults`; merges over the
    hard-coded module constants so any missing key transparently falls back.
    """
    import time as _time
    now = _time.time()
    if (not force) and _DEFAULTS_CACHE["data"] is not None \
            and (now - _DEFAULTS_CACHE["loaded_at"]) < _DEFAULTS_TTL_SEC:
        return _DEFAULTS_CACHE["data"]
    data = _fallback_defaults()
    try:
        doc = await db[C_PRICING_DEFAULTS].find_one({"key": "singleton"}, {"_id": 0}) or {}
        for k, v in (doc.get("data") or {}).items():
            if k in data and v is not None:
                nv = _num(v, None)
                if nv is not None:
                    data[k] = float(nv)
    except Exception:
        pass
    _DEFAULTS_CACHE["data"] = data
    _DEFAULTS_CACHE["loaded_at"] = now
    return data


async def save_pricing_defaults(db, patch: Dict[str, Any], updated_by: Optional[str] = None) -> Dict[str, float]:
    """Upsert the singleton defaults doc; returns the fresh merged snapshot."""
    clean = _sanitize_defaults(patch or {})
    now = now_iso()
    existing = await db[C_PRICING_DEFAULTS].find_one({"key": "singleton"}, {"_id": 0}) or {}
    merged_data = {**(existing.get("data") or {}), **clean}
    await db[C_PRICING_DEFAULTS].update_one(
        {"key": "singleton"},
        {"$set": {"key": "singleton", "data": merged_data, "updated_at": now, "updated_by": updated_by or ""},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    # Invalidate cache immediately so the next price_estimate() picks up the change.
    _DEFAULTS_CACHE["data"] = None
    _DEFAULTS_CACHE["loaded_at"] = 0.0
    return await load_pricing_defaults(db, force=True)


def _region_factor(region: Optional[str]) -> float:
    if not region:
        return 1.0
    return REGION_FACTORS.get(str(region).strip().lower(), 1.1)


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def normalize_price_rule(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate + normalise an incoming price_rule payload."""
    code = (data.get("wasteCode") or data.get("waste_code") or "*").strip() or "*"
    region = (data.get("region") or "*").strip().lower() or "*"
    container = (data.get("containerType") or data.get("container_type") or "any").strip().lower() or "any"
    if container not in ("any", "provided", "needed"):
        container = "any"
    price_per_kg = _num(data.get("pricePerKg") if data.get("pricePerKg") is not None else data.get("price_per_kg"))
    if price_per_kg is None:
        raise ValueError("pricePerKg is required (number)")
    out = {
        "wasteCode": code,
        "region": region,
        "minWeight": _num(data.get("minWeight"), 0.0) or 0.0,
        "maxWeight": _num(data.get("maxWeight"), None),
        "containerType": container,
        "transportRequired": bool(data.get("transportRequired", False)),
        "urgent": bool(data.get("urgent", False)),
        "pricePerKg": price_per_kg,
        "minimumCharge": _num(data.get("minimumCharge"), 0.0) or 0.0,
        # optional logistics overrides (fall back to globals when absent)
        "containerPerKg": _num(data.get("containerPerKg"), None),
        "transportFlat": _num(data.get("transportFlat"), None),
        "transportPerKg": _num(data.get("transportPerKg"), None),
        "urgentSurchargePct": _num(data.get("urgentSurchargePct"), None),
        "currency": data.get("currency") or "UAH",
        "notes": data.get("notes"),
        "active": bool(data.get("active", True)),
    }
    return out


async def find_price_rule(
    db, code: str, region: Optional[str], billable_kg: float, container: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Pick the most specific active rule matching code/region/weight/container."""
    region_l = (region or "*").strip().lower()
    want_container = "needed" if container == "needed" else "provided"
    candidates = await db[C_PRICE_RULES].find(
        {"active": {"$ne": False}, "wasteCode": {"$in": [code, "*"]}},
        {"_id": 0},
    ).to_list(length=1000)

    best: Optional[Dict[str, Any]] = None
    best_score = -1
    best_band = float("inf")
    for r in candidates:
        rreg = (r.get("region") or "*").strip().lower()
        if rreg not in ("*", "", region_l):
            continue
        minw = _num(r.get("minWeight"), 0.0) or 0.0
        maxw = _num(r.get("maxWeight"), None)
        if billable_kg < minw:
            continue
        if maxw is not None and billable_kg > maxw:
            continue
        ctype = (r.get("containerType") or "any").strip().lower()
        if ctype not in ("any", "") and ctype != want_container:
            continue
        score = 0
        if r.get("wasteCode") == code:
            score += 8
        if rreg not in ("*", "") and rreg == region_l:
            score += 4
        if ctype not in ("any", ""):
            score += 2
        band = (maxw - minw) if maxw is not None else float("inf")
        if score > best_score or (score == best_score and band < best_band):
            best, best_score, best_band = r, score, band
    return best


async def price_estimate(
    db, code: str, qty_kg: float, *,
    region: Optional[str] = None, container: Optional[str] = None,
    transport: Optional[bool] = None, urgent: bool = False,
) -> Dict[str, Any]:
    wc = await db[C_CODES].find_one({"code": code}, {"_id": 0})
    if not wc:
        return {"code": code, "ok": False, "reason": "Код відсутній у довіднику"}

    min_kg = _num(wc.get("min_order_kg"), 0.0) or 0.0
    billable_kg = max(_num(qty_kg, 0.0) or 0.0, min_kg)
    needs_container = (container == "needed") and bool(wc.get("requires_container"))
    needs_transport = (transport is True) and bool(wc.get("requires_transport", True))
    rfactor = _region_factor(region)

    rule = await find_price_rule(db, code, region, billable_kg, container)

    # ── Load admin-editable global defaults (DB-backed, 30s cache) ────────
    _pd = await load_pricing_defaults(db)
    _DEF_URGENT      = _pd.get("urgent_surcharge_pct", URGENT_SURCHARGE)
    _DEF_CONTAINER   = _pd.get("container_fee_per_kg", CONTAINER_FEE_PER_KG)
    _DEF_TRANS_BASE  = _pd.get("transport_base",       TRANSPORT_BASE)
    _DEF_TRANS_PERKG = _pd.get("transport_per_kg",     TRANSPORT_PER_KG)

    # ── Resolve pricing parameters (rule overrides defaults) ──
    if rule:
        price_per_kg = _num(rule.get("pricePerKg"))
        min_charge = _num(rule.get("minimumCharge"), 0.0) or 0.0
        container_per_kg = _num(rule.get("containerPerKg"), _DEF_CONTAINER)
        transport_flat = _num(rule.get("transportFlat"), _DEF_TRANS_BASE)
        transport_per_kg = _num(rule.get("transportPerKg"), _DEF_TRANS_PERKG)
        urgent_pct = _num(rule.get("urgentSurchargePct"), _DEF_URGENT)
        rule_region = (rule.get("region") or "*").strip().lower()
        apply_region = rule_region in ("*", "")  # region-specific rule already priced for region
        source = "rule"
        applied_rule = {
            "id": rule.get("id"),
            "wasteCode": rule.get("wasteCode"),
            "region": rule.get("region"),
            "band": [rule.get("minWeight"), rule.get("maxWeight")],
            "pricePerKg": price_per_kg,
            "minimumCharge": min_charge,
        }
    else:
        price_per_kg = _num(wc.get("price_from"), None)
        min_charge = 0.0
        container_per_kg = _DEF_CONTAINER
        transport_flat = _DEF_TRANS_BASE
        transport_per_kg = _DEF_TRANS_PERKG
        urgent_pct = _DEF_URGENT
        apply_region = True
        source = "default"
        applied_rule = None

    breakdown: List[Dict[str, Any]] = []
    base = None
    if price_per_kg is not None:
        base = round(price_per_kg * billable_kg, 2)
        breakdown.append({"key": "base", "label": f"Утилізація ({price_per_kg:g} грн × {billable_kg:g} кг)", "amount": base})
        if min_charge and base < min_charge:
            adj = round(min_charge - base, 2)
            breakdown.append({"key": "min_charge", "label": f"Мінімальний тариф (від {min_charge:g} грн)", "amount": adj})
            base = round(min_charge, 2)

    container_fee = 0.0
    if needs_container:
        container_fee = round((container_per_kg or 0) * billable_kg, 2)
        breakdown.append({"key": "container", "label": "Тара / контейнери", "amount": container_fee})

    transport_fee = 0.0
    if needs_transport:
        transport_fee = round((transport_flat or 0) + (transport_per_kg or 0) * billable_kg, 2)
        breakdown.append({"key": "transport", "label": "Спецтранспорт (вивіз)", "amount": transport_fee})

    subtotal = round((base or 0) + container_fee + transport_fee, 2)

    region_adj = 0.0
    if apply_region and rfactor != 1.0 and subtotal:
        region_adj = round(subtotal * (rfactor - 1.0), 2)
        breakdown.append({"key": "region", "label": f"Регіональний коефіцієнт (×{rfactor:g})", "amount": region_adj})

    after_region = subtotal + region_adj
    urgent_fee = 0.0
    if urgent and after_region:
        urgent_fee = round(after_region * (urgent_pct or 0), 2)
        breakdown.append({"key": "urgent", "label": f"Терміновість (+{round((urgent_pct or 0) * 100):g}%)", "amount": urgent_fee})

    total = round(after_region + urgent_fee, 2) if base is not None else None

    return {
        "code": code, "ok": True,
        "name": wc.get("name"),
        "category": wc.get("category"),
        "hazardous": wc.get("hazardous"),
        "accepted": bool(wc.get("accepted")),
        "price_from": wc.get("price_from"),
        "price_per_kg": price_per_kg,
        "minimum_charge": min_charge,
        "price_unit": wc.get("price_unit"),
        "min_order_kg": min_kg,
        "qty_kg": qty_kg,
        "billable_kg": billable_kg,
        "region": region,
        "container": container,
        "transport": needs_transport,
        "urgent": urgent,
        "breakdown": breakdown,
        "price": total,
        "estimate_from": total,   # backward-compat
        "currency": (rule or {}).get("currency", "UAH") if rule else "UAH",
        "source": source,
        "applied_rule": applied_rule,
        "requires_container": wc.get("requires_container"),
        "requires_transport": wc.get("requires_transport"),
        "required_docs": wc.get("required_docs"),
        "note": (
            "Тариф за прайс-листом. Точна ціна — після узгодження партії, тари та логістики."
            if source == "rule" else
            "Орієнтовна вартість (базовий тариф). Точна ціна — після узгодження партії, тари та логістики."
        ),
    }


async def seed_price_rules(db) -> Dict[str, Any]:
    """Seed tiered price rules for EVERY accepted/licensed code (idempotent per code).

    Базовий тариф залежить від бізнес-категорії коду; для кожного коду — дві смуги:
    мала партія (преміум за кг + мін.тариф) та об'єм (базовий за кг без мінімуму).
    Викликається після seed_license_matrix, тож публічний калькулятор одразу
    повертає реальну ціну для всього ліцензованого набору.
    """
    # Базовий тариф (грн/кг) + мінімальний тариф (грн) за категорією.
    CATEGORY_BASE: Dict[str, tuple[float, float]] = {
        "oils": (18.0, 2000.0),
        "accumulators": (14.0, 2000.0),
        "batteries": (38.0, 2500.0),
        "tires": (9.0, 1800.0),
        "electronics": (28.0, 2500.0),
        "lamps": (45.0, 2500.0),
        "paints": (32.0, 2500.0),
        "polymers": (22.0, 2000.0),
        "plastic": (20.0, 2000.0),
        "medical": (60.0, 3000.0),
        "pharma": (70.0, 3000.0),
        "agrochem": (55.0, 3000.0),
        "organic": (12.0, 1500.0),
        "other_hazard": (40.0, 2500.0),
    }
    DEFAULT_BASE = (35.0, 2500.0)

    # Лише ліцензовані (accepted) коди отримують прайс — рівно «наш» асортимент.
    accepted = await db[C_CODES].find(
        {"accepted": True}, {"_id": 0, "code": 1, "category": 1, "price_from": 1},
    ).to_list(length=2000)

    now = now_iso()
    created, skipped = 0, 0
    for wc in accepted:
        code = wc["code"]
        # Ідемпотентність: пропустити коди, що вже мають правило.
        if await db[C_PRICE_RULES].find_one({"wasteCode": code}, {"_id": 1}):
            skipped += 1
            continue
        base_kg, min_charge = CATEGORY_BASE.get(wc.get("category"), DEFAULT_BASE)
        pf = _num(wc.get("price_from"), None)
        if pf:
            base_kg = pf
        tiers = [
            {"minWeight": 0, "maxWeight": 100, "pricePerKg": round(base_kg * 1.5, 2), "minimumCharge": min_charge},
            {"minWeight": 100, "maxWeight": None, "pricePerKg": round(base_kg, 2), "minimumCharge": 0},
        ]
        for t in tiers:
            doc = normalize_price_rule({"wasteCode": code, "region": "*", "containerType": "any", **t})
            doc["id"] = gen_id("pr")
            doc["created_at"] = now
            doc["updated_at"] = now
            doc["created_by"] = "seed"
            await db[C_PRICE_RULES].insert_one(doc)
            created += 1
        # Проставити price_from на коді (орієнтир для UI), якщо порожній.
        if not pf:
            await db[C_CODES].update_one({"code": code}, {"$set": {"price_from": round(base_kg, 2)}})
    logger.info("[waste] seed price_rules: created=%d skipped_codes=%d", created, skipped)
    return {"seeded": created > 0, "created": created, "skipped_codes": skipped}


# ════════════════════════════════════════════════════════════════════════════
#  CATALOG CATEGORIES — admin-managed (icons + UA/EN names + code assignment)
# ════════════════════════════════════════════════════════════════════════════

# English display names for the built-in categories. Used only to bootstrap the
# `waste_categories` collection the first time; afterwards everything is edited
# from the admin Content Center.
CATEGORY_NAMES_EN: Dict[str, str] = {
    "medical": "Medical waste",
    "pharma": "Pharmaceutical waste",
    "batteries": "Batteries",
    "accumulators": "Accumulators",
    "electronics": "Electronics (WEEE)",
    "mercury": "Mercury-containing waste",
    "lamps": "Lamps",
    "pesticides": "Pesticides",
    "agrochem": "Agrochemicals",
    "paints": "Paints & coatings (PCM)",
    "oils": "Used oils",
    "tires": "Tires",
    "plastic": "Plastic",
    "polymers": "Polymers",
    "organic": "Organic waste",
    "other_hazard": "Other hazardous waste",
}

# Curated set of icon keys the admin can pick from (all exist in lucide-react
# on the frontend via the ICON_REGISTRY). The seed data already uses a subset.
AVAILABLE_ICON_KEYS: List[str] = [
    "stethoscope", "pill", "syringe", "battery", "car-battery", "cpu",
    "alert-triangle", "shield-alert", "lightbulb", "skull", "flask",
    "paint-bucket", "droplet", "fuel", "circle-dot", "recycle", "boxes",
    "leaf", "sprout", "biohazard", "radiation", "atom", "trash-2", "package",
    "factory", "wind", "flame", "bug", "trees", "glass-water",
]


def _slugify_key(text: str) -> str:
    """Very small transliterating slugifier for category keys (ascii-ish)."""
    text = (text or "").strip().lower()
    # keep latin letters/digits, collapse everything else to underscores
    out = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return out or f"cat_{uuid.uuid4().hex[:6]}"


async def ensure_category_indexes(db) -> None:
    try:
        await db[C_CATEGORIES].create_index("key", unique=True)
        await db[C_CATEGORIES].create_index("order")
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] ensure_category_indexes (non-fatal): %s", e)


async def seed_waste_categories(db, *, force: bool = False) -> Dict[str, Any]:
    """Idempotently populate the `waste_categories` collection from the built-in
    CATEGORIES map. Existing rows are preserved (admin edits win) unless force."""
    await ensure_category_indexes(db)
    now = datetime.now(timezone.utc).isoformat()
    created = 0
    kept = 0
    order = 0
    for key, meta in CATEGORIES.items():
        order += 1
        existing = await db[C_CATEGORIES].find_one({"key": key})
        if existing and not force:
            kept += 1
            continue
        doc = {
            "key": key,
            "name_uk": meta.get("name") or key,
            "name_en": CATEGORY_NAMES_EN.get(key, meta.get("name") or key),
            "icon": meta.get("icon") or "shield-alert",
            "synonyms": meta.get("synonyms", []),
            "desc_uk": "",
            "desc_en": "",
            "image_url": "",
            "order": order,
            "active": True,
            "created_at": now,
            "updated_at": now,
        }
        await db[C_CATEGORIES].update_one({"key": key}, {"$set": doc}, upsert=True)
        created += 1
    # Backfill: ensure new optional fields exist on any pre-existing rows.
    try:
        for f in ("desc_uk", "desc_en", "image_url"):
            await db[C_CATEGORIES].update_many({f: {"$exists": False}}, {"$set": {f: ""}})
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] category field backfill (non-fatal): %s", e)
    return {"seeded": True, "created": created, "kept": kept}


async def list_categories_full(db, *, active_only: bool = False,
                               accepted: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Return category docs (ordered) enriched with live code counts."""
    q: Dict[str, Any] = {}
    if active_only:
        q["active"] = True
    cats = await db[C_CATEGORIES].find(q, {"_id": 0}).sort("order", 1).to_list(length=500)
    base_q: Dict[str, Any] = {}
    if accepted is not None:
        base_q["accepted"] = accepted
    out: List[Dict[str, Any]] = []
    for c in cats:
        key = c["key"]
        cnt = await db[C_CODES].count_documents({**base_q, "category": key})
        haz = await db[C_CODES].count_documents({**base_q, "category": key, "hazardous": True})
        out.append({**c, "count": cnt, "hazardous_count": haz})
    return out


async def assign_codes_to_category(db, key: str, codes: List[str]) -> Dict[str, Any]:
    """Set `category=key` on every code in `codes`; any code previously in this
    category but NOT in the list becomes uncategorized (category="")."""
    codes = [str(c).strip() for c in (codes or []) if str(c).strip()]
    # Detach codes that were in this category and are no longer selected.
    detached = await db[C_CODES].update_many(
        {"category": key, "code": {"$nin": codes}},
        {"$set": {"category": ""}},
    )
    attached = 0
    if codes:
        res = await db[C_CODES].update_many(
            {"code": {"$in": codes}},
            {"$set": {"category": key}},
        )
        attached = res.modified_count
    return {"attached": attached, "detached": detached.modified_count}


async def seed_waste_core(db) -> Dict[str, Any]:
    """One-shot bootstrap used at startup: indexes + idempotent code seed +
    реальний ліцензований перелік + прайс для ліцензованих кодів."""
    await ensure_indexes(db)
    res = await seed_waste_codes(db)
    try:
        res["licenses"] = await seed_license_matrix(db)
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] seed_license_matrix (non-fatal): %s", e)
    try:
        # Гарантовано синхронізувати accepted навіть якщо ліцензії вже були.
        res["accepted"] = await recompute_accepted_all(db)
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] recompute_accepted_all (non-fatal): %s", e)
    try:
        res["price_rules"] = await seed_price_rules(db)
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] seed_price_rules (non-fatal): %s", e)
    try:
        res["categories"] = await seed_waste_categories(db)
    except Exception as e:  # pragma: no cover
        logger.warning("[waste] seed_waste_categories (non-fatal): %s", e)
    return res
