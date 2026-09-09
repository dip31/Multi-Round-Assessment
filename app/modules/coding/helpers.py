from typing import Any, List, Optional


def serialize_tags(tags: Any) -> List[str]:
    """Serialize tags into a list of clean, non-empty strings.

    Handles:
    - None -> []
    - "" -> []
    - "   " -> []
    - "strings" -> ["strings"]
    - "math" -> ["math"]
    - "dynamic-programming,binary-search" -> ["dynamic-programming", "binary-search"]
    - "arrays, math, strings" -> ["arrays", "math", "strings"]
    - ["arrays", "math"] -> ["arrays", "math"]
    - [] -> []
    """
    if not tags:
        return []
    if isinstance(tags, list):
        return [tag.strip() for tag in tags if tag and str(tag).strip()]
    return [tag.strip() for tag in str(tags).split(",") if tag.strip()]


def serialize_coding_problem(problem: Any):
    """Serialize a CodingProblem ORM model, dict, or schema into a CodingProblemResponse.

    Ensures:
    - tags is always a List[str]
    - Hidden test cases are filtered out
    - API responses never return raw SQLAlchemy CodingProblem objects
    """
    from app.schemas.coding import CodingProblemResponse

    if isinstance(problem, CodingProblemResponse):
        return problem

    if isinstance(problem, dict):
        raw_test_cases = problem.get("test_cases") or []
        visible_test_cases = [
            tc for tc in raw_test_cases
            if not (tc.get("is_hidden") if isinstance(tc, dict) else getattr(tc, "is_hidden", False))
        ]
        return CodingProblemResponse(
            id=problem.get("id"),
            title=problem.get("title", ""),
            description=problem.get("description", ""),
            difficulty=problem.get("difficulty"),
            tags=serialize_tags(problem.get("tags")),
            input_format=problem.get("input_format"),
            output_format=problem.get("output_format"),
            constraints=problem.get("constraints"),
            test_cases=visible_test_cases,
        )

    raw_test_cases = getattr(problem, "test_cases", []) or []
    visible_test_cases = [
        tc for tc in raw_test_cases
        if not getattr(tc, "is_hidden", False)
    ]
    return CodingProblemResponse(
        id=getattr(problem, "id", None),
        title=getattr(problem, "title", ""),
        description=getattr(problem, "description", ""),
        difficulty=getattr(problem, "difficulty", None),
        tags=serialize_tags(getattr(problem, "tags", None)),
        input_format=getattr(problem, "input_format", None),
        output_format=getattr(problem, "output_format", None),
        constraints=getattr(problem, "constraints", None),
        test_cases=visible_test_cases,
    )
