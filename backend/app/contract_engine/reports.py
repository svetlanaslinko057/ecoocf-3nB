"""Ecologist Report — first-class entity (PDF is only a representation).

Aggregates plan/actual/deviation across a scope (single period, custom range,
or the whole contract). Can be generated at any time — per quarter, arbitrary
period, or the full contract — not only at the end.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

from . import constants as K
from . import schedule as SCH
from .util import gen_id, now_iso, num, round2, parse_date


async def _next_number(db) -> str:
    n = await db[K.C_ECO_REPORTS].count_documents({}) + 1
    from datetime import datetime, timezone
    return f"ECO-REP-{datetime.now(timezone.utc).year}-{n:04d}"


def _period_in_scope(period: Dict[str, Any], scope_type: str, period_ids, date_from, date_to) -> bool:
    if scope_type == "contract":
        return True
    if scope_type == "period":
        return period.get("id") in (period_ids or [])
    if scope_type == "custom":
        pf = parse_date(period.get("date_from"))
        pt = parse_date(period.get("date_to"))
        df = parse_date(date_from)
        dt = parse_date(date_to)
        if not pf or not pt:
            return False
        if df and pt < df:
            return False
        if dt and pf > dt:
            return False
        return True
    return False


async def build_report(
    contract_id: str,
    *,
    scope_type: str = "contract",
    period_ids: Optional[List[str]] = None,
    date_from: Any = None,
    date_to: Any = None,
    ecologist: Optional[Dict[str, Any]] = None,
    conclusion: Optional[str] = None,
    recommendations: Optional[str] = None,
    status: str = "draft",
    by: Optional[Dict[str, Any]] = None,
    db=None,
) -> Dict[str, Any]:
    db = get_db() if db is None else db
    contract = await db[K.C_CONTRACTS].find_one({"id": contract_id}, {"_id": 0})
    if not contract:
        raise ValueError("Contract not found")
    if scope_type not in K.ECO_REPORT_SCOPES:
        scope_type = "contract"

    periods = await db[K.C_PERIODS].find({"contract_id": contract_id}, {"_id": 0}).sort("index", 1).to_list(length=500)
    scoped = [p for p in periods if _period_in_scope(p, scope_type, period_ids, date_from, date_to)]

    # aggregate by waste_code across scoped periods
    by_code: Dict[str, Dict[str, Any]] = {}
    plan_kg = actual_kg = 0.0
    for p in scoped:
        for ln in p.get("lines", []):
            code = ln.get("waste_code")
            agg = by_code.setdefault(code, {
                "waste_code": code, "name": ln.get("name") or code,
                "hazardous": ln.get("hazardous"),
                "planned_kg": 0.0, "actual_kg": 0.0,
                "planned_amount": 0.0, "actual_amount": 0.0,
            })
            agg["planned_kg"] = round2(agg["planned_kg"] + num(ln.get("planned_kg")))
            agg["actual_kg"] = round2(agg["actual_kg"] + num(ln.get("actual_kg")))
            agg["planned_amount"] = round2(agg["planned_amount"] + num(ln.get("planned_amount")))
            agg["actual_amount"] = round2(agg["actual_amount"] + num(ln.get("actual_amount")))
            plan_kg += num(ln.get("planned_kg"))
            actual_kg += num(ln.get("actual_kg"))
    for agg in by_code.values():
        agg["deviation_kg"] = round2(agg["actual_kg"] - agg["planned_kg"])

    scoped_ids = [p.get("id") for p in scoped]
    act_docs = await db[K.C_ACTS].find(
        {"contract_id": contract_id, "status": {"$in": list(K.SIGNED_ACT_STATUSES)}}, {"_id": 0},
    ).to_list(length=1000)
    if scope_type != "contract":
        act_docs = [a for a in act_docs if (a.get("period_id") in scoped_ids) or SCH_any(scoped, a)]
    methods = sorted({(a.get("utilization_method") or "").strip() for a in act_docs if a.get("utilization_method")})
    act_ids = [a.get("id") for a in act_docs]
    total_weight = round2(sum(num(a.get("total_weight_kg")) for a in act_docs)) or actual_kg

    extra_summary: List[Dict[str, Any]] = []
    for p in scoped:
        for e in p.get("extra_works", []):
            extra_summary.append({
                "period_label": p.get("label"), "type": e.get("type"),
                "label": e.get("label"), "amount": e.get("amount"), "stage": e.get("stage"),
            })

    doc = {
        "id": gen_id("ecorep"),
        "number": await _next_number(db),
        "contract_id": contract_id,
        "company_id": contract.get("company_id"),
        "scope_type": scope_type,
        "period_ids": scoped_ids,
        "date_from": date_from,
        "date_to": date_to,
        "codes": list(by_code.values()),
        "utilization_methods": methods,
        "act_ids": act_ids,
        "plan_kg": round2(plan_kg),
        "actual_kg": round2(actual_kg),
        "deviation_kg": round2(actual_kg - plan_kg),
        "total_weight_kg": total_weight,
        "extra_works": extra_summary,
        "ecologist": ecologist or {},
        "conclusion": conclusion or "",
        "recommendations": recommendations or "",
        "status": status if status in K.ECO_REPORT_STATUSES else "draft",
        "pdf_file_id": None,
        "created_at": now_iso(),
        "created_by": (by or {}).get("email") or (by or {}).get("id"),
        "updated_at": now_iso(),
    }
    await db[K.C_ECO_REPORTS].insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


def SCH_any(scoped: List[Dict[str, Any]], act: Dict[str, Any]) -> bool:
    when = act.get("act_date") or act.get("signed_at") or act.get("created_at")
    return any(SCH.window_contains(p, when) for p in scoped)


async def list_reports(contract_id: str, *, db=None) -> List[Dict[str, Any]]:
    db = get_db() if db is None else db
    return await db[K.C_ECO_REPORTS].find({"contract_id": contract_id}, {"_id": 0}).sort("created_at", -1).to_list(length=200)


async def get_report(report_id: str, *, db=None) -> Optional[Dict[str, Any]]:
    db = get_db() if db is None else db
    return await db[K.C_ECO_REPORTS].find_one({"id": report_id}, {"_id": 0})


async def update_report(report_id: str, patch: Dict[str, Any], *, db=None) -> Optional[Dict[str, Any]]:
    db = get_db() if db is None else db
    allowed = {k: patch[k] for k in ("ecologist", "conclusion", "recommendations", "status") if k in patch}
    if allowed.get("status") and allowed["status"] not in K.ECO_REPORT_STATUSES:
        allowed.pop("status")
    allowed["updated_at"] = now_iso()
    await db[K.C_ECO_REPORTS].update_one({"id": report_id}, {"$set": allowed})
    return await get_report(report_id, db=db)


def _content_hash(report: Dict[str, Any]) -> str:
    """Deterministic SHA-256 over the report's material content. This is an
    internal integrity stamp / version fingerprint — NOT a qualified e-signature (КЕП)."""
    import hashlib
    import json
    material = {
        "contract_id": report.get("contract_id"),
        "scope_type": report.get("scope_type"),
        "period_ids": report.get("period_ids"),
        "codes": report.get("codes"),
        "plan_kg": report.get("plan_kg"),
        "actual_kg": report.get("actual_kg"),
        "deviation_kg": report.get("deviation_kg"),
        "total_weight_kg": report.get("total_weight_kg"),
        "utilization_methods": report.get("utilization_methods"),
        "extra_works": report.get("extra_works"),
        "conclusion": report.get("conclusion"),
        "recommendations": report.get("recommendations"),
        "ecologist": report.get("ecologist"),
    }
    blob = json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def sign_off(report_id: str, *, by: Optional[Dict[str, Any]] = None, db=None) -> Optional[Dict[str, Any]]:
    """Internal approval / sign-off of an ecologist report.

    Records actor + timestamp + version + content hash and moves the report to
    ``signed``. This is an internal integrity record only — it is explicitly
    NOT a qualified electronic signature (КЕП).
    """
    db = get_db() if db is None else db
    rep = await get_report(report_id, db=db)
    if not rep:
        raise ValueError("Звіт не знайдено")
    version = int(rep.get("version") or 0) + 1
    signoff = {
        "status": "signed",
        "version": version,
        "content_hash": _content_hash(rep),
        "signed_by": (by or {}).get("email") or (by or {}).get("id"),
        "signed_by_id": (by or {}).get("id"),
        "signed_by_role": (by or {}).get("role"),
        "signed_at": now_iso(),
        "signature_kind": "internal_sign_off",  # NOT a qualified e-signature (КЕП)
        "updated_at": now_iso(),
    }
    await db[K.C_ECO_REPORTS].update_one({"id": report_id}, {"$set": signoff})
    return await get_report(report_id, db=db)


def _money(v, cur="UAH"):
    try:
        return f"{float(v):,.2f} {cur}".replace(",", " ")
    except (TypeError, ValueError):
        return f"0.00 {cur}"


def render_report_html(report: dict, contract: dict = None, company: dict = None) -> str:
    """Render an Ecologist Report entity to a printable HTML document."""
    contract = contract or {}
    company = company or {}
    eco = report.get("ecologist") or {}
    cur = (contract.get("currency") or "UAH")
    rows = ""
    for c in report.get("codes", []):
        rows += (
            "<tr>"
            f"<td>{c.get('waste_code','')}</td>"
            f"<td>{(c.get('name') or '')}</td>"
            f"<td class='num'>{float(c.get('planned_kg') or 0):,.1f}</td>"
            f"<td class='num'>{float(c.get('actual_kg') or 0):,.1f}</td>"
            f"<td class='num'>{float(c.get('deviation_kg') or 0):,.1f}</td>"
            "</tr>"
        )
    extras = ""
    for e in report.get("extra_works", []):
        extras += (
            f"<tr><td>{e.get('period_label','')}</td><td>{e.get('label','')}</td>"
            f"<td class='num'>{_money(e.get('amount'), cur)}</td></tr>"
        )
    extras_block = (
        f"<h3>Додаткові роботи</h3><table><thead><tr><th>Період</th><th>Послуга</th><th>Сума</th></tr></thead>"
        f"<tbody>{extras}</tbody></table>" if extras else ""
    )
    methods = ", ".join(report.get("utilization_methods") or []) or "—"
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: 'DejaVu Sans', Arial, sans-serif; color:#0B1A14; font-size:12px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  h3 {{ margin:18px 0 6px; font-size:14px; color:#0E5E3A; }}
  .muted {{ color:#5b6b63; }}
  .head {{ border-bottom:3px solid #0E5E3A; padding-bottom:8px; margin-bottom:12px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
  th,td {{ border:1px solid #cdd8d2; padding:6px 8px; text-align:left; }}
  th {{ background:#eef5f0; }}
  .num {{ text-align:right; }}
  .grid {{ display:flex; gap:24px; }}
  .grid > div {{ flex:1; }}
  .sig {{ margin-top:36px; display:flex; justify-content:space-between; }}
  .box {{ border:1px solid #cdd8d2; border-radius:8px; padding:10px 12px; background:#f7faf8; }}
</style></head><body>
  <div class="head">
    <h1>Звіт еколога №{report.get('number','')}</h1>
    <div class="muted">Договір: {contract.get('number') or contract.get('id','')} · Компанія: {company.get('name') or company.get('company_name') or '—'}</div>
    <div class="muted">Обсяг звіту: {report.get('scope_type','')} · Дата: {(report.get('created_at') or '')[:10]}</div>
  </div>
  <div class="grid">
    <div class="box"><b>План (кг):</b> {float(report.get('plan_kg') or 0):,.1f}</div>
    <div class="box"><b>Факт (кг):</b> {float(report.get('actual_kg') or 0):,.1f}</div>
    <div class="box"><b>Відхилення (кг):</b> {float(report.get('deviation_kg') or 0):,.1f}</div>
    <div class="box"><b>Методи утилізації:</b> {methods}</div>
  </div>
  <h3>Коди відходів — план / факт / відхилення</h3>
  <table><thead><tr><th>Код</th><th>Найменування</th><th>План, кг</th><th>Факт, кг</th><th>Відхил., кг</th></tr></thead>
  <tbody>{rows or '<tr><td colspan=5>—</td></tr>'}</tbody></table>
  {extras_block}
  <h3>Висновок еколога</h3>
  <div class="box">{(report.get('conclusion') or '—')}</div>
  <h3>Рекомендації</h3>
  <div class="box">{(report.get('recommendations') or '—')}</div>
  <div class="sig">
    <div>Еколог: <b>{eco.get('name') or '________________'}</b><br><span class="muted">Ліцензія №: {eco.get('license_no') or '—'} · {eco.get('position') or ''}</span></div>
    <div>Підпис: ____________________</div>
  </div>
</body></html>"""
