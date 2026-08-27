"""
Wave 19 — Customer Portal View — auth dependencies.

Uses the existing staff auth (`security.require_user`). The customer_id is
always taken from the path — never trusted from the request body — and the
service layer enforces that the deal/doc/invoice belongs to that customer_id.
"""
from __future__ import annotations
from typing import Any, Dict

from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

# Reuse the canonical staff auth from the legacy security module.
from security import require_user  # type: ignore  # noqa: F401


def _db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialised on app.state")
    return db


async def resolve_customer(db: AsyncIOMotorDatabase, customer_id: str) -> Dict[str, Any]:
    """Locate the customer record. 404 if missing."""
    cust = await db.customers.find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"_id": 0, "password": 0},
    )
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    cust["customerId"] = cust.get("customerId") or cust.get("id") or cust.get("user_id") or customer_id
    return cust
