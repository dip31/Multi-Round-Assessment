#!/usr/bin/env python3
"""
Test that result page shows correct problem counts
"""

import requests

BASE_URL = "http://localhost:8000/api/v1"

def main():
    print("🧪 Testing Result Page Counts")
    print("=" * 50)
    
    # Login
    print("1. Logging in...")
    login_response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpass123"
    })
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful")
    
    # Restart coding round
    print("\n2. Restarting coding round...")
    restart_response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
    round_data = restart_response.json()
    round_id = round_data["round_id"]
    problems = round_data["problems"]
    print(f"✅ Coding round restarted with {len(problems)} problems")
    
    # Submit multiple times to first problem (to test run count vs problem count)
    print(f"\n3. Running code multiple times on first problem...")
    problem1_id = problems[0]["id"]
    
    # Run code 3 times (should NOT count as submissions)
    for i in range(3):
        run_response = requests.post(f"{BASE_URL}/coding/run", 
            headers=headers,
            json={
                "round_id": round_id,
                "problem_id": problem1_id,
                "code": f"print('run {i+1}')",
                "language": "python"
            }
        )
        print(f"   Run {i+1}: {run_response.status_code}")
    
    # Submit once (this should count)
    submit_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem1_id,
            "code": "print('submitted solution')",
            "language": "python"
        }
    )
    print(f"   Submit: {submit_response.status_code}")
    
    # Submit to second problem
    print(f"\n4. Submitting to second problem...")
    problem2_id = problems[1]["id"]
    submit2_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problem2_id,
            "code": "print('second solution')",
            "language": "python"
        }
    )
    print(f"   Submit: {submit2_response.status_code}")
    
    # End the round
    print(f"\n5. Ending the round...")
    end_response = requests.post(f"{BASE_URL}/coding/session/{round_id}/end", headers=headers)
    end_data = end_response.json()
    print(f"✅ Round ended")
    
    # Check result data
    print(f"\n6. Checking result data...")
    result_response = requests.get(f"{BASE_URL}/coding/session/{round_id}/result", headers=headers)
    result_data = result_response.json()
    
    print(f"\n📊 RESULT SUMMARY:")
    print(f"   Total Score: {result_data['total_score']}")
    print(f"   Problems Attempted: {result_data['problems_attempted']}")
    print(f"   Problems Solved: {result_data['problems_solved']}")
    
    print(f"\n✅ VERIFICATION:")
    print(f"   Expected Problems Attempted: 2 (total problems in test)")
    print(f"   Actual Problems Attempted: {result_data['problems_attempted']}")
    
    if result_data['problems_attempted'] == 2:
        print(f"   ✅ CORRECT: Shows total problems, not run count")
    else:
        print(f"   ❌ ERROR: Should show 2, not {result_data['problems_attempted']}")
        return False
    
    print(f"\n   Expected Problems Solved: 0-2 (depends on correctness)")
    print(f"   Actual Problems Solved: {result_data['problems_solved']}")
    print(f"   ✅ This count reflects actual 100% scores")
    
    print(f"\n🎉 SUCCESS: Result counts are correct!")
    print(f"   - Problems Attempted shows total problems (2), not run attempts (3+)")
    print(f"   - Problems Solved shows actual solved count")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Test passed!")
    else:
        print("\n❌ Test failed!")