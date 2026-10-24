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
	CodingTestCaseResponse,
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
	_validate_existing_blueprint_assignments,
)
from app.modules.coding.utils.code_evaluator import CodeExecutionUnavailable
from app.models.assessment import AssessmentRound, AssessmentSession
from app.services import session_service
from app.services.mock_drive_service import try_advance_mock_drive
from app.services.assessment_blueprint_service import get_session_blueprint_round_config
from app.services.faculty_access_service import require_faculty_student_access
from app.config.settings import settings

router = APIRouter(prefix="/coding", tags=["Coding Round"])


def _to_problem_response(p: CodingProblem) -> CodingProblemResponse:
	"""Serialize a CodingProblem ORM object to CodingProblemResponse.

	Reads test_cases from the in-memory list already set on the object
	(which has been pre-filtered to visible-only by the service) rather
	than letting Pydantic trigger a new lazy-load that would return all
	test cases including hidden ones.
	"""
	tc_responses = [
		CodingTestCaseResponse(
			id=tc.id,
			input_data=tc.input_data,
			expected_output=tc.expected_output,
			is_hidden=tc.is_hidden,
			explanation=tc.explanation,
		)
		for tc in (p.test_cases or [])
		if not tc.is_hidden  # never expose hidden, even if filter was skipped upstream
	]
	return CodingProblemResponse(
		id=p.id,
		title=p.title,
		description=p.description,
		difficulty=p.difficulty,
		tags=p.tags_list,
		input_format=p.input_format,
		output_format=p.output_format,
		constraints=p.constraints,
		test_cases=tc_responses,
	)


@router.get("/problems", response_model=List[CodingProblemResponse])
def get_problems(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""List coding problems assigned to the user's active round (visible test cases only)."""
	active_round = session_service.get_user_active_round(db, current_user.id, round_type="coding")
	if active_round is None:
		active_session = session_service.get_active_session(db, current_user.id)
		if active_session is not None:
			snapshot, blueprint_round = get_session_blueprint_round_config(
				db, active_session.id, "coding"
			)
			if snapshot is not None and blueprint_round is not None:
				raise HTTPException(
					status_code=409,
					detail="No active Coding round is available for this blueprint-backed assessment.",
				)
		# No active round — return global fallback for dashboard preview only
		problems = list_problems(db)
		return [_to_problem_response(p) for p in problems]

	# Return only problems assigned to this specific round
	from app.models.session_problem import SessionProblem as SP
	assigned = db.query(SP).filter(SP.round_id == active_round.id).order_by(SP.problem_order).all()
	snapshot, blueprint_round = get_session_blueprint_round_config(
		db, active_round.session_id, "coding"
	)
	blueprint_backed = snapshot is not None and blueprint_round is not None
	if blueprint_backed:
		try:
			blueprint_problems = _validate_existing_blueprint_assignments(
				db, blueprint_round, assigned
			)
		except ValueError as error:
			raise HTTPException(status_code=409, detail=str(error))
		for problem in blueprint_problems:
			problem.test_cases = [test_case for test_case in problem.test_cases if not test_case.is_hidden]
		return [_to_problem_response(problem) for problem in blueprint_problems]

	problems = []
	for sp in assigned:
		p = db.query(CodingProblem).filter(CodingProblem.id == sp.problem_id).first()
		if p is not None:
			p.test_cases = [t for t in p.test_cases if not t.is_hidden]
			problems.append(p)
	if not problems:
		problems = list_problems(db)
	return [_to_problem_response(p) for p in problems]


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
	if active_round.expires_at is None:
		# Legacy/practice session without authoritative deadline - use default
		end_time = active_round.started_at + timedelta(minutes=settings.CODING_ROUND_TIME_LIMIT_MINUTES)
		logger.warning(
			"Coding round %s has no expires_at; using default limit of %d minutes",
			active_round.id, settings.CODING_ROUND_TIME_LIMIT_MINUTES
		)
	else:
		end_time = active_round.expires_at
	if datetime.utcnow() > end_time:
		finalize_coding_round(db, active_round.id)
		# Advance mock drive if this was part of a mock drive
		try_advance_mock_drive(db, active_round.session_id)
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
		# Check if there's an expired coding round that needs finalization
		expired_round = (
			db.query(AssessmentRound)
			.join(AssessmentSession, AssessmentRound.session_id == AssessmentSession.id)
			.filter(
				AssessmentSession.user_id == current_user.id,
				AssessmentRound.round_type == "coding",
				AssessmentRound.status == "expired",
			)
			.order_by(AssessmentRound.id.desc())
			.first()
		)
		if expired_round is not None:
			# Finalize the expired round and advance mock drive
			finalize_coding_round(db, expired_round.id)
			from app.services.faculty_practice_assignment_service import finalize_faculty_assigned_attempt
			finalize_faculty_assigned_attempt(db, current_user.id, expired_round.id)
			try_advance_mock_drive(db, expired_round.session_id)
			raise HTTPException(status_code=400, detail="coding round has expired")
		raise HTTPException(status_code=404, detail="no active coding round")

	# enforce timer and auto-finalize on expiry
	if active_round.expires_at is None:
		# Legacy/practice session without authoritative deadline - use default
		end_time = active_round.started_at + timedelta(minutes=settings.CODING_ROUND_TIME_LIMIT_MINUTES)
		logger.warning(
			"Coding round %s has no expires_at; using default limit of %d minutes",
			active_round.id, settings.CODING_ROUND_TIME_LIMIT_MINUTES
		)
	else:
		end_time = active_round.expires_at
	if datetime.utcnow() > end_time:
		# finalize and unlock interview
		finalize_coding_round(db, active_round.id)
		from app.services.faculty_practice_assignment_service import finalize_faculty_assigned_attempt
		finalize_faculty_assigned_attempt(db, current_user.id, active_round.id)
		try_advance_mock_drive(db, active_round.session_id)
		raise HTTPException(status_code=400, detail="coding round has expired")
	# Ensure problem is assigned to this round
	assigned = (
		db.query(SessionProblem)
		.filter(SessionProblem.round_id == active_round.id, SessionProblem.problem_id == payload.problem_id)
		.first()
	)
	if assigned is None:
		raise HTTPException(status_code=400, detail="problem not assigned to current round")

	try:
		result = run_and_evaluate(db, payload.problem_id, payload.code, payload.language, visible_only=False, round_id=active_round.id)
	except CodeExecutionUnavailable as exc:
		# Judge0 could not execute the code (not configured / unreachable /
		# auth-rejected). This is an infrastructure failure: fail closed with a
		# clear, non-2xx response and persist no candidate submission, so a mock
		# result can never silently stand in for real assessment execution.
		raise HTTPException(status_code=503, detail=str(exc))

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


@router.post("/start", response_model=List[CodingProblemResponse])
def start_round(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Start a coding round for the authenticated user's active session."""
	try:
		payload = start_coding_round(db, current_user.id)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# Collect the problem list from whichever key was populated
	problems = payload.get("problems") or []
	if not problems:
		assigned_problem_ids = [sp.problem_id for sp in payload.get("assigned", [])]
		problems = db.query(CodingProblem).filter(CodingProblem.id.in_(assigned_problem_ids)).all()
		for p in problems:
			p.test_cases = [t for t in p.test_cases if not t.is_hidden]

	return [_to_problem_response(p) for p in problems]


@router.post("/start-after-aptitude", response_model=List[CodingProblemResponse])
def start_after_aptitude(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
	"""Finalize the user's aptitude round and ensure coding round is available next."""
	latest_session = db.query(AssessmentSession).filter(
		AssessmentSession.user_id == current_user.id
	).order_by(AssessmentSession.id.desc()).first()
	if latest_session and latest_session.context_id:
		from app.models.assessment_context import AssessmentContext
		context = db.query(AssessmentContext).filter_by(id=latest_session.context_id).first()
		if context and (context.purpose or "").startswith("faculty_assignment:"):
			# Faculty-assigned sequencing is controlled by the persisted assignment,
			# and its next round starts in a separate engine session from Practice.
			return []
	active_aptitude = session_service.get_user_active_round(db, current_user.id, round_type="aptitude")
	if active_aptitude is not None:
		session_service.end_round(db, active_aptitude.id)

	try:
		payload = start_coding_round(db, current_user.id)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	problems = payload.get("problems") or []
	if not problems:
		assigned_problem_ids = [sp.problem_id for sp in payload.get("assigned", [])]
		problems = db.query(CodingProblem).filter(CodingProblem.id.in_(assigned_problem_ids)).all()
		for p in problems:
			p.test_cases = [t for t in p.test_cases if not t.is_hidden]

	return [_to_problem_response(p) for p in problems]


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
		active_session = session_service.get_active_session(db, current_user.id)
		if active_session is not None:
			from app.services.faculty_practice_assignment_service import finalize_faculty_assigned_session
			finalize_faculty_assigned_session(db, current_user.id, active_session.id)
		# If there is no active coding round, nothing to do — idempotent
		return {"status": "no_active_round"}

	# Finalize and unlock interview round
	score = finalize_coding_round(db, active_round.id)
	from app.services.faculty_practice_assignment_service import finalize_faculty_assigned_attempt
	finalize_faculty_assigned_attempt(db, current_user.id, active_round.id)

	# If this coding round was part of a Mock Drive, advance to the next enabled round
	mock_drive_advance = try_advance_mock_drive(db, active_round.session_id)

	response = {
		"status": "finalized",
		"round_score": score,
		"round_id": active_round.id,
		"session_id": active_round.session_id,
	}
	if mock_drive_advance:
		response["mock_drive"] = mock_drive_advance
	return response


@router.get("/submission/{submission_id}", response_model=CodingSubmissionStatusResponse)
def get_submission(
	submission_id: int,
	db: Session = Depends(get_db),
	current_user=Depends(get_current_user),
):
	from app.models.coding import CodingSubmission
	from app.models.assessment import AssessmentRound, AssessmentSession

	sub = db.query(CodingSubmission).filter(CodingSubmission.id == submission_id).first()
	if not sub:
		raise HTTPException(status_code=404, detail="submission not found")

	# Candidate isolation: only the submission owner (or staff roles) may read it.
	round_obj = db.query(AssessmentRound).filter(AssessmentRound.id == sub.round_id).first()
	owner_id = None
	if round_obj is not None:
		session_obj = (
			db.query(AssessmentSession)
			.filter(AssessmentSession.id == round_obj.session_id)
			.first()
		)
		owner_id = session_obj.user_id if session_obj is not None else None

	if owner_id != current_user.id:
		if current_user.role == "faculty" and owner_id is not None:
			require_faculty_student_access(db, current_user, owner_id)
		elif current_user.role not in ("admin", "tpo"):
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
