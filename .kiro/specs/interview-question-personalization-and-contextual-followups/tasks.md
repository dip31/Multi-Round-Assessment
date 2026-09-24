# Implementation Plan: Interview Question Personalization and Contextual Follow-ups

## Overview

This plan breaks down the design into incremental implementation steps, moving from foundational components (resume extraction validation, question validation) through to core features (contextual follow-ups, metadata tracking). Each step builds on previous work with integrated testing to validate correctness properties early.

The approach prioritizes robust validation and graceful fallback: we ensure questions are grounded in resume content before presenting them, and if validation fails, we degrade gracefully to role-based fallback questions while maintaining interview continuity.

---

## Tasks

- [x] 1. Set up project structure and schemas
  - [x] 1.1 Create new modules and directory structure
    - Create `app/modules/interview/services/personalization_service.py` (core orchestration)
    - Create `app/modules/interview/validators/question_validator.py`
    - Create `app/modules/interview/validators/answer_classifier.py`
    - Create `app/modules/interview/generators/contextual_followup_generator.py`
    - Create `app/modules/interview/utils/metadata_tracker.py`
    - _Requirements: Architecture_

  - [x] 1.2 Extend Interview Session and Turn database schemas
    - Add optional fields to `InterviewSession` model: extraction_confidence, retrieval_success_rate, question_personalization_rate, personalization_metadata (JSON), follow_up_quality_score, personalization_warnings
    - Add optional fields to `InterviewTurn` model: personalization_source, question_grounding_confidence, answer_classification (JSON), followup_grounding_score, followup_targeted_aspect
    - Create Alembic migration for schema changes (backward compatible)
    - _Requirements: 2, 12_

  - [x] 1.3 Create Pydantic schemas for new data structures
    - ResumExtractionResult schema (extraction_confidence, skills_count, projects_count, issues, recommendation)
    - QuestionValidationResult schema (is_valid, grounding_confidence_score, personalization_source, recommendation)
    - AnswerClassificationResult schema (quality, intent, content_score, confidence, missing_aspects, domain_markers)
    - ContextualFollowupResult schema (followup_question, followup_type, grounding_score, validation_status)
    - InterviewMetadata schema (extraction_metadata, question_pool_metadata, per_question_metrics, interview_summary)
    - _Requirements: Architecture_

- [ ] 2. Implement Resume Extraction Validation
  - [ ] 2.1 Create Resume Extraction Validator component
    - Implement validation logic: min skills ≥5 (HIGH), ≥3 (MEDIUM), <3 (LOW)
    - Implement validation logic: min projects ≥2 with descriptions (HIGH), ≥1 (MEDIUM)
    - Implement role alignment validation (check experience years match role)
    - Implement retry logic: if skills<3, attempt re-extraction with alternative method
    - Implement fallback: if re-extraction still fails, proceed with LOW confidence and mark metadata
    - Store extraction result with Interview_Session
    - _Requirements: 1.1-1.8_

  - [ ] 2.2 Write property test for resume extraction validation
    - **Property: For any extracted resume data, system must validate skill/project counts and return appropriate confidence level**
    - **Validates: Requirements 1.2, 1.3, 1.4**
    - Generate 50 random resumes with varying skill/project counts
    - Test that validation correctly identifies HIGH/MEDIUM/LOW confidence
    - Test retry logic when skills < 3
    - Assert: confidence level correlates with extracted data quantity

- [ ] 3. Implement Question Personalization Validator
  - [ ] 3.1 Create Question Validator component
    - Implement token matching: check if question text contains skill/project names from resume
    - Implement semantic similarity: identify skill-related references (e.g., "database optimization" matches "PostgreSQL")
    - Calculate grounding_confidence_score: exact match 0.85-1.0, semantic 0.65-0.85, role-only 0.40-0.65, no grounding <0.40
    - Implement regeneration request for questions with confidence < 0.75
    - Mark each question with personalization_source (skill/project name, reference type, confidence, matching_evidence)
    - Track regeneration attempts; allow up to 2 retries, then use fallback
    - Ensure only questions with confidence ≥0.75 are included in final pool (or marked fallback)
    - Return pool only if ≥8 of 10 questions meet threshold
    - _Requirements: 2.1-2.7_

  - [ ] 3.2 Write property test for question personalization validation
    - **Property: For any generated question pool, all non-fallback questions must reference resume content (grounding_confidence_score ≥0.75)**
    - **Validates: Requirements 2.1, 2.5**
    - Generate 50 random question pools with varying resume contexts
    - For each non-fallback question, verify it contains skill/project/role reference
    - Assert: 100% of non-fallback questions pass validation
    - Assert: grounding_confidence_score ≥0.75 for all accepted questions

- [ ] 4. Implement Fallback Question Generator
  - [ ] 4.1 Create Fallback Question Generator component
    - Implement skill-based fallback: "Tell me about your experience with [SKILL]"
    - Implement role-based fallback: "As a [ROLE] developer, how have you approached [AREA]?"
    - Implement project-based fallback: "Describe [PROJECT] in more detail. What was your role?"
    - Select skills by resume frequency (most mentioned first)
    - Map difficulty level to skill selection
    - Implement forbidden pattern prevention: never generate "What is X?", "Explain OOPS", etc.
    - Mark all fallback questions with is_fallback=true, fallback_reason, grounding_confidence=0.5-0.7
    - Ensure fallback questions are usable alternatives even when primary generation fails
    - _Requirements: 3.1-3.8, 8.1-8.7_

  - [ ] 3.4 Write property test for fallback questions
    - **Property: All fallback questions must reference extracted skills or detected role (no completely generic questions)**
    - **Validates: Requirements 3.2, 8.4**
    - Trigger 20 fallback scenarios (low extraction, failed retrieval, API failures)
    - For each fallback question, verify it contains skill/project/role reference
    - Assert: 0 generic templates appear (no "What is...", "Explain OOPS", etc.)
    - Assert: 100% of fallback questions pass grounding check

- [ ] 5. Implement Answer Classification with Domain Awareness
  - [ ] 5.1 Create Answer Classifier component
    - Implement quality classification logic:
      - EXCELLENT: content_score ≥0.85 (demonstrates expertise, technical depth, project examples)
      - COMPLETE: content_score 0.65-0.84 (addresses question with specifics, brief but sufficient)
      - PARTIAL: content_score 0.35-0.64 (addresses question but lacks depth)
      - SHORT: content_score <0.35 (too brief, off-topic, ambiguous)
    - Implement domain marker detection: extract domain-specific keywords (query optimization, indexing, etc.)
    - Implement domain-aware assessment: for expert candidates, brief answers with domain markers should be COMPLETE not SHORT
    - Implement missing_aspects extraction: identify specific gaps using LLM (testing, scaling, security, deployment, etc.)
    - Implement intent classification: POSITIVE, NEGATIVE, NEUTRAL
    - Implement confidence calculation: return confidence score 0.0-1.0 for classification
    - Handle low-confidence classifications (confidence <0.35): mark as ambiguous
    - Map detected role + domain to expected answer patterns for seniority-aware assessment
    - _Requirements: 4.1-4.8_

  - [ ] 5.2 Write property test for answer classification domain awareness
    - **Property: Expert brief answers with domain markers should be classified as COMPLETE, not SHORT**
    - **Validates: Requirements 4.4, 4.5**
    - Create paired answers: expert brief ("PostgreSQL indexing") vs junior brief ("databases")
    - Provide resume context indicating seniority
    - Run classification for both
    - Assert: expert_quality ≥ COMPLETE
    - Assert: junior_quality ≤ PARTIAL
    - Assert: expert receives higher score despite similar brevity

  - [ ] 5.3 Write property test for missing aspects extraction
    - **Property: Answer classification must extract specific missing_aspects, not generic gaps**
    - **Validates: Requirements 4.7**
    - Generate 30 partial answers with various gaps (testing, deployment, scaling, security)
    - Run classification on each
    - Verify missing_aspects list contains specific areas (not "expand on this")
    - Assert: missing_aspects accurately reflect what's missing from answer

- [ ] 6. Implement Contextual Follow-up Generator
  - [ ] 6.1 Create Contextual Follow-up Generator component
    - Implement follow-up type selection:
      - error_recovery: IF answer quality SHORT AND confidence <0.35 (restate question)
      - clarification: IF answer quality SHORT (seek specifics)
      - depth_probe: IF missing_aspects not empty (probe identified gaps)
    - Implement missing aspect targeting: 1st follow-up uses first aspect, 2nd follow-up uses different aspect
    - Implement generation for each follow-up type:
      - clarification: "[Reference from answer]. [Question about missing aspect]?"
      - depth_probe: "[Gap name]. How did you approach [gap]?"
      - error_recovery: "Let me rephrase: [ORIGINAL_QUESTION]. Can you provide more details?"
    - Implement grounding validation: verify follow-up contains word(s) from answer OR references targeted_missing_aspect
    - Calculate grounding_score: 0.5 for answer reference + 0.3 for gap reference + 0.2 for domain language
    - Mark validation_status: high_confidence (≥0.75), low_confidence (0.50-0.74), fallback (<0.50)
    - Implement regeneration: if generated follow-up appears generic, regenerate up to 1x, then use template fallback
    - Implement repetition prevention: track prior follow-ups, don't ask same gap twice
    - Hard limit: max 2 follow-ups per original question
    - _Requirements: 5.1-5.9, 6.1-6.7, 7.1-7.6_

  - [ ] 6.2 Write property test for contextual follow-up generation
    - **Property: All follow-ups must reference answer content or identified gaps (grounding_score ≥0.75)**
    - **Validates: Requirements 5.1, 5.2, 6.2**
    - Generate 100 random (answer, classification) pairs
    - Generate contextual follow-up for each
    - For each follow-up, verify: contains answer reference OR gap reference
    - Assert: 100% of follow-ups have grounding_score ≥0.75
    - Assert: 0 generic follow-ups ("Could you elaborate?", "Tell me more")

  - [ ] 6.3 Write property test for follow-up repetition prevention
    - **Property: Consecutive follow-ups for same question must address different missing aspects**
    - **Validates: Requirements 7.2, 7.3**
    - Simulate 50 interview scenarios with multiple follow-ups per question
    - For each question with 2+ follow-ups, verify targeted_missing_aspect differs
    - Assert: 0 consecutive follow-ups target same aspect
    - Assert: hard limit of 2 follow-ups enforced

- [ ] 7. Implement Question Generation Error Recovery
  - [ ] 7.1 Add retry logic to question generation
    - Wrap question generation with retry handler
    - On timeout: retry up to 2x with exponential backoff (1s, 2s)
    - On API error: retry up to 2x with backoff
    - Log all retries with timestamps and error details
    - If all retries fail: fall back to fallback question generation
    - If RAG retrieval returns 0 docs: proceed with fallback (don't retry forever)
    - If RAG retrieval returns 1-2 docs: still proceed (no minimum threshold)
    - _Requirements: 9.1-9.7_

  - [ ] 7.2 Write integration test for error recovery
    - **Property: Interview must continue despite API failures; never block due to personalization**
    - **Validates: Requirements 9.1-9.5**
    - Simulate 10 failure scenarios: timeout, API error, no docs, network failure
    - For each failure, attempt full interview generation
    - Assert: Interview reaches completion (no exceptions)
    - Assert: Fallback mechanism activates
    - Assert: metadata.warnings populated

- [ ] 8. Implement Interview Metadata Tracking
  - [ ] 8.1 Create Metadata Tracker component
    - Initialize metadata on interview start:
      - extraction_metadata: extraction_confidence, skills_count, projects_count, issues, alternative_extraction_attempted
      - question_pool_metadata: retrieval_success_rate, question_personalization_rate, questions_with_fallback, average_grounding_confidence
      - per_question_metrics: [ {question_number, personalization_source, grounding_confidence, answer_quality, missing_aspects, followups, average_followup_grounding} ]
    - Track per-turn: original question grounding, answer quality, classification confidence, follow-up count, follow-up grounding scores
    - Calculate at interview end:
      - average_follow_up_grounding: mean of all follow-up grounding scores
      - personalization_quality_score: composite 0.0-1.0 based on extraction + question + follow-up quality
      - follow_up_quality_score: mean follow-up grounding score
    - Trigger warnings: IF personalization_quality_score <0.60 OR follow_up_quality_score <0.60
    - Persist metadata to database (JSON field or separate table)
    - Expose metadata in interview report API
    - _Requirements: 11.1-11.7_

  - [ ] 8.2 Write property test for metadata quality scores
    - **Property: Metadata scores should monotonically correlate with underlying quality levels**
    - **Validates: Requirements 11.6, 11.7**
    - Generate 30 interview scenarios with varying quality: HIGH, MEDIUM, LOW
    - Calculate metadata scores for each
    - Assert: HIGH quality scenario: personalization_score ≥0.75
    - Assert: MEDIUM quality scenario: personalization_score 0.50-0.75
    - Assert: LOW quality scenario: personalization_score ≤0.60
    - Assert: warnings correctly triggered

- [ ] 9. Integrate Validators into Question Generation Pipeline
  - [ ] 9.1 Modify existing question generation flow
    - After question pool generation: run Question Validator on all 12 questions
    - Validate each question's grounding: if <0.75, request regeneration from LLM
    - After regeneration attempts: if still <0.75, mark as fallback
    - Select top 10 questions: 8+ must have confidence ≥0.75 (or be acceptable fallbacks)
    - If <8 questions pass threshold: use fallback question generator to fill pool
    - Store personalization_source metadata for each question
    - Store grounding_confidence_score for each question
    - Return final pool with metadata
    - _Requirements: 2, 9_

  - [ ] 9.2 Write integration test for question pool generation
    - **Property: Final question pool must have ≥8/10 questions with confidence ≥0.75 OR be marked fallback**
    - **Validates: Requirements 2.7**
    - Run question generation for 20 candidate resumes
    - For each pool, count questions with confidence ≥0.75
    - Assert: count ≥8 or entire pool marked with lower confidence
    - Assert: all questions reference resume or are marked fallback

- [ ] 10. Integrate Answer Classification into Interview Turn Flow
  - [ ] 10.1 Modify interview turn endpoint
    - When answer is submitted: transcribed text is available
    - Run Answer Classifier on the answer
    - Store classification result in InterviewTurn.answer_classification (JSON)
    - Extract missing_aspects and quality level
    - Determine if follow-up is needed based on quality
    - If quality <COMPLETE AND confidence ≥0.35: generate contextual follow-up
    - If quality <SHORT OR confidence <0.35: generate error_recovery follow-up (restate question)
    - Return follow-up to frontend (or indicate no follow-up needed)
    - _Requirements: 4, 10_

  - [ ] 10.2 Write integration test for answer classification flow
    - **Property: Answer classification must return appropriate quality level and generate contextual follow-up if needed**
    - **Validates: Requirements 4.1-4.8, 10**
    - Submit 30 varied answers: SHORT, PARTIAL, COMPLETE, EXCELLENT quality
    - For each, verify classification is correct
    - If follow-up generated, verify it's contextual (not generic)
    - Assert: domain-aware classification works (expert brief answers get appropriate score)

- [ ] 11. Integrate Contextual Follow-up into Interview Response
  - [ ] 11.1 Wire contextual follow-up generator to interview router
    - Modify `generate_interviewer_response()` in `groq_service.py`
    - Replace hardcoded _brain_fallback() responses with Contextual Follow-up Generator
    - Pass to generator:
      - original_question, candidate_answer
      - answer_classification (quality, missing_aspects, domain_markers, content_score, confidence)
      - candidate_skills, candidate_projects from resume
      - followup_count (0-indexed)
      - prior_followups (list of previous follow-ups for this question)
    - Receive contextual follow-up question
    - Return follow-up to frontend
    - Store follow-up metadata in InterviewTurn
    - _Requirements: 5, 6, 7_

  - [ ] 11.2 Write integration test for follow-up response generation
    - **Property: Interviewer response must be contextual (reference answer or gap), never generic**
    - **Validates: Requirements 5.1-5.8, 6, 7**
    - Simulate 50 interview turns with varied answers
    - For each, generate interviewer response
    - Verify response is contextual: references answer OR missing_aspect
    - Assert: 0 generic responses ("Could you elaborate?", "Tell me more")
    - Assert: consecutive follow-ups address different gaps

- [ ] 12. Integrate Fallback Mechanisms Throughout
  - [ ] 12.1 Test and verify fallback activation for each component
    - Test question generation with no relevant docs: fallback questions used
    - Test question generation with low extraction confidence: fallback questions used
    - Test question generation with API failure: fallback questions used
    - Test follow-up generation with low answer confidence: error_recovery type used
    - Test follow-up generation with LLM failure: template fallback used
    - Verify interview continues in all scenarios (no blocking errors)
    - Verify metadata.warnings populated appropriately
    - _Requirements: 3, 7, 9, 10_

  - [ ] 12.2 Write integration test for graceful degradation
    - **Property: Interview must continue despite failures; never block on personalization**
    - **Validates: Requirements 3, 7, 9**
    - Simulate failures at: extraction, retrieval, generation, classification, follow-up
    - For each failure, run complete interview flow
    - Assert: Interview reaches completion (0 exceptions)
    - Assert: Fallback mechanism activates
    - Assert: metadata correctly documents degradation

- [ ] 13. Backward Compatibility & Migration
  - [ ] 13.1 Ensure new fields don't break existing code
    - All new InterviewSession and InterviewTurn fields are nullable (DEFAULT NULL)
    - Existing queries that don't reference new fields continue to work
    - Existing reports handle NULL new fields gracefully
    - Database migration is backward compatible (additive only, no drops)
    - Legacy interview sessions (without new metadata) can coexist with new sessions
    - _Requirements: 12_

  - [ ] 13.2 Write backward compatibility test
    - **Property: Legacy interview sessions without personalization metadata must continue to work**
    - **Validates: Requirement 12**
    - Create mock legacy InterviewSession and InterviewTurn (missing all new fields)
    - Run existing interview functionality: retrieve session, generate report, run analytics
    - Assert: 0 NULL reference errors
    - Assert: all queries complete successfully
    - Assert: reports display without data for missing fields

- [ ] 14. Checkpoint - Core Features Complete
  - Ensure all core components are implemented and integrated
  - Run full interview flow: generate personalized questions → collect answer → classify → generate contextual follow-up
  - Ask the user if questions arise

- [ ] 15. Add Monitoring & Alerting
  - [ ] 15.1 Implement quality metrics collection
    - Add telemetry for: extraction quality, question personalization rate, follow-up grounding score
    - Calculate per-interview: personalization_quality_score, follow_up_quality_score
    - Track: fallback rate, API retry rate, degradation frequency
    - Store metrics in analytics DB or logging service
    - _Requirements: Monitoring_

  - [ ] 15.2 Create dashboard for quality metrics
    - Display: % of sessions with HIGH extraction confidence
    - Display: average question personalization rate
    - Display: average follow-up grounding score
    - Display: fallback usage rate
    - Display: interview completion rate
    - Create alerts: IF extraction_high <50%, IF question_personalization_rate <70%, IF follow-up_grounding <0.65
    - _Requirements: Monitoring_

- [ ] 16. Documentation & Handoff
  - [ ] 16.1 Document system architecture
    - Write component overview and data flow
    - Document validation rules and confidence thresholds
    - Document fallback mechanisms and recovery strategies
    - _Requirements: Architecture_

  - [ ] 16.2 Document troubleshooting & debugging
    - How to identify personalization failures
    - How to debug low grounding scores
    - How to interpret metadata and warnings
    - _Requirements: Documentation_

- [ ] 17. Final Checkpoint - Production Readiness
  - Verify all property tests pass
  - Verify backward compatibility with existing data
  - Run full regression: Aptitude → Coding → Interview flow
  - Verify metrics and monitoring are working
  - Ask the user if questions arise before handoff

---

## Notes

- Tasks marked with `*` are testing tasks (property-based tests and integration tests). These can be marked as optional if focusing on MVP, but are critical for ensuring feature correctness.
- Each testing task explicitly references which design properties it validates, ensuring correctness properties are comprehensively covered.
- Fallback mechanisms are integrated throughout to ensure graceful degradation: if primary generation fails, interview continues with reduced-confidence questions.
- Metadata tracking is comprehensive but non-blocking: if metadata save fails, interview continues normally.
- All changes are backward compatible: existing interviews and code continue to work unaffected.

