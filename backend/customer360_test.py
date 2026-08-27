"""
ECO NOVA — Customer 360 Feature Test
=====================================
Tests the end-to-end customer logic (сквозна customer logic):
1. Staff login (admin@eco.ua)
2. Invoice list shows 'Company — email' (NOT raw customer_id)
3. Customer 360 page loads with real data
4. Customer 360 KPIs show correct values
5. Customer 360 tabs load real data (Заявки, Рахунки, Договори, Акти)
6. Backend search in invoices (email, company, no match)
7. Company 360 shows linked contact persons
8. Backend RBAC (404 for non-existent, 200 for valid)
"""
import requests
import sys
from datetime import datetime

# Production URL from frontend/.env
BASE_URL = "https://waste-recycler-2.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Seeded credentials
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "EcoAdmin2026!"
DEMO_CUSTOMER_ID = "cust_f238b645ceae"
DEMO_COMPANY_ID = "wco_cfaeccdc02a7"

class Customer360Tester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.failures = []

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
            else:
                self.log(f"Unsupported method {method}", "ERROR")
                self.failures.append(f"{name}: Unsupported method")
                return False, None

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - {name} (status: {response.status_code})", "PASS")
                
                # Additional data checks
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

    def run_all_tests(self):
        self.log("="*80)
        self.log("ECO NOVA Customer 360 Feature Test")
        self.log("="*80)

        # 1. Staff Login
        self.log("\n--- 1. Staff Authentication ---")
        success, data = self.test(
            "Staff login (admin@eco.ua)",
            "POST",
            "/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if not success or not data:
            self.log("❌ Cannot proceed without admin token", "ERROR")
            return self.print_summary()
        
        self.admin_token = data.get("access_token") or data.get("token")
        if not self.admin_token:
            self.log("❌ No token in login response", "ERROR")
            return self.print_summary()
        
        self.log(f"✓ Admin token obtained", "INFO")

        # 2. Invoice List - Check customer DTO enrichment
        self.log("\n--- 2. Invoice List (Customer DTO Enrichment) ---")
        success, data = self.test(
            "GET /api/manager/invoices/my - list invoices",
            "GET",
            "/manager/invoices/my",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("items"), list)
        )
        
        if success and data:
            items = data.get("items", [])
            self.log(f"Found {len(items)} invoices", "INFO")
            
            # Check if any invoice has the demo customer
            demo_invoice = None
            for inv in items:
                if inv.get("customerId") == DEMO_CUSTOMER_ID:
                    demo_invoice = inv
                    break
            
            if demo_invoice:
                customer = demo_invoice.get("customer")
                if customer:
                    display_label = customer.get("display_label", "")
                    email = customer.get("email", "")
                    company_name = customer.get("company_name", "")
                    
                    self.log(f"Demo invoice customer DTO:", "INFO")
                    self.log(f"  display_label: {display_label}", "INFO")
                    self.log(f"  email: {email}", "INFO")
                    self.log(f"  company_name: {company_name}", "INFO")
                    
                    # Verify NOT showing raw customer_id as primary text
                    if DEMO_CUSTOMER_ID in display_label:
                        self.log(f"⚠️  WARNING: Raw customer_id found in display_label", "WARN")
                        self.failures.append("Invoice shows raw customer_id in display_label")
                    
                    # Verify email is present
                    if not email or "client@eco.ua" not in email:
                        self.log(f"⚠️  WARNING: Expected email 'client@eco.ua' not found", "WARN")
                        self.failures.append("Invoice customer email not correct")
                    
                    # Verify company name is present
                    if not company_name or "Демо" not in company_name:
                        self.log(f"⚠️  WARNING: Expected company name with 'Демо' not found", "WARN")
                        self.failures.append("Invoice customer company_name not correct")
                else:
                    self.log(f"⚠️  WARNING: Demo invoice has no customer DTO", "WARN")
                    self.failures.append("Invoice missing customer DTO")
            else:
                self.log(f"⚠️  No invoice found for demo customer {DEMO_CUSTOMER_ID}", "WARN")

        # 3. Backend Search in Invoices
        self.log("\n--- 3. Backend Search in Invoices ---")
        
        # Search by email
        success, data = self.test(
            "Search invoices by email (client@eco.ua)",
            "GET",
            "/manager/invoices/my?q=client@eco.ua",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and len(d.get("items", [])) > 0
        )
        if success and data:
            self.log(f"✓ Found {len(data.get('items', []))} invoices by email", "INFO")
        
        # Search by company name
        success, data = self.test(
            "Search invoices by company name (Демо)",
            "GET",
            "/manager/invoices/my?q=Демо",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and len(d.get("items", [])) > 0
        )
        if success and data:
            self.log(f"✓ Found {len(data.get('items', []))} invoices by company name", "INFO")
        
        # Search with no match
        success, data = self.test(
            "Search invoices with no match (zzznomatch)",
            "GET",
            "/manager/invoices/my?q=zzznomatch",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and len(d.get("items", [])) == 0
        )
        if success and data:
            self.log(f"✓ No invoices found for non-matching search", "INFO")

        # 4. Customer 360 Overview
        self.log("\n--- 4. Customer 360 Overview ---")
        success, data = self.test(
            f"GET /api/customers/{DEMO_CUSTOMER_ID}/eco/overview",
            "GET",
            f"/customers/{DEMO_CUSTOMER_ID}/eco/overview",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and d.get("summary") is not None
        )
        
        if success and data:
            summary = data.get("summary", {})
            customer = data.get("customer", {})
            
            self.log(f"Customer 360 Overview KPIs:", "INFO")
            self.log(f"  Заявок: {summary.get('requests_total', 0)}", "INFO")
            self.log(f"  Активні договори: {summary.get('active_contracts', 0)}", "INFO")
            self.log(f"  Виставлено: {summary.get('invoiced_amount', 0)} {summary.get('currency', 'UAH')}", "INFO")
            self.log(f"  Оплачено: {summary.get('paid_amount', 0)} {summary.get('currency', 'UAH')}", "INFO")
            self.log(f"  Борг: {summary.get('debt_amount', 0)} {summary.get('currency', 'UAH')}", "INFO")
            self.log(f"  Прострочено: {summary.get('overdue_amount', 0)} {summary.get('currency', 'UAH')}", "INFO")
            self.log(f"  Відкриті задачі: {summary.get('open_tasks', 0)}", "INFO")
            self.log(f"  Остання активність: {summary.get('last_activity', '—')}", "INFO")
            
            # Verify expected values from seed data
            if summary.get('requests_total', 0) != 2:
                self.log(f"⚠️  Expected 2 requests, got {summary.get('requests_total', 0)}", "WARN")
                self.failures.append(f"Customer 360: Expected 2 requests, got {summary.get('requests_total', 0)}")
            
            if summary.get('active_contracts', 0) != 1:
                self.log(f"⚠️  Expected 1 active contract, got {summary.get('active_contracts', 0)}", "WARN")
                self.failures.append(f"Customer 360: Expected 1 active contract, got {summary.get('active_contracts', 0)}")
            
            if summary.get('debt_amount', 0) != 333:
                self.log(f"⚠️  Expected debt 333 UAH, got {summary.get('debt_amount', 0)}", "WARN")
                self.failures.append(f"Customer 360: Expected debt 333 UAH, got {summary.get('debt_amount', 0)}")

        # 5. Customer 360 Tabs - Requests
        self.log("\n--- 5. Customer 360 Tabs ---")
        success, data = self.test(
            f"GET /api/customers/{DEMO_CUSTOMER_ID}/eco/requests",
            "GET",
            f"/customers/{DEMO_CUSTOMER_ID}/eco/requests",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("items"), list)
        )
        if success and data:
            items = data.get("items", [])
            self.log(f"✓ Заявки tab: {len(items)} requests", "INFO")
            if len(items) != 2:
                self.log(f"⚠️  Expected 2 requests, got {len(items)}", "WARN")
                self.failures.append(f"Customer 360 Заявки: Expected 2, got {len(items)}")

        # Contracts
        success, data = self.test(
            f"GET /api/customers/{DEMO_CUSTOMER_ID}/eco/contracts",
            "GET",
            f"/customers/{DEMO_CUSTOMER_ID}/eco/contracts",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("items"), list)
        )
        if success and data:
            items = data.get("items", [])
            self.log(f"✓ Договори tab: {len(items)} contracts", "INFO")
            if len(items) != 1:
                self.log(f"⚠️  Expected 1 contract, got {len(items)}", "WARN")
                self.failures.append(f"Customer 360 Договори: Expected 1, got {len(items)}")

        # Acts
        success, data = self.test(
            f"GET /api/customers/{DEMO_CUSTOMER_ID}/eco/acts",
            "GET",
            f"/customers/{DEMO_CUSTOMER_ID}/eco/acts",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("acts"), list)
        )
        if success and data:
            acts = data.get("acts", [])
            self.log(f"✓ Акти tab: {len(acts)} acts", "INFO")
            if len(acts) != 1:
                self.log(f"⚠️  Expected 1 act, got {len(acts)}", "WARN")
                self.failures.append(f"Customer 360 Акти: Expected 1, got {len(acts)}")

        # 6. Company 360 - Contact Persons
        self.log("\n--- 6. Company 360 - Contact Persons ---")
        success, data = self.test(
            f"GET /api/companies/{DEMO_COMPANY_ID}/customers",
            "GET",
            f"/companies/{DEMO_COMPANY_ID}/customers",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and isinstance(d.get("items"), list)
        )
        if success and data:
            items = data.get("items", [])
            self.log(f"✓ Company contact persons: {len(items)} customers", "INFO")
            
            # Check if demo customer is in the list
            demo_found = False
            for item in items:
                if item.get("id") == DEMO_CUSTOMER_ID:
                    demo_found = True
                    self.log(f"✓ Demo customer found in company contacts", "INFO")
                    self.log(f"  email: {item.get('email')}", "INFO")
                    self.log(f"  display_label: {item.get('display_label')}", "INFO")
                    break
            
            if not demo_found:
                self.log(f"⚠️  Demo customer not found in company contacts", "WARN")
                self.failures.append("Company 360: Demo customer not in contact persons list")

        # 7. Backend RBAC Tests
        self.log("\n--- 7. Backend RBAC Tests ---")
        
        # Test 404 for non-existent customer
        success, data = self.test(
            "GET /api/customers/cust_DOESNOTEXIST/eco/overview (should 404)",
            "GET",
            "/customers/cust_DOESNOTEXIST/eco/overview",
            404,
            token=self.admin_token
        )
        if success:
            self.log(f"✓ Correctly returns 404 for non-existent customer", "INFO")
        
        # Test 200 for valid customer
        success, data = self.test(
            f"GET /api/customers/{DEMO_CUSTOMER_ID}/eco/overview (should 200)",
            "GET",
            f"/customers/{DEMO_CUSTOMER_ID}/eco/overview",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") and d.get("summary") is not None
        )
        if success:
            self.log(f"✓ Correctly returns 200 for valid customer", "INFO")

        return self.print_summary()

    def print_summary(self):
        self.log("\n" + "="*80)
        self.log("TEST SUMMARY")
        self.log("="*80)
        self.log(f"Tests Run: {self.tests_run}")
        self.log(f"Tests Passed: {self.tests_passed}")
        self.log(f"Tests Failed: {self.tests_run - self.tests_passed}")
        
        if self.failures:
            self.log("\n❌ FAILURES:", "ERROR")
            for i, failure in enumerate(self.failures, 1):
                self.log(f"  {i}. {failure}", "ERROR")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            self.log("\n✅ ALL TESTS PASSED!", "PASS")
            return 0
        else:
            self.log("\n❌ SOME TESTS FAILED", "FAIL")
            return 1

def main():
    tester = Customer360Tester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
