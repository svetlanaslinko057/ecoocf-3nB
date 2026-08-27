"""Collections, statuses, required fields and the universal variable catalog."""
from __future__ import annotations

# ── Collections ─────────────────────────────────────────────────────────────
C_TYPES = "contract_types"          # NEW — universal contract types
C_TEMPLATES = "cflow_templates"     # NEW — template library (HTML/DOCX/PDF)
C_CONTRACTS = "cflow_contracts"     # NEW — universal acceptance-flow documents
C_FILES = "cflow_files"             # NEW — uploaded sources & payment proofs
C_SETTINGS = "cflow_settings"       # NEW — IBAN requisites, defaults
C_CUSTOMERS = "customers"           # existing
C_COMPANIES = "waste_companies"     # existing
C_STAFF_NOTIF = "waste_notifications"  # existing (staff bell)
C_CLIENT_NOTIF = "notifications"       # existing (client inbox)
C_DOC_TEMPLATES = "document_templates" # existing seeded HTML templates (fallback)

# ── Contract lifecycle (section 9) ─────────────────────────────────────────
STATUSES = (
    "draft",
    "generated",
    "sent_for_review",
    "awaiting_profile",
    "ready_for_acceptance",
    "accepted",
    "awaiting_payment",
    "payment_confirmed",
    "manager_approved",
    "active",
    "revision_pending_acceptance",  # active contract has a NEW revision awaiting re-acceptance
    "closed",
    "archived",
)
STATUS_LABELS_UK = {
    "draft": "Чернетка",
    "generated": "Згенеровано",
    "sent_for_review": "Надіслано на ознайомлення",
    "awaiting_profile": "Очікує реквізити",
    "ready_for_acceptance": "Готовий до прийняття",
    "accepted": "Прийнято клієнтом",
    "awaiting_payment": "Очікує оплату",
    "payment_confirmed": "Оплату підтверджено",
    "manager_approved": "Затверджено менеджером",
    "active": "Активний",
    "revision_pending_acceptance": "Нова редакція очікує погодження",
    "closed": "Завершено",
    "archived": "Архів",
}

# ── Revision policy (Final Consistency Task) ────────────────────────────────
# States in which a legally in-force accepted edition exists. A MATERIAL change
# to such a contract must NOT silently mutate the in-force version — it creates
# an immutable revision that requires re-acceptance (and re-payment if the
# change affects money) before it can supersede the in-force edition.
IN_FORCE_STATES = ("payment_confirmed", "manager_approved", "active")
# Terminal states — never revised.
TERMINAL_STATES = ("closed", "archived")

# Legally-significant legal-profile fields (changing these on an in-force
# contract forces a revision + re-acceptance).
MATERIAL_LEGAL_FIELDS = (
    "legal_name", "edrpou", "legal_address", "signer_full_name", "signer_position",
)
# Legally-significant contract fields.
MATERIAL_CONTRACT_FIELDS = (
    "contract_type_id", "template_id", "service_id", "service_name",
    "valid_from", "valid_to", "value", "currency", "custom_vars",
    "title", "number", "waste_items", "schedule",
)
ALL_MATERIAL_FIELDS = (
    set(MATERIAL_LEGAL_FIELDS) | set(MATERIAL_CONTRACT_FIELDS)
    | {"template", "contract_template", "contract_type", "payment_terms", "manual_regeneration"}
)
# Fields whose change affects the amount/terms → a corrective IBAN invoice and
# fresh payment confirmation are required for the revision.
PAYMENT_IMPACT_FIELDS = ("value", "currency", "payment_terms")
# Non-material fields (allowlist) — internal/technical; never reset acceptance.
NON_MATERIAL_FIELDS = (
    "internal_manager", "internal_comment", "tags", "crm_note", "sync_status",
)

# Revision sub-status (tracked on contract.revision.status)
REVISION_STATUSES = (
    "pending_acceptance",   # client must re-read + accept the new revision
    "accepted",            # re-accepted, no payment impact → ready for approve
    "awaiting_payment",     # re-accepted, corrective invoice issued
    "payment_confirmed",    # corrective payment confirmed → ready for approve
)

# ── Payment status (section 8 — IBAN ONLY) ──────────────────────────────────
PAYMENT_STATUSES = (
    "not_invoiced",
    "invoice_issued",
    "awaiting_bank_transfer",
    "proof_uploaded",
    "payment_confirmed",
    "rejected",
    "needs_clarification",
)
PAYMENT_STATUS_LABELS_UK = {
    "not_invoiced": "Рахунок не виставлено",
    "invoice_issued": "Рахунок виставлено",
    "awaiting_bank_transfer": "Очікує банківський переказ",
    "proof_uploaded": "Завантажено підтвердження",
    "payment_confirmed": "Оплату підтверджено",
    "rejected": "Відхилено",
    "needs_clarification": "Потребує уточнення",
}

# ── Legal profile (section 1) ───────────────────────────────────────────────
REQUIRED_PROFILE_FIELDS = (
    "legal_name",
    "edrpou",
    "legal_address",
    "phone",
    "email",
    "signer_full_name",
    "signer_position",
)
OPTIONAL_PROFILE_FIELDS = (
    "iban",
    "bank_name",
    "mfo",
    "tax_status",
    "vat_number",
    "postal_address",
    "authorized_basis",
    "power_of_attorney",
    "website",
    "contact_person",
)
PROFILE_FIELD_LABELS_UK = {
    "legal_name": "Юридична назва",
    "edrpou": "ЄДРПОУ",
    "legal_address": "Юридична адреса",
    "phone": "Телефон",
    "email": "Email",
    "signer_full_name": "ПІБ підписанта",
    "signer_position": "Посада підписанта",
    "iban": "IBAN",
    "bank_name": "Банк",
    "mfo": "МФО",
    "tax_status": "Податковий статус",
    "vat_number": "ІПН / ПДВ",
    "postal_address": "Поштова адреса",
    "authorized_basis": "Діє на підставі",
    "power_of_attorney": "Довіреність",
    "website": "Вебсайт",
    "contact_person": "Контактна особа",
}

# ── Universal variable catalog (section 5) ──────────────────────────────────
# key -> {label, source path in context, required(default False)}
DEFAULT_VARIABLE_CATALOG = [
    {"key": "company.legal_name", "label": "Юр. назва", "required": True},
    {"key": "company.edrpou", "label": "ЄДРПОУ", "required": True},
    {"key": "company.legal_address", "label": "Юр. адреса", "required": True},
    {"key": "customer.full_name", "label": "Клієнт", "required": False},
    {"key": "customer.email", "label": "Email клієнта", "required": True},
    {"key": "signer.full_name", "label": "Підписант", "required": True},
    {"key": "signer.position", "label": "Посада підписанта", "required": True},
    {"key": "contract.number", "label": "Номер договору", "required": True},
    {"key": "contract.date", "label": "Дата", "required": True},
    {"key": "contract.valid_from", "label": "Діє з", "required": False},
    {"key": "contract.valid_to", "label": "Діє до", "required": False},
    {"key": "contract.value", "label": "Сума", "required": False},
    {"key": "service.name", "label": "Послуга", "required": False},
    {"key": "payment.iban", "label": "IBAN отримувача", "required": False},
    {"key": "payment.terms", "label": "Умови оплати", "required": False},
]

MISSING_MARKER_PREFIX = "[[ВІДСУТНЬО: "
MISSING_MARKER_SUFFIX = "]]"
