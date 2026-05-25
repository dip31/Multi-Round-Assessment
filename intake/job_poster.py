"""
Job Poster Agent — Stage 1
Posts jobs to multiple platforms: LinkedIn, Indeed, Naukri, Adzuna.
Automatically switches between simulation and real APIs based on configuration.
"""
import json
import os
import uuid
from datetime import datetime, timedelta
from html import escape
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from shared.db.database import get_db, generate_id
from shared.db.models import Job, JobPosting, AuditLog
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from shared.auth.jwt_middleware import get_current_user
from config import (
    PRODUCTION_MODE,
    LINKEDIN_CLIENT_ID, LINKEDIN_ACCESS_TOKEN, LINKEDIN_COMPANY_ID,
    INDEED_API_KEY, INDEED_EMPLOYER_ID,
    ADZUNA_FEED_URL, COMPANY_CAREERS_BASE_URL, COMPANY_NAME
)

router = APIRouter(prefix="/intake", tags=["Intake — Stage 1"])


class JobPostRequest(BaseModel):
    job_id: str
    platforms: list[str] = ["linkedin", "indeed", "naukri", "adzuna"]


class JobPostResponse(BaseModel):
    success: bool
    job_id: str
    postings: list[dict]
    message: str


# ── Real API Implementations ──────────────────────────────────

async def _post_to_linkedin_real(job: Job) -> dict:
    """Post job to LinkedIn using real API (2024 simpleJobPostings)."""
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_ACCESS_TOKEN:
        return {
            "platform": "linkedin",
            "status": "failed",
            "error": "LinkedIn API credentials not configured. Add LINKEDIN_CLIENT_ID, LINKEDIN_ACCESS_TOKEN, and LINKEDIN_COMPANY_ID to .env"
        }
    
    # Get company ID from config (you'll need to add this to .env)
    company_id = os.getenv("LINKEDIN_COMPANY_ID", "")
    if not company_id:
        return {
            "platform": "linkedin",
            "status": "failed",
            "error": "LINKEDIN_COMPANY_ID not configured in .env. Get this from your LinkedIn company page."
        }
    
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "x-restli-method": "batch_create",
            "LinkedIn-Version": "202603"
        }
        
        # Map employment type to LinkedIn format
        employment_status_map = {
            "full-time": "FULL_TIME",
            "part-time": "PART_TIME", 
            "contract": "CONTRACT",
            "internship": "INTERNSHIP",
            "temporary": "TEMPORARY",
            "volunteer": "VOLUNTEER"
        }
        
        # LinkedIn simpleJobPostings API payload (2024)
        payload = {
            "elements": [{
                "company": f"urn:li:company:{company_id}",
                "externalJobPostingId": f"job_{job.id}_{int(datetime.utcnow().timestamp())}",
                "jobPostingOperationType": "CREATE",
                "listingType": "BASIC",  # or "PREMIUM" for promoted jobs
                "title": job.title,
                "description": job.description or f"Join our team as a {job.title}",
                "location": job.location or "India",
                "employmentStatus": employment_status_map.get(job.employment_type, "FULL_TIME"),
                "workplaceTypes": ["remote"] if "remote" in (job.location or "").lower() else ["on_site"],
                "companyApplyUrl": f"https://yourcompany.com/apply/{job.id}",  # Replace with actual URL
                "listedAt": int(datetime.utcnow().timestamp() * 1000)  # LinkedIn expects milliseconds
            }]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.linkedin.com/v2/simpleJobPostings",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                elements = result.get("elements", [])
                if elements and elements[0].get("status") == 202:
                    task_id = elements[0].get("id", "").split(":")[-1]
                    return {
                        "platform": "linkedin",
                        "status": "posted",
                        "external_id": task_id,
                        "post_url": f"https://linkedin.com/jobs/search/?f_C={company_id}",
                        "posted_at": datetime.utcnow(),
                        "note": "Job posted successfully. It may take 1-2 hours to appear on LinkedIn."
                    }
                else:
                    error_msg = elements[0].get("error", {}).get("message", "Unknown error") if elements else "No response elements"
                    return {
                        "platform": "linkedin",
                        "status": "failed",
                        "error": f"LinkedIn API error: {error_msg}"
                    }
            else:
                return {
                    "platform": "linkedin",
                    "status": "failed",
                    "error": f"LinkedIn API error: {response.status_code} - {response.text}"
                }
                
    except Exception as e:
        return {
            "platform": "linkedin",
            "status": "failed",
            "error": f"LinkedIn posting error: {str(e)}"
        }


async def _post_to_indeed_real(job: Job) -> dict:
    """Post job to Indeed using real GraphQL API (2024)."""
    if not INDEED_API_KEY:
        return {
            "platform": "indeed",
            "status": "failed",
            "error": "Indeed API credentials not configured. Add INDEED_API_KEY (OAuth access token) to .env"
        }
    
    try:
        headers = {
            "Authorization": f"Bearer {INDEED_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Map employment type to Indeed format
        employment_type_map = {
            "full-time": "FULL_TIME",
            "part-time": "PART_TIME",
            "contract": "CONTRACT", 
            "internship": "INTERNSHIP",
            "temporary": "TEMPORARY"
        }
        
        # Indeed GraphQL Job Sync API mutation (2024)
        mutation = """
        mutation SubmitJobPosting($input: SubmitJobPostingInput!) {
            submitJobPosting(input: $input) {
                jobPosting {
                    id
                    title
                    status
                    jobPostingUrl
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "employerId": os.getenv("INDEED_EMPLOYER_ID", "your-employer-id"),  # You'll need to add this
                "title": job.title,
                "description": job.description or f"We are hiring for {job.title}",
                "employmentType": employment_type_map.get(job.employment_type, "FULL_TIME"),
                "location": {
                    "city": job.location or "Remote",
                    "country": "IN"
                },
                "compensation": {
                    "min": int(job.salary_min) if job.salary_min else None,
                    "max": int(job.salary_max) if job.salary_max else None,
                    "currency": "INR"
                } if job.salary_min else None,
                "applicationMethod": {
                    "type": "EXTERNAL_URL",
                    "url": f"https://yourcompany.com/apply/{job.id}"  # Replace with actual URL
                }
            }
        }
        
        payload = {
            "query": mutation,
            "variables": variables
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://apis.indeed.com/graphql",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                data = result.get("data", {})
                submit_result = data.get("submitJobPosting", {})
                
                if submit_result.get("userErrors"):
                    errors = submit_result["userErrors"]
                    error_msg = "; ".join([f"{err['field']}: {err['message']}" for err in errors])
                    return {
                        "platform": "indeed",
                        "status": "failed",
                        "error": f"Indeed validation errors: {error_msg}"
                    }
                
                job_posting = submit_result.get("jobPosting", {})
                if job_posting:
                    return {
                        "platform": "indeed",
                        "status": "posted",
                        "external_id": job_posting.get("id"),
                        "post_url": job_posting.get("jobPostingUrl"),
                        "posted_at": datetime.utcnow(),
                        "note": "Job posted successfully. It may take 1-2 hours to appear on Indeed."
                    }
                else:
                    return {
                        "platform": "indeed",
                        "status": "failed",
                        "error": "Indeed API returned no job posting data"
                    }
            else:
                return {
                    "platform": "indeed",
                    "status": "failed",
                    "error": f"Indeed API error: {response.status_code} - {response.text}"
                }
                
    except Exception as e:
        return {
            "platform": "indeed",
            "status": "failed",
            "error": f"Indeed posting error: {str(e)}"
        }


async def _post_to_naukri_real(job: Job) -> dict:
    """Post job to Naukri - Manual posting required (no public API)."""
    return {
        "platform": "naukri",
        "status": "manual_required",
        "error": "Naukri doesn't provide a public job posting API. Please post manually at https://recruit.naukri.com/",
        "manual_url": "https://recruit.naukri.com/hiringsuite/naukri-jobposting.html",
        "job_details": {
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "experience": f"{job.experience_min}-{job.experience_max} years" if job.experience_min else "Not specified",
            "salary": f"₹{int(job.salary_min/100000)}-{int(job.salary_max/100000)} LPA" if job.salary_min else "Not disclosed"
        },
        "instructions": [
            "1. Visit https://recruit.naukri.com/",
            "2. Login to your recruiter account", 
            "3. Click 'Post a Job'",
            "4. Fill in the job details provided above",
            "5. Submit and pay for the job posting"
        ]
    }


async def _post_to_adzuna_feed(job: Job) -> dict:
    """
    Prepare a job for Adzuna distribution through an XML feed.

    Adzuna's public developer API exposes job search and market-data endpoints,
    not a public create-job endpoint. Recruiter distribution is handled through
    Adzuna's job feed, ATS integration, or sponsored listing channels.
    """
    feed_url = ADZUNA_FEED_URL or "/api/intake/adzuna-feed.xml"
    apply_url = f"{COMPANY_CAREERS_BASE_URL.rstrip('/')}/apply/{job.id}"

    return {
        "platform": "adzuna",
        "status": "feed_ready",
        "external_id": f"adzuna_feed_{job.id}",
        "post_url": feed_url,
        "posted_at": datetime.utcnow(),
        "note": "Adzuna does not expose a public create-job API. This job is available via the Adzuna XML feed for partner/ATS ingestion.",
        "manual_url": "https://www.adzuna.com/hire/products/job-listings/",
        "job_details": {
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "experience": f"{job.experience_min}-{job.experience_max} years" if job.experience_min else "Not specified",
            "salary": f"{job.currency or 'INR'} {int(job.salary_min)}-{int(job.salary_max)}" if job.salary_min and job.salary_max else "Not disclosed",
            "apply_url": apply_url,
        },
        "instructions": [
            "Share the XML feed URL with Adzuna during recruiter/ATS onboarding.",
            "Keep this job active or posted so it remains in the feed.",
            "Use Adzuna sponsored single-job ads from their recruiter product when direct paid promotion is needed.",
        ],
    }



# ── Simulation Functions ──────────────────────────────────

async def _post_to_linkedin_sim(job: Job) -> dict:
    """Simulate LinkedIn job posting (matches real API response format)."""
    task_id = f"linkedin_task_{uuid.uuid4().hex[:8]}"
    company_id = os.getenv("LINKEDIN_COMPANY_ID", "demo-company")
    
    return {
        "platform": "linkedin",
        "status": "posted",
        "external_id": task_id,
        "post_url": f"https://linkedin.com/jobs/search/?f_C={company_id}",
        "posted_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30),
        "note": "SIMULATION: Job posted successfully. Add LINKEDIN_ACCESS_TOKEN to .env for real posting."
    }


async def _post_to_indeed_sim(job: Job) -> dict:
    """Simulate Indeed job posting (matches real API response format)."""
    job_id = f"indeed_{uuid.uuid4().hex[:8]}"
    return {
        "platform": "indeed",
        "status": "posted",
        "external_id": job_id,
        "post_url": f"https://indeed.com/viewjob?jk={job_id}",
        "posted_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30),
        "note": "SIMULATION: Job posted successfully. Add INDEED_API_KEY to .env for real posting."
    }


async def _post_to_naukri_sim(job: Job) -> dict:
    """Simulate Naukri job posting (manual posting required in reality)."""
    return {
        "platform": "naukri",
        "status": "manual_required",
        "external_id": None,
        "post_url": "https://recruit.naukri.com/hiringsuite/naukri-jobposting.html",
        "posted_at": datetime.utcnow(),
        "note": "SIMULATION: Naukri requires manual posting. Visit https://recruit.naukri.com/ to post jobs.",
        "job_details": {
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "experience": f"{job.experience_min}-{job.experience_max} years" if job.experience_min else "Not specified",
            "salary": f"₹{int(job.salary_min/100000)}-{int(job.salary_max/100000)} LPA" if job.salary_min else "Not disclosed"
        }
    }


async def _post_to_adzuna_sim(job: Job) -> dict:
    """Simulate Adzuna feed preparation."""
    result = await _post_to_adzuna_feed(job)
    result["note"] = "SIMULATION: Job prepared for Adzuna XML feed. Configure Adzuna partner/ATS ingestion for real distribution."
    return result



# ── Platform Handler Registry ─────────────────────────────

def get_platform_handlers():
    """Get platform handlers based on production mode and available credentials."""
    if PRODUCTION_MODE:
        # In production mode, use real APIs if credentials are available, otherwise fall back to simulation
        return {
            "linkedin": _post_to_linkedin_real if LINKEDIN_ACCESS_TOKEN and LINKEDIN_COMPANY_ID else _post_to_linkedin_sim,
            "indeed": _post_to_indeed_real if INDEED_API_KEY and INDEED_EMPLOYER_ID else _post_to_indeed_sim,
            "naukri": _post_to_naukri_real,
            "adzuna": _post_to_adzuna_feed,
        }
    else:
        # In simulation mode, always use simulation
        return {
            "linkedin": _post_to_linkedin_sim,
            "indeed": _post_to_indeed_sim,
            "naukri": _post_to_naukri_sim,
            "adzuna": _post_to_adzuna_sim,
        }
    


# ── API Endpoints ─────────────────────────────────────────

@router.post("/post-job", response_model=JobPostResponse)
async def post_job(
    req: JobPostRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Post a job to multiple platforms."""
    # Get job
    result = await db.execute(select(Job).where(Job.id == req.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.description:
        raise HTTPException(status_code=400, detail="Job must have a description before posting")

    # Get platform handlers
    platform_handlers = get_platform_handlers()
    
    # Post to each platform
    postings = []
    for platform in req.platforms:
        handler = platform_handlers.get(platform)
        if not handler:
            postings.append({
                "platform": platform,
                "status": "failed",
                "error": f"Platform '{platform}' not supported"
            })
            continue

        try:
            result_data = await handler(job)
            
            # Save posting to DB (skip if no external_id or if manual_required)
            if result_data.get("external_id") and result_data.get("status") not in ["manual_required"]:
                posting = JobPosting(
                    id=generate_id(),
                    job_id=req.job_id,
                    platform=platform,
                    external_id=result_data.get("external_id"),
                    post_url=result_data.get("post_url"),
                    status=result_data.get("status", "posted"),
                    posted_at=result_data.get("posted_at"),
                    expires_at=result_data.get("expires_at"),
                )
                db.add(posting)

            postings.append(result_data)

        except Exception as e:
            postings.append({
                "platform": platform,
                "status": "failed",
                "error": f"Posting error: {str(e)}"
            })

    # Update job status
    job.status = "posted"
    
    # Count successful postings by type
    posted_count = len([p for p in postings if p.get("status") == "posted"])
    manual_count = len([p for p in postings if p.get("status") == "manual_required"])
    feed_count = len([p for p in postings if p.get("status") == "feed_ready"])
    failed_count = len([p for p in postings if p.get("status") == "failed"])
    
    # Determine actual mode used (some platforms may fall back to simulation)
    simulation_used = any("SIMULATION" in p.get("note", "") for p in postings)
    actual_mode = "MIXED" if simulation_used and PRODUCTION_MODE else ("PRODUCTION" if PRODUCTION_MODE else "SIMULATION")
    
    # Audit log
    audit = AuditLog(
        id=generate_id(),
        event_type=EventTopics.JOB_POSTED,
        agent_name="job_poster_agent",
        entity_type="job",
        entity_id=req.job_id,
        details=json.dumps({
            "platforms": req.platforms,
            "posted_count": posted_count,
            "manual_count": manual_count,
            "feed_count": feed_count,
            "failed_count": failed_count,
            "production_mode": PRODUCTION_MODE,
            "actual_mode": actual_mode
        }),
    )
    db.add(audit)
    await db.commit()

    # Publish event
    await event_bus.publish(
        EventTopics.JOB_POSTED,
        {
            "job_id": req.job_id,
            "title": job.title,
            "platforms": req.platforms,
            "posting_count": posted_count,
            "manual_count": manual_count,
            "feed_count": feed_count,
            "failed_count": failed_count,
            "production_mode": PRODUCTION_MODE
        },
        agent="job_poster_agent",
    )

    # Include manual postings in success message
    total_handled = posted_count + manual_count + feed_count
    
    # Build message
    message_parts = [f"Posted to {posted_count}/{len(req.platforms)} platforms"]
    if feed_count > 0:
        message_parts.append(f"{feed_count} prepared for feed ingestion")
    if manual_count > 0:
        message_parts.append(f"{manual_count} require manual posting")
    if failed_count > 0:
        message_parts.append(f"{failed_count} failed")
    
    message = " • ".join(message_parts) + f" ({actual_mode} mode)"
    
    return JobPostResponse(
        success=total_handled > 0,
        job_id=req.job_id,
        postings=postings,
        message=message
    )



@router.get("/postings/{job_id}")
async def get_job_postings(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get all postings for a specific job."""
    result = await db.execute(
        select(JobPosting).where(JobPosting.job_id == job_id)
    )
    postings = result.scalars().all()
    return [
        {
            "id": p.id,
            "platform": p.platform,
            "external_id": p.external_id,
            "post_url": p.post_url,
            "status": p.status,
            "posted_at": p.posted_at,
            "expires_at": p.expires_at,
        }
        for p in postings
    ]


@router.get("/adzuna-feed.xml")
async def get_adzuna_feed(db: AsyncSession = Depends(get_db)):
    """Return an XML job feed suitable for Adzuna partner/ATS ingestion."""
    result = await db.execute(
        select(Job).where(Job.status.in_(["active", "posted"]))
    )
    jobs = result.scalars().all()

    items = []
    for job in jobs:
        apply_url = f"{COMPANY_CAREERS_BASE_URL.rstrip('/')}/apply/{job.id}"
        salary = ""
        if job.salary_min and job.salary_max:
            salary = f"{job.currency or 'INR'} {int(job.salary_min)}-{int(job.salary_max)}"

        items.append(f"""
  <job>
    <id>{escape(str(job.id))}</id>
    <title>{escape(job.title or "")}</title>
    <company>{escape(COMPANY_NAME or "")}</company>
    <location>{escape(job.location or "")}</location>
    <description>{escape(job.description or "")}</description>
    <url>{escape(apply_url)}</url>
    <salary>{escape(salary)}</salary>
    <contract_type>{escape(job.employment_type or "")}</contract_type>
    <created_at>{escape(job.created_at.isoformat() if job.created_at else "")}</created_at>
  </job>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<jobs>{''.join(items)}
</jobs>
"""
    return Response(content=xml, media_type="application/xml")
