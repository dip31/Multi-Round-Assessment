"""
Test Judge0 connection from Windows to Ubuntu
"""
import requests
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.config.settings import settings

def test_judge0_direct():
    """Test direct connection to Judge0 API"""
    print("="*60)
    print("TESTING JUDGE0 CONNECTION")
    print("="*60)
    
    judge0_url = settings.JUDGE0_API_URL
    print(f"\nJudge0 URL: {judge0_url}")
    print(f"Judge0 API Key: {'Set' if settings.JUDGE0_API_KEY else 'Not set'}")
    
    # Test 1: Check if Judge0 is reachable
    print("\n1. Testing Judge0 connectivity...")
    try:
        response = requests.get(f"{judge0_url}/about", timeout=5)
        print(f"✓ Judge0 is reachable!")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Cannot connect to Judge0")
        print(f"  Error: {e}")
        print(f"\n  Possible issues:")
        print(f"  1. Judge0 Docker containers not running on Ubuntu")
        print(f"  2. Firewall blocking port 2358")
        print(f"  3. Wrong IP address in .env (current: {judge0_url})")
        print(f"\n  To fix:")
        print(f"  - On Ubuntu, run: docker ps")
        print(f"  - Check if judge0-server is running")
        print(f"  - Check Ubuntu IP: ip addr show")
        print(f"  - Update JUDGE0_API_URL in .env if needed")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 2: Submit a simple Python code
    print("\n2. Testing code submission...")
    test_code = """
n = int(input())
print(n * 2)
"""
    
    payload = {
        "source_code": test_code,
        "language_id": 71,  # Python 3
        "stdin": "5",
    }
    
    headers = {"Content-Type": "application/json"}
    if settings.JUDGE0_API_KEY:
        headers["X-RapidAPI-Key"] = settings.JUDGE0_API_KEY
    
    try:
        response = requests.post(
            f"{judge0_url}/submissions",
            json=payload,
            params={"wait": "true"},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"✓ Code executed successfully!")
            print(f"  Status: {result.get('status', {}).get('description')}")
            print(f"  Output: {result.get('stdout', '').strip()}")
            print(f"  Expected: 10")
            
            if result.get('stdout', '').strip() == "10":
                print(f"\n✓✓ Judge0 is working correctly!")
                return True
            else:
                print(f"\n⚠ Output doesn't match expected")
        else:
            print(f"✗ Submission failed")
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"✗ Request timed out")
        print(f"  Judge0 might be overloaded or slow")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    return False

def test_through_backend():
    """Test Judge0 through the backend API"""
    print("\n" + "="*60)
    print("TESTING THROUGH BACKEND API")
    print("="*60)
    
    # Login first
    print("\n1. Logging in...")
    login_response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"email": "kumar08@gmail.com", "password": "kumar123"}
    )
    
    if login_response.status_code != 200:
        print(f"✗ Login failed")
        return
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✓ Login successful")
    
    # Get round ID
    print("\n2. Getting round info...")
    session_response = requests.get(
        "http://localhost:8000/api/v1/session/status",
        headers=headers
    )
    
    if session_response.status_code != 200:
        print(f"✗ No active session")
        return
    
    session_data = session_response.json()
    coding_round = next(
        (r for r in session_data["rounds"] if r["round_type"] == "coding"),
        None
    )
    
    if not coding_round:
        print(f"✗ No coding round found")
        return
    
    round_id = coding_round["id"]
    print(f"✓ Found coding round: {round_id}")
    
    # Get problems
    print("\n3. Getting problems...")
    problems_response = requests.get(
        f"http://localhost:8000/api/v1/coding/problems/{round_id}",
        headers=headers
    )
    
    if problems_response.status_code != 200:
        print(f"✗ Failed to get problems")
        return
    
    problems = problems_response.json()
    if not problems:
        print(f"✗ No problems assigned")
        return
    
    problem_id = problems[0]["id"]
    print(f"✓ Found problem: {problems[0]['title']}")
    
    # Test run code
    print("\n4. Testing Run Code (uses Judge0)...")
    test_code = """
n = int(input())
arr = list(map(int, input().split()))
print(sum(arr))
"""
    
    run_response = requests.post(
        "http://localhost:8000/api/v1/coding/run",
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem_id,
            "code": test_code,
            "language": "python"
        }
    )
    
    print(f"  Status: {run_response.status_code}")
    
    if run_response.status_code == 200:
        result = run_response.json()
        print(f"✓ Code execution successful!")
        print(f"  Results: {json.dumps(result, indent=2)}")
        
        # Check if it used mock or real Judge0
        if any("mock" in str(r).lower() for r in result.get("results", [])):
            print(f"\n⚠ Using MOCK Judge0 (fallback)")
            print(f"  Real Judge0 might not be accessible")
        else:
            print(f"\n✓✓ Using REAL Judge0!")
    else:
        print(f"✗ Code execution failed")
        print(f"  Response: {run_response.text}")

if __name__ == "__main__":
    # Test direct connection first
    judge0_working = test_judge0_direct()
    
    # Then test through backend
    test_through_backend()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if judge0_working:
        print("✓ Judge0 is accessible from Windows to Ubuntu")
        print("✓ Code execution should work in the frontend")
    else:
        print("⚠ Judge0 is NOT accessible")
        print("  The system will use Mock Judge0 as fallback")
        print("  Mock Judge0 works for testing but doesn't actually execute code")
        print("\n  To fix:")
        print("  1. On Ubuntu: docker-compose up -d")
        print("  2. Check Ubuntu IP and update .env JUDGE0_API_URL")
        print("  3. Ensure port 2358 is open in firewall")
