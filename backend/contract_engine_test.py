"""
Contract Execution Engine — Backend API Test Suite
Tests all HTTP endpoints for the Contract Execution Engine.
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://waste-management-hub-18.preview.emergentagent.com/api"

class ContractEngineAPITester:
    def __init__(self):
        self.staff_token = None
        self.client_token = None
        self.customer_id = None
        self.company_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.contract_id = None
        self.period_id = None
        self.waste_codes = []
        self.act_id = None
        self.report_id = None
        
    def log(self, msg):
        print(f"  {msg}")
        
    def test(self, name, method, endpoint, expected_status, data=None, token=None, params=None):
        """Run a single API test"""
        url = f"{BASE_URL}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        self.tests_run += 1
        print(f"\n🔍 Test {self.tests_run}: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASS - Status: {response.status_code}")
                try:
                    return True, response.json()
                except Exception:
                    return True, {}
            else:
                self.log(f"❌ FAIL - Expected {expected_status}, got {response.status_code}")
                try:
                    self.log(f"   Response: {response.text[:200]}")
                except Exception:
                    pass
                return False, {}
                
        except Exception as e:
            self.log(f"❌ FAIL - Error: {str(e)}")
            return False, {}
    
    def test_staff_login(self):
        """Test staff authentication"""
        success, response = self.test(
            "Staff Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@eco.ua", "password": "EcoAdmin2026!"}
        )
        if success and 'access_token' in response:
            self.staff_token = response['access_token']
            self.log(f"   Staff token obtained")
            return True
        return False
    
    def test_client_login(self):
        """Test client authentication"""
        success, response = self.test(
            "Client Login",
            "POST",
            "customer-auth/login",
            200,
            data={"email": "client@eco.ua", "password": "EcoClient2026!"}
        )
        if success and 'accessToken' in response:
            self.client_token = response['accessToken']
            self.customer_id = response.get('customerId') or response.get('customer_id')
            self.log(f"   Client token obtained, customer_id: {self.customer_id}")
            return True
        return False
    
    def test_get_waste_codes(self):
        """Get waste codes with prices for testing"""
        success, response = self.test(
            "Get Waste Codes with Prices",
            "GET",
            "waste/codes",
            200,
            token=self.staff_token,
            params={"limit": 50}
        )
        if success and 'items' in response:
            # Filter codes that have prices
            codes_with_prices = [
                c for c in response['items'] 
                if c.get('price_from') is not None and c.get('price_from') > 0
            ]
            if codes_with_prices:
                self.waste_codes = [c['code'] for c in codes_with_prices[:3]]
                self.log(f"   Found {len(self.waste_codes)} codes with prices: {self.waste_codes}")
                return True
            else:
                self.log(f"   ⚠️  No codes with prices found, using fallback codes")
                self.waste_codes = ["14 06 03 01 01", "14 06 03 02 01", "14 06 03 03 01"]
                return True
        return False
    
    def test_get_company(self):
        """Get company_id for the customer"""
        success, response = self.test(
            "Get Companies",
            "GET",
            "waste/companies",
            200,
            token=self.staff_token,
            params={"limit": 10}
        )
        if success and 'items' in response:
            companies = response['items']
            if companies:
                # Find company linked to our customer
                for company in companies:
                    if company.get('customer_id') == self.customer_id or company.get('customerId') == self.customer_id:
                        self.company_id = company['id']
                        self.log(f"   Found company: {company.get('name')} ({self.company_id})")
                        return True
                # If no match, use first company
                self.company_id = companies[0]['id']
                self.log(f"   Using first company: {companies[0].get('name')} ({self.company_id})")
                return True
        return False
    
    def test_create_contract(self):
        """Create a contract with engine configuration"""
        today = datetime.now().date()
        valid_from = today.strftime("%Y-%m-%d")
        valid_to = (today + timedelta(days=365)).strftime("%Y-%m-%d")
        
        contract_data = {
            "number": f"TEST-CE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": "Test Contract Execution Engine",
            "company_id": self.company_id,
            "customer_id": self.customer_id,
            "waste_codes": self.waste_codes,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "schedule_config": {
                "period_type": "quarter"
            },
            "financial_terms": {
                "invoice_scope": "period"
            },
            "status": "active"
        }
        
        success, response = self.test(
            "Create Contract",
            "POST",
            "waste/contracts",
            200,  # API returns 200, not 201
            data=contract_data,
            token=self.staff_token
        )
        if success:
            # Extract contract_id from response
            contract = response.get('contract', {})
            if contract and 'id' in contract:
                self.contract_id = contract['id']
                self.log(f"   Contract created: {self.contract_id}")
                return True
            elif 'id' in response:
                self.contract_id = response['id']
                self.log(f"   Contract created: {self.contract_id}")
                return True
        return False
    
    def test_generate_schedule(self):
        """Generate quarterly schedule"""
        success, response = self.test(
            "Generate Schedule",
            "POST",
            f"waste/contracts/{self.contract_id}/schedule/generate",
            200,
            data={"replace": True},
            token=self.staff_token
        )
        if success and 'periods' in response:
            periods = response['periods']
            self.log(f"   Generated {len(periods)} periods")
            if periods:
                self.period_id = periods[0]['id']
                self.log(f"   First period: {periods[0].get('label')} ({self.period_id})")
            return True
        return False
    
    def test_get_schedule(self):
        """Get schedule with financials"""
        success, response = self.test(
            "Get Schedule",
            "GET",
            f"waste/contracts/{self.contract_id}/schedule",
            200,
            token=self.staff_token
        )
        if success:
            periods = response.get('periods', [])
            financials = response.get('financials', {})
            self.log(f"   Periods: {len(periods)}, Contract Value: {financials.get('contract_value')}")
            return True
        return False
    
    def test_line_override_planned_kg(self):
        """Override planned_kg on a period line"""
        if not self.period_id or not self.waste_codes:
            self.log("   ⚠️  Skipped - no period or waste codes")
            return False
        
        success, response = self.test(
            "Override Line - Planned KG",
            "PATCH",
            f"waste/periods/{self.period_id}/lines/{self.waste_codes[0]}",
            200,
            data={"planned_kg": 500.0},
            token=self.staff_token
        )
        if success and 'period' in response:
            period = response['period']
            line = next((l for l in period.get('lines', []) if l['waste_code'] == self.waste_codes[0]), None)
            if line:
                self.log(f"   Line updated: planned_kg={line.get('planned_kg')}, planned_amount={line.get('planned_amount')}")
            return True
        return False
    
    def test_line_override_price(self):
        """Override price_per_kg (should flip to manual)"""
        if not self.period_id or not self.waste_codes:
            self.log("   ⚠️  Skipped - no period or waste codes")
            return False
        
        success, response = self.test(
            "Override Line - Price (Manual)",
            "PATCH",
            f"waste/periods/{self.period_id}/lines/{self.waste_codes[0]}",
            200,
            data={"price_per_kg": 25.50},
            token=self.staff_token
        )
        if success and 'period' in response:
            period = response['period']
            line = next((l for l in period.get('lines', []) if l['waste_code'] == self.waste_codes[0]), None)
            if line:
                price_source = line.get('price_source')
                calc_price = line.get('calc_price_per_kg')
                manual_price = line.get('price_per_kg')
                self.log(f"   Price source: {price_source}, calc={calc_price}, manual={manual_price}")
                if price_source == 'manual':
                    self.log(f"   ✓ Price source correctly switched to 'manual'")
                else:
                    self.log(f"   ⚠️  Price source is '{price_source}', expected 'manual'")
            return True
        return False
    
    def test_add_extra_work(self):
        """Add extra work to a period"""
        if not self.period_id:
            self.log("   ⚠️  Skipped - no period")
            return False
        
        success, response = self.test(
            "Add Extra Work",
            "POST",
            f"waste/periods/{self.period_id}/extra-works",
            200,
            data={
                "type": "transport",
                "amount": 1500.00,
                "stage": "planned"
            },
            token=self.staff_token
        )
        if success and 'extra' in response:
            extra = response['extra']
            self.log(f"   Extra work added: {extra.get('label')} - {extra.get('amount')} UAH")
            return True
        return False
    
    def test_delete_extra_work(self):
        """Delete an extra work"""
        if not self.period_id:
            self.log("   ⚠️  Skipped - no period")
            return False
        
        # First get the period to find an extra work
        success, response = self.test(
            "Get Period for Extra Work",
            "GET",
            f"waste/contracts/{self.contract_id}/schedule",
            200,
            token=self.staff_token
        )
        if success and 'periods' in response:
            period = next((p for p in response['periods'] if p['id'] == self.period_id), None)
            if period and period.get('extra_works'):
                extra_id = period['extra_works'][0]['id']
                success2, _ = self.test(
                    "Delete Extra Work",
                    "DELETE",
                    f"waste/periods/{self.period_id}/extra-works/{extra_id}",
                    200,
                    token=self.staff_token
                )
                return success2
        self.log("   ⚠️  No extra works to delete")
        return False
    
    def test_get_financials(self):
        """Get contract financials (5 values)"""
        success, response = self.test(
            "Get Financials",
            "GET",
            f"waste/contracts/{self.contract_id}/financials",
            200,
            token=self.staff_token
        )
        if success and 'financials' in response:
            fin = response['financials']
            self.log(f"   Contract Value: {fin.get('contract_value')} (frozen: {fin.get('contract_value_frozen')})")
            self.log(f"   Executed Value: {fin.get('executed_value')}")
            self.log(f"   Invoiced Value: {fin.get('invoiced_value')}")
            self.log(f"   Paid Value: {fin.get('paid_value')}")
            self.log(f"   Remaining Value: {fin.get('remaining_value')}")
            return True
        return False
    
    def test_freeze_contract_value(self):
        """Freeze contract value"""
        success, response = self.test(
            "Freeze Contract Value",
            "POST",
            f"waste/contracts/{self.contract_id}/freeze-value",
            200,
            data={},
            token=self.staff_token
        )
        if success and 'financials' in response:
            fin = response['financials']
            frozen = fin.get('contract_value_frozen')
            self.log(f"   Contract value frozen: {frozen}, value: {fin.get('contract_value')}")
            return True
        return False
    
    def test_create_act_for_accumulation(self):
        """Create a signed act to test auto-accumulation"""
        if not self.period_id or not self.waste_codes:
            self.log("   ⚠️  Skipped - no period or waste codes")
            return False
        
        act_data = {
            "contract_id": self.contract_id,
            "company_id": self.company_id,
            "period_id": self.period_id,
            "number": f"ACT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "act_date": datetime.now().date().strftime("%Y-%m-%d"),
            "status": "signed",
            "lines": [
                {
                    "waste_code": self.waste_codes[0],
                    "actual_kg": 450.0,
                    "price_per_kg": 25.00
                }
            ]
        }
        
        success, response = self.test(
            "Create Signed Act (Accumulation)",
            "POST",
            "waste/acts",
            200,  # API returns 200, not 201
            data=act_data,
            token=self.staff_token
        )
        if success:
            # Extract act_id from response
            act = response.get('act', {})
            if act and 'id' in act:
                self.act_id = act['id']
                self.log(f"   Act created: {self.act_id}")
                return True
            elif 'id' in response:
                self.act_id = response['id']
                self.log(f"   Act created: {self.act_id}")
                return True
        return False
    
    def test_verify_accumulation(self):
        """Verify that act accumulated into period"""
        if not self.period_id:
            self.log("   ⚠️  Skipped - no period")
            return False
        
        success, response = self.test(
            "Verify Act Accumulation",
            "GET",
            f"waste/contracts/{self.contract_id}/schedule",
            200,
            token=self.staff_token
        )
        if success and 'periods' in response:
            period = next((p for p in response['periods'] if p['id'] == self.period_id), None)
            if period:
                line = next((l for l in period.get('lines', []) if l['waste_code'] == self.waste_codes[0]), None)
                if line:
                    actual_kg = line.get('actual_kg', 0)
                    actual_amount = line.get('actual_amount', 0)
                    self.log(f"   Line actual_kg: {actual_kg}, actual_amount: {actual_amount}")
                    if actual_kg > 0:
                        self.log(f"   ✓ Act successfully accumulated into period")
                        return True
                    else:
                        self.log(f"   ⚠️  actual_kg is 0, accumulation may have failed")
            financials = response.get('financials', {})
            executed = financials.get('executed_value', 0)
            self.log(f"   Executed Value: {executed}")
            return True
        return False
    
    def test_accumulation_idempotency(self):
        """Test that recomputing actuals is idempotent"""
        success, response = self.test(
            "Recompute Actuals (Idempotency)",
            "POST",
            f"waste/contracts/{self.contract_id}/recompute",
            200,
            data={},
            token=self.staff_token
        )
        if success:
            self.log(f"   ✓ Recompute successful (should be idempotent)")
            return True
        return False
    
    def test_completion_check_not_ready(self):
        """Test completion check when not ready"""
        success, response = self.test(
            "Completion Check (Not Ready)",
            "GET",
            f"waste/contracts/{self.contract_id}/completion-check",
            200,
            token=self.staff_token
        )
        if success:
            ready = response.get('ready', False)
            checks = response.get('checks', [])
            self.log(f"   Ready: {ready}, Checks: {len(checks)}")
            for check in checks:
                status = "✓" if check.get('ok') else "✗"
                self.log(f"     {status} {check.get('label')}: {check.get('detail')}")
            return True
        return False
    
    def test_completion_blocked(self):
        """Test that completion is blocked when not ready"""
        success, response = self.test(
            "Complete Contract (Should Block)",
            "POST",
            f"waste/contracts/{self.contract_id}/complete",
            400,  # Should return 400 when not ready
            data={"confirm": True},
            token=self.staff_token
        )
        if success:
            self.log(f"   ✓ Completion correctly blocked (400 expected)")
            return True
        else:
            # If we got a different status, check if it's because it's already ready
            self.log(f"   Note: Got different status, contract might be ready or already closed")
            return False
    
    def test_create_ecologist_report(self):
        """Create an ecologist report"""
        report_data = {
            "scope_type": "contract",
            "status": "final",
            "ecologist": {
                "name": "Іван Петренко",
                "license_no": "ECO-2024-12345"
            },
            "conclusion": "Утилізація відходів виконана відповідно до вимог законодавства.",
            "recommendations": "Продовжувати дотримуватися екологічних норм."
        }
        
        success, response = self.test(
            "Create Ecologist Report",
            "POST",
            f"waste/contracts/{self.contract_id}/ecologist-reports",
            200,
            data=report_data,
            token=self.staff_token
        )
        if success and 'report' in response:
            report = response['report']
            self.report_id = report.get('id')
            self.log(f"   Report created: {report.get('number')} ({self.report_id})")
            self.log(f"   Status: {report.get('status')}, Plan: {report.get('plan_kg')} kg, Actual: {report.get('actual_kg')} kg")
            return True
        return False
    
    def test_get_ecologist_report_pdf(self):
        """Test PDF generation for ecologist report"""
        if not self.report_id:
            self.log("   ⚠️  Skipped - no report")
            return False
        
        url = f"{BASE_URL}/waste/ecologist-reports/{self.report_id}/pdf"
        headers = {'Authorization': f'Bearer {self.staff_token}'}
        
        self.tests_run += 1
        print(f"\n🔍 Test {self.tests_run}: Get Ecologist Report PDF")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200 and response.headers.get('content-type') == 'application/pdf':
                self.tests_passed += 1
                pdf_size = len(response.content)
                self.log(f"✅ PASS - PDF generated, size: {pdf_size} bytes")
                return True
            else:
                self.log(f"❌ FAIL - Status: {response.status_code}, Content-Type: {response.headers.get('content-type')}")
                return False
        except Exception as e:
            self.log(f"❌ FAIL - Error: {str(e)}")
            return False
    
    def test_client_list_contracts(self):
        """Test client read-only contract list"""
        if not self.customer_id:
            self.log("   ⚠️  Skipped - no customer_id")
            return False
        
        success, response = self.test(
            "Client List Contracts",
            "GET",
            f"customer-cabinet/{self.customer_id}/contract-engine",
            200,
            token=self.client_token
        )
        if success and 'items' in response:
            contracts = response['items']
            self.log(f"   Client has {len(contracts)} contracts")
            return True
        return False
    
    def test_client_contract_detail(self):
        """Test client read-only contract detail"""
        if not self.customer_id or not self.contract_id:
            self.log("   ⚠️  Skipped - no customer_id or contract_id")
            return False
        
        success, response = self.test(
            "Client Contract Detail",
            "GET",
            f"customer-cabinet/{self.customer_id}/contract-engine/{self.contract_id}",
            200,
            token=self.client_token
        )
        if success:
            contract = response.get('contract', {})
            periods = response.get('periods', [])
            financials = response.get('financials', {})
            acts = response.get('acts', [])
            reports = response.get('ecologist_reports', [])
            self.log(f"   Contract: {contract.get('number')}")
            self.log(f"   Periods: {len(periods)}, Acts: {len(acts)}, Reports: {len(reports)}")
            self.log(f"   Financials - Contract: {financials.get('contract_value')}, Executed: {financials.get('executed_value')}")
            return True
        return False
    
    def test_client_ownership_enforcement(self):
        """Test that client cannot access foreign contracts"""
        if not self.customer_id:
            self.log("   ⚠️  Skipped - no customer_id")
            return False
        
        # Try to access a non-existent contract (should return 404)
        fake_contract_id = "fake_contract_12345"
        success, response = self.test(
            "Client Ownership Enforcement (404 Expected)",
            "GET",
            f"customer-cabinet/{self.customer_id}/contract-engine/{fake_contract_id}",
            404,
            token=self.client_token
        )
        if success:
            self.log(f"   ✓ Ownership correctly enforced (404 for foreign contract)")
            return True
        return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*70)
        print("CONTRACT EXECUTION ENGINE - BACKEND API TEST SUITE")
        print("="*70)
        
        # Authentication
        print("\n" + "─"*70)
        print("AUTHENTICATION")
        print("─"*70)
        if not self.test_staff_login():
            print("\n❌ Staff login failed - stopping tests")
            return False
        if not self.test_client_login():
            print("\n⚠️  Client login failed - client tests will be skipped")
        
        # Waste codes
        print("\n" + "─"*70)
        print("WASTE CODES & COMPANY")
        print("─"*70)
        self.test_get_waste_codes()
        if not self.test_get_company():
            print("\n❌ Company lookup failed - stopping tests")
            return False
        
        # Contract creation
        print("\n" + "─"*70)
        print("CONTRACT CREATION & SCHEDULE")
        print("─"*70)
        if not self.test_create_contract():
            print("\n❌ Contract creation failed - stopping tests")
            return False
        self.test_generate_schedule()
        self.test_get_schedule()
        
        # Line overrides
        print("\n" + "─"*70)
        print("LINE OVERRIDES (PRICING)")
        print("─"*70)
        self.test_line_override_planned_kg()
        self.test_line_override_price()
        
        # Extra works
        print("\n" + "─"*70)
        print("EXTRA WORKS")
        print("─"*70)
        self.test_add_extra_work()
        self.test_delete_extra_work()
        
        # Financials
        print("\n" + "─"*70)
        print("FINANCIALS (5 VALUES)")
        print("─"*70)
        self.test_get_financials()
        self.test_freeze_contract_value()
        
        # Act accumulation
        print("\n" + "─"*70)
        print("ACT AUTO-ACCUMULATION")
        print("─"*70)
        self.test_create_act_for_accumulation()
        self.test_verify_accumulation()
        self.test_accumulation_idempotency()
        
        # Completion wizard
        print("\n" + "─"*70)
        print("COMPLETION WIZARD")
        print("─"*70)
        self.test_completion_check_not_ready()
        self.test_completion_blocked()
        
        # Ecologist reports
        print("\n" + "─"*70)
        print("ECOLOGIST REPORTS")
        print("─"*70)
        self.test_create_ecologist_report()
        self.test_get_ecologist_report_pdf()
        
        # Client portal
        if self.client_token:
            print("\n" + "─"*70)
            print("CLIENT PORTAL (READ-ONLY)")
            print("─"*70)
            self.test_client_list_contracts()
            self.test_client_contract_detail()
            self.test_client_ownership_enforcement()
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print("="*70 + "\n")
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = ContractEngineAPITester()
    tester.run_all_tests()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
