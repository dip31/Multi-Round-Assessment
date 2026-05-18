"""
Test the /coding/run endpoint to verify actual_output is being returned
"""
import requests
import json
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000/api/v1"

def test_run_code():
    print("=" * 70)
    print("TESTING /coding/run ENDPOINT")
    print("=" * 70)
    
    # Step 1: Login to get token
    print("\n1. Logging in...")
    login_data = {"email": "testuser@example.com", "password": "testpass123"}
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code != 200:
            print(f"✗ Login failed: {response.status_code}")
            return
        token = response.json()["access_token"]
        print(f"✓ Login successful")
    except Exception as e:
        print(f"✗ Login error: {e}")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Start a session
    print("\n2. Starting session...")
    try:
        response = requests.post(f"{BASE_URL}/session/start", headers=headers)
        if response.status_code not in [200, 201]:
            print(f"✗ Session start failed: {response.status_code}")
            return
        print("✓ Session started")
    except Exception as e:
        print(f"✗ Session start error: {e}")
        return
    
    # Step 3: Start coding round
    print("\n3. Starting coding round...")
    try:
        response = requests.post(f"{BASE_URL}/coding/start-round", headers=headers)
        if response.status_code not in [200, 201]:
            # Try restart if already started
            response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
        
        data = response.json()
        round_id = data["round_id"]
        print(f"✓ Coding round started (ID: {round_id})")
    except Exception as e:
        print(f"✗ Coding round start error: {e}")
        return
    
    # Step 4: Get problems
    print("\n4. Getting problems...")
    try:
        response = requests.get(f"{BASE_URL}/coding/problems/{round_id}", headers=headers)
        problems = response.json()
        if not problems:
            print("✗ No problems found")
            return
        problem_id = problems[0]["id"]
        problem_title = problems[0]["title"]
        print(f"✓ Got {len(problems)} problems")
        print(f"  Testing with: {problem_title} (ID: {problem_id})")
    except Exception as e:
        print(f"✗ Get problems error: {e}")
        return
    
    # Step 5: Run code
    print("\n5. Running code...")
    
    # Simple Python code that should work
    test_code = """n = int(input())
a, b = 0, 1
result = []
for i in range(n + 1):
    result.append(str(a))
    a, b = b, a + b
print(' '.join(result))"""
    
    run_payload = {
        "round_id": round_id,
        "problem_id": problem_id,
        "code": test_code,
        "language": "python"
    }
    
    print(f"\nPayload:")
    print(json.dumps(run_payload, indent=2))
    
    try:
        response = requests.post(f"{BASE_URL}/coding/run", json=run_payload, headers=headers)
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ Run successful!")
            print("\nFull Response:")
            print(json.dumps(data, indent=2))
            
            print("\n" + "=" * 70)
            print("DETAILED RESULTS:")
            print("=" * 70)
            
            for i, result in enumerate(data["results"], 1):
                print(f"\nTest Case {i}:")
                print(f"  Input:           {repr(result['input_data'])}")
                print(f"  Expected Output: {repr(result['expected_output'])}")
                print(f"  Actual Output:   {repr(result['actual_output'])}")
                print(f"  Passed:          {result['passed']}")
                
                if not result['passed']:
                    print(f"\n  ⚠ MISMATCH DETECTED:")
                    print(f"    Expected (stripped): {repr(result['expected_output'].strip())}")
                    print(f"    Actual (stripped):   {repr(result['actual_output'].strip())}")
                    print(f"    Are they equal? {result['expected_output'].strip() == result['actual_output'].strip()}")
        
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

if __name__ == "__main__":
    test_run_code()
