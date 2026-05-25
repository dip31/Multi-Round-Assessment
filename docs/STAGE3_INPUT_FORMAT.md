# Stage 3 — Screening Service: Input & Output Format

## 1. RabbitMQ Message (Trigger)

Stage 2 sends this message to queue `profile_parsed_queue` after parsing a resume:

```json
{
  "event": "profile.parsed",
  "candidate_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- `event` — always `"profile.parsed"`
- `candidate_id` — UUID string of the candidate (must already exist in DB)

> **NOTE:** The message only contains the ID. All actual data is fetched from the database.

---

## 2. Database Records Required Before Processing

### Table: `jobs` (inserted by Stage 1 — Intake)

| Field | Type | Example | Required |
|-------|------|---------|----------|
| id | String (UUID) | `"550e8400-..."` | ✅ |
| title | String | `"Backend Python Developer"` | ✅ |
| skills | Text (JSON string) | `"[\"python\", \"sql\", \"fastapi\"]"` | ✅ |
| experience_min | Integer | `3` | ✅ (used for scoring) |
| experience_max | Integer | `5` | Optional |
| qualification | String | `"bachelor's"` | ✅ (used for scoring) |
| location | String | `"Pune"` | Optional (bonus scoring) |
| description | Text | `"Looking for..."` | Optional |
| status | String | `"draft"` | Default: `"draft"` |

#### Sample SQL Insert:
```sql
INSERT INTO jobs (id, title, skills, experience_min, experience_max, qualification, location, status)
VALUES (
  'job-uuid-001',
  'Backend Python Developer',
  '["python", "sql", "fastapi", "docker"]',
  3,
  5,
  'bachelor''s',
  'Pune',
  'active'
);
```

---

### Table: `candidates` (inserted by Stage 2 — Sourcing/Parsing)

| Field | Type | Example | Required |
|-------|------|---------|----------|
| id | String (UUID) | `"cand-uuid-001"` | ✅ |
| name | String | `"Alice Johnson"` | ✅ (used for duplicate detection) |
| email | String | `"alice@example.com"` | ✅ (used for duplicate detection) |
| phone | String | `"9876543210"` | ✅ (used for duplicate detection) |
| skills | Text (JSON string) | `"[\"python\", \"sql\"]"` | ✅ (used for scoring) |
| experience_years | Float | `4.0` | ✅ (used for scoring) |
| education | String | `"Bachelor's"` | ✅ (used for scoring) |
| location | String | `"Pune"` | Optional (bonus scoring) |
| source | String | `"resume"` or `"github"` | ✅ |
| job_id | String (FK → jobs.id) | `"job-uuid-001"` | ✅ |
| status | String | `"new"` | Default: `"new"` |
| score | Float | `null` | Set by Stage 3 |
| is_duplicate | Boolean | `false` | Default: `false` |

#### Sample SQL Insert:
```sql
INSERT INTO candidates (id, name, email, phone, skills, experience_years, education, location, source, job_id, status)
VALUES (
  'cand-uuid-001',
  'Alice Johnson',
  'alice@example.com',
  '9876543210',
  '["python", "sql", "fastapi"]',
  4.0,
  'Bachelor''s',
  'Pune',
  'resume',
  'job-uuid-001',
  'new'
);
```

---

## 3. Scoring Logic (How Scores Are Calculated)

| Category | Max Points | How It Works |
|----------|-----------|--------------|
| **Skill Match** | 40 | `(matched_skills / required_skills) × 40` |
| **Experience** | 30 | Full 30 if `candidate.experience_years >= job.experience_min`, else proportional |
| **Education** | 20 | Full 20 if candidate meets/exceeds required qualification |
| **Location** | 10 | Bonus 10 if exact match, else 0 |
| **TOTAL** | **100** | Sum of above. **≥ 70 → Shortlisted**, **< 70 → Rejected** |

### Education Hierarchy (highest to lowest):
```
PhD / Doctorate → 5
Master's / M.Tech / MBA → 4
Bachelor's / B.Tech / B.E → 3
Associate → 2
High School → 1
```

### Duplicate Detection (checked before scoring):
- **Exact email match** → duplicate
- **Exact phone match** → duplicate
- **Fuzzy name similarity > 85%** → duplicate
- Duplicates are auto-rejected (skips scoring)

---

## 4. Output — What Stage 3 Writes

### DB Update (on `candidates` table):
```json
{
  "score": 90,
  "score_breakdown": "{\"skill_match\": 30, \"experience\": 30, \"education\": 20, \"location\": 10, \"total\": 90}",
  "status": "shortlisted",
  "rejection_reason": null,
  "is_duplicate": false,
  "merged_into": null
}
```

### RabbitMQ Output (to `candidate_screened_queue`):
```json
{
  "event": "candidate.screened",
  "candidate_id": "cand-uuid-001",
  "status": "shortlisted",
  "score": 90,
  "is_duplicate": false
}
```

---

## 5. Testing Without RabbitMQ / Stage 2

### Option A: Use the API endpoints
```bash
# Create job
curl -X POST "http://localhost:8000/api/intake/jobs" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Job", "skills": ["Python"], "experience_min": 2}'

# Add test candidate
curl -X POST "http://localhost:8000/api/screening/test/add-candidate" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test User", "skills": ["Python"], "experience_years": 3, "job_id": "job-id"}'

# Run screening
curl -X POST "http://localhost:8000/api/screening/run" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "job-id"}'
```

### Option B: Call processor directly (no API needed)
```python
from shared.db.database import get_db
from shared.db.models import Candidate, Job
from screening.processor import process_candidate
import json

# Get database session
db_gen = get_db()
db = next(db_gen)

# Run screening on a candidate
result = process_candidate("candidate-id", db)
print(result)
```