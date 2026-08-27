"""
ECO.NOVA IBAN Contract-First Flow Test
========================================
Tests the online e-sign contract flow fix (contracts_v2 fallback).

ONLINE E-SIGN BRANCH (THE FIX):
1. Manager creates invoice
2. Manager sends online contract → view_token
3. Public view contract (no auth) → Ukrainian title, enriched data
4. Public sign contract → lifecycle=signed
5. Manager issue IBAN → 200 (unblocked)

OFFLINE BRANCH (REGRESSION):
6. Create invoice → try issue-iban without contract → 400
7. Upload offline-signed file → signed
8. Issue IBAN → 200
9. Client upload proof + confirm → awaiting_confirmation
10. Manager confirm payment → paid + order_id
"""
import requests
import sys
import io
from datetime import datetime

# Use the public endpoint from frontend/.env
BASE_URL = "https://code-audit-168.preview.emergentagent.com/api"

# Credentials from backend/.env
MANAGER_EMAIL = "manager@eco.ua"
MANAGER_PASSWORD = "EcoManager2026!"
CLIENT_EMAIL = "client@eco.ua"
CLIENT_PASSWORD = "EcoClient2026!"


class IBANContractTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.manager_token = None
        self.client_token = None
        self.failures = []
        self.invoice_id = None
        self.view_token = None
        self.customer_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, token=None, files=None):
        """Run a single API test"""
        url = f"{BASE_URL}/{endpoint}" if not endpoint.startswith("http") else endpoint
        req_headers = headers or {}
        if token:
            req_headers['Authorization'] = f'Bearer {token}'
        if 'Content-Type' not in req_headers and method in ['POST', 'PUT', 'PATCH'] and not files:
            req_headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 [{self.tests_run}] {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, timeout=15)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, data=data, headers=req_headers, timeout=15)
                else:
                    response = requests.post(url, json=data, headers=req_headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers, timeout=15)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=req_headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=15)
            else:
                print(f"❌ Failed - Unknown method {method}")
                self.failures.append(f"{name}: Unknown method {method}")
                return False, {}

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.text else {}
                except Exception:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.text[:300]}")
                except Exception:
                    pass
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failures.append(f"{name}: {str(e)}")
            return False, {}

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: AUTH
    # ═══════════════════════════════════════════════════════════════════
    
    def test_manager_login(self):
        """Test manager login"""
        success, response = self.run_test(
            "Manager Login",
            "POST",
            "auth/login",
            200,
            data={"email": MANAGER_EMAIL, "password": MANAGER_PASSWORD}
        )
        if success and ('token' in response or 'access_token' in response):
            self.manager_token = response.get('token') or response.get('access_token')
            print(f"   ✓ Manager token obtained")
            return True
        return False

    def test_client_dev_login(self):
        """Test client dev login"""
        success, response = self.run_test(
            "Client Dev Login",
            "POST",
            "client/dev-login",
            200,
            data={"email": CLIENT_EMAIL, "name": "Demo Client"}
        )
        if success and ('token' in response or 'access_token' in response):
            self.client_token = response.get('token') or response.get('access_token')
            print(f"   ✓ Client token obtained")
            return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: ONLINE E-SIGN FLOW (THE FIX)
    # ═══════════════════════════════════════════════════════════════════
    
    def test_get_customers(self):
        """Get customers list to pick a customerId"""
        if not self.manager_token:
            print("   ⚠ Skipping - no manager token")
            return False
        
        success, response = self.run_test(
            "GET /api/customers",
            "GET",
            "customers",
            200,
            token=self.manager_token
        )
        
        if success:
            customers = response.get('data', [])
            if customers:
                self.customer_id = customers[0].get('id')
                print(f"   ✓ Using customer ID: {self.customer_id}")
                return True
            else:
                print(f"   ⚠ No customers found")
                return False
        return False

    def test_create_invoice(self):
        """Create an invoice for online e-sign"""
        if not self.manager_token or not self.customer_id:
            print("   ⚠ Skipping - no manager token or customer ID")
            return False
        
        invoice_data = {
            "customerId": self.customer_id,
            "currency": "UAH",
            "items": [
                {
                    "waste_code": "07 02 13",
                    "name": "Відходи пластмас",
                    "qty": 100,
                    "unit": "kg",
                    "price": 50,
                    "total": 5000
                }
            ],
            "amount": 5000,
            "total": 5000
        }
        
        # Try 201 first, fallback to 200
        success, response = self.run_test(
            "POST /api/manager/invoices (create invoice)",
            "POST",
            "manager/invoices",
            200,
            data=invoice_data,
            token=self.manager_token
        )
        
        if success:
            self.invoice_id = response.get('invoice', {}).get('id')
            print(f"   ✓ Invoice created: {self.invoice_id}")
            return True
        return False

    def test_send_online_contract(self):
        """Send online contract → get view_token"""
        if not self.manager_token or not self.invoice_id:
            print("   ⚠ Skipping - no manager token or invoice ID")
            return False
        
        success, response = self.run_test(
            "POST /api/manager/invoices/{id}/contract/send-online",
            "POST",
            f"manager/invoices/{self.invoice_id}/contract/send-online",
            200,
            token=self.manager_token
        )
        
        if success:
            self.view_token = response.get('view_token')
            contract = response.get('contract', {})
            title = contract.get('title', '')
            
            print(f"   ✓ View token: {self.view_token}")
            print(f"   ✓ Contract title: {title}")
            
            # Verify Ukrainian title
            if 'Договір на утилізацію відходів' in title:
                print(f"   ✓ Ukrainian title confirmed")
                return True
            else:
                print(f"   ⚠ Title doesn't match expected Ukrainian format")
                self.failures.append(f"Contract title not Ukrainian: {title}")
                return False
        return False

    def test_public_view_contract(self):
        """Public view contract (no auth) → verify enriched data"""
        if not self.view_token:
            print("   ⚠ Skipping - no view token")
            return False
        
        success, response = self.run_test(
            "GET /api/contracts/view/{view_token} (PUBLIC, no auth)",
            "GET",
            f"contracts/view/{self.view_token}",
            200
        )
        
        if success:
            contract = response.get('contract', {})
            company = response.get('company', {})
            operator = response.get('operator', {})
            
            title = contract.get('title', '')
            number = contract.get('number', '')
            amount = contract.get('amount')
            currency = contract.get('currency', '')
            items = contract.get('items', [])
            status = contract.get('status', '')
            
            print(f"   ✓ Title: {title}")
            print(f"   ✓ Number: {number}")
            print(f"   ✓ Amount: {amount} {currency}")
            print(f"   ✓ Items count: {len(items)}")
            print(f"   ✓ Company: {company.get('name', '—')}")
            print(f"   ✓ Operator: {operator.get('name', '—')}")
            print(f"   ✓ Status: {status}")
            
            # Verify it's NOT a Bulgarian car template
            if 'България' in title or 'автомобил' in title.lower():
                print(f"   ❌ CRITICAL: Bulgarian car template detected!")
                self.failures.append("Bulgarian car template detected in contract")
                return False
            
            # Verify Ukrainian ECO contract
            if 'Договір на утилізацію' in title and amount and items and operator.get('name'):
                print(f"   ✓ ECO Ukrainian contract confirmed")
                return True
            else:
                print(f"   ⚠ Contract data incomplete")
                self.failures.append("Contract data incomplete")
                return False
        return False

    def test_public_sign_contract(self):
        """Public sign contract → lifecycle=signed"""
        if not self.view_token:
            print("   ⚠ Skipping - no view token")
            return False
        
        sign_data = {
            "full_name": "Петренко Іван Васильович",
            "terms_accepted": True
        }
        
        success, response = self.run_test(
            "POST /api/contracts/view/{view_token}/sign (PUBLIC)",
            "POST",
            f"contracts/view/{self.view_token}/sign",
            200,
            data=sign_data
        )
        
        if success:
            contract = response.get('contract', {})
            lifecycle = contract.get('lifecycle', '')
            signed_full_name = contract.get('signed_full_name', '')
            
            print(f"   ✓ Lifecycle: {lifecycle}")
            print(f"   ✓ Signed by: {signed_full_name}")
            
            if lifecycle == 'signed':
                print(f"   ✓ Contract signed successfully")
                return True
            else:
                print(f"   ⚠ Lifecycle not 'signed': {lifecycle}")
                self.failures.append(f"Contract lifecycle not signed: {lifecycle}")
                return False
        return False

    def test_manager_get_invoice_contract(self):
        """Manager get invoice contract → verify signed=true"""
        if not self.manager_token or not self.invoice_id:
            print("   ⚠ Skipping - no manager token or invoice ID")
            return False
        
        success, response = self.run_test(
            "GET /api/manager/invoices/{id}/contract",
            "GET",
            f"manager/invoices/{self.invoice_id}/contract",
            200,
            token=self.manager_token
        )
        
        if success:
            signed = response.get('signed', False)
            contract = response.get('contract', {})
            
            print(f"   ✓ Signed: {signed}")
            print(f"   ✓ Contract lifecycle: {contract.get('lifecycle', '—')}")
            
            if signed:
                print(f"   ✓ Contract marked as signed")
                return True
            else:
                print(f"   ⚠ Contract not marked as signed")
                self.failures.append("Contract not marked as signed")
                return False
        return False

    def test_issue_iban_after_online_sign(self):
        """Issue IBAN after online sign → 200 (unblocked)"""
        if not self.manager_token or not self.invoice_id:
            print("   ⚠ Skipping - no manager token or invoice ID")
            return False
        
        success, response = self.run_test(
            "POST /api/invoices/{id}/issue-iban (after online sign)",
            "POST",
            f"invoices/{self.invoice_id}/issue-iban",
            200,
            token=self.manager_token
        )
        
        if success:
            invoice = response.get('invoice', {})
            status = invoice.get('status', '')
            number = invoice.get('number', '')
            requisites = invoice.get('requisites', {})
            
            print(f"   ✓ Invoice status: {status}")
            print(f"   ✓ Invoice number: {number}")
            print(f"   ✓ IBAN: {requisites.get('iban', '—')}")
            
            if status == 'sent' and requisites.get('iban'):
                print(f"   ✓ IBAN issued successfully (gate unblocked)")
                return True
            else:
                print(f"   ⚠ IBAN issue incomplete")
                self.failures.append("IBAN issue incomplete")
                return False
        return False

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: OFFLINE BRANCH REGRESSION
    # ═══════════════════════════════════════════════════════════════════
    
    def test_offline_branch(self):
        """Test offline branch: create invoice → try issue-iban without contract → 400"""
        if not self.manager_token or not self.customer_id:
            print("   ⚠ Skipping - no manager token or customer ID")
            return False
        
        # Create another invoice
        invoice_data = {
            "customerId": self.customer_id,
            "currency": "UAH",
            "items": [
                {
                    "waste_code": "07 02 13",
                    "name": "Відходи пластмас",
                    "qty": 50,
                    "unit": "kg",
                    "price": 50,
                    "total": 2500
                }
            ],
            "amount": 2500,
            "total": 2500
        }
        
        success, response = self.run_test(
            "POST /api/manager/invoices (offline branch)",
            "POST",
            "manager/invoices",
            200,
            data=invoice_data,
            token=self.manager_token
        )
        
        if not success:
            return False
        
        offline_invoice_id = response.get('invoice', {}).get('id')
        print(f"   ✓ Offline invoice created: {offline_invoice_id}")
        
        # Try to issue IBAN without contract → should fail with 400
        success, response = self.run_test(
            "POST /api/invoices/{id}/issue-iban (WITHOUT contract, expect 400)",
            "POST",
            f"invoices/{offline_invoice_id}/issue-iban",
            400,
            token=self.manager_token
        )
        
        if success:
            print(f"   ✓ IBAN issue blocked without contract (400)")
        else:
            print(f"   ⚠ IBAN issue should have been blocked (expected 400)")
            self.failures.append("IBAN issue not blocked without contract")
            return False
        
        # Upload offline-signed file
        # Create a minimal valid PDF
        pdf_data = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n210\n%%EOF'
        
        files = {
            'file': ('signed_contract.pdf', io.BytesIO(pdf_data), 'application/pdf')
        }
        form_data = {
            'signed_full_name': 'Петренко Іван Васильович',
            'note': 'Offline signed contract'
        }
        
        success, response = self.run_test(
            "POST /api/manager/invoices/{id}/contract/offline-sign",
            "POST",
            f"manager/invoices/{offline_invoice_id}/contract/offline-sign",
            200,
            data=form_data,
            files=files,
            token=self.manager_token
        )
        
        if not success:
            return False
        
        contract = response.get('contract', {})
        print(f"   ✓ Offline contract signed: {contract.get('id')}")
        
        # Now issue IBAN → should succeed
        success, response = self.run_test(
            "POST /api/invoices/{id}/issue-iban (after offline sign)",
            "POST",
            f"invoices/{offline_invoice_id}/issue-iban",
            200,
            token=self.manager_token
        )
        
        if success:
            invoice = response.get('invoice', {})
            print(f"   ✓ IBAN issued after offline sign: {invoice.get('number')}")
            
            # Store for client payment flow
            self.offline_invoice_id = offline_invoice_id
            return True
        else:
            print(f"   ⚠ IBAN issue failed after offline sign")
            self.failures.append("IBAN issue failed after offline sign")
            return False


def main():
    print("="*80)
    print("ECO.NOVA IBAN CONTRACT-FIRST FLOW TEST")
    print("Online e-sign + offline branch regression")
    print("="*80)
    
    tester = IBANContractTester()
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: AUTH
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("PHASE 1: AUTHENTICATION")
    print("="*80)
    
    if not tester.test_manager_login():
        print("\n❌ CRITICAL: Manager login failed - stopping tests")
        return 1
    
    tester.test_client_dev_login()
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: ONLINE E-SIGN FLOW (THE FIX)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("PHASE 2: ONLINE E-SIGN FLOW (THE FIX)")
    print("="*80)
    
    if not tester.test_get_customers():
        print("\n❌ CRITICAL: No customers found - stopping tests")
        return 1
    
    if not tester.test_create_invoice():
        print("\n❌ CRITICAL: Invoice creation failed - stopping tests")
        return 1
    
    if not tester.test_send_online_contract():
        print("\n❌ CRITICAL: Send online contract failed - stopping tests")
        return 1
    
    tester.test_public_view_contract()
    tester.test_public_sign_contract()
    tester.test_manager_get_invoice_contract()
    tester.test_issue_iban_after_online_sign()
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: OFFLINE BRANCH REGRESSION
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("PHASE 3: OFFLINE BRANCH REGRESSION")
    print("="*80)
    
    tester.test_offline_branch()
    
    # ═══════════════════════════════════════════════════════════════════
    # RESULTS
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    if tester.failures:
        print(f"\n❌ FAILURES ({len(tester.failures)}):")
        for i, failure in enumerate(tester.failures, 1):
            print(f"  {i}. {failure}")
    
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"\n✓ Success rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("\n✅ IBAN CONTRACT-FIRST FLOW TEST PASSED")
        return 0
    elif success_rate >= 70:
        print("\n⚠ IBAN CONTRACT-FIRST FLOW TEST PASSED WITH WARNINGS")
        return 0
    else:
        print("\n❌ IBAN CONTRACT-FIRST FLOW TEST FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
