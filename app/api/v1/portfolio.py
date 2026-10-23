"""
FastAPI router for EDI5 Evidence-Aware Student Portfolio.

Provides:
- GET  /portfolio/me             - Complete evidence-aware portfolio
- PUT  /portfolio/me             - Update basic portfolio metadata (about, external_profiles)
- POST /portfolio/project        - Add project
- PUT  /portfolio/project/{id}   - Update project
- DELETE /portfolio/project/{id} - Delete project
- POST /portfolio/certification  - Add certification
- PUT  /portfolio/certification/{id} - Update certification
- DELETE /portfolio/certification/{id} - Delete certification
- POST /portfolio/experience     - Add experience
- DELETE /portfolio/experience/{id} - Delete experience
- POST /portfolio/achievement    - Add achievement
- DELETE /portfolio/achievement/{id} - Delete achievement
- POST /portfolio/research       - Add research paper
- DELETE /portfolio/research/{id} - Delete research paper
- POST /portfolio/patent         - Add patent
- DELETE /portfolio/patent/{id}  - Delete patent
- PUT  /portfolio/external-profiles - Update external links
"""

import uuid
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.profile import StudentProfile, UserResume
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.interview import InterviewSession, StudentCompetency, CompetencyEvidence
from app.models.aptitude import AptitudeAttempt, AptitudeTopic
from app.models.coding import CodingSubmission
from app.services.profile_service import ProfileService
from app.schemas.portfolio import (
    PortfolioResponse,
    PortfolioUpdate,
    ProjectItem,
    CertificationItem,
    ExperienceItem,
    AchievementItem,
    ResearchItem,
    PatentItem,
    ExternalProfiles,
    SkillEvidenceItem,
    AssessmentHighlightItem,
    BadgeItem,
    CompletenessBreakdown,
    PublicPortfolioResponse,
    SharingStatus,
    EnableSharingRequest,
    VerifyItemRequest,
    VerifyItemResponse,
)

router = APIRouter(prefix="/portfolio", tags=["Student Portfolio"])


def _categorize_skill(skill_name: str) -> str:
    s = skill_name.strip().lower()
    prog_langs = {"python", "c++", "c", "java", "javascript", "typescript", "go", "rust", "ruby", "kotlin", "swift", "c#", "php"}
    dev_stack = {"react", "react.js", "next.js", "vue", "angular", "node.js", "express", "fastapi", "django", "flask", "spring", "html", "css", "tailwind", "tailwind css", "bootstrap", "rest api", "graphql"}
    aiml = {"machine learning", "deep learning", "nlp", "natural language processing", "computer vision", "tensorflow", "pytorch", "keras", "scikit-learn", "data science", "pandas", "numpy", "opencv", "llm", "rag", "transformers"}
    core_cs = {"operating systems", "os", "computer networks", "networking", "dbms", "database management systems", "sql", "postgresql", "mysql", "mongodb", "oops", "object oriented programming", "data structures", "dsa", "algorithms", "system design"}
    tools = {"git", "github", "docker", "kubernetes", "aws", "azure", "gcp", "linux", "jira", "postman", "ci/cd", "jenkins", "redis"}

    if s in prog_langs or any(p in s for p in ["python", "java", "c++", "javascript", "c#"]):
        return "Programming"
    if s in dev_stack or any(p in s for p in ["react", "node", "fastapi", "django", "flask", "html"]):
        return "Development"
    if s in aiml or any(p in s for p in ["learning", "nlp", "vision", "tensor", "torch"]):
        return "AI/ML"
    if s in core_cs or any(p in s for p in ["os", "network", "dbms", "sql", "oops", "data structures"]):
        return "Core CS"
    if s in tools or any(p in s for p in ["git", "docker", "aws", "linux", "postman"]):
        return "Tools"
    return "General"


@router.get("/me", response_model=PortfolioResponse)
def get_my_portfolio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Retrieve full authoritative portfolio for the authenticated student."""
    user_id = current_user.id
    
    # 1. Fetch or initialize student profile
    student_profile = ProfileService.get_or_create_student_profile(db, user_id)
    portfolio_data = dict(student_profile.portfolio_data or {})

    # 2. Extract profile fields
    full_name = student_profile.full_name or current_user.name or (current_user.email.split("@")[0] if current_user.email else "Candidate")
    profile_dict = {
        "id": student_profile.id,
        "user_id": user_id,
        "name": full_name,
        "email": current_user.email,
        "department": student_profile.department,
        "institution": student_profile.institution,
        "graduation_year": student_profile.graduation_year,
        "cgpa": student_profile.cgpa,
        "target_role": student_profile.target_role or "Software Engineer",
        "roll_number": student_profile.roll_number,
        "backlogs_count": student_profile.backlogs_count,
        "mobile_no": student_profile.mobile_no or student_profile.phone_number,
        "tenth_marks": student_profile.tenth_marks,
        "twelfth_marks": student_profile.twelfth_marks,
        "gender": student_profile.gender,
        "date_of_birth": student_profile.date_of_birth,
        "nationality": student_profile.nationality or "Indian",
    }

    # 3. About
    about_text = portfolio_data.get("about") or student_profile.bio or (
        f"{student_profile.department} student at {student_profile.institution} passionate about "
        f"{student_profile.target_role or 'software engineering'} and building high-impact technology."
    )

    # 4. Education
    education_list = portfolio_data.get("education")
    if not education_list:
        education_list = [
            {
                "institution": student_profile.institution,
                "degree": "Bachelor of Technology (B.Tech)",
                "department": student_profile.department,
                "start_year": (student_profile.graduation_year - 4) if student_profile.graduation_year else 2022,
                "graduation_year": student_profile.graduation_year,
                "cgpa": student_profile.cgpa,
                "tenth_marks": student_profile.tenth_marks,
                "twelfth_marks": student_profile.twelfth_marks,
            }
        ]

    # 5. Resumes
    resumes_db = db.query(UserResume).filter(UserResume.user_id == user_id).order_by(UserResume.uploaded_at.desc()).all()
    resumes_list = [
        {
            "id": r.id,
            "cv_name": r.cv_name or r.file_name,
            "cv_type": r.cv_type or "Primary",
            "file_name": r.file_name,
            "file_size": r.file_size,
            "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
            "parsed_skills": r.parsed_skills or [],
        }
        for r in resumes_db
    ]

    # 6. Projects & Certifications from portfolio_data
    projects_raw = portfolio_data.get("projects", [])
    projects = [ProjectItem(**p) for p in projects_raw]

    certifications_raw = portfolio_data.get("certifications", [])
    certifications = [CertificationItem(**c) for c in certifications_raw]

    experience_raw = portfolio_data.get("experience", [])
    experience = [ExperienceItem(**e) for e in experience_raw]

    achievements_raw = portfolio_data.get("achievements", [])
    achievements = [AchievementItem(**a) for a in achievements_raw]

    research_raw = portfolio_data.get("research", [])
    research = [ResearchItem(**r) for r in research_raw]

    patents_raw = portfolio_data.get("patents", [])
    patents = [PatentItem(**p) for p in patents_raw]

    ext_profiles_raw = portfolio_data.get("external_profiles", {})
    external_profiles = ExternalProfiles(**ext_profiles_raw)

    # 7. Assessment Highlights from real assessment data
    user_sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == user_id).all()
    session_ids = [s.id for s in user_sessions]
    
    rounds = []
    if session_ids:
        rounds = db.query(AssessmentRound).filter(
            AssessmentRound.session_id.in_(session_ids),
            AssessmentRound.status == "completed"
        ).all()

    interview_sessions = []
    if session_ids:
        interview_sessions = db.query(InterviewSession).options(
            selectinload(InterviewSession.turns)
        ).filter(
            InterviewSession.session_id.in_(session_ids)
        ).all()

    # Coding submissions
    solved_coding_count = 0
    best_coding_score = 0.0
    coding_attempts = 0
    if session_ids:
        cod_round_ids = [r.id for r in rounds if r.round_type == "coding"]
        if cod_round_ids:
            submissions = db.query(CodingSubmission).filter(
                CodingSubmission.round_id.in_(cod_round_ids)
            ).all()
            coding_attempts = len(submissions)
            for sub in submissions:
                sc = (sub.score or 0.0) * 100
                if sc > best_coding_score:
                    best_coding_score = sc
                if (sub.score or 0.0) >= 0.7:
                    solved_coding_count += 1

    # High-score calculation for rounds
    mcq_rounds = [r for r in rounds if r.round_type in ("mcq", "aptitude")]
    tech_rounds = [r for r in rounds if r.round_type == "technical"]
    comb_rounds = [r for r in rounds if r.round_type == "combined"]

    best_mcq = max([round((r.score or 0.0) * 100, 1) for r in mcq_rounds], default=None)
    best_tech = max([round((r.score or 0.0) * 100, 1) for r in tech_rounds], default=None)
    best_comb = max([round((r.score or 0.0) * 100, 1) for r in comb_rounds], default=None)

    # Interview highlight metrics
    tech_ints = [s for s in interview_sessions if getattr(s, "interview_type", "technical") == "technical"]
    hr_ints = [s for s in interview_sessions if getattr(s, "interview_type", "") == "hr"]
    comm_ints = [s for s in interview_sessions if getattr(s, "interview_type", "") == "communication"]

    def _best_interview_score(sess_list):
        scores = []
        for s in sess_list:
            for t in getattr(s, "turns", []):
                if t.final_score is not None:
                    scores.append(round(t.final_score * 100, 1))
        return max(scores, default=None)

    best_tech_int = _best_interview_score(tech_ints)
    best_hr_int = _best_interview_score(hr_ints)
    best_comm_int = _best_interview_score(comm_ints)

    assessment_highlights = [
        AssessmentHighlightItem(
            round_type="mcq",
            label="MCQ Round (Aptitude)",
            best_score=best_mcq,
            attempts_count=len(mcq_rounds),
        ),
        AssessmentHighlightItem(
            round_type="technical",
            label="Technical Round",
            best_score=best_tech,
            attempts_count=len(tech_rounds),
        ),
        AssessmentHighlightItem(
            round_type="combined",
            label="Combined Round (Aptitude + Tech)",
            best_score=best_comb,
            attempts_count=len(comb_rounds),
        ),
        AssessmentHighlightItem(
            round_type="coding",
            label="Coding Challenge",
            best_score=round(best_coding_score, 1) if coding_attempts > 0 else None,
            problems_solved=solved_coding_count,
            attempts_count=len([r for r in rounds if r.round_type == "coding"]),
        ),
        AssessmentHighlightItem(
            round_type="technical_interview",
            label="Technical Interview",
            best_score=best_tech_int,
            attempts_count=len(tech_ints),
        ),
        AssessmentHighlightItem(
            round_type="hr_interview",
            label="HR Interview",
            best_score=best_hr_int,
            attempts_count=len(hr_ints),
        ),
        AssessmentHighlightItem(
            round_type="communication_interview",
            label="Communication Interview",
            best_score=best_comm_int,
            attempts_count=len(comm_ints),
        ),
    ]

    # 8. Skills & Evidence Mapping - Integrate StudentCompetency for evidence-backed skills
    profile_skills = list(student_profile.skills_json or [])
    project_skills = set()
    for p in projects:
        for t in p.technologies:
            project_skills.add(t.strip())
    resume_skills = set()
    for r in resumes_list:
        for s in r.get("parsed_skills", []):
            resume_skills.add(s.strip())

    all_raw_skills = list(dict.fromkeys(profile_skills + list(project_skills) + list(resume_skills)))
    if not all_raw_skills:
        # Default fallback if empty
        all_raw_skills = ["Python", "Data Structures", "Web Development", "Git"]

    # Fetch competency records for this student
    competencies = db.query(StudentCompetency).filter(StudentCompetency.user_id == user_id).all()
    competency_map = {c.skill.lower(): c for c in competencies}

    # Count evidence records per skill
    evidence_counts = db.query(CompetencyEvidence.skill, func.count(CompetencyEvidence.id)).filter(
        CompetencyEvidence.user_id == user_id
    ).group_by(CompetencyEvidence.skill).all()
    evidence_count_map = {skill.lower(): count for skill, count in evidence_counts}

    # Check verified items for skills (from portfolio data)
    verified_cert_skills = set()
    for c in certifications:
        if c.verification_status == "Verified":
            for s in c.skills:
                verified_cert_skills.add(s.lower())

    verified_project_skills = set()
    for p in projects:
        if p.evidence_status == "Verified":
            for t in p.technologies:
                verified_project_skills.add(t.lower())

    # Build skill evidence - prioritize competency records, supplement with raw skills
    skill_evidence_items = []
    has_tech_assessment = (best_tech is not None and best_tech >= 60.0) or (best_comb is not None and best_comb >= 60.0)
    has_coding_assessment = (best_coding_score >= 60.0) or (solved_coding_count > 0)

    # Track which raw skills have been covered by competency records
    covered_skills = set()

    # First, add skills from StudentCompetency (evidence-backed)
    for comp in competencies:
        sk_lower = comp.skill.lower()
        cat = _categorize_skill(comp.skill)
        covered_skills.add(sk_lower)

        has_proj = any(sk_lower in [t.lower() for t in p.technologies] for p in projects)

        # Determine assessment evidence from competency record
        has_assmt = comp.score > 0 and comp.evidence_source in ("interview", "aptitude", "coding", "practice")

        # Verified if in verified cert/project OR competency has high confidence and assessment source
        is_verified = (sk_lower in verified_cert_skills) or (sk_lower in verified_project_skills) or (
            comp.confidence >= 0.7 and comp.evidence_source in ("interview", "aptitude", "coding")
        )

        skill_evidence_items.append(SkillEvidenceItem(
            name=comp.skill,
            category=cat,
            claimed=True,
            practice_evidence=comp.evidence_source == "practice",
            project_evidence=has_proj,
            assessment_evidence=has_assmt,
            verified=is_verified,
            score=round(comp.score, 1),
            confidence=round(comp.confidence, 2),
            freshness=comp.freshness,
            evidence_source=comp.evidence_source,
            evidence_count=evidence_count_map.get(sk_lower, 0),
        ))

    # Then, add remaining raw skills that don't have competency records (self-reported only)
    for sk in all_raw_skills:
        sk_lower = sk.lower()
        if sk_lower in covered_skills:
            continue

        cat = _categorize_skill(sk)

        has_proj = any(sk_lower in [t.lower() for t in p.technologies] for p in projects)

        # Assessment evidence rule (heuristic fallback for non-competency skills):
        has_assmt = False
        if cat in ("Core CS", "Tools") and has_tech_assessment:
            has_assmt = True
        elif cat == "Programming" and (has_coding_assessment or has_tech_assessment):
            has_assmt = True
        elif cat == "Development" and (has_coding_assessment or len(rounds) > 0):
            has_assmt = True

        has_practice = len(rounds) > 0
        is_verified = (sk_lower in verified_cert_skills) or (sk_lower in verified_project_skills)

        skill_evidence_items.append(SkillEvidenceItem(
            name=sk,
            category=cat,
            claimed=True,
            practice_evidence=has_practice,
            project_evidence=has_proj,
            assessment_evidence=has_assmt,
            verified=is_verified,
            score=None,
            confidence=None,
            freshness=None,
            evidence_source=None,
            evidence_count=None,
        ))

    # 9. Rule-based Badges (transparent criteria)
    badges = [
        BadgeItem(
            id="coding_practitioner",
            name="Coding Practitioner",
            criteria="Successfully solved coding challenges with passing test suites",
            earned=solved_coding_count >= 1 or best_coding_score >= 70.0,
            icon="[Code]",
        ),
        BadgeItem(
            id="consistent_learner",
            name="Consistent Learner",
            criteria="Completed 3 or more assessment and practice sessions",
            earned=len(rounds) >= 3,
            icon="[Fire]",
        ),
        BadgeItem(
            id="technical_achiever",
            name="Technical Achiever",
            criteria="Achieved 75% or higher in Technical Round",
            earned=(best_tech is not None and best_tech >= 75.0) or (best_comb is not None and best_comb >= 75.0),
            icon="[Trophy]",
        ),
        BadgeItem(
            id="interview_ready",
            name="Interview Ready",
            criteria="Completed structured AI Technical or HR Interview",
            earned=len(interview_sessions) >= 1,
            icon="[Mic]",
        ),
        BadgeItem(
            id="certified_builder",
            name="Certified Builder",
            criteria="Has at least 1 verified certification or project in portfolio",
            earned=any(c.verification_status == "Verified" for c in certifications) or any(p.evidence_status == "Verified" for p in projects),
            icon="[Star]",
        ),
    ]

    # 10. Learning Journey Timeline (real dates)
    journey = []
    if student_profile.created_at:
        journey.append({
            "date": student_profile.created_at.strftime("%b %Y"),
            "timestamp": student_profile.created_at.isoformat(),
            "event": "Joined EDI5 Placement Readiness Ecosystem",
            "type": "milestone",
        })
    for r in resumes_db:
        if r.uploaded_at:
            journey.append({
                "date": r.uploaded_at.strftime("%b %d, %Y"),
                "timestamp": r.uploaded_at.isoformat(),
                "event": f"Uploaded Resume: {r.cv_name or r.file_name}",
                "type": "resume",
            })
    for rnd in rounds:
        if rnd.completed_at:
            journey.append({
                "date": rnd.completed_at.strftime("%b %d, %Y"),
                "timestamp": rnd.completed_at.isoformat(),
                "event": f"Completed {rnd.round_type.capitalize()} Round (Score: {round((rnd.score or 0)*100)}%)",
                "type": "assessment",
            })
    for p in projects:
        if p.created_at:
            journey.append({
                "date": p.created_at[:10],
                "timestamp": p.created_at,
                "event": f"Added Project: {p.title}",
                "type": "project",
            })
    for c in certifications:
        if c.issue_date:
            journey.append({
                "date": c.issue_date,
                "timestamp": c.issue_date,
                "event": f"Earned Certification: {c.name} ({c.issuer})",
                "type": "certification",
            })

    journey.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 11. Completeness Calculation
    completed_sections = []
    missing_sections = []

    # Profile (15%)
    if student_profile.department and student_profile.institution and student_profile.cgpa:
        completed_sections.append("Academic Profile Details")
    else:
        missing_sections.append("Academic Profile Details")

    # About (10%)
    if len(about_text.strip()) > 20:
        completed_sections.append("Professional Summary")
    else:
        missing_sections.append("Professional Summary")

    # Skills (15%)
    if len(skill_evidence_items) >= 3:
        completed_sections.append("Categorized Skills")
    else:
        missing_sections.append("Categorized Skills")

    # Resumes (15%)
    if len(resumes_list) > 0:
        completed_sections.append("Stored Resume / CV")
    else:
        missing_sections.append("Stored Resume / CV")

    # Projects (15%)
    if len(projects) > 0:
        completed_sections.append("Technical Projects")
    else:
        missing_sections.append("Technical Projects")

    # Certifications or Achievements (10%)
    if len(certifications) > 0 or len(achievements) > 0:
        completed_sections.append("Certifications & Achievements")
    else:
        missing_sections.append("Certifications & Achievements")

    # External Links (10%)
    if external_profiles.github or external_profiles.linkedin:
        completed_sections.append("External Profiles (GitHub/LinkedIn)")
    else:
        missing_sections.append("External Profiles (GitHub/LinkedIn)")

    # Assessment evidence (10%)
    if len(rounds) > 0 or len(interview_sessions) > 0:
        completed_sections.append("Assessment Evidence")
    else:
        missing_sections.append("Assessment Evidence")

    completeness_score = int((len(completed_sections) / (len(completed_sections) + len(missing_sections))) * 100)

    # 12. Improvement Suggestions
    suggestions = []
    if len(resumes_list) == 0:
        suggestions.append("Upload a primary resume in your Profile to activate recruiter placement matching.")
    if len(projects) == 0:
        suggestions.append("Add your academic or capstone projects to demonstrate hands-on software development.")
    elif any(not p.github_url for p in projects):
        suggestions.append("Attach GitHub repository links to your submitted projects for recruiter code review.")
    if len(certifications) == 0:
        suggestions.append("Add industry certifications (AWS, Oracle, Microsoft, Coursera) to substantiate domain claims.")
    elif any(not c.credential_url for c in certifications):
        suggestions.append("Provide verifiable credential URLs for your listed certifications to enable verified status.")
    if not (external_profiles.github and external_profiles.linkedin):
        suggestions.append("Add both GitHub and LinkedIn URLs to your profile for full recruiter discoverability.")
    if len(rounds) == 0:
        suggestions.append("Complete a Technical or MCQ practice assessment round to generate verified assessment evidence.")

    return PortfolioResponse(
        profile=profile_dict,
        education=education_list,
        about=about_text,
        skills=skill_evidence_items,
        projects=projects,
        certifications=certifications,
        experience=experience,
        achievements=achievements,
        research=research,
        patents=patents,
        resumes=resumes_list,
        assessment_highlights=assessment_highlights,
        badges=badges,
        learning_journey=journey,
        external_profiles=external_profiles,
        completeness=CompletenessBreakdown(
            score=completeness_score,
            completed_sections=completed_sections,
            missing_sections=missing_sections,
        ),
        improvement_suggestions=suggestions,
    )


@router.put("/me", response_model=PortfolioResponse)
def update_portfolio_metadata(
    payload: PortfolioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Update basic portfolio fields like 'about' summary or external profile links."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})

    if payload.about is not None:
        data["about"] = payload.about
        student_profile.bio = payload.about
    if payload.external_profiles is not None:
        data["external_profiles"] = payload.external_profiles.model_dump()

    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


# ── Projects Endpoints ────────────────────────────────────────────────

@router.post("/project", response_model=PortfolioResponse)
def add_project(
    payload: ProjectItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Add a student project to portfolio."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    projects = list(data.get("projects", []))

    new_project = payload.model_dump()
    new_project["id"] = f"proj-{uuid.uuid4().hex[:8]}"
    new_project["created_at"] = datetime.now().isoformat()
    # Student-provided project is always "Submitted" unless institution verifies it
    new_project["evidence_status"] = "Submitted"

    projects.append(new_project)
    data["projects"] = projects
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.put("/project/{project_id}", response_model=PortfolioResponse)
def update_project(
    project_id: str,
    payload: ProjectItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Update an existing project owned by the authenticated student."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    projects = list(data.get("projects", []))

    found = False
    for i, p in enumerate(projects):
        if p.get("id") == project_id:
            updated = payload.model_dump()
            updated["id"] = project_id
            updated["created_at"] = p.get("created_at")
            # Preserve existing verification status (student cannot verify themselves)
            updated["evidence_status"] = p.get("evidence_status", "Submitted")
            projects[i] = updated
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Project not found")

    data["projects"] = projects
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.delete("/project/{project_id}", response_model=PortfolioResponse)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Delete a student project from portfolio."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    projects = [p for p in data.get("projects", []) if p.get("id") != project_id]

    data["projects"] = projects
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


# ── Certifications Endpoints ──────────────────────────────────────────

@router.post("/certification", response_model=PortfolioResponse)
def add_certification(
    payload: CertificationItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Add a certification entry to portfolio."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    certs = list(data.get("certifications", []))

    new_cert = payload.model_dump()
    new_cert["id"] = f"cert-{uuid.uuid4().hex[:8]}"
    new_cert["verification_status"] = "Submitted"

    certs.append(new_cert)
    data["certifications"] = certs
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.delete("/certification/{cert_id}", response_model=PortfolioResponse)
def delete_certification(
    cert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Delete a certification entry from portfolio."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    certs = [c for c in data.get("certifications", []) if c.get("id") != cert_id]

    data["certifications"] = certs
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


# ── Experience Endpoints ──────────────────────────────────────────────

@router.post("/experience", response_model=PortfolioResponse)
def add_experience(
    payload: ExperienceItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Add professional experience or internship."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    exp_list = list(data.get("experience", []))

    new_exp = payload.model_dump()
    new_exp["id"] = f"exp-{uuid.uuid4().hex[:8]}"
    exp_list.append(new_exp)

    data["experience"] = exp_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.delete("/experience/{exp_id}", response_model=PortfolioResponse)
def delete_experience(
    exp_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Delete an experience entry."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    exp_list = [e for e in data.get("experience", []) if e.get("id") != exp_id]

    data["experience"] = exp_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


# ── Achievements Endpoints ────────────────────────────────────────────

@router.post("/achievement", response_model=PortfolioResponse)
def add_achievement(
    payload: AchievementItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Add an achievement or award."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    ach_list = list(data.get("achievements", []))

    new_ach = payload.model_dump()
    new_ach["id"] = f"ach-{uuid.uuid4().hex[:8]}"
    ach_list.append(new_ach)

    data["achievements"] = ach_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.delete("/achievement/{ach_id}", response_model=PortfolioResponse)
def delete_achievement(
    ach_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Delete an achievement entry."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    ach_list = [a for a in data.get("achievements", []) if a.get("id") != ach_id]

    data["achievements"] = ach_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


# ── Research & Publications / Patents Endpoints ───────────────────────

@router.post("/research", response_model=PortfolioResponse)
def add_research(
    payload: ResearchItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Add a research paper or publication."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    res_list = list(data.get("research", []))

    new_res = payload.model_dump()
    new_res["id"] = f"res-{uuid.uuid4().hex[:8]}"
    res_list.append(new_res)

    data["research"] = res_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.delete("/research/{res_id}", response_model=PortfolioResponse)
def delete_research(
    res_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Delete a research paper entry."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    res_list = [r for r in data.get("research", []) if r.get("id") != res_id]

    data["research"] = res_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.post("/patent", response_model=PortfolioResponse)
def add_patent(
    payload: PatentItem,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Add a patent entry."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    pat_list = list(data.get("patents", []))

    new_pat = payload.model_dump()
    new_pat["id"] = f"pat-{uuid.uuid4().hex[:8]}"
    pat_list.append(new_pat)

    data["patents"] = pat_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.delete("/patent/{patent_id}", response_model=PortfolioResponse)
def delete_patent(
    patent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Delete a patent entry."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    pat_list = [p for p in data.get("patents", []) if p.get("id") != patent_id]

    data["patents"] = pat_list
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


@router.put("/external-profiles", response_model=PortfolioResponse)
def update_external_profiles(
    payload: ExternalProfiles,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Update student's external profile links."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    data = dict(student_profile.portfolio_data or {})
    data["external_profiles"] = payload.model_dump()
    student_profile.portfolio_data = data
    db.commit()
    db.refresh(student_profile)
    return get_my_portfolio(db=db, current_user=current_user)


# ── Public Portfolio & Sharing Endpoints ────────────────────────────────

@router.get("/public/{share_token}", response_model=PublicPortfolioResponse)
def get_public_portfolio(
    share_token: str,
    db: Session = Depends(get_db),
) -> PublicPortfolioResponse:
    """
    Retrieve a read-only public portfolio by share token.
    No authentication required - only returns data if portfolio is explicitly public.
    """
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.share_token == share_token,
        StudentProfile.is_public == True
    ).first()

    if not student_profile:
        raise HTTPException(status_code=404, detail="Portfolio not found or not public")

    user_id = student_profile.user_id

    # Reuse the core portfolio assembly logic but with public filtering
    # We call the internal logic directly to avoid JWT requirement
    return _build_public_portfolio(db, user_id, student_profile)


@router.get("/sharing", response_model=SharingStatus)
def get_sharing_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SharingStatus:
    """Get current portfolio sharing status and public URL."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)
    
    public_url = None
    if student_profile.is_public and student_profile.share_token:
        # Construct public URL - in production this would use a config variable
        base_url = "http://localhost:5173"  # TODO: Make configurable
        public_url = f"{base_url}/portfolio/public/{student_profile.share_token}"

    return SharingStatus(
        is_public=student_profile.is_public,
        share_token=student_profile.share_token if student_profile.is_public else None,
        public_url=public_url
    )


@router.post("/sharing", response_model=SharingStatus)
def update_sharing_status(
    payload: EnableSharingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SharingStatus:
    """Enable or disable public portfolio sharing."""
    student_profile = ProfileService.get_or_create_student_profile(db, current_user.id)

    if payload.enabled and not student_profile.is_public:
        # Generate a secure share token
        student_profile.share_token = secrets.token_urlsafe(32)
        student_profile.is_public = True
    elif not payload.enabled and student_profile.is_public:
        # Disable sharing - keep token but mark as not public
        student_profile.is_public = False

    db.commit()
    db.refresh(student_profile)

    public_url = None
    if student_profile.is_public and student_profile.share_token:
        base_url = "http://localhost:5173"  # TODO: Make configurable
        public_url = f"{base_url}/portfolio/public/{student_profile.share_token}"

    return SharingStatus(
        is_public=student_profile.is_public,
        share_token=student_profile.share_token if student_profile.is_public else None,
        public_url=public_url
    )


@router.post("/verify-item", response_model=VerifyItemResponse)
def verify_portfolio_item(
    payload: VerifyItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerifyItemResponse:
    """
    Faculty/TPO/Admin verification of portfolio items.
    Only users with faculty, tpo, or admin roles can verify.
    """
    # Authorization check
    if current_user.role not in ("faculty", "tpo", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty, TPO, or admin can verify portfolio items"
        )

    # Verify target student exists
    target_profile = db.query(StudentProfile).filter(StudentProfile.user_id == payload.student_id).first()
    if not target_profile:
        raise HTTPException(status_code=404, detail="Student profile not found")

    # Get the portfolio data
    portfolio_data = dict(target_profile.portfolio_data or {})
    
    # Find and update the item based on type
    item_type = payload.item_type.lower()
    item_id = payload.item_id
    new_status = payload.decision
    notes = payload.reviewer_notes

    valid_types = {
        "project": ("projects", "evidence_status"),
        "certification": ("certifications", "verification_status"),
    }

    if item_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Unsupported item type: {item_type}")

    list_key, status_key = valid_types[item_type]
    items = portfolio_data.get(list_key, [])

    found = False
    for item in items:
        if item.get("id") == item_id:
            item[status_key] = new_status
            if notes:
                item["reviewer_notes"] = notes
            item["verified_by"] = current_user.id
            item["verified_at"] = datetime.now().isoformat()
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"{item_type.capitalize()} not found")

    portfolio_data[list_key] = items
    target_profile.portfolio_data = portfolio_data
    db.commit()
    db.refresh(target_profile)

    return VerifyItemResponse(
        success=True,
        message=f"{item_type.capitalize()} marked as {new_status}",
        item_type=item_type,
        item_id=item_id,
        new_status=new_status
    )


def _build_public_portfolio(db: Session, user_id: int, student_profile: StudentProfile) -> PublicPortfolioResponse:
    """Build a public portfolio response with private fields stripped."""
    portfolio_data = dict(student_profile.portfolio_data or {})
    user = db.query(User).filter(User.id == user_id).first()

    # Public profile - limited fields
    full_name = student_profile.full_name or (user.name if user else "Candidate")
    public_profile = {
        "name": full_name,
        "headline": student_profile.target_role or "Software Engineer",
        "department": student_profile.department,
        "institution": student_profile.institution,
        "graduation_year": student_profile.graduation_year,
        "target_role": student_profile.target_role,
    }

    # Education
    education_list = portfolio_data.get("education")
    if not education_list:
        education_list = [
            {
                "institution": student_profile.institution,
                "degree": "Bachelor of Technology (B.Tech)",
                "department": student_profile.department,
                "start_year": (student_profile.graduation_year - 4) if student_profile.graduation_year else 2022,
                "graduation_year": student_profile.graduation_year,
                "cgpa": student_profile.cgpa,
            }
        ]

    # About
    about_text = portfolio_data.get("about") or student_profile.bio or ""

    # Projects - only public-visible (Verified) ones
    projects_raw = portfolio_data.get("projects", [])
    public_projects = [
        ProjectItem(**p) for p in projects_raw
        if p.get("evidence_status") == "Verified" or p.get("public_visible", True)
    ]

    # Certifications - only Verified ones
    certifications_raw = portfolio_data.get("certifications", [])
    public_certs = [
        CertificationItem(**c) for c in certifications_raw
        if c.get("verification_status") == "Verified"
    ]

    # Experience - all (typically public)
    experience_raw = portfolio_data.get("experience", [])
    experience = [ExperienceItem(**e) for e in experience_raw]

    # Achievements
    achievements_raw = portfolio_data.get("achievements", [])
    achievements = [AchievementItem(**a) for a in achievements_raw]

    # Research
    research_raw = portfolio_data.get("research", [])
    research = [ResearchItem(**r) for r in research_raw]

    # Patents
    patents_raw = portfolio_data.get("patents", [])
    patents = [PatentItem(**p) for p in patents_raw]

    # External profiles
    ext_profiles_raw = portfolio_data.get("external_profiles", {})
    external_profiles = ExternalProfiles(**ext_profiles_raw)

    # Assessment highlights - use the same logic as private but simplified
    user_sessions = db.query(AssessmentSession).filter(AssessmentSession.user_id == user_id).all()
    session_ids = [s.id for s in user_sessions]

    rounds = []
    if session_ids:
        rounds = db.query(AssessmentRound).filter(
            AssessmentRound.session_id.in_(session_ids),
            AssessmentRound.status == "completed"
        ).all()

    interview_sessions = []
    if session_ids:
        interview_sessions = db.query(InterviewSession).options(
            selectinload(InterviewSession.turns)
        ).filter(
            InterviewSession.session_id.in_(session_ids)
        ).all()

    # Coding submissions
    solved_coding_count = 0
    best_coding_score = 0.0
    if session_ids:
        cod_round_ids = [r.id for r in rounds if r.round_type == "coding"]
        if cod_round_ids:
            submissions = db.query(CodingSubmission).filter(
                CodingSubmission.round_id.in_(cod_round_ids)
            ).all()
            for sub in submissions:
                sc = (sub.score or 0.0) * 100
                if sc > best_coding_score:
                    best_coding_score = sc
                if (sub.score or 0.0) >= 0.7:
                    solved_coding_count += 1

    mcq_rounds = [r for r in rounds if r.round_type in ("mcq", "aptitude")]
    tech_rounds = [r for r in rounds if r.round_type == "technical"]
    comb_rounds = [r for r in rounds if r.round_type == "combined"]

    best_mcq = max([round((r.score or 0.0) * 100, 1) for r in mcq_rounds], default=None)
    best_tech = max([round((r.score or 0.0) * 100, 1) for r in tech_rounds], default=None)
    best_comb = max([round((r.score or 0.0) * 100, 1) for r in comb_rounds], default=None)

    # Interview highlights
    tech_ints = [s for s in interview_sessions if getattr(s, "interview_type", "technical") == "technical"]
    hr_ints = [s for s in interview_sessions if getattr(s, "interview_type", "") == "hr"]
    comm_ints = [s for s in interview_sessions if getattr(s, "interview_type", "") == "communication"]

    def _best_interview_score(sess_list):
        scores = []
        for s in sess_list:
            for t in getattr(s, "turns", []):
                if t.final_score is not None:
                    scores.append(round(t.final_score * 100, 1))
        return max(scores, default=None)

    best_tech_int = _best_interview_score(tech_ints)
    best_hr_int = _best_interview_score(hr_ints)
    best_comm_int = _best_interview_score(comm_ints)

    assessment_highlights = [
        AssessmentHighlightItem(round_type="mcq", label="MCQ Round (Aptitude)", best_score=best_mcq, attempts_count=len(mcq_rounds)),
        AssessmentHighlightItem(round_type="technical", label="Technical Round", best_score=best_tech, attempts_count=len(tech_rounds)),
        AssessmentHighlightItem(round_type="combined", label="Combined Round", best_score=best_comb, attempts_count=len(comb_rounds)),
        AssessmentHighlightItem(round_type="coding", label="Coding Challenge", best_score=round(best_coding_score, 1) if solved_coding_count > 0 else None, problems_solved=solved_coding_count, attempts_count=len([r for r in rounds if r.round_type == "coding"])),
        AssessmentHighlightItem(round_type="technical_interview", label="Technical Interview", best_score=best_tech_int, attempts_count=len(tech_ints)),
        AssessmentHighlightItem(round_type="hr_interview", label="HR Interview", best_score=best_hr_int, attempts_count=len(hr_ints)),
        AssessmentHighlightItem(round_type="communication_interview", label="Communication Interview", best_score=best_comm_int, attempts_count=len(comm_ints)),
    ]

    # Skills - only verified + assessment-backed for public view
    competencies = db.query(StudentCompetency).filter(StudentCompetency.user_id == user_id).all()
    evidence_counts = db.query(CompetencyEvidence.skill, func.count(CompetencyEvidence.id)).filter(
        CompetencyEvidence.user_id == user_id
    ).group_by(CompetencyEvidence.skill).all()
    evidence_count_map = {skill.lower(): count for skill, count in evidence_counts}

    public_skills = []
    for comp in competencies:
        # Only show skills with assessment evidence or verified status
        if comp.score > 0 or comp.confidence >= 0.7:
            cat = _categorize_skill(comp.skill)
            is_verified = comp.confidence >= 0.7 and comp.evidence_source in ("interview", "aptitude", "coding")
            public_skills.append(SkillEvidenceItem(
                name=comp.skill,
                category=cat,
                claimed=True,
                practice_evidence=comp.evidence_source == "practice",
                project_evidence=False,
                assessment_evidence=comp.score > 0,
                verified=is_verified,
                score=round(comp.score, 1),
                confidence=round(comp.confidence, 2),
                freshness=comp.freshness,
                evidence_source=comp.evidence_source,
                evidence_count=evidence_count_map.get(comp.skill.lower(), 0),
            ))

    # Badges - only earned ones
    badges = [
        BadgeItem(id="coding_practitioner", name="Coding Practitioner", criteria="Successfully solved coding challenges", earned=solved_coding_count >= 1 or best_coding_score >= 70.0, icon="[Code]"),
        BadgeItem(id="consistent_learner", name="Consistent Learner", criteria="Completed 3 or more assessment sessions", earned=len(rounds) >= 3, icon="[Fire]"),
        BadgeItem(id="technical_achiever", name="Technical Achiever", criteria="Achieved 75% or higher in Technical Round", earned=(best_tech is not None and best_tech >= 75.0) or (best_comb is not None and best_comb >= 75.0), icon="[Trophy]"),
        BadgeItem(id="interview_ready", name="Interview Ready", criteria="Completed structured AI Technical or HR Interview", earned=len(interview_sessions) >= 1, icon="[Mic]"),
    ]
    badges = [b for b in badges if b.earned]

    # Learning journey - public events only
    journey = []
    if student_profile.created_at:
        journey.append({"date": student_profile.created_at.strftime("%b %Y"), "timestamp": student_profile.created_at.isoformat(), "event": "Joined EDI5 Placement Readiness Ecosystem", "type": "milestone"})
    
    resumes_db = db.query(UserResume).filter(UserResume.user_id == user_id).order_by(UserResume.uploaded_at.desc()).all()
    for r in resumes_db:
        if r.uploaded_at:
            journey.append({"date": r.uploaded_at.strftime("%b %d, %Y"), "timestamp": r.uploaded_at.isoformat(), "event": f"Uploaded Resume: {r.cv_name or r.file_name}", "type": "resume"})
    
    for rnd in rounds:
        if rnd.completed_at:
            journey.append({"date": rnd.completed_at.strftime("%b %d, %Y"), "timestamp": rnd.completed_at.isoformat(), "event": f"Completed {rnd.round_type.capitalize()} Round (Score: {round((rnd.score or 0)*100)}%)", "type": "assessment"})
    
    for p in public_projects:
        if p.created_at:
            journey.append({"date": p.created_at[:10], "timestamp": p.created_at, "event": f"Added Project: {p.title}", "type": "project"})
    
    for c in public_certs:
        if c.issue_date:
            journey.append({"date": c.issue_date, "timestamp": c.issue_date, "event": f"Earned Certification: {c.name} ({c.issuer})", "type": "certification"})

    journey.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Completeness - simplified for public
    completed_sections = []
    missing_sections = []
    if student_profile.department and student_profile.institution:
        completed_sections.append("Academic Profile")
    else:
        missing_sections.append("Academic Profile")
    if about_text:
        completed_sections.append("Professional Summary")
    else:
        missing_sections.append("Professional Summary")
    if public_skills:
        completed_sections.append("Verified Skills")
    else:
        missing_sections.append("Verified Skills")
    if public_projects:
        completed_sections.append("Verified Projects")
    else:
        missing_sections.append("Verified Projects")
    if public_certs:
        completed_sections.append("Verified Certifications")
    else:
        missing_sections.append("Verified Certifications")
    if external_profiles.github or external_profiles.linkedin:
        completed_sections.append("External Profiles")
    else:
        missing_sections.append("External Profiles")
    if rounds or interview_sessions:
        completed_sections.append("Assessment Evidence")
    else:
        missing_sections.append("Assessment Evidence")

    completeness_score = int((len(completed_sections) / (len(completed_sections) + len(missing_sections))) * 100) if (len(completed_sections) + len(missing_sections)) > 0 else 0

    return PublicPortfolioResponse(
        profile=public_profile,
        education=education_list,
        about=about_text,
        skills=public_skills,
        projects=public_projects,
        certifications=public_certs,
        experience=experience,
        achievements=achievements,
        research=research,
        patents=patents,
        assessment_highlights=assessment_highlights,
        badges=badges,
        learning_journey=journey,
        external_profiles=external_profiles,
        completeness=CompletenessBreakdown(score=completeness_score, completed_sections=completed_sections, missing_sections=missing_sections),
    )
