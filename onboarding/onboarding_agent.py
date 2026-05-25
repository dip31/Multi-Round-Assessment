"""
Onboarding Agent — Stage 9
Autonomous agent that listens to offer acceptance events and automatically:
1. Creates onboarding records
2. Generates task checklists (Day 1, Week 1, Month 1)
3. Sends document collection emails
4. Triggers BGV checks
5. Provisions IT resources
6. Publishes completion events for Stage 10 (Analytics)
"""
import asyncio
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from onboarding.onboarding_task_manager import (
    create_task_checklist, send_task_checklist_email
)
from onboarding.document_collector import (
    create_onboarding_record, send_document_checklist_email,
    get_upload_path, REQUIRED_DOCUMENTS, DOCUMENT_LABELS
)
from onboarding.bgv_trigger import trigger_bgv
from onboarding.it_provisioner import provision_it_resources


async def process_onboarding_started_event(event_data: dict):
    """
    Triggered when: onboarding.started event is published (after offer acceptance)
    Action: Create onboarding record, send checklists, trigger BGV
    """
    try:
        offer_id = event_data.get("offer_id")
        candidate_id = event_data.get("candidate_id")
        job_id = event_data.get("job_id")
        joining_date = event_data.get("joining_date")
        
        print(f"[Onboarding Agent] Starting onboarding for candidate {candidate_id}")
        
        # Step 1: Create onboarding record
        onboarding_id = create_onboarding_record(candidate_id, offer_id)
        print(f"[Onboarding Agent] Created onboarding record {onboarding_id}")
        
        # Step 2: Create task checklist
        task_count = create_task_checklist(onboarding_id, candidate_id, joining_date)
        print(f"[Onboarding Agent] Created {task_count} tasks for candidate {candidate_id}")
        
        # Step 3: Send task checklist email
        # Get candidate details from database
        from config import DATABASE_URL
        import sqlite3
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name, email FROM candidates WHERE id=?", (candidate_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            candidate_name, candidate_email = row
            send_task_checklist_email(candidate_email, candidate_name, joining_date)
            print(f"[Onboarding Agent] Sent task checklist to {candidate_email}")
            
            # Step 4: Send document collection email
            upload_paths = {doc: get_upload_path(candidate_id, doc) for doc in REQUIRED_DOCUMENTS}
            send_document_checklist_email(candidate_email, candidate_name, upload_paths)
            print(f"[Onboarding Agent] Sent document checklist to {candidate_email}")
        
        # Step 5: Trigger BGV check
        bgv_result = trigger_bgv(onboarding_id)
        print(f"[Onboarding Agent] BGV triggered: {bgv_result.get('status')}")
        
        # Publish BGV event
        if bgv_result.get("status") == "cleared":
            await event_bus.publish(
                EventTopics.BGV_CLEARED,
                {
                    "onboarding_id": onboarding_id,
                    "candidate_id": candidate_id,
                    "bgv_result": bgv_result,
                },
                agent="onboarding_agent"
            )
        
        # Step 6: Provision IT resources (after BGV clears)
        if bgv_result.get("status") == "cleared":
            it_result = provision_it_resources(onboarding_id)
            print(f"[Onboarding Agent] IT resources provisioned: {it_result}")
            
            # Publish onboarding completion event
            await event_bus.publish(
                EventTopics.ONBOARDING_COMPLETED,
                {
                    "onboarding_id": onboarding_id,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "joining_date": joining_date,
                    "tasks_created": task_count,
                    "bgv_status": bgv_result.get("status"),
                    "it_provisioned": True,
                },
                agent="onboarding_agent"
            )
            
            print(f"[Onboarding Agent] ✅ Onboarding completed for candidate {candidate_id}")
        else:
            print(f"[Onboarding Agent] ⚠️ BGV not cleared. IT provisioning pending.")
        
    except Exception as e:
        print(f"[Onboarding Agent] ❌ Error processing onboarding: {e}")
        import traceback
        traceback.print_exc()


def start_onboarding_agent():
    """Subscribe to events and start the onboarding agent"""
    event_bus.subscribe(EventTopics.ONBOARDING_STARTED, process_onboarding_started_event)
    print("✅ Onboarding Agent (Stage 9) is now listening for events")
