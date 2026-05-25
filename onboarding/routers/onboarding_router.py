"""
Onboarding API Router — Stage 9
Handles task management, document collection, BGV, and IT provisioning.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3

router = APIRouter(tags=["Stage 9: Onboarding"])


class OnboardingCreateRequest(BaseModel):
    candidate_id: int
    offer_id: int
    joining_date: str


class TaskCompleteRequest(BaseModel):
    task_id: int


class DocumentSubmitRequest(BaseModel):
    onboarding_id: int
    doc_type: str
    file_path: str


@router.post("/onboarding/create")
async def create_onboarding(req: OnboardingCreateRequest):
    """Create onboarding record and task checklist."""
    from onboarding.document_collector import create_onboarding_record
    from onboarding.onboarding_task_manager import create_task_checklist
    
    try:
        onboarding_id = create_onboarding_record(req.candidate_id, req.offer_id)
        task_count = create_task_checklist(
            onboarding_id, req.candidate_id, req.joining_date
        )
        
        return {
            "success": True,
            "onboarding_id": onboarding_id,
            "tasks_created": task_count,
            "message": "Onboarding created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/onboarding/list")
async def list_onboarding():
    """List all onboarding records."""
    from config import DATABASE_URL
    
    try:
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT ob.id, ob.candidate_id, ob.offer_id, ob.status,
                   ob.created_at, c.name as candidate_name,
                   j.title as job_title
            FROM onboarding ob
            LEFT JOIN candidates c ON c.id = ob.candidate_id
            LEFT JOIN offers o ON o.id = ob.offer_id
            LEFT JOIN jobs j ON j.id = o.job_id
            ORDER BY ob.created_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            records.append({
                "id": row[0],
                "candidate_id": row[1],
                "offer_id": row[2],
                "status": row[3],
                "created_at": row[4],
                "candidate_name": row[5],
                "job_title": row[6]
            })
        
        return {"success": True, "onboarding": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/onboarding/{onboarding_id}/tasks")
async def get_tasks(onboarding_id: int):
    """Get tasks for an onboarding record."""
    from onboarding.onboarding_task_manager import get_pending_tasks
    
    try:
        tasks = get_pending_tasks(onboarding_id)
        return {"success": True, "tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/task/complete")
async def complete_task(req: TaskCompleteRequest):
    """Mark a task as complete."""
    from onboarding.onboarding_task_manager import mark_task_complete
    
    try:
        mark_task_complete(req.task_id)
        return {
            "success": True,
            "message": f"Task {req.task_id} marked as complete"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/document/submit")
async def submit_document(req: DocumentSubmitRequest):
    """Mark a document as submitted."""
    from onboarding.document_collector import mark_document_submitted
    
    try:
        mark_document_submitted(req.onboarding_id, req.doc_type, req.file_path)
        return {
            "success": True,
            "message": f"Document {req.doc_type} submitted"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/{onboarding_id}/bgv")
async def trigger_bgv(onboarding_id: int):
    """Trigger background verification."""
    from onboarding.bgv_trigger import trigger_bgv as start_bgv
    
    try:
        result = start_bgv(onboarding_id)
        return {
            "success": True,
            "message": "BGV triggered successfully",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/{onboarding_id}/provision")
async def provision_it(onboarding_id: int):
    """Provision IT resources."""
    from onboarding.it_provisioner import provision_it_resources
    
    try:
        result = provision_it_resources(onboarding_id)
        return {
            "success": True,
            "message": "IT resources provisioned",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
