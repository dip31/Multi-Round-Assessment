"""
Offer Management API Router — Stage 8
Handles offer generation, dispatch, negotiation, and rejection.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import datetime, timedelta

router = APIRouter(tags=["Stage 8: Offer Management"])


class OfferGenerateRequest(BaseModel):
    candidate_id: int
    job_id: int
    offered_salary: float
    joining_date: str
    interview_id: Optional[int] = None


class NegotiationRequest(BaseModel):
    offer_id: int
    candidate_ask: float


@router.post("/offer/generate")
async def generate_offer(req: OfferGenerateRequest):
    """Generate offer letter PDF and save to database."""
    from offer.offer_letter_generator import (
        get_candidate_and_job, generate_letter_text,
        generate_offer_pdf, save_offer_to_db
    )
    
    try:
        data = get_candidate_and_job(req.candidate_id, req.job_id)
        data.update({
            "candidate_id": req.candidate_id,
            "job_id": req.job_id,
            "offered_salary": req.offered_salary,
            "joining_date": req.joining_date
        })
        
        letter_text = generate_letter_text(data)
        pdf_path = generate_offer_pdf(data, letter_text)
        offer_id = save_offer_to_db(
            req.candidate_id, req.job_id,
            req.offered_salary, pdf_path, req.joining_date,
            getattr(req, "interview_id", None)
        )
        
        return {
            "success": True,
            "offer_id": offer_id,
            "pdf_path": pdf_path,
            "message": "Offer letter generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/offer/candidate-interview-summary/{candidate_id}")
async def candidate_interview_summary(candidate_id: int):
    """Return latest completed interview summary for a candidate (used by Offer UI)."""
    from config import DATABASE_URL
    import sqlite3
    import json

    try:
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Find latest completed interview for candidate
        cur.execute("""
            SELECT id, job_id, completed_at FROM interview_sessions
            WHERE candidate_id=? AND phase='COMPLETE'
            ORDER BY completed_at DESC LIMIT 1
        """, (candidate_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"success": True, "interview": None}

        interview_id, job_id, completed_at = row

        # Aggregate scores from main turns
        cur.execute("""
            SELECT content_score, final_score, behavioral_snapshot
            FROM interview_turns
            WHERE interview_id=? AND is_followup=0
        """, (interview_id,))
        turns = cur.fetchall()

        content_scores = []
        final_scores = []
        behavior_scores = []
        for t in turns:
            c, f, snap = t
            if c is not None:
                content_scores.append(c)
            if f is not None:
                final_scores.append(f)
            if snap:
                try:
                    s = json.loads(snap)
                except Exception:
                    s = {}
                ec = s.get("eye_contact_pct", 0.5)
                hs = s.get("head_stability", 0.5)
                behavior_scores.append(0.5 * ec + 0.5 * hs)

        avg_content = sum(content_scores) / len(content_scores) if content_scores else 0
        avg_final = sum(final_scores) / len(final_scores) if final_scores else 0
        avg_behavior = sum(behavior_scores) / len(behavior_scores) if behavior_scores else 0

        result = {
            "interview_id": interview_id,
            "job_id": job_id,
            "completed_at": completed_at,
            "content_score": round(avg_content, 3),
            "final_score": round(avg_final, 3),
            "behavior_score": round(avg_behavior, 3),
        }
        conn.close()
        return {"success": True, "interview": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offer/dispatch/{offer_id}")
async def dispatch_offer(offer_id: int):
    """Send offer letter via email."""
    from offer.offer_dispatcher import dispatch_offer as send_offer
    
    try:
        send_offer(offer_id)
        return {
            "success": True,
            "message": f"Offer {offer_id} dispatched successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offer/negotiate")
async def negotiate_offer(req: NegotiationRequest):
    """Handle salary negotiation."""
    from offer.negotiation_bot import handle_negotiation
    
    try:
        result = handle_negotiation(req.offer_id, req.candidate_ask)
        return {
            "success": True,
            "approved": result["approved"],
            "final_salary": result["final_salary"],
            "message": result["message"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/offer/list")
async def list_offers():
    """List all offers with their status."""
    from config import DATABASE_URL
    import sqlite3
    
    try:
        # Extract DB path from DATABASE_URL
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT o.id, o.application_id, o.salary_offered,
                   o.start_date, o.status, o.offered_at, o.currency
            FROM offers o
            ORDER BY o.offered_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        
        offers = []
        for row in rows:
            offers.append({
                "id": row[0],
                "application_id": row[1],
                "offered_salary": row[2],
                "start_date": row[3],
                "status": row[4],
                "offered_at": row[5],
                "currency": row[6] or "USD"
            })
        
        return {"success": True, "offers": offers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offer/reject/{offer_id}")
async def reject_offer(offer_id: int):
    """Send rejection email."""
    from offer.rejection_closer import send_rejection_email
    
    try:
        send_rejection_email(offer_id)
        return {
            "success": True,
            "message": f"Rejection email sent for offer {offer_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offer/accept/{offer_id}")
async def accept_offer(offer_id: str):
    """Accept an offer and trigger onboarding."""
    from config import DATABASE_URL
    from shared.queue.event_bus import event_bus
    from shared.queue.event_topics import EventTopics
    from datetime import datetime, timedelta
    import sqlite3
    
    try:
        # Get offer details
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT application_id, start_date
            FROM offers WHERE id=?
        """, (offer_id,))
        row = cur.fetchone()
        
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Offer not found")
        
        application_id, start_date = row
        
        # Extract candidate_id from application_id (format: app_<candidate_id>)
        candidate_id = application_id.replace("app_", "")
        
        # Update offer status
        cur.execute("""
            UPDATE offers 
            SET status='accepted', accepted_at=? 
            WHERE id=?
        """, (datetime.now().isoformat(), offer_id))
        conn.commit()
        conn.close()
        
        # Publish offer.accepted event to trigger onboarding
        await event_bus.publish(
            EventTopics.OFFER_ACCEPTED,
            {
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "job_id": "job_001",  # Default for now
                "joining_date": start_date or (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            },
            agent="offer_api"
        )
        
        return {
            "success": True,
            "message": f"Offer {offer_id} accepted. Onboarding initiated.",
            "candidate_id": candidate_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
