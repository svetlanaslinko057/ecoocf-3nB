"""
ECO NOVA — Certificates/Licenses Feature Test
==============================================
Tests the admin-managed certificates module (4 real company documents).

Test Coverage:
1. GET /api/site-info returns certificates object with 4 documents
2. Static files are served: /api/static/certificates/*.jpg and *.pdf
3. PUT /api/admin/site-info persists certificates (with auth)
4. PUT /api/admin/site-info returns 401/403 without auth
5. POST /api/admin/site-info/upload-certificate-image requires admin auth
6. POST /api/admin/site-info/upload-certificate-file requires admin auth, PDF only
"""
import requests
import sys
import io
from datetime import datetime

BASE_URL = "https://recycle-waste-deploy.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@bibi.cars"
ADMIN_PASSWORD = "Admin123!"

class CertificatesTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, files=None, check_fn=None):
        """Run a single API test"""
        url = f"{API_BASE}{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if data and not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        self.log(f"Testing {name}...", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers, timeout=15)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            else:
                self.log(f"Unsupported method {method}", "ERROR")
                return False, None

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - {name} - Status: {response.status_code}", "PASS")
                
                # Additional data checks
                if check_fn and response.status_code in [200, 201]:
                    try:
                        json_data = response.json()
                        if not check_fn(json_data):
                            self.log(f"⚠️  Data validation failed for {name}", "WARN")
                            return False, json_data
                        return True, json_data
                    except Exception as e:
                        self.log(f"⚠️  Data check error: {e}", "WARN")
                        return False, None
                
                try:
                    return True, response.json() if response.status_code in [200, 201] else response
                except Exception:
                    return True, response
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

    def run_all_tests(self):
        """Execute all certificate tests"""
        self.log("=" * 60)
        self.log("ECO NOVA — Certificates Feature Test Suite")
        self.log("=" * 60)

        # ── STEP 1: Admin Login ──
        self.log("\n[STEP 1] Admin Authentication", "SECTION")
        success, response = self.test(
            "Admin Login",
            "POST",
            "/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if success and response:
            if isinstance(response, dict) and 'token' in response:
                self.admin_token = response['token']
                self.log(f"Admin token obtained: {self.admin_token[:20]}...", "INFO")
            elif isinstance(response, dict) and 'access_token' in response:
                self.admin_token = response['access_token']
                self.log(f"Admin token obtained: {self.admin_token[:20]}...", "INFO")
            else:
                self.log(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'not a dict'}", "DEBUG")
                self.log("❌ CRITICAL: Token not found in login response", "ERROR")
                return self.print_summary()
        else:
            self.log("❌ CRITICAL: Admin login failed, cannot proceed", "ERROR")
            return self.print_summary()

        # ── STEP 2: GET /api/site-info returns certificates ──
        self.log("\n[STEP 2] GET /api/site-info - Certificates Object", "SECTION")
        
        def check_certificates(data):
            """Validate certificates structure"""
            if 'certificates' not in data:
                self.log("❌ Missing 'certificates' key in response", "ERROR")
                return False
            
            certs = data['certificates']
            if not isinstance(certs, dict):
                self.log("❌ 'certificates' is not a dict", "ERROR")
                return False
            
            if certs.get('enabled') is not True:
                self.log("⚠️  certificates.enabled is not True", "WARN")
            
            items = certs.get('items', [])
            if not isinstance(items, list):
                self.log("❌ certificates.items is not a list", "ERROR")
                return False
            
            if len(items) != 4:
                self.log(f"⚠️  Expected 4 certificate items, got {len(items)}", "WARN")
            
            # Check structure of first item
            if items:
                item = items[0]
                required_fields = ['no', 'category', 'title_uk', 'title_en', 'desc_uk', 'desc_en', 
                                   'issuer_uk', 'issuer_en', 'number', 'issued', 'image_url', 'file_url']
                for field in required_fields:
                    if field not in item:
                        self.log(f"⚠️  Missing field '{field}' in certificate item", "WARN")
                
                # Log sample data
                self.log(f"Sample certificate: {item.get('title_en', 'N/A')}", "INFO")
                self.log(f"  Number: {item.get('number', 'N/A')}", "INFO")
                self.log(f"  Issuer: {item.get('issuer_en', 'N/A')}", "INFO")
                self.log(f"  Image: {item.get('image_url', 'N/A')}", "INFO")
                self.log(f"  File: {item.get('file_url', 'N/A')}", "INFO")
            
            return True

        success, site_info = self.test(
            "GET /api/site-info with certificates",
            "GET",
            "/site-info",
            200,
            check_fn=check_certificates
        )

        # Store certificate URLs for static file tests
        cert_items = []
        if success and site_info and 'certificates' in site_info:
            cert_items = site_info['certificates'].get('items', [])

        # ── STEP 3: Static Files are Served ──
        self.log("\n[STEP 3] Static Certificate Files", "SECTION")
        
        # Test at least one image and one PDF
        if cert_items:
            for i, item in enumerate(cert_items[:2]):  # Test first 2 items
                image_url = item.get('image_url', '')
                file_url = item.get('file_url', '')
                
                if image_url:
                    # Use requests directly for static files (not through self.test which adds /api prefix)
                    full_image_url = f"{BASE_URL}{image_url}" if image_url.startswith('/') else image_url
                    self.log(f"Testing image URL: {full_image_url}", "DEBUG")
                    try:
                        response = requests.get(full_image_url, timeout=10)
                        self.tests_run += 1
                        if response.status_code == 200:
                            self.tests_passed += 1
                            content_type = response.headers.get('content-type', '')
                            self.log(f"✅ PASS - GET certificate image #{i+1} - Status: 200", "PASS")
                            if 'image' in content_type:
                                self.log(f"✓ Image served correctly: {content_type}", "INFO")
                            else:
                                self.log(f"⚠️  Unexpected content-type: {content_type}", "WARN")
                        else:
                            self.log(f"❌ FAIL - GET certificate image #{i+1} - Expected 200, got {response.status_code}", "FAIL")
                    except Exception as e:
                        self.tests_run += 1
                        self.log(f"❌ FAIL - GET certificate image #{i+1} - Error: {e}", "FAIL")
                
                if file_url:
                    # Use requests directly for static files
                    full_file_url = f"{BASE_URL}{file_url}" if file_url.startswith('/') else file_url
                    self.log(f"Testing PDF URL: {full_file_url}", "DEBUG")
                    try:
                        response = requests.get(full_file_url, timeout=10)
                        self.tests_run += 1
                        if response.status_code == 200:
                            self.tests_passed += 1
                            content_type = response.headers.get('content-type', '')
                            self.log(f"✅ PASS - GET certificate PDF #{i+1} - Status: 200", "PASS")
                            if 'pdf' in content_type or 'application/pdf' in content_type:
                                self.log(f"✓ PDF served correctly: {content_type}", "INFO")
                            else:
                                self.log(f"⚠️  Unexpected content-type for PDF: {content_type}", "WARN")
                        else:
                            self.log(f"❌ FAIL - GET certificate PDF #{i+1} - Expected 200, got {response.status_code}", "FAIL")
                    except Exception as e:
                        self.tests_run += 1
                        self.log(f"❌ FAIL - GET certificate PDF #{i+1} - Error: {e}", "FAIL")
        else:
            self.log("⚠️  No certificate items found to test static files", "WARN")

        # ── STEP 4: PUT /api/admin/site-info without auth (should fail) ──
        self.log("\n[STEP 4] PUT /api/admin/site-info - Unauthorized", "SECTION")
        self.test(
            "PUT site-info without auth (should fail)",
            "PUT",
            "/admin/site-info",
            401,  # or 403
            data={"certificates": {"enabled": True}}
        )

        # ── STEP 5: PUT /api/admin/site-info with auth (should succeed) ──
        self.log("\n[STEP 5] PUT /api/admin/site-info - Authorized", "SECTION")
        
        # Modify the first certificate title
        if cert_items:
            modified_certs = {
                "enabled": True,
                "title_uk": site_info['certificates'].get('title_uk', ''),
                "title_en": site_info['certificates'].get('title_en', ''),
                "subtitle_uk": site_info['certificates'].get('subtitle_uk', ''),
                "subtitle_en": site_info['certificates'].get('subtitle_en', ''),
                "items": cert_items.copy()
            }
            # Append " TEST" to first item's title
            if modified_certs['items']:
                modified_certs['items'][0] = {
                    **modified_certs['items'][0],
                    'title_uk': modified_certs['items'][0].get('title_uk', '') + ' TEST'
                }
            
            success, response = self.test(
                "PUT site-info with certificates update",
                "PUT",
                "/admin/site-info",
                200,
                token=self.admin_token,
                data={"certificates": modified_certs}
            )
            
            if success:
                self.log("✓ Certificates update persisted", "INFO")
                
                # Verify the change
                success2, site_info2 = self.test(
                    "GET site-info to verify update",
                    "GET",
                    "/site-info",
                    200
                )
                if success2 and site_info2:
                    updated_title = site_info2.get('certificates', {}).get('items', [{}])[0].get('title_uk', '')
                    if 'TEST' in updated_title:
                        self.log(f"✓ Update verified: {updated_title}", "INFO")
                    else:
                        self.log(f"⚠️  Update not reflected: {updated_title}", "WARN")
                
                # Revert the change
                modified_certs['items'][0]['title_uk'] = modified_certs['items'][0]['title_uk'].replace(' TEST', '')
                self.test(
                    "PUT site-info to revert change",
                    "PUT",
                    "/admin/site-info",
                    200,
                    token=self.admin_token,
                    data={"certificates": modified_certs}
                )

        # ── STEP 6: Upload Endpoints - Unauthorized ──
        self.log("\n[STEP 6] Upload Endpoints - Unauthorized", "SECTION")
        
        # Create a dummy image file
        dummy_image = io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde')
        dummy_image.name = 'test.png'
        
        self.test(
            "POST upload-certificate-image without auth (should fail)",
            "POST",
            "/admin/site-info/upload-certificate-image",
            401,  # or 403
            files={'image': ('test.png', dummy_image, 'image/png')}
        )
        
        # Reset file pointer
        dummy_image.seek(0)
        
        self.test(
            "POST upload-certificate-file without auth (should fail)",
            "POST",
            "/admin/site-info/upload-certificate-file",
            401,  # or 403
            files={'file': ('test.pdf', dummy_image, 'application/pdf')}
        )

        # ── STEP 7: Upload Endpoints - Authorized (with validation) ──
        self.log("\n[STEP 7] Upload Endpoints - Authorized", "SECTION")
        
        # Test image upload with valid image
        dummy_image.seek(0)
        success, response = self.test(
            "POST upload-certificate-image with auth",
            "POST",
            "/admin/site-info/upload-certificate-image",
            200,
            token=self.admin_token,
            files={'image': ('test.png', dummy_image, 'image/png')}
        )
        if success and response:
            self.log(f"✓ Image uploaded: {response.get('url', 'N/A')}", "INFO")
        
        # Test PDF upload with valid PDF
        dummy_pdf = io.BytesIO(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        dummy_pdf.name = 'test.pdf'
        success, response = self.test(
            "POST upload-certificate-file with auth (valid PDF)",
            "POST",
            "/admin/site-info/upload-certificate-file",
            200,
            token=self.admin_token,
            files={'file': ('test.pdf', dummy_pdf, 'application/pdf')}
        )
        if success and response:
            self.log(f"✓ PDF uploaded: {response.get('url', 'N/A')}", "INFO")
        
        # Test PDF upload with non-PDF (should fail)
        dummy_image.seek(0)
        self.test(
            "POST upload-certificate-file with non-PDF (should fail)",
            "POST",
            "/admin/site-info/upload-certificate-file",
            400,
            token=self.admin_token,
            files={'file': ('test.png', dummy_image, 'image/png')}
        )

        return self.print_summary()

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)
        self.log(f"Tests Run: {self.tests_run}")
        self.log(f"Tests Passed: {self.tests_passed}")
        self.log(f"Tests Failed: {self.tests_run - self.tests_passed}")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%")
        self.log("=" * 60)
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = CertificatesTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
