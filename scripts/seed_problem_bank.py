"""
Seed Problem Bank Script

Loads coding problems from problem_bank.json and inserts them into:
- coding_problems table
- coding_test_cases table

Usage:
    python -m scripts.seed_problem_bank

Features:
- Idempotent: skips problems that already exist (by title)
- Maintains test case order
- Handles visible and hidden test cases
- Production-safe with proper error handling
"""

import json
import os
import sys

# ── Ensure project root is on sys.path so app.* imports resolve ──────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Imports (must come after sys.path fix) ───────────────────────────────────
from sqlalchemy.orm import Session
from app.database.db import SessionLocal          # Correct import path
from app.models.coding import CodingProblem, CodingTestCase   # ORM models
# Import all models to resolve foreign key relationships
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_problems(json_path: str) -> list[dict]:
    """Load and return the problem list from the JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed(db: Session, problems: list[dict]) -> None:
    """Insert problems and test cases. Skips problems that already exist."""
    inserted_problems  = 0
    skipped_problems   = 0
    inserted_testcases = 0

    for problem in problems:
        # ── Idempotency check: skip if title already exists ──────────────────
        existing = (
            db.query(CodingProblem)
            .filter(CodingProblem.title == problem["title"])
            .first()
        )
        
        if existing:
            print(f"  [SKIP]   '{problem['title']}' already in database.")
            skipped_problems += 1
            continue

        # ── Insert coding_problems row ───────────────────────────────────────
        new_problem = CodingProblem(
            title         = problem["title"],
            description   = problem["description"],
            difficulty    = problem["difficulty"],
            input_format  = problem["input_format"],
            output_format = problem["output_format"],
            constraints   = problem["constraints"],
            tags          = problem["tags"],   # ARRAY(String) — pass list directly
            created_by    = None,              # seeded by system, no user
        )
        
        db.add(new_problem)
        db.flush()   # get new_problem.id without a full commit yet

        # ── Insert coding_test_cases rows ────────────────────────────────────
        for order, case in enumerate(problem["test_cases"], start=1):
            test_case = CodingTestCase(
                problem_id      = new_problem.id,
                input_data      = case["input_data"],
                expected_output = case["expected_output"],
                is_hidden       = case["is_hidden"],
                case_order      = order,
                explanation     = None,
            )
            db.add(test_case)
            inserted_testcases += 1

        db.commit()
        print(f"  [OK]     '{problem['title']}' inserted with {len(problem['test_cases'])} test cases.")
        inserted_problems += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print(f"  Problems  inserted : {inserted_problems}")
    print(f"  Problems  skipped  : {skipped_problems}")
    print(f"  Test cases inserted: {inserted_testcases}")
    print("=" * 55)
    
    if inserted_problems == 0 and skipped_problems > 0:
        print("  All problems already exist. Database unchanged.")
    else:
        print("  Problem bank seeded successfully!")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    json_path = os.path.join(PROJECT_ROOT, "problem_bank.json")
    
    if not os.path.exists(json_path):
        print(f"ERROR: problem_bank.json not found at {json_path}")
        sys.exit(1)

    print(f"Loading problems from: {json_path}")
    problems = load_problems(json_path)
    print(f"Found {len(problems)} problems in JSON.\n")

    db: Session = SessionLocal()
    try:
        seed(db, problems)
    except Exception as exc:
        db.rollback()
        print(f"\nERROR: Seeding failed — {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
