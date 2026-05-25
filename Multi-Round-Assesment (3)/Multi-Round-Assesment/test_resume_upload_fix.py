"""
Test script to verify resume upload fixes are working.
"""

import sys

def test_groq_service():
    """Test Groq service can be imported and initialized."""
    try:
        from app.services.groq_service import GroqService
        from app.config.settings import settings
        
        if not settings.GROQ_API_KEY:
            print("⚠ GROQ_API_KEY not set in .env (interview features will use fallback)")
            return True
        
        service = GroqService(settings.GROQ_API_KEY)
        print("✓ Groq service initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Groq service error: {e}")
        return False


def test_rag_service():
    """Test RAG service can be imported and initialized."""
    try:
        from app.services.rag_service import RAGOrchestrator
        from app.config.settings import settings
        
        if not settings.GROQ_API_KEY:
            print("⚠ GROQ_API_KEY not set (RAG will use fallback)")
            return True
        
        rag = RAGOrchestrator(settings.GROQ_API_KEY)
        print("✓ RAG service initialized successfully")
        return True
    except Exception as e:
        print(f"✗ RAG service error: {e}")
        return False


def test_database_tables():
    """Test that required tables exist."""
    try:
        from app.database.db import engine
        from sqlalchemy import text
        
        conn = engine.connect()
        
        # Check approved_question_pools
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='approved_question_pools')"
        ))
        pools_exists = result.fetchone()[0]
        
        # Check interview_turns
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='interview_turns')"
        ))
        turns_exists = result.fetchone()[0]
        
        # Check interview_sessions
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='interview_sessions')"
        ))
        sessions_exists = result.fetchone()[0]
        
        conn.close()
        
        if pools_exists and turns_exists and sessions_exists:
            print("✓ All interview tables exist")
            return True
        else:
            print(f"✗ Missing tables:")
            if not pools_exists:
                print("  - approved_question_pools")
            if not turns_exists:
                print("  - interview_turns")
            if not sessions_exists:
                print("  - interview_sessions")
            return False
            
    except Exception as e:
        print(f"✗ Database check error: {e}")
        return False


def test_interview_router():
    """Test that interview router is properly configured."""
    try:
        from app.modules.interview.routers.interview_router import router
        
        routes = [r.path for r in router.routes]
        required_routes = [
            '/resume/upload',
            '/session/start',
            '/session/{interview_id}/next',
            '/session/{interview_id}/respond',
            '/stt',
            '/tts',
        ]
        
        missing = [r for r in required_routes if not any(r in route for route in routes)]
        
        if not missing:
            print(f"✓ Interview router has all {len(routes)} required endpoints")
            return True
        else:
            print(f"✗ Missing routes: {missing}")
            return False
            
    except Exception as e:
        print(f"✗ Router check error: {e}")
        return False


def test_models():
    """Test that interview models can be imported."""
    try:
        from app.models.interview import (
            InterviewSession,
            ApprovedQuestionPool,
            InterviewTurn
        )
        print("✓ Interview models imported successfully")
        return True
    except Exception as e:
        print(f"✗ Model import error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("RESUME UPLOAD FIX VERIFICATION")
    print("=" * 70)
    print()
    
    tests = [
        ("Groq Service", test_groq_service),
        ("RAG Service", test_rag_service),
        ("Database Tables", test_database_tables),
        ("Interview Router", test_interview_router),
        ("Interview Models", test_models),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"Testing {name}...")
        passed = test_func()
        results.append((name, passed))
        print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print()
    print(f"Passed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print()
        print("✓ All tests passed! Resume upload should work correctly.")
        print()
        print("Next steps:")
        print("1. Start backend: uvicorn app.main:app --reload")
        print("2. Start frontend: cd frontend && npm run dev")
        print("3. Test resume upload at http://localhost:5173")
        return 0
    else:
        print()
        print("✗ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
