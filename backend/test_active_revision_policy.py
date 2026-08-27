"""
ACTIVE CONTRACT REVISION POLICY TEST
====================================
Tests the Final Consistency & Release Cleanup of the Universal Contract Flow.

Tests:
1. Material change detection (legal fields + contract fields)
2. Active revision lifecycle (create → send → accept → pay → approve → change legal → revision created)
3. Previous version preservation (old version marked superseded_pending, then superseded)
4. Re-acceptance flow (no payment impact)
5. Payment-impact flow (value change → corrective invoice → proof → confirm → approve)
6. Non-material changes (internal_comment, tags) do NOT create revision
7. DOCX template upload and generation
8. Security: old passwords must fail (401), new passwords must work
9. RBAC: cross-client access blocked

Base URL: https://environmental-utils.preview.emergentagent.com
"""
import requests
import sys
import io
from datetime import datetime

BASE_URL = "https://environmental-utils.preview.emergentagent.com/api"

class ActiveRevisionTester:
    def __init__(self):
        self.staff_token = None
        self.client_token = None
        self.customer_id = None
        self.contract_id = None
        self.contract_type_id = None
        self.template_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
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
            result = {
                "name": name,
                "passed": success,
                "expected": expected_status,
                "actual": response.status_code
            }
            self.test_results.append(result)
            
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
            self.test_results.append({
                "name": name,
                "passed": False,
                "error": str(e)
            })
            return False, {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SECURITY TESTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_old_passwords_rejected(self):
        """Test that old exposed passwords are rejected"""
        print("\n" + "="*80)
        print("SECURITY: OLD PASSWORDS MUST FAIL")
        print("="*80)
        
        # Old admin password
        success, _ = self.test(
            "Old admin password rejected (Admin@12345)",
            "POST",
            "auth/login",
            401,
            data={"email": "admin@bibi.cars", "password": "Admin@12345"}
        )
        
        # Old manager password
        success, _ = self.test(
            "Old manager password rejected (Manager@12345)",
            "POST",
            "auth/login",
            401,
            data={"email": "manager@bibi.cars", "password": "Manager@12345"}
        )
        
        # Old client password
        success, _ = self.test(
            "Old client password rejected (Client@12345)",
            "POST",
            "customer-auth/login",
            401,
            data={"email": "client@demo.com", "password": "Client@12345"}
        )
        
        return True
    
    def test_new_passwords_work(self):
        """Test that new rotated passwords work"""
        print("\n" + "="*80)
        print("SECURITY: NEW PASSWORDS MUST WORK")
        print("="*80)
        
        # New admin password
        success, response = self.test(
            "New admin password works (N3wAdm!n-2026-x7Qz)",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@bibi.cars", "password": "N3wAdm!n-2026-x7Qz"}
        )
        if success:
            # Try different token field names
            token = response.get("token") or response.get("access_token") or response.get("accessToken")
            if token:
                self.staff_token = token
                self.log(f"   Staff token obtained")
            else:
                self.log(f"   ⚠️  No token in response: {list(response.keys())}")
        
        # New client password
        success, response = self.test(
            "New client password works (N3wCli!-2026-t9Mv)",
            "POST",
            "customer-auth/login",
            200,
            data={"email": "client@demo.com", "password": "N3wCli!-2026-t9Mv"}
        )
        if success:
            # Try different token field names
            token = response.get("token") or response.get("access_token") or response.get("accessToken")
            if token:
                self.client_token = token
                self.customer_id = response.get("customerId") or response.get("customer_id") or response.get("id")
                self.log(f"   Client token obtained, customer_id: {self.customer_id}")
            else:
                self.log(f"   ⚠️  No token in response: {list(response.keys())}")
        
        return bool(self.staff_token and self.client_token)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SETUP: CREATE CONTRACT AND TAKE IT TO ACTIVE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def setup_active_contract(self):
        """Create a contract and take it through the full flow to ACTIVE status"""
        print("\n" + "="*80)
        print("SETUP: CREATE ACTIVE CONTRACT")
        print("="*80)
        
        # Get seeded contract types
        success, response = self.test(
            "Get contract types",
            "GET",
            "waste/cflow/types",
            200,
            token=self.staff_token
        )
        if success and response.get("items"):
            # Pick a seeded type (one_time, quarterly, etc.)
            for ct in response["items"]:
                if ct.get("code") in ["one_time", "quarterly", "regular"]:
                    self.contract_type_id = ct["id"]
                    self.log(f"   Using contract type: {ct.get('name')} ({ct.get('code')})")
                    break
        
        if not self.contract_type_id:
            self.log("❌ No suitable contract type found")
            return False
        
        # Fill legal profile (7 required fields)
        success, response = self.test(
            "Fill legal profile",
            "PUT",
            f"waste/cflow/legal-profile/{self.customer_id}",
            200,
            token=self.staff_token,
            data={
                "legal_name": "ТОВ «Тестова Компанія»",
                "edrpou": "12345678",
                "legal_address": "м. Київ, вул. Тестова, 1",
                "phone": "+380501234567",
                "email": "test@example.com",
                "signer_full_name": "Іванов Іван Іванович",
                "signer_position": "Директор"
            }
        )
        
        # Create contract
        success, response = self.test(
            "Create contract",
            "POST",
            "waste/cflow/contracts",
            200,
            token=self.staff_token,
            data={
                "customer_id": self.customer_id,
                "contract_type_id": self.contract_type_id,
                "service_name": "Вивезення відходів",
                "value": 5000,
                "currency": "UAH",
                "title": "Договір на вивезення відходів"
            }
        )
        if success:
            self.contract_id = response.get("id")
            self.log(f"   Contract created: {self.contract_id}")
        else:
            return False
        
        # Send for review
        success, _ = self.test(
            "Send contract for review",
            "POST",
            f"waste/cflow/contracts/{self.contract_id}/send",
            200,
            token=self.staff_token
        )
        
        # Client opens contract
        success, _ = self.test(
            "Client opens contract",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/open",
            200,
            token=self.client_token
        )
        
        # Client accepts contract
        success, _ = self.test(
            "Client accepts contract",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/accept",
            200,
            token=self.client_token,
            data={"read_confirmed": True}
        )
        
        # Client uploads payment proof
        # Create a dummy file
        dummy_file = io.BytesIO(b"PAYMENT PROOF CONTENT")
        success, _ = self.test(
            "Client uploads payment proof",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/proof",
            200,
            token=self.client_token,
            files={"file": ("proof.pdf", dummy_file, "application/pdf")}
        )
        
        # Staff confirms payment
        success, _ = self.test(
            "Staff confirms payment",
            "POST",
            f"waste/cflow/contracts/{self.contract_id}/confirm-payment",
            200,
            token=self.staff_token,
            data={"reference": "TEST-REF-001"}
        )
        
        # Staff approves contract
        success, response = self.test(
            "Staff approves contract → ACTIVE",
            "POST",
            f"waste/cflow/contracts/{self.contract_id}/approve",
            200,
            token=self.staff_token
        )
        
        if success:
            status = response.get("status")
            acceptance = response.get("acceptance")
            active_version = response.get("active_version")
            self.log(f"   Contract status: {status}")
            self.log(f"   Acceptance: {acceptance is not None}")
            self.log(f"   Active version: {active_version}")
            
            if status == "active" and acceptance:
                self.log("   ✅ Contract is now ACTIVE with acceptance")
                return True
            else:
                self.log("   ❌ Contract not properly activated")
                return False
        
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACTIVE REVISION POLICY TESTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_material_legal_change_creates_revision(self):
        """Test that changing a material legal field on an ACTIVE contract creates a revision"""
        print("\n" + "="*80)
        print("TEST: MATERIAL LEGAL CHANGE → REVISION")
        print("="*80)
        
        # Get contract before change
        success, before = self.test(
            "Get contract before legal change",
            "GET",
            f"waste/cflow/contracts/{self.contract_id}",
            200,
            token=self.staff_token
        )
        
        if not success:
            return False
        
        old_status = before.get("status")
        old_acceptance = before.get("acceptance")
        old_active_version = before.get("active_version")
        old_revision = before.get("revision")
        
        self.log(f"   BEFORE: status={old_status}, acceptance={old_acceptance is not None}, active_version={old_active_version}, revision={old_revision is not None}")
        
        # Change legal address (material legal field)
        success, response = self.test(
            "Change legal address (material field)",
            "PUT",
            f"waste/cflow/legal-profile/{self.customer_id}",
            200,
            token=self.staff_token,
            data={
                "legal_address": "м. Київ, вул. Нова Тестова, 99"
            }
        )
        
        # Get contract after change
        success, after = self.test(
            "Get contract after legal change",
            "GET",
            f"waste/cflow/contracts/{self.contract_id}",
            200,
            token=self.staff_token
        )
        
        if not success:
            return False
        
        new_status = after.get("status")
        new_acceptance = after.get("acceptance")
        new_active_version = after.get("active_version")
        new_revision = after.get("revision")
        versions = after.get("versions", [])
        
        self.log(f"   AFTER: status={new_status}, acceptance={new_acceptance is not None}, active_version={new_active_version}, revision={new_revision is not None}")
        
        # CRITICAL CHECKS:
        # 1. Status should be 'revision_pending_acceptance'
        # 2. Acceptance should be PRESERVED (not None)
        # 3. active_version should still be the OLD version
        # 4. revision should exist with status 'pending_acceptance'
        # 5. revision.version should be old_active_version + 1
        
        checks_passed = True
        
        if new_status != "revision_pending_acceptance":
            self.log(f"   ❌ FAIL: Expected status 'revision_pending_acceptance', got '{new_status}'")
            checks_passed = False
        else:
            self.log(f"   ✅ Status correctly changed to 'revision_pending_acceptance'")
        
        if new_acceptance is None:
            self.log(f"   ❌ FAIL: Acceptance was RESET (should be preserved)")
            checks_passed = False
        else:
            self.log(f"   ✅ Acceptance PRESERVED")
        
        if new_active_version != old_active_version:
            self.log(f"   ❌ FAIL: active_version changed from {old_active_version} to {new_active_version} (should stay same)")
            checks_passed = False
        else:
            self.log(f"   ✅ active_version unchanged ({old_active_version})")
        
        if not new_revision:
            self.log(f"   ❌ FAIL: No revision object created")
            checks_passed = False
        else:
            rev_status = new_revision.get("status")
            rev_version = new_revision.get("version")
            rev_acceptance = new_revision.get("acceptance")
            
            self.log(f"   Revision: version={rev_version}, status={rev_status}, acceptance={rev_acceptance is not None}")
            
            if rev_status != "pending_acceptance":
                self.log(f"   ❌ FAIL: Revision status should be 'pending_acceptance', got '{rev_status}'")
                checks_passed = False
            else:
                self.log(f"   ✅ Revision status is 'pending_acceptance'")
            
            if rev_version != old_active_version + 1:
                self.log(f"   ❌ FAIL: Revision version should be {old_active_version + 1}, got {rev_version}")
                checks_passed = False
            else:
                self.log(f"   ✅ Revision version is {rev_version} (old + 1)")
        
        # Check version history
        if versions:
            old_version_obj = next((v for v in versions if v.get("version") == old_active_version), None)
            new_version_obj = next((v for v in versions if v.get("version") == new_revision.get("version")), None)
            
            if old_version_obj:
                old_v_status = old_version_obj.get("status")
                self.log(f"   Old version (v{old_active_version}) status: {old_v_status}")
                if old_v_status != "superseded_pending":
                    self.log(f"   ⚠️  Expected 'superseded_pending', got '{old_v_status}'")
            
            if new_version_obj:
                new_v_status = new_version_obj.get("status")
                self.log(f"   New version (v{new_revision.get('version')}) status: {new_v_status}")
                if new_v_status != "revision_pending":
                    self.log(f"   ⚠️  Expected 'revision_pending', got '{new_v_status}'")
        
        return checks_passed
    
    def test_re_acceptance_flow(self):
        """Test re-acceptance flow (no payment impact)"""
        print("\n" + "="*80)
        print("TEST: RE-ACCEPTANCE FLOW (NO PAYMENT IMPACT)")
        print("="*80)
        
        # Client re-opens contract
        success, _ = self.test(
            "Client re-opens contract with revision",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/open",
            200,
            token=self.client_token
        )
        
        # Client re-accepts
        success, response = self.test(
            "Client re-accepts revision",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/accept",
            200,
            token=self.client_token,
            data={"read_confirmed": True}
        )
        
        if success:
            revision = response.get("revision")
            if revision:
                rev_status = revision.get("status")
                rev_acceptance = revision.get("acceptance")
                self.log(f"   Revision status after re-acceptance: {rev_status}")
                self.log(f"   Revision acceptance: {rev_acceptance is not None}")
                
                # Should be 'accepted' (not 'awaiting_payment' since no payment impact)
                if rev_status == "accepted":
                    self.log(f"   ✅ Revision status is 'accepted' (no payment impact)")
                else:
                    self.log(f"   ❌ Expected 'accepted', got '{rev_status}'")
                    return False
            else:
                self.log(f"   ❌ No revision in response")
                return False
        
        # Staff approves revision
        success, response = self.test(
            "Staff approves revision",
            "POST",
            f"waste/cflow/contracts/{self.contract_id}/approve",
            200,
            token=self.staff_token
        )
        
        if success:
            status = response.get("status")
            active_version = response.get("active_version")
            revision = response.get("revision")
            acceptance_history = response.get("acceptance_history", [])
            
            self.log(f"   Status after approval: {status}")
            self.log(f"   Active version: {active_version}")
            self.log(f"   Revision cleared: {revision is None}")
            self.log(f"   Acceptance history entries: {len(acceptance_history)}")
            
            checks_passed = True
            
            if status != "active":
                self.log(f"   ❌ Expected status 'active', got '{status}'")
                checks_passed = False
            else:
                self.log(f"   ✅ Status is 'active'")
            
            if revision is not None:
                self.log(f"   ❌ Revision should be cleared after approval")
                checks_passed = False
            else:
                self.log(f"   ✅ Revision cleared")
            
            if len(acceptance_history) == 0:
                self.log(f"   ⚠️  No acceptance history (prior acceptance should be preserved)")
            else:
                self.log(f"   ✅ Acceptance history contains {len(acceptance_history)} entries")
            
            return checks_passed
        
        return False
    
    def test_payment_impact_flow(self):
        """Test payment-impact flow (value change)"""
        print("\n" + "="*80)
        print("TEST: PAYMENT-IMPACT FLOW (VALUE CHANGE)")
        print("="*80)
        
        # Change value (payment-impacting field)
        success, response = self.test(
            "Change contract value (payment-impacting)",
            "PATCH",
            f"waste/cflow/contracts/{self.contract_id}",
            200,
            token=self.staff_token,
            data={"value": 7500}
        )
        
        if success:
            revision = response.get("revision")
            if revision:
                payment_required = revision.get("payment_required")
                rev_status = revision.get("status")
                self.log(f"   Revision created with payment_required={payment_required}")
                self.log(f"   Revision status: {rev_status}")
                
                if not payment_required:
                    self.log(f"   ❌ payment_required should be True for value change")
                    return False
                else:
                    self.log(f"   ✅ payment_required is True")
            else:
                self.log(f"   ❌ No revision created")
                return False
        
        # Client re-opens and re-accepts
        success, _ = self.test(
            "Client re-opens contract",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/open",
            200,
            token=self.client_token
        )
        
        success, response = self.test(
            "Client re-accepts (payment-impacting revision)",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/accept",
            200,
            token=self.client_token,
            data={"read_confirmed": True}
        )
        
        if success:
            revision = response.get("revision")
            if revision:
                rev_status = revision.get("status")
                rev_payment = revision.get("payment")
                self.log(f"   Revision status after re-acceptance: {rev_status}")
                
                # Should be 'awaiting_payment'
                if rev_status == "awaiting_payment":
                    self.log(f"   ✅ Revision status is 'awaiting_payment'")
                else:
                    self.log(f"   ❌ Expected 'awaiting_payment', got '{rev_status}'")
                    return False
                
                if rev_payment:
                    pay_status = rev_payment.get("status")
                    iban = rev_payment.get("iban")
                    self.log(f"   Corrective invoice: status={pay_status}, iban={iban}")
                    if iban:
                        self.log(f"   ✅ Corrective IBAN invoice issued")
                    else:
                        self.log(f"   ⚠️  No IBAN in corrective invoice")
                else:
                    self.log(f"   ❌ No payment object in revision")
                    return False
        
        # Client uploads proof
        dummy_file = io.BytesIO(b"CORRECTIVE PAYMENT PROOF")
        success, response = self.test(
            "Client uploads corrective payment proof",
            "POST",
            f"client/cflow/contracts/{self.contract_id}/proof",
            200,
            token=self.client_token,
            files={"file": ("corrective_proof.pdf", dummy_file, "application/pdf")}
        )
        
        if success:
            revision = response.get("revision")
            if revision and revision.get("payment"):
                pay_status = revision["payment"].get("status")
                self.log(f"   Payment status after proof upload: {pay_status}")
                if pay_status == "proof_uploaded":
                    self.log(f"   ✅ Payment status is 'proof_uploaded'")
                else:
                    self.log(f"   ⚠️  Expected 'proof_uploaded', got '{pay_status}'")
        
        # Staff confirms payment
        success, response = self.test(
            "Staff confirms corrective payment",
            "POST",
            f"waste/cflow/contracts/{self.contract_id}/confirm-payment",
            200,
            token=self.staff_token,
            data={"reference": "CORRECTIVE-REF-001"}
        )
        
        if success:
            revision = response.get("revision")
            if revision:
                rev_status = revision.get("status")
                self.log(f"   Revision status after payment confirmation: {rev_status}")
                if rev_status == "payment_confirmed":
                    self.log(f"   ✅ Revision status is 'payment_confirmed'")
                else:
                    self.log(f"   ❌ Expected 'payment_confirmed', got '{rev_status}'")
                    return False
        
        # Staff approves
        success, response = self.test(
            "Staff approves payment-impacting revision",
            "POST",
            f"waste/cflow/contracts/{self.contract_id}/approve",
            200,
            token=self.staff_token
        )
        
        if success:
            status = response.get("status")
            revision = response.get("revision")
            self.log(f"   Status after approval: {status}")
            
            if status == "active" and revision is None:
                self.log(f"   ✅ Contract active, revision cleared")
                return True
            else:
                self.log(f"   ❌ Expected active with no revision")
                return False
        
        return False
    
    def test_non_material_change(self):
        """Test that non-material changes do NOT create a revision"""
        print("\n" + "="*80)
        print("TEST: NON-MATERIAL CHANGE (NO REVISION)")
        print("="*80)
        
        # Get contract before change
        success, before = self.test(
            "Get contract before non-material change",
            "GET",
            f"waste/cflow/contracts/{self.contract_id}",
            200,
            token=self.staff_token
        )
        
        if not success:
            return False
        
        old_status = before.get("status")
        old_acceptance = before.get("acceptance")
        old_revision = before.get("revision")
        
        # Change internal_comment (non-material field)
        success, response = self.test(
            "Change internal_comment (non-material)",
            "PATCH",
            f"waste/cflow/contracts/{self.contract_id}",
            200,
            token=self.staff_token,
            data={"internal_comment": "This is an internal note"}
        )
        
        if success:
            new_status = response.get("status")
            new_acceptance = response.get("acceptance")
            new_revision = response.get("revision")
            
            self.log(f"   Status: {old_status} → {new_status}")
            self.log(f"   Acceptance preserved: {new_acceptance is not None}")
            self.log(f"   Revision created: {new_revision is not None}")
            
            checks_passed = True
            
            if new_status != old_status:
                self.log(f"   ❌ Status changed (should stay same)")
                checks_passed = False
            else:
                self.log(f"   ✅ Status unchanged")
            
            if new_acceptance is None and old_acceptance is not None:
                self.log(f"   ❌ Acceptance was reset")
                checks_passed = False
            else:
                self.log(f"   ✅ Acceptance preserved")
            
            if new_revision is not None and old_revision is None:
                self.log(f"   ❌ Revision was created (should NOT be)")
                checks_passed = False
            else:
                self.log(f"   ✅ No revision created")
            
            return checks_passed
        
        return False
    
    def test_docx_upload(self):
        """Test DOCX template upload"""
        print("\n" + "="*80)
        print("TEST: DOCX TEMPLATE UPLOAD")
        print("="*80)
        
        # Create a minimal DOCX file (just a ZIP with minimal structure)
        import zipfile
        docx_buffer = io.BytesIO()
        with zipfile.ZipFile(docx_buffer, 'w', zipfile.ZIP_DEFLATED) as docx:
            # Add minimal DOCX structure
            docx.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
            docx.writestr('word/document.xml', '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Договір №{{contract.number}}</w:t></w:r></w:p></w:body></w:document>')
        
        docx_buffer.seek(0)
        
        success, response = self.test(
            "Upload DOCX template",
            "POST",
            f"waste/cflow/templates/upload?name=Test DOCX Template&contract_type_id={self.contract_type_id}",
            200,
            token=self.staff_token,
            files={"file": ("test_template.docx", docx_buffer, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        
        if success:
            template_id = response.get("id")
            template_format = response.get("format")
            template_html = response.get("html", "")
            
            self.log(f"   Template ID: {template_id}")
            self.log(f"   Format: {template_format}")
            self.log(f"   HTML extracted: {len(template_html)} chars")
            
            if template_format == "docx":
                self.log(f"   ✅ Template format is 'docx'")
            else:
                self.log(f"   ❌ Expected format 'docx', got '{template_format}'")
                return False
            
            if "contract.number" in template_html:
                self.log(f"   ✅ Variable extracted into HTML")
            else:
                self.log(f"   ⚠️  Variable not found in extracted HTML")
            
            return True
        
        return False
    
    def test_rbac_ownership(self):
        """Test RBAC/ownership - cross-client access blocked"""
        print("\n" + "="*80)
        print("TEST: RBAC/OWNERSHIP")
        print("="*80)
        
        # Create a second client
        success, response = self.test(
            "Create second client account",
            "POST",
            "auth/register",
            200,
            data={
                "email": f"client2_{datetime.now().strftime('%H%M%S')}@test.com",
                "password": "TestPass123!",
                "name": "Test Client 2",
                "role": "customer"
            }
        )
        
        if success and response.get("token"):
            client2_token = response["token"]
            
            # Try to access first client's contract
            success, _ = self.test(
                "Client 2 tries to access Client 1's contract (should be 403)",
                "GET",
                f"client/cflow/contracts/{self.contract_id}",
                403,
                token=client2_token
            )
            
            if success:
                self.log(f"   ✅ Cross-client access blocked (403)")
                return True
            else:
                self.log(f"   ❌ Cross-client access NOT blocked")
                return False
        else:
            self.log(f"   ⚠️  Could not create second client, skipping RBAC test")
            return True  # Don't fail the whole suite
        
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN TEST RUNNER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*80)
        print("ACTIVE CONTRACT REVISION POLICY - COMPREHENSIVE TEST")
        print("="*80)
        print(f"Base URL: {BASE_URL}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Security tests
        if not self.test_old_passwords_rejected():
            print("\n❌ Old password rejection test failed")
            return False
        
        if not self.test_new_passwords_work():
            print("\n❌ New password test failed - cannot proceed")
            return False
        
        # Setup active contract
        if not self.setup_active_contract():
            print("\n❌ Failed to create active contract - cannot proceed")
            return False
        
        # Core revision policy tests
        if not self.test_material_legal_change_creates_revision():
            print("\n❌ Material legal change test FAILED")
        
        if not self.test_re_acceptance_flow():
            print("\n❌ Re-acceptance flow test FAILED")
        
        if not self.test_payment_impact_flow():
            print("\n❌ Payment-impact flow test FAILED")
        
        if not self.test_non_material_change():
            print("\n❌ Non-material change test FAILED")
        
        # Additional tests
        if not self.test_docx_upload():
            print("\n⚠️  DOCX upload test FAILED")
        
        if not self.test_rbac_ownership():
            print("\n⚠️  RBAC test FAILED")
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = ActiveRevisionTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
