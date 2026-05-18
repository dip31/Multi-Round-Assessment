#!/usr/bin/env python3
"""
Test End Test button logic with existing user or create new one
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def create_test_user():
    """Create a test user if it doesn't exist"""
    print("Creating test user...")
    
    register_data = {
        "email": "testuser@example.com",
        "password": "testpass123",
        "name": "Test User"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    
    if response.status_code == 201:
        print("✅ Test user created successfully")
        return True
    elif response.status_code == 409 and "already registered" in response.text:
        print("✅ Test user already exists")
        return True
    else:
        print(f"❌ Failed to create user: {response.status_code} - {response.text}")
        return False

def test_login():
    """Test login with correct credentials"""
    print("Testing login...")
    
    login_response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpass123"
    })
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        print("✅ Login successful")
        return token
    else:
        print(f"❌ Login failed: {login_response.status_code} - {login_response.text}")
        return None

def test_session_status(token):
    """Test session status and coding round"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Testing session status...")
    
    # Start session
    session_response = requests.post(f"{BASE_URL}/session/start", headers=headers)
    print(f"Session start: {session_response.status_code}")
    
    # Start coding round (restart if already active)
    coding_response = requests.post(f"{BASE_URL}/coding/restart-round", headers=headers)
    print(f"Coding round restart: {coding_response.status_code}")
    
    if coding_response.status_code != 200:
        # Try regular start if restart fails
        coding_response = requests.post(f"{BASE_URL}/coding/start-round", headers=headers)
        print(f"Coding round start: {coding_response.status_code}")
    
    if coding_response.status_code == 200:
        round_data = coding_response.json()
        round_id = round_data["round_id"]
        problems = round_data["problems"]
        
        print(f"✅ Coding round started with {len(problems)} problems")
        
        # Check session status
        status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"✅ Session status: all_problems_solved = {status_data['all_problems_solved']}")
            
            # Submit to first problem
            if len(problems) > 0:
                problem_id = problems[0]["id"]
                submit_response = requests.post(f"{BASE_URL}/coding/submit", 
                    headers=headers,
                    json={
                        "round_id": round_id,
                        "problem_id": problem_id,
                        "code": "print('hello')",
                        "language": "python"
                    }
                )
                print(f"First submission: {submit_response.status_code}")
                
                # Check status after first submission
                status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"After 1st submission: all_problems_solved = {status_data['all_problems_solved']}")
                    
                    # Submit to second problem if exists
                    if len(problems) > 1:
                        problem_id = problems[1]["id"]
                        submit_response = requests.post(f"{BASE_URL}/coding/submit", 
                            headers=headers,
                            json={
                                "round_id": round_id,
                                "problem_id": problem_id,
                                "code": "print('world')",
                                "language": "python"
                            }
                        )
                        print(f"Second submission: {submit_response.status_code}")
                        
                        # Check final status
                        status_response = requests.get(f"{BASE_URL}/coding/session/{round_id}", headers=headers)
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            print(f"After 2nd submission: all_problems_solved = {status_data['all_problems_solved']}")
                            print("✅ Expected: True (all problems submitted)")
                            
                            if status_data['all_problems_solved']:
                                print("🎉 SUCCESS: End Test button should now appear!")
                            else:
                                print("❌ ISSUE: End Test button logic not working")
        
        return True
    else:
        print(f"❌ Coding round failed: {coding_response.text}")
        return False

def main():
    print("🧪 Testing End Test Button Logic")
    print("=" * 50)
    
    # Step 1: Create user if needed
    if not create_test_user():
        return False
    
    # Step 2: Login
    token = test_login()
    if not token:
        return False
    
    # Step 3: Test session and submissions
    return test_session_status(token)

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")