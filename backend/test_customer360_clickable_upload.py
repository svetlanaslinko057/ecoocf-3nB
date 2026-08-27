#!/usr/bin/env python3
"""
Backend test for Customer 360 clickable names + acts/reports upload.

Tests:
1. Admin/manager login
2. Customer eco acts endpoint with RBAC
3. File upload with entity_type/entity_id linkage
4. Uploaded files appear in acts/reports
"""
import requests
import sys
import io
from datetime import datetime

BASE_URL = "https://eco-waste-hub-12.preview.emergentagent.com"

class Customer360UploadTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.admin_token = None
        self.manager_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.demo_customer_id = "cust_d0019d11d646"
        self.manager_id = "staff_manager_1785497772"

    def log(self, msg, status="info"):
        prefix = {
            "pass": "✅",
            "fail": "❌",
            "info": "🔍",
            "warn": "⚠️"
        }.get(status, "ℹ️")
        print(f"{prefix} {msg}")

    def test(self, name, fn):
        """Run a test function"""
        self.tests_run += 1
        self.log(f"Testing {name}...", "info")
        try:
            fn()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "pass")
            return True
        except AssertionError as e:
            self.log(f"FAILED: {name} - {e}", "fail")
            return False
        except Exception as e:
            self.log(f"ERROR: {name} - {e}", "fail")
            return False

    def login(self, email, password):
        """Login and return token"""
        r = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"email": email, "password": password}
        )
        if r.status_code != 200:
            raise Exception(f"Login failed: {r.status_code} - {r.text}")
        data = r.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            raise Exception(f"No token in response: {data}")
        return token

    def get_headers(self, token):
        """Get auth headers"""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def test_admin_login(self):
        """Test admin login"""
        self.admin_token = self.login("admin@eco.ua", "EcoAdmin2026!")
        assert self.admin_token, "Admin token is empty"
        self.log(f"Admin logged in, token: {self.admin_token[:20]}...")

    def test_manager_login(self):
        """Test manager login"""
        self.manager_token = self.login("manager@eco.ua", "EcoManager2026!")
        assert self.manager_token, "Manager token is empty"
        self.log(f"Manager logged in, token: {self.manager_token[:20]}...")

    def test_manager_can_access_owned_customer_acts(self):
        """Manager can access acts for owned customer cust_d0019d11d646"""
        r = requests.get(
            f"{self.base_url}/api/customers/{self.demo_customer_id}/eco/acts",
            headers=self.get_headers(self.manager_token)
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("success"), f"Response not successful: {data}"
        assert "acts" in data, f"No 'acts' in response: {data}"
        assert "reports" in data, f"No 'reports' in response: {data}"
        
        # Check for uploaded items (demo customer should have at least one)
        acts = data.get("acts", [])
        reports = data.get("reports", [])
        uploaded_acts = [a for a in acts if a.get("uploaded")]
        uploaded_reports = [r for r in reports if r.get("uploaded")]
        
        self.log(f"Found {len(acts)} acts ({len(uploaded_acts)} uploaded), {len(reports)} reports ({len(uploaded_reports)} uploaded)")
        
        # Verify uploaded items have required fields
        for act in uploaded_acts:
            assert act.get("file_id"), f"Uploaded act missing file_id: {act}"
            assert act.get("title"), f"Uploaded act missing title: {act}"
            self.log(f"  Uploaded act: {act.get('title')} (file_id: {act.get('file_id')})")

    def test_manager_cannot_access_non_owned_customer(self):
        """Manager gets 403 for customer they don't own"""
        # First, get a list of customers as admin to find one NOT owned by manager
        r = requests.get(
            f"{self.base_url}/api/customers?limit=50",
            headers=self.get_headers(self.admin_token)
        )
        assert r.status_code == 200, f"Failed to get customers: {r.status_code}"
        data = r.json()
        customers = data.get("items") or data.get("data") or []
        
        # Find a customer NOT owned by manager (individual customer starting with 'cust-1785498609')
        non_owned = None
        for c in customers:
            cid = c.get("id", "")
            manager_id = c.get("managerId") or c.get("manager_id")
            # Look for individual customers (not the demo client) not owned by this manager
            if cid.startswith("cust-1785498609") and manager_id != self.manager_id:
                non_owned = cid
                break
        
        if not non_owned:
            self.log("No non-owned customer found, skipping RBAC test", "warn")
            return
        
        self.log(f"Testing RBAC with non-owned customer: {non_owned}")
        r = requests.get(
            f"{self.base_url}/api/customers/{non_owned}/eco/acts",
            headers=self.get_headers(self.manager_token)
        )
        assert r.status_code == 403, f"Expected 403 for non-owned customer, got {r.status_code}: {r.text}"
        self.log(f"Correctly got 403 for non-owned customer {non_owned}")

    def test_upload_act_file(self):
        """Upload an act file via POST /api/storage/files"""
        # Create a small test PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n%%EOF"
        
        files = {
            "file": ("test_act.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {
            "purpose": "act",
            "entity_type": "customer",
            "entity_id": self.demo_customer_id,
            "title": f"Test Act Upload {datetime.now().strftime('%H:%M:%S')}"
        }
        
        r = requests.post(
            f"{self.base_url}/api/storage/files",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert r.status_code == 200, f"Upload failed: {r.status_code} - {r.text}"
        result = r.json()
        assert result.get("success"), f"Upload not successful: {result}"
        assert result.get("file"), f"No file in response: {result}"
        
        file_obj = result["file"]
        assert file_obj.get("id"), f"No file id: {file_obj}"
        assert file_obj.get("url"), f"No file url: {file_obj}"
        
        self.log(f"Uploaded act file: {file_obj.get('id')}")
        
        # Verify it appears in acts endpoint
        r = requests.get(
            f"{self.base_url}/api/customers/{self.demo_customer_id}/eco/acts",
            headers=self.get_headers(self.admin_token)
        )
        assert r.status_code == 200, f"Failed to get acts: {r.status_code}"
        data = r.json()
        acts = data.get("acts", [])
        
        # Find our uploaded act
        found = False
        for act in acts:
            if act.get("file_id") == file_obj.get("id"):
                found = True
                assert act.get("uploaded"), f"Act not marked as uploaded: {act}"
                self.log(f"Verified uploaded act appears in acts list")
                break
        
        assert found, f"Uploaded act not found in acts list"

    def test_upload_ecologist_report(self):
        """Upload an ecologist report via POST /api/storage/files"""
        # Create a small test PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n%%EOF"
        
        files = {
            "file": ("test_report.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {
            "purpose": "ecologist_report",
            "entity_type": "customer",
            "entity_id": self.demo_customer_id,
            "title": f"Test Report Upload {datetime.now().strftime('%H:%M:%S')}"
        }
        
        r = requests.post(
            f"{self.base_url}/api/storage/files",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert r.status_code == 200, f"Upload failed: {r.status_code} - {r.text}"
        result = r.json()
        assert result.get("success"), f"Upload not successful: {result}"
        assert result.get("file"), f"No file in response: {result}"
        
        file_obj = result["file"]
        assert file_obj.get("id"), f"No file id: {file_obj}"
        
        self.log(f"Uploaded report file: {file_obj.get('id')}")
        
        # Verify it appears in reports endpoint
        r = requests.get(
            f"{self.base_url}/api/customers/{self.demo_customer_id}/eco/acts",
            headers=self.get_headers(self.admin_token)
        )
        assert r.status_code == 200, f"Failed to get acts: {r.status_code}"
        data = r.json()
        reports = data.get("reports", [])
        
        # Find our uploaded report
        found = False
        for report in reports:
            if report.get("file_id") == file_obj.get("id"):
                found = True
                assert report.get("uploaded"), f"Report not marked as uploaded: {report}"
                self.log(f"Verified uploaded report appears in reports list")
                break
        
        assert found, f"Uploaded report not found in reports list"

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("Customer 360 Clickable Names + Upload Tests")
        print("="*60 + "\n")
        
        # Login tests
        self.test("Admin Login", self.test_admin_login)
        self.test("Manager Login", self.test_manager_login)
        
        # Backend API tests
        self.test("Manager can access owned customer acts", 
                  self.test_manager_can_access_owned_customer_acts)
        self.test("Manager cannot access non-owned customer (403)", 
                  self.test_manager_cannot_access_non_owned_customer)
        self.test("Upload act file", self.test_upload_act_file)
        self.test("Upload ecologist report", self.test_upload_ecologist_report)
        
        # Summary
        print("\n" + "="*60)
        print(f"Tests: {self.tests_passed}/{self.tests_run} passed")
        print("="*60 + "\n")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = Customer360UploadTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
