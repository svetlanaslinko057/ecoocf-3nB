"""FileRepository — single point of access to the canonical ``files`` collection.

Responsibilities:
  * persist file metadata (incl. ``storage_key``, ``version``, ``status``)
  * resolve current/latest version for a given entity
  * list versions / list active files per scope
  * record audit events on lifecycle changes

Legacy callers used ``backend/app/storage/router.py::_save_record`` which
inserted documents into the same ``files`` collection. We keep the
collection name and the legacy field set so the existing UI works
untouched; new fields (``version``, ``status``, ``storage_key``,
``provider``, ``entity_type``, ``entity_id``, ``photo_stage``) are added
as the canonical schema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

FILE_COLLECTION = "files"
FILE_AUDIT_COLLECTION = "file_audit"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileRepository:
    def __init__(self, db) -> None:
        self.db = db

    # ----- create ------------------------------------------------------
    async def add_file(
        self,
        *,
        id: str,
        stored,
        owner: str,
        purpose: Optional[str] = None,
        title: Optional[str] = None,
        company_id: Optional[str] = None,
        object_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        pickup_id: Optional[str] = None,
        act_id: Optional[str] = None,
        invoice_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        photo_stage: Optional[str] = None,
        generated: bool = False,
        parent_file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # derive canonical (entity_type, entity_id) if not provided
        if not entity_type or not entity_id:
            entity_type, entity_id = _derive_entity(
                contract_id=contract_id, pickup_id=pickup_id, act_id=act_id,
                invoice_id=invoice_id, object_id=object_id, company_id=company_id,
            )
        # determine version number for that (entity_type, entity_id, purpose[, photo_stage])
        # Photos are scoped per stage so re-uploading the ``signed_act`` photo
        # does NOT mark ``before_loading`` as replaced.
        version = 1
        if entity_type and entity_id:
            version = await self._next_version(entity_type, entity_id, purpose, photo_stage=photo_stage)
            # mark previous active version (same scope) as ``replaced`` so list-latest queries
            # return only the current one (history remains queryable).
            replace_q: Dict[str, Any] = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "purpose": purpose or "general",
                "status": "active",
            }
            if photo_stage:
                replace_q["photo_stage"] = photo_stage
            else:
                # Non-photo records: do not collide with stage-tagged records.
                replace_q["photo_stage"] = None
            await self.db[FILE_COLLECTION].update_many(
                replace_q,
                {"$set": {"status": "replaced", "replaced_at": _iso()}},
            )

        now = _iso()
        doc = {
            "id": id,
            "filename": stored.filename,
            "title": title or stored.filename,
            # legacy field names kept for backward compatibility
            "mime": stored.mime,
            "mimeType": stored.mime,
            "size": stored.size,
            "sha256": stored.sha256,
            "storage_key": stored.storage_key,
            "storageKey": stored.storage_key,
            "path": stored.storage_key,  # legacy alias
            "provider": stored.provider,
            "uploaded_by": owner,
            "uploadedBy": owner,
            "purpose": purpose or "general",
            "company_id": company_id,
            "companyId": company_id,
            "object_id": object_id,
            "objectId": object_id,
            "contract_id": contract_id,
            "pickup_id": pickup_id,
            "act_id": act_id,
            "invoice_id": invoice_id,
            "entity_type": entity_type,
            "entityType": entity_type,
            "entity_id": entity_id,
            "entityId": entity_id,
            "photo_stage": photo_stage,
            "photoStage": photo_stage,
            "generated": bool(generated),
            "version": version,
            "parent_file_id": parent_file_id,
            "parentFileId": parent_file_id,
            "status": "active",
            "created_at": now,
            "createdAt": now,
            "updated_at": now,
        }
        await self.db[FILE_COLLECTION].insert_one(dict(doc))
        await self._audit(
            file_id=id, entity_type=entity_type, entity_id=entity_id,
            event="created", by=owner, details={"version": version, "generated": generated},
        )
        return {k: v for k, v in doc.items() if k != "_id"}

    async def _next_version(self, entity_type: str, entity_id: str, purpose: Optional[str], *, photo_stage: Optional[str] = None) -> int:
        q: Dict[str, Any] = {"entity_type": entity_type, "entity_id": entity_id, "purpose": purpose or "general"}
        if photo_stage:
            q["photo_stage"] = photo_stage
        else:
            q["photo_stage"] = None
        last = await self.db[FILE_COLLECTION].find_one(
            q, sort=[("version", -1)], projection={"_id": 0, "version": 1},
        )
        return int((last or {}).get("version") or 0) + 1

    # ----- queries -----------------------------------------------------
    async def get(self, file_id: str) -> Optional[Dict[str, Any]]:
        return await self.db[FILE_COLLECTION].find_one({"id": file_id}, {"_id": 0})

    async def find(self, query: Dict[str, Any], *, limit: int = 200, sort_desc: bool = True) -> List[Dict[str, Any]]:
        cursor = self.db[FILE_COLLECTION].find(query, {"_id": 0}).sort(
            "created_at", -1 if sort_desc else 1
        ).limit(int(limit))
        return await cursor.to_list(length=int(limit))

    async def versions(self, entity_type: str, entity_id: str, *, purpose: Optional[str] = None) -> List[Dict[str, Any]]:
        q: Dict[str, Any] = {"entity_type": entity_type, "entity_id": entity_id}
        if purpose:
            q["purpose"] = purpose
        return await self.find(q, limit=500)

    async def latest(self, entity_type: str, entity_id: str, *, purpose: Optional[str] = None) -> Optional[Dict[str, Any]]:
        q: Dict[str, Any] = {"entity_type": entity_type, "entity_id": entity_id, "status": "active"}
        if purpose:
            q["purpose"] = purpose
        return await self.db[FILE_COLLECTION].find_one(q, {"_id": 0}, sort=[("version", -1)])

    # ----- mutation ----------------------------------------------------
    async def soft_delete(self, file_id: str, by: Optional[str] = None) -> bool:
        res = await self.db[FILE_COLLECTION].update_one(
            {"id": file_id},
            {"$set": {"status": "deleted", "deleted_at": _iso(), "updated_at": _iso()}},
        )
        if res.matched_count:
            await self._audit(file_id=file_id, event="deleted", by=by)
        return bool(res.matched_count)

    # ----- audit -------------------------------------------------------
    async def _audit(
        self,
        *,
        file_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        event: str,
        by: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            await self.db[FILE_AUDIT_COLLECTION].insert_one({
                "at": _iso(),
                "file_id": file_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "event": event,
                "by": by,
                "details": details or {},
            })
        except Exception:
            pass


def _derive_entity(**ids: Any):
    """Return (entity_type, entity_id) from the first non-empty link."""
    mapping = [
        ("contract", ids.get("contract_id")),
        ("act", ids.get("act_id")),
        ("pickup", ids.get("pickup_id")),
        ("invoice", ids.get("invoice_id")),
        ("object", ids.get("object_id")),
        ("company", ids.get("company_id")),
    ]
    for t, v in mapping:
        if v:
            return t, v
    return None, None
