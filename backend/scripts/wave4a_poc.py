"""
Wave 4A — Pricing Engine v2 + License Matrix + Directory Admin
Backend smoke / POC test (read-only side effects rolled back at the end).
"""
from __future__ import annotations

import os
import sys
import time
import requests

BASE = os.environ.get("BASE_URL", "http://localhost:8001")
ADMIN_EMAIL = "admin@bibi.cars"
ADMIN_PASS = "Admin12345!"

passed = 0
failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  — {detail}")


def login(email: str, password: str) -> str:
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    print(f"\n=== Wave 4A POC against {BASE} ===\n")
    token = login(ADMIN_EMAIL, ADMIN_PASS)
    H = {"Authorization": f"Bearer {token}"}

    # ── 1) Public pricing meta ──
    print("[1] Pricing meta (public)")
    r = requests.get(f"{BASE}/api/waste/pricing/meta", timeout=10)
    check("GET /pricing/meta is 200", r.status_code == 200)
    js = r.json()
    check("regions returned", isinstance(js.get("regions"), list) and len(js["regions"]) >= 5)
    check("defaults present", "urgent_surcharge_pct" in (js.get("defaults") or {}))

    # ── 2) Price rules CRUD ──
    print("\n[2] Price Rules CRUD")
    r = requests.get(f"{BASE}/api/waste/price_rules", headers=H, timeout=10)
    check("GET /price_rules 200", r.status_code == 200)
    before = len(r.json().get("items", []))

    # Pick an existing code
    codes = requests.get(f"{BASE}/api/waste/codes?limit=5", timeout=10).json()["items"]
    code = codes[0]["code"]

    # Create
    body = {
        "wasteCode": code, "region": "kyiv", "minWeight": 0, "maxWeight": 25,
        "containerType": "needed", "transportRequired": True, "urgent": False,
        "pricePerKg": 99.5, "minimumCharge": 1234, "currency": "UAH",
        "notes": "POC test rule",
    }
    r = requests.post(f"{BASE}/api/waste/price_rules", headers=H, json=body, timeout=10)
    check("POST /price_rules 200", r.status_code == 200, r.text[:200])
    rule = r.json()["rule"]
    rid = rule["id"]
    check("created has pricePerKg=99.5", rule.get("pricePerKg") == 99.5)
    check("created has containerType=needed", rule.get("containerType") == "needed")

    # Update
    r = requests.put(f"{BASE}/api/waste/price_rules/{rid}", headers=H, json={"pricePerKg": 77.7, "active": False}, timeout=10)
    check("PUT /price_rules/{id} 200", r.status_code == 200)
    check("update reflects pricePerKg=77.7", r.json()["rule"]["pricePerKg"] == 77.7)
    check("update reflects active=False", r.json()["rule"]["active"] is False)

    # Validation: bad waste code
    r = requests.post(f"{BASE}/api/waste/price_rules", headers=H, json={"wasteCode": "NOT EXIST", "pricePerKg": 10}, timeout=10)
    check("404 for unknown waste code", r.status_code == 404)

    # Validation: missing pricePerKg
    r = requests.post(f"{BASE}/api/waste/price_rules", headers=H, json={"wasteCode": code}, timeout=10)
    check("400 when pricePerKg missing", r.status_code == 400)

    # ── 3) Price quote applies rule ──
    print("\n[3] Price quote uses Pricing Engine v2")
    # Re-enable our rule, quote should use it
    requests.put(f"{BASE}/api/waste/price_rules/{rid}", headers=H, json={"active": True, "pricePerKg": 60, "minimumCharge": 5000}, timeout=10)
    q = requests.post(f"{BASE}/api/waste/price", json={
        "code": code, "weight": 10, "region": "kyiv", "container": "needed",
        "transport": True, "urgent": True,
    }, timeout=10).json()
    check("price ok", q.get("ok") is True)
    check("source==rule", q.get("source") == "rule")
    check("price_per_kg=60", q.get("price_per_kg") == 60)
    # min_charge triggers since 60*10 < 5000
    has_min = any(b.get("key") == "min_charge" for b in q.get("breakdown", []))
    check("min_charge tier applied", has_min)
    has_transport = any(b.get("key") == "transport" for b in q.get("breakdown", []))
    check("transport line present", has_transport)
    has_urgent = any(b.get("key") == "urgent" for b in q.get("breakdown", []))
    check("urgent surcharge present", has_urgent)
    check("total price > 0", (q.get("price") or 0) > 0)

    # Delete
    r = requests.delete(f"{BASE}/api/waste/price_rules/{rid}", headers=H, timeout=10)
    check("DELETE /price_rules/{id} 200", r.status_code == 200)

    # ── 4) License Matrix CRUD ──
    print("\n[4] License Matrix CRUD")
    body = {
        "waste_code": code, "allowed": True,
        "license_number": "POC-LIC-001",
        "valid_until": "2099-12-31T00:00:00+00:00",
        "notes": "POC license",
    }
    r = requests.post(f"{BASE}/api/waste/licenses", headers=H, json=body, timeout=10)
    check("POST /licenses 200", r.status_code == 200)
    lic = r.json()["license"]
    lic_id = lic["id"]
    check("license has waste_code", lic.get("waste_code") == code)

    # License check should now accept
    chk = requests.get(f"{BASE}/api/waste/license/check", params={"code": code}, timeout=10).json()
    check("license check accepted=True", chk.get("accepted") is True)
    check("license check reason set", "Ліцензія" in (chk.get("reason") or ""))

    # Toggle to expired -> not accepted
    requests.post(f"{BASE}/api/waste/licenses", headers=H, json={**body, "valid_until": "2000-01-01T00:00:00+00:00"}, timeout=10)
    chk2 = requests.get(f"{BASE}/api/waste/license/check", params={"code": code}, timeout=10).json()
    check("expired license blocks acceptance", chk2.get("accepted") is False)

    r = requests.delete(f"{BASE}/api/waste/licenses/{lic_id}", headers=H, timeout=10)
    check("DELETE /licenses/{id} 200", r.status_code == 200)

    # ── 5) Waste Directory Admin (codes CRUD) ──
    print("\n[5] Waste Directory CRUD")
    new_code = "99 99 99"
    # Make sure it does not exist
    requests.delete(f"{BASE}/api/waste/codes/by-code", headers=H, params={"code": new_code}, timeout=10)

    r = requests.post(f"{BASE}/api/waste/codes", headers=H, json={
        "code": new_code, "name": "POC Тестовий код",
        "category": "other_hazard", "hazardous": True, "hazard_class": 3,
        "human_names": ["тест", "POC"], "price_from": 42, "price_unit": "kg",
        "min_order_kg": 10, "requires_container": True, "requires_transport": False,
    }, timeout=10)
    check("POST /codes 201/200", r.status_code == 200, r.text[:200])
    check("created code has slug", bool(r.json()["code"].get("slug")))

    # Duplicate -> 409
    r = requests.post(f"{BASE}/api/waste/codes", headers=H, json={"code": new_code, "name": "dup"}, timeout=10)
    check("duplicate code -> 409", r.status_code == 409)

    # Update
    r = requests.put(f"{BASE}/api/waste/codes/by-code", headers=H, params={"code": new_code}, json={"name": "POC Updated", "price_from": 55}, timeout=10)
    check("PUT /codes/by-code 200", r.status_code == 200)
    check("update name applied", r.json()["code"]["name"] == "POC Updated")
    check("update price_from applied", r.json()["code"]["price_from"] == 55)

    # Search hits it
    r = requests.get(f"{BASE}/api/waste/search", params={"q": "POC Updated"}, timeout=10).json()
    found = any(it["code"] == new_code for it in r.get("items", []))
    check("search by name finds new code", found)

    # Bulk import upsert
    r = requests.post(f"{BASE}/api/waste/admin/import", headers=H, json=[{
        "code": new_code, "name": "POC Imported", "category": "other_hazard",
    }], timeout=15)
    check("admin/import upsert 200", r.status_code == 200)
    check("import returned counts", r.json().get("updated", 0) >= 1 or r.json().get("created", 0) >= 1)

    # Delete
    r = requests.delete(f"{BASE}/api/waste/codes/by-code", headers=H, params={"code": new_code}, timeout=10)
    check("DELETE /codes/by-code 200", r.status_code == 200)

    # ── 6) Stats includes price_rules ──
    print("\n[6] Stats")
    s = requests.get(f"{BASE}/api/waste/stats", headers=H, timeout=10).json()
    check("stats.codes >= 80", s.get("codes", 0) >= 80)
    check("stats.price_rules present", "price_rules" in s)

    print(f"\n=== Result: passed={passed} failed={failed} ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
