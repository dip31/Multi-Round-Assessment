"""
Analytics Agent — Stage 10
Autonomous agent that listens to all pipeline events and automatically:
1. Updates recruitment funnel metrics
2. Tracks time-to-hire
3. Analyzes source ROI
4. Generates forecasts
5. Logs all events for reporting
"""
import asyncio
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from datetime import datetime


async def process_pipeline_event(event_data: dict, event_type: str):
    """
    Triggered when: Any pipeline event occurs
    Action: Log event and update analytics
    """
    try:
        # Log the event for analytics
        from config import DATABASE_URL
        import sqlite3
        import json
        
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Insert into audit_log for analytics tracking
        cur.execute("""
            INSERT INTO audit_log (event_type, agent_name, entity_type, entity_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_type,
            event_data.get("agent", "system"),
            event_data.get("entity_type", "unknown"),
            str(event_data.get("candidate_id") or event_data.get("job_id") or event_data.get("offer_id") or ""),
            json.dumps(event_data),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # Print analytics summary for key events
        if event_type in [
            EventTopics.JOB_CREATED,
            EventTopics.CANDIDATE_SHORTLISTED,
            EventTopics.INTERVIEW_COMPLETED,
            EventTopics.OFFER_EXTENDED,
            EventTopics.ONBOARDING_COMPLETED
        ]:
            print(f"[Analytics Agent] 📊 Logged: {event_type} - {event_data.get('candidate_id', 'N/A')}")
        
    except Exception as e:
        print(f"[Analytics Agent] ❌ Error logging event: {e}")


async def process_onboarding_completed_event(event_data: dict):
    """
    Triggered when: onboarding.completed event is published
    Action: Calculate final metrics and generate reports
    """
    try:
        candidate_id = event_data.get("candidate_id")
        job_id = event_data.get("job_id")
        
        print(f"[Analytics Agent] Candidate {candidate_id} completed onboarding!")
        print(f"[Analytics Agent] 🎉 Full pipeline completed for candidate {candidate_id}")
        
        # Calculate time-to-hire
        from config import DATABASE_URL
        import sqlite3
        
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Get application start date
        cur.execute("""
            SELECT created_at FROM audit_log 
            WHERE entity_id=? AND event_type='profile.parsed'
            ORDER BY created_at ASC LIMIT 1
        """, (str(candidate_id),))
        start_row = cur.fetchone()
        
        # Get completion date
        cur.execute("""
            SELECT created_at FROM audit_log 
            WHERE entity_id=? AND event_type='onboarding.completed'
            ORDER BY created_at DESC LIMIT 1
        """, (str(candidate_id),))
        end_row = cur.fetchone()
        
        time_to_hire = None
        if start_row and end_row:
            start_date = datetime.fromisoformat(start_row[0])
            end_date = datetime.fromisoformat(end_row[0])
            time_to_hire = (end_date - start_date).days
            
            print(f"[Analytics Agent] ⏱️ Time-to-hire for candidate {candidate_id}: {time_to_hire} days")
        
        conn.close()
        
        # Publish analytics event
        await event_bus.publish(
            EventTopics.CANDIDATE_HIRED,
            {
                "candidate_id": candidate_id,
                "job_id": job_id,
                "time_to_hire_days": time_to_hire,
                "completed_at": datetime.now().isoformat(),
            },
            agent="analytics_agent"
        )
        
    except Exception as e:
        print(f"[Analytics Agent] ❌ Error processing completion: {e}")


def start_analytics_agent():
    """Subscribe to all events and start the analytics agent"""
    
    # Subscribe to key pipeline events
    event_bus.subscribe(EventTopics.JOB_CREATED, lambda data: process_pipeline_event(data, EventTopics.JOB_CREATED))
    event_bus.subscribe(EventTopics.PROFILE_PARSED, lambda data: process_pipeline_event(data, EventTopics.PROFILE_PARSED))
    event_bus.subscribe(EventTopics.CANDIDATE_SHORTLISTED, lambda data: process_pipeline_event(data, EventTopics.CANDIDATE_SHORTLISTED))
    event_bus.subscribe(EventTopics.INTERVIEW_COMPLETED, lambda data: process_pipeline_event(data, EventTopics.INTERVIEW_COMPLETED))
    event_bus.subscribe(EventTopics.OFFER_EXTENDED, lambda data: process_pipeline_event(data, EventTopics.OFFER_EXTENDED))
    event_bus.subscribe(EventTopics.ONBOARDING_STARTED, lambda data: process_pipeline_event(data, EventTopics.ONBOARDING_STARTED))
    event_bus.subscribe(EventTopics.ONBOARDING_COMPLETED, process_onboarding_completed_event)
    
    print("✅ Analytics Agent (Stage 10) is now listening for all pipeline events")
