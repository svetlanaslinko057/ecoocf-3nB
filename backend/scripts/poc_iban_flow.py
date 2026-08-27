"""
POC — full IBAN bank-transfer + contract-first flow (ECO.NOVA).

Runs end-to-end against the live local backend (http://localhost:8001):

  1. Admin sets company requisites (UAH account).
  2. Manager creates a UAH invoice for the demo client.
  3. issue-iban WITHOUT a signed contract -> expect 400 (contract-first gate).
  4. Manager attaches an offline-signed contract file -> contract signed.
  5. issue-iban -> success, invoice status == sent, requisites snapshot present.
  6. Client confirm-payment WITHOUT proof -> expect 400 (proof mandatory).
  7. Client uploads proof, then confirm-payment -> awaiting_confirmation.
  8. Manager pending-confirmation queue contains the invoice.
  9. Manager confirm-payment -> paid + order created (order executes).
 10. Assert an order document exists for the invoice.

Exit code 0 == all green.
"""
import io
import sys
import requests

BASE = "http://localhost:8001"
ADMIN = {"email": "admin@eco.ua", "password": "EcoAdmin2026!"}
MANAGER = {"email": "manager@eco.ua", "password": "EcoManager2026!"}
CLIENT_EMAIL = "client@eco.ua"

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []


def check(name, cond, extra=""):
    results.append(cond)
    print(f"  [{PASS if cond else FAIL}] {name} {extra}")
    return cond


def staff_login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def client_login(email):
    r = requests.post(f"{BASE}/api/client/dev-login", json={"email": email, "name": "Demo Client"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j["token"], j["customer"]


def main():
    print("== ECO.NOVA IBAN flow POC ==")
    admin_tok = staff_login(ADMIN)
    mgr_tok = staff_login(MANAGER)
    client_tok, customer = client_login(CLIENT_EMAIL)
    AH = {"Authorization": f"Bearer {admin_tok}"}
    MH = {"Authorization": f"Bearer {mgr_tok}"}
    CH = {"Authorization": f"Bearer {client_tok}"}
    customer_id = customer["customerId"]
    print(f"  client customerId = {customer_id}")

    # 1) Admin sets requisites (UAH)
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
            {"currency": "UAH", "iban": "UA213223130000026007233566001", "bank_name": "АТ «ПриватБанк»", "mfo": "305299", "enabled": True},
            {"currency": "USD", "iban": "UA903052990000026005000000001", "bank_name": "АТ «ПриватБанк»", "mfo": "305299", "enabled": True},
        ],
    }
    r = requests.put(f"{BASE}/api/admin/billing/requisites", json=req_body, headers=AH, timeout=20)
    check("admin set requisites", r.status_code == 200, f"(HTTP {r.status_code})")
    req = r.json().get("requisites", {})
    check("requisites configured + UAH present", req.get("configured") and "UAH" in req.get("currencies", []), str(req.get("currencies")))

    # 2) Manager creates a UAH invoice
    inv_body = {
        "customerId": customer_id,
        "currency": "UAH",
        "notes": "POC invoice",
        "items": [{"name": "Утилізація відходів (код 01)", "price": 12000, "qty": 1}],
    }
    r = requests.post(f"{BASE}/api/manager/invoices", json=inv_body, headers=MH, timeout=20)
    check("manager create invoice", r.status_code == 200, f"(HTTP {r.status_code})")
    invoice = r.json()["invoice"]
    inv_id = invoice["id"]
    check("invoice currency UAH", invoice.get("currency") == "UAH", invoice.get("currency"))
    print(f"  invoice id = {inv_id}")

    # 3) issue-iban WITHOUT signed contract -> 400
    r = requests.post(f"{BASE}/api/invoices/{inv_id}/issue-iban", headers=MH, timeout=20)
    check("issue-iban blocked without signed contract (400)", r.status_code == 400, f"(HTTP {r.status_code}: {r.json().get('detail','')[:50]})")

    # 4) Offline-sign contract (upload dummy PDF)
    files = {"file": ("signed_contract.pdf", io.BytesIO(b"%PDF-1.4 signed contract bytes"), "application/pdf")}
    data = {"signed_full_name": "Петренко П.П.", "note": "Підписано офлайн"}
    r = requests.post(f"{BASE}/api/manager/invoices/{inv_id}/contract/offline-sign", files=files, data=data, headers=MH, timeout=30)
    check("manager offline-sign contract", r.status_code == 200, f"(HTTP {r.status_code})")
    contract = r.json().get("contract", {})
    check("contract lifecycle == signed", contract.get("lifecycle") == "signed", contract.get("lifecycle"))

    # contract status endpoint
    r = requests.get(f"{BASE}/api/manager/invoices/{inv_id}/contract", headers=MH, timeout=20)
    check("contract status endpoint reports signed", r.json().get("signed") is True)

    # 5) issue-iban now succeeds
    r = requests.post(f"{BASE}/api/invoices/{inv_id}/issue-iban", headers=MH, timeout=20)
    check("issue-iban success after signing", r.status_code == 200, f"(HTTP {r.status_code})")
    issued = r.json()["invoice"]
    check("invoice status == sent", issued.get("status") == "sent", issued.get("status"))
    snap = issued.get("requisites") or {}
    check("requisites snapshot has UAH IBAN", (snap.get("currency") == "UAH") and snap.get("iban", "").startswith("UA"), snap.get("iban"))
    check("payment_purpose generated", bool(issued.get("payment_purpose")), issued.get("payment_purpose"))

    # 6) Client sees the invoice
    r = requests.get(f"{BASE}/api/client/invoices", headers=CH, timeout=20)
    check("client lists invoices", r.status_code == 200, f"(HTTP {r.status_code})")
    items = r.json().get("items", [])
    mine = [i for i in items if i.get("id") == inv_id]
    check("client sees the issued invoice", len(mine) == 1, f"(found {len(items)} total)")

    # 6b) confirm-payment WITHOUT proof -> 400
    r = requests.post(f"{BASE}/api/client/invoices/{inv_id}/confirm-payment", json={"note": "paid"}, headers=CH, timeout=20)
    check("client confirm blocked without proof (400)", r.status_code == 400, f"(HTTP {r.status_code})")

    # 7) upload proof then confirm
    files = {"file": ("receipt.pdf", io.BytesIO(b"%PDF-1.4 payment receipt"), "application/pdf")}
    r = requests.post(f"{BASE}/api/client/invoices/{inv_id}/upload-proof", files=files, headers=CH, timeout=30)
    check("client upload proof", r.status_code == 200, f"(HTTP {r.status_code})")
    proof_url = r.json().get("url")
    r = requests.post(f"{BASE}/api/client/invoices/{inv_id}/confirm-payment", json={"note": "Сплачено", "proof_url": proof_url}, headers=CH, timeout=20)
    check("client confirm payment (with proof)", r.status_code == 200, f"(HTTP {r.status_code})")
    check("invoice status == awaiting_confirmation", r.json()["invoice"].get("status") == "awaiting_confirmation", r.json()["invoice"].get("status"))

    # 8) Manager pending-confirmation queue
    r = requests.get(f"{BASE}/api/manager/invoices/pending-confirmation", headers=MH, timeout=20)
    check("manager pending-confirmation list", r.status_code == 200, f"(HTTP {r.status_code})")
    pend = [i for i in r.json().get("items", []) if i.get("id") == inv_id]
    check("invoice in pending queue", len(pend) == 1)
    if pend:
        check("proof_url visible to manager", bool(pend[0].get("payment_claim", {}).get("proof_url")))

    # 9) Manager confirm-payment -> paid + order
    r = requests.post(f"{BASE}/api/invoices/{inv_id}/confirm-payment", json={"note": "Гроші надійшли"}, headers=MH, timeout=30)
    check("manager confirm payment", r.status_code == 200, f"(HTTP {r.status_code})")
    body = r.json()
    check("invoice status == paid", body["invoice"].get("status") == "paid", body["invoice"].get("status"))
    order_id = body.get("order_id")
    check("order created (order executes)", bool(order_id), str(order_id))

    print("\n== RESULT ==")
    ok = all(results)
    print(f"  {sum(results)}/{len(results)} checks passed -> {'ALL GREEN ✅' if ok else 'FAILURES ❌'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
