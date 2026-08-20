from typing import List, Dict, Any
import os
import requests
import time
import json
from functools import lru_cache

from app.models.coding import CodingTestCase
from app.config.settings import settings


VALID_CODING_STATUSES = {
    "running",
    "accepted",
    "wrong_answer",
    "runtime_error",
    "time_limit_exceeded",
    "compilation_error",
    "memory_limit_exceeded",
    "internal_error",
}

JUDGE0_URL = settings.JUDGE0_URL
JUDGE0_API_KEY = settings.JUDGE0_API_KEY
JUDGE0_HTTP_TIMEOUT = settings.JUDGE0_HTTP_TIMEOUT
JUDGE0_BATCH_POLL_INTERVAL = 0.5
JUDGE0_BATCH_MAX_POLLS = 60
# Optional environment-provided language map JSON: {"python":71, "cpp":54}
JUDGE0_LANGUAGE_MAP = settings.JUDGE0_LANGUAGE_MAP
# Set to "rapidapi" if using RapidAPI hosted Judge0, otherwise uses X-Auth-Token (self-hosted)
JUDGE0_AUTH_MODE = settings.JUDGE0_AUTH_MODE


def _mock_evaluate(code: str, language: str, test_cases: List[CodingTestCase], visible_only: bool = True) -> Dict[str, Any]:
    def normalize_text(s: str) -> str:
        if s is None:
            return ""
        # Normalize CRLF -> LF
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        # Strip leading/trailing whitespace and collapse multiple spaces
        s = " ".join(s.strip().split())
        return s

    def numeric_compare(a: str, b: str, tol: float = 1e-6) -> bool:
        try:
            fa = float(a)
            fb = float(b)
            return abs(fa - fb) <= tol
        except Exception:
            return False

    total = len(test_cases)
    passed = 0
    total_time = 0.0
    max_mem = 0
    
    # Track per-case results for run (visible_only=True)
    test_case_results = []
    
    for tc in test_cases:
        expected = normalize_text(tc.expected_output)
        # For mock, we'll assume the code echoes input for simplicity
        actual = normalize_text(tc.input_data)
        passed_bool = (expected == actual or numeric_compare(expected, actual))
        if passed_bool:
            passed += 1
        
        # Collect per-case detail only when visible_only=True (run)
        if visible_only:
            test_case_results.append({
                "input_data": tc.input_data,
                "expected_output": tc.expected_output,
                "actual_output": actual,
                "passed": passed_bool,
            })

    score = (passed / total) if total else 0.0
    status = "accepted" if passed == total and total > 0 else "wrong_answer"
    result = {
        "status": status,
        "judge0_token": None,
        "score": score,
        "test_cases_passed": passed,
        "total_test_cases": total,
        "execution_time": total_time,
        "memory_used": max_mem,
    }
    
    # Only include test_case_results for /run (visible_only=True)
    if visible_only:
        result["test_case_results"] = test_case_results
    
    return result


@lru_cache(maxsize=1)
def _fetch_languages() -> List[Dict[str, Any]]:
    if not JUDGE0_URL:
        return []
    try:
        resp = requests.get(f"{JUDGE0_URL}/languages", timeout=JUDGE0_HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _find_language_id(lang: str) -> Any:
    # Try to find a language id matching the provided language string
    # First prefer an explicit env-provided mapping to avoid dynamic lookups
    if JUDGE0_LANGUAGE_MAP:
        try:
            m = json.loads(JUDGE0_LANGUAGE_MAP)
            if isinstance(m, dict) and lang in m:
                return m[lang]
        except Exception:
            pass

    langs = _fetch_languages()
    key = (lang or "").lower()
    for item in langs:
        name = (item.get("name") or "").lower()
        if key == name or key in name:
            return item.get("id")
        # check aliases/extensions
        for ext in (item.get("extensions") or []):
            if key == ext.lstrip("."):
                return item.get("id")
    # fallback: try numeric
    try:
        return int(lang)
    except Exception:
        return None


def _normalize_status(description: str) -> str:
    if not description:
        return "unknown"
    normalized = description.strip().lower().replace(" ", "_")
    if normalized in VALID_CODING_STATUSES:
        return normalized
    if normalized.startswith("runtime_error"):
        # Judge0 emits granular runtime errors (NZEC, SIGSEGV, SIGABRT, ...).
        # Map all of them to the generic runtime_error status.
        return "runtime_error"
    if normalized == "partial":
        return "wrong_answer"
    if normalized == "mocked":
        return "wrong_answer"
    if normalized == "time_limit_exceeded":
        return "time_limit_exceeded"
    if normalized == "memory_limit_exceeded":
        return "memory_limit_exceeded"
    if normalized == "internal_error":
        return "internal_error"
    if normalized == "segmentation_fault":
        return "runtime_error"
    if normalized == "output_limit_exceeded":
        return "runtime_error"
    if normalized == "wrong_answer":
        return "wrong_answer"
    if normalized == "accepted":
        return "accepted"
    return normalized


def _aggregate_status(passed: int, total: int, status_descriptions: List[str]) -> str:
    if total <= 0:
        return "wrong_answer"

    for description in status_descriptions:
        normalized = _normalize_status(description)
        if normalized == "compilation_error":
            return "compilation_error"
        if normalized == "runtime_error":
            return "runtime_error"
        if normalized == "time_limit_exceeded":
            return "time_limit_exceeded"

    return "accepted" if passed == total else "wrong_answer"


def _build_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if JUDGE0_API_KEY:
        if JUDGE0_AUTH_MODE == "rapidapi":
            headers["X-RapidAPI-Key"] = JUDGE0_API_KEY
            headers["X-RapidAPI-Host"] = "judge0-ce.p.rapidapi.com"
        else:
            headers["X-Auth-Token"] = JUDGE0_API_KEY
    return headers


def _evaluate_batch(code: str, language: str, test_cases: List[CodingTestCase], visible_only: bool = True) -> Dict[str, Any]:
    """Evaluate using Judge0 batch API - submit all test cases at once, then poll for results."""
    lang_id = _find_language_id(language)
    if lang_id is None:
        return {
            "status": "internal_error",
            "judge0_token": None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": f"Unsupported language: {language}",
        }

    headers = _build_headers()

    max_cases = settings.CODING_MAX_TEST_CASES_PER_PROBLEM
    if len(test_cases) > max_cases:
        test_cases = test_cases[:max_cases]

    # Build batch submission payload
    submissions = []
    for tc in test_cases:
        submissions.append({
            "source_code": code,
            "language_id": lang_id,
            "stdin": tc.input_data,
            "expected_output": tc.expected_output,
        })

    try:
        # Submit batch
        resp = requests.post(
            f"{JUDGE0_URL}/submissions/batch",
            json={"submissions": submissions},
            headers=headers,
            timeout=JUDGE0_HTTP_TIMEOUT
        )
        resp.raise_for_status()
        batch_data = resp.json()
    except requests.Timeout:
        return {
            "status": "time_limit_exceeded",
            "judge0_token": None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": "Judge0 batch submission timed out",
        }
    except requests.ConnectionError:
        return {
            "status": "internal_error",
            "judge0_token": None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": "Cannot connect to Judge0 server",
        }
    except requests.HTTPError as e:
        return {
            "status": "internal_error",
            "judge0_token": None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": f"Judge0 HTTP error: {e.response.status_code}",
        }
    except Exception as e:
        return {
            "status": "internal_error",
            "judge0_token": None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": f"Judge0 request failed: {str(e)}",
        }

    tokens = [item.get("token") for item in batch_data if item.get("token")]
    if not tokens:
        return {
            "status": "internal_error",
            "judge0_token": None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": "No tokens returned from Judge0 batch submission",
        }

    # Poll for results
    token_str = ",".join(tokens)
    results = None
    for _ in range(JUDGE0_BATCH_MAX_POLLS):
        try:
            poll_resp = requests.get(
                f"{JUDGE0_URL}/submissions/batch",
                params={"tokens": token_str, "fields": "stdout,time,memory,status,compile_output,stderr,message"},
                headers=headers,
                timeout=JUDGE0_HTTP_TIMEOUT
            )
            poll_resp.raise_for_status()
            results = poll_resp.json().get("submissions", [])
        except Exception:
            time.sleep(JUDGE0_BATCH_POLL_INTERVAL)
            continue

        # Check if all completed
        all_done = all(
            r.get("status", {}).get("id", 0) not in (1, 2)  # 1=In Queue, 2=Processing
            for r in results
        )
        if all_done:
            break
        time.sleep(JUDGE0_BATCH_POLL_INTERVAL)

    if results is None:
        return {
            "status": "internal_error",
            "judge0_token": tokens[0] if tokens else None,
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": len(test_cases),
            "execution_time": 0.0,
            "memory_used": 0,
            "error_message": "Failed to poll Judge0 batch results",
        }

    # Aggregate results
    return _aggregate_batch_results(results, test_cases, visible_only)


def _aggregate_batch_results(results: List[Dict], test_cases: List[CodingTestCase], visible_only: bool) -> Dict[str, Any]:
    total = len(test_cases)
    passed = 0
    total_time = 0.0
    max_memory = 0
    first_token = None
    status_descriptions: List[str] = []
    compile_output = None
    stderr_output = None
    judge0_message = None
    test_case_results = []

    for idx, data in enumerate(results):
        status = data.get("status", {})
        status_desc = _normalize_status(status.get("description"))
        status_descriptions.append(status_desc)

        if first_token is None:
            first_token = data.get("token")

        if data.get("compile_output"):
            compile_output = data.get("compile_output")
        if data.get("stderr"):
            stderr_output = data.get("stderr")
        if data.get("message"):
            judge0_message = data.get("message")

        time_used = data.get("time") or 0.0
        mem_used = data.get("memory") or 0
        total_time += float(time_used or 0.0)
        try:
            max_memory = max(max_memory, int(mem_used or 0))
        except Exception:
            pass

        is_accepted = "accepted" in status_desc
        if is_accepted:
            passed += 1

        if visible_only and idx < len(test_cases):
            tc = test_cases[idx]
            test_case_results.append({
                "input_data": tc.input_data,
                "expected_output": tc.expected_output,
                "actual_output": data.get("stdout") or "",
                "passed": is_accepted,
            })

    score = (passed / total) if total else 0.0
    agg_status = _aggregate_status(passed, total, status_descriptions)

    result = {
        "status": agg_status,
        "judge0_token": first_token,
        "score": score,
        "test_cases_passed": passed,
        "total_test_cases": total,
        "execution_time": total_time,
        "memory_used": max_memory,
    }

    if compile_output:
        result["compile_output"] = compile_output
    if stderr_output:
        result["stderr"] = stderr_output
    if judge0_message:
        result["message"] = judge0_message
    if visible_only:
        result["test_case_results"] = test_case_results

    return result


def evaluate_submission(code: str, language: str, test_cases: List[CodingTestCase], visible_only: bool = True) -> Dict[str, Any]:
    """Evaluate submission via Judge0 batch API. Falls back to mock if Judge0 not configured."""
    if not JUDGE0_URL:
        return _mock_evaluate(code, language, test_cases, visible_only)

    return _evaluate_batch(code, language, test_cases, visible_only)

