"""
Verify Problem Bank Script

Checks the database to verify that problems and test cases were seeded correctly.

Usage:
    python -m scripts.verify_problem_bank
"""

import os
import sys

# ── Ensure project root is on sys.path ───────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Imports ───────────────────────────────────────────────────────────────────
from sqlalchemy import func
from app.database.db import SessionLocal
from app.models.coding import CodingProblem, CodingTestCase


def verify() -> None:
    """Verify the seeded data in the database."""
    db = SessionLocal()
    
    try:
        # Count problems
        problem_count = db.query(func.count(CodingProblem.id)).scalar()
        
        # Count test cases
        testcase_count = db.query(func.count(CodingTestCase.id)).scalar()
        
        # Count by difficulty
        easy_count = db.query(func.count(CodingProblem.id)).filter(
            CodingProblem.difficulty == "easy"
        ).scalar()
        
        medium_count = db.query(func.count(CodingProblem.id)).filter(
            CodingProblem.difficulty == "medium"
        ).scalar()
        
        hard_count = db.query(func.count(CodingProblem.id)).filter(
            CodingProblem.difficulty == "hard"
        ).scalar()
        
        # Count visible vs hidden test cases
        visible_count = db.query(func.count(CodingTestCase.id)).filter(
            CodingTestCase.is_hidden == False
        ).scalar()
        
        hidden_count = db.query(func.count(CodingTestCase.id)).filter(
            CodingTestCase.is_hidden == True
        ).scalar()
        
        # Display results
        print("\n" + "=" * 60)
        print("  PROBLEM BANK VERIFICATION")
        print("=" * 60)
        print(f"\n  Total Problems:      {problem_count}")
        print(f"  Total Test Cases:    {testcase_count}")
        print(f"\n  Difficulty Breakdown:")
        print(f"    - Easy:            {easy_count}")
        print(f"    - Medium:          {medium_count}")
        print(f"    - Hard:            {hard_count}")
        print(f"\n  Test Case Breakdown:")
        print(f"    - Visible:         {visible_count}")
        print(f"    - Hidden:          {hidden_count}")
        print("\n" + "=" * 60)
        
        # Sample problems
        print("\n  Sample Problems:")
        print("  " + "-" * 56)
        
        sample_problems = db.query(CodingProblem).limit(5).all()
        for prob in sample_problems:
            tc_count = db.query(func.count(CodingTestCase.id)).filter(
                CodingTestCase.problem_id == prob.id
            ).scalar()
            print(f"    [{prob.difficulty:6}] {prob.title} ({tc_count} test cases)")
        
        print("  " + "-" * 56)
        print()
        
        # Validation
        if problem_count == 20 and testcase_count == 140:
            print("  ✅ SUCCESS: Expected 20 problems and 140 test cases found!")
        elif problem_count == 0:
            print("  ⚠️  WARNING: No problems found. Run seed script first.")
        else:
            print(f"  ⚠️  WARNING: Expected 20 problems and 140 test cases,")
            print(f"              but found {problem_count} problems and {testcase_count} test cases.")
        
        print()
        
    finally:
        db.close()


if __name__ == "__main__":
    verify()
