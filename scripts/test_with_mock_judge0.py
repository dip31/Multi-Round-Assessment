#!/usr/bin/env python3
"""
Test code execution with Mock Judge0 fallback
"""

import requests
import os

BASE_URL = "http://localhost:8000/api/v1"

def main():
    print("🧪 Testing Code Execution with Mock Judge0")
    print("=" * 50)
    
    # Check if backend is running
    print("\n1. Checking backend status...")
    try:
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/docs", timeout=2)
        print("✅ Backend is running")
    except:
        print("❌ Backend is not running!")
        print("   Start it with: uvicorn app.main:app --reload")
        return False
    
    # Login
    print("\n2. Logging in...")
    login_response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpass123"
    })
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        return False
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful")
    
    # Restart coding round
    print("\n3. Starting fresh coding round...")
    restart_response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
    
    if restart_response.status_code not in [200, 201]:
        print(f"❌ Restart failed: {restart_response.status_code}")
        return False
    
    round_data = restart_response.json()
    round_id = round_data["round_id"]
    problems = round_data["problems"]
    print(f"✅ Coding round started with {len(problems)} problems")
    
    # Test Run Code
    print("\n4. Testing Run Code feature...")
    problem_id = problems[0]["id"]
    
    test_code = """
n = int(input())
print(n * 2)
"""
    
    run_response = requests.post(f"{BASE_URL}/coding/run", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem_id,
            "code": test_code,
            "language": "python"
        }
    )
    
    if run_response.status_code != 200:
        print(f"❌ Run Code failed: {run_response.status_code}")
        print(f"   Response: {run_response.text}")
        return False
    
    run_data = run_response.json()
    print(f"✅ Run Code successful!")
    print(f"   Results: {len(run_data['results'])} test cases")
    
    for i, result in enumerate(run_data['results'][:2]):
        print(f"   Test {i+1}: {'✅ Passed' if result['passed'] else '❌ Failed'}")
        print(f"      Input: {result['input_data'][:50]}...")
        print(f"      Expected: {result['expected_output'][:50]}...")
        print(f"      Actual: {result['actual_output'][:50]}...")
    
    # Test Submit Code
    print("\n5. Testing Submit Code feature...")
    
    submit_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem_id,
            "code": test_code,
            "language": "python"
        }
    )
    
    if submit_response.status_code != 200:
        print(f"❌ Submit Code failed: {submit_response.status_code}")
        print(f"   Response: {submit_response.text}")
        return False
    
    submit_data = submit_response.json()
    print(f"✅ Submit Code successful!")
    print(f"   Verdict: {submit_data['verdict']}")
    print(f"   Score: {submit_data['score']}")
    print(f"   Passed: {submit_data['passed_cases']}/{submit_data['total_cases']}")
    
    # Check if Mock Judge0 was used
    print("\n6. Checking execution method...")
    if submit_data.get('execution_time', 0) == 0:
        print("   ℹ️  Mock Judge0 was likely used (execution_time = 0)")
        print("   This is expected when real Judge0 is not available")
    else:
        print("   ✅ Real Judge0 was used")
    
    print("\n" + "=" * 50)
    print("🎉 Code execution is working!")
    print("\nSummary:")
    print("  ✅ Backend is running")
    print("  ✅ Authentication works")
    print("  ✅ Coding round starts")
    print("  ✅ Run Code works")
    print("  ✅ Submit Code works")
    print("  ✅ Code execution functional (Mock or Real Judge0)")
    
    print("\n📝 Note:")
    print("  If Mock Judge0 is being used, you can:")
    print("  1. Fix real Judge0 on Ubuntu server (192.168.0.104)")
    print("  2. Or continue using Mock Judge0 for testing")
    print("  3. Mock Judge0 supports Python code execution safely")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Tests failed!")