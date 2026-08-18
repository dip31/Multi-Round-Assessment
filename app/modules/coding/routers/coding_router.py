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
	CodingRunResponse,
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


@router.post("/run", response_model=CodingRunResponse)
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
	if datetime.now() > end_time:
		finalize_coding_round(db, active_round.id)
		raise HTTPException(status_code=400, detail="coding round has expired")

	result = run_and_evaluate(db, payload.problem_id, payload.code, payload.language, visible_only=True, round_id=active_round.id)
	
	# Map to CodingRunResponse
	return {
		"status": result.get("status", "unknown"),
		"test_cases_passed": result.get("test_cases_passed", 0),
		"total_test_cases": result.get("total_test_cases", 0),
		"execution_time": result.get("execution_time"),
		"test_case_results": result.get("test_case_results", []),
		"compile_output": result.get("compile_output"),
		"stderr": result.get("stderr"),
		"message": result.get("message"),
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
	if datetime.now() > end_time:
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
	
	# Fetch the created submission from DB to get submitted_at timestamp
	from app.models.coding import CodingSubmission
	submission = db.query(CodingSubmission).filter(CodingSubmission.id == result["submission_id"]).first()
	if not submission:
		raise HTTPException(status_code=500, detail="submission created but not found")
	
	# Map to CodingSubmissionResponse
	return {
		"submission_id": submission.id,
		"status": result.get("status", "unknown"),
		"score": result.get("score", 0.0),
		"test_cases_passed": result.get("test_cases_passed", 0),
		"total_test_cases": result.get("total_test_cases", 0),
		"submitted_at": submission.submitted_at,
		"execution_time": result.get("execution_time"),
		"compile_output": result.get("compile_output"),
		"stderr": result.get("stderr"),
		"message": result.get("message"),
	}


@router.post("/start")
def start_round(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Start a coding round for the authenticated user's active session.

	Returns the full payload: {round, assigned, problems} so the frontend
	can extract session_id and problems in one call.
	"""
	try:
		payload = start_coding_round(db, current_user.id)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# Ensure hidden test cases are never exposed to the frontend
	problems = payload.get("problems") or []
	for p in problems:
		p.test_cases = [t for t in p.test_cases if not t.is_hidden]

	return payload


@router.post("/start-after-aptitude")
def start_after_aptitude(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Finalize the user's aptitude round and ensure coding round is available next.

	This keeps the session active, unlocks the coding round, and is safe to call more than once.
	Returns the full payload: {round, assigned, problems}.
	"""
	active_aptitude = session_service.get_user_active_round(db, current_user.id, round_type="aptitude")
	if active_aptitude is not None:
		session_service.end_round(db, active_aptitude.id)

	try:
		payload = start_coding_round(db, current_user.id)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# Ensure hidden test cases are never exposed to the frontend
	problems = payload.get("problems") or []
	for p in problems:
		p.test_cases = [t for t in p.test_cases if not t.is_hidden]

	return payload


@router.get("/results")
def get_results(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Get all submissions for the user's completed coding round."""
	from app.models.coding import CodingSubmission, CodingProblem
	from app.models.assessment import AssessmentRound, AssessmentSession
	
	# Try to get active coding round
	active_round = session_service.get_user_active_round(db, current_user.id, round_type="coding")
	
	if active_round is None:
		# Find the user's latest session (active or completed)
		session = db.query(AssessmentSession).filter(
			AssessmentSession.user_id == current_user.id
		).order_by(AssessmentSession.id.desc()).first()
		
		if session:
			# Find completed coding round for that session
			completed_round = db.query(AssessmentRound).filter(
				AssessmentRound.session_id == session.id,
				AssessmentRound.round_type == "coding",
				AssessmentRound.status == "completed"
			).order_by(AssessmentRound.id.desc()).first()
			
			if completed_round:
				active_round = completed_round
			else:
				return []
		else:
			return []
	
	# Get submissions for this round
	submissions = db.query(CodingSubmission).filter(
		CodingSubmission.round_id == active_round.id
	).all()
	
	results = []
	for sub in submissions:
		problem = db.query(CodingProblem).filter(CodingProblem.id == sub.problem_id).first()
		results.append({
			"submission_id": sub.id,
			"problem_id": sub.problem_id,
			"title": problem.title if problem else f"Problem {sub.problem_id}",
			"language": sub.language,
			"status": sub.status,
			"score": sub.score,
			"test_cases_passed": None,
			"total_test_cases": None,
			"execution_time": sub.execution_time,
			"submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
		})
	
	return results


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
		"compile_output": None,
		"stderr": None,
		"message": None,
	}
