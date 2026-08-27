"""Document lifecycle — state machine per entity_type.

Lifecycle is **separate** from the business-entity status (e.g. a Contract
row may sit in ``signed`` while its Document goes ``draft → generated →
sent → signed → archived``). It is stored in ``entity_documents`` keyed by
``(entity_type, entity_id)``.

Defined transitions (locked by PO):

  Contract: draft → generated → sent → signed → archived
  Act:      draft → generated → sent → signed → archived
  Invoice:  draft → generated → sent → paid → archived
  Pickup:   draft → generated → sent → signed → archived (uses same as contract/act)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ENTITY_DOCUMENTS = "entity_documents"

LIFECYCLES: Dict[str, Tuple[str, ...]] = {
    "contract": ("draft", "generated", "sent", "signed", "archived"),
    "act":      ("draft", "generated", "sent", "signed", "archived"),
    "invoice":  ("draft", "generated", "sent", "paid",   "archived"),
    "pickup":   ("draft", "generated", "sent", "signed", "archived"),
}

UKR_LABELS = {
    "draft":     "Чернетка",
    "generated": "Згенеровано",
    "sent":      "Надіслано",
    "signed":    "Підписано",
    "paid":      "Сплачено",
    "archived":  "Архів",
}


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def labels_for(entity_type: str) -> List[Dict[str, str]]:
    states = LIFECYCLES.get(entity_type) or LIFECYCLES["contract"]
    return [{"key": s, "label": UKR_LABELS.get(s, s)} for s in states]


def can_transition(entity_type: str, from_state: str, to_state: str) -> bool:
    states = LIFECYCLES.get(entity_type)
    if not states or to_state not in states:
        return False
    if from_state == to_state:
        return False
    # forward-only transitions; allow direct jump to ``archived`` from any state
    if to_state == "archived":
        return True
    try:
        i = states.index(from_state)
        j = states.index(to_state)
        # Allow moving forward by 1 step OR direct to terminal archived.
        return j == i + 1
    except ValueError:
        # Unknown source — only ``draft → next`` is allowed.
        return from_state in (None, "", "draft") and to_state in states


class LifecycleRepository:
    def __init__(self, db) -> None:
        self.db = db

    @staticmethod
    def _scope(entity_type: str, entity_id: str) -> Dict[str, Any]:
        return {"entity_type": entity_type, "entity_id": entity_id}

    async def get(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        doc = await self.db[ENTITY_DOCUMENTS].find_one(
            self._scope(entity_type, entity_id), {"_id": 0}
        )
        if not doc:
            doc = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "status": "draft",
                "history": [],
            }
        doc["available"] = LIFECYCLES.get(entity_type, ())
        doc["labels"] = labels_for(entity_type)
        return doc

    async def mark(self, entity_type: str, entity_id: str, *, status: str, by: Optional[str], note: Optional[str] = None, file_id: Optional[str] = None) -> Dict[str, Any]:
        """Idempotently set lifecycle state. Used by PDF regenerate to stamp
        ``generated`` without involving the transition validator (system event).
        """
        now = _iso()
        await self.db[ENTITY_DOCUMENTS].update_one(
            self._scope(entity_type, entity_id),
            {
                "$set": {**self._scope(entity_type, entity_id), "status": status, "updated_at": now, "current_file_id": file_id},
                "$push": {"history": {"at": now, "to": status, "by": by, "note": note, "file_id": file_id}},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return await self.get(entity_type, entity_id)

    async def transition(self, entity_type: str, entity_id: str, *, to_state: str, by: Optional[str], note: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        cur = await self.get(entity_type, entity_id)
        if not can_transition(entity_type, cur.get("status") or "draft", to_state):
            return False, cur
        new = await self.mark(entity_type, entity_id, status=to_state, by=by, note=note)
        return True, new
