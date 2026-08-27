"""Idempotent seed for universal contract types + a default HTML template.

These are ONLY examples/seeds so the system is usable out of the box; they are
not business-logic hard-codes. Everything is editable via the admin surface.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.db_runtime import get_db
from . import constants as K
from . import service as S

logger = logging.getLogger("eco.contract_flow.seed")

_DEFAULT_TEMPLATE_HTML = (
    "<html><head><meta charset='utf-8'>"
    "<style>body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:13px;line-height:1.65;color:#0f172a;padding:36px}"
    "h1{font-size:22px;margin-bottom:4px} h3{margin-top:22px;color:#065f46} .muted{color:#64748b}"
    ".req{background:#f1f5f9;padding:12px 14px;border-radius:10px;margin:12px 0}"
    ".sig{margin-top:48px;display:flex;justify-content:space-between}</style></head><body>"
    "<h1>Договір №{{contract.number}}</h1>"
    "<p class='muted'>м. Київ &nbsp;·&nbsp; {{contract.date}}</p>"
    "<div class='req'><b>ВИКОНАВЕЦЬ:</b> {{payment.recipient_name}}, ЄДРПОУ {{payment.recipient_edrpou}}<br/>"
    "IBAN: {{payment.iban}}, {{payment.bank_name}}</div>"
    "<div class='req'><b>ЗАМОВНИК:</b> {{company.legal_name}}, ЄДРПОУ {{company.edrpou}}<br/>"
    "Юридична адреса: {{company.legal_address}}<br/>"
    "В особі: {{signer.full_name}}, {{signer.position}}<br/>"
    "Контакти: {{customer.email}}, {{customer.phone}}</div>"
    "<h3>1. Предмет договору</h3>"
    "<p>ВИКОНАВЕЦЬ надає послугу «{{service.name}}» відповідно до чинного законодавства України "
    "про поводження з відходами. Загальна вартість: <b>{{contract.value}} {{contract.currency}}</b>.</p>"
    "<h3>2. Порядок оплати (тільки IBAN)</h3>"
    "<p>Оплата здійснюється виключно банківським переказом на рахунок ВИКОНАВЦЯ: "
    "IBAN {{payment.iban}}. Призначення платежу: «Оплата за договором №{{contract.number}}».<br/>"
    "{{payment.terms}}</p>"
    "<h3>3. Строк дії</h3>"
    "<p>Договір діє з {{contract.valid_from}} до {{contract.valid_to}}.</p>"
    "<div class='sig'><div>ЗАМОВНИК:<br/><br/>______________<br/>{{signer.full_name}}</div>"
    "<div>ВИКОНАВЕЦЬ:<br/><br/>______________<br/>{{payment.recipient_name}}</div></div>"
    "</body></html>"
)

_SEED_TYPES = [
    {"name": "Разова утилізація", "code": "one_time", "invoice_scope": "final",
     "description": "Разовий вивіз та утилізація партії відходів."},
    {"name": "Квартальне обслуговування", "code": "quarterly", "invoice_scope": "per_period",
     "description": "Регулярне обслуговування з квартальними періодами."},
    {"name": "Регулярний вивіз", "code": "regular", "invoice_scope": "per_period",
     "description": "Регулярний вивіз відходів за графіком."},
    {"name": "Медичні відходи", "code": "medical", "invoice_scope": "per_act",
     "description": "Поводження з медичними відходами."},
    {"name": "Фармацевтичні відходи", "code": "pharma", "invoice_scope": "per_act",
     "description": "Утилізація фармацевтичних відходів."},
    {"name": "Небезпечні хімічні відходи", "code": "hazardous_chem", "invoice_scope": "final",
     "description": "Поводження з небезпечними хімічними відходами."},
]


async def seed_if_empty() -> Dict[str, Any]:
    db = get_db()
    if db is None:
        return {"seeded": False}
    await S.ensure_indexes()
    await S.get_settings()  # ensure settings doc

    created_types = 0
    tpl_id = None
    if await db[K.C_TEMPLATES].count_documents({}) == 0:
        tpl = await S.create_template({
            "name": "Універсальний договір (UA)", "language": "uk", "format": "html",
            "status": "active", "html": _DEFAULT_TEMPLATE_HTML,
            "variables_schema": K.DEFAULT_VARIABLE_CATALOG,
        }, actor="system")
        tpl_id = tpl["id"]

    if await db[K.C_TYPES].count_documents({}) == 0:
        for i, t in enumerate(_SEED_TYPES):
            payload = dict(t)
            if tpl_id:
                payload["default_template_id"] = tpl_id
            await S.create_type(payload, actor="system")
            created_types += 1

    logger.info("[cflow] seed complete types=%d template=%s", created_types, tpl_id)
    return {"seeded": True, "types_created": created_types, "template_id": tpl_id}
