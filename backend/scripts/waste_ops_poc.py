#!/usr/bin/env python3
"""Wave 3 — Operations Center POC: full operational cycle end-to-end."""
import json, sys, urllib.parse, urllib.request

B = "http://localhost:8001"

def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(B + path, data=data, method=method)
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
    if not cond: ok.failed += 1
ok.failed = 0

def main():
    _, d = call("POST", "/api/auth/login", body={"email": "admin@bibi.cars", "password": "Admin12345!"})
    tok = d["access_token"]; print("login ok")

    _, d = call("POST", "/api/waste/companies", tok, {"name": "ТОВ ЕКО-Тест Операції", "edrpou": "99887766"})
    cid = d["company"]["id"]
    _, d = call("POST", "/api/waste/objects", tok, {"company_id": cid, "name": "Корпус №1", "object_type": "hospital", "pickup_schedule": "щотижня, пн"})
    oid = d["object"]["id"]
    _, d = call("POST", "/api/waste/requests", tok, {"company_id": cid, "object_id": oid,
               "items": [{"waste_code": "18 01 03*", "qty": 80}, {"waste_code": "20 01 21*", "qty": 40}]})
    rid = d["request"]["id"]
    print(f"company={cid} object={oid} request={rid}")

    print("== Contract from request ==")
    st, d = call("POST", f"/api/waste/requests/{rid}/contract", tok, {"amount": 12000})
    ctr = d.get("contract", {}); ok(st == 200 and ctr.get("number", "").startswith("WC-"), f"contract {ctr.get('number')} status={ctr.get('status')}")
    ctr_id = ctr["id"]
    for s in ["sent", "agreed", "signed", "active"]:
        st, d = call("POST", f"/api/waste/contracts/{ctr_id}/status", tok, {"status": s})
        ok(st == 200 and d["contract"]["status"] == s, f"contract -> {s}")
    st, d = call("GET", f"/api/waste/contracts/{ctr_id}", tok)
    ok(bool(d["contract"].get("signed_at")), f"signed_at set ({d['contract'].get('signed_at') is not None})")

    print("== Pickup from request ==")
    st, d = call("POST", f"/api/waste/requests/{rid}/pickup", tok,
                 {"scheduled_at": "2026-07-01", "driver": {"name": "Петро", "phone": "+380501230000", "vehicle": "ADR-1234"}, "transport_type": "ADR"})
    pk = d.get("pickup", {}); ok(st == 200 and pk.get("number", "").startswith("PU-"), f"pickup {pk.get('number')} status={pk.get('status')}")
    pk_id = pk["id"]
    for s in ["route", "driver_assigned", "picked_up", "delivered"]:
        st, d = call("POST", f"/api/waste/pickups/{pk_id}/status", tok, {"status": s})
        ok(st == 200 and d["pickup"]["status"] == s, f"pickup -> {s}")
    st, d = call("GET", f"/api/waste/pickups/{pk_id}", tok)
    ok(bool(d["pickup"].get("picked_up_at")) and bool(d["pickup"].get("delivered_at")), "picked_up_at & delivered_at set")

    print("== Act from request ==")
    st, d = call("POST", f"/api/waste/requests/{rid}/act", tok, {"utilization_method": "Інсинерація", "total_weight_kg": 120})
    act = d.get("act", {}); ok(st == 200 and act.get("number", "").startswith("ACT-") and act.get("status") == "expected", f"act {act.get('number')} status={act.get('status')}")
    act_id = act["id"]
    for s in ["created", "signed", "archived"]:
        st, d = call("POST", f"/api/waste/acts/{act_id}/status", tok, {"status": s})
        ok(st == 200 and d["act"]["status"] == s, f"act -> {s}")
    st, d = call("GET", f"/api/waste/acts/{act_id}", tok)
    ok(bool(d["act"].get("signed_at")), "act signed_at set")

    print("== Invalid status rejected ==")
    st, d = call("POST", f"/api/waste/acts/{act_id}/status", tok, {"status": "bogus"})
    ok(st == 400, f"invalid status -> {st}")

    print("== Object Center detail ==")
    st, d = call("GET", f"/api/waste/objects/{oid}/detail", tok)
    ok(st == 200 and d["stats"]["requests"] >= 1 and d["stats"]["pickups"] >= 1 and d["stats"]["acts"] >= 1,
       f"object detail req={d['stats']['requests']} pickups={d['stats']['pickups']} acts={d['stats']['acts']} types={d['stats']['waste_types']} next_pickup={d['stats'].get('next_pickup')}")
    ok(d.get("pickup_schedule") == "щотижня, пн", "pickup_schedule present")

    print("== Tasks & comments ==")
    st, d = call("POST", f"/api/waste/companies/{cid}/tasks", tok, {"title": "Передзвонити по договору", "due_at": "2026-07-02"})
    ok(st == 200, "task created")
    st, d = call("POST", f"/api/waste/companies/{cid}/comments", tok, {"text": "Клієнт просить вивіз у вихідні"})
    ok(st == 200, "comment created")

    print("== Company360 v2 (all tabs) ==")
    st, d = call("GET", f"/api/waste/companies/{cid}", tok)
    s = d["stats"]
    ok(st == 200 and s["contracts"] >= 1 and s["acts"] >= 1 and s["pickups"] >= 1 and s["tasks"] >= 1,
       f"company360 contracts={s['contracts']} acts={s['acts']} pickups={s['pickups']} tasks={s['tasks']} active_contracts={s['active_contracts']} signed_acts={s['signed_acts']}")
    ok(len(d.get("timeline", [])) >= 4, f"timeline has {len(d.get('timeline', []))} events")
    ok(all(k in d for k in ["objects","requests","contracts","acts","pickups","tasks","comments","timeline","invoices","payments","documents","calls"]),
       "all ERP tabs present in payload")

    print("== Stats v2 ==")
    st, d = call("GET", "/api/waste/stats", tok)
    ok(st == 200 and "contracts" in d and "pickups" in d and "acts" in d and "contract_labels" in d,
       f"stats contracts={d.get('contracts')} pickups={d.get('pickups')} acts={d.get('acts')}")

    print()
    if ok.failed:
        print(f"RESULT: ❌ {ok.failed} checks FAILED"); sys.exit(1)
    print("RESULT: ✅ ALL OPERATIONS CENTER CHECKS PASSED")

if __name__ == "__main__":
    main()
