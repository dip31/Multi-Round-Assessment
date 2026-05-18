"""
Test with correct solutions to verify the completion logic
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_with_correct_solutions():
    print("=" * 70)
    print("TESTING WITH CORRECT SOLUTIONS")
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
    
    # Step 3: Get problems and their details
    print("\n3. Getting problems...")
    try:
        response = requests.get(f"{BASE_URL}/coding/problems/{round_id}", headers=headers)
        problems = response.json()
        print(f"✓ Got {len(problems)} problems")
        
        # Get details for each problem
        problem_details = []
        for p in problems:
            detail_response = requests.get(f"{BASE_URL}/coding/problem/{round_id}/{p['id']}", headers=headers)
            if detail_response.status_code == 200:
                detail = detail_response.json()
                problem_details.append(detail)
                print(f"  Problem: {detail['title']}")
                print(f"    Difficulty: {detail['difficulty']}")
                if detail['visible_test_cases']:
                    tc = detail['visible_test_cases'][0]
                    print(f"    Sample Input: {repr(tc['input_data'])}")
                    print(f"    Sample Output: {repr(tc['expected_output'])}")
        
    except Exception as e:
        print(f"✗ Get problems error: {e}")
        return
    
    # Step 4: Solve each problem with correct solutions
    solutions = {
        "Add Two Numbers": """a, b = map(int, input().split())
print(a + b)""",
        
        "Factorial of a Number": """n = int(input())
if n == 0 or n == 1:
    print(1)
else:
    result = 1
    for i in range(2, n + 1):
        result *= i
    print(result)""",
        
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
        
        "Count Vowels in a String": """s = input()
vowels = 'aeiouAEIOU'
count = sum(1 for c in s if c in vowels)
print(count)"""
    }
    
    for i, detail in enumerate(problem_details, 1):
        print(f"\n{3+i}. Solving problem: {detail['title']}")
        
        # Get the appropriate solution
        solution = solutions.get(detail['title'])
        if not solution:
            solution = """# Generic solution
n = int(input())
print(n)"""
            print(f"  Using generic solution (no specific solution available)")
        else:
            print(f"  Using specific solution")
        
        submit_payload = {
            "round_id": round_id,
            "problem_id": detail['id'],
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
                print(f"    Passed: {result['passed_cases']}/{result['total_cases']}")
                
                if result['verdict'] == 'accepted':
                    print(f"    🎉 PROBLEM SOLVED!")
                else:
                    print(f"    ⚠️  Not fully solved")
            else:
                print(f"  ✗ Submission failed: {response.status_code}")
                print(f"    Response: {response.text}")
        except Exception as e:
            print(f"  ✗ Submission error: {e}")
    
    # Step 5: Check final session status
    print(f"\n{3+len(problem_details)+1}. Checking final session status...")
    try:
        response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
        data = response.json()
        print(f"✓ Session status retrieved")
        print(f"  All problems solved: {data.get('all_problems_solved', 'Not available')}")
        print(f"  Problems status:")
        
        solved_count = 0
        for p in data['problems']:
            print(f"    - {p['title']}: {p['status']}")
            if p['status'] == 'accepted':
                solved_count += 1
        
        print(f"\n  Summary: {solved_count}/{len(data['problems'])} problems solved")
        
        if data.get('all_problems_solved'):
            print("\n🎉 ALL PROBLEMS SOLVED! End Round button should now be visible in frontend.")
        else:
            print(f"\n⚠️  Only {solved_count} problems solved. End Round button should be hidden.")
            
    except Exception as e:
        print(f"✗ Session status error: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nNow test the frontend:")
    print("1. Open http://localhost:3000")
    print("2. Login and go to the coding round")
    print("3. Check if 'End Round' button appears only when all problems are solved")
    print("4. Verify the button shows 'Complete Assessment' with green color")

if __name__ == "__main__":
    test_with_correct_solutions()