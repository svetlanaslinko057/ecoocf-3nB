"""
Contract Engine — math & logic test (runs against the live Mongo).

Exercises the PRODUCTION engine code end-to-end:
  schedule generation (quarter) -> line overrides (calc vs manual) ->
  extra-works as separate positions -> freeze Contract Value ->
  act sign -> auto-accumulation (idempotent) -> Executed Value ->
  invoices -> Invoiced/Paid/Remaining -> completion checks -> ecologist report.

Run:  cd /app/backend && python -m scripts.test_contract_engine
Cleans up all demo docs at the end.
"""
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db_runtime import set_db  # noqa: E402
from app.contract_engine import constants as K  # noqa: E402
from app.contract_engine import periods as PERIODS  # noqa: E402
from app.contract_engine import financials as FIN  # noqa: E402
from app.contract_engine import accumulation as ACC  # noqa: E402
from app.contract_engine import completion as COMP  # noqa: E402
from app.contract_engine import reports as REP  # noqa: E402
from app.contract_engine import invoicing as INV  # noqa: E402
from app.contract_engine.util import gen_id, now_iso  # noqa: E402

PASS, FAIL = 0, 0
CID = "ctr_ce_test_demo"


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \u2705 {name} {extra}")
    else:
        FAIL += 1
        print(f"  \u274c {name} {extra}")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    set_db(db)

    # ---- pick 2 real accepted codes with a price -------------------------
    codes_docs = await db[K.C_CODES].find(
        {"accepted": True, "price_from": {"$ne": None}}, {"_id": 0, "code": 1, "price_from": 1},
    ).limit(2).to_list(length=2)
    if len(codes_docs) < 2:
        codes_docs = await db[K.C_CODES].find({}, {"_id": 0, "code": 1}).limit(2).to_list(length=2)
    c1, c2 = codes_docs[0]["code"], codes_docs[1]["code"]
    print(f"Using waste codes: {c1}, {c2}")

    # ---- clean any prior run --------------------------------------------
    await _cleanup(db)

    # ---- 1. create a contract + generate quarterly schedule -------------
    contract = {
        "id": CID, "number": "WC-CE-TEST", "company_id": "demo_ce_company",
        "customer_id": "demo_ce_customer", "object_ids": [], "waste_codes": [c1, c2],
        "status": "draft", "currency": "UAH",
        "valid_from": "2026-01-01", "valid_to": "2026-06-30",
        "total_limit_kg": 100000,
        "schedule_config": {"period_type": "quarter", "auto_generate": True},
        "financial_terms": {"invoice_scope": "per_period", "vat_pct": 20},
        "items": [{"waste_code": c1}, {"waste_code": c2}],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db[K.C_CONTRACTS].insert_one(dict(contract))

    periods = await PERIODS.generate(CID)
    check("schedule quarter -> 2 periods (Q1,Q2)", len(periods) == 2, f"(got {len(periods)})")
    q1, q2 = periods[0], periods[1]
    check("period labels", q1["label"] == "2026-Q1" and q2["label"] == "2026-Q2", f"({q1['label']},{q2['label']})")
    check("each period seeded 2 lines", len(q1["lines"]) == 2 and len(q2["lines"]) == 2)

    # ---- 2. set planned volumes (overrides) -----------------------------
    await PERIODS.update_line(q1["id"], c1, {"planned_kg": 1000})
    await PERIODS.update_line(q1["id"], c2, {"planned_kg": 500})
    r = await PERIODS.update_line(q2["id"], c1, {"planned_kg": 2000})
    q1 = await PERIODS.get_period(q1["id"])
    ln_c1 = next(l for l in q1["lines"] if l["waste_code"] == c1)
    check("planned_kg persisted", ln_c1["planned_kg"] == 1000)
    check("calculated price present", ln_c1.get("calc_price_per_kg") is not None, f"({ln_c1.get('calc_price_per_kg')})")
    check("line planned_amount computed", ln_c1["planned_amount"] > 0, f"({ln_c1['planned_amount']})")

    # ---- 3. manual price override (calc vs manual visible) --------------
    await PERIODS.update_line(q1["id"], c2, {"price_per_kg": 12.5})
    q1 = await PERIODS.get_period(q1["id"])
    ln_c2 = next(l for l in q1["lines"] if l["waste_code"] == c2)
    check("override -> price_source=manual", ln_c2["price_source"] == "manual", f"({ln_c2['price_source']})")
    check("both calc & manual retained", ln_c2.get("calc_price_per_kg") is not None and ln_c2["price_per_kg"] == 12.5)
    check("manual line amount = 12.5*500", ln_c2["planned_amount"] == 6250.0, f"({ln_c2['planned_amount']})")

    # ---- 4. extra work as a SEPARATE position ---------------------------
    await PERIODS.add_extra_work(q1["id"], {"type": "transport", "amount": 3000, "stage": "planned"})
    q1 = await PERIODS.get_period(q1["id"])
    check("extra work stored separately", len(q1["extra_works"]) == 1 and q1["extra_works"][0]["type"] == "transport")
    check("period planned includes extra", q1["totals"]["planned_extra_amount"] == 3000.0, f"({q1['totals']['planned_extra_amount']})")

    # ---- 5. financials: five values -------------------------------------
    fin = await FIN.recompute(CID)
    planned_total = fin["planned_total"]
    check("planned_total > 0", planned_total > 0, f"({planned_total})")
    check("contract_value == planned (not frozen)", fin["contract_value"] == planned_total and not fin["contract_value_frozen"])
    check("executed_value == 0 (no acts yet)", fin["executed_value"] == 0.0)
    check("invoiced/paid/remaining present", "invoiced_value" in fin and "paid_value" in fin and "remaining_value" in fin)

    # ---- 6. freeze Contract Value at signing ----------------------------
    fin = await FIN.freeze_contract_value(CID)
    frozen_cv = fin["contract_value"]
    check("contract_value frozen", fin["contract_value_frozen"] and frozen_cv == planned_total, f"({frozen_cv})")
    # change plan AFTER freeze -> planned_total moves, contract_value stays
    await PERIODS.update_line(q2["id"], c2, {"planned_kg": 1000})
    fin = await FIN.recompute(CID)
    check("frozen Contract Value stays after plan change", fin["contract_value"] == frozen_cv, f"(cv={fin['contract_value']}, planned={fin['planned_total']})")
    check("planned_total diverged from frozen", fin["planned_total"] != frozen_cv)

    # ---- 7. act sign -> auto-accumulation -------------------------------
    act = {
        "id": gen_id("act"), "number": "ACT-CE-1", "company_id": "demo_ce_company",
        "contract_id": CID, "period_id": q1["id"], "status": "signed",
        "act_date": "2026-02-15", "utilization_method": "\u0421\u043f\u0430\u043b\u044e\u0432\u0430\u043d\u043d\u044f",
        "total_weight_kg": 1400,
        "lines": [
            {"waste_code": c1, "actual_kg": 900, "price_per_kg": 10},
            {"waste_code": c2, "actual_kg": 500},
        ],
        "extra_works": [{"type": "urgent", "label": "\u0422\u0435\u0440\u043c\u0456\u043d\u043e\u0432\u0438\u0439 \u0432\u0438\u0457\u0437\u0434", "amount": 1500}],
        "created_at": now_iso(),
    }
    await db[K.C_ACTS].insert_one(dict(act))
    await ACC.on_act_changed(act)
    q1 = await PERIODS.get_period(q1["id"])
    ln_c1 = next(l for l in q1["lines"] if l["waste_code"] == c1)
    check("act -> line actual_kg accumulated", ln_c1["actual_kg"] == 900, f"({ln_c1['actual_kg']})")
    check("act actual price applied", ln_c1["actual_amount"] == 9000.0, f"({ln_c1['actual_amount']})")
    check("act extra -> executed extra in period", any(e.get("source") == "act" for e in q1["extra_works"]))
    fin = await FIN.recompute(CID)
    exec_after = fin["executed_value"]
    check("executed_value > 0 after act", exec_after > 0, f"({exec_after})")

    # ---- 8. idempotency: re-run accumulation -> same executed -----------
    await ACC.on_act_changed(act)
    fin2 = await FIN.recompute(CID)
    check("accumulation idempotent", fin2["executed_value"] == exec_after, f"({fin2['executed_value']} == {exec_after})")
    q1 = await PERIODS.get_period(q1["id"])
    ln_c1 = next(l for l in q1["lines"] if l["waste_code"] == c1)
    check("no double accumulation", ln_c1["actual_kg"] == 900, f"({ln_c1['actual_kg']})")

    # ---- 9. invoices -> Invoiced / Paid / Remaining ---------------------
    inv = {"id": gen_id("inv"), "contract_id": CID, "period_id": q1["id"], "invoice_scope": "per_period",
           "customerId": "demo_ce_customer", "amount": 5000, "total": 5000, "currency": "UAH",
           "status": "pending", "created_at": now_iso()}
    await db[K.C_INVOICES].insert_one(dict(inv))
    fin = await FIN.recompute(CID)
    check("invoiced_value = 5000", fin["invoiced_value"] == 5000.0, f"({fin['invoiced_value']})")
    check("paid_value = 0", fin["paid_value"] == 0.0)
    check("remaining = contract_value - paid", fin["remaining_value"] == round(frozen_cv - 0, 2), f"({fin['remaining_value']})")
    await db[K.C_INVOICES].update_one({"id": inv["id"]}, {"$set": {"status": "paid"}})
    fin = await FIN.recompute(CID)
    check("paid_value = 5000 after paid", fin["paid_value"] == 5000.0, f"({fin['paid_value']})")
    check("remaining reduced by payment", fin["remaining_value"] == round(frozen_cv - 5000, 2), f"({fin['remaining_value']})")
    check("outstanding = invoiced - paid = 0", fin["outstanding_value"] == 0.0)

    # ---- 10. completion wizard ------------------------------------------
    comp = await COMP.completion_check(CID)
    check("completion has 6 checks", len(comp["checks"]) == 6)
    check("acts_closed OK (act signed)", _chk(comp, "acts_closed"))
    check("invoices_paid OK (only invoice paid)", _chk(comp, "invoices_paid"))
    check("ecologist_report NOT ok yet", not _chk(comp, "ecologist_report"))
    check("not ready to close", comp["ready"] is False)
    try:
        await COMP.complete_contract(CID, confirm=True)
        check("complete blocked when not ready", False)
    except ValueError:
        check("complete blocked when not ready", True)

    # ---- 11. ecologist report (per contract) ----------------------------
    rep = await REP.build_report(
        CID, scope_type="contract",
        ecologist={"name": "\u041f\u0435\u0442\u0440\u0435\u043d\u043a\u043e \u0406.\u0406.", "license_no": "EKO-123"},
        conclusion="\u0423\u0442\u0438\u043b\u0456\u0437\u0430\u0446\u0456\u044f \u0432\u0438\u043a\u043e\u043d\u0430\u043d\u0430 \u0443 \u043f\u043e\u0432\u043d\u043e\u043c\u0443 \u043e\u0431\u0441\u044f\u0437\u0456.",
        status="final",
    )
    check("report aggregates codes", len(rep["codes"]) >= 2, f"({len(rep['codes'])})")
    check("report methods captured", "\u0421\u043f\u0430\u043b\u044e\u0432\u0430\u043d\u043d\u044f" in rep["utilization_methods"])
    check("report actual_kg > 0", rep["actual_kg"] > 0, f"({rep['actual_kg']})")
    check("report has number", rep["number"].startswith("ECO-REP-"))

    comp = await COMP.completion_check(CID)
    check("ecologist_report OK after final report", _chk(comp, "ecologist_report"))

    # ---- 12. invoicing: zero-price protection (on q2, before it is billed) ----
    await PERIODS.update_line(q2["id"], c1, {"planned_kg": 500, "price_per_kg": 0})
    try:
        await INV.generate_period_invoice(CID, q2["id"], basis="planned")
        check("zero-price invoice blocked", False)
    except INV.BillingError:
        check("zero-price invoice blocked", True)
    await PERIODS.update_line(q2["id"], c1, {"price_per_kg": 20})

    # ---- 13. period invoice + idempotency (q2) --------------------------
    r = await INV.generate_period_invoice(CID, q2["id"], basis="planned")
    inv1_id = r["invoice"]["id"]
    inv1_amt = float(r["invoice"]["amount"])
    check("period invoice created", not r["idempotent"] and r["invoice"]["invoice_scope"] == "per_period")
    check("invoiced_value increased", r["financials"]["invoiced_value"] > 5000, f"({r['financials']['invoiced_value']})")
    r2 = await INV.generate_period_invoice(CID, q2["id"], basis="planned")
    check("period invoice idempotent", r2["idempotent"] and r2["invoice"]["id"] == inv1_id)

    # ---- 14. act invoice + idempotency ----------------------------------
    ra = await INV.generate_act_invoice(CID, act["id"])
    inv_act_id = ra["invoice"]["id"]
    check("act invoice created", not ra["idempotent"] and ra["invoice"]["invoice_scope"] == "per_act")
    ra2 = await INV.generate_act_invoice(CID, act["id"])
    check("act invoice idempotent", ra2["idempotent"] and ra2["invoice"]["id"] == inv_act_id)

    # ---- 15. partial payment reconciliation (accounts for prior paid) ----
    prior_paid = (await FIN.recompute(CID))["paid_value"]
    half = round(inv1_amt / 2, 2)
    await db[K.C_INVOICES].update_one({"id": inv1_id}, {"$set": {"status": "partial", "amount_paid": half}})
    fin = await FIN.recompute(CID)
    check("partial payment added to paid_value", abs(fin["paid_value"] - (prior_paid + half)) < 0.01, f"(paid={fin['paid_value']} exp={prior_paid + half})")
    check("remaining = contract_value - paid", abs(fin["remaining_value"] - round(fin["contract_value"] - (prior_paid + half), 2)) < 0.01, f"({fin['remaining_value']})")

    # ---- 16. cancelled invoice drops from invoiced ----------------------
    fin_before = await FIN.recompute(CID)
    await db[K.C_INVOICES].update_one({"id": inv_act_id}, {"$set": {"status": "cancelled"}})
    fin_after = await FIN.recompute(CID)
    check("cancelled invoice removed from invoiced_value", fin_after["invoiced_value"] < fin_before["invoiced_value"], f"({fin_before['invoiced_value']} -> {fin_after['invoiced_value']})")

    # ---- 17. two acts in one period accumulate --------------------------
    act2 = {
        "id": gen_id("act"), "number": "ACT-CE-2", "company_id": "demo_ce_company",
        "contract_id": CID, "period_id": q1["id"], "status": "signed",
        "act_date": "2026-03-01", "utilization_method": "Спалювання",
        "total_weight_kg": 200, "lines": [{"waste_code": c1, "actual_kg": 200, "price_per_kg": 20}],
        "created_at": now_iso(),
    }
    await db[K.C_ACTS].insert_one(dict(act2))
    await ACC.on_act_changed(act2)
    q1r = await PERIODS.get_period(q1["id"])
    ln_c1r = next(l for l in q1r["lines"] if l["waste_code"] == c1)
    check("two acts in one period accumulate (900+200=1100)", ln_c1r["actual_kg"] == 1100, f"({ln_c1r['actual_kg']})")

    # ---- 18. ecologist report internal sign-off -------------------------
    signed = await REP.sign_off(rep["id"], by={"id": "u1", "email": "eco@eco.ua", "role": "manager"})
    check("report signed-off status", signed["status"] == "signed")
    check("sign-off has content_hash", bool(signed.get("content_hash")) and len(signed["content_hash"]) == 64)
    check("sign-off records actor+version", signed.get("signed_by") == "eco@eco.ua" and signed.get("version") == 1)
    check("sign-off is NOT КЕП", signed.get("signature_kind") == "internal_sign_off")

    await _cleanup(db)
    print(f"\n==== RESULT: {PASS} passed, {FAIL} failed ====")
    return 0 if FAIL == 0 else 1


def _chk(comp, key):
    return next((c["ok"] for c in comp["checks"] if c["key"] == key), False)


async def _cleanup(db):
    await db[K.C_CONTRACTS].delete_many({"id": CID})
    await db[K.C_PERIODS].delete_many({"contract_id": CID})
    await db[K.C_ACTS].delete_many({"contract_id": CID})
    await db[K.C_INVOICES].delete_many({"contract_id": CID})
    await db[K.C_ECO_REPORTS].delete_many({"contract_id": CID})
    await db[K.C_INVOICES].delete_many({"contract_id": CID})


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
