"""
outreach/rejection_emailer.py
════════════════════════════════════════════════════════════════════
Stage 4 — Rejection Emailer
Listens to 'candidate.rejected' events from RabbitMQ (published by Kumar),
selects the correct rejection template based on rejection stage, sends a
polite rejection email via SendGrid (rate-throttled via Redis), and logs
the communication in the DB.
"""

import json
import logging
import os
from datetime import datetime, timezone

import pika
import redis
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from shared.db.database import db_session
from shared.db.models import Application, Candidate, Communication, Job
from shared.queue.event_topics import CANDIDATE_REJECTED

# ─── Env ────────────────────────────────────────────────────────────────────
load_dotenv()

SENDGRID_API_KEY     = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL  = os.getenv("SENDGRID_FROM_EMAIL", "noreply@company.com")
RABBITMQ_URL         = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
REDIS_URL            = os.getenv("REDIS_URL", "redis://localhost:6379/0")
COMPANY_NAME         = os.getenv("COMPANY_NAME", "Our Company")
TALENT_POOL_BASE_URL = os.getenv("TALENT_POOL_BASE_URL", "https://company.com/talent-pool")

# Rate limit: max 50 rejection emails per hour
REJECTION_RATE_LIMIT   = 50
REJECTION_WINDOW_SECS  = 3600
REJECTION_REDIS_KEY    = "rejection_emailer:count"

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("rejection_emailer")

# ─── Jinja2 ─────────────────────────────────────────────────────────────────
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)

# ─── Redis client ────────────────────────────────────────────────────────────
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _check_rate_limit() -> bool:
    """
    Enforce max 50 rejection emails/hour using a Redis counter.
    Returns True if we're within the limit, False if throttled.
    """
    current = redis_client.get(REJECTION_REDIS_KEY)
    if current is None:
        redis_client.setex(REJECTION_REDIS_KEY, REJECTION_WINDOW_SECS, 1)
        return True
    if int(current) >= REJECTION_RATE_LIMIT:
        log.warning("Rejection email rate limit reached (%d/hr). Throttling.", REJECTION_RATE_LIMIT)
        return False
    redis_client.incr(REJECTION_REDIS_KEY)
    return True


def _already_rejected(db, candidate_id: str, job_id: str) -> bool:
    """Return True if we already sent a rejection email for this candidate+job."""
    return (
        db.query(Communication)
        .filter_by(candidate_id=candidate_id, job_id=job_id, communication_type="REJECTION")
        .first()
    ) is not None


def _select_template(rejection_stage: str) -> str:
    """
    Map the rejection stage from the event payload to the correct email template.
    rejection_stage: 'screening_rejection' | 'prescreening_rejection'
    """
    return {
        "screening_rejection":    "rejection_screening.html",
        "prescreening_rejection": "rejection_prescreening.html",
    }.get(rejection_stage, "rejection_screening.html")


def _soften_reason(reason: str) -> str:
    """
    Replace blunt rejection phrasing with diplomatic language.
    Kumar's scoring engine may return raw numeric or technical reasons.
    """
    if not reason:
        return ""
    replacements = {
        "score below threshold": "your profile didn't meet the minimum requirements for this role",
        "skills mismatch":       "your skill set didn't fully align with this specific role's needs",
        "experience too low":    "the role requires a higher level of experience than your current profile reflects",
        "location mismatch":     "candidates closer to the work location were prioritised for this role",
    }
    for raw, soft in replacements.items():
        if raw.lower() in reason.lower():
            return soft.capitalize()
    return reason


def send_rejection_email(
    candidate: Candidate,
    job: Job,
    rejection_stage: str,
    rejection_reason: str,
    db,
) -> bool:
    """Build and send a rejection email; log to communications table."""
    template_file = _select_template(rejection_stage)
    first_name    = candidate.name.split()[0] if candidate.name else "Candidate"
    soft_reason   = _soften_reason(rejection_reason)
    talent_pool_url = f"{TALENT_POOL_BASE_URL}?join=true&cid={candidate.id}"

    tmpl = jinja_env.get_template(template_file)
    html_body = tmpl.render(
        first_name=first_name,
        job_title=job.title,
        company_name=COMPANY_NAME,
        rejection_reason=soft_reason,
        talent_pool_url=talent_pool_url,
        unsubscribe_url=f"{TALENT_POOL_BASE_URL}?unsubscribe=true",
    )

    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=candidate.email,
        subject=f"Update on your application — {job.title} at {COMPANY_NAME}",
        html_content=html_body,
    )
    try:
        sg   = SendGridAPIClient(SENDGRID_API_KEY)
        resp = sg.send(message)
        sg_msg_id = resp.headers.get("X-Message-Id", "")
        log.info(
            "Rejection email sent to %s (stage=%s, status=%s)",
            candidate.email, rejection_stage, resp.status_code,
        )
    except Exception as exc:
        log.error("SendGrid error for rejection email to %s: %s", candidate.email, exc)
        return False

    # ── Log to communications table ──────────────────────────────────────────
    comm = Communication(
        candidate_id=candidate.id,
        job_id=job.id,
        communication_type="REJECTION",
        direction="OUTBOUND",
        subject=f"Update on your application — {job.title} at {COMPANY_NAME}",
        content=html_body,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(comm)
    db.commit()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# RABBITMQ CONSUMER
# ─────────────────────────────────────────────────────────────────────────────

def _process_message(ch, method, properties, body):
    """Callback for each candidate.rejected event."""
    try:
        payload          = json.loads(body)
        candidate_id     = payload.get("candidate_id")
        job_id           = payload.get("job_id")
        rejection_stage  = payload.get("rejection_stage", "screening_rejection")
        rejection_reason = payload.get("rejection_reason", "")

        log.info(
            "Received candidate.rejected event: candidate=%s, job=%s, stage=%s",
            candidate_id, job_id, rejection_stage,
        )

        if not candidate_id or not job_id:
            log.warning("Malformed event — missing candidate_id or job_id")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Rate limiting
        if not _check_rate_limit():
            # Requeue so it's retried once the window resets
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return

        with db_session() as db:
            # Idempotency: skip if already rejected
            if _already_rejected(db, candidate_id, job_id):
                log.info(
                    "Rejection already sent for candidate %s / job %s — skipping.",
                    candidate_id, job_id,
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            candidate = db.query(Candidate).filter_by(id=candidate_id).first()
            job       = db.query(Job).filter_by(id=job_id).first()

            if not candidate or not job:
                log.error("Candidate or job not found in DB")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            success = send_rejection_email(
                candidate, job, rejection_stage, rejection_reason, db
            )

        ch.basic_ack(delivery_tag=method.delivery_tag) if success \
            else ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as exc:
        log.exception("Unexpected error in rejection_emailer: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    """Connect to RabbitMQ and start consuming candidate.rejected events."""
    params     = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel    = connection.channel()

    channel.queue_declare(queue=CANDIDATE_REJECTED, durable=True)
    channel.basic_qos(prefetch_count=5)
    channel.basic_consume(queue=CANDIDATE_REJECTED, on_message_callback=_process_message)

    log.info("✅ rejection_emailer listening on queue: %s", CANDIDATE_REJECTED)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Shutting down rejection_emailer...")
        channel.stop_consuming()
    finally:
        connection.close()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_consumer()
