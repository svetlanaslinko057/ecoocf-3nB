#!/usr/bin/env python3
"""
Waste Core POC — end-to-end flow verification (Wave 2).

Flow: login -> seed check -> smart search -> license check -> price ->
create company -> create object -> create request -> license-aware items ->
stage transition (new->quote->contract) -> Company360 aggregate -> stats ->
License Matrix override (deny a code) -> re-check acceptance.
"""
import json
import sys
import urllib.parse
import urllib.request

B = "http://localhost:8001"


def call(method, path, token=None, body=None):
    url = B + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def ok(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        ok.failed += 1
ok.failed = 0


def main():
    print("== 1. Login ==")
    st, d = call("POST", "/api/auth/login", body={"email": "admin@bibi.cars", "password": "Admin12345!"})
    token = d.get("access_token")
    ok(st == 200 and token, f"admin login ({st})")

    print("== 2. Smart search ==")
    q = urllib.parse.quote("прострочені ліки")
    st, d = call("GET", f"/api/waste/search?q={q}")
    codes = [i["code"] for i in d.get("items", [])]
    ok(st == 200 and any("20 01 32" in c or "18 01 09" in c for c in codes), f"'прострочені ліки' -> {codes[:3]}")

    print("== 3. License check (default) ==")
    st, d = call("GET", "/api/waste/license/check?code=" + urllib.parse.quote("16 06 01*"))
    ok(st == 200 and d["accepted"] is True, f"16 06 01* accepted={d.get('accepted')}")

    print("== 4. Price estimate ==")
    st, d = call("POST", "/api/waste/price", body={"code": "16 06 01*", "qty_kg": 500})
    ok(st == 200 and d.get("estimate_from"), f"16 06 01* x500kg estimate_from={d.get('estimate_from')}")

    print("== 5. Create company (Company360) ==")
    st, d = call("POST", "/api/waste/companies", token,
                 {"name": "ТОВ Медцентр Добробут", "edrpou": "12345678",
                  "email": "eco@dobrobut.test", "phone": "+380441234567"})
    cid = d.get("company", {}).get("id")
    ok(st == 200 and cid, f"company created id={cid}")

    print("== 6. Create object (branch/site) ==")
    st, d = call("POST", "/api/waste/objects", token,
                 {"company_id": cid, "name": "Лабораторія (Лівий берег)", "object_type": "lab",
                  "address": "Київ, вул. Прикладна, 1"})
    oid = d.get("object", {}).get("id")
    ok(st == 200 and oid, f"object created id={oid}")

    print("== 7. Create waste request (license-enriched items) ==")
    st, d = call("POST", "/api/waste/requests", token,
                 {"company_id": cid, "object_id": oid,
                  "items": [{"waste_code": "18 01 03*", "qty": 50, "unit": "kg"},
                            {"waste_code": "20 01 21*", "qty": 30, "unit": "шт"}]})
    rid = d.get("request", {}).get("id")
    items = d.get("request", {}).get("items", [])
    ok(st == 200 and rid, f"request created id={rid}")
    ok(all("accepted" in it and "hazardous" in it for it in items), "items enriched with license/hazard flags")

    print("== 8. Stage transitions ==")
    for stage in ["quote", "contract"]:
        st, d = call("POST", f"/api/waste/requests/{rid}/stage", token, {"stage": stage, "note": f"-> {stage}"})
        ok(st == 200 and d["request"]["stage"] == stage, f"stage -> {stage}")
    st, d = call("GET", f"/api/waste/requests/{rid}", token)
    hist = d.get("request", {}).get("stage_history", [])
    ok(len(hist) >= 3, f"stage_history len={len(hist)}")

    print("== 9. Company360 aggregate ==")
    st, d = call("GET", f"/api/waste/companies/{cid}", token)
    ok(st == 200 and d["stats"]["objects"] >= 1 and d["stats"]["requests"] >= 1,
       f"company360 objects={d['stats']['objects']} requests={d['stats']['requests']} open={d['stats']['open_requests']}")

    print("== 10. Public request (lead from calculator) ==")
    st, d = call("POST", "/api/waste/requests/public", None,
                 {"company_name": "ФОП Тест", "contact_name": "Іван", "contact_phone": "+380501112233",
                  "items": [{"waste_code": "16 06 01*", "qty": 200}]})
    ok(st == 200 and d.get("request_id"), f"public request id={d.get('request_id')}")

    print("== 11. License Matrix override (deny a code) ==")
    st, d = call("POST", "/api/waste/licenses", token,
                 {"waste_code": "06 03 11*", "allowed": False, "license_number": "—",
                  "notes": "Ціаніди — не приймаємо"})
    ok(st == 200, "license matrix entry created (deny)")
    st, d = call("GET", "/api/waste/license/check?code=" + urllib.parse.quote("06 03 11*"))
    ok(st == 200 and d["accepted"] is False, f"06 03 11* now accepted={d.get('accepted')} ({d.get('reason')})")

    print("== 12. Stats ==")
    st, d = call("GET", "/api/waste/stats", token)
    ok(st == 200 and d["codes"] > 0 and d["companies"] >= 1 and d["requests"] >= 2,
       f"stats codes={d['codes']} companies={d['companies']} requests={d['requests']} by_stage={d['requests_by_stage']}")

    print()
    if ok.failed:
        print(f"RESULT: ❌ {ok.failed} checks FAILED")
        sys.exit(1)
    print("RESULT: ✅ ALL WASTE CORE CHECKS PASSED")


if __name__ == "__main__":
    main()
