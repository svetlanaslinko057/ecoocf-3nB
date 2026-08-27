"""Wave 4B — Operations Details + Object Center + Company360 Full backend POC."""
from __future__ import annotations
import os, sys, requests

BASE = os.environ.get("BASE_URL", "http://localhost:8001")
passed = 0; failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  ✓ {name}")
    else: failed += 1; print(f"  ✗ {name}  — {detail}")

def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"email":"admin@bibi.cars","password":"Admin12345!"}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]

def main():
    print(f"\n=== Wave 4B POC against {BASE} ===\n")
    H = {"Authorization": f"Bearer {login()}"}

    # Setup: company + object with schedule
    co = requests.post(f"{BASE}/api/waste/companies", headers=H, json={"name":"Wave4B POC Co","segment":"medical"}).json()["company"]
    cid = co["id"]
    obj = requests.post(f"{BASE}/api/waste/objects", headers=H, json={
        "company_id": cid, "name": "POC Філія", "object_type": "hospital",
        "address": "Київ", "responsible_name": "Тест", "responsible_phone": "+380",
        "pickup_schedule": {"frequency": "weekly", "weekday": "mon", "time": "09:00"},
    }).json()["object"]
    oid = obj["id"]
    check("object created with schedule", obj.get("pickup_schedule", {}).get("frequency") == "weekly")

    # Update object schedule
    upd = requests.put(f"{BASE}/api/waste/objects/{oid}", headers=H, json={
        "pickup_schedule": {"frequency": "biweekly", "weekday": "wed", "time": "14:30", "notes": "POC"}
    }).json()
    check("PUT /objects/{id} updates schedule", upd.get("object", {}).get("pickup_schedule", {}).get("frequency") == "biweekly")

    # Request → contract / pickup / act
    req = requests.post(f"{BASE}/api/waste/requests", headers=H, json={
        "company_id": cid, "object_id": oid,
        "items": [{"waste_code": "18 01 03*", "qty": 30}],
    }).json()
    rid = req["request"]["id"]
    ct = requests.post(f"{BASE}/api/waste/requests/{rid}/contract", headers=H, json={"amount": 9999}).json()["contract"]
    pk = requests.post(f"{BASE}/api/waste/requests/{rid}/pickup", headers=H).json()["pickup"]
    ac = requests.post(f"{BASE}/api/waste/requests/{rid}/act", headers=H).json()["act"]
    check("downstream contract+pickup+act generated", all([ct.get("id"), pk.get("id"), ac.get("id")]))

    # ── Detail GET ──
    print("\n[detail GET]")
    for kind, _id in [("contracts", ct["id"]), ("pickups", pk["id"]), ("acts", ac["id"])]:
        r = requests.get(f"{BASE}/api/waste/{kind}/{_id}", headers=H)
        check(f"GET /{kind}/{{id}} 200", r.status_code == 200)

    # ── PUT (Operations Details fields) ──
    print("\n[update operational fields]")
    r = requests.put(f"{BASE}/api/waste/contracts/{ct['id']}", headers=H, json={
        "title": "Договір POC v2", "amount": 12500, "currency": "UAH",
        "valid_from": "2026-01-01T00:00:00+00:00", "valid_to": "2027-01-01T00:00:00+00:00",
        "file_id": "https://example.com/contract.pdf", "signed_by": "manager@bibi.cars",
    }).json()
    c = r.get("contract") or r.get("item") or {}
    check("contract title saved", c.get("title") == "Договір POC v2")
    check("contract amount=12500", c.get("amount") == 12500)
    check("contract file_id (URL) saved", c.get("file_id", "").startswith("https://"))

    r = requests.put(f"{BASE}/api/waste/pickups/{pk['id']}", headers=H, json={
        "scheduled_at": "2026-07-15T10:00:00+00:00",
        "route": "Kyiv 1 → Kyiv 2",
        "transport_type": "adr", "container_type": "ibc",
        "weight_kg": 28.5,
        "driver": {"name": "Іванов І.", "phone": "+380441000000", "vehicle": "Sprinter АА0000ББ", "gps": "50.45,30.52"},
        "photo_url": "https://example.com/photo.jpg",
    }).json()
    p = r.get("pickup") or r.get("item") or {}
    check("pickup route saved", "Kyiv" in (p.get("route") or ""))
    check("pickup weight=28.5", p.get("weight_kg") == 28.5)
    check("pickup driver embedded", (p.get("driver") or {}).get("vehicle", "").startswith("Sprinter"))
    check("pickup photo_url saved", (p.get("photo_url") or "").startswith("https://"))

    r = requests.put(f"{BASE}/api/waste/acts/{ac['id']}", headers=H, json={
        "act_date": "2026-07-20T00:00:00+00:00",
        "total_weight_kg": 28.0, "utilization_method": "incineration",
        "file_id": "https://example.com/act.pdf", "signed_by": "ops@bibi.cars",
    }).json()
    a = r.get("act") or r.get("item") or {}
    check("act method=incineration", a.get("utilization_method") == "incineration")
    check("act weight=28.0", a.get("total_weight_kg") == 28.0)

    # ── Status transitions ──
    print("\n[status transitions + history]")
    r = requests.post(f"{BASE}/api/waste/contracts/{ct['id']}/status", headers=H, json={"status": "signed"}).json()
    c2 = r.get("contract") or {}
    check("contract signed -> signed_at set", bool(c2.get("signed_at")))
    check("contract history grows", len(c2.get("status_history") or []) >= 2)

    r = requests.post(f"{BASE}/api/waste/pickups/{pk['id']}/status", headers=H, json={"status": "picked_up"}).json()
    p2 = r.get("pickup") or {}
    check("pickup picked_up -> picked_up_at set", bool(p2.get("picked_up_at")))

    r = requests.post(f"{BASE}/api/waste/acts/{ac['id']}/status", headers=H, json={"status": "signed"}).json()
    a2 = r.get("act") or {}
    check("act signed -> signed_at set", bool(a2.get("signed_at")))

    # ── Object Center aggregate ──
    print("\n[object center detail]")
    r = requests.get(f"{BASE}/api/waste/objects/{oid}/detail", headers=H).json()
    check("object detail has company", bool(r.get("company")))
    check("object detail has requests >=1", len(r.get("requests") or []) >= 1)
    check("object detail has pickups >=1", len(r.get("pickups") or []) >= 1)
    check("object detail has acts >=1", len(r.get("acts") or []) >= 1)
    check("object detail.stats.waste_types >=1", (r.get("stats") or {}).get("waste_types", 0) >= 1)
    check("object detail.pickup_schedule echoed", (r.get("pickup_schedule") or {}).get("frequency") == "biweekly")

    # ── Company360: tasks CRUD + comments + timeline ──
    print("\n[company360 tasks + comments + timeline]")
    t = requests.post(f"{BASE}/api/waste/companies/{cid}/tasks", headers=H, json={
        "title": "POC Task", "due_at": "2026-12-31T00:00:00+00:00", "assigned_to": "manager@bibi.cars", "object_id": oid,
    }).json()
    tid = (t.get("task") or {}).get("id")
    check("task created", bool(tid))
    r = requests.get(f"{BASE}/api/waste/companies/{cid}/tasks", headers=H).json()
    check("task in list", any(x["id"] == tid for x in r.get("items") or []))
    requests.put(f"{BASE}/api/waste/tasks/{tid}", headers=H, json={"status": "in_progress"})
    r = requests.get(f"{BASE}/api/waste/companies/{cid}/tasks", headers=H).json()
    item = next((x for x in r.get("items") or [] if x["id"] == tid), None)
    check("task status updated", item and item.get("status") == "in_progress")
    r = requests.delete(f"{BASE}/api/waste/tasks/{tid}", headers=H)
    check("task delete 200", r.status_code == 200)

    cm = requests.post(f"{BASE}/api/waste/companies/{cid}/comments", headers=H, json={"text": "POC comment ✓"}).json()
    check("comment created", bool((cm.get("comment") or {}).get("id")))
    r = requests.get(f"{BASE}/api/waste/companies/{cid}/comments", headers=H).json()
    check("comments listed", len(r.get("items") or []) >= 1)

    r = requests.get(f"{BASE}/api/waste/companies/{cid}/timeline", headers=H).json()
    check("timeline has events", len(r.get("items") or []) >= 3)

    print(f"\n=== Result: passed={passed} failed={failed} ===")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
