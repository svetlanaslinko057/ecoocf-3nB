"""POC: classic email registration + verify + cabinet + company link + manager assign."""
import sys, time, requests

BASE = "http://localhost:8001"


def jp(label, r):
    ok = r.status_code < 400
    print(f"[{'OK ' if ok else 'ERR'}] {label}: {r.status_code}")
    if not ok:
        print("     ->", r.text[:300])
    return r


def main():
    email = f"clinic{int(time.time())}@example.com"
    pwd = "Str0ngPass!23"

    # 1) register (B2B fields)
    r = jp("POST /customer-auth/register", requests.post(f"{BASE}/api/customer-auth/register", json={
        "email": email, "password": pwd, "name": "Олена", "surname": "Коваль",
        "middle_name": "Іванівна", "company_name": "КНП Лікарня №7", "phone": "+380501112233",
    }))
    if r.status_code >= 400:
        return 1
    body = r.json()
    code = body.get("devCode")
    print("     dry_run:", body.get("dry_run"), "devCode:", code)
    assert code, "devCode missing — dry-run fallback not working"

    # 2) verify -> session
    r = jp("POST /customer-auth/verify-email", requests.post(f"{BASE}/api/customer-auth/verify-email",
            json={"email": email, "code": code}))
    if r.status_code >= 400:
        return 1
    vr = r.json()
    token = vr.get("sessionToken") or vr.get("token")
    print("     name:", vr.get("name"), "token len:", len(token or ""))
    H = {"Authorization": f"Bearer {token}"}

    # 3) /client/me (cabinet shares the session) + company link
    r = jp("GET /client/me", requests.get(f"{BASE}/api/client/me", headers=H))
    cust = r.json().get("customer", {})
    print("     company_name:", cust.get("company_name"), "company_id:", cust.get("company_id"))
    assert cust.get("company_id"), "company not linked"

    # 4) login with the same credentials
    r = jp("POST /customer-auth/login", requests.post(f"{BASE}/api/customer-auth/login",
            json={"email": email, "password": pwd}))
    assert r.status_code < 400 and (r.json().get("sessionToken")), "login failed"

    # 5) verify manager auto-assignment (admin view of company)
    admin = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@bibi.cars", "password": "Admin12345!"}).json()
    AH = {"Authorization": f"Bearer {admin['access_token']}"}
    r = requests.get(f"{BASE}/api/waste/companies", headers=AH, params={"q": "Лікарня №7"})
    if r.status_code < 400:
        items = r.json().get("items") or r.json().get("companies") or r.json().get("data") or []
        print("     companies found:", len(items))
        if items:
            print("     assigned_manager_id:", items[0].get("assigned_manager_id"))

    # 6) admin email/integrations surface (Resend manageable)
    r = jp("GET /admin/integrations", requests.get(f"{BASE}/api/admin/integrations", headers=AH))
    if r.status_code < 400:
        provs = [p.get("provider") for p in r.json()]
        print("     providers:", provs)
        assert "resend" in provs

    print("\nPOC DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
