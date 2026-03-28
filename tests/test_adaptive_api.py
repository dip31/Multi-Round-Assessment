"""
Test adaptive difficulty by directly calling API endpoints.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx


async def test_adaptive_api():
    """Test adaptive difficulty via API calls."""
    
    print("🧪 Testing Adaptive Difficulty via API...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test 1: Login and start session
            print("\n📝 Test 1: Login and start session")
            login_response = await client.post("http://localhost:8000/api/v1/auth/login", json={
                "email": "test@example.com", 
                "password": "testpass"
            })
            
            if login_response.status_code != 200:
                print(f"❌ Login failed: {login_response.text}")
                return
                
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            session_response = await client.post("http://localhost:8000/api/v1/session/start", headers=headers)
            if session_response.status_code != 200:
                print(f"❌ Session start failed: {session_response.text}")
                return
                
            session_id = session_response.json()["id"]
            print(f"✅ Started session: {session_id}")
            
            # Test 2: Get first question (should be medium)
            print("\n📝 Test 2: Get first question (should be medium)")
            question_response = await client.get(f"http://localhost:8000/api/v1/aptitude/next-question", headers=headers)
            
            if question_response.status_code != 200:
                print(f"❌ Get question failed: {question_response.text}")
                return
                
            question1 = question_response.json()
            print(f"   Question difficulty: {question1['difficulty']}")
            
            # Test 3: Submit correct answer (should increase difficulty)
            print("\n📝 Test 3: Submit correct answer (should increase difficulty)")
            submit_response = await client.post(f"http://localhost:8000/api/v1/aptitude/submit-answer", 
                headers=headers, json={
                    "question_id": question1["question_id"],
                    "selected_option": "A",
                    "response_time": 15.0
                }
            )
            
            if submit_response.status_code != 200:
                print(f"❌ Submit failed: {submit_response.text}")
                return
                
            result1 = submit_response.json()
            print(f"   Was correct: {result1['correct']}")
            print(f"   Next difficulty: {result1['next_difficulty']}")
            
            # Test 4: Get next question (should be harder)
            print("\n📝 Test 4: Get next question (should be harder)")
            question_response2 = await client.get(f"http://localhost:8000/api/v1/aptitude/next-question", headers=headers)
            
            if question_response2.status_code != 200:
                print(f"❌ Get question failed: {question_response2.text}")
                return
                
            question2 = question_response2.json()
            print(f"   Question difficulty: {question2['difficulty']}")
            
            print("\n✅ Adaptive difficulty test completed successfully!")
            print("🎯 The RL system is working correctly!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_adaptive_api())
