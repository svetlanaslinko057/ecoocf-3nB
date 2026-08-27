"""
app.services.customers
=======================

Customer-domain helpers for the client cabinet.

Production data mode
--------------------
This module contains **no demo/mock seeding**. The cabinet always reflects the
customer's real business state:

  * ``ensure_customer_record`` guarantees a minimal customer document exists so
    cabinet endpoints don't 404 — it never fabricates orders, invoices,
    contracts, shipments, carfax, notifications or timeline events.
  * ``require_customer`` resolves the Bearer session into a customer doc.

If a customer has no business data yet, every cabinet endpoint simply returns
empty arrays / zero counters, and the frontend renders production empty states.
Business entities are created exclusively by real business actions elsewhere in
the system — never automatically for presentation purposes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

# Canonical runtime DB accessor — published by server.py at module-load.
from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.customers")


__all__ = ["require_customer", "ensure_customer_record"]


def _db():
    """Lazy Motor handle resolver."""
    return get_db()


async def _resolve_bearer(authorization: Optional[str]):
    """Lazy bridge to the auth-core resolver that lives in ``server.py``."""
    from server import _resolve_bearer as _server_resolve_bearer
    return await _server_resolve_bearer(authorization)


async def ensure_customer_record(customer_id: str) -> None:
    """Guarantee a minimal REAL customer document exists — WITHOUT any business
    history. Used by cabinet endpoints so look-ups by id don't 404, while the
    cabinet stays empty until real activity occurs.

    We intentionally do NOT fabricate profile fields here; real profile data
    (name/email/phone) comes from the registration / Google-auth flow.
    """
    try:
        existing = await _db().customers.find_one({'id': customer_id}, {'_id': 0, 'id': 1})
        if existing:
            return
        now = datetime.now(timezone.utc)
        await _db().customers.update_one(
            {'id': customer_id},
            {'$setOnInsert': {
                'id': customer_id,
                'customerId': customer_id,
                'role': 'customer',
                'status': 'active',
                'createdAt': now,
                'updatedAt': now,
            }},
            upsert=True,
        )
    except Exception:
        logger.exception(f"[CABINET] ensure_customer_record failed for {customer_id}")


async def require_customer(authorization: Optional[str]) -> Dict[str, Any]:
    """Resolve the Bearer session into a customer doc; 401 if missing/expired."""
    customer = await _resolve_bearer(authorization)
    if not customer:
        raise HTTPException(status_code=401, detail="Authentication required")
    return customer
