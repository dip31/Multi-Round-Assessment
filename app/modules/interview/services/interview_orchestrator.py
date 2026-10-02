"""
Interview turn orchestrator.

Owns the per-turn interview pipeline that previously lived inline in
``interview_router.submit_response``. The route is now a thin adapter: it
resolves the session, hands off here, and returns what it gets back.

The pipeline, in order — the order is part of the contract:

    0. Load session state and the question under discussion
    1. Silence handling (may short-circuit with RETRY)
    2. Understand the answer (classification)
    3. Behavioural scoring
    4. Final scoring
    5. Follow-up decision, then turn advancement
    6. Pre-fetch the next question
    7. Generate what the interviewer says
    8. RL reward update
    9. Persist session state and the turn row
   10. Assemble the response

Two things are deliberately load-bearing and easy to break:

* ``rl_state`` is read into a plain dict, mutated, and reassigned wholesale
  onto the session. SQLAlchemy does not track in-place mutation of a JSONB
  column, so mutating ``interview.rl_state`` directly would silently fail to
  persist. Always go through ``self._state`` and let ``_persist`` reassign.
* The completion summary is computed *after* the current turn has been
  committed, so the turn being processed is included in the averages.

SCOPE BOUNDARY: this module owns interview *intelligence* — what to ask, when
to follow up, how to score. It does not own interviewer *presentation*. The
selected interviewer may change wording, voice and name; it must never reach
the scoring weights, the follow-up policy, the difficulty choice or the RL
state. See ``config/interviewer_profiles.py``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.assessment import AssessmentRound
from app.models.interview import (
    ApprovedQuestionPool,
    InterviewSession,
    InterviewTurn,
)
from app.modules.interview.schemas.interview_schema import (
    InterviewSummaryInfo,
    NextQuestionInfo,
    ScoresInfo,
    SubmitResponseRequest,
    SubmitResponseResponse,
)
from app.modules.interview.config import interviewer_profiles
from app.modules.interview.services import answer_understanding, followup_policy, question_planner
from app.modules.interview.services.answer_understanding import AnswerUnderstanding
from app.modules.interview.services.interview_rl_engine import InterviewRLEngine

logger = logging.getLogger(__name__)


# ── Scoring constants ──────────────────────────────────────────────────────
# These are assessment criteria. Changing them changes every candidate's score
# and invalidates comparison against historical sessions. They are constants
# here purely to name what were magic numbers in the route — the values are
# unchanged and must not be tuned as part of interviewer or latency work.

BEHAVIOR_WEIGHT_EYE_CONTACT = 0.4
BEHAVIOR_WEIGHT_VOICE = 0.3
BEHAVIOR_WEIGHT_HEAD_STABILITY = 0.3

FINAL_WEIGHT_CONTENT = 0.5
FINAL_WEIGHT_INTENT = 0.3
FINAL_WEIGHT_BEHAVIOR = 0.2

INTENT_SCORES = {
    "POSITIVE": 1.0,
    "NEUTRAL": 0.6,
    "NEGATIVE": 0.3,
}
DEFAULT_INTENT_SCORE = 0.6

# Response-time thresholds (seconds) used as a proxy for vocal delivery: a
# candidate who spoke for longer produced more signal to assess.
VOICE_SCORE_THRESHOLD_FULL = 5
VOICE_SCORE_THRESHOLD_PARTIAL = 2

DEFAULT_BEHAVIOR_METRIC = 0.5

# Turns of dialogue retained for interviewer context (3 exchanges).
CONVERSATION_HISTORY_LIMIT = 6

RETRY_MESSAGE = "I didn't catch that. Could you please repeat your answer?"


class InterviewError(Exception):
    """A recoverable, client-facing interview error.

    Carries an HTTP status so the router can translate it without this module
    importing FastAPI — keeping the orchestrator testable without a web stack.
    """

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class InterviewOrchestrator:
    """Runs one interview turn end to end.

    Construct per request; instances hold mutable per-turn state and are not
    safe to share or reuse across turns.
    """

    def __init__(self, db: Session, groq_service: Any):
        """
        Args:
            db: Active SQLAlchemy session.
            groq_service: Provides ``classify_answer`` and
                ``generate_interviewer_response``. Injected so the pipeline can
                be exercised with a stub.
        """
        self.db = db
        self.groq = groq_service

        # Per-turn state, populated by handle_response.
        self._state: Dict[str, Any] = {}
        self._rl_engine = InterviewRLEngine()
        # Who the candidate thinks they are talking to. Affects wording only,
        # and is resolved from the session rather than the request so a client
        # cannot switch interviewer mid-interview.
        self._profile = interviewer_profiles.get_interviewer(None)

    # ── Public entry point ─────────────────────────────────────────────────

    def handle_response(
        self,
        interview: InterviewSession,
        req: SubmitResponseRequest,
    ) -> SubmitResponseResponse:
        """Process one submitted candidate answer.

        Args:
            interview: The live session, already loaded and authorised.
            req: The submitted transcript, timing and behavioural snapshot.

        Returns:
            The complete response for the frontend — what the interviewer says,
            the next question when there is one, scores, and a summary on
            completion.

        Raises:
            InterviewError: If the session has no question in flight.
        """
        # ── STEP 0: Load state ─────────────────────────────────────────────
        # Copy rather than alias: see the module docstring on JSONB mutation.
        self._state = dict(interview.rl_state or {})
        self._rl_engine = InterviewRLEngine()
        self._rl_engine.from_dict(self._state)

        # Read from the session column, NOT from rl_state — persona must stay
        # out of the Q-learning state so that identical answers score
        # identically whichever interviewer was chosen. NULL (every session that
        # predates interviewer selection) resolves to the default.
        self._profile = interviewer_profiles.get_interviewer(interview.interviewer_id)

        # The question always comes from persisted state, never from the request
        # body — otherwise a candidate could answer a question of their own
        # choosing and be scored against it.
        question = self._state.get("current_question_text", "")
        difficulty = self._state.get("current_question_difficulty", question_planner.DEFAULT_DIFFICULTY)

        if not question:
            raise InterviewError("No active question found")

        transcript = answer_understanding.normalize_transcript(req.transcript)

        # ── STEP 1: Silence handling ───────────────────────────────────────
        force_next = False

        if answer_understanding.is_silence(transcript):
            if self._state.get("silence_count", 0) == 0:
                return self._reprompt_for_silence(interview)
            # Already re-prompted once — stop waiting and score it as empty.
            understanding = answer_understanding.silent_answer()
            force_next = True
        else:
            # ── STEP 2: Understand the answer ──────────────────────────────
            understanding = answer_understanding.understand(
                self.groq,
                question=question,
                transcript=transcript,
                interview_type=self._state.get("interview_type", "technical"),
            )

        # ── STEP 3 & 4: Scoring ────────────────────────────────────────────
        snapshot = req.behavioral_snapshot.model_dump() if req.behavioral_snapshot else {}
        response_time_sec = req.response_time_sec or 0.0

        behavior_score = self._score_behavior(snapshot, response_time_sec)
        intent_score = INTENT_SCORES.get(understanding.intent, DEFAULT_INTENT_SCORE)
        final_score = self._score_final(understanding.content_score, intent_score, behavior_score)

        # ── STEP 5: Decision, then turn advancement ────────────────────────
        decision = followup_policy.decide(
            force_next=force_next,
            quality=understanding.quality,
            intent=understanding.intent,
            followup_count=self._state.get("followup_count", 0),
            irrelevant_count=self._state.get("irrelevant_count", 0),
            negative_count=self._state.get("negative_count", 0),
        )
        followup_policy.apply_increments(self._state, decision)

        action = decision.action
        logger.info(
            "Interview %s turn %s: quality=%s intent=%s score=%.2f -> %s (%s)",
            interview.id, interview.current_turn, understanding.quality,
            understanding.intent, final_score, action, decision.reason,
        )

        if action == "NEXT":
            action = self._advance_turn(interview)

        # ── STEP 6: Pre-fetch the next question ────────────────────────────
        next_question_obj = None
        if action == "NEXT":
            next_question_obj = self._plan_next_question(interview, final_score)

        # ── STEP 7: What the interviewer says ──────────────────────────────
        message = self._generate_message(
            question=question,
            transcript=transcript,
            understanding=understanding,
            action=action,
            followup_type=decision.followup_type,
            next_question_obj=next_question_obj,
        )

        # ── STEP 8: RL reward update ───────────────────────────────────────
        reward = self._update_rl(
            interview=interview,
            action=action,
            understanding=understanding,
            difficulty=difficulty,
            final_score=final_score,
        )

        # ── STEP 9: Persist ────────────────────────────────────────────────
        self._record_exchange(question, transcript)

        if action == "NEXT" and next_question_obj:
            self._promote_next_question(next_question_obj)

        self._apply_phase_transition(interview, action)
        self._persist(interview)

        turn = self._build_turn_row(
            interview=interview,
            question=question,
            difficulty=difficulty,
            transcript=transcript,
            response_time_sec=response_time_sec,
            understanding=understanding,
            final_score=final_score,
            snapshot=snapshot,
            reward=reward,
            action=action,
        )
        self.db.add(turn)
        self.db.commit()

        # ── STEP 10: Assemble the response ─────────────────────────────────
        summary = None
        if action == "COMPLETE":
            # Deliberately after the commit above so this turn is counted.
            summary = self._finalize_interview(interview)

        return SubmitResponseResponse(
            action=action,
            message=message,
            is_complete=(action == "COMPLETE"),
            followup_type=decision.followup_type,
            next_question=self._build_next_question_info(interview, action, next_question_obj),
            scores=ScoresInfo(
                content_score=understanding.content_score,
                intent_score=intent_score,
                behavior_score=behavior_score,
                final_score=final_score,
            ),
            interview_summary=summary,
        )

    # ── Step 1 helper ──────────────────────────────────────────────────────

    def _reprompt_for_silence(self, interview: InterviewSession) -> SubmitResponseResponse:
        """Ask the candidate to repeat themselves, without scoring the turn.

        No LLM call, no turn row, no turn advancement — a missed answer costs
        the candidate nothing the first time.
        """
        self._state["silence_count"] = 1
        interview.rl_state = self._state
        self.db.commit()

        logger.info("Interview %s: first silence, re-prompting candidate", interview.id)

        return SubmitResponseResponse(
            action="RETRY",
            message=RETRY_MESSAGE,
            is_complete=False,
            scores=None,
            next_question=None,
        )

    # ── Step 3 & 4 helpers ─────────────────────────────────────────────────

    def _score_behavior(self, snapshot: Dict[str, Any], response_time_sec: float) -> float:
        """Blend eye contact, vocal delivery and head stability into one score."""
        eye_contact = snapshot.get("eye_contact_pct", DEFAULT_BEHAVIOR_METRIC)
        head_stability = snapshot.get("head_stability", DEFAULT_BEHAVIOR_METRIC)
        voice_score = self._score_voice(response_time_sec)

        return (
            BEHAVIOR_WEIGHT_EYE_CONTACT * eye_contact
            + BEHAVIOR_WEIGHT_VOICE * voice_score
            + BEHAVIOR_WEIGHT_HEAD_STABILITY * head_stability
        )

    @staticmethod
    def _score_voice(response_time_sec: float) -> float:
        """Score vocal delivery from how long the candidate spoke."""
        if response_time_sec > VOICE_SCORE_THRESHOLD_FULL:
            return 1.0
        if response_time_sec > VOICE_SCORE_THRESHOLD_PARTIAL:
            return 0.5
        return 0.0

    @staticmethod
    def _score_final(content_score: float, intent_score: float, behavior_score: float) -> float:
        """Weighted blend of content, intent and behaviour."""
        return (
            FINAL_WEIGHT_CONTENT * content_score
            + FINAL_WEIGHT_INTENT * intent_score
            + FINAL_WEIGHT_BEHAVIOR * behavior_score
        )

    # ── Step 5 helper ──────────────────────────────────────────────────────

    def _advance_turn(self, interview: InterviewSession) -> str:
        """Move to the next turn, or promote the decision to COMPLETE.

        Returns the resolved action. Per-question counters are reset only when
        the interview actually continues — a completed interview keeps its final
        counters for the report.
        """
        if interview.current_turn + 1 >= interview.total_turns:
            return "COMPLETE"

        interview.current_turn += 1
        followup_policy.reset_turn_counters(self._state)
        return "NEXT"

    # ── Step 6 helper ──────────────────────────────────────────────────────

    def _plan_next_question(
        self,
        interview: InterviewSession,
        final_score: float,
    ) -> Optional[Dict[str, Any]]:
        """Choose the next question from the approved pool."""
        approved_pool = (
            self.db.query(ApprovedQuestionPool)
            .filter(
                ApprovedQuestionPool.session_id == interview.session_id,
                ApprovedQuestionPool.admin_approved == True,  # noqa: E712 - SQL comparison
            )
            .first()
        )

        if not approved_pool:
            logger.warning(
                "Interview %s: no approved pool found while planning next question",
                interview.id,
            )
            return None

        next_difficulty = self._rl_engine.select_difficulty(
            {"last_score": final_score, "turn": interview.current_turn}
        )

        return question_planner.select_question(
            approved_pool.question_pool,
            asked_question_ids=self._state.get("asked_question_ids", []),
            phase=question_planner.phase_for_turn(interview.current_turn, interview.phase),
            difficulty=next_difficulty,
            # Mid-interview: prefer a repeat over leaving the candidate in
            # silence. See question_planner's module docstring.
            reuse_exhausted_pool=True,
        )

    # ── Step 7 helper ──────────────────────────────────────────────────────

    def _generate_message(
        self,
        *,
        question: str,
        transcript: str,
        understanding: AnswerUnderstanding,
        action: str,
        followup_type: Optional[str],
        next_question_obj: Optional[Dict[str, Any]],
    ) -> str:
        """Produce the interviewer's spoken line for this turn."""
        return self.groq.generate_interviewer_response(
            question=question,
            answer=transcript,
            quality=understanding.quality,
            intent=understanding.intent,
            missing_part=understanding.missing_part,
            action=action,
            followup_type=followup_type,
            next_question=next_question_obj["question"] if next_question_obj else None,
            conversation_history=self._state.get("conversation_history", []),
            # Persona arrives as rendered text. Note what is NOT passed: the
            # decision and the next question above were already settled by the
            # policy and planner, so the persona can only change how they are
            # voiced, never what they are.
            interviewer_identity=self._profile.system_identity(),
            interviewer_style=self._profile.style_block(),
            interviewer_transition_hint=self._profile.persona.transition_hint,
        )

    # ── Step 8 helper ──────────────────────────────────────────────────────

    def _update_rl(
        self,
        *,
        interview: InterviewSession,
        action: str,
        understanding: AnswerUnderstanding,
        difficulty: str,
        final_score: float,
    ) -> Optional[float]:
        """Apply the Q-learning update for a completed main question.

        Only main questions carry a reward — follow-ups are part of the same
        question and would otherwise double-count one difficulty choice.

        Returns the reward, or ``None`` when no update was made.
        """
        if action not in ("NEXT", "COMPLETE"):
            return None

        reward = self._rl_engine.compute_reward(
            final_score=final_score,
            quality=understanding.quality,
            intent=understanding.intent,
            difficulty=difficulty,
            content_score=understanding.content_score,
        )

        # The state the difficulty was chosen *from*. On NEXT the turn counter
        # has already advanced, so step back one to attribute the reward to the
        # turn that actually earned it.
        previous_turn = interview.current_turn - 1 if action == "NEXT" else interview.current_turn
        current_state = {
            "last_score": self._state.get("last_score", 0.5),
            "turn": previous_turn,
        }
        next_state = {
            "last_score": final_score,
            "turn": interview.current_turn,
        }

        self._rl_engine.update(current_state, difficulty, reward, next_state)
        self._state["last_score"] = final_score

        return reward

    # ── Step 9 helpers ─────────────────────────────────────────────────────

    def _record_exchange(self, question: str, transcript: str) -> None:
        """Append this exchange to the rolling conversation history."""
        history: List[Dict[str, str]] = self._state.get("conversation_history", [])
        history.append({"role": "interviewer", "content": question})
        history.append({"role": "candidate", "content": transcript})
        self._state["conversation_history"] = history[-CONVERSATION_HISTORY_LIMIT:]

    def _promote_next_question(self, next_question_obj: Dict[str, Any]) -> None:
        """Make the pre-fetched question the one in flight.

        This is the only place the current question is advanced, so a failure
        anywhere earlier in the turn leaves the candidate on the same question
        rather than silently skipping one.
        """
        self._state["current_question_text"] = next_question_obj["question"]
        self._state["current_question_difficulty"] = next_question_obj.get(
            "difficulty", question_planner.DEFAULT_DIFFICULTY
        )
        self._state["current_question_id"] = next_question_obj.get("id")

        asked = self._state.get("asked_question_ids", [])
        asked.append(next_question_obj.get("id"))
        self._state["asked_question_ids"] = asked

    @staticmethod
    def _apply_phase_transition(interview: InterviewSession, action: str) -> None:
        """Flip HR → TECHNICAL at the boundary, or to COMPLETE when finished.

        COMPLETE is applied last so it wins over the technical transition on a
        session that finishes exactly at the boundary turn.
        """
        if interview.current_turn == question_planner.TECHNICAL_PHASE_START_TURN:
            interview.phase = "TECHNICAL"

        if action == "COMPLETE":
            interview.phase = "COMPLETE"

    def _persist(self, interview: InterviewSession) -> None:
        """Write the mutated state back onto the session.

        The Q-table and exploration rate are merged in from the engine; every
        other key was mutated on ``self._state`` directly. Reassignment (rather
        than in-place mutation) is what makes SQLAlchemy flush the JSONB column.
        """
        rl_dict = self._rl_engine.to_dict()
        self._state["q_table"] = rl_dict["q_table"]
        self._state["epsilon"] = rl_dict["epsilon"]
        interview.rl_state = self._state

    def _build_turn_row(
        self,
        *,
        interview: InterviewSession,
        question: str,
        difficulty: str,
        transcript: str,
        response_time_sec: float,
        understanding: AnswerUnderstanding,
        final_score: float,
        snapshot: Dict[str, Any],
        reward: Optional[float],
        action: str,
    ) -> InterviewTurn:
        """Build the audit row for this turn."""
        is_followup = action == "FOLLOWUP"

        return InterviewTurn(
            interview_id=interview.id,
            turn_number=interview.current_turn,
            question_text=question,
            question_difficulty=difficulty,
            candidate_response=transcript,
            response_time_sec=response_time_sec,
            content_score=understanding.content_score,
            final_score=final_score,
            intent=understanding.intent,
            behavioral_snapshot=snapshot,
            rl_reward=reward,
            is_followup=is_followup,
            followup_number=self._state.get("followup_count", 0),
            parent_turn_id=self._find_parent_turn_id(interview) if is_followup else None,
        )

    def _find_parent_turn_id(self, interview: InterviewSession) -> Optional[int]:
        """Find the main turn a follow-up hangs off."""
        last_main_turn = (
            self.db.query(InterviewTurn)
            .filter(
                InterviewTurn.interview_id == interview.id,
                InterviewTurn.is_followup == False,  # noqa: E712 - SQL comparison
            )
            .order_by(InterviewTurn.id.desc())
            .first()
        )
        return last_main_turn.id if last_main_turn else None

    # ── Step 10 helpers ────────────────────────────────────────────────────

    @staticmethod
    def _build_next_question_info(
        interview: InterviewSession,
        action: str,
        next_question_obj: Optional[Dict[str, Any]],
    ) -> Optional[NextQuestionInfo]:
        """Describe the upcoming question for the frontend.

        Present only on NEXT — on FOLLOWUP the candidate stays on the current
        question, and on COMPLETE there is nothing left to ask.
        """
        if action != "NEXT" or not next_question_obj:
            return None

        return NextQuestionInfo(
            text=next_question_obj["question"],
            difficulty=next_question_obj.get("difficulty", question_planner.DEFAULT_DIFFICULTY),
            phase=interview.phase,
            turn_number=interview.current_turn,
        )

    def _finalize_interview(self, interview: InterviewSession) -> InterviewSummaryInfo:
        """Close out the interview and summarise it.

        Must be called after the final turn is committed so it is included in
        the averages. Also settles the linked assessment round and stops
        proctoring, since nothing else will.
        """
        main_turns = (
            self.db.query(InterviewTurn)
            .filter(
                InterviewTurn.interview_id == interview.id,
                InterviewTurn.is_followup == False,  # noqa: E712 - SQL comparison
            )
            .all()
        )
        total_followups = (
            self.db.query(InterviewTurn)
            .filter(
                InterviewTurn.interview_id == interview.id,
                InterviewTurn.is_followup == True,  # noqa: E712 - SQL comparison
            )
            .count()
        )

        main_scores = [t.final_score for t in main_turns if t.final_score is not None]
        avg_score = sum(main_scores) / max(len(main_scores), 1)
        followup_rate = total_followups / max(len(main_turns), 1) * 100

        interview.status = "COMPLETED"
        interview.completion_reason = "ALL_QUESTIONS_COMPLETED"
        interview.completed_at = datetime.now()

        self._settle_linked_round(interview, avg_score)
        self.db.commit()

        logger.info(
            "Interview %s complete: %d turns, avg %.2f, follow-up rate %.1f%%",
            interview.id, len(main_turns), avg_score, followup_rate,
        )

        return InterviewSummaryInfo(
            total_turns=len(main_turns),
            avg_final_score=round(avg_score, 2),
            followup_rate=round(followup_rate, 1),
        )

    def _settle_linked_round(self, interview: InterviewSession, avg_score: float) -> None:
        """Mark the parent assessment round complete and stop proctoring."""
        if not interview.round_id:
            return

        linked_round = (
            self.db.query(AssessmentRound)
            .filter(AssessmentRound.id == interview.round_id)
            .first()
        )

        if linked_round is None or linked_round.status != "active":
            return

        linked_round.status = "completed"
        linked_round.completed_at = interview.completed_at
        linked_round.score = round(avg_score, 2)

        # Imported here, as in the original route, to avoid a circular import
        # between the interview and proctoring modules at startup.
        from app.services.proctoring_service import stop_proctoring_session

        stop_proctoring_session(self.db, linked_round.session_id)
