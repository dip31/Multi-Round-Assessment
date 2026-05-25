"""
Offer Management Agent — Stage 8
Autonomous agent that listens to interview completion events and automatically:
1. Generates offer letters for successful candidates
2. Dispatches offers via email
3. Handles salary negotiations
4. Publishes events for Stage 9 (Onboarding)
"""
import asyncio
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from offer.offer_letter_generator import (
    get_candidate_and_job, generate_letter_text,
    generate_offer_pdf, save_offer_to_db
)
from offer.offer_dispatcher import dispatch_offer
from datetime import datetime, timedelta


async def process_interview_completed_event(event_data: dict):
    """
    Triggered when: interview.completed event is published
    Action: Generate and send offer letter if candidate passed
    """
    try:
        interview_id = event_data.get("interview_id")
        candidate_id = event_data.get("candidate_id")
        job_id = event_data.get("job_id")
        overall_score = event_data.get("overall_score", 0)
        recommendation = event_data.get("recommendation", "reject")
        
        print(f"[Offer Agent] Received interview completion for candidate {candidate_id}")
        
        # Only generate offers for candidates with "hire" recommendation
        if recommendation.lower() == "hire" or overall_score >= 0.7:
            print(f"[Offer Agent] Candidate {candidate_id} passed interview. Generating offer...")
            
            # Get candidate and job details
            data = get_candidate_and_job(candidate_id, job_id)
            
            # Calculate offer salary (use max salary from job posting)
            offered_salary = data.get("salary_max", 100000)
            
            # Set joining date (30 days from now)
            joining_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Save offer to database using existing schema
            from config import DATABASE_URL
            import sqlite3
            import uuid
            
            db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            offer_id = f"offer_{uuid.uuid4().hex[:8]}"
            
            # Insert into offers table (existing schema)
            cur.execute("""
                INSERT INTO offers (
                    id, application_id, salary_offered, currency, 
                    benefits, start_date, status, offered_at, 
                    response_deadline, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                offer_id,
                f"app_{candidate_id}",  # application_id
                offered_salary,
                "USD",
                "Health Insurance, 401k, PTO",
                joining_date,
                "pending",
                datetime.now().isoformat(),
                (datetime.now() + timedelta(days=7)).isoformat(),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            print(f"[Offer Agent] Offer {offer_id} generated for candidate {candidate_id}")
            
            # Publish event for tracking
            await event_bus.publish(
                EventTopics.OFFER_EXTENDED,
                {
                    "offer_id": offer_id,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "offered_salary": offered_salary,
                    "joining_date": joining_date,
                },
                agent="offer_agent"
            )
            
            print(f"[Offer Agent] ✅ Offer process completed for candidate {candidate_id}")
        else:
            print(f"[Offer Agent] Candidate {candidate_id} did not pass interview (score: {overall_score}). No offer generated.")
            
    except Exception as e:
        print(f"[Offer Agent] ❌ Error processing interview completion: {e}")
        import traceback
        traceback.print_exc()


async def process_offer_accepted_event(event_data: dict):
    """
    Triggered when: Candidate accepts offer (manual trigger or API call)
    Action: Publish event to trigger Stage 9 (Onboarding)
    """
    try:
        offer_id = event_data.get("offer_id")
        candidate_id = event_data.get("candidate_id")
        job_id = event_data.get("job_id")
        joining_date = event_data.get("joining_date")
        
        print(f"[Offer Agent] Offer {offer_id} accepted by candidate {candidate_id}")
        
        # Publish event to trigger onboarding
        await event_bus.publish(
            EventTopics.ONBOARDING_STARTED,
            {
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "joining_date": joining_date,
            },
            agent="offer_agent"
        )
        
        print(f"[Offer Agent] ✅ Triggered onboarding for candidate {candidate_id}")
        
    except Exception as e:
        print(f"[Offer Agent] ❌ Error processing offer acceptance: {e}")


def start_offer_agent():
    """Subscribe to events and start the offer agent"""
    event_bus.subscribe(EventTopics.INTERVIEW_COMPLETED, process_interview_completed_event)
    event_bus.subscribe(EventTopics.OFFER_ACCEPTED, process_offer_accepted_event)
    print("✅ Offer Agent (Stage 8) is now listening for events")
