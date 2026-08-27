"""Backfill legacy ``files`` rows to the canonical Wave 5B-v2 schema.

Idempotent: marks completion via ``app_state.wave_5bv2_migration_at`` and
skips already-migrated rows by detecting the new fields. Safe to run on
every startup — costs are bounded by the size of the existing collection
(<1000 rows in production).

What we backfill:
  * version=1                 if missing
  * status='active'           if missing
  * storage_key=path           if missing
  * provider='local'           if missing
  * entity_type/entity_id     derived from contract_id/act_id/pickup_id/...
  * mimeType / uploadedBy / createdAt / companyId / objectId aliases

No binary is moved — files stay where they are on disk; the
``storage_key`` is set to the existing (already-absolute) path so the
LocalStorageProvider can serve them unchanged.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger("bibi.storage.migration")

FILE_COLLECTION = "files"


def _derive_entity(d: Dict[str, Any]):
    pairs = [
        ("contract", d.get("contract_id")),
        ("act",      d.get("act_id")),
        ("pickup",   d.get("pickup_id")),
        ("invoice",  d.get("invoice_id")),
        ("object",   d.get("object_id")),
        ("company",  d.get("company_id")),
    ]
    for t, v in pairs:
        if v:
            return t, v
    return None, None


async def run_migration(db) -> Dict[str, Any]:
    seen = 0
    patched = 0
    cursor = db[FILE_COLLECTION].find({}, {"_id": 0})
    async for doc in cursor:
        seen += 1
        patch: Dict[str, Any] = {}
        if "version" not in doc or doc.get("version") in (None, 0):
            patch["version"] = 1
        if not doc.get("status"):
            patch["status"] = "active"
        if not doc.get("storage_key"):
            patch["storage_key"] = doc.get("path") or doc.get("storageKey") or ""
            patch["storageKey"] = patch["storage_key"]
        if not doc.get("provider"):
            patch["provider"] = "local"
        if not doc.get("mimeType") and doc.get("mime"):
            patch["mimeType"] = doc["mime"]
        if not doc.get("uploadedBy") and doc.get("uploaded_by"):
            patch["uploadedBy"] = doc["uploaded_by"]
        if not doc.get("createdAt") and doc.get("created_at"):
            patch["createdAt"] = doc["created_at"]
        if not doc.get("entity_type") or not doc.get("entity_id"):
            et, ei = _derive_entity(doc)
            if et and ei:
                patch["entity_type"] = et
                patch["entityType"] = et
                patch["entity_id"] = ei
                patch["entityId"] = ei
        if patch:
            patch["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db[FILE_COLLECTION].update_one({"id": doc["id"]}, {"$set": patch})
            patched += 1
    try:
        await db.app_state.update_one(
            {"_id": "wave_5bv2_migration"},
            {"$set": {"at": datetime.now(timezone.utc).isoformat(), "seen": seen, "patched": patched}},
            upsert=True,
        )
    except Exception:
        pass
    logger.info("[storage.migration] seen=%d patched=%d", seen, patched)
    return {"seen": seen, "patched": patched}
