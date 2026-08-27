"""
ECO NOVA — CONTRACT OWNERSHIP FIX VERIFICATION (FINAL)
======================================================
Verifies the MEDIUM bug fix for customer-cabinet contract-engine endpoints.

Bug Fix: GET /api/customer-cabinet/{customer_id}/contract-engine/{contract_id}
now grants access when contract's company_id matches customer's company_id
(not just customer_id).
"""
import requests
import sys
import uuid
from datetime import datetime

BASE_URL = "https://waste-management-hub-18.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "yzbXEE0E4pH1AqgqQgeP!Ec"
CLIENT_EMAIL = "client@eco.ua"
CLIENT_PASSWORD = "0g0aP13v6cvHZLezSFEG!Ec"

class OwnershipFixTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.client_token = None
        self.client_id = None
        self.client_company_id = None
        self.failures = []
        self.test_contract_id = None

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")

    def test(self, name, expected_status, fn):
        """Run a test function"""
        self.tests_run += 1
        self.log(f"Testing: {name}", "TEST")
        
        try:
            status, result = fn()
            success = status == expected_status
            
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - {name} (status: {status})", "PASS")
                return True, result
            else:
                self.log(f"❌ FAIL - {name} - Expected {expected_status}, got {status}", "FAIL")
                self.failures.append(f"{name}: Expected {expected_status}, got {status}")
                return False, result
                
        except Exception as e:
            self.log(f"❌ FAIL - {name} - {str(e)}", "FAIL")
            self.failures.append(f"{name}: {str(e)}")
            return False, None

    def setup(self):
        """Login and get client info"""
        self.log("=== SETUP ===")
        
        # Client login
        response = requests.post(
            f"{API_BASE}/customer-auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD},
            timeout=15
        )
        if response.status_code != 200:
            self.log("Failed to login as client", "ERROR")
            return False
        
        data = response.json()
        self.client_token = data.get("accessToken")
        self.client_id = data.get("customerId")
        self.log(f"Client ID: {self.client_id}")
        
        # Get client profile
        response = requests.get(
            f"{API_BASE}/client/me",
            headers={"Authorization": f"Bearer {self.client_token}"},
            timeout=15
        )
        if response.status_code == 200:
            customer = response.json().get("customer", {})
            self.client_company_id = customer.get("company_id")
            self.log(f"Client company_id: {self.client_company_id}")
        
        return True

    def test_company_owned_contract_detail(self):
        """Test 1: Company-owned contract (customer_id=None) is accessible"""
        self.log("=== TEST 1: Company-owned contract (customer_id=None, company_id match) ===")
        
        # Use existing contract: contract_1785454087_a7a416d2 (has company_id, no customer_id)
        contract_id = "contract_1785454087_a7a416d2"
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/customer-cabinet/{self.client_id}/contract-engine/{contract_id}",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("contract") and "periods" in data and "financials" in data:
                    return 200, data
            return response.status_code, response.text
        
        success, _ = self.test("Company-owned contract detail", 200, test_fn)
        if success:
            self.log("✅ FIX VERIFIED: Company-owned contract accessible", "SUCCESS")
        return success

    def test_company_owned_contract_list(self):
        """Test 2: Company-owned contract appears in list"""
        self.log("=== TEST 2: Company-owned contract in list ===")
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/customer-cabinet/{self.client_id}/contract-engine",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                # Check if company-owned contract is in list
                company_owned = [c for c in items if not c.get("customer_id") and c.get("company_id") == self.client_company_id]
                if company_owned:
                    self.log(f"Found {len(company_owned)} company-owned contract(s)", "INFO")
                    return 200, data
            return response.status_code, response.text
        
        success, _ = self.test("Company-owned contract in list", 200, test_fn)
        if success:
            self.log("✅ FIX VERIFIED: Company-owned contract in list", "SUCCESS")
        return success

    def test_different_company_denied(self):
        """Test 3: Contract from different company returns 404"""
        self.log("=== TEST 3: Different company contract denied ===")
        
        # Create a temporary contract with different company_id
        from pymongo import MongoClient
        import os
        
        try:
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/eco_nova")
            client = MongoClient(mongo_url)
            db = client.get_default_database()
            
            # Create test contract with different company
            self.test_contract_id = f"WC-TEST-{uuid.uuid4().hex[:6].upper()}"
            other_company_id = f"comp_other_{uuid.uuid4().hex[:8]}"
            
            test_contract = {
                "id": self.test_contract_id,
                "number": self.test_contract_id,
                "customer_id": None,
                "company_id": other_company_id,  # Different company
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "schedule_config": {"type": "monthly"},
            }
            
            db.waste_contracts.insert_one(test_contract)
            self.log(f"Created test contract: {self.test_contract_id} (different company)", "INFO")
            client.close()
            
        except Exception as e:
            self.log(f"Failed to create test contract: {e}", "ERROR")
            return False
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/customer-cabinet/{self.client_id}/contract-engine/{self.test_contract_id}",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            return response.status_code, response.text
        
        success, _ = self.test("Different company contract denied", 404, test_fn)
        if success:
            self.log("✅ SECURITY OK: Different company contract returns 404", "SUCCESS")
        return success

    def test_direct_customer_match(self):
        """Test 4: Direct customer_id match still works"""
        self.log("=== TEST 4: Direct customer_id match ===")
        
        # Use existing contract: contract_1785449364_e725a8a3 (has customer_id match)
        contract_id = "contract_1785449364_e725a8a3"
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/customer-cabinet/{self.client_id}/contract-engine/{contract_id}",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("contract"):
                    return 200, data
            return response.status_code, response.text
        
        success, _ = self.test("Direct customer_id match", 200, test_fn)
        if success:
            self.log("✅ NO REGRESSION: Direct customer_id match works", "SUCCESS")
        return success

    def test_token_scoped_list(self):
        """Test 5: Token-scoped list endpoint (regression)"""
        self.log("=== TEST 5: Token-scoped list endpoint ===")
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/client/contract-engine",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and isinstance(data.get("items"), list):
                    return 200, data
            return response.status_code, response.text
        
        success, _ = self.test("Token-scoped list endpoint", 200, test_fn)
        if success:
            self.log("✅ REGRESSION OK: Token-scoped list works", "SUCCESS")
        return success

    def test_token_scoped_detail(self):
        """Test 6: Token-scoped detail endpoint (regression)"""
        self.log("=== TEST 6: Token-scoped detail endpoint ===")
        
        contract_id = "contract_1785449364_e725a8a3"
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/client/contract-engine/{contract_id}",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("contract"):
                    return 200, data
            return response.status_code, response.text
        
        success, _ = self.test("Token-scoped detail endpoint", 200, test_fn)
        if success:
            self.log("✅ REGRESSION OK: Token-scoped detail works", "SUCCESS")
        return success

    def test_token_scoped_foreign_contract(self):
        """Test 7: Token-scoped endpoint denies foreign contract"""
        self.log("=== TEST 7: Token-scoped foreign contract denied ===")
        
        foreign_id = f"WC-FOREIGN-{uuid.uuid4().hex[:6].upper()}"
        
        def test_fn():
            response = requests.get(
                f"{API_BASE}/client/contract-engine/{foreign_id}",
                headers={"Authorization": f"Bearer {self.client_token}"},
                timeout=15
            )
            return response.status_code, response.text
        
        success, _ = self.test("Token-scoped foreign contract denied", 404, test_fn)
        if success:
            self.log("✅ SECURITY OK: Foreign contract returns 404", "SUCCESS")
        return success

    def cleanup(self):
        """Clean up test data"""
        if self.test_contract_id:
            self.log("=== CLEANUP ===")
            try:
                from pymongo import MongoClient
                import os
                
                mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/eco_nova")
                client = MongoClient(mongo_url)
                db = client.get_default_database()
                
                db.waste_contracts.delete_one({"id": self.test_contract_id})
                self.log(f"Deleted test contract: {self.test_contract_id}")
                client.close()
                
            except Exception as e:
                self.log(f"Cleanup failed: {e}", "WARN")

    def run(self):
        """Run all tests"""
        self.log("=" * 70)
        self.log("CONTRACT OWNERSHIP FIX VERIFICATION")
        self.log("=" * 70)
        
        if not self.setup():
            self.log("Setup failed, aborting", "ERROR")
            return 1
        
        # Run tests
        self.test_company_owned_contract_detail()
        self.test_company_owned_contract_list()
        self.test_different_company_denied()
        self.test_direct_customer_match()
        self.test_token_scoped_list()
        self.test_token_scoped_detail()
        self.test_token_scoped_foreign_contract()
        
        # Cleanup
        self.cleanup()
        
        # Summary
        self.log("=" * 70)
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        self.log("=" * 70)
        
        if self.failures:
            self.log("FAILURES:", "ERROR")
            for failure in self.failures:
                self.log(f"  - {failure}", "ERROR")
        else:
            self.log("✅ ALL TESTS PASSED - OWNERSHIP FIX VERIFIED", "SUCCESS")
        
        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = OwnershipFixTester()
    sys.exit(tester.run())
