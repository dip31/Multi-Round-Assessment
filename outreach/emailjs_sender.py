"""
outreach/emailjs_sender.py
════════════════════════════════════════════════════════════════════
EmailJS Integration for Outreach Emails
Uses EmailJS free service to send outreach emails to candidates.
"""

import json
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional

from config import (
    EMAILJS_SERVICE_ID,
    EMAILJS_TEMPLATE_ID,
    EMAILJS_PUBLIC_KEY,
    EMAILJS_PRIVATE_KEY,
    COMPANY_NAME,
    SCREENING_BASE_URL,
    TALENT_POOL_BASE_URL
)

log = logging.getLogger("emailjs_sender")


def send_email_via_emailjs(
    to_email: str,
    to_name: str,
    subject: str,
    message: str,
    chatbot_url: Optional[str] = None
) -> bool:
    """
    Send email using EmailJS service.
    
    Args:
        to_email: Recipient email address
        to_name: Recipient name
        subject: Email subject
        message: Email message body
        chatbot_url: Optional chatbot URL for prescreening
    
    Returns:
        True if email sent successfully, False otherwise
    """
    
    if not EMAILJS_SERVICE_ID or not EMAILJS_PUBLIC_KEY:
        log.warning("EmailJS not configured - skipping email send")
        return False
    
    url = "https://api.emailjs.com/api/v1.0/email/send"
    
    template_params = {
        "to_email": to_email,
        "to_name": to_name,
        "subject": subject,
        "message": message,
        "company_name": COMPANY_NAME,
        "chatbot_url": chatbot_url or SCREENING_BASE_URL,
        "unsubscribe_url": f"{TALENT_POOL_BASE_URL}?unsubscribe=true"
    }
    
    payload = {
        "service_id": EMAILJS_SERVICE_ID,
        "template_id": EMAILJS_TEMPLATE_ID,
        "user_id": EMAILJS_PUBLIC_KEY,
        "accessToken": EMAILJS_PRIVATE_KEY,
        "template_params": template_params
    }
    
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        
        if response.status_code == 200:
            log.info(f"✅ Email sent successfully to {to_email}")
            return True
        else:
            log.error(f"❌ EmailJS error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log.error(f"❌ Failed to send email via EmailJS: {e}")
        return False


def send_outreach_email(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    chatbot_url: str
) -> bool:
    """
    Send outreach email to candidate about job opportunity.
    """
    first_name = candidate_name.split()[0] if candidate_name else "Candidate"
    
    subject = f"Exciting Opportunity: {job_title} at {COMPANY_NAME}"
    
    message = f"""
Hi {first_name},

We came across your profile and believe you would be a great fit for our {job_title} position at {COMPANY_NAME}.

We'd love to learn more about you! Please take a few minutes to complete our quick prescreening questionnaire:

{chatbot_url}

This will help us understand your background better and move forward with your application.

Looking forward to hearing from you!

Best regards,
{COMPANY_NAME} Recruitment Team
    """.strip()
    
    return send_email_via_emailjs(
        to_email=candidate_email,
        to_name=candidate_name,
        subject=subject,
        message=message,
        chatbot_url=chatbot_url
    )


def send_prescreening_invitation(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    chatbot_url: str
) -> bool:
    """
    Send prescreening invitation email to candidate.
    """
    first_name = candidate_name.split()[0] if candidate_name else "Candidate"
    
    subject = f"Complete Your Prescreening - {job_title} at {COMPANY_NAME}"
    
    message = f"""
Hi {first_name},

Thank you for your interest in the {job_title} position at {COMPANY_NAME}!

To proceed with your application, please complete our prescreening questionnaire:

{chatbot_url}

This should only take 5-10 minutes and will help us better understand your qualifications.

Best regards,
{COMPANY_NAME} Recruitment Team
    """.strip()
    
    return send_email_via_emailjs(
        to_email=candidate_email,
        to_name=candidate_name,
        subject=subject,
        message=message,
        chatbot_url=chatbot_url
    )


def send_rejection_email(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    rejection_reason: str = ""
) -> bool:
    """
    Send polite rejection email to candidate.
    """
    first_name = candidate_name.split()[0] if candidate_name else "Candidate"
    
    subject = f"Update on your application - {job_title} at {COMPANY_NAME}"
    
    reason_text = f"\n\n{rejection_reason}" if rejection_reason else ""
    
    message = f"""
Hi {first_name},

Thank you for your interest in the {job_title} position at {COMPANY_NAME}.

After careful consideration, we have decided to move forward with other candidates whose profiles more closely match our current requirements.{reason_text}

We appreciate the time you took to apply and encourage you to explore other opportunities with us in the future.

We wish you all the best in your job search!

Best regards,
{COMPANY_NAME} Recruitment Team
    """.strip()
    
    return send_email_via_emailjs(
        to_email=candidate_email,
        to_name=candidate_name,
        subject=subject,
        message=message
    )
