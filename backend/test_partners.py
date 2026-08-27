"""
Backend test for Partners feature redesign.
Tests:
1. GET /api/site-info returns partners.items with image_url + logo_url + link
2. POST /api/admin/site-info/upload-partner-logo returns {success, url} and URL is fetchable
3. PUT /api/admin/site-info persists partner data
"""
import requests
import sys
from io import BytesIO
from PIL import Image

API_URL = "https://admin-logic-test-4.preview.emergentagent.com"

class PartnersBackendTest:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def log(self, msg, status="info"):
        prefix = {
            "info": "ℹ️",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️"
        }.get(status, "•")
        print(f"{prefix} {msg}")

    def test(self, name, fn):
        """Run a single test"""
        self.tests_run += 1
        self.log(f"Testing: {name}", "info")
        try:
            fn()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "success")
            return True
        except AssertionError as e:
            self.log(f"FAILED: {name} - {e}", "error")
            self.failures.append({"test": name, "error": str(e)})
            return False
        except Exception as e:
            self.log(f"ERROR: {name} - {e}", "error")
            self.failures.append({"test": name, "error": str(e)})
            return False

    def login(self):
        """Login as admin"""
        self.log("Logging in as admin@eco.ua...", "info")
        try:
            r = requests.post(
                f"{API_URL}/api/auth/login",
                json={"email": "admin@eco.ua", "password": "EcoAdmin2026!"},
                timeout=10
            )
            assert r.status_code == 200, f"Login failed with status {r.status_code}: {r.text}"
            data = r.json()
            # Token can be in 'token' or 'access_token'
            self.token = data.get("token") or data.get("access_token")
            assert self.token, "No token or access_token in login response"
            self.log("Login successful", "success")
            return True
        except Exception as e:
            self.log(f"Login failed: {e}", "error")
            return False

    def test_get_site_info(self):
        """Test GET /api/site-info returns partners with image_url + logo_url + link"""
        r = requests.get(f"{API_URL}/api/site-info", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        
        data = r.json()
        assert "partners" in data, "No 'partners' key in response"
        
        partners = data["partners"]
        assert "items" in partners, "No 'items' in partners"
        
        items = partners["items"]
        self.log(f"Found {len(items)} partner items", "info")
        
        # Check structure of each item
        for i, item in enumerate(items):
            assert "image_url" in item, f"Partner {i} missing 'image_url'"
            assert "logo_url" in item, f"Partner {i} missing 'logo_url'"
            assert "link" in item, f"Partner {i} missing 'link'"
            assert "name_uk" in item, f"Partner {i} missing 'name_uk'"
            assert "name_en" in item, f"Partner {i} missing 'name_en'"
            assert "desc_uk" in item, f"Partner {i} missing 'desc_uk'"
            assert "desc_en" in item, f"Partner {i} missing 'desc_en'"
            self.log(f"  Partner {i}: {item.get('name_en', 'N/A')} - image_url={bool(item.get('image_url'))}, logo_url={bool(item.get('logo_url'))}", "info")

    def test_upload_partner_logo(self):
        """Test POST /api/admin/site-info/upload-partner-logo"""
        assert self.token, "No auth token available"
        
        # Create a small test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        headers = {"Authorization": f"Bearer {self.token}"}
        files = {"image": ("test.png", img_bytes, "image/png")}
        
        r = requests.post(
            f"{API_URL}/api/admin/site-info/upload-partner-logo",
            headers=headers,
            files=files,
            timeout=15
        )
        
        assert r.status_code == 200, f"Upload failed with status {r.status_code}: {r.text}"
        
        data = r.json()
        assert data.get("success") is True, "Upload did not return success=True"
        assert "url" in data, "No 'url' in upload response"
        
        url = data["url"]
        self.log(f"Uploaded image URL: {url}", "info")
        
        # Verify the URL is fetchable
        full_url = f"{API_URL}{url}" if url.startswith("/") else url
        r2 = requests.get(full_url, timeout=10)
        assert r2.status_code == 200, f"Uploaded image not fetchable: {r2.status_code}"
        assert len(r2.content) > 0, "Uploaded image has zero bytes"
        self.log(f"Image is fetchable ({len(r2.content)} bytes)", "success")

    def test_update_site_info_partners(self):
        """Test PUT /api/admin/site-info with partners data"""
        assert self.token, "No auth token available"
        
        # First get current site info
        r = requests.get(f"{API_URL}/api/site-info", timeout=10)
        assert r.status_code == 200, "Failed to get site-info"
        current = r.json()
        
        # Prepare update payload with partners
        partners = current.get("partners", {})
        items = partners.get("items", [])
        
        # Add a test partner if none exist
        if len(items) == 0:
            items.append({
                "id": "test-partner-1",
                "enabled": True,
                "name_uk": "Тестовий партнер",
                "name_en": "Test Partner",
                "desc_uk": "Опис тестового партнера",
                "desc_en": "Test partner description",
                "image_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=70",
                "logo_url": "",
                "link": "https://example.com"
            })
        
        payload = {
            "partners": {
                "enabled": True,
                "title_uk": partners.get("title_uk", "Наші партнери"),
                "title_en": partners.get("title_en", "Our partners"),
                "subtitle_uk": partners.get("subtitle_uk", ""),
                "subtitle_en": partners.get("subtitle_en", ""),
                "items": items
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        r = requests.put(
            f"{API_URL}/api/admin/site-info",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        assert r.status_code == 200, f"Update failed with status {r.status_code}: {r.text}"
        
        data = r.json()
        assert "partners" in data, "No 'partners' in response"
        self.log("Partners data persisted successfully", "success")

    def run_all(self):
        """Run all tests"""
        self.log("=" * 60, "info")
        self.log("PARTNERS BACKEND TESTS", "info")
        self.log("=" * 60, "info")
        
        # Login first
        if not self.login():
            self.log("Cannot proceed without login", "error")
            return False
        
        # Run tests
        self.test("GET /api/site-info returns partners structure", self.test_get_site_info)
        self.test("POST /api/admin/site-info/upload-partner-logo", self.test_upload_partner_logo)
        self.test("PUT /api/admin/site-info persists partners", self.test_update_site_info_partners)
        
        # Summary
        self.log("=" * 60, "info")
        self.log(f"Tests run: {self.tests_run}", "info")
        self.log(f"Tests passed: {self.tests_passed}", "success" if self.tests_passed == self.tests_run else "warning")
        self.log(f"Tests failed: {len(self.failures)}", "error" if self.failures else "info")
        
        if self.failures:
            self.log("\nFailed tests:", "error")
            for f in self.failures:
                self.log(f"  • {f['test']}: {f['error']}", "error")
        
        return self.tests_passed == self.tests_run

if __name__ == "__main__":
    tester = PartnersBackendTest()
    success = tester.run_all()
    sys.exit(0 if success else 1)
