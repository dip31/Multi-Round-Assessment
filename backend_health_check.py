"""
Backend Health Check Script

Comprehensive health check for the AI Placement Platform backend.
Verifies all critical components and connections.
"""

import sys
from typing import Dict, List, Tuple


def check_imports() -> Tuple[bool, str]:
    """Check if all critical imports work."""
    try:
        from app.main import app
        from app.api.v1.router import api_router
        from app.database.db import engine
        from app.config.settings import settings
        return True, "All imports successful"
    except Exception as e:
        return False, f"Import error: {str(e)}"


def check_database() -> Tuple[bool, str]:
    """Check database connection."""
    try:
        from app.database.db import engine
        from sqlalchemy import text
        
        conn = engine.connect()
        conn.execute(text('SELECT 1'))
        conn.close()
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database error: {str(e)}"


def check_api_routes() -> Tuple[bool, str]:
    """Check if all API routes are registered."""
    try:
        from app.main import app
        
        routes = [r for r in app.routes if hasattr(r, 'path')]
        if len(routes) < 20:
            return False, f"Only {len(routes)} routes found (expected 25+)"
        
        return True, f"{len(routes)} API routes registered"
    except Exception as e:
        return False, f"Route check error: {str(e)}"


def check_critical_endpoints() -> Tuple[bool, str]:
    """Check if critical endpoints exist."""
    try:
        from app.main import app
        
        critical_paths = [
            '/api/v1/auth/register',
            '/api/v1/auth/login',
            '/api/v1/session/start',
            '/api/v1/aptitude/next-question',
            '/api/v1/interview/resume/upload',
        ]
        
        all_paths = [r.path for r in app.routes if hasattr(r, 'path')]
        missing = [p for p in critical_paths if p not in all_paths]
        
        if missing:
            return False, f"Missing endpoints: {', '.join(missing)}"
        
        return True, "All critical endpoints present"
    except Exception as e:
        return False, f"Endpoint check error: {str(e)}"


def check_environment() -> Tuple[bool, str]:
    """Check environment configuration."""
    try:
        from app.config.settings import settings
        
        issues = []
        
        if not settings.DATABASE_URL:
            issues.append("DATABASE_URL not set")
        
        if settings.SECRET_KEY == "change-me-in-production":
            issues.append("SECRET_KEY using default value (security risk)")
        
        if not settings.GROQ_API_KEY:
            issues.append("GROQ_API_KEY not set (interview features disabled)")
        
        if not settings.SARVAM_API_KEY:
            issues.append("SARVAM_API_KEY not set (TTS disabled)")
        
        if issues:
            return False, "; ".join(issues)
        
        return True, "Environment properly configured"
    except Exception as e:
        return False, f"Environment check error: {str(e)}"


def check_models() -> Tuple[bool, str]:
    """Check if database models are properly defined."""
    try:
        from app.models.user import User
        from app.models.assessment import AssessmentSession, AssessmentRound
        from app.models.aptitude import AptitudeQuestion, AptitudeAttempt
        from app.models.interview import InterviewSession, ApprovedQuestionPool
        from app.models.proctoring import ProctoringEvent
        from app.models.advanced_proctoring import AdvancedProctoringEvent
        
        return True, "All database models loaded"
    except Exception as e:
        return False, f"Model error: {str(e)}"


def run_health_check():
    """Run all health checks and display results."""
    
    print("=" * 70)
    print("BACKEND HEALTH CHECK")
    print("=" * 70)
    
    checks = [
        ("Imports", check_imports),
        ("Database Connection", check_database),
        ("API Routes", check_api_routes),
        ("Critical Endpoints", check_critical_endpoints),
        ("Database Models", check_models),
        ("Environment Config", check_environment),
    ]
    
    results: List[Dict] = []
    all_passed = True
    
    for name, check_func in checks:
        print(f"\nChecking {name}...", end=" ")
        passed, message = check_func()
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(status)
        print(f"  {message}")
        
        results.append({
            "name": name,
            "passed": passed,
            "message": message,
        })
        
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print(f"\nPassed: {passed_count}/{total_count}")
    
    if all_passed:
        print("\n✓ All checks passed! Backend is ready to run.")
        print("\nTo start the server:")
        print("  uvicorn app.main:app --reload")
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        print("\nFailed checks:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['name']}: {r['message']}")
        return 1


if __name__ == "__main__":
    sys.exit(run_health_check())
