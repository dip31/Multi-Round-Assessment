"""Judge0 client diagnostics and fallback behavior.

These tests run without any live Judge0 instance or credentials: the HTTP
layer is monkeypatched. They lock in the Task 3 outcome — an auth-protected
Judge0 instance with no ``JUDGE0_API_KEY`` surfaces a diagnosable failure
instead of a generic "unavailable".
"""

import requests
import pytest

from app.modules.coding.utils import code_evaluator as ce
from app.models.coding import CodingTestCase


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.content = b"{}"

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"{self.status_code} error", response=self
            )


def _cases(n=2):
    return [
        CodingTestCase(input_data=f"{i}\n", expected_output=f"{i}\n")
        for i in range(1, n + 1)
    ]


def test_not_configured_returns_diagnosable_mock(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "")
    result = ce.evaluate_submission("print(1)", "python", _cases())
    assert result["status"] == "internal_error"
    assert result["score"] == 0.0
    assert result["test_cases_passed"] == 0
    assert "not configured" in result["message"].lower()


def test_authentication_failure_surfaces_token_hint(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "http://judge0.local:2358")
    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "")

    def _raise_401(*args, **kwargs):
        raise requests.HTTPError("401", response=_FakeResponse(401))

    monkeypatch.setattr(ce.requests, "post", _raise_401)

    result = ce.evaluate_submission("print(1)", "python", _cases())
    assert result["status"] == "internal_error"
    assert "401" in result["message"]
    assert "JUDGE0_API_KEY" in result["message"]


def test_unreachable_surfaces_connection_hint(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "http://judge0.local:2358")
    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "secret")

    def _raise_conn(*args, **kwargs):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(ce.requests, "post", _raise_conn)

    result = ce.evaluate_submission("print(1)", "python", _cases())
    assert result["status"] == "internal_error"
    assert "unreachable" in result["message"].lower()


def test_successful_batch_aggregates_accepted(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "http://judge0.local:2358")
    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "secret")

    def _post(*args, **kwargs):
        return _FakeResponse(201, [{"token": "t1"}, {"token": "t2"}])

    def _get(*args, **kwargs):
        return _FakeResponse(
            200,
            {
                "submissions": [
                    {
                        "token": "t1",
                        "status": {"id": 3, "description": "Accepted"},
                        "stdout": "1\n",
                        "time": "0.01",
                        "memory": 1000,
                    },
                    {
                        "token": "t2",
                        "status": {"id": 3, "description": "Accepted"},
                        "stdout": "2\n",
                        "time": "0.01",
                        "memory": 1200,
                    },
                ]
            },
        )

    monkeypatch.setattr(ce.requests, "post", _post)
    monkeypatch.setattr(ce.requests, "get", _get)

    result = ce.evaluate_submission("print(x)", "python", _cases())
    assert result["status"] == "accepted"
    assert result["test_cases_passed"] == 2
    assert result["score"] == 1.0
    assert result["judge0_token"] == "t1"
    assert len(result["test_case_results"]) == 2


def test_health_reports_missing_auth_without_leaking_key(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "http://judge0.local:2358")
    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "")
    monkeypatch.setattr(ce.requests, "get", lambda *a, **k: _FakeResponse(401))

    info = ce.judge0_health()
    assert info["configured"] is True
    assert info["reachable"] is True
    assert info["status_code"] == 401
    assert info["api_key_configured"] is False
    assert "auth" in info["error"].lower()


def test_health_reports_not_configured(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "")
    info = ce.judge0_health()
    assert info["configured"] is False
    assert "JUDGE0_URL" in info["error"]


def test_health_reports_healthy(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_URL", "http://judge0.local:2358")
    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "secret")
    monkeypatch.setattr(ce.requests, "get", lambda *a, **k: _FakeResponse(200, {"version": "1.13"}))

    info = ce.judge0_health()
    assert info["reachable"] is True
    assert info["status_code"] == 200
    assert info["api_key_configured"] is True
    assert info["error"] is None


def test_build_headers_auth_modes(monkeypatch):
    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "k")
    monkeypatch.setattr(ce, "JUDGE0_AUTH_MODE", "self-hosted")
    assert ce._build_headers()["X-Auth-Token"] == "k"

    monkeypatch.setattr(ce, "JUDGE0_AUTH_MODE", "rapidapi")
    headers = ce._build_headers()
    assert headers["X-RapidAPI-Key"] == "k"
    assert headers["X-RapidAPI-Host"] == "judge0-ce.p.rapidapi.com"

    monkeypatch.setattr(ce, "JUDGE0_API_KEY", "")
    headers = ce._build_headers()
    assert "X-Auth-Token" not in headers
    assert "X-RapidAPI-Key" not in headers


class _RecordingQuery:
    def __init__(self, added):
        self._added = added

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _RecordingDB:
    """Minimal DB stub: records persisted rows, returns empty test-case lists."""

    def __init__(self):
        self.added = []
        self.commits = 0

    def query(self, *args, **kwargs):
        return _RecordingQuery(self.added)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def test_full_submit_fails_closed_when_execution_unavailable(monkeypatch):
    """A scored submit must never persist a mock result as a candidate score."""
    from app.modules.coding.services import coding_service

    monkeypatch.setattr(
        coding_service,
        "evaluate_submission",
        lambda **kwargs: {
            "status": "internal_error",
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": 0,
            "message": "Judge0 rejected the request (401)",
        },
    )
    db = _RecordingDB()
    with pytest.raises(coding_service.CodeExecutionUnavailable):
        coding_service.run_and_evaluate(
            db, problem_id=1, code="print(1)", language="python",
            visible_only=False, round_id=1,
        )
    # Nothing persisted, so the candidate is not silently scored zero.
    assert db.added == []
    assert db.commits == 0


def test_run_preview_returns_unavailable_without_persisting(monkeypatch):
    """The non-scored preview path surfaces the failure but never persists."""
    from app.modules.coding.services import coding_service

    monkeypatch.setattr(
        coding_service,
        "evaluate_submission",
        lambda **kwargs: {
            "status": "internal_error",
            "score": 0.0,
            "test_cases_passed": 0,
            "total_test_cases": 0,
            "message": "unreachable",
        },
    )
    db = _RecordingDB()
    result = coding_service.run_and_evaluate(
        db, problem_id=1, code="print(1)", language="python", visible_only=True,
    )
    assert result["status"] == "internal_error"
    assert db.added == []
