"""
Quick script to create a contract with a pending revision for UI testing
"""
import requests
import io

BASE_URL = "https://environmental-utils.preview.emergentagent.com/api"

# Login as staff
print("1. Staff login...")
r = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "admin@bibi.cars",
    "password": "N3wAdm!n-2026-x7Qz"
})
staff_token = r.json().get("token") or r.json().get("access_token")
print(f"   Staff token: {staff_token[:20]}...")

# Login as client
print("2. Client login...")
r = requests.post(f"{BASE_URL}/customer-auth/login", json={
    "email": "client@demo.com",
    "password": "N3wCli!-2026-t9Mv"
})
client_token = r.json().get("token") or r.json().get("access_token")
customer_id = r.json().get("customerId") or r.json().get("customer_id")
print(f"   Client token: {client_token[:20]}...")
print(f"   Customer ID: {customer_id}")

# Get contract types
print("3. Get contract types...")
r = requests.get(f"{BASE_URL}/waste/cflow/types", headers={"Authorization": f"Bearer {staff_token}"})
types = r.json().get("items", [])
contract_type_id = next((t["id"] for t in types if t.get("code") in ["one_time", "quarterly", "regular"]), None)
print(f"   Using type: {contract_type_id}")

# Create contract
print("4. Create contract...")
r = requests.post(f"{BASE_URL}/waste/cflow/contracts", 
    headers={"Authorization": f"Bearer {staff_token}", "Content-Type": "application/json"},
    json={
        "customer_id": customer_id,
        "contract_type_id": contract_type_id,
        "service_name": "UI Test Service",
        "value": 3000,
        "currency": "UAH",
        "title": "UI Test Contract with Revision"
    }
)
contract = r.json()
contract_id = contract["id"]
print(f"   Contract created: {contract_id}")

# Send for review
print("5. Send for review...")
requests.post(f"{BASE_URL}/waste/cflow/contracts/{contract_id}/send", 
    headers={"Authorization": f"Bearer {staff_token}"})

# Client opens
print("6. Client opens...")
requests.post(f"{BASE_URL}/client/cflow/contracts/{contract_id}/open", 
    headers={"Authorization": f"Bearer {client_token}"})

# Client accepts
print("7. Client accepts...")
requests.post(f"{BASE_URL}/client/cflow/contracts/{contract_id}/accept", 
    headers={"Authorization": f"Bearer {client_token}", "Content-Type": "application/json"},
    json={"read_confirmed": True})

# Upload proof
print("8. Upload proof...")
dummy_file = io.BytesIO(b"PROOF")
requests.post(f"{BASE_URL}/client/cflow/contracts/{contract_id}/proof", 
    headers={"Authorization": f"Bearer {client_token}"},
    files={"file": ("proof.pdf", dummy_file, "application/pdf")})

# Confirm payment
print("9. Confirm payment...")
requests.post(f"{BASE_URL}/waste/cflow/contracts/{contract_id}/confirm-payment", 
    headers={"Authorization": f"Bearer {staff_token}", "Content-Type": "application/json"},
    json={"reference": "UI-TEST"})

# Approve
print("10. Approve → ACTIVE...")
requests.post(f"{BASE_URL}/waste/cflow/contracts/{contract_id}/approve", 
    headers={"Authorization": f"Bearer {staff_token}"})

# Change legal address to create revision
print("11. Change legal address → CREATE REVISION...")
requests.put(f"{BASE_URL}/waste/cflow/legal-profile/{customer_id}", 
    headers={"Authorization": f"Bearer {staff_token}", "Content-Type": "application/json"},
    json={"legal_address": "м. Київ, вул. UI Test, 123"})

# Get contract to verify revision
print("12. Verify revision created...")
r = requests.get(f"{BASE_URL}/waste/cflow/contracts/{contract_id}", 
    headers={"Authorization": f"Bearer {staff_token}"})
contract = r.json()
status = contract.get("status")
revision = contract.get("revision")

print(f"\n✅ Contract ready for UI testing:")
print(f"   Contract ID: {contract_id}")
print(f"   Status: {status}")
print(f"   Has revision: {revision is not None}")
if revision:
    print(f"   Revision version: {revision.get('version')}")
    print(f"   Revision status: {revision.get('status')}")
print(f"\n   Staff URL: https://environmental-utils.preview.emergentagent.com/app/contract-flow")
print(f"   Client URL: https://environmental-utils.preview.emergentagent.com/client/contract-flow")
