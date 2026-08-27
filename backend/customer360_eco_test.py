"""
Customer 360 ECO Enhancements Test Suite
Tests the four new features:
1. Requests & Contracts tabs with real data
2. Unified activity timeline (invoice + waste events)
3. Global CRM search (customers, invoices, contracts, requests, companies)
4. Export Customer Card PDF
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://eco-waste-hub-12.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "EcoAdmin2026!"
MANAGER_EMAIL = "manager@eco.ua"
MANAGER_PASSWORD = "EcoManager2026!"

# Test data
DEMO_CUSTOMER_ID = "cust_d0019d11d646"
INDIVIDUAL_CUSTOMER_ID_PREFIX = "cust-1785498609"  # admin's individual customer

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.manager_token = None
        self.manager_id = None
        
    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")
        
    def test(self, name, condition, details=""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            self.log(f"✅ {name}", "PASS")
            if details:
                self.log(f"   {details}", "INFO")
        else:
            self.log(f"❌ {name}", "FAIL")
            if details:
                self.log(f"   {details}", "ERROR")
        return condition
    
    def login(self, email, password):
        """Login and return token"""
        try:
            r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                token = data.get("access_token") or data.get("token")
                user_id = data.get("user", {}).get("id") or data.get("id")
                self.log(f"✅ Login successful: {email}", "INFO")
                return token, user_id
            else:
                self.log(f"❌ Login failed: {r.status_code} - {r.text[:200]}", "ERROR")
                return None, None
        except Exception as e:
            self.log(f"❌ Login exception: {str(e)}", "ERROR")
            return None, None
    
    def get(self, endpoint, token, params=None):
        """Make authenticated GET request"""
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=15)
            return r
        except Exception as e:
            self.log(f"Request exception: {str(e)}", "ERROR")
            return None
    
    def run_all_tests(self):
        self.log("="*80)
        self.log("Customer 360 ECO Enhancements Test Suite")
        self.log("="*80)
        
        # Login as admin
        self.log("\n--- Admin Login ---")
        self.admin_token, _ = self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if not self.admin_token:
            self.log("❌ Admin login failed, cannot continue", "CRITICAL")
            return False
        
        # Login as manager
        self.log("\n--- Manager Login ---")
        self.manager_token, self.manager_id = self.login(MANAGER_EMAIL, MANAGER_PASSWORD)
        if not self.manager_token:
            self.log("❌ Manager login failed, cannot continue", "CRITICAL")
            return False
        
        # Test 1: Requests tab with real data
        self.log("\n--- Test 1: Requests Tab (Real Data) ---")
        self.test_requests_tab()
        
        # Test 2: Contracts tab with real data
        self.log("\n--- Test 2: Contracts Tab (Real Data) ---")
        self.test_contracts_tab()
        
        # Test 3: Unified activity timeline
        self.log("\n--- Test 3: Unified Activity Timeline ---")
        self.test_activity_timeline()
        
        # Test 4: Global CRM search
        self.log("\n--- Test 4: Global CRM Search ---")
        self.test_crm_search()
        
        # Test 5: Export Customer Card PDF
        self.log("\n--- Test 5: Export Customer Card PDF ---")
        self.test_export_pdf()
        
        # Test 6: RBAC enforcement
        self.log("\n--- Test 6: RBAC Enforcement ---")
        self.test_rbac()
        
        # Summary
        self.log("\n" + "="*80)
        self.log(f"Tests Passed: {self.tests_passed}/{self.tests_run}")
        self.log("="*80)
        
        return self.tests_passed == self.tests_run
    
    def test_requests_tab(self):
        """Test GET /api/customers/{id}/eco/requests returns >=2 real requests"""
        r = self.get(f"/customers/{DEMO_CUSTOMER_ID}/eco/requests", self.admin_token)
        
        if not r:
            self.test("Requests endpoint reachable", False, "Request failed")
            return
        
        self.test("Requests endpoint returns 200", r.status_code == 200, 
                 f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            self.test("Requests returns items array", "items" in data, 
                     f"Keys: {list(data.keys())}")
            self.test("Requests has >=2 items", len(items) >= 2, 
                     f"Found {len(items)} requests")
            
            if items:
                req = items[0]
                self.test("Request has required fields", 
                         all(k in req for k in ["id", "created_at"]),
                         f"Sample keys: {list(req.keys())[:10]}")
    
    def test_contracts_tab(self):
        """Test GET /api/customers/{id}/eco/contracts returns >=2 real contracts"""
        r = self.get(f"/customers/{DEMO_CUSTOMER_ID}/eco/contracts", self.admin_token)
        
        if not r:
            self.test("Contracts endpoint reachable", False, "Request failed")
            return
        
        self.test("Contracts endpoint returns 200", r.status_code == 200, 
                 f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            self.test("Contracts returns items array", "items" in data, 
                     f"Keys: {list(data.keys())}")
            self.test("Contracts has >=2 items", len(items) >= 2, 
                     f"Found {len(items)} contracts")
            
            if items:
                contract = items[0]
                self.test("Contract has required fields", 
                         all(k in contract for k in ["id", "created_at"]),
                         f"Sample keys: {list(contract.keys())[:10]}")
                
                # Check for WC-2026 contract numbers
                numbers = [c.get("number") or c.get("contract_number") for c in items]
                has_wc = any("WC-2026" in str(n) for n in numbers if n)
                self.test("Contracts include WC-2026 series", has_wc,
                         f"Numbers: {numbers[:3]}")
    
    def test_activity_timeline(self):
        """Test GET /api/customers/{id}/eco/activity returns unified timeline"""
        r = self.get(f"/customers/{DEMO_CUSTOMER_ID}/eco/activity", self.admin_token)
        
        if not r:
            self.test("Activity endpoint reachable", False, "Request failed")
            return
        
        self.test("Activity endpoint returns 200", r.status_code == 200, 
                 f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            events = data.get("events", [])
            comments = data.get("comments", [])
            
            self.test("Activity returns events array", "events" in data, 
                     f"Keys: {list(data.keys())}")
            self.test("Activity returns comments array", "comments" in data)
            self.test("Activity has events", len(events) > 0, 
                     f"Found {len(events)} events")
            
            if events:
                # Check for invoice events (kind='invoice')
                invoice_events = [e for e in events if e.get("kind") == "invoice"]
                self.test("Timeline includes invoice events", len(invoice_events) > 0,
                         f"Found {len(invoice_events)} invoice events")
                
                # Check for waste/contract events
                waste_events = [e for e in events if e.get("kind") == "event"]
                self.test("Timeline includes waste/contract events", len(waste_events) > 0,
                         f"Found {len(waste_events)} waste events")
                
                # Check event structure
                if invoice_events:
                    inv_event = invoice_events[0]
                    self.test("Invoice event has amount in title", 
                             "UAH" in str(inv_event.get("title", "")),
                             f"Title: {inv_event.get('title', '')[:80]}")
                    self.test("Invoice event has required fields",
                             all(k in inv_event for k in ["id", "kind", "title", "created_at"]),
                             f"Keys: {list(inv_event.keys())}")
    
    def test_crm_search(self):
        """Test GET /api/crm/search with various queries"""
        
        # Test 1: Search for "Демо" (should return customer + company)
        r = self.get("/crm/search", self.admin_token, params={"q": "Демо"})
        if r and r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            self.test("Search 'Демо' returns groups", len(groups) > 0,
                     f"Found {len(groups)} groups")
            
            if groups:
                types = [g.get("type") for g in groups]
                self.test("Search 'Демо' includes customer type", "customer" in types,
                         f"Types: {types}")
                
                # Check customer result structure
                customer_group = next((g for g in groups if g.get("type") == "customer"), None)
                if customer_group:
                    items = customer_group.get("items", [])
                    if items:
                        item = items[0]
                        self.test("Customer result has display_label", "display_label" in item,
                                 f"Label: {item.get('display_label', '')[:80]}")
                        self.test("Customer result has customer_360_url", "customer_360_url" in item,
                                 f"URL: {item.get('customer_360_url', '')}")
                        # Check for "Company — email" format
                        label = item.get("display_label", "")
                        self.test("Customer label has 'Company — email' format", 
                                 "—" in label and "@" in label,
                                 f"Label: {label}")
        else:
            self.test("Search 'Демо' endpoint", False, f"Status: {r.status_code if r else 'None'}")
        
        # Test 2: Search by email
        r = self.get("/crm/search", self.admin_token, params={"q": "client@eco.ua"})
        if r and r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            types = [g.get("type") for g in groups]
            self.test("Search by email returns customer", "customer" in types,
                     f"Types: {types}")
        
        # Test 3: Search by contract number
        r = self.get("/crm/search", self.admin_token, params={"q": "WC-2026"})
        if r and r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            types = [g.get("type") for g in groups]
            self.test("Search 'WC-2026' returns contract", "contract" in types,
                     f"Types: {types}")
        
        # Test 4: Short query (< 2 chars) returns empty
        r = self.get("/crm/search", self.admin_token, params={"q": "x"})
        if r and r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            total_items = sum(len(g.get("items", [])) for g in groups)
            self.test("Short query returns empty results", total_items == 0,
                     f"Found {total_items} items")
        
        # Test 5: No password field in results
        r = self.get("/crm/search", self.admin_token, params={"q": "Демо"})
        if r and r.status_code == 200:
            data = r.json()
            has_password = "password" in str(data).lower()
            self.test("Search results do NOT contain password field", not has_password)
    
    def test_export_pdf(self):
        """Test GET /api/customers/{id}/card.pdf"""
        
        # Test 1: Valid customer returns PDF
        r = self.get(f"/customers/{DEMO_CUSTOMER_ID}/card.pdf", self.admin_token)
        
        if not r:
            self.test("PDF export endpoint reachable", False, "Request failed")
            return
        
        self.test("PDF export returns 200", r.status_code == 200,
                 f"Status: {r.status_code}")
        
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            self.test("PDF has correct Content-Type", "application/pdf" in content_type,
                     f"Content-Type: {content_type}")
            
            content_length = len(r.content)
            self.test("PDF body is non-trivial (>2KB)", content_length > 2048,
                     f"Size: {content_length} bytes")
            
            # Check for PDF magic bytes
            is_pdf = r.content[:4] == b'%PDF'
            self.test("PDF has valid PDF header", is_pdf,
                     f"Header: {r.content[:10]}")
        
        # Test 2: Non-existent customer returns 404
        r = self.get("/customers/nonexistent_id_12345/card.pdf", self.admin_token)
        if r:
            self.test("PDF export for non-existent customer returns 404", 
                     r.status_code == 404,
                     f"Status: {r.status_code}")
    
    def test_rbac(self):
        """Test RBAC enforcement for manager scope"""
        
        # Test 1: Manager can access their own customer (demo client)
        r = self.get(f"/customers/{DEMO_CUSTOMER_ID}/eco/requests", self.manager_token)
        if r:
            self.test("Manager can access owned customer (requests)", 
                     r.status_code == 200,
                     f"Status: {r.status_code}")
        
        # Test 2: Manager search is scoped to their own customers
        r = self.get("/crm/search", self.manager_token, params={"q": "Демо"})
        if r and r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            customer_group = next((g for g in groups if g.get("type") == "customer"), None)
            if customer_group:
                items = customer_group.get("items", [])
                # Manager should find demo client (they own it)
                has_demo = any(DEMO_CUSTOMER_ID in str(item.get("id", "")) for item in items)
                self.test("Manager search finds owned customer", has_demo,
                         f"Found {len(items)} customers")
        
        # Test 3: Manager cannot export PDF for customer they don't own
        # First, try to find an individual customer ID (admin's customer)
        r = self.get("/crm/search", self.admin_token, params={"q": "ihor.kovalchuk"})
        individual_id = None
        if r and r.status_code == 200:
            data = r.json()
            groups = data.get("groups", [])
            customer_group = next((g for g in groups if g.get("type") == "customer"), None)
            if customer_group and customer_group.get("items"):
                individual_id = customer_group["items"][0].get("id")
        
        if individual_id:
            r = self.get(f"/customers/{individual_id}/card.pdf", self.manager_token)
            if r:
                self.test("Manager gets 403 for non-owned customer PDF", 
                         r.status_code == 403,
                         f"Status: {r.status_code}, Customer: {individual_id}")
        else:
            self.log("⚠️  Could not find individual customer for RBAC test", "WARN")

def main():
    runner = TestRunner()
    success = runner.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
