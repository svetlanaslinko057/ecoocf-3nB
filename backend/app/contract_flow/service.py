"""Universal contract flow — business logic.

Reuses existing customers/companies/notifications; never duplicates the
Contract Execution Engine. Operates on its own collections so any template can
be attached later through the admin UI without touching domain logic.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db
from . import constants as K
from . import legal_profile as LP
from . import variables as V

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def ensure_indexes() -> None:
    db = get_db()
    if db is None:
        return
    await db[K.C_TYPES].create_index("id", unique=True)
    await db[K.C_TEMPLATES].create_index("id", unique=True)
    await db[K.C_CONTRACTS].create_index("id", unique=True)
    await db[K.C_CONTRACTS].create_index("customer_id")
    await db[K.C_FILES].create_index("id", unique=True)


async def get_settings() -> Dict[str, Any]:
    db = get_db()
    doc = await db[K.C_SETTINGS].find_one({"id": "default"}, {"_id": 0})
    if not doc:
        doc = {
            "id": "default",
            "iban": "UA00 0000 0000 0000 0000 0000 0000",
            "recipient_name": "ТОВ «ЕКО.НОВА»",
            "recipient_edrpou": "00000000",
            "bank_name": "АТ «БАНК»",
            "payment_terms": "Оплата протягом 5 банківських днів з дати виставлення рахунку.",
            "vat_number": "",
        }
        await db[K.C_SETTINGS].insert_one(dict(doc))
    return doc


async def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    patch = {k: v for k, v in (patch or {}).items() if k != "id"}
    await db[K.C_SETTINGS].update_one({"id": "default"}, {"$set": patch}, upsert=True)
    return await get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Customer / company resolution + legal profile
# ─────────────────────────────────────────────────────────────────────────────

async def resolve_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db[K.C_CUSTOMERS].find_one(
        {"$or": [{"id": customer_id}, {"customerId": customer_id}, {"user_id": customer_id}]},
        {"_id": 0},
    )


async def _linked_company(customer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    db = get_db()
    cid = customer.get("company_id") or customer.get("companyId")
    if cid:
        c = await db[K.C_COMPANIES].find_one({"id": cid}, {"_id": 0})
        if c:
            return c
    name = (customer.get("company_name") or "").strip()
    if name:
        return await db[K.C_COMPANIES].find_one({"name": name}, {"_id": 0})
    return None


async def legal_profile_for(customer_id: str) -> Dict[str, Any]:
    customer = await resolve_customer(customer_id)
    if not customer:
        return {"error": "customer_not_found"}
    company = await _linked_company(customer)
    out = LP.profile_and_validation(customer, company)
    out["customer_id"] = customer.get("id") or customer_id
    out["customer_name"] = customer.get("name")
    out["labels"] = {f: K.PROFILE_FIELD_LABELS_UK.get(f, f)
                     for f in (K.REQUIRED_PROFILE_FIELDS + K.OPTIONAL_PROFILE_FIELDS)}
    return out


async def update_legal_profile(customer_id: str, patch: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    """Write requisites onto the customer's ``legal_profile`` sub-doc with audit."""
    db = get_db()
    customer = await resolve_customer(customer_id)
    if not customer:
        raise ValueError("customer_not_found")
    allowed = set(K.REQUIRED_PROFILE_FIELDS) | set(K.OPTIONAL_PROFILE_FIELDS)
    before = customer.get("legal_profile") or {}
    changes = {}
    new_lp = dict(before)
    for k, v in (patch or {}).items():
        if k in allowed:
            val = ("" if v is None else str(v)).strip()
            if new_lp.get(k, "") != val:
                changes[k] = {"before": before.get(k, ""), "after": val}
                new_lp[k] = val
    await db[K.C_CUSTOMERS].update_one(
        {"id": customer.get("id")},
        {"$set": {"legal_profile": new_lp}},
    )
    if changes:
        await db["cflow_audit"].insert_one({
            "id": _id("aud"), "entity": "legal_profile", "customer_id": customer.get("id"),
            "actor": actor, "at": V.now_iso(), "changes": changes,
        })
        # A change to legal data propagates to the customer's contracts. Material
        # legal changes on an IN-FORCE contract create a revision (re-acceptance);
        # non-in-force contracts are regenerated in place.
        changed_keys = list(changes.keys())
        before_map = {k: changes[k]["before"] for k in changes}
        after_map = {k: changes[k]["after"] for k in changes}
        await _apply_legal_change_to_contracts(
            customer.get("id"), changed_keys, before_map, after_map,
            reason="Оновлено юридичні реквізити")
    return await legal_profile_for(customer.get("id"))


# ─────────────────────────────────────────────────────────────────────────────
# Contract Types
# ─────────────────────────────────────────────────────────────────────────────

async def list_types(active: Optional[bool] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if active is not None:
        q["active"] = active
    return await db[K.C_TYPES].find(q, {"_id": 0}).sort("created_at", -1).to_list(length=200)


async def create_type(data: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    db = get_db()
    doc = {
        "id": _id("ctype"),
        "name": (data.get("name") or "").strip() or "Без назви",
        "code": (data.get("code") or "").strip(),
        "description": data.get("description", ""),
        "service_ids": data.get("service_ids", []),
        "waste_category_ids": data.get("waste_category_ids", []),
        "active": bool(data.get("active", True)),
        "default_template_id": data.get("default_template_id"),
        "invoice_scope": data.get("invoice_scope", "final"),
        "acceptance_policy": data.get("acceptance_policy", "full_profile"),
        "required_profile_fields": data.get("required_profile_fields") or list(K.REQUIRED_PROFILE_FIELDS),
        "required_documents": data.get("required_documents", []),
        "variables_schema": data.get("variables_schema", []),
        "created_at": V.now_iso(), "updated_at": V.now_iso(), "created_by": actor,
    }
    await db[K.C_TYPES].insert_one(dict(doc))
    return doc


async def update_type(type_id: str, patch: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    db = get_db()
    patch = {k: v for k, v in (patch or {}).items() if k not in ("id", "created_at", "created_by")}
    patch["updated_at"] = V.now_iso()
    await db[K.C_TYPES].update_one({"id": type_id}, {"$set": patch})
    return await db[K.C_TYPES].find_one({"id": type_id}, {"_id": 0})


async def delete_type(type_id: str) -> None:
    await get_db()[K.C_TYPES].delete_one({"id": type_id})


async def get_type(type_id: str) -> Optional[Dict[str, Any]]:
    return await get_db()[K.C_TYPES].find_one({"id": type_id}, {"_id": 0})


# ─────────────────────────────────────────────────────────────────────────────
# Template library
# ─────────────────────────────────────────────────────────────────────────────

async def list_templates(type_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if type_id:
        q["contract_type_id"] = type_id
    if status:
        q["status"] = status
    return await db[K.C_TEMPLATES].find(q, {"_id": 0, "html": 0}).sort("updated_at", -1).to_list(length=200)


async def get_template(template_id: str, *, with_html: bool = True) -> Optional[Dict[str, Any]]:
    proj = {"_id": 0} if with_html else {"_id": 0, "html": 0}
    tpl = await get_db()[K.C_TEMPLATES].find_one({"id": template_id}, proj)
    if tpl:
        return tpl
    # Fallback to seeded document_templates (existing HTML library)
    if with_html:
        legacy = await get_db()[K.C_DOC_TEMPLATES].find_one({"id": template_id}, {"_id": 0})
        if legacy:
            return {
                "id": legacy["id"], "name": legacy.get("name"), "format": "html",
                "language": legacy.get("language", "uk"), "status": "active",
                "html": legacy.get("html", ""), "variables_schema": [],
                "contract_type_id": None, "version": 1, "source": "document_templates",
            }
    return None


async def create_template(data: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    db = get_db()
    html = data.get("html") or ""
    doc = {
        "id": _id("tpl"),
        "name": (data.get("name") or "").strip() or "Шаблон",
        "contract_type_id": data.get("contract_type_id"),
        "language": data.get("language", "uk"),
        "format": data.get("format", "html"),  # html | docx | pdf
        "version": int(data.get("version", 1)),
        "status": data.get("status", "draft"),  # draft | active | archived
        "html": html,
        "source_file_id": data.get("source_file_id"),
        "variables_schema": data.get("variables_schema", []),
        "required_fields": data.get("required_fields", []),
        "service_ids": data.get("service_ids", []),
        "checksum": V.checksum(html),
        "created_by": actor, "approved_by": data.get("approved_by"),
        "created_at": V.now_iso(), "updated_at": V.now_iso(),
    }
    await db[K.C_TEMPLATES].insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def update_template(template_id: str, patch: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    db = get_db()
    patch = {k: v for k, v in (patch or {}).items() if k not in ("id", "created_at", "created_by")}
    if "html" in patch:
        patch["checksum"] = V.checksum(patch.get("html") or "")
    patch["updated_at"] = V.now_iso()
    await db[K.C_TEMPLATES].update_one({"id": template_id}, {"$set": patch})
    return await get_template(template_id)


async def delete_template(template_id: str) -> None:
    await get_db()[K.C_TEMPLATES].delete_one({"id": template_id})


async def _pick_template_for(ctype: Optional[Dict[str, Any]], template_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if template_id:
        tpl = await get_template(template_id)
        if tpl:
            return tpl
    if ctype and ctype.get("default_template_id"):
        tpl = await get_template(ctype["default_template_id"])
        if tpl:
            return tpl
    # active template bound to the type
    db = get_db()
    if ctype:
        tpl = await db[K.C_TEMPLATES].find_one(
            {"contract_type_id": ctype["id"], "status": "active"}, {"_id": 0})
        if tpl:
            return tpl
    # any active template
    tpl = await db[K.C_TEMPLATES].find_one({"status": "active"}, {"_id": 0})
    return tpl


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────

async def _notify_staff(title: str, body: str, *, kind: str, meta: Dict[str, Any] | None = None) -> None:
    db = get_db()
    try:
        await db[K.C_STAFF_NOTIF].insert_one({
            "id": _id("wn"), "audiences": ["staff", "admin"], "read_by": [],
            "kind": kind, "title": title, "body": body, "meta": meta or {},
            "created_at": V.now_iso(),
        })
    except Exception:
        pass


async def _notify_client(customer_id: str, title: str, body: str, *, kind: str, meta: Dict[str, Any] | None = None) -> None:
    db = get_db()
    try:
        await db[K.C_CLIENT_NOTIF].insert_one({
            "id": _id("cn"), "customerId": customer_id, "userId": customer_id,
            "read": False, "isRead": False, "type": kind, "kind": kind,
            "title": title, "message": body, "body": body, "meta": meta or {},
            "created_at": V.now_iso(), "createdAt": V.now_iso(),
        })
    except Exception:
        pass


async def _email_best_effort(to: str, subject: str, body: str, *, contract_id: str) -> None:
    """Best-effort e-mail via the existing outbox; never claims delivery."""
    db = get_db()
    try:
        await db["email_outbox"].insert_one({
            "id": _id("mail"), "to": to, "subject": subject, "body": body,
            "status": "queued", "transport": "best_effort",
            "meta": {"contract_id": contract_id}, "created_at": V.now_iso(),
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Contract generation (immutable versions)
# ─────────────────────────────────────────────────────────────────────────────

async def _build_generation(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Render current template with current data → version payload + gates."""
    customer = await resolve_customer(contract["customer_id"]) or {}
    company = await _linked_company(customer)
    profile = LP.build_profile(customer, company)
    validation = LP.validate_profile(profile)

    ctype = await get_type(contract.get("contract_type_id")) if contract.get("contract_type_id") else None
    tpl = await _pick_template_for(ctype, contract.get("template_id"))

    settings = await get_settings()
    payment = dict(contract.get("payment") or {})
    payment.setdefault("iban", settings.get("iban"))
    payment.setdefault("recipient_name", settings.get("recipient_name"))
    payment.setdefault("recipient_edrpou", settings.get("recipient_edrpou"))
    payment.setdefault("bank_name", settings.get("bank_name"))
    payment.setdefault("terms", settings.get("payment_terms"))

    catalog = None
    if tpl and tpl.get("variables_schema"):
        catalog = tpl["variables_schema"]
    elif ctype and ctype.get("variables_schema"):
        catalog = ctype["variables_schema"]

    ctx = V.build_context(
        profile=profile, customer=customer, contract=contract,
        ctype=ctype, payment=payment, custom_vars=contract.get("custom_vars") or {},
    )
    html_src = (tpl or {}).get("html") or _fallback_html()
    rendered, missing_vars = V.render_template(html_src, ctx, catalog)
    required_missing = [m for m in missing_vars if m.get("required")]

    return {
        "profile": profile,
        "validation": validation,
        "template_id": (tpl or {}).get("id"),
        "template_name": (tpl or {}).get("name"),
        "rendered_html": rendered,
        "checksum": V.checksum(rendered),
        "missing_variables": missing_vars,
        "required_missing_variables": required_missing,
        "payment": payment,
    }


def _acceptance_gate(validation: Dict[str, Any], required_missing: List[Dict[str, Any]]) -> Dict[str, Any]:
    reasons: List[str] = []
    for f in validation.get("missing_fields", []):
        reasons.append(K.PROFILE_FIELD_LABELS_UK.get(f, f))
    for f in validation.get("invalid_fields", []):
        reasons.append(f"{K.PROFILE_FIELD_LABELS_UK.get(f, f)} (некоректно)")
    for m in required_missing:
        reasons.append(m.get("label", m.get("key")))
    can_accept = validation.get("complete", False) and len(required_missing) == 0
    return {"can_accept": can_accept, "reasons": reasons}


def _version_by_no(versions: List[Dict[str, Any]], no: Any) -> Optional[Dict[str, Any]]:
    for v in versions:
        if v.get("version") == no:
            return v
    return versions[-1] if versions else None


def _public_contract(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    versions = d.get("versions") or []
    # ``current`` = the legally in-force edition. For a contract that never
    # reached in-force, this is simply the latest generated version.
    active_no = d.get("active_version")
    if active_no is not None:
        d["current"] = _version_by_no(versions, active_no)
    elif versions:
        d["current"] = versions[-1]
    # A pending revision (if any) is exposed separately so the UI never shows
    # it as the in-force document until it is re-accepted + approved.
    rev = d.get("revision")
    if rev:
        d["revision_document"] = _version_by_no(versions, rev.get("version"))
        rev["status_label"] = {
            "pending_acceptance": "Очікує повторного погодження",
            "accepted": "Погоджено — очікує затвердження",
            "awaiting_payment": "Очікує коригувальну оплату",
            "payment_confirmed": "Оплату підтверджено — очікує затвердження",
        }.get(rev.get("status"), rev.get("status"))
        rev_pay = rev.get("payment") or {}
        rev["payment_status_label"] = K.PAYMENT_STATUS_LABELS_UK.get(rev_pay.get("status"), rev_pay.get("status"))
    d["status_label"] = K.STATUS_LABELS_UK.get(d.get("status"), d.get("status"))
    pay = d.get("payment") or {}
    d["payment_status_label"] = K.PAYMENT_STATUS_LABELS_UK.get(pay.get("status"), pay.get("status"))
    return d


def _material_changes(changed_fields: Optional[List[str]]) -> List[str]:
    """Filter a list of changed field keys down to the legally-material ones."""
    if not changed_fields:
        return []
    return [f for f in changed_fields if f in K.ALL_MATERIAL_FIELDS]


def _is_in_force(doc: Dict[str, Any]) -> bool:
    return doc.get("status") in K.IN_FORCE_STATES and bool(doc.get("acceptance"))


def _payment_impacting(changed_fields: List[str]) -> bool:
    return any(f in K.PAYMENT_IMPACT_FIELDS for f in (changed_fields or []))


async def create_contract(data: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    db = get_db()
    customer_id = data.get("customer_id")
    customer = await resolve_customer(customer_id) if customer_id else None
    if not customer:
        raise ValueError("customer_not_found")
    cid = customer.get("id")

    num = data.get("number") or f"CT-{V.now_iso()[:10].replace('-', '')}-{uuid.uuid4().hex[:4].upper()}"
    doc: Dict[str, Any] = {
        "id": _id("cflow"),
        "number": num,
        "customer_id": cid,
        "customer_name": customer.get("name"),
        "contract_type_id": data.get("contract_type_id"),
        "template_id": data.get("template_id"),
        "service_id": data.get("service_id"),
        "service_name": data.get("service_name"),
        "title": data.get("title") or "Договір",
        "date": V.now_iso()[:10],
        "valid_from": data.get("valid_from"),
        "valid_to": data.get("valid_to"),
        "value": data.get("value") or data.get("amount"),
        "currency": data.get("currency", "UAH"),
        "custom_vars": data.get("custom_vars") or {},
        "status": "draft",
        "versions": [],
        "acceptance": None,
        "payment": {"status": "not_invoiced"},
        "approval": None,
        "events": [],
        "created_by": actor,
        "created_at": V.now_iso(), "updated_at": V.now_iso(),
    }
    await db[K.C_CONTRACTS].insert_one(dict(doc))
    # generate first version
    return await regenerate(doc["id"], actor=actor, reason="Первинна генерація")


async def _load(contract_id: str) -> Dict[str, Any]:
    doc = await get_db()[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not doc:
        raise ValueError("contract_not_found")
    return doc


async def regenerate(contract_id: str, *, actor: str, reason: str = "Регенерація",
                     changed_fields: Optional[List[str]] = None,
                     before: Optional[Dict[str, Any]] = None,
                     after: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Regenerate a contract document.

    Behaviour depends on whether the contract is already in force (has an
    accepted, legally-binding edition):

      * NOT in force  → the current draft/review version is replaced in place
        and any prior (non-binding) acceptance is reset. This is the original
        pre-acceptance flow.
      * In force + MATERIAL change → a new immutable REVISION is created that
        requires re-acceptance (and re-payment when the change affects money).
        The in-force edition stays intact and legally valid until the revision
        is approved. This removes the old contradiction where an active
        contract could lose its acceptance yet remain ``active``.
      * In force + NON-material change → the in-force version's rendered HTML is
        refreshed in place WITHOUT touching acceptance or status.
    """
    doc = await _load(contract_id)

    if _is_in_force(doc):
        material = _material_changes(changed_fields)
        # A manual regenerate (no explicit field list) on an in-force contract
        # is treated conservatively as a material revision.
        if changed_fields is None:
            material = ["manual_regeneration"]
        if not material:
            return await _refresh_inforce_version(doc, actor=actor, reason=reason)
        return await _create_revision(doc, actor=actor, reason=reason,
                                      changed_fields=material, before=before, after=after)

    # ── Non-in-force: original in-place regeneration ────────────────────────
    db = get_db()
    gen = await _build_generation(doc)
    gate = _acceptance_gate(gen["validation"], gen["required_missing_variables"])

    versions = doc.get("versions") or []
    version_no = len(versions) + 1
    prev = versions[-1] if versions else None
    version = {
        "version": version_no,
        "parent_version_id": (prev or {}).get("version"),
        "template_id": gen["template_id"],
        "template_name": gen["template_name"],
        "html": gen["rendered_html"],
        "checksum": gen["checksum"],
        "missing_variables": gen["missing_variables"],
        "profile_snapshot": gen["profile"],
        "validation": gen["validation"],
        "can_accept": gate["can_accept"],
        "blocking_reasons": gate["reasons"],
        "changed_fields": _material_changes(changed_fields),
        "before": before or {},
        "after": after or {},
        "change_reason": reason,
        "acceptance_required": True,
        "payment_required": _payment_impacting(changed_fields or []),
        "accepted_by": None, "accepted_at": None,
        "approved_by": None, "approved_at": None,
        "superseded_version_id": None,
        "at": V.now_iso(), "by": actor, "reason": reason,
        "status": "current",
    }
    for v in versions:
        v["status"] = "replaced"
    versions.append(version)

    new_status = doc.get("status")
    if new_status in ("draft",):
        new_status = "generated"
    updates = {
        "versions": versions,
        "current_version": version_no,
        "active_version": version_no,
        "payment": {**(doc.get("payment") or {}), **{k: gen["payment"].get(k) for k in
                    ("iban", "recipient_name", "recipient_edrpou", "bank_name", "terms")}},
        "acceptance": None,
        "updated_at": V.now_iso(),
    }
    if doc.get("status") in ("sent_for_review", "awaiting_profile", "ready_for_acceptance",
                             "accepted", "awaiting_payment"):
        updates["status"] = "ready_for_acceptance" if gate["can_accept"] else "awaiting_profile"
    else:
        updates["status"] = new_status
    updates.setdefault("payment", {}).setdefault("status", (doc.get("payment") or {}).get("status", "not_invoiced"))

    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": updates})
    await _event(contract_id, "generated", actor, reason)
    return _public_contract(await _load(contract_id))


async def _refresh_inforce_version(doc: Dict[str, Any], *, actor: str, reason: str) -> Dict[str, Any]:
    """Re-render the in-force version's HTML in place for a NON-material change.

    Acceptance, payment and status are untouched — the edition remains legally
    binding. Used e.g. when a purely cosmetic/optional field changes.
    """
    db = get_db()
    gen = await _build_generation(doc)
    versions = doc.get("versions") or []
    active_no = doc.get("active_version") or (versions[-1]["version"] if versions else 1)
    for v in versions:
        if v.get("version") == active_no:
            v["html"] = gen["rendered_html"]
            v["checksum"] = gen["checksum"]
            v["missing_variables"] = gen["missing_variables"]
            v["profile_snapshot"] = gen["profile"]
            v["refreshed_at"] = V.now_iso()
    await db[K.C_CONTRACTS].update_one(
        {"id": doc["id"]}, {"$set": {"versions": versions, "updated_at": V.now_iso()}})
    await _audit(doc["id"], "version_refresh", actor,
                 {"reason": reason, "version": active_no, "material": False})
    return _public_contract(await _load(doc["id"]))


async def _create_revision(doc: Dict[str, Any], *, actor: str, reason: str,
                           changed_fields: List[str],
                           before: Optional[Dict[str, Any]] = None,
                           after: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create an immutable revision of an IN-FORCE contract.

    The current in-force version is preserved and marked ``superseded_pending``
    (still the legally-valid edition). A new version is appended with status
    ``revision_pending`` and the contract moves to
    ``revision_pending_acceptance`` — it CANNOT be treated as fully active until
    the client re-accepts (and re-pays if the change is payment-impacting) and a
    manager approves the revision.
    """
    db = get_db()
    contract_id = doc["id"]
    gen = await _build_generation(doc)
    gate = _acceptance_gate(gen["validation"], gen["required_missing_variables"])

    versions = doc.get("versions") or []
    active_no = doc.get("active_version") or (versions[-1]["version"] if versions else 1)
    version_no = len(versions) + 1
    pay_impact = _payment_impacting(changed_fields)

    revision_version = {
        "version": version_no,
        "parent_version_id": active_no,
        "template_id": gen["template_id"],
        "template_name": gen["template_name"],
        "html": gen["rendered_html"],
        "checksum": gen["checksum"],
        "missing_variables": gen["missing_variables"],
        "profile_snapshot": gen["profile"],
        "validation": gen["validation"],
        "can_accept": gate["can_accept"],
        "blocking_reasons": gate["reasons"],
        "changed_fields": changed_fields,
        "before": before or {},
        "after": after or {},
        "change_reason": reason,
        "acceptance_required": True,
        "payment_required": pay_impact,
        "accepted_by": None, "accepted_at": None,
        "approved_by": None, "approved_at": None,
        "superseded_version_id": None,
        "at": V.now_iso(), "by": actor, "reason": reason,
        "status": "revision_pending",
    }
    # Mark the in-force version as "superseded_pending" so history is explicit,
    # but keep active_version pointing at it (still legally valid).
    for v in versions:
        if v.get("version") == active_no:
            v["status"] = "superseded_pending"
    versions.append(revision_version)

    revision = {
        "version": version_no,
        "status": "pending_acceptance",
        "acceptance": None,
        "payment_required": pay_impact,
        "payment": {"status": "not_invoiced"} if pay_impact else None,
        "changed_fields": changed_fields,
        "before": before or {},
        "after": after or {},
        "change_reason": reason,
        "created_by": actor,
        "created_at": V.now_iso(),
        "opened_at": None,
    }
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {
            "versions": versions,
            "revision": revision,
            "status": "revision_pending_acceptance",
            "updated_at": V.now_iso(),
        }},
    )
    await _audit(contract_id, "revision_created", actor, {
        "version": version_no, "parent_version_id": active_no,
        "changed_fields": changed_fields, "payment_required": pay_impact,
        "reason": reason,
    })
    await _event(contract_id, "revision_created", actor,
                 f"Створено нову редакцію (v{version_no}). Потрібне повторне ознайомлення.")
    await _notify_client(doc["customer_id"], "Підготовлено нову редакцію договору",
                         f"За договором №{doc.get('number')} підготовлено нову редакцію. "
                         f"Будь ласка, ознайомтеся та повторно погодьте умови.",
                         kind="contract_revision", meta={"contract_id": contract_id, "version": version_no})
    await _notify_staff("Створено нову редакцію договору",
                        f"Договір №{doc.get('number')}: нова редакція v{version_no} очікує повторного погодження клієнтом.",
                        kind="contract_revision", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


async def patch_contract(contract_id: str, patch: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    patch = patch or {}
    material_allowed = set(K.MATERIAL_CONTRACT_FIELDS)
    non_material = set(K.NON_MATERIAL_FIELDS)

    upd: Dict[str, Any] = {}
    changed_material: List[str] = []
    before: Dict[str, Any] = {}
    after: Dict[str, Any] = {}
    nm_changed: Dict[str, Any] = {}
    for k, v in patch.items():
        if k in material_allowed:
            if doc.get(k) != v:
                changed_material.append(k)
                before[k] = doc.get(k)
                after[k] = v
            upd[k] = v
        elif k in non_material:
            if doc.get(k) != v:
                nm_changed[k] = {"before": doc.get(k), "after": v}
            upd[k] = v
    if upd:
        upd["updated_at"] = V.now_iso()
        await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": upd})
    if nm_changed:
        # Non-material (internal/technical) change — NEVER resets acceptance.
        await _audit(contract_id, "non_material_change", actor, {"changes": nm_changed})
        await _event(contract_id, "non_material_change", actor,
                     "Оновлено службові поля (без повторного погодження)")
    if changed_material:
        # Material change → regenerate (creates a revision if in force).
        return await regenerate(contract_id, actor=actor, reason="Зміна параметрів договору",
                                changed_fields=changed_material, before=before, after=after)
    return _public_contract(await _load(contract_id))


async def send_for_review(contract_id: str, *, actor: str) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    versions = doc.get("versions") or []
    cur = versions[-1] if versions else {}
    status = "ready_for_acceptance" if cur.get("can_accept") else "awaiting_profile"
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"status": status, "sent_at": V.now_iso(), "updated_at": V.now_iso()}},
    )
    await _event(contract_id, "sent_for_review", actor, "Надіслано клієнту")
    await _notify_client(doc["customer_id"], "Договір на ознайомлення",
                         f"Вам надіслано договір №{doc.get('number')} для ознайомлення.",
                         kind="contract_sent", meta={"contract_id": contract_id})
    cust = await resolve_customer(doc["customer_id"]) or {}
    if cust.get("email"):
        await _email_best_effort(cust["email"], f"Договір №{doc.get('number')}",
                                 "Договір надіслано на ознайомлення у вашому кабінеті.",
                                 contract_id=contract_id)
    return _public_contract(await _load(contract_id))


# ─────────────────────────────────────────────────────────────────────────────
# Client acceptance
# ─────────────────────────────────────────────────────────────────────────────

async def mark_opened(contract_id: str, customer_id: str) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    if doc["customer_id"] != customer_id:
        raise PermissionError("forbidden")
    sets = {"opened_at": doc.get("opened_at") or V.now_iso(), "updated_at": V.now_iso()}
    rev = doc.get("revision")
    if rev and not rev.get("opened_at"):
        sets["revision.opened_at"] = V.now_iso()
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": sets})
    await _event(contract_id, "opened", customer_id, "Клієнт відкрив договір")
    return _public_contract(await _load(contract_id))


async def accept_contract(contract_id: str, customer_id: str, *, ip: str, user_agent: str, read_confirmed: bool) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    if doc["customer_id"] != customer_id:
        raise PermissionError("forbidden")
    if not read_confirmed:
        raise ValueError("read_not_confirmed")

    # ── Revision re-acceptance path ─────────────────────────────────────────
    rev = doc.get("revision")
    if rev and rev.get("status") == "pending_acceptance":
        if not rev.get("opened_at"):
            raise ValueError("not_opened")
        gen = await _build_generation(doc)
        gate = _acceptance_gate(gen["validation"], gen["required_missing_variables"])
        if not gate["can_accept"]:
            return {"error": "profile_incomplete", "blocking_reasons": gate["reasons"],
                    "validation": gen["validation"],
                    "required_missing_variables": gen["required_missing_variables"]}
        versions = doc.get("versions") or []
        rev_ver = _version_by_no(versions, rev.get("version")) or {}
        acceptance = {
            "accepted_at": V.now_iso(), "accepted_by": customer_id,
            "ip": ip, "user_agent": user_agent,
            "document_version": rev_ver.get("version"), "document_hash": rev_ver.get("checksum"),
            "read_confirmed": True,
        }
        # stamp acceptance onto the revision version
        for v in versions:
            if v.get("version") == rev.get("version"):
                v["accepted_by"] = customer_id
                v["accepted_at"] = acceptance["accepted_at"]
        rev["acceptance"] = acceptance
        pay_required = bool(rev.get("payment_required"))
        rev["status"] = "awaiting_payment" if pay_required else "accepted"
        await db[K.C_CONTRACTS].update_one(
            {"id": contract_id},
            {"$set": {"revision": rev, "versions": versions, "updated_at": V.now_iso()}})
        await _audit(contract_id, "revision_accepted", customer_id,
                     {"version": rev.get("version"), "hash": rev_ver.get("checksum"),
                      "payment_required": pay_required})
        await _event(contract_id, "revision_accepted", customer_id,
                     f"Клієнт повторно погодив редакцію v{rev.get('version')}")
        if pay_required:
            await _issue_revision_invoice(contract_id, actor="system")
            await _notify_staff("Нову редакцію погоджено — очікує коригувальну оплату",
                                f"Договір №{doc.get('number')}: редакцію v{rev.get('version')} погоджено, "
                                f"виставлено коригувальний рахунок (IBAN).",
                                kind="revision_accepted", meta={"contract_id": contract_id})
        else:
            await _notify_staff("Нову редакцію погоджено — очікує затвердження",
                                f"Договір №{doc.get('number')}: редакцію v{rev.get('version')} погоджено клієнтом. "
                                f"Очікує Approve менеджера.",
                                kind="revision_ready_for_approve", meta={"contract_id": contract_id})
        return _public_contract(await _load(contract_id))

    # ── First-time acceptance path ──────────────────────────────────────────
    if not doc.get("opened_at"):
        raise ValueError("not_opened")
    gen = await _build_generation(doc)
    gate = _acceptance_gate(gen["validation"], gen["required_missing_variables"])
    if not gate["can_accept"]:
        return {"error": "profile_incomplete", "blocking_reasons": gate["reasons"],
                "validation": gen["validation"], "required_missing_variables": gen["required_missing_variables"]}
    versions = doc.get("versions") or []
    cur = versions[-1] if versions else {}
    acceptance = {
        "accepted_at": V.now_iso(), "accepted_by": customer_id,
        "ip": ip, "user_agent": user_agent,
        "document_version": cur.get("version"), "document_hash": cur.get("checksum"),
        "read_confirmed": True,
    }
    for v in versions:
        if v.get("version") == cur.get("version"):
            v["accepted_by"] = customer_id
            v["accepted_at"] = acceptance["accepted_at"]
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"acceptance": acceptance, "versions": versions,
                  "active_version": cur.get("version"),
                  "status": "awaiting_payment", "updated_at": V.now_iso()}},
    )
    await _audit(contract_id, "accepted", customer_id,
                 {"version": cur.get("version"), "hash": cur.get("checksum")})
    await _event(contract_id, "accepted", customer_id, "Клієнт прийняв умови")
    # auto-issue invoice on acceptance
    await issue_invoice(contract_id, actor="system", notify=False)
    await _notify_staff("Договір прийнято клієнтом",
                        f"Клієнт прийняв договір №{doc.get('number')} — очікує оплату (IBAN).",
                        kind="contract_accepted", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


async def _issue_revision_invoice(contract_id: str, *, actor: str) -> None:
    """Issue a corrective IBAN invoice for a payment-impacting revision."""
    db = get_db()
    doc = await _load(contract_id)
    rev = doc.get("revision") or {}
    settings = await get_settings()
    payment = dict(rev.get("payment") or {})
    payment.update({
        "status": "awaiting_bank_transfer",
        "invoice_id": payment.get("invoice_id") or _id("inv"),
        "iban": settings.get("iban"),
        "recipient_name": settings.get("recipient_name"),
        "recipient_edrpou": settings.get("recipient_edrpou"),
        "bank_name": settings.get("bank_name"),
        "amount_due": doc.get("value"),
        "currency": doc.get("currency", "UAH"),
        "payment_purpose": f"Коригувальна оплата за договором №{doc.get('number')} (редакція v{rev.get('version')})",
        "terms": settings.get("payment_terms"),
        "invoice_issued_at": V.now_iso(),
    })
    rev["payment"] = payment
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"revision": rev, "updated_at": V.now_iso()}})
    await _event(contract_id, "revision_invoice_issued", actor, "Виставлено коригувальний рахунок (IBAN)")
    await _notify_client(doc["customer_id"], "Коригувальний рахунок",
                         f"За новою редакцією договору №{doc.get('number')} виставлено рахунок до оплати.",
                         kind="invoice_issued", meta={"contract_id": contract_id})


# ─────────────────────────────────────────────────────────────────────────────
# IBAN payment flow
# ─────────────────────────────────────────────────────────────────────────────

async def issue_invoice(contract_id: str, *, actor: str, notify: bool = True) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    settings = await get_settings()
    amount = doc.get("value")
    payment = dict(doc.get("payment") or {})
    payment.update({
        "status": "awaiting_bank_transfer",
        "invoice_id": payment.get("invoice_id") or _id("inv"),
        "iban": settings.get("iban"),
        "recipient_name": settings.get("recipient_name"),
        "recipient_edrpou": settings.get("recipient_edrpou"),
        "bank_name": settings.get("bank_name"),
        "amount_due": amount,
        "currency": doc.get("currency", "UAH"),
        "payment_purpose": f"Оплата за договором №{doc.get('number')}",
        "terms": settings.get("payment_terms"),
        "invoice_issued_at": V.now_iso(),
    })
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"payment": payment,
                  "status": "awaiting_payment" if doc.get("status") in ("accepted", "awaiting_payment") else doc.get("status"),
                  "updated_at": V.now_iso()}},
    )
    await _event(contract_id, "invoice_issued", actor, "Виставлено рахунок (IBAN)")
    if notify:
        await _notify_client(doc["customer_id"], "Виставлено рахунок",
                             f"Рахунок за договором №{doc.get('number')} готовий до оплати банківським переказом.",
                             kind="invoice_issued", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


async def upload_proof(contract_id: str, customer_id: Optional[str], file_id: str, filename: str, *, actor: str) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    if customer_id and doc["customer_id"] != customer_id:
        raise PermissionError("forbidden")
    rev = doc.get("revision")
    proof = {
        "proof_file_id": file_id,
        "proof_filename": filename,
        "proof_uploaded_at": V.now_iso(),
        "status": "proof_uploaded",
    }
    if rev and rev.get("payment_required") and rev.get("status") == "awaiting_payment":
        payment = dict(rev.get("payment") or {})
        payment.update(proof)
        rev["payment"] = payment
        await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"revision": rev, "updated_at": V.now_iso()}})
        await _event(contract_id, "revision_proof_uploaded", actor, "Завантажено підтвердження коригувальної оплати")
        await _notify_staff("Завантажено підтвердження оплати (редакція)",
                            f"Клієнт завантажив підтвердження коригувальної оплати за договором №{doc.get('number')}.",
                            kind="proof_uploaded", meta={"contract_id": contract_id})
        return _public_contract(await _load(contract_id))
    payment = dict(doc.get("payment") or {})
    payment.update(proof)
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"payment": payment, "updated_at": V.now_iso()}})
    await _event(contract_id, "proof_uploaded", actor, "Завантажено платіжне підтвердження")
    await _notify_staff("Завантажено підтвердження оплати",
                        f"Клієнт завантажив підтвердження оплати за договором №{doc.get('number')}.",
                        kind="proof_uploaded", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


async def confirm_payment(contract_id: str, *, actor: str, reference: str = "", notes: str = "") -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    rev = doc.get("revision")
    confirm = {
        "status": "payment_confirmed",
        "payment_confirmed_by": actor,
        "payment_confirmed_at": V.now_iso(),
        "payment_reference": reference,
        "payment_notes": notes,
    }
    if rev and rev.get("payment_required") and rev.get("status") in ("awaiting_payment",):
        payment = dict(rev.get("payment") or {})
        payment.update(confirm)
        rev["payment"] = payment
        rev["status"] = "payment_confirmed"
        await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"revision": rev, "updated_at": V.now_iso()}})
        await _audit(contract_id, "revision_payment_confirmed", actor, {"reference": reference})
        await _event(contract_id, "revision_payment_confirmed", actor, "Коригувальну оплату підтверджено")
        await _notify_staff("Коригувальну оплату підтверджено — потрібне затвердження",
                            f"Договір №{doc.get('number')}: редакцію оплачено, очікує Approve.",
                            kind="revision_ready_for_approve", meta={"contract_id": contract_id})
        return _public_contract(await _load(contract_id))
    payment = dict(doc.get("payment") or {})
    payment.update(confirm)
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"payment": payment, "status": "payment_confirmed", "updated_at": V.now_iso()}},
    )
    await _audit(contract_id, "payment_confirmed", actor, {"reference": reference})
    await _event(contract_id, "payment_confirmed", actor, "Оплату підтверджено менеджером")
    await _notify_client(doc["customer_id"], "Оплату підтверджено",
                         f"Оплату за договором №{doc.get('number')} підтверджено. Очікуйте активації.",
                         kind="payment_confirmed", meta={"contract_id": contract_id})
    await _notify_staff("Оплату підтверджено — потрібне затвердження",
                        f"Договір №{doc.get('number')} оплачено, очікує Approve менеджера/адміна.",
                        kind="ready_for_approve", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


async def reject_payment(contract_id: str, *, actor: str, notes: str = "") -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    rev = doc.get("revision")
    if rev and rev.get("payment_required") and rev.get("status") in ("awaiting_payment",):
        payment = dict(rev.get("payment") or {})
        payment.update({"status": "needs_clarification", "payment_notes": notes,
                        "payment_rejected_by": actor, "payment_rejected_at": V.now_iso()})
        rev["payment"] = payment
        await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"revision": rev, "updated_at": V.now_iso()}})
        await _event(contract_id, "revision_payment_rejected", actor, notes or "Коригувальну оплату відхилено")
        await _notify_client(doc["customer_id"], "Оплату потрібно уточнити",
                             f"Коригувальну оплату за договором №{doc.get('number')} потрібно уточнити. {notes}",
                             kind="payment_rejected", meta={"contract_id": contract_id})
        return _public_contract(await _load(contract_id))
    payment = dict(doc.get("payment") or {})
    payment.update({"status": "needs_clarification", "payment_notes": notes,
                    "payment_rejected_by": actor, "payment_rejected_at": V.now_iso()})
    await db[K.C_CONTRACTS].update_one({"id": contract_id}, {"$set": {"payment": payment, "updated_at": V.now_iso()}})
    await _event(contract_id, "payment_rejected", actor, notes or "Оплату відхилено")
    await _notify_client(doc["customer_id"], "Оплату потрібно уточнити",
                         f"Оплату за договором №{doc.get('number')} потрібно уточнити. {notes}",
                         kind="payment_rejected", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


async def approve_contract(contract_id: str, *, actor: str) -> Dict[str, Any]:
    db = get_db()
    doc = await _load(contract_id)
    rev = doc.get("revision")

    # ── Approve a pending REVISION → promote it to the new in-force edition ──
    if rev:
        if not rev.get("acceptance"):
            raise ValueError("revision_not_accepted")
        if rev.get("payment_required") and (rev.get("payment") or {}).get("status") != "payment_confirmed":
            raise ValueError("revision_payment_not_confirmed")
        versions = doc.get("versions") or []
        old_active = doc.get("active_version")
        new_active = rev.get("version")
        for v in versions:
            if v.get("version") == old_active:
                v["status"] = "superseded"
                v["superseded_version_id"] = new_active
            elif v.get("version") == new_active:
                v["status"] = "current"
                v["approved_by"] = actor
                v["approved_at"] = V.now_iso()
        # Preserve prior acceptance in history, promote revision acceptance.
        history = list(doc.get("acceptance_history") or [])
        if doc.get("acceptance"):
            history.append({**doc["acceptance"], "superseded_at": V.now_iso()})
        new_payment = doc.get("payment") or {}
        if rev.get("payment_required") and rev.get("payment"):
            new_payment = {**new_payment, **rev["payment"]}
        approval = {"approved_by": actor, "approved_at": V.now_iso(), "revision_of": old_active}
        await db[K.C_CONTRACTS].update_one(
            {"id": contract_id},
            {"$set": {
                "versions": versions,
                "active_version": new_active,
                "current_version": new_active,
                "acceptance": rev.get("acceptance"),
                "acceptance_history": history,
                "payment": new_payment,
                "approval": approval,
                "status": "active",
                "revision": None,
                "activated_at": V.now_iso(),
                "updated_at": V.now_iso(),
            }},
        )
        await _audit(contract_id, "revision_approved", actor,
                     {"new_active_version": new_active, "superseded_version": old_active})
        await _event(contract_id, "revision_approved", actor,
                     f"Затверджено нову редакцію v{new_active}; попередню (v{old_active}) переведено в архів версій.")
        await _notify_client(doc["customer_id"], "Нову редакцію договору активовано",
                             f"Нову редакцію договору №{doc.get('number')} затверджено та активовано.",
                             kind="contract_active", meta={"contract_id": contract_id})
        await _notify_staff("Нову редакцію активовано",
                            f"Договір №{doc.get('number')}: редакцію v{new_active} затверджено та активовано.",
                            kind="contract_active", meta={"contract_id": contract_id})
        return _public_contract(await _load(contract_id))

    # ── First-time activation ───────────────────────────────────────────────
    if (doc.get("payment") or {}).get("status") != "payment_confirmed":
        raise ValueError("payment_not_confirmed")
    if not doc.get("acceptance"):
        raise ValueError("not_accepted")
    versions = doc.get("versions") or []
    active_no = doc.get("active_version") or (versions[-1]["version"] if versions else 1)
    for v in versions:
        if v.get("version") == active_no:
            v["approved_by"] = actor
            v["approved_at"] = V.now_iso()
    approval = {"approved_by": actor, "approved_at": V.now_iso()}
    await db[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$set": {"approval": approval, "status": "active", "versions": versions,
                  "active_version": active_no,
                  "activated_at": V.now_iso(), "updated_at": V.now_iso()}},
    )
    await _audit(contract_id, "manager_approved", actor, {"active_version": active_no})
    await _event(contract_id, "manager_approved", actor, "Затверджено менеджером — договір активний")
    await _notify_client(doc["customer_id"], "Договір активовано",
                         f"Ваш договір №{doc.get('number')} активовано.",
                         kind="contract_active", meta={"contract_id": contract_id})
    await _notify_staff("Договір активовано",
                        f"Договір №{doc.get('number')} затверджено та активовано.",
                        kind="contract_active", meta={"contract_id": contract_id})
    return _public_contract(await _load(contract_id))


# ─────────────────────────────────────────────────────────────────────────────
# Version invalidation
# ─────────────────────────────────────────────────────────────────────────────

async def _apply_legal_change_to_contracts(customer_id: str, changed_fields: List[str],
                                           before: Dict[str, Any], after: Dict[str, Any],
                                           *, reason: str) -> None:
    """Propagate a legal-profile change to the customer's contracts.

    * In-force contract + MATERIAL legal change → create a revision (re-accept).
    * In-force contract + non-material change  → refresh HTML in place.
    * Non-in-force (still in the pre-acceptance flow) → regenerate in place.
    * Draft / terminal → skip.
    """
    db = get_db()
    q = {"customer_id": customer_id, "status": {"$nin": list(K.TERMINAL_STATES)}}
    rows = await db[K.C_CONTRACTS].find(
        q, {"id": 1, "status": 1, "acceptance": 1, "revision": 1}).to_list(length=500)
    material_legal = [f for f in changed_fields if f in K.MATERIAL_LEGAL_FIELDS]
    for r in rows:
        cid = r["id"]
        in_force = r.get("status") in K.IN_FORCE_STATES and bool(r.get("acceptance"))
        try:
            if in_force:
                if material_legal:
                    if r.get("revision"):
                        continue  # a revision is already pending — don't stack
                    full = await _load(cid)
                    await _create_revision(
                        full, actor="system", reason=reason, changed_fields=material_legal,
                        before={k: before.get(k) for k in material_legal},
                        after={k: after.get(k) for k in material_legal})
                else:
                    full = await _load(cid)
                    await _refresh_inforce_version(full, actor="system", reason=reason)
            elif r.get("status") in ("generated", "sent_for_review", "awaiting_profile",
                                     "ready_for_acceptance", "accepted", "awaiting_payment"):
                await regenerate(cid, actor="system", reason=reason,
                                 changed_fields=changed_fields, before=before, after=after)
            # draft / revision_pending_acceptance → skip
        except Exception:
            pass


async def _event(contract_id: str, kind: str, actor: str, note: str) -> None:
    await get_db()[K.C_CONTRACTS].update_one(
        {"id": contract_id},
        {"$push": {"events": {"kind": kind, "actor": actor, "note": note, "at": V.now_iso()}}},
    )


async def _audit(contract_id: str, kind: str, actor: str, data: Dict[str, Any]) -> None:
    """Append-only audit trail (never updated/deleted)."""
    try:
        await get_db()["cflow_audit"].insert_one({
            "id": _id("aud"), "entity": "contract", "contract_id": contract_id,
            "kind": kind, "actor": actor, "at": V.now_iso(), "data": data or {},
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Reads
# ─────────────────────────────────────────────────────────────────────────────

async def list_contracts(*, customer_id: Optional[str] = None, status: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if customer_id:
        q["customer_id"] = customer_id
    if status:
        q["status"] = status
    rows = await db[K.C_CONTRACTS].find(q, {"_id": 0, "versions": 0}).sort("created_at", -1).to_list(length=limit)
    for r in rows:
        r["status_label"] = K.STATUS_LABELS_UK.get(r.get("status"), r.get("status"))
        pay = r.get("payment") or {}
        r["payment_status_label"] = K.PAYMENT_STATUS_LABELS_UK.get(pay.get("status"), pay.get("status"))
    return rows


async def get_contract(contract_id: str, *, customer_id: Optional[str] = None) -> Dict[str, Any]:
    doc = await _load(contract_id)
    if customer_id and doc.get("customer_id") != customer_id:
        raise PermissionError("forbidden")
    return _public_contract(doc)


# ─────────────────────────────────────────────────────────────────────────────
# Files (payment proofs & template sources)
# ─────────────────────────────────────────────────────────────────────────────

async def save_file(content: bytes, filename: str, content_type: str, *, purpose: str, owner: str) -> Dict[str, Any]:
    import base64
    db = get_db()
    fid = _id("file")
    doc = {
        "id": fid, "filename": filename, "content_type": content_type or "application/octet-stream",
        "size": len(content), "purpose": purpose, "owner": owner,
        "b64": base64.b64encode(content).decode("ascii"), "created_at": V.now_iso(),
    }
    await db[K.C_FILES].insert_one(doc)
    return {"id": fid, "filename": filename, "size": len(content), "content_type": doc["content_type"]}


async def get_file(file_id: str) -> Optional[Dict[str, Any]]:
    import base64
    db = get_db()
    doc = await db[K.C_FILES].find_one({"id": file_id}, {"_id": 0})
    if not doc:
        return None
    doc["bytes"] = base64.b64decode(doc.pop("b64", "") or "")
    return doc


def _fallback_html() -> str:
    return (
        "<html><head><meta charset='utf-8'>"
        "<style>body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:13px;line-height:1.6;color:#111;padding:32px}"
        "h1{font-size:20px} .muted{color:#555} .sig{margin-top:40px}</style></head><body>"
        "<h1>Договір №{{contract.number}}</h1>"
        "<p class='muted'>Дата: {{contract.date}}</p>"
        "<p><b>ВИКОНАВЕЦЬ:</b> {{payment.recipient_name}}, ЄДРПОУ {{payment.recipient_edrpou}}</p>"
        "<p><b>ЗАМОВНИК:</b> {{company.legal_name}}, ЄДРПОУ {{company.edrpou}},<br/>"
        "адреса: {{company.legal_address}}<br/>"
        "в особі {{signer.full_name}} ({{signer.position}})</p>"
        "<h3>Предмет договору</h3>"
        "<p>Послуга: {{service.name}}. Загальна сума: {{contract.value}} {{contract.currency}}.</p>"
        "<h3>Порядок оплати</h3>"
        "<p>Оплата здійснюється банківським переказом на IBAN {{payment.iban}}.<br/>"
        "{{payment.terms}}</p>"
        "<div class='sig'><p>ЗАМОВНИК: ______________ {{signer.full_name}}</p>"
        "<p>ВИКОНАВЕЦЬ: ______________</p></div>"
        "</body></html>"
    )
