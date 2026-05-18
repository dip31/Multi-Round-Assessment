"""
Judge0 Client

All HTTP communication with Judge0 API.
Uses wait=true for synchronous execution — single request returns full result.
No business logic. No database access.
"""

import requests
from fastapi import HTTPException
from app.config.settings import settings

LANGUAGE_MAP = {
    "python": 71,   # Python 3.8.1
    "cpp":    54,   # C++ GCC 9.2.0
    "java":   62,   # Java OpenJDK 13.0.1
}


def submit_code(source_code: str, language_id: int, stdin: str) -> dict:
    """Submit code to Judge0 and wait for result synchronously.

    Uses wait=true so Judge0 executes the code and returns the full result
    in a single HTTP request. No polling needed.

    Args:
        source_code: The candidate's source code string.
        language_id: Judge0 integer language ID from LANGUAGE_MAP.
        stdin: Standard input for this test case.

    Returns:
        Full Judge0 response dict containing:
          stdout        — program output (may be None)
          stderr        — error output (may be None)
          compile_output — compilation errors (may be None)
          status        — dict with id (int) and description (str)
          time          — execution time in seconds as string
          memory        — memory used in KB as integer

    Raises:
        HTTPException(503): If Judge0 is unreachable or returns error.
    """
    # Use mock Judge0 if enabled (for Windows testing)
    if settings.USE_MOCK_JUDGE0:
        from app.modules.coding.utils.mock_judge0 import mock_submit_code
        return mock_submit_code(source_code, language_id, stdin)
    
    url = f"{settings.JUDGE0_API_URL}/submissions"
    params = {"wait": "true"}

    payload = {
        "source_code": source_code,
        "language_id": language_id,
        "stdin": stdin if stdin else "",
    }

    headers = {"Content-Type": "application/json"}
    if settings.JUDGE0_API_KEY:
        headers["X-RapidAPI-Key"] = settings.JUDGE0_API_KEY

    try:
        response = requests.post(
            url,
            json=payload,
            params=params,
            headers=headers,
            timeout=30        # 30 seconds max for code execution
        )
        response.raise_for_status()
        result = response.json()
        
        # If Judge0 returns internal error (status_id 13), fall back to mock
        if result.get("status", {}).get("id") == 13:
            from app.modules.coding.utils.mock_judge0 import mock_submit_code
            return mock_submit_code(source_code, language_id, stdin)
        
        return result

    except requests.exceptions.ConnectionError:
        # Fall back to mock if Judge0 is not reachable
        from app.modules.coding.utils.mock_judge0 import mock_submit_code
        return mock_submit_code(source_code, language_id, stdin)
    except requests.exceptions.Timeout:
        raise HTTPException(503, "Judge0 request timed out.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(503, f"Judge0 service error: {str(e)}")
