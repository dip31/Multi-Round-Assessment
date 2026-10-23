# EDI5 Dynamic Retell Interviewer Architecture

## Overview

This document describes the implementation of dynamic interviewer creation in EDI5 with Retell AI integration. Admins can now create custom interviewers from the frontend, which automatically provisions Retell LLM and Agent resources.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EDI5 FRONTEND (Admin UI)                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ InterviewerManagement.jsx                                        │   │
│  │ - List/Edit/Delete dynamic interviewers                          │   │
│  │ - Create form with personality, voice, avatar config             │   │
│  │ - Voice preview using existing TTS infrastructure                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬────────────────────────────────────────────┘
                           │ REST API (Authenticated, Admin-only)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      EDI5 BACKEND (FastAPI)                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ InterviewerService                                               │   │
│  │ - create_interviewer()                                           │   │
│  │   1. Validate input                                              │   │
│  │   2. Create Retell LLM with personality prompt                   │   │
│  │   3. Create Retell Agent using LLM                               │   │
│  │   4. Save DynamicInterviewer to DB with Retell IDs              │   │
│  │   5. Rollback on failure (cleanup Retell resources)             │   │
│  │ - update_interviewer() / deactivate_interviewer()                │   │
│  │ - list_interviewers() / get_interviewer()                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         │                         │                    │              │
│         ▼                         ▼                    ▼              │
│  ┌──────────────┐         ┌──────────────┐         ┌────────────┐   │
│  │ PostgreSQL   │         │ Retell SDK   │         │ Interview  │   │
│  │ DynamicInter-│         │ - llm.create │         │ Session    │   │
│  │ viewer table │         │ - agent.create│        │ uses agent │   │
│  └──────────────┘         │ - agent.patch │        │ ID at start│   │
│                           └──────────────┘         └────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Model

### DynamicInterviewer (PostgreSQL)

```sql
CREATE TABLE dynamic_interviewers (
    id              SERIAL PRIMARY KEY,
    slug            VARCHAR(50) UNIQUE NOT NULL,      -- Used as interviewer_id
    name            VARCHAR(100) NOT NULL,
    title           VARCHAR(200) NOT NULL,
    tagline         VARCHAR(500) NOT NULL,
    description     TEXT,
    personality     TEXT NOT NULL,                     -- Comma-separated traits
    speaking_style  TEXT NOT NULL,
    greeting        TEXT NOT NULL,
    avatar_initials VARCHAR(10) NOT NULL,
    accent          VARCHAR(20) NOT NULL,              -- Tailwind color
    avatar_url      VARCHAR(500),
    voice_id        VARCHAR(100) NOT NULL,             -- Retell/Sarvam voice
    voice_model     VARCHAR(100),
    voice_provider  VARCHAR(50) DEFAULT 'retell',
    language_code   VARCHAR(10) DEFAULT 'en-US',
    pace            FLOAT DEFAULT 0.95,
    retell_llm_id   VARCHAR(100),                      -- Created LLM
    retell_agent_id VARCHAR(100),                      -- Created Agent
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/interview/interviewers` | List all (static + dynamic) | Any user |
| GET | `/interview/interviewers/voices` | Available voices | Any user |
| GET | `/interview/interviewers/manage` | List dynamic (admin) | Admin |
| GET | `/interview/interviewers/manage/{id}` | Get detail (admin) | Admin |
| POST | `/interview/interviewers` | Create (admin) | Admin |
| PATCH | `/interview/interviewers/manage/{id}` | Update (admin) | Admin |
| DELETE | `/interview/interviewers/manage/{id}` | Deactivate (admin) | Admin |
| POST | `/interview/interviewers/preview-voice` | Voice preview | Any user |
| GET | `/integrations/retell/health` | Health check | - |

### Request/Response Examples

#### Create Interviewer
```json
POST /interview/interviewers
{
  "name": "Alex Chen",
  "title": "Senior Backend Engineer",
  "tagline": "Expert in distributed systems and cloud architecture",
  "description": "Specializes in Go, Kubernetes, and system design",
  "personality": "Calm, analytical, encouraging, direct but kind",
  "speaking_style": "Concise and technically precise, uses analogies",
  "greeting": "Hi, I'm {name}. Thanks for making the time today — let's start with a quick introduction.",
  "avatar_initials": "AC",
  "accent": "indigo",
  "avatar_url": "https://example.com/avatar.png",
  "voice_id": "shubh",
  "voice_model": "bulbul:v3",
  "language_code": "en-US",
  "pace": 0.95
}

Response 201:
{
  "interviewer": { ... },
  "retell_llm_id": "llm_abc123",
  "retell_agent_id": "agent_xyz789"
}
```

## Interview Session Flow with Dynamic Interviewers

```
Candidate selects interviewer
        │
        ▼
POST /interview/session/start?interviewer_id=alex-chen
        │
        ▼
EDI5 Backend:
  1. Resolve interviewer_id -> slug
  2. Check DynamicInterviewer table for slug
  3. If dynamic with retell_agent_id:
       Use that agent_id for web call
     Else if static profile:
       Use global RETELL_AGENT_ID with agent_override
        │
        ▼
Retell create-web-call with effective agent_id
        │
        ▼
Return retell_call_id, access_token, ice_servers
        │
        ▼
Frontend connects to Retell Web Call
        │
        ▼
Interview proceeds with EDI5 orchestration
```

## Retell LLM Prompt Generation

The system automatically generates a Retell LLM prompt from the interviewer's personality:

```
You are {name}, {title}.

{tagline}

Your personality:
- {trait1}
- {trait2}
...

Your speaking style:
{speaking_style}

You are a professional interviewer conducting a campus placement interview for an engineering student.

CRITICAL RULES - These are inviolable:
- You NEVER lecture or explain the answer
- You NEVER repeat what the candidate just said back to them
- You NEVER ask two questions in one response
- Maximum 2 sentences in your response
- Sound human, not like a bot reading a script

You receive interview actions from the EDI5 interview engine...
```

## Voice Preview

The system reuses the existing Sarvam TTS infrastructure for voice previews:

1. User clicks "Preview" on any voice
2. Frontend calls `POST /interview/interviewers/preview-voice?voice_id=shubh`
3. Backend calls Sarvam TTS via existing `text_to_speech()` function
3. Returns WAV audio to frontend for playback

## Rollback & Error Handling

The service implements automatic rollback on failure:

```python
try:
    llm = client.llm.create(...)
    agent = client.agent.create(llm_id=llm.llm_id, ...)
    db.save(interviewer)
except Exception as e:
    # Cleanup created resources
    if agent_id: client.agent.delete(agent_id)
    if llm_id: client.llm.delete(llm_id)
    raise InterviewerServiceError(...)
```

## Integration with Existing Interviewers

Static interviewers (Arjun, Kavya, Ishita, Priya) continue working unchanged:

- Defined in `interviewer_profiles.py`
- Use global `RETELL_AGENT_ID` with per-interviewer `agent_override`
- Appear in `/interview/interviewers` list alongside dynamic interviewers
- Marked with `is_dynamic: false` in API response

## Frontend UI

### Admin Management Page (`/admin/interviewers`)

Features:
- **Tabbed interface**: List / Create / Edit
- **Card grid layout**: Shows avatar, name, title, tagline, voice, status
- **Filters**: Show/hide inactive interviewers
- **Create/Edit form**: All fields with validation
- **Voice selector**: Dropdown with preview buttons
- **Voice preview**: Play any voice before selecting
- **Accent color picker**: Tailwind color palette
- **Avatar**: Initials + color + optional image URL
- **Inline validation**: Real-time error display

### Candidate Interview Setup

The existing `/resume-upload` flow now shows both static and dynamic interviewers in the selection step. Dynamic interviewers appear with `is_dynamic: true` badge.

## Deployment Checklist

### Backend
- [ ] Add `retell-sdk` to requirements.txt
- [ ] Run Alembic migration for `dynamic_interviewers` table
- [ ] Set `RETELL_API_KEY` in environment
- [ ] Set `RETELL_AGENT_ID` (global fallback agent)
- [ ] Set `RETELL_LLM_WEBSOCKET_URL` (for custom LLM WebSocket)
- [ ] Verify webhook URL configured in Retell dashboard

### Frontend
- [ ] Build and deploy updated frontend
- [ ] Test voice preview with different voices
- [ ] Verify dynamic interviewers appear in candidate setup

## Testing Checklist

### Backend Tests
- [ ] Create interviewer → Retell LLM + Agent created
- [ ] Invalid voice → 400, no resources created
- [ ] Retell LLM failure → 502, cleanup attempted
- [ ] Retell Agent failure → 500, LLM cleanup attempted
- [ ] DB failure after Retell → cleanup attempted
- [ ] Unauthorized user → 403
- [ ] Double submit → one interviewer, one agent
- [ ] Create → fetch roster → appears in list
- [ ] Create → select → start interview → correct agent used

### Frontend Tests
- [ ] Voice preview plays audio
- [ ] Form validation works
- [ ] Edit form pre-populates correctly
- [ ] Deactivate confirmation works
- [ ] Dynamic interviewer appears in candidate setup
- [ ] Interview starts with correct agent

## Files Created/Modified

### New Files
- `app/models/interview.py` - Added `DynamicInterviewer` model
- `app/modules/interview/services/interviewer_service.py` - Retell integration service
- `app/modules/interview/routers/interviewer_management.py` - Admin API endpoints
- `frontend/src/pages/InterviewerManagement.jsx` - Admin UI component

### Modified Files
- `app/models/__init__.py` - Export `DynamicInterviewer`
- `app/models/interview.py` - Add `DynamicInterviewer` class
- `app/modules/interview/routers/__init__.py` - Export new router
- `app/modules/interview/routers/interview_router.py` - Include router, update list/start endpoints
- `app/modules/interview/schemas/interview_schema.py` - Add `is_dynamic` field
- `app/config/settings.py` - Document Retell settings
- `requirements.txt` - Add `retell-sdk`
- `app/modules/interview/services/interview_service.py` - Add management API functions
- `frontend/src/services/interviewService.js` - Add management API calls
- `frontend/src/App.jsx` - Add route and import
- `frontend/src/pages/InterviewerManagement.jsx` - Admin UI component

## Migration

```bash
# Generate migration
alembic revision --autogenerate -m "Add dynamic_interviewers table"

# Apply migration
alembic upgrade head
```

## Future Enhancements

1. **Agent Versioning**: Support multiple versions of interviewer agents
2. **Voice Cloning**: Integrate custom voice training
3. **Analytics Dashboard**: Interviewer usage statistics
4. **Bulk Operations**: Import/export interviewer configs
5. **Template System**: Pre-built interviewer templates
6. **A/B Testing**: Compare interviewer effectiveness