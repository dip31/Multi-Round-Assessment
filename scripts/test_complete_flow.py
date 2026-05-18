"""
Test the complete flow with both problems solved
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_complete_flow():
    print("=" * 70)
    print("TESTING COMPLETE FLOW - SOLVE ALL PROBLEMS")
    print("=" * 70)
    
    # Step 1: Login
    print("\n1. Logging in...")
    login_data = {"email": "testuser@example.com", "password": "testpass123"}
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        token = response.json()["access_token"]
        print("✓ Login successful")
    except Exception as e:
        print(f"✗ Login error: {e}")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Start fresh session
    print("\n2. Starting fresh session...")
    try:
        response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
        data = response.json()
        round_id = data["round_id"]
        print(f"✓ Fresh coding round started (ID: {round_id})")
    except Exception as e:
        print(f"✗ Session start error: {e}")
        return
    
    # Step 3: Get problems
    print("\n3. Getting problems...")
    try:
        response = requests.get(f"{BASE_URL}/coding/problems/{round_id}", headers=headers)
        problems = response.json()
        print(f"✓ Got {len(problems)} problems")
        for p in problems:
            print(f"  - {p['title']} (ID: {p['id']})")
    except Exception as e:
        print(f"✗ Get problems error: {e}")
        return
    
    # Step 4: Solve first problem
    print(f"\n4. Solving first problem: {problems[0]['title']}")
    
    # Count Vowels solution
    vowel_solution = """s = input()
vowels = 'aeiouAEIOU'
count = sum(1 for c in s if c in vowels)
print(count)"""
    
    submit_payload = {
        "round_id": round_id,
        "problem_id": problems[0]['id'],
        "code": vowel_solution,
        "language": "python"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ First submission successful")
            print(f"  Verdict: {result['verdict']}")
            print(f"  Score: {result['score']}")
            print(f"  Passed: {result['passed_cases']}/{result['total_cases']}")
        else:
            print(f"✗ First submission failed: {response.status_code}")
    except Exception as e:
        print(f"✗ First submission error: {e}")
    
    # Step 5: Check status after first problem
    print("\n5. Checking status after first problem...")
    try:
        response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
        data = response.json()
        print(f"✓ Status retrieved")
        print(f"  All problems solved: {data['all_problems_solved']}")
        for p in data['problems']:
            print(f"    - {p['title']}: {p['status']}")
    except Exception as e:
        print(f"✗ Status error: {e}")
    
    # Step 6: Solve second problem
    print(f"\n6. Solving second problem: {problems[1]['title']}")
    
    # Longest Increasing Subsequence solution
    lis_solution = """n = int(input())
arr = list(map(int, input().split()))

# Dynamic programming approach
dp = [1] * n

for i in range(1, n):
    for j in range(i):
        if arr[j] < arr[i]:
            dp[i] = max(dp[i], dp[j] + 1)

print(max(dp))"""
    
    submit_payload['problem_id'] = problems[1]['id']
    submit_payload['code'] = lis_solution
    
    try:
        response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Second submission successful")
            print(f"  Verdict: {result['verdict']}")
            print(f"  Score: {result['score']}")
            print(f"  Passed: {result['passed_cases']}/{result['total_cases']}")
        else:
            print(f"✗ Second submission failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Second submission error: {e}")
    
    # Step 7: Check final status
    print("\n7. Checking final status...")
    try:
        response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
        data = response.json()
        print(f"✓ Final status retrieved")
        print(f"  All problems solved: {data['all_problems_solved']}")
        
        solved_count = 0
        for p in data['problems']:
            print(f"    - {p['title']}: {p['status']}")
            if p['status'] == 'accepted':
                solved_count += 1
        
        print(f"\n  Summary: {solved_count}/{len(data['problems'])} problems solved")
        
        if data['all_problems_solved']:
            print("\n🎉 ALL PROBLEMS SOLVED!")
            print("✓ End Round button should now be visible in frontend")
            print("✓ Button should show 'Complete Assessment' in green")
        else:
            print(f"\n⚠️  Only {solved_count} problems solved")
            print("✓ End Round button should be hidden")
            print("✓ Should show 'Solve all problems to end round' message")
            
    except Exception as e:
        print(f"✗ Final status error: {e}")
    
    # Step 8: Test end round
    print("\n8. Testing end round...")
    try:
        response = requests.post(f"{BASE_URL}/coding/session/{round_id}/end", headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Round ended successfully")
            print(f"  Final status: {result['status']}")
            print(f"  Total score: {result['total_score']}")
            print(f"  Problems attempted: {result['problems_attempted']}")
            print(f"  Problems solved: {result['problems_solved']}")
            
            if result['problems_attempted'] == len(problems) and result['problems_solved'] == len(problems):
                print("\n🎯 PERFECT! All counting is correct!")
            else:
                print(f"\n⚠️  Counting issue detected:")
                print(f"    Expected attempted: {len(problems)}, got: {result['problems_attempted']}")
                print(f"    Expected solved: {len(problems)}, got: {result['problems_solved']}")
        else:
            print(f"✗ End round failed: {response.status_code}")
    except Exception as e:
        print(f"✗ End round error: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nNow test the frontend:")
    print("1. Open http://localhost:3000")
    print("2. Login and start a new coding round")
    print("3. Solve problems and watch the End Round button behavior")
    print("4. Verify button only appears when ALL problems are solved")

if __name__ == "__main__":
    test_complete_flow()