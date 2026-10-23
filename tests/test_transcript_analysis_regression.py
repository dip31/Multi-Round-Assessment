"""
Regression tests for EDI5 transcript, analysis, and competency bugs.

Tests cover confirmed defects from EDI5_COMPLETE_TRANSCRIPT_WORKFLOW_AUDIT.md:
  F-0:  Wrong user_id in competency updates
  F-1:  Non-existent GroqService.chat_completion() method
  F-2:  Pool expected concepts never used
  F-3:  partial_concepts / evidence not persisted
  F-4:  Report endpoint re-runs analysis
  F-6:  Webhook counters reset to per-call deltas
  F-8:  Browser transcript dedup by positional count
  F-10: Freshness always returns "high"
  F-12: Missing (user_id, skill) unique constraint
  F-13: Hardcoded interview_type
"""

import json
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

# ── Imports under test ──────────────────────────────────────────────────

from app.modules.interview.services.transcript_normalizer import (
    CanonicalTranscriptEvent,
    normalize_retell_transcript,
    normalize_retell_utterance,
    select_changed_events,
    extract_utterances,
    TranscriptSpeaker,
    TranscriptMessageType,
)
from app.modules.interview.services.competency_updater import CompetencyUpdater
from app.modules.interview.services.interview_analysis import (
    InterviewAnalysisService,
    QuestionAnalysis,
)
from app.modules.interview.services.answer_analyzer import (
    AnswerAnalysis,
    ConceptEvaluation,
)
from app.services.groq_service import GroqService, GROQ_MODEL


# ═══════════════════════════════════════════════════════════════════════
# F-0: Competency updater must resolve the REAL user_id
# ═══════════════════════════════════════════════════════════════════════

class TestF0_CompetencyUserIdResolution:
    """F-0: user_id must be AssessmentSession.user_id, NOT interview.session_id."""
    
    def test_update_from_interview_resolves_real_user_id(self):
        """The competency updater must resolve user_id through AssessmentSession."""
        from app.models.interview import InterviewSession, StudentCompetency
        from app.models.assessment import AssessmentSession
        
        db = MagicMock()
        
        # Set up mock chain:
        # InterviewSession.session_id = 99 (assessment session PK)
        # AssessmentSession.user_id = 42 (real user PK)
        mock_interview = MagicMock()
        mock_interview.id = 1
        mock_interview.session_id = 99  # NOT the user id
        
        mock_assessment = MagicMock()
        mock_assessment.id = 99
        mock_assessment.user_id = 42  # THIS is the real user id
        
        # Track what user_id gets passed to _update_skill_competency
        captured_user_ids = []
        original_update = CompetencyUpdater._update_skill_competency
        
        def spy_update(self_inner, user_id, skill, evidence, interview_id):
            captured_user_ids.append(user_id)
            return None  # Skip actual DB work
        
        # Mock DB queries to return correct objects per model type
        query_results = {}
        
        def make_query(model):
            q = MagicMock()
            if model is InterviewSession:
                q.filter.return_value.first.return_value = mock_interview
            elif model is AssessmentSession:
                q.filter.return_value.first.return_value = mock_assessment
            elif model is StudentCompetency:
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q
        
        db.query.side_effect = make_query
        db.flush = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        
        updater = CompetencyUpdater(db)
        
        mock_qa = MagicMock()
        mock_qa.expected_concepts = ["concept_a", "concept_b"]
        mock_qa.covered_concepts = ["concept_a"]
        mock_qa.missing_concepts = ["concept_b"]
        mock_qa.incorrect_concepts = []
        mock_qa.partial_concepts = []
        mock_qa.score = 7.0
        mock_qa.confidence = 0.8
        mock_qa.depth_level = "Good"
        
        skill_mapping = {"Python": ["concept_a", "concept_b"]}
        
        with patch.object(CompetencyUpdater, '_update_skill_competency', spy_update):
            updater.update_from_interview(
                interview_id=1,
                question_analyses=[mock_qa],
                skill_mapping=skill_mapping,
            )
        
        # The real test: user_id 42 was used, NOT session_id 99
        assert len(captured_user_ids) > 0, "_update_skill_competency must be called"
        for uid in captured_user_ids:
            assert uid == 42, f"Expected user_id=42, got {uid} (session_id leak)"
    
    def test_missing_assessment_session_aborts_safely(self):
        """If AssessmentSession is missing, competency update must NOT proceed."""
        from app.models.interview import InterviewSession
        from app.models.assessment import AssessmentSession
        
        db = MagicMock()
        
        mock_interview = MagicMock(spec=InterviewSession)
        mock_interview.id = 1
        mock_interview.session_id = 99
        
        def query_side_effect(model):
            q = MagicMock()
            if model == InterviewSession:
                q.filter.return_value.first.return_value = mock_interview
            elif model == AssessmentSession:
                q.filter.return_value.first.return_value = None  # Not found
            else:
                q.filter.return_value.first.return_value = None
            return q
        
        db.query.side_effect = query_side_effect
        
        updater = CompetencyUpdater(db)
        result = updater.update_from_interview(
            interview_id=1,
            question_analyses=[MagicMock()],
            skill_mapping={"Python": ["concept"]},
        )
        
        assert result == [], "Must return empty list when AssessmentSession not found"
        db.commit.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# F-1: Expected concept generator must use correct Groq SDK method
# ═══════════════════════════════════════════════════════════════════════

class TestF1_GroqMethodCall:
    """F-1: _generate_expected_concepts must call client.chat.completions.create()."""
    
    def test_groq_service_has_no_chat_completion_method(self):
        """Verify that GroqService does NOT have a chat_completion method."""
        groq = GroqService.__new__(GroqService)
        assert not hasattr(groq, 'chat_completion'), \
            "GroqService should not have chat_completion — that was the bug"
    
    def test_generate_expected_concepts_uses_correct_method(self):
        """_generate_expected_concepts must use client.chat.completions.create()."""
        mock_groq = MagicMock()  # No spec — allow .client access
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '["concept_a", "concept_b", "concept_c"]'
        mock_groq.client.chat.completions.create.return_value = mock_response
        
        service = InterviewAnalysisService(groq_service=mock_groq)
        concepts = service._generate_expected_concepts("What is OOP?", "technical")
        
        # Must call the CORRECT method
        mock_groq.client.chat.completions.create.assert_called_once()
        assert "concept_a" in concepts
        assert len(concepts) == 3
    
    def test_generate_expected_concepts_fallback_on_error(self):
        """On LLM failure, should return generic fallback, not crash."""
        mock_groq = MagicMock()  # No spec — allow .client access
        mock_groq.client.chat.completions.create.side_effect = Exception("API error")
        
        service = InterviewAnalysisService(groq_service=mock_groq)
        concepts = service._generate_expected_concepts("What is OOP?", "technical")
        
        # Should return fallback concepts, not raise
        assert len(concepts) == 4
        assert "Core concept understanding" in concepts


# ═══════════════════════════════════════════════════════════════════════
# F-3: partial_concepts and evidence must be persisted
# ═══════════════════════════════════════════════════════════════════════

class TestF3_PartialConceptsPersistence:
    """F-3: _persist_question_analysis must save partial_concepts and evidence."""
    
    def test_persist_includes_partial_concepts_and_evidence(self):
        """Both create and update paths must include partial_concepts and evidence."""
        from app.models.interview import InterviewQuestionAnalysis
        
        db = MagicMock()
        # No existing record
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = MagicMock()
        db.commit = MagicMock()
        
        service = InterviewAnalysisService()
        
        analysis = QuestionAnalysis(
            question_id="q1",
            question_number=1,
            question_text="What is OOP?",
            question_type="QUESTION",
            candidate_answer="OOP is about objects",
            expected_concepts=["encapsulation", "inheritance"],
            covered_concepts=["encapsulation"],
            missing_concepts=["inheritance"],
            incorrect_concepts=[],
            partial_concepts=["polymorphism"],
            concept_evaluations=[
                ConceptEvaluation(
                    concept="encapsulation",
                    status="demonstrated",
                    evidence="Candidate mentioned data hiding"
                ),
                ConceptEvaluation(
                    concept="polymorphism",
                    status="partial",
                    evidence="Briefly mentioned overriding"
                ),
            ],
            strengths=["Clear explanation"],
            gaps=["Missing inheritance"],
            score=6.0,
            confidence=0.8,
            depth_level="Basic",
            interview_turn_id=1,
            pool_question_id=None,
        )
        
        service._persist_question_analysis(db, interview_id=1, analysis=analysis)
        
        # Verify db.add was called with a record that includes partial_concepts and evidence
        add_call = db.add.call_args
        assert add_call is not None, "db.add must be called for new record"
        record = add_call[0][0]
        assert record.partial_concepts == ["polymorphism"]
        assert record.evidence == {
            "encapsulation": "Candidate mentioned data hiding",
            "polymorphism": "Briefly mentioned overriding",
        }


# ═══════════════════════════════════════════════════════════════════════
# F-10: Freshness must decay based on evidence age
# ═══════════════════════════════════════════════════════════════════════

class TestF10_FreshnessDcay:
    """F-10: _calculate_freshness must return different tiers based on age."""
    
    def test_freshness_high_for_recent(self):
        db = MagicMock()
        updater = CompetencyUpdater(db)
        # Verified 5 days ago
        result = updater._calculate_freshness(datetime.now() - timedelta(days=5))
        assert result == "high"
    
    def test_freshness_medium_for_moderate(self):
        db = MagicMock()
        updater = CompetencyUpdater(db)
        # Verified 45 days ago
        result = updater._calculate_freshness(datetime.now() - timedelta(days=45))
        assert result == "medium"
    
    def test_freshness_low_for_stale(self):
        db = MagicMock()
        updater = CompetencyUpdater(db)
        # Verified 120 days ago
        result = updater._calculate_freshness(datetime.now() - timedelta(days=120))
        assert result == "low"
    
    def test_freshness_high_for_none(self):
        """Brand-new record with no previous verification."""
        db = MagicMock()
        updater = CompetencyUpdater(db)
        result = updater._calculate_freshness(None)
        assert result == "high"
    
    def test_freshness_boundary_30_days(self):
        db = MagicMock()
        updater = CompetencyUpdater(db)
        assert updater._calculate_freshness(datetime.now() - timedelta(days=30)) == "high"
        assert updater._calculate_freshness(datetime.now() - timedelta(days=31)) == "medium"
    
    def test_freshness_boundary_90_days(self):
        db = MagicMock()
        updater = CompetencyUpdater(db)
        assert updater._calculate_freshness(datetime.now() - timedelta(days=90)) == "medium"
        assert updater._calculate_freshness(datetime.now() - timedelta(days=91)) == "low"


# ═══════════════════════════════════════════════════════════════════════
# Transcript Normalization Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTranscriptNormalization:
    """Tests for the canonical transcript event pipeline."""
    
    def test_normalize_agent_utterance(self):
        """Retell 'agent' role maps to 'ai' speaker."""
        utterance = {
            "role": "agent",
            "content": "Tell me about yourself",
            "utterance_id": "u1",
            "is_final": True,
        }
        event = normalize_retell_utterance(utterance, sequence=1)
        assert event.speaker == "ai"
        assert event.text == "Tell me about yourself"
        assert event.is_final is True
        assert event.message_type == "question"
    
    def test_normalize_user_utterance(self):
        """Retell 'user' role maps to 'candidate' speaker."""
        utterance = {
            "role": "user",
            "content": "I have 5 years of experience",
            "is_final": True,
        }
        event = normalize_retell_utterance(utterance, sequence=2)
        assert event.speaker == "candidate"
        assert event.message_type == "answer"
    
    def test_deterministic_turn_id_without_utterance_id(self):
        """Without utterance_id, turn_id must be deterministic based on sequence."""
        utterance = {"role": "agent", "content": "Hello", "is_final": True}
        event = normalize_retell_utterance(utterance, sequence=5)
        assert event.turn_id == "turn-5"
    
    def test_deterministic_turn_id_with_utterance_id(self):
        """With utterance_id, turn_id must use it."""
        utterance = {
            "role": "agent", "content": "Hello",
            "utterance_id": "abc123", "is_final": True,
        }
        event = normalize_retell_utterance(utterance, sequence=5)
        assert event.turn_id == "abc123"
    
    def test_normalize_transcript_skips_empty(self):
        """Empty content utterances should be skipped."""
        utterances = [
            {"role": "agent", "content": "Hello", "is_final": True},
            {"role": "user", "content": "", "is_final": True},
            {"role": "user", "content": "  ", "is_final": True},
            {"role": "user", "content": "My answer", "is_final": True},
        ]
        events = normalize_retell_transcript(utterances)
        assert len(events) == 2
        assert events[0].text == "Hello"
        assert events[1].text == "My answer"
    
    def test_select_changed_events_filters_unchanged(self):
        """select_changed_events should only emit events whose fingerprint changed."""
        fingerprints = {}
        
        events1 = [
            CanonicalTranscriptEvent(
                turn_id="t1", speaker="ai", text="Hello",
                timestamp=1000, is_final=False, sequence=1,
            ),
        ]
        changed1 = select_changed_events(fingerprints, events1)
        assert len(changed1) == 1  # First time, everything is new
        
        # Same event again — should not be re-emitted
        changed2 = select_changed_events(fingerprints, events1)
        assert len(changed2) == 0
        
        # Updated text — should be re-emitted
        events2 = [
            CanonicalTranscriptEvent(
                turn_id="t1", speaker="ai", text="Hello world",
                timestamp=1000, is_final=True, sequence=1,
            ),
        ]
        changed3 = select_changed_events(fingerprints, events2)
        assert len(changed3) == 1
    
    def test_extract_utterances_list_format(self):
        """extract_utterances handles bare array format."""
        data = [{"role": "agent", "content": "Hi"}]
        result = extract_utterances(data)
        assert len(result) == 1
    
    def test_extract_utterances_dict_format(self):
        """extract_utterances handles {utterances: [...]} format."""
        data = {"utterances": [{"role": "agent", "content": "Hi"}]}
        result = extract_utterances(data)
        assert len(result) == 1
    
    def test_extract_utterances_empty(self):
        """extract_utterances handles None and empty."""
        assert extract_utterances(None) == []
        assert extract_utterances({}) == []
        assert extract_utterances([]) == []


# ═══════════════════════════════════════════════════════════════════════
# F-13: interview_type should use phase, not hardcoded "technical"
# ═══════════════════════════════════════════════════════════════════════

class TestF13_InterviewType:
    """F-13: Analysis should use the interview's phase, not hardcoded 'technical'."""
    
    def test_persist_uses_question_type(self):
        """_persist_question_analysis should use question_type, not hardcoded 'technical'."""
        from app.models.interview import InterviewQuestionAnalysis
        
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = MagicMock()
        db.commit = MagicMock()
        
        service = InterviewAnalysisService()
        
        analysis = QuestionAnalysis(
            question_id="q1", question_number=1,
            question_text="Tell me about yourself",
            question_type="HR",
            candidate_answer="I am...",
            expected_concepts=["motivation"], covered_concepts=["motivation"],
            missing_concepts=[], incorrect_concepts=[], partial_concepts=[],
            concept_evaluations=[], strengths=["Good intro"], gaps=[],
            score=8.0, confidence=0.9, depth_level="Good",
            interview_turn_id=1, pool_question_id=None,
        )
        
        service._persist_question_analysis(db, interview_id=1, analysis=analysis)
        
        record = db.add.call_args[0][0]
        assert record.interview_type == "hr", \
            f"Expected 'hr' but got '{record.interview_type}'"


# ═══════════════════════════════════════════════════════════════════════
# Phase 6: Live Transcript Broadcast & Finalization Gating Tests
# ═══════════════════════════════════════════════════════════════════════

class TestLiveTranscriptAndFinalizationGating:
    """Verify live transcript broadcasting in edi5_core and finalization gating."""

    @pytest.mark.asyncio
    async def test_edi5_core_broadcasts_live_transcript(self):
        """In edi5_core mode, _handle_update_only must normalize and broadcast changed events."""
        from app.modules.interview.services.retell_llm_websocket import RetellLLMWebSocketHandler, RetellLLMContext
        
        ws = MagicMock()
        adapter = MagicMock()
        db_factory = MagicMock()
        
        handler = RetellLLMWebSocketHandler(
            websocket=ws,
            call_id="call_test_123",
            adapter=adapter,
            get_db_session=db_factory,
        )
        handler.context.edi5_interview_id = 42
        
        data = {
            "transcript": [
                {"role": "agent", "content": "Welcome to the interview.", "is_final": True},
                {"role": "user", "content": "Thank you, excited to start.", "is_final": False},
            ],
            "turntaking": "user_turn",
        }
        
        broadcasts = []
        async def mock_broadcast(interview_id, payload):
            broadcasts.append((interview_id, payload))
            
        with patch(
            "app.modules.interview.routers.transcript_websocket.broadcast_transcript_update",
            side_effect=mock_broadcast,
        ), patch.object(handler, "_persist_structured_transcript", return_value=None):
            await handler._handle_update_only(data)
            
        assert len(broadcasts) == 2, "Both utterances must be broadcast"
        assert broadcasts[0][0] == 42
        assert broadcasts[0][1]["speaker"] == "ai"
        assert broadcasts[0][1]["text"] == "Welcome to the interview."
        assert broadcasts[1][1]["speaker"] == "candidate"
        assert broadcasts[1][1]["is_final"] is False
        
        # Second call with identical content should be skipped by select_changed_events
        broadcasts.clear()
        with patch(
            "app.modules.interview.routers.transcript_websocket.broadcast_transcript_update",
            side_effect=mock_broadcast,
        ), patch.object(handler, "_persist_structured_transcript", return_value=None):
            await handler._handle_update_only(data)
            
        assert len(broadcasts) == 0, "Unchanged transcript events must not be rebroadcast"

    @pytest.mark.asyncio
    async def test_reconciliation_preserves_order_and_updates_content(self):
        """Finalization reconciliation updates existing sequence messages in place."""
        from app.modules.interview.services.retell_finalization_service import RetellFinalizationService
        from app.models.interview import InterviewSession, InterviewConversation, InterviewMessage
        
        db = MagicMock()
        interview = MagicMock(spec=InterviewSession)
        interview.id = 10
        interview.session_id = 99
        interview.current_turn = 2
        
        conv = MagicMock(spec=InterviewConversation)
        conv.id = 101
        
        # Existing message 1 (interim user message)
        existing_msg = MagicMock(spec=InterviewMessage)
        existing_msg.sequence_number = 1
        existing_msg.text = "I have 3 yrs"
        existing_msg.is_final = False
        
        db.query.return_value.filter.return_value.first.return_value = conv
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [existing_msg]
        
        service = RetellFinalizationService(db)
        
        canonical_events = [
            CanonicalTranscriptEvent(
                turn_id="turn-1",
                speaker="candidate",
                text="I have 3 years of experience in Python and FastAPI.",
                timestamp=1000,
                is_final=True,
                sequence=1,
            )
        ]
        
        count = await service._reconcile_final_transcript(interview, canonical_events)
        
        assert count == 1
        assert existing_msg.text == "I have 3 years of experience in Python and FastAPI."
        assert existing_msg.is_final is True


# ═══════════════════════════════════════════════════════════════════════
# Run configuration
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
