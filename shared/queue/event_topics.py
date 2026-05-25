"""
Event topic names as constants — imported by all agents.
These define the async message contracts between agents.
"""


class EventTopics:
    # ── Intake (Stage 1) ─────────────────────────────
    JOB_CREATED = "job.created"
    JOB_UPDATED = "job.updated"
    JD_GENERATED = "jd.generated"
    JOB_POSTED = "job.posted"
    JOB_POST_FAILED = "job.post_failed"

    # ── Sourcing (Stage 2) ───────────────────────────
    RESUME_UPLOADED = "resume.uploaded"
    PROFILE_PARSED = "profile.parsed"
    PROFILE_SCRAPED = "profile.scraped"
    CANDIDATE_CREATED = "candidate.created"

    # ── Cross-stage ──────────────────────────────────
    CANDIDATE_MATCHED = "candidate.matched"
    APPLICATION_CREATED = "application.created"

    # ── Phase 3 Events (Screening & Hiring) ──────────
    CANDIDATE_SCREENED = "candidate.screened"
    CANDIDATE_SCORED = "candidate.scored"
    CANDIDATE_SHORTLISTED = "candidate.shortlisted"
    CANDIDATE_REJECTED = "candidate.rejected"
    DUPLICATE_DETECTED = "duplicate.detected"
    INTERVIEW_SCHEDULED = "interview.scheduled"
    INTERVIEW_COMPLETED = "interview.completed"
    INTERVIEW_CANCELLED = "interview.cancelled"
    OFFER_EXTENDED = "offer.extended"
    OFFER_ACCEPTED = "offer.accepted"
    OFFER_REJECTED = "offer.rejected"
    CANDIDATE_HIRED = "candidate.hired"
    ONBOARDING_STARTED = "onboarding.started"
    ONBOARDING_COMPLETED = "onboarding.completed"
    COMMUNICATION_SENT = "communication.sent"
    COMMUNICATION_RECEIVED = "communication.received"
    
    # ── Outreach & Prescreening (Stages 4-5) ─────────
    OUTREACH_SENT = "outreach.sent"
    FOLLOWUP_SENT = "followup.sent"
    REJECTION_SENT = "rejection.sent"
    SCREENING_PASSED = "screening.passed"
    SCREENING_FAILED = "screening.failed"
    BGV_INITIATED = "bgv.initiated"
    BGV_CLEARED = "bgv.cleared"
    BGV_FLAGGED = "bgv.flagged"

    # ── System ───────────────────────────────────────
    AGENT_ERROR = "agent.error"
    AUDIT_EVENT = "audit.event"
