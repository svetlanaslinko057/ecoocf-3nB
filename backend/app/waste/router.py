"""
Waste Core HTTP surface (Wave 2)
================================

All routes under ``/api/waste``.

Public (no-auth) read surface — feeds the future SEO directory + calculator:
  GET  /api/waste/categories
  GET  /api/waste/codes                     list / filter / search
  GET  /api/waste/codes/by-code             exact lookup (?code=18 01 03*)
  GET  /api/waste/codes/{slug}              SEO code page
  GET  /api/waste/search                    smart phrase -> codes
  GET  /api/waste/license/check             acceptance decision (?code=)
  POST /api/waste/price                     v0 price estimate
  POST /api/waste/requests/public           public lead (from calculator/site)

Staff surface (RBAC):
  POST/PUT/DELETE /api/waste/codes          admin
  POST /api/waste/admin/seed | /import      admin
  CRUD /api/waste/companies                 manager/admin   (Company360)
  CRUD /api/waste/objects                   manager/admin
  CRUD /api/waste/licenses                  admin           (License Matrix)
  CRUD /api/waste/requests + /{id}/stage    manager/admin
  GET  /api/waste/stats                     manager/admin
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from security import require_admin, require_manager_or_admin
from app.core.db_runtime import get_db
from app.waste import service as S
from app.waste.seed_data import CATEGORIES, WASTE_CODES

logger = logging.getLogger("eco.waste.router")

router = APIRouter(prefix="/api/waste", tags=["waste"])


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC READ SURFACE
# ════════════════════════════════════════════════════════════════════════════
@router.get("/categories")
async def list_categories(accepted: Optional[bool] = None):
    """Category cards with live code counts (the SEO landing layer).

    `accepted=true` → рахувати лише ліцензовані коди (публічний фронт).
    Дані читаються з керованої адмінкою колекції ``waste_categories``.
    """
    db = get_db()
    active_only = bool(accepted)  # публічний фронт бачить лише активні категорії
    cats = await S.list_categories_full(db, active_only=active_only, accepted=accepted)
    out: List[Dict[str, Any]] = []
    for c in cats:
        # Приховувати порожні категорії на публічному фронті (accepted-only).
        if accepted and c.get("count", 0) == 0:
            continue
        out.append({
            "key": c["key"],
            "name": c.get("name_uk") or c["key"],   # backward-compat (UA)
            "name_uk": c.get("name_uk") or c["key"],
            "name_en": c.get("name_en") or c.get("name_uk") or c["key"],
            "icon": c.get("icon"),
            "synonyms": c.get("synonyms", []),
            "desc_uk": c.get("desc_uk", ""),
            "desc_en": c.get("desc_en", ""),
            "image_url": c.get("image_url", ""),
            "order": c.get("order", 0),
            "active": c.get("active", True),
            "count": c.get("count", 0),
            "hazardous_count": c.get("hazardous_count", 0),
        })
    return {"success": True, "categories": out, "total_categories": len(out)}


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN — CATALOG CATEGORY MANAGEMENT (Content Center → Каталог відходів)
# ════════════════════════════════════════════════════════════════════════════
@router.get("/admin/icons", dependencies=[Depends(require_manager_or_admin)])
async def admin_available_icons():
    """Icon keys the admin may pick from (rendered client-side via ICON_REGISTRY)."""
    return {"success": True, "icons": S.AVAILABLE_ICON_KEYS}


@router.get("/admin/categories", dependencies=[Depends(require_manager_or_admin)])
async def admin_list_categories():
    """Full category list (all, incl. inactive) with live counts + assigned codes."""
    db = get_db()
    cats = await S.list_categories_full(db, active_only=False, accepted=None)
    out: List[Dict[str, Any]] = []
    for c in cats:
        code_rows = await db[S.C_CODES].find(
            {"category": c["key"]}, {"_id": 0, "code": 1, "name": 1, "hazardous": 1, "accepted": 1}
        ).sort("code", 1).to_list(length=1000)
        out.append({**c, "codes": [r.get("code") for r in code_rows], "code_rows": code_rows})
    return {"success": True, "categories": out, "total": len(out)}


@router.post("/admin/categories", dependencies=[Depends(require_admin)])
async def admin_create_category(payload: Dict[str, Any] = Body(...)):
    """Create a new catalog category. `codes` (optional) assigns waste codes to it."""
    db = get_db()
    name_uk = (payload.get("name_uk") or "").strip()
    name_en = (payload.get("name_en") or "").strip()
    if not name_uk and not name_en:
        raise HTTPException(status_code=422, detail="name_uk or name_en is required")
    key = (payload.get("key") or "").strip() or S._slugify_key(name_en or name_uk)
    if await db[S.C_CATEGORIES].find_one({"key": key}):
        raise HTTPException(status_code=409, detail=f"category key '{key}' already exists")
    # order → append to end unless explicitly given
    if payload.get("order") is not None:
        order = int(payload["order"])
    else:
        last = await db[S.C_CATEGORIES].find_one({}, sort=[("order", -1)])
        order = int((last or {}).get("order", 0)) + 1
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "key": key,
        "name_uk": name_uk or name_en,
        "name_en": name_en or name_uk,
        "icon": (payload.get("icon") or "shield-alert").strip(),
        "synonyms": payload.get("synonyms") or [],
        "desc_uk": (payload.get("desc_uk") or "").strip(),
        "desc_en": (payload.get("desc_en") or "").strip(),
        "image_url": (payload.get("image_url") or "").strip(),
        "order": order,
        "active": bool(payload.get("active", True)),
        "created_at": now,
        "updated_at": now,
    }
    await db[S.C_CATEGORIES].insert_one(dict(doc))
    assign = await S.assign_codes_to_category(db, key, payload.get("codes") or [])
    return {"success": True, "category": doc, "assign": assign}


@router.put("/admin/categories/{key}", dependencies=[Depends(require_admin)])
async def admin_update_category(key: str, patch: Dict[str, Any] = Body(...)):
    """Update category meta (icon / names / order / synonyms / active) and,
    if `codes` is present, re-sync the assigned waste codes."""
    db = get_db()
    existing = await db[S.C_CATEGORIES].find_one({"key": key})
    if not existing:
        raise HTTPException(status_code=404, detail="category not found")
    updates: Dict[str, Any] = {}
    for field in ("name_uk", "name_en", "icon", "desc_uk", "desc_en", "image_url"):
        if field in patch and patch[field] is not None:
            updates[field] = str(patch[field]).strip()
    if "synonyms" in patch and patch["synonyms"] is not None:
        updates["synonyms"] = patch["synonyms"]
    if "order" in patch and patch["order"] is not None:
        updates["order"] = int(patch["order"])
    if "active" in patch and patch["active"] is not None:
        updates["active"] = bool(patch["active"])
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db[S.C_CATEGORIES].update_one({"key": key}, {"$set": updates})
    assign = None
    if "codes" in patch and patch["codes"] is not None:
        assign = await S.assign_codes_to_category(db, key, patch["codes"])
    doc = await db[S.C_CATEGORIES].find_one({"key": key}, {"_id": 0})
    return {"success": True, "category": doc, "assign": assign}


@router.delete("/admin/categories/{key}", dependencies=[Depends(require_admin)])
async def admin_delete_category(key: str):
    """Delete a category. Any codes assigned to it become uncategorized."""
    db = get_db()
    existing = await db[S.C_CATEGORIES].find_one({"key": key})
    if not existing:
        raise HTTPException(status_code=404, detail="category not found")
    detached = await db[S.C_CODES].update_many({"category": key}, {"$set": {"category": ""}})
    await db[S.C_CATEGORIES].delete_one({"key": key})
    return {"success": True, "deleted": key, "detached_codes": detached.modified_count}


@router.post("/admin/categories/reorder", dependencies=[Depends(require_admin)])
async def admin_reorder_categories(payload: Dict[str, Any] = Body(...)):
    """Persist a new ordering. Body: {"order": ["key1","key2", ...]}."""
    db = get_db()
    order_list = payload.get("order") or []
    now = datetime.now(timezone.utc).isoformat()
    for idx, key in enumerate(order_list):
        await db[S.C_CATEGORIES].update_one(
            {"key": key}, {"$set": {"order": idx + 1, "updated_at": now}}
        )
    return {"success": True, "count": len(order_list)}



@router.get("/codes")
async def list_codes(
    q: Optional[str] = None,
    category: Optional[str] = None,
    hazardous: Optional[bool] = None,
    chapter: Optional[str] = None,
    group: Optional[str] = None,
    parent_code: Optional[str] = None,
    official: Optional[bool] = None,
    accepted: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    if hazardous is not None:
        query["hazardous"] = hazardous
    if chapter:
        query["chapter"] = chapter
    if group:
        query["group"] = group
    if parent_code:
        query["parent_code"] = parent_code
    if official is not None:
        query["official"] = official
    if accepted is not None:
        query["accepted"] = accepted
    if q:
        # Передати у smart-search, якщо є фільтр пошуку — він робить ранжування
        rows = await S.search_codes(db, q=q, category=category, hazardous=hazardous, accepted=accepted, limit=limit + offset)
        # додаткове фільтрування за главою/групою (smart search їх не знає)
        if chapter:
            rows = [r for r in rows if r.get("chapter") == chapter]
        if group:
            rows = [r for r in rows if r.get("group") == group]
        if parent_code:
            rows = [r for r in rows if r.get("parent_code") == parent_code]
        total = len(rows)
        return {"success": True, "items": rows[offset:offset + limit], "count": len(rows[offset:offset + limit]), "total": total}

    total = await db[S.C_CODES].count_documents(query)
    cursor = db[S.C_CODES].find(query, {"_id": 0}).sort("code", 1).skip(offset).limit(limit)
    rows = await cursor.to_list(length=limit)
    return {"success": True, "items": rows, "count": len(rows), "total": total}


@router.get("/chapters")
async def list_chapters():
    """20 глав офіційного «Національного переліку відходів»."""
    db = get_db()
    chs = await db[S.C_CHAPTERS].find({}, {"_id": 0}).sort("code", 1).to_list(length=100)
    # збагачуємо лічильниками
    for c in chs:
        c["codes_count"] = await db[S.C_CODES].count_documents({"chapter": c["code"]})
        c["hazardous_count"] = await db[S.C_CODES].count_documents({"chapter": c["code"], "hazardous": True})
        c["groups_count"] = await db[S.C_GROUPS].count_documents({"chapter": c["code"]})
    return {"success": True, "items": chs, "count": len(chs)}


@router.get("/groups")
async def list_groups(chapter: Optional[str] = None):
    """115 підгруп або підгрупи у межах конкретної глави."""
    db = get_db()
    q = {"chapter": chapter} if chapter else {}
    grps = await db[S.C_GROUPS].find(q, {"_id": 0}).sort("code", 1).to_list(length=500)
    for g in grps:
        g["codes_count"] = await db[S.C_CODES].count_documents({"group": g["code"]})
        g["hazardous_count"] = await db[S.C_CODES].count_documents({"group": g["code"], "hazardous": True})
    return {"success": True, "items": grps, "count": len(grps)}


@router.get("/codes/by-code")
async def get_code_by_code(code: str):
    db = get_db()
    wc = await db[S.C_CODES].find_one({"code": code}, {"_id": 0})
    if not wc:
        raise HTTPException(404, "Код відсутній у довіднику")
    mirror = None
    if wc.get("mirror_code"):
        mirror = await db[S.C_CODES].find_one({"code": wc["mirror_code"]}, {"_id": 0})
    return {"success": True, "code": wc, "mirror": mirror}


@router.get("/search")
async def smart_search(q: str = Query(..., min_length=1), accepted: Optional[bool] = None, limit: int = Query(20, ge=1, le=100)):
    """Waste Intelligence v0 — resolve a human phrase OR code fragment to codes."""
    rows = await S.search_codes(get_db(), q=q, accepted=accepted, limit=limit)
    return {"success": True, "query": q, "items": rows, "count": len(rows)}


@router.get("/license/check")
async def check_license(code: str):
    return {"success": True, **(await S.license_check(get_db(), code))}


@router.get("/pricing/meta")
async def pricing_meta():
    """Public pricing metadata: regions, surcharges, default coefficients.

    ``defaults`` reflects the admin-editable values persisted in
    ``waste_pricing_defaults`` (falls back to module constants if missing).
    """
    defaults = await S.load_pricing_defaults(get_db())
    return {
        "success": True,
        "regions": [
            {"key": "kyiv", "name": "Київ", "factor": S.REGION_FACTORS["kyiv"]},
            {"key": "kyiv_oblast", "name": "Київська область", "factor": S.REGION_FACTORS["kyiv_oblast"]},
            {"key": "center", "name": "Центр", "factor": S.REGION_FACTORS["center"]},
            {"key": "north", "name": "Північ", "factor": S.REGION_FACTORS["north"]},
            {"key": "west", "name": "Захід", "factor": S.REGION_FACTORS["west"]},
            {"key": "east", "name": "Схід", "factor": S.REGION_FACTORS["east"]},
            {"key": "south", "name": "Південь", "factor": S.REGION_FACTORS["south"]},
        ],
        "containers": [
            {"key": "provided", "name": "Тара клієнта"},
            {"key": "needed", "name": "Потрібна наша тара"},
        ],
        "defaults": {
            "urgent_surcharge_pct": defaults["urgent_surcharge_pct"],
            "container_fee_per_kg": defaults["container_fee_per_kg"],
            "transport_base": defaults["transport_base"],
            "transport_per_kg": defaults["transport_per_kg"],
        },
        "currency": "UAH",
    }


# ── Admin-editable global pricing defaults ────────────────────────────────
# Read: admin OR manager (для перегляду в /app/pricing).
# Write: admin only (rotates URGENCY/TRANSPORT/CONTAINER глобальні відсотки).
@router.get("/pricing/defaults", dependencies=[Depends(require_manager_or_admin)])
async def get_pricing_defaults():
    """Return current admin-editable pricing defaults."""
    data = await S.load_pricing_defaults(get_db(), force=True)
    return {"success": True, "defaults": data}


@router.put("/pricing/defaults", dependencies=[Depends(require_admin)])
async def update_pricing_defaults(
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Update admin-editable pricing defaults (any subset).

    Body: {urgent_surcharge_pct?, container_fee_per_kg?, transport_base?, transport_per_kg?}
    Values are clamped to [0, +∞); urgent_surcharge_pct additionally capped at 5.0 (=500%).
    """
    fresh = await S.save_pricing_defaults(
        get_db(),
        data,
        updated_by=user.get("email") or user.get("id"),
    )
    return {"success": True, "defaults": fresh}


@router.post("/price")
async def estimate_price(data: Dict[str, Any] = Body(...)):
    code = (data.get("code") or data.get("wasteCode") or "").strip()
    if not code:
        raise HTTPException(400, "code is required")
    qty = data.get("qty_kg") or data.get("weight") or data.get("quantity") or 0
    return {"success": True, **(await S.price_estimate(
        get_db(), code, float(qty),
        region=data.get("region"),
        container=data.get("container"),
        transport=data.get("transport"),
        urgent=bool(data.get("urgent")),
    ))}


# NOTE: keep the {slug} route LAST among GET /codes/* so it doesn't shadow
# the explicit sub-paths above.
@router.get("/codes/{slug}")
async def get_code_by_slug(slug: str):
    db = get_db()
    wc = await db[S.C_CODES].find_one({"slug": slug}, {"_id": 0})
    if not wc:
        raise HTTPException(404, "Сторінку коду не знайдено")
    mirror = None
    if wc.get("mirror_code"):
        mirror = await db[S.C_CODES].find_one({"code": wc["mirror_code"]}, {"_id": 0})
    return {"success": True, "code": wc, "mirror": mirror}


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN — codes management + seeding
# ════════════════════════════════════════════════════════════════════════════
@router.post("/admin/seed", dependencies=[Depends(require_admin)])
async def admin_seed(force: bool = False):
    res = await S.seed_waste_codes(get_db(), force=force)
    return {"success": True, **res}


@router.post("/admin/reseed-national", dependencies=[Depends(require_admin)])
async def admin_reseed_national():
    """Drop ALL waste codes/chapters/groups та повторно засіяти офіційним переліком.
    License Matrix не чіпається — після reseed синхронізуємо `accepted`."""
    res = await S.seed_waste_codes(get_db(), force=True)
    rec = await S.recompute_accepted_all(get_db())
    return {"success": True, **res, "accepted": rec}


@router.get("/admin/stats", dependencies=[Depends(require_admin)])
async def admin_stats():
    db = get_db()
    return {
        "success": True,
        "chapters": await db[S.C_CHAPTERS].count_documents({}),
        "groups": await db[S.C_GROUPS].count_documents({}),
        "codes": await db[S.C_CODES].count_documents({}),
        "hazardous": await db[S.C_CODES].count_documents({"hazardous": True}),
        "accepted": await db[S.C_CODES].count_documents({"accepted": True}),
        "official": await db[S.C_CODES].count_documents({"official": True}),
        "custom": await db[S.C_CODES].count_documents({"official": {"$ne": True}}),
        "with_price": await db[S.C_CODES].count_documents({"price_from": {"$ne": None, "$gt": 0}}),
    }


@router.post("/admin/import", dependencies=[Depends(require_admin)])
async def admin_import(items: List[Dict[str, Any]] = Body(...)):
    """Bulk import/replace waste codes from an external dataset (upsert by code)."""
    db = get_db()
    created, updated = 0, 0
    for entry in items:
        if not entry.get("code"):
            continue
        doc = S.build_full_doc(entry)
        prev = await db[S.C_CODES].find_one({"code": doc["code"]}, {"_id": 0, "id": 1, "created_at": 1})
        if prev:
            doc["id"] = prev.get("id") or doc["id"]
            doc["created_at"] = prev.get("created_at") or doc["created_at"]
            await db[S.C_CODES].update_one({"code": doc["code"]}, {"$set": doc})
            updated += 1
        else:
            await db[S.C_CODES].insert_one(doc)
            created += 1
    total = await db[S.C_CODES].count_documents({})
    return {"success": True, "created": created, "updated": updated, "total": total}


@router.post("/codes", dependencies=[Depends(require_admin)])
async def create_code(entry: Dict[str, Any] = Body(...)):
    db = get_db()
    if not entry.get("code"):
        raise HTTPException(400, "code is required")
    if await db[S.C_CODES].find_one({"code": entry["code"]}):
        raise HTTPException(409, "Код вже існує")
    doc = S.build_full_doc(entry)
    await db[S.C_CODES].insert_one(doc)
    return {"success": True, "code": S.serialize(doc)}


@router.put("/codes/by-code", dependencies=[Depends(require_admin)])
async def update_code(code: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    existing = await db[S.C_CODES].find_one({"code": code}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Код відсутній у довіднику")
    patch.pop("id", None)
    patch.pop("code", None)
    patch["updated_at"] = S.now_iso()
    await db[S.C_CODES].update_one({"code": code}, {"$set": patch})
    fresh = await db[S.C_CODES].find_one({"code": code}, {"_id": 0})
    return {"success": True, "code": fresh}


@router.delete("/codes/by-code", dependencies=[Depends(require_admin)])
async def delete_code(code: str):
    db = get_db()
    res = await db[S.C_CODES].delete_one({"code": code})
    if not res.deleted_count:
        raise HTTPException(404, "Код відсутній у довіднику")
    return {"success": True}


# ── ADMIN: Глави (level=1) ──────────────────────────────────────────────────
@router.post("/chapters", dependencies=[Depends(require_admin)])
async def create_chapter(entry: Dict[str, Any] = Body(...)):
    db = get_db()
    code = (entry.get("code") or "").strip()
    name = (entry.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "code та name обовʼязкові")
    if await db[S.C_CHAPTERS].find_one({"code": code}):
        raise HTTPException(409, "Глава вже існує")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("chap"), "code": code, "name": name, "level": 1,
        "category": entry.get("category") or "other_hazard",
        "created_at": now, "updated_at": now,
    }
    await db[S.C_CHAPTERS].insert_one(doc)
    return {"success": True, "chapter": S.serialize(doc)}


@router.put("/chapters/by-code", dependencies=[Depends(require_admin)])
async def update_chapter(code: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    if not await db[S.C_CHAPTERS].find_one({"code": code}):
        raise HTTPException(404, "Главу не знайдено")
    patch.pop("id", None)
    patch.pop("code", None)
    patch["updated_at"] = S.now_iso()
    await db[S.C_CHAPTERS].update_one({"code": code}, {"$set": patch})
    fresh = await db[S.C_CHAPTERS].find_one({"code": code}, {"_id": 0})
    return {"success": True, "chapter": fresh}


@router.delete("/chapters/by-code", dependencies=[Depends(require_admin)])
async def delete_chapter(code: str):
    db = get_db()
    # Заборонити, якщо є коди/підгрупи у цій главі
    n_codes = await db[S.C_CODES].count_documents({"chapter": code})
    n_grps = await db[S.C_GROUPS].count_documents({"chapter": code})
    if n_codes or n_grps:
        raise HTTPException(409, f"Главу неможливо видалити: містить {n_grps} підгруп(и) та {n_codes} кодів. Спочатку перенесіть або видаліть їх.")
    res = await db[S.C_CHAPTERS].delete_one({"code": code})
    if not res.deleted_count:
        raise HTTPException(404, "Главу не знайдено")
    return {"success": True}


# ── ADMIN: Підгрупи (level=2) ────────────────────────────────────────────────
@router.post("/groups", dependencies=[Depends(require_admin)])
async def create_group(entry: Dict[str, Any] = Body(...)):
    db = get_db()
    code = (entry.get("code") or "").strip()
    name = (entry.get("name") or "").strip()
    chapter = (entry.get("chapter") or "").strip()
    if not code or not name or not chapter:
        raise HTTPException(400, "code, name та chapter обовʼязкові")
    if not await db[S.C_CHAPTERS].find_one({"code": chapter}):
        raise HTTPException(400, "Глава-батько не існує")
    if await db[S.C_GROUPS].find_one({"code": code}):
        raise HTTPException(409, "Підгрупа вже існує")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("grp"), "code": code, "name": name, "level": 2,
        "chapter": chapter, "parent_code": chapter,
        "created_at": now, "updated_at": now,
    }
    await db[S.C_GROUPS].insert_one(doc)
    return {"success": True, "group": S.serialize(doc)}


@router.put("/groups/by-code", dependencies=[Depends(require_admin)])
async def update_group(code: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    if not await db[S.C_GROUPS].find_one({"code": code}):
        raise HTTPException(404, "Підгрупу не знайдено")
    patch.pop("id", None)
    patch.pop("code", None)
    patch["updated_at"] = S.now_iso()
    await db[S.C_GROUPS].update_one({"code": code}, {"$set": patch})
    fresh = await db[S.C_GROUPS].find_one({"code": code}, {"_id": 0})
    return {"success": True, "group": fresh}


@router.delete("/groups/by-code", dependencies=[Depends(require_admin)])
async def delete_group(code: str):
    db = get_db()
    n_codes = await db[S.C_CODES].count_documents({"group": code})
    if n_codes:
        raise HTTPException(409, f"Підгрупу неможливо видалити: містить {n_codes} кодів. Спочатку перенесіть або видаліть їх.")
    res = await db[S.C_GROUPS].delete_one({"code": code})
    if not res.deleted_count:
        raise HTTPException(404, "Підгрупу не знайдено")
    return {"success": True}


# ════════════════════════════════════════════════════════════════════════════
#  COMPANIES — Company360
# ════════════════════════════════════════════════════════════════════════════
@router.get("/companies", dependencies=[Depends(require_manager_or_admin)])
async def list_companies(
    q: Optional[str] = None,
    kind: Optional[str] = None,
    mine: bool = False,
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = get_db()
    query: Dict[str, Any] = {"deleted": {"$ne": True}}
    # kind: "client" (default real customers/leads converted) | "lead" (cold)
    if kind == "lead":
        query["kind"] = "lead"
    elif kind == "client":
        query["kind"] = {"$ne": "lead"}
    if mine and user.get("role") != "admin":
        query["assigned_manager_id"] = user.get("id")
    elif mine:
        query["assigned_manager_id"] = user.get("id")
    if q:
        rx = {"$regex": q, "$options": "i"}
        query["$or"] = [{"name": rx}, {"edrpou": rx}, {"email": rx}, {"phone": rx}]
    rows = await db[S.C_COMPANIES].find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    await _attach_managers(db, rows)
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/companies", dependencies=[Depends(require_manager_or_admin)])
async def create_company(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("co"),
        "name": name,
        "edrpou": (data.get("edrpou") or "").strip() or None,
        "email": (data.get("email") or "").strip() or None,
        "phone": (data.get("phone") or "").strip() or None,
        "address": data.get("address"),
        "contacts": data.get("contacts") or [],
        "tags": data.get("tags") or [],
        "status": data.get("status") or "active",
        "assigned_manager_id": data.get("assigned_manager_id") or user.get("id"),
        "notes": data.get("notes"),
        "created_at": now, "updated_at": now,
        "created_by": user.get("email") or user.get("id"),
    }
    await db[S.C_COMPANIES].insert_one(doc)
    return {"success": True, "company": S.serialize(doc)}


@router.get("/companies/{company_id}", dependencies=[Depends(require_manager_or_admin)])
async def company360(company_id: str):
    """Company360 aggregate (mini-ERP): company + all operational tabs + counters."""
    db = get_db()
    company = await db[S.C_COMPANIES].find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(404, "Компанію не знайдено")
    await _attach_managers(db, [company])
    objects = await db[S.C_OBJECTS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=500)
    requests = await db[S.C_REQUESTS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    contracts = await db[S.C_CONTRACTS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    acts = await db[S.C_ACTS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    pickups = await db[S.C_PICKUPS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    tasks = await db[S.C_TASKS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=100)
    comments = await db[S.C_COMMENTS].find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(length=100)
    timeline = await db[S.C_ACTIVITY].find({"company_id": company_id}, {"_id": 0}).sort("at", -1).to_list(length=100)
    stage_counts: Dict[str, int] = {}
    for r in requests:
        st = r.get("stage", "new")
        stage_counts[st] = stage_counts.get(st, 0) + 1
    return {
        "success": True,
        "company": company,
        # ── ERP tabs ──
        "objects": objects,
        "requests": requests,
        "contracts": contracts,
        "acts": acts,
        "pickups": pickups,
        "tasks": tasks,
        "comments": comments,
        "timeline": timeline,
        # invoices/payments/documents/calls reserved — wired when company<->CRM
        # customer linking lands (kept as keys so the frontend tabs are stable).
        "invoices": [],
        "payments": [],
        "documents": [],
        "calls": [],
        "stats": {
            "objects": len(objects),
            "requests": len(requests),
            "contracts": len(contracts),
            "acts": len(acts),
            "pickups": len(pickups),
            "tasks": len(tasks),
            "open_tasks": sum(1 for t in tasks if t.get("status") != "done"),
            "by_stage": stage_counts,
            "open_requests": sum(1 for r in requests if r.get("stage") not in ("act", "archived")),
            "active_contracts": sum(1 for c in contracts if c.get("status") in ("signed", "active")),
            "signed_acts": sum(1 for a in acts if a.get("status") in ("signed", "archived")),
        },
    }


@router.put("/companies/{company_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_company(company_id: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    if not await db[S.C_COMPANIES].find_one({"id": company_id}):
        raise HTTPException(404, "Компанію не знайдено")
    patch.pop("id", None)
    patch["updated_at"] = S.now_iso()
    await db[S.C_COMPANIES].update_one({"id": company_id}, {"$set": patch})
    fresh = await db[S.C_COMPANIES].find_one({"id": company_id}, {"_id": 0})
    return {"success": True, "company": fresh}


@router.delete("/companies/{company_id}", dependencies=[Depends(require_manager_or_admin)])
async def delete_company(company_id: str):
    db = get_db()
    await db[S.C_COMPANIES].update_one({"id": company_id}, {"$set": {"deleted": True, "updated_at": S.now_iso()}})
    return {"success": True}


# ════════════════════════════════════════════════════════════════════════════
#  OBJECTS — company sites / branches (hospital, factory, lab, ...)
# ════════════════════════════════════════════════════════════════════════════
@router.get("/objects", dependencies=[Depends(require_manager_or_admin)])
async def list_objects(company_id: Optional[str] = None, limit: int = Query(200, ge=1, le=1000)):
    db = get_db()
    query: Dict[str, Any] = {"deleted": {"$ne": True}}
    if company_id:
        query["company_id"] = company_id
    rows = await db[S.C_OBJECTS].find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/objects", dependencies=[Depends(require_manager_or_admin)])
async def create_object(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    company_id = (data.get("company_id") or "").strip()
    name = (data.get("name") or "").strip()
    if not company_id or not name:
        raise HTTPException(400, "company_id and name are required")
    if not await db[S.C_COMPANIES].find_one({"id": company_id}):
        raise HTTPException(404, "Компанію не знайдено")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("obj"),
        "company_id": company_id,
        "parent_id": data.get("parent_id"),  # for branch hierarchy
        "name": name,
        "object_type": data.get("object_type") or "site",  # hospital/factory/lab/warehouse/gas_station/agrofirm
        "address": data.get("address"),
        "geo": data.get("geo"),
        "contacts": data.get("contacts") or [],
        "responsible_staff_id": data.get("responsible_staff_id"),
        "responsible_name": data.get("responsible_name"),
        "responsible_phone": data.get("responsible_phone"),
        "pickup_schedule": data.get("pickup_schedule"),
        "notes": data.get("notes"),
        "created_at": now, "updated_at": now,
        "created_by": user.get("email") or user.get("id"),
    }
    await db[S.C_OBJECTS].insert_one(doc)
    return {"success": True, "object": S.serialize(doc)}


@router.put("/objects/{object_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_object(object_id: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    if not await db[S.C_OBJECTS].find_one({"id": object_id}):
        raise HTTPException(404, "Об'єкт не знайдено")
    patch.pop("id", None)
    patch["updated_at"] = S.now_iso()
    await db[S.C_OBJECTS].update_one({"id": object_id}, {"$set": patch})
    fresh = await db[S.C_OBJECTS].find_one({"id": object_id}, {"_id": 0})
    return {"success": True, "object": fresh}


@router.delete("/objects/{object_id}", dependencies=[Depends(require_manager_or_admin)])
async def delete_object(object_id: str):
    db = get_db()
    await db[S.C_OBJECTS].update_one({"id": object_id}, {"$set": {"deleted": True, "updated_at": S.now_iso()}})
    return {"success": True}


# ════════════════════════════════════════════════════════════════════════════
#  LICENSE MATRIX
# ════════════════════════════════════════════════════════════════════════════
@router.get("/licenses", dependencies=[Depends(require_manager_or_admin)])
async def list_licenses(limit: int = Query(2000, ge=1, le=5000)):
    db = get_db()
    rows = await db[S.C_LICENSES].find({}, {"_id": 0}).sort("waste_code", 1).limit(int(limit)).to_list(length=int(limit))
    # Збагатити назвою/категорією коду + позначкою прострочення.
    now = S.datetime.now(S.timezone.utc)
    for r in rows:
        wc = await db[S.C_CODES].find_one({"code": r.get("waste_code")}, {"_id": 0, "name": 1, "category": 1, "category_name": 1, "hazardous": 1})
        if wc:
            r["code_name"] = wc.get("name")
            r["category"] = wc.get("category")
            r["category_name"] = wc.get("category_name")
            r["hazardous"] = wc.get("hazardous")
            r["in_catalog"] = True
        else:
            r["in_catalog"] = False
        # expiry stamp
        expired = False
        expiring_soon = False
        vu = r.get("valid_until")
        if vu:
            try:
                dt = S.datetime.fromisoformat(str(vu).replace("Z", "+00:00"))
                expired = dt < now
                expiring_soon = (not expired) and (dt - now).days <= 30
            except Exception:
                pass
        r["expired"] = expired
        r["expiring_soon"] = expiring_soon
        r["active"] = bool(r.get("allowed")) and not expired
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/licenses", dependencies=[Depends(require_admin)])
async def upsert_license(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_admin)):
    db = get_db()
    code = (data.get("waste_code") or "").strip()
    if not code:
        raise HTTPException(400, "waste_code is required")
    # Код має існувати у довіднику (майстер-переліку).
    if not await db[S.C_CODES].find_one({"code": code}, {"_id": 1}):
        raise HTTPException(404, f"Код «{code}» відсутній у довіднику")
    now = S.now_iso()
    doc = {
        "waste_code": code,
        "allowed": bool(data.get("allowed", True)),
        "license_id": data.get("license_id"),
        "license_number": data.get("license_number"),
        "valid_from": data.get("valid_from"),
        "valid_until": data.get("valid_until"),
        "notes": data.get("notes"),
        "updated_at": now,
        "updated_by": user.get("email") or user.get("id"),
    }
    existing = await db[S.C_LICENSES].find_one({"waste_code": code}, {"_id": 0, "id": 1, "created_at": 1, "source": 1})
    if existing:
        doc["id"] = existing.get("id")
        doc["created_at"] = existing.get("created_at")
        doc["source"] = existing.get("source")
        await db[S.C_LICENSES].update_one({"waste_code": code}, {"$set": doc})
    else:
        doc["id"] = S.gen_id("lic")
        doc["created_at"] = now
        doc["source"] = "manual"
        await db[S.C_LICENSES].insert_one(doc)
    # Синхронізувати accepted для цього коду.
    accepted = await S.sync_code_accepted(db, code)
    await S.log_activity(db, company_id=None, entity_type="license", entity_id=code,
                         event="updated", message=f"Ліцензія для {code}: {'приймаємо' if accepted else 'не приймаємо'}",
                         by=user.get("email"))
    fresh = await db[S.C_LICENSES].find_one({"waste_code": code}, {"_id": 0})
    return {"success": True, "license": fresh, "accepted": accepted}


@router.delete("/licenses/{license_id}", dependencies=[Depends(require_admin)])
async def delete_license(license_id: str):
    db = get_db()
    lic = await db[S.C_LICENSES].find_one({"id": license_id}, {"_id": 0, "waste_code": 1})
    res = await db[S.C_LICENSES].delete_one({"id": license_id})
    if not res.deleted_count:
        raise HTTPException(404, "Запис ліцензії не знайдено")
    # Після видалення запису код стає «не приймаємо».
    if lic and lic.get("waste_code"):
        await S.sync_code_accepted(db, lic["waste_code"])
    return {"success": True}


@router.post("/licenses/seed", dependencies=[Depends(require_admin)])
async def seed_licenses(force: bool = False):
    """Засіяти/перезасіяти реальний ліцензований перелік (admin only)."""
    res = await S.seed_license_matrix(get_db(), force=force)
    return {"success": True, **res}


@router.post("/licenses/recompute", dependencies=[Depends(require_admin)])
async def recompute_accepted():
    """Примусово перерахувати прапор `accepted` для всіх кодів."""
    res = await S.recompute_accepted_all(get_db())
    return {"success": True, **res}


# ════════════════════════════════════════════════════════════════════════════
#  WASTE REQUESTS — lifecycle
# ════════════════════════════════════════════════════════════════════════════
def _validate_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "items must be a non-empty list")
    out = []
    for it in items:
        code = (it.get("waste_code") or it.get("code") or "").strip()
        if not code:
            raise HTTPException(400, "each item needs a waste_code")
        out.append({
            "waste_code": code,
            "name": it.get("name"),
            "qty": it.get("qty"),
            "unit": it.get("unit") or "kg",
            "packaging": it.get("packaging"),
            "notes": it.get("notes"),
        })
    return out


async def _build_request_doc(db, data: Dict[str, Any], *, source: str, created_by: Optional[str]) -> Dict[str, Any]:
    now = S.now_iso()
    items = _validate_items(data.get("items"))
    # Enrich items with license acceptance + names.
    for it in items:
        chk = await S.license_check(db, it["waste_code"])
        it["hazardous"] = chk.get("hazardous")
        it["accepted"] = chk.get("accepted")
        if not it.get("name"):
            it["name"] = chk.get("name")
    # ── B2B linkage: inherit the responsible manager from the company so the
    #    request lands directly in that manager's queue. ──────────────────
    assigned_manager_id = data.get("assigned_manager_id")
    company_id = data.get("company_id")
    if not assigned_manager_id and company_id:
        try:
            co = await db[S.C_COMPANIES].find_one({"id": company_id}, {"_id": 0, "assigned_manager_id": 1})
            if co:
                assigned_manager_id = co.get("assigned_manager_id")
        except Exception:
            pass
    return {
        "id": S.gen_id("wr"),
        "company_id": company_id,
        "object_id": data.get("object_id"),
        "items": items,
        "stage": "new",
        "assigned_manager_id": assigned_manager_id,
        "source": source,
        "contact": {
            "name": data.get("contact_name") or (data.get("contact") or {}).get("name"),
            "phone": data.get("contact_phone") or (data.get("contact") or {}).get("phone"),
            "email": data.get("contact_email") or (data.get("contact") or {}).get("email"),
            "company_name": data.get("company_name"),
        },
        "comment": data.get("comment"),
        "created_at": now, "updated_at": now,
        "created_by": created_by,
        "stage_history": [{"stage": "new", "at": now, "by": created_by or source}],
    }


@router.post("/requests/public")
async def create_request_public(data: Dict[str, Any] = Body(...)):
    """Public request from the calculator / site (no auth). Generates a lead.

    Guardrail: публічна заявка приймається лише для ліцензованих кодів
    («ми приймаємо»). Не-ліцензовані коди відхиляються.
    """
    db = get_db()
    items = _validate_items(data.get("items"))
    not_accepted: List[str] = []
    for it in items:
        chk = await S.license_check(db, it["waste_code"])
        if not chk.get("accepted"):
            not_accepted.append(it["waste_code"])
    if not_accepted:
        raise HTTPException(
            422,
            f"Ці коди поза нашою ліцензією (не приймаємо): {', '.join(not_accepted)}",
        )
    doc = await _build_request_doc(db, data, source="public", created_by=None)
    await db[S.C_REQUESTS].insert_one(doc)
    await S.log_activity(db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
                         entity_type="request", entity_id=doc["id"], event="created",
                         message="Нова заявка з сайту/калькулятора", by="public")
    return {"success": True, "request_id": doc["id"], "stage": doc["stage"]}


@router.get("/requests", dependencies=[Depends(require_manager_or_admin)])
async def list_requests(
    stage: Optional[str] = None,
    company_id: Optional[str] = None,
    mine: bool = False,
    limit: int = Query(200, ge=1, le=1000),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = get_db()
    query: Dict[str, Any] = {}
    if stage:
        query["stage"] = stage
    if company_id:
        query["company_id"] = company_id
    if mine:
        # requests where THIS manager is responsible — directly or via the company
        my_company_ids = [
            c.get("id")
            for c in await db[S.C_COMPANIES].find(
                {"assigned_manager_id": user.get("id")}, {"_id": 0, "id": 1}
            ).to_list(length=1000)
        ]
        query["$or"] = [
            {"assigned_manager_id": user.get("id")},
            {"company_id": {"$in": my_company_ids}},
        ]
    rows = await db[S.C_REQUESTS].find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    await _attach_company_names(db, rows)
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/requests", dependencies=[Depends(require_manager_or_admin)])
async def create_request(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    doc = await _build_request_doc(db, data, source="manager", created_by=user.get("email") or user.get("id"))
    await db[S.C_REQUESTS].insert_one(doc)
    await S.log_activity(db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
                         entity_type="request", entity_id=doc["id"], event="created",
                         message="Заявку створено менеджером", by=user.get("email") or user.get("id"))
    return {"success": True, "request": S.serialize(doc)}


@router.get("/requests/{request_id}", dependencies=[Depends(require_manager_or_admin)])
async def get_request(request_id: str):
    db = get_db()
    doc = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Заявку не знайдено")
    company = await db[S.C_COMPANIES].find_one({"id": doc.get("company_id")}, {"_id": 0}) if doc.get("company_id") else None
    obj = await db[S.C_OBJECTS].find_one({"id": doc.get("object_id")}, {"_id": 0}) if doc.get("object_id") else None
    return {"success": True, "request": doc, "company": company, "object": obj}


@router.post("/requests/{request_id}/stage", dependencies=[Depends(require_manager_or_admin)])
async def transition_stage(request_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    stage = (data.get("stage") or "").strip()
    if stage not in S.REQUEST_STAGES:
        raise HTTPException(400, f"stage must be one of {S.REQUEST_STAGES}")
    doc = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Заявку не знайдено")
    now = S.now_iso()
    hist = {"stage": stage, "at": now, "by": user.get("email") or user.get("id"), "note": data.get("note")}
    await db[S.C_REQUESTS].update_one(
        {"id": request_id},
        {"$set": {"stage": stage, "updated_at": now}, "$push": {"stage_history": hist}},
    )
    await S.log_activity(db, company_id=doc.get("company_id"), object_id=doc.get("object_id"),
                         entity_type="request", entity_id=request_id, event="stage_changed",
                         message=f"Заявка: етап → {S.STAGE_LABELS_UK.get(stage, stage)}",
                         by=user.get("email") or user.get("id"))
    fresh = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    return {"success": True, "request": fresh}


@router.put("/requests/{request_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_request(request_id: str, patch: Dict[str, Any] = Body(...)):
    db = get_db()
    if not await db[S.C_REQUESTS].find_one({"id": request_id}):
        raise HTTPException(404, "Заявку не знайдено")
    patch.pop("id", None)
    patch.pop("stage_history", None)
    if "items" in patch:
        patch["items"] = _validate_items(patch["items"])
    patch["updated_at"] = S.now_iso()
    await db[S.C_REQUESTS].update_one({"id": request_id}, {"$set": patch})
    fresh = await db[S.C_REQUESTS].find_one({"id": request_id}, {"_id": 0})
    return {"success": True, "request": fresh}


# ════════════════════════════════════════════════════════════════════════════
#  PRICING ENGINE v2 — Admin CRUD over waste_price_rules (Wave 4A)
# ════════════════════════════════════════════════════════════════════════════
@router.get("/price_rules", dependencies=[Depends(require_manager_or_admin)])
async def list_price_rules(
    waste_code: Optional[str] = None,
    region: Optional[str] = None,
    active: Optional[bool] = None,
    limit: int = Query(500, ge=1, le=2000),
):
    """List all price rules, optionally filtered by code/region/active flag."""
    db = get_db()
    query: Dict[str, Any] = {}
    if waste_code:
        query["wasteCode"] = waste_code
    if region:
        query["region"] = region.strip().lower()
    if active is not None:
        query["active"] = active
    rows = await db[S.C_PRICE_RULES].find(query, {"_id": 0}).sort([("wasteCode", 1), ("minWeight", 1)]).limit(int(limit)).to_list(length=int(limit))
    return {"success": True, "items": rows, "count": len(rows)}


@router.post("/price_rules", dependencies=[Depends(require_admin)])
async def create_price_rule(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_admin)):
    db = get_db()
    try:
        doc = S.normalize_price_rule(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Validate waste code exists (allow "*" as wildcard for global default rules).
    if doc["wasteCode"] != "*":
        if not await db[S.C_CODES].find_one({"code": doc["wasteCode"]}, {"_id": 1}):
            raise HTTPException(404, f"Код «{doc['wasteCode']}» відсутній у довіднику")
    now = S.now_iso()
    doc["id"] = S.gen_id("pr")
    doc["created_at"] = now
    doc["updated_at"] = now
    doc["created_by"] = user.get("email") or user.get("id")
    await db[S.C_PRICE_RULES].insert_one(doc)
    return {"success": True, "rule": S.serialize(doc)}


@router.put("/price_rules/{rule_id}", dependencies=[Depends(require_admin)])
async def update_price_rule(rule_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_admin)):
    db = get_db()
    existing = await db[S.C_PRICE_RULES].find_one({"id": rule_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Правило ціноутворення не знайдено")
    merged = {**existing, **data}
    try:
        doc = S.normalize_price_rule(merged)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if doc["wasteCode"] != "*":
        if not await db[S.C_CODES].find_one({"code": doc["wasteCode"]}, {"_id": 1}):
            raise HTTPException(404, f"Код «{doc['wasteCode']}» відсутній у довіднику")
    doc["id"] = rule_id
    doc["created_at"] = existing.get("created_at")
    doc["created_by"] = existing.get("created_by")
    doc["updated_at"] = S.now_iso()
    doc["updated_by"] = user.get("email") or user.get("id")
    await db[S.C_PRICE_RULES].update_one({"id": rule_id}, {"$set": doc})
    fresh = await db[S.C_PRICE_RULES].find_one({"id": rule_id}, {"_id": 0})
    return {"success": True, "rule": fresh}


@router.delete("/price_rules/{rule_id}", dependencies=[Depends(require_admin)])
async def delete_price_rule(rule_id: str):
    db = get_db()
    res = await db[S.C_PRICE_RULES].delete_one({"id": rule_id})
    if not res.deleted_count:
        raise HTTPException(404, "Правило ціноутворення не знайдено")
    return {"success": True}


@router.post("/price_rules/seed", dependencies=[Depends(require_admin)])
async def seed_price_rules_demo():
    """Seed a few demonstrative tiered rules (idempotent — skips if any exist)."""
    res = await S.seed_price_rules(get_db())
    return {"success": True, **res}


# ════════════════════════════════════════════════════════════════════════════
#  STATS — dashboard overview
# ════════════════════════════════════════════════════════════════════════════
@router.get("/stats", dependencies=[Depends(require_manager_or_admin)])
async def waste_stats():
    db = get_db()
    by_stage: Dict[str, int] = {}
    for st in S.REQUEST_STAGES:
        by_stage[st] = await db[S.C_REQUESTS].count_documents({"stage": st})
    now = S.datetime.now(S.timezone.utc)
    now_iso = now.isoformat()
    licenses_total = await db[S.C_LICENSES].count_documents({})
    licenses_expired = await db[S.C_LICENSES].count_documents({"valid_until": {"$lt": now_iso}})
    return {
        "success": True,
        "codes": await db[S.C_CODES].count_documents({}),
        "hazardous_codes": await db[S.C_CODES].count_documents({"hazardous": True}),
        "accepted_codes": await db[S.C_CODES].count_documents({"accepted": True}),
        "companies": await db[S.C_COMPANIES].count_documents({"deleted": {"$ne": True}}),
        "objects": await db[S.C_OBJECTS].count_documents({"deleted": {"$ne": True}}),
        "licenses": licenses_total,
        "licenses_expired": licenses_expired,
        "requests": await db[S.C_REQUESTS].count_documents({}),
        "requests_by_stage": by_stage,
        "open_requests": await db[S.C_REQUESTS].count_documents({"stage": {"$nin": ["act", "archived"]}}),
        # ── Wave 3 — Operations Center ──
        "contracts": await db[S.C_CONTRACTS].count_documents({}),
        "active_contracts": await db[S.C_CONTRACTS].count_documents({"status": {"$in": ["signed", "active"]}}),
        "pickups": await db[S.C_PICKUPS].count_documents({}),
        "pending_pickups": await db[S.C_PICKUPS].count_documents({"status": {"$in": ["planning", "route", "driver_assigned"]}}),
        "acts": await db[S.C_ACTS].count_documents({}),
        "signed_acts": await db[S.C_ACTS].count_documents({"status": {"$in": ["signed", "archived"]}}),
        "price_rules": await db[S.C_PRICE_RULES].count_documents({}),
        "active_price_rules": await db[S.C_PRICE_RULES].count_documents({"active": {"$ne": False}}),
        "stages": S.REQUEST_STAGES,
        "stage_labels": S.STAGE_LABELS_UK,
        "contract_stages": S.CONTRACT_STAGES,
        "contract_labels": S.CONTRACT_LABELS_UK,
        "pickup_stages": S.PICKUP_STAGES,
        "pickup_labels": S.PICKUP_LABELS_UK,
        "act_stages": S.ACT_STAGES,
        "act_labels": S.ACT_LABELS_UK,
    }


# ════════════════════════════════════════════════════════════════════════════
#  Inquiries inbox (staff) — звернення / запити на дзвінок із публічного сайту.
#  Records are created (unauthenticated) by POST /api/public/inquiry
#  (app/client/router.py) into the `public_inquiries` collection.
# ════════════════════════════════════════════════════════════════════════════
C_INQUIRIES = "public_inquiries"
INQUIRY_STATUSES = ["new", "in_progress", "contacted", "closed"]
INQUIRY_STATUS_LABELS = {
    "new": "Нове",
    "in_progress": "В роботі",
    "contacted": "Зв'язалися",
    "closed": "Закрите",
}
INQUIRY_TYPE_LABELS = {
    "callback": "Зворотний дзвінок",
    "inquiry": "Звернення",
    "request": "Заявка з сайту",
}


@router.get("/inquiries", dependencies=[Depends(require_manager_or_admin)])
async def list_inquiries(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """List public-site inquiries (callbacks / questions / site requests)."""
    db = get_db()
    flt: Dict[str, Any] = {}
    if status and status in INQUIRY_STATUSES:
        flt["status"] = status
    if q:
        rx = {"$regex": q.strip(), "$options": "i"}
        flt["$or"] = [{"name": rx}, {"phone": rx}, {"email": rx}, {"company_name": rx}, {"message": rx}]
    rows = await db[C_INQUIRIES].find(flt, {"_id": 0}).sort("created_at", -1).limit(500).to_list(length=500)
    # counters (independent of the current filter)
    counts = {s: await db[C_INQUIRIES].count_documents({"status": s}) for s in INQUIRY_STATUSES}
    counts["total"] = await db[C_INQUIRIES].count_documents({})
    items = []
    for r in rows:
        r = S.serialize(r)
        r["status_label"] = INQUIRY_STATUS_LABELS.get(r.get("status"), r.get("status"))
        r["type_label"] = INQUIRY_TYPE_LABELS.get(r.get("type"), r.get("type"))
        items.append(r)
    return {
        "success": True,
        "items": items,
        "count": len(items),
        "counts": counts,
        "statuses": INQUIRY_STATUSES,
        "status_labels": INQUIRY_STATUS_LABELS,
    }


@router.patch("/inquiries/{inquiry_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_inquiry(inquiry_id: str, data: Dict[str, Any] = Body(...)):
    """Update an inquiry: change status and/or attach an internal note."""
    db = get_db()
    patch: Dict[str, Any] = {"updated_at": S.now_iso()}
    new_status = (data or {}).get("status")
    if new_status:
        if new_status not in INQUIRY_STATUSES:
            raise HTTPException(422, f"Невідомий статус: {new_status}")
        patch["status"] = new_status
    if "note" in (data or {}):
        patch["note"] = str(data.get("note") or "")[:2000]
    res = await db[C_INQUIRIES].update_one({"id": inquiry_id}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(404, "Звернення не знайдено")
    fresh = await db[C_INQUIRIES].find_one({"id": inquiry_id}, {"_id": 0})
    fresh = S.serialize(fresh)
    fresh["status_label"] = INQUIRY_STATUS_LABELS.get(fresh.get("status"), fresh.get("status"))
    fresh["type_label"] = INQUIRY_TYPE_LABELS.get(fresh.get("type"), fresh.get("type"))
    return {"success": True, "inquiry": fresh}


# ════════════════════════════════════════════════════════════════════════════
#  TEAM / LINKAGE — managers, company ownership, cold leads
#  (admin acts as the team-lead: lists managers, assigns & reassigns companies)
# ════════════════════════════════════════════════════════════════════════════
C_STAFF = "staff"
_MANAGER_ROLES = {"admin", "manager", "team_lead"}


def _manager_public(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": s.get("id"),
        "name": s.get("name") or (s.get("email") or "").split("@")[0],
        "email": s.get("email", ""),
        "phone": s.get("phone", ""),
        "role": s.get("role", "manager"),
    }


async def _attach_managers(db, rows: List[Dict[str, Any]]) -> None:
    """Resolve assigned_manager_id → {manager:{id,name,email,phone}} on each row."""
    ids = list({r.get("assigned_manager_id") for r in rows if r.get("assigned_manager_id")})
    if not ids:
        for r in rows:
            r["manager"] = None
        return
    staff = await db[C_STAFF].find({"id": {"$in": ids}}, {"_id": 0}).to_list(length=len(ids))
    by_id = {s.get("id"): _manager_public(s) for s in staff}
    for r in rows:
        r["manager"] = by_id.get(r.get("assigned_manager_id"))


async def _attach_company_names(db, rows: List[Dict[str, Any]]) -> None:
    """Resolve company_id → company_name on request rows (for queue lists)."""
    ids = list({r.get("company_id") for r in rows if r.get("company_id")})
    by_id: Dict[str, str] = {}
    if ids:
        cos = await db[S.C_COMPANIES].find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(length=len(ids))
        by_id = {c.get("id"): c.get("name") for c in cos}
    for r in rows:
        if not (r.get("contact") or {}).get("company_name"):
            r.setdefault("contact", {})
            r["contact"]["company_name"] = by_id.get(r.get("company_id"))
        r["company_name"] = (r.get("contact") or {}).get("company_name") or by_id.get(r.get("company_id"))


@router.get("/managers", dependencies=[Depends(require_manager_or_admin)])
async def list_managers():
    """All staff who can own companies/leads (admin + managers). Admin = team-lead."""
    db = get_db()
    rows = await db[C_STAFF].find(
        {"role": {"$in": list(_MANAGER_ROLES)}, "disabled": {"$ne": True}}, {"_id": 0}
    ).sort("name", 1).to_list(length=500)
    return {"success": True, "items": [_manager_public(s) for s in rows], "count": len(rows)}


@router.patch("/companies/{company_id}/manager", dependencies=[Depends(require_admin)])
async def assign_company_manager(
    company_id: str,
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    """(Re)assign a company to a manager. Admin-only (team-lead role)."""
    db = get_db()
    company = await db[S.C_COMPANIES].find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(404, "Компанію не знайдено")
    manager_id = (data.get("manager_id") or data.get("assigned_manager_id") or "").strip() or None
    manager = None
    if manager_id:
        manager = await db[C_STAFF].find_one({"id": manager_id}, {"_id": 0})
        if not manager:
            raise HTTPException(404, "Менеджера не знайдено")
    prev = company.get("assigned_manager_id")
    await db[S.C_COMPANIES].update_one(
        {"id": company_id},
        {"$set": {"assigned_manager_id": manager_id, "updated_at": S.now_iso()}},
    )
    # Cascade: keep open requests of this company in sync with the new owner.
    await db[S.C_REQUESTS].update_many(
        {"company_id": company_id, "stage": {"$nin": ["act", "archived"]}},
        {"$set": {"assigned_manager_id": manager_id}},
    )
    # Keep linked customers' managerId in sync (so client sees the right manager).
    try:
        await db["customers"].update_many(
            {"company_id": company_id}, {"$set": {"managerId": manager_id}}
        )
    except Exception:
        pass
    mgr_name = (manager or {}).get("name") or (manager or {}).get("email") or "—"
    await S.log_activity(
        db, company_id=company_id, entity_type="company", entity_id=company_id,
        event="manager_assigned",
        message=f"Компанію передано менеджеру: {mgr_name}"
                + (f" (раніше: {prev})" if prev and prev != manager_id else ""),
        by=user.get("email") or user.get("id"),
    )
    fresh = await db[S.C_COMPANIES].find_one({"id": company_id}, {"_id": 0})
    await _attach_managers(db, [fresh])
    return {"success": True, "company": fresh}


# ── Cold leads — companies with kind="lead" (no customer account yet) ──────
@router.get("/leads", dependencies=[Depends(require_manager_or_admin)])
async def list_leads(
    q: Optional[str] = None,
    mine: bool = False,
    limit: int = Query(200, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    db = get_db()
    query: Dict[str, Any] = {"kind": "lead", "deleted": {"$ne": True}}
    if mine:
        query["assigned_manager_id"] = user.get("id")
    if q:
        rx = {"$regex": q, "$options": "i"}
        query["$or"] = [{"name": rx}, {"contact_name": rx}, {"phone": rx}, {"email": rx}]
    rows = await db[S.C_COMPANIES].find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    await _attach_managers(db, rows)
    return {"success": True, "items": rows, "count": len(rows), "statuses": LEAD_STATUSES, "status_labels": LEAD_STATUS_LABELS}


LEAD_STATUSES = ["new", "contacted", "qualified", "won", "lost"]
LEAD_STATUS_LABELS = {
    "new": "Новий", "contacted": "Контакт", "qualified": "Кваліфікований",
    "won": "Виграно", "lost": "Втрачено",
}


@router.post("/leads", dependencies=[Depends(require_manager_or_admin)])
async def create_lead(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    """Manager creates a COLD lead — a prospective company without a customer
    account (e.g. someone who called or walked in). Stored as a company with
    kind='lead'; auto-converts/links when the customer later registers with a
    matching company name (see _link_customer_company)."""
    db = get_db()
    name = (data.get("name") or data.get("company_name") or "").strip()
    contact_name = (data.get("contact_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not name and not contact_name and not phone:
        raise HTTPException(400, "Вкажіть назву компанії, контактну особу або телефон")
    now = S.now_iso()
    doc = {
        "id": S.gen_id("co"),
        "kind": "lead",
        "lead_status": (data.get("lead_status") if data.get("lead_status") in LEAD_STATUSES else "new"),
        "name": name or contact_name or phone,
        "contact_name": contact_name or None,
        "edrpou": (data.get("edrpou") or "").strip() or None,
        "email": (data.get("email") or "").strip() or None,
        "phone": phone or None,
        "address": data.get("address"),
        "source": (data.get("source") or "manager_cold").strip(),
        "status": "active",
        "assigned_manager_id": data.get("assigned_manager_id") or user.get("id"),
        "notes": data.get("notes"),
        "created_at": now, "updated_at": now,
        "created_by": user.get("email") or user.get("id"),
    }
    await db[S.C_COMPANIES].insert_one(doc)
    await S.log_activity(
        db, company_id=doc["id"], entity_type="company", entity_id=doc["id"],
        event="lead_created", message=f"Створено холодний лід: {doc['name']}",
        by=user.get("email") or user.get("id"),
    )
    fresh = await db[S.C_COMPANIES].find_one({"id": doc["id"]}, {"_id": 0})
    await _attach_managers(db, [fresh])
    return {"success": True, "lead": fresh}


@router.patch("/leads/{lead_id}", dependencies=[Depends(require_manager_or_admin)])
async def update_lead(lead_id: str, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    patch: Dict[str, Any] = {"updated_at": S.now_iso()}
    for f in ("name", "contact_name", "phone", "email", "edrpou", "address", "notes", "assigned_manager_id"):
        if f in (data or {}):
            patch[f] = data.get(f)
    if "lead_status" in (data or {}):
        st = data.get("lead_status")
        if st not in LEAD_STATUSES:
            raise HTTPException(422, f"Невідомий статус: {st}")
        patch["lead_status"] = st
    res = await db[S.C_COMPANIES].update_one({"id": lead_id, "kind": "lead"}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(404, "Лід не знайдено")
    fresh = await db[S.C_COMPANIES].find_one({"id": lead_id}, {"_id": 0})
    await _attach_managers(db, [fresh])
    return {"success": True, "lead": fresh}


@router.post("/leads/{lead_id}/convert", dependencies=[Depends(require_manager_or_admin)])
async def convert_lead(lead_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    """Promote a cold lead into a regular client company (kind='client')."""
    db = get_db()
    lead = await db[S.C_COMPANIES].find_one({"id": lead_id, "kind": "lead"}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Лід не знайдено")
    await db[S.C_COMPANIES].update_one(
        {"id": lead_id},
        {"$set": {"kind": "client", "lead_status": "won", "updated_at": S.now_iso()}},
    )
    await S.log_activity(
        db, company_id=lead_id, entity_type="company", entity_id=lead_id,
        event="lead_converted", message="Лід конвертовано в компанію-клієнта",
        by=user.get("email") or user.get("id"),
    )
    fresh = await db[S.C_COMPANIES].find_one({"id": lead_id}, {"_id": 0})
    await _attach_managers(db, [fresh])
    return {"success": True, "company": fresh}


@router.get("/notifications", dependencies=[Depends(require_manager_or_admin)])
async def list_notifications(
    unread: bool = False,
    limit: int = Query(50, ge=1, le=200),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Notification feed for the current staffer (their own + admin-wide)."""
    db = get_db()
    uid = user.get("id")
    aud = ["staff", "admin", uid] if user.get("role") == "admin" else ["staff", uid]
    query: Dict[str, Any] = {"audiences": {"$in": aud}}
    if unread:
        query["read_by"] = {"$ne": uid}
    rows = await db["waste_notifications"].find(query, {"_id": 0}).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    unread_count = await db["waste_notifications"].count_documents(
        {"audiences": {"$in": aud}, "read_by": {"$ne": uid}}
    )
    for r in rows:
        r["read"] = uid in (r.get("read_by") or [])
    return {"success": True, "items": rows, "count": len(rows), "unread": unread_count}


@router.post("/notifications/{notification_id}/read", dependencies=[Depends(require_manager_or_admin)])
async def mark_notification_read(notification_id: str, user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    await db["waste_notifications"].update_one(
        {"id": notification_id}, {"$addToSet": {"read_by": user.get("id")}}
    )
    return {"success": True}


@router.post("/notifications/read-all", dependencies=[Depends(require_manager_or_admin)])
async def mark_all_notifications_read(user: Dict[str, Any] = Depends(require_manager_or_admin)):
    db = get_db()
    uid = user.get("id")
    aud = ["staff", "admin", uid] if user.get("role") == "admin" else ["staff", uid]
    await db["waste_notifications"].update_many(
        {"audiences": {"$in": aud}}, {"$addToSet": {"read_by": uid}}
    )
    return {"success": True}


# ════════════════════════════════════════════════════════════════════════════
#  MESSAGE CENTER — directed messaging (ECO)
#  Ланцюг ролей: Admin → Manager + Client ;  Manager → Client
#  Admin може писати менеджерам і клієнтам. Менеджер — лише клієнтам.
#  Staff-повідомлення йдуть у `waste_notifications` (бачить bell + інбокс),
#  клієнтські — у `notifications` (видно в кабінеті клієнта).
# ════════════════════════════════════════════════════════════════════════════
import uuid as _uuid_mc
from datetime import datetime as _dt_mc, timezone as _tz_mc

_ADMIN_ROLES_MC = {"admin", "owner", "master_admin"}


def _is_admin_role(user: Dict[str, Any]) -> bool:
    return (user.get("role") or "").lower() in _ADMIN_ROLES_MC


@router.get("/messages/recipients", dependencies=[Depends(require_manager_or_admin)])
async def message_recipients(user: Dict[str, Any] = Depends(require_manager_or_admin)):
    """Дозволені одержувачі для поточної ролі.

    Admin → {managers, clients};  Manager → {clients}.
    """
    db = get_db()
    is_admin = _is_admin_role(user)
    managers: List[Dict[str, Any]] = []
    if is_admin:
        rows = await db.staff.find(
            {"role": {"$in": ["manager"]}, "active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "email": 1},
        ).sort("name", 1).to_list(length=500)
        managers = [
            {"id": r.get("id"), "name": r.get("name") or r.get("email"), "email": r.get("email")}
            for r in rows if r.get("id")
        ]
    crows = await db.customers.find(
        {}, {"_id": 0, "id": 1, "name": 1, "email": 1, "companyName": 1, "company_name": 1},
    ).sort("name", 1).to_list(length=1000)
    clients = [
        {
            "id": r.get("id"),
            "name": r.get("name") or r.get("companyName") or r.get("company_name") or r.get("email") or "—",
            "email": r.get("email"),
            "company": r.get("companyName") or r.get("company_name"),
        }
        for r in crows if r.get("id")
    ]
    return {
        "success": True,
        "can_message_managers": is_admin,
        "can_message_clients": True,
        "managers": managers,
        "clients": clients,
    }


@router.post("/messages/send", dependencies=[Depends(require_manager_or_admin)])
async def message_send(
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Надіслати повідомлення.

    payload: {
      audience: "managers" | "clients",
      scope: "all" | "selected",
      recipient_ids: [ ... ],            # коли scope == "selected"
      title: str, body: str,
      priority: "low" | "normal" | "high"
    }
    """
    db = get_db()
    is_admin = _is_admin_role(user)
    audience = (payload.get("audience") or "").strip().lower()
    scope = (payload.get("scope") or "selected").strip().lower()
    recipient_ids = payload.get("recipient_ids") or []
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    priority = (payload.get("priority") or "normal").strip().lower()
    if priority not in ("low", "normal", "high"):
        priority = "normal"

    if not title or not body:
        raise HTTPException(400, "Вкажіть тему та текст повідомлення")
    if audience not in ("managers", "clients"):
        raise HTTPException(400, "audience має бути 'managers' або 'clients'")
    if audience == "managers" and not is_admin:
        raise HTTPException(403, "Менеджер може писати лише клієнтам")

    from_id = user.get("id")
    from_name = user.get("name") or user.get("email") or "Система"
    from_role = (user.get("role") or "").lower()
    now = _dt_mc.now(_tz_mc.utc)
    now_iso = now.isoformat()

    target_managers: List[Dict[str, Any]] = []
    target_clients: List[Dict[str, Any]] = []

    if audience == "managers":
        q: Dict[str, Any] = {"role": {"$in": ["manager"]}, "active": {"$ne": False}}
        if scope == "selected":
            if not recipient_ids:
                raise HTTPException(400, "Оберіть одержувачів")
            q["id"] = {"$in": list(recipient_ids)}
        rows = await db.staff.find(q, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(length=500)
        target_managers = [r for r in rows if r.get("id")]
        if not target_managers:
            raise HTTPException(404, "Менеджерів не знайдено")
        # one waste_notifications row visible to the selected managers' uids
        notif = {
            "id": f"msg_{_uuid_mc.uuid4().hex[:12]}",
            "audiences": [m["id"] for m in target_managers],
            "read_by": [],
            "kind": "message",
            "title": title,
            "body": body,
            "priority": priority,
            "from_id": from_id,
            "from_name": from_name,
            "from_role": from_role,
            "created_at": now_iso,
        }
        await db["waste_notifications"].insert_one(notif)
    else:  # clients
        cq: Dict[str, Any] = {}
        if scope == "selected":
            if not recipient_ids:
                raise HTTPException(400, "Оберіть одержувачів")
            cq["id"] = {"$in": list(recipient_ids)}
        crows = await db.customers.find(
            cq, {"_id": 0, "id": 1, "name": 1, "email": 1, "companyName": 1, "company_name": 1}
        ).to_list(length=2000)
        target_clients = [r for r in crows if r.get("id")]
        if not target_clients:
            raise HTTPException(404, "Клієнтів не знайдено")
        docs = []
        for c in target_clients:
            docs.append({
                "id": f"msg_{_uuid_mc.uuid4().hex[:12]}",
                "_id": _uuid_mc.uuid4().hex,
                "customerId": c["id"],
                "type": "message",
                "kind": "message",
                "title": title,
                "body": body,
                "message": body,
                "priority": priority,
                "from_id": from_id,
                "from_name": from_name,
                "from_role": from_role,
                "read": False,
                "createdAt": now,
                "created_at": now_iso,
            })
        if docs:
            await db.notifications.insert_many(docs)

    recipient_count = len(target_managers) + len(target_clients)
    outbox = {
        "id": f"out_{_uuid_mc.uuid4().hex[:12]}",
        "from_id": from_id,
        "from_name": from_name,
        "from_role": from_role,
        "audience": audience,
        "scope": scope,
        "title": title,
        "body": body,
        "priority": priority,
        "recipient_count": recipient_count,
        "recipient_managers": [{"id": m["id"], "name": m.get("name") or m.get("email")} for m in target_managers],
        "recipient_clients": [{"id": c["id"], "name": c.get("name") or c.get("companyName") or c.get("email")} for c in target_clients],
        "created_at": now_iso,
    }
    await db["staff_messages"].insert_one({**outbox, "_id": _uuid_mc.uuid4().hex})
    return {"success": True, "sent": recipient_count, "message": outbox}


@router.get("/messages/sent", dependencies=[Depends(require_manager_or_admin)])
async def message_sent(
    limit: int = Query(100, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_manager_or_admin),
):
    """Вихідні повідомлення поточного користувача (outbox)."""
    db = get_db()
    rows = await db["staff_messages"].find(
        {"from_id": user.get("id")}, {"_id": 0}
    ).sort("created_at", -1).limit(int(limit)).to_list(length=int(limit))
    return {"success": True, "items": rows, "count": len(rows)}


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN · editable public contacts (header / footer / Contacts page)
# ════════════════════════════════════════════════════════════════════════════
_C_SITE_CONTACTS = "site_settings"


def _clean_contact_list(items, allowed_keys=("label", "value")):
    out = []
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            val = (it.get("value") or "").strip()
            if not val:
                continue
            out.append({k: (it.get(k) or "").strip() for k in allowed_keys})
    return out


@router.get("/admin/site-contacts", dependencies=[Depends(require_admin)])
async def admin_get_site_contacts():
    from app.site_directory import DEFAULT_CONTACTS
    db = get_db()
    doc = await db[_C_SITE_CONTACTS].find_one({"id": "public_contacts"}, {"_id": 0})
    return {"success": True, "contacts": {**DEFAULT_CONTACTS, **(doc or {})}}


@router.put("/admin/site-contacts", dependencies=[Depends(require_admin)])
async def admin_update_site_contacts(
    data: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_admin),
):
    from app.contact_validation import normalize_phone, validate_email_addr
    db = get_db()
    phones = _clean_contact_list(data.get("phones"))
    emails = _clean_contact_list(data.get("emails"))
    # Validate each contact value; reject the whole save on first bad entry.
    for p in phones:
        ok, norm, err = normalize_phone(p["value"])
        if not ok:
            raise HTTPException(400, f"Телефон «{p['value']}»: {err}")
        p["value"] = norm
    for e in emails:
        ok, norm, err = validate_email_addr(e["value"], required=True)
        if not ok:
            raise HTTPException(400, f"Email «{e['value']}»: {err}")
        e["value"] = norm
    payload = {
        "id": "public_contacts",
        "phones": phones,
        "emails": emails,
        "address": (data.get("address") or "").strip(),
        "working_hours": (data.get("working_hours") or "").strip(),
        "telegram": (data.get("telegram") or "").strip(),
        "viber": (data.get("viber") or "").strip(),
        "messenger": (data.get("messenger") or "").strip(),
        "updated_at": S.now_iso(),
        "updated_by": user.get("id"),
    }
    await db[_C_SITE_CONTACTS].update_one(
        {"id": "public_contacts"}, {"$set": payload}, upsert=True
    )
    return {"success": True, "contacts": payload}


__all__ = ["router"]
