"""
Test the final fixes for counting and end test button
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_final_fixes():
    print("=" * 70)
    print("TESTING FINAL FIXES")
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
        total_problems = len(problems)
        print(f"✓ Got {total_problems} problems total")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p['title']} (ID: {p['id']})")
    except Exception as e:
        print(f"✗ Get problems error: {e}")
        return
    
    # Step 4: Submit solutions for both problems
    solutions = {
        "Count Vowels in a String": """s = input()
vowels = 'aeiouAEIOU'
count = sum(1 for c in s if c in vowels)
print(count)""",
        
        "Add Two Numbers": """a, b = map(int, input().split())
print(a + b)""",
        
        "Binary Search": """n = int(input())
arr = list(map(int, input().split()))
target = int(input())

left, right = 0, n - 1
result = -1

while left <= right:
    mid = (left + right) // 2
    if arr[mid] == target:
        result = mid
        break
    elif arr[mid] < target:
        left = mid + 1
    else:
        right = mid - 1

print(result)""",
        
        "Maximum Subarray Sum": """n = int(input())
arr = list(map(int, input().split()))

max_sum = arr[0]
current_sum = arr[0]

for i in range(1, n):
    current_sum = max(arr[i], current_sum + arr[i])
    max_sum = max(max_sum, current_sum)

print(max_sum)""",
        
        "Factorial of a Number": """n = int(input())
if n == 0 or n == 1:
    print(1)
else:
    result = 1
    for i in range(2, n + 1):
        result *= i
    print(result)"""
    }
    
    solved_count = 0
    
    for i, problem in enumerate(problems, 1):
        print(f"\n{3+i}. Solving problem {i}/{total_problems}: {problem['title']}")
        
        # Get appropriate solution
        solution = solutions.get(problem['title'], """# Generic solution
n = int(input())
print(n)""")
        
        # Simulate multiple run attempts (should not affect final count)
        print(f"  Simulating 2 run attempts (should NOT be counted)...")
        for run_attempt in range(2):
            run_payload = {
                "round_id": round_id,
                "problem_id": problem['id'],
                "code": solution,
                "language": "python"
            }
            try:
                requests.post(f"{BASE_URL}/coding/run", json=run_payload, headers=headers)
            except:
                pass
        
        # Now submit the actual solution
        print(f"  Submitting actual solution...")
        submit_payload = {
            "round_id": round_id,
            "problem_id": problem['id'],
            "code": solution,
            "language": "python"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                print(f"  ✓ Submission successful")
                print(f"    Verdict: {result['verdict']}")
                print(f"    Score: {result['score']}")
                
                if result['verdict'] == 'accepted':
                    solved_count += 1
                    print(f"    🎉 PROBLEM SOLVED! ({solved_count}/{total_problems})")
                else:
                    print(f"    ⚠️  Not fully solved")
            else:
                print(f"  ✗ Submission failed: {response.status_code}")
        except Exception as e:
            print(f"  ✗ Submission error: {e}")
        
        # Check session status after each submission
        try:
            response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
            data = response.json()
            all_solved = data.get('all_problems_solved', False)
            print(f"    All problems solved: {all_solved}")
            
            if all_solved:
                print(f"    🎯 END TEST BUTTON SHOULD NOW BE VISIBLE!")
                break
        except Exception as e:
            print(f"    ✗ Status check error: {e}")
    
    # Step 5: End round and check final results
    print(f"\n{3+len(problems)+1}. Ending round and checking results...")
    try:
        response = requests.post(f"{BASE_URL}/coding/session/{round_id}/end", headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Round ended successfully")
            print(f"\n📊 FINAL RESULTS:")
            print(f"  Total Problems: {result['problems_attempted']} (should be {total_problems})")
            print(f"  Problems Solved: {result['problems_solved']} (should be {solved_count})")
            print(f"  Total Score: {result['total_score']}")
            
            # Verify the counts are correct
            if result['problems_attempted'] == total_problems:
                print(f"  ✅ Total Problems count is CORRECT")
            else:
                print(f"  ❌ Total Problems count is WRONG (expected {total_problems}, got {result['problems_attempted']})")
            
            if result['problems_solved'] == solved_count:
                print(f"  ✅ Problems Solved count is CORRECT")
            else:
                print(f"  ❌ Problems Solved count is WRONG (expected {solved_count}, got {result['problems_solved']})")
                
        else:
            print(f"✗ End round failed: {response.status_code}")
    except Exception as e:
        print(f"✗ End round error: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nExpected Behavior:")
    print("1. 'Total Problems' should show total problems in test (2)")
    print("2. 'Problems Solved' should show only 100% score problems")
    print("3. Run attempts should NOT be counted")
    print("4. End Test button should appear immediately after solving last problem")
    print("5. Result page should show 'Total Problems' instead of 'Problems Attempted'")

if __name__ == "__main__":
    test_final_fixes()