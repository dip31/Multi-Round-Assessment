# Design Document: Interview Question Personalization and Contextual Follow-ups

## Overview

This document specifies the technical design for ensuring interview questions are grounded in candidate resume content and follow-up questions are contextually relevant to candidate answers. The system achieves this through:

1. **Resume Extraction Validation Pipeline**: Validates extracted skills/projects are sufficient before proceeding with question generation
2. **Question Personalization Validator**: Verifies each generated question references resume content with confidence scoring
3. **Domain-Aware Answer Classification**: Understands domain expertise to assess answer completeness appropriately
4. **Contextual Follow-up Generator**: Creates follow-ups that reference candidate answers and identified gaps
5. **Metadata & Monitoring**: Tracks personalization and contextual grounding quality for all interviews

The design prioritizes robustness through graceful degradation: if personalization fully fails, interviews proceed with role-based fallback questions while maintaining system stability.

---

## Architecture

### High-Level Components

```
Resume Extraction & Validation
    ↓ (extracts skills, projects, role)
    ↓
Question Pool Generation
    ↓ (creates 12 candidate questions with resume context)
    ↓
Question Personalization Validator
    ↓ (validates each question references resume; regenerates if needed)
    ↓
Question Pool Finalization
    ↓ (returns 10 questions with personalization_source and confidence_score)
    ↓
Interview Execution
    ├─ Candidate Answer → Answer Classifier
    │   ├─ Analyzes for quality, missing_aspects, content_score
    │   ├─ Considers domain markers
    │   ↓
    └─ Follow-up Decision
        ├─ IF quality < threshold → generate contextual follow-up
        ├─ Contextual Follow-up Generator
        │   ├─ References answer text or missing_aspects
        │   ├─ Validates grounding (confidence ≥ 0.75)
        │   ├─ Prevents repetition from prior follow-ups
        │   ↓
        └─ Follow-up Validator → Interview Execution continues
```

### System Boundaries

**In Scope:**
- Resume extraction validation (min skills/projects extracted)
- Question personalization validation (each Q references resume)
- Answer classification with domain awareness
- Contextual follow-up generation
- Fallback handling (graceful degradation)
- Metadata tracking (personalization quality, follow-up quality)

**Out of Scope (Existing System):**
- Resume file upload/parsing mechanics (PyMuPDF, Groq extraction)
- Audio recording and transcription (existing)
- Question pool ranking/selection (existing interview flow)
- Interviewer UI/UX (existing components)
- Timer and recording controls (existing)
- Proctoring (separate feature)

---

## Components and Interfaces

### 1. Resume Extraction Validator

**Purpose**: Validate that resume parsing extracted sufficient skill and project data.

**Input**:
```python
{
    "interview_id": int,
    "extracted_skills": List[str],  # e.g., ["Python", "Django", "PostgreSQL"]
    "extracted_projects": List[Dict],  # [{"name": str, "description": str}]
    "detected_role": Literal["JUNIOR", "MID", "SENIOR"],
    "extraction_method": str  # "pymudf+groq" etc.
}
```

**Output**:
```python
{
    "is_valid": bool,
    "extraction_confidence": Literal["HIGH", "MEDIUM", "LOW"],
    "skills_count": int,
    "projects_count": int,
    "issues": List[str],  # ["too_few_skills", "no_projects", etc.]
    "recommendation": Literal["PROCEED", "RETRY", "FALLBACK_MODE"],
    "metadata": {
        "validation_timestamp": datetime,
        "retry_count": int,
        "alternative_extraction_attempted": bool
    }
}
```

**Algorithm**:
1. Count distinct skills extracted (≥5 for HIGH, ≥3 for MEDIUM, <3 for LOW)
2. Count projects with non-empty description (≥2 for HIGH, ≥1 for MEDIUM)
3. Validate detected_role alignment with years of experience (if available)
4. If confidence is MEDIUM or LOW, attempt alternative extraction method
5. Return confidence level and recommendation

**Error Handling**:
- If skills < 3 after retry: proceed with MEDIUM confidence, note in metadata
- If skills < 1: proceed with LOW confidence, note in metadata
- System continues regardless; confidence level informs follow-up strategy

---

### 2. Question Personalization Validator

**Purpose**: Verify each generated interview question is grounded in candidate's resume and assign confidence score.

**Input**:
```python
{
    "question_id": int,
    "question_text": str,  # "Tell me about your Django ORM design patterns"
    "candidate_skills": List[str],  # ["Python", "Django", "PostgreSQL", ...]
    "candidate_projects": List[Dict],  # [{"name": str, "description": str}, ...]
    "detected_role": str,
    "question_source": str  # "rag_generated" or "fallback"
}
```

**Output**:
```python
{
    "is_valid": bool,
    "grounding_confidence_score": float,  # 0.0-1.0
    "personalization_source": {
        "skill": Optional[str],  # e.g., "Django"
        "project": Optional[str],  # e.g., "E-commerce platform"
        "reference_type": Literal["skill", "project", "role"],
        "matching_evidence": str  # e.g., "question contains 'Django' which is in skills"
    },
    "recommendation": Literal["ACCEPT", "REGENERATE", "FALLBACK"],
    "regeneration_attempt": int
}
```

**Algorithm**:
1. Tokenize question text and candidate skills/projects
2. Check for exact matches or semantic similarity (token overlap ≥ 1 token)
3. For each skill/project in candidate's resume, check if mentioned in question text
4. Assign grounding_confidence_score:
   - Exact skill/project name mentioned: 0.85-1.0
   - Semantic similarity (related to skill): 0.65-0.85
   - Role-based reference only (no specific skill): 0.40-0.65
   - No resume grounding: 0.0-0.40
5. If score < 0.75: return recommendation=REGENERATE
6. If score < 0.40: return recommendation=FALLBACK

**Validation Rules**:
- Never accept generic questions ("What is...", "Explain...", "Describe the difference between...") without explicit resume reference
- Accept skill-specific questions: "Tell me about your Django experience"
- Accept project-specific: "Describe how you handled performance in your E-commerce platform"
- Reject generic questions with no resume grounding

**Error Handling**:
- If regeneration fails 2x: accept fallback (grounding_confidence_score = 0.5-0.7)
- Track all regeneration attempts in metadata

---

### 3. Answer Classifier with Domain Awareness

**Purpose**: Classify candidate answers with understanding of domain expertise and actual completeness.

**Input**:
```python
{
    "answer_id": int,
    "answer_text": str,  # Transcribed candidate answer
    "original_question": str,
    "question_domain": Literal["DATABASE", "FRONTEND", "BACKEND", "DEVOPS", "GENERAL"],
    "candidate_skills": List[str],  # Resume skills for domain context
    "prior_classification": Optional[Dict]  # For follow-up turns
}
```

**Output**:
```python
{
    "quality": Literal["SHORT", "PARTIAL", "COMPLETE", "EXCELLENT"],
    "intent": Literal["POSITIVE", "NEGATIVE", "NEUTRAL"],
    "content_score": float,  # 0.0-1.0 detailed assessment
    "confidence": float,  # 0.0-1.0 classifier confidence in this assessment
    "missing_aspects": List[str],  # ["testing", "deployment", "scaling"]
    "domain_markers": List[str],  # ["query optimization", "indexing", "schema design"]
    "depth_indicators": Dict,  # {"mentions_specifics": bool, "technical_depth": int}
    "fallback_followup_type": Literal["elaboration", "clarification", "depth_probe", "error_recovery"],
    "reasoning": str  # Explanation for classification
}
```

**Quality Classification Rules**:

1. **EXCELLENT** (content_score ≥ 0.85):
   - Answer demonstrates specific expertise with technical depth
   - Contains project examples or architectural patterns
   - Shows problem-solving approach or lessons learned
   - Any length (expert can convey knowledge concisely)

2. **COMPLETE** (content_score 0.65-0.84):
   - Answer directly addresses question with specifics
   - Contains 1-2 domain-relevant details
   - May be brief but shows understanding
   - Junior developer with specific technologies: "PostgreSQL and MongoDB in production"
   - Senior developer: "I've optimized queries using indexes and EXPLAIN ANALYZE"

3. **PARTIAL** (content_score 0.35-0.64):
   - Answer addresses question but lacks depth or specifics
   - "I've used databases" (no specific types, no details)
   - "Backend is important" (vague, no technical content)
   - Contains general statements without examples

4. **SHORT** (content_score < 0.35):
   - Answer is too brief or off-topic
   - "Yeah" or "I don't know" or no substantial content
   - Doesn't address the question
   - Ambiguous or unclear response

**Domain-Aware Assessment**:

```
Domain: DATABASE
Question: "Tell me about your database experience"
Answer: "PostgreSQL and MongoDB"

Domain Markers Detected: ["PostgreSQL", "MongoDB", "databases"]
Prior Answers This Interview: [(q1_domain=DATABASE, quality=COMPLETE, ...)]

Assessment:
- Brevity alone: would score SHORT (2 words)
- Domain markers: Found 2 specific technologies
- Candidate role: Senior (from resume)
- With domain awareness:
  - If answer = "PostgreSQL and MongoDB" from Senior dev → COMPLETE (expert communicates concisely)
  - If answer = "PostgreSQL and MongoDB" from Junior dev → PARTIAL (needs more detail on usage)
- Result: quality = COMPLETE (when context is Senior developer)
```

**Missing Aspects Extraction**:
- For DATABASE questions: Extract missing from [testing, scaling, optimization, replication, transactions, security]
- For FRONTEND questions: Extract missing from [performance, testing, accessibility, state_management, error_handling]
- For BACKEND questions: Extract missing from [error_handling, testing, monitoring, deployment, security]
- Use LLM to identify specific gaps from answer text

**Error Handling**:
- If classification confidence < 0.35: mark as "ambiguous", use error_recovery fallback follow-up
- If classification confidence 0.35-0.75: proceed with low_confidence flag
- If classification confidence ≥ 0.75: proceed normally

---

### 4. Contextual Follow-up Generator

**Purpose**: Generate follow-up questions that reference candidate answers and identified gaps without repetition.

**Input**:
```python
{
    "followup_id": int,
    "followup_count": int,  # 1st or 2nd follow-up (0-based)
    "original_question": str,
    "candidate_answer": str,
    "answer_classification": {
        "quality": str,
        "missing_aspects": List[str],
        "domain_markers": List[str],
        "content_score": float
    },
    "candidate_skills": List[str],
    "candidate_projects": List[Dict],
    "prior_followups": List[str],  # Previous follow-up questions asked
    "prior_missing_aspects_addressed": List[str]  # Gaps already explored
}
```

**Output**:
```python
{
    "followup_question": str,
    "followup_type": Literal["clarification", "depth_probe", "error_recovery"],
    "grounding_score": float,  # 0.0-1.0 how contextual this follow-up is
    "grounding_evidence": str,  # Explanation of why this is contextual
    "targeted_missing_aspect": str,  # Which gap this addresses
    "validation_status": Literal["high_confidence", "low_confidence", "fallback"],
    "includes_answer_reference": bool,
    "includes_gap_reference": bool
}
```

**Generation Algorithm**:

**Step 1: Determine Follow-up Type**
```
IF answer_classification.quality == "SHORT" AND confidence < 0.35:
    → follow_up_type = "error_recovery"  # Restate question
ELIF answer_classification.quality == "SHORT":
    → follow_up_type = "clarification"  # Seek specific details
ELIF answer_classification.missing_aspects not empty:
    → follow_up_type = "depth_probe"  # Probe identified gaps
ELSE:
    → no follow-up needed
```

**Step 2: Select Missing Aspect to Address**
```
IF followup_count == 0:
    # First follow-up: use first missing aspect
    targeted_aspect = answer_classification.missing_aspects[0]
ELIF followup_count == 1:
    # Second follow-up: use different aspect
    addressed_so_far = prior_missing_aspects_addressed + [first_followup_targeted_aspect]
    remaining_aspects = [a for a in missing_aspects if a not in addressed_so_far]
    targeted_aspect = remaining_aspects[0] if remaining_aspects else None
    IF targeted_aspect is None:
        # No new aspects to address → Don't ask follow-up (or ask elaboration on same aspect)
        return None  # Stop following up
```

**Step 3: Generate Contextual Follow-up**

**For type=clarification** (Seeking specifics):
- Template: "[Reference from answer]. [Question about missing aspect]?"
- Example: "You mentioned PostgreSQL. Which specific performance optimizations did you implement?"
- Must include word(s) from candidate_answer

**For type=depth_probe** (Explore gap):
- Template: "[Gap name]. How did you approach [gap]?"
- Example: "You didn't mention testing. What was your testing strategy for this feature?"
- Must reference targeted_missing_aspect

**For type=error_recovery** (Restate):
- Template: "Let me rephrase the question. [Original question]. Can you provide more details?"
- Used only when classification confidence is very low

**Step 4: Validate Grounding**
```
grounding_score = 0.0
IF follow_up_question contains word(s) from candidate_answer:
    grounding_score += 0.5  # Directly references answer
IF follow_up_question contains or references targeted_missing_aspect:
    grounding_score += 0.3  # Addresses identified gap
IF follow_up_question uses domain-appropriate language:
    grounding_score += 0.2  # Professional phrasing

IF grounding_score >= 0.75:
    validation_status = "high_confidence"
ELIF grounding_score >= 0.50:
    validation_status = "low_confidence"
ELSE:
    validation_status = "fallback"
    # Use minimal contextual fallback: "You mentioned [gap]. Can you tell me more about that?"
```

**Repetition Prevention**:
```
FOR each prior_followup in prior_followups:
    IF prior_followup addresses same missing_aspect:
        → Don't ask this follow-up
        → Select different aspect OR stop following up
```

**Error Handling**:
- If LLM generation times out: use template-based fallback (minimal contextual)
- If generated follow-up appears generic: regenerate up to 1x, then use template fallback
- Never allow completely generic follow-up as final answer

---

### 5. Fallback Question Generator

**Purpose**: Generate semi-personalized fallback questions when primary generation fails.

**Input**:
```python
{
    "fallback_reason": Literal["low_extraction_confidence", "no_relevant_docs", "api_failure", "all_aspects_covered"],
    "candidate_skills": List[str],
    "candidate_projects": List[Dict],
    "detected_role": str,
    "extraction_confidence": Literal["HIGH", "MEDIUM", "LOW"],
    "question_count_needed": int,  # How many fallback questions to generate
    "question_difficulties": List[str]  # ["EASY", "MEDIUM", "MEDIUM", "HARD", ...]
}
```

**Output**:
```python
{
    "fallback_questions": List[{
        "question_text": str,
        "difficulty": str,
        "fallback_reason": str,
        "personalization_source": str,  # Skill or project referenced
        "grounding_confidence_score": float,  # 0.5-0.7 range
        "is_fallback": bool = True
    }]
}
```

**Generation Rules**:

1. **High Extraction Confidence + No Relevant Docs**:
   ```
   template = "Tell me about your experience with [SKILL_FROM_RESUME]"
   select_skill_by = frequency_in_resume
   → "Tell me about your experience with Django"
   → confidence = 0.75
   ```

2. **Medium Extraction Confidence**:
   ```
   template = "As a [DETECTED_ROLE] developer, how have you approached [SKILL]?"
   → "As a Mid-level developer, how have you approached database optimization?"
   → confidence = 0.60
   ```

3. **Low Extraction Confidence**:
   ```
   template = "Tell me about your approach to [COMMON_AREA_FOR_ROLE]"
   common_areas = {
       JUNIOR: ["learning new technologies", "debugging issues"],
       MID: ["system design", "code review"],
       SENIOR: ["architectural decisions", "mentoring"]
   }
   → "Tell me about your approach to system design"
   → confidence = 0.50
   ```

4. **Project-Based Fallback** (if projects extracted):
   ```
   template = "Describe [PROJECT_NAME] in more detail. What was your role?"
   → "Describe the E-commerce dashboard in more detail. What was your role?"
   → confidence = 0.70
   ```

**Never Use** (forbidden templates):
- "What is X?"
- "Explain OOPS concepts"
- "What is the difference between X and Y?"
- "Describe the process of..."
- Any completely generic question

---

### 6. Interview Metadata Tracker

**Purpose**: Track personalization and contextual grounding quality metrics throughout interview session.

**Data Structure**:
```python
{
    "interview_id": int,
    "extraction_metadata": {
        "extraction_confidence": str,  # HIGH/MEDIUM/LOW
        "skills_count": int,
        "projects_count": int,
        "issues": List[str],
        "alternative_extraction_attempted": bool
    },
    "question_pool_metadata": {
        "retrieval_success_rate": float,  # % of skills with relevant docs
        "question_personalization_rate": float,  # % with grounding_confidence >= 0.75
        "questions_with_fallback": int,
        "average_grounding_confidence": float
    },
    "per_question_metrics": [
        {
            "question_number": int,
            "question_text": str,
            "personalization_source": str,
            "grounding_confidence": float,
            "answer_quality": str,
            "answer_classification_confidence": float,
            "missing_aspects": List[str],
            "followups": [
                {
                    "followup_number": int,
                    "followup_text": str,
                    "followup_type": str,
                    "grounding_score": float,
                    "targeted_aspect": str
                }
            ],
            "average_followup_grounding": float
        }
    ],
    "interview_summary": {
        "total_questions": int,
        "total_followups": int,
        "average_followup_grounding": float,
        "personalization_quality_score": float,  # 0.0-1.0
        "follow_up_quality_score": float,  # 0.0-1.0
        "warnings": List[str]  # ["limited_personalization", "low_follow_up_quality"]
    }
}
```

**Calculation Formulas**:

```
personalization_quality_score = (
    extraction_confidence_weight * extraction_confidence_numeric +
    question_personalization_rate * 0.8 +
    average_question_grounding_confidence * 0.6
) / 3
Range: 0.0-1.0, where 0.6+ is acceptable

follow_up_quality_score = average_followup_grounding / 1.0
Range: 0.0-1.0, where 0.65+ is acceptable

Warnings Trigger:
- IF personalization_quality_score < 0.60: "limited_personalization"
- IF follow_up_quality_score < 0.60: "low_follow_up_quality"
```

---

## Data Models

### Database Extensions

**New Fields on InterviewSession**:
```python
extraction_confidence: Enum[HIGH, MEDIUM, LOW]  # Extraction quality
retrieval_success_rate: Float (0.0-1.0)  # % of skills with relevant docs
question_personalization_rate: Float (0.0-1.0)  # % of Q pool personalized
personalization_metadata: JSON  # Full tracking data
follow_up_quality_score: Float (0.0-1.0)  # Overall follow-up contextual grounding
personalization_warnings: List[str]  # ["limited_personalization", ...]
```

**New Fields on InterviewTurn**:
```python
personalization_source: Optional[String]  # Which skill/project this Q targets
question_grounding_confidence: Optional[Float]  # 0.0-1.0
answer_classification: JSON  # Full classification with missing_aspects
followup_grounding_score: Optional[Float]  # For follow-up turns
followup_targeted_aspect: Optional[String]  # What gap this follow-up addresses
```

**Note**: All new fields are `nullable` for backward compatibility with existing sessions.

---

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: All Interview Questions Must Reference Resume Content

**Validates: Requirements 1, 2**

For any candidate interview session with valid resume context (≥3 skills extracted), every question in the final question pool must either:
- Contain exact mention of a skill/project from the resume, OR
- Be marked as fallback with a personalization_source referencing a skill/project

Testing approach: Generate question pools for candidates with varying resume richness (3 skills, 5 skills, 10 skills). Verify each question contains ≥1 resume reference or is marked fallback. Check that grounding_confidence_score ≥ 0.75 for non-fallback questions.

### Property 2: All Follow-ups Must Reference Answer Content or Identified Gaps

**Validates: Requirements 5, 6**

For any follow-up question generated during an interview, the follow-up text must contain either:
- Word(s) from the candidate's answer text, OR
- Explicit reference to a missing_aspect identified in answer classification

Testing approach: Generate follow-ups for various answer classifications (SHORT, PARTIAL, COMPLETE, EXCELLENT). Verify each follow-up contains answer references or gap references. Measure grounding_score; expect ≥0.75 for high_confidence, ≥0.50 for low_confidence.

### Property 3: No Follow-up Addresses Same Gap Twice in Sequence

**Validates: Requirement 7**

For any two consecutive follow-ups for the same original question, the targeted_missing_aspect must be different between them.

Testing approach: Simulate interviews with multiple follow-ups per question. For each question with 2+ follow-ups, verify targeted_aspect differs. Count violations; expect zero.

### Property 4: Fallback Questions Still Reference Extracted Skills or Role

**Validates: Requirement 8**

When fallback questions are generated (extraction_confidence < HIGH or no relevant docs), every fallback question must still reference either:
- A skill from the extracted skills list, OR
- The detected_role in the question phrasing

Testing approach: Trigger fallback scenarios (force low extraction confidence, block RAG retrieval). Verify fallback questions contain skill references or role references. No completely generic questions like "What is X?" should appear.

### Property 5: Answer Classification Correctly Distinguishes Expert Brief Answers from Incomplete Answers

**Validates: Requirement 4**

For any answer classified as COMPLETE or EXCELLENT, the average interview score for that interview session should be consistent with the candidate's resume-indicated experience level. Expert candidates who provide brief answers should not be penalized compared to experts providing verbose answers.

Testing approach: Create test candidates with clear seniority levels in resume. Run through answer classification algorithm. Compare final interview scores across seniority levels. Expect: similar scores for experts regardless of verbosity, with COMPLETE/EXCELLENT classifications treating brevity appropriately.

### Property 6: Metadata Quality Scores Correlate with Interview Quality

**Validates: Requirement 11**

For any completed interview session, the personalization_quality_score should be:
- ≥0.75 when extraction_confidence=HIGH and question_personalization_rate ≥ 0.80
- 0.50-0.75 when extraction_confidence=MEDIUM or question_personalization_rate = 0.60-0.80
- ≤0.60 when extraction_confidence=LOW or question_personalization_rate < 0.60

Testing approach: Run interviews with varying extraction/question quality. Calculate personalization_quality_score. Verify score ranges align with expected quality levels. Check that warnings are correctly triggered when scores fall below thresholds.

### Property 7: Graceful Degradation Maintains Interview Continuity

**Validates: Requirements 3, 9**

When resume extraction fails, RAG retrieval fails, or question generation times out, the interview should continue with fallback questions and completion should not be blocked.

Testing approach: Simulate various failures at each stage (extraction, retrieval, generation). For each failure, verify:
1. Interview does not crash or return error to user
2. Fallback mechanism activates
3. Interview proceeds with reduced-confidence questions
4. metadata.warnings correctly indicates degradation
5. Interview reaches completion successfully

### Property 8: Follow-up Repetition Prevention Works Across Multiple Turns

**Validates: Requirement 7**

For any interview session with multiple questions, no two follow-up questions across the entire session should ask about the exact same topic/gap (e.g., two different questions should not both have follow-ups about "testing").

Testing approach: Run complete multi-turn interviews. Extract targeted_aspects from all follow-up turns. Verify that duplicate missing_aspects across different original questions are minimized. Count violations.

---

## Error Handling

### Extraction Validation Failures
- **Low extraction confidence (< 3 skills)**: Proceed with metadata flag, use fewer skills for question generation
- **No projects extracted**: Proceed with skill-only targeting
- **Recovery**: Offer to retry extraction with alternative parser; continue regardless

### Question Validation Failures
- **Generated question not grounded**: Retry generation up to 2x
- **After 2 retries, still not grounded**: Use fallback question (grounding_confidence = 0.5-0.7)
- **Max retries exceeded**: Still include in pool with low confidence; flag in metadata

### Answer Classification Ambiguity
- **Classification confidence < 0.35**: Use error_recovery follow-up type (restate question)
- **Classification confidence 0.35-0.75**: Proceed with low_confidence flag; still generate contextual follow-up
- **Classification confidence ≥ 0.75**: Proceed normally

### Follow-up Generation Failures
- **LLM timeout during generation**: Use template-based fallback
- **Generated follow-up detected as generic**: Regenerate up to 1x
- **After regeneration, still generic**: Use minimal contextual fallback: "You mentioned [aspect]. Can you elaborate?"

### API Failures (Groq, Sarvam, etc.)
- **First call fails**: Retry up to 2x with exponential backoff (1s, 2s)
- **All retries fail**: Fall back to role-based or skill-based fallback
- **Continue interview**: System proceeds even if personalization is degraded

### Database Write Failures (Metadata)
- **Metadata save fails**: Log error, continue interview
- **On next successful write**: Include backlog of metadata
- **Never block interview on metadata save**

---

## Testing Strategy

### Unit Tests

**Question Personalization Validator**:
- Test exact skill match detection
- Test semantic similarity detection
- Test role-based reference detection
- Test score calculation and threshold behavior
- Test regeneration retry logic

**Answer Classifier**:
- Test domain-aware assessment (expert brief answer vs junior brief answer)
- Test quality category assignment
- Test missing aspect extraction
- Test domain marker detection
- Test confidence calculation

**Contextual Follow-up Generator**:
- Test follow-up type selection based on answer quality
- Test missing aspect targeting
- Test repetition prevention
- Test grounding score calculation
- Test template fallback

**Fallback Question Generator**:
- Test skill-based fallback questions
- Test role-based fallback questions
- Test project-based fallback questions
- Test that generic templates are never used

**Interview Metadata Tracker**:
- Test score calculations
- Test warning triggers
- Test metadata persistence
- Test backward compatibility

### Property-Based Tests

**Property 1: All questions reference resume content**
- Generate random resumes with 3-10 skills, 1-5 projects
- Generate question pools for each resume
- Verify each question contains resume reference or is marked fallback

**Property 2: All follow-ups reference answers or gaps**
- Generate random answer classifications
- Generate contextual follow-ups
- Verify follow-up references answer content or missing_aspect
- Test grounding_score ≥ 0.75 for high_confidence

**Property 3: No duplicate gaps in consecutive follow-ups**
- Simulate interviews with multiple follow-ups per question
- For each pair of consecutive follow-ups, verify different targeted_aspects
- Count violations; expect 0

**Property 4: Fallback questions maintain personalization**
- Trigger fallback scenarios (low extraction, no docs, timeouts)
- Verify fallback questions contain skill/role references
- Never accept completely generic templates

**Property 5: Expert brief answers classified appropriately**
- Create expert resume + brief answer
- Create junior resume + brief answer
- Run classification for both
- Verify expert answer gets higher quality classification

**Property 6: Metadata scores align with quality**
- Vary extraction confidence and question personalization rate
- Calculate personalization_quality_score
- Verify score ranges match expected levels

**Property 7: Interview continues despite failures**
- Simulate extraction failure
- Simulate retrieval failure
- Simulate generation timeout
- Verify interview reaches completion for each scenario

**Property 8: No repeated gaps across interview session**
- Run multi-question interview
- Extract all targeted_aspects from follow-ups
- Count duplicates across different original questions
- Expect minimal duplication

---

## Implementation Notes

### Language & Libraries

- **Backend**: Python/FastAPI (existing)
- **LLM for Generation**: Groq API (existing)
- **LLM for Classification**: Groq API or similar (use existing pattern)
- **Template-Based Fallback**: Python string templates (no new dependency)
- **Domain Markers**: Hardcoded keyword lists per domain (maintainable)

### Database Migrations

- Add new nullable fields to `InterviewSession` (backward compatible)
- Add new nullable fields to `InterviewTurn` (backward compatible)
- Create metadata storage mechanism (JSON fields or separate table)

### Integration Points

1. **Resume Extraction Service**: Already exists; add validation wrapper
2. **Question Generation Service**: Existing; add personalization validator
3. **Answer Transcription**: Already exists; pass to classifier
4. **Interviewer Brain**: Existing response generation; replace with contextual generator
5. **Interview Storage**: Existing; extend with new metadata fields

### Performance Considerations

- **Validation**: <100ms per question (lightweight token matching)
- **Classification**: <500ms per answer (LLM classification, existing pattern)
- **Follow-up Generation**: <1s per follow-up (LLM generation, acceptable delay)
- **Metadata Calculation**: <50ms per interview session (numerical aggregation)

### Security & Privacy

- No sensitive data logged (resume content, answers, classifications logged only as identifiers/scores)
- All LLM calls sanitize inputs
- Metadata fields remain non-PII (scores, confidence metrics only)
- Question/answer text stored already (no new privacy concerns)

---

## Migration Strategy

1. **Phase 1**: Deploy validation components (extraction validator, question validator) as passive monitors
   - Collect metrics without blocking existing flow
   - Identify current quality gaps

2. **Phase 2**: Deploy answer classifier
   - Run in parallel to existing classification
   - Compare classifications; merge when confident

3. **Phase 3**: Deploy contextual follow-up generator
   - Run in parallel to existing brain responses
   - Switch to new generator when high confidence

4. **Phase 4**: Full integration
   - Enable validation → regeneration loop
   - Enable metadata tracking
   - Monitor for quality improvements

---

## Monitoring & Alerts

### Key Metrics to Track

1. **Extraction Quality**: % of sessions with HIGH confidence extraction
2. **Question Personalization Rate**: % of questions with grounding_confidence ≥ 0.75
3. **Follow-up Grounding Score**: Average grounding_score across all follow-ups
4. **Fallback Rate**: % of sessions using fallback questions
5. **Interview Completion Rate**: % of interviews reaching completion (should remain ~100%)

### Alerts

- If extraction_confidence < 0.50 for >20% of sessions: Investigate resume parsing
- If question_personalization_rate < 0.70: Investigate RAG retrieval quality
- If follow_up_grounding_score < 0.60: Investigate contextual generation quality
- If fallback_rate > 0.30: High failure rate; investigate API availability
- If interview_completion_rate < 0.95: Possible blocker; investigate immediately



## Correctness Properties (Detailed)

Based on the acceptance criteria analysis, here are the testable properties that define correctness for this feature. Each property is universally quantified and implementable as a property-based test.

### Property 1: All Non-Fallback Questions Reference Resume Content

**Validates: Requirements 2.1, 2.5**

*For any* candidate resume and generated question pool, every non-fallback question in the pool must contain exact mention or semantic reference to at least one skill, project, or detected role from that resume. Alternatively, if no resume reference can be established, the question must be marked `is_fallback=true` and not included in the final pool as a personalized question.

**Test Implementation**:
- Generate 50 random resumes with 3-15 skills and 1-5 projects each
- For each resume, run question generation
- For each non-fallback question (is_fallback=false), tokenize and check:
  - Contains exact skill name from resume, OR
  - Contains exact project name from resume, OR
  - Contains detected_role reference
- Assert: 100% of non-fallback questions meet one condition
- Assert: grounding_confidence_score ≥ 0.75 for all non-fallback questions

### Property 2: All Follow-up Questions Reference Answer Content or Identified Gaps

**Validates: Requirements 5.1, 5.5, 6.1, 6.2**

*For any* candidate answer and follow-up generated for that answer, the follow-up question text must contain either: (a) at least one word or phrase from the candidate's answer, OR (b) explicit reference to a missing_aspect identified in the answer classification.

**Test Implementation**:
- Generate 100 random (answer_text, classification) pairs
- Generate contextual follow-up for each pair
- For each follow-up:
  - Extract words from answer_text
  - Extract missing_aspects from classification
  - Check if follow-up contains ≥1 word from answer OR ≥1 missing_aspect reference
  - Calculate grounding_score
- Assert: 100% of follow-ups have grounding_score ≥ 0.75
- Assert: All follow-ups reference answer or gap (0 generic follow-ups)

### Property 3: Consecutive Follow-ups Address Different Missing Aspects

**Validates: Requirements 7.2, 7.6**

*For any* interview session with multiple follow-up turns for the same original question, if there are two follow-ups (followup_count 0 and 1), then the targeted_missing_aspect of followup[0] must differ from targeted_missing_aspect of followup[1].

**Test Implementation**:
- Simulate 50 interview scenarios with answers that warrant multiple follow-ups
- For each scenario with 2+ follow-ups per question:
  - Extract targeted_missing_aspect from each follow-up
  - Check that consecutive follow-ups have different targeted_aspects
- Assert: 0 violations (no consecutive follow-ups target same aspect)
- Assert: followup_count never exceeds 2 (hard cap enforced)

### Property 4: Fallback Questions Still Reference Extracted Skills or Role

**Validates: Requirements 3.1, 3.2, 8.1, 8.2, 8.4**

*For any* fallback scenario (low extraction confidence, no relevant docs, API failure), every fallback question generated must reference either: (a) a skill from the extracted skills list, OR (b) the detected_role phrase, OR (c) a project from extracted projects. No completely generic templates like "What is X?" or "Explain concept" should ever appear.

**Test Implementation**:
- Trigger 20 fallback scenarios:
  - 5 with low extraction (skills < 3)
  - 5 with failed retrieval (no docs)
  - 5 with API failures (simulated timeouts)
  - 5 with complete failure (no skills, no docs, no role)
- For each fallback question:
  - Check contains skill/project/role reference
  - Check does NOT match forbidden patterns: ["What is", "Explain", "Describe the difference", "Tell me about OOPS"]
- Assert: 100% of fallback questions have valid references
- Assert: 0 completely generic templates appear

### Property 5: Answer Classification Correctly Differentiates Expert Brief Answers from Incomplete Answers

**Validates: Requirements 4.3, 4.4, 4.5**

*For any* technical question with two answer responses—one from an expert providing brief but complete technical answer, one from a junior developer providing equally brief but vague answer—the expert answer must receive COMPLETE or EXCELLENT quality classification, while the junior answer receives SHORT or PARTIAL.

**Test Implementation**:
- Create paired answers for 20 technical questions:
  - Pair 1 (Expert): "PostgreSQL, optimized queries with indexes" vs Pair 1 (Junior): "I've used databases"
  - Pair 2 (Expert): "Handled 1M requests/sec with Redis cache" vs Pair 2 (Junior): "Performance matters"
  - ... (20 pairs total)
- Provide resume context indicating seniority level
- Run classification for all answers
- For each pair:
  - Assert: expert_quality ≥ COMPLETE
  - Assert: junior_quality ≤ PARTIAL
  - Assert: expert score > junior score (despite similar brevity)

### Property 6: Metadata Quality Scores Align with Actual Interview Quality Levels

**Validates: Requirements 11.6, 11.7**

*For any* completed interview session, the personalization_quality_score and follow_up_quality_score should monotonically correlate with the underlying quality of extraction, question personalization, and follow-up grounding. Sessions with HIGH extraction confidence and 80%+ question personalization rate should have personalization_quality_score ≥ 0.75; sessions with LOW extraction and <60% question personalization should have score ≤ 0.60.

**Test Implementation**:
- Generate 30 interview scenarios with varying quality levels:
  - 10 with HIGH extraction, 90% question personalization, high follow-up grounding
  - 10 with MEDIUM extraction, 70% question personalization, medium follow-up grounding
  - 10 with LOW extraction, 50% question personalization, low follow-up grounding
- For each scenario:
  - Calculate personalization_quality_score
  - Calculate follow_up_quality_score
- Assert:
  - HIGH quality scenario: personalization_score ≥ 0.75
  - MEDIUM quality scenario: personalization_score 0.50-0.75
  - LOW quality scenario: personalization_score ≤ 0.60
- Assert: warnings correctly triggered when scores < thresholds

### Property 7: Graceful Degradation Maintains Interview Continuity

**Validates: Requirements 3, 9**

*For any* failure scenario (extraction fails, retrieval fails, LLM times out, API error), the interview system must not crash, must not return error to user, and must permit interview to reach completion. The system must degrade gracefully to fallback mechanisms while maintaining as much personalization as possible.

**Test Implementation**:
- Simulate 10 failure scenarios at each major checkpoint:
  - At extraction: force extraction to fail
  - At retrieval: block RAG retriever
  - At question generation: simulate Groq timeout
  - At classification: simulate LLM error
  - At follow-up generation: simulate LLM timeout
- For each failure:
  - Attempt to run full interview flow
  - Assert: No exception thrown; flow continues
  - Assert: Interview reaches completion
  - Assert: Metadata.warnings populated with failure reason
  - Assert: Fallback mechanism activated (fallback=true in data)
- Assert: 0 interviews blocked or errored due to personalization failures

### Property 8: No Follow-up Gaps Repeated Across Question Sequence

**Validates: Requirements 7.1, 7.6**

*For any* multi-question interview session where different original questions have follow-ups, no two follow-up turns across different original questions should target the same missing_aspect (within the same session). E.g., if Question 1's follow-up targets "testing", then Question 2's follow-up should not also target "testing".

**Test Implementation**:
- Simulate 15 full interview sessions (10 questions each)
- Extract all follow-up turns across all questions
- For each pair of (followup from question_i, followup from question_j where i≠j):
  - Check if targeted_missing_aspect is identical
- Count violations: aspect duplicated across different question follow-ups
- Assert: violations < 5% (minimal duplication acceptable)

### Property 9: New Fields Optional and Backward Compatible

**Validates: Requirement 12**

*For any* legacy interview session (created before this feature) that lacks personalization metadata fields, the system must still function correctly: queries succeed, reports still generate, existing functionality continues.

**Test Implementation**:
- Create mock legacy InterviewSession and InterviewTurn records WITHOUT:
  - personalization_source
  - question_grounding_confidence
  - answer_classification
  - followup_grounding_score
  - followup_targeted_aspect
- Run existing interview functionality on these records:
  - Retrieve session details
  - Generate reports
  - Run analytics queries
  - Fetch interview report
- Assert: 0 NULL reference errors, 0 schema mismatches
- Assert: All queries complete successfully
- Assert: Reports display without data for missing fields

### Property 10: Invalid Questions Rejected and Regenerated

**Validates: Requirements 2.2, 2.6**

*For any* question generation attempt that produces an invalid question (grounding_confidence_score < 0.75), the system must not immediately include it in the pool. Instead, it must either: (a) regenerate the question, OR (b) after 2 regeneration failures, mark it as fallback and include with confidence 0.5-0.7.

**Test Implementation**:
- Force question validator to produce invalid questions (mock low grounding scores)
- For each invalid question:
  - Track regeneration attempts
  - Assert: regeneration requested (not accepted as-is)
- After 2 regenerations:
  - Assert: question included as fallback (is_fallback=true)
  - Assert: grounding_confidence_score in range 0.5-0.7
- Assert: No invalid question included as personalized without regeneration or fallback

