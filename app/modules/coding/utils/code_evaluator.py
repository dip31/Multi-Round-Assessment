"""
Code Evaluator

Pure logic for comparing outputs and calculating scores.
No database access. No HTTP calls. No side effects.
"""

from app.modules.coding.utils.judge0_client import submit_code


def compare_output(expected: str, actual: str) -> bool:
    """Compare expected vs actual output after stripping whitespace.

    Args:
        expected: Correct expected output string.
        actual: Actual output from Judge0 (may be None).

    Returns:
        True if outputs match after stripping, False otherwise.
    """
    if actual is None:
        return False
    return expected.strip() == actual.strip()


def calculate_score(passed_cases: int, total_cases: int) -> float:
    """Calculate percentage score from passed test cases.

    Args:
        passed_cases: Number of test cases that passed.
        total_cases: Total test cases evaluated.

    Returns:
        Float between 0.0 and 100.0, rounded to 2 decimal places.
    """
    if total_cases == 0:
        return 0.0
    return round((passed_cases / total_cases) * 100, 2)


def determine_verdict(passed_cases: int, total_cases: int,
                      last_status_id: int) -> str:
    """Determine final verdict string from results.

    Args:
        passed_cases: Number of test cases that passed.
        total_cases: Total test cases evaluated.
        last_status_id: Judge0 status ID from the last failed test case.

    Returns:
        Verdict string: accepted | wrong_answer |
                        compilation_error | runtime_error |
                        time_limit_exceeded
    """
    if last_status_id == 6:
        return "compilation_error"
    if last_status_id == 5:
        return "time_limit_exceeded"
    if last_status_id in [7, 8, 9, 10, 11, 12]:
        return "runtime_error"
    if passed_cases == total_cases:
        return "accepted"
    # For partial or no passes, return wrong_answer (database constraint)
    return "wrong_answer"


def evaluate_submission(code: str, language_id: int,
                        test_cases: list) -> dict:
    """Run code against test cases and return evaluation result.

    Sends code to Judge0 for each test case using wait=true.
    Compares stdout with expected_output after stripping whitespace.

    Args:
        code: Source code string.
        language_id: Judge0 integer language ID.
        test_cases: List of test case ORM objects with input_data
                    and expected_output fields.

    Returns:
        Dict with:
          passed_cases    — int
          total_cases     — int
          verdict         — str
          score           — float (0.0 to 100.0)
          execution_time  — float (max across all test cases, seconds)
          memory_used     — int (max across all test cases, KB)
          results         — list of per-test-case result dicts
    """
    passed_cases = 0
    total_cases = len(test_cases)
    last_status_id = 3       # default: accepted
    max_exec_time = 0.0
    max_memory = 0
    results = []

    for tc in test_cases:
        # Submit to Judge0 — wait=true returns full result immediately
        result = submit_code(code, language_id, tc.input_data)

        status_id = result.get("status", {}).get("id", 11)
        stdout = result.get("stdout") or ""
        exec_time = float(result.get("time") or 0)
        memory = int(result.get("memory") or 0)

        max_exec_time = max(max_exec_time, exec_time)
        max_memory = max(max_memory, memory)
        last_status_id = status_id

        passed = compare_output(tc.expected_output, stdout)
        if passed:
            passed_cases += 1

        results.append({
            "input_data":      tc.input_data,
            "expected_output": tc.expected_output,
            "actual_output":   stdout.strip() if stdout else "",
            "passed":          passed,
            "status":          result.get("status", {}).get(
                                   "description", "Unknown")
        })

    score = calculate_score(passed_cases, total_cases)
    verdict = determine_verdict(passed_cases, total_cases, last_status_id)

    return {
        "passed_cases":   passed_cases,
        "total_cases":    total_cases,
        "verdict":        verdict,
        "score":          score,
        "execution_time": max_exec_time,
        "memory_used":    max_memory,
        "results":        results,
    }
