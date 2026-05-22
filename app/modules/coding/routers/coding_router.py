"""
Coding router stub.

Endpoints for fetching coding problems, submitting code, and retrieving
Judge0 results will be added here.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.session_problem import SessionProblem
from app.models.coding import CodingProblem
from app.schemas.coding import (
	CodingProblemResponse,
	CodingSubmissionRequest,
	CodingSubmissionResponse,
	CodingSubmissionStatusResponse,
)
from app.modules.coding.services.coding_service import (
	list_problems,
	run_and_evaluate,
	start_coding_round,
	finalize_coding_round,
    
)
from app.services import session_service
from app.config.settings import settings


router = APIRouter(prefix="/coding", tags=["Coding Round"])


@router.get("/problems", response_model=List[CodingProblemResponse])
def get_problems(db: Session = Depends(get_db)):
	"""List assigned coding problems for the current round (visible test cases only)."""
	# Return problems for the user's active coding round if one exists
	return list_problems(db)


@router.post("/run", response_model=CodingSubmissionResponse)
def run_code(payload: CodingSubmissionRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Run code against visible test cases only (not persisted). Requires an active coding round."""
	active_round = session_service.get_user_active_round(db, current_user.id, round_type="coding")
	if active_round is None:
		raise HTTPException(status_code=404, detail="no active coding round")

	# Ensure the problem is assigned to this round
	assigned = (
		db.query(SessionProblem)
		.filter(SessionProblem.round_id == active_round.id, SessionProblem.problem_id == payload.problem_id)
		.first()
	)
	if assigned is None:
		raise HTTPException(status_code=400, detail="problem not assigned to current round")

	# If the round has expired, finalize automatically and reject runs
	limit_minutes = settings.CODING_ROUND_TIME_LIMIT_MINUTES
	end_time = active_round.started_at + timedelta(minutes=limit_minutes)
	if datetime.utcnow() > end_time:
		finalize_coding_round(db, active_round.id)
		raise HTTPException(status_code=400, detail="coding round has expired")

	result = run_and_evaluate(db, payload.problem_id, payload.code, payload.language, visible_only=True)
	return {
		"submission_id": result.get("submission_id", 0),
		"judge0_token": result.get("judge0_token"),
		"status": result.get("status", "ok"),
		"score": result.get("score"),
		"execution_time": result.get("execution_time"),
		"memory_used": result.get("memory_used"),
		"submitted_at": None,
	}


@router.post("/submit", response_model=CodingSubmissionResponse)
def submit_code(payload: CodingSubmissionRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Submit code: evaluate visible + hidden tests and persist a submission."""
	active_round = session_service.get_user_active_round(db, current_user.id, round_type="coding")
	if active_round is None:
		raise HTTPException(status_code=404, detail="no active coding round")

	# enforce timer and auto-finalize on expiry
	limit_minutes = settings.CODING_ROUND_TIME_LIMIT_MINUTES
	end_time = active_round.started_at + timedelta(minutes=limit_minutes)
	if datetime.utcnow() > end_time:
		# finalize and unlock interview
		finalize_coding_round(db, active_round.id)
		raise HTTPException(status_code=400, detail="coding round has expired")
	# Ensure problem is assigned to this round
	assigned = (
		db.query(SessionProblem)
		.filter(SessionProblem.round_id == active_round.id, SessionProblem.problem_id == payload.problem_id)
		.first()
	)
	if assigned is None:
		raise HTTPException(status_code=400, detail="problem not assigned to current round")

	result = run_and_evaluate(db, payload.problem_id, payload.code, payload.language, visible_only=False, round_id=active_round.id)
	return {
		"submission_id": result.get("submission_id"),
		"judge0_token": result.get("judge0_token"),
		"status": result.get("status", "ok"),
		"score": result.get("score"),
		"execution_time": result.get("execution_time"),
		"memory_used": result.get("memory_used"),
		"submitted_at": None,
	}


@router.post("/start")
def start_round(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Start a coding round for the authenticated user's active session."""
	try:
		payload = start_coding_round(db, current_user.id)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# Return assigned problems (visible test cases filtered by service)
	problems = payload.get("problems")
	if problems is not None:
		return problems

	assigned_problem_ids = [sp.problem_id for sp in payload.get("assigned", [])]
	problems = db.query(CodingProblem).filter(CodingProblem.id.in_(assigned_problem_ids)).all()
	for p in problems:
		p.test_cases = [t for t in p.test_cases if not t.is_hidden]
	return problems


@router.post("/start-after-aptitude")
def start_after_aptitude(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Finalize the user's aptitude round and ensure coding round is available next.

	This keeps the session active, unlocks the coding round, and is safe to call more than once.
	"""
	active_aptitude = session_service.get_user_active_round(db, current_user.id, round_type="aptitude")
	if active_aptitude is not None:
		session_service.end_round(db, active_aptitude.id)

	try:
		payload = start_coding_round(db, current_user.id)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	problems = payload.get("problems")
	if problems is not None:
		return problems

	assigned_problem_ids = [sp.problem_id for sp in payload.get("assigned", [])]
	problems = db.query(CodingProblem).filter(CodingProblem.id.in_(assigned_problem_ids)).all()
	for p in problems:
		p.test_cases = [t for t in p.test_cases if not t.is_hidden]
	return problems


@router.post("/finish")
def finish_round(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Explicitly finalize the user's active coding round (called when candidate clicks Finish)."""
	active_round = session_service.get_user_active_round(db, current_user.id, round_type="coding")
	if active_round is None:
		# If there is no active coding round, nothing to do — idempotent
		return {"status": "no_active_round"}

	# Finalize and unlock interview round
	score = finalize_coding_round(db, active_round.id)
	return {"status": "finalized", "round_score": score}


@router.get("/submission/{submission_id}", response_model=CodingSubmissionStatusResponse)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
	from app.models.coding import CodingSubmission

	sub = db.query(CodingSubmission).filter(CodingSubmission.id == submission_id).first()
	if not sub:
		raise HTTPException(status_code=404, detail="submission not found")
	return {
		"submission_id": sub.id,
		"problem_id": sub.problem_id,
		"status": sub.status or "unknown",
		"score": sub.score,
		"execution_time": sub.execution_time,
		"memory_used": sub.memory_used,
		"test_cases_passed": None,
		"total_test_cases": None,
		"error_message": None,
	}
