# IntelliHire — Interview Database Schema

## Entity Relationship Overview
- One `interview_sessions` has many `interview_questions`.
- Each `interview_questions` row has one or zero `interview_answers`.
- `interview_evaluation` is one-per-session summarizing results.
- `proctoring_violations` belong to `interview_sessions`.
- RL artifacts:
  - `rl_q_table` stores Q-values per `user_id` + `state` + `action`.
  - `rl_attempt_log` stores per-question RL attempt history linking user/session/question.

ER diagram (textual):
interview_sessions (1) — (N) interview_questions — (1) — (1) interview_answers
interview_sessions (1) — (N) proctoring_violations
interview_sessions (1) — (1) interview_evaluation

## Table Definitions (field types and constraints)

Note: Types shown are PostgreSQL primary types. For SQLite use compatible mappings in Migration Notes.

1) interview_sessions
- id: UUID PRIMARY KEY
- user_id: UUID NOT NULL
- role: VARCHAR(64) NOT NULL
- start_time: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- end_time: TIMESTAMP WITH TIME ZONE NULL
- status: VARCHAR(32) NOT NULL CHECK(status IN ('IDLE','INITIALIZING','PERMISSION_CHECK','READY','QUESTION_ASKED','RECORDING','PROCESSING','EVALUATING','NEXT_QUESTION','COMPLETED','TERMINATED'))
- answer_mode: VARCHAR(16) NOT NULL CHECK(answer_mode IN ('voice','text'))
- current_question_index: INTEGER NOT NULL DEFAULT 0
- total_score: NUMERIC(6,2) NULL
- warning_count: INTEGER NOT NULL DEFAULT 0
- session_token: TEXT UNIQUE NOT NULL
- last_activity_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

2) interview_questions
- id: UUID PRIMARY KEY
- session_id: UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE
- question_text: TEXT NOT NULL
- difficulty: VARCHAR(8) NOT NULL CHECK(difficulty IN ('easy','medium','hard'))
- category: VARCHAR(64) NULL
- time_limit: INTEGER NOT NULL DEFAULT 120  -- seconds
- question_index: INTEGER NOT NULL
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

Unique constraint: (session_id, question_index)

3) interview_answers
- id: UUID PRIMARY KEY
- question_id: UUID NOT NULL REFERENCES interview_questions(id) ON DELETE CASCADE
- answer_text: TEXT NULL
- answer_audio_url: TEXT NULL
- ai_feedback: TEXT NULL
- scores: JSONB NOT NULL  -- structure: {"technical":float,"communication":float,"confidence":float,"problem_solving":float,"total":float}
- response_time: INTEGER NOT NULL  -- milliseconds
- is_skipped: BOOLEAN NOT NULL DEFAULT FALSE
- submitted_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

4) interview_evaluation
- id: UUID PRIMARY KEY
- session_id: UUID NOT NULL UNIQUE REFERENCES interview_sessions(id) ON DELETE CASCADE
- technical_score: NUMERIC(5,2) NOT NULL
- communication_score: NUMERIC(5,2) NOT NULL
- confidence_score: NUMERIC(5,2) NOT NULL
- problem_solving_score: NUMERIC(5,2) NOT NULL
- total_score: NUMERIC(6,2) NOT NULL
- penalty_points: INTEGER NOT NULL DEFAULT 0
- final_score: NUMERIC(6,2) NOT NULL
- summary: TEXT NULL
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

5) proctoring_violations
- id: UUID PRIMARY KEY
- session_id: UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE
- event_type: VARCHAR(64) NOT NULL  -- e.g., 'tab_switch','webcam_missing','multiple_faces','copy_paste'
- timestamp: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- screenshot_url: TEXT NULL
- warning_number: INTEGER NOT NULL

Index: (session_id, warning_number)

6) rl_q_table
- user_id: UUID NOT NULL
- state: VARCHAR(128) NOT NULL  -- "medium|2|0|fast|high"
- action: VARCHAR(16) NOT NULL CHECK(action IN ('increase','same','decrease'))
- q_value: NUMERIC(10,6) NOT NULL DEFAULT 0.1
- visit_count: INTEGER NOT NULL DEFAULT 0
- updated_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
Primary key: (user_id, state, action)

7) rl_attempt_log
- id: UUID PRIMARY KEY
- user_id: UUID NOT NULL
- session_id: UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE
- question_id: UUID NULL REFERENCES interview_questions(id)
- difficulty: VARCHAR(8) NOT NULL
- state_before: VARCHAR(128) NOT NULL
- action_taken: VARCHAR(16) NOT NULL
- reward: NUMERIC(5,2) NOT NULL
- state_after: VARCHAR(128) NOT NULL
- response_time: INTEGER NOT NULL -- milliseconds
- is_correct: BOOLEAN NOT NULL
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

## Indexes (which columns and why)
- interview_sessions: index on (`user_id`) for quick session lookup.
- interview_questions: index on (`session_id`, `question_index`) for next-question queries.
- interview_answers: index on (`question_id`) for fast retrieval.
- interview_evaluation: index on (`session_id`) unique for aggregation fetches.
- proctoring_violations: index on (`session_id`, `timestamp`) to query recent events.
- rl_q_table: primary (user_id, state, action) and index on (`user_id`, `state`) for RL lookups.
- rl_attempt_log: index on (`user_id`, `session_id`, `created_at`) for analytics.

## Relationships (FK references)
- `interview_questions.session_id` → `interview_sessions.id`
- `interview_answers.question_id` → `interview_questions.id`
- `interview_evaluation.session_id` → `interview_sessions.id`
- `proctoring_violations.session_id` → `interview_sessions.id`
- `rl_attempt_log.session_id` → `interview_sessions.id`
- `rl_attempt_log.question_id` → `interview_questions.id` (nullable)

## Sample Data
1) interview_sessions (3 rows)
- {id: "11111111-1111-1111-1111-111111111111", user_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", role:"backend_engineer", start_time: "2026-05-25T09:00:00Z", status:"READY", answer_mode:"voice", current_question_index:2, total_score: null, warning_count:0, session_token:"sess_tok_abc123"}
- {id: "22222222-2222-2222-2222-222222222222", user_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", role:"frontend_engineer", start_time:"2026-05-25T10:00:00Z", status:"COMPLETED", answer_mode:"text", current_question_index:10, total_score:82.50, warning_count:1, session_token:"sess_tok_def456"}
- {id: "33333333-3333-3333-3333-333333333333", user_id: "cccccccc-cccc-cccc-cccc-cccccccccccc", role:"data_scientist", start_time:"2026-05-25T11:00:00Z", status:"TERMINATED", answer_mode:"voice", current_question_index:4, total_score: null, warning_count:3, session_token:"sess_tok_ghi789"}

2) interview_questions (sample for session 1111)
- {id:"q1-1111", session_id:"11111111-1111-1111-1111-111111111111", question_text:"Implement a debounce function in JS.", difficulty:"medium", category:"algorithms", time_limit:120, question_index:0}
- {id:"q1-1112", session_id:"11111111-1111-1111-1111-111111111111", question_text:"Explain ACID vs BASE.", difficulty:"easy", category:"databases", time_limit:90, question_index:1}
- {id:"q1-1113", session_id:"11111111-1111-1111-1111-111111111111", question_text:"Design a rate limiter for APIs.", difficulty:"hard", category:"systems", time_limit:180, question_index:2}

3) interview_answers
- {id:"a1-1111", question_id:"q1-1111", answer_text:"Use setTimeout clearTimeout...", answer_audio_url:null, ai_feedback:"Good explanation.", scores:{"technical":8.0,"communication":7.5,"confidence":7.0,"problem_solving":7.5,"total":7.75}, response_time:45000, is_skipped:false, submitted_at:"2026-05-25T09:05:00Z"}

4) rl_q_table (sample)
- {user_id:"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", state:"medium|2|0|fast|high", action:"increase", q_value:0.12, visit_count:5, updated_at:"2026-05-25T09:05:01Z"}
- {user_id:"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", state:"medium|2|0|fast|high", action:"same", q_value:0.10, visit_count:12, updated_at:"2026-05-25T09:04:59Z"}

5) proctoring_violations
- {id:"pv1", session_id:"33333333-3333-3333-3333-333333333333", event_type:"tab_switch", timestamp:"2026-05-25T11:10:00Z", screenshot_url:null, warning_number:1}

## SQLite vs PostgreSQL Differences
- JSONB: PostgreSQL `JSONB` → SQLite `TEXT` storing JSON string; use SQLAlchemy `JSON` type or custom serializer.
- UUID: PostgreSQL `UUID` → SQLite `TEXT` with UUID strings.
- TIMESTAMP WITH TIME ZONE: SQLite stores as `TEXT` ISO8601; enforce UTC in app layer.
- Check constraints: SQLite supports limited check enforcement; prefer app-level validation for enums.
- ARRAY: PostgreSQL `ARRAY` not used; avoid arrays; convert to comma-separated TEXT in SQLite if required.

## Migration Notes
- Add migrations for `rl_q_table` PK (user_id,state,action) and optimistic init default 0.1.
- When migrating `JSONB` columns (scores) to SQLite, ensure cast to text and validate JSON on read/write.
- Ensure `visit_count` non-null default 0 on all rows.
- Add migration to add `epsilon` column to `rl_q_table` if persistence of epsilon is implemented to fix the in-memory reset bug.
