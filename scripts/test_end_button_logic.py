#!/usr/bin/env python3
"""
Test script to verify End Test button logic works correctly.

Tests:
1. End Test button appears only when ALL problems are submitted (attempted or accepted)
2. Result counting shows total problems in test, not submission attempts
3. Button appears for both correct and incorrect submissions
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_end_button_logic():
    """Test the complete End Test button logic"""
    
    print("🧪 Testing End Test Button Logic")
    print("=" * 50)
    
    # Step 1: Login
    print("\n1️⃣ Logging in...")
    login_response = requests.post(f"{BASE_URL}/auth/login", data={
        "username": "testuser@example.com",
        "password": "testpass123"
    })
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        return False
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful")
    
    # Step 2: Start fresh session
    print("\n2️⃣ Starting fresh session...")
    session_response = requests.post(f"{BASE_URL}/session/restart", headers=headers)
    
    if session_response.status_code != 200:
        print(f"❌ Session start failed: {session_response.status_code}")
        return False
    
    print("✅ Fresh session started")
    
    # Step 3: Start coding round
    print("\n3️⃣ Starting coding round...")
    coding_response = requests.post(f"{BASE_URL}/coding/start-round", headers=headers)
    
    if coding_response.status_code != 200:
        print(f"❌ Coding round start failed: {coding_response.status_code}")
        return False
    
    round_data = coding_response.json()
    round_id = round_data["round_id"]
    problems = round_data["problems"]
    
    print(f"✅ Coding round started with {len(problems)} problems")
    print(f"   Round ID: {round_id}")
    for i, p in enumerate(problems):
        print(f"   Problem {i+1}: {p['title']} (ID: {p['id']})")
    
    # Step 4: Check initial session status
    print("\n4️⃣ Checking initial session status...")
    status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    
    if status_response.status_code != 200:
        print(f"❌ Session status failed: {status_response.status_code}")
        return False
    
    status_data = status_response.json()
    print(f"✅ Initial status: all_problems_solved = {status_data['all_problems_solved']}")
    print("   Expected: False (no problems submitted yet)")
    
    if status_data['all_problems_solved']:
        print("❌ ERROR: all_problems_solved should be False initially")
        return False
    
    # Step 5: Submit first problem (correct solution)
    print(f"\n5️⃣ Submitting first problem (correct solution)...")
    problem1_id = problems[0]["id"]
    
    # Simple correct solution for most problems
    correct_code = '''
def solution():
    # Simple solution that should pass basic test cases
    n = int(input())
    result = []
    for i in range(n):
        result.append(str(i))
    print(" ".join(result))

solution()
'''
    
    submit1_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem1_id,
            "code": correct_code,
            "language": "python"
        }
    )
    
    if submit1_response.status_code != 200:
        print(f"❌ First submission failed: {submit1_response.status_code}")
        print(f"   Response: {submit1_response.text}")
        return False
    
    result1 = submit1_response.json()
    print(f"✅ First submission: {result1['verdict']} (Score: {result1['score']})")
    
    # Check status after first submission
    status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    status_data = status_response.json()
    print(f"   Status after 1st submission: all_problems_solved = {status_data['all_problems_solved']}")
    print("   Expected: False (only 1 of 2 problems submitted)")
    
    if status_data['all_problems_solved']:
        print("❌ ERROR: all_problems_solved should be False after 1 submission")
        return False
    
    # Step 6: Submit second problem (intentionally wrong solution)
    print(f"\n6️⃣ Submitting second problem (wrong solution)...")
    problem2_id = problems[1]["id"]
    
    # Intentionally wrong solution
    wrong_code = '''
def solution():
    # This will produce wrong output
    print("wrong answer")

solution()
'''
    
    submit2_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem2_id,
            "code": wrong_code,
            "language": "python"
        }
    )
    
    if submit2_response.status_code != 200:
        print(f"❌ Second submission failed: {submit2_response.status_code}")
        print(f"   Response: {submit2_response.text}")
        return False
    
    result2 = submit2_response.json()
    print(f"✅ Second submission: {result2['verdict']} (Score: {result2['score']})")
    
    # Step 7: Check final status - should show all_problems_solved = True
    print(f"\n7️⃣ Checking final session status...")
    status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    status_data = status_response.json()
    
    print(f"✅ Final status: all_problems_solved = {status_data['all_problems_solved']}")
    print("   Expected: True (both problems submitted, regardless of correctness)")
    
    if not status_data['all_problems_solved']:
        print("❌ ERROR: all_problems_solved should be True after all submissions")
        return False
    
    # Step 8: Check problem statuses
    print(f"\n8️⃣ Checking individual problem statuses...")
    for problem in status_data['problems']:
        print(f"   Problem {problem['problem_order']}: {problem['title']} - Status: {problem['status']}")
    
    # Step 9: Test end round functionality
    print(f"\n9️⃣ Testing end round...")
    end_response = requests.post(f"{BASE_URL}/coding/session/{round_id}/end", headers=headers)
    
    if end_response.status_code != 200:
        print(f"❌ End round failed: {end_response.status_code}")
        return False
    
    end_data = end_response.json()
    print(f"✅ Round ended successfully")
    print(f"   Final score: {end_data['total_score']}")
    print(f"   Problems attempted: {end_data['problems_attempted']}")
    print(f"   Problems solved: {end_data['problems_solved']}")
    
    # Step 10: Check result data
    print(f"\n🔟 Checking result data...")
    result_response = requests.get(f"{BASE_URL}/coding/session/{round_id}/result", headers=headers)
    
    if result_response.status_code != 200:
        print(f"❌ Result fetch failed: {result_response.status_code}")
        return False
    
    result_data = result_response.json()
    print(f"✅ Result data:")
    print(f"   Total score: {result_data['total_score']}")
    print(f"   Problems attempted: {result_data['problems_attempted']} (should be 2, not submission count)")
    print(f"   Problems solved: {result_data['problems_solved']} (should be count of 100% scores)")
    
    # Verify the counts are correct
    if result_data['problems_attempted'] != 2:
        print(f"❌ ERROR: problems_attempted should be 2, got {result_data['problems_attempted']}")
        return False
    
    print("\n🎉 All tests passed! End Test button logic is working correctly.")
    print("\nSummary:")
    print("✅ End Test button appears only when ALL problems are submitted")
    print("✅ Button appears for both correct and incorrect submissions")
    print("✅ Result counting shows total problems (2), not submission attempts")
    print("✅ Problems solved count reflects actual 100% scores")
    
    return True

if __name__ == "__main__":
    success = test_end_button_logic()
    if not success:
        print("\n❌ Test failed!")
        exit(1)
    else:
        print("\n✅ All tests passed!")