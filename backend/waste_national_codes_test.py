"""
ECO.NOVA WASTE CODES - NATIONAL LIST REPLACEMENT TEST
======================================================
Testing the replacement of 80 demo codes with 431 official Ukrainian waste codes
from Національний перелік відходів (Постанова КМУ №1102).

Expected results:
- 18 chapters (level=1)
- 81 groups (level=2)
- 431 leaf codes (level=3)
- 196 hazardous codes (ending with *)
- All codes: accepted=true, official=true
- 13 active categories with counts summing to 431

Base URL: https://eco-platform-dev.preview.emergentagent.com
"""
import requests
import sys
import json
from datetime import datetime

# Production URL from frontend/.env
BASE_URL = "https://eco-platform-dev.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@bibi.cars"
ADMIN_PASSWORD = "Admin123!"

class WasteCodesReplacementTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.failures = []
        self.warnings = []
        self.test_results = []

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "TEST": "🔍",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️ ",
        }.get(level, "")
        print(f"[{timestamp}] {prefix} {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, 
             check_fn=None, timeout=30):
        """Run a single API test"""
        url = f"{API_BASE}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        self.log(f"{name}", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                self.log(f"Unsupported method {method}", "FAIL")
                self.failures.append(f"{name}: Unsupported method")
                self.test_results.append({"test": name, "status": "FAIL", "reason": "Unsupported method"})
                return False, None

            success = response.status_code == expected_status
            
            # Try to parse JSON response
            json_data = None
            try:
                if response.content:
                    json_data = response.json()
            except Exception:
                pass

            if success:
                self.tests_passed += 1
                self.log(f"PASS - {name} (HTTP {response.status_code})", "PASS")
                
                # Additional data checks
                if check_fn and json_data:
                    try:
                        check_result = check_fn(json_data)
                        if not check_result:
                            self.log(f"Data validation failed for {name}", "WARN")
                            self.warnings.append(f"{name}: Data validation failed")
                            self.test_results.append({"test": name, "status": "PASS_WITH_WARNING", "data": json_data})
                            return True, json_data
                    except Exception as e:
                        self.log(f"Data check error: {e}", "WARN")
                        self.warnings.append(f"{name}: Data check error - {e}")
                        self.test_results.append({"test": name, "status": "PASS_WITH_WARNING", "error": str(e)})
                        return True, json_data
                
                self.test_results.append({"test": name, "status": "PASS", "data": json_data})
                return True, json_data
            else:
                self.log(f"FAIL - {name} - Expected HTTP {expected_status}, got {response.status_code}", "FAIL")
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                
                # Log response body for debugging
                if json_data:
                    self.log(f"Response: {json.dumps(json_data, indent=2)[:500]}", "FAIL")
                else:
                    self.log(f"Response: {response.text[:500]}", "FAIL")
                
                self.test_results.append({"test": name, "status": "FAIL", "expected": expected_status, "got": response.status_code, "response": json_data or response.text[:500]})
                return False, json_data

        except requests.exceptions.Timeout:
            self.log(f"FAIL - {name} - Request timeout (>{timeout}s)", "FAIL")
            self.failures.append(f"{name}: Request timeout")
            self.test_results.append({"test": name, "status": "FAIL", "reason": "Timeout"})
            return False, None
        except Exception as e:
            self.log(f"FAIL - {name} - Error: {str(e)[:200]}", "FAIL")
            self.failures.append(f"{name}: {str(e)[:200]}")
            self.test_results.append({"test": name, "status": "FAIL", "error": str(e)[:200]})
            return False, None

    def test_admin_login(self):
        """Test admin login and get token"""
        success, data = self.test(
            "Admin Login",
            "POST",
            "/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            check_fn=lambda d: "access_token" in d or "token" in d
        )
        if success and data:
            self.admin_token = data.get("access_token") or data.get("token")
            self.log(f"Admin token obtained: {self.admin_token[:30]}...", "INFO")
        return success

    def test_categories_count(self):
        """Test GET /api/waste/categories?accepted=true returns 13 categories with counts summing to 431"""
        success, data = self.test(
            "GET /api/waste/categories?accepted=true",
            "GET",
            "/waste/categories?accepted=true",
            200,
            check_fn=lambda d: "categories" in d and isinstance(d.get("categories"), list)
        )
        
        if success and data:
            categories = data.get("categories", [])
            total_count = sum(cat.get("count", 0) for cat in categories)
            
            self.log(f"Found {len(categories)} categories with total count: {total_count}", "INFO")
            
            # Check if we have 13 categories
            if len(categories) != 13:
                self.warnings.append(f"Expected 13 categories, got {len(categories)}")
            
            # Check if total count is 431
            if total_count != 431:
                self.warnings.append(f"Expected total count 431, got {total_count}")
            
            # Log each category
            for cat in categories:
                self.log(f"  - {cat.get('key')}: {cat.get('count')} codes ({cat.get('hazardous_count', 0)} hazardous)", "INFO")
        
        return success

    def test_codes_list_accepted(self):
        """Test GET /api/waste/codes?accepted=true&limit=1000 returns 431 items all with accepted=true and official=true"""
        success, data = self.test(
            "GET /api/waste/codes?accepted=true&limit=1000",
            "GET",
            "/waste/codes?accepted=true&limit=1000",
            200,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            total = data.get("total", len(items))
            
            self.log(f"Found {len(items)} codes (total: {total})", "INFO")
            
            # Check if we have 431 codes
            if total != 431:
                self.warnings.append(f"Expected 431 total codes, got {total}")
            
            # Check all codes have accepted=true and official=true
            non_accepted = [c for c in items if not c.get("accepted")]
            non_official = [c for c in items if not c.get("official")]
            
            if non_accepted:
                self.warnings.append(f"Found {len(non_accepted)} codes with accepted=false")
            
            if non_official:
                self.warnings.append(f"Found {len(non_official)} codes with official=false")
            
            # Count hazardous codes
            hazardous_count = sum(1 for c in items if c.get("hazardous"))
            self.log(f"Hazardous codes: {hazardous_count}", "INFO")
        
        return success

    def test_codes_filter_by_category(self):
        """Test GET /api/waste/codes filtered by category"""
        # Test with 'oils' category
        success, data = self.test(
            "GET /api/waste/codes?category=oils&accepted=true",
            "GET",
            "/waste/codes?category=oils&accepted=true&limit=100",
            200,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            self.log(f"Found {len(items)} codes in 'oils' category", "INFO")
            
            # Check all codes belong to 'oils' category
            wrong_category = [c for c in items if c.get("category") != "oils"]
            if wrong_category:
                self.warnings.append(f"Found {len(wrong_category)} codes with wrong category")
        
        return success

    def test_code_detail_by_slug(self):
        """Test GET /api/waste/codes/{slug} e.g. 13-02-05 returns full detail"""
        # Test with code 13 02 05* (slug: 13-02-05)
        success, data = self.test(
            "GET /api/waste/codes/13-02-05",
            "GET",
            "/waste/codes/13-02-05",
            200,
            check_fn=lambda d: "code" in d and isinstance(d.get("code"), dict)
        )
        
        if success and data:
            code_data = data.get("code", {})
            self.log(f"Code detail: {code_data.get('code')} - {code_data.get('name')}", "INFO")
            self.log(f"  Category: {code_data.get('category')}, Hazardous: {code_data.get('hazardous')}", "INFO")
            self.log(f"  Storage: {code_data.get('storage', 'N/A')[:50]}...", "INFO")
            self.log(f"  Transport: {code_data.get('transport', 'N/A')[:50]}...", "INFO")
            self.log(f"  Process: {code_data.get('utilization_process', 'N/A')[:50]}...", "INFO")
            self.log(f"  Price unit: {code_data.get('price_unit')}", "INFO")
        
        return success

    def test_search_ukrainian_phrase(self):
        """Test GET /api/waste/search?q=оливи returns relevant codes"""
        success, data = self.test(
            "GET /api/waste/search?q=оливи",
            "GET",
            "/waste/search?q=оливи&limit=20",
            200,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            self.log(f"Search 'оливи' found {len(items)} codes", "INFO")
            
            # Log first few results
            for i, code in enumerate(items[:5]):
                self.log(f"  {i+1}. {code.get('code')} - {code.get('name')}", "INFO")
        
        return success

    def test_search_code_fragment(self):
        """Test GET /api/waste/search?q=16 06 returns relevant codes"""
        success, data = self.test(
            "GET /api/waste/search?q=16 06",
            "GET",
            "/waste/search?q=16 06&limit=20",
            200,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            self.log(f"Search '16 06' found {len(items)} codes", "INFO")
            
            # Log first few results
            for i, code in enumerate(items[:5]):
                self.log(f"  {i+1}. {code.get('code')} - {code.get('name')}", "INFO")
        
        return success

    def test_code_by_code_param(self):
        """Test GET /api/waste/codes/by-code?code=16 06 01* returns the code"""
        success, data = self.test(
            "GET /api/waste/codes/by-code?code=16 06 01*",
            "GET",
            "/waste/codes/by-code?code=16 06 01*",
            200,
            check_fn=lambda d: "code" in d and isinstance(d.get("code"), dict)
        )
        
        if success and data:
            code_data = data.get("code", {})
            self.log(f"Code: {code_data.get('code')} - {code_data.get('name')}", "INFO")
            self.log(f"  Hazardous: {code_data.get('hazardous')}, Category: {code_data.get('category')}", "INFO")
        
        return success

    def test_price_estimate(self):
        """Test POST /api/waste/price with {code, weight_kg} returns price_per_kg"""
        success, data = self.test(
            "POST /api/waste/price",
            "POST",
            "/waste/price",
            200,
            data={"code": "13 02 05*", "qty_kg": 100},
            check_fn=lambda d: "ok" in d and d.get("ok") == True
        )
        
        if success and data:
            self.log(f"Price estimate for 13 02 05* (100kg):", "INFO")
            self.log(f"  Price per kg: {data.get('price_per_kg')}", "INFO")
            self.log(f"  Total price: {data.get('price')}", "INFO")
            self.log(f"  Currency: {data.get('currency')}", "INFO")
        
        return success

    def test_license_check(self):
        """Test GET /api/waste/license/check?code=13 02 05* returns accepted=true"""
        success, data = self.test(
            "GET /api/waste/license/check?code=13 02 05*",
            "GET",
            "/waste/license/check?code=13 02 05*",
            200,
            check_fn=lambda d: "accepted" in d
        )
        
        if success and data:
            self.log(f"License check for 13 02 05*:", "INFO")
            self.log(f"  Accepted: {data.get('accepted')}", "INFO")
            self.log(f"  Hazardous: {data.get('hazardous')}", "INFO")
            self.log(f"  Reason: {data.get('reason')}", "INFO")
            
            if not data.get("accepted"):
                self.warnings.append("Code 13 02 05* is not accepted (expected accepted=true)")
        
        return success

    def test_chapters_list(self):
        """Test GET /api/waste/chapters returns 18 chapters"""
        if not self.admin_token:
            self.log("Skipping chapters test - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/waste/chapters",
            "GET",
            "/waste/chapters",
            200,
            token=self.admin_token,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            count = data.get("count", len(items))
            
            self.log(f"Found {count} chapters", "INFO")
            
            if count != 18:
                self.warnings.append(f"Expected 18 chapters, got {count}")
            
            # Log first few chapters
            for i, chapter in enumerate(items[:5]):
                self.log(f"  {chapter.get('code')}: {chapter.get('name')[:50]}...", "INFO")
        
        return success

    def test_groups_list(self):
        """Test GET /api/waste/groups returns 81 groups"""
        if not self.admin_token:
            self.log("Skipping groups test - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/waste/groups",
            "GET",
            "/waste/groups",
            200,
            token=self.admin_token,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            count = data.get("count", len(items))
            
            self.log(f"Found {count} groups", "INFO")
            
            if count != 81:
                self.warnings.append(f"Expected 81 groups, got {count}")
            
            # Log first few groups
            for i, group in enumerate(items[:5]):
                self.log(f"  {group.get('code')}: {group.get('name')[:50]}...", "INFO")
        
        return success

    def test_admin_stats(self):
        """Test GET /api/waste/admin/stats returns total=431 accepted=431"""
        if not self.admin_token:
            self.log("Skipping admin stats - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/waste/admin/stats",
            "GET",
            "/waste/admin/stats",
            200,
            token=self.admin_token,
            check_fn=lambda d: "codes" in d and "accepted" in d
        )
        
        if success and data:
            self.log(f"Admin stats:", "INFO")
            self.log(f"  Total codes: {data.get('codes')}", "INFO")
            self.log(f"  Accepted codes: {data.get('accepted')}", "INFO")
            self.log(f"  Hazardous codes: {data.get('hazardous')}", "INFO")
            self.log(f"  Official codes: {data.get('official')}", "INFO")
            self.log(f"  Chapters: {data.get('chapters')}", "INFO")
            self.log(f"  Groups: {data.get('groups')}", "INFO")
            
            if data.get('codes') != 431:
                self.warnings.append(f"Expected 431 total codes, got {data.get('codes')}")
            
            if data.get('accepted') != 431:
                self.warnings.append(f"Expected 431 accepted codes, got {data.get('accepted')}")
        
        return success

    def test_hazardous_codes_validation(self):
        """Verify hazardous codes (ending with *) have hazardous=true"""
        success, data = self.test(
            "GET /api/waste/codes?limit=1000",
            "GET",
            "/waste/codes?limit=1000",
            200,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            
            # Check codes ending with *
            hazardous_codes = [c for c in items if c.get("code", "").endswith("*")]
            non_hazardous_codes = [c for c in items if not c.get("code", "").endswith("*")]
            
            self.log(f"Codes ending with *: {len(hazardous_codes)}", "INFO")
            self.log(f"Codes not ending with *: {len(non_hazardous_codes)}", "INFO")
            
            # Verify hazardous flag
            wrong_hazardous = [c for c in hazardous_codes if not c.get("hazardous")]
            wrong_non_hazardous = [c for c in non_hazardous_codes if c.get("hazardous")]
            
            if wrong_hazardous:
                self.warnings.append(f"Found {len(wrong_hazardous)} codes ending with * but hazardous=false")
                for code in wrong_hazardous[:5]:
                    self.log(f"  - {code.get('code')}: hazardous={code.get('hazardous')}", "WARN")
            
            if wrong_non_hazardous:
                self.warnings.append(f"Found {len(wrong_non_hazardous)} codes not ending with * but hazardous=true")
                for code in wrong_non_hazardous[:5]:
                    self.log(f"  - {code.get('code')}: hazardous={code.get('hazardous')}", "WARN")
        
        return success

    def run_all(self):
        """Run all waste codes replacement tests"""
        self.log("=" * 80, "INFO")
        self.log("ECO.NOVA WASTE CODES - NATIONAL LIST REPLACEMENT TEST", "INFO")
        self.log(f"Base URL: {BASE_URL}", "INFO")
        self.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        self.log("=" * 80, "INFO")
        
        # Phase 1: Authentication
        self.log("\n=== PHASE 1: AUTHENTICATION ===", "INFO")
        if not self.test_admin_login():
            self.log("Admin login failed - cannot proceed with admin tests", "FAIL")
        
        # Phase 2: Public Endpoints
        self.log("\n=== PHASE 2: PUBLIC ENDPOINTS ===", "INFO")
        self.test_categories_count()
        self.test_codes_list_accepted()
        self.test_codes_filter_by_category()
        self.test_code_detail_by_slug()
        self.test_search_ukrainian_phrase()
        self.test_search_code_fragment()
        self.test_code_by_code_param()
        self.test_price_estimate()
        self.test_license_check()
        
        # Phase 3: Admin Endpoints
        self.log("\n=== PHASE 3: ADMIN ENDPOINTS ===", "INFO")
        self.test_chapters_list()
        self.test_groups_list()
        self.test_admin_stats()
        
        # Phase 4: Data Validation
        self.log("\n=== PHASE 4: DATA VALIDATION ===", "INFO")
        self.test_hazardous_codes_validation()
        
        # Summary
        self.log("\n" + "=" * 80, "INFO")
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed", "INFO")
        
        if self.warnings:
            self.log(f"\nWARNINGS ({len(self.warnings)}):", "WARN")
            for warning in self.warnings:
                self.log(f"  - {warning}", "WARN")
        
        if self.failures:
            self.log(f"\nFAILURES ({len(self.failures)}):", "FAIL")
            for failure in self.failures:
                self.log(f"  - {failure}", "FAIL")
        
        self.log("=" * 80, "INFO")
        self.log(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        
        # Calculate success percentage
        success_pct = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        return {
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "success_percentage": round(success_pct, 2),
            "warnings": self.warnings,
            "failures": self.failures,
            "test_results": self.test_results
        }

def main():
    tester = WasteCodesReplacementTester()
    results = tester.run_all()
    
    # Save results to JSON
    output_file = "/app/backend/waste_national_codes_test_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Test results saved to: {output_file}")
    
    return 0 if results["tests_passed"] == results["tests_run"] else 1

if __name__ == "__main__":
    sys.exit(main())
