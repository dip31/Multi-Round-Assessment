from typing import List, Dict, Any
import os
import requests
import time
import json
from functools import lru_cache

from app.models.coding import CodingTestCase
from app.config.settings import settings


JUDGE0_URL = os.environ.get("JUDGE0_URL")
JUDGE0_API_KEY = os.environ.get("JUDGE0_API_KEY")
JUDGE0_HTTP_TIMEOUT = float(os.environ.get("JUDGE0_HTTP_TIMEOUT", "15"))
# Optional environment-provided language map JSON: {"python":71, "cpp":54}
JUDGE0_LANGUAGE_MAP = os.environ.get("JUDGE0_LANGUAGE_MAP")


def _mock_evaluate(code: str, language: str, test_cases: List[CodingTestCase]) -> Dict[str, Any]:
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
    for tc in test_cases:
        expected = normalize_text(tc.expected_output)
        # For mock, we'll assume the code echoes input for simplicity
        actual = normalize_text(tc.input_data)
        if expected == actual or numeric_compare(expected, actual):
            passed += 1

    score = (passed / total) if total else 0.0
    return {
        "status": "mocked",
        "judge0_token": None,
        "score": score,
        "test_cases_passed": passed,
        "total_test_cases": total,
        "execution_time": total_time,
        "memory_used": max_mem,
    }


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
    return description.strip().lower().replace(" ", "_")


def evaluate_submission(code: str, language: str, test_cases: List[CodingTestCase], visible_only: bool = True) -> Dict[str, Any]:
    """Evaluate submission synchronously via Judge0 per-test (wait=true). Falls back to mock if Judge0 not configured.

    Runs one submission per test case (synchronous) and aggregates results.
    """
    if not JUDGE0_URL:
        return _mock_evaluate(code, language, test_cases)

    lang_id = _find_language_id(language)
    headers = {"Content-Type": "application/json"}
    if JUDGE0_API_KEY:
        headers["X-Auth-Token"] = JUDGE0_API_KEY

    # Enforce configured max test cases cap to avoid very long sync runs
    max_cases = settings.CODING_MAX_TEST_CASES_PER_PROBLEM
    if len(test_cases) > max_cases:
        test_cases = test_cases[:max_cases]

    total = len(test_cases)
    passed = 0
    total_time = 0.0
    max_memory = 0
    first_token = None

    for tc in test_cases:
        payload = {
            "source_code": code,
            "language_id": lang_id,
            "stdin": tc.input_data,
            "expected_output": tc.expected_output,
        }
        try:
            resp = requests.post(f"{JUDGE0_URL}/submissions?wait=true", json=payload, headers=headers, timeout=JUDGE0_HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            # treat as time limit
            status_desc = "time_limit_exceeded"
            data = {}
        except Exception:
            return _mock_evaluate(code, language, test_cases)

        status = data.get("status", {})
        status_desc = _normalize_status(status.get("description"))
        if first_token is None:
            first_token = data.get("token")

        # Judge0 may return stdout/time/memory
        out = data.get("stdout")
        time_used = data.get("time") or 0.0
        mem_used = data.get("memory") or 0
        total_time += float(time_used or 0.0)
        try:
            max_memory = max(max_memory, int(mem_used or 0))
        except Exception:
            pass

        # Passed if judge returned accepted description
        if "accepted" in status_desc:
            passed += 1

    score = (passed / total) if total else 0.0
    agg_status = "accepted" if passed == total and total > 0 else "partial" if passed > 0 else "wrong_answer"

    return {
        "status": agg_status,
        "judge0_token": first_token,
        "score": score,
        "test_cases_passed": passed,
        "total_test_cases": total,
        "execution_time": total_time,
        "memory_used": max_memory,
    }

