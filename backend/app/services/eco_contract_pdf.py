"""
eco_contract_pdf.py — ECO.NOVA Ukrainian waste-utilization contract PDF.

Self-contained generator (HTML → WeasyPrint → PDF) that builds a proper
*Ukrainian* «Договір на утилізацію відходів» from a ``contracts_v2`` record
created by the IBAN invoice flow. Replaces the legacy car-import (BG) template
for this flow.

The PDF is stored in the customer's File Manager (Contracts folder) via
``app.services.file_manager.upload_file`` so the existing public download
endpoint (``/api/contracts/view/{token}/download``) streams it unchanged.

Reflects the contract's current state: when ``signed_full_name`` is present the
signature block is stamped (name, date, IP); otherwise blank signature lines.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import file_manager as fm

logger = logging.getLogger("eco.contract_pdf")


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def _money(v: Any, cur: str = "UAH") -> str:
    try:
        n = float(v or 0)
    except Exception:
        n = 0.0
    s = f"{n:,.2f}".replace(",", "\u00A0").replace(".", ",")
    return f"{s}\u00A0{_esc(cur)}"


def _fmt_date(v: Any) -> str:
    if not v:
        return "____________"
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        months = ["січня", "лютого", "березня", "квітня", "травня", "червня",
                  "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
        return f"{dt.day:02d} {months[dt.month - 1]} {dt.year} р."
    except Exception:
        return _esc(str(v)[:10])


def _items_rows(items: List[Dict[str, Any]], currency: str) -> str:
    rows = []
    total = 0.0
    for i, it in enumerate(items or [], start=1):
        name = it.get("name") or it.get("description") or "—"
        qty = it.get("qty") or 1
        unit = it.get("unit") or "од."
        price = it.get("price") or it.get("line_total") or 0
        line = it.get("line_total")
        if line is None:
            try:
                line = float(price) * float(qty)
            except Exception:
                line = price
        try:
            total += float(line)
        except Exception:
            pass
        rows.append(
            f"<tr><td class='c'>{i}</td><td>{_esc(name)}</td>"
            f"<td class='c'>{_esc(qty)} {_esc(unit)}</td>"
            f"<td class='r'>{_money(price, currency)}</td>"
            f"<td class='r'>{_money(line, currency)}</td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='5' class='c muted'>—</td></tr>")
    rows.append(
        f"<tr class='total'><td colspan='4' class='r'><b>Разом</b></td>"
        f"<td class='r'><b>{_money(total, currency)}</b></td></tr>"
    )
    return "".join(rows)


def build_contract_html(contract: Dict[str, Any], requisites: Optional[Dict[str, Any]] = None) -> str:
    req = requisites or {}
    number = contract.get("number") or contract.get("id") or "—"
    currency = (contract.get("currency") or "UAH").upper()
    amount = contract.get("amount") or 0
    items = contract.get("items") or []
    company = contract.get("company") or {}
    operator = contract.get("operator") or {}
    created = contract.get("created_at") or contract.get("sent_at")
    today = _fmt_date(created or datetime.now(timezone.utc).isoformat())

    op_name = operator.get("name") or req.get("legal_name") or "ТОВ «ЕКО-НОВА»"
    op_edrpou = operator.get("edrpou") or req.get("edrpou") or ""
    op_address = req.get("legal_address") or ""
    op_director = req.get("director_name") or ""
    op_basis = req.get("director_basis") or "Статуту"
    # IBAN/bank live inside per-currency accounts[] of the requisites doc
    _accounts = req.get("accounts") or []
    _acc = next((a for a in _accounts if (a.get("currency") or "").upper() == currency and a.get("iban")), None) \
        or next((a for a in _accounts if a.get("iban")), None) or {}
    iban = _acc.get("iban") or req.get("iban") or ""
    bank = _acc.get("bank_name") or req.get("bank_name") or ""
    mfo = _acc.get("mfo") or req.get("mfo") or ""

    cust_name = company.get("name") or "—"
    cust_edrpou = company.get("edrpou") or ""
    cust_email = company.get("email") or ""

    signed_name = contract.get("signed_full_name") or ""
    signed_at = contract.get("signed_at")
    signed_ip = contract.get("signed_ip") or ""

    if signed_name:
        cust_sign = (
            f"<div class='sig-name'>{_esc(signed_name)}</div>"
            f"<div class='sig-meta'>Підписано електронно: {_fmt_date(signed_at)}"
            + (f" · IP {_esc(signed_ip)}" if signed_ip else "") + "</div>"
        )
        stamp = "<div class='esign-badge'>● Підписано електронним підписом</div>"
    else:
        cust_sign = "<div class='sig-line'>&nbsp;</div><div class='sig-meta'>(підпис, П.І.Б.)</div>"
        stamp = "<div class='esign-badge pending'>○ Очікує електронного підпису</div>"

    purpose = (req.get("payment_purpose_template") or "Оплата за рахунком {number} від {date}")
    try:
        purpose = purpose.format(number=number, date=_fmt_date(created)[:11])
    except Exception:
        purpose = f"Оплата за рахунком {number}"

    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 18mm 16mm; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: "DejaVu Sans", Arial, sans-serif; color: #1c1c1c; font-size: 11px; line-height: 1.5; }}
    .head {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0E5E3A; padding-bottom: 10px; margin-bottom: 16px; }}
    .brand {{ font-size: 18px; font-weight: 800; color: #0E5E3A; letter-spacing: .5px; }}
    .brand small {{ display:block; font-size: 9px; font-weight: 600; color:#6b7280; letter-spacing: 2px; text-transform: uppercase; }}
    h1 {{ font-size: 15px; text-align: center; margin: 6px 0 2px; }}
    .sub {{ text-align:center; color:#6b7280; margin-bottom: 16px; }}
    .meta {{ text-align:right; font-size: 10px; color:#374151; }}
    .parties {{ display:flex; gap: 14px; margin-bottom: 14px; }}
    .party {{ flex:1; border:1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; }}
    .party h3 {{ margin:0 0 6px; font-size: 11px; color:#0E5E3A; text-transform: uppercase; letter-spacing:.5px; }}
    .party div {{ margin: 2px 0; }}
    .lbl {{ color:#6b7280; }}
    h2 {{ font-size: 12px; color:#0E5E3A; margin: 16px 0 6px; border-bottom:1px solid #e5e7eb; padding-bottom:4px; }}
    table {{ width:100%; border-collapse: collapse; margin: 6px 0; }}
    th, td {{ border:1px solid #e5e7eb; padding: 6px 8px; }}
    th {{ background:#f1f7f3; text-align:left; font-size: 10px; }}
    td.c {{ text-align:center; }} td.r {{ text-align:right; }}
    tr.total td {{ background:#f9fafb; }}
    .muted {{ color:#9ca3af; }}
    p {{ margin: 5px 0; text-align: justify; }}
    .pay {{ background:#f1f7f3; border:1px solid #cfe6d8; border-radius:8px; padding:10px 12px; }}
    .pay div {{ margin: 2px 0; }} .mono {{ font-family:"DejaVu Sans Mono", monospace; }}
    .signs {{ display:flex; gap: 24px; margin-top: 26px; }}
    .signbox {{ flex:1; }}
    .sig-line {{ border-bottom:1px solid #9ca3af; height: 24px; }}
    .sig-name {{ border-bottom:1px solid #0E5E3A; padding-bottom:3px; font-weight:700; }}
    .sig-meta {{ font-size: 9px; color:#6b7280; margin-top:3px; }}
    .esign-badge {{ display:inline-block; margin-top:6px; font-size:9px; font-weight:700; color:#0E5E3A; }}
    .esign-badge.pending {{ color:#b45309; }}
    .foot {{ margin-top: 22px; text-align:center; font-size: 9px; color:#9ca3af; border-top:1px solid #e5e7eb; padding-top:8px; }}
    </style></head><body>
    <div class="head">
      <div class="brand">ECO.NOVA<small>Платформа утилізації відходів</small></div>
      <div class="meta">м. Київ<br>{today}</div>
    </div>

    <h1>ДОГОВІР № {_esc(number)}</h1>
    <div class="sub">про надання послуг з утилізації небезпечних відходів</div>

    <div class="parties">
      <div class="party">
        <h3>Виконавець</h3>
        <div><b>{_esc(op_name)}</b></div>
        {f'<div><span class="lbl">ЄДРПОУ:</span> {_esc(op_edrpou)}</div>' if op_edrpou else ''}
        {f'<div><span class="lbl">Адреса:</span> {_esc(op_address)}</div>' if op_address else ''}
        {f'<div><span class="lbl">В особі:</span> {_esc(op_director)}, що діє на підставі {_esc(op_basis)}</div>' if op_director else ''}
      </div>
      <div class="party">
        <h3>Замовник</h3>
        <div><b>{_esc(cust_name)}</b></div>
        {f'<div><span class="lbl">ЄДРПОУ:</span> {_esc(cust_edrpou)}</div>' if cust_edrpou else ''}
        {f'<div><span class="lbl">Email:</span> {_esc(cust_email)}</div>' if cust_email else ''}
      </div>
    </div>

    <h2>1. Предмет договору</h2>
    <p>1.1. Виконавець зобовʼязується надати Замовнику послуги зі збирання, перевезення, оброблення та утилізації відходів згідно з переліком, наведеним у п. 2 цього Договору, а Замовник зобовʼязується прийняти та оплатити такі послуги.</p>
    <p>1.2. Послуги надаються відповідно до вимог чинного законодавства України у сфері поводження з відходами та наявних у Виконавця ліцензій/дозволів.</p>

    <h2>2. Перелік відходів та вартість послуг</h2>
    <table>
      <thead><tr><th class="c">№</th><th>Найменування / код відходу</th><th class="c">Кількість</th><th class="r">Ціна</th><th class="r">Сума</th></tr></thead>
      <tbody>{_items_rows(items, currency)}</tbody>
    </table>
    <p>2.1. Загальна вартість послуг за цим Договором становить <b>{_money(amount, currency)}</b>.</p>

    <h2>3. Порядок оплати</h2>
    <p>3.1. Оплата здійснюється Замовником шляхом банківського переказу на поточний рахунок Виконавця за наведеними нижче реквізитами на підставі виставленого рахунку.</p>
    <div class="pay">
      <div><span class="lbl">Отримувач:</span> <b>{_esc(op_name)}</b>{f' (ЄДРПОУ {_esc(op_edrpou)})' if op_edrpou else ''}</div>
      {f'<div><span class="lbl">IBAN:</span> <span class="mono">{_esc(iban)}</span></div>' if iban else '<div class="muted">IBAN буде зазначено у рахунку</div>'}
      {f'<div><span class="lbl">Банк:</span> {_esc(bank)}{f" · МФО {_esc(mfo)}" if mfo else ""}</div>' if bank else ''}
      <div><span class="lbl">Призначення платежу:</span> {_esc(purpose)}</div>
    </div>
    <p>3.2. Послуги вважаються прийнятими після надходження коштів на рахунок Виконавця та підтвердження оплати уповноваженим менеджером.</p>

    <h2>4. Відповідальність сторін та інші умови</h2>
    <p>4.1. Сторони несуть відповідальність за невиконання або неналежне виконання умов цього Договору згідно з чинним законодавством України.</p>
    <p>4.2. Договір може бути підписаний в електронній формі. Електронний підпис, дата, час та IP-адреса підписання фіксуються та мають юридичну силу.</p>
    <p>4.3. Усі спори вирішуються шляхом переговорів, а в разі недосягнення згоди — у судовому порядку.</p>

    <div class="signs">
      <div class="signbox">
        <h3 style="color:#0E5E3A;font-size:11px;">Виконавець</h3>
        <div class="sig-line">&nbsp;</div>
        <div class="sig-meta">{_esc(op_name)}{f' · {_esc(op_director)}' if op_director else ''}</div>
      </div>
      <div class="signbox">
        <h3 style="color:#0E5E3A;font-size:11px;">Замовник</h3>
        {cust_sign}
        {stamp}
      </div>
    </div>

    <div class="foot">ECO.NOVA · Платформа утилізації відходів · Україна · Документ сформовано автоматично {today}</div>
    </body></html>"""


async def generate_eco_contract_pdf(
    contract: Dict[str, Any],
    *,
    requisites: Optional[Dict[str, Any]] = None,
    generated_by: Optional[str] = None,
    generated_by_email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Render the Ukrainian ECO contract → PDF → store in customer Contracts
    folder. Returns the file_manager file_doc (or None on failure)."""
    customer_id = contract.get("customerId") or contract.get("customer_id")
    if not customer_id:
        logger.warning("[eco_pdf] contract %s has no customer_id", contract.get("id"))
        return None
    try:
        html_str = build_contract_html(contract, requisites)
        from weasyprint import HTML  # local import keeps boot fast
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception:
        logger.exception("[eco_pdf] render failed for contract %s", contract.get("id"))
        return None

    try:
        from app.core.db_runtime import get_db
        db = get_db()
        await fm.ensure_system_folders(customer_id)
        folder = await db.client_folders.find_one(
            {"customer_id": customer_id, "slug": "contracts", "is_system": True}, {"_id": 0}
        ) or await db.client_folders.find_one(
            {"customer_id": customer_id, "name": "Contracts", "is_system": True}, {"_id": 0}
        )
        if not folder:
            logger.warning("[eco_pdf] no Contracts folder for customer %s", customer_id)
            return None
        number = str(contract.get("number") or contract.get("id") or "contract").replace("/", "-")
        state = "signed" if contract.get("signed_full_name") else "draft"
        filename = f"Dohovir_{number}_{state}.pdf"
        file_doc = await fm.upload_file(
            customer_id=customer_id,
            folder_id=folder["id"],
            original_name=filename,
            content_type="application/pdf",
            data=pdf_bytes,
            comment=f"Договір утилізації {number} ({state})",
            uploaded_by=generated_by,
            uploaded_by_email=generated_by_email,
        )
        return file_doc
    except Exception:
        logger.exception("[eco_pdf] store failed for contract %s", contract.get("id"))
        return None
