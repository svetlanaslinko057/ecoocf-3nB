"""
Call Intelligence API Test Suite
=================================
Tests the on-demand transcription + AI analysis pipeline for Ringostat calls.

Test Coverage:
1. GET /api/admin/calls/intelligence/config - verify OpenAI configured
2. GET /api/admin/calls/intelligence/stats?days=30 - verify stats endpoint
3. GET /api/admin/calls/intelligence/recent - verify recent calls list
4. POST /api/admin/calls/{call_id}/intelligence/process - on-demand processing
5. GET /api/admin/calls/{call_id}/intelligence - retrieve processed data
6. Idempotency: cached vs force re-run
7. RBAC: unauthenticated access returns 401/403
"""
import requests
import sys
import time
from datetime import datetime

# Production URL from frontend/.env
BASE_URL = "https://environmental-utils.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Seeded credentials from backend/.env
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "EcoAdmin2026!"

# Demo call IDs (seeded in ringostat_calls)
DEMO_CALL_ANALYZED = "ci_demo_jfk_001"  # Already analyzed
DEMO_CALL_FRESH = "ci_demo_jfk_002"     # NOT analyzed yet, for fresh test

class CallIntelligenceTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.failures = []

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, check_fn=None, timeout=15):
        """Run a single API test"""
        url = f"{API_BASE}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        self.log(f"Testing: {name}", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
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
            self.failures.append(f"{name}: Timeout")
            return False, None
        except Exception as e:
            self.log(f"❌ FAIL - {name} - Error: {str(e)}", "FAIL")
            self.failures.append(f"{name}: {str(e)}")
            return False, None

    def test_login(self):
        """Test admin login"""
        self.log("=== AUTHENTICATION ===", "SECTION")
        success, response = self.test(
            "Admin Login",
            "POST",
            "/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if success and response and 'access_token' in response:
            self.admin_token = response['access_token']
            self.log(f"Admin token obtained: {self.admin_token[:20]}...", "INFO")
            return True
        else:
            self.log("Failed to obtain admin token", "ERROR")
            return False

    def test_config(self):
        """Test GET /api/admin/calls/intelligence/config"""
        self.log("=== CONFIG ENDPOINT ===", "SECTION")
        success, response = self.test(
            "Get Call Intelligence Config",
            "GET",
            "/admin/calls/intelligence/config",
            200,
            token=self.admin_token,
            check_fn=lambda r: (
                r.get('success') == True and
                r.get('openai_configured') == True and
                'transcribe_model' in r and
                'analyze_model' in r and
                'supported_languages' in r and
                r.get('auto_process') == False
            )
        )
        if success and response:
            self.log(f"  - OpenAI configured: {response.get('openai_configured')}", "INFO")
            self.log(f"  - Transcribe model: {response.get('transcribe_model')}", "INFO")
            self.log(f"  - Analyze model: {response.get('analyze_model')}", "INFO")
            self.log(f"  - Auto process: {response.get('auto_process')}", "INFO")
        return success

    def test_stats(self):
        """Test GET /api/admin/calls/intelligence/stats?days=30"""
        self.log("=== STATS ENDPOINT ===", "SECTION")
        success, response = self.test(
            "Get Call Intelligence Stats",
            "GET",
            "/admin/calls/intelligence/stats?days=30",
            200,
            token=self.admin_token,
            check_fn=lambda r: (
                r.get('success') == True and
                'stats' in r
            )
        )
        if success and response:
            stats = response.get('stats', {})
            self.log(f"  - Total calls with CI: {stats.get('total_calls_with_ci', 0)}", "INFO")
            self.log(f"  - Positive: {stats.get('positive', 0)}", "INFO")
            self.log(f"  - Negative: {stats.get('negative', 0)}", "INFO")
            self.log(f"  - High intent: {stats.get('high_intent', 0)}", "INFO")
        return success

    def test_recent(self):
        """Test GET /api/admin/calls/intelligence/recent"""
        self.log("=== RECENT CALLS ENDPOINT ===", "SECTION")
        success, response = self.test(
            "Get Recent Analyzed Calls",
            "GET",
            "/admin/calls/intelligence/recent",
            200,
            token=self.admin_token,
            check_fn=lambda r: (
                r.get('success') == True and
                'items' in r and
                isinstance(r.get('items'), list)
            )
        )
        if success and response:
            items = response.get('items', [])
            self.log(f"  - Recent analyzed calls: {len(items)}", "INFO")
        return success

    def test_process_call(self, call_id, force=False, expect_jfk=False):
        """Test POST /api/admin/calls/{call_id}/intelligence/process"""
        self.log(f"=== PROCESS CALL: {call_id} (force={force}) ===", "SECTION")
        
        # This may take 10-60s for transcription + analysis
        success, response = self.test(
            f"Process Call {call_id}",
            "POST",
            f"/admin/calls/{call_id}/intelligence/process",
            200,
            token=self.admin_token,
            data={"force": force},
            timeout=90,  # Allow up to 90s for Whisper + gpt-4o
            check_fn=lambda r: (
                r.get('success') == True and
                'transcript' in r and
                'intelligence' in r
            )
        )
        
        if success and response:
            transcript = response.get('transcript', {})
            intelligence = response.get('intelligence', {})
            
            self.log(f"  - Transcript full_text length: {len(transcript.get('full_text', ''))}", "INFO")
            self.log(f"  - Transcript language: {transcript.get('language')}", "INFO")
            self.log(f"  - Intelligence summary: {intelligence.get('summary', '')[:100]}...", "INFO")
            self.log(f"  - Sentiment: {intelligence.get('sentiment')}", "INFO")
            self.log(f"  - Purchase intent: {intelligence.get('purchase_intent')}", "INFO")
            self.log(f"  - Model: {intelligence.get('model')}", "INFO")
            
            # If expecting JFK quote, verify it's in the transcript
            if expect_jfk:
                full_text = transcript.get('full_text', '').lower()
                if 'ask not what your country can do for you' in full_text or 'ask not what' in full_text:
                    self.log("  ✅ JFK quote found in transcript!", "INFO")
                else:
                    self.log("  ⚠️  JFK quote NOT found in transcript", "WARN")
                    self.failures.append(f"Process Call {call_id}: JFK quote not in transcript")
                    return False, response
            
            # Check that intelligence has required fields
            if not intelligence.get('summary'):
                self.log("  ⚠️  Intelligence summary is empty", "WARN")
                self.failures.append(f"Process Call {call_id}: Empty summary")
                return False, response
                
        return success, response

    def test_get_intelligence(self, call_id, expect_ready=True):
        """Test GET /api/admin/calls/{call_id}/intelligence"""
        self.log(f"=== GET INTELLIGENCE: {call_id} ===", "SECTION")
        success, response = self.test(
            f"Get Intelligence for {call_id}",
            "GET",
            f"/admin/calls/{call_id}/intelligence",
            200,
            token=self.admin_token,
            check_fn=lambda r: (
                'call_id' in r and
                'status' in r and
                (r.get('status') == 'ready' if expect_ready else True)
            )
        )
        
        if success and response:
            self.log(f"  - Status: {response.get('status')}", "INFO")
            self.log(f"  - Recording available: {response.get('recording_available')}", "INFO")
            if response.get('intelligence'):
                intel = response.get('intelligence', {})
                self.log(f"  - Summary: {intel.get('summary', '')[:100]}...", "INFO")
                self.log(f"  - Sentiment: {intel.get('sentiment')}", "INFO")
        
        return success, response

    def test_rbac(self):
        """Test RBAC: unauthenticated requests should fail"""
        self.log("=== RBAC: UNAUTHENTICATED ACCESS ===", "SECTION")
        
        # Test config without token
        success, _ = self.test(
            "Config without auth (should fail)",
            "GET",
            "/admin/calls/intelligence/config",
            401,  # Expect 401 Unauthorized
            token=None
        )
        
        return success

    def run_all_tests(self):
        """Run all Call Intelligence tests"""
        self.log("=" * 60, "HEADER")
        self.log("CALL INTELLIGENCE API TEST SUITE", "HEADER")
        self.log("=" * 60, "HEADER")
        
        # 1. Login
        if not self.test_login():
            self.log("Login failed, cannot continue", "ERROR")
            return False
        
        # 2. Config
        self.test_config()
        
        # 3. Stats
        self.test_stats()
        
        # 4. Recent
        self.test_recent()
        
        # 5. RBAC
        self.test_rbac()
        
        # 6. Process fresh call (ci_demo_jfk_002)
        self.log("", "")
        self.log("Testing on-demand processing with fresh call...", "INFO")
        success, process_response = self.test_process_call(
            DEMO_CALL_FRESH, 
            force=False, 
            expect_jfk=True
        )
        
        if success:
            # 7. Get intelligence after processing
            time.sleep(2)  # Brief pause
            self.test_get_intelligence(DEMO_CALL_FRESH, expect_ready=True)
            
            # 8. Test idempotency (cached result)
            self.log("", "")
            self.log("Testing idempotency (should return cached)...", "INFO")
            start_time = time.time()
            success2, cached_response = self.test_process_call(
                DEMO_CALL_FRESH,
                force=False,
                expect_jfk=True
            )
            elapsed = time.time() - start_time
            
            if success2 and cached_response:
                if cached_response.get('cached'):
                    self.log(f"  ✅ Cached result returned in {elapsed:.2f}s", "INFO")
                else:
                    self.log(f"  ⚠️  Expected cached result but got fresh processing", "WARN")
            
            # 9. Test force re-run
            self.log("", "")
            self.log("Testing force re-run...", "INFO")
            self.test_process_call(DEMO_CALL_FRESH, force=True, expect_jfk=True)
        
        # Print summary
        self.log("", "")
        self.log("=" * 60, "HEADER")
        self.log("TEST SUMMARY", "HEADER")
        self.log("=" * 60, "HEADER")
        self.log(f"Tests run: {self.tests_run}", "INFO")
        self.log(f"Tests passed: {self.tests_passed}", "INFO")
        self.log(f"Tests failed: {self.tests_run - self.tests_passed}", "INFO")
        
        if self.failures:
            self.log("", "")
            self.log("FAILURES:", "ERROR")
            for failure in self.failures:
                self.log(f"  - {failure}", "ERROR")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"Success rate: {success_rate:.1f}%", "INFO")
        
        return self.tests_passed == self.tests_run

def main():
    tester = CallIntelligenceTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
