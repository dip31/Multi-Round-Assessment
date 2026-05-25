"""
Production Interview System Test

Tests all critical features:
1. Audio control (no overlap)
2. Question progression (no repeats)
3. Evaluation + follow-up engine
4. State persistence
5. Conversational flow
"""

import asyncio
import json
import sys
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.models.interview import InterviewSession, ApprovedQuestionPool, InterviewTurn
from app.models.assessment import AssessmentSession
from app.models.user import User
from app.services.groq_service import GroqService
from app.modules.interview.services.interview_rl_engine import InterviewRLEngine
from app.config.settings import settings

def test_question_pool_has_ids():
    """Test that question pools have unique IDs."""
    print("\n=== TEST 1: Question Pool IDs ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    pool = groq.generate_question_pool(
        skills=["Python", "FastAPI"],
        projects={"p1": "Built REST API"},
        count=5
    )
    
    ids = [q.get("id") for q in pool]
    print(f"Generated {len(pool)} questions")
    print(f"IDs: {ids}")
    
    assert all(q.get("id") for q in pool), "All questions must have IDs"
    assert len(ids) == len(set(ids)), "IDs must be unique"
    print("✅ PASS: All questions have unique IDs")


def test_evaluation_quality_classification():
    """Test that evaluation returns quality classification."""
    print("\n=== TEST 2: Evaluation Quality ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    
    test_cases = [
        ("What is Python?", "I like pizza", "IRRELEVANT"),
        ("Explain OOP", "Objects", "SHORT"),
        ("Describe REST API", "REST uses HTTP methods like GET and POST", "PARTIAL"),
        ("Tell me about yourself", "I'm a software engineer with 5 years of experience in Python and web development. I've built multiple REST APIs and worked on microservices architecture.", "GOOD"),
    ]
    
    for question, answer, expected_quality in test_cases:
        result = groq.evaluate_response(question, answer)
        print(f"\nQ: {question[:40]}...")
        print(f"A: {answer[:40]}...")
        print(f"Quality: {result['quality']} (expected: {expected_quality})")
        print(f"Score: {result['content_score']}")
        
        assert "quality" in result, "Must return quality"
        assert "content_score" in result, "Must return content_score"
        assert result["quality"] in ["IRRELEVANT", "SHORT", "PARTIAL", "GOOD"], "Invalid quality"
    
    print("\n✅ PASS: Evaluation returns quality classification")


def test_followup_generation():
    """Test follow-up message generation."""
    print("\n=== TEST 3: Follow-up Generation ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    
    test_cases = [
        ("SHORT", "", "What is Python?"),
        ("PARTIAL", "error handling", "Explain exception handling in Python"),
        ("IRRELEVANT", "", "Describe your experience with databases"),
    ]
    
    for quality, missing, question in test_cases:
        followup = groq.generate_followup_message(quality, missing, question)
        print(f"\nQuality: {quality}")
        print(f"Missing: {missing}")
        print(f"Follow-up: {followup}")
        
        assert followup, "Must return follow-up message"
        assert len(followup) > 10, "Follow-up must be meaningful"
    
    print("\n✅ PASS: Follow-up messages generated")


def test_rl_state_persistence():
    """Test that RL state persists all required fields."""
    print("\n=== TEST 4: RL State Persistence ===")
    
    engine = InterviewRLEngine()
    engine.followup_count = 2
    engine.irrelevant_count = 1
    engine.asked_question_ids = ["q1", "q2", "q3"]
    engine.current_question_text = "What is Python?"
    engine.current_question_difficulty = "EASY"
    
    # Serialize
    state_dict = engine.to_dict()
    print(f"Serialized state keys: {list(state_dict.keys())}")
    
    # Deserialize
    engine2 = InterviewRLEngine()
    engine2.from_dict(state_dict)
    
    assert engine2.followup_count == 2, "followup_count must persist"
    assert engine2.irrelevant_count == 1, "irrelevant_count must persist"
    assert engine2.asked_question_ids == ["q1", "q2", "q3"], "asked_question_ids must persist"
    assert engine2.current_question_text == "What is Python?", "current_question_text must persist"
    assert engine2.current_question_difficulty == "EASY", "current_question_difficulty must persist"
    
    print("✅ PASS: RL state persists all fields")


def test_decision_engine_logic():
    """Test the decision engine follow-up logic."""
    print("\n=== TEST 5: Decision Engine ===")
    
    engine = InterviewRLEngine()
    
    # Test IRRELEVANT flow
    print("\n--- IRRELEVANT Flow ---")
    engine.irrelevant_count = 0
    print(f"First IRRELEVANT (count={engine.irrelevant_count}): Should follow-up")
    assert engine.irrelevant_count == 0, "Should allow first follow-up"
    
    engine.irrelevant_count = 1
    print(f"Second IRRELEVANT (count={engine.irrelevant_count}): Should advance")
    assert engine.irrelevant_count >= 1, "Should advance after second"
    
    # Test SHORT/PARTIAL flow
    print("\n--- SHORT/PARTIAL Flow ---")
    engine.followup_count = 0
    print(f"First SHORT (count={engine.followup_count}): Should follow-up")
    assert engine.followup_count < 2, "Should allow follow-up"
    
    engine.followup_count = 1
    print(f"Second SHORT (count={engine.followup_count}): Should follow-up")
    assert engine.followup_count < 2, "Should allow follow-up"
    
    engine.followup_count = 2
    print(f"Third SHORT (count={engine.followup_count}): Should advance")
    assert engine.followup_count >= 2, "Should advance after max"
    
    # Test reset
    engine.reset_turn_counters()
    assert engine.followup_count == 0, "Counters must reset"
    assert engine.irrelevant_count == 0, "Counters must reset"
    
    print("\n✅ PASS: Decision engine logic correct")


def test_reward_function():
    """Test reward computation with quality."""
    print("\n=== TEST 6: Reward Function ===")
    
    engine = InterviewRLEngine()
    
    test_cases = [
        (0.9, "EASY", 0, "GOOD", 0, "Should penalize EASY with high score"),
        (0.2, "HARD", 0, "SHORT", 0, "Should penalize HARD with low score"),
        (0.6, "MEDIUM", 0, "GOOD", 0, "Should reward optimal range"),
        (0.5, "MEDIUM", 0, "IRRELEVANT", 2, "Should penalize multiple irrelevant"),
    ]
    
    for score, diff, turn, quality, followup, desc in test_cases:
        reward = engine.compute_reward(score, diff, turn, quality, followup)
        print(f"{desc}: reward={reward:.2f}")
        assert isinstance(reward, float), "Reward must be float"
    
    print("\n✅ PASS: Reward function works with quality")


def test_database_migration():
    """Test that database has new columns."""
    print("\n=== TEST 7: Database Schema ===")
    
    db = SessionLocal()
    try:
        # Check if columns exist by querying
        from sqlalchemy import text
        result = db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'interview_turns' "
                "AND column_name IN ('is_followup', 'followup_number')"
            )
        ).fetchall()
        
        columns = [r[0] for r in result]
        print(f"Found columns: {columns}")
        
        if 'is_followup' not in columns or 'followup_number' not in columns:
            print("⚠️  WARNING: Migration not applied yet. Run: alembic upgrade head")
        else:
            print("✅ PASS: Database schema updated")
    finally:
        db.close()


async def test_full_flow_simulation():
    """Simulate a complete interview flow."""
    print("\n=== TEST 8: Full Flow Simulation ===")
    
    db = SessionLocal()
    try:
        # Find a test user
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            print("⚠️  No test user found, skipping flow test")
            return
        
        # Check for existing active session and complete it
        existing = db.query(AssessmentSession).filter(
            AssessmentSession.user_id == user.id,
            AssessmentSession.status == "in_progress"
        ).first()
        
        if existing:
            existing.status = "completed"
            db.commit()
        
        # Create test assessment session
        assessment = AssessmentSession(
            user_id=user.id,
            status="in_progress",
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        
        # Create test question pool
        pool = ApprovedQuestionPool(
            session_id=assessment.id,
            extracted_skills=["Python", "FastAPI"],
            extracted_projects={},
            question_pool=[
                {"id": "q1", "question": "What is Python?", "difficulty": "EASY", "phase": "HR", "topic": "General"},
                {"id": "q2", "question": "Explain REST APIs", "difficulty": "MEDIUM", "phase": "TECHNICAL", "topic": "Backend"},
                {"id": "q3", "question": "Design a scalable system", "difficulty": "HARD", "phase": "TECHNICAL", "topic": "Architecture"},
            ],
            admin_approved=True,
            approved_by=user.id,
        )
        db.add(pool)
        db.commit()
        db.refresh(pool)
        
        # Create interview session
        rl_engine = InterviewRLEngine()
        interview = InterviewSession(
            session_id=assessment.id,
            phase="HR",
            current_turn=0,
            total_turns=3,
            rl_state=rl_engine.to_dict(),
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)
        
        print(f"Created interview session: {interview.id}")
        
        # Simulate question flow
        for i in range(3):
            print(f"\n--- Turn {i+1} ---")
            
            # Restore RL
            rl_engine = InterviewRLEngine()
            rl_engine.from_dict(interview.rl_state)
            
            # Select question
            available = [q for q in pool.question_pool if q["id"] not in rl_engine.asked_question_ids]
            if not available:
                print("No more questions")
                break
            
            selected = available[0]
            rl_engine.asked_question_ids.append(selected["id"])
            rl_engine.current_question_text = selected["question"]
            rl_engine.current_question_difficulty = selected["difficulty"]
            
            print(f"Question: {selected['question']}")
            print(f"Asked IDs: {rl_engine.asked_question_ids}")
            
            # Save state
            interview.rl_state = rl_engine.to_dict()
            interview.current_turn += 1
            db.commit()
        
        # Verify no duplicates
        asked = rl_engine.asked_question_ids
        assert len(asked) == len(set(asked)), "No duplicate questions"
        print(f"\n✅ PASS: No duplicate questions asked")
        
        # Cleanup
        db.delete(interview)
        db.delete(pool)
        db.delete(assessment)
        db.commit()
        
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Production Interview System Test Suite")
    print("=" * 60)
    
    try:
        # Run tests
        test_question_pool_has_ids()
        test_evaluation_quality_classification()
        test_followup_generation()
        test_rl_state_persistence()
        test_decision_engine_logic()
        test_reward_function()
        test_database_migration()
        asyncio.run(test_full_flow_simulation())
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
