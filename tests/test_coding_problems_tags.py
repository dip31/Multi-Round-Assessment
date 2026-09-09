import pytest
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.coding.routers.coding_router import get_problems, start_round, start_after_aptitude
from app.modules.coding.helpers import serialize_tags, serialize_coding_problem
from app.models.coding import CodingProblem, CodingTestCase
from app.schemas.coding import CodingProblemResponse, CodingTestCaseResponse


class MockTestCase:
    def __init__(self, id, input_data="1", expected_output="2", is_hidden=False, explanation=None):
        self.id = id
        self.input_data = input_data
        self.expected_output = expected_output
        self.is_hidden = is_hidden
        self.explanation = explanation


class MockProblem:
    def __init__(self, id, title, description, difficulty, tags, input_format, output_format, constraints, test_cases=None):
        self.id = id
        self.title = title
        self.description = description
        self.difficulty = difficulty
        self.tags = tags
        self.input_format = input_format
        self.output_format = output_format
        self.constraints = constraints
        self.test_cases = test_cases or []


class MockRound:
    def __init__(self, id=1, session_id=10, round_type="coding", status="in_progress"):
        self.id = id
        self.session_id = session_id
        self.round_type = round_type
        self.status = status


class MockUser:
    def __init__(self, id=1):
        self.id = id


class MockDB:
    def __init__(self, problems=None):
        self.problems = problems or []


def test_serialize_tags_helper():
    """Test the shared serialize_tags helper with all expected formats and edge cases."""
    # Comma-separated strings
    assert serialize_tags("dynamic-programming,binary-search") == ["dynamic-programming", "binary-search"]
    assert serialize_tags("strings") == ["strings"]
    assert serialize_tags("math") == ["math"]
    assert serialize_tags("arrays, math, strings") == ["arrays", "math", "strings"]
    assert serialize_tags("  trailing , leading  , spaces  ") == ["trailing", "leading", "spaces"]

    # Empty & None values
    assert serialize_tags("") == []
    assert serialize_tags(None) == []
    assert serialize_tags("   ") == []
    assert serialize_tags(",,") == []

    # List inputs
    assert serialize_tags(["dynamic-programming", "binary-search"]) == ["dynamic-programming", "binary-search"]
    assert serialize_tags(["  arrays  ", "", None, "math"]) == ["arrays", "math"]
    assert serialize_tags([]) == []


def test_coding_problem_tags_serialization(monkeypatch):
    """Test GET /coding/problems serializes tags into List[str]."""
    # Mock list_problems to return our mock problems
    def mock_list_problems(db):
        return [
            MockProblem(1, "Test 1", "Desc 1", "easy", "arrays,math", "in", "out", "con"),
            MockProblem(2, "Test 2", "Desc 2", "medium", "arrays", "in", "out", "con"),
            MockProblem(3, "Test 3", "Desc 3", "hard", "strings", "in", "out", "con"),
            MockProblem(4, "Test 4", "Desc 4", "easy", "", "in", "out", "con"),
            MockProblem(5, "Test 5", "Desc 5", "medium", None, "in", "out", "con"),
            MockProblem(6, "Test 6", "Desc 6", "hard", "arrays, math, strings", "in", "out", "con"),
        ]

    coding_router_module = sys.modules['app.modules.coding.routers.coding_router']
    monkeypatch.setattr(coding_router_module, "list_problems", mock_list_problems)

    response = get_problems(db=MockDB([]))

    assert len(response) == 6
    assert isinstance(response[0], CodingProblemResponse)

    # "arrays,math" -> ["arrays", "math"]
    assert response[0].tags == ["arrays", "math"]

    # "arrays" -> ["arrays"]
    assert response[1].tags == ["arrays"]

    # "strings" -> ["strings"]
    assert response[2].tags == ["strings"]

    # "" -> []
    assert response[3].tags == []

    # None -> []
    assert response[4].tags == []

    # "arrays, math, strings" -> ["arrays", "math", "strings"]
    assert response[5].tags == ["arrays", "math", "strings"]


def test_coding_start_round_serialization(monkeypatch):
    """Test POST /coding/start serializes problems with List[str] tags and excludes hidden tests."""
    mock_problems = [
        MockProblem(
            1, "P1", "D1", "hard", "dynamic-programming,binary-search", "in", "out", "con",
            test_cases=[
                MockTestCase(1, input_data="1", expected_output="2", is_hidden=False),
                MockTestCase(2, input_data="3", expected_output="4", is_hidden=True),
            ]
        ),
        MockProblem(2, "P2", "D2", "easy", "strings", "in", "out", "con"),
        MockProblem(3, "P3", "D3", "medium", "math", "in", "out", "con"),
        MockProblem(4, "P4", "D4", "easy", "", "in", "out", "con"),
        MockProblem(5, "P5", "D5", "medium", None, "in", "out", "con"),
    ]

    def mock_start_coding_round(db, user_id):
        return {
            "round": MockRound(),
            "assigned": [],
            "problems": mock_problems,
        }

    coding_router_module = sys.modules['app.modules.coding.routers.coding_router']
    monkeypatch.setattr(coding_router_module, "start_coding_round", mock_start_coding_round)

    payload = start_round(db=MockDB(), current_user=MockUser())

    assert "problems" in payload
    problems = payload["problems"]
    assert len(problems) == 5

    # Ensure raw SQLAlchemy / MockProblem objects are NOT returned
    for p in problems:
        assert isinstance(p, CodingProblemResponse)
        assert not isinstance(p, MockProblem)

    # Check tags serialization
    assert problems[0].tags == ["dynamic-programming", "binary-search"]
    assert problems[1].tags == ["strings"]
    assert problems[2].tags == ["math"]
    assert problems[3].tags == []
    assert problems[4].tags == []

    # Check hidden test cases are excluded
    assert len(problems[0].test_cases) == 1
    assert problems[0].test_cases[0].id == 1
    assert not problems[0].test_cases[0].is_hidden


def test_coding_start_after_aptitude_serialization(monkeypatch):
    """Test POST /coding/start-after-aptitude serializes problems with List[str] tags."""
    mock_problems = [
        MockProblem(1, "P1", "D1", "hard", "dynamic-programming,binary-search", "in", "out", "con"),
        MockProblem(2, "P2", "D2", "easy", "strings", "in", "out", "con"),
    ]

    def mock_start_coding_round(db, user_id):
        return {
            "round": MockRound(),
            "assigned": [],
            "problems": mock_problems,
        }

    coding_router_module = sys.modules['app.modules.coding.routers.coding_router']
    monkeypatch.setattr(coding_router_module, "start_coding_round", mock_start_coding_round)
    monkeypatch.setattr(coding_router_module.session_service, "get_user_active_round", lambda db, uid, round_type: None)

    payload = start_after_aptitude(db=MockDB(), current_user=MockUser())

    problems = payload["problems"]
    assert len(problems) == 2
    assert isinstance(problems[0], CodingProblemResponse)
    assert problems[0].tags == ["dynamic-programming", "binary-search"]
    assert problems[1].tags == ["strings"]


def test_coding_problem_response_pydantic_schema():
    """Test CodingProblemResponse directly parses comma-separated string tags and handles None/empty."""
    p1 = CodingProblemResponse(
        id=1, title="T1", description="D1", tags="dynamic-programming,binary-search"
    )
    assert p1.tags == ["dynamic-programming", "binary-search"]

    p2 = CodingProblemResponse(
        id=2, title="T2", description="D2", tags="strings"
    )
    assert p2.tags == ["strings"]

    p3 = CodingProblemResponse(
        id=3, title="T3", description="D3", tags="math"
    )
    assert p3.tags == ["math"]

    p4 = CodingProblemResponse(
        id=4, title="T4", description="D4", tags=""
    )
    assert p4.tags == []

    p5 = CodingProblemResponse(
        id=5, title="T5", description="D5", tags=None
    )
    assert p5.tags == []


def test_api_client_start_round_json_response(monkeypatch):
    """Test HTTP POST /api/v1/coding/start returns 200 with problems having List[str] tags in JSON."""
    from app.core.auth import get_current_user
    from app.database.db import get_db

    mock_problems = [
        MockProblem(1, "P1", "D1", "hard", "dynamic-programming,binary-search", "in", "out", "con"),
        MockProblem(2, "P2", "D2", "easy", "strings", "in", "out", "con"),
        MockProblem(3, "P3", "D3", "medium", "math", "in", "out", "con"),
    ]

    coding_router_module = sys.modules['app.modules.coding.routers.coding_router']
    monkeypatch.setattr(
        coding_router_module,
        "start_coding_round",
        lambda db, uid: {
            "round": {"id": 1, "session_id": 1},
            "assigned": [],
            "problems": mock_problems,
        },
    )

    test_app = FastAPI()
    test_app.include_router(coding_router_module.router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user] = lambda: MockUser()
    test_app.dependency_overrides[get_db] = lambda: MockDB()

    client = TestClient(test_app)
    res = client.post("/api/v1/coding/start")
    assert res.status_code == 200
    data = res.json()
    assert "problems" in data
    problems = data["problems"]
    assert len(problems) == 3

    # Exactly what frontend expects:
    assert isinstance(problems[0]["tags"], list)
    assert problems[0]["tags"] == ["dynamic-programming", "binary-search"]

    assert isinstance(problems[1]["tags"], list)
    assert problems[1]["tags"] == ["strings"]

    assert isinstance(problems[2]["tags"], list)
    assert problems[2]["tags"] == ["math"]


def test_api_client_start_after_aptitude_json_response(monkeypatch):
    """Test HTTP POST /api/v1/coding/start-after-aptitude returns 200 with problems having List[str] tags in JSON."""
    from app.core.auth import get_current_user
    from app.database.db import get_db

    mock_problems = [
        MockProblem(1, "P1", "D1", "hard", "dynamic-programming,binary-search", "in", "out", "con"),
        MockProblem(2, "P2", "D2", "easy", "strings", "in", "out", "con"),
    ]

    coding_router_module = sys.modules['app.modules.coding.routers.coding_router']
    monkeypatch.setattr(
        coding_router_module,
        "start_coding_round",
        lambda db, uid: {
            "round": {"id": 1, "session_id": 1},
            "assigned": [],
            "problems": mock_problems,
        },
    )
    monkeypatch.setattr(coding_router_module.session_service, "get_user_active_round", lambda db, uid, round_type: None)

    test_app = FastAPI()
    test_app.include_router(coding_router_module.router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user] = lambda: MockUser()
    test_app.dependency_overrides[get_db] = lambda: MockDB()

    client = TestClient(test_app)
    res = client.post("/api/v1/coding/start-after-aptitude")
    assert res.status_code == 200
    data = res.json()
    assert "problems" in data
    problems = data["problems"]
    assert len(problems) == 2

    assert isinstance(problems[0]["tags"], list)
    assert problems[0]["tags"] == ["dynamic-programming", "binary-search"]

    assert isinstance(problems[1]["tags"], list)
    assert problems[1]["tags"] == ["strings"]
