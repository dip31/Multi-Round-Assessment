"""
Candidate Scraper Agent — DEPRECATED
Candidate scraping is removed from the active pipeline. Use the candidate intake forms and resume upload flow instead.
"""
import json
import uuid
import re
import hashlib
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from shared.db.database import get_db, generate_id
from shared.db.models import Job, Candidate, Application, AuditLog
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from shared.auth.jwt_middleware import get_current_user
from config import (
    PRODUCTION_MODE, GITHUB_API_TOKEN, STACKOVERFLOW_API_KEY,
    LINKEDIN_TALENT_API_KEY, ANGELLIST_API_KEY, HACKERRANK_API_KEY,
    ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY
)

router = APIRouter(prefix="/sourcing", tags=["Sourcing — Stage 2"])


class ScrapeRequest(BaseModel):
    job_id: str | None = None
    skills: list[str] = []
    location: str = ""
    experience_min: int = 0
    experience_max: int = 10
    platforms: list[str] = ["github", "stackoverflow", "linkedin", "angellist"]
    max_results: int = 10


class ScraperTestRequest(ScrapeRequest):
    use_real_apis: bool | None = None


def _normalise_tag(skill: str) -> str:
    """Convert a skill name into a Stack Exchange tag-like value."""
    aliases = {
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "typescript",
        "node.js": "node.js",
        "nodejs": "node.js",
        "react.js": "reactjs",
        "react": "reactjs",
        "vue.js": "vue.js",
        "vue": "vue.js",
        "c#": "c#",
        "c++": "c++",
        "python": "python",
        "fastapi": "fastapi",
        "django": "django",
        "java": "java",
        "spring": "spring",
        "sql": "sql",
        "postgresql": "postgresql",
        "docker": "docker",
        "kubernetes": "kubernetes",
    }
    key = skill.strip().lower()
    return aliases.get(key, key.replace(" ", "-"))


def _seeded_rng(platform: str, skills: list[str], location: str) -> random.Random:
    seed_text = f"{platform}|{','.join(skills)}|{location}".lower()
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(seed)


def _skill_matches(skills: list[str], text: str) -> list[str]:
    haystack = (text or "").lower()
    matches = []
    for skill in skills:
        needle = skill.strip().lower()
        if needle and needle in haystack:
            matches.append(skill)
    return matches


def _location_score(candidate_location: str | None, target_location: str) -> int:
    if not target_location:
        return 0
    if not candidate_location:
        return 0
    return 10 if target_location.lower() in candidate_location.lower() else 0


# ── Real API Implementations ──────────────────────────────────

async def _scrape_github_real(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Scrape GitHub profiles using real API."""
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_API_TOKEN:
            headers["Authorization"] = f"token {GITHUB_API_TOKEN}"

        search_skills = skills[:3] or ["python"]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            candidates_by_login = {}
            seen_logins = set()

            async def add_user(login: str, matched_repo: dict | None = None, matched_skill: str | None = None):
                if not login or login in seen_logins:
                    return
                seen_logins.add(login)

                user_response = await client.get(
                    f"https://api.github.com/users/{login}",
                    headers=headers
                )

                if user_response.status_code != 200:
                    return

                user_data = user_response.json()
                if user_data.get("type") != "User":
                    return

                repos_response = await client.get(
                    f"https://api.github.com/users/{login}/repos",
                    headers=headers,
                    params={"sort": "updated", "per_page": 20}
                )

                user_skills = set()
                repo_text = ""
                if repos_response.status_code == 200:
                    repos = repos_response.json()
                    for user_repo in repos:
                        if user_repo.get("language"):
                            user_skills.add(user_repo["language"])
                        repo_text += " ".join([
                            user_repo.get("name") or "",
                            user_repo.get("description") or "",
                            user_repo.get("language") or "",
                        ]) + " "

                matched_skills = set(_skill_matches(search_skills, repo_text + " " + (user_data.get("bio") or "")))
                if matched_skill:
                    matched_skills.add(matched_skill)
                if not matched_skills and search_skills:
                    matched_skills.add(search_skills[0])

                match_score = len(matched_skills) * 25
                match_score += min(int(user_data.get("followers", 0) or 0), 100) // 10
                match_score += _location_score(user_data.get("location"), location)
                if matched_repo:
                    match_score += min(int(matched_repo.get("stargazers_count", 0) or 0), 500) // 50

                candidates_by_login[login] = {
                    "name": user_data.get("name") or user_data["login"],
                    "email": user_data.get("email"),
                    "location": user_data.get("location"),
                    "current_role": user_data.get("bio") or "Developer",
                    "skills": sorted(user_skills | matched_skills),
                    "source": "github",
                    "source_profile_url": user_data["html_url"],
                    "experience_years": max(1, (datetime.now().year -
                                             datetime.fromisoformat(user_data["created_at"].replace("Z", "+00:00")).year)),
                    "match_score": match_score,
                    "match_reasons": {
                        "matched_skills": sorted(matched_skills),
                        "location_match": bool(_location_score(user_data.get("location"), location)),
                    },
                    "github_stats": {
                        "public_repos": user_data.get("public_repos", 0),
                        "followers": user_data.get("followers", 0),
                        "following": user_data.get("following", 0),
                        "matched_repo": matched_repo.get("html_url") if matched_repo else None,
                        "matched_repo_stars": matched_repo.get("stargazers_count", 0) if matched_repo else 0
                    }
                }

            # Search users first. This respects GitHub's user search qualifiers like
            # language and location, when those profile fields are available.
            for skill in search_skills:
                query_parts = [f"language:{skill}"]
                if location:
                    query_parts.append(f'location:"{location}"')
                response = await client.get(
                    "https://api.github.com/search/users",
                    headers=headers,
                    params={
                        "q": " ".join(query_parts),
                        "sort": "repositories",
                        "order": "desc",
                        "per_page": min(max_results, 20)
                    }
                )
                if response.status_code == 200:
                    for user in response.json().get("items", []):
                        await add_user(user.get("login"), matched_skill=skill)
                        if len(candidates_by_login) >= max_results:
                            break

            # Fallback: search repositories and convert owners to candidate profiles.
            for skill in search_skills:
                if len(candidates_by_login) >= max_results:
                    break
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    headers=headers,
                    params={
                        "q": f"language:{skill} stars:>0",
                        "sort": "updated",
                        "order": "desc",
                        "per_page": min(max_results * 4, 40)
                    }
                )

                if response.status_code != 200:
                    print(f"GitHub API error {response.status_code}: {response.text[:300]}")
                    continue

                for repo in response.json().get("items", []):
                    owner = repo.get("owner") or {}
                    await add_user(owner.get("login"), matched_repo=repo, matched_skill=skill)
                    if len(candidates_by_login) >= max_results:
                        break

            candidates = sorted(candidates_by_login.values(), key=lambda c: c.get("match_score", 0), reverse=True)
            return candidates[:max_results]
            
    except Exception as e:
        print(f"GitHub scraping error: {e}")
        return []


async def _scrape_stackoverflow_real(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Scrape Stack Overflow profiles using real API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            tags = [_normalise_tag(skill) for skill in (skills[:3] or ["python"])]
            candidates_by_user = {}

            params = {"site": "stackoverflow", "pagesize": min(max_results, 30)}
            if STACKOVERFLOW_API_KEY:
                params["key"] = STACKOVERFLOW_API_KEY

            for tag in tags:
                response = await client.get(
                    f"https://api.stackexchange.com/2.3/tags/{tag}/top-answerers/month",
                    params=params
                )

                if response.status_code != 200:
                    print(f"Stack Overflow API error {response.status_code}: {response.text[:300]}")
                    continue

                data = response.json()

                for item in data.get("items", []):
                    user_data = item.get("user") or item
                    user_id = user_data.get("user_id") or user_data.get("account_id") or user_data.get("link")
                    if not user_id:
                        continue

                    existing = candidates_by_user.get(user_id)
                    matched_tags = set(existing.get("match_reasons", {}).get("matched_tags", [])) if existing else set()
                    matched_tags.add(tag)

                    answer_score = item.get("answer_score", 0)
                    post_count = item.get("post_count", 0)
                    reputation = user_data.get("reputation", 0)
                    match_score = len(matched_tags) * 30
                    match_score += min(int(answer_score or 0), 500) // 25
                    match_score += min(int(post_count or 0), 50)
                    match_score += min(int(reputation or 0), 50000) // 5000
                    match_score += _location_score(user_data.get("location"), location)

                    # Estimate experience based on account age and reputation.
                    account_age = (datetime.now().timestamp() - user_data.get("creation_date", 0)) / (365.25 * 24 * 3600)
                    experience_years = max(1, int(account_age))

                    candidates_by_user[user_id] = {
                        "name": user_data.get("display_name", "Stack Overflow User"),
                        "email": None,
                        "location": user_data.get("location"),
                        "current_role": f"{', '.join(sorted(matched_tags))} Developer",
                        "skills": sorted(set(skills or []) | matched_tags),
                        "source": "stackoverflow",
                        "source_profile_url": user_data.get("link"),
                        "experience_years": experience_years,
                        "match_score": match_score,
                        "match_reasons": {
                            "matched_tags": sorted(matched_tags),
                            "location_match": bool(_location_score(user_data.get("location"), location)),
                            "period": "month",
                        },
                        "stackoverflow_stats": {
                            "reputation": reputation,
                            "badge_counts": user_data.get("badge_counts", {}),
                            "answer_score": answer_score,
                            "post_count": post_count,
                            "matched_tag": tag
                        }
                    }

            candidates = sorted(candidates_by_user.values(), key=lambda c: c.get("match_score", 0), reverse=True)
            return candidates[:max_results]
            
    except Exception as e:
        print(f"Stack Overflow scraping error: {e}")
        return []


async def _scrape_linkedin_real(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Scrape LinkedIn profiles using real Talent Solutions API."""
    if not LINKEDIN_TALENT_API_KEY:
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_TALENT_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # LinkedIn Talent Solutions People Search API
        search_criteria = {
            "keywords": " ".join(skills) if skills else "",
            "locationFacet": [location] if location else [],
            "start": 0,
            "count": min(max_results, 25)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.linkedin.com/v2/peopleSearch",
                headers=headers,
                json=search_criteria
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            candidates = []
            
            for person in data.get("elements", [])[:max_results]:
                candidates.append({
                    "name": f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
                    "email": None,  # LinkedIn doesn't provide emails in search
                    "location": person.get("geoLocation", {}).get("name"),
                    "current_role": person.get("headline"),
                    "skills": skills,  # Use searched skills
                    "source": "linkedin",
                    "source_profile_url": person.get("publicProfileUrl"),
                    "experience_years": 3,  # Default estimate
                    "linkedin_data": {
                        "industry": person.get("industry"),
                        "summary": person.get("summary")
                    }
                })
            
            return candidates
            
    except Exception as e:
        print(f"LinkedIn scraping error: {e}")
        return []


async def _scrape_angellist_real(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Scrape AngelList/Wellfound profiles using real API."""
    if not ANGELLIST_API_KEY:
        return []
    
    try:
        headers = {"Authorization": f"Bearer {ANGELLIST_API_KEY}"}
        
        params = {
            "role": "developer",
            "locations[]": location if location else "remote",
            "limit": min(max_results, 20)
        }
        
        if skills:
            params["skills[]"] = skills[0]  # AngelList typically takes one primary skill
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.angel.co/1/talent/search",
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            candidates = []
            
            for person in data.get("talent", [])[:max_results]:
                candidates.append({
                    "name": person.get("name"),
                    "email": person.get("email"),
                    "location": person.get("location"),
                    "current_role": person.get("what"),
                    "skills": person.get("skills", []),
                    "source": "angellist",
                    "source_profile_url": person.get("angellist_url"),
                    "experience_years": person.get("experience", 2),
                    "angellist_data": {
                        "bio": person.get("bio"),
                        "resume_url": person.get("resume_url")
                    }
                })
            
            return candidates
            
    except Exception as e:
        print(f"AngelList scraping error: {e}")
        return []


# ── Simulation Functions ──────────────────────────────────

async def _scrape_github_sim(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Simulate GitHub profile scraping."""
    rng = _seeded_rng("github", skills, location)
    primary = (skills[0] if skills else "Python").title()
    locations = [location or "Remote", "Bangalore", "Pune", "Hyderabad", "Mumbai"]
    candidates = []
    for i in range(min(max_results, 5)):
        suffix = rng.randint(100, 999)
        candidates.append({
            "name": f"{primary} GitHub Developer {suffix}",
            "email": f"{primary.lower().replace(' ', '')}.dev{suffix}@github.example",
            "location": rng.choice(locations),
            "current_role": f"{primary} Software Developer",
            "skills": skills[:3] + ["Git", "Open Source"],
            "source": "github",
            "source_profile_url": f"https://github.com/{primary.lower().replace(' ', '-')}-dev-{suffix}",
            "experience_years": rng.randint(1, 8),
            "note": "SIMULATED - Add GITHUB_API_TOKEN to .env for real scraping"
        })
    return candidates


async def _scrape_stackoverflow_sim(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Simulate Stack Overflow profile scraping."""
    rng = _seeded_rng("stackoverflow", skills, location)
    primary = _normalise_tag(skills[0]) if skills else "python"
    locations = [location or "Global", "Bangalore", "Delhi", "Chennai", "Remote"]
    candidates = []
    for i in range(min(max_results, 3)):
        user_id = rng.randint(10000, 99999)
        candidates.append({
            "name": f"{primary.title()} SO Expert {user_id}",
            "email": None,
            "location": rng.choice(locations),
            "current_role": f"Senior {primary} Developer",
            "skills": skills[:2] + ["Problem Solving", "Technical Writing"],
            "source": "stackoverflow",
            "source_profile_url": f"https://stackoverflow.com/users/{user_id}",
            "experience_years": rng.randint(2, 10),
            "note": "SIMULATED - Add STACKOVERFLOW_API_KEY to .env for real scraping"
        })
    return candidates


async def _scrape_linkedin_sim(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Simulate LinkedIn profile scraping."""
    candidates = []
    for i in range(min(max_results, 4)):
        candidates.append({
            "name": f"LinkedIn Professional {i+1}",
            "email": None,
            "location": location or "India",
            "current_role": f"Senior {skills[0] if skills else 'Software'} Engineer",
            "skills": skills + ["Leadership", "Team Management"],
            "source": "linkedin",
            "source_profile_url": f"https://linkedin.com/in/professional{i+1}",
            "experience_years": 4 + i,
            "note": "SIMULATED - Add LINKEDIN_TALENT_API_KEY to .env for real scraping"
        })
    return candidates


async def _scrape_angellist_sim(skills: list[str], location: str, max_results: int = 10) -> list[dict]:
    """Simulate AngelList profile scraping."""
    candidates = []
    for i in range(min(max_results, 3)):
        candidates.append({
            "name": f"Startup Developer {i+1}",
            "email": f"startup{i+1}@example.com",
            "location": location or "Bangalore",
            "current_role": "Full Stack Developer",
            "skills": skills + ["Startup Experience", "Agile"],
            "source": "angellist",
            "source_profile_url": f"https://wellfound.com/u/startup-dev-{i+1}",
            "experience_years": 2 + i,
            "note": "SIMULATED - Add ANGELLIST_API_KEY to .env for real scraping"
        })
    return candidates


# ── Platform Handler Registry ─────────────────────────────

def get_scraper_handlers():
    """Get scraper handlers based on production mode and available credentials."""
    if PRODUCTION_MODE:
        return {
            "github": _scrape_github_real,
            "stackoverflow": _scrape_stackoverflow_real,
            "linkedin": _scrape_linkedin_real,
            "angellist": _scrape_angellist_real,
            # Note: Adzuna removed - it's a job aggregator, not a candidate database
        }
    else:
        return {
            "github": _scrape_github_sim,
            "stackoverflow": _scrape_stackoverflow_sim,
            "linkedin": _scrape_linkedin_sim,
            "angellist": _scrape_angellist_sim,
            # Note: Adzuna removed - it's a job aggregator, not a candidate database
        }


# ── API Endpoints ─────────────────────────────────────────

def get_real_scraper_handlers():
    """Get real scraper handlers regardless of PRODUCTION_MODE, useful for diagnostics."""
    return {
        "github": _scrape_github_real,
        "stackoverflow": _scrape_stackoverflow_real,
        "linkedin": _scrape_linkedin_real,
        "angellist": _scrape_angellist_real,
    }


def get_sim_scraper_handlers():
    """Get simulation scraper handlers regardless of PRODUCTION_MODE."""
    return {
        "github": _scrape_github_sim,
        "stackoverflow": _scrape_stackoverflow_sim,
        "linkedin": _scrape_linkedin_sim,
        "angellist": _scrape_angellist_sim,
    }


async def _hydrate_scrape_request_from_job(req: ScrapeRequest, db: AsyncSession):
    """Fill missing scrape fields from a selected job."""
    if not req.job_id:
        return None

    result = await db.execute(select(Job).where(Job.id == req.job_id))
    job_data = result.scalar_one_or_none()
    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job with id {req.job_id} not found")

    if not req.skills and job_data.skills:
        try:
            req.skills = json.loads(job_data.skills) if isinstance(job_data.skills, str) else job_data.skills
        except (json.JSONDecodeError, TypeError):
            req.skills = [job_data.skills] if job_data.skills else []

    if not req.location and job_data.location:
        req.location = job_data.location

    if req.experience_min == 0 and job_data.experience_min is not None:
        req.experience_min = job_data.experience_min

    if req.experience_max == 10 and job_data.experience_max is not None:
        req.experience_max = job_data.experience_max

    return job_data


@router.post("/test-scrapers", include_in_schema=False)
async def test_scrapers(
    req: ScraperTestRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Candidate scraping is disabled. Use candidate intake and resume upload instead.
    """
    raise HTTPException(
        status_code=410,
        detail="Candidate scraping has been removed from the pipeline. Use resume/manual intake routes instead.",
    )


@router.post("/scrape-profiles", include_in_schema=False)
async def scrape_profiles(
    req: ScrapeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Candidate scraping is disabled."""
    raise HTTPException(
        status_code=410,
        detail="Candidate scraping has been removed from the pipeline. Use resume/manual intake routes instead.",
    )
@router.get("/scraping-status", include_in_schema=False)
async def get_scraping_status():
    """Candidate scraping is removed from the active pipeline."""
    raise HTTPException(
        status_code=410,
        detail="Candidate scraping has been removed from the pipeline. Scraping status is no longer available.",
    )
