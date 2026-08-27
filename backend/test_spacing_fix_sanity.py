#!/usr/bin/env python3
"""
Backend sanity checks for spacing fix regression testing.
Tests 3 endpoints:
1. GET /api/waste/stats (requires admin token)
2. GET /api/seo/robots.txt (public)
3. GET /api/public/blog/articles (public)
"""
import requests
import sys
import os

BASE_URL = os.getenv("REACT_APP_BACKEND_URL", "https://circular-hub-11.preview.emergentagent.com")
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "EcoAdmin2026!"

class SanityTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log(self, msg, success=None):
        """Log test result"""
        print(msg)
        if success is not None:
            self.results.append({"message": msg, "success": success})

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        self.log(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                self.log(f"❌ Failed - Unsupported method {method}", False)
                return False, {}

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ Passed - Status: {response.status_code}", True)
            else:
                self.log(f"❌ Failed - Expected {expected_status}, got {response.status_code}", False)
                try:
                    self.log(f"   Response: {response.text[:200]}")
                except Exception:
                    pass

            try:
                return success, response.json() if success else {}
            except Exception:
                return success, {}

        except Exception as e:
            self.log(f"❌ Failed - Error: {str(e)}", False)
            return False, {}

    def test_admin_login(self):
        """Test admin login and get token"""
        self.log("\n" + "="*60)
        self.log("STEP 1: Admin Login")
        self.log("="*60)
        
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "/api/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.log(f"✅ Token acquired: {self.token[:20]}...")
            return True
        elif success and 'token' in response:
            self.token = response['token']
            self.log(f"✅ Token acquired: {self.token[:20]}...")
            return True
        else:
            self.log("❌ Login failed - no token in response", False)
            return False

    def test_waste_stats(self):
        """Test GET /api/waste/stats (requires admin token)"""
        self.log("\n" + "="*60)
        self.log("STEP 2: Waste Stats (Admin)")
        self.log("="*60)
        
        if not self.token:
            self.log("❌ Skipped - No admin token", False)
            return False
        
        success, _ = self.run_test(
            "Waste Stats",
            "GET",
            "/api/waste/stats",
            200
        )
        return success

    def test_robots_txt(self):
        """Test GET /api/seo/robots.txt (public)"""
        self.log("\n" + "="*60)
        self.log("STEP 3: Robots.txt (Public)")
        self.log("="*60)
        
        # Temporarily remove token for public endpoint
        temp_token = self.token
        self.token = None
        
        success, _ = self.run_test(
            "Robots.txt",
            "GET",
            "/api/seo/robots.txt",
            200
        )
        
        self.token = temp_token
        return success

    def test_blog_articles(self):
        """Test GET /api/public/blog/articles (public)"""
        self.log("\n" + "="*60)
        self.log("STEP 4: Blog Articles (Public)")
        self.log("="*60)
        
        # Temporarily remove token for public endpoint
        temp_token = self.token
        self.token = None
        
        success, _ = self.run_test(
            "Blog Articles",
            "GET",
            "/api/public/blog/articles",
            200
        )
        
        self.token = temp_token
        return success

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*60)
        self.log("SUMMARY")
        self.log("="*60)
        self.log(f"📊 Tests passed: {self.tests_passed}/{self.tests_run}")
        
        if self.tests_passed == self.tests_run:
            self.log("✅ All backend sanity checks passed!")
            return 0
        else:
            self.log("❌ Some tests failed")
            return 1

def main():
    tester = SanityTester()
    
    print("="*60)
    print("Backend Sanity Checks - Spacing Fix Regression")
    print(f"Base URL: {BASE_URL}")
    print("="*60)
    
    # Run tests
    tester.test_admin_login()
    tester.test_waste_stats()
    tester.test_robots_txt()
    tester.test_blog_articles()
    
    # Print summary
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
