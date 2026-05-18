"""
Test that End Test button appears immediately after solving last problem
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_end_button_timing():
    print("=" * 70)
    print("TESTING END BUTTON TIMING")
    print("=" * 70)
    
    # Login
    login_data = {"email": "testuser@example.com", "password": "testpass123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Start fresh session
    response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
    round_id = response.json()["round_id"]
    print(f"Started round {round_id}")
    
    # Get problems
    response = requests.get(f"{BASE_URL}/coding/problems/{round_id}", headers=headers)
    problems = response.json()
    print(f"Got {len(problems)} problems:")
    for p in problems:
        print(f"  - {p['title']}")
    
    # Solve first problem
    print(f"\n1. Solving first problem: {problems[0]['title']}")
    
    first_solution = """n = int(input())
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

print(result)"""
    
    submit_payload = {
        "round_id": round_id,
        "problem_id": problems[0]['id'],
        "code": first_solution,
        "language": "python"
    }
    
    response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
    result = response.json()
    print(f"First submission: {result['verdict']} (Score: {result['score']})")
    
    # Check status after first problem
    response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    data = response.json()
    print(f"After first problem - All solved: {data['all_problems_solved']}")
    
    # Solve second problem
    print(f"\n2. Solving second problem: {problems[1]['title']}")
    
    second_solution = """n = int(input())
arr = list(map(int, input().split()))
total = sum(arr)
print(total)"""
    
    submit_payload['problem_id'] = problems[1]['id']
    submit_payload['code'] = second_solution
    
    response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
    result = response.json()
    print(f"Second submission: {result['verdict']} (Score: {result['score']})")
    
    # Check status IMMEDIATELY after second problem
    print(f"\n3. Checking status IMMEDIATELY after second submission...")
    response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    data = response.json()
    
    print(f"All problems solved: {data['all_problems_solved']}")
    print(f"Problem statuses:")
    for p in data['problems']:
        print(f"  - {p['title']}: {p['status']}")
    
    if data['all_problems_solved']:
        print(f"\n🎉 SUCCESS! End Test button should be visible immediately!")
    else:
        print(f"\n⚠️  End Test button will still be hidden")
        
        # Check individual problem statuses
        accepted_count = sum(1 for p in data['problems'] if p['status'] == 'accepted')
        print(f"Problems with 'accepted' status: {accepted_count}/{len(data['problems'])}")
    
    print("\n" + "=" * 70)
    print("FRONTEND TEST INSTRUCTIONS:")
    print("=" * 70)
    print("1. Open http://localhost:3000")
    print("2. Login and start a coding round")
    print("3. Solve the first problem - End button should be HIDDEN")
    print("4. Solve the second problem - End button should appear IMMEDIATELY")
    print("5. Button should be green and say 'Complete Assessment'")

if __name__ == "__main__":
    test_end_button_timing()