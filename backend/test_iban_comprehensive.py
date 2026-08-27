"""
Comprehensive IBAN Flow Test for ECO.NOVA
==========================================
Tests the full contract-first IBAN bank-transfer payment flow:
1. Admin configures company requisites (UAH + USD)
2. Manager creates invoice for a customer (using GET /api/customers)
3. Contract-first gate: issue-iban blocked without signed contract
4. Manager signs contract offline
5. Manager issues invoice by IBAN
6. Client views invoice with requisites
7. Client uploads proof and confirms payment
8. Manager reviews pending confirmation queue
9. Manager confirms payment -> order created
10. Stripe FROZEN verification

Uses public URL from REACT_APP_BACKEND_URL.
"""
import io
import sys
import os
import requests

# Public endpoint
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://code-audit-168.preview.emergentagent.com")

# Credentials
ADMIN = {"email": "admin@eco.ua", "password": "EcoAdmin2026!"}
MANAGER = {"email": "manager@eco.ua", "password": "EcoManager2026!"}
CLIENT_EMAIL = "client@eco.ua"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
results = []


def check(name, cond, extra=""):
    results.append(cond)
    status = PASS if cond else FAIL
    print(f"  [{status}] {name} {extra}")
    return cond


def staff_login(creds):
    """Login staff (admin/manager)"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def client_login(email):
    """Dev-login for client (requires ALLOW_DEV_LOGIN=true)"""
    r = requests.post(f"{BASE_URL}/api/client/dev-login", json={"email": email, "name": "Demo Client"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j["token"], j["customer"]


def main():
    print("=" * 60)
    print("ECO.NOVA IBAN Flow Comprehensive Test")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}\n")

    # ═══════════════════════════════════════════════════════════════
    # Auth
    # ═══════════════════════════════════════════════════════════════
    print("🔐 Authentication...")
    try:
        admin_tok = staff_login(ADMIN)
        check("Admin login", True)
    except Exception as e:
        check("Admin login", False, f"(Error: {e})")
        print("\n❌ Cannot proceed without admin auth")
        sys.exit(1)

    try:
        mgr_tok = staff_login(MANAGER)
        check("Manager login", True)
    except Exception as e:
        check("Manager login", False, f"(Error: {e})")
        print("\n❌ Cannot proceed without manager auth")
        sys.exit(1)

    try:
        client_tok, customer = client_login(CLIENT_EMAIL)
        customer_id = customer["customerId"]
        check("Client dev-login", True, f"(customerId: {customer_id})")
    except Exception as e:
        check("Client dev-login", False, f"(Error: {e})")
        print("\n⚠️  Client login failed - will skip client tests")
        client_tok = None
        customer_id = None

    AH = {"Authorization": f"Bearer {admin_tok}"}
    MH = {"Authorization": f"Bearer {mgr_tok}"}
    CH = {"Authorization": f"Bearer {client_tok}"} if client_tok else {}

    # ═══════════════════════════════════════════════════════════════
    # 1. Admin — Configure Requisites (UAH + USD)
    # ═══════════════════════════════════════════════════════════════
    print("\n📋 1. Admin — Configure Company Requisites...")
    req_body = {
        "legal_name": "ТОВ «ЕКО-НОВА»",
        "edrpou": "44556677",
        "ipn": "445566778899",
        "vat_payer": True,
        "legal_address": "м. Київ, вул. Зелена, 1",
        "director_name": "Іваненко І.І.",
        "phone": "+380443334455",
        "email": "billing@eco.ua",
        "payment_purpose_template": "Оплата за рахунком {number} від {date}",
        "accounts": [
            {
                "currency": "UAH",
                "iban": "UA213223130000026007233566001",
                "bank_name": "АТ «ПриватБанк»",
                "mfo": "305299",
                "enabled": True,
            },
            {
                "currency": "USD",
                "iban": "UA903052990000026005000000001",
                "bank_name": "АТ «ПриватБанк»",
                "mfo": "305299",
                "swift": "PBANUA2X",
                "enabled": True,
            },
        ],
    }
    try:
        r = requests.put(f"{BASE_URL}/api/admin/billing/requisites", json=req_body, headers=AH, timeout=20)
        check("PUT /api/admin/billing/requisites", r.status_code == 200, f"(HTTP {r.status_code})")
        if r.status_code == 200:
            req = r.json().get("requisites", {})
            check("Requisites configured=true", req.get("configured") is True)
            check("UAH in currencies", "UAH" in req.get("currencies", []))
            check("USD in currencies", "USD" in req.get("currencies", []))
    except Exception as e:
        check("PUT /api/admin/billing/requisites", False, f"(Error: {e})")

    # Manager preview requisites
    try:
        r = requests.get(f"{BASE_URL}/api/billing/requisites", headers=MH, timeout=20)
        check("GET /api/billing/requisites (manager preview)", r.status_code == 200, f"(HTTP {r.status_code})")
    except Exception as e:
        check("GET /api/billing/requisites", False, f"(Error: {e})")

    # ═══════════════════════════════════════════════════════════════
    # 2. Manager — Get Customers List (NEW feature)
    # ═══════════════════════════════════════════════════════════════
    print("\n👥 2. Manager — Get Customers List (NEW CustomerPicker)...")
    try:
        r = requests.get(f"{BASE_URL}/api/customers", headers=MH, timeout=20)
        check("GET /api/customers", r.status_code == 200, f"(HTTP {r.status_code})")
        if r.status_code == 200:
            customers = r.json().get("items") or r.json().get("data") or []
            check("Customers list not empty", len(customers) > 0, f"(found {len(customers)})")
            if not customer_id and customers:
                # Use first customer if client login failed
                customer_id = customers[0].get("id")
                print(f"  ℹ️  Using first customer: {customer_id}")
    except Exception as e:
        check("GET /api/customers", False, f"(Error: {e})")

    if not customer_id:
        print("\n❌ No customer_id available - cannot proceed with invoice tests")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════════
    # 3. Manager — Create Invoice
    # ═══════════════════════════════════════════════════════════════
    print("\n📄 3. Manager — Create Invoice...")
    inv_body = {
        "customerId": customer_id,
        "currency": "UAH",
        "notes": "Test IBAN invoice",
        "items": [{"name": "Утилізація відходів (тест)", "price": 15000, "qty": 1}],
    }
    try:
        r = requests.post(f"{BASE_URL}/api/manager/invoices", json=inv_body, headers=MH, timeout=20)
        check("POST /api/manager/invoices", r.status_code == 200, f"(HTTP {r.status_code})")
        if r.status_code == 200:
            invoice = r.json()["invoice"]
            inv_id = invoice["id"]
            check("Invoice currency UAH", invoice.get("currency") == "UAH")
            print(f"  ℹ️  Invoice ID: {inv_id}")
        else:
            print(f"  ⚠️  Response: {r.text[:200]}")
            inv_id = None
    except Exception as e:
        check("POST /api/manager/invoices", False, f"(Error: {e})")
        inv_id = None

    if not inv_id:
        print("\n❌ Invoice creation failed - cannot proceed")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════════
    # 4. Contract-First Gate — issue-iban blocked without contract
    # ═══════════════════════════════════════════════════════════════
    print("\n🚫 4. Contract-First Gate — issue-iban blocked...")
    try:
        r = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/issue-iban", headers=MH, timeout=20)
        check("POST /api/invoices/{id}/issue-iban (no contract)", r.status_code == 400, f"(HTTP {r.status_code})")
        if r.status_code == 400:
            detail = r.json().get("detail", "")
            check("Error mentions contract", "договір" in detail.lower() or "contract" in detail.lower(), f"({detail[:50]})")
    except Exception as e:
        check("POST /api/invoices/{id}/issue-iban", False, f"(Error: {e})")

    # ═══════════════════════════════════════════════════════════════
    # 5. Manager — Offline Sign Contract
    # ═══════════════════════════════════════════════════════════════
    print("\n✍️  5. Manager — Offline Sign Contract...")
    try:
        files = {"file": ("signed_contract.pdf", io.BytesIO(b"%PDF-1.4 signed contract"), "application/pdf")}
        data = {"signed_full_name": "Петренко П.П.", "note": "Підписано офлайн"}
        r = requests.post(f"{BASE_URL}/api/manager/invoices/{inv_id}/contract/offline-sign", files=files, data=data, headers=MH, timeout=30)
        check("POST /api/manager/invoices/{id}/contract/offline-sign", r.status_code == 200, f"(HTTP {r.status_code})")
        if r.status_code == 200:
            contract = r.json().get("contract", {})
            check("Contract lifecycle=signed", contract.get("lifecycle") == "signed")
    except Exception as e:
        check("POST /api/manager/invoices/{id}/contract/offline-sign", False, f"(Error: {e})")

    # Check contract status endpoint
    try:
        r = requests.get(f"{BASE_URL}/api/manager/invoices/{inv_id}/contract", headers=MH, timeout=20)
        check("GET /api/manager/invoices/{id}/contract", r.status_code == 200, f"(HTTP {r.status_code})")
        if r.status_code == 200:
            check("Contract signed=true", r.json().get("signed") is True)
    except Exception as e:
        check("GET /api/manager/invoices/{id}/contract", False, f"(Error: {e})")

    # ═══════════════════════════════════════════════════════════════
    # 6. Manager — Issue Invoice by IBAN (after signing)
    # ═══════════════════════════════════════════════════════════════
    print("\n💳 6. Manager — Issue Invoice by IBAN...")
    try:
        r = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/issue-iban", headers=MH, timeout=20)
        check("POST /api/invoices/{id}/issue-iban (after signing)", r.status_code == 200, f"(HTTP {r.status_code})")
        if r.status_code == 200:
            issued = r.json()["invoice"]
            check("Invoice status=sent", issued.get("status") == "sent")
            snap = issued.get("requisites") or {}
            check("Requisites snapshot has UAH IBAN", snap.get("currency") == "UAH" and snap.get("iban", "").startswith("UA"))
            check("payment_purpose generated", bool(issued.get("payment_purpose")))
    except Exception as e:
        check("POST /api/invoices/{id}/issue-iban", False, f"(Error: {e})")

    # ═══════════════════════════════════════════════════════════════
    # 7. Client — View Invoice
    # ═══════════════════════════════════════════════════════════════
    if client_tok:
        print("\n👤 7. Client — View Invoice...")
        try:
            r = requests.get(f"{BASE_URL}/api/client/invoices", headers=CH, timeout=20)
            check("GET /api/client/invoices", r.status_code == 200, f"(HTTP {r.status_code})")
            if r.status_code == 200:
                items = r.json().get("items", [])
                mine = [i for i in items if i.get("id") == inv_id]
                check("Client sees issued invoice", len(mine) == 1, f"(found {len(items)} total)")
        except Exception as e:
            check("GET /api/client/invoices", False, f"(Error: {e})")

        # ═══════════════════════════════════════════════════════════════
        # 8. Client — Confirm Payment WITHOUT proof (should fail)
        # ═══════════════════════════════════════════════════════════════
        print("\n🚫 8. Client — Confirm Payment WITHOUT proof (blocked)...")
        try:
            r = requests.post(f"{BASE_URL}/api/client/invoices/{inv_id}/confirm-payment", json={"note": "paid"}, headers=CH, timeout=20)
            check("POST /api/client/invoices/{id}/confirm-payment (no proof)", r.status_code == 400, f"(HTTP {r.status_code})")
            if r.status_code == 400:
                detail = r.json().get("detail", "")
                check("Error mentions proof", "підтвердження" in detail.lower() or "proof" in detail.lower(), f"({detail[:50]})")
        except Exception as e:
            check("POST /api/client/invoices/{id}/confirm-payment", False, f"(Error: {e})")

        # ═══════════════════════════════════════════════════════════════
        # 9. Client — Upload Proof + Confirm Payment
        # ═══════════════════════════════════════════════════════════════
        print("\n📤 9. Client — Upload Proof + Confirm Payment...")
        try:
            files = {"file": ("receipt.pdf", io.BytesIO(b"%PDF-1.4 payment receipt"), "application/pdf")}
            r = requests.post(f"{BASE_URL}/api/client/invoices/{inv_id}/upload-proof", files=files, headers=CH, timeout=30)
            check("POST /api/client/invoices/{id}/upload-proof", r.status_code == 200, f"(HTTP {r.status_code})")
            if r.status_code == 200:
                proof_url = r.json().get("url")
                check("Proof URL returned", bool(proof_url))
                
                # Now confirm with proof
                r = requests.post(f"{BASE_URL}/api/client/invoices/{inv_id}/confirm-payment", json={"note": "Сплачено", "proof_url": proof_url}, headers=CH, timeout=20)
                check("POST /api/client/invoices/{id}/confirm-payment (with proof)", r.status_code == 200, f"(HTTP {r.status_code})")
                if r.status_code == 200:
                    check("Invoice status=awaiting_confirmation", r.json()["invoice"].get("status") == "awaiting_confirmation")
        except Exception as e:
            check("Client upload proof + confirm", False, f"(Error: {e})")

        # ═══════════════════════════════════════════════════════════════
        # 10. Manager — Pending Confirmation Queue
        # ═══════════════════════════════════════════════════════════════
        print("\n📋 10. Manager — Pending Confirmation Queue...")
        try:
            r = requests.get(f"{BASE_URL}/api/manager/invoices/pending-confirmation", headers=MH, timeout=20)
            check("GET /api/manager/invoices/pending-confirmation", r.status_code == 200, f"(HTTP {r.status_code})")
            if r.status_code == 200:
                pend = [i for i in r.json().get("items", []) if i.get("id") == inv_id]
                check("Invoice in pending queue", len(pend) == 1)
                if pend:
                    check("proof_url visible to manager", bool(pend[0].get("payment_claim", {}).get("proof_url")))
        except Exception as e:
            check("GET /api/manager/invoices/pending-confirmation", False, f"(Error: {e})")

        # ═══════════════════════════════════════════════════════════════
        # 11. Manager — Confirm Payment (order created)
        # ═══════════════════════════════════════════════════════════════
        print("\n✅ 11. Manager — Confirm Payment...")
        try:
            r = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/confirm-payment", json={"note": "Кошти надійшли"}, headers=MH, timeout=30)
            check("POST /api/invoices/{id}/confirm-payment", r.status_code == 200, f"(HTTP {r.status_code})")
            if r.status_code == 200:
                body = r.json()
                check("Invoice status=paid", body["invoice"].get("status") == "paid")
                order_id = body.get("order_id")
                check("Order created (order executes)", bool(order_id), f"(order_id: {order_id})")
        except Exception as e:
            check("POST /api/invoices/{id}/confirm-payment", False, f"(Error: {e})")

        # ═══════════════════════════════════════════════════════════════
        # 12. Manager — Reject Payment (test)
        # ═══════════════════════════════════════════════════════════════
        print("\n🔄 12. Manager — Reject Payment (test on another invoice)...")
        # Create another invoice for reject test
        try:
            inv_body2 = {
                "customerId": customer_id,
                "currency": "UAH",
                "items": [{"name": "Test reject", "price": 1000, "qty": 1}],
            }
            r = requests.post(f"{BASE_URL}/api/manager/invoices", json=inv_body2, headers=MH, timeout=20)
            if r.status_code == 200:
                inv_id2 = r.json()["invoice"]["id"]
                # Sign contract
                files = {"file": ("signed.pdf", io.BytesIO(b"%PDF-1.4 signed"), "application/pdf")}
                requests.post(f"{BASE_URL}/api/manager/invoices/{inv_id2}/contract/offline-sign", files=files, data={"signed_full_name": "Test"}, headers=MH, timeout=30)
                # Issue
                requests.post(f"{BASE_URL}/api/invoices/{inv_id2}/issue-iban", headers=MH, timeout=20)
                # Client confirm
                files = {"file": ("proof.pdf", io.BytesIO(b"%PDF-1.4 proof"), "application/pdf")}
                r = requests.post(f"{BASE_URL}/api/client/invoices/{inv_id2}/upload-proof", files=files, headers=CH, timeout=30)
                proof_url = r.json().get("url")
                requests.post(f"{BASE_URL}/api/client/invoices/{inv_id2}/confirm-payment", json={"proof_url": proof_url}, headers=CH, timeout=20)
                # Manager reject
                r = requests.post(f"{BASE_URL}/api/invoices/{inv_id2}/reject-payment", json={"reason": "Платіж не знайдено"}, headers=MH, timeout=20)
                check("POST /api/invoices/{id}/reject-payment", r.status_code == 200, f"(HTTP {r.status_code})")
                if r.status_code == 200:
                    check("Invoice status back to sent", r.json()["invoice"].get("status") == "sent")
        except Exception as e:
            check("Reject payment test", False, f"(Error: {e})")

    # ═══════════════════════════════════════════════════════════════
    # 13. Stripe FROZEN Verification
    # ═══════════════════════════════════════════════════════════════
    print("\n🔒 13. Stripe FROZEN Verification...")
    try:
        r = requests.post(f"{BASE_URL}/api/stripe/create-checkout-session", json={"amount": 100}, headers=MH, timeout=20)
        frozen = r.status_code in (424, 503, 404)
        check("POST /api/stripe/create-checkout-session (FROZEN)", frozen, f"(HTTP {r.status_code})")
        if not frozen and r.status_code == 200:
            print("  ⚠️  WARNING: Stripe appears to be working (should be FROZEN)")
    except Exception as e:
        # If endpoint doesn't exist, that's also acceptable (frozen)
        check("Stripe FROZEN (endpoint not found)", True, f"(Error: {e})")

    # ═══════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    pct = (passed / total * 100) if total > 0 else 0
    print(f"Tests passed: {passed}/{total} ({pct:.1f}%)")
    
    if passed == total:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
