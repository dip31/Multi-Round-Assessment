#!/usr/bin/env python3
"""
Simple test for End Test button logic
"""

import requests

BASE_URL = "http://localhost:8000/api/v1"

def main():
    print("🧪 Testing End Test Button Logic")
    print("=" * 50)
    
    # Login
    print("1. Logging in...")
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
    print("\n2. Restarting coding round...")
    restart_response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
    
    if restart_response.status_code not in [200, 201]:
        print(f"❌ Restart failed: {restart_response.status_code} - {restart_response.text}")
        return False
    
    round_data = restart_response.json()
    round_id = round_data["round_id"]
    problems = round_data["problems"]
    print(f"✅ Coding round restarted with {len(problems)} problems")
    
    # Check initial status
    print("\n3. Checking initial status...")
    status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    status_data = status_response.json()
    print(f"Initial all_problems_solved: {status_data['all_problems_solved']}")
    
    if status_data['all_problems_solved']:
        print("❌ ERROR: Should be False initially")
        return False
    
    # Submit first problem
    print("\n4. Submitting first problem...")
    submit1_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problems[0]["id"],
            "code": "print('hello')",
            "language": "python"
        }
    )
    
    if submit1_response.status_code != 200:
        print(f"❌ First submission failed: {submit1_response.status_code}")
        return False
    
    result1 = submit1_response.json()
    print(f"✅ First submission: {result1['verdict']}")
    
    # Check status after first submission
    status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    status_data = status_response.json()
    print(f"After 1st submission all_problems_solved: {status_data['all_problems_solved']}")
    
    if status_data['all_problems_solved']:
        print("❌ ERROR: Should be False after 1 submission")
        return False
    
    # Submit second problem
    print("\n5. Submitting second problem...")
    submit2_response = requests.post(f"{BASE_URL}/coding/submit", 
        headers=headers,
        json={
            "round_id": round_id,
            "problem_id": problems[1]["id"],
            "code": "print('world')",
            "language": "python"
        }
    )
    
    if submit2_response.status_code != 200:
        print(f"❌ Second submission failed: {submit2_response.status_code}")
        return False
    
    result2 = submit2_response.json()
    print(f"✅ Second submission: {result2['verdict']}")
    
    # Check final status
    print("\n6. Checking final status...")
    status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
    status_data = status_response.json()
    print(f"After 2nd submission all_problems_solved: {status_data['all_problems_solved']}")
    
    if not status_data['all_problems_solved']:
        print("❌ ERROR: Should be True after all submissions")
        return False
    
    print("\n🎉 SUCCESS: End Test button logic is working!")
    print("✅ End Test button should now appear in the frontend")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Test passed!")
    else:
        print("\n❌ Test failed!")