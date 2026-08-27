"""Unified Admin Platform — universal subsystems (Slice 2).

ADDITIVE ONLY. Introduces brand-new *universal* collections + read-only adapters
so any ECO entity behaves the same. Nothing here mutates existing CRM / Waste /
SEO / Content / Documents schemas.

New collections (all namespaced, never collide with domain data):
  * u_comments      — universal comments   (entity_type, entity_id, ...)
  * u_attachments   — universal attachments (links to existing file/GridFS layer)
  * u_audit         — universal audit trail (before/after diffs)
  * u_activity      — universal activity events (native, emitted by unified ops)
  * u_notif_state   — per-user "seen" signature for the header notification centre

The Activity Feed is a HYBRID: it merges native `u_activity` events with events
*derived live* from existing domain collections (recent create/update on deals,
contracts, pickups, content, leads, media, seo) — so it is populated without
touching any domain write-path.
"""
from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bibi.unified.universal")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return {}
    return {k: _iso(v) for k, v in doc.items() if k != "_id"}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _actor(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    user = user or {}
    return {
        "id": user.get("id") or user.get("sub") or "system",
        "name": user.get("name") or user.get("email") or "Система",
        "role": user.get("role") or "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entity → collection / status-field / label map (reused by several services).
# ─────────────────────────────────────────────────────────────────────────────
ENTITY_COLLECTION = {
    "waste_code": "waste_codes",
    "company": "waste_companies",
    "lead": "leads",
    "deal": "deals",
    "contract": "contracts",
    "pickup": "waste_pickups",
    "customer": "customers",
    "content_page": "content_pages",
    "faq": "faq_items",
    "media": "media_assets",
    "seo_page": "seo_page_metadata",
    "blog": "blog_articles",
    "invoice": "invoices",
}

ENTITY_LABEL = {
    "waste_code": "Код відходу", "company": "Компанія", "lead": "Лід",
    "deal": "Угода", "contract": "Договір", "pickup": "Вивіз",
    "customer": "Клієнт", "content_page": "Сторінка", "faq": "FAQ",
    "media": "Медіа", "seo_page": "SEO-сторінка", "blog": "Стаття",
    "invoice": "Рахунок", "staff": "Персонал",
}


# ─────────────────────────────────────────────────────────────────────────────
# Draft Adapter — read-only lifecycle mapping (never writes domain status).
#   universal stages: draft · review · published · archived
#   For domains with a bespoke lifecycle we expose the NATIVE stages plus a
#   universal bucket so the UI can render one consistent badge/stepper.
# ─────────────────────────────────────────────────────────────────────────────
STAGE_META = {
    "draft":     {"label": "Чернетка",   "color": "slate"},
    "review":    {"label": "На рев'ю",   "color": "amber"},
    "published": {"label": "Опубліковано", "color": "green"},
    "archived":  {"label": "Архів",      "color": "zinc"},
    "active":    {"label": "Активний",   "color": "green"},
    "won":       {"label": "Виграно",    "color": "green"},
    "lost":      {"label": "Втрачено",   "color": "rose"},
    "open":      {"label": "Відкрито",   "color": "blue"},
    "unknown":   {"label": "—",          "color": "slate"},
}

LIFECYCLES: Dict[str, Dict[str, Any]] = {
    "content_page": {
        "field": "status", "type": "standard",
        "stages": ["draft", "review", "published", "archived"],
        "map": {},  # identity
    },
    "deal": {
        "field": "stage", "type": "custom",
        "stages": ["new", "qualifying", "negotiation", "won", "lost"],
        "map": {"new": "draft", "qualifying": "draft", "negotiation": "review", "won": "published", "lost": "archived"},
    },
    "lead": {
        "field": "stage", "type": "custom",
        "stages": ["new", "qualifying", "converted", "lost"],
        "map": {"new": "draft", "qualifying": "review", "converted": "published", "lost": "archived"},
    },
    "contract": {
        "field": "status", "type": "custom",
        "stages": ["draft", "sent", "signed", "active", "closed"],
        "map": {"draft": "draft", "sent": "review", "signed": "published", "active": "published", "closed": "archived"},
    },
    "pickup": {
        "field": "status", "type": "custom",
        "stages": ["planning", "assigned", "picked_up", "delivered", "closed"],
        "map": {"planning": "draft", "assigned": "review", "picked_up": "review", "delivered": "published", "closed": "archived"},
    },
    "invoice": {
        "field": "status", "type": "custom",
        "stages": ["draft", "issued", "paid", "overdue", "cancelled"],
        "map": {"draft": "draft", "issued": "review", "paid": "published", "overdue": "review", "cancelled": "archived"},
    },
}


class DraftAdapter:
    """Pure read-only resolver of any entity's lifecycle → universal stage."""

    @staticmethod
    def lifecycle_map() -> Dict[str, Any]:
        return {k: {"field": v["field"], "type": v["type"], "stages": v["stages"]} for k, v in LIFECYCLES.items()}

    @staticmethod
    def resolve(entity_type: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        spec = LIFECYCLES.get(entity_type)
        if not spec:
            native = str((doc or {}).get("status") or (doc or {}).get("stage") or "unknown")
            uni = native if native in STAGE_META else "unknown"
            return {
                "entity_type": entity_type, "native_status": native, "universal_stage": uni,
                "label": STAGE_META.get(uni, STAGE_META["unknown"])["label"],
                "color": STAGE_META.get(uni, STAGE_META["unknown"])["color"],
                "lifecycle_type": "none", "stages": [],
            }
        native = str((doc or {}).get(spec["field"]) or "").lower() or "unknown"
        uni = spec["map"].get(native, native) if spec["type"] == "custom" else native
        if uni not in STAGE_META:
            uni = "draft"
        return {
            "entity_type": entity_type,
            "native_status": native,
            "universal_stage": uni,
            "label": STAGE_META[uni]["label"],
            "color": STAGE_META[uni]["color"],
            "lifecycle_type": spec["type"],
            "stages": spec["stages"],
        }


class UniversalService:
    """Single facade over the universal subsystems (Slice 2)."""

    def __init__(self, db):
        self.db = db
        self.comments = db.u_comments
        self.attachments = db.u_attachments
        self.audit = db.u_audit
        self.activity = db.u_activity
        self.notif_state = db.u_notif_state
        self._indexed = False

    async def ensure_indexes(self):
        if self._indexed:
            return
        try:
            for coll in (self.comments, self.attachments, self.audit, self.activity):
                await coll.create_index([("entity_type", 1), ("entity_id", 1), ("created_at", -1)])
            await self.activity.create_index([("created_at", -1)])
            await self.comments.create_index("id", unique=True)
            await self.attachments.create_index("id", unique=True)
            await self.notif_state.create_index("user_id", unique=True)
            self._indexed = True
        except Exception as e:  # pragma: no cover
            logger.debug("ensure_indexes failed: %s", e)

    # ── internal: emit an activity + optional audit event ────────────────
    async def _emit(self, entity_type, entity_id, action, actor, *, title="", icon="activity",
                    color="slate", url="", before=None, after=None, audit=False):
        ts = _now()
        ev = {
            "id": _uid("act"), "entity_type": entity_type, "entity_id": str(entity_id),
            "entity_label": ENTITY_LABEL.get(entity_type, entity_type),
            "action": action, "title": title, "icon": icon, "color": color, "url": url,
            "actor": actor, "created_at": ts,
        }
        try:
            await self.activity.insert_one(dict(ev))
        except Exception as e:  # pragma: no cover
            logger.debug("activity insert failed: %s", e)
        if audit:
            try:
                await self.audit.insert_one({
                    "id": _uid("aud"), "entity_type": entity_type, "entity_id": str(entity_id),
                    "action": action, "actor": actor, "before": before, "after": after,
                    "created_at": ts,
                })
            except Exception as e:  # pragma: no cover
                logger.debug("audit insert failed: %s", e)
        return _clean(ev)

    # ═══════════════════════ COMMENTS ═══════════════════════
    async def list_comments(self, entity_type, entity_id, limit=100):
        cur = self.comments.find(
            {"entity_type": entity_type, "entity_id": str(entity_id), "deleted": {"$ne": True}}
        ).sort("created_at", 1).limit(limit)
        return [_clean(d) for d in await cur.to_list(length=limit)]

    async def create_comment(self, entity_type, entity_id, text, actor, attachments=None):
        text = (text or "").strip()
        if not text:
            raise ValueError("empty comment")
        doc = {
            "id": _uid("cmt"), "entity_type": entity_type, "entity_id": str(entity_id),
            "author": actor, "text": text, "attachments": attachments or [],
            "created_at": _now(), "edited_at": None, "deleted": False,
        }
        await self.comments.insert_one(dict(doc))
        await self._emit(entity_type, entity_id, "comment.created", actor,
                         title=text[:80], icon="message", color="blue", audit=False)
        return _clean(doc)

    async def update_comment(self, comment_id, text, actor):
        text = (text or "").strip()
        c = await self.comments.find_one({"id": comment_id})
        if not c:
            raise LookupError("comment not found")
        await self.comments.update_one({"id": comment_id}, {"$set": {"text": text, "edited_at": _now()}})
        return _clean(await self.comments.find_one({"id": comment_id}))

    async def delete_comment(self, comment_id, actor):
        c = await self.comments.find_one({"id": comment_id})
        if not c:
            raise LookupError("comment not found")
        await self.comments.update_one({"id": comment_id}, {"$set": {"deleted": True, "edited_at": _now()}})
        return True

    # ═══════════════════════ ATTACHMENTS ═══════════════════════
    # Reuses the EXISTING content_media GridFS bucket (no new storage system).
    async def list_attachments(self, entity_type, entity_id, limit=100):
        cur = self.attachments.find(
            {"entity_type": entity_type, "entity_id": str(entity_id), "deleted": {"$ne": True}}
        ).sort("created_at", -1).limit(limit)
        return [_clean(d) for d in await cur.to_list(length=limit)]

    async def register_attachment(self, entity_type, entity_id, *, filename, url, mime,
                                  size, actor, file_id=None):
        doc = {
            "id": _uid("att"), "entity_type": entity_type, "entity_id": str(entity_id),
            "filename": filename, "url": url, "mime": mime, "size": size,
            "file_id": file_id, "uploaded_by": actor, "created_at": _now(), "deleted": False,
        }
        await self.attachments.insert_one(dict(doc))
        await self._emit(entity_type, entity_id, "attachment.added", actor,
                         title=filename, icon="paperclip", color="violet", audit=True,
                         after={"filename": filename, "url": url})
        return _clean(doc)

    async def delete_attachment(self, attachment_id, actor):
        a = await self.attachments.find_one({"id": attachment_id})
        if not a:
            raise LookupError("attachment not found")
        await self.attachments.update_one({"id": attachment_id}, {"$set": {"deleted": True}})
        await self._emit(a["entity_type"], a["entity_id"], "attachment.removed", actor,
                         title=a.get("filename", ""), icon="paperclip", color="rose", audit=True,
                         before={"filename": a.get("filename")})
        return a  # returns raw doc so router can drop the GridFS blob

    # ═══════════════════════ AUDIT ═══════════════════════
    async def list_audit(self, entity_type, entity_id, limit=100):
        cur = self.audit.find(
            {"entity_type": entity_type, "entity_id": str(entity_id)}
        ).sort("created_at", -1).limit(limit)
        return [_clean(d) for d in await cur.to_list(length=limit)]

    async def record_audit(self, entity_type, entity_id, action, actor, before=None, after=None):
        doc = {
            "id": _uid("aud"), "entity_type": entity_type, "entity_id": str(entity_id),
            "action": action, "actor": actor, "before": before, "after": after, "created_at": _now(),
        }
        await self.audit.insert_one(dict(doc))
        return _clean(doc)

    # ═══════════════════════ LIFECYCLE (Draft Adapter) ═══════════════════════
    async def resolve_lifecycle(self, entity_type, entity_id):
        coll_name = ENTITY_COLLECTION.get(entity_type)
        doc = None
        if coll_name:
            try:
                doc = await self.db[coll_name].find_one({"id": str(entity_id)})
            except Exception:
                doc = None
        return DraftAdapter.resolve(entity_type, doc or {})

    # ═══════════════════════ ACTIVITY FEED (hybrid) ═══════════════════════
    async def _derived_activity(self, limit=40):
        """Live-derive recent domain events (read-only) from existing collections."""
        out: List[Dict[str, Any]] = []
        derive_specs = [
            ("deals", "deal", "Угода", "handshake", "green", lambda d: d.get("title") or d.get("company") or "Угода"),
            ("contracts", "contract", "Договір", "scroll", "emerald", lambda d: f"Договір {d.get('number', '')}"),
            ("waste_pickups", "pickup", "Вивіз", "truck", "amber", lambda d: f"Вивіз {d.get('number', '')}"),
            ("leads", "lead", "Лід", "users", "blue", lambda d: d.get("name") or d.get("company") or "Лід"),
            ("content_pages", "content_page", "Сторінка", "file", "violet", lambda d: d.get("title") or d.get("path")),
            ("media_assets", "media", "Медіа", "image", "cyan", lambda d: d.get("filename") or "Медіа"),
            ("seo_page_metadata", "seo_page", "SEO", "globe", "teal", lambda d: d.get("path") or d.get("title")),
        ]
        for coll, tkey, label, icon, color, titler in derive_specs:
            try:
                cur = self.db[coll].find({}).sort([("updated_at", -1), ("created_at", -1)]).limit(6)
                for d in await cur.to_list(length=6):
                    ts = d.get("updated_at") or d.get("created_at")
                    if not isinstance(ts, (datetime, date)):
                        continue
                    out.append({
                        "id": f"derived_{tkey}_{d.get('id') or d.get('_id')}",
                        "entity_type": tkey, "entity_id": str(d.get("id") or d.get("_id")),
                        "entity_label": label,
                        "action": "updated", "title": str(titler(d) or label),
                        "icon": icon, "color": color, "url": "",
                        "actor": {"name": "Система"}, "created_at": ts, "derived": True,
                    })
            except Exception as e:  # pragma: no cover
                logger.debug("derive %s failed: %s", coll, e)
        return out

    async def activity_feed(self, entity_type=None, entity_id=None, limit=40, include_derived=True):
        q: Dict[str, Any] = {}
        if entity_type:
            q["entity_type"] = entity_type
        if entity_id:
            q["entity_id"] = str(entity_id)
        native = []
        try:
            cur = self.activity.find(q).sort("created_at", -1).limit(limit)
            native = [_clean(d) for d in await cur.to_list(length=limit)]
        except Exception as e:  # pragma: no cover
            logger.debug("activity_feed native failed: %s", e)
        merged = native
        if include_derived and not entity_id:
            derived = await self._derived_activity(limit)
            merged = native + [ {**d, "created_at": _iso(d["created_at"])} for d in derived ]
        merged.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"items": merged[:limit], "count": len(merged[:limit])}

    # ═══════════════════════ TIMELINE (per-entity merge) ═══════════════════════
    async def timeline(self, entity_type, entity_id, limit=100):
        entity_id = str(entity_id)
        comments = await self.list_comments(entity_type, entity_id, limit)
        attachments = await self.list_attachments(entity_type, entity_id, limit)
        audit = await self.list_audit(entity_type, entity_id, limit)
        acts = (await self.activity_feed(entity_type, entity_id, limit, include_derived=False))["items"]
        lifecycle = await self.resolve_lifecycle(entity_type, entity_id)

        events: List[Dict[str, Any]] = []
        for c in comments:
            events.append({"kind": "comment", "id": c["id"], "ts": c.get("created_at"),
                           "actor": c.get("author", {}), "text": c.get("text"),
                           "attachments": c.get("attachments", []), "icon": "message", "color": "blue"})
        for a in attachments:
            events.append({"kind": "attachment", "id": a["id"], "ts": a.get("created_at"),
                           "actor": a.get("uploaded_by", {}), "title": a.get("filename"),
                           "url": a.get("url"), "mime": a.get("mime"), "icon": "paperclip", "color": "violet"})
        for au in audit:
            events.append({"kind": "audit", "id": au["id"], "ts": au.get("created_at"),
                           "actor": au.get("actor", {}), "action": au.get("action"),
                           "before": au.get("before"), "after": au.get("after"), "icon": "history", "color": "amber"})
        for ev in acts:
            if str(ev.get("action", "")).startswith(("comment.", "attachment.")):
                continue  # already represented above
            events.append({"kind": "event", "id": ev["id"], "ts": ev.get("created_at"),
                           "actor": ev.get("actor", {}), "action": ev.get("action"),
                           "title": ev.get("title"), "icon": ev.get("icon", "activity"),
                           "color": ev.get("color", "slate")})
        events.sort(key=lambda x: x.get("ts") or "", reverse=True)
        return {
            "entity_type": entity_type, "entity_id": entity_id,
            "lifecycle": lifecycle,
            "counts": {"comments": len(comments), "attachments": len(attachments), "audit": len(audit)},
            "events": events[:limit],
        }

    # ═══════════════════════ HEADER NOTIFICATIONS (aggregated) ═══════════════════════
    async def _count(self, coll, q):
        try:
            return await self.db[coll].count_documents(q)
        except Exception:
            return 0

    async def notifications(self, user):
        now = _now()
        items = []

        content_review = await self._count("content_pages", {"status": "review"})
        if content_review:
            items.append({"key": "content_review", "category": "Контент", "icon": "file",
                          "color": "violet", "title": "Контент очікує рев'ю", "count": content_review,
                          "url": "/app/content/pages"})

        leads_new = await self._count("leads", {"stage": "new"})
        if leads_new:
            items.append({"key": "leads_new", "category": "CRM", "icon": "users", "color": "blue",
                          "title": "Нові ліди", "count": leads_new, "url": "/app/leads"})

        pickups_planning = await self._count("waste_pickups", {"status": "planning"})
        if pickups_planning:
            items.append({"key": "pickups_planning", "category": "Операції", "icon": "truck",
                          "color": "amber", "title": "Вивози в плануванні", "count": pickups_planning,
                          "url": "/app/operations"})

        # Overdue invoices (best-effort — collection may be empty)
        overdue = 0
        try:
            overdue = await self.db["invoices"].count_documents(
                {"status": {"$nin": ["paid", "cancelled"]}, "due_date": {"$lt": now}}
            )
        except Exception:
            overdue = 0
        if overdue:
            items.append({"key": "invoices_overdue", "category": "Фінанси", "icon": "receipt",
                          "color": "rose", "title": "Прострочені рахунки", "count": overdue,
                          "url": "/app/finance"})

        contracts_sign = await self._count("contracts", {"status": {"$in": ["sent", "draft"]}})
        if contracts_sign:
            items.append({"key": "contracts_pending", "category": "Документи", "icon": "scroll",
                          "color": "emerald", "title": "Договори очікують підпис", "count": contracts_sign,
                          "url": "/app/contracts"})

        total = sum(i["count"] for i in items)
        signature = "|".join(f"{i['key']}:{i['count']}" for i in items)

        # unread = current signature differs from last seen signature
        seen_sig = ""
        try:
            st = await self.notif_state.find_one({"user_id": _actor(user)["id"]})
            seen_sig = (st or {}).get("signature", "")
        except Exception:
            seen_sig = ""

        return {"items": items, "total": total, "unread": signature != seen_sig,
                "signature": signature}

    async def mark_notifications_seen(self, user, signature):
        uid = _actor(user)["id"]
        await self.notif_state.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "signature": signature or "", "seen_at": _now()}},
            upsert=True,
        )
        return {"success": True}
