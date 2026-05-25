"""
Scoring Engine — scores a candidate against a job's requirements.

Score breakdown (0–100):
  - Skill match:  0–40  (intersection of candidate vs job skills)
  - Experience:   0–30  (candidate.experience_years vs job.experience_min)
  - Education:    0–20  (hierarchy: PhD > Master's > Bachelor's > Associate > other)
  - Location:     0–10  (bonus for exact location match)
"""
import json
import logging

logger = logging.getLogger(__name__)

# Education hierarchy — higher index = higher qualification
EDUCATION_LEVELS = {
    "high school": 1,
    "associate": 2,
    "bachelor's": 3,
    "bachelors": 3,
    "bachelor": 3,
    "b.tech": 3,
    "b.e": 3,
    "b.sc": 3,
    "master's": 4,
    "masters": 4,
    "master": 4,
    "m.tech": 4,
    "m.e": 4,
    "m.sc": 4,
    "mba": 4,
    "phd": 5,
    "doctorate": 5,
}


def _parse_skills(raw):
    """Safely parse skills field — could be a JSON string or already a list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [s.strip().lower() for s in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [s.strip().lower() for s in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _score_skills(candidate_skills, job_skills):
    """Skill match score: 0–40 based on intersection ratio."""
    if not job_skills:
        return 40  # no requirements → full marks
    if not candidate_skills:
        return 0

    c_set = set(candidate_skills)
    j_set = set(job_skills)
    match_count = len(c_set & j_set)
    ratio = match_count / len(j_set)
    return round(ratio * 40)


def _score_experience(candidate_years, job_min):
    """Experience score: 0–30 based on whether candidate meets minimum."""
    if job_min is None or job_min <= 0:
        return 30  # no requirement → full marks
    if candidate_years is None:
        return 0

    if candidate_years >= job_min:
        return 30
    else:
        # partial credit: proportional to how close they are
        ratio = candidate_years / job_min
        return round(ratio * 30)


def _get_education_level(education_str):
    """Map an education string to a numeric level."""
    if not education_str:
        return 0
    key = education_str.strip().lower()
    return EDUCATION_LEVELS.get(key, 1)  # default to 1 (high school) for unknown


def _score_education(candidate_edu, job_qualification):
    """Education score: 0–20 based on meeting required qualification."""
    if not job_qualification:
        return 20  # no requirement → full marks

    c_level = _get_education_level(candidate_edu)
    j_level = _get_education_level(job_qualification)

    if j_level == 0:
        return 20
    if c_level >= j_level:
        return 20
    elif c_level > 0:
        return round((c_level / j_level) * 20)
    return 0


def _score_location(candidate_loc, job_loc):
    """Location bonus: 0–10 for exact match."""
    if not job_loc or not candidate_loc:
        return 0
    if candidate_loc.strip().lower() == job_loc.strip().lower():
        return 10
    return 0


def calculate_score(candidate, job):
    """
    Calculate candidate's total score against a job.

    Args:
        candidate: Candidate ORM object.
        job: Job ORM object.

    Returns:
        (total_score: int, breakdown: dict)
    """
    c_skills = _parse_skills(candidate.skills)
    j_skills = _parse_skills(job.skills)

    skill_score = _score_skills(c_skills, j_skills)
    exp_score = _score_experience(candidate.experience_years, job.experience_min)
    edu_score = _score_education(candidate.education, job.qualification)
    loc_score = _score_location(candidate.location, job.location)

    total = skill_score + exp_score + edu_score + loc_score

    breakdown = {
        "skill_match": skill_score,
        "experience": exp_score,
        "education": edu_score,
        "location": loc_score,
        "total": total,
    }

    logger.info("Score for candidate %s: %d — %s", candidate.id, total, breakdown)
    return total, breakdown
