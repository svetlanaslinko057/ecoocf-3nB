"""
BIBI Cars — Block 6.2 — Lead SLA background worker
====================================================

Runs every 60s. Calls :func:`app.services.lead_sla.scan_overdue_leads`.
Idempotent — duplicate scans are safe (markers stop second-write).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("bibi.lead_sla.worker")


TICK_INTERVAL_SEC: int = 60


async def lead_sla_loop(db: Any) -> None:
    """Long-running scan loop. Exits only when cancelled by registry."""
    from app.services import lead_sla as svc

    logger.info("[lead_sla] worker starting (interval=%ss)", TICK_INTERVAL_SEC)
    while True:
        try:
            report = await svc.scan_overdue_leads(db)
            if any(report.get(k, 0) for k in ("reminded", "escalated", "auto_reassigned")):
                logger.info("[lead_sla] tick: %s", report)
        except asyncio.CancelledError:
            logger.info("[lead_sla] worker cancelled")
            raise
        except Exception as e:
            logger.warning("[lead_sla] tick failed: %s", e, exc_info=True)
        await asyncio.sleep(TICK_INTERVAL_SEC)


__all__ = ["lead_sla_loop", "TICK_INTERVAL_SEC"]
