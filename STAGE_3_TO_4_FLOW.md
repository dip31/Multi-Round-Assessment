# Stage 3 → Stage 4 Automation Flow

## ✅ YES - Shortlisted candidates are automatically sent from Stage 3 to Stage 4

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         STAGE 2: SOURCING                        │
│                                                                   │
│  Resume Upload → Parse Resume → Create Candidate                 │
│                                                                   │
│  Publishes: "profile.parsed" event                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        STAGE 3: SCREENING                        │
│                                                                   │
│  1. Listens to: "profile.parsed" event                          │
│  2. Duplicate Detection (checks existing candidates)             │
│  3. Score Calculation (skills, experience, education, location)  │
│  4. Decision:                                                     │
│     • Score >= 70 → status = "shortlisted"                       │
│     • Score < 70  → status = "rejected"                          │
│  5. Save to database                                             │
│  6. Publishes event:                                             │
│     • "candidate.shortlisted" (if score >= 70)                   │
│     • "candidate.rejected" (if score < 70)                       │
│                                                                   │
│  File: screening/processor.py                                    │
│  File: screening/shortlister.py                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        STAGE 4: OUTREACH                         │
│                                                                   │
│  1. Listens to: "candidate.shortlisted" event                   │
│  2. Fetches candidate and job details from database              │
│  3. Generates unique chatbot URL with token                      │
│  4. Sends outreach email via EmailJS:                            │
│     • Subject: "Exciting Opportunity: [Job] at [Company]"        │
│     • Contains prescreening chatbot link                         │
│  5. Logs communication in database                               │
│  6. Updates application status to "OUTREACH_SENT"                │
│                                                                   │
│  File: outreach/email_sender.py                                  │
│  Function: process_candidate_shortlisted_event()                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      STAGE 5: PRESCREENING                       │
│                                                                   │
│  Candidate clicks link → Answers 6 questions → Evaluation        │
└─────────────────────────────────────────────────────────────────┘
```

## Event Subscription Details

### In main.py (Startup):
```python
# Stage 3 subscribes to Stage 2 events
from screening.shortlister import process_profile_parsed_event
event_bus.subscribe("profile.parsed", process_profile_parsed_event)

# Stage 4 subscribes to Stage 3 events
from outreach.email_sender import process_candidate_shortlisted_event
event_bus.subscribe("candidate.shortlisted", process_candidate_shortlisted_event)
```

## Code References

### Stage 3: Publishing the Event
**File:** `screening/shortlister.py`
```python
await event_bus.publish(
    EventTopics.CANDIDATE_SHORTLISTED,  # "candidate.shortlisted"
    {
        "candidate_id": result["candidate_id"],
        "job_id": payload.get("job_id"),
        "status": result["status"],
        "score": result["score"],
        "is_duplicate": result["is_duplicate"],
    },
    agent="screening_shortlister"
)
```

### Stage 4: Handling the Event
**File:** `outreach/email_sender.py`
```python
async def process_candidate_shortlisted_event(payload: dict):
    """
    Process a candidate.shortlisted event from the event bus.
    This is called when Stage 3 shortlists a candidate.
    """
    candidate_id = payload.get("candidate_id")
    job_id = payload.get("job_id")
    
    # Fetch candidate and job from database
    with db_session() as db:
        candidate = db.query(Candidate).filter_by(id=candidate_id).first()
        job = db.query(Job).filter_by(id=job_id).first()
        
        # Send outreach email
        success = send_outreach_email(candidate, job, db)
```

## Scoring Threshold

**File:** `screening/processor.py`
```python
SHORTLIST_THRESHOLD = 70  # Minimum score to be shortlisted

if total_score >= SHORTLIST_THRESHOLD:
    status = "shortlisted"  # → Triggers Stage 4
else:
    status = "rejected"     # → No outreach sent
```

## Testing the Flow

### 1. Upload a Resume
```bash
POST /api/sourcing/upload
Content-Type: multipart/form-data

file: resume.pdf
job_id: <job-uuid>
```

### 2. System Automatically:
- ✅ Parses resume (Stage 2)
- ✅ Scores candidate (Stage 3)
- ✅ If score >= 70: Sends outreach email (Stage 4)
- ✅ Creates prescreening session (Stage 5)

### 3. Check Logs
```bash
python main.py

# You should see:
✅ Screening shortlister subscribed to profile.parsed events
✅ Outreach email sender subscribed to candidate.shortlisted events
📌 Queue 'recruitment.profile_parsed' bound to 'profile.parsed'
📌 Queue 'recruitment.candidate_shortlisted' bound to 'candidate.shortlisted'
```

### 4. Verify in Database
```sql
-- Check candidate status
SELECT id, name, status, score FROM candidates;

-- Check if outreach was sent
SELECT * FROM communications WHERE communication_type = 'OUTREACH';

-- Check application status
SELECT * FROM applications WHERE status = 'OUTREACH_SENT';
```

## Event Bus Architecture

The system uses RabbitMQ for event-driven communication:

- **Publisher:** Stage 3 (screening/shortlister.py)
- **Topic:** "candidate.shortlisted"
- **Subscriber:** Stage 4 (outreach/email_sender.py)
- **Message Queue:** recruitment.candidate_shortlisted

This ensures:
- ✅ Loose coupling between stages
- ✅ Automatic retry on failure
- ✅ Scalability (can add more workers)
- ✅ Reliability (messages persist in queue)

## Troubleshooting

### Outreach emails not being sent?

1. **Check if candidate was shortlisted:**
   ```sql
   SELECT id, name, status, score FROM candidates WHERE status = 'shortlisted';
   ```

2. **Check event bus logs:**
   ```bash
   # Look for:
   "Published screening result for candidate X: shortlisted"
   "Processing candidate.shortlisted event: candidate=X, job=Y"
   ```

3. **Check EmailJS configuration:**
   - Verify EMAILJS_* variables in .env
   - Check EmailJS dashboard for delivery status

4. **Check RabbitMQ connection:**
   ```bash
   # Should see:
   ✅ Connected to RabbitMQ at amqp://recruitment:***@localhost:5672/
   ```

### Candidate not being shortlisted?

1. **Check score:**
   ```sql
   SELECT id, name, score, score_breakdown FROM candidates;
   ```
   Score must be >= 70 to be shortlisted

2. **Check for duplicates:**
   ```sql
   SELECT id, name, is_duplicate, merged_into FROM candidates WHERE is_duplicate = true;
   ```
   Duplicates are automatically rejected

3. **Check job exists:**
   ```sql
   SELECT * FROM jobs WHERE id = '<job-uuid>';
   ```

## Summary

✅ **YES** - The automation is fully implemented:
- Stage 3 automatically publishes "candidate.shortlisted" events
- Stage 4 automatically listens and sends outreach emails
- No manual intervention required
- Event-driven architecture ensures reliability
