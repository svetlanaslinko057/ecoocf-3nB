"""
PHASE SECURITY — Wave S2.2 — Staff object-ownership ACL.

Canonical, dependency-free helpers that decide whether a *staff* user may see a
given customer (and the customer-scoped objects hung off them: invoices, orders,
payments, deposits, ...). Mirrors the spec already used by server.py's
`_customer_scope_filter` / `_can_user_see_customer`, centralised here so new
route guards reuse ONE source of truth.

Role policy (Customer-Card spec):
  • admin / master_admin / owner → see everything
  • team_lead                    → see everything (team-scoping requires a team
                                    membership model that does not yet exist —
                                    tracked as an S2.2 residual)
  • manager                      → only customers where managerId == their id
  • anything else                → denied
"""
from __future__ import annotations

from typing import Any, Dict

_ALL_ACCESS_ROLES = ("admin", "master_admin", "owner")


def _staff_uid(user: Dict[str, Any]) -> str:
    return (
        user.get("id")
        or user.get("managerId")
        or user.get("staff_id")
        or user.get("email")
        or ""
    )


def staff_can_see_customer(user: Dict[str, Any], customer: Dict[str, Any]) -> bool:
    """True if `user` (a staff principal) may access `customer`'s data."""
    role = (user.get("role") or "").lower()
    if role in _ALL_ACCESS_ROLES:
        return True
    if role == "manager":
        uid = _staff_uid(user)
        return bool(uid) and customer.get("managerId") == uid
    return False


def customer_scope_filter(user: Dict[str, Any]) -> Dict[str, Any]:
    """Mongo filter fragment constraining a customers/managerId-bearing query."""
    role = (user.get("role") or "").lower()
    if role in _ALL_ACCESS_ROLES:
        return {}
    if role == "manager":
        uid = _staff_uid(user)
        if uid:
            return {"managerId": uid}
    return {"_id": "__deny__"}
