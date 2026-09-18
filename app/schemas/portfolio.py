"""
Pydantic schemas for EDI5 Student Portfolio Module.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ExternalProfiles(BaseModel):
    github: Optional[str] = None
    linkedin: Optional[str] = None
    leetcode: Optional[str] = None
    hackerrank: Optional[str] = None
    kaggle: Optional[str] = None
    website: Optional[str] = None


class ProjectItem(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    problem_statement: Optional[str] = None
    solution: Optional[str] = None
    technologies: List[str] = []
    role: Optional[str] = "Developer"
    individual_or_team: Optional[str] = "Individual"  # "Individual" | "Team"
    duration: Optional[str] = None
    github_url: Optional[str] = None
    demo_url: Optional[str] = None
    docs_url: Optional[str] = None
    research_paper_url: Optional[str] = None
    patent_url: Optional[str] = None
    evidence_status: str = "Submitted"  # "Submitted" | "Under Review" | "Verified" | "Rejected"
    created_at: Optional[str] = None


class CertificationItem(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=2, max_length=200)
    issuer: str = Field(..., min_length=2, max_length=150)
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None
    skills: List[str] = []
    verification_status: str = "Submitted"  # "Submitted" | "Under Review" | "Verified" | "Rejected"


class ExperienceItem(BaseModel):
    id: Optional[str] = None
    organization: str = Field(..., min_length=2, max_length=150)
    role: str = Field(..., min_length=2, max_length=100)
    type: str = "Internship"  # "Internship" | "Industry Project" | "Research" | "Freelance" | "Part-time"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    skills: List[str] = []


class AchievementItem(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=2, max_length=200)
    organization: Optional[str] = None
    date: Optional[str] = None
    position: Optional[str] = None
    description: Optional[str] = None
    evidence_url: Optional[str] = None


class ResearchItem(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=2, max_length=300)
    authors: Optional[str] = None
    journal: Optional[str] = None
    status: str = "Published"  # "Submitted" | "Under Review" | "Published"
    doi: Optional[str] = None
    publication_date: Optional[str] = None
    area: Optional[str] = None
    paper_url: Optional[str] = None


class PatentItem(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=2, max_length=300)
    application_number: Optional[str] = None
    filing_date: Optional[str] = None
    inventors: Optional[str] = None
    status: str = "Filed"  # "Draft" | "Filed" | "Under Review" | "Published" | "Granted"
    document_url: Optional[str] = None


class SkillEvidenceItem(BaseModel):
    name: str
    category: str  # "Programming", "Development", "AI/ML", "Core CS", "Tools", "General"
    claimed: bool = True
    practice_evidence: bool = False
    project_evidence: bool = False
    assessment_evidence: bool = False
    verified: bool = False


class AssessmentHighlightItem(BaseModel):
    round_type: str
    label: str
    best_score: Optional[float] = None
    problems_solved: Optional[int] = None
    attempts_count: int = 0
    evidence_type: str = "Assessment Evidence"


class BadgeItem(BaseModel):
    id: str
    name: str
    criteria: str
    earned: bool
    icon: str
    unlocked_at: Optional[str] = None


class CompletenessBreakdown(BaseModel):
    score: int
    completed_sections: List[str]
    missing_sections: List[str]


class PortfolioResponse(BaseModel):
    profile: Dict[str, Any]
    education: List[Dict[str, Any]]
    about: str
    skills: List[SkillEvidenceItem]
    projects: List[ProjectItem]
    certifications: List[CertificationItem]
    experience: List[ExperienceItem]
    achievements: List[AchievementItem]
    research: List[ResearchItem]
    patents: List[PatentItem]
    resumes: List[Dict[str, Any]]
    assessment_highlights: List[AssessmentHighlightItem]
    badges: List[BadgeItem]
    learning_journey: List[Dict[str, Any]]
    external_profiles: ExternalProfiles
    completeness: CompletenessBreakdown
    improvement_suggestions: List[str]


class PortfolioUpdate(BaseModel):
    about: Optional[str] = None
    external_profiles: Optional[ExternalProfiles] = None
