"""
ECO.NOVA - Waste Catalog Features Test
=======================================
Testing catalog category enhancements:
- Category descriptions (UA/EN)
- Cover image upload
- Drag-and-drop reordering
- Homepage catalog quick-links

Base URL from frontend/.env
"""
import requests
import sys
import time
import json
import os
from datetime import datetime

# Production URL from frontend/.env
BASE_URL = "https://eco-recycler-3.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "admin@bibi.cars"
ADMIN_PASSWORD = "Admin@12345"

class CatalogFeaturesTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.failures = []
        self.warnings = []
        self.test_category_key = None

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
             check_fn=None, timeout=15, files=None):
        """Run a single API test"""
        url = f"{API_BASE}{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        # Don't set Content-Type for multipart/form-data (files)
        if not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        self.log(f"{name}", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers={k:v for k,v in headers.items() if k != 'Content-Type'}, timeout=timeout)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                self.log(f"Unsupported method {method}", "FAIL")
                self.failures.append(f"{name}: Unsupported method")
                return False, None

            success = response.status_code == expected_status
            
            json_data = None
            try:
                if response.content:
                    json_data = response.json()
            except Exception:
                pass

            if success:
                self.tests_passed += 1
                self.log(f"PASS - {name} (HTTP {response.status_code})", "PASS")
                
                if check_fn and json_data:
                    try:
                        check_result = check_fn(json_data)
                        if not check_result:
                            self.log(f"Data validation failed for {name}", "WARN")
                            self.warnings.append(f"{name}: Data validation failed")
                    except Exception as e:
                        self.log(f"Data check error: {e}", "WARN")
                        self.warnings.append(f"{name}: Data check error - {e}")
                
                return True, json_data
            else:
                self.log(f"FAIL - {name} - Expected HTTP {expected_status}, got {response.status_code}", "FAIL")
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                
                if json_data:
                    self.log(f"Response: {json.dumps(json_data, indent=2)[:500]}", "FAIL")
                else:
                    self.log(f"Response: {response.text[:500]}", "FAIL")
                
                return False, json_data

        except Exception as e:
            self.log(f"FAIL - {name} - Error: {str(e)[:200]}", "FAIL")
            self.failures.append(f"{name}: {str(e)[:200]}")
            return False, None

    def test_admin_login(self):
        """Test admin login"""
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

    def test_get_admin_categories(self):
        """Test GET /api/waste/admin/categories - should return desc_uk, desc_en, image_url"""
        if not self.admin_token:
            self.log("Skipping - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/waste/admin/categories",
            "GET",
            "/waste/admin/categories",
            200,
            token=self.admin_token,
            check_fn=lambda d: (
                "success" in d and
                "categories" in d and
                isinstance(d.get("categories"), list)
            )
        )
        
        if success and data:
            categories = data.get("categories", [])
            self.log(f"Found {len(categories)} categories", "INFO")
            
            # Check if categories have the new fields
            if categories:
                first_cat = categories[0]
                has_desc_uk = "desc_uk" in first_cat
                has_desc_en = "desc_en" in first_cat
                has_image_url = "image_url" in first_cat
                
                self.log(f"Category fields: desc_uk={has_desc_uk}, desc_en={has_desc_en}, image_url={has_image_url}", "INFO")
                
                if not (has_desc_uk and has_desc_en and has_image_url):
                    self.warnings.append("Categories missing desc_uk, desc_en, or image_url fields")
                
                # Check medical category specifically
                medical = next((c for c in categories if c.get("key") == "medical"), None)
                if medical:
                    self.log(f"Medical category: desc_uk={bool(medical.get('desc_uk'))}, desc_en={bool(medical.get('desc_en'))}, image_url={bool(medical.get('image_url'))}, codes={len(medical.get('codes', []))}", "INFO")
        
        return success

    def test_upload_image(self):
        """Test POST /api/admin/media/upload - should return asset.url"""
        if not self.admin_token:
            self.log("Skipping - no admin token", "WARN")
            return False, None
        
        # Create a small test image (1x1 PNG)
        test_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test_image.png', test_image_data, 'image/png')}
        
        success, data = self.test(
            "POST /api/admin/media/upload",
            "POST",
            "/admin/media/upload",
            200,
            token=self.admin_token,
            files=files,
            check_fn=lambda d: "asset" in d and "url" in d.get("asset", {})
        )
        
        image_url = None
        if success and data:
            asset = data.get("asset", {})
            image_url = asset.get("url", "")
            self.log(f"Image uploaded: {image_url}", "INFO")
            
            # Verify the image is retrievable
            if image_url:
                try:
                    img_response = requests.get(f"{BASE_URL}{image_url}", timeout=10)
                    if img_response.status_code == 200:
                        self.log(f"Image retrievable at {image_url}", "INFO")
                    else:
                        self.warnings.append(f"Image not retrievable: HTTP {img_response.status_code}")
                except Exception as e:
                    self.warnings.append(f"Failed to retrieve image: {e}")
        
        return success, image_url

    def test_create_category(self, image_url=None):
        """Test POST /api/waste/admin/categories with desc_uk, desc_en, image_url"""
        if not self.admin_token:
            self.log("Skipping - no admin token", "WARN")
            return False
        
        test_key = f"test_cat_{int(time.time())}"
        payload = {
            "key": test_key,
            "name_uk": "Тестова категорія",
            "name_en": "Test Category",
            "desc_uk": "Це тестовий опис українською мовою для перевірки функціоналу.",
            "desc_en": "This is a test description in English to verify functionality.",
            "icon": "shield-alert",
            "active": True,
            "codes": ["18 01 03*"]  # One medical waste code
        }
        
        if image_url:
            payload["image_url"] = image_url
        
        success, data = self.test(
            "POST /api/waste/admin/categories (create test category)",
            "POST",
            "/waste/admin/categories",
            200,
            token=self.admin_token,
            data=payload,
            check_fn=lambda d: "success" in d and d.get("success") == True
        )
        
        if success and data:
            category = data.get("category", {})
            self.test_category_key = category.get("key", test_key)
            self.log(f"Test category created: {self.test_category_key}", "INFO")
            
            # Verify fields were saved
            if category.get("desc_uk") != payload["desc_uk"]:
                self.warnings.append("desc_uk not saved correctly")
            if category.get("desc_en") != payload["desc_en"]:
                self.warnings.append("desc_en not saved correctly")
            if image_url and category.get("image_url") != image_url:
                self.warnings.append("image_url not saved correctly")
        
        return success

    def test_update_category(self):
        """Test PUT /api/waste/admin/categories/{key} - update descriptions"""
        if not self.admin_token or not self.test_category_key:
            self.log("Skipping - no admin token or test category", "WARN")
            return False
        
        updated_payload = {
            "desc_uk": "Оновлений опис українською",
            "desc_en": "Updated description in English"
        }
        
        success, data = self.test(
            f"PUT /api/waste/admin/categories/{self.test_category_key}",
            "PUT",
            f"/waste/admin/categories/{self.test_category_key}",
            200,
            token=self.admin_token,
            data=updated_payload,
            check_fn=lambda d: "success" in d and d.get("success") == True
        )
        
        if success and data:
            category = data.get("category", {})
            if category.get("desc_uk") == updated_payload["desc_uk"]:
                self.log("desc_uk updated successfully", "INFO")
            else:
                self.warnings.append("desc_uk not updated correctly")
            
            if category.get("desc_en") == updated_payload["desc_en"]:
                self.log("desc_en updated successfully", "INFO")
            else:
                self.warnings.append("desc_en not updated correctly")
        
        return success

    def test_reorder_categories(self):
        """Test POST /api/waste/admin/categories/reorder"""
        if not self.admin_token:
            self.log("Skipping - no admin token", "WARN")
            return False
        
        # Get current categories
        _, data = self.test(
            "GET categories for reorder",
            "GET",
            "/waste/admin/categories",
            200,
            token=self.admin_token
        )
        
        if not data:
            self.log("Cannot test reorder - no categories data", "WARN")
            return False
        
        categories = data.get("categories", [])
        if len(categories) < 2:
            self.log("Cannot test reorder - need at least 2 categories", "WARN")
            return False
        
        # Reverse the order
        original_order = [c["key"] for c in categories]
        new_order = list(reversed(original_order))
        
        success, data = self.test(
            "POST /api/waste/admin/categories/reorder",
            "POST",
            "/waste/admin/categories/reorder",
            200,
            token=self.admin_token,
            data={"order": new_order},
            check_fn=lambda d: "success" in d and d.get("success") == True
        )
        
        if success:
            # Verify the order was persisted
            time.sleep(0.5)
            _, verify_data = self.test(
                "Verify reorder persisted",
                "GET",
                "/waste/admin/categories",
                200,
                token=self.admin_token
            )
            
            if verify_data:
                new_categories = verify_data.get("categories", [])
                new_keys = [c["key"] for c in new_categories]
                
                if new_keys == new_order:
                    self.log("Reorder persisted correctly", "INFO")
                else:
                    self.warnings.append("Reorder not persisted correctly")
                
                # Restore original order
                self.test(
                    "Restore original order",
                    "POST",
                    "/waste/admin/categories/reorder",
                    200,
                    token=self.admin_token,
                    data={"order": original_order}
                )
        
        return success

    def test_public_categories(self):
        """Test GET /api/waste/categories?accepted=true - public endpoint"""
        success, data = self.test(
            "GET /api/waste/categories?accepted=true (public)",
            "GET",
            "/waste/categories?accepted=true",
            200,
            check_fn=lambda d: "success" in d and "categories" in d
        )
        
        if success and data:
            categories = data.get("categories", [])
            self.log(f"Public endpoint returns {len(categories)} categories", "INFO")
            
            # Check if categories have desc_uk, desc_en, image_url
            if categories:
                first_cat = categories[0]
                has_desc_uk = "desc_uk" in first_cat
                has_desc_en = "desc_en" in first_cat
                has_image_url = "image_url" in first_cat
                
                if not (has_desc_uk and has_desc_en and has_image_url):
                    self.warnings.append("Public categories missing desc_uk, desc_en, or image_url fields")
                else:
                    self.log("Public categories have all required fields", "INFO")
        
        return success

    def test_delete_category(self):
        """Test DELETE /api/waste/admin/categories/{key}"""
        if not self.admin_token or not self.test_category_key:
            self.log("Skipping - no admin token or test category", "WARN")
            return False
        
        success, data = self.test(
            f"DELETE /api/waste/admin/categories/{self.test_category_key}",
            "DELETE",
            f"/waste/admin/categories/{self.test_category_key}",
            200,
            token=self.admin_token,
            check_fn=lambda d: "success" in d and d.get("success") == True
        )
        
        if success:
            self.log(f"Test category {self.test_category_key} deleted", "INFO")
        
        return success

    def run_all(self):
        """Run all catalog feature tests"""
        self.log("=" * 80, "INFO")
        self.log("ECO.NOVA - WASTE CATALOG FEATURES TEST", "INFO")
        self.log(f"Base URL: {BASE_URL}", "INFO")
        self.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        self.log("=" * 80, "INFO")
        
        # Phase 1: Authentication
        self.log("\n=== PHASE 1: AUTHENTICATION ===", "INFO")
        if not self.test_admin_login():
            self.log("Cannot proceed without admin token", "FAIL")
            return 1
        
        # Phase 2: Get admin categories
        self.log("\n=== PHASE 2: GET ADMIN CATEGORIES ===", "INFO")
        self.test_get_admin_categories()
        
        # Phase 3: Image upload
        self.log("\n=== PHASE 3: IMAGE UPLOAD ===", "INFO")
        upload_success, image_url = self.test_upload_image()
        
        # Phase 4: Create test category
        self.log("\n=== PHASE 4: CREATE TEST CATEGORY ===", "INFO")
        self.test_create_category(image_url if upload_success else None)
        
        # Phase 5: Update category
        self.log("\n=== PHASE 5: UPDATE CATEGORY ===", "INFO")
        self.test_update_category()
        
        # Phase 6: Reorder categories
        self.log("\n=== PHASE 6: REORDER CATEGORIES ===", "INFO")
        self.test_reorder_categories()
        
        # Phase 7: Public categories endpoint
        self.log("\n=== PHASE 7: PUBLIC CATEGORIES ===", "INFO")
        self.test_public_categories()
        
        # Phase 8: Cleanup - delete test category
        self.log("\n=== PHASE 8: CLEANUP ===", "INFO")
        self.test_delete_category()
        
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
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = CatalogFeaturesTester()
    return tester.run_all()

if __name__ == "__main__":
    sys.exit(main())
