"""
customer_resolver.py — single source of truth for turning a customer_id (or a
document that references a customer) into a stable, UI-ready DTO.

The golden rule (per product spec):
  • Route/navigate ALWAYS by the stable `customer_id` (emails can change).
  • Display ALWAYS the human label: "Company — email"  (fallback "Name — email").
  • Never surface the raw customer_id as the primary text in the UI.

DTO shape (kept intentionally small & flat so it serialises cleanly to JSON):
  {
    id, full_name, email, phone,
    company_id, company_name,
    display_label,          # "ТОВ «Демо» — client@eco.ua"
    customer_360_url        # "/app/customers/<id>"  (frontend route)
  }
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _full_name(cust: Dict[str, Any]) -> str:
    if not cust:
        return ""
    name = (cust.get("name") or "").strip()
    if name:
        return name
    parts = [cust.get("surname"), cust.get("first_name"), cust.get("middle_name")]
    joined = " ".join(p.strip() for p in parts if p and str(p).strip())
    return joined.strip()


def build_dto(cust: Optional[Dict[str, Any]], *, fallback_id: str = "",
              fallback_email: str = "", fallback_name: str = "",
              fallback_company: str = "") -> Dict[str, Any]:
    """Build a customer DTO from a customer doc (or from loose fields when the
    customer record is missing — e.g. an orphaned invoice)."""
    cust = cust or {}
    cid = cust.get("id") or cust.get("customerId") or fallback_id or ""
    email = (cust.get("email") or fallback_email or "").strip()
    full_name = _full_name(cust) or (fallback_name or "").strip()
    company_name = (cust.get("company_name") or fallback_company or "").strip()
    company_id = cust.get("company_id") or ""

    # Human label — company first, then a personal name, then email, then id.
    primary = company_name or full_name
    if primary and email:
        label = f"{primary} — {email}"
    elif primary:
        label = primary
    elif email:
        label = email
    else:
        label = cid or "—"

    return {
        "id": cid,
        "full_name": full_name,
        "email": email,
        "phone": (cust.get("phone") or "").strip(),
        "company_id": company_id,
        "company_name": company_name,
        "display_label": label,
        "customer_360_url": f"/app/customers/{cid}" if cid else "",
    }


async def resolve_many(db, ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Resolve a batch of customer ids → {id: DTO}. Missing ids are omitted."""
    uniq = sorted({i for i in ids if i})
    if not uniq:
        return {}
    docs = await db.customers.find({"id": {"$in": uniq}}, {"_id": 0}).to_list(length=len(uniq))
    return {d["id"]: build_dto(d) for d in docs if d.get("id")}


async def resolve_one(db, customer_id: str) -> Optional[Dict[str, Any]]:
    if not customer_id:
        return None
    doc = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    return build_dto(doc, fallback_id=customer_id) if doc else None


async def search_customer_ids(db, q: str, scope_filter: Optional[Dict[str, Any]] = None,
                              limit: int = 200) -> List[str]:
    """Return customer ids whose name/email/company/phone match `q`.
    Optionally constrained by a scope filter (e.g. manager ownership)."""
    q = (q or "").strip()
    if not q:
        return []
    import re
    rx = {"$regex": re.escape(q), "$options": "i"}
    or_clauses = [
        {"email": rx}, {"name": rx}, {"first_name": rx}, {"surname": rx},
        {"company_name": rx}, {"phone": rx}, {"id": rx},
    ]
    flt: Dict[str, Any] = {"$or": or_clauses}
    if scope_filter:
        flt = {"$and": [scope_filter, flt]}
    docs = await db.customers.find(flt, {"_id": 0, "id": 1}).to_list(length=limit)
    return [d["id"] for d in docs if d.get("id")]
