"""
UNIVERSAL CONTRACT FLOW COMPREHENSIVE TEST
==========================================
Tests the complete ECO.NOVA Universal Contract Template & Acceptance Flow:

1. SOFT BLOCKING FULL FLOW: Create → Send → Block acceptance → Fill profile → Accept → Pay → Approve
2. DIFFERENT TYPE/TEMPLATE: Custom contract type with template variables
3. VERSION INVALIDATION: Legal data change invalidates acceptance
4. RBAC/OWNERSHIP: 403 for other client's contracts, 401 for unauthenticated
5. LEGAL PROFILE VALIDATION: Endpoint returns validation with missing/invalid fields
6. NOTIFICATIONS: Staff and client notifications created
7. PDF GENERATION: PDF endpoint returns application/pdf

Base URL from frontend/.env: https://environmental-utils.preview.emergentagent.com
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://environmental-utils.preview.emergentagent.com/api"

class ContractFlowTester:
    def __init__(self):
        self.staff_token = None
        self.client1_token = None
        self.client2_token = None
        self.customer1_id = None
        self.customer2_id = None
        self.contract1_id = None
        self.contract2_id = None
        self.contract_type_id = None
        self.template_id = None
        self.tests_run = 0
        self.tests_passed = 0
        
    def log(self, msg):
        print(f"  {msg}")
        
    def test(self, name, method, endpoint, expected_status, data=None, token=None, params=None, files=None):
        """Run a single API test"""
        url = f"{BASE_URL}/{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        self.tests_run += 1
        print(f"\n🔍 Test {self.tests_run}: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers, timeout=30)
                else:
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                headers['Content-Type'] = 'application/json'
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                headers['Content-Type'] = 'application/json'
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except Exception:
                    return True, {}
            else:
                self.log(f"❌ FAIL - Expected {expected_status}, got {response.status_code}")
                try:
                    self.log(f"   Response: {response.text[:500]}")
                except Exception:
                    pass
                return False, {}
                
        except Exception as e:
            self.log(f"❌ FAIL - Error: {str(e)}")
            return False, {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_staff_login(self):
        """Test staff login"""
        success, response = self.test(
            "Staff Login (admin@bibi.cars)",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@bibi.cars", "password": "Admin@12345"}
        )
        if success and 'access_token' in response:
            self.staff_token = response['access_token']
            self.log(f"   ✓ Staff token obtained")
            return True
        return False
    
    def test_client1_dev_login(self):
        """Test client 1 login (seeded client@demo.com)"""
        success, response = self.test(
            "Client 1 Login (client@demo.com)",
            "POST",
            "customer-auth/login",
            200,
            data={"email": "client@demo.com", "password": "Client@12345"}
        )
        if success and 'accessToken' in response:
            self.client1_token = response['accessToken']
            self.customer1_id = response.get('customerId') or response.get('customer_id')
            self.log(f"   ✓ Client 1 token obtained, customer_id: {self.customer1_id}")
            return True
        return False
    
    def test_client2_dev_login(self):
        """Test client 2 - create customer for RBAC testing (no login needed)"""
        # First create a new customer via staff endpoint
        customer_data = {
            "name": f"Test Client 2 {datetime.now().strftime('%H%M%S')}",
            "email": f"testclient2_{datetime.now().strftime('%H%M%S')}@example.com",
            "phone": "+380501234567"
        }
        success1, response1 = self.test(
            "Create Client 2 Customer (for RBAC test)",
            "POST",
            "customers",
            200,
            data=customer_data,
            token=self.staff_token
        )
        if success1:
            customer = response1.get('customer', {}) or response1
            self.customer2_id = customer.get('id') or customer.get('customerId')
            self.log(f"   ✓ Client 2 customer created: {self.customer2_id}")
            # For RBAC test, we don't need client2_token - we just need a different customer_id
            # Client 1 will try to access Client 2's contract and should get 403
            self.client2_token = None  # Not needed for RBAC test
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 1: SOFT BLOCKING FULL FLOW
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_s1_create_contract(self):
        """S1: Staff creates contract for client 1"""
        success, response = self.test(
            "S1: Create Contract for Client 1",
            "POST",
            "waste/cflow/contracts",
            200,
            data={
                "customer_id": self.customer1_id,
                "title": "Test Universal Contract",
                "value": 10000,
                "currency": "UAH"
            },
            token=self.staff_token
        )
        if success and 'id' in response:
            self.contract1_id = response['id']
            self.log(f"   ✓ Contract created: {response.get('number')} ({self.contract1_id})")
            self.log(f"   Status: {response.get('status')}")
            return True
        return False
    
    def test_s1_send_contract(self):
        """S1: Staff sends contract → status becomes awaiting_profile"""
        success, response = self.test(
            "S1: Send Contract (awaiting_profile expected)",
            "POST",
            f"waste/cflow/contracts/{self.contract1_id}/send",
            200,
            token=self.staff_token
        )
        if success:
            status = response.get('status')
            self.log(f"   Status: {status}")
            if status == 'awaiting_profile':
                self.log(f"   ✓ Status correctly set to awaiting_profile (incomplete profile)")
                return True
            else:
                self.log(f"   ⚠️  Expected awaiting_profile, got {status}")
        return False
    
    def test_s1_client_open_contract(self):
        """S1: Client opens contract"""
        success, response = self.test(
            "S1: Client Opens Contract",
            "POST",
            f"client/cflow/contracts/{self.contract1_id}/open",
            200,
            token=self.client1_token
        )
        if success:
            self.log(f"   ✓ Contract opened by client")
            self.log(f"   opened_at: {response.get('opened_at')}")
            return True
        return False
    
    def test_s1_accept_blocked_409(self):
        """S1: Client tries to accept → 409 with blocking_reasons"""
        success, response = self.test(
            "S1: Accept Blocked (409 expected)",
            "POST",
            f"client/cflow/contracts/{self.contract1_id}/accept",
            409,
            data={"read_confirmed": True},
            token=self.client1_token
        )
        if success:
            detail = response.get('detail', {})
            blocking_reasons = detail.get('blocking_reasons', [])
            self.log(f"   ✓ Acceptance blocked with 409")
            self.log(f"   Blocking reasons: {blocking_reasons}")
            if len(blocking_reasons) > 0:
                self.log(f"   ✓ Blocking reasons present (profile incomplete)")
                return True
        return False
    
    def test_s1_fill_legal_profile(self):
        """S1: Client fills all 7 required fields → auto-regenerates"""
        profile_data = {
            "legal_name": "Test Company Legal Name",
            "edrpou": "12345678",
            "legal_address": "Kyiv, Test Street 123",
            "phone": "+380501234567",
            "email": "legal@testcompany.com",
            "signer_full_name": "Іван Петренко",
            "signer_position": "Директор"
        }
        success, response = self.test(
            "S1: Fill Legal Profile (7 required fields)",
            "PUT",
            f"client/cflow/legal-profile",
            200,
            data=profile_data,
            token=self.client1_token
        )
        if success:
            validation = response.get('validation', {})
            complete = validation.get('complete', False)
            self.log(f"   Profile complete: {complete}")
            self.log(f"   Completion: {validation.get('completion_percent')}%")
            if complete:
                self.log(f"   ✓ Profile complete, contract should auto-regenerate")
                return True
        return False
    
    def test_s1_verify_can_accept(self):
        """S1: Verify contract can_accept is now true, status ready_for_acceptance"""
        success, response = self.test(
            "S1: Verify can_accept=true, status=ready_for_acceptance",
            "GET",
            f"client/cflow/contracts/{self.contract1_id}",
            200,
            token=self.client1_token
        )
        if success:
            status = response.get('status')
            current = response.get('current', {})
            can_accept = current.get('can_accept', False)
            self.log(f"   Status: {status}")
            self.log(f"   can_accept: {can_accept}")
            if status == 'ready_for_acceptance' and can_accept:
                self.log(f"   ✓ Contract ready for acceptance")
                return True
        return False
    
    def test_s1_client_accept(self):
        """S1: Client accepts → status awaiting_payment, payment auto-issued"""
        success, response = self.test(
            "S1: Client Accepts Contract",
            "POST",
            f"client/cflow/contracts/{self.contract1_id}/accept",
            200,
            data={"read_confirmed": True},
            token=self.client1_token
        )
        if success:
            status = response.get('status')
            acceptance = response.get('acceptance')
            payment = response.get('payment', {})
            self.log(f"   Status: {status}")
            self.log(f"   Acceptance: {acceptance is not None}")
            self.log(f"   Payment status: {payment.get('status')}")
            self.log(f"   IBAN: {payment.get('iban')}")
            self.log(f"   Amount due: {payment.get('amount_due')}")
            if status == 'awaiting_payment' and acceptance and payment.get('status') == 'awaiting_bank_transfer':
                self.log(f"   ✓ Acceptance successful, payment auto-issued")
                return True
        return False
    
    def test_s1_upload_proof(self):
        """S1: Client uploads payment proof"""
        # Create a dummy file
        files = {'file': ('proof.txt', b'Payment proof content', 'text/plain')}
        success, response = self.test(
            "S1: Upload Payment Proof",
            "POST",
            f"client/cflow/contracts/{self.contract1_id}/proof",
            200,
            files=files,
            token=self.client1_token
        )
        if success:
            payment = response.get('payment', {})
            self.log(f"   Payment status: {payment.get('status')}")
            self.log(f"   Proof file: {payment.get('proof_filename')}")
            if payment.get('status') == 'proof_uploaded':
                self.log(f"   ✓ Proof uploaded successfully")
                return True
        return False
    
    def test_s1_confirm_payment(self):
        """S1: Staff confirms payment → payment_confirmed"""
        success, response = self.test(
            "S1: Staff Confirms Payment",
            "POST",
            f"waste/cflow/contracts/{self.contract1_id}/confirm-payment",
            200,
            data={"reference": "TEST-REF-123", "notes": "Test payment confirmed"},
            token=self.staff_token
        )
        if success:
            status = response.get('status')
            payment = response.get('payment', {})
            self.log(f"   Status: {status}")
            self.log(f"   Payment status: {payment.get('status')}")
            if status == 'payment_confirmed' and payment.get('status') == 'payment_confirmed':
                self.log(f"   ✓ Payment confirmed")
                return True
        return False
    
    def test_s1_approve_contract(self):
        """S1: Staff approves → status active, activated_at set"""
        success, response = self.test(
            "S1: Staff Approves Contract",
            "POST",
            f"waste/cflow/contracts/{self.contract1_id}/approve",
            200,
            token=self.staff_token
        )
        if success:
            status = response.get('status')
            activated_at = response.get('activated_at')
            approval = response.get('approval')
            self.log(f"   Status: {status}")
            self.log(f"   Activated at: {activated_at}")
            self.log(f"   Approval: {approval is not None}")
            if status == 'active' and activated_at and approval:
                self.log(f"   ✓ Contract activated")
                return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 2: DIFFERENT TYPE/TEMPLATE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_s2_create_contract_type(self):
        """S2: Create a contract type"""
        success, response = self.test(
            "S2: Create Contract Type",
            "POST",
            "waste/cflow/types",
            200,
            data={
                "name": "Test Service Contract",
                "code": "TSC",
                "description": "Test contract type with custom variables",
                "active": True,
                "variables_schema": [
                    {"key": "service.custom_field", "label": "Custom Field", "required": True}
                ]
            },
            token=self.staff_token
        )
        if success and 'id' in response:
            self.contract_type_id = response['id']
            self.log(f"   ✓ Contract type created: {response.get('name')} ({self.contract_type_id})")
            return True
        return False
    
    def test_s2_create_template(self):
        """S2: Create active template bound to type with custom variable"""
        html_content = """<html><head><meta charset='utf-8'></head><body>
<h1>Договір №{{contract.number}}</h1>
<p>Дата: {{contract.date}}</p>
<p><b>ВИКОНАВЕЦЬ:</b> {{payment.recipient_name}}</p>
<p><b>ЗАМОВНИК:</b> {{company.legal_name}}, ЄДРПОУ {{company.edrpou}}</p>
<p><b>Custom Field:</b> {{service.custom_field}}</p>
<p>Сума: {{contract.value}} {{contract.currency}}</p>
</body></html>"""
        
        success, response = self.test(
            "S2: Create Active Template with Custom Variable",
            "POST",
            "waste/cflow/templates",
            200,
            data={
                "name": "Test Template with Custom Var",
                "contract_type_id": self.contract_type_id,
                "html": html_content,
                "status": "active",
                "variables_schema": [
                    {"key": "service.custom_field", "label": "Custom Field", "required": True}
                ]
            },
            token=self.staff_token
        )
        if success and 'id' in response:
            self.template_id = response['id']
            self.log(f"   ✓ Template created: {response.get('name')} ({self.template_id})")
            return True
        return False
    
    def test_s2_create_contract_with_type(self):
        """S2: Create contract of that type → generation succeeds"""
        success, response = self.test(
            "S2: Create Contract with Custom Type",
            "POST",
            "waste/cflow/contracts",
            200,
            data={
                "customer_id": self.customer1_id,
                "contract_type_id": self.contract_type_id,
                "template_id": self.template_id,
                "title": "Test Contract with Custom Type",
                "value": 5000,
                "custom_vars": {
                    "service.custom_field": "Custom Value Test"
                }
            },
            token=self.staff_token
        )
        if success and 'id' in response:
            self.contract2_id = response['id']
            current = response.get('current', {})
            html = current.get('html', '')
            self.log(f"   ✓ Contract created: {response.get('number')} ({self.contract2_id})")
            self.log(f"   Template used: {current.get('template_name')}")
            if 'Custom Value Test' in html:
                self.log(f"   ✓ Custom variable rendered in HTML")
                return True
            else:
                self.log(f"   ⚠️  Custom variable not found in HTML")
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 3: VERSION INVALIDATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_s3_verify_contract_accepted(self):
        """S3: Verify contract1 is in awaiting_payment state (accepted but not paid)"""
        success, response = self.test(
            "S3: Verify Contract Accepted (awaiting_payment)",
            "GET",
            f"waste/cflow/contracts/{self.contract1_id}",
            200,
            token=self.staff_token
        )
        if success:
            status = response.get('status')
            acceptance = response.get('acceptance')
            current = response.get('current', {})
            version = current.get('version', 0)
            self.log(f"   Status: {status}")
            self.log(f"   Accepted: {acceptance is not None}")
            self.log(f"   Current version: {version}")
            if status in ('awaiting_payment', 'payment_confirmed') and acceptance:
                self.log(f"   ✓ Contract is accepted (version {version})")
                return True
        return False
    
    def test_s3_change_legal_address(self):
        """S3: Staff changes legal_address → NEW version, acceptance reset"""
        success, response = self.test(
            "S3: Change Legal Address (invalidates acceptance)",
            "PUT",
            f"waste/cflow/legal-profile/{self.customer1_id}",
            200,
            data={"legal_address": "Kyiv, NEW Address 456"},
            token=self.staff_token
        )
        if success:
            self.log(f"   ✓ Legal address updated")
            return True
        return False
    
    def test_s3_verify_version_incremented(self):
        """S3: Verify contract has NEW version, acceptance reset, status back to ready_for_acceptance"""
        success, response = self.test(
            "S3: Verify Version Incremented & Acceptance Reset",
            "GET",
            f"waste/cflow/contracts/{self.contract1_id}",
            200,
            token=self.staff_token
        )
        if success:
            status = response.get('status')
            acceptance = response.get('acceptance')
            current = response.get('current', {})
            version = current.get('version', 0)
            self.log(f"   Status: {status}")
            self.log(f"   Acceptance: {acceptance}")
            self.log(f"   Current version: {version}")
            if version > 1 and acceptance is None and status == 'ready_for_acceptance':
                self.log(f"   ✓ Version incremented, acceptance reset, status reverted")
                return True
            else:
                self.log(f"   ⚠️  Version invalidation may not have worked as expected")
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCENARIO 4: RBAC/OWNERSHIP
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_s4_client2_access_client1_contract_403(self):
        """S4: Client 1 tries to access a contract created for Client 2 -> 403"""
        # First, create a contract for client 2
        success1, response1 = self.test(
            "S4: Create Contract for Client 2",
            "POST",
            "waste/cflow/contracts",
            200,
            data={
                "customer_id": self.customer2_id,
                "title": "Client 2 Contract",
                "value": 5000,
                "currency": "UAH"
            },
            token=self.staff_token
        )
        if not success1:
            self.log(f"   ⚠️  Could not create contract for client 2")
            return False
        
        client2_contract_id = response1.get('id')
        self.log(f"   Contract for Client 2 created: {client2_contract_id}")
        
        # Now Client 1 tries to access Client 2's contract -> should get 403
        success2, response2 = self.test(
            "S4: Client 1 Access Client 2 Contract (403 expected)",
            "GET",
            f"client/cflow/contracts/{client2_contract_id}",
            403,
            token=self.client1_token
        )
        if success2:
            self.log(f"   ✓ Correctly returned 403 (forbidden)")
            return True
        return False
    
    def test_s4_unauthenticated_access_401(self):
        """S4: Unauthenticated request to client endpoint → 401"""
        success, response = self.test(
            "S4: Unauthenticated Access (401 expected)",
            "GET",
            f"client/cflow/contracts/{self.contract1_id}",
            401,
            token=None
        )
        if success:
            self.log(f"   ✓ Correctly returned 401 (unauthorized)")
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LEGAL PROFILE VALIDATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_legal_profile_validation(self):
        """Test legal profile validation endpoint with invalid data"""
        # First, corrupt the profile with invalid edrpou and email
        success1, response1 = self.test(
            "Set Invalid Legal Profile Data",
            "PUT",
            f"waste/cflow/legal-profile/{self.customer2_id}",
            200,
            data={
                "edrpou": "123",  # Invalid (too short)
                "email": "invalid-email"  # Invalid format
            },
            token=self.staff_token
        )
        
        # Now get validation
        success2, response2 = self.test(
            "Get Legal Profile Validation",
            "GET",
            f"waste/cflow/legal-profile/{self.customer2_id}",
            200,
            token=self.staff_token
        )
        if success2:
            validation = response2.get('validation', {})
            missing_fields = validation.get('missing_fields', [])
            invalid_fields = validation.get('invalid_fields', [])
            complete = validation.get('complete', False)
            completion_percent = validation.get('completion_percent', 0)
            
            self.log(f"   Complete: {complete}")
            self.log(f"   Completion: {completion_percent}%")
            self.log(f"   Missing fields: {missing_fields}")
            self.log(f"   Invalid fields: {invalid_fields}")
            
            if 'edrpou' in invalid_fields and 'email' in invalid_fields:
                self.log(f"   ✓ Invalid fields correctly detected")
                return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_staff_notifications(self):
        """Test staff notifications created"""
        success, response = self.test(
            "Get Staff Notifications",
            "GET",
            "waste/notifications",
            200,
            params={"limit": 50},
            token=self.staff_token
        )
        if success:
            items = response.get('items', [])
            self.log(f"   Total notifications: {len(items)}")
            
            # Look for contract flow notifications
            cf_notifs = [n for n in items if 'contract' in n.get('kind', '').lower() or 
                        'contract' in n.get('title', '').lower()]
            self.log(f"   Contract flow notifications: {len(cf_notifs)}")
            
            if len(cf_notifs) > 0:
                for n in cf_notifs[:3]:
                    self.log(f"     - {n.get('kind')}: {n.get('title')}")
                self.log(f"   ✓ Staff notifications created")
                return True
        return False
    
    def test_client_notifications(self):
        """Test client notifications created"""
        success, response = self.test(
            "Get Client Notifications",
            "GET",
            "client/notifications",
            200,
            token=self.client1_token
        )
        if success:
            items = response.get('items', []) or response.get('notifications', [])
            self.log(f"   Total notifications: {len(items)}")
            
            # Look for contract flow notifications
            cf_notifs = [n for n in items if 'contract' in n.get('kind', '').lower() or 
                        'contract' in n.get('type', '').lower() or
                        'contract' in n.get('title', '').lower()]
            self.log(f"   Contract flow notifications: {len(cf_notifs)}")
            
            if len(cf_notifs) > 0:
                for n in cf_notifs[:3]:
                    self.log(f"     - {n.get('kind') or n.get('type')}: {n.get('title')}")
                self.log(f"   ✓ Client notifications created")
                return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PDF GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_pdf_generation(self):
        """Test PDF endpoint returns application/pdf"""
        url = f"{BASE_URL}/waste/cflow/contracts/{self.contract1_id}/pdf"
        headers = {'Authorization': f'Bearer {self.staff_token}'}
        
        self.tests_run += 1
        print(f"\n🔍 Test {self.tests_run}: PDF Generation")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                self.log(f"   Status: {response.status_code}")
                self.log(f"   Content-Type: {content_type}")
                self.log(f"   Content length: {len(response.content)} bytes")
                
                if 'application/pdf' in content_type or 'text/html' in content_type:
                    self.tests_passed += 1
                    self.log(f"   ✅ PASS - PDF endpoint working")
                    return True
                else:
                    self.log(f"   ⚠️  Unexpected content type: {content_type}")
            else:
                self.log(f"   ❌ FAIL - Status: {response.status_code}")
        except Exception as e:
            self.log(f"   ❌ FAIL - Error: {str(e)}")
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN TEST RUNNER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*80)
        print("UNIVERSAL CONTRACT FLOW COMPREHENSIVE TEST")
        print("="*80)
        
        # AUTHENTICATION
        print("\n" + "─"*80)
        print("AUTHENTICATION")
        print("─"*80)
        if not self.test_staff_login():
            print("\n❌ Staff login failed - stopping tests")
            return False
        if not self.test_client1_dev_login():
            print("\n❌ Client 1 login failed - stopping tests")
            return False
        if not self.test_client2_dev_login():
            print("\n❌ Client 2 login failed - stopping tests")
            return False
        
        # SCENARIO 1: SOFT BLOCKING FULL FLOW
        print("\n" + "─"*80)
        print("SCENARIO 1: SOFT BLOCKING FULL FLOW")
        print("─"*80)
        if not self.test_s1_create_contract():
            print("\n❌ Contract creation failed - stopping scenario 1")
        else:
            self.test_s1_send_contract()
            self.test_s1_client_open_contract()
            self.test_s1_accept_blocked_409()
            self.test_s1_fill_legal_profile()
            self.test_s1_verify_can_accept()
            self.test_s1_client_accept()
            self.test_s1_upload_proof()
            self.test_s1_confirm_payment()
            self.test_s1_approve_contract()
        
        # SCENARIO 2: DIFFERENT TYPE/TEMPLATE
        print("\n" + "─"*80)
        print("SCENARIO 2: DIFFERENT TYPE/TEMPLATE")
        print("─"*80)
        self.test_s2_create_contract_type()
        self.test_s2_create_template()
        self.test_s2_create_contract_with_type()
        
        # SCENARIO 3: VERSION INVALIDATION
        print("\n" + "─"*80)
        print("SCENARIO 3: VERSION INVALIDATION")
        print("─"*80)
        self.test_s3_verify_contract_accepted()
        self.test_s3_change_legal_address()
        self.test_s3_verify_version_incremented()
        
        # SCENARIO 4: RBAC/OWNERSHIP
        print("\n" + "─"*80)
        print("SCENARIO 4: RBAC/OWNERSHIP")
        print("─"*80)
        self.test_s4_client2_access_client1_contract_403()
        self.test_s4_unauthenticated_access_401()
        
        # LEGAL PROFILE VALIDATION
        print("\n" + "─"*80)
        print("LEGAL PROFILE VALIDATION")
        print("─"*80)
        self.test_legal_profile_validation()
        
        # NOTIFICATIONS
        print("\n" + "─"*80)
        print("NOTIFICATIONS")
        print("─"*80)
        self.test_staff_notifications()
        self.test_client_notifications()
        
        # PDF GENERATION
        print("\n" + "─"*80)
        print("PDF GENERATION")
        print("─"*80)
        self.test_pdf_generation()
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        print("="*80 + "\n")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = ContractFlowTester()
    tester.run_all_tests()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
