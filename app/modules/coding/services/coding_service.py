from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.coding import CodingProblem, CodingTestCase, CodingSubmission
from app.models.session_problem import SessionProblem
from app.modules.coding.utils.code_evaluator import (
    CodeExecutionUnavailable,
    evaluate_submission,
)
from app.services import session_service
from app.config.settings import settings
from app.models.assessment import AssessmentRound, AssessmentSession
from app.services.assessment_blueprint_service import (
    configured_question_count,
    difficulty_weights,
    get_session_blueprint_round_config,
    scheduled_round_value,
    topic_weights,
)
from app.services.topic_taxonomy import get_topic_category, normalize_topic


CODING_ROUND_PROBLEMS_COUNT = 3


def _matches_blueprint_topic(problem: CodingProblem, target_topic: Optional[str]) -> bool:
    if target_topic is None:
        return True

    target = normalize_topic(str(target_topic)) or str(target_topic).strip()
    if not target:
        return True

    for tag in problem.tags_list or []:
        canonical_tag = normalize_topic(str(tag)) or str(tag).strip()
        if not canonical_tag:
            continue

        if canonical_tag.casefold() == target.casefold():
            return True

        if (
            target.casefold() == "data structures & algorithms"
            and get_topic_category(canonical_tag) == "Data Structures & Algorithms"
        ):
            return True

    return False


def _matches_blueprint_difficulty(problem: CodingProblem, target_difficulty: Optional[str]) -> bool:
    if target_difficulty is None:
        return True
    return (problem.difficulty or "").casefold() == str(target_difficulty).casefold()


def _validate_existing_blueprint_assignments(
    db: Session,
    round_config: dict,
    assignments: list[SessionProblem],
    pool_problem_ids: Optional[list] = None,
) -> list[CodingProblem]:
    count = configured_question_count(round_config) or CODING_ROUND_PROBLEMS_COUNT
    problem_ids = [assignment.problem_id for assignment in assignments]
    if len(assignments) != count or len(set(problem_ids)) != count:
        raise ValueError(
            "Existing coding assignments do not satisfy the pinned blueprint: "
            f"expected {count} unique assignments, found {len(assignments)}."
        )
    if pool_problem_ids is not None:
        scoped = set(pool_problem_ids)
        if any(problem_id not in scoped for problem_id in problem_ids):
            raise ValueError(
                "Existing coding assignments are outside the generated problem pool "
                "and cannot be resumed safely."
            )

    problems = (
        db.query(CodingProblem)
        .filter(CodingProblem.id.in_(problem_ids))
        .all()
    )
    problems_by_id = {problem.id: problem for problem in problems}
    if len(problems_by_id) != count:
        raise ValueError(
            "Existing coding assignments do not satisfy the pinned blueprint: "
            "one or more assigned coding problems are unavailable."
        )

    topics = topic_weights(round_config)
    difficulties = difficulty_weights(round_config)
    ordered_problems = []
    for index, assignment in enumerate(assignments):
        problem = problems_by_id[assignment.problem_id]
        target_topic = scheduled_round_value(topics, index)
        target_difficulty = scheduled_round_value(difficulties, index)
        if (
            not _matches_blueprint_topic(problem, target_topic)
            or not _matches_blueprint_difficulty(problem, target_difficulty)
        ):
            raise ValueError(
                "Existing coding assignments do not satisfy the pinned blueprint: "
                f"problem {problem.id} does not match scheduled topic "
                f"{target_topic!r} and difficulty {target_difficulty!r}."
            )
        ordered_problems.append(problem)

    return ordered_problems


def _select_blueprint_coding_problems(
    db: Session,
    round_obj: AssessmentRound,
    round_config: dict,
    problem_ids: Optional[list] = None,
) -> list[CodingProblem]:
    count = configured_question_count(round_config) or CODING_ROUND_PROBLEMS_COUNT
    problems_query = db.query(CodingProblem).order_by(CodingProblem.id)
    if problem_ids is not None:
        # Pool-only scoping: a complete generated pool is authoritative, so the
        # seeded bank is never mixed in (and never silently substituted). An
        # empty scope yields no candidates and surfaces the usual inventory gap.
        problems_query = problems_query.filter(CodingProblem.id.in_(problem_ids))
    problems = problems_query.all()
    if len(problems) < count:
        raise ValueError(
            "Configured blueprint cannot currently be satisfied by the available coding question bank: "
            f"requested {count} unique coding problems, but only {len(problems)} are available."
        )

    selected: list[CodingProblem] = []
    selected_ids: set[int] = set()
    topics = topic_weights(round_config)
    difficulties = difficulty_weights(round_config)

    for index in range(count):
        target_topic = scheduled_round_value(topics, index)
        target_difficulty = scheduled_round_value(difficulties, index)
        remaining = [problem for problem in problems if problem.id not in selected_ids]

        candidates = [
            problem
            for problem in remaining
            if _matches_blueprint_topic(problem, target_topic)
            and _matches_blueprint_difficulty(problem, target_difficulty)
        ]

        # A broad DSA bucket also matches specific topics such as Arrays.
        # Reserve candidates that satisfy later scheduled topics so the broad
        # bucket cannot consume their only eligible inventory first.
        reserved_ids = set()
        for future_index in range(index + 1, count):
            future_topic = scheduled_round_value(topics, future_index)
            future_difficulty = scheduled_round_value(difficulties, future_index)
            for problem in remaining:
                if (
                    _matches_blueprint_topic(problem, future_topic)
                    and _matches_blueprint_difficulty(problem, future_difficulty)
                ):
                    reserved_ids.add(problem.id)
        unreserved = [problem for problem in candidates if problem.id not in reserved_ids]
        if unreserved:
            candidates = unreserved

        if not candidates:
            raise ValueError(
                "Configured blueprint cannot currently be satisfied by the available coding question bank: "
                f"unable to assign {count} unique coding problems while respecting the blueprint topic "
                f"requirements (requested topic={target_topic!r}, difficulty={target_difficulty!r})."
            )

        chosen = random.choice(candidates)
        selected.append(chosen)
        selected_ids.add(chosen.id)

    if len(selected) != count or len({problem.id for problem in selected}) != count:
        raise ValueError(
            "Configured blueprint cannot currently be satisfied by the available coding question bank: "
            f"selected {len(selected)} unique problems for a configured target of {count}."
        )

    return selected


def configured_time_limit(round_config: Optional[dict]) -> Optional[int]:
    value = (round_config or {}).get("time_limit_minutes")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return int(value)


def list_problems(db: Session) -> List[CodingProblem]:
    # Return a small set of problems for the round (visible test cases only)
    problems = (
        db.query(CodingProblem)
        .order_by(CodingProblem.id)
        .limit(CODING_ROUND_PROBLEMS_COUNT)
        .all()
    )
    # Eager load only non-hidden test cases
    for p in problems:
        p.test_cases = [t for t in p.test_cases if not t.is_hidden]
    return problems


def start_coding_round(db: Session, user_id: int) -> dict:
    """Create or resume the active coding round and assign problems exactly once."""
    session = session_service.get_active_session(db, user_id)
    if session is None:
        # Allow coding round to be started directly from dashboard by creating a session.
        session = session_service.create_session(db, user_id=user_id)

    # Expire an overdue round first. That helper commits, so acquire the
    # session lock afterwards and hold it while finding/creating the active
    # coding round and assigning its problems. This makes concurrent StrictMode
    # or retry requests share the same assignment set.
    session_service.get_user_active_round(db, user_id, round_type="coding")
    session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session.id)
        .with_for_update()
        .one()
    )
    round_query = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.round_type == "coding",
        AssessmentRound.status == "active",
    ).order_by(AssessmentRound.id.desc())
    round_obj = round_query.with_for_update().first()
    if round_obj is None:
        round_obj = session_service.create_round(
            db, session_id=session.id, round_type="coding"
        )
        # create_round commits, releasing the session lock. Re-lock the round
        # and re-read assignments below in case another start request won it.
        round_obj = db.query(AssessmentRound).filter(
            AssessmentRound.id == round_obj.id
        ).with_for_update().one()

    snapshot, blueprint_round = get_session_blueprint_round_config(db, round_obj.session_id, "coding")
    configured_count = configured_question_count(blueprint_round)
    blueprint_backed = snapshot is not None and blueprint_round is not None
    pool_problem_ids = None
    if blueprint_backed:
        from app.services.question_pool_generation_service import (
            question_pool_generation_service,
        )

        pool_problem_ids = question_pool_generation_service.coding_pool_scope(db, snapshot)
    if blueprint_backed:
        round_obj.max_questions = configured_count or CODING_ROUND_PROBLEMS_COUNT
        duration = configured_time_limit(blueprint_round)
        if duration:
            round_obj.expires_at = round_obj.started_at + timedelta(minutes=duration)

    assigned = (
        db.query(SessionProblem)
        .filter(SessionProblem.round_id == round_obj.id)
        .order_by(SessionProblem.problem_order.asc(), SessionProblem.id.asc())
        .all()
    )
    if assigned:
        if blueprint_backed:
            problems = _validate_existing_blueprint_assignments(
                db, blueprint_round, assigned, pool_problem_ids=pool_problem_ids
            )
        else:
            problems = [
                db.query(CodingProblem).filter(CodingProblem.id == item.problem_id).first()
                for item in assigned
            ]
            problems = [problem for problem in problems if problem is not None]
    else:
        if blueprint_backed:
            problems = _select_blueprint_coding_problems(
                db, round_obj, blueprint_round, problem_ids=pool_problem_ids
            )
            expected_count = configured_count or CODING_ROUND_PROBLEMS_COUNT
            if len(problems) != expected_count or len({problem.id for problem in problems}) != expected_count:
                raise ValueError(
                    "Configured blueprint cannot currently be satisfied by the available coding question bank: "
                    f"selected {len(problems)} unique problems for a configured target of {expected_count}."
                )
        else:
            problems = db.query(CodingProblem).order_by(func.random()).limit(CODING_ROUND_PROBLEMS_COUNT).all()

        assigned = []
        for idx, problem in enumerate(problems, start=1):
            item = SessionProblem(
                round_id=round_obj.id,
                problem_id=problem.id,
                problem_order=idx,
                marked_for_review=False,
                assigned_at=datetime.now(),
            )
            db.add(item)
            assigned.append(item)
        db.commit()
        for item in assigned:
            db.refresh(item)

    for problem in problems:
        problem.test_cases = [test_case for test_case in problem.test_cases if not test_case.is_hidden]
    db.commit()
    return {"round": round_obj, "assigned": assigned, "problems": problems}


def run_and_evaluate(
    db: Session,
    problem_id: int,
    code: str,
    language: str,
    visible_only: bool = True,
    round_id: Optional[int] = None,
) -> Dict[str, Any]:
    # Load test cases
    test_cases = (
        db.query(CodingTestCase)
        .filter(CodingTestCase.problem_id == problem_id)
        .order_by(CodingTestCase.case_order)
        .all()
    )
    if visible_only:
        test_cases = [t for t in test_cases if not t.is_hidden]

    result = evaluate_submission(code=code, language=language, test_cases=test_cases, visible_only=visible_only)

    status = result.get("status")
    if status not in {"running", "accepted", "wrong_answer", "runtime_error", "time_limit_exceeded", "compilation_error", "memory_limit_exceeded", "internal_error"}:
        status = "accepted" if (result.get("score") or 0) >= 1.0 else "wrong_answer"
    result["status"] = status

    # A full submit is the scored assessment path. When Judge0 could not execute
    # the code (not configured / unreachable / auth-rejected) the result is an
    # infrastructure failure, not a property of the candidate's submission. It
    # must never be persisted as a candidate "runtime_error"/0 score, because
    # that would silently substitute a mock result for real execution.
    if not visible_only and status == "internal_error":
        raise CodeExecutionUnavailable(
            result.get("message")
            or "Code execution is currently unavailable; the submission was not scored."
        )

# If this is a full submit, persist a CodingSubmission row
    if not visible_only:
        if round_id is None:
            raise ValueError("round_id is required for submissions")

        # The DB CHECK constraint only allows these values — remap anything outside it.
        # internal_error and memory_limit_exceeded are not in the original constraint.
        _DB_ALLOWED_STATUSES = {"running", "accepted", "wrong_answer", "runtime_error",
                                 "time_limit_exceeded", "compilation_error"}
        persist_status = status if status in _DB_ALLOWED_STATUSES else "runtime_error"

        submission = CodingSubmission(
            round_id=round_id,
            problem_id=problem_id,
            code=code,
            language=language,
            judge0_token=result.get("judge0_token"),
            status=persist_status,
            score=result.get("score"),
            execution_time=result.get("execution_time"),
            memory_used=result.get("memory_used"),
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        result["submission_id"] = submission.id

    return result


def finalize_coding_round(db: Session, round_id: int) -> float:
    """Compute best submission per assigned problem for the round and update round/session scores.

    Returns the computed round score (0..1).
    """
    # Get assigned problems
    assigned = db.query(SessionProblem).filter(SessionProblem.round_id == round_id).all()
    if not assigned:
        # No problems assigned — still mark the round completed so result endpoint works
        rnd = db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()
        if rnd and rnd.status != "completed":
            rnd.score = 0.0
            rnd.status = "completed"
            db.commit()
        return 0.0

    best_scores = []
    for sp in assigned:
        best = (
            db.query(func.max(CodingSubmission.score))
            .filter(CodingSubmission.round_id == round_id, CodingSubmission.problem_id == sp.problem_id)
            .scalar()
        )
        best_scores.append(float(best or 0.0))

    round_score = sum(best_scores) / len(best_scores) if best_scores else 0.0

    # Update round record
    rnd = db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()

    if rnd:
        # Idempotent: only update if not already completed
        if rnd.status != "completed":
            rnd.score = round_score
            rnd.status = "completed"
            db.commit()

            # Update session total as average of completed rounds
            session_id = rnd.session_id
            completed_scores = (
                db.query(func.avg(AssessmentRound.score))
                .filter(AssessmentRound.session_id == session_id, AssessmentRound.status == "completed")
                .scalar()
            )
            sess = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
            if sess:
                sess.total_score = float(completed_scores or 0.0)
                db.commit()

            # M2-E: Do NOT auto-create interview round.
            # Practice uses independent progression — the user selects the next
            # round themselves from the dashboard. Auto-creating interview here
            # blocks the user from starting other round types (409 conflict).

    return round_score
