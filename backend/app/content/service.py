"""Content platform service layer — Phase D1.

All DB access lives here so routers stay thin. Every mutation snapshots the
previous state into `content_versions` and invalidates the prerender cache on
publish so bots see fresh HTML within seconds.

Collections
-----------
* `content_pages`    — one doc per (path, lang) pair with block tree.
* `content_versions` — append-only history (last N=50 kept, older archived).
* `media_assets`     — uploaded image/file metadata.
* `faq_items`        — FAQ entries, scoped globally or per-page/group.
* `landing_templates`— D2 scaffold: templates + variables (models only, no UI).
"""
from __future__ import annotations

import logging
import uuid
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.content.blocks import validate_blocks

logger = logging.getLogger("bibi.content")


STATUSES = ("draft", "review", "published", "archived")
MAX_VERSIONS_PER_PAGE = 50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_path(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    # collapse double slashes
    p = re.sub(r"/+", "/", p)
    # drop trailing slash except root
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def _clean_lang(lang: str) -> str:
    lang = (lang or "uk").strip().lower()
    return lang if lang in ("uk", "en") else "uk"


def _serialise(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    out = dict(doc)
    out.pop("_id", None)
    return out


def _invalidate_prerender() -> None:
    try:
        from app.seo import prerender as _pr
        _pr.invalidate_prerender_cache()
    except Exception as e:  # pragma: no cover
        logger.debug("prerender invalidate skipped: %s", e)


# ---------------------------------------------------------------------------
# ContentPageService
# ---------------------------------------------------------------------------

class ContentPageService:
    """CRUD + publish workflow for content pages.

    A `content_pages` document looks like::

        {
          "id":            "cpg_...",
          "path":          "/services/battery-utilisation",
          "lang":          "uk",
          "slug":          "battery-utilisation",
          "kind":          "page"|"waste_code"|"service"|"industry"|"landing"|"blog",
          "title":         "...",
          "summary":       "...",
          "blocks":        [ ... normalised block tree ... ],
          "seo":           { title, description, og_image, canonical_override, robots },
          "cms":           { tags[], category, cover_image_url, breadcrumbs[] },
          "status":        "draft"|"review"|"published"|"archived",
          "ai_status":     "none"|"pending"|"reviewed",   # D2 hook
          "human_review_required": bool,                    # D2 hook
          "reviewer_id":   Optional[str],                    # D2 hook
          "reviewed_at":   Optional[str],                    # D2 hook
          "created_at":    iso,
          "created_by":    staff_id,
          "updated_at":    iso,
          "updated_by":    staff_id,
          "published_at":  Optional[iso],
          "published_by":  Optional[str],
          "version":       int,                              # bumped on every save
        }
    """

    def __init__(self, db):
        self.db = db
        self.col = db.content_pages
        self.versions = db.content_versions

    # --- helpers ---------------------------------------------------------

    async def _ensure_indexes(self) -> None:
        try:
            await self.col.create_index("id", unique=True)
            await self.col.create_index([("path", 1), ("lang", 1)], unique=True)
            await self.col.create_index("status")
            await self.col.create_index("kind")
            await self.col.create_index("updated_at")
            await self.versions.create_index([("page_id", 1), ("version", -1)])
        except Exception as e:  # pragma: no cover
            logger.debug("index setup skipped: %s", e)

    async def _snapshot(self, page: Dict[str, Any], actor: Dict[str, Any], action: str) -> None:
        snap = {
            "id": str(uuid.uuid4()),
            "page_id": page["id"],
            "version": int(page.get("version") or 1),
            "action": action,
            "snapshot": {k: v for k, v in page.items() if k != "_id"},
            "actor_id": (actor or {}).get("id") or (actor or {}).get("sub"),
            "actor_email": (actor or {}).get("email"),
            "created_at": _now(),
        }
        try:
            await self.versions.insert_one(snap)
            # Prune older than N (keep last 50)
            cutoff = await self.versions.find({"page_id": page["id"]}) \
                .sort("version", -1).skip(MAX_VERSIONS_PER_PAGE).to_list(200)
            if cutoff:
                ids = [c["_id"] for c in cutoff]
                await self.versions.delete_many({"_id": {"$in": ids}})
        except Exception as e:  # pragma: no cover
            logger.debug("version snapshot skipped: %s", e)

    # --- CRUD -----------------------------------------------------------

    async def list_pages(self, *, status: Optional[str] = None, kind: Optional[str] = None,
                         q: Optional[str] = None, lang: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if kind:
            query["kind"] = kind
        if lang:
            query["lang"] = _clean_lang(lang)
        if q:
            rgx = re.compile(re.escape(q), re.I)
            query["$or"] = [
                {"title": rgx}, {"path": rgx}, {"slug": rgx}, {"summary": rgx},
            ]
        cursor = self.col.find(query).sort("updated_at", -1).limit(max(1, min(500, int(limit))))
        return [_serialise(d) for d in await cursor.to_list(500)]

    async def get_by_id(self, page_id: str) -> Optional[Dict[str, Any]]:
        return _serialise(await self.col.find_one({"id": page_id}))

    async def get_by_path(self, path: str, lang: str = "uk") -> Optional[Dict[str, Any]]:
        return _serialise(await self.col.find_one({"path": _clean_path(path), "lang": _clean_lang(lang)}))

    async def get_public(self, path: str, lang: str = "uk") -> Optional[Dict[str, Any]]:
        """Return only published pages — used by public API."""
        doc = await self.col.find_one({
            "path": _clean_path(path),
            "lang": _clean_lang(lang),
            "status": "published",
        })
        return _serialise(doc)

    async def create(self, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
        path = _clean_path(payload.get("path") or "")
        if not path:
            raise ValueError("path is required")
        lang = _clean_lang(payload.get("lang") or "uk")
        if await self.col.find_one({"path": path, "lang": lang}):
            raise ValueError(f"page already exists at {path} ({lang})")
        now = _now()
        actor_id = (actor or {}).get("id") or (actor or {}).get("sub")
        doc = {
            "id": "cpg_" + uuid.uuid4().hex[:12],
            "path": path,
            "lang": lang,
            "slug": (payload.get("slug") or path.rsplit("/", 1)[-1] or "home")[:200],
            "kind": (payload.get("kind") or "page")[:32],
            "title": (payload.get("title") or "")[:300],
            "summary": (payload.get("summary") or "")[:800],
            "blocks": validate_blocks(payload.get("blocks") or []),
            "seo": self._clean_seo(payload.get("seo") or {}),
            "cms": self._clean_cms(payload.get("cms") or {}),
            "status": "draft",
            "ai_status": "none",
            "human_review_required": False,
            "reviewer_id": None,
            "reviewed_at": None,
            "created_at": now,
            "created_by": actor_id,
            "updated_at": now,
            "updated_by": actor_id,
            "published_at": None,
            "published_by": None,
            "version": 1,
        }
        await self.col.insert_one(doc)
        await self._snapshot(doc, actor, action="create")
        return _serialise(doc)

    async def update(self, page_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
        existing = await self.col.find_one({"id": page_id})
        if not existing:
            raise LookupError(f"page {page_id} not found")
        # snapshot previous state before overwriting
        await self._snapshot(_serialise(existing), actor, action="update")
        actor_id = (actor or {}).get("id") or (actor or {}).get("sub")
        upd: Dict[str, Any] = {
            "updated_at": _now(),
            "updated_by": actor_id,
            "version": int(existing.get("version") or 1) + 1,
        }
        for k in ("title", "summary", "slug", "kind"):
            if k in payload and payload[k] is not None:
                upd[k] = str(payload[k])[:300 if k == "title" else 800 if k == "summary" else 200]
        if "blocks" in payload:
            upd["blocks"] = validate_blocks(payload["blocks"])
        if "seo" in payload and isinstance(payload["seo"], dict):
            upd["seo"] = self._clean_seo(payload["seo"])
        if "cms" in payload and isinstance(payload["cms"], dict):
            upd["cms"] = self._clean_cms(payload["cms"])
        # AI Guard fields (D2 will use these)
        for k in ("ai_status", "human_review_required", "reviewer_id", "reviewed_at"):
            if k in payload:
                upd[k] = payload[k]
        await self.col.update_one({"id": page_id}, {"$set": upd})
        # If the page is currently published, an edit affects the live version;
        # invalidate cache so bots pick up the change on next request.
        if existing.get("status") == "published":
            _invalidate_prerender()
        return await self.get_by_id(page_id)

    async def delete(self, page_id: str, actor: Dict[str, Any]) -> bool:
        existing = await self.col.find_one({"id": page_id})
        if not existing:
            return False
        await self._snapshot(_serialise(existing), actor, action="delete")
        await self.col.delete_one({"id": page_id})
        if existing.get("status") == "published":
            _invalidate_prerender()
        return True

    # --- publish workflow -----------------------------------------------

    async def transition(self, page_id: str, new_status: str, actor: Dict[str, Any]) -> Dict[str, Any]:
        if new_status not in STATUSES:
            raise ValueError(f"unknown status {new_status}")
        existing = await self.col.find_one({"id": page_id})
        if not existing:
            raise LookupError(f"page {page_id} not found")
        prev = existing.get("status") or "draft"
        if prev == new_status:
            return _serialise(existing)
        await self._snapshot(_serialise(existing), actor, action=f"transition:{prev}->{new_status}")
        actor_id = (actor or {}).get("id") or (actor or {}).get("sub")
        upd: Dict[str, Any] = {
            "status": new_status,
            "updated_at": _now(),
            "updated_by": actor_id,
            "version": int(existing.get("version") or 1) + 1,
        }
        if new_status == "published":
            upd["published_at"] = _now()
            upd["published_by"] = actor_id
        await self.col.update_one({"id": page_id}, {"$set": upd})
        # Any transition that changes public visibility → invalidate cache.
        if prev == "published" or new_status == "published":
            _invalidate_prerender()
        return await self.get_by_id(page_id)

    # --- version restore -------------------------------------------------

    async def list_versions(self, page_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.versions.find({"page_id": page_id}).sort("version", -1).limit(int(limit))
        return [_serialise(d) for d in await cursor.to_list(200)]

    async def restore_version(self, page_id: str, version: int, actor: Dict[str, Any]) -> Dict[str, Any]:
        v = await self.versions.find_one({"page_id": page_id, "version": int(version)})
        if not v:
            raise LookupError(f"version {version} not found for {page_id}")
        snap = v.get("snapshot") or {}
        # Restore as a new DRAFT so the current published version is not
        # overwritten silently. Editor can then transition to review/publish.
        payload = {
            "title": snap.get("title"),
            "summary": snap.get("summary"),
            "blocks": snap.get("blocks") or [],
            "seo": snap.get("seo") or {},
            "cms": snap.get("cms") or {},
            "kind": snap.get("kind"),
            "slug": snap.get("slug"),
        }
        page = await self.get_by_id(page_id)
        if not page:
            raise LookupError(f"page {page_id} not found")
        # Force back to draft on restore.
        payload_full = {**payload}
        await self.update(page_id, payload_full, actor)
        return await self.transition(page_id, "draft", actor)

    # --- helpers --------------------------------------------------------

    def _clean_seo(self, seo: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": (seo.get("title") or "")[:300],
            "description": (seo.get("description") or "")[:500],
            "keywords": (seo.get("keywords") or "")[:500],
            "og_image": (seo.get("og_image") or "")[:2000],
            "canonical_override": (seo.get("canonical_override") or "")[:2000],
            "robots": (seo.get("robots") or "")[:100],
            "twitter_card": (seo.get("twitter_card") or "summary_large_image")[:40],
        }

    def _clean_cms(self, cms: Dict[str, Any]) -> Dict[str, Any]:
        tags = cms.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        breadcrumbs = cms.get("breadcrumbs") or []
        if not isinstance(breadcrumbs, list):
            breadcrumbs = []
        return {
            "tags": [str(t)[:60] for t in tags][:20],
            "category": (cms.get("category") or "")[:100],
            "cover_image_url": (cms.get("cover_image_url") or "")[:2000],
            "breadcrumbs": [
                {"label": str(b.get("label", ""))[:200], "href": str(b.get("href", ""))[:500]}
                for b in breadcrumbs if isinstance(b, dict)
            ][:8],
            "author_id": (cms.get("author_id") or "")[:60],
            "editor_id": (cms.get("editor_id") or "")[:60],
            "expert_id": (cms.get("expert_id") or "")[:60],
            "sources": [str(s)[:500] for s in (cms.get("sources") or []) if isinstance(s, str)][:20],
        }


# ---------------------------------------------------------------------------
# ContentVersionService (thin — exposed for admin diff/history UI)
# ---------------------------------------------------------------------------

class ContentVersionService:
    def __init__(self, db):
        self.db = db
        self.col = db.content_versions

    async def get(self, page_id: str, version: int) -> Optional[Dict[str, Any]]:
        return _serialise(await self.col.find_one({"page_id": page_id, "version": int(version)}))


# ---------------------------------------------------------------------------
# MediaLibraryService
# ---------------------------------------------------------------------------

class MediaLibraryService:
    """Metadata registry for uploaded media. Actual bytes are stored in
    the `content_media` GridFS bucket (uploaded via admin_media router)."""

    def __init__(self, db):
        self.db = db
        self.col = db.media_assets

    async def _ensure_indexes(self) -> None:
        try:
            await self.col.create_index("id", unique=True)
            await self.col.create_index("tags")
            await self.col.create_index("created_at")
        except Exception as e:  # pragma: no cover
            logger.debug("media index setup skipped: %s", e)

    async def list(self, *, q: Optional[str] = None, tag: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if tag:
            query["tags"] = tag
        if q:
            rgx = re.compile(re.escape(q), re.I)
            query["$or"] = [{"filename": rgx}, {"alt": rgx}, {"caption": rgx}]
        cursor = self.col.find(query).sort("created_at", -1).limit(int(limit))
        return [_serialise(d) for d in await cursor.to_list(500)]

    async def get(self, asset_id: str) -> Optional[Dict[str, Any]]:
        return _serialise(await self.col.find_one({"id": asset_id}))

    async def register(self, *, filename: str, url: str, mime: str, size: int,
                       width: Optional[int], height: Optional[int],
                       actor: Dict[str, Any]) -> Dict[str, Any]:
        actor_id = (actor or {}).get("id") or (actor or {}).get("sub")
        doc = {
            "id": "med_" + uuid.uuid4().hex[:12],
            "filename": (filename or "asset")[:200],
            "url": url,
            "mime": mime[:80],
            "size": int(size or 0),
            "width": int(width) if width else None,
            "height": int(height) if height else None,
            "alt": "",
            "caption": "",
            "author": "",
            "copyright": "",
            "tags": [],
            "focus_x": 50,
            "focus_y": 50,
            "created_at": _now(),
            "created_by": actor_id,
            "updated_at": _now(),
        }
        await self.col.insert_one(doc)
        return _serialise(doc)

    async def update(self, asset_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        upd: Dict[str, Any] = {"updated_at": _now()}
        for k in ("alt", "caption", "author", "copyright"):
            if k in payload:
                upd[k] = str(payload[k] or "")[:500]
        if "tags" in payload:
            tags = payload["tags"] or []
            upd["tags"] = [str(t)[:60] for t in tags if str(t).strip()][:20] if isinstance(tags, list) else []
        for k in ("focus_x", "focus_y"):
            if k in payload:
                try:
                    upd[k] = max(0, min(100, int(payload[k])))
                except (TypeError, ValueError):
                    pass
        res = await self.col.update_one({"id": asset_id}, {"$set": upd})
        if res.matched_count == 0:
            return None
        return await self.get(asset_id)

    async def delete(self, asset_id: str) -> bool:
        res = await self.col.delete_one({"id": asset_id})
        return res.deleted_count > 0


# ---------------------------------------------------------------------------
# FAQService — global / per-page / per-group items.
# ---------------------------------------------------------------------------

class FAQService:
    def __init__(self, db):
        self.db = db
        self.col = db.faq_items

    async def _ensure_indexes(self) -> None:
        try:
            await self.col.create_index("id", unique=True)
            await self.col.create_index("group")
            await self.col.create_index("page_path")
            await self.col.create_index("lang")
            await self.col.create_index("order")
        except Exception as e:  # pragma: no cover
            logger.debug("faq index setup skipped: %s", e)

    async def list(self, *, group: Optional[str] = None, page_path: Optional[str] = None,
                    lang: Optional[str] = None, q: Optional[str] = None,
                    published_only: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if group:
            query["group"] = group
        if page_path:
            query["page_path"] = _clean_path(page_path)
        if lang:
            query["lang"] = _clean_lang(lang)
        if published_only:
            query["published"] = True
        if q:
            rgx = re.compile(re.escape(q), re.I)
            query["$or"] = [{"question": rgx}, {"answer": rgx}, {"tags": rgx}]
        cursor = self.col.find(query).sort([("order", 1), ("created_at", -1)]).limit(int(limit))
        return [_serialise(d) for d in await cursor.to_list(500)]

    async def create(self, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
        actor_id = (actor or {}).get("id") or (actor or {}).get("sub")
        doc = {
            "id": "faq_" + uuid.uuid4().hex[:12],
            "question": (payload.get("question") or "")[:400],
            "answer": (payload.get("answer") or "")[:8000],
            "group": (payload.get("group") or "")[:100],
            "page_path": _clean_path(payload.get("page_path") or ""),
            "lang": _clean_lang(payload.get("lang") or "uk"),
            "order": int(payload.get("order") or 100),
            "tags": [str(t)[:60] for t in (payload.get("tags") or []) if str(t).strip()][:10],
            "published": bool(payload.get("published", True)),
            "created_at": _now(),
            "created_by": actor_id,
            "updated_at": _now(),
            "updated_by": actor_id,
        }
        if not doc["question"] or not doc["answer"]:
            raise ValueError("question and answer are required")
        await self.col.insert_one(doc)
        _invalidate_prerender()
        return _serialise(doc)

    async def update(self, faq_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        actor_id = (actor or {}).get("id") or (actor or {}).get("sub")
        upd: Dict[str, Any] = {"updated_at": _now(), "updated_by": actor_id}
        for k, maxlen in (("question", 400), ("answer", 8000), ("group", 100)):
            if k in payload:
                upd[k] = str(payload[k] or "")[:maxlen]
        if "page_path" in payload:
            upd["page_path"] = _clean_path(payload["page_path"] or "")
        if "lang" in payload:
            upd["lang"] = _clean_lang(payload["lang"] or "uk")
        if "order" in payload:
            try:
                upd["order"] = int(payload["order"])
            except (TypeError, ValueError):
                pass
        if "tags" in payload:
            tags = payload["tags"] or []
            upd["tags"] = [str(t)[:60] for t in tags if str(t).strip()][:10] if isinstance(tags, list) else []
        if "published" in payload:
            upd["published"] = bool(payload["published"])
        res = await self.col.update_one({"id": faq_id}, {"$set": upd})
        if res.matched_count == 0:
            return None
        _invalidate_prerender()
        return _serialise(await self.col.find_one({"id": faq_id}))

    async def delete(self, faq_id: str) -> bool:
        res = await self.col.delete_one({"id": faq_id})
        if res.deleted_count > 0:
            _invalidate_prerender()
            return True
        return False

    async def resolve_group(self, group: str, lang: str = "uk") -> List[Dict[str, str]]:
        """Returns [{question, answer}] for a group, used at render time."""
        cursor = self.col.find({
            "group": group,
            "lang": _clean_lang(lang),
            "published": True,
        }).sort([("order", 1)]).limit(50)
        items = await cursor.to_list(50)
        return [{"question": it.get("question", ""), "answer": it.get("answer", "")} for it in items]
