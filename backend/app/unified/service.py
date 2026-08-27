"""Unified Admin Platform — service layer (Slice 1).

READ-ONLY aggregation over existing domain collections. No writes, no schema
changes. Every collection query is wrapped in try/except so a missing/renamed
collection degrades gracefully (empty results) instead of 500-ing the whole
search. Serialisation strips Mongo `_id` and coerces datetimes to ISO strings.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.unified")


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation helpers (avoid "ObjectId / datetime not JSON serializable")
# ─────────────────────────────────────────────────────────────────────────────
def _iso(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return {}
    out = {}
    for k, val in doc.items():
        if k == "_id":
            continue
        out[k] = _iso(val)
    return out


def _rx(q: str):
    """Case-insensitive, escaped substring regex for safe Mongo `$regex`."""
    return {"$regex": re.escape(q), "$options": "i"}


# ─────────────────────────────────────────────────────────────────────────────
# Entity registry — how each searchable domain maps to a unified result.
#   collection : Mongo collection name
#   fields     : text fields to match against
#   type       : unified result type key (used by the frontend router)
#   builder    : (doc) -> {title, subtitle} projection
#   url        : (doc) -> in-app route
# ─────────────────────────────────────────────────────────────────────────────
def _first(doc: Dict[str, Any], *keys, default: str = "") -> str:
    for k in keys:
        v = doc.get(k)
        if v:
            return str(v)
    return default


ENTITY_TYPES: Dict[str, Dict[str, Any]] = {
    "waste_code": {
        "collection": "waste_codes",
        "fields": ["code", "name", "slug", "category_name"],
        "label": "Код відходу",
        "title": lambda d: _first(d, "name", "code", default="—"),
        "subtitle": lambda d: f"Код {_first(d, 'code')} · {_first(d, 'category_name')}".strip(" ·"),
        "url": lambda d: f"/waste-code/{d.get('slug')}" if d.get("slug") else "/app/directory",
    },
    "company": {
        "collection": "waste_companies",
        "fields": ["name", "edrpou", "email", "phone"],
        "label": "Компанія",
        "title": lambda d: _first(d, "name", default="Компанія"),
        "subtitle": lambda d: f"{_first(d, 'status', default='—')} · {_first(d, 'edrpou')}".strip(" ·"),
        "url": lambda d: f"/app/companies/{d.get('id')}" if d.get("id") else "/app/companies",
    },
    "lead": {
        "collection": "leads",
        "fields": ["name", "company", "phone", "email", "wasteType"],
        "label": "Лід",
        "title": lambda d: _first(d, "name", "company", default="Лід"),
        "subtitle": lambda d: f"{_first(d, 'company')} · {_first(d, 'stage', 'status')}".strip(" ·"),
        "url": lambda d: "/app/leads",
    },
    "deal": {
        "collection": "deals",
        "fields": ["title", "company", "customerName", "wasteType"],
        "label": "Угода",
        "title": lambda d: _first(d, "title", "company", default="Угода"),
        "subtitle": lambda d: f"{_first(d, 'stage')} · {_first(d, 'amount')} {_first(d, 'currency', default='EUR')}".strip(" ·"),
        "url": lambda d: f"/app/deals/{d.get('id')}" if d.get("id") else "/app/crm",
    },
    "contract": {
        "collection": "contracts",
        "fields": ["number", "company", "customer_name"],
        "label": "Договір",
        "title": lambda d: f"Договір {_first(d, 'number', default=str(d.get('id', ''))[:8])}",
        "subtitle": lambda d: f"{_first(d, 'company', 'customer_name')} · {_first(d, 'status')}".strip(" ·"),
        "url": lambda d: "/app/contracts",
    },
    "pickup": {
        "collection": "waste_pickups",
        "fields": ["number", "status"],
        "label": "Вивіз",
        "title": lambda d: f"Вивіз {_first(d, 'number', default=str(d.get('id', ''))[:8])}",
        "subtitle": lambda d: f"{_first(d, 'status')} · {_first(d, 'weight_kg')} кг".strip(" ·"),
        "url": lambda d: "/app/operations",
    },
    "customer": {
        "collection": "customers",
        "fields": ["name", "email", "company_name", "phone"],
        "label": "Клієнт",
        "title": lambda d: _first(d, "name", "company_name", "email", default="Клієнт"),
        "subtitle": lambda d: f"{_first(d, 'company_name')} · {_first(d, 'email')}".strip(" ·"),
        "url": lambda d: "/app/companies",
    },
    "content_page": {
        "collection": "content_pages",
        "fields": ["title", "path", "slug"],
        "label": "Сторінка",
        "title": lambda d: _first(d, "title", "path", default="Сторінка"),
        "subtitle": lambda d: f"{_first(d, 'path')} · {_first(d, 'status')}".strip(" ·"),
        "url": lambda d: f"/app/content/pages/{d.get('id')}" if d.get("id") else "/app/content/pages",
    },
    "faq": {
        "collection": "faq_items",
        "fields": ["question", "answer", "scope"],
        "label": "FAQ",
        "title": lambda d: _first(d, "question", default="FAQ"),
        "subtitle": lambda d: f"Scope: {_first(d, 'scope', default='global')}",
        "url": lambda d: "/app/content/faq",
    },
    "media": {
        "collection": "media_assets",
        "fields": ["filename", "alt", "caption", "tags"],
        "label": "Медіа",
        "title": lambda d: _first(d, "filename", "alt", default="Медіа"),
        "subtitle": lambda d: _first(d, "mime", default="—"),
        "url": lambda d: "/app/content/media",
    },
    "seo_page": {
        "collection": "seo_page_metadata",
        "fields": ["path", "title", "description"],
        "label": "SEO-сторінка",
        "title": lambda d: _first(d, "title", "path", default="SEO"),
        "subtitle": lambda d: _first(d, "path"),
        "url": lambda d: "/app/seo/pages",
    },
    "blog": {
        "collection": "blog_articles",
        "fields": ["title", "slug", "excerpt"],
        "label": "Стаття",
        "title": lambda d: _first(d, "title", default="Стаття"),
        "subtitle": lambda d: _first(d, "slug"),
        "url": lambda d: "/app/blog",
    },
}


class UnifiedService:
    def __init__(self, db):
        self.db = db

    # ── Global Search ─────────────────────────────────────────────────────
    async def global_search(
        self,
        q: str,
        types: Optional[List[str]] = None,
        per_type: int = 5,
    ) -> Dict[str, Any]:
        q = (q or "").strip()
        if len(q) < 2:
            return {"query": q, "groups": [], "total": 0}

        wanted = [t for t in (types or list(ENTITY_TYPES.keys())) if t in ENTITY_TYPES]
        groups: List[Dict[str, Any]] = []
        total = 0

        for tkey in wanted:
            spec = ENTITY_TYPES[tkey]
            coll = self.db[spec["collection"]]
            ors = [{f: _rx(q)} for f in spec["fields"]]
            try:
                cursor = coll.find({"$or": ors}).limit(int(per_type))
                docs = await cursor.to_list(length=int(per_type))
            except Exception as e:  # pragma: no cover
                logger.debug("search %s failed: %s", tkey, e)
                docs = []
            items = []
            for d in docs:
                try:
                    items.append({
                        "type": tkey,
                        "label": spec["label"],
                        "id": d.get("id") or str(d.get("_id")),
                        "title": spec["title"](d),
                        "subtitle": spec["subtitle"](d),
                        "url": spec["url"](d),
                    })
                except Exception as e:  # pragma: no cover
                    logger.debug("project %s failed: %s", tkey, e)
            if items:
                total += len(items)
                groups.append({"type": tkey, "label": spec["label"], "items": items})

        return {"query": q, "groups": groups, "total": total}

    # ── Relation resolver (Universal Relation Picker source) ──────────────
    async def relations(self, type: str, q: str = "", limit: int = 20) -> Dict[str, Any]:
        if type not in ENTITY_TYPES:
            return {"type": type, "items": [], "count": 0}
        spec = ENTITY_TYPES[type]
        coll = self.db[spec["collection"]]
        q = (q or "").strip()
        query: Dict[str, Any] = {}
        if q:
            query = {"$or": [{f: _rx(q)} for f in spec["fields"]]}
        try:
            docs = await coll.find(query).limit(int(min(100, max(1, limit)))).to_list(length=limit)
        except Exception as e:  # pragma: no cover
            logger.debug("relations %s failed: %s", type, e)
            docs = []
        items = []
        for d in docs:
            try:
                items.append({
                    "type": type,
                    "id": d.get("id") or str(d.get("_id")),
                    "title": spec["title"](d),
                    "subtitle": spec["subtitle"](d),
                    "url": spec["url"](d),
                })
            except Exception:
                pass
        return {"type": type, "label": spec["label"], "items": items, "count": len(items)}

    def relation_types(self) -> List[Dict[str, str]]:
        return [{"type": k, "label": v["label"]} for k, v in ENTITY_TYPES.items()]

    # ── Unified Dashboard ─────────────────────────────────────────────────
    async def _count(self, coll: str, query: Optional[Dict[str, Any]] = None) -> int:
        try:
            return await self.db[coll].count_documents(query or {})
        except Exception:
            return 0

    async def _recent(self, coll: str, tkey: str, limit: int = 6) -> List[Dict[str, Any]]:
        spec = ENTITY_TYPES.get(tkey)
        if not spec:
            return []
        out = []
        try:
            cursor = self.db[coll].find({}).sort([("updated_at", -1), ("created_at", -1)]).limit(limit)
            docs = await cursor.to_list(length=limit)
            for d in docs:
                out.append({
                    "type": tkey,
                    "id": d.get("id") or str(d.get("_id")),
                    "title": spec["title"](d),
                    "subtitle": spec["subtitle"](d),
                    "url": spec["url"](d),
                    "ts": _iso(d.get("updated_at") or d.get("created_at")),
                })
        except Exception as e:  # pragma: no cover
            logger.debug("recent %s failed: %s", tkey, e)
        return out

    async def dashboard(self) -> Dict[str, Any]:
        # Domain KPI cards — each aggregates across an existing domain.
        crm = {
            "leads": await self._count("leads"),
            "deals": await self._count("deals"),
            "customers": await self._count("customers"),
        }
        waste = {
            "codes": await self._count("waste_codes"),
            "companies": await self._count("waste_companies"),
            "pickups": await self._count("waste_pickups"),
        }
        content = {
            "pages": await self._count("content_pages"),
            "published": await self._count("content_pages", {"status": "published"}),
            "drafts": await self._count("content_pages", {"status": "draft"}),
            "review": await self._count("content_pages", {"status": "review"}),
            "faq": await self._count("faq_items"),
            "media": await self._count("media_assets"),
        }
        seo = {"pages": await self._count("seo_page_metadata")}
        finance = {
            "contracts": await self._count("contracts"),
            "invoices": await self._count("invoices"),
            "payments": await self._count("payments"),
        }
        staff = {"members": await self._count("staff")}

        # Deals amount sum (best-effort aggregation)
        deals_value = 0.0
        try:
            agg = await self.db["deals"].aggregate([
                {"$group": {"_id": None, "sum": {"$sum": {"$ifNull": ["$amount", 0]}}}}
            ]).to_list(length=1)
            if agg:
                deals_value = round(float(agg[0].get("sum") or 0), 2)
        except Exception:
            pass

        recent = {
            "leads": await self._recent("leads", "lead", 5),
            "deals": await self._recent("deals", "deal", 5),
            "pickups": await self._recent("waste_pickups", "pickup", 5),
            "content": await self._recent("content_pages", "content_page", 5),
        }

        return {
            "cards": {
                "crm": crm,
                "waste": waste,
                "content": content,
                "seo": seo,
                "finance": finance,
                "staff": staff,
                "deals_value": deals_value,
            },
            "recent": recent,
        }
