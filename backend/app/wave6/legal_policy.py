"""
Wave 6 — Legal Policy settings (small, focused config).

This is intentionally a *configuration* page, NOT a workflow page. It lives at
``/api/admin/settings/legal-policy`` and exposes exactly five fields:

  * default_fx_usd_to_eur
  * min_deposit_eur
  * deposit_percent_of_max_bid
  * refund_deadline_days
  * invoice_template_id

It stores the doc in ``app_settings`` under key ``legal_policy`` so that it
lives alongside other small admin configs (mirrors the existing
``SettingsService`` pattern).

Note: This module does NOT replace the operational ``LegalWorkflowPage`` /
``/api/legal/*`` endpoints. Those are workspace endpoints (deposits, stages,
contracts). This one is policy / defaults only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator

logger = logging.getLogger("bibi.wave6.legal_policy")

COLLECTION = "app_settings"
SETTINGS_KEY = "legal_policy"

DEFAULTS: Dict[str, Any] = {
    "default_fx_usd_to_eur":         0.92,
    "min_deposit_eur":               1000,
    "deposit_percent_of_max_bid":    10,        # i.e. 10%
    "refund_deadline_days":          30,
    "invoice_template_id":           "default",
}


class LegalPolicyIn(BaseModel):
    default_fx_usd_to_eur: float = Field(..., gt=0, lt=10)
    min_deposit_eur: float = Field(..., ge=0, le=1_000_000)
    deposit_percent_of_max_bid: float = Field(..., ge=0, le=100)
    refund_deadline_days: int = Field(..., ge=0, le=3650)
    invoice_template_id: str = Field(..., min_length=1, max_length=200)

    @validator("invoice_template_id")
    def _strip(cls, v: str) -> str:
        return v.strip()


async def get_policy(db) -> Dict[str, Any]:
    """Return the current policy. Falls back to DEFAULTS on first read and
    persists them so the doc exists on the next call."""
    try:
        doc = await db[COLLECTION].find_one({"key": SETTINGS_KEY}, {"_id": 0})
    except Exception as e:
        logger.warning("[legal_policy] read failed: %s", e)
        doc = None

    if doc and isinstance(doc.get("value"), dict):
        merged = {**DEFAULTS, **doc["value"]}
        merged["updated_at"] = doc.get("updated_at")
        merged["updated_by"] = doc.get("updated_by")
        return merged

    # Seed defaults
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db[COLLECTION].update_one(
            {"key": SETTINGS_KEY},
            {"$set": {
                "key": SETTINGS_KEY,
                "value": DEFAULTS,
                "updated_at": now,
                "updated_by": "system",
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("[legal_policy] seed failed: %s", e)
    return {**DEFAULTS, "updated_at": now, "updated_by": "system"}


async def set_policy(db, payload: LegalPolicyIn, by_email: Optional[str]) -> Dict[str, Any]:
    """Replace the whole policy. Atomic upsert."""
    value = payload.dict()
    now = datetime.now(timezone.utc).isoformat()
    await db[COLLECTION].update_one(
        {"key": SETTINGS_KEY},
        {"$set": {
            "key": SETTINGS_KEY,
            "value": value,
            "updated_at": now,
            "updated_by": by_email or "admin",
        }},
        upsert=True,
    )
    return {**value, "updated_at": now, "updated_by": by_email or "admin"}
