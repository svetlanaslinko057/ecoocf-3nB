"""
ECO NOVA — CONTRACT OWNERSHIP FIX VERIFICATION
==============================================
Goal: Verify the MEDIUM bug fix for customer-cabinet contract-engine endpoints.

Bug Fix: Previously GET /api/customer-cabinet/{customer_id}/contract-engine/{contract_id}
enforced ownership ONLY by customer_id. Now it also grants access when the contract's
company_id equals the requesting customer's company_id.

Test Coverage:
1. OWNERSHIP FIX (positive): contract with customer_id=None but company_id matching customer's company
2. OWNERSHIP FIX (list): company-owned contract appears in list endpoint
3. OWNERSHIP SECURE (negative): contract from different company returns 404
4. Direct customer_id match still works
5. Regression: token-scoped /api/client/contract-engine endpoints still work
"""
import requests
import sys
import uuid
from datetime import datetime, timezone

# Production URL from frontend/.env
BASE_URL = "https://waste-management-hub-18.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Seeded credentials (from backend/.env)
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "yzbXEE0E4pH1AqgqQgeP!Ec"
CLIENT_EMAIL = "client@eco.ua"
CLIENT_PASSWORD = "0g0aP13v6cvHZLezSFEG!Ec"

class ContractOwnershipTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.client_token = None
        self.client_id = None
        self.client_company_id = None
        self.failures = []
        self.test_contracts = []  # Track for cleanup
        self.test_companies = []  # Track for cleanup

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, check_fn=None):
        """Run a single API test"""
        url = f"{API_BASE}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        self.log(f"Testing: {name}", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)
            else:
                self.log(f"Unsupported method {method}", "ERROR")
                self.failures.append(f"{name}: Unsupported method")
                return False, None

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - {name} (status: {response.status_code})", "PASS")
                
                if check_fn and response.status_code in [200, 201]:
                    try:
                        json_data = response.json()
                        if not check_fn(json_data):
                            self.log(f"⚠️  Data validation failed for {name}", "WARN")
                            self.failures.append(f"{name}: Data validation failed")
                            return False, json_data
                        return True, json_data
                    except Exception as e:
                        self.log(f"⚠️  Data check error: {e}", "WARN")
                        self.failures.append(f"{name}: Data check error - {e}")
                        return False, None
                
                try:
                    return True, response.json() if response.status_code in [200, 201] else None
                except Exception:
                    return True, None
            else:
                self.log(f"❌ FAIL - {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                try:
                    self.log(f"Response: {response.text[:500]}", "DEBUG")
                except Exception:
                    pass
                return False, None

        except requests.exceptions.Timeout:
            self.log(f"❌ FAIL - {name} - Request timeout", "FAIL")
            self.failures.append(f"{name}: Request timeout")
            return False, None
        except Exception as e:
            self.log(f"❌ FAIL - {name} - {str(e)}", "FAIL")
            self.failures.append(f"{name}: {str(e)}")
            return False, None

    def setup_auth(self):
        """Login as admin and client"""
        self.log("=== SETUP: Authentication ===")
        
        # Admin login
        success, data = self.test(
            "Admin login",
            "POST",
            "/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if not success or not data:
            self.log("Failed to login as admin", "ERROR")
            return False
        self.admin_token = data.get("access_token")
        
        # Client login (customer-auth)
        success, data = self.test(
            "Client login",
            "POST",
            "/customer-auth/login",
            200,
            data={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        if not success or not data:
            self.log("Failed to login as client", "ERROR")
            return False
        self.client_token = data.get("accessToken")
        self.client_id = data.get("customerId")
        
        self.log(f"Client ID: {self.client_id}")
        
        # Get client's company_id from customers collection
        # We'll use admin token to query the database via a helper endpoint or direct DB access
        # For now, let's fetch it via the /api/client/me endpoint
        success, data = self.test(
            "Get client profile",
            "GET",
            "/client/me",
            200,
            token=self.client_token
        )
        if success and data:
            customer = data.get("customer", {})
            self.client_company_id = customer.get("company_id")
            self.log(f"Client company_id: {self.client_company_id}")
        
        return True

    def create_test_data(self):
        """Create test contracts with different ownership patterns"""
        self.log("=== SETUP: Creating test data ===")
        
        # If client doesn't have a company_id, create one
        if not self.client_company_id:
            self.log("Client has no company_id, creating test company", "WARN")
            company_id = f"comp_test_{uuid.uuid4().hex[:8]}"
            # We need to update the customer record - this requires direct DB access
            # For now, we'll skip this and assume the client has a company_id
            self.log("Skipping company creation - client must have company_id", "ERROR")
            return False
        
        # 1. Create contract with customer_id=None but company_id=client's company
        contract_1_id = f"WC-TEST-{uuid.uuid4().hex[:6].upper()}"
        contract_1 = {
            "id": contract_1_id,
            "number": contract_1_id,
            "customer_id": None,  # KEY: No customer_id
            "company_id": self.client_company_id,  # KEY: Client's company
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schedule_config": {"type": "monthly"},  # Mark as engine-enabled
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
        }
        
        # 2. Create contract with different company_id (negative test)
        contract_2_id = f"WC-TEST-{uuid.uuid4().hex[:6].upper()}"
        other_company_id = f"comp_other_{uuid.uuid4().hex[:8]}"
        contract_2 = {
            "id": contract_2_id,
            "number": contract_2_id,
            "customer_id": None,
            "company_id": other_company_id,  # Different company
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schedule_config": {"type": "monthly"},
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
        }
        
        # 3. Create contract with direct customer_id match
        contract_3_id = f"WC-TEST-{uuid.uuid4().hex[:6].upper()}"
        contract_3 = {
            "id": contract_3_id,
            "number": contract_3_id,
            "customer_id": self.client_id,  # Direct customer match
            "company_id": self.client_company_id,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schedule_config": {"type": "monthly"},
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
        }
        
        # Insert contracts via direct DB access (we need a helper endpoint or use pymongo)
        # For testing, we'll use a workaround: create via existing API if available
        # Since there's no public contract creation endpoint, we'll use direct DB insertion
        
        self.log("Creating test contracts via direct DB insertion...")
        
        # We need to insert directly into MongoDB
        # Let's use a Python script approach with pymongo
        try:
            from pymongo import MongoClient
            import os
            
            # Get MongoDB URL from environment
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/eco_nova")
            client = MongoClient(mongo_url)
            db = client.get_default_database()
            
            # Insert contracts
            db.waste_contracts.insert_one(contract_1)
            self.test_contracts.append(contract_1_id)
            self.log(f"Created contract 1: {contract_1_id} (company-owned, no customer_id)")
            
            db.waste_contracts.insert_one(contract_2)
            self.test_contracts.append(contract_2_id)
            self.log(f"Created contract 2: {contract_2_id} (different company)")
            
            db.waste_contracts.insert_one(contract_3)
            self.test_contracts.append(contract_3_id)
            self.log(f"Created contract 3: {contract_3_id} (direct customer_id match)")
            
            client.close()
            
            # Store contract IDs for testing
            self.contract_company_owned = contract_1_id
            self.contract_other_company = contract_2_id
            self.contract_direct_customer = contract_3_id
            
            return True
            
        except Exception as e:
            self.log(f"Failed to create test data: {e}", "ERROR")
            return False

    def test_ownership_fix_positive(self):
        """Test that company-owned contract (customer_id=None) is accessible"""
        self.log("=== TEST 1: Ownership Fix (Positive) ===")
        
        success, data = self.test(
            "Get company-owned contract (customer_id=None, company_id match)",
            "GET",
            f"/customer-cabinet/{self.client_id}/contract-engine/{self.contract_company_owned}",
            200,
            token=self.client_token,
            check_fn=lambda d: d.get("success") and d.get("contract") and d.get("periods") is not None and d.get("financials") is not None
        )
        
        if success and data:
            self.log("✅ Company-owned contract is accessible (FIX VERIFIED)", "SUCCESS")
            return True
        else:
            self.log("❌ Company-owned contract returned non-200 (FIX FAILED)", "ERROR")
            return False

    def test_ownership_fix_list(self):
        """Test that company-owned contract appears in list endpoint"""
        self.log("=== TEST 2: Ownership Fix (List) ===")
        
        success, data = self.test(
            "List contracts (should include company-owned)",
            "GET",
            f"/customer-cabinet/{self.client_id}/contract-engine",
            200,
            token=self.client_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            contract_ids = [c.get("id") for c in items]
            
            if self.contract_company_owned in contract_ids:
                self.log(f"✅ Company-owned contract found in list (FIX VERIFIED)", "SUCCESS")
                return True
            else:
                self.log(f"❌ Company-owned contract NOT in list (FIX FAILED)", "ERROR")
                self.log(f"Found contracts: {contract_ids}", "DEBUG")
                return False
        
        return False

    def test_ownership_secure_negative(self):
        """Test that contract from different company returns 404"""
        self.log("=== TEST 3: Ownership Security (Negative) ===")
        
        success, data = self.test(
            "Get contract from different company (should be 404)",
            "GET",
            f"/customer-cabinet/{self.client_id}/contract-engine/{self.contract_other_company}",
            404,
            token=self.client_token
        )
        
        if success:
            self.log("✅ Different company contract correctly returns 404 (SECURITY OK)", "SUCCESS")
            return True
        else:
            self.log("❌ Different company contract did NOT return 404 (SECURITY ISSUE)", "ERROR")
            return False

    def test_direct_customer_match(self):
        """Test that direct customer_id match still works"""
        self.log("=== TEST 4: Direct Customer Match ===")
        
        success, data = self.test(
            "Get contract with direct customer_id match",
            "GET",
            f"/customer-cabinet/{self.client_id}/contract-engine/{self.contract_direct_customer}",
            200,
            token=self.client_token,
            check_fn=lambda d: d.get("success") and d.get("contract")
        )
        
        if success:
            self.log("✅ Direct customer_id match works (REGRESSION OK)", "SUCCESS")
            return True
        else:
            self.log("❌ Direct customer_id match failed (REGRESSION)", "ERROR")
            return False

    def test_token_scoped_endpoints(self):
        """Test token-scoped /api/client/contract-engine endpoints (regression)"""
        self.log("=== TEST 5: Token-Scoped Endpoints (Regression) ===")
        
        # Test list endpoint
        success, data = self.test(
            "Token-scoped list endpoint",
            "GET",
            "/client/contract-engine",
            200,
            token=self.client_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("items"), list)
        )
        
        if not success:
            self.log("❌ Token-scoped list endpoint failed", "ERROR")
            return False
        
        # Test detail endpoint with demo contract WC-2026-000002
        success, data = self.test(
            "Token-scoped detail endpoint (WC-2026-000002)",
            "GET",
            "/client/contract-engine/WC-2026-000002",
            200,
            token=self.client_token,
            check_fn=lambda d: d.get("success") and d.get("contract")
        )
        
        if not success:
            self.log("⚠️  Demo contract WC-2026-000002 not accessible (may not exist)", "WARN")
        
        # Test foreign contract returns 404
        foreign_id = f"WC-FOREIGN-{uuid.uuid4().hex[:6].upper()}"
        success, data = self.test(
            "Token-scoped detail endpoint (foreign contract, should be 404)",
            "GET",
            f"/client/contract-engine/{foreign_id}",
            404,
            token=self.client_token
        )
        
        if success:
            self.log("✅ Token-scoped endpoints work correctly (REGRESSION OK)", "SUCCESS")
            return True
        else:
            self.log("❌ Token-scoped endpoints have issues", "ERROR")
            return False

    def cleanup(self):
        """Clean up test data"""
        self.log("=== CLEANUP: Removing test data ===")
        
        try:
            from pymongo import MongoClient
            import os
            
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/eco_nova")
            client = MongoClient(mongo_url)
            db = client.get_default_database()
            
            for contract_id in self.test_contracts:
                db.waste_contracts.delete_one({"id": contract_id})
                self.log(f"Deleted contract: {contract_id}")
            
            client.close()
            self.log("✅ Cleanup complete", "SUCCESS")
            
        except Exception as e:
            self.log(f"⚠️  Cleanup failed: {e}", "WARN")

    def run(self):
        """Run all tests"""
        self.log("=" * 60)
        self.log("CONTRACT OWNERSHIP FIX VERIFICATION")
        self.log("=" * 60)
        
        # Setup
        if not self.setup_auth():
            self.log("Setup failed, aborting tests", "ERROR")
            return 1
        
        if not self.create_test_data():
            self.log("Test data creation failed, aborting tests", "ERROR")
            return 1
        
        # Run tests
        self.test_ownership_fix_positive()
        self.test_ownership_fix_list()
        self.test_ownership_secure_negative()
        self.test_direct_customer_match()
        self.test_token_scoped_endpoints()
        
        # Cleanup
        self.cleanup()
        
        # Summary
        self.log("=" * 60)
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        self.log("=" * 60)
        
        if self.failures:
            self.log("FAILURES:", "ERROR")
            for failure in self.failures:
                self.log(f"  - {failure}", "ERROR")
        
        return 0 if self.tests_passed == self.tests_run else 1

if __name__ == "__main__":
    tester = ContractOwnershipTester()
    sys.exit(tester.run())
