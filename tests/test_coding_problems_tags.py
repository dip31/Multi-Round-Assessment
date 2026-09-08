import pytest
from app.modules.coding.routers.coding_router import get_problems
from app.models.coding import CodingProblem, CodingTestCase
from app.schemas.coding import CodingProblemResponse

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

class MockDB:
    def __init__(self, problems):
        self.problems = problems

def test_coding_problem_tags_serialization(monkeypatch):
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
    
    import sys
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
