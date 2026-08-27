"""Pickup photo workflow — fixed stage enum + completeness checker.

Locked by PO:
  before_loading  — фото відходів до завантаження
  after_loading   — фото після завантаження
  container       — фото тари / контейнерів
  transport       — фото транспорту з вантажем
  signed_act      — фото підписаного акту приймання

Pickup cannot move to ``delivered`` / ``completed`` without
``before_loading`` + ``after_loading`` + ``signed_act``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PHOTO_STAGES = (
    "before_loading",
    "after_loading",
    "container",
    "transport",
    "signed_act",
)

STAGE_LABELS = {
    "before_loading": "До завантаження",
    "after_loading":  "Після завантаження",
    "container":      "Контейнер",
    "transport":      "Транспорт",
    "signed_act":     "Підписаний акт",
}

REQUIRED_FOR_CLOSE = ("before_loading", "after_loading", "signed_act")

# Pickup statuses that require the full checklist before being allowed.
GUARDED_STATUSES = {"delivered", "completed", "closed", "done"}


def normalize_stage(value: Optional[str]) -> Optional[str]:
    v = (value or "").strip().lower()
    return v if v in PHOTO_STAGES else None


def ensure_allowed(value: Optional[str]) -> str:
    v = normalize_stage(value)
    if not v:
        raise ValueError(f"Невідома стадія фото. Допустимі: {', '.join(PHOTO_STAGES)}")
    return v


async def collect_present(db, pickup_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return {stage: [file_records]} for the given pickup."""
    out: Dict[str, List[Dict[str, Any]]] = {s: [] for s in PHOTO_STAGES}
    cursor = db["files"].find(
        {"pickup_id": pickup_id, "photo_stage": {"$in": list(PHOTO_STAGES)}, "status": "active"},
        {"_id": 0},
    ).sort("created_at", 1)
    async for f in cursor:
        stg = f.get("photo_stage")
        if stg in out:
            out[stg].append(f)
    return out


async def checklist(db, pickup_id: str) -> Dict[str, Any]:
    present_map = await collect_present(db, pickup_id)
    stages = []
    for s in PHOTO_STAGES:
        items = present_map.get(s) or []
        stages.append({
            "key": s,
            "label": STAGE_LABELS[s],
            "required": s in REQUIRED_FOR_CLOSE,
            "count": len(items),
            "present": bool(items),
        })
    missing = [s for s in REQUIRED_FOR_CLOSE if not present_map.get(s)]
    return {
        "stages": stages,
        "required": list(REQUIRED_FOR_CLOSE),
        "missing": missing,
        "can_close": len(missing) == 0,
    }
