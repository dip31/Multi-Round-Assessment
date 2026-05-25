"""
outreach/email_sender.py
════════════════════════════════════════════════════════════════════
Stage 4 — Automated Outreach
Listens to 'candidate.shortlisted' events from RabbitMQ (published by Stage 3),
fetches candidate + job data from PostgreSQL, builds a personalised HTML email
using Jinja2, sends it via SendGrid, and records the communication in the DB.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from shared.db.database import get_db, db_session
from shared.db.models import Application, Candidate, Job, Communication
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from outreach.emailjs_sender import send_outreach_email as send_via_emailjs
from config import (
    COMPANY_NAME,
    SCREENING_BASE_URL,
    TALENT_POOL_BASE_URL
)

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("email_sender")

# ─── Jinja2 ─────────────────────────────────────────────────────────────────
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_chatbot_url(candidate_id: str, job_id: str) -> tuple[str, str]:
    """Generate a unique screening link embedding a UUID token. Returns (url, token)."""
    token = str(uuid.uuid4())
    return f"{SCREENING_BASE_URL}?token={token}", token


def _render_email(first_name: str, job_title: str, chatbot_url: str) -> str:
    """Render the outreach Jinja2 HTML template."""
    tmpl = jinja_env.get_template("outreach_email.html")
    unsubscribe_url = f"{TALENT_POOL_BASE_URL}?unsubscribe=true"
    return tmpl.render(
        first_name=first_name,
        job_title=job_title,
        company_name=COMPANY_NAME,
        chatbot_url=chatbot_url,
        unsubscribe_url=unsubscribe_url,
    )


def send_outreach_email(candidate: Candidate, job: Job, db) -> bool:
    """
    Core function: build + send outreach email via EmailJS,
    record in communications table, update application stage to 4.
    Returns True on success.
    """
    first_name = candidate.name.split()[0] if candidate.name else "Candidate"
    chatbot_url, token = _build_chatbot_url(str(candidate.id), str(job.id))

    # ── Send via EmailJS ────────────────────────────────────────────────────
    success = send_via_emailjs(
        candidate_email=candidate.email,
        candidate_name=candidate.name,
        job_title=job.title,
        chatbot_url=chatbot_url
    )
    
    if not success:
        log.error("EmailJS error for candidate %s", candidate.id)
        return False

    log.info("Email sent to %s (candidate_id=%s)", candidate.email, candidate.id)

    # ── Log to communications table ──────────────────────────────────────────
    comm = Communication(
        candidate_id=candidate.id,
        job_id=job.id,
        communication_type="OUTREACH",
        direction="OUTBOUND",
        subject=f"Exciting Opportunity: {job.title} at {COMPANY_NAME}",
        content=f"Outreach email sent with chatbot URL: {chatbot_url}",
        sent_at=datetime.now(timezone.utc),
    )
    db.add(comm)

    # ── Update application stage to 4 ───────────────────────────────────────
    app = (
        db.query(Application)
        .filter_by(candidate_id=candidate.id, job_id=job.id)
        .first()
    )
    if app:
        app.status = "OUTREACH_SENT"

    db.commit()
    log.info("Communications record saved for candidate %s", candidate.id)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# RABBITMQ CONSUMER
# ─────────────────────────────────────────────────────────────────────────────

def _process_message(ch, method, properties, body):
    """Callback fired for each candidate.shortlisted event."""
    try:
        payload = json.loads(body)
        log.info("Received candidate.shortlisted event: %s", payload)

        candidate_id = payload.get("candidate_id")
        job_id       = payload.get("job_id")
        application_id = payload.get("application_id")

        # Prefer application_id if provided
        with db_session() as db:
            if application_id:
                app = db.query(Application).filter_by(id=application_id).first()
                if app:
                    candidate_id = app.candidate_id
                    job_id = app.job_id

            if not candidate_id or not job_id:
                log.warning("Malformed event payload — missing candidate_id or job_id")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            candidate = db.query(Candidate).filter_by(id=candidate_id).first()
            job       = db.query(Job).filter_by(id=job_id).first()

            if not candidate:
                log.error("Candidate %s not found in DB", candidate_id)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            if not job:
                log.error("Job %s not found in DB", job_id)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            success = send_outreach_email(candidate, job, db)

        if success:
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as exc:
        log.exception("Unexpected error processing message: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    """Connect to RabbitMQ and start consuming candidate.shortlisted events."""
    params     = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel    = connection.channel()

    channel.queue_declare(queue=CANDIDATE_SHORTLISTED, durable=True)
    channel.basic_qos(prefetch_count=5)
    channel.basic_consume(queue=CANDIDATE_SHORTLISTED, on_message_callback=_process_message)

    log.info("✅ email_sender listening on queue: %s", CANDIDATE_SHORTLISTED)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Shutting down email_sender consumer...")
        channel.stop_consuming()
    finally:
        connection.close()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_consumer()

# ─────────────────────────────────────────────────────────────────────────────
# EVENT BUS INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

async def process_candidate_shortlisted_event(payload: dict):
    """
    Process a candidate.shortlisted event from the event bus.
    This is called when Stage 3 shortlists a candidate.
    """
    try:
        candidate_id = payload.get("candidate_id")
        job_id = payload.get("job_id")
        application_id = payload.get("application_id")

        if application_id:
            with db_session() as db:
                app = db.query(Application).filter_by(id=application_id).first()
                if app:
                    candidate_id = app.candidate_id
                    job_id = app.job_id

        if not candidate_id or not job_id:
            log.warning("Malformed event — missing candidate_id or job_id: %s", payload)
            return

        log.info("Processing candidate.shortlisted event: candidate=%s, job=%s", candidate_id, job_id)

        with db_session() as db:
            candidate = db.query(Candidate).filter_by(id=candidate_id).first()
            job = db.query(Job).filter_by(id=job_id).first()

            if not candidate or not job:
                log.error("Candidate or job not found in database")
                return

            # Send outreach email
            success = send_outreach_email(candidate, job, db)
            if success:
                log.info("Outreach email sent successfully to %s", candidate.email)
            else:
                log.error("Failed to send outreach email to %s", candidate.email)

    except Exception as exc:
        log.exception("Unexpected error processing candidate.shortlisted event: %s", exc)