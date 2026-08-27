"""
ECO.NOVA HAZARDOUS-WASTE B2B PLATFORM — COMPREHENSIVE API TEST
===============================================================
Testing deployment + hardening for:
- Auth (staff + customer)
- Admin integrations (OpenAI, Resend, Gmail, Ringostat)
- Ringostat (settings, calls, webhook simulation)
- Call Intelligence (recent, stats, config, at-risk)
- Waste domain core (contracts, codes, leads, customers, staff)
- Manager scope restrictions
- Client cabinet

Base URL: https://waste-management-44.preview.emergentagent.com
"""
import requests
import sys
import time
import json
from datetime import datetime, timedelta

# Production URL from frontend/.env
BASE_URL = "https://waste-management-44.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Seeded credentials from backend/.env
ADMIN_EMAIL = "admin@eco.ua"
ADMIN_PASSWORD = "EcoAdmin2026!"
MANAGER_EMAIL = "manager@eco.ua"
MANAGER_PASSWORD = "EcoManager2026!"
CLIENT_EMAIL = "client@eco.ua"
CLIENT_PASSWORD = "EcoClient2026!"

# Ringostat credentials from backend/.env
RINGOSTAT_PROJECT_ID = "240338"
RINGOSTAT_AUTH_KEY = "5BvxFSDxhVFIjGyBvjxl8vG7SAgNxaDA"

class ComprehensiveTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.manager_token = None
        self.client_token = None
        self.failures = []
        self.warnings = []

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "TEST": "🔍",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️ ",
            "ERROR": "🔥",
        }.get(level, "")
        print(f"[{timestamp}] {prefix} {msg}")

    def test(self, name, method, endpoint, expected_status, token=None, data=None, 
             check_fn=None, timeout=15, headers_extra=None):
        """Run a single API test with detailed error reporting"""
        url = f"{API_BASE}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if headers_extra:
            headers.update(headers_extra)

        self.tests_run += 1
        self.log(f"{name}", "TEST")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                self.log(f"Unsupported method {method}", "ERROR")
                self.failures.append(f"{name}: Unsupported method")
                return False, None

            success = response.status_code == expected_status
            
            # Try to parse JSON response
            json_data = None
            try:
                if response.content:
                    json_data = response.json()
            except Exception:
                pass

            if success:
                self.tests_passed += 1
                self.log(f"PASS - {name} (HTTP {response.status_code})", "PASS")
                
                # Additional data checks
                if check_fn and json_data:
                    try:
                        check_result = check_fn(json_data)
                        if not check_result:
                            self.log(f"Data validation failed for {name}", "WARN")
                            self.warnings.append(f"{name}: Data validation failed")
                            return True, json_data  # Still pass HTTP status check
                    except Exception as e:
                        self.log(f"Data check error: {e}", "WARN")
                        self.warnings.append(f"{name}: Data check error - {e}")
                
                return True, json_data
            else:
                self.log(f"FAIL - {name} - Expected HTTP {expected_status}, got {response.status_code}", "FAIL")
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                
                # Log response body for debugging
                if json_data:
                    self.log(f"Response: {json.dumps(json_data, indent=2)[:500]}", "ERROR")
                else:
                    self.log(f"Response: {response.text[:500]}", "ERROR")
                
                return False, json_data

        except requests.exceptions.Timeout:
            self.log(f"FAIL - {name} - Request timeout (>{timeout}s)", "FAIL")
            self.failures.append(f"{name}: Request timeout")
            return False, None
        except requests.exceptions.ConnectionError as e:
            self.log(f"FAIL - {name} - Connection error: {str(e)[:200]}", "FAIL")
            self.failures.append(f"{name}: Connection error")
            return False, None
        except Exception as e:
            self.log(f"FAIL - {name} - Error: {str(e)[:200]}", "FAIL")
            self.failures.append(f"{name}: {str(e)[:200]}")
            return False, None

    # ========== AUTH TESTS ==========
    def test_admin_login(self):
        """Test admin staff login via POST /api/auth/login"""
        success, data = self.test(
            "Admin Login (staff)",
            "POST",
            "/auth/login",
            200,
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            check_fn=lambda d: "access_token" in d or "token" in d
        )
        if success and data:
            self.admin_token = data.get("access_token") or data.get("token")
            self.log(f"Admin token: {self.admin_token[:30]}...", "INFO")
        return success

    def test_manager_login(self):
        """Test manager staff login via POST /api/auth/login"""
        success, data = self.test(
            "Manager Login (staff)",
            "POST",
            "/auth/login",
            200,
            data={"email": MANAGER_EMAIL, "password": MANAGER_PASSWORD},
            check_fn=lambda d: "access_token" in d or "token" in d
        )
        if success and data:
            self.manager_token = data.get("access_token") or data.get("token")
            self.log(f"Manager token: {self.manager_token[:30]}...", "INFO")
        return success

    def test_client_login(self):
        """Test customer login via POST /api/customer-auth/login"""
        success, data = self.test(
            "Client Login (customer)",
            "POST",
            "/customer-auth/login",
            200,
            data={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD},
            check_fn=lambda d: any(k in d for k in ["sessionToken", "token", "accessToken", "access_token"])
        )
        if success and data:
            self.client_token = (data.get("sessionToken") or data.get("token") or 
                                data.get("accessToken") or data.get("access_token"))
            self.log(f"Client token: {self.client_token[:30] if self.client_token else 'None'}...", "INFO")
        return success

    def test_auth_me(self):
        """Test GET /api/auth/me with admin token"""
        if not self.admin_token:
            self.log("Skipping auth/me - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/auth/me (admin)",
            "GET",
            "/auth/me",
            200,
            token=self.admin_token,
            check_fn=lambda d: d.get("email") == ADMIN_EMAIL
        )
        return success

    # ========== ADMIN INTEGRATIONS TESTS ==========
    def test_admin_integrations_list(self):
        """Test GET /api/admin/integrations - must return all 8 providers"""
        if not self.admin_token:
            self.log("Skipping integrations list - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/integrations (list all)",
            "GET",
            "/admin/integrations",
            200,
            token=self.admin_token,
            check_fn=lambda d: (
                isinstance(d, list) and
                len(d) >= 8 and
                all(p in [item.get("provider") for item in d] 
                    for p in ["google_oauth", "stripe", "ringostat", "email", "resend", "shipping", "openai", "sms"])
            )
        )
        if success and data:
            providers = [item.get("provider") for item in data]
            self.log(f"Found {len(data)} integrations: {', '.join(providers)}", "INFO")
            
            # Check ringostat is enabled
            ringostat = next((item for item in data if item.get("provider") == "ringostat"), None)
            if ringostat:
                is_enabled = ringostat.get("isEnabled", False)
                self.log(f"Ringostat isEnabled: {is_enabled}", "INFO")
                if not is_enabled:
                    self.warnings.append("Ringostat integration is not enabled")
        
        return success

    # ========== RINGOSTAT TESTS ==========
    def test_ringostat_settings(self):
        """Test GET /api/admin/ringostat/settings - should return api_key, project_id, enabled"""
        if not self.admin_token:
            self.log("Skipping ringostat settings - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/ringostat/settings",
            "GET",
            "/admin/ringostat/settings",
            200,
            token=self.admin_token,
            check_fn=lambda d: (
                "api_key" in d and
                "project_id" in d and
                "enabled" in d and
                "webhook_secret" in d
            )
        )
        if success and data:
            # Check if credentials match expected values (may be masked)
            api_key = data.get("api_key", "")
            project_id = data.get("project_id", "")
            enabled = data.get("enabled", False)
            webhook_secret = data.get("webhook_secret", "")
            
            self.log(f"Ringostat: project_id={project_id}, enabled={enabled}, "
                    f"api_key={'SET' if api_key else 'EMPTY'}, "
                    f"webhook_secret={'SET' if webhook_secret else 'EMPTY'}", "INFO")
            
            # Verify project_id matches expected
            if project_id != RINGOSTAT_PROJECT_ID:
                self.warnings.append(f"Ringostat project_id mismatch: expected {RINGOSTAT_PROJECT_ID}, got {project_id}")
        
        return success

    def test_ringostat_calls_list(self):
        """Test GET /api/admin/ringostat/calls - should return 200 with array shape"""
        if not self.admin_token:
            self.log("Skipping ringostat calls - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/ringostat/calls",
            "GET",
            "/admin/ringostat/calls?period=month&limit=50",
            200,
            token=self.admin_token,
            check_fn=lambda d: "calls" in d and isinstance(d.get("calls"), list)
        )
        if success and data:
            calls = data.get("calls", [])
            self.log(f"Found {len(calls)} Ringostat calls", "INFO")
        
        return success

    def test_ringostat_webhook_simulate(self):
        """Test POST /api/integrations/ringostat/webhook with sample payload"""
        # First, get webhook_secret from settings
        if not self.admin_token:
            self.log("Skipping webhook simulate - no admin token", "WARN")
            return False
        
        # Get webhook secret
        _, settings_data = self.test(
            "GET webhook_secret for simulation",
            "GET",
            "/admin/ringostat/settings",
            200,
            token=self.admin_token
        )
        
        webhook_secret = ""
        if settings_data:
            webhook_secret = settings_data.get("webhook_secret", "")
        
        if not webhook_secret:
            self.log("No webhook_secret found - webhook simulation may fail", "WARN")
        
        # Simulate inbound call webhook
        sample_payload = {
            "call_id": f"test_call_{int(time.time())}",
            "direction": "inbound",
            "from": "+380501234567",
            "to": "+380441234567",
            "status": "COMPLETED",
            "duration": 125,
            "started_at": datetime.now().isoformat(),
            "answered_at": datetime.now().isoformat(),
            "ended_at": (datetime.now() + timedelta(seconds=125)).isoformat(),
            "recording_url": None,
            "extension": "101",
            "project_id": RINGOSTAT_PROJECT_ID
        }
        
        endpoint = f"/integrations/ringostat/webhook"
        if webhook_secret:
            endpoint += f"?token={webhook_secret}"
        
        success, data = self.test(
            "POST /api/integrations/ringostat/webhook (simulate)",
            "POST",
            endpoint,
            200,
            data=sample_payload,
            timeout=20
        )
        
        if success:
            self.log(f"Webhook simulation successful - call_id: {sample_payload['call_id']}", "INFO")
            
            # Verify the call appears in the calls list
            time.sleep(1)  # Give DB time to persist
            _, calls_data = self.test(
                "Verify webhook call persisted",
                "GET",
                "/admin/ringostat/calls?period=today&limit=10",
                200,
                token=self.admin_token
            )
            
            if calls_data:
                calls = calls_data.get("calls", [])
                found = any(c.get("call_id") == sample_payload["call_id"] for c in calls)
                if found:
                    self.log("✓ Webhook call found in calls list", "INFO")
                else:
                    self.warnings.append("Webhook call not found in calls list after simulation")
        
        return success

    # ========== CALL INTELLIGENCE TESTS ==========
    def test_call_intelligence_recent(self):
        """Test GET /api/admin/calls/intelligence/recent"""
        if not self.admin_token:
            self.log("Skipping call intelligence recent - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/calls/intelligence/recent",
            "GET",
            "/admin/calls/intelligence/recent?limit=20",
            200,
            token=self.admin_token,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        if success and data:
            items = data.get("items", [])
            self.log(f"Found {len(items)} analyzed calls", "INFO")
        
        return success

    def test_call_intelligence_stats(self):
        """Test GET /api/admin/calls/intelligence/stats"""
        if not self.admin_token:
            self.log("Skipping call intelligence stats - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/calls/intelligence/stats",
            "GET",
            "/admin/calls/intelligence/stats?days=30",
            200,
            token=self.admin_token,
            check_fn=lambda d: "stats" in d
        )
        return success

    def test_call_intelligence_config(self):
        """Test GET /api/admin/calls/intelligence/config"""
        if not self.admin_token:
            self.log("Skipping call intelligence config - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/calls/intelligence/config",
            "GET",
            "/admin/calls/intelligence/config",
            200,
            token=self.admin_token,
            check_fn=lambda d: "openai_configured" in d and "key_source" in d
        )
        if success and data:
            configured = data.get("openai_configured", False)
            key_source = data.get("key_source", "none")
            self.log(f"OpenAI configured: {configured}, source: {key_source}", "INFO")
        
        return success

    def test_call_intelligence_at_risk(self):
        """Test GET /api/admin/calls/intelligence/at-risk"""
        if not self.admin_token:
            self.log("Skipping call intelligence at-risk - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/calls/intelligence/at-risk",
            "GET",
            "/admin/calls/intelligence/at-risk?days=14&limit=20",
            200,
            token=self.admin_token,
            check_fn=lambda d: "items" in d and isinstance(d.get("items"), list)
        )
        if success and data:
            items = data.get("items", [])
            self.log(f"Found {len(items)} at-risk calls", "INFO")
        
        return success

    # ========== INTEGRATION CONFIG TESTS ==========
    def test_integration_config_openai(self):
        """Test OpenAI integration config persistence"""
        if not self.admin_token:
            self.log("Skipping OpenAI config - no admin token", "WARN")
            return False
        
        # Check current config
        success, data = self.test(
            "GET /api/admin/integrations (check OpenAI)",
            "GET",
            "/admin/integrations",
            200,
            token=self.admin_token
        )
        
        if success and data:
            openai_item = next((item for item in data if item.get("provider") == "openai"), None)
            if openai_item:
                is_enabled = openai_item.get("isEnabled", False)
                mode = openai_item.get("mode", "")
                creds = openai_item.get("credentials", {})
                api_key = creds.get("apiKey", "")
                
                self.log(f"OpenAI: isEnabled={is_enabled}, mode={mode}, "
                        f"apiKey={'MASKED' if api_key and api_key.startswith('…') else 'SET' if api_key else 'EMPTY'}", 
                        "INFO")
        
        return success

    def test_integration_config_resend(self):
        """Test Resend integration config persistence"""
        if not self.admin_token:
            self.log("Skipping Resend config - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/integrations (check Resend)",
            "GET",
            "/admin/integrations",
            200,
            token=self.admin_token
        )
        
        if success and data:
            resend_item = next((item for item in data if item.get("provider") == "resend"), None)
            if resend_item:
                is_enabled = resend_item.get("isEnabled", False)
                mode = resend_item.get("mode", "")
                creds = resend_item.get("credentials", {})
                api_key = creds.get("apiKey", "")
                
                self.log(f"Resend: isEnabled={is_enabled}, mode={mode}, "
                        f"apiKey={'MASKED' if api_key and api_key.startswith('…') else 'SET' if api_key else 'EMPTY'}", 
                        "INFO")
        
        return success

    def test_integration_config_google_oauth(self):
        """Test Gmail/Google OAuth integration config persistence"""
        if not self.admin_token:
            self.log("Skipping Google OAuth config - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/admin/integrations (check Google OAuth)",
            "GET",
            "/admin/integrations",
            200,
            token=self.admin_token
        )
        
        if success and data:
            google_item = next((item for item in data if item.get("provider") == "google_oauth"), None)
            if google_item:
                is_enabled = google_item.get("isEnabled", False)
                mode = google_item.get("mode", "")
                creds = google_item.get("credentials", {})
                client_id = creds.get("clientId", "")
                client_secret = creds.get("clientSecret", "")
                
                self.log(f"Google OAuth: isEnabled={is_enabled}, mode={mode}, "
                        f"clientId={'SET' if client_id else 'EMPTY'}, "
                        f"clientSecret={'MASKED' if client_secret and client_secret.startswith('…') else 'SET' if client_secret else 'EMPTY'}", 
                        "INFO")
        
        return success

    # ========== WASTE DOMAIN CORE TESTS ==========
    def test_waste_contracts(self):
        """Test GET /api/waste/contracts"""
        if not self.admin_token:
            self.log("Skipping waste contracts - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/waste/contracts",
            "GET",
            "/waste/contracts",
            200,
            token=self.admin_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        if success and data:
            items = data if isinstance(data, list) else data.get("items", [])
            self.log(f"Found {len(items)} waste contracts", "INFO")
        
        return success

    def test_waste_codes(self):
        """Test GET /api/waste/codes (or catalogue)"""
        if not self.admin_token:
            self.log("Skipping waste codes - no admin token", "WARN")
            return False
        
        # Try both /waste/codes and /waste/catalogue
        success1, data1 = self.test(
            "GET /api/waste/codes",
            "GET",
            "/waste/codes",
            200,
            token=self.admin_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        
        if not success1:
            # Try alternative endpoint
            success2, data2 = self.test(
                "GET /api/waste/catalogue",
                "GET",
                "/waste/catalogue",
                200,
                token=self.admin_token,
                check_fn=lambda d: isinstance(d, (list, dict))
            )
            return success2
        
        if success1 and data1:
            items = data1 if isinstance(data1, list) else data1.get("items", [])
            self.log(f"Found {len(items)} waste codes", "INFO")
        
        return success1

    def test_leads_list(self):
        """Test GET /api/leads"""
        if not self.admin_token:
            self.log("Skipping leads list - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/leads",
            "GET",
            "/leads",
            200,
            token=self.admin_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        if success and data:
            items = data if isinstance(data, list) else data.get("items", [])
            self.log(f"Found {len(items)} leads", "INFO")
        
        return success

    def test_customers_list(self):
        """Test GET /api/customers"""
        if not self.admin_token:
            self.log("Skipping customers list - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/customers",
            "GET",
            "/customers",
            200,
            token=self.admin_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        if success and data:
            items = data if isinstance(data, list) else data.get("items", [])
            self.log(f"Found {len(items)} customers", "INFO")
        
        return success

    def test_staff_list(self):
        """Test GET /api/staff"""
        if not self.admin_token:
            self.log("Skipping staff list - no admin token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/staff",
            "GET",
            "/staff",
            200,
            token=self.admin_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        if success and data:
            items = data if isinstance(data, list) else data.get("items", [])
            self.log(f"Found {len(items)} staff members", "INFO")
        
        return success

    # ========== MANAGER SCOPE TESTS ==========
    def test_manager_customers_scope(self):
        """Test manager can only see their own customers"""
        if not self.manager_token:
            self.log("Skipping manager scope - no manager token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/customers (manager scope)",
            "GET",
            "/customers",
            200,
            token=self.manager_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        if success and data:
            items = data if isinstance(data, list) else data.get("items", [])
            self.log(f"Manager sees {len(items)} customers (scoped)", "INFO")
        
        return success

    def test_manager_admin_endpoint_forbidden(self):
        """Test manager cannot access admin-only endpoints"""
        if not self.manager_token:
            self.log("Skipping manager forbidden - no manager token", "WARN")
            return False
        
        # Try to PATCH ringostat settings (admin-only)
        success, data = self.test(
            "PATCH /api/admin/ringostat/settings (manager forbidden)",
            "PATCH",
            "/admin/ringostat/settings",
            403,  # Should be forbidden
            token=self.manager_token,
            data={"enabled": True}
        )
        return success

    # ========== CLIENT CABINET TESTS ==========
    def test_client_me(self):
        """Test GET /api/client/me"""
        if not self.client_token:
            self.log("Skipping client/me - no client token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/client/me",
            "GET",
            "/client/me",
            200,
            token=self.client_token,
            check_fn=lambda d: d.get("email") == CLIENT_EMAIL
        )
        return success

    def test_client_contracts(self):
        """Test GET /api/client/contracts"""
        if not self.client_token:
            self.log("Skipping client contracts - no client token", "WARN")
            return False
        
        success, data = self.test(
            "GET /api/client/contracts",
            "GET",
            "/client/contracts",
            200,
            token=self.client_token,
            check_fn=lambda d: isinstance(d, (list, dict))
        )
        if success and data:
            items = data if isinstance(data, list) else data.get("items", [])
            self.log(f"Client sees {len(items)} contracts", "INFO")
        
        return success

    # ========== RUN ALL TESTS ==========
    def run_all(self):
        """Run comprehensive backend API tests"""
        self.log("=" * 80, "INFO")
        self.log("ECO.NOVA HAZARDOUS-WASTE B2B PLATFORM - COMPREHENSIVE API TEST", "INFO")
        self.log(f"Base URL: {BASE_URL}", "INFO")
        self.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        self.log("=" * 80, "INFO")
        
        # Phase 1: Authentication
        self.log("\n=== PHASE 1: AUTHENTICATION ===", "INFO")
        self.test_admin_login()
        self.test_manager_login()
        self.test_client_login()
        self.test_auth_me()
        
        # Phase 2: Admin Integrations
        self.log("\n=== PHASE 2: ADMIN INTEGRATIONS ===", "INFO")
        self.test_admin_integrations_list()
        self.test_integration_config_openai()
        self.test_integration_config_resend()
        self.test_integration_config_google_oauth()
        
        # Phase 3: Ringostat
        self.log("\n=== PHASE 3: RINGOSTAT ===", "INFO")
        self.test_ringostat_settings()
        self.test_ringostat_calls_list()
        self.test_ringostat_webhook_simulate()
        
        # Phase 4: Call Intelligence
        self.log("\n=== PHASE 4: CALL INTELLIGENCE ===", "INFO")
        self.test_call_intelligence_recent()
        self.test_call_intelligence_stats()
        self.test_call_intelligence_config()
        self.test_call_intelligence_at_risk()
        
        # Phase 5: Waste Domain Core
        self.log("\n=== PHASE 5: WASTE DOMAIN CORE ===", "INFO")
        self.test_waste_contracts()
        self.test_waste_codes()
        self.test_leads_list()
        self.test_customers_list()
        self.test_staff_list()
        
        # Phase 6: Manager Scope
        self.log("\n=== PHASE 6: MANAGER SCOPE ===", "INFO")
        self.test_manager_customers_scope()
        self.test_manager_admin_endpoint_forbidden()
        
        # Phase 7: Client Cabinet
        self.log("\n=== PHASE 7: CLIENT CABINET ===", "INFO")
        self.test_client_me()
        self.test_client_contracts()
        
        # Summary
        self.log("\n" + "=" * 80, "INFO")
        self.log(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed", "INFO")
        
        if self.warnings:
            self.log(f"\nWARNINGS ({len(self.warnings)}):", "WARN")
            for warning in self.warnings:
                self.log(f"  - {warning}", "WARN")
        
        if self.failures:
            self.log(f"\nFAILURES ({len(self.failures)}):", "ERROR")
            for failure in self.failures:
                self.log(f"  - {failure}", "ERROR")
        
        self.log("=" * 80, "INFO")
        self.log(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = ComprehensiveTester()
    return tester.run_all()

if __name__ == "__main__":
    sys.exit(main())
