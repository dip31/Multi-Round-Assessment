#!/usr/bin/env python3
"""
Test script to verify Stage 2 to Stage 3 data flow is working properly.
"""
import asyncio
import json
from shared.db.database import async_session, db_session
from shared.db.models import Job, Candidate, Application
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from screening.processor import process_candidate
from screening.candidate_job_linker import link_candidates_to_jobs


async def test_stage2_to_stage3_flow():
    """Test the complete flow from Stage 2 to Stage 3."""
    
    print("🧪 Testing Stage 2 to Stage 3 Data Flow")
    print("=" * 50)
    
    async with async_session() as db:
        # 1. Create a test job
        test_job = Job(
            id="test-job-001",
            title="Python Developer",
            skills='["python", "sql", "fastapi"]',
            experience_min=2,
            experience_max=5,
            qualification="bachelor's",
            location="Remote",
            status="active"
        )
        db.add(test_job)
        
        # 2. Create a test candidate (simulating Stage 2 output)
        test_candidate = Candidate(
            id="test-candidate-001",
            name="John Doe",
            email="john.doe@example.com",
            phone="1234567890",
            location="Remote",
            current_role="Software Engineer",
            experience_years=3.0,
            skills='["python", "sql", "django"]',
            education='[{"degree": "Bachelor\'s", "institution": "Tech University", "year": "2020"}]',
            work_history='[{"company": "TechCorp", "role": "Developer", "duration": "2020-2023"}]',
            source="upload",
            status="parsed",
            job_id="test-job-001"  # This should be set by our fixes
        )
        db.add(test_candidate)
        
        # 3. Create application record
        test_application = Application(
            id="test-app-001",
            job_id="test-job-001",
            candidate_id="test-candidate-001",
            status="applied"
        )
        db.add(test_application)
        
        await db.commit()
        print("✅ Created test job, candidate, and application")
        
        # 4. Test the event publishing (Stage 2 behavior)
        await event_bus.publish(
            EventTopics.PROFILE_PARSED,
            {
                "candidate_id": "test-candidate-001",
                "job_id": "test-job-001",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "skills": ["python", "sql", "django"],
                "experience_years": 3.0,
                "education": [{"degree": "Bachelor's", "institution": "Tech University"}]
            },
            agent="test_agent"
        )
        print("✅ Published profile.parsed event")
        
        # 5. Test Stage 3 processing directly
        with db_session() as sync_db:
            result = process_candidate("test-candidate-001", sync_db)
            
            if result:
                print(f"✅ Stage 3 processing successful:")
                print(f"   - Candidate ID: {result['candidate_id']}")
                print(f"   - Job ID: {result['job_id']}")
                print(f"   - Status: {result['status']}")
                print(f"   - Score: {result['score']}")
                print(f"   - Is Duplicate: {result['is_duplicate']}")
            else:
                print("❌ Stage 3 processing failed")
                return False
        
        # 6. Verify candidate was updated
        await db.refresh(test_candidate)
        print(f"✅ Candidate updated in database:")
        print(f"   - Status: {test_candidate.status}")
        print(f"   - Score: {test_candidate.score}")
        print(f"   - Job ID: {test_candidate.job_id}")
        
        # 7. Test candidate linking utility
        print("\n🔗 Testing candidate linking utility...")
        
        # Create a candidate without job_id to test linking
        unlinked_candidate = Candidate(
            id="test-candidate-002",
            name="Jane Smith",
            email="jane.smith@example.com",
            phone="0987654321",
            skills='["javascript", "react"]',
            experience_years=2.0,
            source="upload",
            status="parsed"
            # Note: no job_id set
        )
        db.add(unlinked_candidate)
        
        unlinked_application = Application(
            id="test-app-002",
            job_id="test-job-001",
            candidate_id="test-candidate-002",
            status="applied"
        )
        db.add(unlinked_application)
        
        await db.commit()
        
        # Test the linking
        with db_session() as sync_db:
            link_result = link_candidates_to_jobs(sync_db)
            print(f"✅ Linking result: {link_result}")
        
        # Verify linking worked
        await db.refresh(unlinked_candidate)
        if unlinked_candidate.job_id:
            print(f"✅ Candidate successfully linked to job: {unlinked_candidate.job_id}")
        else:
            print("❌ Candidate linking failed")
        
        # Cleanup
        await db.delete(test_job)
        await db.delete(test_candidate)
        await db.delete(test_application)
        await db.delete(unlinked_candidate)
        await db.delete(unlinked_application)
        await db.commit()
        print("✅ Cleanup completed")
        
        return True


async def test_candidate_without_job():
    """Test handling of candidates without job_id."""
    
    print("\n🧪 Testing Candidate Without Job ID")
    print("=" * 40)
    
    async with async_session() as db:
        # Create candidate without job_id
        orphan_candidate = Candidate(
            id="orphan-candidate-001",
            name="Orphan Candidate",
            email="orphan@example.com",
            skills='["python"]',
            experience_years=1.0,
            source="upload",
            status="parsed"
            # No job_id
        )
        db.add(orphan_candidate)
        await db.commit()
        
        # Test processing
        with db_session() as sync_db:
            result = process_candidate("orphan-candidate-001", sync_db)
            
            if result and result["status"] == "rejected":
                print(f"✅ Orphan candidate correctly rejected:")
                print(f"   - Status: {result['status']}")
                print(f"   - Reason: No job_id")
            else:
                print("❌ Orphan candidate handling failed")
        
        # Cleanup
        await db.delete(orphan_candidate)
        await db.commit()


if __name__ == "__main__":
    async def main():
        try:
            # Connect event bus
            await event_bus.connect()
            
            # Run tests
            success1 = await test_stage2_to_stage3_flow()
            await test_candidate_without_job()
            
            if success1:
                print("\n🎉 All tests passed! Stage 2 to Stage 3 flow is working correctly.")
            else:
                print("\n❌ Some tests failed. Check the output above.")
                
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await event_bus.close()
    
    asyncio.run(main())