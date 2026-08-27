"""POC: client cabinet + inquiry + staff inbox end-to-end (dev-login path)."""
import sys
import requests

BASE = "http://localhost:8001"


def jp(label, r):
    ok = r.status_code < 400
    print(f"[{'OK ' if ok else 'ERR'}] {label}: {r.status_code}")
    if not ok:
        print("     ->", r.text[:300])
    return r


def main():
    fails = 0

    # 1) public google client id
    r = jp("GET /auth/google-client-id", requests.get(f"{BASE}/api/auth/google-client-id"))
    data = r.json()
    assert data.get("enabled") and data.get("clientId"), "google client id not configured"

    # 2) dev-login (env-gated) -> session token
    r = jp("POST /client/dev-login", requests.post(f"{BASE}/api/client/dev-login",
            json={"email": "hospital@example.com", "name": "Лікарня №1", "company_name": "КНП Лікарня №1", "phone": "+380441112233"}))
    if r.status_code >= 400:
        print("dev-login disabled? ensure ALLOW_DEV_LOGIN=true"); return 1
    token = r.json().get("sessionToken") or r.json().get("token")
    H = {"Authorization": f"Bearer {token}"}

    # 3) /client/me
    r = jp("GET /client/me", requests.get(f"{BASE}/api/client/me", headers=H))
    assert r.json().get("customer", {}).get("email") == "hospital@example.com"

    # 4) update profile
    jp("PUT /client/me", requests.put(f"{BASE}/api/client/me", headers=H,
        json={"name": "Лікарня №1", "company_name": "КНП Лікарня №1", "position": "Гол. лікар"}))

    # 5) search licensed codes
    r = jp("GET /waste/search (accepted)", requests.get(f"{BASE}/api/waste/search", headers=H,
            params={"q": "18 01", "limit": 5, "accepted": "true"}))
    codes = r.json().get("items") or r.json().get("codes") or r.json().get("results") or []
    print("     found codes:", [c.get("code") for c in codes][:5])

    # 6) create request (use first accepted code if any, else a known accepted one)
    if codes:
        code = codes[0].get("code")
        r = requests.post(f"{BASE}/api/client/requests", headers=H,
                json={"items": [{"waste_code": code, "qty": 120, "unit": "kg", "name": codes[0].get("name")}], "comment": "POC заявка"})
        jp(f"POST /client/requests ({code})", r)
        req_id = r.json().get("request_id") if r.status_code < 400 else None
    else:
        print("     no accepted codes found for search term; skipping create")
        req_id = None

    # 7) summary + requests list
    jp("GET /client/summary", requests.get(f"{BASE}/api/client/summary", headers=H))
    r = jp("GET /client/requests", requests.get(f"{BASE}/api/client/requests", headers=H))
    print("     my requests:", r.json().get("count"))

    # 8) reorder + detail
    if req_id:
        jp("GET /client/requests/{id}", requests.get(f"{BASE}/api/client/requests/{req_id}", headers=H))
        jp("POST /client/requests/{id}/reorder", requests.post(f"{BASE}/api/client/requests/{req_id}/reorder", headers=H))

    # 9) documents
    jp("GET /client/documents", requests.get(f"{BASE}/api/client/documents", headers=H))

    # 10) public inquiry (callback)
    jp("POST /public/inquiry", requests.post(f"{BASE}/api/public/inquiry",
        json={"name": "Іван", "phone": "+380501234567", "email": "ivan@clinic.ua", "company_name": "Клініка", "message": "Передзвоніть", "type": "callback"}))

    # 11) staff inbox
    admin = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@bibi.cars", "password": "Admin12345!"}).json()
    AH = {"Authorization": f"Bearer {admin['access_token']}"}
    r = jp("GET /waste/inquiries (staff)", requests.get(f"{BASE}/api/waste/inquiries", headers=AH))
    inqs = r.json().get("items", [])
    print("     inquiries:", r.json().get("counts"))
    if inqs:
        iid = inqs[0]["id"]
        jp("PATCH /waste/inquiries/{id}", requests.patch(f"{BASE}/api/waste/inquiries/{iid}", headers=AH,
            json={"status": "in_progress", "note": "Передзвонили"}))

    print("\nPOC DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
