"""
Admin SEO Center Backend Test — Phase B2
=========================================
Tests all 15+ admin SEO endpoints + public SEO endpoints + security.

Coverage:
1. Admin login (admin@bibi.cars / Admin12345!)
2. GET /api/admin/seo/settings (global SEO)
3. PATCH /api/admin/seo/settings (toggle allow_indexing_in_production)
4. GET /api/admin/seo/company (E-E-A-T)
5. PUT /api/admin/seo/company (with validation: email, lat, lng)
6. GET /api/admin/seo/analytics (GA4/GTM/Pixel)
7. PUT /api/admin/seo/analytics (with validation: GA4 format)
8. GET /api/admin/seo/pages (page metadata CRUD)
9. POST /api/admin/seo/pages (create override for /)
10. DELETE /api/admin/seo/pages/ (remove override)
11. GET /api/admin/seo/sitemap (sitemap state)
12. GET /api/admin/seo/sitemap/preview?kind=pages (XML preview)
13. POST /api/admin/seo/sitemap/regenerate
14. GET /api/admin/seo/robots (robots config)
15. PUT /api/admin/seo/robots (mode=noindex)
16. GET /api/admin/seo/robots/preview (robots.txt preview)
17. GET /api/seo/meta?path=/ (public metadata with admin override)
18. GET /api/seo/robots.txt (public robots.txt)
19. Unauthenticated access returns 401/403
20. Master switch: preview environment always shows Disallow: /
"""
import requests
import sys
import os
import json

# Public endpoint from frontend/.env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://extended-admin-test.preview.emergentagent.com")

# Test credentials
ADMIN_EMAIL = "admin@bibi.cars"
ADMIN_PASSWORD = "Admin12345!"

class SeoTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.created_page_path = None

    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, check_fn=None):
        """Run a single API test"""
        url = f"{BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        self.log(f"Testing {name}...", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)
            else:
                self.log(f"Unsupported method {method}", "ERROR")
                return False, None

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - {name} - Status: {response.status_code}", "PASS")
                
                # Additional data checks
                if check_fn and response.status_code in (200, 201):
                    try:
                        json_data = response.json()
                        if not check_fn(json_data):
                            self.log(f"⚠️  Data validation failed for {name}", "WARN")
                            return False, json_data
                    except Exception as e:
                        self.log(f"⚠️  Data check error: {e}", "WARN")
                
                try:
                    return True, response.json() if response.status_code in (200, 201) else response.text
                except Exception:
                    return True, response.text
            else:
                self.log(f"❌ FAIL - {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    self.log(f"Response: {response.text[:300]}", "DEBUG")
                except Exception:
                    pass
                return False, None

        except requests.exceptions.Timeout:
            self.log(f"❌ FAIL - {name} - Request timeout", "FAIL")
            return False, None
        except Exception as e:
            self.log(f"❌ FAIL - {name} - Error: {str(e)}", "FAIL")
            return False, None

    def login(self):
        """Login as admin"""
        self.log(f"Logging in as {ADMIN_EMAIL}...", "AUTH")
        url = f"{BASE_URL}/api/auth/login"
        try:
            response = requests.post(url, json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.admin_token = data.get("token") or data.get("access_token")
                self.log(f"✅ Login successful, token: {self.admin_token[:20]}...", "AUTH")
                return True
            else:
                self.log(f"❌ Login failed: {response.status_code} - {response.text[:200]}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Login error: {str(e)}", "ERROR")
            return False

    def run_all_tests(self):
        """Run all SEO Center tests"""
        self.log("=" * 60, "INFO")
        self.log("Admin SEO Center Backend Test — Phase B2", "INFO")
        self.log("=" * 60, "INFO")

        # 1. Login
        if not self.login():
            self.log("Cannot proceed without admin token", "ERROR")
            return False

        # 2. Test unauthenticated access (should return 401/403)
        self.log("\n--- Testing Security (Unauthenticated Access) ---", "INFO")
        self.test(
            "Unauthenticated /api/admin/seo/settings",
            "GET", "/api/admin/seo/settings", 401,
            token=None
        )
        self.test(
            "Unauthenticated /api/admin/seo/company",
            "GET", "/api/admin/seo/company", 401,
            token=None
        )

        # 3. GET /api/admin/seo/settings
        self.log("\n--- Testing Global SEO Settings ---", "INFO")
        success, settings_data = self.test(
            "GET /api/admin/seo/settings",
            "GET", "/api/admin/seo/settings", 200,
            token=self.admin_token,
            check_fn=lambda d: "settings" in d and "public_origin" in d["settings"]
        )

        # 4. PATCH /api/admin/seo/settings (toggle allow_indexing_in_production)
        if success and settings_data:
            current_indexing = settings_data.get("settings", {}).get("allow_indexing_in_production", False)
            new_indexing = not current_indexing
            self.test(
                f"PATCH /api/admin/seo/settings (toggle indexing to {new_indexing})",
                "PATCH", "/api/admin/seo/settings", 200,
                token=self.admin_token,
                data={"allow_indexing_in_production": new_indexing},
                check_fn=lambda d: d.get("settings", {}).get("allow_indexing_in_production") == new_indexing
            )
            # Toggle back
            self.test(
                f"PATCH /api/admin/seo/settings (toggle back to {current_indexing})",
                "PATCH", "/api/admin/seo/settings", 200,
                token=self.admin_token,
                data={"allow_indexing_in_production": current_indexing}
            )

        # 5. GET /api/admin/seo/company
        self.log("\n--- Testing Company Profile (E-E-A-T) ---", "INFO")
        self.test(
            "GET /api/admin/seo/company",
            "GET", "/api/admin/seo/company", 200,
            token=self.admin_token,
            check_fn=lambda d: "company" in d
        )

        # 6. PUT /api/admin/seo/company (valid data)
        self.test(
            "PUT /api/admin/seo/company (valid)",
            "PUT", "/api/admin/seo/company", 200,
            token=self.admin_token,
            data={
                "legal_name": "ТОВ ЕКО-НОВА",
                "edrpou": "12345678",
                "company_email": "info@eco-nova.ua",
                "company_lat": "50.4501",
                "company_lng": "30.5234"
            },
            check_fn=lambda d: d.get("success") == True
        )

        # 7. PUT /api/admin/seo/company (invalid email - should return 422)
        self.test(
            "PUT /api/admin/seo/company (invalid email)",
            "PUT", "/api/admin/seo/company", 422,
            token=self.admin_token,
            data={"company_email": "not-an-email"}
        )

        # 8. PUT /api/admin/seo/company (invalid lat - should return 422)
        self.test(
            "PUT /api/admin/seo/company (invalid lat)",
            "PUT", "/api/admin/seo/company", 422,
            token=self.admin_token,
            data={"company_lat": "999"}
        )

        # 9. GET /api/admin/seo/analytics
        self.log("\n--- Testing Analytics & Verifications ---", "INFO")
        self.test(
            "GET /api/admin/seo/analytics",
            "GET", "/api/admin/seo/analytics", 200,
            token=self.admin_token,
            check_fn=lambda d: "analytics" in d
        )

        # 10. PUT /api/admin/seo/analytics (valid GA4)
        self.test(
            "PUT /api/admin/seo/analytics (valid GA4)",
            "PUT", "/api/admin/seo/analytics", 200,
            token=self.admin_token,
            data={
                "ga4_measurement_id": "G-ABCD123456",
                "gtm_container_id": "GTM-ABCD123"
            },
            check_fn=lambda d: d.get("success") == True
        )

        # 11. PUT /api/admin/seo/analytics (invalid GA4 - should return 422)
        self.test(
            "PUT /api/admin/seo/analytics (invalid GA4)",
            "PUT", "/api/admin/seo/analytics", 422,
            token=self.admin_token,
            data={"ga4_measurement_id": "INVALID-FORMAT"}
        )

        # 12. GET /api/admin/seo/pages
        self.log("\n--- Testing Page Metadata CRUD ---", "INFO")
        success, pages_data = self.test(
            "GET /api/admin/seo/pages",
            "GET", "/api/admin/seo/pages", 200,
            token=self.admin_token,
            check_fn=lambda d: "items" in d and "known_routes" in d
        )

        # 13. POST /api/admin/seo/pages (create override for /)
        success, create_data = self.test(
            "POST /api/admin/seo/pages (create / override)",
            "POST", "/api/admin/seo/pages", 200,
            token=self.admin_token,
            data={
                "path": "/",
                "_uk": {
                    "title": "Test Title Override",
                    "description": "Test Description Override"
                },
                "faq": [
                    {"q": "Test Question?", "a": "Test Answer!"}
                ]
            },
            check_fn=lambda d: d.get("success") == True and d.get("path") == "/"
        )

        # 14. Verify /api/seo/meta?path=/ picks up the admin override
        self.log("\n--- Testing Public SEO Metadata ---", "INFO")
        self.test(
            "GET /api/seo/meta?path=/ (should have admin override)",
            "GET", "/api/seo/meta?path=/&lang=uk", 200,
            token=None,  # Public endpoint
            check_fn=lambda d: "Test Title Override" in d.get("title", "") or "Test Title Override" in d.get("shortTitle", "")
        )

        # 15. Verify JSON-LD contains FAQPage node
        success, meta_data = self.test(
            "GET /api/seo/meta?path=/ (check FAQPage in JSON-LD)",
            "GET", "/api/seo/meta?path=/&lang=uk", 200,
            token=None,
            check_fn=lambda d: any(
                node.get("@type") == "FAQPage" 
                for node in d.get("jsonld", {}).get("@graph", [])
            )
        )

        # 16. DELETE /api/admin/seo/pages/
        self.test(
            "DELETE /api/admin/seo/pages/ (remove override)",
            "DELETE", "/api/admin/seo/pages/", 200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") == True
        )

        # 17. GET /api/admin/seo/sitemap
        self.log("\n--- Testing Sitemap Manager ---", "INFO")
        self.test(
            "GET /api/admin/seo/sitemap",
            "GET", "/api/admin/seo/sitemap", 200,
            token=self.admin_token,
            check_fn=lambda d: "sitemap" in d and "urls_included" in d["sitemap"]
        )

        # 18. GET /api/admin/seo/sitemap/preview?kind=pages
        success, sitemap_xml = self.test(
            "GET /api/admin/seo/sitemap/preview?kind=pages",
            "GET", "/api/admin/seo/sitemap/preview?kind=pages", 200,
            token=self.admin_token,
            check_fn=lambda d: "<?xml" in str(d) and "<urlset" in str(d)
        )

        # 19. POST /api/admin/seo/sitemap/regenerate
        self.test(
            "POST /api/admin/seo/sitemap/regenerate",
            "POST", "/api/admin/seo/sitemap/regenerate", 200,
            token=self.admin_token,
            check_fn=lambda d: d.get("success") == True and "regenerated_at" in d
        )

        # 20. GET /api/admin/seo/robots
        self.log("\n--- Testing Robots Manager ---", "INFO")
        success, robots_data = self.test(
            "GET /api/admin/seo/robots",
            "GET", "/api/admin/seo/robots", 200,
            token=self.admin_token,
            check_fn=lambda d: "robots" in d and "context" in d
        )

        # 21. PUT /api/admin/seo/robots (mode=noindex)
        self.test(
            "PUT /api/admin/seo/robots (mode=noindex)",
            "PUT", "/api/admin/seo/robots", 200,
            token=self.admin_token,
            data={
                "mode": "noindex",
                "disallow": ["/private"]
            },
            check_fn=lambda d: d.get("success") == True
        )

        # 22. GET /api/admin/seo/robots/preview
        success, robots_preview = self.test(
            "GET /api/admin/seo/robots/preview",
            "GET", "/api/admin/seo/robots/preview", 200,
            token=self.admin_token,
            check_fn=lambda d: "Disallow: /" in str(d) and "admin forced noindex" in str(d)
        )

        # 23. Reset robots mode to auto
        self.test(
            "PUT /api/admin/seo/robots (reset to auto)",
            "PUT", "/api/admin/seo/robots", 200,
            token=self.admin_token,
            data={"mode": "auto"}
        )

        # 24. GET /api/seo/robots.txt (public)
        self.log("\n--- Testing Public Robots.txt ---", "INFO")
        success, robots_txt = self.test(
            "GET /api/seo/robots.txt (preview env should have Disallow: /)",
            "GET", "/api/seo/robots.txt", 200,
            token=None,
            check_fn=lambda d: "Disallow: /" in str(d)
        )
        if success:
            self.log(f"Robots.txt preview (first 300 chars): {str(robots_txt)[:300]}", "DEBUG")

        # Summary
        self.log("\n" + "=" * 60, "INFO")
        self.log(f"Tests passed: {self.tests_passed}/{self.tests_run}", "INFO")
        self.log("=" * 60, "INFO")
        
        return self.tests_passed == self.tests_run

def main():
    tester = SeoTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
