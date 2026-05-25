"""
Demo: Score a resume against a sample job to show how the scoring engine works.
"""
import json
import sys
import os
import io
import uuid

# Fix Windows console encoding — prevents UnicodeEncodeError with special characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.db.database import engine, get_db
from shared.db.models import Base, Candidate, Job
from screening.scoring_engine import calculate_score
from screening.duplicate_detector import check_duplicate
from screening.processor import process_candidate

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Get database session
db_gen = get_db()
db = next(db_gen)

# ── Create a sample Job ──────────────────────────────────────────────────────
job = Job(
    title="Frontend Developer Intern (Insurance Tech Startup)",
    skills=json.dumps(["javascript", "react", "nodejs", "mongodb", "html", "css"]),
    experience_min=0,
    experience_max=2,
    qualification="bachelor's",
    location="Pune",
    description="Looking for a frontend developer intern with React.js experience.",
)
db.add(job)
db.commit()

# ── Create Candidate from the resume ─────────────────────────────────────────
candidate = Candidate(
    name="Kumar",
    email="kumar@example.com",
    phone="9999999999",
    skills=json.dumps(["javascript", "react", "nodejs", "express", "mongodb", "html", "css", "c", "cpp", "sqlite", "ocr", "tensorflow"]),
    experience_years=1.0,  # ~1 year of project experience (2nd year student)
    education="bachelor's",
    location="Pune",
    source="resume",
    job_id=job.id,
)
db.add(candidate)
db.commit()

# ── Show the scoring breakdown step-by-step ──────────────────────────────────
print("=" * 65)
print("  SCREENING SERVICE -- LIVE SCORING DEMO")
print("=" * 65)

print(f"\n[JOB] {job.title}")
print(f"   Required Skills: {json.loads(job.skills)}")
print(f"   Experience Min:  {job.experience_min} years")
print(f"   Qualification:   {job.qualification}")
print(f"   Location:        {job.location}")

print(f"\n[CANDIDATE] {candidate.name}")
print(f"   Skills:          {json.loads(candidate.skills)}")
print(f"   Experience:      {candidate.experience_years} years")
print(f"   Education:       {candidate.education}")
print(f"   Location:        {candidate.location}")

print("\n" + "-" * 65)
print("  SCORING BREAKDOWN")
print("-" * 65)

total, breakdown = calculate_score(candidate, job)

# Detailed explanation
c_skills = set(s.lower() for s in json.loads(candidate.skills))
j_skills = set(s.lower() for s in json.loads(job.skills))
matched = c_skills & j_skills
unmatched = j_skills - c_skills

print(f"\n[1] SKILL MATCH (0-40 pts):        {breakdown['skill_match']} / 40")
print(f"     Job requires:    {j_skills}")
print(f"     You have:        {c_skills}")
print(f"     [+] Matched:     {matched} ({len(matched)}/{len(j_skills)})")
if unmatched:
    print(f"     [-] Missing:     {unmatched}")
print(f"     Formula:         {len(matched)}/{len(j_skills)} x 40 = {breakdown['skill_match']}")

print(f"\n[2] EXPERIENCE (0-30 pts):         {breakdown['experience']} / 30")
print(f"     Required min:    {job.experience_min} years")
print(f"     Your experience: {candidate.experience_years} years")
if candidate.experience_years >= (job.experience_min or 0):
    print(f"     [+] Meets requirement -> full 30 pts")
else:
    print(f"     [!] Below min -> partial credit")

print(f"\n[3] EDUCATION (0-20 pts):          {breakdown['education']} / 20")
print(f"     Required:        {job.qualification}")
print(f"     Yours:           {candidate.education}")
print(f"     [+] Meets requirement -> full 20 pts")

print(f"\n[4] LOCATION BONUS (0-10 pts):     {breakdown['location']} / 10")
print(f"     Job location:    {job.location}")
print(f"     Your location:   {candidate.location}")
print(f"     [+] Match -> 10 pts bonus")

print("\n" + "=" * 65)
print(f"  TOTAL SCORE: {total} / 100")
print(f"  THRESHOLD:   70 (shortlisted if >= 70)")
if total >= 70:
    print(f"  [+] STATUS:  SHORTLISTED")
else:
    print(f"  [-] STATUS:  REJECTED (score below 70)")
print("=" * 65)

# Now run full processor to show the end-to-end result
print("\n\n--- Running full process_candidate() ---")
result = process_candidate(candidate.id, db)
print(f"Result: {json.dumps(result, indent=2)}")

db.refresh(candidate)
print(f"\nDB state after processing:")
print(f"  status:           {candidate.status}")
print(f"  score:            {candidate.score}")
print(f"  score_breakdown:  {candidate.score_breakdown}")
print(f"  is_duplicate:     {candidate.is_duplicate}")
print(f"  rejection_reason: {candidate.rejection_reason}")

# Close database session
try:
    next(db_gen)
except StopIteration:
    pass
