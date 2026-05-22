"""Seed coding problems and test cases for the coding round.

Usage:
    python scripts/seed_coding_questions.py
    python scripts/seed_coding_questions.py --markdown "C:/path/to/coding_question_bank.md"
"""

from __future__ import annotations

import sys
import re
import argparse
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import SessionLocal
from app.models.coding import CodingProblem, CodingTestCase

DEFAULT_MARKDOWN_PATH = Path.home() / "Downloads" / "coding_question_bank.md"

DIFFICULTY_BY_TITLE: Dict[str, str] = {
    "Reverse String": "easy",
    "Palindrome Check": "easy",
    "Find Maximum Element": "easy",
    "Factorial of a Number": "easy",
    "Prime Number Check": "easy",
    "Fibonacci Series": "easy",
    "Sum of Array Elements": "easy",
    "Count Vowels": "easy",
    "Two Sum": "medium",
    "Valid Parentheses": "medium",
}

TAGS_BY_TITLE: Dict[str, List[str]] = {
    "Reverse String": ["string"],
    "Palindrome Check": ["string"],
    "Find Maximum Element": ["array"],
    "Factorial of a Number": ["math"],
    "Prime Number Check": ["math"],
    "Fibonacci Series": ["dp", "math"],
    "Sum of Array Elements": ["array"],
    "Count Vowels": ["string"],
    "Two Sum": ["array", "hashmap"],
    "Valid Parentheses": ["stack", "string"],
}


def _normalize_block(text: str) -> str:
    return text.replace("\r\n", "\n").strip("\n")


def _extract_header_block(section: str, header: str) -> str:
    pattern = re.compile(rf"### {re.escape(header)}\s*\n(.*?)(?=\n### |\Z)", re.DOTALL)
    match = pattern.search(section)
    if not match:
        return ""
    return _normalize_block(match.group(1))


def _extract_input_output_cases(block: str, is_hidden: bool, start_order: int) -> List[Dict[str, Any]]:
    case_pattern = re.compile(r"Input:\s*\n(.*?)\n\s*Output:\s*\n(.*?)(?=\n(?:#### Test Case\s+\d+|\d+\.\s*\nInput:)|\Z)", re.DOTALL)
    cases: List[Dict[str, Any]] = []
    order = start_order
    for match in case_pattern.finditer(block):
        input_data = _normalize_block(match.group(1))
        expected_output = _normalize_block(match.group(2))
        cases.append(
            {
                "input_data": input_data,
                "expected_output": expected_output,
                "is_hidden": is_hidden,
                "case_order": order,
            }
        )
        order += 1
    return cases


def parse_markdown_question_bank(markdown_text: str) -> List[Dict[str, Any]]:
    chunks = re.split(r"\n## Problem\s+", markdown_text)
    problems: List[Dict[str, Any]] = []

    for chunk in chunks[1:]:
        section = "## Problem " + chunk
        lines = section.splitlines()
        if not lines:
            continue

        title_line = lines[0].replace("## Problem", "").strip()
        if "—" in title_line:
            title = title_line.split("—", 1)[1].strip()
        elif "-" in title_line:
            title = title_line.split("-", 1)[1].strip()
        else:
            title = title_line.strip()

        description = _extract_header_block(section, "Description")
        input_format = _extract_header_block(section, "Input")
        output_format = _extract_header_block(section, "Output")

        visible_block = _extract_header_block(section, "Visible Test Cases")
        hidden_block = _extract_header_block(section, "Hidden Test Cases")

        visible_cases = _extract_input_output_cases(visible_block, is_hidden=False, start_order=1)
        hidden_cases = _extract_input_output_cases(hidden_block, is_hidden=True, start_order=len(visible_cases) + 1)
        test_cases = visible_cases + hidden_cases

        if not test_cases:
            continue

        problems.append(
            {
                "title": title,
                "description": description,
                "difficulty": DIFFICULTY_BY_TITLE.get(title, "easy"),
                "tags": TAGS_BY_TITLE.get(title, []),
                "input_format": input_format,
                "output_format": output_format,
                "constraints": "",
                "test_cases": test_cases,
            }
        )

    return problems


def upsert_problem(db: Session, payload: Dict[str, Any]) -> None:
    problem = db.query(CodingProblem).filter(CodingProblem.title == payload["title"]).first()

    if problem is None:
        problem = CodingProblem(
            title=payload["title"],
            description=payload["description"],
            difficulty=payload["difficulty"],
            tags=payload["tags"],
            input_format=payload["input_format"],
            output_format=payload["output_format"],
            constraints=payload["constraints"],
        )
        db.add(problem)
        db.flush()
    else:
        problem.description = payload["description"]
        problem.difficulty = payload["difficulty"]
        problem.tags = payload["tags"]
        problem.input_format = payload["input_format"]
        problem.output_format = payload["output_format"]
        problem.constraints = payload["constraints"]

    db.query(CodingTestCase).filter(CodingTestCase.problem_id == problem.id).delete()

    for case in payload["test_cases"]:
        db.add(
            CodingTestCase(
                problem_id=problem.id,
                input_data=case["input_data"],
                expected_output=case["expected_output"],
                is_hidden=case["is_hidden"],
                case_order=case["case_order"],
                explanation=case.get("explanation"),
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed coding problems from markdown question bank")
    parser.add_argument(
        "--markdown",
        type=str,
        default=str(DEFAULT_MARKDOWN_PATH),
        help="Path to markdown question bank file",
    )
    args = parser.parse_args()

    markdown_path = Path(args.markdown)
    if not markdown_path.exists():
        raise FileNotFoundError(f"Question bank file not found: {markdown_path}")

    markdown_text = markdown_path.read_text(encoding="utf-8")
    problems = parse_markdown_question_bank(markdown_text)
    if not problems:
        raise ValueError("No coding problems could be parsed from the markdown file")

    db: Session = SessionLocal()
    try:
        for problem in problems:
            upsert_problem(db, problem)
        db.commit()

        problems_count = db.query(CodingProblem).count()
        test_cases_count = db.query(CodingTestCase).count()
        print(
            f"Seed complete from {markdown_path}. "
            f"imported={len(problems)}, coding_problems={problems_count}, coding_test_cases={test_cases_count}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
