# Phase 3 — Transcript Analysis Audit

**Date:** 2026-10-07  
**Status:** Pre-implementation audit

---

## 1. Current Transcript Storage

| Component | Table/Model | Key Fields | Status |
|-----------|-------------|------------|--------|
| Structured conversation | `InterviewConversation` | `interview_id`, `total_messages`, `ai_message_count`, `candidate_message_count` | ✅ Implemented |
| Individual messages | `InterviewMessage` | `sequence_number`, `speaker`, `text`, `message_type`, `turn_id`, `retell_utterance_id`, `is_final`, `confidence` | ✅ Implemented |
| Transcript persistence | WS (`retell_llm_websocket.py`) + Webhook (`retell_webhook.py`) | Both persist to `InterviewMessage` with `turn_id = interview.current_turn` | ✅ Implemented |
| Frontend real-time | WebSocket (`transcript_websocket.py`) | Broadcasts `CanonicalTranscriptEvent` | ✅ Phase 2 |

**Gap:** Messages have `turn_id` pointing to `InterviewTurn.current_turn` at time of utterance, but no explicit question-answer grouping beyond the turn linkage.

---

## 2. Current Interview-Turn Storage

| Table | Key Fields | Notes |
|-------|------------|-------|
| `InterviewTurn` | `id`, `interview_id`, `turn_number`, `question_text`, `candidate_response`, `content_score`, `final_score`, `intent`, `is_followup`, `followup_number`, `parent_turn_id` | ✅ Links follow-ups to parent via `parent_turn_id` |
| `question_pool` (in `ApprovedQuestionPool`) | JSON array with `id`, `question`, `difficulty`, `topic`, `phase`, `grounded_in`, `personalized` | ✅ Questions have stable IDs |

**Gap:** The pool questions have IDs but `InterviewTurn.question_id` is NOT stored — only `question_text`. This makes it hard to map back to pool rubrics.

---

## 3. How Questions Are Identified

| Source | Method | Reliability |
|--------|--------|-------------|
| Pool selection | `QuestionPlanner.select_question()` returns pool item with `id` (hash) | High — but not persisted to `InterviewTurn` |
| Turn creation | `InterviewOrchestrator` creates turn with `question_text` only | Medium — text match only |
| Follow-ups | `parent_turn_id` links to main question | High for follow-up grouping |

**Gap:** `InterviewTurn` lacks `question_id` field to link to pool question.

---

## 4. How Answers Are Currently Identified

| Source | Method |
|--------|--------|
| Live interview | Candidate audio → STT → transcript → `InterviewTurn.candidate_response` |
| Retell modes | `InterviewMessage` (speaker=CANDIDATE) linked via `turn_id` |
| Report generation | `InterviewTurn.candidate_response` + follow-up answers |

---

## 5. Existing Scoring Logic

| Component | Formula | Range |
|-----------|---------|-------|
| Content score | Groq classifier | 0.0–1.0 |
| Intent score | POSITIVE=1.0, NEUTRAL=0.6, NEGATIVE=0.3 | 0.2–1.0 |
| Behavior score | 0.5×eye_contact + 0.5×head_stability | 0.0–1.0 |
| Final score | 0.5×content + 0.3×intent + 0.2×behavior | 0.0–1.0 |

**Gap:** Scores are per-turn aggregates; no concept-level breakdown.

---

## 6. Existing Expected-Answer/Rubric Information

| Status | Details |
|--------|---------|
| Question pool | Has `grounded_in` field but NO expected concepts/rubric |
| `InterviewAnalysisService` | Generates expected concepts on-the-fly via LLM at report time |
| Persistence | None — concepts generated fresh each report request |

**Critical Gap:** No stored expected concepts/rubrics to enable consistent evaluation or competency mapping.

---

## 7. Existing Competency Update Mechanism

| Status | Details |
|--------|---------|
| StudentProfile | Has `skills_json` (JSONB) but no competency scores/confidence/freshness |
| AssessmentRound | Has aggregate `score` only |
| InterviewTurn | Has per-turn scores but no skill mapping |
| Historical tracking | None |

**Critical Gap:** No competency profile with evidence, confidence, freshness, or history.

---

## 8. Interview Completion Flow

```
Frontend (RetellInterviewRoom)
    → POST /interview/session/{id}/complete  (or retell-transcript)
    → Interview marked COMPLETED
    → AssessmentRound marked completed
    → Frontend navigates to /interview/report/{id}
    → GET /interview/session/{id}/report
        → Calls InterviewAnalysisService.analyze_interview() ON-DEMAND
        → Returns question-wise analysis in response
```

**Gap:** Analysis is synchronous, on-demand, not persisted. No async job queue.

---

## 9. Reusable Services

| Service | Location | Reusable For |
|---------|----------|--------------|
| `InterviewAnalysisService` | `interview_analysis.py` | Core analysis logic — needs enhancement |
| `GroqService` | `groq_service.py` | LLM calls — JSON parsing, fallbacks |
| `transcript_normalizer` | `transcript_normalizer.py` | Canonical event format |
| `QuestionPlanner` | `question_planner.py` | Pool selection logic |
| `transcript_websocket` | `transcript_websocket.py` | Real-time broadcast |

---

## 10. Missing Components Required for Phase 3

| Component | Description | Priority |
|-----------|-------------|----------|
| Expected concepts storage | Add `expected_concepts` to pool questions or separate rubric table | Critical |
| Question ID on InterviewTurn | Add `question_id` FK to link turn to pool question | Critical |
| Answer analysis persistence | Store per-question analysis results (covered/missing/incorrect concepts) | Critical |
| Competency evidence model | Track skill evidence from interviews | Critical |
| Async analysis job | Background processing instead of on-demand | High |
| Confidence score | Separate from competency score | High |
| API endpoint | GET /analysis with persisted results | High |

---

## 11. Files to Modify

| File | Changes |
|------|---------|
| `app/models/interview.py` | Add `question_id` to `InterviewTurn`; add competency evidence model |
| `app/modules/interview/schemas/interview_schema.py` | Add analysis result schemas with concepts, confidence, competency changes |
| `app/modules/interview/services/interview_analysis.py` | Enhance with rubric reuse, confidence, competency evidence output |
| `app/modules/interview/routers/interview_router.py` | Add async analysis trigger on completion; persist results |
| `app/modules/interview/services/question_planner.py` | Store selected question_id on turn creation |
| `app/modules/interview/services/interview_orchestrator.py` | Pass question_id when creating turns |

---

## 12. Files to Create

| File | Purpose |
|------|---------|
| `app/modules/interview/services/answer_analyzer.py` | Semantic answer evaluation with structured output |
| `app/modules/interview/services/competency_updater.py` | Update student competency profile from interview evidence |
| `app/modules/interview/models/competency.py` | Competency evidence/history models |
| `app/modules/interview/routers/analysis.py` | Analysis endpoints (async status, results) |

---

## 13. Database Changes Required

| Change | Table | Type |
|--------|-------|------|
| Add `question_id` | `interview_turns` | String FK (pool question id) |
| Add `expected_concepts` | `approved_question_pools` → question_pool JSON | JSONB array per question |
| New table | `interview_question_analysis` | Analysis results per question |
| New table | `competency_evidence` | Skill evidence from interviews |
| New table | `student_competency` | Current competency score, confidence, freshness |

---

## 14. Architecture Summary

```
Interview Completed (Phase 2)
         │
         ▼
Final Transcript (InterviewMessage + InterviewTurn)
         │
         ▼
Question/Answer Segmentation (using turn_id + question_id)
         │
         ▼
Expected Concepts (from pool question.rubric)
         │
         ▼
Semantic Analysis (LLM: covered/missing/incorrect/partial)
         │
         ▼
Persisted QuestionAnalysis (new table)
         │
         ▼
Competency Evidence Extraction
         │
         ▼
StudentCompetency Update (new table with history)
         │
         ▼
Report API returns structured analysis
```