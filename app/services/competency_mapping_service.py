"""
Evidence-to-competency mapping foundation (Phase 4C Part 4, Stage 2).

This service links raw assessment evidence to competencies that were explicitly
configured on the session's pinned blueprint snapshot. Design rules:

* Mapping happens ONLY when the evidence's topic exactly matches a topic listed
  under a configured competency (case-insensitive, trimmed). No taxonomy
  category, question-text similarity, or guessed semantic matching is used.
* Evidence with no explicit topic (e.g. interview turns) is left unmapped.
* No competency score is calculated or persisted. ``raw_metric`` stores the
  original evidence values untouched.
* If a topic is claimed by more than one competency, it is ambiguous and is
  deliberately left unmapped rather than guessed.
* Mapping is idempotent and candidate/session isolated.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.aptitude import AptitudeAttempt
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext
from app.models.coding import CodingSubmission
from app.models.competency import CompetencyEvidenceMapping
from app.services.assessment_blueprint_service import get_session_blueprint_snapshot

logger = logging.getLogger(__name__)

APTITUDE_EVIDENCE_TYPE = "aptitude_attempt"
CODING_EVIDENCE_TYPE = "coding_submission"

# Competency evidence mapping lifecycle states (stored on AssessmentContext).
MAPPING_STATUS_PENDING = "pending"
MAPPING_STATUS_COMPLETED = "completed"
MAPPING_STATUS_FAILED = "failed"
MAPPING_STATUS_NOT_APPLICABLE = "not_applicable"

# Terminal states that must never be downgraded to failed by a redundant retry.
_MAPPING_TERMINAL_STATES = (MAPPING_STATUS_COMPLETED, MAPPING_STATUS_NOT_APPLICABLE)

# Maximum length of a persisted failure diagnostic (no candidate content stored).
_MAPPING_ERROR_MAX_LEN = 500


def _normalize(value: Any) -> str:
    return str(value).strip().casefold()


def configured_competencies(snapshot: Optional[dict]) -> list[dict]:
    """Return the competencies configured on the pinned blueprint snapshot.

    Returns an empty list when no snapshot or no competency configuration is
    present (legacy blueprints). Never invents competencies.
    """
    if not snapshot:
        return []
    blueprint_data = snapshot.get("blueprint_data") or {}
    competencies = blueprint_data.get("competencies")
    if not isinstance(competencies, list):
        return []
    return [c for c in competencies if isinstance(c, dict) and c.get("name")]


def competency_identifier(competency: dict) -> str:
    """Stable identifier for a configured competency.

    Uses the optional explicit ``id`` when present, otherwise the normalized
    (but human-readable) name.
    """
    explicit_id = competency.get("id")
    if explicit_id:
        return str(explicit_id).strip()
    return str(competency.get("name", "")).strip()


def _topic_to_competencies(competencies: list[dict]) -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for competency in competencies:
        topics = competency.get("topics") or []
        if not isinstance(topics, list):
            continue
        for topic in topics:
            key = _normalize(topic)
            if not key:
                continue
            lookup.setdefault(key, []).append(competency)
    return lookup


def match_competency_for_topic(
    competencies: list[dict], topic: Optional[str]
) -> Optional[dict]:
    """Return the single competency that explicitly lists ``topic``.

    Returns ``None`` when the topic matches nothing or when more than one
    competency claims the same topic (ambiguous -> never guessed).
    """
    if not topic:
        return None
    key = _normalize(topic)
    if not key:
        return None
    matches = _topic_to_competencies(competencies).get(key, [])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning(
            "Ambiguous competency topic %r claimed by %d competencies; left unmapped.",
            topic,
            len(matches),
        )
    return None


def _existing_mapping(
    db: Session, evidence_type: str, evidence_id: int, competency_id: str
) -> Optional[CompetencyEvidenceMapping]:
    return (
        db.query(CompetencyEvidenceMapping)
        .filter(
            CompetencyEvidenceMapping.evidence_type == evidence_type,
            CompetencyEvidenceMapping.evidence_id == evidence_id,
            CompetencyEvidenceMapping.competency_id == competency_id,
        )
        .first()
    )


def _build_mapping(
    *,
    session: AssessmentSession,
    round_id: int,
    evidence_type: str,
    evidence_id: int,
    competency: dict,
    source: str,
    blueprint_version: Optional[int],
    raw_metric: dict,
) -> CompetencyEvidenceMapping:
    return CompetencyEvidenceMapping(
        candidate_id=session.user_id,
        context_id=session.context_id,
        session_id=session.id,
        round_id=round_id,
        evidence_type=evidence_type,
        evidence_id=evidence_id,
        competency_id=competency_identifier(competency),
        competency_name=str(competency.get("name", "")).strip(),
        source=source,
        blueprint_version=blueprint_version,
        raw_metric=raw_metric,
    )


def _add_if_new(
    db: Session,
    created: list[CompetencyEvidenceMapping],
    **kwargs,
) -> None:
    evidence_type = kwargs["evidence_type"]
    evidence_id = kwargs["evidence_id"]
    competency_key = competency_identifier(kwargs["competency"])
    if any(
        m.evidence_type == evidence_type
        and m.evidence_id == evidence_id
        and m.competency_id == competency_key
        for m in created
    ):
        return
    if _existing_mapping(db, evidence_type, evidence_id, competency_key) is not None:
        return
    mapping = _build_mapping(**kwargs)
    db.add(mapping)
    created.append(mapping)


def has_configured_competencies(db: Session, session: AssessmentSession) -> bool:
    """Return True when the session's pinned snapshot declares competencies.

    Read-only for Mock Drive contexts (the snapshot is pinned at start). Never
    invents competencies; legacy/blueprintless sessions return False.
    """
    try:
        snapshot = get_session_blueprint_snapshot(db, session)
    except HTTPException:
        return False
    return bool(configured_competencies(snapshot))


def map_session_evidence(
    db: Session, session: AssessmentSession, *, commit: bool = True
) -> list[CompetencyEvidenceMapping]:
    """Map all explicitly-associated evidence for one session.

    Returns the newly created mappings. Evidence that cannot be explicitly
    matched to a configured competency stays unmapped; no score is produced.
    """
    try:
        snapshot = get_session_blueprint_snapshot(db, session)
    except HTTPException:
        logger.warning("No usable pinned snapshot for session %s; nothing mapped.", session.id)
        return []

    competencies = configured_competencies(snapshot)
    if not competencies:
        return []

    created = _persist_session_mappings(db, session, competencies, snapshot)
    if created and commit:
        db.commit()
    return created


def _persist_session_mappings(
    db: Session,
    session: AssessmentSession,
    competencies: list[dict],
    snapshot: dict,
) -> list[CompetencyEvidenceMapping]:
    blueprint_version = snapshot.get("blueprint_version")
    rounds = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .all()
    )

    created: list[CompetencyEvidenceMapping] = []
    for round_ in rounds:
        if round_.round_type == "aptitude":
            _map_aptitude_round(db, session, round_, competencies, blueprint_version, created)
        elif round_.round_type == "coding":
            _map_coding_round(db, session, round_, competencies, blueprint_version, created)
        # Interview rounds carry no explicit topic and are intentionally
        # left unmapped rather than guessed from free-text responses.
    return created


def _mapping_context(
    db: Session, session: AssessmentSession
) -> Optional[AssessmentContext]:
    """Return the AssessmentContext that owns this session, if any."""
    context = session.context
    if context is None and session.context_id is not None:
        context = (
            db.query(AssessmentContext)
            .filter(AssessmentContext.id == session.context_id)
            .first()
        )
    return context


def _safe_error(exc: BaseException) -> str:
    """Concise, content-free diagnostic for operators (no candidate responses)."""
    text = f"{type(exc).__name__}: {exc}".strip()
    if len(text) > _MAPPING_ERROR_MAX_LEN:
        text = text[:_MAPPING_ERROR_MAX_LEN]
    return text


def _run_mapping_attempt(
    db: Session, session: AssessmentSession, context: AssessmentContext
) -> None:
    """Run one mapping attempt for a completed Mock Drive session.

    Mapping writes are isolated in a SAVEPOINT so a failure never discards
    unrelated pending work in the caller's transaction and partial writes stay
    atomic. Assessment completion has already been committed by the caller.
    """
    session_id = getattr(session, "id", None)
    context_id = getattr(context, "id", None)
    # Resolve applicability before opening the savepoint so the (rare) lazy
    # snapshot backfill, which commits, never runs inside it.
    applicable = has_configured_competencies(db, session)

    savepoint = db.begin_nested()
    try:
        created = map_session_evidence(db, session, commit=False)
        db.flush()
        context.competency_mapping_status = (
            MAPPING_STATUS_COMPLETED if applicable else MAPPING_STATUS_NOT_APPLICABLE
        )
        context.competency_mapping_error = None
        context.competency_mapping_attempted_at = datetime.utcnow()
        context.competency_mapping_completed_at = datetime.utcnow()
        db.flush()
        savepoint.commit()
        db.commit()
        logger.info(
            "Competency mapping %s for session %s (%d new mapping(s)).",
            context.competency_mapping_status,
            session_id,
            len(created),
        )
    except Exception as exc:  # noqa: BLE001 - best-effort, never blocks completion
        savepoint.rollback()
        _record_mapping_failure(
            db, context, exc, session_id=session_id, context_id=context_id
        )


def _record_mapping_failure(
    db: Session,
    context: AssessmentContext,
    exc: BaseException,
    *,
    session_id: Optional[int],
    context_id: Optional[int],
) -> None:
    """Persist a failed mapping attempt in a fresh transaction.

    Runs after the savepoint rollback so the failure indicator survives the
    discarded partial mapping writes. Never downgrades a mapping that already
    completed successfully.
    """
    try:
        if context.competency_mapping_status in _MAPPING_TERMINAL_STATES:
            db.rollback()
            return
        context.competency_mapping_status = MAPPING_STATUS_FAILED
        context.competency_mapping_error = _safe_error(exc)
        context.competency_mapping_attempted_at = datetime.utcnow()
        db.commit()
    except Exception:  # noqa: BLE001 - failure indicator is best-effort
        db.rollback()
        logger.exception(
            "Could not persist competency mapping failure status for context %s "
            "(session %s).",
            context_id,
            session_id,
        )
    logger.exception(
        "Competency evidence mapping failed for context %s (session %s); "
        "assessment completion is unaffected and the mapping can be reprocessed "
        "via the Mock Drive competency-mapping recovery endpoint.",
        context_id,
        session_id,
    )


def finalize_session_competency_mapping(
    db: Session, session: AssessmentSession
) -> None:
    """Best-effort competency mapping when a Mock Drive assessment completes.

    Additive and non-blocking: mapping must never prevent a candidate from
    completing an assessment. Records a durable lifecycle status on the
    session's AssessmentContext (pending -> completed | not_applicable | failed)
    so a failed mapping can be detected and safely reprocessed. Never downgrades
    a mapping that already completed. No score is computed.
    """
    context = _mapping_context(db, session)
    if context is None or context.mock_drive_id is None:
        return
    if context.competency_mapping_status in _MAPPING_TERMINAL_STATES:
        return
    _run_mapping_attempt(db, session, context)


def reprocess_competency_mapping(
    db: Session, session: AssessmentSession
) -> dict[str, Any]:
    """Idempotent recovery entry point for one completed Mock Drive session.

    Retries mapping for a ``completed`` session whose mapping is missing,
    ``pending`` or ``failed``. Uses the session's pinned blueprint snapshot,
    never reruns the assessment, and never changes scores. Serialized per
    context via a row lock. Terminal states are never downgraded.
    """
    context = _mapping_context(db, session)
    if context is None or context.mock_drive_id is None:
        return {"status": "not_applicable", "reason": "not_a_mock_drive_session"}
    if session.status != "completed":
        return {"status": "skipped", "reason": "session_not_completed"}

    locked = (
        db.query(AssessmentContext)
        .filter(AssessmentContext.id == context.id)
        .with_for_update()
        .first()
    )
    if locked is None:
        return {"status": "skipped", "reason": "context_missing"}
    if locked.competency_mapping_status in _MAPPING_TERMINAL_STATES:
        return {
            "status": locked.competency_mapping_status,
            "reason": "already_final",
            "reprocessed": False,
        }

    _run_mapping_attempt(db, session, locked)
    refreshed = (
        db.query(AssessmentContext)
        .filter(AssessmentContext.id == context.id)
        .first()
    )
    return {
        "status": refreshed.competency_mapping_status,
        "error": refreshed.competency_mapping_error,
        "reprocessed": True,
    }


def _map_aptitude_round(
    db: Session,
    session: AssessmentSession,
    round_: AssessmentRound,
    competencies: list[dict],
    blueprint_version: Optional[int],
    created: list[CompetencyEvidenceMapping],
) -> None:
    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_.id)
        .all()
    )
    for attempt in attempts:
        question = attempt.question
        topic = None
        if question is not None and question.topic is not None:
            topic = question.topic.name
        competency = match_competency_for_topic(competencies, topic)
        if competency is None:
            continue
        raw_metric = {
            "topic": topic,
            "is_correct": attempt.is_correct,
            "response_time": attempt.response_time,
            "difficulty": attempt.difficulty,
            "reward": attempt.reward,
            "attempt_number": attempt.attempt_number,
        }
        _add_if_new(
            db,
            created,
            session=session,
            round_id=round_.id,
            evidence_type=APTITUDE_EVIDENCE_TYPE,
            evidence_id=attempt.id,
            competency=competency,
            source="aptitude",
            blueprint_version=blueprint_version,
            raw_metric=raw_metric,
        )


def _map_coding_round(
    db: Session,
    session: AssessmentSession,
    round_: AssessmentRound,
    competencies: list[dict],
    blueprint_version: Optional[int],
    created: list[CompetencyEvidenceMapping],
) -> None:
    submissions = (
        db.query(CodingSubmission)
        .filter(CodingSubmission.round_id == round_.id)
        .all()
    )
    for submission in submissions:
        problem = submission.problem
        tags = list(problem.tags_list or []) if problem is not None else []
        for tag in tags:
            competency = match_competency_for_topic(competencies, tag)
            if competency is None:
                continue
            raw_metric = {
                "topic": tag,
                "status": submission.status,
                "score": submission.score,
                "language": submission.language,
                "execution_time": submission.execution_time,
                "memory_used": submission.memory_used,
            }
            _add_if_new(
                db,
                created,
                session=session,
                round_id=round_.id,
                evidence_type=CODING_EVIDENCE_TYPE,
                evidence_id=submission.id,
                competency=competency,
                source="coding",
                blueprint_version=blueprint_version,
                raw_metric=raw_metric,
            )
