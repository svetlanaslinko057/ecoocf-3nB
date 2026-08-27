"""Collection names, enums and UA labels for the contract engine."""
from __future__ import annotations

# ── Collections (reuse existing + two new) ──────────────────────────────────
C_CONTRACTS = "waste_contracts"        # existing (ops_router) — extended
C_PERIODS = "contract_periods"         # NEW — universal schedule
C_ACTS = "utilization_acts"            # existing — extended (contract_id/period_id)
C_PICKUPS = "waste_pickups"            # existing
C_INVOICES = "invoices"                # existing (server.py) — extended (links)
C_ECO_REPORTS = "ecologist_reports"    # NEW
C_TASKS = "waste_tasks"                # existing
C_FILES = "files"                      # existing (object storage)
C_COMPANIES = "waste_companies"        # existing
C_CODES = "waste_codes"                # existing

# ── Universal schedule period types ─────────────────────────────────────────
PERIOD_TYPES = ("quarter", "month", "custom", "one_time")
PERIOD_TYPE_LABELS_UK = {
    "quarter": "Квартал",
    "month": "Місяць",
    "custom": "Довільний період",
    "one_time": "Разовий",
}

PERIOD_STATUSES = ("planned", "active", "in_progress", "completed", "cancelled")
PERIOD_STATUS_LABELS_UK = {
    "planned": "Заплановано",
    "active": "Активний",
    "in_progress": "В роботі",
    "completed": "Завершено",
    "cancelled": "Скасовано",
}

# ── Extra works — each a SEPARATE position (visible in history + PDF) ────────
EXTRA_WORK_TYPES = ("transport", "urgent", "packaging", "lab", "sorting", "other")
EXTRA_WORK_LABELS_UK = {
    "transport": "Транспорт",
    "urgent": "Терміновий виїзд",
    "packaging": "Додаткова тара",
    "lab": "Лабораторія",
    "sorting": "Сортування",
    "other": "Інші послуги",
}
# stage: planned = part of contract baseline; executed = incurred during ops
EXTRA_WORK_STAGES = ("planned", "executed")

# ── Invoice scope (set on the contract) ─────────────────────────────────────
INVOICE_SCOPES = ("per_period", "per_act", "final")
INVOICE_SCOPE_LABELS_UK = {
    "per_period": "За період (квартал/місяць)",
    "per_act": "За кожним актом",
    "final": "Фінальний",
}

# Acts considered "executed" (contribute to Executed Value)
SIGNED_ACT_STATUSES = ("signed", "archived")
OPEN_ACT_STATUSES = ("expected", "created")
PAID_INVOICE_STATUSES = ("paid",)
CANCELLED_INVOICE_STATUSES = ("cancelled", "void", "rejected")

ECO_REPORT_SCOPES = ("period", "custom", "contract")
ECO_REPORT_STATUSES = ("draft", "final", "signed")
