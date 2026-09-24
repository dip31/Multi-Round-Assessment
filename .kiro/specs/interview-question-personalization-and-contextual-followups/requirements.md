# Requirements Document: Interview Question Personalization and Contextual Follow-ups

## Introduction

The interview system currently generates generic questions that lack grounding in candidate resume content and produces repetitive, non-contextual follow-up questions. This results in poor assessment of candidate fit and frustration with non-personalized interactions. This document specifies requirements for two interconnected features:

1. **Interview Question Personalization**: Ensuring all interview questions are explicitly grounded in a candidate's actual resume skills, projects, and experience
2. **Contextual Follow-up Questions**: Generating contextually relevant follow-up questions based on what the candidate actually said, not generic fallback templates

These features aim to create higher-quality assessments by tailoring questions to candidate background and providing intelligent follow-up that demonstrates understanding of their responses.

---

## Glossary

- **Resume_Content**: The parsed structured data extracted from a candidate's resume including skills, projects, work experience, and educational background
- **Interview_Question**: A question presented to the candidate in an interview round, with difficulty level, question text, and grounding metadata
- **Question_Personalization**: The process of validating that an interview question is explicitly linked to and references specific content from the candidate's resume
- **Question_Pool**: The set of 10 interview questions generated for a specific candidate before the interview begins
- **Candidate_Answer**: The candidate's spoken response to an interview question, converted to text via transcription
- **Answer_Classification**: The system's assessment of a candidate's answer including quality level, intent, and missing aspects
- **Follow_Up_Question**: An additional question asked to a candidate after their initial answer, designed to probe deeper into their knowledge on specific aspects
- **Follow_Up_Type**: The category of follow-up question (elaboration, clarification, depth_probe, error_recovery)
- **Contextual_Grounding**: A follow-up question that explicitly references content from the candidate's answer or specific missing aspects identified in the classification
- **Fallback_Mechanism**: The system's behavior when primary question generation or follow-up generation fails
- **Interview_Session**: A single interview instance with a specific candidate, question pool, and turn sequence
- **Domain_Knowledge**: Subject matter expertise in a technical area (databases, frontend, DevOps, etc.)
- **Answer_Quality_Score**: A numeric assessment of how complete and accurate the candidate's answer is (0.0-1.0)
- **Confidence_Threshold**: Minimum confidence score required to classify an answer or question as valid (e.g., 0.75)

---

## Current System Behavior (Problem Statement)

### Issue 1: Questions Are Not Grounded in Resume

**Current Implementation:**
- `app/services/groq_service.py`: generate_question_pool() receives extracted skills and projects from resume
- RAG retriever searches knowledge base for related content
- Groq LLM generates 12 questions and selects top 10
- Process has **no validation** that generated questions actually reference candidate's resume
- Questions are stored and presented with a `"personalized": true` flag that is **never verified**

**Observed Problematic Behavior:**
1. Senior Python/Django developer with ML projects receives: "What is HTTP?", "Explain inheritance", "What is a database?"
2. When resume parsing fails or is incomplete, system falls back to hardcoded generic questions (e.g., "Explain OOPS concepts", "What is the difference between...") that have zero connection to resume
3. When RAG retriever fails or returns unrelated documents, generated questions are still treated as "personalized" even though they lack resume grounding

**Evidence from Code:**
- File: `app/services/groq_service.py` lines 242-320
  - Technical fallback questions: 12 hardcoded generic questions with no resume reference
  - Triggered when: Groq API fails, returns invalid JSON, or network timeout
  - Problem: Fallback lacks any connection to candidate's skills, projects, or detected role

- File: `app/services/groq_service.py` lines 31-120
  - RAG retriever has no validation that docs match candidate's skills
  - Resume extraction may be incomplete (PyMuPDF + Groq LLM extraction can miss formatted content)
  - No recovery mechanism if retrieval fails or returns minimal results

**Impact:**
- Assessment doesn't measure candidate's actual expertise
- Candidates experience frustration: "These questions don't test my skills"
- High-level candidates appear lower-skilled than they are when asked beginner questions
- Low-level candidates may appear higher-skilled if generic questions happen to match their experience

### Issue 2: Follow-up Questions Are Repetitive and Non-Contextual

**Current Implementation:**
- `app/modules/interview/routers/interview_router.py` lines 570-620: Decision engine classifies answer into QUALITY category
- `app/services/groq_service.py`: _brain_fallback() provides hardcoded responses for each category
- System receives (quality, followup_type) but does **not analyze what the candidate actually said**
- All answers in same quality category receive identical follow-up question

**Observed Problematic Behavior:**
1. Question: "Tell me about your database experience"
   - Short answer: "I used PostgreSQL" → Response: "Could you elaborate on that in more detail?"
   - Long answer: "I designed a PostgreSQL schema with 50+ tables handling 1M transactions/day" → Response: "Could you elaborate on that in more detail?"
   - Problem: Same generic follow-up despite vastly different answer quality

2. Question: "Describe your most complex project"
   - Candidate answer: "Built real-time stock trading dashboard with React, WebSockets, PostgreSQL. Handled 1000s concurrent users with <100ms latency."
   - Classifier assessment: quality="SHORT" (due to word count heuristic, not semantic analysis)
   - System response: "Could you elaborate in more detail?"
   - Expected: "That's impressive latency. Tell me about your approach to real-time synchronization."
   - Problem: System doesn't understand answer demonstrated deep expertise; requests elaboration anyway

3. First follow-up gets same response as second follow-up because system doesn't track follow-up history or count

**Evidence from Code:**
- File: `app/services/groq_service.py` (fallback responses)
  ```python
  fallback_responses = {
      "short": "Could you elaborate on that in more detail?",
      "partial": "Good start. Can you expand on that point?",
      "negative": "That's honest. How do you see yourself adapting to this?",
      "irrelevant": "Let's refocus — could you address the original question?",
  }
  ```
  - All answers of same quality category get identical response
  - Responses are generic templates, not contextual

- File: `app/modules/interview/routers/interview_router.py` lines 570-620
  - Quality classification: quality in ["SHORT", "PARTIAL", "GOOD", "IRRELEVANT"]
  - Decision: IF quality == "SHORT" → action="FOLLOWUP", followup_type="elaborate"
  - Problem: No distinction between "brief but complete" vs "incomplete"
  - Problem: "missing_part" field exists but is ignored when generating response

- File: `app/services/groq_service.py` (classifier)
  ```python
  classification = {
      "quality": "PARTIAL",           # Surface-level categorization
      "intent": "POSITIVE",
      "missing_part": "deployment",   # This is extracted but never used!
      "content_score": 0.55           # 0-1 score exists
  }
  ```
  - Classifier extracts "missing_part" ("authentication", "scaling", "deployment", etc.)
  - This information is **completely ignored** in follow-up generation
  - Interviewer brain prompt does not receive or use this context

**Impact:**
- Candidates frustrated by repetitive questioning
- Brief but accurate answers marked as incomplete and requested to re-explain
- Expert candidates asked to elaborate on questions where they've already demonstrated deep knowledge
- Assessment quality suffers because follow-ups don't probe the actual gaps
- Follow-up sequence doesn't build toward deeper understanding; just repeats same request

### Issue 3: No Semantic Understanding of Answer Completeness

**Current Problem:**
- Answer classification uses word count thresholds and basic keyword matching
- System cannot differentiate:
  - "I used PostgreSQL" (1 phrase, domain expert's minimal but complete answer)
  - "I used PostgreSQL" (1 phrase, junior dev's incomplete answer who should elaborate)
  - "I've used PostgreSQL and MongoDB in production for 3 years, optimized queries..." (complete expert answer)
- System treats all via same rules; doesn't account for **domain knowledge**

**Example:**
- Question: "Tell me about your database experience"
- Domain Expert answer: "PostgreSQL and MongoDB" (8 words)
  - Actual quality: COMPLETE (expert can convey experience concisely)
  - Current system score: SHORT (word count < threshold)
  - Current behavior: Request elaboration unnecessarily
- Junior developer answer: "I've worked with databases" (5 words)
  - Actual quality: INCOMPLETE (vague, no specifics)
  - System score: SHORT (word count < threshold)
  - Current behavior: Request elaboration (correct, but for wrong reasons)

**Evidence:**
- No classifier documentation of how quality is determined
- Content_score exists but threshold for "complete" answer is not specified
- Missing_part field suggests classifier knows WHAT is missing, but system uses generic response templates instead

### Issue 4: Fallback Mechanism Loses All Personalization

**Current Problem:**
- When any error occurs (API failure, network timeout, invalid response), system falls back to hardcoded generic questions
- Fallback questions have **zero connection** to candidate's resume
- Fallback is indistinguishable from asking generic questions to every candidate

**Triggers for Fallback:**
1. Groq LLM extraction of resume fails → skills list is empty or incomplete
2. RAG retriever fails or returns minimal results → no relevant documents available
3. Groq question generation times out or returns invalid JSON
4. Network connectivity issues during question pool generation

**Example Impact:**
1. Candidate uploads resume PDF (complex formatting)
2. PyMuPDF + Groq extraction extracts: ["Python"] (should be ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "ML"])
3. RAG retriever finds 0 relevant documents (extraction was too minimal)
4. System falls back to: "Explain OOPS concepts", "What is the difference between...", "Describe your experience with databases"
5. Candidate with Kubernetes experience asked "What is the difference between..." (beginner-level)

**No Recovery Mechanism:**
- No validation that extraction was complete
- No retry logic if retrieval fails
- No graceful degradation that maintains partial personalization
- Fallback is all-or-nothing: either full personalization or zero personalization

---

## Defining Interview Question Personalization

Interview Question Personalization means each interview question must:

1. **Explicit Resume Grounding**: Question text must explicitly reference or relate to specific content from candidate's resume
   - ✅ "Tell me about your Django ORM design patterns" (references Django from resume)
   - ✅ "Describe a scaling challenge you faced with PostgreSQL" (references PostgreSQL from resume)
   - ❌ "What is HTTP?" (doesn't reference any resume content)
   - ❌ "Explain OOPS concepts" (generic, no resume connection)

2. **Difficulty Alignment**: Question difficulty must match candidate's experience level indicated in resume
   - ✅ Senior Python developer with 5+ projects → MEDIUM/HARD questions about advanced topics
   - ✅ Junior developer with 1 project → EASY/MEDIUM foundational questions
   - ❌ Senior developer asked "What is a database?"
   - ❌ Junior developer asked "Design a distributed transaction system"

3. **Skill-Based Targeting**: Question should probe skills candidate has explicitly claimed or demonstrated
   - ✅ Resume lists "PostgreSQL, optimization" → "Tell me about a query optimization challenge"
   - ✅ Resume lists "React, performance" → "How do you optimize React component rendering?"
   - ❌ Resume lists "DevOps" → Question about mobile app development
   - ❌ Resume lists "Python" → Question requires Rust knowledge

4. **Project Context**: Questions may reference or build upon specific projects mentioned in resume
   - ✅ Resume describes "E-commerce dashboard in React" → "How did you handle state management in your dashboard?"
   - ✅ Resume describes "ML recommendation engine" → "What were your main challenges building the recommendation model?"
   - ❌ Resume has no API experience → Detailed API design questions

5. **Continuity and Progression**: If multiple questions target same skill area, they should probe different depths or aspects
   - ✅ Question 1: "Tell me about your PostgreSQL experience" → Question 5: "Describe your approach to database indexing" (different aspects)
   - ❌ Question 1: "Tell me about PostgreSQL" → Question 5: "Tell me about PostgreSQL" (repetitive)

**Validation Criteria:**
- For each generated question, system must verify:
  - ✅ Question text contains at least one skill/project/technology from candidate's resume
  - ✅ Difficulty level matches candidate's experience level
  - ✅ If API/retrieval fails, graceful fallback must still maintain some personalization (use detected role + skills)
  - ❌ Generic fallback questions (no resume grounding) should never be presented without indicating they are fallback

---

## Defining Contextual Follow-up Questions

Contextual Follow-up Questions are follow-ups that:

1. **Reference Answer Content**: Follow-up explicitly acknowledges what the candidate said
   - ✅ Candidate: "I used PostgreSQL for scalability" → Follow-up: "Tell me about your scaling approach"
   - ✅ Candidate: "Handled race conditions with locks" → Follow-up: "How did you handle deadlock scenarios?"
   - ❌ "Could you elaborate?" (doesn't reference their answer)
   - ❌ "Tell me more" (generic, could apply to any answer)

2. **Address Specific Gaps**: Follow-up targets specific missing information identified in answer classification
   - ✅ Classification identifies missing: "deployment" → Follow-up: "How did you deploy this to production?"
   - ✅ Classification identifies missing: "testing" → Follow-up: "What was your testing strategy?"
   - ❌ "Can you expand on that?" (doesn't specify what gap to address)
   - ❌ "Could you say more?" (doesn't acknowledge classified missing aspect)

3. **Domain-Aware**: Follow-up demonstrates understanding of the domain/technology discussed
   - ✅ Question: "PostgreSQL experience?" → Candidate: "JSON operators, JSONB" → Follow-up: "How did you leverage JSONB performance advantages?"
   - ✅ Question: "React scaling?" → Candidate: "Code splitting, lazy loading" → Follow-up: "How did you handle the bundle size trade-offs?"
   - ❌ "Tell me more" (could be asked about any topic)
   - ❌ "Can you elaborate?" (no domain understanding)

4. **Respects Answer Completeness**: Follow-up is appropriate only when actual gap exists
   - ✅ Brief but complete answer "PostgreSQL, MongoDB" from expert → No follow-up needed (or minimal probe: "What made you choose MongoDB?")
   - ✅ Incomplete answer "I've used databases" → Follow-up: "Which specific databases have you used?"
   - ❌ Complete expert answer "I designed a schema handling 1M transactions/day with 99.9% uptime" → Follow-up: "Could you elaborate?" (inappropriate)

5. **Progressive Depth**: If multiple follow-ups occur for same question, they should probe progressively deeper aspects, not repeat the same question
   - ✅ First follow-up: "What was your main challenge?" → Second follow-up: "How did you solve that challenge?" (progression)
   - ❌ First follow-up: "Tell me more" → Second follow-up: "Could you elaborate?" (repetitive)

**Validation Criteria:**
- For each follow-up question, system must verify:
  - ✅ Follow-up explicitly references candidate's answer text or classified missing aspect
  - ✅ Follow-up is grammatically and contextually appropriate for the answer provided
  - ✅ Follow-up does not repeat same gap from previous follow-up (if this is 2nd+ follow-up)
  - ❌ Generic follow-ups should never be used (except during fallback recovery)
  - ✅ If follow-up generation fails, at minimum a minimally-personalized fallback is used

---

## Requirements

### Requirement 1: Resume Extraction Validation

**User Story:** As the interview system, I want to validate that resume parsing completed successfully and extracted sufficient skill/project data, so that I can ensure questions will have adequate resume context.

#### Acceptance Criteria

1. WHEN a candidate uploads a resume, THE Resume_Extraction_Service SHALL parse the resume using PyMuPDF and Groq LLM
2. WHEN extraction completes, THE Resume_Extraction_Service SHALL validate that at least 5 distinct skills were extracted
3. WHEN extraction completes, THE Resume_Extraction_Service SHALL validate that at least 2 projects were extracted with descriptions
4. WHEN extraction completes, THE Resume_Extraction_Service SHALL validate that detected role (Junior/Mid/Senior) matches experience level
5. IF any validation fails, THEN THE Resume_Extraction_Service SHALL log extraction quality issue with affected field
6. IF skills count < 3, THEN THE Resume_Extraction_Service SHALL attempt re-extraction using alternative parsing method
7. IF re-extraction still yields < 3 skills, THEN THE Resume_Extraction_Service SHALL proceed with extracted data and mark interview as "low-confidence personalization"
8. THE Resume_Extraction_Service SHALL store all extracted data (skills, projects, role) with the Interview_Session for use in question generation

### Requirement 2: Question Pool Personalization Validation

**User Story:** As the interview system, I want to validate that all generated interview questions are actually grounded in the candidate's resume, so that interviews test relevant skills.

#### Acceptance Criteria

1. WHEN a Question_Pool is generated, THE Question_Generator SHALL create 12 candidate questions using resume context
2. FOR EACH question in the generated pool, THE Question_Validator SHALL verify that question text contains at least one skill or project name from the candidate's resume
3. WHEN a question fails validation (no resume grounding detected), THE Question_Validator SHALL request regeneration of that question
4. THE Question_Generator SHALL mark each question with a personalization_source field indicating which resume skill/project it references
5. WHEN marking question personalization_source, THE system SHALL include:
   - Referenced skill name (e.g., "PostgreSQL", "React", "FastAPI")
   - Reference type: "skill", "project", or "technology"
   - Confidence score (0.0-1.0) indicating how strongly question is grounded
6. THE system SHALL only include questions in final pool with confidence score ≥ 0.75
7. IF after 2 regeneration attempts a question still fails validation, THE system SHALL replace it with a minimally-generic question marked as "fallback" with confidence score = 0.0
8. WHEN Question_Pool is finalized, THE system SHALL return pool only if at least 8 of 10 questions have confidence ≥ 0.75

### Requirement 3: Fallback Question Handling for Personalization Failures

**User Story:** As the interview system, I want graceful degradation when resume-personalized questions cannot be generated, so that interviews proceed even if personalization partially fails.

#### Acceptance Criteria

1. IF resume extraction yields insufficient skills (< 3), THEN THE Fallback_Manager SHALL still generate questions using detected role + available skills
2. THE Fallback_Manager SHALL create role-based semi-generic questions that reference available skills (e.g., "Tell me about your 3 years of Python experience")
3. IF RAG retrieval returns no relevant documents, THEN THE Fallback_Manager SHALL use role + skills to generate questions without document context
4. THE Fallback_Manager SHALL mark fallback questions with fallback_type field indicating reason (low_extraction_confidence, no_relevant_docs, api_failure)
5. THE system SHALL never use completely generic questions (e.g., "What is HTTP?") as fallback
6. IF all personalization attempts fail, THEN THE system SHALL present to candidate with warning: "This interview could not be personalized to your experience. Questions may not reflect your background."
7. IF complete failure occurs, THEN THE system SHALL generate questions based on detected role (Junior/Mid/Senior) with generic difficulty-appropriate questions
8. THE system SHALL log all fallback usages with reason and whether interview proceeded or was cancelled

### Requirement 4: Answer Classification with Domain Awareness

**User Story:** As the interview system, I want to classify candidate answers with understanding of domain expertise and completeness, so that follow-ups address actual gaps.

#### Acceptance Criteria

1. WHEN a candidate provides an answer, THE Answer_Classifier SHALL analyze answer text and classify into quality category
2. THE Answer_Classifier SHALL return classification object including:
   - quality: category (SHORT, PARTIAL, COMPLETE, EXCELLENT)
   - intent: engagement level (POSITIVE, NEGATIVE, NEUTRAL)
   - missing_aspects: list of specific missing areas (e.g., ["testing", "scaling", "security"])
   - content_score: numeric 0.0-1.0 assessment of answer quality
   - domain_markers: list of domain-specific keywords/patterns detected in answer
3. FOR TECHNICAL questions, THE Answer_Classifier SHALL consider domain_markers when assessing quality
4. WHEN an answer for database question contains specific technology references (e.g., "query optimization", "indexing", "schema design"), THE Answer_Classifier SHALL consider these as evidence of expertise even if answer is brief
5. WHEN an expert developer provides brief but complete answer, THE Answer_Classifier SHALL classify as COMPLETE (not SHORT)
6. WHEN an answer demonstrates specific domain knowledge (project examples, technical depth, architecture patterns), THE Answer_Classifier SHALL classify as EXCELLENT if content_score ≥ 0.85
7. THE Answer_Classifier SHALL identify specific missing_aspects from the classification, not generic "expand on this"
8. IF Answer_Classifier has low confidence (content_score ≤ 0.35), THE system SHALL mark answer as ambiguous and prepare fallback follow-up

### Requirement 5: Contextual Follow-up Generation

**User Story:** As the interview system, I want to generate follow-up questions that reference what the candidate actually said and address specific gaps, so that interviews feel like natural conversations.

#### Acceptance Criteria

1. WHEN an answer is classified and requires follow-up, THE Follow_Up_Generator SHALL receive:
   - Original question text
   - Candidate's answer text
   - Classification (quality, missing_aspects, content_score)
   - Candidate's resume context (skills, projects)
2. THE Follow_Up_Generator SHALL create follow-up question that explicitly references the candidate's answer or identified missing_aspect
3. THE Follow_Up_Generator SHALL use follow_up_type to determine question style:
   - FOR follow_up_type="clarification": Follow-up clarifies ambiguous answer (e.g., "Which databases specifically?")
   - FOR follow_up_type="depth_probe": Follow-up probes technical depth (e.g., "How did you handle the scaling challenge?")
   - FOR follow_up_type="error_recovery": Follow-up redirects after off-topic answer
4. WHEN missing_aspects list includes specific gaps (e.g., ["deployment", "monitoring"]), THE Follow_Up_Generator SHALL ask about first item: "How did you approach deployment?"
5. THE Follow_Up_Generator SHALL vary follow-up language based on answer content to avoid repetition
6. THE Follow_Up_Generator SHALL NOT generate generic follow-ups (never use: "Could you elaborate?", "Tell me more", "Can you explain further?")
7. WHEN follow_up_count > 1 for same question, THE Follow_Up_Generator SHALL probe different missing_aspect than previous follow-up
8. THE Follow_Up_Generator SHALL mark follow-up with validation_status field (high_confidence, low_confidence, fallback)

### Requirement 6: Follow-up Contextual Grounding Validation

**User Story:** As the interview system, I want to ensure follow-up questions are truly contextual, so that follow-ups feel appropriate and not generic.

#### Acceptance Criteria

1. WHEN a Follow_Up_Question is generated, THE Follow_Up_Validator SHALL verify that follow-up text contains:
   - At least one phrase from the candidate's answer, OR
   - At least one of the missing_aspects identified in classification
2. WHEN validation passes, THE Follow_Up_Validator SHALL assign grounding_score ≥ 0.75
3. WHEN validation fails (follow-up appears generic), THE Follow_Up_Validator SHALL request regeneration
4. IF after 1 regeneration attempt follow-up is still generic, THE Follow_Up_Validator SHALL use a minimally-contextual fallback that references the question + missing_aspect (e.g., "You mentioned [aspect]. Can you elaborate on that?")
5. THE Follow_Up_Validator SHALL track grounding_score for all follow-ups and calculate average for interview session
6. IF average grounding_score < 0.65 for interview session, THE system SHALL flag interview as "low quality follow-ups" for review
7. THE Follow_Up_Validator SHALL never permit completely generic follow-ups as final follow-up (fallback minimum is "minimally contextual")

### Requirement 7: Follow-up Repetition Prevention

**User Story:** As the interview system, I want to prevent asking the same follow-up question twice or addressing same gap repeatedly, so that candidates aren't frustrated by repetitive questioning.

#### Acceptance Criteria

1. WHEN generating a 2nd or 3rd follow-up for same original question, THE Follow_Up_Generator SHALL track previously asked follow-ups
2. THE Follow_Up_Generator SHALL NOT generate follow-up that addresses same missing_aspect as previous follow-up
3. WHEN candidate has already provided answer to specific missing_aspect, THE system SHALL mark that aspect as "addressed" and select different aspect for next follow-up
4. THE system SHALL limit follow-ups per question to maximum 2 additional follow-ups (3 total Q&A turns: original question + up to 2 follow-ups)
5. WHEN maximum follow-ups reached (2 follow-ups completed), THE system SHALL automatically move to next question regardless of answer quality
6. THE system SHALL track follow-up history per Interview_Session and prevent asking same follow-up phrasing across different questions (within same interview)

### Requirement 8: Resume-Grounded Fallback Questions

**User Story:** As the interview system, I want fallback questions to maintain some resume grounding even when primary generation fails, so that incomplete personalization is better than no personalization.

#### Acceptance Criteria

1. WHEN question generation fails and fallback is needed, THE Fallback_Generator SHALL still use resume context (skills, projects, role)
2. THE Fallback_Generator SHALL generate questions in format: "Tell me about your [SKILL_FROM_RESUME] experience" or "Describe [PROJECT_FROM_RESUME] in more detail"
3. WHEN multiple skills are available, THE Fallback_Generator SHALL select skill based on:
   - Frequency of mention in resume (most frequently mentioned first)
   - Mapping to question difficulty level
4. THE Fallback_Generator SHALL never use generic question templates (e.g., "What is X?", "Explain OOPS")
5. WHEN resume has insufficient information (< 3 skills), THE Fallback_Generator SHALL use role-based questions: "As a [detected_role] developer, describe your approach to [common_area]"
6. ALL fallback questions SHALL be marked with fallback=true and fallback_reason field (e.g., "no_relevant_docs", "api_failure", "low_extraction_confidence")
7. WHEN interview report is generated, fallback questions SHALL be noted with lower reliability score (0.5-0.7 range vs 0.8-1.0 for personalized)

### Requirement 9: Question Generation Error Recovery

**User Story:** As the interview system, I want to recover gracefully from question generation failures, so that interviews can proceed even with API errors or timeouts.

#### Acceptance Criteria

1. IF Groq LLM times out during question generation, THE Question_Generator SHALL retry up to 2 times with exponential backoff (1s, 2s)
2. IF all retries fail, THE Question_Generator SHALL fall back to fallback question generation using available resume context
3. IF RAG retrieval returns no relevant documents, THE Question_Generator SHALL proceed with question generation using only resume context (skills, projects)
4. THE system SHALL log all retries and failures with timestamps and error details
5. WHEN RAG retrieval returns < 3 documents, THE system SHALL still proceed (minimum threshold: use whatever context is available)
6. WHEN question generation completes with partial failure (some questions fallback, others personalized), THE system SHALL return mixed pool with confidence scores per question
7. THE system SHALL document in Interview_Session metadata:
   - extraction_confidence: (high/medium/low) based on skills/projects extracted
   - retrieval_success_rate: (% of skills that found relevant docs)
   - question_personalization_rate: (% of final pool with confidence ≥ 0.75)

### Requirement 10: Answer Classification Confidence and Fallback

**User Story:** As the interview system, I want to handle low-confidence answer classifications, so that follow-ups are not generated for ambiguous answers.

#### Acceptance Criteria

1. WHEN an answer is classified with low confidence (content_score < 0.35), THE Answer_Classifier SHALL mark classification as ambiguous
2. WHEN classification confidence is low, THE Follow_Up_Generator SHALL generate "error_recovery" type follow-up instead of depth probe
3. THE error_recovery follow-up SHALL restate the original question: "Let me rephrase: [ORIGINAL_QUESTION]. Can you provide more specific details?"
4. WHEN classification confidence is high (content_score ≥ 0.75), THE Follow_Up_Generator SHALL generate contextual follow-up immediately
5. WHEN classification confidence is medium (0.35-0.75), THE Follow_Up_Generator SHALL generate follow-up with low_confidence flag but still contextual
6. THE system SHALL track classification confidence for all answers in Interview_Session
7. WHEN average classification confidence < 0.50 for session, THE system SHALL flag session for manual review (possible transcription quality issue)

### Requirement 11: Interview Session Metadata for Quality Assessment

**User Story:** As the interview system and administrators, I want detailed metadata about how personalization and contextual follow-ups performed during each interview, so that quality issues can be identified and improved.

#### Acceptance Criteria

1. WHEN an Interview_Session begins, THE system SHALL initialize metadata object including:
   - extraction_confidence (high/medium/low)
   - retrieval_success_rate (% of skills with relevant docs)
   - question_personalization_rate (% of pool with confidence ≥ 0.75)
   - questions_with_fallback (count)
2. DURING interview, THE system SHALL track for each question:
   - original_question_personalization_score (0.0-1.0)
   - answer_classification_confidence (0.0-1.0)
   - follow_up_count (0-2)
   - follow_up_grounding_scores (list of scores per follow-up)
3. AT end of interview, THE system SHALL calculate:
   - average_follow_up_grounding (mean of all follow_up_grounding_scores)
   - personalization_quality_score (overall 0.0-1.0 score)
   - follow_up_quality_score (0.0-1.0 score based on contextual grounding)
4. WHEN storing Interview_Session, THE system SHALL persist this metadata to database for later analysis
5. THE system SHALL expose metadata in interview report for display to administrators
6. WHEN personalization_quality_score < 0.60, interview SHALL be marked with warning: "This interview had limited personalization"
7. WHEN follow_up_quality_score < 0.60, interview SHALL be marked with warning: "Follow-up questions were less contextual than expected"

### Requirement 12: Backward Compatibility with Existing System

**User Story:** As the interview system, I want new personalization and contextual follow-up features to coexist with existing interviewer logic, so that system remains stable during implementation.

#### Acceptance Criteria

1. THE new follow-up generation SHALL be used in place of existing hardcoded _brain_fallback() responses
2. THE existing Interview_Turn, Interview_Session, and Interview_Round schemas SHALL remain unchanged (new fields added as optional)
3. WHEN legacy interview data is retrieved, THE system SHALL handle missing personalization_source fields gracefully
4. THE question generation pipeline SHALL produce compatible output format with existing system
5. ALL existing interview functionality (timer, recording, proctoring) SHALL continue working without modification
6. THE system SHALL not break existing reports or analytics that rely on Interview_Turn or Interview_Session data
7. WHEN new metadata fields are added to Interview_Session, existing sessions SHALL continue to function with nullable/default values

---

## Acceptance Criteria Summary

### Core Feature 1: Question Personalization
- ✅ All questions validated to reference resume content (confidence ≥ 0.75)
- ✅ Questions difficulty matches candidate experience level
- ✅ Fallback questions still grounded in extracted skills/role
- ✅ System tracks personalization metrics (extraction confidence, retrieval success rate, question personalization rate)

### Core Feature 2: Contextual Follow-ups
- ✅ All follow-ups reference candidate's answer or identified gaps (grounding score ≥ 0.75)
- ✅ No generic follow-ups ("Could you elaborate?")
- ✅ Follow-ups address different gaps (no repetition)
- ✅ Maximum 2 follow-ups per original question
- ✅ System tracks contextual grounding metrics per interview

### Quality Assurance
- ✅ Graceful degradation when APIs fail or extraction is incomplete
- ✅ Interview can proceed even with partial personalization
- ✅ Metadata tracked for all interviews (personalization quality, follow-up quality)
- ✅ Low-quality sessions flagged for review

### Backward Compatibility
- ✅ Existing schemas remain compatible
- ✅ Existing interview features unaffected
- ✅ Existing reports work with new optional fields

---

## Testing Strategy

### Unit-Level Validation (Examples)
- Verify question contains skill from resume
- Verify answer classification identifies missing aspects
- Verify follow-up addresses identified missing aspect
- Verify fallback question still references a skill

### Property-Based Validation (Universal Properties)
- For any candidate resume, all generated questions must reference at least one resume skill or project
- For any answer, if follow-up is generated, follow-up text must contain word(s) from answer or identified missing aspect
- For any two follow-ups for same question, they must not address identical missing_aspects
- For any personalized question, grounding_score must be ≥ 0.75 or question must be marked as fallback
- For any candidate resume with sufficient skills (≥3), question pool personalization rate must be ≥ 0.75

### Integration Testing
- Full interview flow with various resume inputs (rich profile, minimal profile, missing fields)
- Follow-up generation across multiple turns per question
- Error scenarios: API failures, extraction failures, retrieval failures
- Fallback question usage and graceful degradation

