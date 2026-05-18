"""
Test starting the coding round and check the actual error
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_start_round():
    # 1. Login first
    print("1. Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "kumar08@gmail.com", "password": "kumar123"}
    )
    
    if login_response.status_code != 200:
        print(f"✗ Login failed: {login_response.status_code}")
        print(f"  Response: {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    print(f"✓ Login successful")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Check session status
    print("\n2. Checking session status...")
    session_response = requests.get(f"{BASE_URL}/session/status", headers=headers)
    print(f"  Status: {session_response.status_code}")
    if session_response.status_code == 200:
        print(f"  Session: {json.dumps(session_response.json(), indent=2)}")
    else:
        print(f"  Response: {session_response.text}")
    
    # 3. Try to start coding round
    print("\n3. Starting coding round...")
    start_response = requests.post(f"{BASE_URL}/coding/start-round", headers=headers)
    print(f"  Status: {start_response.status_code}")
    
    if start_response.status_code == 201:
        print(f"✓ Coding round started!")
        print(f"  Response: {json.dumps(start_response.json(), indent=2)}")
    else:
        print(f"✗ Failed to start coding round")
        print(f"  Response: {start_response.text}")
        
        # Try to get more details
        try:
            error_detail = start_response.json()
            print(f"  Error detail: {json.dumps(error_detail, indent=2)}")
        except:
            pass

if __name__ == "__main__":
    test_start_round()
