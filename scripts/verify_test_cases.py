"""
Verify test cases in the database
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import text
from app.database.db import SessionLocal

def main():
    db = SessionLocal()
    
    print("\n" + "=" * 100)
    print("STEP 1: VERIFY TEST CASE COUNTS")
    print("=" * 100)
    
    query = text("""
        SELECT 
            cp.id,
            cp.title,
            cp.difficulty,
            COUNT(ct.id) AS total,
            COUNT(CASE WHEN ct.is_hidden = false THEN 1 END) AS visible,
            COUNT(CASE WHEN ct.is_hidden = true THEN 1 END) AS hidden
        FROM coding_problems cp
        LEFT JOIN coding_test_cases ct ON ct.problem_id = cp.id
        GROUP BY cp.id, cp.title, cp.difficulty
        ORDER BY cp.id
    """)
    
    result = db.execute(query)
    
    print(f"\n{'ID':<4} | {'Title':<35} | {'Diff':<8} | {'Total':<6} | {'Visible':<8} | {'Hidden':<7}")
    print("-" * 100)
    
    problems_with_no_visible = []
    problems_with_no_tests = []
    
    for row in result:
        pid, title, diff, total, visible, hidden = row
        print(f"{pid:<4} | {title:<35} | {diff:<8} | {total:<6} | {visible:<8} | {hidden:<7}")
        
        if visible == 0 and total > 0:
            problems_with_no_visible.append((pid, title))
        if total == 0:
            problems_with_no_tests.append((pid, title))
    
    print("\n" + "=" * 100)
    print("STEP 2: CHECK FOR ISSUES")
    print("=" * 100)
    
    if problems_with_no_tests:
        print("\n❌ CRITICAL: Problems with NO test cases:")
        for pid, title in problems_with_no_tests:
            print(f"   Problem {pid}: {title}")
    else:
        print("\n✓ All problems have test cases")
    
    if problems_with_no_visible:
        print("\n⚠️  WARNING: Problems with NO visible test cases:")
        for pid, title in problems_with_no_visible:
            print(f"   Problem {pid}: {title}")
        print("   → Run Code will return empty results for these problems")
    else:
        print("✓ All problems have visible test cases")
    
    # Check for null or empty test data
    print("\n" + "=" * 100)
    print("STEP 3: CHECK FOR NULL/EMPTY TEST DATA")
    print("=" * 100)
    
    query2 = text("""
        SELECT 
            ct.id,
            cp.title,
            ct.input_data,
            ct.expected_output,
            ct.is_hidden,
            ct.case_order
        FROM coding_test_cases ct
        JOIN coding_problems cp ON cp.id = ct.problem_id
        WHERE ct.input_data IS NULL
           OR ct.expected_output IS NULL
        ORDER BY cp.id, ct.case_order
    """)
    
    result2 = db.execute(query2)
    rows = list(result2)
    
    if rows:
        print("\n❌ CRITICAL: Test cases with null/empty data:")
        for row in rows:
            tc_id, title, inp, out, hidden, order = row
            print(f"   Test Case {tc_id} (Problem: {title}, Order: {order})")
            print(f"      Input: {'NULL/EMPTY' if not inp else 'OK'}")
            print(f"      Output: {'NULL/EMPTY' if not out else 'OK'}")
    else:
        print("\n✓ All test cases have valid input_data and expected_output")
    
    db.close()
    
    print("\n" + "=" * 100)
    print("VERIFICATION COMPLETE")
    print("=" * 100)
    
    if problems_with_no_tests or rows:
        print("\n❌ ISSUES FOUND - Fix before proceeding")
        sys.exit(1)
    elif problems_with_no_visible:
        print("\n⚠️  WARNINGS FOUND - Review before proceeding")
        sys.exit(0)
    else:
        print("\n✅ ALL CHECKS PASSED - Database is ready!")
        sys.exit(0)

if __name__ == "__main__":
    main()
