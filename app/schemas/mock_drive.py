"""
Pydantic schemas for TPO Mock Drive management.

MockDriveCreate  — request body for POST (create)
MockDriveUpdate  — request body for PUT (edit a draft)
MockDriveResponse — serialised response (from ORM)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import math

from pydantic import BaseModel, Field, model_validator

from app.models.mock_drive import VALID_ROUNDS

# Canonical branch list (mirrors frontend Register.jsx options).
VALID_BRANCHES = (
    "Computer Science",
    "Information Technology",
    "Electronics & Communication",
    "Mechanical Engineering",
    "Civil Engineering",
    "Other",
)


# ── Shared eligibility sub-schema ─────────────────────────────────────

class MockDriveEligibility(BaseModel):
    minimum_cgpa: float = Field(6.0, ge=0.0, le=10.0, description="Minimum CGPA required")
    maximum_backlogs: int = Field(0, ge=0, description="Maximum allowed active backlogs")
    eligible_branches: List[str] = Field(
        default_factory=list,
        description="List of eligible branch names",
    )

    @model_validator(mode="after")
    def validate_branches(self) -> "MockDriveEligibility":
        for branch in self.eligible_branches:
            if branch not in VALID_BRANCHES:
                raise ValueError(
                    f"Unknown branch {branch!r}. Valid options: {VALID_BRANCHES}"
                )
        return self


# ── Create ────────────────────────────────────────────────────────────

class MockDriveCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    target_role: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None

    minimum_cgpa: float = Field(6.0, ge=0.0, le=10.0)
    maximum_backlogs: int = Field(0, ge=0)
    eligible_branches: List[str] = Field(default_factory=list)

    # Dict or List mapping round name → enabled flag
    # e.g. {"aptitude": true, "coding": true} or ["aptitude", "coding"]
    selected_rounds: Dict[str, bool] | List[str] = Field(default_factory=dict)
    round_configurations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    rounds: Optional[Dict[str, bool] | List[str]] = None

    # Phase 4C Part 1: Optional approved CompanyBlueprint reference
    blueprint_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rounds" in data and ("selected_rounds" not in data or not data["selected_rounds"]):
                data["selected_rounds"] = data["rounds"]
            if "selected_rounds" in data and data["selected_rounds"] is not None:
                sr = data["selected_rounds"]
                if isinstance(sr, list):
                    data["selected_rounds"] = {r: True for r in sr if isinstance(r, str)}
        return data

    @model_validator(mode="after")
    def validate_rounds(self) -> "MockDriveCreate":
        if isinstance(self.selected_rounds, list):
            self.selected_rounds = {r: True for r in self.selected_rounds}
        self._check_rounds(self.selected_rounds)
        self._check_round_configurations(self.round_configurations, self.selected_rounds)
        self._check_branches(self.eligible_branches)
        return self

    @staticmethod
    def _check_rounds(rounds: Dict[str, bool]) -> None:
        unknown = set(rounds.keys()) - set(VALID_ROUNDS)
        if unknown:
            raise ValueError(
                f"Unknown round(s): {unknown}. Valid rounds: {VALID_ROUNDS}"
            )
        if not any(rounds.values()):
            raise ValueError("At least one assessment round must be selected.")

    @staticmethod
    def _check_branches(branches: List[str]) -> None:
        for branch in branches:
            if branch not in VALID_BRANCHES:
                raise ValueError(
                    f"Unknown branch {branch!r}. Valid options: {VALID_BRANCHES}"
                )

    @staticmethod
    def _check_round_configurations(configurations: Dict[str, Dict[str, Any]], selected: Dict[str, bool]) -> None:
        if set(configurations) - set(VALID_ROUNDS):
            raise ValueError("Round configuration contains an unsupported round.")
        for round_type, config in configurations.items():
            if not selected.get(round_type):
                raise ValueError("Round configuration is only allowed for selected rounds.")
            count, duration = config.get("question_count"), config.get("duration_minutes")
            difficulty = config.get("difficulty_distribution")
            if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 100:
                raise ValueError("question_count must be between 1 and 100.")
            if not isinstance(duration, int) or isinstance(duration, bool) or not 5 <= duration <= 300:
                raise ValueError("duration_minutes must be between 5 and 300.")
            if not isinstance(difficulty, dict) or set(difficulty) != {"easy", "medium", "hard"}:
                raise ValueError("difficulty_distribution must contain easy, medium, and hard.")
            if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1 for v in difficulty.values()) or abs(sum(difficulty.values()) - 1) > 0.01:
                raise ValueError("difficulty_distribution must contain weights summing to 1.")


# ── Update (DRAFT only) ───────────────────────────────────────────────

class MockDriveUpdate(BaseModel):
    company_name: Optional[str] = Field(None, min_length=1, max_length=200)
    target_role: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None

    minimum_cgpa: Optional[float] = Field(None, ge=0.0, le=10.0)
    maximum_backlogs: Optional[int] = Field(None, ge=0)
    eligible_branches: Optional[List[str]] = None

    selected_rounds: Optional[Dict[str, bool] | List[str]] = None
    round_configurations: Optional[Dict[str, Dict[str, Any]]] = None
    rounds: Optional[Dict[str, bool] | List[str]] = None
    blueprint_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rounds" in data and ("selected_rounds" not in data or not data["selected_rounds"]):
                data["selected_rounds"] = data["rounds"]
            if "selected_rounds" in data and data["selected_rounds"] is not None:
                sr = data["selected_rounds"]
                if isinstance(sr, list):
                    data["selected_rounds"] = {r: True for r in sr if isinstance(r, str)}
        return data

    @model_validator(mode="after")
    def validate_update(self) -> "MockDriveUpdate":
        if self.selected_rounds is not None:
            if isinstance(self.selected_rounds, list):
                self.selected_rounds = {r: True for r in self.selected_rounds}
            MockDriveCreate._check_rounds(self.selected_rounds)
            MockDriveCreate._check_round_configurations(self.round_configurations or {}, self.selected_rounds)
        elif self.round_configurations is not None:
            MockDriveCreate._check_round_configurations(
                self.round_configurations,
                {round_type: True for round_type in self.round_configurations},
            )
        if self.eligible_branches is not None:
            MockDriveCreate._check_branches(self.eligible_branches)
        return self



# ── Response ──────────────────────────────────────────────────────────

class MockDriveResponse(BaseModel):
    id: int
    company_name: str
    target_role: str
    description: Optional[str] = None
    status: str
    minimum_cgpa: float
    maximum_backlogs: int
    eligible_branches: List[str] = []
    selected_rounds: Dict[str, bool] = {}
    round_configurations: Dict[str, Dict[str, Any]] = {}
    rounds: List[str] = Field(default_factory=list)
    blueprint_id: Optional[int] = None
    blueprint_version: Optional[int] = None
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def populate_rounds(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rounds" not in data or not data["rounds"]:
                sr = data.get("selected_rounds") or {}
                if isinstance(sr, dict):
                    data["rounds"] = [r for r, on in sr.items() if on and r in VALID_ROUNDS]
                elif isinstance(sr, list):
                    data["rounds"] = [r for r in sr if r in VALID_ROUNDS]
        return data


# ── Consolidated Result (G6) ────────────────────────────────────────────
# Response schema for GET /mock-drives/{id}/result
# Aggregates per-round results into a single consolidated view.

class RoundResultSummary(BaseModel):
    """Summary of a single round's result within a Mock Drive."""
    round_type: str
    status: str  # "not_started" | "in_progress" | "completed" | "expired" | "expired"
    score: Optional[float] = None
    max_score: Optional[float] = None
    evaluation_status: Optional[str] = None  # evaluated | pending | unavailable
    completion_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


class MockDriveResultResponse(BaseModel):
    """Consolidated Mock Drive result for a candidate."""
    mock_drive_id: int
    company_name: str
    target_role: str
    blueprint_id: Optional[int] = None
    blueprint_version: Optional[int] = None
    status: str  # "not_started" | "in_progress" | "completed"
    candidate_id: int
    session_id: Optional[int] = None
    enabled_rounds: List[str]
    rounds: List[RoundResultSummary]
    overall_score: Optional[float] = None
    total_score: Optional[float] = None
    completed_at: Optional[datetime] = None
    completion_reason: Optional[str] = None
    competency_scoring: Optional[CompetencyScoringSummary] = None

    model_config = {"from_attributes": True}


class StudentMockDriveHistoryItem(BaseModel):
    mock_drive_id: int
    company_name: str
    target_role: str
    status: str
    completed_at: Optional[datetime] = None


# ── Derived candidate roster (G4) ───────────────────────────────────────
# Response schema for GET /tpo/mock-drives/{id}/roster
# Derived from authoritative AssessmentContext/Session/Round records; no
# duplicate assignment state is stored.

class MockDriveRosterRound(BaseModel):
    """Per-round participation/result row for one candidate in a drive."""
    round: str  # canonical drive round key, e.g. "technical_interview"
    round_type: str  # persisted AssessmentRound.round_type
    status: str  # active | completed | expired | not_started
    deadline_passed: bool = False
    score: Optional[float] = None
    max_score: Optional[float] = None
    completed_at: Optional[datetime] = None


class MockDriveRosterEntry(BaseModel):
    """One candidate's participation in a Mock Drive attempt."""
    candidate_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    context_id: int
    context_status: str  # active | completed
    session_id: Optional[int] = None
    session_status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    overall_score: Optional[float] = None
    competency_mapping_status: Optional[str] = None
    overall_score_status: Optional[str] = None
    evidence_coverage: Optional[float] = None
    assessed_competency_count: Optional[int] = None
    required_competency_count: Optional[int] = None
    missing_competencies: List[str] = Field(default_factory=list)
    scoring_error: Optional[str] = None
    competencies: List[Dict[str, Any]] = Field(default_factory=list)
    rounds: List[MockDriveRosterRound] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ── D1: Competency Scoring ───────────────────────────────────────────────

class CompetencyScoreSummary(BaseModel):
    """Normalized score and evidence for one configured competency."""
    competency_id: str
    competency_name: str
    weight_pct: Optional[float] = None
    normalized_score: Optional[float] = None
    status: str  # "assessed" | "not_assessed"
    evidence_count: int = 0
    evidence_types: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CompetencyScoringSummary(BaseModel):
    """Blueprint-driven competency scoring aggregate for a session."""
    overall_score: Optional[float] = None
    overall_score_status: str  # "final" | "provisional" | "unavailable"
    required_competency_count: int = 0
    assessed_competency_count: int = 0
    evidence_coverage: Optional[float] = None
    missing_competencies: List[str] = Field(default_factory=list)
    competencies: List[CompetencyScoreSummary] = Field(default_factory=list)
    blueprint_id: Optional[int] = None
    blueprint_version: Optional[int] = None
    scoring_policy_version: str
    scoring_error: Optional[str] = None

    model_config = {"from_attributes": True}


class MockDriveRosterResponse(BaseModel):
    """Derived candidate roster for one Mock Drive (TPO/admin view)."""
    mock_drive_id: int
    company_name: str
    target_role: str
    blueprint_id: Optional[int] = None
    blueprint_version: Optional[int] = None
    status: str  # drive global status
    enabled_rounds: List[str]
    total_participants: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
    candidates: List[MockDriveRosterEntry] = Field(default_factory=list)
