"""
Waste Catalog Management Backend Test
Tests the new admin-managed catalog category feature (Wave D1).
"""
import requests
import sys
from datetime import datetime

class WasteCatalogTester:
    def __init__(self, base_url="https://eco-recycler-3.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_category_key = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except Exception:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except Exception:
                    print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_login(self, email, password):
        """Test admin login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        print(f"   Login response keys: {list(response.keys())}")
        if success and 'token' in response:
            self.token = response['token']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        elif success and 'access_token' in response:
            self.token = response['access_token']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        print(f"   ❌ No token found in response: {response}")
        return False

    def test_get_icons(self):
        """Test GET /api/waste/admin/icons"""
        success, response = self.run_test(
            "Get Available Icons",
            "GET",
            "waste/admin/icons",
            200
        )
        if success and 'icons' in response:
            icons = response['icons']
            print(f"   Found {len(icons)} available icons")
            print(f"   Sample icons: {icons[:5]}")
            return True
        return False

    def test_list_categories(self):
        """Test GET /api/waste/admin/categories"""
        success, response = self.run_test(
            "List Admin Categories",
            "GET",
            "waste/admin/categories",
            200
        )
        if success and 'categories' in response:
            cats = response['categories']
            print(f"   Found {len(cats)} categories")
            if cats:
                sample = cats[0]
                print(f"   Sample category: {sample.get('key')} - {sample.get('name_uk')} / {sample.get('name_en')}")
                print(f"   Icon: {sample.get('icon')}, Count: {sample.get('count')}, Order: {sample.get('order')}")
                if 'codes' in sample:
                    print(f"   Assigned codes: {len(sample.get('codes', []))} codes")
            return True
        return False

    def test_create_category(self):
        """Test POST /api/waste/admin/categories"""
        timestamp = datetime.now().strftime("%H%M%S")
        test_data = {
            "name_uk": f"Тестова категорія {timestamp}",
            "name_en": f"Test Category {timestamp}",
            "icon": "flask",
            "synonyms": ["тест", "test"],
            "active": True,
            "codes": ["18 01 03*", "18 01 06*"]  # Medical waste codes
        }
        
        success, response = self.run_test(
            "Create Test Category",
            "POST",
            "waste/admin/categories",
            200,
            data=test_data
        )
        
        if success and 'category' in response:
            cat = response['category']
            self.test_category_key = cat.get('key')
            print(f"   Created category key: {self.test_category_key}")
            print(f"   Name UK: {cat.get('name_uk')}")
            print(f"   Name EN: {cat.get('name_en')}")
            print(f"   Icon: {cat.get('icon')}")
            print(f"   Active: {cat.get('active')}")
            if 'assign' in response:
                print(f"   Code assignment: {response['assign']}")
            return True
        return False

    def test_update_category(self):
        """Test PUT /api/waste/admin/categories/{key}"""
        if not self.test_category_key:
            print("   ⚠️  Skipped - No test category key available")
            return False
        
        update_data = {
            "name_uk": "Оновлена тестова категорія",
            "name_en": "Updated Test Category",
            "icon": "atom",
            "active": False,
            "codes": ["18 01 03*"]  # Reduced to 1 code
        }
        
        success, response = self.run_test(
            "Update Test Category",
            "PUT",
            f"waste/admin/categories/{self.test_category_key}",
            200,
            data=update_data
        )
        
        if success and 'category' in response:
            cat = response['category']
            print(f"   Updated name UK: {cat.get('name_uk')}")
            print(f"   Updated icon: {cat.get('icon')}")
            print(f"   Updated active: {cat.get('active')}")
            if 'assign' in response:
                print(f"   Code re-assignment: {response['assign']}")
            return True
        return False

    def test_reorder_categories(self):
        """Test POST /api/waste/admin/categories/reorder"""
        # First get current categories
        success, response = self.run_test(
            "Get Categories for Reorder",
            "GET",
            "waste/admin/categories",
            200
        )
        
        if not success or 'categories' not in response:
            return False
        
        cats = response['categories']
        if len(cats) < 2:
            print("   ⚠️  Need at least 2 categories to test reorder")
            return False
        
        # Create new order (reverse first two)
        order = [c['key'] for c in cats]
        if len(order) >= 2:
            order[0], order[1] = order[1], order[0]
        
        success, response = self.run_test(
            "Reorder Categories",
            "POST",
            "waste/admin/categories/reorder",
            200,
            data={"order": order}
        )
        
        if success:
            print(f"   Reordered {response.get('count', 0)} categories")
            return True
        return False

    def test_public_categories(self):
        """Test GET /api/waste/categories?accepted=true (public endpoint)"""
        # Temporarily remove token for public endpoint test
        temp_token = self.token
        self.token = None
        
        success, response = self.run_test(
            "Public Categories (accepted=true)",
            "GET",
            "waste/categories?accepted=true",
            200
        )
        
        # Restore token
        self.token = temp_token
        
        if success and 'categories' in response:
            cats = response['categories']
            print(f"   Found {len(cats)} public categories")
            if cats:
                sample = cats[0]
                print(f"   Sample: {sample.get('key')} - {sample.get('name_uk')} / {sample.get('name_en')}")
                print(f"   Icon: {sample.get('icon')}, Count: {sample.get('count')}")
            return True
        return False

    def test_delete_category(self):
        """Test DELETE /api/waste/admin/categories/{key}"""
        if not self.test_category_key:
            print("   ⚠️  Skipped - No test category key available")
            return False
        
        success, response = self.run_test(
            "Delete Test Category",
            "DELETE",
            f"waste/admin/categories/{self.test_category_key}",
            200
        )
        
        if success:
            print(f"   Deleted category: {response.get('deleted')}")
            print(f"   Detached codes: {response.get('detached_codes', 0)}")
            self.test_category_key = None
            return True
        return False


def main():
    print("=" * 70)
    print("WASTE CATALOG MANAGEMENT BACKEND TEST")
    print("=" * 70)
    
    tester = WasteCatalogTester()
    
    # 1. Login
    if not tester.test_login("admin@bibi.cars", "Admin@12345"):
        print("\n❌ Login failed, stopping tests")
        return 1
    
    # 2. Test GET icons
    tester.test_get_icons()
    
    # 3. Test GET admin categories
    tester.test_list_categories()
    
    # 4. Test CREATE category
    tester.test_create_category()
    
    # 5. Test UPDATE category
    tester.test_update_category()
    
    # 6. Test REORDER categories
    tester.test_reorder_categories()
    
    # 7. Test public categories endpoint
    tester.test_public_categories()
    
    # 8. Test DELETE category (cleanup)
    tester.test_delete_category()
    
    # Print results
    print("\n" + "=" * 70)
    print(f"📊 RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    print("=" * 70)
    
    return 0 if tester.tests_passed == tester.tests_run else 1


if __name__ == "__main__":
    sys.exit(main())
