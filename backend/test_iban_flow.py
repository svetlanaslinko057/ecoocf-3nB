"""
Quick IBAN flow backend API test - verify endpoints are accessible
"""
import requests
import sys
import os

BASE_URL = "https://repo-deployment-7.preview.emergentagent.com"
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "EcoAdmin2026!"
MANAGER_EMAIL = "manager@eco.ua"
MANAGER_PASSWORD = "EcoManager2026!"
CLIENT_EMAIL = "client@eco.ua"

class IBANTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.manager_token = None
        self.client_token = None

    def test(self, name, method, endpoint, expected_status, token=None, data=None):
        url = f"{BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            else:
                print(f"❌ Unsupported method {method}")
                return False

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASS - Status: {response.status_code}")
                return True
            else:
                print(f"❌ FAIL - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.text[:300]}")
                except Exception:
                    pass
                return False

        except Exception as e:
            print(f"❌ FAIL - Error: {str(e)}")
            return False

    def login_staff(self, email, password):
        print(f"\n🔐 Logging in as {email}...")
        url = f"{BASE_URL}/api/auth/login"
        try:
            response = requests.post(url, json={"email": email, "password": password}, timeout=15)
            if response.status_code == 200:
                token = response.json()["access_token"]
                print(f"✅ Login successful")
                return token
            else:
                print(f"❌ Login failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Login error: {e}")
            return None

    def login_client(self, email):
        print(f"\n🔐 Client dev-login as {email}...")
        url = f"{BASE_URL}/api/client/dev-login"
        try:
            response = requests.post(url, json={"email": email, "name": "Test Client"}, timeout=15)
            if response.status_code == 200:
                token = response.json()["token"]
                print(f"✅ Client login successful")
                return token
            else:
                print(f"❌ Client login failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Client login error: {e}")
            return None

    def run(self):
        print("=" * 60)
        print("ECO.NOVA IBAN Flow Backend API Test")
        print("=" * 60)

        # Login
        self.admin_token = self.login_staff(ADMIN_EMAIL, ADMIN_PASSWORD)
        self.manager_token = self.login_staff(MANAGER_EMAIL, MANAGER_PASSWORD)
        self.client_token = self.login_client(CLIENT_EMAIL)

        if not all([self.admin_token, self.manager_token, self.client_token]):
            print("\n❌ CRITICAL: Login failed for one or more roles")
            return False

        # Test IBAN endpoints
        print("\n" + "=" * 60)
        print("Testing IBAN Endpoints")
        print("=" * 60)

        # Admin: Get requisites
        self.test(
            "Admin GET requisites",
            "GET",
            "/api/admin/billing/requisites",
            200,
            self.admin_token
        )

        # Manager: Get requisites (preview)
        self.test(
            "Manager GET requisites preview",
            "GET",
            "/api/billing/requisites",
            200,
            self.manager_token
        )

        # Manager: List invoices
        self.test(
            "Manager GET my invoices",
            "GET",
            "/api/manager/invoices/my",
            200,
            self.manager_token
        )

        # Manager: Pending confirmation queue
        self.test(
            "Manager GET pending confirmation",
            "GET",
            "/api/manager/invoices/pending-confirmation",
            200,
            self.manager_token
        )

        # Client: List invoices
        self.test(
            "Client GET invoices",
            "GET",
            "/api/client/invoices",
            200,
            self.client_token
        )

        # Print results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Tests passed: {self.tests_passed}/{self.tests_run}")
        
        if self.tests_passed == self.tests_run:
            print("✅ ALL BACKEND IBAN ENDPOINTS ACCESSIBLE")
            return True
        else:
            print("❌ SOME BACKEND TESTS FAILED")
            return False

def main():
    tester = IBANTester()
    success = tester.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
