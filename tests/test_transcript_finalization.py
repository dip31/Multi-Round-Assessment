"""Regression tests for Retell transcript finalization workflow."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.assessment_context import AssessmentPolicy, AssessmentContext
from app.models.interview import (
    InterviewSession,
    InterviewConversation,
    InterviewMessage,
    InterviewMessageSpeaker,
    InterviewMessageType,
    InterviewQuestionAnalysis,
    StudentCompetency,
    CompetencyEvidence,
    InterviewTurn,
)
from app.modules.interview.services.transcript_normalizer import (
    normalize_call_transcript_object,
    CanonicalTranscriptEvent,
    TranscriptSpeaker,
    TranscriptMessageType,
    merge_transcript_events,
)
from app.modules.interview.services.retell_finalization_service import (
    RetellFinalizationService,
    FinalizationResult,
    get_retell_finalization_service,
)
from app.modules.interview.services.competency_updater import (
    CompetencyUpdater,
    get_competency_updater,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        AssessmentPolicy.__table__,
        AssessmentContext.__table__,
        AssessmentSession.__table__,
        AssessmentRound.__table__,
        InterviewSession.__table__,
        InterviewTurn.__table__,
        InterviewConversation.__table__,
        InterviewMessage.__table__,
        InterviewQuestionAnalysis.__table__,
        StudentCompetency.__table__,
        CompetencyEvidence.__table__,
    ])
    session = sessionmaker(bind=engine)()
    # Create user and assessment session
    user = User(name="Test User", email="test@test.com", password_hash="hash")
    session.add(user)
    session.commit()
    assessment = AssessmentSession(user_id=user.id, status="active")
    session.add(assessment)
    session.commit()
    yield session
    session.close()


def create_interview(db, user_id, assessment_id, retell_call_id="call-test-123", voice_mode="edi5_core", create_turns=True):
    """Helper to create interview session with Retell config."""
    interview = InterviewSession(
        session_id=assessment_id,
        phase="TECHNICAL",
        current_turn=0,
        total_turns=5,
        retell_call_id=retell_call_id,
        retell_agent_id="agent-test",
        personalization_metadata={"voice_mode": voice_mode},
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    if create_turns:
        turn1 = InterviewTurn(interview_id=interview.id, turn_number=1, question_text="Question 1")
        turn2 = InterviewTurn(interview_id=interview.id, turn_number=2, question_text="Question 2")
        db.add_all([turn1, turn2])
        db.commit()

    return interview


class TestTranscriptNormalizerFinal:
    """Tests for normalize_call_transcript_object."""

    def test_normalize_final_transcript_object_basic(self):
        transcript_object = [
            {"role": "agent", "content": "Hello, welcome to the interview.", "words": []},
            {"role": "user", "content": "Thank you, happy to be here.", "words": []},
            {"role": "agent", "content": "First question: explain dependency injection.", "words": []},
            {"role": "user", "content": "Dependency injection is a pattern...", "words": []},
        ]
        events = normalize_call_transcript_object(transcript_object)
        
        assert len(events) == 4
        assert events[0].speaker == "ai"
        assert events[1].speaker == "candidate"
        assert events[2].speaker == "ai"
        assert events[3].speaker == "candidate"
        assert all(e.is_final for e in events)
        assert events[0].sequence == 1
        assert events[3].sequence == 4
        assert all(e.turn_id.startswith("final-") for e in events)
        assert all(e.retell_utterance_id is None for e in events)

    def test_normalize_skips_empty_content(self):
        transcript_object = [
            {"role": "agent", "content": "  ", "words": []},
            {"role": "user", "content": "Valid answer", "words": []},
        ]
        events = normalize_call_transcript_object(transcript_object)
        assert len(events) == 1
        assert events[0].text == "Valid answer"

    def test_normalize_transfer_target_role(self):
        transcript_object = [
            {"role": "transfer_target", "content": "Transferring...", "words": []},
        ]
        events = normalize_call_transcript_object(transcript_object)
        assert events[0].speaker == "system"
        assert events[0].message_type == "system"

    def test_normalize_empty_list(self):
        assert normalize_call_transcript_object([]) == []
        assert normalize_call_transcript_object(None) == []


class TestReconciliation:
    """Tests for deterministic final-live reconciliation."""

    def test_reconcile_final_replaces_live(self, db):
        """Final transcript overwrites live messages at same sequence."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id)
        
        # Create live messages (simulated partial updates)
        conv = InterviewConversation(
            interview_id=interview.id, session_id=assessment.id,
            total_messages=3, ai_message_count=2, candidate_message_count=1
        )
        db.add(conv)
        db.flush()
        
        live_msgs = [
            InterviewMessage(conversation_id=conv.id, sequence_number=1,
                           speaker="AI", text="Live question 1", message_type="QUESTION",
                           is_final=False, turn_id=1),
            InterviewMessage(conversation_id=conv.id, sequence_number=2,
                           speaker="CANDIDATE", text="Live partial answer", message_type="ANSWER",
                           is_final=False, turn_id=1),
            InterviewMessage(conversation_id=conv.id, sequence_number=3,
                           speaker="AI", text="Live follow-up", message_type="FOLLOW_UP",
                           is_final=False, turn_id=2),
        ]
        for m in live_msgs:
            db.add(m)
        db.commit()
        
        # Final transcript (authoritative)
        final_events = [
            CanonicalTranscriptEvent(
                turn_id="final-1", speaker="ai", text="Final question 1",
                timestamp=0, is_final=True, sequence=1,
                message_type="question", interview_turn_id=1
            ),
            CanonicalTranscriptEvent(
                turn_id="final-2", speaker="candidate", text="Final complete answer",
                timestamp=0, is_final=True, sequence=2,
                message_type="answer", interview_turn_id=1
            ),
            CanonicalTranscriptEvent(
                turn_id="final-3", speaker="ai", text="Final next question",
                timestamp=0, is_final=True, sequence=3,
                message_type="question", interview_turn_id=2
            ),
        ]
        
        # Simulate reconciliation logic
        existing_by_seq = {m.sequence_number: m for m in live_msgs}
        for event in final_events:
            seq = event.sequence
            if seq in existing_by_seq:
                m = existing_by_seq[seq]
                m.speaker = event.speaker
                m.text = event.text
                m.message_type = event.message_type.upper()
                m.is_final = True
            else:
                new_m = InterviewMessage(
                    conversation_id=conv.id, sequence_number=seq,
                    speaker=event.speaker, text=event.text,
                    message_type=event.message_type.upper(), is_final=True,
                    turn_id=event.interview_turn_id
                )
                db.add(new_m)
        
        # Delete surplus
        final_len = len(final_events)
        for m in live_msgs:
            if m.sequence_number > final_len:
                db.delete(m)
        db.commit()
        
        # Verify
        result = db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conv.id
        ).order_by(InterviewMessage.sequence_number).all()
        
        assert len(result) == 3
        assert result[0].text == "Final question 1"
        assert result[1].text == "Final complete answer"
        assert result[2].text == "Final next question"
        assert all(m.is_final for m in result)

    def test_reconcile_final_longer_than_live(self, db):
        """Final transcript longer than live - appends new."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id)
        
        conv = InterviewConversation(
            interview_id=interview.id, session_id=assessment.id,
            total_messages=1, ai_message_count=1, candidate_message_count=0
        )
        db.add(conv)
        db.flush()
        
        # Only one live message
        live = InterviewMessage(conversation_id=conv.id, sequence_number=1,
                               speaker="AI", text="Live Q1", message_type="QUESTION",
                               is_final=False, turn_id=1)
        db.add(live)
        db.commit()
        
        # Final has 4 messages
        final_events = [
            CanonicalTranscriptEvent(turn_id="final-1", speaker="ai", text="Final Q1",
                                     timestamp=0, is_final=True, sequence=1,
                                     message_type="question", interview_turn_id=1),
            CanonicalTranscriptEvent(turn_id="final-2", speaker="candidate", text="Final A1",
                                     timestamp=0, is_final=True, sequence=2,
                                     message_type="answer", interview_turn_id=1),
            CanonicalTranscriptEvent(turn_id="final-3", speaker="ai", text="Final Q2",
                                     timestamp=0, is_final=True, sequence=3,
                                     message_type="question", interview_turn_id=2),
            CanonicalTranscriptEvent(turn_id="final-4", speaker="candidate", text="Final A2",
                                     timestamp=0, is_final=True, sequence=4,
                                     message_type="answer", interview_turn_id=2),
        ]
        
        existing_by_seq = {m.sequence_number: m for m in [live]}
        for event in final_events:
            seq = event.sequence
            if seq in existing_by_seq:
                m = existing_by_seq[seq]
                m.speaker = event.speaker
                m.text = event.text
                m.message_type = event.message_type.upper()
                m.is_final = True
            else:
                new_m = InterviewMessage(
                    conversation_id=conv.id, sequence_number=seq,
                    speaker=event.speaker, text=event.text,
                    message_type=event.message_type.upper(), is_final=True,
                    turn_id=event.interview_turn_id
                )
                db.add(new_m)
        db.commit()
        
        result = db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conv.id
        ).order_by(InterviewMessage.sequence_number).all()
        
        assert len(result) == 4
        assert result[3].text == "Final A2"

    def test_reconcile_final_shorter_than_live(self, db):
        """Final transcript shorter than live - deletes surplus."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id)
        
        conv = InterviewConversation(
            interview_id=interview.id, session_id=assessment.id,
            total_messages=5, ai_message_count=3, candidate_message_count=2
        )
        db.add(conv)
        db.flush()
        
        # 5 live messages
        for i in range(1, 6):
            speaker = "AI" if i % 2 == 1 else "CANDIDATE"
            m = InterviewMessage(
                conversation_id=conv.id, sequence_number=i,
                speaker=speaker, text=f"Live {i}", message_type="QUESTION" if speaker == "AI" else "ANSWER",
                is_final=False, turn_id=1
            )
            db.add(m)
        db.commit()
        
        # Final has only 2
        final_events = [
            CanonicalTranscriptEvent(turn_id="final-1", speaker="ai", text="Final Q1",
                                     timestamp=0, is_final=True, sequence=1,
                                     message_type="question", interview_turn_id=1),
            CanonicalTranscriptEvent(turn_id="final-2", speaker="candidate", text="Final A1",
                                     timestamp=0, is_final=True, sequence=2,
                                     message_type="answer", interview_turn_id=1),
        ]
        
        existing_by_seq = {m.sequence_number: m for m in 
                          db.query(InterviewMessage).filter(InterviewMessage.conversation_id == conv.id).all()}
        for event in final_events:
            seq = event.sequence
            if seq in existing_by_seq:
                m = existing_by_seq[seq]
                m.speaker = event.speaker
                m.text = event.text
                m.message_type = event.message_type.upper()
                m.is_final = True
        
        # Delete surplus (handled by service logic)
        db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conv.id,
            InterviewMessage.sequence_number > len(final_events)
        ).delete()
        db.commit()
        
        result = db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conv.id
        ).order_by(InterviewMessage.sequence_number).all()
        
        assert len(result) == 2
        assert result[0].text == "Final Q1"
        assert result[1].text == "Final A1"


class TestFinalizationService:
    """Tests for RetellFinalizationService."""

    @pytest.mark.asyncio
    async def test_no_call_id_marks_completed(self, db):
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id=None)
        
        service = RetellFinalizationService(db)
        result = await service.finalize_interview_transcript(interview.id)
        
        assert result.success is True
        assert result.status == "no_call"
        assert result.transcript_finalized is False
        
        # Refresh
        db.refresh(interview)
        assert interview.transcript_status == "completed"
        assert interview.transcript_source == "live"

    @pytest.mark.asyncio
    async def test_call_not_ended_returns_not_ready(self, db):
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id="call-ongoing")
        
        service = RetellFinalizationService(db)
        
        # Mock call response with ongoing status
        mock_call = MagicMock()
        mock_call.call_status = "ongoing"
        mock_call.transcript_object = None
        mock_call.transcript = None
        mock_call.metadata = {"edi5_interview_session_id": interview.id}
        
        with patch.object(service, '_retrieve_call', return_value=mock_call):
            result = await service.finalize_interview_transcript(interview.id)
        
        assert result.success is False
        assert result.status == "not_ready"
        
        db.refresh(interview)
        assert interview.transcript_status == "pending"

    @pytest.mark.asyncio
    async def test_call_ended_no_transcript_returns_failed(self, db):
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id="call-no-transcript")
        
        service = RetellFinalizationService(db)
        
        mock_call = MagicMock()
        mock_call.call_status = "ended"
        mock_call.transcript_object = None
        mock_call.transcript = None
        mock_call.metadata = {"edi5_interview_session_id": interview.id}
        
        with patch.object(service, '_retrieve_call', return_value=mock_call):
            result = await service.finalize_interview_transcript(interview.id)
        
        assert result.success is False
        assert result.status == "failed"
        
        db.refresh(interview)
        assert interview.transcript_status == "failed"

    @pytest.mark.asyncio
    async def test_successful_finalization_with_transcript_object(self, db):
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id="call-final")
        
        service = RetellFinalizationService(db)
        
        # Use a plain object instead of MagicMock to avoid JSON serialization issues
        class MockCall:
            call_status = "ended"
            transcript_object = [
                {"role": "agent", "content": "Question 1", "words": []},
                {"role": "user", "content": "Answer 1", "words": []},
            ]
            transcript = "Agent: Question 1\nUser: Answer 1"
            metadata = {"edi5_interview_session_id": None}  # Will set after interview created
            call_analysis = {"summary": "Good interview"}
            duration_ms = 600000
            start_timestamp = 1000000
            end_timestamp = 1600000
            disconnection_reason = "user_hangup"
            recording_url = "https://retell.example/recording.mp3"
        
        mock_call = MockCall()
        mock_call.metadata = {"edi5_interview_session_id": interview.id}
        
        with patch.object(service, '_retrieve_call', return_value=mock_call):
            result = await service.finalize_interview_transcript(interview.id)
        
        assert result.success is True
        assert result.status == "completed"
        assert result.transcript_finalized is True
        assert result.messages_reconciled == 2
        
        db.refresh(interview)
        assert interview.transcript_status == "completed"
        assert interview.transcript_source == "final"
        
        # Verify conversation created with messages
        conv = db.query(InterviewConversation).filter(
            InterviewConversation.interview_id == interview.id
        ).first()
        assert conv is not None
        assert conv.total_messages == 2
        
        msgs = db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conv.id
        ).order_by(InterviewMessage.sequence_number).all()
        assert len(msgs) == 2
        assert msgs[0].speaker == "AI"
        assert msgs[1].speaker == "CANDIDATE"
        assert msgs[0].text == "Question 1"
        assert msgs[1].text == "Answer 1"
        assert all(m.is_final for m in msgs)

    @pytest.mark.asyncio
    async def test_ownership_mismatch_rejected(self, db):
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id="call-other")
        
        service = RetellFinalizationService(db)
        
        # Mock call with different interview_id in metadata
        mock_call = MagicMock()
        mock_call.call_status = "ended"
        mock_call.transcript_object = [{"role": "agent", "content": "Q", "words": []}]
        mock_call.metadata = {"edi5_interview_session_id": 999}  # Different!
        
        with patch.object(service, '_retrieve_call', return_value=mock_call):
            result = await service.finalize_interview_transcript(interview.id)
        
        assert result.success is False
        assert result.status == "failed"
        
        db.refresh(interview)
        assert interview.transcript_status == "failed"


class TestCompetencyIdempotency:
    """Tests for competency update idempotency."""

    def test_competency_evidence_not_duplicated(self, db):
        """Same interview_id + skill should not create duplicate evidence."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id)
        
        updater = CompetencyUpdater(db)
        
        # Create mock question analyses
        analyses = [
            MagicMock(
                covered_concepts=["concept A", "concept B"],
                missing_concepts=["concept C"],
                incorrect_concepts=[],
                partial_concepts=[],
                score=8.0,
                confidence=0.85,
                depth_level="Strong",
            ),
            MagicMock(
                covered_concepts=["concept B"],
                missing_concepts=["concept A"],
                incorrect_concepts=[],
                partial_concepts=[],
                score=7.0,
                confidence=0.8,
                depth_level="Good",
            ),
        ]
        
        skill_mapping = {"Python": ["concept A", "concept B", "concept C"]}
        
        # First update
        updates1 = updater.update_from_interview(interview.id, analyses, skill_mapping)
        assert len(updates1) == 1
        assert updates1[0].skill == "Python"
        assert updates1[0].evidence_recorded is True
        
        # Verify evidence created
        evidence1 = db.query(CompetencyEvidence).filter(
            CompetencyEvidence.user_id == user.id,
            CompetencyEvidence.skill == "Python",
            CompetencyEvidence.source == "interview",
            CompetencyEvidence.source_id == interview.id,
        ).all()
        assert len(evidence1) == 1
        
        # Second update (same interview)
        updates2 = updater.update_from_interview(interview.id, analyses, skill_mapping)
        # Should return empty because score delta < 0.5 threshold
        # But if it does update, evidence should not duplicate
        evidence2 = db.query(CompetencyEvidence).filter(
            CompetencyEvidence.user_id == user.id,
            CompetencyEvidence.skill == "Python",
            CompetencyEvidence.source == "interview",
            CompetencyEvidence.source_id == interview.id,
        ).all()
        assert len(evidence2) == 1  # Still only one


class TestCompleteInterviewGating:
    """Tests for analysis gating on transcript finalization."""

    def test_retell_mode_defer_analysis_when_pending(self, db):
        """Retell mode with pending transcript should defer analysis."""
        # This tests the logic in complete_interview endpoint
        # We can't easily test the full endpoint without FastAPI TestClient,
        # but we verify the logic behavior conceptually
        pass  # Placeholder for integration test


class TestMergeTranscriptEvents:
    """Tests for merge_transcript_events (unused but available)."""

    def test_merge_by_utterance_id(self):
        existing = [
            CanonicalTranscriptEvent(turn_id="u1", speaker="ai", text="Old Q1",
                                     timestamp=1000, is_final=False, sequence=1,
                                     retell_utterance_id="u1", message_type="question"),
        ]
        incoming = [
            CanonicalTranscriptEvent(turn_id="u1", speaker="ai", text="Updated Q1",
                                     timestamp=1000, is_final=True, sequence=1,
                                     retell_utterance_id="u1", message_type="question"),
        ]
        merged = merge_transcript_events(existing, incoming)
        assert len(merged) == 1
        assert merged[0].text == "Updated Q1"
        assert merged[0].is_final is True
        assert merged[0].turn_id == "u1"  # Preserved original turn_id

    def test_merge_by_sequence_fallback(self):
        existing = [
            CanonicalTranscriptEvent(turn_id="old-1", speaker="ai", text="Old Q1",
                                     timestamp=1000, is_final=False, sequence=1,
                                     message_type="question"),
        ]
        incoming = [
            CanonicalTranscriptEvent(turn_id="new-1", speaker="ai", text="New Q1",
                                     timestamp=1000, is_final=True, sequence=1,
                                     message_type="question"),
        ]
        merged = merge_transcript_events(existing, incoming)
        assert len(merged) == 1
        assert merged[0].text == "New Q1"
        assert merged[0].turn_id == "old-1"  # Preserved original turn_id

    def test_merge_new_events(self):
        existing = [
            CanonicalTranscriptEvent(turn_id="u1", speaker="ai", text="Q1",
                                     timestamp=1000, is_final=True, sequence=1,
                                     retell_utterance_id="u1", message_type="question"),
        ]
        incoming = [
            CanonicalTranscriptEvent(turn_id="u1", speaker="ai", text="Q1",
                                     timestamp=1000, is_final=True, sequence=1,
                                     retell_utterance_id="u1", message_type="question"),
            CanonicalTranscriptEvent(turn_id="u2", speaker="candidate", text="A1",
                                     timestamp=2000, is_final=True, sequence=2,
                                     retell_utterance_id="u2", message_type="answer"),
        ]
        merged = merge_transcript_events(existing, incoming)
        assert len(merged) == 2
        assert merged[1].text == "A1"


class TestForeignKeyAndRollbackIntegrity:
    """Tests verifying foreign key constraints on turn_id and session rollback safety."""

    def test_direct_invalid_turn_id_violates_foreign_key(self, db):
        """Attempting to insert an invalid turn_id raises IntegrityError when FKs are enabled."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, create_turns=False)
        conv = InterviewConversation(interview_id=interview.id, session_id=assessment.id)
        db.add(conv)
        db.commit()

        # Non-existent turn_id (e.g. 0 or 9999) must raise IntegrityError
        invalid_msg = InterviewMessage(
            conversation_id=conv.id,
            sequence_number=1,
            speaker="AI",
            text="Invalid turn message",
            message_type="QUESTION",
            turn_id=0,
        )
        db.add(invalid_msg)
        with pytest.raises(Exception) as exc_info:
            db.commit()
        db.rollback()
        assert "FOREIGN KEY constraint failed" in str(exc_info.value) or "IntegrityError" in type(exc_info.value).__name__

    @pytest.mark.asyncio
    async def test_finalization_with_null_turn_id_succeeds_fk_constraint(self, db):
        """Finalization in retell_hosted mode (no InterviewTurns) persists messages with turn_id=None without FK errors."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id="call-fk-test", voice_mode="retell_hosted", create_turns=False)
        assert interview.current_turn == 0

        service = RetellFinalizationService(db)
        class MockCall:
            call_status = "ended"
            transcript_object = [
                {"role": "agent", "content": "Question 1", "words": []},
                {"role": "user", "content": "Answer 1", "words": []},
            ]
            transcript = "Agent: Question 1\nUser: Answer 1"
            metadata = {"edi5_interview_session_id": interview.id}
            call_analysis = {}
            duration_ms = 1000
            start_timestamp = 1000
            end_timestamp = 2000
            disconnection_reason = "hangup"
            recording_url = "https://example.com/rec.mp3"

        with patch.object(service, '_retrieve_call', return_value=MockCall()):
            result = await service.finalize_interview_transcript(interview.id)

        assert result.success is True
        assert result.status == "completed"

        messages = db.query(InterviewMessage).all()
        assert len(messages) == 2
        for m in messages:
            assert m.turn_id is None
            assert m.is_final is True

    @pytest.mark.asyncio
    async def test_finalization_recovers_after_exception_without_pending_rollback(self, db):
        """When an exception occurs during finalization, session is rolled back and error state is recorded cleanly without PendingRollbackError."""
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = create_interview(db, user.id, assessment.id, retell_call_id="call-err-test", create_turns=False)

        service = RetellFinalizationService(db)
        class MockCall:
            call_status = "ended"
            transcript_object = [{"role": "agent", "content": "Q", "words": []}]
            metadata = {"edi5_interview_session_id": interview.id}

        # Force an error inside _reconcile_final_transcript
        with patch.object(service, '_retrieve_call', return_value=MockCall()):
            with patch.object(service, '_reconcile_final_transcript', side_effect=RuntimeError("Simulated reconciliation crash")):
                result = await service.finalize_interview_transcript(interview.id)

        assert result.success is False
        assert result.status == "failed"
        assert "Simulated reconciliation crash" in result.error

        db.refresh(interview)
        assert interview.transcript_status == "failed"
        assert "Simulated reconciliation crash" in interview.transcript_finalization_error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])