"""
Phase 4A: EDI5 Pre-seeded Benchmark Historical Data.

Serves as an OPTIONAL deterministic fallback when TPO/company-specific
data is insufficient, eliminating cold-start issues without external web scraping.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.company_data import CompanyHistoricalData


# Pre-seeded company and role assessment benchmarks
EDI5_BENCHMARKS: List[Dict[str, Any]] = [
    {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "aliases": ["google", "alphabet"],
        "role_aliases": ["software engineer", "sde", "swe", "software developer", "sde-1", "sde-2"],
        "data": {
            "year": 2024,
            "rounds": ["aptitude", "coding", "technical_interview", "hr_interview"],
            "topics": [
                "Data Structures & Algorithms", "Dynamic Programming", "Graphs & Graph Algorithms",
                "Trees & Binary Search Trees", "Arrays", "System Design", "Operating Systems",
                "Object-Oriented Programming", "Behavioral & Leadership Principles"
            ],
            "difficulty": "hard",
            "question_types": ["MCQ", "Coding", "System Design", "Behavioral"],
            "duration_minutes": 150,
            "round_patterns": {
                "aptitude": {
                    "duration_minutes": 45,
                    "question_count": 25,
                    "focus_areas": ["Quantitative Aptitude", "Logical Reasoning", "Data Interpretation"],
                },
                "coding": {
                    "duration_minutes": 90,
                    "question_count": 2,
                    "focus_areas": ["Dynamic Programming", "Graphs & Graph Algorithms", "Arrays"],
                },
                "technical_interview": {
                    "duration_minutes": 45,
                    "question_count": 3,
                    "focus_areas": ["System Design", "Operating Systems", "Object-Oriented Programming"],
                },
                "hr_interview": {
                    "duration_minutes": 30,
                    "question_count": 3,
                    "focus_areas": ["Behavioral & Leadership Principles", "HR & Personal Interview"],
                },
            },
            "notes": "EDI5 Benchmark: Google hiring process focuses heavily on algorithmic problem-solving (Medium-Hard LeetCode difficulty), scalability concepts in system design, and Googliness/culture fit.",
        },
    },
    {
        "company_name": "Amazon",
        "target_role": "Software Development Engineer",
        "aliases": ["amazon", "aws"],
        "role_aliases": ["software development engineer", "sde", "sde-1", "sde-2", "software engineer", "software developer"],
        "data": {
            "year": 2024,
            "rounds": ["aptitude", "coding", "technical_interview", "hr_interview"],
            "topics": [
                "Data Structures & Algorithms", "Trees & Binary Search Trees", "Graphs & Graph Algorithms",
                "Hashing & Hash Tables", "Dynamic Programming", "Object-Oriented Programming",
                "System Design", "Behavioral & Leadership Principles"
            ],
            "difficulty": "hard",
            "question_types": ["MCQ", "Coding", "System Design", "Behavioral"],
            "duration_minutes": 135,
            "round_patterns": {
                "aptitude": {
                    "duration_minutes": 45,
                    "question_count": 20,
                    "focus_areas": ["Logical Reasoning", "Quantitative Aptitude", "Data Interpretation"],
                },
                "coding": {
                    "duration_minutes": 90,
                    "question_count": 2,
                    "focus_areas": ["Trees & Binary Search Trees", "Hashing & Hash Tables", "Arrays"],
                },
                "technical_interview": {
                    "duration_minutes": 45,
                    "question_count": 2,
                    "focus_areas": ["Object-Oriented Programming", "System Design", "Operating Systems"],
                },
                "hr_interview": {
                    "duration_minutes": 45,
                    "question_count": 4,
                    "focus_areas": ["Behavioral & Leadership Principles", "HR & Personal Interview"],
                },
            },
            "notes": "EDI5 Benchmark: Amazon emphasizes Amazon Leadership Principles throughout all technical and behavioral rounds alongside standard tree/graph coding problems.",
        },
    },
    {
        "company_name": "Microsoft",
        "target_role": "Software Engineer",
        "aliases": ["microsoft", "msft"],
        "role_aliases": ["software engineer", "sde", "software developer", "swe"],
        "data": {
            "year": 2024,
            "rounds": ["coding", "technical_interview", "hr_interview"],
            "topics": [
                "Data Structures & Algorithms", "Strings", "Trees & Binary Search Trees",
                "Linked Lists", "Recursion & Backtracking", "Operating Systems",
                "Computer Networks", "Database Management Systems", "Behavioral & Leadership Principles"
            ],
            "difficulty": "medium",
            "question_types": ["Coding", "System Design", "Behavioral"],
            "duration_minutes": 120,
            "round_patterns": {
                "coding": {
                    "duration_minutes": 90,
                    "question_count": 3,
                    "focus_areas": ["Strings", "Trees & Binary Search Trees", "Arrays"],
                },
                "technical_interview": {
                    "duration_minutes": 45,
                    "question_count": 3,
                    "focus_areas": ["Operating Systems", "Database Management Systems", "Computer Networks"],
                },
                "hr_interview": {
                    "duration_minutes": 30,
                    "question_count": 2,
                    "focus_areas": ["Behavioral & Leadership Principles", "HR & Personal Interview"],
                },
            },
            "notes": "EDI5 Benchmark: Microsoft technical rounds focus on clean, bug-free code, time/space complexity analysis, and solid OS/DBMS fundamentals.",
        },
    },
    {
        "company_name": "TCS",
        "target_role": "Digital / Prime",
        "aliases": ["tcs", "tata consultancy services"],
        "role_aliases": ["digital", "prime", "ninja", "software engineer", "developer", "software developer"],
        "data": {
            "year": 2024,
            "rounds": ["aptitude", "coding", "technical_interview", "hr_interview"],
            "topics": [
                "Quantitative Aptitude", "Logical Reasoning", "Verbal Ability",
                "Percentages, Profit & Loss", "Time, Speed & Distance", "Data Interpretation",
                "Data Structures & Algorithms", "Arrays", "SQL & Querying", "Database Management Systems",
                "Object-Oriented Programming", "HR & Personal Interview"
            ],
            "difficulty": "medium",
            "question_types": ["MCQ", "Coding", "Subjective / Theory"],
            "duration_minutes": 150,
            "round_patterns": {
                "aptitude": {
                    "duration_minutes": 75,
                    "question_count": 60,
                    "focus_areas": ["Quantitative Aptitude", "Logical Reasoning", "Verbal Ability"],
                },
                "coding": {
                    "duration_minutes": 60,
                    "question_count": 2,
                    "focus_areas": ["Arrays", "Strings", "Math & Number Theory"],
                },
                "technical_interview": {
                    "duration_minutes": 30,
                    "question_count": 4,
                    "focus_areas": ["Database Management Systems", "SQL & Querying", "Object-Oriented Programming"],
                },
                "hr_interview": {
                    "duration_minutes": 20,
                    "question_count": 3,
                    "focus_areas": ["HR & Personal Interview"],
                },
            },
            "notes": "EDI5 Benchmark: TCS National Qualifier Assessment format with high emphasis on speed in Numerical and Reasoning sections plus core database/OOP questions in interviews.",
        },
    },
    {
        "company_name": "Generic Benchmark",
        "target_role": "Software Engineer",
        "aliases": ["generic", "industry", "standard", "default"],
        "role_aliases": ["software engineer", "sde", "software developer", "developer", "backend developer", "frontend developer", "full stack developer"],
        "data": {
            "year": 2024,
            "rounds": ["aptitude", "coding", "technical_interview"],
            "topics": [
                "Quantitative Aptitude", "Logical Reasoning", "Verbal Ability",
                "Data Structures & Algorithms", "Arrays", "Strings", "Trees & Binary Search Trees",
                "Database Management Systems", "Object-Oriented Programming", "Operating Systems",
                "Behavioral & Leadership Principles"
            ],
            "difficulty": "medium",
            "question_types": ["MCQ", "Coding", "Subjective / Theory"],
            "duration_minutes": 120,
            "round_patterns": {
                "aptitude": {
                    "duration_minutes": 45,
                    "question_count": 30,
                    "focus_areas": ["Quantitative Aptitude", "Logical Reasoning", "Verbal Ability"],
                },
                "coding": {
                    "duration_minutes": 60,
                    "question_count": 2,
                    "focus_areas": ["Arrays", "Strings", "Data Structures & Algorithms"],
                },
                "technical_interview": {
                    "duration_minutes": 45,
                    "question_count": 3,
                    "focus_areas": ["Database Management Systems", "Object-Oriented Programming", "Operating Systems"],
                },
            },
            "notes": "EDI5 Benchmark: Standard industry placement hiring pattern representing typical multi-round assessment across leading engineering campuses.",
        },
    },
]


def benchmark_role_compatible(target_role: str, benchmark: Dict[str, Any]) -> bool:
    role_norm = (target_role or "").strip().lower()
    accepted = [benchmark["target_role"], *benchmark.get("role_aliases", [])]
    return any(role_norm == alias.lower() or alias.lower() in role_norm for alias in accepted)


def select_edi5_benchmark(
    company_name: str, target_role: str, *, allow_generic_fallback: bool = False
) -> Dict[str, Any]:
    """Return an explicit role-compatible benchmark selection result."""
    comp_norm = (company_name or "").strip().lower()
    for bm in EDI5_BENCHMARKS:
        comp_matches = (
            comp_norm == bm["company_name"].lower() or
            any(alias in comp_norm for alias in bm.get("aliases", []))
        )
        if comp_matches and benchmark_role_compatible(target_role, bm):
            return {"status": "role_compatible_evidence_found", "benchmark": bm, "match_type": "company_and_role"}

    generic = EDI5_BENCHMARKS[-1]
    if benchmark_role_compatible(target_role, generic):
        return {"status": "generic_fallback_found", "benchmark": generic, "match_type": "role_compatible_generic"}
    if allow_generic_fallback:
        return {"status": "generic_fallback_found", "benchmark": generic, "match_type": "explicit_generic_fallback"}
    return {"status": "no_compatible_evidence_found", "benchmark": None, "match_type": None}


def find_edi5_benchmark(company_name: str, target_role: str) -> Optional[Dict[str, Any]]:
    """Find a company/role benchmark without silently crossing role families."""
    return select_edi5_benchmark(company_name, target_role)["benchmark"]


def seed_edi5_fallback_data(
    db: Session,
    company_name: str,
    target_role: str,
    created_by_id: int,
) -> CompanyHistoricalData:
    """Create a pre_seeded CompanyHistoricalData record from the EDI5 benchmark."""
    selection = select_edi5_benchmark(company_name, target_role, allow_generic_fallback=True)
    bm = selection["benchmark"]
    if not bm:
        raise ValueError(f"No compatible EDI5 benchmark for {target_role}")
    data = dict(bm["data"])
    data["is_edi5_benchmark"] = True
    data["benchmark_reference"] = f"{bm['company_name']} - {bm['target_role']}"
    data["source_provenance"] = {
        "classification": "generic_fallback" if bm["company_name"] == "Generic Benchmark" else "pre_seeded_benchmark",
        "selection_status": selection["status"],
        "benchmark_company": bm["company_name"],
        "benchmark_role": bm["target_role"],
        "requested_company": company_name.strip(),
        "requested_role": target_role.strip(),
        "explicit_fallback_requested": True,
    }

    label = f"EDI5 Benchmark: {bm['company_name']} ({bm['target_role']})"

    item = CompanyHistoricalData(
        company_name=company_name.strip(),
        target_role=target_role.strip(),
        label=label,
        source_type="pre_seeded",
        raw_data=data,
        created_by_id=created_by_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_available_benchmarks() -> List[Dict[str, str]]:
    """Return catalog of available EDI5 benchmarks."""
    return [
        {
            "company_name": bm["company_name"],
            "target_role": bm["target_role"],
            "difficulty": bm["data"]["difficulty"],
            "rounds": ", ".join(bm["data"]["rounds"]),
        }
        for bm in EDI5_BENCHMARKS
    ]
