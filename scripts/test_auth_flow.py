"""
Test authentication flow and token validation
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_auth_flow():
    print("=" * 60)
    print("TESTING AUTHENTICATION FLOW")
    print("=" * 60)
    
    # Test 1: Register a test user
    print("\n1. Testing Registration...")
    register_data = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpass123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        if response.status_code == 201:
            print("✓ Registration successful")
        elif response.status_code == 409:
            print("✓ User already exists (expected if running multiple times)")
        else:
            print(f"✗ Registration failed: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"✗ Registration error: {e}")
        return
    
    # Test 2: Login
    print("\n2. Testing Login...")
    login_data = {
        "email": "testuser@example.com",
        "password": "testpass123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print("✓ Login successful")
            print(f"  Token: {token[:50]}...")
        else:
            print(f"✗ Login failed: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"✗ Login error: {e}")
        return
    
    # Test 3: Access protected endpoint
    print("\n3. Testing Protected Endpoint (Session Status)...")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/session/status", headers=headers)
        if response.status_code == 200:
            print("✓ Protected endpoint accessible with token")
            data = response.json()
            print(f"  User ID: {data.get('user_id')}")
            print(f"  Active Session: {data.get('active_session_id')}")
        elif response.status_code == 404:
            print("✓ Protected endpoint accessible with token")
            print("  (404 is expected - no active session yet)")
        else:
            print(f"✗ Protected endpoint failed: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"✗ Protected endpoint error: {e}")
        return
    
    # Test 4: Access without token (should fail)
    print("\n4. Testing Protected Endpoint WITHOUT Token...")
    try:
        response = requests.get(f"{BASE_URL}/session/status")
        if response.status_code == 401:
            print("✓ Correctly rejected request without token (401)")
        else:
            print(f"✗ Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 5: Start a session
    print("\n5. Testing Session Start...")
    try:
        response = requests.post(f"{BASE_URL}/session/start", headers=headers)
        if response.status_code in [200, 201]:
            data = response.json()
            session_id = data.get("session_id")
            print("✓ Session started successfully")
            print(f"  Session ID: {session_id}")
        else:
            print(f"✗ Session start failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Session start error: {e}")
    
    print("\n" + "=" * 60)
    print("AUTHENTICATION FLOW TEST COMPLETE")
    print("=" * 60)
    print("\nTo test in Swagger:")
    print(f"1. Copy this token: {token}")
    print("2. Go to http://localhost:8000/docs")
    print("3. Click 'Authorize' button")
    print(f"4. Enter: Bearer {token}")
    print("5. Click 'Authorize' then 'Close'")
    print("6. Now you can test all endpoints in Swagger")

if __name__ == "__main__":
    test_auth_flow()
