# Answer Evaluation Process - How It Works

## Overview
The current demo view is **NOT connected to evaluation** - it's purely visual for the jury. However, when candidates answer through the real prescreening interface (`/candidate/prescreening?token=xxx`), their answers ARE evaluated automatically.

---

## Current Evaluation Method: AI-Powered (Anthropic Claude)

### How It Works:

1. **Candidate Completes Interview**
   - Answers all 6 questions through the chatbot interface
   - Clicks "Submit Interview"
   - Session status changes to "COMPLETED"

2. **Evaluation Triggered**
   - `answer_evaluator.py` is called with the session ID
   - Fetches all Q&A pairs from the database

3. **AI Evaluation (Per Question)**
   - Each answer is sent to **Claude AI (Anthropic)** with this prompt:
   
   ```
   You are an expert HR evaluator reviewing candidate pre-screening answers.
   Score the answer on a scale: Excellent, Good, Average, or Poor.
   Also flag if the answer contains a knockout disqualifier, for example:
   - Notice period more than 90 days
   - Salary expectation more than 30% above budget
   - Explicit lack of required experience
   
   Return JSON: {"score": "Excellent|Good|Average|Poor", "disqualified": true|false, "reason": "brief explanation"}
   ```

4. **Scoring System**
   - **Excellent** = 4 points
   - **Good** = 3 points
   - **Average** = 2 points
   - **Poor** = 1 point

5. **Verdict Calculation**
   - Average score calculated across all 6 answers
   - **PASS**: Average ≥ 2.5 AND not disqualified
   - **BORDERLINE**: Average ≥ 2.0 AND not disqualified
   - **FAIL**: Average < 2.0 OR disqualified

6. **Actions Taken**
   - Verdict stored in database
   - Application status updated to "PRESCREENED"
   - RabbitMQ event published:
     - `screening.passed` → Triggers BGV (Background Verification)
     - `screening.failed` → Sends rejection email

---

## Problem: Anthropic Claude Not Available

The current system uses **Anthropic Claude API** which:
- ❌ Requires API key (not configured)
- ❌ Costs money per API call
- ❌ Has rate limits
- ❌ May fail if API is down

**Current Status**: The evaluation will fail because `ANTHROPIC_API_KEY` is not set.

---

## Alternative: Rule-Based Evaluation (Free & Reliable)

Since you're using **fixed questions** and want a **free solution**, I recommend implementing a **rule-based evaluation system** instead of AI:

### Rule-Based Evaluation Logic:

```python
def evaluate_answer_rule_based(question_index, question, answer):
    """
    Evaluate answer based on rules instead of AI.
    Returns: {"score": "Excellent|Good|Average|Poor", "disqualified": bool, "reason": str}
    """
    answer_lower = answer.lower().strip()
    answer_length = len(answer)
    
    # Basic validation
    if answer_length < 20:
        return {"score": "Poor", "disqualified": True, "reason": "Answer too short"}
    
    # Question-specific rules
    if question_index == 0:  # Motivation
        if answer_length > 100:
            return {"score": "Excellent", "disqualified": False, "reason": "Detailed motivation"}
        elif answer_length > 50:
            return {"score": "Good", "disqualified": False, "reason": "Good motivation"}
        else:
            return {"score": "Average", "disqualified": False, "reason": "Brief motivation"}
    
    elif question_index == 1:  # Experience
        years_keywords = ["year", "years", "experience", "worked"]
        if any(keyword in answer_lower for keyword in years_keywords):
            return {"score": "Good", "disqualified": False, "reason": "Experience mentioned"}
        else:
            return {"score": "Average", "disqualified": False, "reason": "Experience unclear"}
    
    elif question_index == 2:  # Skills
        skill_keywords = ["python", "java", "javascript", "react", "node", "sql", "aws", "docker"]
        skills_found = sum(1 for skill in skill_keywords if skill in answer_lower)
        if skills_found >= 3:
            return {"score": "Excellent", "disqualified": False, "reason": f"{skills_found} skills mentioned"}
        elif skills_found >= 1:
            return {"score": "Good", "disqualified": False, "reason": f"{skills_found} skill(s) mentioned"}
        else:
            return {"score": "Average", "disqualified": False, "reason": "Skills mentioned"}
    
    elif question_index == 3:  # Handling pressure
        positive_keywords = ["manage", "prioritize", "organize", "plan", "communicate"]
        if any(keyword in answer_lower for keyword in positive_keywords):
            return {"score": "Good", "disqualified": False, "reason": "Good approach to pressure"}
        else:
            return {"score": "Average", "disqualified": False, "reason": "Approach mentioned"}
    
    elif question_index == 4:  # Salary expectations
        # Check for unrealistic expectations (example: > 50 LPA for entry level)
        if "50" in answer or "100" in answer or "crore" in answer_lower:
            return {"score": "Poor", "disqualified": True, "reason": "Salary expectation too high"}
        else:
            return {"score": "Good", "disqualified": False, "reason": "Reasonable expectations"}
    
    elif question_index == 5:  # Availability
        immediate_keywords = ["immediate", "immediately", "now", "asap", "2 weeks", "1 month"]
        long_notice = ["3 months", "90 days", "6 months"]
        
        if any(keyword in answer_lower for keyword in long_notice):
            return {"score": "Poor", "disqualified": True, "reason": "Notice period too long"}
        elif any(keyword in answer_lower for keyword in immediate_keywords):
            return {"score": "Excellent", "disqualified": False, "reason": "Available soon"}
        else:
            return {"score": "Good", "disqualified": False, "reason": "Availability mentioned"}
    
    # Default
    return {"score": "Average", "disqualified": False, "reason": "Answer provided"}
```

---

## Recommendation: Switch to Rule-Based

### Advantages:
✅ **Free** - No API costs
✅ **Fast** - Instant evaluation
✅ **Reliable** - No API failures
✅ **Consistent** - Same rules every time
✅ **Transparent** - Easy to explain to jury
✅ **Customizable** - Easy to adjust rules

### Disadvantages:
❌ Less sophisticated than AI
❌ Can't understand context as well
❌ Requires manual rule updates

---

## For Your Jury Demo

### Current State:
- **Demo View**: Questions visible but NOT evaluated (just for show)
- **Real Prescreening**: Would use Claude AI but will fail (no API key)

### What I Recommend:

**Option 1: Keep Current Setup (AI-based)**
- Configure `ANTHROPIC_API_KEY` in `.env`
- Costs ~$0.01 per candidate evaluation
- More impressive for jury ("AI-powered evaluation")

**Option 2: Switch to Rule-Based (Recommended)**
- I can implement the rule-based evaluator
- Free, fast, reliable
- Still impressive ("Intelligent rule-based evaluation")

**Option 3: Hybrid Approach**
- Use rule-based by default
- Fall back to AI if `ANTHROPIC_API_KEY` is set
- Best of both worlds

---

## What Happens After Evaluation?

### If PASS:
1. ✅ Verdict: "PASS" stored in database
2. ✅ Event published: `screening.passed`
3. ✅ Background verification initiated automatically
4. ✅ If BGV clears → Auto-hire decision
5. ✅ Congratulations email sent

### If FAIL:
1. ❌ Verdict: "FAIL" stored in database
2. ❌ Event published: `screening.failed`
3. ❌ Rejection email sent automatically
4. ❌ Application status: "REJECTED"

---

## To Enable Real Evaluation

### Option A: Use Anthropic Claude (Current)
```bash
# In .env file
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Option B: Switch to Rule-Based (I can implement)
```bash
# In .env file
EVALUATION_METHOD=rule_based  # or "ai" for Claude
```

---

## Summary

**Current Demo View**: Just visual, no evaluation
**Real Prescreening**: Uses Claude AI (not configured)
**Recommendation**: Switch to rule-based evaluation for free, reliable, demo-ready system

Would you like me to:
1. Implement the rule-based evaluator?
2. Keep Claude but add fallback to rules?
3. Just configure Claude with your API key?
