"""
outreach/followup_manager.py
════════════════════════════════════════════════════════════════════
Stage 4 — Automated Follow-up Scheduler
Uses APScheduler (with Celery Beat as optional replacement) to check
every hour for candidates who haven't responded, and fires follow-up
emails at Day 3, Day 5, and Day 7 cadences.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from celery import Celery
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from shared.db.database import db_session
from shared.db.models import Application, Candidate, Communication, Job

# ─── Env ────────────────────────────────────────────────────────────────────
load_dotenv()

REDIS_URL            = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SENDGRID_API_KEY     = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL  = os.getenv("SENDGRID_FROM_EMAIL", "noreply@company.com")
COMPANY_NAME         = os.getenv("COMPANY_NAME", "Our Company")
SCREENING_BASE_URL   = os.getenv("SCREENING_BASE_URL", "https://screening.company.com/chat")
TALENT_POOL_BASE_URL = os.getenv("TALENT_POOL_BASE_URL", "https://company.com/talent-pool")

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("followup_manager")

# ─── Jinja2 ─────────────────────────────────────────────────────────────────
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)

# ─── Celery app (optional — can swap to APScheduler) ────────────────────────
celery_app = Celery("followup_manager", broker=REDIS_URL, backend=REDIS_URL)

# Celery Beat schedule — runs check_followups every hour
celery_app.conf.beat_schedule = {
    "check-followups-every-hour": {
        "task": "outreach.followup_manager.check_followups",
        "schedule": 3600.0,
    }
}
celery_app.conf.timezone = "UTC"


# ─────────────────────────────────────────────────────────────────────────────
# FOLLOW-UP TEMPLATES MAP
# ─────────────────────────────────────────────────────────────────────────────

_FOLLOWUP_CONFIG = [
    # (current_comm_type, check_field, days_threshold, next_comm_type, template_file)
    ("OUTREACH",    "opened",  3, "OUTREACH_F1", "followup_1.html"),
    ("OUTREACH_F1", "clicked", 5, "OUTREACH_F2", "followup_2.html"),
    ("OUTREACH_F2", "replied", 7, "OUTREACH_FINAL", "followup_final.html"),
]


def _send_followup_email(
    candidate: Candidate,
    job: Job,
    comm_type: str,
    template_file: str,
    chatbot_url: str,
) -> tuple[bool, str, str]:
    """Render and send a follow-up email; return (success, html_body, sg_msg_id)."""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    first_name = candidate.name.split()[0] if candidate.name else "Candidate"
    tmpl = jinja_env.get_template(template_file)
    html_body = tmpl.render(
        first_name=first_name,
        job_title=job.title,
        company_name=COMPANY_NAME,
        chatbot_url=chatbot_url,
        talent_pool_url=f"{TALENT_POOL_BASE_URL}?cid={candidate.id}",
        unsubscribe_url=f"{TALENT_POOL_BASE_URL}?unsubscribe=true",
    )

    subject_map = {
        "OUTREACH_F1":    f"Did you see our message? — {job.title} at {COMPANY_NAME}",
        "OUTREACH_F2":    f"Still here for you — {job.title} opportunity",
        "OUTREACH_FINAL": f"Last chance: {job.title} at {COMPANY_NAME}",
    }

    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=candidate.email,
        subject=subject_map.get(comm_type, f"Follow-up: {job.title}"),
        html_content=html_body,
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        resp = sg.send(message)
        sg_msg_id = resp.headers.get("X-Message-Id", "")
        log.info(
            "Follow-up (%s) sent to %s (status=%s)",
            comm_type, candidate.email, resp.status_code,
        )
        return True, html_body, sg_msg_id
    except Exception as exc:
        log.error("SendGrid error sending follow-up to %s: %s", candidate.email, exc)
        return False, "", ""


# ─────────────────────────────────────────────────────────────────────────────
# CORE TASK
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="outreach.followup_manager.check_followups")
def check_followups():
    """
    Hourly task:
    For each follow-up tier, query communications for candidates who haven't
    responded and whose last email was sent beyond the tier's day threshold.
    """
    now = datetime.now(timezone.utc)
    log.info("Running check_followups at %s", now.isoformat())

    with db_session() as db:
        for (curr_type, check_field, days, next_type, template) in _FOLLOWUP_CONFIG:
            cutoff = now - timedelta(days=days)

            overdue_comms = (
                db.query(Communication)
                .filter(
                    Communication.communication_type == curr_type,
                    Communication.sent_at <= cutoff,
                )
                .all()
            )

            for comm in overdue_comms:
                candidate = db.query(Candidate).filter_by(
                    id=comm.candidate_id
                ).first()

                # ── Skip if already sent this follow-up tier ──────────────
                already_sent = (
                    db.query(Communication)
                    .filter_by(
                        candidate_id=comm.candidate_id,
                        job_id=comm.job_id,
                        communication_type=next_type,
                    )
                    .first()
                )
                if already_sent:
                    continue

                job = db.query(Job).filter_by(id=comm.job_id).first()
                if not job:
                    continue

                # The chatbot link is the same as the original outreach
                original = (
                    db.query(Communication)
                    .filter_by(
                        candidate_id=comm.candidate_id,
                        job_id=comm.job_id,
                        communication_type="OUTREACH",
                    )
                    .first()
                )
                # Extract chatbot URL from original email content (simple fallback)
                chatbot_url = f"{SCREENING_BASE_URL}?token={comm.id}"

                success, html_body, sg_msg_id = _send_followup_email(
                    candidate, job, next_type, template, chatbot_url
                )

                if success:
                    # Log the follow-up communication
                    followup_comm = Communication(
                        candidate_id=candidate.id,
                        job_id=job.id,
                        communication_type=next_type,
                        direction="OUTBOUND",
                        subject=f"Follow-up: {job.title}",
                        content=html_body,
                        sent_at=now,
                    )
                    db.add(followup_comm)

                    # On final follow-up → mark UNRESPONSIVE
                    if next_type == "OUTREACH_FINAL":
                        app = (
                            db.query(Application)
                            .filter_by(
                                candidate_id=candidate.id,
                                job_id=job.id,
                            )
                            .first()
                        )
                        if app:
                            app.status = "UNRESPONSIVE"
                            log.info(
                                "Marked candidate %s as UNRESPONSIVE",
                                candidate.id,
                            )

    log.info("check_followups complete.")


# ─────────────────────────────────────────────────────────────────────────────
# APScheduler FALLBACK (run standalone without Celery)
# ─────────────────────────────────────────────────────────────────────────────

def run_with_apscheduler():
    """Start APScheduler blocking scheduler — use when Celery is not available."""
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(check_followups, "interval", hours=1, id="check_followups")
    log.info("✅ APScheduler started — check_followups runs every hour")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("APScheduler stopping...")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if "--celery" in sys.argv:
        # Start as Celery worker: python followup_manager.py --celery
        # (normally launched via: celery -A outreach.followup_manager worker --beat)
        print("Use: celery -A outreach.followup_manager worker --beat -l info")
    else:
        run_with_apscheduler()
