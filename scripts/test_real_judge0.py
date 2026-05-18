"""
Test the complete flow with real Judge0 on Ubuntu server
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"
JUDGE0_URL = "http://192.168.0.104:2358"

def test_complete_flow():
    print("=" * 70)
    print("TESTING COMPLETE FLOW WITH REAL JUDGE0")
    print("=" * 70)
    
    # Step 1: Test Judge0 directly
    print("\n1. Testing Judge0 connection...")
    try:
        response = requests.get(f"{JUDGE0_URL}/about", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Judge0 connected - Version: {data.get('version')}")
        else:
            print(f"✗ Judge0 error: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Judge0 connection failed: {e}")
        return
    
    # Step 2: Login
    print("\n2. Logging in...")
    login_data = {"email": "testuser@example.com", "password": "testpass123"}
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print("✓ Login successful")
        else:
            print(f"✗ Login failed: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Login error: {e}")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 3: Start session and coding round
    print("\n3. Starting session and coding round...")
    try:
        # Start session
        response = requests.post(f"{BASE_URL}/session/start", headers=headers)
        print(f"Session: {response.status_code}")
        
        # Start coding round
        response = requests.post(f"{BASE_URL}/coding/start-round", headers=headers)
        if response.status_code in [200, 201]:
            data = response.json()
            round_id = data["round_id"]
            print(f"✓ Coding round started (ID: {round_id})")
        else:
            # Try restart if already started
            response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
            data = response.json()
            round_id = data["round_id"]
            print(f"✓ Coding round restarted (ID: {round_id})")
    except Exception as e:
        print(f"✗ Session/round error: {e}")
        return
    
    # Step 4: Get problems
    print("\n4. Getting problems...")
    try:
        response = requests.get(f"{BASE_URL}/coding/problems/{round_id}", headers=headers)
        problems = response.json()
        if problems:
            problem_id = problems[0]["id"]
            problem_title = problems[0]["title"]
            print(f"✓ Got {len(problems)} problems")
            print(f"  Testing with: {problem_title} (ID: {problem_id})")
        else:
            print("✗ No problems found")
            return
    except Exception as e:
        print(f"✗ Get problems error: {e}")
        return
    
    # Step 5: Test with real Judge0
    print("\n5. Testing code execution with real Judge0...")
    
    # Simple Python code that should work for most problems
    test_code = """n = int(input())
print(f"Input received: {n}")
print("Hello from Judge0!")"""
    
    run_payload = {
        "round_id": round_id,
        "problem_id": problem_id,
        "code": test_code,
        "language": "python"
    }
    
    print(f"\nPayload:")
    print(json.dumps(run_payload, indent=2))
    
    try:
        print("\nSending request to backend...")
        response = requests.post(f"{BASE_URL}/coding/run", json=run_payload, headers=headers)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ Code execution successful!")
            print("\nResults:")
            
            for i, result in enumerate(data["results"], 1):
                print(f"\nTest Case {i}:")
                print(f"  Input:           {repr(result['input_data'])}")
                print(f"  Expected Output: {repr(result['expected_output'])}")
                print(f"  Actual Output:   {repr(result['actual_output'])}")
                print(f"  Passed:          {result['passed']}")
                
                # Check if we got real output (not empty)
                if result['actual_output']:
                    print(f"  🎉 REAL JUDGE0 OUTPUT RECEIVED!")
                else:
                    print(f"  ⚠️  No output (may be using mock)")
        
        elif response.status_code == 503:
            print("✗ Judge0 service unavailable")
            print(response.json())
        else:
            print(f"✗ Run failed: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"✗ Run code error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nServices running:")
    print("- Backend: http://localhost:8000")
    print("- Frontend: http://localhost:3000")
    print("- Judge0: http://192.168.0.104:2358")
    print("\nYou can now test the complete application!")

if __name__ == "__main__":
    test_complete_flow()