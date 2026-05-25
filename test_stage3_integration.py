#!/usr/bin/env python3
"""
Test script to verify Stage 3 integration works end-to-end.
Creates a job, adds candidates, and runs screening.
"""
import asyncio
import json
import httpx

BASE_URL = "http://localhost:8000/api"

async def test_stage3_integration():
    """Test the complete Stage 1 → Stage 2 → Stage 3 flow."""
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing Stage 3 Integration...")
        
        # Step 1: Create a job (Stage 1)
        print("\n📋 Step 1: Creating a job...")
        job_data = {
            "title": "Senior Python Developer",
            "department": "Engineering",
            "location": "Bangalore",
            "experience_min": 3,
            "experience_max": 7,
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "qualification": "bachelor's"
        }
        
        response = await client.post(f"{BASE_URL}/intake/jobs", json=job_data)
        if response.status_code != 200:
            print(f"❌ Failed to create job: {response.text}")
            return
        
        job = response.json()
        job_id = job["job_id"]
        print(f"✅ Created job: {job_data['title']} (ID: {job_id})")
        
        # Step 2: Add test candidates (simulating Stage 2)
        print("\n👥 Step 2: Adding test candidates...")
        candidates_data = [
            {
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "phone": "+1234567890",
                "location": "Bangalore",
                "current_role": "Python Developer",
                "experience_years": 5,
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
                "education": "Bachelor's in Computer Science",
                "job_id": job_id,
                "source": "test"
            },
            {
                "name": "Bob Smith",
                "email": "bob@example.com", 
                "phone": "+1234567891",
                "location": "Mumbai",
                "current_role": "Software Engineer",
                "experience_years": 2,
                "skills": ["Python", "Django", "MySQL"],
                "education": "Master's in Software Engineering",
                "job_id": job_id,
                "source": "test"
            },
            {
                "name": "Carol Davis",
                "email": "carol@example.com",
                "phone": "+1234567892", 
                "location": "Bangalore",
                "current_role": "Senior Developer",
                "experience_years": 8,
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "React"],
                "education": "PhD in Computer Science",
                "job_id": job_id,
                "source": "test"
            }
        ]
        
        candidate_ids = []
        for candidate_data in candidates_data:
            # Manually insert candidate (simulating Stage 2 output)
            response = await client.post(f"{BASE_URL}/screening/test/add-candidate", json=candidate_data)
            if response.status_code == 200:
                candidate = response.json()
                candidate_ids.append(candidate["id"])
                print(f"✅ Added candidate: {candidate_data['name']}")
            else:
                print(f"❌ Failed to add candidate {candidate_data['name']}: {response.text}")
        
        if not candidate_ids:
            print("❌ No candidates added, cannot test screening")
            return
        
        # Step 3: Check screening stats before
        print("\n📊 Step 3: Checking initial screening stats...")
        response = await client.get(f"{BASE_URL}/screening/stats?job_id={job_id}")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Initial stats: {stats['total_candidates']} candidates, {stats['screened']} screened")
        
        # Step 4: Run screening (Stage 3)
        print("\n🔍 Step 4: Running screening...")
        screening_request = {
            "job_id": job_id,
            "force_rescreen": False
        }
        
        response = await client.post(f"{BASE_URL}/screening/run", json=screening_request)
        if response.status_code != 200:
            print(f"❌ Failed to run screening: {response.text}")
            return
        
        screening_result = response.json()
        print(f"✅ Screening completed: {screening_result['message']}")
        print(f"   Screened {screening_result['screened_count']} candidates")
        
        # Step 5: Check results
        print("\n📈 Step 5: Checking screening results...")
        response = await client.get(f"{BASE_URL}/screening/stats?job_id={job_id}")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Final stats:")
            print(f"   Total candidates: {stats['total_candidates']}")
            print(f"   Screened: {stats['screened']}")
            print(f"   Shortlisted: {stats['shortlisted']}")
            print(f"   Rejected: {stats['rejected']}")
            print(f"   Average score: {stats['avg_score']}")
        
        # Step 6: Get detailed candidate results
        print("\n👤 Step 6: Getting candidate details...")
        response = await client.get(f"{BASE_URL}/screening/candidates?job_id={job_id}")
        if response.status_code == 200:
            candidates = response.json()
            print(f"✅ Candidate screening results:")
            for candidate in candidates:
                status_emoji = "🟢" if candidate["status"] == "shortlisted" else "🔴" if candidate["status"] == "rejected" else "⚪"
                score = candidate["score"] if candidate["score"] is not None else "N/A"
                print(f"   {status_emoji} {candidate['name']}: {candidate['status']} (Score: {score})")
        
        print("\n🎉 Stage 3 integration test completed successfully!")
        print("✅ Job creation (Stage 1) → Candidate sourcing (Stage 2) → Screening (Stage 3) flow verified")

if __name__ == "__main__":
    asyncio.run(test_stage3_integration())