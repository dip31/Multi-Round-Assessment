# Interview Round Quality Report
**Date:** September 23, 2026  
**Status:** Critical Issues Identified

---

## Executive Summary

The interview round system has **two major quality issues**:

1. **Questions are not properly grounded in resume content** — Questions often feel generic rather than personalized to the candidate's skills and projects
2. **Follow-up questions are repetitive and non-contextual** — The system defaults to "Can you elaborate?" without understanding what the candidate actually said

These issues stem from **weak resume-to-question linking** and **oversimplified follow-up logic**.

---

## Issue 1: Poor Question Generation from Resume

### Root Cause

The question generation pipeline has **three failure points**:

#### A. Resume Extraction May Be Incomplete
**File:** `app/services/rag_service.py` (parse_resume function)
- Uses PyMuPDF + Groq LLM to extract skills and projects
- **Problem:** When Groq LLM fails or returns incomplete data, fallback is minimal
- **Impact:** Skills list might be missing important technologies, projects lack context

#### B. RAG Retrieval Doesn't Validate Relevance
**File:** `app/services/groq_service.py` (generate_question_pool, lines 31-120)
```python
# Current logic:
retrieved_docs = retrieve(
    skills=skills,
    projects=projects,
    detected_role=detected_role,
    k=8,
    final_k=5
)
context = format_for_prompt(retrieved_docs)
```
- Retrieves 5 "relevant" documents from knowledge base
- **Problem:** No validation that retrieved docs actually relate to candidate's skills
- **Issue:** If retrieval fails, defaults to "No additional context available"

#### C. Fallback Questions Are Generic
**File:** `app/services/groq_service.py` (lines 242-320+)
```python
# Fallback examples for TECHNICAL:
technical_fallbacks = [
    ("What is the difference between...", "EASY", "Data Structures"),
    ("Explain OOPS concepts", "MEDIUM", "OOPS"),
    # ... 12 hardcoded generic questions
]
```
- **Problem:** Fallback questions have NO connection to candidate's resume
- **Trigger:** Activates when Groq API fails or returns invalid JSON
- **Frequency:** Observed when network issues or API timeouts occur

#### D. "Personalized" Flag Not Validated
**File:** `app/services/groq_service.py` (generate_question_pool response)
```python
{
    "question": "Tell me about your experience with databases",
    "difficulty": "MEDIUM",
    "personalized": true,  # ← No validation this is actually true
    "grounded_in": "candidate's project"  # ← Self-reported, not verified
}
```
- AI claims question is "personalized" but there's no verification
- Each generated question's relevance is never checked against candidate's actual skills

### How This Manifests

**Observed Behavior:**
- Candidate uploads resume (Senior Python/Django developer with ML projects)
- Generated questions: "Explain what an API is", "What is a database?"
- These are EASY foundational questions, not relevant to senior dev with ML background

**Why This Happens:**
1. Resume parsing extracts skills: ["Python", "Django", "ML", "TensorFlow"]
2. RAG retriever searches knowledge base but may find unrelated docs
3. Question generator sees "Python" → generates "What is OOP?"
4. If API fails → uses hardcoded fallback questions (completely generic)

---

## Issue 2: Non-Contextual Follow-Up Questions

### Root Cause

The follow-up logic is **rule-based but non-semantic**:

**File:** `app/modules/interview/routers/interview_router.py` (lines 570-620)

#### Current Logic

```python
# Step 5: Decision Engine
if quality == "IRRELEVANT":
    action = "FOLLOWUP"
    followup_type = "redirect_to_original"
elif quality == "SHORT":
    action = "FOLLOWUP"
    followup_type = "elaborate"
elif quality == "PARTIAL":
    action = "FOLLOWUP"
    followup_type = "expand_missing"
elif intent == "NEGATIVE":
    action = "FOLLOWUP"
    followup_type = "redirect_negative"
else:
    action = "NEXT"  # Move to next question
```

#### Hardcoded Brain Responses

**File:** `app/services/groq_service.py` (_brain_fallback function)

```python
fallback_responses = {
    "short": "Could you elaborate on that in more detail?",
    "partial": "Good start. Can you expand on that point?",
    "negative": "That's honest. How do you see yourself adapting to this?",
    "irrelevant": "Let's refocus — could you address the original question?",
}
```

### Problems

#### 1. All "SHORT" Answers Get Same Response
- Candidate answers: "I used Python" → "Could you elaborate?"
- Candidate answers: "I used Python for 5 projects building ML models" → "Could you elaborate?"
- **Problem:** No distinction between actually-short vs. sufficient-but-brief answers

#### 2. No Understanding of Answer Content
- Question: "Tell me about your database experience"
- Answer: "I designed a schema with 50+ tables handling 1M transactions/day"
- System sees quality="PARTIAL" → responds with "Can you expand?"
- **Problem:** The answer demonstrates expertise, but system requests elaboration anyway

#### 3. Repetitive Follow-Up Loops
- First follow-up: "Could you elaborate?"
- Candidate provides more detail
- System still scores it PARTIAL → another "Could you elaborate?"
- **Problem:** Hard cap of 2 follow-ups means candidate can be asked same thing twice

#### 4. Missing Semantic Analysis
The classifier returns:
```python
{
    "quality": "PARTIAL",           # ← Surface assessment
    "intent": "POSITIVE",           # ← Engagement level
    "missing_part": "deployment",   # ← What's missing
    "content_score": 0.55           # ← 0-1 score
}
```

But the interviewer brain response generator doesn't:
- Use `missing_part` to guide follow-up toward specific topic
- Consider whether candidate demonstrated deep knowledge
- Differentiate between "brief but accurate" vs. "incomplete"

### How This Manifests

**Observed Behavior:**
```
Q: "Describe your most complex project"
A: "Built a real-time stock trading dashboard using React, WebSockets, and PostgreSQL. 
   Handled 1000s of concurrent users with <100ms latency."

System Response: "Could you elaborate in more detail?"

Expected: "That's impressive. How did you handle the real-time data synchronization?"
```

**Why This Happens:**
1. Classifier sees answer is ~50 words → "SHORT"
2. No semantic understanding that answer demonstrates deep expertise
3. Rule: SHORT → followup type = "elaborate"
4. Brain generates: "Could you elaborate?"

---

## Why Questions Aren't Resume-Grounded

### Issue Chain

```
Resume Upload
    ↓
PyMuPDF Extract Text
    ↓
Groq Parse → Extract skills/projects
    ↓
[RISK POINT 1: Extraction incomplete/wrong]
    ↓
Question Generator receives: skills=["Python"], projects={"Dashboard": "web app"}
    ↓
RAG Retriever searches knowledge base
    ↓
[RISK POINT 2: Retriever returns unrelated docs or fails]
    ↓
Question prompt uses context
    ↓
Groq generates 12 questions
    ↓
[RISK POINT 3: Generated questions not actually grounded]
    ↓
IF Groq API fails/invalid JSON:
    → Use hardcoded fallback (completely generic, 0% resume grounding)
    ↓
Questions stored in DB
```

### Why Each Point Fails

| Risk Point | Root Cause | Impact |
|-----------|-----------|--------|
| **Extraction incomplete** | Groq temp=0.3 may miss less-obvious skills; PDF parsing sometimes misses formatted content | Skills list = ["Python"], should be ["Python", "FastAPI", "PostgreSQL", "Docker", "ML"] |
| **RAG retriever unrelated** | No validation that retrieved docs match candidate; fallback to generic context | Questions generated about basic concepts instead of advanced topics |
| **Generated questions not grounded** | AI claims "personalized":true but no verification; if Groq fails → hardcoded fallback | Questions are generic: "Explain OOPS" instead of "Tell me about your Django ORM design patterns" |

---

## Why Follow-Ups Are Generic

### Issue Chain

```
Candidate provides answer
    ↓
Answer stored + sent to classifier
    ↓
Groq classify_answer() returns:
    {quality: "SHORT", intent: "POSITIVE", missing_part: "authentication", content_score: 0.35}
    ↓
Decision engine sees quality="SHORT"
    → Sets: action="FOLLOWUP", followup_type="elaborate"
    ↓
Interviewer Brain invoked
    ↓
generate_interviewer_response():
    - System: "You are a warm interviewer..."
    - Current question + answer
    - action="FOLLOWUP", followup_type="elaborate"
    - Task: "Encourage elaboration"
    ↓
IF Groq API fails:
    → Use fallback: "Could you elaborate on that in more detail?"
    ↓
Response returned to candidate
```

### Why This Is Weak

**The system doesn't:**
1. Analyze what the candidate **actually said**
2. Understand what **aspect** is missing
3. Personalize follow-up based on **question context**
4. Recognize when an answer is **sufficient but brief**

**Example:**
```
Question: "What's your experience with databases?"

Answer: "I've used PostgreSQL and MongoDB. Designed schemas, optimized queries."

Classifier sees:
- 14 words + demonstrates knowledge
- quality = "SHORT" (arbitrary word count threshold)
- missing_part = "scaling/replication"

Interviewer generates:
- Default: "Could you elaborate?"

Should generate:
- "Good, you've touched on both SQL and NoSQL. Tell me about a specific scaling challenge you faced."
```

---

## Current Failures Breakdown

### Questions Not Personalized

**Evidence from Testing:**
- Resume uploaded for Django developer with 5 projects
- Generated questions include: "What is HTTP?", "Explain inheritance"
- These are beginner-level questions, not advanced

**Root Cause Sequence:**
1. Resume parsing succeeds but extracts minimal skills
2. RAG retriever fails or returns generic results
3. Question generator uses fallback questions
4. Fallback = hardcoded generic bank (zero personalization)

**Frequency:** Occurs when API fails or during high load

### Follow-Ups Always "Can You Elaborate"

**Evidence from Testing:**
- Short but complete answers scored as "SHORT"
- All SHORT answers receive same response
- No variation based on question type or missing content
- Hard cap of 2 follow-ups means repetition possible

**Root Cause Sequence:**
1. Classifier bins answer into QUALITY category (SHORT, PARTIAL, etc.)
2. Decision engine maps quality → action (FOLLOWUP)
3. Interviewer brain receives action + followup_type
4. Brain prompt uses generic task: "Encourage elaboration"
5. IF API fails → fallback response used (always same)

**Frequency:** Happens on almost every answer classified as SHORT

---

## Technical Debt & Design Issues

### 1. No Validation of Question Relevance
**Current:** Questions generated, marked "personalized":true, stored as-is  
**Should be:** 
- Verify each question references candidate's actual skills/projects
- If not → regenerate or reject

### 2. Classifier Ignores Domain Knowledge
**Current:** Binary quality classification (SHORT/PARTIAL/GOOD)  
**Should be:** 
- Consider question domain (DSA vs. HR vs. Communication)
- Evaluate answer against domain expectations
- For technical questions: recognize depth even if brief

### 3. Interviewer Brain Ignores Answer Content
**Current:** Receives (quality, followup_type) + generic task  
**Should be:**
- Receive full answer text + classification details
- Analyze what was actually said
- Generate contextual follow-up based on **specific missing part**

### 4. Fallback Mechanism Too Aggressive
**Current:** Generic fallback questions used if ANY error occurs  
**Should be:**
- Validate resume parsing success before proceeding
- Retry retrieval if first attempt fails
- Fall back only to semi-generic questions still tied to detected role

### 5. No Feedback Loop
**Current:** No validation that questions are helping  
**Should be:**
- Track: "How many questions required follow-ups?"
- Measure: "Were final scores consistent with domain expectations?"
- Alert: If >60% of questions need follow-up, regenerate pool

---

## Immediate Problems

### For Users

| Problem | User Impact |
|---------|------------|
| Generic questions | Frustration — "This doesn't test my skills" |
| Repetitive follow-ups | Annoyance — "I already answered this" |
| Low-level questions for advanced devs | Time waste — irrelevant questions |
| Same follow-up wording | Feels robotic, not like human interviewer |

### For Assessment Quality

| Problem | Assessment Impact |
|---------|------------------|
| Questions not grounded in resume | Scores reflect generic knowledge, not role-fit |
| Repetitive follow-ups | Penalizes candidates who communicate briefly but accurately |
| No semantic answer analysis | Good answers marked as incomplete |
| Fallback to generic questions | Can't differentiate candidate skill levels |

---

## Recommended Fixes (Priority Order)

### P0: Make Questions Resume-Grounded
1. Add validation step after question generation
2. For each question, verify it mentions candidate's skills/projects
3. Reject questions that don't explicitly reference resume content
4. Improve fallback to use detected role + skills

### P1: Make Follow-Ups Contextual
1. Enhance classifier to return **specific missing aspects** (not just generic "missing_part")
2. Modify brain prompt to **explicitly reference** what was said and what's missing
3. Vary follow-up language based on question type
4. Recognize when brief answers are **sufficient**

### P2: Add Quality Monitoring
1. Track how many follow-ups per question on average
2. Flag questions that consistently need >1 follow-up
3. Measure score consistency across candidate cohorts

### P3: Improve Resume Extraction
1. Validate extraction completeness
2. Require min threshold of skills extracted (e.g., ≥5 skills)
3. Cross-reference extracted skills against hardcoded tech list
4. Retry extraction if result seems incomplete

---

## Next Steps

To address these issues, we should:

1. **Create an interview-enhancement spec** with detailed requirements for:
   - Resume-grounded question validation
   - Contextual follow-up generation
   - Answer semantic analysis improvements

2. **Implement verification layer** ensuring questions link to resume

3. **Redesign interviewer brain prompt** to use full context

4. **Add monitoring/alerts** for question quality issues

Would you like me to create a detailed spec to fix these issues?
