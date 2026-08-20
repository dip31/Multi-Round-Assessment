import os
import json
from typing import Literal

RoleType = Literal["SDE", "Data Science", "Full Stack"]

ROLE_KEYWORDS = {
    "SDE": [
        "java", "c++", "c#", "golang", "rust",
        "data structures", "algorithms", "system design",
        "microservices", "kubernetes", "docker",
        "distributed systems", "competitive programming",
        "spring", "hibernate", "maven", "gradle",
        "design patterns", "low level design"
    ],
    "Data Science": [
        "tensorflow", "pytorch", "keras", "scikit-learn",
        "machine learning", "deep learning", "nlp",
        "computer vision", "pandas", "numpy", "matplotlib",
        "seaborn", "jupyter", "data analysis", "statistics",
        "regression", "classification", "clustering",
        "neural network", "transformer", "bert", "llm",
        "data science", "ai", "ml", "xgboost",
        "random forest", "feature engineering"
    ],
    "Full Stack": [
        "react", "vue", "angular", "next.js", "node.js",
        "express", "django", "flask", "fastapi", "tailwind",
        "css", "html", "javascript", "typescript",
        "rest api", "graphql", "webpack", "vite",
        "frontend", "backend", "full stack", "web development",
        "mongodb", "postgresql", "mysql", "redis",
        "responsive design", "spa"
    ]
}


def detect_role(
    skills: list,
    projects: dict | list,
    fallback: str = "SDE"
) -> RoleType:
    """
    Detect candidate role from skills and projects.
    Uses keyword scoring — counts matches per role.
    Always returns a value, never raises.
    """
    try:
        projects_text = ""
        if isinstance(projects, dict):
            projects_text = " ".join([str(v) for v in projects.values()])
        elif isinstance(projects, list):
            projects_text = " ".join([str(p) for p in projects])

        search_text = " ".join([
            " ".join([str(s) for s in skills]),
            projects_text
        ]).lower()

        scores = {}
        for role, keywords in ROLE_KEYWORDS.items():
            scores[role] = sum(
                1 for kw in keywords
                if kw.lower() in search_text
            )

        max_score = max(scores.values())
        if max_score == 0:
            return fallback

        return max(scores, key=scores.get)

    except Exception as e:
        print(f"[RoleDetection] Error: {e}")
        return fallback


def load_question_bank() -> dict:
    """Load question bank JSON. Returns {} on failure."""
    try:
        path = os.path.join(
            os.path.dirname(__file__),
            "../data/question_bank.json"
        )
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[QuestionBank] Load failed: {e}")
        return {}
