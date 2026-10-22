"""Blueprint question-pool generation orchestrator.

This service is the ONLY entry point for the TPO "Generate Question Pool" flow
(Parts: generate -> validate -> persist -> complete) and for the runtime
integration points that consume generated pools:

- ``aptitude_pool_scope`` / ``coding_pool_scope`` -> Phase 4C pool-only scoping
- ``complete_pool_for_round``                   -> interview clone (no candidate-time LLM)
- ``publish_blocking_errors``                    -> publish gate for LLM-provenance blueprints

Design rules enforced here:
- Generation happens ONLY pre-candidate from an approved blueprint.
- A pool is marked ``complete`` ONLY after the full pool validated and persisted.
- Invalid/failed pools are never partially or silently substituted in.
- Regeneration is version-isolated: rows are only replaced for the exact
  (blueprint_id, blueprint_version, round_type) and - because generated rows are
  referenced by candidate assignments - a pool already in use cannot be silently
  replaced (integrity error -> pool marked failed instead).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.aptitude import AptitudeQuestion, AptitudeTopic
from app.models.coding import CodingProblem, CodingTestCase
from app.models.question_pool_generation import (
    GENERATED_POOL_ROUNDS,
    POOL_BATCH_SIZES,
    POOL_SIZES,
    POOL_STATUS_COMPLETE,
    POOL_STATUS_FAILED,
    POOL_STATUS_INCOMPLETE,
    POOL_STATUS_IN_PROGRESS,
    GeneratedQuestionPool,
)
from app.services.assessment_blueprint_service import (
    configured_question_count,
    difficulty_weights,
    get_blueprint_round_config,
    get_drive_blueprint_snapshot,
    scheduled_round_value,
    snapshot_company_blueprint,
    topic_weights,
    weighted_schedule,
)
from app.services.groq_service import GroqService
from app.services.question_pool_validation import (
    deduplicate_pool,
    missing_interview_topics,
    select_deterministic_pool,
    validate_aptitude_pool,
    validate_coding_pool,
    validate_interview_pool,
)

logger = logging.getLogger(__name__)

SOURCE_LLM = "llm_generated"

INTERVIEW_ROUNDS = ("technical_interview", "hr_interview")

# Bounded topic-specific top-up: at most this many focused provider calls per
# configured interview topic that received no authored question in the pool.
INTERVIEW_TOPIC_TOPUP_ATTEMPTS = 1


def pool_batch_plan(round_type: str, pool_size: int) -> List[int]:
    """Split ``pool_size`` into bounded per-call sizes for one round.

    Returns the list of item counts, in generation order, that sum to
    ``pool_size``. Each entry is at most the round's batch size, so a 30-item
    aptitude pool is requested as 10+10+10, a 10-item coding pool as 5+5, and
    so on. A pool smaller than the batch size is a single call.
    """
    pool_size = int(pool_size or 0)
    if pool_size <= 0:
        return []
    batch_size = int(POOL_BATCH_SIZES.get(round_type) or pool_size)
    if batch_size >= pool_size:
        return [pool_size]
    plan = [batch_size] * (pool_size // batch_size)
    remainder = pool_size % batch_size
    if remainder:
        plan.append(remainder)
    return plan


def _interview_positions(
    topics: Dict[str, float], pool_size: int
) -> List[Dict[str, Any]]:
    """Deterministic topic schedule for an interview pool.

    Every configured topic is placed at least once (so batched generation can
    never silently drop one); the remaining slots follow the weighted-fair
    sequence, matching the aptitude/coding scheduling behavior.
    """
    names = list(topics.keys())
    positions = [{"topic": name} for name in names[:pool_size]]
    remaining = pool_size - len(positions)
    if remaining > 0:
        positions += [
            {"topic": name}
            for name in weighted_schedule(topics, pool_size)[:remaining]
        ]
    return positions


class _GroqAdapter:
    """Default LLM generator facade (replaced by tests via ``llm_generator``)."""

    def __init__(self) -> None:
        self._client = GroqService(settings.GROQ_API_KEY)

    def generate_aptitude_question_pool(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._client.generate_aptitude_question_pool(spec)

    def generate_coding_problem_pool(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._client.generate_coding_problem_pool(spec)

    def generate_interview_question_pool(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._client.generate_interview_question_pool(spec)


class QuestionPoolGenerationService:
    def __init__(self, llm_generator: Optional[Any] = None) -> None:
        self._llm = llm_generator or _GroqAdapter()

    # ── Blueprint introspection ─────────────────────────────────────

    @staticmethod
    def rounds_for_blueprint(snapshot: Optional[Dict[str, Any]]) -> List[str]:
        if not snapshot:
            return []
        rounds = (snapshot.get("blueprint_data") or {}).get("rounds") or []
        ordered = []
        for round_config in rounds:
            if isinstance(round_config, dict):
                round_type = round_config.get("round_type")
                if round_type in GENERATED_POOL_ROUNDS and round_type not in ordered:
                    ordered.append(round_type)
        return ordered

    # ── Registry queries ────────────────────────────────────────────

    def complete_pool_for_round(
        self,
        db: Session,
        blueprint_id: Optional[int],
        blueprint_version: Optional[int],
        round_type: str,
    ) -> Optional[GeneratedQuestionPool]:
        """Return the complete generated pool registry row, or None."""
        if blueprint_id is None or blueprint_version is None:
            return None
        return (
            db.query(GeneratedQuestionPool)
            .filter(
                GeneratedQuestionPool.blueprint_id == blueprint_id,
                GeneratedQuestionPool.blueprint_version == blueprint_version,
                GeneratedQuestionPool.round_type == round_type,
                GeneratedQuestionPool.status == POOL_STATUS_COMPLETE,
            )
            .first()
        )

    def list_pool_statuses(
        self, db: Session, blueprint: Any
    ) -> List[Dict[str, Any]]:
        """Return per-round generation status for the TPO UI."""
        snapshot = snapshot_company_blueprint(blueprint)
        rows = {
            row.round_type: row
            for row in db.query(GeneratedQuestionPool).filter(
                GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.blueprint_version == blueprint.version,
            ).all()
        }
        result = []
        for round_type in self.rounds_for_blueprint(snapshot):
            row = rows.get(round_type)
            pool_size = POOL_SIZES.get(round_type, 0)
            result.append(
                {
                    "round_type": round_type,
                    "pool_size": pool_size,
                    "required_count": pool_size,
                    "status": row.status if row else "not_generated",
                    "validated_count": row.validated_count if row else 0,
                    "generation_error": row.generation_error if row else None,
                    "generated": bool(row and row.status == POOL_STATUS_COMPLETE),
                }
            )
        return result

    # ── Runtime scoping (Phase 4C pool-only with seeded fallback) ─────

    def aptitude_pool_scope(
        self, db: Session, snapshot: Optional[Dict[str, Any]]
    ) -> Optional[List[int]]:
        """Return generated aptitude question IDs when a complete pool exists.

        ``None`` means "no complete pool" -> Phase 4C falls back to the seeded
        bank (backward compatible). A non-empty list is authoritative and
        pool-only.
        """
        if not snapshot:
            return None
        if self.complete_pool_for_round(
            db, snapshot.get("blueprint_id"), snapshot.get("blueprint_version"), "aptitude"
        ) is None:
            return None
        return [
            row[0]
            for row in db.query(AptitudeQuestion.id)
            .filter(
                AptitudeQuestion.blueprint_id == snapshot.get("blueprint_id"),
                AptitudeQuestion.blueprint_version == snapshot.get("blueprint_version"),
                AptitudeQuestion.source == SOURCE_LLM,
            )
            .order_by(AptitudeQuestion.id)
            .all()
        ]

    def coding_pool_scope(
        self, db: Session, snapshot: Optional[Dict[str, Any]]
    ) -> Optional[List[int]]:
        """Return generated coding problem IDs when a complete pool exists."""
        if not snapshot:
            return None
        if self.complete_pool_for_round(
            db, snapshot.get("blueprint_id"), snapshot.get("blueprint_version"), "coding"
        ) is None:
            return None
        return [
            row[0]
            for row in db.query(CodingProblem.id)
            .filter(
                CodingProblem.blueprint_id == snapshot.get("blueprint_id"),
                CodingProblem.blueprint_version == snapshot.get("blueprint_version"),
                CodingProblem.source == SOURCE_LLM,
            )
            .order_by(CodingProblem.id)
            .all()
        ]

    # ── Generation ──────────────────────────────────────────────────

    def generate_for_blueprint(
        self,
        db: Session,
        blueprint: Any,
        created_by_id: Optional[int],
    ) -> Dict[str, Any]:
        """Generate a validated pool for every enabled round of a blueprint.

        Idempotent: rounds with an existing complete pool are skipped. Rounds
        that regenerate cleanly replace prior generated rows for the exact
        (blueprint_id, blueprint_version, round_type).
        """
        if blueprint.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Blueprint {blueprint.id} must be approved before a question "
                    f"pool can be generated (current status: {blueprint.status!r})."
                ),
            )

        snapshot = snapshot_company_blueprint(blueprint)
        round_statuses: List[Dict[str, Any]] = []
        for round_type in self.rounds_for_blueprint(snapshot):
            if self.complete_pool_for_round(
                db, blueprint.id, blueprint.version, round_type
            ) is not None:
                round_statuses.append(
                    {
                        "round_type": round_type,
                        "status": POOL_STATUS_COMPLETE,
                        "required_count": POOL_SIZES[round_type],
                        "validated_count": POOL_SIZES[round_type],
                        "generation_error": None,
                        "skipped": True,
                    }
                )
                continue
            round_config = get_blueprint_round_config(snapshot, round_type)
            round_statuses.append(
                self._generate_round(
                    db=db,
                    blueprint=blueprint,
                    snapshot=snapshot,
                    round_type=round_type,
                    round_config=round_config,
                    created_by_id=created_by_id,
                )
            )
        return {
            "blueprint_id": blueprint.id,
            "blueprint_version": blueprint.version,
            "rounds": round_statuses,
        }

    def _generate_round(
        self,
        db: Session,
        blueprint: Any,
        snapshot: Dict[str, Any],
        round_type: str,
        round_config: Optional[Dict[str, Any]],
        created_by_id: Optional[int],
    ) -> Dict[str, Any]:
        pool_size = POOL_SIZES[round_type]
        registry = self._upsert_registry(
            db, blueprint, round_type, pool_size, created_by_id
        )
        registry.status = POOL_STATUS_IN_PROGRESS
        registry.generation_error = None
        db.commit()

        spec = self._build_spec(
            blueprint, snapshot, round_type, round_config, pool_size
        )
        try:
            items = self._generate_in_batches(round_type, spec)
            # Providers routinely echo an approved topic label with different
            # capitalization/whitespace. Aptitude/coding validation matches the
            # topic exactly, so canonicalize each item's topic to the blueprint's
            # approved label before selection/validation/persistence; this keeps
            # an otherwise-correct pool from being failed and stops persisted
            # rows creating a near-duplicate topic. Genuinely different topics
            # are left untouched and still fail. (Interview coverage already
            # compares topics case-insensitively, so it is unchanged.)
            if round_type in ("aptitude", "coding"):
                items = self._canonicalize_topics(items, spec.get("topics") or [])
            # Cross-batch repeats are dropped before selection/validation so a
            # batched provider call cannot fail the pool on duplicates alone.
            items = deduplicate_pool(items, round_type)
            if round_type in INTERVIEW_ROUNDS:
                # Batched calls can omit a configured topic; author a bounded,
                # topic-specific top-up so every required topic has a question.
                items = self._ensure_interview_topic_coverage(round_type, spec, items)
                items = deduplicate_pool(items, round_type)
            items = select_deterministic_pool(items, spec)
            if round_type == "aptitude":
                valid, reasons = validate_aptitude_pool(items, spec)
                if not valid:
                    raise ValueError("Aptitude pool failed validation: " + "; ".join(reasons))
                count = self._persist_aptitude_rows(db, blueprint, round_type, spec, items, created_by_id)
            elif round_type == "coding":
                valid, reasons = validate_coding_pool(items, spec)
                if not valid:
                    raise ValueError("Coding pool failed validation: " + "; ".join(reasons))
                count = self._persist_coding_rows(db, blueprint, round_type, spec, items, created_by_id)
            elif round_type in ("technical_interview", "hr_interview"):
                valid, reasons = validate_interview_pool(items, spec)
                if not valid:
                    raise ValueError(
                        f"{round_type} pool failed validation: " + "; ".join(reasons)
                    )
                count = self._persist_interview_content(db, blueprint, round_type, spec, items)
            else:  # pragma: no cover - guarded by rounds_for_blueprint
                raise ValueError(f"Unsupported round_type {round_type!r}")

            registry.status = POOL_STATUS_COMPLETE
            registry.validated_count = count
            registry.generation_error = None
            db.commit()
        except ValueError as error:
            db.rollback()
            registry = db.get(GeneratedQuestionPool, registry.id)
            registry.status = POOL_STATUS_INCOMPLETE
            registry.generation_error = str(error)
            db.commit()
            return self._round_result(registry)
        except Exception as error:  # noqa: BLE001 - network/db failures surface as failed
            logger.exception("Pool generation failed for %s", round_type)
            db.rollback()
            registry = db.get(GeneratedQuestionPool, registry.id)
            registry.status = POOL_STATUS_FAILED
            registry.generation_error = str(error)[:2000]
            db.commit()
            return self._round_result(registry)

        return {
            "round_type": round_type,
            "status": POOL_STATUS_COMPLETE,
            "required_count": pool_size,
            "validated_count": registry.validated_count,
            "generation_error": None,
            "skipped": False,
        }

    def _round_result(self, registry: GeneratedQuestionPool) -> Dict[str, Any]:
        return {
            "round_type": registry.round_type,
            "status": registry.status,
            "required_count": registry.required_count,
            "validated_count": registry.validated_count,
            "generation_error": registry.generation_error,
            "skipped": False,
        }

    def _upsert_registry(
        self,
        db: Session,
        blueprint: Any,
        round_type: str,
        pool_size: int,
        created_by_id: Optional[int],
    ) -> GeneratedQuestionPool:
        registry = (
            db.query(GeneratedQuestionPool)
            .filter(
                GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.blueprint_version == blueprint.version,
                GeneratedQuestionPool.round_type == round_type,
            )
            .first()
        )
        if registry is None:
            registry = GeneratedQuestionPool(
                blueprint_id=blueprint.id,
                blueprint_version=blueprint.version,
                company_name=blueprint.company_name,
                target_role=blueprint.target_role,
                round_type=round_type,
                status=POOL_STATUS_IN_PROGRESS,
                required_count=pool_size,
                validated_count=0,
                created_by_id=created_by_id,
            )
            db.add(registry)
            db.flush()
        return registry

    def _generate_in_batches(
        self, round_type: str, spec: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate one pool through bounded provider calls.

        The pool is requested in batches of at most ``POOL_BATCH_SIZES`` items
        (e.g. aptitude 10+10+10, coding 5+5) instead of a single large request.
        Each batch gets its own spec copy:
        - ``pool_size``       -> this batch's item count
        - ``positions``       -> this batch's slice of the blueprint schedule
        - ``position_offset`` -> global index of the batch's first schedule slot,
          so generators can number items globally and stay unique across batches
        Results are concatenated in batch order; de-duplication, deterministic
        selection, and validation then run once against the FULL spec.
        """
        plan = pool_batch_plan(round_type, int(spec.get("pool_size") or 0))
        if not plan:
            return self._call_provider(round_type, spec)

        positions = list(spec.get("positions") or [])
        full_size = int(spec.get("pool_size") or 0)
        sliceable = bool(positions) and len(positions) == full_size

        collected: List[Dict[str, Any]] = []
        offset = 0
        for batch_size in plan:
            batch_spec = dict(spec)
            batch_spec["pool_size"] = batch_size
            batch_spec["position_offset"] = offset
            if sliceable:
                batch_spec["positions"] = positions[offset:offset + batch_size]
            collected.extend(self._call_provider(round_type, batch_spec))
            offset += batch_size
        return collected

    def _call_provider(self, round_type: str, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        if round_type == "aptitude":
            return self._llm.generate_aptitude_question_pool(spec)
        if round_type == "coding":
            return self._llm.generate_coding_problem_pool(spec)
        if round_type in ("technical_interview", "hr_interview"):
            return self._llm.generate_interview_question_pool(spec)
        raise ValueError(f"Unsupported round_type {round_type!r}")  # pragma: no cover

    # ── Interview topic coverage (bounded, topic-specific top-up) ────

    def _ensure_interview_topic_coverage(
        self,
        round_type: str,
        spec: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Author a bounded, topic-specific question for any uncovered topic.

        Batched generation can omit a configured topic entirely (each batch is
        asked for fewer items than there are topics). For every configured topic
        with no authored question, request a single focused question, bounded by
        ``INTERVIEW_TOPIC_TOPUP_ATTEMPTS``; only shape-valid items whose topic
        matches the requested topic are accepted. A topic that still has no
        valid question fails validation afterwards with the clear coverage error
        - no generic fallback is ever substituted.
        """
        missing = missing_interview_topics(items, spec)
        if not missing:
            return items
        for topic in missing:
            for _ in range(INTERVIEW_TOPIC_TOPUP_ATTEMPTS):
                focused_spec = {
                    "company_name": spec.get("company_name"),
                    "target_role": spec.get("target_role"),
                    "round_type": round_type,
                    "phase": spec.get("phase"),
                    "difficulty_distribution": spec.get("difficulty_distribution") or {},
                    "pool_size": 1,
                    "topics": [topic],
                    "positions": [{"topic": topic}],
                    "position_offset": 0,
                }
                try:
                    produced = self._call_provider(round_type, focused_spec)
                except Exception:  # noqa: BLE001 - a failed top-up just leaves the topic missing
                    logger.warning(
                        "Interview topic top-up call failed for %r", topic, exc_info=True
                    )
                    continue
                candidate = self._first_valid_topic_item(produced, topic, spec)
                if candidate is not None:
                    items.append(candidate)
                    break
        return items

    @staticmethod
    def _first_valid_topic_item(
        produced: Optional[List[Dict[str, Any]]],
        topic: str,
        spec: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Return the first item that is a valid, single question for ``topic``."""
        single_spec = {
            "pool_size": 1,
            "phase": spec.get("phase"),
            "topics": [topic],
            "positions": [{"topic": topic}],
        }
        for candidate in produced or []:
            if not isinstance(candidate, dict):
                continue
            valid, _ = validate_interview_pool([candidate], single_spec)
            if valid:
                return candidate
        return None

    def _build_spec(
        self,
        blueprint: Any,
        snapshot: Dict[str, Any],
        round_type: str,
        round_config: Optional[Dict[str, Any]],
        pool_size: int,
    ) -> Dict[str, Any]:
        topics = topic_weights(round_config)
        difficulties = difficulty_weights(round_config)
        base = {
            "company_name": blueprint.company_name,
            "target_role": blueprint.target_role,
            "round_type": round_type,
            "pool_size": pool_size,
            "topics": list(topics.keys()),
            "difficulty_distribution": difficulties,
            "question_count": configured_question_count(round_config),
        }
        if round_type == "aptitude":
            base["positions"] = [
                {
                    "topic": scheduled_round_value(topics, idx),
                    "difficulty": scheduled_round_value(difficulties, idx),
                }
                for idx in range(pool_size)
            ]
        elif round_type == "coding":
            base["positions"] = [
                {
                    "topic": scheduled_round_value(topics, idx),
                    "difficulty": scheduled_round_value(difficulties, idx),
                }
                for idx in range(pool_size)
            ]
        elif round_type == "technical_interview":
            base["phase"] = "TECHNICAL"
            if topics:
                base["positions"] = _interview_positions(topics, pool_size)
        elif round_type == "hr_interview":
            base["phase"] = "HR"
            if topics:
                base["positions"] = _interview_positions(topics, pool_size)
        return base

    @staticmethod
    def _canonicalize_topics(
        items: List[Dict[str, Any]], topics: List[str]
    ) -> List[Dict[str, Any]]:
        """Rewrite each item's topic to the blueprint's approved label.

        Comparison ignores surrounding whitespace and case (matching the
        interview topic-coverage comparison), so a provider that changes only
        the casing of a configured topic does not fail the pool. An item whose
        topic does not case-insensitively match any configured topic is left
        untouched, so genuinely unrelated topics still fail validation.
        """
        canonical = {}
        for name in topics:
            if isinstance(name, str) and name.strip():
                canonical.setdefault(name.strip().casefold(), name.strip())
        if not canonical:
            return items
        for item in items:
            raw = item.get("topic") if isinstance(item, dict) else None
            if not isinstance(raw, str):
                continue
            approved = canonical.get(raw.strip().casefold())
            if approved is not None:
                item["topic"] = approved
        return items

    def _persist_aptitude_rows(
        self,
        db: Session,
        blueprint: Any,
        round_type: str,
        spec: Dict[str, Any],
        items: List[Dict[str, Any]],
        created_by_id: Optional[int],
    ) -> int:
        self._clear_generated_rows(
            db, blueprint, round_type
        )
        batch = uuid.uuid4().hex[:16]
        created = 0
        for item in items:
            topic_name = str(item.get("topic") or "").strip()
            topic = (
                db.query(AptitudeTopic)
                .filter(AptitudeTopic.name == topic_name)
                .first()
            )
            if topic is None:
                topic = AptitudeTopic(name=topic_name)
                db.add(topic)
                db.flush()
            question = AptitudeQuestion(
                question_text=str(item.get("question_text") or ""),
                option_a=str(item.get("option_a") or ""),
                option_b=str(item.get("option_b") or ""),
                option_c=str(item.get("option_c") or ""),
                option_d=str(item.get("option_d") or ""),
                correct_option=str(item.get("correct_option") or "").upper(),
                difficulty=str(item.get("difficulty") or "").casefold(),
                topic_id=topic.id,
                is_active=True,
                created_by=created_by_id,
                source=SOURCE_LLM,
                source_batch=batch,
                company_name=blueprint.company_name,
                target_role=blueprint.target_role,
                blueprint_id=blueprint.id,
                blueprint_version=blueprint.version,
            )
            db.add(question)
            created += 1
        db.flush()
        return created

    def _persist_coding_rows(
        self,
        db: Session,
        blueprint: Any,
        round_type: str,
        spec: Dict[str, Any],
        items: List[Dict[str, Any]],
        created_by_id: Optional[int],
    ) -> int:
        self._clear_generated_rows(db, blueprint, round_type)
        batch = uuid.uuid4().hex[:16]
        created = 0
        for item in items:
            test_cases = item.get("test_cases") or []
            supplied_tags = item.get("tags")
            if isinstance(supplied_tags, list):
                # Explicit LLM tags (list, not a JSON string). Empty list is
                # allowed by the model. Each entry is normalized to a string.
                tags = [str(tag).strip() for tag in supplied_tags if str(tag).strip()]
            else:
                # No tags supplied: default to the validated blueprint topic.
                tags = [str(item.get("topic") or "").strip()]
            problem = CodingProblem(
                title=str(item.get("title") or ""),
                description=str(item.get("description") or ""),
                difficulty=str(item.get("difficulty") or "").casefold(),
                input_format=str(item.get("input_format") or ""),
                output_format=str(item.get("output_format") or ""),
                constraints=str(item.get("constraints") or ""),
                tags=tags,
                created_by=created_by_id,
                source=SOURCE_LLM,
                source_batch=batch,
                company_name=blueprint.company_name,
                target_role=blueprint.target_role,
                blueprint_id=blueprint.id,
                blueprint_version=blueprint.version,
            )
            db.add(problem)
            db.flush()
            for case_idx, case in enumerate(test_cases, start=1):
                db.add(
                    CodingTestCase(
                        problem_id=problem.id,
                        input_data=str(case.get("input_data") or ""),
                        expected_output=str(case.get("expected_output") or ""),
                        is_hidden=bool(case.get("is_hidden")),
                        case_order=case_idx,
                    )
                )
            created += 1
        db.flush()
        return created

    def _persist_interview_content(
        self,
        db: Session,
        blueprint: Any,
        round_type: str,
        spec: Dict[str, Any],
        items: List[Dict[str, Any]],
    ) -> int:
        content: List[Dict[str, Any]] = []
        for item in items:
            question_text = str(item.get("question") or "")
            question_id = hashlib.md5(question_text.encode("utf-8")).hexdigest()[:12]
            content.append(
                {
                    "id": question_id,
                    "question": question_text,
                    "difficulty": str(item.get("difficulty") or "").upper(),
                    "topic": str(item.get("topic") or ""),
                    "phase": spec["phase"],
                    "expected_answer": str(item.get("expected_answer") or ""),
                    "evaluation_criteria": str(item.get("evaluation_criteria") or ""),
                    "role": blueprint.target_role,
                    "blueprint_pool": True,
                }
            )
        registry = (
            db.query(GeneratedQuestionPool)
            .filter(
                GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.blueprint_version == blueprint.version,
                GeneratedQuestionPool.round_type == round_type,
            )
            .first()
        )
        if registry is None:
            raise ValueError(f"registry row missing for {round_type}")
        registry.content = content
        db.flush()
        return len(content)

    def _clear_generated_rows(
        self, db: Session, blueprint: Any, round_type: str
    ) -> None:
        """Delete previously generated rows for this exact blueprint+version+round.

        Rows already referenced by candidate assignments (or any FK) raise an
        integrity error, which is caught upstream and reported as failed — this
        prevents silently replacing pool content a published drive already uses.
        """
        if round_type == "aptitude":
            rows = (
                db.query(AptitudeQuestion)
                .filter(
                    AptitudeQuestion.blueprint_id == blueprint.id,
                    AptitudeQuestion.blueprint_version == blueprint.version,
                    AptitudeQuestion.source == SOURCE_LLM,
                )
                .all()
            )
            for row in rows:
                db.delete(row)
        elif round_type == "coding":
            rows = (
                db.query(CodingProblem)
                .filter(
                    CodingProblem.blueprint_id == blueprint.id,
                    CodingProblem.blueprint_version == blueprint.version,
                    CodingProblem.source == SOURCE_LLM,
                )
                .all()
            )
            for row in rows:
                db.delete(row)
        db.flush()

    # ── Publish gate (pool readiness) ────────────────────────────────

    def publish_blocking_errors(
        self, db: Session, drive: Any
    ) -> List[str]:
        """Return errors blocking a drive from publishing.

        Applies to every blueprint-backed drive regardless of provenance:

        * An enabled interview round has no seeded bank, so it always requires a
          complete pre-generated pool for the pinned blueprint version.
        * An enabled aptitude/coding round keeps the seeded-bank escape hatch:
          when the blueprint configures the round and the seeded bank cannot
          satisfy it, a complete pre-generated pool is required. A round the
          blueprint does not configure carries no requirement and is skipped.
          Rounds the seeded bank CAN satisfy keep the historical behavior.

        Legacy / blueprintless drives (``blueprint_id`` is ``None``) are never
        gated: their publish path is unchanged and backward compatible.
        """
        if drive.blueprint_id is None:
            return []
        try:
            snapshot = get_drive_blueprint_snapshot(db, drive)
        except HTTPException:
            return []
        if not snapshot:
            return []

        enabled = [
            round_type
            for round_type, enabled in (drive.selected_rounds or {}).items()
            if enabled
        ]
        errors: List[str] = []
        for round_type in enabled:
            if round_type not in GENERATED_POOL_ROUNDS:
                continue
            round_config = get_blueprint_round_config(snapshot, round_type)
            has_pool = (
                self.complete_pool_for_round(
                    db,
                    snapshot.get("blueprint_id"),
                    snapshot.get("blueprint_version"),
                    round_type,
                )
                is not None
            )
            if round_type in ("technical_interview", "hr_interview"):
                if not has_pool:
                    errors.append(
                        f"A validated {round_type} question pool must be generated for this "
                        "blueprint before publishing an interview round."
                    )
            elif not has_pool:
                if round_config is None:
                    continue
                if not self._seeded_round_feasible(
                    db, round_type, round_config, snapshot
                ):
                    errors.append(
                        f"The approved {round_type} topics cannot be satisfied by the seeded "
                        "question bank; generate and validate a question pool before publishing."
                    )
        return errors

    def _seeded_round_feasible(
        self,
        db: Session,
        round_type: str,
        round_config: Optional[Dict[str, Any]],
        snapshot: Dict[str, Any],
    ) -> bool:
        """True when the seeded bank can already satisfy the round schedule."""
        try:
            if round_type == "aptitude":
                from app.modules.aptitude.routers.aptitude_router import (
                    _select_blueprint_aptitude_questions,
                )

                seeded_ids = [
                    row[0]
                    for row in db.query(AptitudeQuestion.id)
                    .filter(
                        AptitudeQuestion.is_active.is_(True),
                        or_(
                            AptitudeQuestion.source.is_(None),
                            AptitudeQuestion.source != SOURCE_LLM,
                        ),
                    )
                    .order_by(AptitudeQuestion.id)
                    .all()
                ]
                _select_blueprint_aptitude_questions(
                    db, round_config, question_ids=seeded_ids
                )
                return True
            if round_type == "coding":
                from app.modules.coding.services.coding_service import (
                    _select_blueprint_coding_problems,
                )

                seeded_ids = [
                    row[0]
                    for row in db.query(CodingProblem.id)
                    .filter(
                        or_(
                            CodingProblem.source.is_(None),
                            CodingProblem.source != SOURCE_LLM,
                        )
                    )
                    .order_by(CodingProblem.id)
                    .all()
                ]
                _select_blueprint_coding_problems(db, None, round_config, problem_ids=seeded_ids)
                return True
            return False
        except (ValueError, TypeError):
            return False


question_pool_generation_service = QuestionPoolGenerationService()
