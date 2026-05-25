"""
prescreening/background_checker.py
════════════════════════════════════════════════════════════════════
Stage 5 — Background Verification (BGV)
Listens to 'screening.passed' events from RabbitMQ, initiates a
background check via SpringVerify API (with mock fallback), polls
for results, and fires bgv.cleared or FLAGGED accordingly.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import httpx
import pika
from apscheduler.schedulers.background import BackgroundScheduler
try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    Celery = None
from dotenv import load_dotenv

from shared.db.database import db_session
from shared.db.models import AuditLog, Candidate, Application
from shared.queue.event_topics import BGV_CLEARED, SCREENING_PASSED
from outreach.emailjs_sender import send_email_via_emailjs
from config import COMPANY_NAME, HR_ADMIN_EMAIL

# ─── Env ────────────────────────────────────────────────────────────────────
load_dotenv()

SPRINGVERIFY_API_KEY = os.getenv("SPRINGVERIFY_API_KEY", "")
BGV_MOCK             = os.getenv("BGV_MOCK", "True").lower() == "true"
RABBITMQ_URL         = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
REDIS_URL            = os.getenv("REDIS_URL", "redis://localhost:6379/0")

SPRINGVERIFY_BASE    = "https://api.springverify.com/v1"
BGV_POLL_INTERVAL    = 1800    # 30 minutes in seconds

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("background_checker")

# ─── Celery (for polling task) ───────────────────────────────────────────────
celery_app = Celery("background_checker", broker=REDIS_URL, backend=REDIS_URL)

# APScheduler fallback
_scheduler = BackgroundScheduler()


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def _audit(db, entity_id, action: str, metadata: dict):
    """Write a record to audit_log table."""
    log_entry = AuditLog(
        entity_type  = "candidate",
        entity_id    = entity_id,
        action       = action,
        performed_by = "background_checker",
        timestamp    = datetime.now(timezone.utc),
        meta         = metadata,      # 'metadata' is reserved by SQLAlchemy; column attr is 'meta'
    )
    db.add(log_entry)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# BGV API CALLS
# ─────────────────────────────────────────────────────────────────────────────

def _initiate_bgv_springverify(candidate: Candidate) -> str | None:
    """
    Call SpringVerify API to start a BGV.
    Returns the bgv_request_id on success, None on failure.
    """
    payload = {
        "name":              candidate.name,
        "email":             candidate.email,
        "phone":             candidate.phone or "",
        "previous_employer": (
            (candidate.parsed_profile or {}).get("previous_employer", "")
        ),
        "education":         candidate.education or {},
    }
    headers = {
        "Authorization": f"Bearer {SPRINGVERIFY_API_KEY}",
        "Content-Type":  "application/json",
    }
    try:
        resp = httpx.post(
            f"{SPRINGVERIFY_BASE}/employee",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        bgv_id = data.get("id") or data.get("employee_id")
        log.info("SpringVerify BGV initiated for %s → ID %s", candidate.email, bgv_id)
        return str(bgv_id)
    except httpx.HTTPStatusError as exc:
        log.error("SpringVerify API error: %s — %s", exc.response.status_code, exc.response.text)
        return None
    except Exception as exc:
        log.error("SpringVerify connection error: %s", exc)
        return None


def _initiate_bgv_mock(candidate: Candidate) -> str:
    """Mock BGV — returns a fake request ID immediately."""
    mock_id = f"MOCK-BGV-{candidate.id}"
    log.info("BGV_MOCK=True — using mock BGV ID: %s", mock_id)
    time.sleep(2)   # Simulate slight network delay
    return mock_id


def _poll_bgv_springverify(bgv_request_id: str) -> dict | None:
    """
    Poll SpringVerify for BGV result.
    Returns dict {status: 'CLEAR' | 'DISCREPANCY', notes: str} or None.
    """
    headers = {"Authorization": f"Bearer {SPRINGVERIFY_API_KEY}"}
    try:
        resp = httpx.get(
            f"{SPRINGVERIFY_BASE}/employee/{bgv_request_id}",
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        data   = resp.json()
        status = data.get("status", "PENDING").upper()
        return {
            "status": "CLEAR" if status == "VERIFIED" else "DISCREPANCY" if status == "FAILED" else "PENDING",
            "notes":  data.get("remarks", ""),
            "raw":    data,
        }
    except Exception as exc:
        log.error("BGV poll error for %s: %s", bgv_request_id, exc)
        return None


def _poll_bgv_mock(bgv_request_id: str) -> dict:
    """Mock poll — always returns CLEAR after 5 seconds."""
    time.sleep(5)
    log.info("Mock BGV poll for %s → CLEAR", bgv_request_id)
    return {"status": "CLEAR", "notes": "Mock verification passed", "raw": {}}


# ─────────────────────────────────────────────────────────────────────────────
# RESULT HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def _publish_event(topic: str, payload: dict):
    """Publish a RabbitMQ event."""
    try:
        params     = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel    = connection.channel()
        channel.queue_declare(queue=topic, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=topic,
            body=json.dumps(payload).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        log.info("Published event '%s': %s", topic, payload)
    except Exception as exc:
        log.error("RabbitMQ publish error for %s: %s", topic, exc)


def _alert_hr_admin(candidate: Candidate, bgv_notes: str):
    """Email HR admin when a BGV discrepancy is detected."""
    message = f"""
BGV Discrepancy Alert

Candidate: {candidate.name} ({candidate.email})
BGV Result: FLAGGED
Notes: {bgv_notes}

Please review this candidate's background verification results.
    """.strip()
    
    send_email_via_emailjs(
        to_email=HR_ADMIN_EMAIL,
        to_name="HR Admin",
        subject=f"[{COMPANY_NAME}] BGV Discrepancy — {candidate.name}",
        message=message
    )
    log.info("BGV discrepancy alert sent to HR admin for %s", candidate.email)


def _handle_bgv_result(candidate_id: str, job_id: str, bgv_result: dict):
    """
    Update candidate.bgv_status and publish event based on BGV outcome.
    """
    status = bgv_result.get("status", "PENDING")
    notes  = bgv_result.get("notes", "")

    with db_session() as db:
        candidate = db.query(Candidate).filter_by(id=candidate_id).first()
        if not candidate:
            log.error("Candidate %s not found during BGV result handling", candidate_id)
            return

        candidate.bgv_status = status
        _audit(db, candidate_id, f"bgv_result_{status.lower()}", bgv_result)

        if status == "CLEAR":
            log.info("BGV CLEAR for candidate %s — firing bgv.cleared event", candidate_id)
            _publish_event(BGV_CLEARED, {
                "candidate_id": candidate_id,
                "job_id":       job_id,
                "bgv_status":   "CLEAR",
            })
            
            # 🚀 AUTO-HIRING DECISION: BGV Clear + Prescreening Pass = Auto-Hire
            _auto_finalize_hiring_decision(candidate_id, job_id, db)
        elif status == "DISCREPANCY":
            log.warning("BGV DISCREPANCY for candidate %s — alerting HR admin", candidate_id)
            _alert_hr_admin(candidate, notes)
        else:
            log.info("BGV still PENDING for candidate %s", candidate_id)


# ─────────────────────────────────────────────────────────────────────────────
# POLLING TASK
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="prescreening.background_checker.poll_bgv_status")
def poll_bgv_status(bgv_request_id: str, candidate_id: str, job_id: str):
    """
    Celery task: poll BGV status until a conclusive result (CLEAR or DISCREPANCY).
    Scheduled to retry every 30 minutes.
    """
    log.info("Polling BGV status for request_id=%s", bgv_request_id)

    if BGV_MOCK:
        result = _poll_bgv_mock(bgv_request_id)
    else:
        result = _poll_bgv_springverify(bgv_request_id)

    if not result:
        log.warning("BGV poll returned no result — will retry.")
        return

    status = result.get("status", "PENDING")
    if status == "PENDING":
        # Re-schedule in 30 minutes
        poll_bgv_status.apply_async(
            args=[bgv_request_id, candidate_id, job_id],
            countdown=BGV_POLL_INTERVAL,
        )
        log.info("BGV still PENDING — re-scheduled in 30 minutes")
    else:
        _handle_bgv_result(candidate_id, job_id, result)


# ─────────────────────────────────────────────────────────────────────────────
# RABBITMQ CONSUMER
# ─────────────────────────────────────────────────────────────────────────────

def _process_message(ch, method, properties, body):
    """Callback for each screening.passed event."""
    try:
        payload      = json.loads(body)
        candidate_id = payload.get("candidate_id")
        job_id       = payload.get("job_id")

        log.info("Received screening.passed: candidate=%s, job=%s", candidate_id, job_id)

        if not candidate_id or not job_id:
            log.warning("Malformed event — missing candidate_id or job_id")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        with db_session() as db:
            candidate = db.query(Candidate).filter_by(candidate_id=candidate_id).first()
            if not candidate:
                log.error("Candidate %s not found", candidate_id)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # ── Initiate BGV ─────────────────────────────────────────────────
            if BGV_MOCK:
                bgv_id = _initiate_bgv_mock(candidate)
            else:
                bgv_id = _initiate_bgv_springverify(candidate)

            if not bgv_id:
                log.error("BGV initiation failed for candidate %s", candidate_id)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

            # Store BGV request ID on the candidate record
            candidate.bgv_request_id = bgv_id
            _audit(db, candidate_id, "bgv_initiated", {
                "bgv_request_id": bgv_id,
                "mock":           BGV_MOCK,
                "initiated_at":   datetime.now(timezone.utc).isoformat(),
            })

        # ── Start polling (Celery preferred, APScheduler as fallback) ─────────
        try:
            poll_bgv_status.apply_async(
                args=[bgv_id, candidate_id, job_id],
                countdown=BGV_POLL_INTERVAL if not BGV_MOCK else 5,
            )
            log.info("BGV polling scheduled via Celery for %s", candidate_id)
        except Exception:
            # Fallback: schedule via APScheduler
            from datetime import timedelta
            run_time = datetime.now(timezone.utc) + timedelta(seconds=5 if BGV_MOCK else BGV_POLL_INTERVAL)
            _scheduler.add_job(
                poll_bgv_status,
                "date",
                run_date=run_time,
                args=[bgv_id, candidate_id, job_id],
                id=f"bgv_poll_{bgv_id}",
                replace_existing=True,
            )
            if not _scheduler.running:
                _scheduler.start()
            log.info("BGV polling scheduled via APScheduler for %s", candidate_id)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        log.exception("Unexpected error in background_checker: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    """Connect to RabbitMQ and consume screening.passed events."""
    params     = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel    = connection.channel()

    channel.queue_declare(queue=SCREENING_PASSED, durable=True)
    channel.basic_qos(prefetch_count=3)
    channel.basic_consume(queue=SCREENING_PASSED, on_message_callback=_process_message)

    log.info("✅ background_checker listening on queue: %s", SCREENING_PASSED)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Shutting down background_checker...")
        channel.stop_consuming()
    finally:
        connection.close()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_consumer()



# ─────────────────────────────────────────────────────────────────────────────
# AUTO-HIRING DECISION - Final Automation Step
# ─────────────────────────────────────────────────────────────────────────────

def _auto_finalize_hiring_decision(candidate_id: str, job_id: str, db):
    """
    Automatically finalize hiring decision when:
    - BGV is CLEAR
    - Prescreening is PASSED
    
    This is the final automation step - minimal human intervention!
    """
    try:
        from shared.db.models import Score
        
        # Check if candidate passed prescreening
        score = db.query(Score).join(Application).filter(
            Application.candidate_id == candidate_id,
            Application.job_id == job_id,
            Score.tag == "PASS"
        ).first()
        
        if not score:
            log.info("Candidate %s did not pass prescreening - no auto-hire", candidate_id)
            return
        
        # Get application
        app = db.query(Application).filter_by(
            candidate_id=candidate_id,
            job_id=job_id
        ).first()
        
        if not app:
            return
        
        # 🎉 AUTO-HIRE: Update status to SELECTED
        app.status = "SELECTED"
        app.stage = 6  # Interview/Offer stage
        
        candidate = db.query(Candidate).filter_by(candidate_id=candidate_id).first()
        job = db.query(Job).filter_by(job_id=job_id).first()
        
        # Log audit trail
        audit = AuditLog(
            entity_type="application",
            entity_id=str(app.application_id),
            action="auto_selected_for_hire",
            performed_by="ai_agent_system",
            timestamp=datetime.now(timezone.utc),
            meta={
                "candidate_id": candidate_id,
                "job_id": job_id,
                "prescreening_score": score.total_score,
                "bgv_status": "CLEAR",
                "decision": "AUTO_SELECTED",
                "reason": "Passed AI prescreening + BGV cleared"
            }
        )
        db.add(audit)
        db.commit()
        
        log.info("🎉 AUTO-HIRE: Candidate %s selected for %s position!", 
                 candidate.full_name if candidate else candidate_id,
                 job.title if job else job_id)
        
        # Publish hiring event
        _publish_event("candidate.selected", {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "status": "SELECTED",
            "decision_type": "AUTOMATED",
            "prescreening_score": score.total_score,
            "bgv_status": "CLEAR"
        })
        
        # Send congratulations email (optional)
        _send_selection_notification(candidate, job, db)
        
    except Exception as e:
        log.exception("Error in auto-hiring decision: %s", e)


def _send_selection_notification(candidate: Candidate, job: Job, db):
    """Send automated selection notification to candidate."""
    try:
        first_name = candidate.name.split()[0] if candidate.name else 'Candidate'
        
        message = f"""
Congratulations! 🎉

Hi {first_name},

We're excited to inform you that you've been selected for the next round of our {job.title} position at {COMPANY_NAME}!

Our team will reach out to you shortly to schedule an interview and discuss the next steps.

Thank you for your interest in joining our team!

Best regards,
{COMPANY_NAME} Recruitment Team
        """.strip()
        
        success = send_email_via_emailjs(
            to_email=candidate.email,
            to_name=candidate.name,
            subject=f"Great News: Selected for {job.title} at {COMPANY_NAME}!",
            message=message
        )
        
        if success:
            # Log communication
            from shared.db.models import Communication
            comm = Communication(
                candidate_id=candidate.id,
                job_id=job.id,
                communication_type="SELECTION_NOTIFICATION",
                direction="OUTBOUND",
                subject=f"Great News: Selected for {job.title} at {COMPANY_NAME}!",
                content=message,
                sent_at=datetime.now(timezone.utc)
            )
            db.add(comm)
            db.commit()
            
            log.info("Selection notification sent to %s", candidate.email)
        
    except Exception as e:
        log.exception("Error sending selection notification: %s", e)
