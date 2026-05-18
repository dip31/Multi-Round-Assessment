"""
Test the problem completion logic and end round functionality
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_problem_completion():
    print("=" * 70)
    print("TESTING PROBLEM COMPLETION LOGIC")
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
        for i, p in enumerate(problems, 1):
            print(f"  Problem {i}: {p['title']} (ID: {p['id']}) - Status: {p['status']}")
    except Exception as e:
        print(f"✗ Get problems error: {e}")
        return
    
    # Step 4: Check initial session status
    print("\n4. Checking initial session status...")
    try:
        response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
        data = response.json()
        print(f"✓ Session status retrieved")
        print(f"  All problems solved: {data.get('all_problems_solved', 'Not available')}")
        print(f"  Problems status:")
        for p in data['problems']:
            print(f"    - {p['title']}: {p['status']}")
    except Exception as e:
        print(f"✗ Session status error: {e}")
        return
    
    # Step 5: Submit solution for first problem
    print(f"\n5. Submitting solution for first problem (ID: {problems[0]['id']})...")
    
    # Simple solution that should work for most problems
    solution_code = """# Simple solution
n = int(input())
print(n)"""
    
    submit_payload = {
        "round_id": round_id,
        "problem_id": problems[0]['id'],
        "code": solution_code,
        "language": "python"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Submission successful")
            print(f"  Verdict: {result['verdict']}")
            print(f"  Score: {result['score']}")
            print(f"  Passed: {result['passed_cases']}/{result['total_cases']}")
        else:
            print(f"✗ Submission failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Submission error: {e}")
    
    # Step 6: Check session status after first submission
    print("\n6. Checking session status after first submission...")
    try:
        response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
        data = response.json()
        print(f"✓ Session status retrieved")
        print(f"  All problems solved: {data.get('all_problems_solved', 'Not available')}")
        print(f"  Problems status:")
        for p in data['problems']:
            print(f"    - {p['title']}: {p['status']}")
    except Exception as e:
        print(f"✗ Session status error: {e}")
    
    # Step 7: Submit solution for second problem
    if len(problems) > 1:
        print(f"\n7. Submitting solution for second problem (ID: {problems[1]['id']})...")
        
        submit_payload['problem_id'] = problems[1]['id']
        
        try:
            response = requests.post(f"{BASE_URL}/coding/submit", json=submit_payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Submission successful")
                print(f"  Verdict: {result['verdict']}")
                print(f"  Score: {result['score']}")
                print(f"  Passed: {result['passed_cases']}/{result['total_cases']}")
            else:
                print(f"✗ Submission failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Submission error: {e}")
        
        # Step 8: Check final session status
        print("\n8. Checking final session status...")
        try:
            response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
            data = response.json()
            print(f"✓ Session status retrieved")
            print(f"  All problems solved: {data.get('all_problems_solved', 'Not available')}")
            print(f"  Problems status:")
            for p in data['problems']:
                print(f"    - {p['title']}: {p['status']}")
                
            if data.get('all_problems_solved'):
                print("\n🎉 ALL PROBLEMS SOLVED! End Round button should now be visible.")
            else:
                print("\n⚠️  Not all problems solved yet. End Round button should be hidden.")
                
        except Exception as e:
            print(f"✗ Session status error: {e}")
    
    # Step 9: Test end round
    print(f"\n9. Testing end round...")
    try:
        response = requests.post(f"{BASE_URL}/coding/session/{round_id}/end", headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Round ended successfully")
            print(f"  Final status: {result['status']}")
            print(f"  Total score: {result['total_score']}")
            print(f"  Problems attempted: {result['problems_attempted']}")
            print(f"  Problems solved: {result['problems_solved']}")
        else:
            print(f"✗ End round failed: {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ End round error: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nKey Points to Verify:")
    print("1. 'All problems solved' flag should be true only when ALL problems have 'accepted' status")
    print("2. 'Problems attempted' should count only submitted problems (not run attempts)")
    print("3. 'Problems solved' should count only problems with score = 100")
    print("4. End Round button should only appear when all problems are solved")

if __name__ == "__main__":
    test_problem_completion()