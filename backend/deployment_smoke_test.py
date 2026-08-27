"""
ECO.NOVA Deployment Smoke Test
================================
Fresh deployment verification for ECO.NOVA B2B hazardous waste platform.
Tests basic deployment health, auth, and key endpoints.

Stack: FastAPI + React 19 + MongoDB
UI Language: Ukrainian
"""
import requests
import sys
import os
from datetime import datetime

# Public endpoint from frontend/.env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://code-review-staging-1.preview.emergentagent.com")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@bibi.cars"
ADMIN_PASSWORD = "Admin12345!"
MANAGER_EMAIL = "manager@bibi.cars"
MANAGER_PASSWORD = "Manager12345!"

class DeploymentTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.admin_token = None
        self.manager_token = None
        self.failures = []

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, check_fn=None):
        """Run a single API test"""
        url = f"{BASE_URL}{endpoint}"
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
            else:
                self.log(f"Unsupported method {method}", "ERROR")
                self.tests_failed += 1
                self.failures.append(f"{name}: Unsupported method {method}")
                return False

            success = response.status_code == expected_status
            
            # Additional checks
            if success and check_fn:
                try:
                    json_data = response.json()
                    if not check_fn(json_data):
                        success = False
                        self.log(f"  ❌ FAIL - Data validation failed", "FAIL")
                        self.failures.append(f"{name}: Data validation failed")
                except Exception as e:
                    success = False
                    self.log(f"  ❌ FAIL - Check function error: {e}", "FAIL")
                    self.failures.append(f"{name}: Check error - {e}")
            
            if success:
                self.tests_passed += 1
                self.log(f"  ✅ PASS - Status: {response.status_code}", "PASS")
                return response
            else:
                self.tests_failed += 1
                self.log(f"  ❌ FAIL - Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    self.log(f"  Response: {response.text[:300]}", "DEBUG")
                except Exception:
                    pass
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            self.tests_failed += 1
            self.log(f"  ❌ FAIL - Request timeout (15s)", "FAIL")
            self.failures.append(f"{name}: Timeout")
            return None
        except Exception as e:
            self.tests_failed += 1
            self.log(f"  ❌ FAIL - Error: {str(e)}", "FAIL")
            self.failures.append(f"{name}: {str(e)}")
            return None

    def run_all_tests(self):
        """Run all deployment smoke tests"""
        self.log("="*80, "INFO")
        self.log("ECO.NOVA DEPLOYMENT SMOKE TEST", "INFO")
        self.log(f"Base URL: {BASE_URL}", "INFO")
        self.log("="*80, "INFO")
        
        # ═══════════════════════════════════════════════════════════════
        # 1. HEALTH CHECK
        # ═══════════════════════════════════════════════════════════════
        self.log("\n[1] HEALTH CHECK", "SECTION")
        
        response = self.test(
            "Health endpoint",
            "GET",
            "/api/health",
            200,
            check_fn=lambda d: d.get('status') == 'ok' and d.get('mongo_ok') == True
        )
        
        if response:
            try:
                data = response.json()
                self.log(f"  MongoDB: {'✅ Connected' if data.get('mongo_ok') else '❌ Not connected'}", "INFO")
            except Exception:
                pass
        
        # ═══════════════════════════════════════════════════════════════
        # 2. AUTHENTICATION
        # ═══════════════════════════════════════════════════════════════
        self.log("\n[2] AUTHENTICATION", "SECTION")
        
        # Admin login
        self.log(f"Logging in as admin: {ADMIN_EMAIL}", "AUTH")
        response = self.test(
            "Admin login",
            "POST",
            "/api/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            check_fn=lambda d: 'access_token' in d or 'token' in d
        )
        
        if response:
            try:
                data = response.json()
                self.admin_token = data.get('access_token') or data.get('token')
                self.log(f"  ✅ Admin token obtained", "AUTH")
            except Exception:
                self.log(f"  ❌ Failed to extract admin token", "AUTH")
        
        # Manager login
        self.log(f"Logging in as manager: {MANAGER_EMAIL}", "AUTH")
        response = self.test(
            "Manager login",
            "POST",
            "/api/auth/login",
            200,
            data={"email": MANAGER_EMAIL, "password": MANAGER_PASSWORD},
            check_fn=lambda d: 'access_token' in d or 'token' in d
        )
        
        if response:
            try:
                data = response.json()
                self.manager_token = data.get('access_token') or data.get('token')
                self.log(f"  ✅ Manager token obtained", "AUTH")
            except Exception:
                self.log(f"  ❌ Failed to extract manager token", "AUTH")
        
        if not self.admin_token:
            self.log("❌ CRITICAL: Admin login failed - cannot continue with authenticated tests", "CRITICAL")
            return False
        
        # Test /api/auth/me
        self.test(
            "Get current user (admin)",
            "GET",
            "/api/auth/me",
            200,
            token=self.admin_token,
            check_fn=lambda d: 'email' in d or 'user' in d
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 3. ADMIN ENDPOINTS
        # ═══════════════════════════════════════════════════════════════
        self.log("\n[3] ADMIN ENDPOINTS", "SECTION")
        
        # Dashboard/summary endpoints
        self.test(
            "Admin staff list",
            "GET",
            "/api/staff",
            200,
            token=self.admin_token
        )
        
        self.test(
            "Admin settings",
            "GET",
            "/api/settings",
            200,
            token=self.admin_token
        )
        
        # Waste domain endpoints (admin scope)
        self.test(
            "Waste companies list",
            "GET",
            "/api/waste/companies",
            200,
            token=self.admin_token
        )
        
        self.test(
            "Waste requests list",
            "GET",
            "/api/waste/requests",
            200,
            token=self.admin_token
        )
        
        self.test(
            "Waste stats",
            "GET",
            "/api/waste/stats",
            200,
            token=self.admin_token
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 4. PUBLIC ENDPOINTS (Waste Catalog)
        # ═══════════════════════════════════════════════════════════════
        self.log("\n[4] PUBLIC ENDPOINTS (Waste Catalog)", "SECTION")
        
        self.test(
            "Public waste categories",
            "GET",
            "/api/waste/categories",
            200,
            check_fn=lambda d: isinstance(d, list) or 'categories' in d
        )
        
        self.test(
            "Public waste codes",
            "GET",
            "/api/waste/codes",
            200,
            check_fn=lambda d: isinstance(d, list) or 'codes' in d or 'items' in d
        )
        
        self.test(
            "Public waste search",
            "GET",
            "/api/waste/search?q=пластик",
            200
        )
        
        self.test(
            "Public license check",
            "GET",
            "/api/waste/license/check?code=17.01.01",
            200
        )
        
        # ═══════════════════════════════════════════════════════════════
        # 5. MANAGER ENDPOINTS
        # ═══════════════════════════════════════════════════════════════
        self.log("\n[5] MANAGER ENDPOINTS", "SECTION")
        
        if self.manager_token:
            self.test(
                "Manager auth/me",
                "GET",
                "/api/auth/me",
                200,
                token=self.manager_token
            )
            
            self.test(
                "Manager calls (my)",
                "GET",
                "/api/manager/calls/my",
                200,
                token=self.manager_token
            )
            
            self.test(
                "Manager waste companies",
                "GET",
                "/api/waste/companies",
                200,
                token=self.manager_token
            )
        else:
            self.log("⚠️  Skipping manager tests - manager login failed", "WARN")
        
        # ═══════════════════════════════════════════════════════════════
        # 6. CRM ENDPOINTS
        # ═══════════════════════════════════════════════════════════════
        self.log("\n[6] CRM ENDPOINTS", "SECTION")
        
        self.test(
            "Tasks list",
            "GET",
            "/api/tasks",
            200,
            token=self.admin_token
        )
        
        self.test(
            "Invoices list",
            "GET",
            "/api/invoices",
            200,
            token=self.admin_token
        )
        
        self.test(
            "Documents list",
            "GET",
            "/api/documents",
            200,
            token=self.admin_token
        )
        
        return True

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*80, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("="*80, "INFO")
        self.log(f"Tests Run:    {self.tests_run}", "INFO")
        self.log(f"Tests Passed: {self.tests_passed} ✅", "INFO")
        self.log(f"Tests Failed: {self.tests_failed} ❌", "INFO")
        
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run * 100)
            self.log(f"Success Rate: {success_rate:.1f}%", "INFO")
        
        if self.failures:
            self.log("\nFailed Tests:", "INFO")
            for failure in self.failures:
                self.log(f"  - {failure}", "FAIL")
        
        self.log("="*80, "INFO")
        
        if self.tests_passed == self.tests_run:
            self.log("✅ ALL TESTS PASSED - DEPLOYMENT VERIFIED", "SUCCESS")
            return 0
        else:
            self.log("❌ SOME TESTS FAILED - DEPLOYMENT ISSUES DETECTED", "FAILURE")
            return 1

def main():
    tester = DeploymentTester()
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        tester.log("\n⚠️  Tests interrupted by user", "WARN")
    except Exception as e:
        tester.log(f"\n❌ Unexpected error: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
    
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
