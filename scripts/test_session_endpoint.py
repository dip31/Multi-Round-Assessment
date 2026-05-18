"""
Test the session endpoint directly to debug the all_problems_solved field
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_session_endpoint():
    print("Testing session endpoint...")
    
    # Login
    login_data = {"email": "testuser@example.com", "password": "testpass123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test session endpoint
    try:
        response = requests.get(f"{BASE_URL}/coding/session/40", headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response keys:", list(data.keys()))
            print("all_problems_solved field:", data.get('all_problems_solved', 'MISSING'))
            
            # Check problem statuses
            print("\nProblem statuses:")
            for p in data.get('problems', []):
                print(f"  {p['title']}: {p['status']}")
        else:
            print("Error:", response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_session_endpoint()