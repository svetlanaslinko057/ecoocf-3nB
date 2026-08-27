#!/usr/bin/env python3
"""
POC — «Accepted layer» (License Matrix → accepted → public filtering → pricing).

Перевіряє реальну логіку: лише ліцензований піднабір кодів стає публічним,
калькулятор повертає ціну для прийнятих кодів, а toggling ліцензії миттєво
змінює прапор accepted.

Запуск:  python3 /app/backend/scripts/waste_acceptance_poc.py
"""
import sys
import requests

BASE = "http://localhost:8001/api"
ADMIN = {"email": "admin@bibi.cars", "password": "Admin12345!"}

passed = 0
failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name} {extra}")
    else:
        failed += 1
        print(f"  ✗ FAIL: {name} {extra}")


def main():
    s = requests.Session()
    # 1) login
    r = s.post(f"{BASE}/auth/login", json=ADMIN, timeout=30)
    token = r.json().get("access_token")
    check("admin login", bool(token))
    H = {"Authorization": f"Bearer {token}"}

    # 2) (re)seed licensed set (idempotent) + recompute
    r = s.post(f"{BASE}/waste/licenses/seed", headers=H, timeout=60)
    j = r.json()
    seeded_count = j.get("created") or j.get("count")
    print(f"\n[seed_license_matrix] {j}")
    check("license seed returned licensed>=30", (j.get("licensed", 0) >= 30), f"licensed={j.get('licensed')}")

    # 3) admin stats — accepted_codes equals licensed
    r = s.get(f"{BASE}/waste/admin/stats", headers=H, timeout=30)
    st = r.json()
    print(f"[admin/stats] codes={st.get('codes')} accepted={st.get('accepted')} official={st.get('official')}")
    check("accepted == licensed count", st.get("accepted") == j.get("licensed"),
          f"accepted={st.get('accepted')} licensed={j.get('licensed')}")
    check("full national catalog preserved (>800 codes)", st.get("codes", 0) > 800, f"codes={st.get('codes')}")

    # 4) PUBLIC /codes?accepted=true returns ONLY licensed
    r = s.get(f"{BASE}/waste/codes", params={"accepted": "true", "limit": 2000}, timeout=30)
    pub = r.json()
    acc_total = pub.get("total")
    all_accepted = all(c.get("accepted") for c in pub.get("items", []))
    print(f"[public /codes?accepted=true] total={acc_total} all_accepted={all_accepted}")
    check("public codes count == accepted", acc_total == st.get("accepted"), f"total={acc_total}")
    check("every public code is accepted", all_accepted)

    # 5) ADMIN /codes (no filter) sees the full catalog (maximally wide)
    r = s.get(f"{BASE}/waste/codes", params={"limit": 1}, headers=H, timeout=30)
    check("admin sees full catalog", r.json().get("total", 0) > 800, f"total={r.json().get('total')}")

    # 6) categories accepted-only hides empty categories
    r = s.get(f"{BASE}/waste/categories", params={"accepted": "true"}, timeout=30)
    cats = r.json().get("categories", [])
    check("accepted categories all have count>0", all(c["count"] > 0 for c in cats), f"cats={len(cats)}")

    # 7) license/check — licensed code accepted, random non-licensed code rejected
    r = s.get(f"{BASE}/waste/license/check", params={"code": "13 02 05*"}, timeout=30)
    lc = r.json()
    check("licensed code accepted (13 02 05*)", lc.get("accepted") is True, f"reason={lc.get('reason')}")
    r = s.get(f"{BASE}/waste/license/check", params={"code": "01 01 01"}, timeout=30)
    lc2 = r.json()
    check("non-licensed code NOT accepted (01 01 01)", lc2.get("accepted") is False, f"reason={lc2.get('reason')}")

    # 8) price estimate for accepted code returns breakdown + price
    r = s.post(f"{BASE}/waste/price", json={"code": "13 02 05*", "weight": 500, "region": "kyiv", "transport": True}, timeout=30)
    pr = r.json()
    print(f"[price 13 02 05* 500kg] price={pr.get('price')} accepted={pr.get('accepted')} breakdown_rows={len(pr.get('breakdown', []))}")
    check("price ok + accepted + has price", pr.get("ok") and pr.get("accepted") and (pr.get("price") or 0) > 0)
    check("price has breakdown", len(pr.get("breakdown", [])) >= 1)

    # 9) toggle OFF a code -> accepted flips to false, then restore
    test_code = "16 01 03"
    r = s.post(f"{BASE}/waste/licenses", headers=H, json={"waste_code": test_code, "allowed": False}, timeout=30)
    off = r.json()
    check("toggle off -> accepted False", off.get("accepted") is False, f"accepted={off.get('accepted')}")
    r = s.get(f"{BASE}/waste/codes", params={"accepted": "true", "limit": 2000}, timeout=30)
    codes_now = {c["code"] for c in r.json().get("items", [])}
    check("toggled-off code removed from public", test_code not in codes_now)
    # restore
    s.post(f"{BASE}/waste/licenses", headers=H, json={
        "waste_code": test_code, "allowed": True,
        "license_number": "1247-ОР", "valid_until": "2030-12-31T00:00:00+00:00",
        "notes": "Відпрацьовані шини",
    }, timeout=30)
    r = s.get(f"{BASE}/waste/license/check", params={"code": test_code}, timeout=30)
    check("restore -> accepted True again", r.json().get("accepted") is True)

    print(f"\n==== POC RESULT: {passed} passed, {failed} failed ====")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
